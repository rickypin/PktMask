import sys
import json
from pathlib import Path
from unittest.mock import Mock

import pytest
pytestmark = pytest.mark.integration

# 待测试脚本模块路径
MODULE_PATH = "scripts.validation.validate_tls23_frames"


def _mock_subprocess(monkeypatch, tmp_path):
    """拦截 validate_tls23_frames 调用的 tls23_marker 子进程。

    行为：
      1. 记录命令行参数；
      2. 在指定 --output-dir 目录下写入伪造的 *_tls23_frames.json 文件；
      3. 返回 returncode=0 的 CompletedProcess 模拟对象。
    """

    calls = []

    def _run(cmd, check, text=True, capture_output=True):  # noqa: D401, D403 – 测试辅助函数
        # 解析 --pcap 与 --output-dir 路径以便写入假文件
        calls.append(cmd)
        try:
            pcap_index = cmd.index("--pcap") + 1
            pcap_path = Path(cmd[pcap_index])
            out_index = cmd.index("--output-dir") + 1
            out_dir = Path(cmd[out_index])
        except (ValueError, IndexError):
            raise AssertionError("validate_tls23_frames 传递的参数格式不正确") from None

        json_path = out_dir / f"{pcap_path.stem}_tls23_frames.json"
        out_dir.mkdir(parents=True, exist_ok=True)
        json_path.write_text('[{"frame": 1, "path": "eth:ip:tcp:tls"}]', encoding="utf-8")

        completed = Mock()
        completed.returncode = 0
        completed.stdout = ""
        completed.stderr = ""
        return completed

    monkeypatch.setattr("subprocess.run", _run)
    return calls


@pytest.mark.skipif(sys.platform == "win32", reason="脚本路径兼容性在 Windows 下未验证")
def test_validate_tls23_frames_main(monkeypatch, tmp_path):
    """Phase 5 集成测试: 验证 validate_tls23_frames 主流程。"""

    calls = _mock_subprocess(monkeypatch, tmp_path)

    import importlib

    validate_mod = importlib.import_module(MODULE_PATH)

    # 使用 tests/data/tls 目录作为输入
    project_root = Path(__file__).parent.parent.parent
    input_dir = project_root / "tests" / "data" / "tls"

    argv = [
        "--input-dir",
        str(input_dir),
        "--output-dir",
        str(tmp_path),
        "--no-annotate",
    ]

    # 替换 sys.argv 以模拟命令行调用
    monkeypatch.setattr(sys, "argv", ["validate_tls23_frames"] + argv)

    # 执行脚本，捕获 SystemExit
    with pytest.raises(SystemExit) as exc:
        validate_mod.main()

    # 成功退出 (code 0)
    assert exc.value.code == 0, "脚本未以 0 退出"

    # 汇总文件存在且可解析
    summary_path = tmp_path / "tls23_validation_summary.json"
    assert summary_path.exists(), "缺少汇总 JSON 文件"

    data = json.loads(summary_path.read_text(encoding="utf-8"))
    assert data["files"], "汇总结果为空"

    # 确认 tls23_marker 被调用
    assert calls, "未调用 tls23_marker 子进程" 