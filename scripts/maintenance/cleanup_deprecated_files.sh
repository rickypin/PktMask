#!/bin/bash
# PktMask项目废弃文件清理脚本
# 
# 用途: 清理项目中的废弃代码、缓存文件、临时文件等
# 作者: PktMask开发团队
# 日期: 2025-07-22
# 版本: v1.0

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="cleanup_backup_${TIMESTAMP}.tar.gz"

# 日志函数
log() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 显示帮助信息
show_help() {
    cat << EOF
PktMask项目废弃文件清理脚本

用法: $0 [选项]

选项:
  -h, --help          显示此帮助信息
  -d, --dry-run       预览模式，只显示将要删除的文件，不实际删除
  -b, --backup        清理前创建备份
  -f, --force         强制清理，跳过确认提示
  -v, --verbose       详细输出模式
  --cache-only        仅清理缓存文件
  --output-only       仅清理输出文件
  --system-only       仅清理系统文件

清理级别:
  --level-0           零风险清理 (缓存、系统文件、输出文件)
  --level-1           低风险清理 (包含重复备份)
  --level-2           中风险清理 (需人工确认)

示例:
  $0 --dry-run        # 预览将要清理的文件
  $0 --level-0 -b     # 零风险清理并创建备份
  $0 --cache-only     # 仅清理Python缓存
EOF
}

# 解析命令行参数
DRY_RUN=false
CREATE_BACKUP=false
FORCE=false
VERBOSE=false
CACHE_ONLY=false
OUTPUT_ONLY=false
SYSTEM_ONLY=false
CLEANUP_LEVEL=0

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -d|--dry-run)
            DRY_RUN=true
            shift
            ;;
        -b|--backup)
            CREATE_BACKUP=true
            shift
            ;;
        -f|--force)
            FORCE=true
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        --cache-only)
            CACHE_ONLY=true
            shift
            ;;
        --output-only)
            OUTPUT_ONLY=true
            shift
            ;;
        --system-only)
            SYSTEM_ONLY=true
            shift
            ;;
        --level-0)
            CLEANUP_LEVEL=0
            shift
            ;;
        --level-1)
            CLEANUP_LEVEL=1
            shift
            ;;
        --level-2)
            CLEANUP_LEVEL=2
            shift
            ;;
        *)
            log_error "未知选项: $1"
            show_help
            exit 1
            ;;
    esac
done

# 切换到项目根目录
cd "$PROJECT_ROOT"

# 统计函数
count_files() {
    local pattern="$1"
    find . -name "$pattern" -type f 2>/dev/null | wc -l | tr -d ' '
}

count_dirs() {
    local pattern="$1"
    find . -name "$pattern" -type d 2>/dev/null | wc -l | tr -d ' '
}

# 计算文件大小
calculate_size() {
    local pattern="$1"
    local type="$2"
    if [[ "$type" == "d" ]]; then
        find . -name "$pattern" -type d -exec du -sh {} + 2>/dev/null | awk '{sum+=$1} END {print sum "M"}'
    else
        find . -name "$pattern" -type f -exec du -sh {} + 2>/dev/null | awk '{sum+=$1} END {print sum "M"}'
    fi
}

# 显示清理统计
show_cleanup_stats() {
    log "正在分析项目文件..."
    
    echo
    echo "📊 清理统计预览:"
    echo "=================="
    
    # Python缓存文件
    local pycache_dirs=$(count_dirs "__pycache__")
    local pyc_files=$(count_files "*.pyc")
    echo "🐍 Python缓存文件:"
    echo "   - __pycache__ 目录: ${pycache_dirs}个"
    echo "   - .pyc 文件: ${pyc_files}个"
    
    # 系统文件
    local ds_store_files=$(count_files ".DS_Store")
    echo "🖥️  系统文件:"
    echo "   - .DS_Store 文件: ${ds_store_files}个"
    
    # 输出文件
    if [[ -d "./output/maskstage_validation" ]]; then
        local validation_files=$(find ./output/maskstage_validation -type f 2>/dev/null | wc -l | tr -d ' ')
        echo "📄 输出文件:"
        echo "   - 验证输出文件: ${validation_files}个"
    fi
    
    if [[ -d "./output/tmp" ]]; then
        local tmp_files=$(find ./output/tmp -type f 2>/dev/null | wc -l | tr -d ' ')
        echo "   - 临时分析文件: ${tmp_files}个"
    fi
    
    # 备份目录
    local backup_dirs=$(find . -maxdepth 1 -name "backup_refactor_*" -type d 2>/dev/null | wc -l | tr -d ' ')
    if [[ $backup_dirs -gt 0 ]]; then
        echo "💾 备份目录:"
        echo "   - 重构备份目录: ${backup_dirs}个"
    fi
    
    echo
}

# 创建备份
create_backup() {
    if [[ "$CREATE_BACKUP" == true ]]; then
        log "正在创建清理前备份..."
        
        local backup_items=()
        
        # 添加要备份的项目
        [[ -d "./output" ]] && backup_items+=("./output")
        [[ -d "./backup_refactor_20250721_230702" ]] && backup_items+=("./backup_refactor_20250721_230702")
        [[ -d "./backup_refactor_20250721_230749" ]] && backup_items+=("./backup_refactor_20250721_230749")
        [[ -d "./scripts/validation" ]] && backup_items+=("./scripts/validation")
        
        if [[ ${#backup_items[@]} -gt 0 ]]; then
            tar -czf "$BACKUP_FILE" "${backup_items[@]}" 2>/dev/null || true
            log_success "备份已创建: $BACKUP_FILE"
        else
            log_warning "没有找到需要备份的文件"
        fi
    fi
}

# 清理Python缓存文件
cleanup_python_cache() {
    if [[ "$CACHE_ONLY" == true ]] || [[ "$CLEANUP_LEVEL" -ge 0 ]]; then
        log "正在清理Python缓存文件..."
        
        if [[ "$DRY_RUN" == true ]]; then
            echo "将要删除的__pycache__目录:"
            find . -name "__pycache__" -type d
            echo
            echo "将要删除的.pyc文件:"
            find . -name "*.pyc" -type f
        else
            # 删除__pycache__目录
            find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
            
            # 删除.pyc文件
            find . -name "*.pyc" -type f -delete 2>/dev/null || true
            
            log_success "Python缓存文件清理完成"
        fi
    fi
}

# 清理系统文件
cleanup_system_files() {
    if [[ "$SYSTEM_ONLY" == true ]] || [[ "$CLEANUP_LEVEL" -ge 0 ]]; then
        log "正在清理系统文件..."
        
        if [[ "$DRY_RUN" == true ]]; then
            echo "将要删除的.DS_Store文件:"
            find . -name ".DS_Store" -type f
        else
            # 删除.DS_Store文件
            find . -name ".DS_Store" -type f -delete 2>/dev/null || true
            
            log_success "系统文件清理完成"
        fi
    fi
}

# 清理输出文件
cleanup_output_files() {
    if [[ "$OUTPUT_ONLY" == true ]] || [[ "$CLEANUP_LEVEL" -ge 0 ]]; then
        log "正在清理历史输出文件..."
        
        if [[ "$DRY_RUN" == true ]]; then
            echo "将要删除的输出目录:"
            [[ -d "./output/maskstage_validation" ]] && echo "  ./output/maskstage_validation/"
            [[ -d "./output/tmp" ]] && echo "  ./output/tmp/"
        else
            # 删除验证输出
            [[ -d "./output/maskstage_validation" ]] && rm -rf "./output/maskstage_validation"
            
            # 删除临时输出
            [[ -d "./output/tmp" ]] && rm -rf "./output/tmp"
            
            log_success "输出文件清理完成"
        fi
    fi
}

# 清理重复备份
cleanup_duplicate_backups() {
    if [[ "$CLEANUP_LEVEL" -ge 1 ]]; then
        log "正在清理重复备份目录..."
        
        if [[ "$DRY_RUN" == true ]]; then
            echo "将要删除的备份目录:"
            [[ -d "./backup_refactor_20250721_230702" ]] && echo "  ./backup_refactor_20250721_230702/"
        else
            # 删除较旧的备份，保留最新的
            [[ -d "./backup_refactor_20250721_230702" ]] && rm -rf "./backup_refactor_20250721_230702"
            
            log_success "重复备份清理完成"
        fi
    fi
}

# 清理空目录
cleanup_empty_dirs() {
    if [[ "$CLEANUP_LEVEL" -ge 1 ]]; then
        log "正在清理空目录..."
        
        local empty_dirs=("./backup" "./output/monitoring")
        
        if [[ "$DRY_RUN" == true ]]; then
            echo "将要删除的空目录:"
            for dir in "${empty_dirs[@]}"; do
                [[ -d "$dir" ]] && [[ -z "$(ls -A "$dir" 2>/dev/null)" ]] && echo "  $dir"
            done
        else
            for dir in "${empty_dirs[@]}"; do
                [[ -d "$dir" ]] && [[ -z "$(ls -A "$dir" 2>/dev/null)" ]] && rmdir "$dir" 2>/dev/null || true
            done
            
            log_success "空目录清理完成"
        fi
    fi
}

# 主清理函数
main_cleanup() {
    log "开始执行清理操作..."
    log "清理级别: Level-$CLEANUP_LEVEL"
    
    if [[ "$DRY_RUN" == true ]]; then
        log_warning "预览模式 - 不会实际删除文件"
    fi
    
    # 显示统计信息
    show_cleanup_stats
    
    # 确认清理
    if [[ "$FORCE" != true ]] && [[ "$DRY_RUN" != true ]]; then
        echo
        read -p "确认执行清理操作? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log "清理操作已取消"
            exit 0
        fi
    fi
    
    # 创建备份
    create_backup
    
    # 执行清理
    cleanup_python_cache
    cleanup_system_files
    cleanup_output_files
    cleanup_duplicate_backups
    cleanup_empty_dirs
    
    if [[ "$DRY_RUN" != true ]]; then
        log_success "清理操作完成!"
        
        if [[ "$CREATE_BACKUP" == true ]]; then
            echo
            log "备份文件: $BACKUP_FILE"
            log "如需恢复，请运行: tar -xzf $BACKUP_FILE"
        fi
    else
        log "预览完成 - 使用 --force 参数执行实际清理"
    fi
}

# 执行主函数
main_cleanup
