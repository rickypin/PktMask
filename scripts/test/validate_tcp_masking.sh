#!/bin/bash
# validate_tcp_masking.sh
# TCP Sequence-Based Masking Validation Framework 自动运行脚本

set -e  # 遇到错误时退出

echo "开始TCP序列号掩码机制验证..."
echo "=========================================="

# 设置项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# 创建reports目录
mkdir -p reports

# 设置Python路径
export PYTHONPATH="$PROJECT_ROOT/src:$PYTHONPATH"

echo "Phase 1: 数据结构验证..."
echo "------------------------"
pytest tests/unit/test_tcp_sequence_masking_validation_framework.py::TestPhase1DataStructureValidation -v --tb=short

echo ""
echo "Phase 2: PyShark分析器验证..."
echo "----------------------------"
pytest tests/unit/test_tcp_sequence_masking_validation_framework.py::TestPhase2PySharkAnalyzerValidation -v --tb=short

echo ""
echo "Phase 3: TcpPayloadMaskerAdapter验证..."
echo "---------------------------------------"  
pytest tests/unit/test_phase3_payload_masker_adapter.py -v --tb=short

echo ""
echo "Phase 4: 协议策略验证..."
echo "----------------------"
pytest tests/unit/test_tcp_sequence_masking_validation_framework.py::TestPhase4ProtocolStrategyValidation -v --tb=short

echo ""
echo "Phase 5: 端到端集成验证..."
echo "-------------------------"
pytest tests/unit/test_tcp_sequence_masking_validation_framework.py::TestPhase5EndToEndIntegrationValidation -v --tb=short

echo ""
echo "运行完整验证框架..."
echo "==================="
pytest tests/unit/test_tcp_sequence_masking_validation_framework.py -v --tb=short \
    --junitxml=reports/tcp_sequence_masking_junit.xml \
    --html=reports/tcp_sequence_masking_report.html --self-contained-html

echo ""
echo "运行现有相关测试..."
echo "=================="

# 运行现有的Phase测试
if [ -f "tests/unit/test_phase1_sequence_mask_table.py" ]; then
    echo "运行Phase 1相关测试..."
    pytest tests/unit/test_phase1_sequence_mask_table.py -v --tb=short
fi

if [ -f "tests/unit/test_phase1_tcp_stream.py" ]; then
    echo "运行TCP流测试..."
    pytest tests/unit/test_phase1_tcp_stream.py -v --tb=short
fi

if [ -f "tests/unit/test_phase2_pyshark_analyzer.py" ]; then
    echo "运行PyShark分析器测试..."
    pytest tests/unit/test_phase2_pyshark_analyzer.py -v --tb=short
fi

# 新文件名已更改，直接运行
if [ -f "tests/unit/test_phase3_payload_masker_adapter.py" ]; then
    echo "运行TcpPayloadMaskerAdapter测试..."
    pytest tests/unit/test_phase3_payload_masker_adapter.py -v --tb=short
fi

if [ -f "tests/unit/test_phase4_protocol_strategy.py" ]; then
    echo "运行协议策略测试..."
    pytest tests/unit/test_phase4_protocol_strategy.py -v --tb=short
fi

# 运行集成测试
echo ""
echo "运行集成测试..."
echo "=============="
if [ -f "tests/integration/test_phase5_comprehensive_integration.py" ]; then
    pytest tests/integration/test_phase5_comprehensive_integration.py -v --tb=short
fi

echo ""
echo "验证完成！"
echo "=========="

# 检查报告文件
if [ -f "reports/tcp_sequence_masking_report.html" ]; then
    echo "✅ HTML报告已生成: reports/tcp_sequence_masking_report.html"
fi

if [ -f "reports/tcp_sequence_masking_junit.xml" ]; then
    echo "✅ JUnit报告已生成: reports/tcp_sequence_masking_junit.xml"
fi

echo ""
echo "主要验证目标："
echo "- ✅ 数据结构正确性"
echo "- ✅ PyShark分析器功能"
echo "- ✅ Scapy回写器功能"
echo "- ✅ 协议策略框架"
echo "- ✅ 端到端集成测试"
echo ""
echo "特别验证TLS样本处理："
echo "- 包14、15 (TLS Application Data) 应被置零"
echo "- 包4、6、7、9、10、12、16、19 (TLS Handshake) 应保持不变"
echo ""
echo "验证完成！查看报告了解详细结果。" 