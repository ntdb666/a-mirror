"""
缓存清理后台任务

每天凌晨2点自动运行清理任务
"""

import asyncio
import logging
from datetime import datetime, time as dt_time, timedelta
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


class CacheCleanupScheduler:
    """缓存清理调度器"""
    
    def __init__(self, cleanup_time: dt_time = dt_time(2, 0), expiry_days: int = 30):
        """
        初始化调度器
        
        Args:
            cleanup_time: 每天运行清理的时间（默认凌晨2点）
            expiry_days: 缓存过期天数（默认30天）
        """
        self.cleanup_time = cleanup_time
        self.expiry_days = expiry_days
        self._task = None
        self._running = False
    
    async def _schedule_loop(self):
        """调度循环"""
        while self._running:
            try:
                # 计算到下次运行的等待时间
                wait_seconds = self._calculate_wait_time()
                next_run = datetime.now() + timedelta(seconds=wait_seconds)
                
                # 等待到运行时间
                await asyncio.sleep(wait_seconds)
                
                # 运行清理任务
                if self._running:  # 再次检查是否仍在运行
                    await self._run_cleanup()
                
            except asyncio.CancelledError:
                logger.info("Cache cleanup scheduler cancelled")
                break
            except Exception as e:
                logger.error(f"Error in cleanup scheduler loop: {e}", exc_info=True)
                # 发生错误时等待1小时后重试
                await asyncio.sleep(3600)
    
    def _calculate_wait_time(self) -> float:
        """
        计算到下次运行时间的等待秒数
        
        Returns:
            等待秒数
        """
        now = datetime.now()
        
        # 计算今天的目标时间
        target = datetime.combine(now.date(), self.cleanup_time)
        
        # 如果今天的目标时间已经过了，改为明天
        if now.time() >= self.cleanup_time:
            target = target + timedelta(days=1)
        
        wait_seconds = (target - now).total_seconds()
        return wait_seconds
    
    async def _run_cleanup(self):
        """运行清理脚本"""
        try:
            # 查找清理脚本路径
            script_path = Path("/app/scripts/cache_cleanup.py")
            
            if not script_path.exists():
                logger.error(f"Cleanup script not found: {script_path}")
                return
            
            # 运行清理脚本
            result = await asyncio.create_subprocess_exec(
                sys.executable,
                str(script_path),
                "--days", str(self.expiry_days),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                logger.error(
                    f"Cache cleanup failed with exit code {result.returncode}\n"
                    f"stderr: {stderr.decode()}"
                )
        
        except Exception as e:
            logger.error(f"Failed to run cache cleanup: {e}", exc_info=True)
    
    def start(self):
        """启动调度器"""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._schedule_loop())
    
    def stop(self):
        """停止调度器"""
        if not self._running:
            return
        
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()


# 全局调度器实例
_scheduler: CacheCleanupScheduler = None


def get_scheduler(cleanup_time: dt_time = None, expiry_days: int = None) -> CacheCleanupScheduler:
    """
    获取全局调度器实例
    
    Args:
        cleanup_time: 清理时间（仅在首次调用时使用）
        expiry_days: 过期天数（仅在首次调用时使用）
    
    Returns:
        CacheCleanupScheduler 实例
    """
    global _scheduler
    
    if _scheduler is None:
        from mirrorsrun.config import CACHE_EXPIRY_DAYS
        
        _scheduler = CacheCleanupScheduler(
            cleanup_time=cleanup_time or dt_time(2, 0),
            expiry_days=expiry_days or CACHE_EXPIRY_DAYS
        )
    
    return _scheduler


async def start_cleanup_scheduler():
    """
    启动缓存清理调度器的便捷函数
    
    在 FastAPI 的 startup 事件中调用此函数
    """
    scheduler = get_scheduler()
    scheduler.start()

