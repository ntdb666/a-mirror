# 缓存包管理指南

## 概述

LightMirrors 将下载的包缓存在文件系统中，本指南介绍如何查看和管理这些缓存包。

## 缓存目录结构

```
data/cache/
├── files.pythonhosted.org/          # PyPI 包缓存
│   └── packages/
│       └── xx/xx/hash/
│           └── package-1.0.0.whl
├── registry.npmjs.org/              # NPM 包缓存
│   └── package-name/
│       └── package-1.0.0.tgz
├── download.pytorch.org/            # PyTorch 包缓存
└── registry-1.docker.io/            # Docker 镜像层缓存
```

**重要文件：**
- 普通文件（如 `.whl`, `.tar.gz`, `.tgz`）= 已完成下载
- `.aria2` 文件（如 `package.whl.aria2`）= 正在下载中

## 快速使用

### 使用管理脚本（推荐）

#### Windows (PowerShell)
```powershell
# 查看缓存统计
.\scripts\cache_manager.ps1 stats

# 查看所有缓存包
.\scripts\cache_manager.ps1 list

# 搜索特定包
.\scripts\cache_manager.ps1 search numpy

# 查看最大的文件
.\scripts\cache_manager.ps1 top

# 查看正在下载的包
.\scripts\cache_manager.ps1 downloading

# 清理 30 天前的包
.\scripts\cache_manager.ps1 clean-old 30

# 清理大于 100MB 的文件
.\scripts\cache_manager.ps1 clean-large 100
```

#### Linux/Mac (Bash)
```bash
# 查看缓存统计
./scripts/cache_manager.sh stats

# 查看所有缓存包
./scripts/cache_manager.sh list

# 搜索特定包
./scripts/cache_manager.sh search numpy

# 查看最大的文件
./scripts/cache_manager.sh top
```

## 手动管理命令

### 1. 查看缓存统计

**Windows (PowerShell):**
```powershell
# 总文件数
(Get-ChildItem -Path data\cache -File -Recurse -Exclude "*.aria2").Count

# 总缓存大小
$size = (Get-ChildItem -Path data\cache -Recurse -File | Measure-Object -Property Length -Sum).Sum
"{0:N2} GB" -f ($size / 1GB)

# Python 包数量
(Get-ChildItem -Path data\cache -File -Recurse -Filter "*.whl").Count
```

**Linux/Mac (Bash):**
```bash
# 总文件数
find data/cache/ -type f ! -name "*.aria2" | wc -l

# 总缓存大小
du -sh data/cache/

# Python 包数量
find data/cache/ -name "*.whl" | wc -l
```

### 2. 搜索特定包

**Windows:**
```powershell
# 搜索 numpy 包
Get-ChildItem -Path data\cache -File -Recurse | Where-Object { $_.Name -like "*numpy*" }

# 搜索特定版本
Get-ChildItem -Path data\cache -File -Recurse | Where-Object { $_.Name -like "*numpy-1.24.0*" }
```

**Linux/Mac:**
```bash
# 搜索 numpy 包
find data/cache/ -name "*numpy*"

# 搜索特定版本
find data/cache/ -name "*numpy-1.24.0*"
```

### 3. 查看正在下载的包

**Windows:**
```powershell
Get-ChildItem -Path data\cache -Filter "*.aria2" -Recurse | ForEach-Object { $_.BaseName }
```

**Linux/Mac:**
```bash
find data/cache/ -name "*.aria2" -exec basename {} .aria2 \;
```

### 4. 查看最大的文件

**Windows:**
```powershell
Get-ChildItem -Path data\cache -File -Recurse -Exclude "*.aria2" | 
    Sort-Object Length -Descending | 
    Select-Object -First 10 | 
    Format-Table Name, @{Label="Size(MB)";Expression={"{0:N2}" -f ($_.Length/1MB)}}
```

**Linux/Mac:**
```bash
find data/cache/ -type f ! -name "*.aria2" -exec du -h {} + | sort -rh | head -10
```

## 清理策略

### 按时间清理

**清理 30 天前的包：**

Windows:
```powershell
$cutoffDate = (Get-Date).AddDays(-30)
Get-ChildItem -Path data\cache -File -Recurse -Exclude "*.aria2" | 
    Where-Object { $_.LastWriteTime -lt $cutoffDate } | 
    Remove-Item -Force
```

Linux/Mac:
```bash
find data/cache/ -type f ! -name "*.aria2" -mtime +30 -delete
```

### 按大小清理

**清理大于 100MB 的文件：**

Windows:
```powershell
Get-ChildItem -Path data\cache -File -Recurse -Exclude "*.aria2" | 
    Where-Object { $_.Length -gt 100MB } | 
    Remove-Item -Force
```

Linux/Mac:
```bash
find data/cache/ -type f -size +100M ! -name "*.aria2" -delete
```

### 清理特定来源

**清理 PyPI 缓存：**
```bash
rm -rf data/cache/files.pythonhosted.org/
```

**清理 NPM 缓存：**
```bash
rm -rf data/cache/registry.npmjs.org/
```

### 清理所有缓存

⚠️ **警告：这将删除所有缓存！**

Windows:
```powershell
Remove-Item -Path data\cache\* -Recurse -Force
```

Linux/Mac:
```bash
rm -rf data/cache/*
```

## 在 Docker 容器中管理

### 进入容器查看

```bash
# 进入 lightmirrors 容器
docker-compose exec lightmirrors sh

# 查看缓存
ls -lh /app/cache/

# 查看特定来源
ls -lh /app/cache/files.pythonhosted.org/packages/

# 退出容器
exit
```

### 从宿主机清理

```bash
# 停止服务
docker-compose down

# 清理缓存
rm -rf data/cache/*

# 重启服务
docker-compose up -d
```

## 监控缓存增长

### 定期查看缓存大小

创建监控脚本 `scripts/monitor_cache.ps1`:

```powershell
while ($true) {
    Clear-Host
    Write-Host "=== 缓存监控 ===" -ForegroundColor Green
    Write-Host "时间: $(Get-Date)"
    
    $size = (Get-ChildItem -Path data\cache -Recurse -File | Measure-Object -Property Length -Sum).Sum
    Write-Host "缓存大小: $("{0:N2}" -f ($size / 1GB)) GB"
    
    $fileCount = (Get-ChildItem -Path data\cache -File -Recurse -Exclude "*.aria2").Count
    Write-Host "文件数量: $fileCount"
    
    $downloading = (Get-ChildItem -Path data\cache -Filter "*.aria2" -Recurse).Count
    Write-Host "正在下载: $downloading"
    
    Start-Sleep -Seconds 60
}
```

运行：
```powershell
.\scripts\monitor_cache.ps1
```

## 缓存生命周期建议

由于当前项目**未设置包生命周期**，缓存会永久保留。建议根据使用情况定期清理：

### 推荐清理策略

1. **按时间清理**（每月）
   - 清理 30 天未访问的包
   - 保留常用包

2. **按大小清理**（空间不足时）
   - 优先清理大文件（> 100MB）
   - 清理不常用的大型包

3. **按来源清理**（针对性）
   - 根据使用频率清理特定来源
   - 例如：很少用 PyTorch，可清理 download.pytorch.org

### 自动化清理脚本

创建定时任务每周清理旧包：

**Windows 任务计划程序：**
1. 打开"任务计划程序"
2. 创建基本任务
3. 触发器：每周
4. 操作：启动程序 `powershell.exe`
5. 参数：`-File C:\path\to\scripts\cache_manager.ps1 clean-old 30`

**Linux Cron：**
```bash
# 编辑 crontab
crontab -e

# 添加每周日凌晨 2 点清理
0 2 * * 0 cd /path/to/LightMirrors && ./scripts/cache_manager.sh clean-old 30
```

## 故障排查

### 缓存文件损坏

如果包下载失败，可能留下损坏的文件：

```bash
# 查找 0 字节文件
find data/cache/ -type f -size 0

# 删除 0 字节文件
find data/cache/ -type f -size 0 -delete
```

### Aria2 未完成文件

清理残留的 .aria2 文件：

```bash
# 查找
find data/cache/ -name "*.aria2"

# 删除（会中断下载）
find data/cache/ -name "*.aria2" -delete
```

### 磁盘空间不足

快速释放空间：

1. 清理大文件
2. 清理旧文件
3. 清理不常用的来源

```powershell
# Windows - 释放 10GB 空间
.\scripts\cache_manager.ps1 clean-large 200
.\scripts\cache_manager.ps1 clean-old 7
```

## 与量化数据配合使用

结合 `data/metrics/metrics.json` 分析缓存效率：

```python
import json
import pandas as pd

# 读取量化数据
with open('data/metrics/metrics.json', 'r') as f:
    metrics = json.load(f)

df = pd.DataFrame(metrics)

# 找出从未被二次访问的包（缓存命中率低）
packages = df.groupby('package_name').agg({
    'cache_hit': 'sum',
    'file_size': 'first'
}).reset_index()

# 只下载一次且占用空间大的包（可考虑清理）
single_use_large = packages[
    (packages['cache_hit'] == 0) & 
    (packages['file_size'] > 50*1024*1024)  # > 50MB
]

print("建议清理的包：")
print(single_use_large)
```

## 最佳实践

1. **定期检查**：每周查看缓存统计
2. **按需清理**：根据磁盘使用情况清理
3. **保留热点**：不要清理高频使用的包
4. **记录操作**：清理前备份量化数据
5. **监控增长**：关注缓存增长速度

## 相关文档

- [量化数据说明](../data/metrics/README.md)
- [功能更新说明](../METRICS_UPDATE.md)
- [项目 README](../README.md)

