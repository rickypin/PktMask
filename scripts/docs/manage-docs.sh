#!/bin/bash
# PktMask 文档管理工具
# 用途：提供文档创建、检查、更新等功能的统一入口

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DOCS_DIR="$PROJECT_ROOT/docs"
SCRIPTS_DIR="$PROJECT_ROOT/scripts/docs"

# 显示帮助信息
show_help() {
    cat << EOF
PktMask 文档管理工具

用法: $0 <命令> [选项]

命令:
  create <type> <name>     创建新文档
  check                    运行所有质量检查
  check-links             检查链接有效性
  check-format            检查格式规范
  check-freshness         检查文档时效性
  stats                   生成统计报告
  update-index            更新 README 索引
  validate                验证文档结构
  help                    显示此帮助信息

文档类型 (用于 create 命令):
  user-guide              用户指南
  dev-guide               开发者指南
  api-doc                 API 文档
  arch-doc                架构文档
  tool-guide              工具指南

示例:
  $0 create user-guide new-feature-guide
  $0 check
  $0 stats
  $0 update-index user

EOF
}

# 日志函数
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# 检查依赖
check_dependencies() {
    local missing_deps=()
    
    # 检查必需的命令
    for cmd in find grep sed awk; do
        if ! command -v "$cmd" &> /dev/null; then
            missing_deps+=("$cmd")
        fi
    done
    
    if [[ ${#missing_deps[@]} -gt 0 ]]; then
        log_error "缺少必需的依赖: ${missing_deps[*]}"
        exit 1
    fi
}

# 创建新文档
create_document() {
    local doc_type="$1"
    local doc_name="$2"
    
    if [[ -z "$doc_type" || -z "$doc_name" ]]; then
        log_error "用法: $0 create <type> <name>"
        exit 1
    fi
    
    # 确定目标目录和模板
    local target_dir=""
    local template_type=""
    
    case "$doc_type" in
        "user-guide")
            target_dir="$DOCS_DIR/user"
            template_type="user"
            ;;
        "dev-guide")
            target_dir="$DOCS_DIR/dev"
            template_type="dev"
            ;;
        "api-doc")
            target_dir="$DOCS_DIR/api"
            template_type="api"
            ;;
        "arch-doc")
            target_dir="$DOCS_DIR/architecture"
            template_type="arch"
            ;;
        "tool-guide")
            target_dir="$DOCS_DIR/tools"
            template_type="tool"
            ;;
        *)
            log_error "不支持的文档类型: $doc_type"
            log_info "支持的类型: user-guide, dev-guide, api-doc, arch-doc, tool-guide"
            exit 1
            ;;
    esac
    
    # 生成文件名
    local filename="${doc_name}.md"
    local filepath="$target_dir/$filename"
    
    # 检查文件是否已存在
    if [[ -f "$filepath" ]]; then
        log_error "文档已存在: $filepath"
        exit 1
    fi
    
    # 创建目录（如果不存在）
    mkdir -p "$target_dir"
    
    # 生成文档内容
    local current_date=$(date '+%Y-%m-%d')
    local doc_title=$(echo "$doc_name" | sed 's/-/ /g' | sed 's/\b\w/\U&/g')
    
    cat > "$filepath" << EOF
# $doc_title

> **版本**: v1.0.0  
> **创建日期**: $current_date  
> **最后更新**: $current_date  
> **适用范围**: PktMask ≥ 4.0.0  
> **维护状态**: ✅ 活跃维护  

---

## 1. 概述

### 1.1 简介

{请在此处添加文档的基本介绍}

### 1.2 主要内容

- 内容点1
- 内容点2
- 内容点3

---

## 2. 详细说明

### 2.1 章节1

{请在此处添加详细内容}

### 2.2 章节2

{请在此处添加详细内容}

---

## 3. 示例

### 3.1 基本示例

\`\`\`bash
# 示例命令
echo "Hello, PktMask!"
\`\`\`

### 3.2 高级示例

\`\`\`python
# Python 示例代码
def example_function():
    return "示例结果"
\`\`\`

---

## 4. 相关资源

- [相关文档1](链接)
- [相关文档2](链接)

---

> 💡 **提示**: 请根据实际需要修改此模板内容，并更新相应的 README.md 索引。

EOF
    
    log_success "文档已创建: $filepath"
    log_info "请记得更新 $target_dir/README.md 中的索引"
    
    # 提示用户下一步操作
    echo ""
    log_info "建议的下一步操作:"
    echo "1. 编辑文档内容: $filepath"
    echo "2. 更新索引: $0 update-index $(basename "$target_dir")"
    echo "3. 运行质量检查: $0 check"
}

# 检查链接有效性
check_links() {
    log_info "检查文档链接有效性..."
    
    local error_count=0
    
    # 检查内部链接
    while IFS= read -r -d '' file; do
        log_info "检查文件: $(basename "$file")"
        
        # 提取相对链接
        while IFS= read -r line; do
            if [[ -n "$line" ]]; then
                local link_path=$(echo "$line" | sed -n 's/.*](\([^)]*\)).*/\1/p')
                if [[ -n "$link_path" && "$link_path" =~ ^\.\./ ]]; then
                    local abs_path="$(dirname "$file")/$link_path"
                    if [[ ! -f "$abs_path" ]]; then
                        log_error "无效链接: $(basename "$file") -> $link_path"
                        ((error_count++))
                    fi
                fi
            fi
        done < <(grep -n "](\.\./" "$file" 2>/dev/null || true)
        
    done < <(find "$DOCS_DIR" -name "*.md" -print0)
    
    if [[ $error_count -eq 0 ]]; then
        log_success "所有链接检查通过"
    else
        log_error "发现 $error_count 个无效链接"
        return 1
    fi
}

# 检查格式规范
check_format() {
    log_info "检查文档格式规范..."
    
    local error_count=0
    
    # 检查文件命名规范
    while IFS= read -r -d '' file; do
        local filename=$(basename "$file")
        if [[ "$filename" != "README.md" && ! "$filename" =~ ^[a-z0-9-]+\.md$ ]]; then
            log_error "文件命名不规范: $filename (应使用 kebab-case)"
            ((error_count++))
        fi
    done < <(find "$DOCS_DIR" -name "*.md" -print0)
    
    # 检查文档头部信息
    while IFS= read -r -d '' file; do
        if [[ "$(basename "$file")" != "README.md" ]]; then
            if ! head -10 "$file" | grep -q "> \*\*版本\*\*:"; then
                log_warning "缺少版本信息: $(basename "$file")"
            fi
            if ! head -10 "$file" | grep -q "> \*\*适用范围\*\*:"; then
                log_warning "缺少适用范围: $(basename "$file")"
            fi
        fi
    done < <(find "$DOCS_DIR" -name "*.md" -print0)
    
    if [[ $error_count -eq 0 ]]; then
        log_success "格式检查通过"
    else
        log_error "发现 $error_count 个格式问题"
        return 1
    fi
}

# 检查文档时效性
check_freshness() {
    log_info "检查文档时效性..."
    
    local warn_days=90
    local critical_days=180
    local current_date=$(date +%s)
    local warning_count=0
    local critical_count=0
    
    while IFS= read -r -d '' file; do
        local file_date=$(stat -f %m "$file" 2>/dev/null || stat -c %Y "$file" 2>/dev/null)
        local days_old=$(( (current_date - file_date) / 86400 ))
        
        if [[ $days_old -gt $critical_days ]]; then
            log_error "严重过期 ($days_old 天): $(basename "$file")"
            ((critical_count++))
        elif [[ $days_old -gt $warn_days ]]; then
            log_warning "需要更新 ($days_old 天): $(basename "$file")"
            ((warning_count++))
        fi
    done < <(find "$DOCS_DIR" -name "*.md" -print0)
    
    log_info "时效性检查完成: $warning_count 个警告, $critical_count 个严重过期"
    
    if [[ $critical_count -gt 0 ]]; then
        return 1
    fi
}

# 生成统计报告
generate_stats() {
    log_info "生成文档统计报告..."
    
    # 统计文档数量
    local total_docs=$(find "$DOCS_DIR" -name "*.md" | wc -l)
    local user_docs=$(find "$DOCS_DIR/user" -name "*.md" 2>/dev/null | wc -l || echo 0)
    local dev_docs=$(find "$DOCS_DIR/dev" -name "*.md" 2>/dev/null | wc -l || echo 0)
    local api_docs=$(find "$DOCS_DIR/api" -name "*.md" 2>/dev/null | wc -l || echo 0)
    local arch_docs=$(find "$DOCS_DIR/architecture" -name "*.md" 2>/dev/null | wc -l || echo 0)
    local tool_docs=$(find "$DOCS_DIR/tools" -name "*.md" 2>/dev/null | wc -l || echo 0)
    local archive_docs=$(find "$DOCS_DIR/archive" -name "*.md" 2>/dev/null | wc -l || echo 0)
    
    # 统计内容规模
    local total_lines=$(find "$DOCS_DIR" -name "*.md" -exec wc -l {} + 2>/dev/null | tail -1 | awk '{print $1}' || echo 0)
    local total_words=$(find "$DOCS_DIR" -name "*.md" -exec wc -w {} + 2>/dev/null | tail -1 | awk '{print $1}' || echo 0)
    
    # 显示统计结果
    echo ""
    echo "📊 PktMask 文档统计报告"
    echo "=========================="
    echo ""
    echo "📁 文档分布:"
    echo "  用户文档:     $user_docs"
    echo "  开发者文档:   $dev_docs"
    echo "  API 文档:     $api_docs"
    echo "  架构文档:     $arch_docs"
    echo "  工具文档:     $tool_docs"
    echo "  历史存档:     $archive_docs"
    echo "  总计:         $total_docs"
    echo ""
    echo "📈 内容规模:"
    echo "  总行数:       $(printf "%'d" $total_lines)"
    echo "  总词数:       $(printf "%'d" $total_words)"
    echo "  平均行数:     $(( total_lines / total_docs ))"
    echo ""
    
    log_success "统计报告生成完成"
}

# 更新 README 索引
update_index() {
    local target_dir="$1"
    
    if [[ -z "$target_dir" ]]; then
        log_error "用法: $0 update-index <directory>"
        log_info "可用目录: user, dev, api, architecture, tools, archive"
        exit 1
    fi
    
    local full_path="$DOCS_DIR/$target_dir"
    
    if [[ ! -d "$full_path" ]]; then
        log_error "目录不存在: $full_path"
        exit 1
    fi
    
    log_info "更新 $target_dir 目录的 README 索引..."
    
    # 这里可以添加自动更新 README.md 的逻辑
    # 目前只是提示用户手动更新
    log_warning "请手动更新 $full_path/README.md 中的文档索引"
    
    # 列出目录中的所有 .md 文件（除了 README.md）
    echo ""
    echo "目录中的文档文件:"
    find "$full_path" -maxdepth 1 -name "*.md" ! -name "README.md" | sort | while read file; do
        echo "  - $(basename "$file")"
    done
}

# 验证文档结构
validate_structure() {
    log_info "验证文档目录结构..."
    
    local required_dirs=("user" "dev" "api" "architecture" "tools" "archive")
    local missing_dirs=()
    
    for dir in "${required_dirs[@]}"; do
        if [[ ! -d "$DOCS_DIR/$dir" ]]; then
            missing_dirs+=("$dir")
        fi
    done
    
    if [[ ${#missing_dirs[@]} -gt 0 ]]; then
        log_error "缺少必需的目录: ${missing_dirs[*]}"
        return 1
    fi
    
    # 检查每个目录是否有 README.md
    for dir in "${required_dirs[@]}"; do
        if [[ ! -f "$DOCS_DIR/$dir/README.md" ]]; then
            log_warning "缺少索引文件: $dir/README.md"
        fi
    done
    
    log_success "文档结构验证通过"
}

# 运行所有检查
run_all_checks() {
    log_info "运行所有文档质量检查..."
    
    local failed_checks=()
    
    # 运行各项检查
    if ! validate_structure; then
        failed_checks+=("structure")
    fi
    
    if ! check_format; then
        failed_checks+=("format")
    fi
    
    if ! check_links; then
        failed_checks+=("links")
    fi
    
    if ! check_freshness; then
        failed_checks+=("freshness")
    fi
    
    # 报告结果
    if [[ ${#failed_checks[@]} -eq 0 ]]; then
        log_success "所有检查通过！"
    else
        log_error "以下检查失败: ${failed_checks[*]}"
        return 1
    fi
}

# 主函数
main() {
    # 检查依赖
    check_dependencies
    
    # 解析命令
    case "${1:-help}" in
        "create")
            create_document "$2" "$3"
            ;;
        "check")
            run_all_checks
            ;;
        "check-links")
            check_links
            ;;
        "check-format")
            check_format
            ;;
        "check-freshness")
            check_freshness
            ;;
        "stats")
            generate_stats
            ;;
        "update-index")
            update_index "$2"
            ;;
        "validate")
            validate_structure
            ;;
        "help"|*)
            show_help
            ;;
    esac
}

# 运行主函数
main "$@"
