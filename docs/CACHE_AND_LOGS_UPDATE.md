# 缓存生命周期管理和日志按天分割功能更新

## 版本信息

**版本**: v2.0  
**更新日期**: 2025-11-01  
**更新内容**: 缓存自动清理 + 日志按天分割

---

## 🎯 功能概述

### 功能 1: 缓存生命周期自动管理

自动追踪缓存文件的访问情况，定期清理长期未使用的文件，保持磁盘空间高效利用。

**核心特性**：
- ✅ 自动追踪每个缓存文件的最后访问时间
- ✅ 每天凌晨 2:00 自动清理过期文件（默认 30 天未访问）
- ✅ 首次启动自动扫描现有缓存，赋予完整生命周期
- ✅ 支持手动清理和预览
- ✅ 详细的清理日志和统计信息

### 功能 2: 日志文件按天分割

量化数据日志按日期自动分割存储，便于管理和分析历史数据。

**核心特性**：
- ✅ 自动按日期生成独立的日志文件（`metrics-YYYY-MM-DD.json`）
- ✅ 跨天会话记录到会话开始日期的文件中
- ✅ 保留所有历史日志，便于长期分析
- ✅ 支持合并多日数据进行统计

---

## 📦 文件变更

### 新增文件

1. **`src/mirrorsrun/cache_tracker.py`**
   - 缓存访问时间追踪模块
   - 实现 `CacheAccessTracker` 类

2. **`src/mirrorsrun/cache_cleanup_task.py`**
   - 后台清理调度器
   - 每天凌晨自动运行清理任务

3. **`scripts/cache_cleanup.py`**
   - 手动清理脚本
   - 支持 dry-run 和自定义过期天数

4. **`docs/CACHE_LIFECYCLE.md`**
   - 缓存生命周期管理完整文档

5. **`docs/CACHE_AND_LOGS_UPDATE.md`**
   - 本更新说明文档

### 修改文件

1. **`src/mirrorsrun/config.py`**
   ```python
   # 新增配置项
   CACHE_EXPIRY_DAYS = int(os.environ.get("CACHE_EXPIRY_DAYS", "30"))
   CACHE_ACCESS_TRACKING_FILE = os.path.join(DATA_DIR, "cache_access.json")
   ENABLE_CACHE_CLEANUP = os.environ.get("ENABLE_CACHE_CLEANUP", "true") == "true"
   ```

2. **`src/mirrorsrun/proxy/file_cache.py`**
   - 缓存命中时更新访问时间
   - 下载完成时记录访问时间

3. **`src/mirrorsrun/server.py`**
   - 启动时初始化缓存追踪器
   - 启动时启动清理调度器
   - 关闭时停止清理调度器

4. **`src/mirrorsrun/metrics.py`**
   - 支持按日期生成文件名 (`_get_metrics_file_for_date`)
   - `record_metric` 接受 `record_time` 参数
   - `_append_to_json` 接受 `metrics_file` 参数

5. **`src/mirrorsrun/session_manager.py`**
   - 会话记录到会话开始日期的文件中

6. **`docker-compose.yml` 和 `docker-compose-caddy.yml`**
   ```yaml
   environment:
     - CACHE_EXPIRY_DAYS=30
     - ENABLE_CACHE_CLEANUP=true
     - SESSION_TIMEOUT=5
     - ENABLE_SESSION_SUMMARY=true
   ```

7. **`data/metrics/README.md`**
   - 添加日志按天分割的说明
   - 添加查看历史数据的方法

---

## 🚀 使用指南

### 快速开始

1. **更新并重启服务**：
   ```bash
   docker-compose pull
   docker-compose up -d
   ```

2. **验证功能启动**：
   ```bash
   docker logs lightmirrors | grep -i "cache"
   ```
   
   应该看到：
   ```
   Cache tracker initialized
   Cache cleanup scheduler enabled
   Initialized tracking for XX existing cache files with current time
   ```

### 配置缓存清理

编辑 `docker-compose.yml`：

```yaml
environment:
  # 修改过期天数（默认 30 天）
  - CACHE_EXPIRY_DAYS=60
  
  # 禁用自动清理（如果需要）
  - ENABLE_CACHE_CLEANUP=false
```

应用更改：
```bash
docker-compose up -d
```

### 手动清理缓存

**预览将被清理的文件**（不实际删除）：
```bash
docker exec lightmirrors python3 /app/scripts/cache_cleanup.py --dry-run
```

**执行清理**（使用默认配置）：
```bash
docker exec lightmirrors python3 /app/scripts/cache_cleanup.py
```

**使用自定义天数**：
```bash
# 清理 7 天未使用的文件
docker exec lightmirrors python3 /app/scripts/cache_cleanup.py --days 7
```

### 查看日志文件

**查看今天的数据**：
```bash
TODAY=$(date +%Y-%m-%d)
docker exec lightmirrors cat /app/data/metrics-${TODAY}.json | jq
```

**查看特定日期**：
```bash
docker exec lightmirrors cat /app/data/metrics-2025-11-01.json | jq
```

**统计缓存命中率**：
```bash
jq '[.[] | select(.type != "install_session") | .cache_hit] | add / length * 100' metrics-2025-11-01.json
```

---

## 📊 监控和维护

### 查看缓存追踪状态

```bash
# 查看追踪的文件数量
docker exec lightmirrors cat /app/data/cache_access.json | jq 'length'

# 查看最近访问的文件
docker exec lightmirrors cat /app/data/cache_access.json | jq 'to_entries | sort_by(.value) | reverse | .[0:10]'
```

### 查看清理日志

```bash
# 查看最近的清理记录
docker logs lightmirrors 2>&1 | grep "Cache cleanup"

# 实时监控
docker logs -f lightmirrors | grep -i "cache\|cleanup"
```

### 磁盘空间监控

```bash
# 查看缓存目录大小
du -sh ./data/cache/

# 查看数据目录大小
du -sh ./data/metrics/
```

---

## 🔄 升级注意事项

### 从旧版本升级

1. **备份数据**（推荐）：
   ```bash
   cp -r ./data ./data.backup.$(date +%Y%m%d)
   ```

2. **拉取最新代码**：
   ```bash
   git pull
   ```

3. **重启服务**：
   ```bash
   docker-compose down
   docker-compose up -d
   ```

4. **验证启动**：
   ```bash
   docker logs lightmirrors | tail -50
   ```

### 现有缓存处理

**不用担心！** 系统会自动处理：

- ✅ 首次启动时自动扫描所有现有缓存
- ✅ 为每个文件设置当前时间作为访问时间
- ✅ 所有现有缓存获得完整的 30 天生命周期
- ✅ 不会误删除任何有价值的缓存

### 日志文件迁移

旧的 `metrics.json` 文件会保留，新数据会写入按日期分割的文件。

**可选清理**：
```bash
# 备份旧文件
mv ./data/metrics/metrics.json ./data/metrics/metrics.json.old

# 或者直接删除（如果不需要历史数据）
rm ./data/metrics/metrics.json
```

---

## 🎓 最佳实践

### 推荐配置

**开发环境**：
```yaml
CACHE_EXPIRY_DAYS=7   # 快速迭代，短生命周期
ENABLE_CACHE_CLEANUP=true
```

**生产环境（小团队）**：
```yaml
CACHE_EXPIRY_DAYS=30  # 标准配置
ENABLE_CACHE_CLEANUP=true
```

**生产环境（大团队）**：
```yaml
CACHE_EXPIRY_DAYS=90  # 更长的生命周期
ENABLE_CACHE_CLEANUP=true
```

**CI/CD 环境**：
```yaml
CACHE_EXPIRY_DAYS=14  # 频繁重建，中等生命周期
ENABLE_CACHE_CLEANUP=true
```

### 日志管理

**定期分析**：
```bash
# 每月统计分析脚本
#!/bin/bash
MONTH=$(date +%Y-%m)
jq -s 'add | [.[] | select(.type != "install_session")] | 
  {
    total: length,
    cache_hits: [.[] | select(.cache_hit == true)] | length,
    cache_miss: [.[] | select(.cache_hit == false)] | length,
    hit_rate: ([.[] | select(.cache_hit == true)] | length) / length * 100
  }' ./data/metrics/metrics-${MONTH}-*.json
```

**日志归档**：
```bash
# 归档 3 个月前的日志
find ./data/metrics/ -name "metrics-*.json" -mtime +90 -exec gzip {} \;
```

---

## 🛠️ 故障排查

### 问题 1: "Cache tracker initialized" 日志未出现

**检查**：
```bash
docker logs lightmirrors 2>&1 | grep -i "cache\|error"
```

**可能原因**：
- 配置文件语法错误
- 权限问题

**解决**：
```bash
# 检查配置
docker exec lightmirrors env | grep CACHE

# 检查权限
docker exec lightmirrors ls -la /app/data/
```

### 问题 2: 清理任务未运行

**检查调度器状态**：
```bash
docker logs lightmirrors 2>&1 | grep "cleanup scheduler"
```

**手动触发测试**：
```bash
docker exec lightmirrors python3 /app/scripts/cache_cleanup.py --dry-run
```

### 问题 3: 日志文件未按天分割

**检查新文件**：
```bash
docker exec lightmirrors ls -lh /app/data/metrics-*.json
```

**验证记录**：
```bash
# 安装一个包后检查今天的文件
docker exec lightmirrors cat /app/data/metrics-$(date +%Y-%m-%d).json | jq
```

---

## 📚 相关文档

- **[缓存生命周期管理](./CACHE_LIFECYCLE.md)** - 详细功能说明
- **[量化数据说明](../data/metrics/README.md)** - 日志格式和分析方法
- **[缓存管理工具](./CACHE_MANAGEMENT.md)** - 手动管理缓存的方法
- **[快速开始](./QUICK_START.md)** - 基本使用指南

---

## 💡 技术细节

### 缓存追踪实现

**数据结构**：
```json
{
  "/app/cache/pypi.../package.whl": "2025-11-01T10:30:00Z"
}
```

**更新时机**：
1. 缓存命中时（每次访问）
2. 首次下载完成时
3. 启动时扫描现有文件

**线程安全**：使用文件锁确保并发安全

### 日志分割实现

**文件命名**: `metrics-{date}.json`
**日期来源**: 
- 单包记录：使用当前 UTC 时间
- 会话记录：使用会话开始时间

**跨天处理**: 会话完整记录在开始日期的文件中

### 性能影响

- **启动扫描**: O(n)，n = 缓存文件数量，通常 < 5 秒
- **访问更新**: O(1)，< 1ms
- **清理任务**: 凌晨运行，不影响服务
- **日志分割**: 无额外开销，正常写入

---

## 🎉 总结

这次更新带来了两个重要功能：

1. **自动化缓存管理** - 不再需要手动清理，系统自动维护
2. **结构化日志存储** - 便于长期分析和历史数据管理

**升级建议**: ✅ 强烈推荐所有用户升级

**向后兼容**: ✅ 完全兼容，平滑升级

**风险评估**: 🟢 低风险，现有功能不受影响

如有问题，请查看相关文档或提交 Issue。

