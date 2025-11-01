# 镜像量化数据说明

## 概述

此目录存放 LightMirrors 镜像服务的量化指标数据，用于分析镜像效果和性能。

## 数据文件组织

从 **v2.0** 开始，量化数据按天分割存储：

```
data/metrics/
├── metrics-2025-11-01.json  # 2025年11月1日的数据
├── metrics-2025-11-02.json  # 2025年11月2日的数据
├── metrics-2025-11-03.json  # 2025年11月3日的数据
└── ...
```

**文件命名格式**: `metrics-YYYY-MM-DD.json`

### 跨天会话处理

如果一个安装会话跨越午夜（例如 23:58 开始，00:02 结束），整个会话（包括所有包和会话汇总）会被记录到**会话开始时的日期文件**中。

**示例**：
- 会话开始：2025-11-01 23:58
- 会话结束：2025-11-02 00:02
- 记录位置：`metrics-2025-11-01.json`

### 查看历史数据

**查看特定日期**：
```bash
# 查看2025年11月1日的数据
cat data/metrics/metrics-2025-11-01.json | jq

# 统计当天缓存命中率
jq '[.[] | select(.type != "install_session") | .cache_hit] | add / length' data/metrics/metrics-2025-11-01.json
```

**合并多天数据**：
```bash
# 合并11月所有数据
jq -s 'add' data/metrics/metrics-2025-11-*.json > november.json

# 合并后分析
jq '[.[] | select(.cache_hit == true)] | length' november.json
```

**Python 分析**：
```python
import json
from pathlib import Path

# 读取所有11月数据
metrics_dir = Path("data/metrics")
all_data = []

for file in sorted(metrics_dir.glob("metrics-2025-11-*.json")):
    with open(file) as f:
        all_data.extend(json.load(f))

# 分析
cache_hits = [m for m in all_data if m.get("cache_hit") == True]
print(f"缓存命中率: {len(cache_hits) / len(all_data) * 100:.1f}%")
```

## 数据文件格式

### 单个包记录（Package Record）

包含所有包下载请求的量化数据，每条记录包括：

- **timestamp**: 请求时间戳（UTC）
- **url**: 请求的完整 URL
- **package_name**: 包名（从 URL 提取）
- **file_size_mb**: 文件大小（**MB**）
- **cache_hit**: 是否缓存命中（true/false）
- **total_time**: 总耗时（秒，从请求到响应完成）
- **status**: 状态（success/timeout/error）
- **aria2_download_speed_mbs**: Aria2 从上游源下载的速度（**MB/s**，仅初次下载）
- **aria2_download_time**: Aria2 下载耗时（秒，仅初次下载）
- **client_receive_speed_mbs**: 客户端有效吞吐量（**MB/s**，仅初次下载，包含等待时间）
- **status_message**: 状态说明（可选）

**注意：** 
- 缓存命中时不记录 `client_receive_speed_mbs`，因为读取本地缓存的速度不具有参考意义
- 初次下载时，`client_receive_speed_mbs` = 文件大小 / 总耗时，反映从客户端角度的有效下载速度
- **单位统一**：文件大小使用 **MB**，速度使用 **MB/s**

## 数据记录场景

### 1. 缓存命中
当请求的文件已在缓存中时：
- `cache_hit = true`
- 记录从请求到响应生成的时间（通常为毫秒级）
- 记录文件大小
- 不记录 `client_receive_speed`（本地读取速度无参考价值）

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

## 数据输出格式示例

### JSON 数据格式（data/metrics/metrics.json）

JSON 文件包含两种类型的记录：

#### 1. 单包记录（type 字段不存在或为空）

```json
{
  "timestamp": "2025-10-31T10:30:45.123Z",
  "url": "https://files.pythonhosted.org/packages/.../numpy-1.24.0.whl",
  "package_name": "numpy-1.24.0.whl",
  "file_size_mb": 14.53,
  "cache_hit": false,
  "total_time": 12.5,
  "aria2_download_speed_mbs": 1.16,
  "aria2_download_time": 10.2,
  "client_receive_speed_mbs": 1.16,
  "status": "success"
}
```

#### 2. 安装会话汇总记录（type = "install_session"）

```json
{
  "type": "install_session",
  "session_id": "pip-1234567890",
  "timestamp_start": "2025-10-31T11:30:00.123Z",
  "timestamp_end": "2025-10-31T11:30:15.623Z",
  "total_time": 15.5,
  "main_package": "pandas",
  "package_count": 3,
  "total_size_mb": 25.5,
  "downloaded_size_mb": 25.0,
  "cache_hit_count": 1,
  "cache_hit_rate": 0.333,
  "avg_download_speed_mbs": 1.29,
  "packages": [
    {"name": "pandas-2.0.0.whl", "size_mb": 10.0, "cache_hit": false, "time": 8.5},
    {"name": "numpy-1.24.0.whl", "size_mb": 15.0, "cache_hit": false, "time": 12.2},
    {"name": "pytz-2023.3.whl", "size_mb": 0.5, "cache_hit": true, "time": 0.01}
  ],
  "user_agent": "pip/23.0.1",
  "client_ip": "192.168.1.100"
}
```

### 控制台日志格式

#### 单包日志

```
[METRICS] Cache HIT | requests-2.28.0.whl | Total: 0.003s | Size: 0.06MB
[METRICS] Cache MISS | numpy-1.24.0.whl | Aria2: 10.2s @ 1.16MB/s | Total: 12.5s | Size: 14.53MB
[METRICS] Aria2 download completed: numpy-1.24.0.whl
```

#### 安装汇总日志（新增）

在同一次安装的所有包下载完成后（5秒无新请求），自动输出汇总：

```
[INSTALL-SUMMARY] pandas 安装完成 | 总时间: 15.5s | 包数: 3 | 总大小: 25.5MB | 下载: 25.0MB | 缓存命中: 1/3 (33.3%) | 平均速度: 1.29MB/s
  └─ pandas-2.0.0.whl (10.0MB, 下载, 8.5s)
  └─ numpy-1.24.0.whl (15.0MB, 下载, 12.2s)
  └─ pytz-2023.3.whl (0.5MB, 缓存, 0.01s)
```

**说明：**
- **Cache HIT**: 缓存命中，Total 是服务器读取缓存文件的时间（通常 < 10ms）
- **Cache MISS**: 缓存未命中，Aria2 显示上游下载速度和时间，Total 是客户端等待的总时间
- **INSTALL-SUMMARY**: 安装会话汇总，显示整个安装过程的总体情况
  - **总时间**：从第一个包请求到最后一个包完成的时间
  - **包数**：本次安装涉及的包总数
  - **总大小**：所有包的总大小
  - **下载**：实际从上游下载的大小（不含缓存命中的）
  - **缓存命中**：命中数/总数 (命中率%)
  - **平均速度**：总下载大小 / 总下载时间
- **单位统一**: JSON 和日志中，文件大小统一使用 **MB**，下载速度统一使用 **MB/s**

## 使用建议

1. **下载速度分析**：查看 `aria2_download_speed_mbs` 字段，评估上游源下载速度
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

# 平均下载速度（已经是 MB/s）
avg_speed = df[df['aria2_download_speed_mbs'].notna()]['aria2_download_speed_mbs'].mean()
print(f"平均下载速度: {avg_speed:.2f} MB/s")

# 缓存命中 vs 未命中的平均响应时间
hit_time = df[df['cache_hit'] == True]['total_time'].mean()
miss_time = df[df['cache_hit'] == False]['total_time'].mean()
print(f"缓存命中平均响应: {hit_time:.2f}s")
print(f"缓存未命中平均响应: {miss_time:.2f}s")
```

