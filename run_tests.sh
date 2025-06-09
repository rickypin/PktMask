#!/bin/bash

# PktMask 自动化测试脚本
# 用于打包发布前的完整测试验证

set -e  # 遇到错误时退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_message() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 显示帮助信息
show_help() {
    echo "PktMask 自动化测试脚本"
    echo ""
    echo "使用方法:"
    echo "  ./run_tests.sh [选项]"
    echo ""
    echo "选项:"
    echo "  -h, --help          显示此帮助信息"
    echo "  -q, --quick         快速测试(跳过性能测试)"
    echo "  -u, --unit          仅运行单元测试"
    echo "  -i, --integration   仅运行集成测试"
    echo "  -p, --performance   仅运行性能测试"
    echo "  -c, --clean         清理测试报告目录"
    echo "  -o, --output DIR    指定输出目录(默认: test_reports)"
    echo "  --no-deps          跳过依赖检查"
    echo ""
    echo "示例:"
    echo "  ./run_tests.sh                # 运行所有测试"
    echo "  ./run_tests.sh --quick        # 快速测试"
    echo "  ./run_tests.sh --unit         # 仅单元测试"
    echo "  ./run_tests.sh --clean        # 清理报告目录"
}

# 检查Python环境
check_python_env() {
    print_message "检查Python环境..."
    
    if ! command -v python3 &> /dev/null; then
        print_error "未找到 python3，请安装Python 3.8+"
        exit 1
    fi
    
    python_version=$(python3 -c "import sys; print('.'.join(map(str, sys.version_info[:2])))")
    print_success "Python版本: $python_version"
    
    # 检查虚拟环境
    if [[ "$VIRTUAL_ENV" != "" ]]; then
        print_success "使用虚拟环境: $VIRTUAL_ENV"
    else
        print_warning "未检测到虚拟环境，建议使用虚拟环境"
    fi
}

# 检查依赖
check_dependencies() {
    print_message "检查测试依赖..."
    
    # 检查pytest
    if ! python3 -c "import pytest" 2>/dev/null; then
        print_warning "pytest未安装，正在安装测试依赖..."
        pip install -e ".[dev]" || {
            print_error "依赖安装失败"
            exit 1
        }
    fi
    
    print_success "依赖检查完成"
}

# 清理报告目录
clean_reports() {
    local output_dir=${1:-"test_reports"}
    
    if [[ -d "$output_dir" ]]; then
        print_message "清理报告目录: $output_dir"
        rm -rf "$output_dir"
        print_success "报告目录已清理"
    else
        print_message "报告目录不存在，无需清理"
    fi
}

# 运行测试
run_tests() {
    local test_args="$1"
    local output_dir=${2:-"test_reports"}
    
    print_message "开始运行 PktMask 测试套件..."
    print_message "参数: $test_args"
    print_message "输出目录: $output_dir"
    
    # 创建输出目录
    mkdir -p "$output_dir"
    
    # 运行测试套件
    if python3 test_suite.py $test_args --output "$output_dir"; then
        print_success "测试套件执行完成"
        
        # 查找生成的报告文件
        html_report=$(find "$output_dir" -name "test_summary_*.html" | head -1)
        json_report=$(find "$output_dir" -name "test_summary_*.json" | head -1)
        
        if [[ -f "$html_report" ]]; then
            print_success "HTML报告: $html_report"
            
            # 在macOS上自动打开报告
            if [[ "$OSTYPE" == "darwin"* ]]; then
                print_message "在浏览器中打开报告..."
                open "$html_report"
            fi
        fi
        
        if [[ -f "$json_report" ]]; then
            print_success "JSON报告: $json_report"
        fi
        
        return 0
    else
        print_error "测试套件执行失败"
        return 1
    fi
}

# 主函数
main() {
    local test_args=""
    local output_dir="test_reports"
    local clean_only=false
    local skip_deps=false
    
    # 解析命令行参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -q|--quick)
                test_args="$test_args --quick"
                shift
                ;;
            -u|--unit)
                test_args="$test_args --unit"
                shift
                ;;
            -i|--integration)
                test_args="$test_args --integration"
                shift
                ;;
            -p|--performance)
                test_args="$test_args --performance"
                shift
                ;;
            -c|--clean)
                clean_only=true
                shift
                ;;
            -o|--output)
                output_dir="$2"
                shift 2
                ;;
            --no-deps)
                skip_deps=true
                shift
                ;;
            *)
                print_error "未知选项: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    echo "🧪 PktMask 自动化测试脚本"
    echo "================================"
    
    # 如果只是清理，执行清理后退出
    if [[ "$clean_only" == true ]]; then
        clean_reports "$output_dir"
        exit 0
    fi
    
    # 检查环境
    check_python_env
    
    if [[ "$skip_deps" != true ]]; then
        check_dependencies
    fi
    
    # 运行测试
    if run_tests "$test_args" "$output_dir"; then
        echo ""
        print_success "🎉 测试完成！"
        exit 0
    else
        echo ""
        print_error "❌ 测试失败！"
        exit 1
    fi
}

# 执行主函数
main "$@" 