#!/bin/bash

# PktMask 自动化测试脚本 - 简化版
# 直接使用pytest运行实际存在的测试文件

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
    echo "  --coverage          生成覆盖率报告"
    echo "  --verbose           详细输出"
    echo ""
    echo "示例:"
    echo "  ./run_tests.sh                # 运行所有测试"
    echo "  ./run_tests.sh --quick        # 快速测试"
    echo "  ./run_tests.sh --unit         # 仅单元测试"
    echo "  ./run_tests.sh --coverage     # 生成覆盖率报告"
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
        print_warning "pytest未安装"
        
        # 检查是否在虚拟环境中
        if [[ "$VIRTUAL_ENV" != "" ]]; then
            print_message "在虚拟环境中安装pytest..."
            pip install pytest pytest-cov pytest-html pytest-xvfb || {
                print_error "依赖安装失败"
                exit 1
            }
        else
            print_error "请先创建并激活虚拟环境，或者使用 --user 标志安装："
            print_error "  python3 -m venv venv"
            print_error "  source venv/bin/activate"
            print_error "  pip install pytest pytest-cov pytest-html pytest-xvfb"
            print_error ""
            print_error "或者使用用户安装:"
            print_error "  python3 -m pip install --user pytest pytest-cov pytest-html pytest-xvfb"
            
            # 尝试用户安装
            print_warning "尝试用户安装pytest..."
            if python3 -m pip install --user pytest pytest-cov pytest-html pytest-xvfb; then
                print_success "pytest用户安装成功"
            else
                print_error "用户安装也失败，请手动安装pytest"
                exit 1
            fi
        fi
    fi
    
    # 再次检查pytest是否可用
    if ! python3 -c "import pytest" 2>/dev/null; then
        print_error "pytest仍然不可用，请检查安装"
        exit 1
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

# 定义测试路径
get_test_paths() {
    local test_type="$1"
    
    case "$test_type" in
        "unit")
            echo "tests/test_basic_phase_7.py tests/test_config_system.py tests/test_managers.py tests/test_pktmask.py tests/test_gui.py"
            ;;
        "integration")
            echo "tests/test_integration_phase_7.py test_phase_3_gui_integration.py"
            ;;
        "performance")
            echo "tests/performance/test_runner.py tests/performance/benchmark_suite.py tests/performance/run_optimization_test.py"
            ;;
        "phase_specific")
            echo "test_phase_1_processors.py test_automated_dialog_handling.py test_error_handling.py"
            ;;
        *)
            # 所有测试
            echo "tests/ test_phase_1_processors.py test_phase_3_gui_integration.py test_automated_dialog_handling.py test_error_handling.py"
            ;;
    esac
}

# 运行pytest测试
run_pytest() {
    local test_paths="$1"
    local output_dir="$2"
    local coverage="$3"
    local verbose="$4"
    
    # 创建输出目录
    mkdir -p "$output_dir"
    
    # 构建pytest参数
    local pytest_args="-v"
    
    if [[ "$verbose" == "true" ]]; then
        pytest_args="$pytest_args -s"
    fi
    
    # 添加覆盖率报告
    if [[ "$coverage" == "true" ]]; then
        pytest_args="$pytest_args --cov=src/pktmask --cov-report=html:$output_dir/htmlcov --cov-report=term"
    fi
    
    # 添加HTML报告
    pytest_args="$pytest_args --html=$output_dir/report.html --self-contained-html"
    
    # 添加JUnit XML报告
    pytest_args="$pytest_args --junitxml=$output_dir/junit.xml"
    
    # 设置GUI测试环境变量
    export QT_QPA_PLATFORM=offscreen
    export PYTEST_CURRENT_TEST=automated_test
    
    print_message "运行测试: $test_paths"
    print_message "pytest参数: $pytest_args"
    
    # 运行pytest
    if python3 -m pytest $pytest_args $test_paths; then
        print_success "测试执行完成"
        
        # 查找生成的报告文件
        html_report="$output_dir/report.html"
        if [[ -f "$html_report" ]]; then
            print_success "HTML报告生成: $html_report"
            
            # 在macOS上自动打开报告
            if [[ "$OSTYPE" == "darwin"* ]]; then
                print_message "在浏览器中打开报告..."
                open "$html_report"
            fi
        fi
        
        if [[ "$coverage" == "true" && -d "$output_dir/htmlcov" ]]; then
            print_success "覆盖率报告生成: $output_dir/htmlcov/index.html"
        fi
        
        return 0
    else
        print_error "测试执行失败"
        return 1
    fi
}

# 主函数
main() {
    local test_type="all"
    local output_dir="test_reports"
    local clean_only=false
    local coverage=false
    local verbose=false
    
    # 解析命令行参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -q|--quick)
                test_type="quick"
                shift
                ;;
            -u|--unit)
                test_type="unit"
                shift
                ;;
            -i|--integration)
                test_type="integration"
                shift
                ;;
            -p|--performance)
                test_type="performance"
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
            --coverage)
                coverage=true
                shift
                ;;
            --verbose)
                verbose=true
                shift
                ;;
            *)
                print_error "未知选项: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    echo "🧪 PktMask 自动化测试脚本 (简化版)"
    echo "========================================="
    
    # 如果只是清理，执行清理后退出
    if [[ "$clean_only" == true ]]; then
        clean_reports "$output_dir"
        exit 0
    fi
    
    # 检查环境
    check_python_env
    check_dependencies
    
    # 获取测试路径
    if [[ "$test_type" == "quick" ]]; then
        test_paths=$(get_test_paths "unit")
        test_paths="$test_paths $(get_test_paths "integration")"
        test_paths="$test_paths $(get_test_paths "phase_specific")"
    elif [[ "$test_type" == "all" ]]; then
        test_paths=$(get_test_paths "all")
    else
        test_paths=$(get_test_paths "$test_type")
    fi
    
    print_message "测试类型: $test_type"
    print_message "输出目录: $output_dir"
    
    # 运行测试
    if run_pytest "$test_paths" "$output_dir" "$coverage" "$verbose"; then
        print_success "🎉 所有测试完成！"
        
        if [[ -f "$output_dir/report.html" ]]; then
            echo ""
            print_message "📊 查看测试报告: $output_dir/report.html"
        fi
        
        if [[ "$coverage" == "true" ]]; then
            echo ""
            print_message "📈 查看覆盖率报告: $output_dir/htmlcov/index.html"
        fi
        
        exit 0
    else
        print_error "❌ 测试执行失败！"
        exit 1
    fi
}

# 运行主函数
main "$@" 