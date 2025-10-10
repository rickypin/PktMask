#!/bin/bash
# PktMask CLI 全面测试脚本
# 基于代码审查的完整命令和参数测试

set -e  # 遇到错误时退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 测试计数器
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# 测试数据路径
TEST_DATA_DIR="tests/samples/tls-single"
TEMP_DIR=$(mktemp -d)
OUTPUT_DIR="${TEMP_DIR}/output"

# 清理函数
cleanup() {
    echo -e "\n${BLUE}清理临时文件...${NC}"
    rm -rf "${TEMP_DIR}"
}

trap cleanup EXIT

# 创建输出目录
mkdir -p "${OUTPUT_DIR}"

# 获取测试文件
if [ ! -d "${TEST_DATA_DIR}" ]; then
    echo -e "${RED}错误: 测试数据目录不存在: ${TEST_DATA_DIR}${NC}"
    exit 1
fi

TEST_PCAP=$(find "${TEST_DATA_DIR}" -name "*.pcap" -type f | head -1)
if [ -z "${TEST_PCAP}" ]; then
    echo -e "${RED}错误: 未找到测试 PCAP 文件${NC}"
    exit 1
fi

echo -e "${GREEN}使用测试文件: ${TEST_PCAP}${NC}"
echo -e "${BLUE}临时目录: ${TEMP_DIR}${NC}\n"

# 测试函数
run_test() {
    local test_name="$1"
    local test_cmd="$2"
    local expected_exit_code="${3:-0}"
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    
    echo -e "${YELLOW}[测试 ${TOTAL_TESTS}] ${test_name}${NC}"
    echo "命令: ${test_cmd}"
    
    if eval "${test_cmd}" > /dev/null 2>&1; then
        actual_exit_code=0
    else
        actual_exit_code=$?
    fi
    
    if [ "${actual_exit_code}" -eq "${expected_exit_code}" ]; then
        echo -e "${GREEN}✅ 通过${NC}\n"
        PASSED_TESTS=$((PASSED_TESTS + 1))
        return 0
    else
        echo -e "${RED}❌ 失败 (期望退出码: ${expected_exit_code}, 实际: ${actual_exit_code})${NC}\n"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        return 1
    fi
}

# 显示测试输出的函数
run_test_with_output() {
    local test_name="$1"
    local test_cmd="$2"
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    
    echo -e "${YELLOW}[测试 ${TOTAL_TESTS}] ${test_name}${NC}"
    echo "命令: ${test_cmd}"
    echo "输出:"
    
    if eval "${test_cmd}"; then
        echo -e "${GREEN}✅ 通过${NC}\n"
        PASSED_TESTS=$((PASSED_TESTS + 1))
        return 0
    else
        echo -e "${RED}❌ 失败${NC}\n"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        return 1
    fi
}

echo "=========================================="
echo "PktMask CLI 全面测试"
echo "=========================================="
echo ""

# =============================================================================
# 1. 主命令测试
# =============================================================================
echo -e "${BLUE}=== 1. 主命令测试 ===${NC}\n"

run_test_with_output \
    "主帮助命令" \
    "python -m pktmask --help"

run_test \
    "无效命令应失败" \
    "python -m pktmask invalid-command" \
    2

# =============================================================================
# 2. process 命令 - 帮助和基础测试
# =============================================================================
echo -e "${BLUE}=== 2. process 命令测试 ===${NC}\n"

run_test_with_output \
    "process 帮助命令" \
    "python -m pktmask process --help"

# =============================================================================
# 3. process 命令 - 单操作测试
# =============================================================================
echo -e "${BLUE}=== 3. 单操作测试 ===${NC}\n"

run_test \
    "单文件去重处理" \
    "python -m pktmask process '${TEST_PCAP}' -o '${OUTPUT_DIR}/dedup.pcap' --dedup"

run_test \
    "单文件 IP 匿名化处理" \
    "python -m pktmask process '${TEST_PCAP}' -o '${OUTPUT_DIR}/anon.pcap' --anon"

run_test \
    "单文件载荷掩码处理" \
    "python -m pktmask process '${TEST_PCAP}' -o '${OUTPUT_DIR}/mask.pcap' --mask"

# =============================================================================
# 4. process 命令 - 操作组合测试
# =============================================================================
echo -e "${BLUE}=== 4. 操作组合测试 ===${NC}\n"

run_test \
    "去重 + 匿名化组合" \
    "python -m pktmask process '${TEST_PCAP}' -o '${OUTPUT_DIR}/dedup_anon.pcap' --dedup --anon"

run_test \
    "去重 + 掩码组合" \
    "python -m pktmask process '${TEST_PCAP}' -o '${OUTPUT_DIR}/dedup_mask.pcap' --dedup --mask"

run_test \
    "匿名化 + 掩码组合" \
    "python -m pktmask process '${TEST_PCAP}' -o '${OUTPUT_DIR}/anon_mask.pcap' --anon --mask"

run_test \
    "所有操作组合" \
    "python -m pktmask process '${TEST_PCAP}' -o '${OUTPUT_DIR}/all.pcap' --dedup --anon --mask"

# =============================================================================
# 5. process 命令 - 错误处理测试
# =============================================================================
echo -e "${BLUE}=== 5. 错误处理测试 ===${NC}\n"

run_test \
    "无操作标志应失败" \
    "python -m pktmask process '${TEST_PCAP}' -o '${OUTPUT_DIR}/error.pcap'" \
    1

run_test \
    "不存在的文件应失败" \
    "python -m pktmask process '${TEMP_DIR}/nonexistent.pcap' -o '${OUTPUT_DIR}/error.pcap' --dedup" \
    1

run_test \
    "无效文件类型应失败" \
    "python -m pktmask process '${TEMP_DIR}/test.txt' -o '${OUTPUT_DIR}/error.pcap' --dedup" \
    1

# =============================================================================
# 6. process 命令 - 协议参数测试
# =============================================================================
echo -e "${BLUE}=== 6. 协议参数测试 ===${NC}\n"

run_test \
    "TLS 协议掩码" \
    "python -m pktmask process '${TEST_PCAP}' -o '${OUTPUT_DIR}/mask_tls.pcap' --mask --mask-protocol tls"

run_test \
    "HTTP 协议掩码" \
    "python -m pktmask process '${TEST_PCAP}' -o '${OUTPUT_DIR}/mask_http.pcap' --mask --mask-protocol http"

run_test \
    "自动协议检测" \
    "python -m pktmask process '${TEST_PCAP}' -o '${OUTPUT_DIR}/mask_auto.pcap' --mask --mask-protocol auto"

run_test \
    "无效协议应失败" \
    "python -m pktmask process '${TEST_PCAP}' -o '${OUTPUT_DIR}/mask_invalid.pcap' --mask --mask-protocol invalid" \
    1

# =============================================================================
# 7. process 命令 - 输出路径测试
# =============================================================================
echo -e "${BLUE}=== 7. 输出路径测试 ===${NC}\n"

# 复制测试文件到临时目录用于自动输出测试
cp "${TEST_PCAP}" "${TEMP_DIR}/test_auto.pcap"

run_test \
    "自动生成输出路径" \
    "cd '${TEMP_DIR}' && python -m pktmask process test_auto.pcap --dedup"

run_test \
    "嵌套输出目录自动创建" \
    "python -m pktmask process '${TEST_PCAP}' -o '${TEMP_DIR}/level1/level2/output.pcap' --dedup"

# =============================================================================
# 8. process 命令 - 详细输出测试
# =============================================================================
echo -e "${BLUE}=== 8. 详细输出测试 ===${NC}\n"

run_test_with_output \
    "详细模式输出" \
    "python -m pktmask process '${TEST_PCAP}' -o '${OUTPUT_DIR}/verbose.pcap' --dedup --verbose"

# =============================================================================
# 9. process 命令 - 目录处理测试
# =============================================================================
echo -e "${BLUE}=== 9. 目录处理测试 ===${NC}\n"

# 创建测试目录
TEST_DIR="${TEMP_DIR}/test_pcaps"
mkdir -p "${TEST_DIR}"
cp "${TEST_PCAP}" "${TEST_DIR}/test1.pcap"
cp "${TEST_PCAP}" "${TEST_DIR}/test2.pcap"

run_test \
    "目录批量处理" \
    "python -m pktmask process '${TEST_DIR}' -o '${OUTPUT_DIR}/batch' --dedup"

# 创建空目录测试
EMPTY_DIR="${TEMP_DIR}/empty"
mkdir -p "${EMPTY_DIR}"

run_test_with_output \
    "空目录处理（应警告）" \
    "python -m pktmask process '${EMPTY_DIR}' -o '${OUTPUT_DIR}/empty_out' --dedup"

# 创建混合文件目录
MIXED_DIR="${TEMP_DIR}/mixed"
mkdir -p "${MIXED_DIR}"
cp "${TEST_PCAP}" "${MIXED_DIR}/test.pcap"
echo "test" > "${MIXED_DIR}/readme.txt"
echo "{}" > "${MIXED_DIR}/data.json"

run_test \
    "混合文件目录处理" \
    "python -m pktmask process '${MIXED_DIR}' -o '${OUTPUT_DIR}/mixed_out' --dedup"

# =============================================================================
# 10. validate 命令测试
# =============================================================================
echo -e "${BLUE}=== 10. validate 命令测试 ===${NC}\n"

run_test_with_output \
    "validate 帮助命令" \
    "python -m pktmask validate --help"

run_test_with_output \
    "验证单个文件" \
    "python -m pktmask validate '${TEST_PCAP}'"

run_test_with_output \
    "验证单个文件（详细模式）" \
    "python -m pktmask validate '${TEST_PCAP}' --verbose"

run_test_with_output \
    "验证目录" \
    "python -m pktmask validate '${TEST_DATA_DIR}'"

run_test_with_output \
    "验证目录（详细模式）" \
    "python -m pktmask validate '${TEST_DATA_DIR}' --verbose"

run_test \
    "验证不存在的文件应失败" \
    "python -m pktmask validate '${TEMP_DIR}/nonexistent.pcap'" \
    1

# 创建无效文件类型
echo "test" > "${TEMP_DIR}/test.txt"

run_test \
    "验证无效文件类型应失败" \
    "python -m pktmask validate '${TEMP_DIR}/test.txt'" \
    1

# =============================================================================
# 11. config 命令测试
# =============================================================================
echo -e "${BLUE}=== 11. config 命令测试 ===${NC}\n"

run_test_with_output \
    "config 帮助命令" \
    "python -m pktmask config --help"

run_test_with_output \
    "仅去重配置" \
    "python -m pktmask config --dedup"

run_test_with_output \
    "仅匿名化配置" \
    "python -m pktmask config --anon"

run_test_with_output \
    "仅掩码配置" \
    "python -m pktmask config --mask"

run_test_with_output \
    "所有操作配置" \
    "python -m pktmask config --dedup --anon --mask"

run_test \
    "无操作配置应失败" \
    "python -m pktmask config" \
    1

# =============================================================================
# 测试总结
# =============================================================================
echo ""
echo "=========================================="
echo "测试总结"
echo "=========================================="
echo -e "总测试数: ${TOTAL_TESTS}"
echo -e "${GREEN}通过: ${PASSED_TESTS}${NC}"
echo -e "${RED}失败: ${FAILED_TESTS}${NC}"
echo ""

if [ ${FAILED_TESTS} -eq 0 ]; then
    echo -e "${GREEN}✅ 所有测试通过！${NC}"
    exit 0
else
    echo -e "${RED}❌ 有 ${FAILED_TESTS} 个测试失败${NC}"
    exit 1
fi

