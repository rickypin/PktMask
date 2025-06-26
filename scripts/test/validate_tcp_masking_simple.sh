#!/bin/bash

# TCP序列号掩码机制简化验证脚本
# ==============================

set -e  # 遇到错误立即退出

# 颜色输出定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 项目根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# 日志函数
log_info() {
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

log_phase() {
    echo -e "${PURPLE}[PHASE]${NC} $1"
}

# 检查环境
check_environment() {
    log_info "检查验证环境..."
    
    # 检查Python环境
    if ! command -v python3 &> /dev/null; then
        log_error "Python3 未安装"
        exit 1
    fi
    
    # 检查pytest
    if ! python3 -c "import pytest" 2>/dev/null; then
        log_error "pytest 未安装，请运行: pip install pytest"
        exit 1
    fi
    
    # 检查TLS样本文件
    TLS_SAMPLE="tests/samples/tls-single/tls_sample.pcap"
    if [[ ! -f "$TLS_SAMPLE" ]]; then
        log_warning "TLS样本文件不存在: $TLS_SAMPLE"
    else
        log_success "TLS样本文件存在: $TLS_SAMPLE"
    fi
    
    echo ""
}

# 运行简化验证
run_simple_validation() {
    log_phase "运行TCP序列号掩码机制简化验证"
    echo "----------------------------------------"
    
    # 设置PYTHONPATH确保能找到src模块
    export PYTHONPATH="$PROJECT_ROOT:$PROJECT_ROOT/src:$PYTHONPATH"
    
    if PYTHONPATH="$PROJECT_ROOT:$PROJECT_ROOT/src:$PYTHONPATH" pytest "tests/unit/test_tcp_sequence_masking_validation_simple.py" -v --tb=short; then
        log_success "简化验证通过"
        return 0
    else
        log_error "简化验证失败"
        return 1
    fi
}

# 运行TLS样本验证
run_tls_validation() {
    log_phase "运行TLS样本专项验证"
    echo "----------------------------------------"
    
    if python scripts/validate_tls_sample.py --quick; then
        log_success "TLS样本验证通过"
        return 0
    else
        log_error "TLS样本验证失败"
        return 1
    fi
}

# 主验证流程
main() {
    echo -e "${CYAN}================================${NC}"
    echo -e "${CYAN}TCP序列号掩码机制简化验证${NC}"
    echo -e "${CYAN}================================${NC}"
    echo ""
    
    # 检查环境
    check_environment
    
    # 运行简化验证
    simple_result=0
    run_simple_validation || simple_result=$?
    echo ""
    
    # 运行TLS样本验证
    tls_result=0
    run_tls_validation || tls_result=$?
    echo ""
    
    # 打印验证结果摘要
    echo -e "${CYAN}================================${NC}"
    echo -e "${CYAN}验证结果摘要${NC}"
    echo -e "${CYAN}================================${NC}"
    echo ""
    
    if [[ $simple_result -eq 0 ]]; then
        echo -e "✅ 简化验证: PASS"
    else
        echo -e "❌ 简化验证: FAIL"
    fi
    
    if [[ $tls_result -eq 0 ]]; then
        echo -e "✅ TLS样本验证: PASS"
    else
        echo -e "❌ TLS样本验证: FAIL"
    fi
    
    echo ""
    
    if [[ $simple_result -eq 0 && $tls_result -eq 0 ]]; then
        log_success "🎉 所有验证通过！TCP序列号掩码机制验证成功！"
        exit 0
    else
        log_warning "⚠️ 部分验证失败，需要进一步调试。"
        exit 1
    fi
}

# 处理命令行参数
case "${1:-}" in
    --help|-h)
        echo "TCP序列号掩码机制简化验证脚本"
        echo ""
        echo "用法: $0 [选项]"
        echo ""
        echo "选项:"
        echo "  --help, -h     显示此帮助信息"
        echo "  --env-check    仅检查环境配置"
        echo "  --simple-only  仅运行简化验证"
        echo "  --tls-only     仅运行TLS样本验证"
        exit 0
        ;;
    --env-check)
        check_environment
        exit 0
        ;;
    --simple-only)
        check_environment
        run_simple_validation
        exit $?
        ;;
    --tls-only)
        check_environment
        run_tls_validation
        exit $?
        ;;
    "")
        # 运行完整验证
        main
        ;;
    *)
        log_error "未知选项: $1"
        echo "使用 --help 查看可用选项"
        exit 1
        ;;
esac 