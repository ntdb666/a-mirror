# 缓存生命周期管理

## 概述

LightMirrors 提供自动化的缓存生命周期管理功能，自动清理长期未使用的缓存文件，保持磁盘空间的高效利用。

## 工作原理

### 访问追踪

系统会追踪每个缓存文件的最后访问时间（即最后一次缓存命中的时间）：

- **追踪文件**: `data/cache_access.json`
- **追踪事件**: 每次缓存命中或首次下载完成时
- **记录内容**: 文件路径 → 最后访问时间（UTC）

**示例**：
```json
{
  "/app/cache/files.pythonhosted.org/packages/.../numpy-1.24.0.whl": "2025-11-01T10:30:00Z",
  "/app/cache/pypi.tuna.tsinghua.edu.cn/packages/.../PyQt5-5.15.11.whl": "2025-11-01T06:33:15Z"
}
```

### 自动清理

系统会在每天凌晨 2:00 自动运行清理任务，删除超过指定天数（默认 30 天）未被访问的缓存文件。

**清理流程**：
1. 读取 `cache_access.json` 获取所有追踪文件
2. 计算每个文件的最后访问时间距今天数
3. 删除超过阈值的文件
4. 从追踪文件中移除已删除文件的记录
5. 记录清理日志

## 配置选项

### 环境变量

在 `docker-compose.yml` 中配置：

```yaml
environment:
  # 缓存过期天数（默认 30 天）
  - CACHE_EXPIRY_DAYS=30
  
  # 是否启用自动清理（默认 true）
  - ENABLE_CACHE_CLEANUP=true
  
  # 访问追踪文件路径（默认 /app/data/cache_access.json）
  - CACHE_ACCESS_TRACKING_FILE=/app/data/cache_access.json
```

### 调整清理时间

清理任务默认在每天凌晨 2:00 运行。如需修改，编辑 `src/mirrorsrun/cache_cleanup_task.py`：

```python
scheduler = CacheCleanupScheduler(
    cleanup_time=dt_time(2, 0),  # 修改为其他时间，例如 dt_time(3, 30) 表示 3:30
    expiry_days=30
)
```

## 手动管理

### 查看清理预览

在不实际删除文件的情况下预览会被清理的内容：

```bash
# Linux/Mac
docker exec lightmirrors python3 /app/scripts/cache_cleanup.py --dry-run

# Windows PowerShell
docker exec lightmirrors python3 /app/scripts/cache_cleanup.py --dry-run
```

### 手动执行清理

立即执行清理（使用默认 30 天配置）：

```bash
docker exec lightmirrors python3 /app/scripts/cache_cleanup.py
```

### 自定义清理阈值

临时使用不同的过期天数：

```bash
# 清理 7 天未使用的文件
docker exec lightmirrors python3 /app/scripts/cache_cleanup.py --days 7

# 清理 60 天未使用的文件
docker exec lightmirrors python3 /app/scripts/cache_cleanup.py --days 60
```

### 查看追踪文件

```bash
# 查看所有被追踪的文件
docker exec lightmirrors cat /app/data/cache_access.json | jq

# 统计追踪的文件数量
docker exec lightmirrors cat /app/data/cache_access.json | jq 'length'

# 查看最近访问的10个文件
docker exec lightmirrors cat /app/data/cache_access.json | jq 'to_entries | sort_by(.value) | reverse | .[0:10]'
```

## 清理日志

清理任务会输出详细的日志信息：

**控制台日志**（Docker logs）：
```
2025-11-01 02:00:00 - mirrorsrun.cache_cleanup_task - INFO - Starting cache cleanup task...
2025-11-01 02:00:05 - mirrorsrun.cache_cleanup_task - INFO - Cache cleanup completed successfully
```

**清理脚本输出**：
```
======================================================================
LightMirrors Cache Cleanup - 2025-11-01 02:00:00
======================================================================
Expiry threshold: 30 days
Mode: LIVE (files will be deleted)
Tracking file: /app/data/cache_access.json

Files last accessed before 2025-10-02 00:00:00 UTC will be deleted

📊 Total tracked files: 150

✅ Active files (accessed within 30 days): 120
⏰ Expired files (not accessed for 30+ days): 28
⚠️  Missing files (tracked but not found on disk): 2

Processing 28 expired files...

  📁 old-package-1.0.0.whl
     Size: 45.23 MB | Last access: 35 days ago
     ✅ Deleted

  📁 another-package-2.1.0.whl
     Size: 12.87 MB | Last access: 40 days ago
     ✅ Deleted

...

======================================================================
Cleanup Summary
======================================================================
✅ Successfully deleted: 28 files
💾 Space freed: 567.34 MB

📊 Remaining active files: 120
📅 Next recommended cleanup: 2025-11-02
======================================================================
```

## 现有缓存处理

### 首次启动

当首次启用缓存生命周期管理功能时，系统会自动扫描现有的缓存文件：

1. **自动扫描**: 在服务启动时，系统会扫描 `CACHE_DIR` 目录
2. **初始化追踪**: 为所有现有文件设置**当前时间**作为最后访问时间
3. **完整生命周期**: 所有现有缓存都获得完整的 30 天生命周期

**日志示例**：
```
2025-11-01 10:00:00 - mirrorsrun.cache_tracker - INFO - Scanning cache directory for existing files: /app/cache/
2025-11-01 10:00:02 - mirrorsrun.cache_tracker - INFO - Initialized tracking for 150 existing cache files with current time
2025-11-01 10:00:02 - mirrorsrun.cache_tracker - INFO - Cache tracker initialized
```

**优势**：
- ✅ 所有现有缓存都有完整的 30 天生命周期
- ✅ 不会在首次启动时误删除有价值的缓存
- ✅ 平滑过渡，无需人工干预

## 最佳实践

### 推荐配置

**小型团队**（< 10 人）：
```yaml
CACHE_EXPIRY_DAYS=30  # 30天过期
```

**中型团队**（10-50 人）：
```yaml
CACHE_EXPIRY_DAYS=60  # 60天过期，使用频率较高
```

**大型团队**（50+ 人）：
```yaml
CACHE_EXPIRY_DAYS=90  # 90天过期，缓存复用率高
```

**CI/CD 场景**：
```yaml
CACHE_EXPIRY_DAYS=14  # 14天过期，频繁重建环境
```

### 监控建议

定期检查清理效果：

```bash
# 每周查看清理日志
docker logs lightmirrors 2>&1 | grep "Cache cleanup"

# 每月统计缓存使用情况
du -sh /path/to/data/cache/
```

### 磁盘空间管理

**预留空间建议**：
- 小型项目（< 100 包）: 5-10 GB
- 中型项目（100-500 包）: 20-50 GB
- 大型项目（500+ 包）: 100+ GB

**空间告警**：建议设置磁盘使用率告警（例如 80%）

## 故障排查

### 问题 1: 清理任务未运行

**检查日志**：
```bash
docker logs lightmirrors 2>&1 | grep -i "cleanup"
```

**可能原因**：
- `ENABLE_CACHE_CLEANUP=false`
- 服务未正确启动
- 时间配置错误

**解决方案**：
```bash
# 检查配置
docker exec lightmirrors env | grep CACHE

# 手动触发清理
docker exec lightmirrors python3 /app/scripts/cache_cleanup.py --dry-run
```

### 问题 2: 文件未被清理

**检查追踪记录**：
```bash
# 查看特定文件的追踪记录
docker exec lightmirrors cat /app/data/cache_access.json | jq '."/app/cache/path/to/file.whl"'
```

**可能原因**：
- 文件仍在访问阈值内
- 文件未被追踪（在追踪功能启用前下载）
- 追踪文件损坏

**解决方案**：
```bash
# 重新初始化追踪（重启服务）
docker restart lightmirrors
```

### 问题 3: 追踪文件过大

如果 `cache_access.json` 文件过大（> 10 MB），可能包含大量已删除文件的记录。

**清理方法**：
```bash
# 备份当前追踪文件
docker exec lightmirrors cp /app/data/cache_access.json /app/data/cache_access.json.backup

# 清理不存在的文件记录（会在下次清理时自动进行）
docker exec lightmirrors python3 /app/scripts/cache_cleanup.py --dry-run
```

## 安全性

- **原子操作**: 文件删除和追踪记录更新使用事务性操作
- **错误恢复**: 删除失败时会记录日志但不中断清理流程
- **备份建议**: 定期备份 `cache_access.json` 文件
- **回滚**: 可以从备份恢复追踪记录，但无法恢复已删除的缓存文件

## 性能影响

- **启动扫描**: 首次启动时扫描现有缓存，时间取决于文件数量（通常 < 5 秒）
- **访问更新**: 每次缓存命中时更新追踪文件，性能影响可忽略（< 1ms）
- **清理任务**: 在凌晨低峰时段运行，不影响服务性能
- **磁盘 I/O**: 清理任务的磁盘操作在后台执行，不阻塞请求处理

## 相关文档

- [缓存管理工具](./CACHE_MANAGEMENT.md) - 手动查看和管理缓存
- [量化数据说明](../data/metrics/README.md) - 理解缓存命中率等指标
- [快速开始](./QUICK_START.md) - 基本使用指南

