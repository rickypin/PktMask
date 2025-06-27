import json
from unittest import mock

import pytest

# 动态导入工具模块，避免提前解析 argparse
MODULE_PATH = "pktmask.tools.tls23_marker"

def _import_module():
    import importlib
    return importlib.import_module(MODULE_PATH)


def _mock_tshark_version(monkeypatch, version_output="TShark (Wireshark) 4.2.3"):
    """Mock subprocess.run 以返回指定版本输出，并在扫描命令时返回示例 JSON。"""

    class _Completed:
        def __init__(self, stdout):
            self.stdout = stdout
            self.stderr = ""

    sample_json = json.dumps([
        {
            "_source": {
                "layers": {
                    "frame.number": ["1"],
                    "frame.protocols": ["eth:ip:tcp:tls"],
                    "tls.record.content_type": ["23"],
                }
            }
        }
    ])

    def _run(cmd, check, text, capture_output):
        if "-v" in cmd:
            return _Completed(version_output)
        else:
            return _Completed(sample_json)

    monkeypatch.setattr("subprocess.run", _run)


def test_parse_args_and_env_check(monkeypatch, tmp_path):
    # 模拟 tshark 版本输出满足要求
    _mock_tshark_version(monkeypatch)

    tls23 = _import_module()

    input_pcap = tmp_path / "sample.pcapng"
    input_pcap.touch()

    argv = [
        "--pcap",
        str(input_pcap),
        "--verbose",
        "--formats",
        "json",
        "--memory",
        "512",
    ]

    # 捕获 SystemExit 并检查退出码 0
    with pytest.raises(SystemExit) as exc_info:
        tls23.main(argv)
    assert exc_info.value.code == 0

    # 验证输出文件已创建
    output_json = input_pcap.with_name(f"{input_pcap.stem}_tls23_frames.json")
    assert output_json.exists()
    data = json.loads(output_json.read_text())
    assert data["summary"]["total_matches"] == 1
    assert data["matches"][0]["frame"] == 1


def test_version_too_low(monkeypatch):
    # 模拟低版本导致退出码 1
    _mock_tshark_version(monkeypatch, "TShark (Wireshark) 3.6.8")

    tls23 = _import_module()

    argv = ["--pcap", "dummy.pcapng"]

    with pytest.raises(SystemExit) as exc_info:
        tls23.main(argv)
    assert exc_info.value.code == 1 