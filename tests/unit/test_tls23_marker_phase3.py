import json
from unittest import mock
import pytest
pytestmark = pytest.mark.unit

MODULE_PATH = "pktmask.tools.tls23_marker"

def _import_module():
    import importlib
    return importlib.import_module(MODULE_PATH)


def _mock_subprocess_for_phase3(monkeypatch):
    """根据调用次数返回不同的 tshark JSON 输出，以模拟阶段3逻辑。"""

    class _Completed:
        def __init__(self, stdout):
            self.stdout = stdout
            self.stderr = ""

    # 调用计数器
    call_counter = {"count": 0}

    # 第一次扫描返回只包含 frame 2，显式 content-type=23
    sample_first = json.dumps([
        {
            "_source": {
                "layers": {
                    "frame.number": ["2"],
                    "frame.protocols": ["eth:ip:tcp:tls"],
                    "tls.record.content_type": ["23"],
                    "tcp.stream": ["1"],
                }
            }
        }
    ])

    # 第二次针对流 1 的扫描，返回 frame 1(缺头) + frame 2
    sample_second = json.dumps([
        {
            "_source": {
                "layers": {
                    "frame.number": ["1"],
                    "frame.protocols": ["eth:ip:tcp"],
                    "tcp.stream": ["1"],
                    "tcp.seq_relative": ["0"],
                    "tcp.len": ["3"],
                    "tcp.payload": ["17:03:03"],
                }
            }
        },
        {
            "_source": {
                "layers": {
                    "frame.number": ["2"],
                    "frame.protocols": ["eth:ip:tcp:tls"],
                    "tcp.stream": ["1"],
                    "tcp.seq_relative": ["3"],
                    "tcp.len": ["7"],
                    "tcp.payload": ["00:05:aa:bb:cc:dd:ee"],
                }
            }
        },
    ])

    def _run(cmd, check, text, capture_output):
        if "-v" in cmd:
            return _Completed("TShark (Wireshark) 4.2.3")

        # 非版本检测调用，根据调用次数返回不同 JSON
        call_counter["count"] += 1
        if call_counter["count"] == 1:
            return _Completed(sample_first)
        else:
            return _Completed(sample_second)

    monkeypatch.setattr("subprocess.run", _run)


def test_phase3_supplements_missing_header(monkeypatch, tmp_path):
    _mock_subprocess_for_phase3(monkeypatch)

    tls23 = _import_module()

    pcap = tmp_path / "input.pcapng"
    pcap.touch()

    argv = ["--pcap", str(pcap), "--formats", "json"]

    with pytest.raises(SystemExit) as exc_info:
        tls23.main(argv)
    assert exc_info.value.code == 0

    json_out = pcap.with_name(f"{pcap.stem}_tls23_frames.json")
    data = json.loads(json_out.read_text())

    frames = {item["frame"] for item in data["matches"]}
    # 期望补标后包含 1 和 2
    assert frames == {1, 2} 