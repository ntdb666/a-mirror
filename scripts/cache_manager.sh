#!/bin/bash

# LightMirrors 缓存管理脚本

CACHE_DIR="./data/cache"

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 显示帮助信息
show_help() {
    echo "LightMirrors 缓存管理工具"
    echo ""
    echo "用法: $0 [命令]"
    echo ""
    echo "命令:"
    echo "  list            列出所有缓存的包"
    echo "  stats           显示缓存统计信息"
    echo "  search <关键词>  搜索特定包"
    echo "  size            显示缓存大小"
    echo "  top             显示最大的 10 个文件"
    echo "  downloading     显示正在下载的包"
    echo "  old [天数]       显示 N 天前的包（默认 30 天）"
    echo "  clean-old [天数] 清理 N 天前的包（默认 30 天）"
    echo "  clean-large [MB] 清理大于 N MB 的文件（默认 100 MB）"
    echo "  clean-all       清理所有缓存（需要确认）"
    echo "  help            显示此帮助信息"
    echo ""
}

# 列出所有缓存的包
list_packages() {
    echo -e "${GREEN}=== 缓存的包列表 ===${NC}"
    find "$CACHE_DIR" -type f ! -name "*.aria2" -exec ls -lh {} \; | tail -50
    echo ""
    echo "（显示最近 50 个文件）"
}

# 显示统计信息
show_stats() {
    echo -e "${GREEN}=== 缓存统计信息 ===${NC}"
    
    total_files=$(find "$CACHE_DIR" -type f ! -name "*.aria2" 2>/dev/null | wc -l)
    echo "总文件数: $total_files"
    
    whl_count=$(find "$CACHE_DIR" -name "*.whl" 2>/dev/null | wc -l)
    echo "Python Wheel 包: $whl_count"
    
    tar_count=$(find "$CACHE_DIR" -name "*.tar.gz" 2>/dev/null | wc -l)
    echo "Tar.gz 包: $tar_count"
    
    tgz_count=$(find "$CACHE_DIR" -name "*.tgz" 2>/dev/null | wc -l)
    echo "Tgz 包: $tgz_count"
    
    downloading=$(find "$CACHE_DIR" -name "*.aria2" 2>/dev/null | wc -l)
    echo "正在下载: $downloading"
    
    echo ""
}

# 显示缓存大小
show_size() {
    echo -e "${GREEN}=== 缓存大小 ===${NC}"
    du -sh "$CACHE_DIR" 2>/dev/null
    echo ""
    echo -e "${GREEN}=== 按来源统计 ===${NC}"
    du -h --max-depth=2 "$CACHE_DIR" 2>/dev/null | sort -rh | head -10
}

# 显示最大的文件
show_top() {
    echo -e "${GREEN}=== 最大的 10 个文件 ===${NC}"
    find "$CACHE_DIR" -type f ! -name "*.aria2" -exec du -h {} + 2>/dev/null | sort -rh | head -10
}

# 搜索包
search_package() {
    keyword=$1
    if [ -z "$keyword" ]; then
        echo -e "${RED}错误: 请提供搜索关键词${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}=== 搜索结果: $keyword ===${NC}"
    find "$CACHE_DIR" -type f -name "*$keyword*" ! -name "*.aria2" -exec ls -lh {} \;
}

# 显示正在下载的包
show_downloading() {
    echo -e "${GREEN}=== 正在下载的包 ===${NC}"
    aria2_files=$(find "$CACHE_DIR" -name "*.aria2" 2>/dev/null)
    
    if [ -z "$aria2_files" ]; then
        echo "当前没有正在下载的包"
    else
        echo "$aria2_files" | while read -r file; do
            basename=$(basename "$file" .aria2)
            echo "📥 $basename"
        done
    fi
    echo ""
}

# 显示旧文件
show_old() {
    days=${1:-30}
    echo -e "${GREEN}=== $days 天前的文件 ===${NC}"
    find "$CACHE_DIR" -type f ! -name "*.aria2" -mtime +$days -exec ls -lh {} \;
}

# 清理旧文件
clean_old() {
    days=${1:-30}
    
    count=$(find "$CACHE_DIR" -type f ! -name "*.aria2" -mtime +$days 2>/dev/null | wc -l)
    
    if [ "$count" -eq 0 ]; then
        echo "没有找到 $days 天前的文件"
        exit 0
    fi
    
    echo -e "${YELLOW}将删除 $count 个 $days 天前的文件${NC}"
    read -p "确认删除? (yes/no): " confirm
    
    if [ "$confirm" = "yes" ]; then
        find "$CACHE_DIR" -type f ! -name "*.aria2" -mtime +$days -delete
        echo -e "${GREEN}✓ 已删除${NC}"
    else
        echo "已取消"
    fi
}

# 清理大文件
clean_large() {
    size_mb=${1:-100}
    
    echo -e "${GREEN}=== 大于 ${size_mb}MB 的文件 ===${NC}"
    find "$CACHE_DIR" -type f -size +${size_mb}M ! -name "*.aria2" -exec ls -lh {} \;
    
    count=$(find "$CACHE_DIR" -type f -size +${size_mb}M ! -name "*.aria2" 2>/dev/null | wc -l)
    
    if [ "$count" -eq 0 ]; then
        echo "没有找到大于 ${size_mb}MB 的文件"
        exit 0
    fi
    
    echo ""
    echo -e "${YELLOW}找到 $count 个文件${NC}"
    read -p "确认删除这些文件? (yes/no): " confirm
    
    if [ "$confirm" = "yes" ]; then
        find "$CACHE_DIR" -type f -size +${size_mb}M ! -name "*.aria2" -delete
        echo -e "${GREEN}✓ 已删除${NC}"
    else
        echo "已取消"
    fi
}

# 清理所有缓存
clean_all() {
    echo -e "${RED}⚠️  警告: 这将删除所有缓存的包！${NC}"
    echo ""
    show_stats
    echo ""
    read -p "确认删除所有缓存? 输入 'DELETE-ALL' 确认: " confirm
    
    if [ "$confirm" = "DELETE-ALL" ]; then
        rm -rf "$CACHE_DIR"/*
        echo -e "${GREEN}✓ 所有缓存已清理${NC}"
    else
        echo "已取消"
    fi
}

# 主程序
case "$1" in
    list)
        list_packages
        ;;
    stats)
        show_stats
        ;;
    search)
        search_package "$2"
        ;;
    size)
        show_size
        ;;
    top)
        show_top
        ;;
    downloading)
        show_downloading
        ;;
    old)
        show_old "$2"
        ;;
    clean-old)
        clean_old "$2"
        ;;
    clean-large)
        clean_large "$2"
        ;;
    clean-all)
        clean_all
        ;;
    help|"")
        show_help
        ;;
    *)
        echo -e "${RED}未知命令: $1${NC}"
        echo ""
        show_help
        exit 1
        ;;
esac

