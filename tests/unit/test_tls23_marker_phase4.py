import json
import pytest
pytestmark = pytest.mark.unit

MODULE_PATH = "pktmask.tools.tls23_marker"


def _import_module():
    import importlib
    return importlib.import_module(MODULE_PATH)


class _Completed:
    def __init__(self, stdout=""):
        self.stdout = stdout
        self.stderr = ""


def _mock_subprocess_for_phase4(monkeypatch):
    """模拟 tshark 两轮调用 + editcap 调用，记录命令序列。"""

    calls = []

    sample_first = json.dumps([
        {
            "_source": {
                "layers": {
                    "frame.number": ["1"],
                    "frame.protocols": ["eth:ip:tcp:tls"],
                    "tls.record.content_type": ["23"],
                    "tcp.stream": ["0"],
                }
            }
        }
    ])

    sample_second = json.dumps([])  # 二次扫描无需补帧

    def _run(cmd, check, text=True, capture_output=True):
        calls.append(cmd)
        if "-v" in cmd:
            return _Completed("TShark (Wireshark) 4.2.3")
        if "editcap" in cmd[0]:
            return _Completed("")
        # tshark 调用
        if any("tcp.stream" in c for c in cmd):
            return _Completed(sample_second)
        return _Completed(sample_first)

    monkeypatch.setattr("subprocess.run", _run)
    monkeypatch.setattr("shutil.which", lambda name: name)  # 假设 editcap 存在

    return calls


def test_phase4_annotation(monkeypatch, tmp_path):
    calls = _mock_subprocess_for_phase4(monkeypatch)
    tls23 = _import_module()

    pcap = tmp_path / "sample.pcapng"
    pcap.touch()

    argv = ["--pcap", str(pcap), "--formats", "json"]  # 默认注释开启

    with pytest.raises(SystemExit) as exc:
        tls23.main(argv)
    assert exc.value.code == 0

    # 确认 editcap 被调用
    assert any(cmd[0] == "editcap" for cmd in calls), "editcap 未被调用" 