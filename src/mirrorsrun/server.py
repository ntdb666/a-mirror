import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))  # noqa: E402

import base64
import signal
import urllib.parse
from typing import Callable
import logging
import ipaddress

import httpx
import uvicorn
from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from starlette.staticfiles import StaticFiles

from mirrorsrun.config import (
    BASE_DOMAIN,
    RPC_SECRET,
    EXTERNAL_URL_ARIA2,
    EXTERNAL_HOST_ARIA2,
    SCHEME, SSL_SELF_SIGNED,
    SERVER_PORT,
    SESSION_TIMEOUT,
    ENABLE_SESSION_SUMMARY,
)

from mirrorsrun.sites.npm import npm
from mirrorsrun.sites.pypi import pypi
from mirrorsrun.sites.torch import torch
from mirrorsrun.sites.docker import dockerhub, k8s, quay, ghcr, nvcr
from mirrorsrun.sites.common import common
from mirrorsrun.sites.goproxy import goproxy

subdomain_mapping = {
    "mirrors": common,
    "pip": pypi,
    "torch": torch,
    "npm": npm,
    "docker": dockerhub,
    "k8s": k8s,
    "ghcr": ghcr,
    "quay": quay,
    "nvcr": nvcr,
    "goproxy": goproxy,
}

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

app = FastAPI()

app.mount(
    "/aria2/",
    StaticFiles(directory="/wwwroot/"),
    name="static",
)


# 启动时的初始化
@app.on_event("startup")
async def startup_event():
    """应用启动时的初始化"""
    if ENABLE_SESSION_SUMMARY:
        from mirrorsrun.session_manager import session_manager
        from mirrorsrun.proxy.file_cache import metrics_recorder
        
        await session_manager.start_cleanup_task(
            timeout=SESSION_TIMEOUT,
            metrics_recorder=metrics_recorder
        )
        logger.info("Session summary feature enabled")


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时的清理"""
    if ENABLE_SESSION_SUMMARY:
        from mirrorsrun.session_manager import session_manager
        session_manager.stop_cleanup_task()
        logger.info("Session cleanup task stopped")


async def aria2(request: Request, call_next):
    if request.url.path == "/":
        return RedirectResponse("/aria2/index.html")
    if request.url.path == "/jsonrpc":
        # dont use proxy for internal API
        async with httpx.AsyncClient(
            mounts={"all://": httpx.AsyncHTTPTransport()}
        ) as client:
            data = await request.body()
            response = await client.request(
                url="http://aria2:6800/jsonrpc",
                method=request.method,
                headers=request.headers,
                content=data,
            )
            headers = response.headers
            headers.pop("content-length", None)
            headers.pop("content-encoding", None)
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=headers,
            )
    return await call_next(request)


def is_ip_address(hostname: str) -> bool:
    """Check if hostname is an IP address"""
    try:
        ipaddress.ip_address(hostname)
        return True
    except ValueError:
        return False


@app.middleware("http")
async def capture_request(request: Request, call_next: Callable):
    hostname = request.url.hostname
    if not hostname:
        return Response(content="Bad Request", status_code=400)

    path = request.url.path

    # Support IP address access via path prefix (e.g., /pip/, /npm/)
    if is_ip_address(hostname):
        # Aria2 access: let FastAPI's static file mount handle /aria2/ paths
        if path.startswith("/aria2/"):
            # For /aria2/jsonrpc, we need special handling
            if path == "/aria2/jsonrpc":
                # Create modified request to proxy to aria2 RPC
                scope = dict(request.scope)
                scope["path"] = "/jsonrpc"
                scope["raw_path"] = b"/jsonrpc"
                modified_request = Request(scope, request.receive)
                return await aria2(modified_request, call_next)
            # Handle root path /aria2/ - should return index.html
            if path == "/aria2/" or path == "/aria2":
                # Return index.html for frontend routing
                scope = dict(request.scope)
                scope["path"] = "/aria2/index.html"
                scope["raw_path"] = b"/aria2/index.html"
                modified_request = Request(scope, request.receive)
                return await call_next(modified_request)
            # Handle paths with hash fragments (frontend routing)
            # For example: /aria2/#!/settings/rpc/set should return index.html
            if "/#" in path:
                # Return index.html for frontend routing
                scope = dict(request.scope)
                scope["path"] = "/aria2/index.html"
                scope["raw_path"] = b"/aria2/index.html"
                modified_request = Request(scope, request.receive)
                return await call_next(modified_request)
            # For other /aria2/ paths, let call_next handle (FastAPI static files)
            return await call_next(request)
        
        # Check for service path prefixes
        for service_name, handler in subdomain_mapping.items():
            prefix = f"/{service_name}/"
            if path.startswith(prefix):
                # Create a new request with the service prefix removed from path
                # This allows handlers to work correctly (e.g., /pip/simple/ -> /simple/)
                new_path = path[len(prefix) - 1:]  # Keep the leading /
                if not new_path.startswith("/"):
                    new_path = "/" + new_path
                
                # Create modified request with new path
                scope = dict(request.scope)
                scope["path"] = new_path
                scope["raw_path"] = new_path.encode()
                modified_request = Request(scope, request.receive)
                
                return await handler(modified_request)
        
        # Default: show available services
        if path == "/" or path == "":
            services_list = "\n".join([f"  /{name}/" for name in subdomain_mapping.keys()])
            return Response(
                content=f"LightMirrors 镜像服务\n\n可用服务:\n{services_list}\n\n示例:\n  /pip/simple/  - PyPI 镜像\n  /npm/  - NPM 镜像\n  /docker/  - Docker 镜像\n  /aria2/  - Aria2 管理界面",
                status_code=200,
                media_type="text/plain; charset=utf-8"
            )
        
        return await call_next(request)

    # Original domain-based routing
    if not hostname.endswith(f".{BASE_DOMAIN}"):
        return await call_next(request)

    if hostname.startswith("aria2."):
        return await aria2(request, call_next)

    subdomain = hostname.split(".")[0]

    if subdomain in subdomain_mapping:
        return await subdomain_mapping[subdomain](request)

    return await call_next(request)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    port = SERVER_PORT
    logger.info(f"Server started at {SCHEME}://*.{BASE_DOMAIN}:{port}")

    for dn in subdomain_mapping.keys():
        logger.info(f" - {SCHEME}://{dn}.{BASE_DOMAIN}:{port}")

    aria2_secret = base64.b64encode(RPC_SECRET.encode()).decode()

    params = {
        "protocol": SCHEME,
        "host": EXTERNAL_HOST_ARIA2,
        "port": str(SERVER_PORT),
        "interface": "jsonrpc",
        "secret": aria2_secret,
    }

    query_string = urllib.parse.urlencode(params)
    aria2_url_with_auth = EXTERNAL_URL_ARIA2 + "#!/settings/rpc/set?" + query_string

    logger.info(f"Download manager (Aria2) at {aria2_url_with_auth}")

    uvicorn.run(
        app="server:app",
        host="0.0.0.0",
        ssl_keyfile='/app/certs/private.key' if SSL_SELF_SIGNED else None,
        ssl_certfile='/app/certs/certificate.pem' if SSL_SELF_SIGNED else None,
        port=SERVER_PORT,
        reload=True,  # TODO: reload only in dev mode
        proxy_headers=not SSL_SELF_SIGNED,  # trust x-forwarded-for etc.
        forwarded_allow_ips="*",
    )
