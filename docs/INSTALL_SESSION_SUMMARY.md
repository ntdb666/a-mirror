# 安装会话汇总功能说明

## 📊 功能概述

安装会话汇总功能会自动识别同一次 `pip install` 的所有包请求，并在安装完成后输出一条汇总日志，让您直观看到整个安装过程的总体情况。

## 🎯 解决的问题

**问题**：之前的日志太细碎，每个包单独一条记录，无法直观看出整体安装效果。

**解决**：自动聚合同一次安装的所有包，输出一条汇总日志。

## 📝 日志示例

### 修改前（只有单包日志）

```
[METRICS] Cache MISS | pandas-2.0.0.whl | Aria2: 8.2s @ 1.22MB/s | Total: 8.5s | Size: 10.0MB
[METRICS] Cache MISS | numpy-1.24.0.whl | Aria2: 11.8s @ 1.27MB/s | Total: 12.2s | Size: 15.0MB
[METRICS] Cache HIT | pytz-2023.3.whl | Total: 0.010s | Size: 0.5MB
```

看不出这是一次安装，也不知道总共花了多少时间。

### 修改后（新增汇总日志）

```
[METRICS] Cache MISS | pandas-2.0.0.whl | Aria2: 8.2s @ 1.22MB/s | Total: 8.5s | Size: 10.0MB
[METRICS] Cache MISS | numpy-1.24.0.whl | Aria2: 11.8s @ 1.27MB/s | Total: 12.2s | Size: 15.0MB
[METRICS] Cache HIT | pytz-2023.3.whl | Total: 0.010s | Size: 0.5MB
[INSTALL-SUMMARY] pandas 安装完成 | 总时间: 15.5s | 包数: 3 | 总大小: 25.5MB | 下载: 25.0MB | 缓存命中: 1/3 (33.3%) | 平均速度: 1.25MB/s
  └─ pandas-2.0.0.whl (10.0MB, 下载, 8.5s)
  └─ numpy-1.24.0.whl (15.0MB, 下载, 12.2s)
  └─ pytz-2023.3.whl (0.5MB, 缓存, 0.01s)
```

一目了然！✨

## ⏱️ 总时间定义

**总时间 = 从第一个包请求到达，到最后一个包下载完成的时间**

这反映的是**用户等待镜像服务的总时间**，不包括 pip 本地处理时间。

### 示例时间轴

```
用户执行: pip install pandas

T0 (0.0s):   用户按下回车
T1 (0.1s):   第一个请求到达 (pandas.whl)
T2 (8.6s):   pandas 下载完成
T3 (8.7s):   第二个请求到达 (numpy.whl, 依赖)
T4 (20.9s):  numpy 下载完成
T5 (21.0s):  第三个请求到达 (pytz.whl, 依赖)
T6 (21.1s):  pytz 下载完成（缓存命中）

总时间 = T6 - T1 = 21.0s
```

## 🔍 会话识别策略

系统通过以下方式识别同一次安装：

1. **相同的 User-Agent** (如 `pip/23.0.1`)
2. **相同的客户端 IP**
3. **时间间隔 < 5 秒**

**5 秒内没有新请求 = 会话结束，输出汇总**

## 📊 汇总信息说明

```
[INSTALL-SUMMARY] pandas 安装完成 | 总时间: 15.5s | 包数: 3 | 总大小: 25.5MB | 下载: 25.0MB | 缓存命中: 1/3 (33.3%) | 平均速度: 1.29MB/s
```

| 指标 | 说明 |
|------|------|
| **主包名称** | 推测的主安装包（通常是第一个包） |
| **总时间** | 从第一个包请求到最后一个完成的时间 |
| **包数** | 本次安装涉及的包总数（包括依赖） |
| **总大小** | 所有包的总大小 |
| **下载** | 实际从上游下载的大小（不含缓存命中的） |
| **缓存命中** | 命中数/总数 (命中率%) |
| **平均速度** | 总下载大小 / 总下载时间（仅计算实际下载的包） |

### 包列表详情

```
  └─ pandas-2.0.0.whl (10.0MB, 下载, 8.5s)
  └─ numpy-1.24.0.whl (15.0MB, 下载, 12.2s)
  └─ pytz-2023.3.whl (0.5MB, 缓存, 0.01s)
```

每个包显示：
- 包名
- 大小（MB）
- 状态（下载 or 缓存）
- 耗时（秒）

## 🗂️ JSON 数据格式

会话汇总也会记录到 `data/metrics/metrics.json`：

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

## ⚙️ 配置选项

### 启用/禁用功能

默认启用。如果要禁用，设置环境变量：

```bash
# .env 文件
ENABLE_SESSION_SUMMARY=false
```

### 调整会话超时时间

默认 5 秒。如果您的网络较慢，可以延长：

```bash
# .env 文件
SESSION_TIMEOUT=10  # 10秒无新请求才算会话结束
```

## 🎭 使用场景

### 场景 1：安装单个包

```bash
pip install --index-url http://localhost:8080/pip/simple/ --trusted-host localhost requests
```

输出：
```
[METRICS] Cache MISS | requests-2.31.0.whl | Aria2: 2.5s @ 0.02MB/s | Total: 3.2s | Size: 0.06MB
[INSTALL-SUMMARY] requests 安装完成 | 总时间: 3.2s | 包数: 1 | 总大小: 0.06MB | 下载: 0.06MB | 缓存命中: 0/1 (0.0%) | 平均速度: 0.02MB/s
  └─ requests-2.31.0-py3-none-any.whl (0.06MB, 下载, 3.2s)
```

### 场景 2：安装带依赖的包

```bash
pip install --index-url http://localhost:8080/pip/simple/ --trusted-host localhost pandas
```

输出：
```
[METRICS] Cache MISS | pandas-2.0.0.whl | ...
[METRICS] Cache MISS | numpy-1.24.0.whl | ...
[METRICS] Cache MISS | python-dateutil-2.8.2.whl | ...
[METRICS] Cache HIT | pytz-2023.3.whl | ...
[INSTALL-SUMMARY] pandas 安装完成 | 总时间: 45.2s | 包数: 5 | 总大小: 35.8MB | 下载: 35.3MB | 缓存命中: 1/5 (20.0%) | 平均速度: 1.15MB/s
  └─ pandas-2.0.0.whl (...)
  └─ numpy-1.24.0.whl (...)
  └─ python-dateutil-2.8.2.whl (...)
  └─ pytz-2023.3.whl (...)
  └─ six-1.16.0.whl (...)
```

### 场景 3：重复安装（全缓存命中）

```bash
pip install --index-url http://localhost:8080/pip/simple/ --trusted-host localhost pandas
```

输出：
```
[METRICS] Cache HIT | pandas-2.0.0.whl | Total: 0.002s | Size: 10.0MB
[METRICS] Cache HIT | numpy-1.24.0.whl | Total: 0.003s | Size: 15.0MB
...
[INSTALL-SUMMARY] pandas 安装完成 | 总时间: 0.1s | 包数: 5 | 总大小: 35.8MB | 下载: 0.00MB | 缓存命中: 5/5 (100.0%)
  └─ pandas-2.0.0.whl (10.0MB, 缓存, 0.002s)
  └─ numpy-1.24.0.whl (15.0MB, 缓存, 0.003s)
  ...
```

可以看出缓存完全命中，响应时间从 45 秒降到 0.1 秒！🚀

## 📈 数据分析示例

### Python 分析会话数据

```python
import json
import pandas as pd

with open('data/metrics/metrics.json', 'r') as f:
    data = json.load(f)

# 过滤出会话记录
sessions = [d for d in data if d.get('type') == 'install_session']
df = pd.DataFrame(sessions)

print(f"总安装次数: {len(df)}")
print(f"平均安装时间: {df['total_time'].mean():.1f}s")
print(f"平均包数: {df['package_count'].mean():.1f}")
print(f"平均缓存命中率: {df['cache_hit_rate'].mean()*100:.1f}%")

# 最慢的安装
slowest = df.nlargest(5, 'total_time')[['main_package', 'total_time', 'package_count', 'cache_hit_rate']]
print("\n最慢的 5 次安装:")
print(slowest)

# 最常安装的包
top_packages = df['main_package'].value_counts().head(10)
print("\n最常安装的包:")
print(top_packages)
```

## 🔧 技术实现

### 会话管理

- 使用 `SessionManager` 单例管理所有活跃会话
- 每个会话由 User-Agent + Client IP + 时间窗口生成唯一 ID
- 后台任务每 2 秒检查一次，超时会话自动输出汇总

### 线程安全

- 使用 `asyncio.Lock()` 保护会话数据
- 确保并发请求正确记录到同一会话

### 内存管理

- 会话完成后立即清理，防止内存泄漏
- 服务重启时会话数据丢失（可接受）

## ❓ 常见问题

**Q: 为什么我看不到汇总日志？**

A: 确保：
1. `ENABLE_SESSION_SUMMARY=true` (默认已启用)
2. 等待 5 秒让会话超时
3. 查看完整日志而不是只过滤 METRICS

**Q: 可以调整超时时间吗？**

A: 可以，设置环境变量 `SESSION_TIMEOUT=10` (单位：秒)

**Q: 并发安装会混淆吗？**

A: 不会，不同的 User-Agent 或 IP 会被识别为不同会话

**Q: 单包安装也会输出汇总吗？**

A: 是的，即使只有 1 个包也会输出汇总，保持一致性

**Q: 影响性能吗？**

A: 几乎没有影响，会话记录是异步的，不阻塞下载

## 📚 相关文档

- [量化数据说明](../data/metrics/README.md)
- [快速开始指南](./QUICK_START.md)
- [如何查看日志](./HOW_TO_VIEW_LOGS.md)

