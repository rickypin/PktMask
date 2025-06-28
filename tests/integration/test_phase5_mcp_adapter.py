from __future__ import annotations

try:
    from fastapi.testclient import TestClient  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    import pytest

    pytest.skip("fastapi 未安装，跳过 MCP API 测试", allow_module_level=True)

from pathlib import Path

from pktmask.adapters.mcp import app


def test_mcp_process_noop(tmp_path: Path) -> None:
    """通过 MCP API 处理一个文件但不启用任何 Stage，验证 200 返回。"""

    client = TestClient(app)

    # 选择较小的示例文件
    sample_input = Path("tests/data/tls/tls_1_2_plainip.pcap")
    if not sample_input.exists():
        # 若样本缺失则跳过测试
        print("sample pcap not found, skipping test")
        return

    output_path = tmp_path / "out.pcap"

    response = client.post(
        "/process",
        json={
            "input_path": str(sample_input),
            "output_path": str(output_path),
            "steps": {},
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["success"] is True
    assert data["input_file"] == str(sample_input)
    # 无 Stage 时不会真正写输出文件；只需确保字段存在
    assert "stage_stats" in data 