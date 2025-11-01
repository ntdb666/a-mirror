#!/usr/bin/env python3
"""
缓存清理脚本

自动删除指定天数未被访问的缓存文件。
"""

import sys
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 添加项目路径到 sys.path
sys.path.insert(0, '/app/src')

from mirrorsrun.cache_tracker import CacheAccessTracker
from mirrorsrun.config import CACHE_DIR, DATA_DIR, CACHE_EXPIRY_DAYS, CACHE_ACCESS_TRACKING_FILE


def format_size(size_bytes: int) -> str:
    """格式化文件大小"""
    if size_bytes >= 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
    elif size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.2f} KB"
    else:
        return f"{size_bytes} bytes"


def cleanup_expired_cache(expiry_days: int = 30, dry_run: bool = False):
    """
    清理过期缓存
    
    Args:
        expiry_days: 过期天数（默认30天）
        dry_run: 是否只是模拟运行（不真正删除）
    """
    print("=" * 70)
    print(f"LightMirrors Cache Cleanup - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print(f"Expiry threshold: {expiry_days} days")
    print(f"Mode: {'DRY RUN (no files will be deleted)' if dry_run else 'LIVE (files will be deleted)'}")
    print(f"Tracking file: {CACHE_ACCESS_TRACKING_FILE}")
    print()
    
    # 初始化追踪器
    try:
        tracker = CacheAccessTracker(CACHE_ACCESS_TRACKING_FILE)
    except Exception as e:
        print(f"❌ Failed to initialize cache tracker: {e}")
        return 1
    
    # 计算截止时间
    cutoff_time = datetime.now(timezone.utc) - timedelta(days=expiry_days)
    print(f"Files last accessed before {cutoff_time.strftime('%Y-%m-%d %H:%M:%S UTC')} will be deleted")
    print()
    
    # 扫描所有追踪的文件
    tracked_files = tracker.get_all_tracked_files()
    
    if not tracked_files:
        print("ℹ️  No tracked cache files found")
        return 0
    
    print(f"📊 Total tracked files: {len(tracked_files)}")
    print()
    
    # 分类统计
    expired_files = []
    active_files = []
    missing_files = []
    
    for cache_file, last_access in tracked_files.items():
        if not os.path.exists(cache_file):
            missing_files.append(cache_file)
        elif last_access < cutoff_time:
            file_size = os.path.getsize(cache_file)
            expired_files.append((cache_file, last_access, file_size))
        else:
            active_files.append((cache_file, last_access))
    
    print(f"✅ Active files (accessed within {expiry_days} days): {len(active_files)}")
    print(f"⏰ Expired files (not accessed for {expiry_days}+ days): {len(expired_files)}")
    print(f"⚠️  Missing files (tracked but not found on disk): {len(missing_files)}")
    print()
    
    # 清理缺失的文件记录
    if missing_files:
        print(f"Cleaning up {len(missing_files)} missing file records...")
        for cache_file in missing_files:
            if not dry_run:
                tracker.remove_tracking(cache_file)
            print(f"  🗑️  Removed tracking: {cache_file}")
        print()
    
    # 删除过期文件
    if not expired_files:
        print("✨ No expired files to clean up!")
        return 0
    
    print(f"Processing {len(expired_files)} expired files...")
    print()
    
    deleted_count = 0
    freed_space = 0
    errors = []
    
    # 按大小排序，先显示大文件
    expired_files.sort(key=lambda x: x[2], reverse=True)
    
    for cache_file, last_access, file_size in expired_files:
        days_old = (datetime.now(timezone.utc) - last_access).days
        size_str = format_size(file_size)
        
        print(f"  📁 {os.path.basename(cache_file)}")
        print(f"     Size: {size_str} | Last access: {days_old} days ago")
        
        if not dry_run:
            try:
                os.remove(cache_file)
                tracker.remove_tracking(cache_file)
                deleted_count += 1
                freed_space += file_size
                print(f"     ✅ Deleted")
            except Exception as e:
                errors.append((cache_file, str(e)))
                print(f"     ❌ Error: {e}")
        else:
            deleted_count += 1
            freed_space += file_size
            print(f"     🔍 Would delete")
        
        print()
    
    # 输出总结
    print("=" * 70)
    print("Cleanup Summary")
    print("=" * 70)
    
    if dry_run:
        print(f"💡 DRY RUN MODE - No files were actually deleted")
        print()
        print(f"Would delete: {deleted_count} files")
        print(f"Would free: {format_size(freed_space)}")
    else:
        print(f"✅ Successfully deleted: {deleted_count} files")
        print(f"💾 Space freed: {format_size(freed_space)}")
        
        if errors:
            print(f"❌ Errors encountered: {len(errors)}")
            for cache_file, error in errors:
                print(f"  - {cache_file}: {error}")
    
    print()
    print(f"📊 Remaining active files: {len(active_files)}")
    print(f"📅 Next recommended cleanup: {(datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')}")
    print("=" * 70)
    
    return 0 if not errors else 1


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="LightMirrors Cache Cleanup Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 预览将要删除的文件（不实际删除）
  python3 cache_cleanup.py --dry-run
  
  # 清理30天未访问的文件（默认）
  python3 cache_cleanup.py
  
  # 清理7天未访问的文件
  python3 cache_cleanup.py --days 7
  
  # 清理60天未访问的文件
  python3 cache_cleanup.py --days 60
        """
    )
    
    parser.add_argument(
        "--days",
        type=int,
        default=CACHE_EXPIRY_DAYS,
        help=f"Number of days before considering a file expired (default: {CACHE_EXPIRY_DAYS})"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be deleted without actually deleting files"
    )
    
    args = parser.parse_args()
    
    try:
        exit_code = cleanup_expired_cache(args.days, args.dry_run)
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  Cleanup interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

