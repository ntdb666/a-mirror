# 如何查看日志输出

## 📋 概述

LightMirrors 的量化日志会输出到两个地方：
1. **控制台日志**：实时输出到 Docker 容器日志
2. **JSON 文件**：持久化保存到 `data/metrics/metrics.json`

---

## 🖥️ 方法 1：查看实时控制台日志

### Windows (PowerShell)

```powershell
# 查看所有实时日志
docker-compose logs -f lightmirrors

# 只查看量化指标日志
docker-compose logs -f lightmirrors | Select-String "METRICS"

# 查看最近 100 条日志
docker-compose logs --tail 100 lightmirrors

# 只看最近 50 条 METRICS 日志
docker-compose logs --tail 100 lightmirrors | Select-String "METRICS"
```

### Linux/Mac (Bash)

```bash
# 查看所有实时日志
docker-compose logs -f lightmirrors

# 只查看量化指标日志
docker-compose logs -f lightmirrors | grep METRICS

# 查看最近 100 条日志
docker-compose logs --tail 100 lightmirrors

# 只看最近 50 条 METRICS 日志
docker-compose logs --tail 100 lightmirrors | grep METRICS
```

### 日志输出示例

```
lightmirrors  | 2025-10-31 11:31:00 - mirrorsrun.metrics - INFO - [METRICS] Cache HIT | requests-2.28.0.whl | Total: 0.003s | Size: 0.06MB
lightmirrors  | 2025-10-31 11:31:05 - mirrorsrun.metrics - INFO - [METRICS] Cache MISS | numpy-1.24.0.whl | Aria2: 10.2s @ 1.16MB/s | Total: 12.5s | Size: 14.53MB
lightmirrors  | 2025-10-31 11:31:05 - mirrorsrun.metrics - INFO - [METRICS] Aria2 download completed: numpy-1.24.0.whl
```

---

## 📁 方法 2：查看 JSON 数据文件

### 查看文件位置

JSON 数据文件在：
```
data/metrics/metrics.json
```

### Windows

```powershell
# 查看原始 JSON
Get-Content data\metrics\metrics.json

# 格式化查看（转换为 PowerShell 对象）
Get-Content data\metrics\metrics.json | ConvertFrom-Json | Format-List

# 只看最后 5 条记录
Get-Content data\metrics\metrics.json | ConvertFrom-Json | Select-Object -Last 5 | Format-List

# 在记事本中打开
notepad data\metrics\metrics.json

# 在 VS Code 中打开
code data\metrics\metrics.json
```

### Linux/Mac

```bash
# 查看原始 JSON
cat data/metrics/metrics.json

# 格式化查看（需要 jq）
cat data/metrics/metrics.json | jq '.'

# 只看最后 5 条记录
cat data/metrics/metrics.json | jq '.[-5:]'

# 查看特定包
cat data/metrics/metrics.json | jq '.[] | select(.package_name | contains("numpy"))'

# 在编辑器中打开
vim data/metrics/metrics.json
nano data/metrics/metrics.json
```

### JSON 数据格式

```json
[
  {
    "timestamp": "2025-10-31T11:31:01.331884Z",
    "url": "https://pypi.tuna.tsinghua.edu.cn/packages/.../shapely-2.1.2.whl",
    "package_name": "shapely-2.1.2-cp312-cp312-win_amd64.whl",
    "file_size_mb": 1.64,
    "cache_hit": false,
    "total_time": 1.035,
    "status": "success",
    "aria2_download_speed_mbs": 1.64,
    "aria2_download_time": 1.001,
    "client_receive_speed_mbs": 1.59
  },
  {
    "timestamp": "2025-10-31T11:31:01.397012Z",
    "url": "https://pypi.tuna.tsinghua.edu.cn/packages/.../shapely-2.1.2.whl",
    "package_name": "shapely-2.1.2-cp312-cp312-win_amd64.whl",
    "file_size_mb": 1.64,
    "cache_hit": true,
    "total_time": 0.002,
    "status": "success"
  }
]
```

**字段说明：**
- `file_size_mb`: 文件大小，单位 **MB**
- `aria2_download_speed_mbs`: Aria2 下载速度，单位 **MB/s**
- `client_receive_speed_mbs`: 客户端接收速度，单位 **MB/s**
- 缓存命中时不包含速度字段

---

## 🔍 方法 3：在容器内查看日志

### 进入容器

```bash
# 进入 lightmirrors 容器
docker-compose exec lightmirrors sh

# 查看日志文件
cat /app/data/metrics.json

# 退出容器
exit
```

---

## 📊 方法 4：使用 Python 分析日志

### 安装依赖

```bash
pip install pandas
```

### 创建分析脚本

创建 `view_metrics.py`:

```python
import json
import pandas as pd

# 读取数据
with open('data/metrics/metrics.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

df = pd.DataFrame(data)

print(f"总记录数: {len(df)}")
print(f"时间范围: {df['timestamp'].min()} 至 {df['timestamp'].max()}")
print()

# 缓存命中统计
print("=== 缓存统计 ===")
cache_hit_count = df['cache_hit'].sum()
cache_miss_count = len(df) - cache_hit_count
cache_hit_rate = cache_hit_count / len(df) * 100
print(f"缓存命中: {cache_hit_count} 次 ({cache_hit_rate:.1f}%)")
print(f"缓存未命中: {cache_miss_count} 次")
print()

# 下载速度统计
print("=== 下载速度统计 ===")
downloads = df[df['aria2_download_speed_mbs'].notna()]
if len(downloads) > 0:
    print(f"平均下载速度: {downloads['aria2_download_speed_mbs'].mean():.2f} MB/s")
    print(f"最快下载速度: {downloads['aria2_download_speed_mbs'].max():.2f} MB/s")
    print(f"最慢下载速度: {downloads['aria2_download_speed_mbs'].min():.2f} MB/s")
print()

# 最近 10 条记录
print("=== 最近 10 条记录 ===")
for _, row in df.tail(10).iterrows():
    cache_status = "HIT " if row['cache_hit'] else "MISS"
    print(f"[{cache_status}] {row['package_name'][:50]:<50} | {row['file_size_mb']:>7.2f}MB | {row['total_time']:>6.3f}s")
```

### 运行分析

```bash
python view_metrics.py
```

---

## 🎯 常用场景

### 1. 监控实时下载

**场景**：测试时实时查看下载情况

```bash
# Windows
docker-compose logs -f lightmirrors | Select-String "METRICS|Aria2"

# Linux/Mac
docker-compose logs -f lightmirrors | grep -E "METRICS|Aria2"
```

### 2. 查找特定包的下载记录

**场景**：查看 numpy 包的下载历史

Windows:
```powershell
Get-Content data\metrics\metrics.json | ConvertFrom-Json | Where-Object { $_.package_name -like "*numpy*" }
```

Linux/Mac:
```bash
cat data/metrics/metrics.json | jq '.[] | select(.package_name | contains("numpy"))'
```

### 3. 统计今天的缓存命中率

**场景**：查看今天的镜像效果

Python:
```python
import json
from datetime import date

with open('data/metrics/metrics.json', 'r') as f:
    data = json.load(f)

today = date.today().isoformat()
today_records = [r for r in data if r['timestamp'].startswith(today)]
hit_rate = sum(1 for r in today_records if r['cache_hit']) / len(today_records) * 100
print(f"今天的缓存命中率: {hit_rate:.1f}%")
```

### 4. 导出为 CSV

**场景**：导出到 Excel 分析

```python
import json
import pandas as pd

with open('data/metrics/metrics.json', 'r') as f:
    data = json.load(f)

df = pd.DataFrame(data)
df.to_csv('metrics_export.csv', index=False, encoding='utf-8-sig')
print("已导出到 metrics_export.csv")
```

### 5. 持续监控（自动刷新）

**场景**：终端持续显示最新日志

Windows PowerShell:
```powershell
while ($true) {
    Clear-Host
    docker-compose logs --tail 20 lightmirrors | Select-String "METRICS"
    Start-Sleep -Seconds 2
}
```

Linux/Mac:
```bash
watch -n 2 'docker-compose logs --tail 20 lightmirrors | grep METRICS'
```

---

## ⚠️ 故障排查

### 问题 1：没有日志输出

**检查服务是否运行：**
```bash
docker-compose ps
```

**检查容器日志：**
```bash
docker-compose logs lightmirrors
```

### 问题 2：JSON 文件为空或不存在

**检查目录权限：**
```bash
ls -la data/metrics/
```

**在容器内检查：**
```bash
docker-compose exec lightmirrors ls -la /app/data/
docker-compose exec lightmirrors cat /app/data/metrics.json
```

**重新初始化：**
```bash
# 停止服务
docker-compose down

# 确保目录存在
mkdir -p data/metrics

# 重启服务
docker-compose up -d
```

### 问题 3：日志过多难以查看

**只看 METRICS 相关：**
```bash
docker-compose logs lightmirrors 2>&1 | grep METRICS
```

**保存到文件：**
```bash
docker-compose logs lightmirrors > logs_$(date +%Y%m%d).txt
```

---

## 💡 推荐工作流

1. **启动服务后，开两个终端**：
   - 终端 1：`docker-compose logs -f lightmirrors | grep METRICS`（实时监控）
   - 终端 2：正常操作（测试下载等）

2. **定期查看 JSON 数据**：
   ```bash
   cat data/metrics/metrics.json | jq '.[-10:]'  # 查看最近 10 条
   ```

3. **每天分析一次**：
   ```bash
   python view_metrics.py  # 运行统计脚本
   ```

---

## 📚 相关文档

- [量化数据说明](../data/metrics/README.md)
- [快速开始指南](./QUICK_START.md)
- [缓存管理指南](./CACHE_MANAGEMENT.md)

