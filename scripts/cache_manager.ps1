# LightMirrors 缓存管理脚本 (PowerShell 版本)

param(
    [string]$Command = "help",
    [string]$Param = ""
)

$CACHE_DIR = ".\data\cache"

# 显示帮助信息
function Show-Help {
    Write-Host "LightMirrors 缓存管理工具" -ForegroundColor Green
    Write-Host ""
    Write-Host "用法: .\scripts\cache_manager.ps1 <命令> [参数]"
    Write-Host ""
    Write-Host "命令:"
    Write-Host "  list            列出所有缓存的包"
    Write-Host "  stats           显示缓存统计信息"
    Write-Host "  search <关键词>  搜索特定包"
    Write-Host "  size            显示缓存大小"
    Write-Host "  top             显示最大的 10 个文件"
    Write-Host "  downloading     显示正在下载的包"
    Write-Host "  old [天数]       显示 N 天前的包（默认 30 天）"
    Write-Host "  clean-old [天数] 清理 N 天前的包（默认 30 天）"
    Write-Host "  clean-large [MB] 清理大于 N MB 的文件（默认 100 MB）"
    Write-Host "  clean-all       清理所有缓存（需要确认）"
    Write-Host "  help            显示此帮助信息"
    Write-Host ""
    Write-Host "示例:"
    Write-Host "  .\scripts\cache_manager.ps1 stats"
    Write-Host "  .\scripts\cache_manager.ps1 search numpy"
    Write-Host "  .\scripts\cache_manager.ps1 clean-old 30"
    Write-Host ""
}

# 列出所有缓存的包
function Show-List {
    Write-Host "=== 缓存的包列表 ===" -ForegroundColor Green
    
    if (Test-Path $CACHE_DIR) {
        Get-ChildItem -Path $CACHE_DIR -File -Recurse -Exclude "*.aria2" | 
            Select-Object -Last 50 | 
            Format-Table Name, @{Label="Size(MB)";Expression={"{0:N2}" -f ($_.Length/1MB)}}, LastWriteTime -AutoSize
        Write-Host ""
        Write-Host "（显示最近 50 个文件）"
    } else {
        Write-Host "缓存目录不存在" -ForegroundColor Red
    }
}

# 显示统计信息
function Show-Stats {
    Write-Host "=== 缓存统计信息 ===" -ForegroundColor Green
    
    if (-not (Test-Path $CACHE_DIR)) {
        Write-Host "缓存目录不存在" -ForegroundColor Red
        return
    }
    
    $allFiles = Get-ChildItem -Path $CACHE_DIR -File -Recurse -Exclude "*.aria2"
    $totalFiles = $allFiles.Count
    Write-Host "总文件数: $totalFiles"
    
    $whlCount = ($allFiles | Where-Object { $_.Extension -eq ".whl" }).Count
    Write-Host "Python Wheel 包: $whlCount"
    
    $tarGzCount = ($allFiles | Where-Object { $_.Name -like "*.tar.gz" }).Count
    Write-Host "Tar.gz 包: $tarGzCount"
    
    $tgzCount = ($allFiles | Where-Object { $_.Extension -eq ".tgz" }).Count
    Write-Host "Tgz 包: $tgzCount"
    
    $aria2Files = Get-ChildItem -Path $CACHE_DIR -File -Recurse -Filter "*.aria2"
    Write-Host "正在下载: $($aria2Files.Count)"
    
    $totalSize = ($allFiles | Measure-Object -Property Length -Sum).Sum / 1GB
    Write-Host "总缓存大小: $("{0:N2}" -f $totalSize) GB"
    
    Write-Host ""
}

# 显示缓存大小
function Show-Size {
    Write-Host "=== 缓存大小 ===" -ForegroundColor Green
    
    if (-not (Test-Path $CACHE_DIR)) {
        Write-Host "缓存目录不存在" -ForegroundColor Red
        return
    }
    
    $totalSize = (Get-ChildItem -Path $CACHE_DIR -Recurse -File | Measure-Object -Property Length -Sum).Sum
    $sizeGB = $totalSize / 1GB
    $sizeMB = $totalSize / 1MB
    
    if ($sizeGB -gt 1) {
        Write-Host "总缓存大小: $("{0:N2}" -f $sizeGB) GB"
    } else {
        Write-Host "总缓存大小: $("{0:N2}" -f $sizeMB) MB"
    }
    
    Write-Host ""
    Write-Host "=== 按来源统计（前 10） ===" -ForegroundColor Green
    
    Get-ChildItem -Path $CACHE_DIR -Directory | ForEach-Object {
        $dirSize = (Get-ChildItem -Path $_.FullName -Recurse -File | Measure-Object -Property Length -Sum).Sum / 1MB
        [PSCustomObject]@{
            Directory = $_.Name
            "Size(MB)" = "{0:N2}" -f $dirSize
        }
    } | Sort-Object {[double]$_."Size(MB)"} -Descending | Select-Object -First 10 | Format-Table -AutoSize
}

# 显示最大的文件
function Show-Top {
    Write-Host "=== 最大的 10 个文件 ===" -ForegroundColor Green
    
    if (-not (Test-Path $CACHE_DIR)) {
        Write-Host "缓存目录不存在" -ForegroundColor Red
        return
    }
    
    Get-ChildItem -Path $CACHE_DIR -File -Recurse -Exclude "*.aria2" | 
        Sort-Object Length -Descending | 
        Select-Object -First 10 | 
        Format-Table Name, @{Label="Size(MB)";Expression={"{0:N2}" -f ($_.Length/1MB)}}, FullName -AutoSize
}

# 搜索包
function Search-Package {
    param([string]$Keyword)
    
    if ([string]::IsNullOrWhiteSpace($Keyword)) {
        Write-Host "错误: 请提供搜索关键词" -ForegroundColor Red
        return
    }
    
    Write-Host "=== 搜索结果: $Keyword ===" -ForegroundColor Green
    
    if (-not (Test-Path $CACHE_DIR)) {
        Write-Host "缓存目录不存在" -ForegroundColor Red
        return
    }
    
    $results = Get-ChildItem -Path $CACHE_DIR -File -Recurse -Exclude "*.aria2" | 
        Where-Object { $_.Name -like "*$Keyword*" }
    
    if ($results.Count -eq 0) {
        Write-Host "未找到匹配的包" -ForegroundColor Yellow
    } else {
        $results | Format-Table Name, @{Label="Size(MB)";Expression={"{0:N2}" -f ($_.Length/1MB)}}, LastWriteTime, FullName -AutoSize
        Write-Host ""
        Write-Host "找到 $($results.Count) 个文件"
    }
}

# 显示正在下载的包
function Show-Downloading {
    Write-Host "=== 正在下载的包 ===" -ForegroundColor Green
    
    if (-not (Test-Path $CACHE_DIR)) {
        Write-Host "缓存目录不存在" -ForegroundColor Red
        return
    }
    
    $aria2Files = Get-ChildItem -Path $CACHE_DIR -File -Recurse -Filter "*.aria2"
    
    if ($aria2Files.Count -eq 0) {
        Write-Host "当前没有正在下载的包"
    } else {
        foreach ($file in $aria2Files) {
            $basename = $file.BaseName
            Write-Host "📥 $basename"
        }
    }
    Write-Host ""
}

# 显示旧文件
function Show-Old {
    param([int]$Days = 30)
    
    Write-Host "=== $Days 天前的文件 ===" -ForegroundColor Green
    
    if (-not (Test-Path $CACHE_DIR)) {
        Write-Host "缓存目录不存在" -ForegroundColor Red
        return
    }
    
    $cutoffDate = (Get-Date).AddDays(-$Days)
    $oldFiles = Get-ChildItem -Path $CACHE_DIR -File -Recurse -Exclude "*.aria2" | 
        Where-Object { $_.LastWriteTime -lt $cutoffDate }
    
    if ($oldFiles.Count -eq 0) {
        Write-Host "没有找到 $Days 天前的文件"
    } else {
        $oldFiles | Format-Table Name, @{Label="Size(MB)";Expression={"{0:N2}" -f ($_.Length/1MB)}}, LastWriteTime -AutoSize
        Write-Host ""
        Write-Host "共 $($oldFiles.Count) 个文件"
    }
}

# 清理旧文件
function Clean-Old {
    param([int]$Days = 30)
    
    if (-not (Test-Path $CACHE_DIR)) {
        Write-Host "缓存目录不存在" -ForegroundColor Red
        return
    }
    
    $cutoffDate = (Get-Date).AddDays(-$Days)
    $oldFiles = Get-ChildItem -Path $CACHE_DIR -File -Recurse -Exclude "*.aria2" | 
        Where-Object { $_.LastWriteTime -lt $cutoffDate }
    
    if ($oldFiles.Count -eq 0) {
        Write-Host "没有找到 $Days 天前的文件"
        return
    }
    
    $totalSize = ($oldFiles | Measure-Object -Property Length -Sum).Sum / 1MB
    Write-Host "将删除 $($oldFiles.Count) 个 $Days 天前的文件，总大小: $("{0:N2}" -f $totalSize) MB" -ForegroundColor Yellow
    
    $confirm = Read-Host "确认删除? (yes/no)"
    
    if ($confirm -eq "yes") {
        $oldFiles | Remove-Item -Force
        Write-Host "✓ 已删除" -ForegroundColor Green
    } else {
        Write-Host "已取消"
    }
}

# 清理大文件
function Clean-Large {
    param([int]$SizeMB = 100)
    
    Write-Host "=== 大于 ${SizeMB}MB 的文件 ===" -ForegroundColor Green
    
    if (-not (Test-Path $CACHE_DIR)) {
        Write-Host "缓存目录不存在" -ForegroundColor Red
        return
    }
    
    $largeFiles = Get-ChildItem -Path $CACHE_DIR -File -Recurse -Exclude "*.aria2" | 
        Where-Object { $_.Length -gt ($SizeMB * 1MB) }
    
    if ($largeFiles.Count -eq 0) {
        Write-Host "没有找到大于 ${SizeMB}MB 的文件"
        return
    }
    
    $largeFiles | Format-Table Name, @{Label="Size(MB)";Expression={"{0:N2}" -f ($_.Length/1MB)}}, FullName -AutoSize
    
    Write-Host ""
    Write-Host "找到 $($largeFiles.Count) 个文件" -ForegroundColor Yellow
    $confirm = Read-Host "确认删除这些文件? (yes/no)"
    
    if ($confirm -eq "yes") {
        $largeFiles | Remove-Item -Force
        Write-Host "✓ 已删除" -ForegroundColor Green
    } else {
        Write-Host "已取消"
    }
}

# 清理所有缓存
function Clean-All {
    Write-Host "⚠️  警告: 这将删除所有缓存的包！" -ForegroundColor Red
    Write-Host ""
    
    Show-Stats
    
    Write-Host ""
    $confirm = Read-Host "确认删除所有缓存? 输入 'DELETE-ALL' 确认"
    
    if ($confirm -eq "DELETE-ALL") {
        if (Test-Path $CACHE_DIR) {
            Remove-Item -Path "$CACHE_DIR\*" -Recurse -Force
            Write-Host "✓ 所有缓存已清理" -ForegroundColor Green
        }
    } else {
        Write-Host "已取消"
    }
}

# 主程序
switch ($Command.ToLower()) {
    "list" { Show-List }
    "stats" { Show-Stats }
    "search" { Search-Package -Keyword $Param }
    "size" { Show-Size }
    "top" { Show-Top }
    "downloading" { Show-Downloading }
    "old" { 
        if ($Param) {
            Show-Old -Days ([int]$Param)
        } else {
            Show-Old
        }
    }
    "clean-old" { 
        if ($Param) {
            Clean-Old -Days ([int]$Param)
        } else {
            Clean-Old
        }
    }
    "clean-large" { 
        if ($Param) {
            Clean-Large -SizeMB ([int]$Param)
        } else {
            Clean-Large
        }
    }
    "clean-all" { Clean-All }
    default { Show-Help }
}

