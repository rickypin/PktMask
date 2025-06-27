#!/usr/bin/env python3
"""validate_tls23_frames.py — Phase 5 集成测试脚本

此脚本批量调用 *tls23_marker* 工具，对目录中的 pcap/pcapng 文件
进行 TLS Application-Data(frame.content-type = 23) 帧标记，并汇总结果。

用法示例：
    python scripts/validation/validate_tls23_frames.py \
        --input-dir tests/data/tls \
        --output-dir output/reports/tls23_validation \
        --no-annotate --verbose

退出码：
    0  所有文件扫描成功且生成 JSON 结果;
    1  有文件处理失败 / 结果缺失;
    2  输入目录不存在或为空。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

__all__ = ["main"]

# ---------------------------------------------------------------------------
# CLI & util helpers
# ---------------------------------------------------------------------------

def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="validate_tls23_frames",
        description="批量运行 tls23_marker 并汇总结果的集成测试脚本",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--input-dir",
        type=Path,
        required=True,
        help="包含 pcap/pcapng 文件的目录",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="结果输出目录，默认为 <input-dir>/tls23_marker_results",
    )
    parser.add_argument(
        "--tshark-path",
        help="自定义 tshark 可执行文件路径，将透传给 tls23_marker",
    )
    parser.add_argument(
        "--formats",
        default="json",
        help="tls23_marker 输出格式 (逗号分隔)，默认仅生成 json",
    )
    parser.add_argument(
        "--no-annotate",
        action="store_true",
        help="调用 tls23_marker 时添加 --no-annotate 以加速扫描",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="输出详细执行日志",
    )
    return parser


def _find_pcap_files(directory: Path) -> List[Path]:
    """在目录中查找所有 .pcap / .pcapng 文件 (非递归)。"""
    return sorted(
        [
            p
            for p in directory.iterdir()
            if p.is_file() and p.suffix in {".pcap", ".pcapng"}
        ]
    )


# ---------------------------------------------------------------------------
# Main workflow
# ---------------------------------------------------------------------------

def main(argv: List[str] | None = None) -> None:  # noqa: C901 – 保持单函数结构便于调用
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    input_dir: Path = args.input_dir
    if not input_dir.exists() or not input_dir.is_dir():
        sys.stderr.write(f"[validate-tls23] 输入目录不存在或不是目录: {input_dir}\n")
        sys.exit(2)

    pcap_files = _find_pcap_files(input_dir)
    if not pcap_files:
        sys.stderr.write(f"[validate-tls23] 目录中未找到 pcap/pcapng 文件: {input_dir}\n")
        sys.exit(2)

    output_dir: Path = args.output_dir or (input_dir / "tls23_marker_results")
    output_dir.mkdir(parents=True, exist_ok=True)

    summary: Dict[str, Any] = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "input_dir": str(input_dir.resolve()),
        "output_dir": str(output_dir.resolve()),
        "files": [],
    }

    overall_success = True

    for pcap in pcap_files:
        cmd: List[str] = [
            sys.executable,
            "-m",
            "pktmask.tools.tls23_marker",
            "--pcap",
            str(pcap),
            "--formats",
            args.formats,
            "--output-dir",
            str(output_dir),
        ]
        if args.no_annotate:
            cmd.append("--no-annotate")
        if args.tshark_path:
            cmd.extend(["--tshark-path", args.tshark_path])

        if args.verbose:
            sys.stdout.write(f"[validate-tls23] 运行: {' '.join(cmd)}\n")

        try:
            # 捕获输出，方便后续调试，但不打印到屏幕
            completed = subprocess.run(
                cmd,
                check=True,
                text=True,
                capture_output=not args.verbose,
            )
            if args.verbose and completed.stdout:
                sys.stdout.write(completed.stdout)
            if args.verbose and completed.stderr:
                sys.stderr.write(completed.stderr)

        except subprocess.CalledProcessError as exc:
            sys.stderr.write(f"[validate-tls23] 处理 {pcap.name} 失败，退出码 {exc.returncode}\n")
            if exc.stderr:
                sys.stderr.write(exc.stderr)
            overall_success = False
            continue

        # ------------------------------------------------------------
        # 根据 --formats 参数决定验证逻辑
        # ------------------------------------------------------------
        requested_formats = {fmt.strip().lower() for fmt in args.formats.split(',') if fmt.strip()}

        file_entry: Dict[str, Any] = {
            "file": str(pcap.name),
            "frames_detected": 0,
            "status": "ok",
        }

        # ---- Prefer JSON when存在 ----
        if "json" in requested_formats:
            json_path = output_dir / f"{pcap.stem}_tls23_frames.json"
            file_entry["json"] = str(json_path.name)

            if not json_path.exists():
                sys.stderr.write(f"[validate-tls23] 缺少预期输出文件: {json_path}\n")
                file_entry["status"] = "missing_json"
                overall_success = False
            else:
                try:
                    frames_data = json.loads(json_path.read_text(encoding="utf-8"))
                    if isinstance(frames_data, list):
                        # legacy schema
                        file_entry["frames_detected"] = len(frames_data)
                    else:
                        file_entry["frames_detected"] = (
                            frames_data.get("summary", {}).get("total_matches", 0)
                        )
                except Exception as e:  # pragma: no cover
                    sys.stderr.write(f"[validate-tls23] 解析 {json_path.name} 失败: {e}\n")
                    file_entry["status"] = "parse_error"
                    overall_success = False

        # ---- Fallback to TSV when仅请求 TSV ----
        elif "tsv" in requested_formats:
            tsv_path = output_dir / f"{pcap.stem}_tls23_frames.tsv"
            file_entry["tsv"] = str(tsv_path.name)

            if not tsv_path.exists():
                sys.stderr.write(f"[validate-tls23] 缺少预期输出文件: {tsv_path}\n")
                file_entry["status"] = "missing_tsv"
                overall_success = False
            else:
                try:
                    total_frames = None
                    detail_rows = 0
                    with tsv_path.open("r", encoding="utf-8") as fp:
                        for line in fp:
                            line = line.rstrip("\n")
                            if not line:
                                continue
                            if line.startswith("#"):
                                # Header lines like: "# total_frames\t42"
                                parts = line[1:].split("\t", 1)
                                if len(parts) == 2 and parts[0].strip() == "total_frames":
                                    try:
                                        total_frames = int(parts[1].strip())
                                    except ValueError:
                                        total_frames = None
                                continue
                            # non-header detail row
                            detail_rows += 1
                    file_entry["frames_detected"] = total_frames if total_frames is not None else detail_rows
                except Exception as e:  # pragma: no cover
                    sys.stderr.write(f"[validate-tls23] 解析 {tsv_path.name} 失败: {e}\n")
                    file_entry["status"] = "parse_error"
                    overall_success = False
        else:
            # 既不包含 json 也不包含 tsv —— 无法判定结果
            sys.stderr.write(
                "[validate-tls23] 无法验证输出，未包含 json/tsv 任一格式。请至少启用其中一种。\n"
            )
            file_entry["status"] = "unsupported_format"
            overall_success = False

        summary["files"].append(file_entry)

    # 写入汇总 JSON
    summary_path = output_dir / "tls23_validation_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.verbose:
        sys.stdout.write(f"[validate-tls23] 已写入汇总文件: {summary_path}\n")

    sys.exit(0 if overall_success else 1)


if __name__ == "__main__":
    main() 