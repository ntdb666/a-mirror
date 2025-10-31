import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
import hashlib

logger = logging.getLogger(__name__)


@dataclass
class PackageInfo:
    """单个包的信息"""
    name: str
    size_mb: float
    cache_hit: bool
    download_time: float
    start_time: float
    end_time: float


@dataclass
class InstallSession:
    """安装会话数据"""
    session_id: str
    user_agent: str
    client_ip: str
    start_time: float
    last_activity: float
    packages: List[PackageInfo] = field(default_factory=list)
    
    def add_package(self, package: PackageInfo):
        """添加包到会话"""
        self.packages.append(package)
        self.last_activity = time.time()
    
    def is_expired(self, timeout: int = 5) -> bool:
        """检查会话是否超时"""
        return (time.time() - self.last_activity) > timeout
    
    def get_total_time(self) -> float:
        """获取总时间（从第一个包到最后一个包）"""
        if not self.packages:
            return 0.0
        return self.packages[-1].end_time - self.packages[0].start_time
    
    def get_main_package_name(self) -> str:
        """推测主包名称"""
        if not self.packages:
            return "unknown"
        
        # 优先使用第一个包
        first_pkg = self.packages[0].name
        
        # 去掉版本号和扩展名
        main_name = first_pkg.split('-')[0]
        return main_name
    
    def get_total_size_mb(self) -> float:
        """获取总大小"""
        return sum(pkg.size_mb for pkg in self.packages)
    
    def get_downloaded_size_mb(self) -> float:
        """获取实际下载的大小（不含缓存命中）"""
        return sum(pkg.size_mb for pkg in self.packages if not pkg.cache_hit)
    
    def get_cache_hit_count(self) -> int:
        """获取缓存命中数"""
        return sum(1 for pkg in self.packages if pkg.cache_hit)
    
    def get_cache_hit_rate(self) -> float:
        """获取缓存命中率"""
        if not self.packages:
            return 0.0
        return self.get_cache_hit_count() / len(self.packages)
    
    def get_avg_download_speed_mbs(self) -> float:
        """获取平均下载速度（仅计算实际下载的包）"""
        downloaded_pkgs = [pkg for pkg in self.packages if not pkg.cache_hit]
        if not downloaded_pkgs:
            return 0.0
        
        total_size = sum(pkg.size_mb for pkg in downloaded_pkgs)
        total_time = sum(pkg.download_time for pkg in downloaded_pkgs)
        
        if total_time <= 0:
            return 0.0
        return total_size / total_time


class SessionManager:
    """会话管理器（单例）"""
    _instance = None
    _lock = asyncio.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.sessions: Dict[str, InstallSession] = {}
        self.session_lock = asyncio.Lock()
        self._initialized = True
        self._cleanup_task = None
        logger.info("SessionManager initialized")
    
    def _generate_session_id(self, user_agent: str, client_ip: str) -> str:
        """生成会话 ID"""
        # 使用 user-agent + client-ip + 时间窗口（秒级）生成 session key
        time_window = int(time.time() / 5)  # 每5秒一个时间窗口
        key = f"{user_agent}:{client_ip}:{time_window}"
        return hashlib.md5(key.encode()).hexdigest()[:12]
    
    async def record_package(
        self,
        user_agent: str,
        client_ip: str,
        package_name: str,
        size_mb: float,
        cache_hit: bool,
        download_time: float,
        start_time: float,
        end_time: float
    ):
        """记录包信息到会话"""
        async with self.session_lock:
            session_id = self._generate_session_id(user_agent, client_ip)
            
            # 获取或创建会话
            if session_id not in self.sessions:
                self.sessions[session_id] = InstallSession(
                    session_id=session_id,
                    user_agent=user_agent,
                    client_ip=client_ip,
                    start_time=start_time,
                    last_activity=time.time()
                )
                logger.debug(f"Created new session: {session_id}")
            
            session = self.sessions[session_id]
            
            # 添加包信息
            package_info = PackageInfo(
                name=package_name,
                size_mb=size_mb,
                cache_hit=cache_hit,
                download_time=download_time,
                start_time=start_time,
                end_time=end_time
            )
            session.add_package(package_info)
            
            logger.debug(
                f"Added package to session {session_id}: {package_name} "
                f"(packages: {len(session.packages)})"
            )
    
    async def finalize_session(self, session_id: str, metrics_recorder=None):
        """完成会话并输出汇总日志"""
        async with self.session_lock:
            if session_id not in self.sessions:
                return
            
            session = self.sessions[session_id]
            
            # 至少要有一个包才输出
            if not session.packages:
                del self.sessions[session_id]
                return
            
            # 输出汇总日志
            self._log_session_summary(session)
            
            # 记录到 JSON（如果提供了 metrics_recorder）
            if metrics_recorder:
                self._record_session_to_json(session, metrics_recorder)
            
            # 清理会话
            del self.sessions[session_id]
            logger.debug(f"Finalized and removed session: {session_id}")
    
    def _log_session_summary(self, session: InstallSession):
        """输出会话汇总日志"""
        main_package = session.get_main_package_name()
        total_time = session.get_total_time()
        package_count = len(session.packages)
        total_size = session.get_total_size_mb()
        downloaded_size = session.get_downloaded_size_mb()
        cache_hit_count = session.get_cache_hit_count()
        cache_hit_rate = session.get_cache_hit_rate()
        avg_speed = session.get_avg_download_speed_mbs()
        
        # 主汇总行
        summary_line = (
            f"[INSTALL-SUMMARY] {main_package} 安装完成 | "
            f"总时间: {total_time:.1f}s | "
            f"包数: {package_count} | "
            f"总大小: {total_size:.2f}MB | "
            f"下载: {downloaded_size:.2f}MB | "
            f"缓存命中: {cache_hit_count}/{package_count} ({cache_hit_rate*100:.1f}%)"
        )
        
        if avg_speed > 0:
            summary_line += f" | 平均速度: {avg_speed:.2f}MB/s"
        
        logger.info(summary_line)
        
        # 包列表详情
        for pkg in session.packages:
            status = "缓存" if pkg.cache_hit else "下载"
            logger.info(
                f"  └─ {pkg.name} ({pkg.size_mb:.2f}MB, {status}, {pkg.download_time:.2f}s)"
            )
    
    def _record_session_to_json(self, session: InstallSession, metrics_recorder):
        """记录会话到 JSON"""
        from datetime import timezone
        
        start_dt = datetime.fromtimestamp(session.start_time, tz=timezone.utc)
        end_dt = datetime.fromtimestamp(session.packages[-1].end_time, tz=timezone.utc)
        
        session_data = {
            "type": "install_session",
            "session_id": session.session_id,
            "timestamp_start": start_dt.isoformat(),
            "timestamp_end": end_dt.isoformat(),
            "total_time": round(session.get_total_time(), 3),
            "main_package": session.get_main_package_name(),
            "package_count": len(session.packages),
            "total_size_mb": round(session.get_total_size_mb(), 2),
            "downloaded_size_mb": round(session.get_downloaded_size_mb(), 2),
            "cache_hit_count": session.get_cache_hit_count(),
            "cache_hit_rate": round(session.get_cache_hit_rate(), 3),
            "avg_download_speed_mbs": round(session.get_avg_download_speed_mbs(), 2),
            "packages": [
                {
                    "name": pkg.name,
                    "size_mb": round(pkg.size_mb, 2),
                    "cache_hit": pkg.cache_hit,
                    "time": round(pkg.download_time, 3)
                }
                for pkg in session.packages
            ],
            "user_agent": session.user_agent,
            "client_ip": session.client_ip
        }
        
        # 直接追加到 JSON 文件
        metrics_recorder._append_to_json(session_data)
    
    async def check_expired_sessions(self, timeout: int = 5, metrics_recorder=None):
        """检查并完成过期的会话"""
        async with self.session_lock:
            expired_sessions = [
                session_id
                for session_id, session in self.sessions.items()
                if session.is_expired(timeout)
            ]
        
        # 在锁外处理过期会话，避免死锁
        for session_id in expired_sessions:
            await self.finalize_session(session_id, metrics_recorder)
    
    async def start_cleanup_task(self, timeout: int = 5, metrics_recorder=None):
        """启动后台清理任务"""
        if self._cleanup_task is not None:
            return
        
        async def cleanup_loop():
            while True:
                try:
                    await asyncio.sleep(2)  # 每2秒检查一次
                    await self.check_expired_sessions(timeout, metrics_recorder)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error in cleanup task: {e}", exc_info=True)
        
        self._cleanup_task = asyncio.create_task(cleanup_loop())
        logger.info("Session cleanup task started")
    
    def stop_cleanup_task(self):
        """停止后台清理任务"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            self._cleanup_task = None
            logger.info("Session cleanup task stopped")


# 全局单例
session_manager = SessionManager()

