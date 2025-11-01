import json
import logging
import os
from datetime import datetime
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class MetricsRecorder:
    """量化数据记录器"""
    
    def __init__(self, metrics_file: str):
        self.metrics_file = metrics_file  # 基础文件路径（用于确定目录）
        self._ensure_data_dir()
    
    def _ensure_data_dir(self):
        """确保数据目录存在"""
        data_dir = os.path.dirname(self.metrics_file)
        if data_dir:
            Path(data_dir).mkdir(parents=True, exist_ok=True)
    
    def _get_metrics_file_for_date(self, date: datetime) -> str:
        """
        获取指定日期的 metrics 文件路径
        
        Args:
            date: 日期时间对象
            
        Returns:
            格式为 metrics-YYYY-MM-DD.json 的文件路径
        """
        date_str = date.strftime("%Y-%m-%d")
        base_dir = os.path.dirname(self.metrics_file)
        return os.path.join(base_dir, f"metrics-{date_str}.json")
    
    def _ensure_metrics_file(self, metrics_file: str):
        """确保指定的 metrics 文件存在"""
        if not os.path.exists(metrics_file):
            try:
                with open(metrics_file, 'w', encoding='utf-8') as f:
                    json.dump([], f)
            except Exception as e:
                logger.error(f"Failed to initialize metrics file: {e}")
    
    def record_metric(
        self,
        url: str,
        package_name: str,
        file_size: int,
        cache_hit: bool,
        total_time: float,
        status: str,
        aria2_download_speed: Optional[float] = None,
        aria2_download_time: Optional[float] = None,
        client_receive_speed: Optional[float] = None,
        status_message: Optional[str] = None,
        record_time: Optional[datetime] = None,
    ):
        """
        记录量化指标
        
        Args:
            url: 请求的完整 URL
            package_name: 包名
            file_size: 文件大小（字节）
            cache_hit: 是否缓存命中
            total_time: 总耗时（秒）
            status: 状态 (success/timeout/error/client_disconnect)
            aria2_download_speed: Aria2 平均下载速度（bytes/s）
            aria2_download_time: Aria2 下载耗时（秒）
            client_receive_speed: 客户端接收速度（bytes/s）
            status_message: 状态说明
            record_time: 记录时间（用于跨天会话，记录到会话开始日期）
        """
        # 使用指定的记录时间或当前时间
        if record_time is None:
            record_time = datetime.utcnow()
        
        timestamp = record_time.isoformat() + 'Z'
        
        # 获取该日期对应的文件
        metrics_file = self._get_metrics_file_for_date(record_time)
        
        # 转换为 MB 和 MB/s 单位
        file_size_mb = file_size / (1024 * 1024)
        
        metric_data = {
            "timestamp": timestamp,
            "url": url,
            "package_name": package_name,
            "file_size_mb": round(file_size_mb, 2),
            "cache_hit": cache_hit,
            "total_time": round(total_time, 3),
            "status": status,
        }
        
        # 添加可选字段（转换为 MB/s）
        if aria2_download_speed is not None:
            aria2_speed_mbs = aria2_download_speed / (1024 * 1024)
            metric_data["aria2_download_speed_mbs"] = round(aria2_speed_mbs, 2)
        if aria2_download_time is not None:
            metric_data["aria2_download_time"] = round(aria2_download_time, 3)
        if client_receive_speed is not None:
            client_speed_mbs = client_receive_speed / (1024 * 1024)
            metric_data["client_receive_speed_mbs"] = round(client_speed_mbs, 2)
        if status_message:
            metric_data["status_message"] = status_message
        
        # 写入对应日期的 JSON 文件
        self._append_to_json(metric_data, metrics_file)
        
        # 输出格式化日志
        self._log_metric(metric_data)
    
    def _append_to_json(self, metric_data: dict, metrics_file: str):
        """
        追加数据到指定的 JSON 文件
        
        Args:
            metric_data: 要追加的指标数据
            metrics_file: 目标文件路径
        """
        try:
            # 确保文件存在
            self._ensure_metrics_file(metrics_file)
            
            # 读取现有数据
            with open(metrics_file, 'r', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                    if not isinstance(data, list):
                        data = []
                except json.JSONDecodeError:
                    data = []
            
            # 追加新数据
            data.append(metric_data)
            
            # 写回文件
            with open(metrics_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        
        except Exception as e:
            logger.error(f"Failed to append metric to JSON file {metrics_file}: {e}")
    
    def _log_metric(self, metric_data: dict):
        """输出格式化的控制台日志"""
        package_name = metric_data["package_name"]
        file_size_mb = metric_data["file_size_mb"]
        total_time = metric_data["total_time"]
        cache_hit = metric_data["cache_hit"]
        status = metric_data["status"]
        
        # 统一使用 MB 作为单位
        size_str = f"{file_size_mb:.2f}MB"
        
        if cache_hit:
            # 缓存命中
            logger.info(
                f"[METRICS] Cache HIT | {package_name} | "
                f"Total: {total_time:.3f}s | Size: {size_str}"
            )
        else:
            # 缓存未命中
            aria2_speed_mbs = metric_data.get("aria2_download_speed_mbs")
            aria2_time = metric_data.get("aria2_download_time")
            
            if aria2_speed_mbs and aria2_time:
                # 统一使用 MB/s 作为速度单位
                log_msg = (
                    f"[METRICS] Cache MISS | {package_name} | "
                    f"Aria2: {aria2_time:.2f}s @ {aria2_speed_mbs:.2f}MB/s | "
                    f"Total: {total_time:.2f}s | Size: {size_str}"
                )
            else:
                log_msg = (
                    f"[METRICS] Cache MISS | {package_name} | "
                    f"Total: {total_time:.2f}s | Size: {size_str}"
                )
            
            if status != "success":
                log_msg += f" | Status: {status}"
                if metric_data.get("status_message"):
                    log_msg += f" ({metric_data['status_message']})"
            
            logger.info(log_msg)


def format_size(size_bytes: int) -> str:
    """格式化文件大小"""
    if size_bytes >= 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f}GB"
    elif size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f}MB"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.2f}KB"
    else:
        return f"{size_bytes}B"

