import argparse
import json
import logging
import shutil
import subprocess
import sys
from glob import glob
from pathlib import Path
from typing import List, Dict, Any

# -------------------------- 日志配置 --------------------------
LOG_FORMAT = "[%(levelname)s] %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger("tls23_e2e_validator")

# ---------------------- 常量与工具函数 ------------------------
DEFAULT_GLOB = "**/*.pcap,**/*.pcapng"
DEFAULT_OUTPUT_DIR = Path("output/tls23_e2e")
PYTHON_EXEC = sys.executable  # 遵循用户规则：使用当前 python3 可执行文件


def run_cmd(cmd: List[str], verbose: bool = False) -> None:
    """执行外部命令并实时输出。出现非零退出码时抛出 RuntimeError"""
    if verbose:
        logger.info("运行命令: %s", " ".join(cmd))
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if verbose and result.stdout:
        print(result.stdout)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(cmd)}\n{result.stdout}")


def discover_files(input_dir: Path, pattern: str) -> List[Path]:
    """递归扫描输入目录符合 glob 模式的文件。

    支持以逗号或空格分隔的多个 glob 表达式，例如
    "**/*.pcap,**/*.pcapng"。"""
    patterns = [p.strip() for p in pattern.replace(" ", ",").split(",") if p.strip()]
    matched: List[Path] = []
    for pat in patterns:
        matched.extend(Path(p) for p in glob(str(input_dir / pat), recursive=True))
    # 去重并仅保留文件
    unique_files = {p.resolve() for p in matched if p.is_file()}
    return [Path(p) for p in unique_files]


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def extract_frames(data: Any) -> List[Dict[str, Any]]:
    """根据 tls23_marker 输出格式提取帧列表。尽量兼容多种结构"""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        # 新版 schema 使用 "matches"
        for key in ("frames", "records", "packets", "matches"):
            if key in data and isinstance(data[key], list):
                return data[key]
    return []


def is_zero_payload(frame: Dict[str, Any]) -> bool:
    """判断 frame 是否已全部置零。兼容多种字段格式：
    1) 旧版 schema 使用 payload_preview / data 等十六进制字符串
    2) 新版 schema 使用 zero_bytes + lengths 数字统计"""
    # --- 新版 numeric 判断 ---
    if "zero_bytes" in frame:
        zb = frame.get("zero_bytes", 0)
        if "lengths" in frame and isinstance(frame["lengths"], list) and frame["lengths"]:
            total_len = sum(frame["lengths"])
            return zb >= total_len  # 若置零字节数>=总长度，则认为已全部置零
        # 没有 lengths 字段时，若 zero_bytes>0 则视为已置零（保守假设）
        return zb > 0

    # --- 旧版字符串判断 ---
    hex_fields = []
    for key in ("payload_preview", "data", "payload_hex", "payload"):
        if key in frame and isinstance(frame[key], str):
            hex_fields.append(frame[key])
    if not hex_fields:
        # 无载荷字段，视为已置零（可能长度==0）
        return True
    for hf in hex_fields:
        cleaned = hf.replace(" ", "").replace(":", "")
        if cleaned and set(cleaned) != {"0"}:
            return False
    return True


# ---------------------- 主验证逻辑 ----------------------------

def validate_file(original_json: Path, masked_json: Path) -> Dict[str, Any]:
    """比较原始与掩码后的 tls23_marker JSON 结果。

    返回字段说明：
    - status: pass / fail
    - total_records: TLS 23 消息总数
    - masked_records: 完全成功掩码的消息数
    - unmasked_records: 未完全掩码的消息数
    - records_before / records_after: 原始、掩码文件检测到的消息数
    - masked_ok_frames: 完全掩码的帧号列表
    - failed_frames: 未完全掩码(仍含明文字节)的帧号列表
    - failed_frame_details: 掩码失败帧的主要信息
    """
    original_frames = extract_frames(read_json(original_json))
    masked_frames = extract_frames(read_json(masked_json))

    # 使用 packet_number 或 frame 字段标识帧
    def _get_frame_no(f: Dict[str, Any]) -> int:
        for k in ("packet_number", "frame", "frame_no", "no"):
            if k in f and isinstance(f[k], int):
                return f[k]
        return -1

    # 构建帧号到 frame 对象的映射，便于后续比较
    masked_by_no = { _get_frame_no(f): f for f in masked_frames }

    failed_frames: List[int] = []
    masked_ok_frames: List[int] = []
    failed_frame_details: List[Dict[str, Any]] = []

    for no, m_frame in masked_by_no.items():
        if no == -1:  # 无法识别帧号，跳过
            continue
        if is_zero_payload(m_frame):
            masked_ok_frames.append(no)
        else:
            failed_frames.append(no)
            # 收集关键信息，方便调试
            failed_frame_details.append({
                "frame": no,
                "path": m_frame.get("path"),
                "lengths": m_frame.get("lengths"),
                "zero_bytes": m_frame.get("zero_bytes"),
                "num_records": m_frame.get("num_records"),
                # 尝试提供十六进制预览（若有）
                "payload_preview": m_frame.get("payload_preview") or m_frame.get("data") or m_frame.get("payload_hex"),
            })

    total_records = len(masked_frames)
    masked_records = len(masked_ok_frames)
    unmasked_records = len(failed_frames)

    status = "pass" if unmasked_records == 0 else "fail"

    return {
        "status": status,
        "records_before": len(original_frames),
        "records_after": len(masked_frames),
        "total_records": total_records,
        "masked_records": masked_records,
        "unmasked_records": unmasked_records,
        "masked_ok_frames": sorted(masked_ok_frames),
        "failed_frames": sorted(failed_frames),
        "failed_frame_details": failed_frame_details,
    }


# ---------------------- 后端处理函数 --------------------------

def run_pktmask_trim_internal(input_path: Path, output_path: Path, verbose: bool = False) -> None:
    """使用内部 EnhancedTrimmer 处理文件，避免启动 GUI。"""
    if verbose:
        logger.info("使用 EnhancedTrimmer 后端处理: %s -> %s", input_path, output_path)

    try:
        from pktmask.core.processors.enhanced_trimmer import EnhancedTrimmer
        from pktmask.core.processors.base_processor import ProcessorConfig
    except ImportError as imp_err:
        raise RuntimeError(f"无法导入 EnhancedTrimmer: {imp_err}")

    trimmer = EnhancedTrimmer(config=ProcessorConfig(enabled=True, name="EnhancedTrimmer", priority=0))
    if not trimmer.initialize():
        raise RuntimeError("EnhancedTrimmer 初始化失败")

    result = trimmer.process_file(str(input_path), str(output_path))
    if not result.success:
        raise RuntimeError(f"EnhancedTrimmer 处理失败: {result.error or '未知错误'}")

    if verbose:
        # 优先尝试从处理详情中提取批量掩码统计
        stats = result.stats or {}
        try:
            details = result.data.get("details", {}) if isinstance(result.data, dict) else {}
            perf = details.get("stage_performance", {}).get("TcpPayloadMaskerAdapter", {})
            stage_stats = perf.get("stats", {}) if isinstance(perf, dict) else {}
            if stage_stats:
                stats.update(stage_stats)
        except Exception:
            pass
        logger.info("EnhancedTrimmer 处理完成: %s", stats)


# -------------------------- CLI -------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="TLS23 端到端掩码验证脚本 (基于 tls23_marker + PktMask)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--input-dir", type=Path, required=True, help="递归扫描 PCAP/PCAPNG 的目录")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="结果输出目录")
    parser.add_argument("--pktmask-mode", default="trim", help="调用 PktMask 主程序的模式")
    parser.add_argument("--glob", dest="glob_pattern", default=DEFAULT_GLOB, help="文件匹配 glob 表达式")
    parser.add_argument("--verbose", action="store_true", help="输出详细调试信息")

    args = parser.parse_args()

    input_dir: Path = args.input_dir
    output_dir: Path = args.output_dir
    glob_pattern: str = args.glob_pattern
    verbose: bool = args.verbose

    # 专用目录保存掩码后的 PCAP，以避免污染原始目录，便于后续清理
    masked_dir: Path = output_dir / "masked_pcaps"
    masked_dir.mkdir(parents=True, exist_ok=True)

    files = discover_files(input_dir, glob_pattern)
    if not files:
        logger.error("输入目录无匹配文件: %s", input_dir)
        sys.exit(2)

    results = []
    passed_files = 0

    for pcap_path in files:
        stem = pcap_path.stem
        suffix = pcap_path.suffix  # .pcap / .pcapng
        orig_json = output_dir / f"{stem}_orig_tls23.json"
        masked_json = output_dir / f"{stem}_masked_tls23.json"

        try:
            # ---------- 第一次扫描 ----------
            run_cmd(
                [
                    PYTHON_EXEC,
                    "-m",
                    "pktmask.tools.tls23_marker",
                    "--pcap",
                    str(pcap_path),
                    "--no-annotate",
                    "--formats",
                    "json",
                    "--output-dir",
                    str(output_dir),
                ],
                verbose,
            )
            # 移动文件为 _orig_tls23.json
            tmp_json = output_dir / f"{stem}_tls23_frames.json"
            if tmp_json.exists():
                shutil.move(tmp_json, orig_json)

            # ---------- 调用 PktMask 进行掩码 ----------
            masked_file = masked_dir / f"{stem}_masked{suffix}"
            run_pktmask_trim_internal(pcap_path, masked_file, verbose)

            # ---------- 第二次扫描 ----------
            run_cmd(
                [
                    PYTHON_EXEC,
                    "-m",
                    "pktmask.tools.tls23_marker",
                    "--pcap",
                    str(masked_file),
                    "--no-annotate",
                    "--formats",
                    "json",
                    "--output-dir",
                    str(output_dir),
                ],
                verbose,
            )
            tmp_json_masked = output_dir / f"{stem}_masked_tls23_frames.json"
            # 如果 tls23_marker 仍然使用 _tls23_frames.json 命名，则兼容处理
            if not tmp_json_masked.exists():
                generic_tmp = output_dir / f"{stem}_tls23_frames.json"
                if generic_tmp.exists():
                    tmp_json_masked = generic_tmp
            if tmp_json_masked.exists():
                shutil.move(tmp_json_masked, masked_json)

            # ---------- 结果对比 ----------
            file_result = validate_file(orig_json, masked_json)
            file_result["file"] = pcap_path.name
            results.append(file_result)
            if file_result["status"] == "pass":
                passed_files += 1
                logger.info("✅ %s - 通过", pcap_path.name)
            else:
                logger.warning("❌ %s - 失败", pcap_path.name)

        except Exception as e:
            logger.error("处理文件 %s 时出错: %s", pcap_path, e)
            results.append({
                "file": pcap_path.name,
                "status": "error",
                "error": str(e),
            })

    overall_pass_rate = (passed_files / len(files)) * 100
    summary = {
        "overall_pass_rate": round(overall_pass_rate, 2),
        "files": results,
    }
    write_json(output_dir / "validation_summary.json", summary)

    # 生成 HTML 报告
    write_html_report(summary, output_dir / "validation_summary.html")

    logger.info("📊 Overall Pass Rate: %.2f%%", overall_pass_rate)

    # 退出码
    if passed_files == len(files):
        sys.exit(0)
    else:
        sys.exit(1)


def write_html_report(summary: Dict[str, Any], output_path: Path) -> None:
    """根据 summary 生成人类可读的 HTML 报告"""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 简单内联样式，避免外部依赖
    style = (
        "body{font-family:Arial,Helvetica,sans-serif;margin:20px;}"
        "h1{font-size:24px;} table{border-collapse:collapse;width:100%;}"
        "th,td{border:1px solid #ddd;padding:8px;} th{background:#f4f4f4;}"
        "tr.pass{background:#e8f7e4;} tr.fail{background:#fdecea;}"
        "code{background:#f4f4f4;padding:2px 4px;border-radius:4px;}"
    )

    rows_html = []
    for f in summary.get("files", []):
        status = f.get("status")
        cls = "pass" if status == "pass" else "fail"
        rows_html.append(
            f"<tr class='{cls}'>"
            f"<td>{f.get('file')}</td>"
            f"<td>{status}</td>"
            f"<td>{f.get('total_records','-')}</td>"
            f"<td>{f.get('masked_records','-')}</td>"
            f"<td>{f.get('unmasked_records','-')}</td>"
            f"</tr>"
        )
        # 若失败则添加详情行，可折叠 <details>
        if status != "pass" and f.get("failed_frame_details"):
            detail_lines = []
            for d in f["failed_frame_details"]:
                frame = d.get("frame")
                path = d.get("path")
                zero = d.get("zero_bytes")
                lens = d.get("lengths")
                preview = (d.get("payload_preview") or "").replace("<", "&lt;")
                detail_lines.append(
                    f"<li>帧 <code>{frame}</code> | path=<code>{path}</code> | lengths={lens} | zero_bytes={zero} | payload_preview=<code>{preview}</code></li>"
                )
            details_html = "<details><summary>失败帧详情</summary><ul>" + "\n".join(detail_lines) + "</ul></details>"
            rows_html.append(f"<tr class='{cls}'><td colspan='5'>" + details_html + "</td></tr>")

    html = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<title>TLS23 Validation Report</title><style>{style}</style></head><body>"
        f"<h1>TLS23 Validation Report</h1>"
        f"<p>Overall Pass Rate: <strong>{summary.get('overall_pass_rate')}%</strong></p>"
        "<table><thead><tr><th>File</th><th>Status</th><th>Total Records</th><th>Masked</th><th>Unmasked</th></tr></thead><tbody>"
        + "\n".join(rows_html) + "</tbody></table>" "</body></html>"
    )

    output_path.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        logger.exception("运行时异常: %s", exc)
        sys.exit(3) 