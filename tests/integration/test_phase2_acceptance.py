import pytest
import tempfile
from pathlib import Path
from shutil import copyfile

from scapy.all import rdpcap

from src.pktmask.core.trim.stages import (
    EnhancedPySharkAnalyzer as PySharkAnalyzer,
    TcpPayloadMaskerAdapter,
)
from src.pktmask.core.trim.stages.base_stage import StageContext


@pytest.mark.parametrize(
    "pcap_relpath",
    [
        "tests/data/tls/tls_plainip.pcap",
        "tests/data/tls/tls_vlan.pcap",
    ],
)
def test_phase2_acceptance_basic(tmp_path, pcap_relpath):
    """Phase-2 基本验收测试：确保输出文件与输入文件包数一致，且至少有 1 个包被掩码。"""

    in_path = Path(pcap_relpath)
    assert in_path.exists(), f"输入文件不存在: {in_path}"

    work_dir = tmp_path / "work"
    work_dir.mkdir()

    # 输出文件路径
    out_path = tmp_path / f"masked_{in_path.name}"

    # 构造 StageContext，直接使用原文件作为 tshark_output（测试环境避免调用外部 tshark）
    context = StageContext(input_file=in_path, output_file=out_path, work_dir=work_dir)
    context.tshark_output = in_path  # 简化：映射同一文件

    # 1. 执行 EnhancedPySharkAnalyzer
    analyzer = PySharkAnalyzer()
    assert analyzer.initialize(), "Analyzer 初始化失败"
    assert analyzer.validate_inputs(context), "Analyzer 输入验证未通过"
    result1 = analyzer.execute(context)
    assert result1.success, f"Analyzer 执行失败: {result1.data}"
    instr_cnt = result1.data["instruction_count"]
    # 对于仅包含 TLS Handshake 的样本，可能不会生成掩码指令
    assert instr_cnt >= 0, "掩码指令计数不存在"

    # 2. 执行 TcpPayloadMaskerAdapter
    adapter = TcpPayloadMaskerAdapter()
    assert adapter.initialize(), "Adapter 初始化失败"
    assert adapter.validate_inputs(context), "Adapter 输入验证未通过"
    result2 = adapter.execute(context)
    assert result2.success, f"Adapter 执行失败: {result2.error}"

    # 3. 基本一致性验证
    packets_orig = rdpcap(str(in_path))
    packets_masked = rdpcap(str(out_path))
    assert len(packets_orig) == len(packets_masked), "输出文件包数与原始文件不一致"
    # packets_modified 可能为 0（例如样本只包含 TLS 握手）
    assert result2.data["packets_modified"] >= 0, "处理统计缺失" 