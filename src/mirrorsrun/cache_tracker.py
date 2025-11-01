import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional
from threading import Lock

logger = logging.getLogger(__name__)


class CacheAccessTracker:
    """缓存文件访问时间追踪器"""
    
    def __init__(self, tracking_file: str = "/app/data/cache_access.json"):
        self.tracking_file = tracking_file
        self._data: Dict[str, str] = {}
        self._lock = Lock()  # 线程安全锁
        self._ensure_tracking_file()
        self._load()
    
    def _ensure_tracking_file(self):
        """确保追踪文件目录存在"""
        tracking_dir = os.path.dirname(self.tracking_file)
        if tracking_dir:
            Path(tracking_dir).mkdir(parents=True, exist_ok=True)
        
        # 如果文件不存在，创建空的 JSON 对象
        if not os.path.exists(self.tracking_file):
            try:
                with open(self.tracking_file, 'w', encoding='utf-8') as f:
                    json.dump({}, f)
            except Exception as e:
                logger.error(f"Failed to initialize tracking file: {e}")
    
    def _load(self):
        """从文件加载追踪数据"""
        try:
            with open(self.tracking_file, 'r', encoding='utf-8') as f:
                self._data = json.load(f)
                if not isinstance(self._data, dict):
                    logger.warning("Invalid tracking data format, resetting to empty dict")
                    self._data = {}
        except (json.JSONDecodeError, FileNotFoundError):
            logger.warning("Failed to load tracking data, starting fresh")
            self._data = {}
        except Exception as e:
            logger.error(f"Error loading tracking data: {e}")
            self._data = {}
    
    def _save(self):
        """保存追踪数据到文件"""
        try:
            # 原子写入：先写入临时文件，再重命名
            temp_file = self.tracking_file + '.tmp'
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            
            # 重命名以确保原子性
            os.replace(temp_file, self.tracking_file)
        except Exception as e:
            logger.error(f"Failed to save tracking data: {e}")
    
    def update_access_time(self, cache_file_path: str, access_time: Optional[datetime] = None):
        """
        更新文件的访问时间
        
        Args:
            cache_file_path: 缓存文件的完整路径
            access_time: 访问时间（默认使用当前时间）
        """
        if access_time is None:
            access_time = datetime.now(timezone.utc)
        
        timestamp = access_time.isoformat().replace('+00:00', 'Z')
        
        with self._lock:
            self._data[cache_file_path] = timestamp
            self._save()
    
    def get_last_access_time(self, cache_file_path: str) -> Optional[datetime]:
        """
        获取文件的最后访问时间
        
        Args:
            cache_file_path: 缓存文件的完整路径
            
        Returns:
            最后访问时间，如果未追踪则返回 None
        """
        with self._lock:
            timestamp_str = self._data.get(cache_file_path)
            if timestamp_str:
                try:
                    # 处理带 Z 后缀的 UTC 时间
                    if timestamp_str.endswith('Z'):
                        timestamp_str = timestamp_str[:-1] + '+00:00'
                    return datetime.fromisoformat(timestamp_str)
                except ValueError as e:
                    logger.warning(f"Invalid timestamp format for {cache_file_path}: {e}")
                    return None
            return None
    
    def get_all_tracked_files(self) -> Dict[str, datetime]:
        """
        获取所有被追踪的文件及其访问时间
        
        Returns:
            字典，键为文件路径，值为访问时间
        """
        result = {}
        with self._lock:
            for file_path, timestamp_str in self._data.items():
                try:
                    # 处理带 Z 后缀的 UTC 时间
                    if timestamp_str.endswith('Z'):
                        timestamp_str = timestamp_str[:-1] + '+00:00'
                    result[file_path] = datetime.fromisoformat(timestamp_str)
                except ValueError as e:
                    logger.warning(f"Invalid timestamp for {file_path}: {e}")
                    continue
        return result
    
    def remove_tracking(self, cache_file_path: str):
        """
        移除文件的追踪记录
        
        Args:
            cache_file_path: 缓存文件的完整路径
        """
        with self._lock:
            if cache_file_path in self._data:
                del self._data[cache_file_path]
                self._save()
    
    def initialize_from_filesystem(self, cache_dir: str):
        """
        扫描缓存目录，为现有文件初始化访问时间
        使用当前时间作为初始访问时间，确保现有缓存有完整的30天生命周期
        
        Args:
            cache_dir: 缓存目录路径
        """
        if not os.path.exists(cache_dir):
            logger.warning(f"Cache directory does not exist: {cache_dir}")
            return
        
        tracked_files = set(self._data.keys())
        current_time = datetime.now(timezone.utc)
        initialized_count = 0
        
        try:
            for root, dirs, files in os.walk(cache_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    
                    # 只处理未追踪的文件
                    if file_path not in tracked_files:
                        try:
                            # 验证文件确实存在且可读
                            if os.path.isfile(file_path) and os.access(file_path, os.R_OK):
                                # 使用当前时间作为访问时间
                                self._data[file_path] = current_time.isoformat().replace('+00:00', 'Z')
                                initialized_count += 1
                        except Exception as e:
                            logger.warning(f"Failed to initialize tracking for {file_path}: {e}")
        except Exception as e:
            logger.error(f"Error scanning cache directory: {e}")
        
        if initialized_count > 0:
            self._save()
            logger.info(f"Initialized tracking for {initialized_count} existing cache files with current time")
        else:
            logger.info("No new cache files to initialize")


# 全局单例实例
cache_tracker: Optional[CacheAccessTracker] = None


def get_cache_tracker(tracking_file: Optional[str] = None) -> CacheAccessTracker:
    """
    获取全局 CacheAccessTracker 实例
    
    Args:
        tracking_file: 追踪文件路径（仅在首次调用时使用）
        
    Returns:
        CacheAccessTracker 实例
    """
    global cache_tracker
    if cache_tracker is None:
        from mirrorsrun.config import CACHE_ACCESS_TRACKING_FILE
        cache_tracker = CacheAccessTracker(tracking_file or CACHE_ACCESS_TRACKING_FILE)
    return cache_tracker

