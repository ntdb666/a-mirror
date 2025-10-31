import logging
import os
import pathlib
import typing
import time
from asyncio import sleep
from enum import Enum
from urllib.parse import urlparse, quote

import httpx
from starlette.requests import Request
from starlette.responses import Response
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR, HTTP_504_GATEWAY_TIMEOUT

from mirrorsrun.aria2_api import add_download, get_status
from mirrorsrun.config import CACHE_DIR, EXTERNAL_URL_ARIA2, METRICS_FILE
from mirrorsrun.metrics import MetricsRecorder

logger = logging.getLogger(__name__)

# 初始化指标记录器
metrics_recorder = MetricsRecorder(METRICS_FILE)


def get_cache_file_and_folder(url: str) -> typing.Tuple[str, str]:
    parsed_url = urlparse(url)
    hostname = parsed_url.hostname
    path = parsed_url.path
    assert hostname
    assert path

    base_dir = pathlib.Path(CACHE_DIR)
    assert parsed_url.path[0] == "/"
    assert parsed_url.path[-1] != "/"
    cache_file = (base_dir / hostname / path[1:]).resolve()

    assert cache_file.is_relative_to(base_dir)

    return str(cache_file), os.path.dirname(cache_file)


class DownloadingStatus(Enum):
    DOWNLOADING = 1
    DOWNLOADED = 2
    NOT_FOUND = 3


def lookup_cache(url: str) -> DownloadingStatus:
    cache_file, _ = get_cache_file_and_folder(url)

    cache_file_aria2 = f"{cache_file}.aria2"
    if os.path.exists(cache_file_aria2):
        return DownloadingStatus.DOWNLOADING

    if os.path.exists(cache_file):
        assert not os.path.isdir(cache_file)
        return DownloadingStatus.DOWNLOADED
    return DownloadingStatus.NOT_FOUND


def make_cached_response(url):
    cache_file, _ = get_cache_file_and_folder(url)

    assert os.path.exists(cache_file)
    assert not os.path.isdir(cache_file)
    with open(cache_file, "rb") as f:
        content = f.read()
        return Response(content=content, status_code=200)


async def get_url_content_length(url):
    async with httpx.AsyncClient() as client:
        head_response = await client.head(url)
        content_len = head_response.headers.get("content-length", None)
        return content_len


async def try_file_based_cache(
    request: Request,
    target_url: str,
    download_wait_time: int = 60,
) -> Response:
    # 记录请求开始时间
    start_time = time.time()
    package_name = os.path.basename(urlparse(target_url).path)
    
    cache_status = lookup_cache(target_url)
    cache_file, cache_file_dir = get_cache_file_and_folder(target_url)
    
    # 场景 1: 缓存命中
    if cache_status == DownloadingStatus.DOWNLOADED:
        logger.info(f"Cache hit for {target_url}")
        response = make_cached_response(target_url)
        
        # 记录缓存命中指标
        total_time = time.time() - start_time
        file_size = os.path.getsize(cache_file)
        
        # 注意：缓存命中时，total_time 只是服务器读取文件的时间，
        # 不包括网络传输时间，所以不记录 client_receive_speed
        metrics_recorder.record_metric(
            url=target_url,
            package_name=package_name,
            file_size=file_size,
            cache_hit=True,
            total_time=total_time,
            status="success",
        )
        
        return response

    # 场景 2: 正在下载中
    if cache_status == DownloadingStatus.DOWNLOADING:
        logger.info(f"Download is not finished, return 504 for {target_url}")
        return Response(
            content=f"This file is downloading, view it at {EXTERNAL_URL_ARIA2}",
            status_code=HTTP_504_GATEWAY_TIMEOUT,
        )

    # 场景 3: 缓存未命中，需要下载
    assert cache_status == DownloadingStatus.NOT_FOUND

    logger.info(f"prepare to cache, {target_url=} {cache_file=} {cache_file_dir=}")

    processed_url = quote(target_url, safe="/:?=&%")

    try:
        # 提交 aria2 下载任务并获取 GID
        gid = await add_download(
            processed_url,
            save_dir=cache_file_dir,
            out_file=os.path.basename(cache_file),
            headers={
                key: value
                for key, value in request.headers.items()
                if key in ["user-agent", "accept", "authorization"]
            },
        )
        logger.info(f"[Aria2] Download task created, GID: {gid}")
    except Exception as e:
        logger.error(f"Download error, return 500 for {target_url}", exc_info=e)
        
        # 记录下载错误
        total_time = time.time() - start_time
        metrics_recorder.record_metric(
            url=target_url,
            package_name=package_name,
            file_size=0,
            cache_hit=False,
            total_time=total_time,
            status="error",
            status_message=str(e),
        )
        
        return Response(
            content=f"Failed to add download: {e}",
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # 等待下载完成，并监控下载速度
    aria2_download_start = time.time()
    last_completed_length = 0
    total_speed_samples = []
    
    for i in range(download_wait_time):
        await sleep(1)
        cache_status = lookup_cache(target_url)
        
        # 检查下载是否完成
        if cache_status == DownloadingStatus.DOWNLOADED:
            aria2_download_time = time.time() - aria2_download_start
            total_time = time.time() - start_time
            file_size = os.path.getsize(cache_file)
            
            # 计算平均下载速度
            aria2_avg_speed = file_size / aria2_download_time if aria2_download_time > 0 else 0
            client_receive_speed = file_size / total_time if total_time > 0 else 0
            
            logger.info(f"[METRICS] Aria2 download completed: {package_name}")
            
            # 记录下载成功指标
            metrics_recorder.record_metric(
                url=target_url,
                package_name=package_name,
                file_size=file_size,
                cache_hit=False,
                total_time=total_time,
                status="success",
                aria2_download_speed=aria2_avg_speed,
                aria2_download_time=aria2_download_time,
                client_receive_speed=client_receive_speed,
            )
            
            logger.info(f"Cache ready for {target_url}")
            return make_cached_response(target_url)
        
        # 定期获取下载状态（每 5 秒一次）
        if i % 5 == 0:
            try:
                status_info = await get_status(gid)
                download_speed = int(status_info.get("downloadSpeed", 0))
                completed_length = int(status_info.get("completedLength", 0))
                total_length = int(status_info.get("totalLength", 0))
                
                if download_speed > 0:
                    total_speed_samples.append(download_speed)
                
                logger.debug(
                    f"[Aria2] GID: {gid} | Speed: {download_speed / (1024*1024):.2f}MB/s | "
                    f"Progress: {completed_length}/{total_length}"
                )
            except Exception as e:
                logger.warning(f"Failed to get aria2 status for GID {gid}: {e}")

    # 场景 4: 超时
    assert cache_status != DownloadingStatus.NOT_FOUND
    
    total_time = time.time() - start_time
    
    # 尝试获取最终状态
    try:
        status_info = await get_status(gid)
        file_size = int(status_info.get("completedLength", 0))
    except Exception:
        file_size = 0
    
    logger.info(f"Download timeout after {download_wait_time}s for {target_url}")
    
    # 记录超时指标
    metrics_recorder.record_metric(
        url=target_url,
        package_name=package_name,
        file_size=file_size,
        cache_hit=False,
        total_time=total_time,
        status="timeout",
        status_message=f"Download not finished after {download_wait_time}s",
    )
    
    return Response(
        content=f"This file is downloading, view it at {EXTERNAL_URL_ARIA2}",
        status_code=HTTP_504_GATEWAY_TIMEOUT,
    )
