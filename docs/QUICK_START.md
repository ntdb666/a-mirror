# 快速开始指南

## 启动服务

```bash
# 构建并启动服务
docker-compose up -d --build

# 查看日志
docker-compose logs -f lightmirrors
```

## 查看量化数据

### 实时日志监控

```bash
# 查看实时日志（包含量化指标）
docker-compose logs -f lightmirrors | grep METRICS
```

输出示例：
```
lightmirrors  | [METRICS] Cache HIT | requests-2.28.0.whl | Total: 0.003s | Size: 0.06MB
lightmirrors  | [METRICS] Cache MISS | numpy-1.24.0.whl | Aria2: 10.2s @ 1.16MB/s | Total: 12.5s | Size: 14.53MB
lightmirrors  | [METRICS] Aria2 download completed: numpy-1.24.0.whl
```

**说明**：
- 缓存命中的响应时间通常在毫秒级（1-10ms），反映本地文件读取速度
- 缓存未命中时显示 Aria2 下载速度和总等待时间
- **单位统一**：文件大小统一为 **MB**，下载速度统一为 **MB/s**

### 查看 JSON 量化数据

```bash
# 查看原始数据
cat data/metrics/metrics.json

# 美化输出（Linux/Mac）
cat data/metrics/metrics.json | jq '.'

# 只看最后 5 条记录
cat data/metrics/metrics.json | jq '.[-5:]'
```

Windows PowerShell:
```powershell
# 查看原始数据
Get-Content data\metrics\metrics.json

# 转换为对象查看
Get-Content data\metrics\metrics.json | ConvertFrom-Json | Select-Object -Last 5
```

## 管理缓存包

### 查看缓存统计

Windows:
```powershell
.\scripts\cache_manager.ps1 stats
```

Linux/Mac:
```bash
./scripts/cache_manager.sh stats
```

输出示例：
```
=== 缓存统计信息 ===
总文件数: 127
Python Wheel 包: 89
Tar.gz 包: 38
Tgz 包: 0
正在下载: 2
总缓存大小: 1.24 GB
```

### 搜索特定包

```powershell
# Windows
.\scripts\cache_manager.ps1 search numpy

# Linux/Mac
./scripts/cache_manager.sh search numpy
```

### 查看正在下载的包

```powershell
# Windows
.\scripts\cache_manager.ps1 downloading

# Linux/Mac
./scripts/cache_manager.sh downloading
```

## 测试镜像服务

### 测试 PyPI 镜像

```bash
# 使用镜像安装包
pip install --index-url http://localhost:8080/pip/simple/ --trusted-host localhost requests

# 观察日志
docker-compose logs -f lightmirrors
```

第一次请求（缓存未命中）：
```
[METRICS] Cache MISS | requests-2.31.0-py3-none-any.whl | Aria2: 2.5s @ 0.02MB/s | Total: 3.2s | Size: 0.06MB
[METRICS] Aria2 download completed: requests-2.31.0-py3-none-any.whl
```

第二次请求（缓存命中）：
```
[METRICS] Cache HIT | requests-2.31.0-py3-none-any.whl | Total: 0.002s | Size: 0.06MB
```

### 测试 NPM 镜像

```bash
# 使用镜像安装包
npm install express --registry=http://localhost:8080/npm/

# 观察日志
docker-compose logs -f lightmirrors
```

### 测试 Docker 镜像

```bash
# 配置 Docker 镜像
# 编辑 /etc/docker/daemon.json (Linux)
{
  "registry-mirrors": ["http://localhost:8080/docker/"]
}

# 重启 Docker
sudo systemctl restart docker

# 拉取镜像
docker pull nginx
```

## 分析量化数据

### Python 分析示例

创建 `analyze_metrics.py`:

```python
import json
import pandas as pd
from datetime import datetime

# 读取数据
with open('data/metrics/metrics.json', 'r') as f:
    data = json.load(f)

df = pd.DataFrame(data)

print("=== 镜像效果分析 ===\n")

# 1. 缓存命中率
cache_hit_rate = df['cache_hit'].sum() / len(df) * 100
print(f"✓ 缓存命中率: {cache_hit_rate:.2f}%")

# 2. 平均下载速度（已经是 MB/s）
downloads = df[df['aria2_download_speed_mbs'].notna()]
if len(downloads) > 0:
    avg_speed_mbps = downloads['aria2_download_speed_mbs'].mean()
    print(f"✓ 平均 Aria2 下载速度: {avg_speed_mbps:.2f} MB/s")

# 3. 响应时间对比
hit_time = df[df['cache_hit'] == True]['total_time'].mean()
miss_time = df[df['cache_hit'] == False]['total_time'].mean()
speedup = miss_time / hit_time if hit_time > 0 else 0

print(f"✓ 缓存命中平均响应时间: {hit_time:.3f}s")
print(f"✓ 缓存未命中平均响应时间: {miss_time:.3f}s")
print(f"✓ 加速倍数: {speedup:.1f}x")

# 4. 总下载量（已经是 MB）
total_downloaded_mb = downloads['file_size_mb'].sum()
print(f"✓ 总下载量: {total_downloaded_mb / 1024:.2f} GB")

# 5. 最常用的包
print("\n=== Top 10 最常用的包 ===")
top_packages = df['package_name'].value_counts().head(10)
for pkg, count in top_packages.items():
    print(f"  {pkg}: {count} 次")

# 6. 状态统计
print("\n=== 状态统计 ===")
status_counts = df['status'].value_counts()
for status, count in status_counts.items():
    print(f"  {status}: {count}")
```

运行分析：
```bash
python analyze_metrics.py
```

输出示例：
```
=== 镜像效果分析 ===

✓ 缓存命中率: 68.50%
✓ 平均 Aria2 下载速度: 2.45 MB/s
✓ 缓存命中平均响应时间: 0.043s
✓ 缓存未命中平均响应时间: 5.234s
✓ 加速倍数: 121.7x
✓ 总下载量: 3.45 GB

=== Top 10 最常用的包 ===
  requests-2.31.0-py3-none-any.whl: 15 次
  numpy-1.24.0-cp311-cp311-linux_x86_64.whl: 8 次
  pandas-2.0.0-cp311-cp311-linux_x86_64.whl: 6 次
  ...

=== 状态统计 ===
  success: 127
  timeout: 3
  error: 1
```

## 定期维护

### 每周维护清单

1. **查看缓存大小**
```bash
.\scripts\cache_manager.ps1 size
```

2. **清理旧包**（30 天前）
```bash
.\scripts\cache_manager.ps1 clean-old 30
```

3. **备份量化数据**
```bash
# Windows
Copy-Item data\metrics\metrics.json data\metrics\metrics_backup_$(Get-Date -Format 'yyyyMMdd').json

# Linux/Mac
cp data/metrics/metrics.json data/metrics/metrics_backup_$(date +%Y%m%d).json
```

4. **查看服务健康状态**
```bash
docker-compose ps
docker-compose logs --tail=50 lightmirrors
```

### 故障排查

**问题：下载一直超时**
```bash
# 检查 Aria2 状态
docker-compose logs aria2

# 重启 Aria2
docker-compose restart aria2
```

**问题：metrics.json 无法写入**
```bash
# 检查目录权限
ls -la data/metrics/

# 在容器内检查
docker-compose exec lightmirrors ls -la /app/data/
```

**问题：缓存文件损坏**
```bash
# 查找并删除 0 字节文件
find data/cache/ -type f -size 0 -delete

# 清理残留的 .aria2 文件
find data/cache/ -name "*.aria2" -delete
```

## 生产环境建议

1. **使用外部代理**
   - 配置 `http_proxy` 和 `https_proxy` 环境变量
   - 加速上游源访问

2. **定期备份**
   - 备份 `data/metrics/metrics.json`
   - 备份 `data/aria2/aria2.session`

3. **监控磁盘空间**
   - 设置告警阈值（如 80%）
   - 自动清理旧缓存

4. **日志轮转**
   - 配置 Docker 日志限制
   - 定期归档量化数据

5. **性能优化**
   - 增加 Aria2 并发下载数
   - 调整缓存目录到高速磁盘

## 相关文档

- [缓存管理详细指南](./CACHE_MANAGEMENT.md)
- [量化数据说明](../data/metrics/README.md)
- [功能更新说明](../METRICS_UPDATE.md)

## 常见问题

**Q: 量化数据文件会无限增长吗？**
A: 是的，建议定期备份并清空，或实现日志轮转。

**Q: 缓存包会自动过期吗？**
A: 不会，当前未实现自动过期，需要手动清理。

**Q: 如何查看某个包的下载历史？**
```bash
cat data/metrics/metrics.json | jq '.[] | select(.package_name | contains("numpy"))'
```

**Q: 如何重置所有数据？**
```bash
# 停止服务
docker-compose down

# 清理缓存和数据
rm -rf data/cache/*
rm -rf data/metrics/metrics.json

# 重启服务
docker-compose up -d
```

