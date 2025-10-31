# 镜像量化数据说明

## 概述

此目录存放 LightMirrors 镜像服务的量化指标数据，用于分析镜像效果和性能。

## 数据文件

### metrics.json

包含所有包下载请求的量化数据，每条记录包括：

- **timestamp**: 请求时间戳（UTC）
- **url**: 请求的完整 URL
- **package_name**: 包名（从 URL 提取）
- **file_size**: 文件大小（字节）
- **cache_hit**: 是否缓存命中（true/false）
- **total_time**: 总耗时（秒，从请求到响应完成）
- **status**: 状态（success/timeout/error）
- **aria2_download_speed**: Aria2 平均下载速度（bytes/s，仅初次下载）
- **aria2_download_time**: Aria2 下载耗时（秒，仅初次下载）
- **client_receive_speed**: 客户端接收速度（bytes/s）
- **status_message**: 状态说明（可选）

## 数据记录场景

### 1. 缓存命中
当请求的文件已在缓存中时：
- `cache_hit = true`
- 记录从请求到完成的总时间
- 记录文件大小和客户端接收速度

### 2. 初次下载（缓存未命中）
当需要从上游源下载文件时：
- `cache_hit = false`
- 记录 Aria2 下载速度和下载时间
- 下载完成后打印 `[METRICS] Aria2 download completed: {package_name}`
- 记录总耗时（包括下载时间和传输给客户端的时间）

### 3. 下载超时
当下载超过 60 秒仍未完成时：
- `status = "timeout"`
- 记录已等待时间和已下载大小
- 客户端收到 504 响应

### 4. 下载错误
当下载失败时：
- `status = "error"`
- 记录错误信息

## 控制台日志示例

```
[METRICS] Cache HIT | requests-2.28.0.whl | Total: 0.05s | Size: 62.83KB
[METRICS] Cache MISS | numpy-1.24.0.whl | Aria2: 10.2s @ 1.16MB/s | Total: 12.5s | Size: 14.53MB
[METRICS] Aria2 download completed: numpy-1.24.0.whl
```

## 使用建议

1. **下载速度分析**：查看 `aria2_download_speed` 字段，评估上游源下载速度
2. **缓存效率分析**：统计 `cache_hit = true` 的比例，评估缓存命中率
3. **性能分析**：对比缓存命中和未命中的 `total_time`，评估镜像加速效果
4. **问题诊断**：查看 `status = "timeout"` 或 `"error"` 的记录，找出问题包

## 数据可视化建议

可以使用以下工具分析 metrics.json：
- Python + pandas + matplotlib
- Grafana + JSON 数据源插件
- Jupyter Notebook

示例 Python 分析代码：

```python
import json
import pandas as pd

with open('metrics.json', 'r') as f:
    data = json.load(f)

df = pd.DataFrame(data)

# 缓存命中率
cache_hit_rate = df['cache_hit'].sum() / len(df) * 100
print(f"缓存命中率: {cache_hit_rate:.2f}%")

# 平均下载速度（MB/s）
avg_speed = df[df['aria2_download_speed'].notna()]['aria2_download_speed'].mean() / (1024*1024)
print(f"平均下载速度: {avg_speed:.2f} MB/s")

# 缓存命中 vs 未命中的平均响应时间
hit_time = df[df['cache_hit'] == True]['total_time'].mean()
miss_time = df[df['cache_hit'] == False]['total_time'].mean()
print(f"缓存命中平均响应: {hit_time:.2f}s")
print(f"缓存未命中平均响应: {miss_time:.2f}s")
```

