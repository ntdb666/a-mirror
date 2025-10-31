# 镜像量化监控功能更新说明

## 更新概述

为 LightMirrors 添加了完整的量化数据记录功能，用于可视化分析镜像效果。

## 新增功能

### 1. 量化数据记录
- 自动记录所有包下载请求的量化指标
- 数据以 JSON 格式持久化到 `data/metrics/metrics.json`
- 包含下载速度、缓存命中率、响应时间等关键指标

### 2. 控制台日志增强
- 缓存命中：显示响应时间和文件大小
- 缓存未命中：显示 Aria2 下载速度、下载时间和总耗时
- 下载完成：打印 "Aria2 download completed" 确认消息
- 超时/错误：打印状态说明

### 3. 速度监控
- **Aria2 下载速度**：从上游源下载的速度（bytes/s）
- **客户端接收速度**：客户端从镜像接收的速度（bytes/s）
- 定期（每 5 秒）获取 Aria2 下载状态

### 4. 缓存策略跟踪
- 记录每次请求是否命中缓存
- 可统计缓存命中率和加速效果
- 注：当前项目未设置包生命周期，缓存会一直保留

## 文件修改清单

### 新增文件
- `src/mirrorsrun/metrics.py` - 量化数据记录模块
- `data/metrics/.gitkeep` - 数据目录占位符
- `data/metrics/README.md` - 数据说明文档

### 修改文件
- `src/mirrorsrun/config.py` - 添加 DATA_DIR 和 METRICS_FILE 配置
- `src/mirrorsrun/proxy/file_cache.py` - 添加完整的指标追踪逻辑
- `src/Dockerfile` - 创建 /app/data 目录
- `docker-compose.yml` - 挂载 data/metrics 目录
- `docker-compose-caddy.yml` - 挂载 data/metrics 目录

## 使用方法

### 1. 启动服务
```bash
docker-compose up -d --build
```

### 2. 查看量化数据
```bash
cat data/metrics/metrics.json
```

### 3. 查看实时日志
```bash
docker-compose logs -f lightmirrors
```

日志示例：
```
[METRICS] Cache HIT | requests-2.28.0.whl | Total: 0.05s | Size: 62.83KB
[METRICS] Cache MISS | numpy-1.24.0.whl | Aria2: 10.2s @ 1.16MB/s | Total: 12.5s | Size: 14.53MB
[METRICS] Aria2 download completed: numpy-1.24.0.whl
```

## 数据分析示例

### 查看缓存命中率
```python
import json
import pandas as pd

with open('data/metrics/metrics.json', 'r') as f:
    data = json.load(f)

df = pd.DataFrame(data)
cache_hit_rate = df['cache_hit'].sum() / len(df) * 100
print(f"缓存命中率: {cache_hit_rate:.2f}%")
```

### 查看平均下载速度
```python
# 过滤出初次下载的记录
downloads = df[df['aria2_download_speed'].notna()]
avg_speed_mbps = downloads['aria2_download_speed'].mean() / (1024*1024)
print(f"平均 Aria2 下载速度: {avg_speed_mbps:.2f} MB/s")
```

### 对比缓存效果
```python
hit_time = df[df['cache_hit'] == True]['total_time'].mean()
miss_time = df[df['cache_hit'] == False]['total_time'].mean()
speedup = miss_time / hit_time
print(f"缓存命中响应时间: {hit_time:.2f}s")
print(f"缓存未命中响应时间: {miss_time:.2f}s")
print(f"加速倍数: {speedup:.1f}x")
```

## 环境变量配置（可选）

可以通过环境变量自定义配置：

```bash
# .env 文件
DATA_DIR=/app/data/
```

## 关键指标说明

| 指标 | 说明 | 单位 |
|------|------|------|
| cache_hit | 是否缓存命中 | boolean |
| total_time | 从请求到完成的总时间 | 秒 |
| aria2_download_speed | Aria2 从上游下载的速度 | bytes/s |
| aria2_download_time | Aria2 下载耗时 | 秒 |
| client_receive_speed | 客户端接收速度 | bytes/s |
| file_size | 文件大小 | 字节 |

## 注意事项

1. **数据持久化**：metrics.json 会不断追加，建议定期备份和清理
2. **性能影响**：指标记录对性能影响极小（< 1ms）
3. **磁盘空间**：每条记录约 200-300 字节，注意监控磁盘使用
4. **缓存策略**：当前未设置包过期时间，缓存会永久保留

## 未来改进方向

- [ ] 添加包生命周期管理（自动清理过期缓存）
- [ ] 实时仪表盘（Grafana）
- [ ] 按服务类型（PyPI/NPM/Docker）分类统计
- [ ] 下载失败自动重试策略优化
- [ ] 支持导出为 CSV 格式

