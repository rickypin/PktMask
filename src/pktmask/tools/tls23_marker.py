"""TLS23 Marker Tool (Stage 1: CLI Skeleton & Environment Detection)

This module implements CLI parameter parsing and basic environment detection functionality for the tls23_marker tool,
with subsequent stages gradually adding scanning, supplementary marking and output logic.

使用示例：
    python -m pktmask.tools.tls23_marker --pcap input.pcapng
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Tuple

MIN_TSHARK_VERSION: Tuple[int, int, int] = (4, 2, 0)


def _parse_tshark_version(output: str) -> Tuple[int, int, int] | None:
    """Parse version number from `tshark -v` output.

    Expected format example::
        TShark (Wireshark) 4.2.1 (Git commit 111222)
    """
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", output)
    if not m:
        return None
    return tuple(map(int, m.groups()))  # type: ignore [return-value]


def _check_tshark_version(tshark_path: str | None, verbose: bool = False) -> str:
    """Verify local tshark is available and version is sufficient, return actual executable path.

    If `tshark_path` is empty, assume it can be called directly from PATH.
    Exit with non-zero code 1 if version is insufficient or not executable.
    """
    executable = tshark_path or "tshark"

    try:
        # Use hidden subprocess to prevent cmd window popup on Windows
        from ..utils.subprocess_utils import run_hidden_subprocess

        completed = run_hidden_subprocess(
            [executable, "-v"],
            check=True,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        sys.stderr.write(
            f"[tls23-marker] Error: Cannot execute '{executable}': {exc}\n"
        )
        sys.exit(1)

    version = _parse_tshark_version(completed.stdout + completed.stderr)
    if version is None:
        sys.stderr.write("[tls23-marker] Error: Cannot parse tshark version number.\n")
        sys.exit(1)

    if version < MIN_TSHARK_VERSION:
        ver_str = ".".join(map(str, version))
        min_str = ".".join(map(str, MIN_TSHARK_VERSION))
        sys.stderr.write(
            f"[tls23-marker] Error: tshark version too low ({ver_str}), requires ≥ {min_str}.\n"
        )
        sys.exit(1)

    if verbose:
        sys.stdout.write(
            f"[tls23-marker] 检测到 tshark {'.'.join(map(str, version))} 于 {executable}\n"
        )

    return executable


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tls23_marker",
        description="标记 TLS Application Data 帧 (content-type=23) 的工具 – Stage 1 CLI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument("--pcap", required=True, help="待分析的 pcap/pcapng 文件路径")
    parser.add_argument(
        "--decode-as",
        action="append",
        dest="decode_as",
        metavar="PORT,PROTO",
        help="额外端口解码，格式如 8443,tls，可多次指定",
    )
    parser.add_argument(
        "--no-annotate",
        action="store_true",
        help="仅输出列表，不写回注释",
    )
    parser.add_argument(
        "--formats",
        default="json,tsv",
        help="输出格式，逗号分隔，可选 json,tsv",
    )
    parser.add_argument(
        "--tshark-path",
        help="自定义 tshark 可执行文件路径 (默认从 PATH 搜索)",
    )
    parser.add_argument(
        "--memory",
        type=int,
        default=256,
        metavar="MiB",
        help="TCP 重组内存上限 (MiB)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="结果文件输出目录 (默认与输入文件同目录)",
    )
    parser.add_argument("--verbose", action="store_true", help="输出调试信息")
    parser.add_argument(
        "--legacy",
        action="store_true",
        help="启用旧版兼容模式（不输出 num_records / lengths 等新增字段）",
    )

    return parser


def _hex_to_bytes(h: str) -> bytes:
    """把 Wireshark 提供的十六进制字段(可含冒号/空格)转换成 bytes."""
    h = h.replace(":", "").replace(" ", "").strip()
    if not h:
        return b""
    import binascii

    try:
        return binascii.unhexlify(h)
    except binascii.Error:
        return b""


def main(argv: list[str] | None = None) -> None:
    argv = argv if argv is not None else sys.argv[1:]
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    # 环境检测
    tshark_exec = _check_tshark_version(args.tshark_path, args.verbose)

    if args.verbose:
        sys.stdout.write(
            f"[tls23-marker] 输入文件: {args.pcap}\n"
            f"[tls23-marker] 输出目录: {args.output_dir or Path(args.pcap).parent}\n"
            f"[tls23-marker] 输出格式: {args.formats}\n"
            f"[tls23-marker] 注释写回: {'关闭' if args.no_annotate else '开启'}\n"
            f"[tls23-marker] tshark 可执行: {tshark_exec}\n"
        )

    # -------------------- 阶段 2：显式扫描实现 -------------------- #

    # 构造 tshark 命令
    tshark_cmd: list[str] = [
        tshark_exec,
        "-2",  # 两遍分析，启用重组
        "-r",
        str(args.pcap),
        "-T",
        "json",
        # 仅输出必要字段，减少 JSON 体积
        "-e",
        "frame.number",
        "-e",
        "frame.protocols",
        "-e",
        "tls.record.content_type",
        "-e",
        "tls.record.opaque_type",
        "-e",
        "tls.record.length",
        "-e",
        "tls.app_data",  # 直接抓取应用数据 hex
        "-e",
        "tcp.stream",
        "-E",
        "occurrence=a",  # 展开所有出现
        "-o",
        "tcp.desegment_tcp_streams:TRUE",
    ]

    # 处理 decode-as
    if args.decode_as:
        for spec in args.decode_as:
            tshark_cmd += ["-d", spec]

    if args.verbose:
        sys.stdout.write(f"[tls23-marker] Running command: {' '.join(tshark_cmd)}\n")

    try:
        # Use hidden subprocess to prevent cmd window popup on Windows
        from ..utils.subprocess_utils import run_hidden_subprocess

        completed = run_hidden_subprocess(
            tshark_cmd,
            check=True,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.CalledProcessError as exc:
        sys.stderr.write(f"[tls23-marker] Error: tshark execution failed: {exc}\n")
        sys.exit(3)

    import json  # 延迟导入

    try:
        packets = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"[tls23-marker] Error: tshark JSON parsing failed: {exc}\n")
        sys.exit(3)

    hits: list[dict[str, str | int]] = []
    hits_by_stream: dict[int, set[int]] = {}
    frame_record_counts: dict[int, int] = defaultdict(int)
    zero_bytes_count: dict[int, int] = defaultdict(int)

    for pkt in packets:
        layers = pkt.get("_source", {}).get("layers", {})  # type: ignore[arg-type]
        if not layers:
            continue

        # TLS 1.3 起字段改名为 tls.record.opaque_type；旧版为 content_type
        content_types_raw = layers.get("tls.record.content_type")
        opaque_types_raw = layers.get("tls.record.opaque_type")

        def _to_list(val):
            if val is None:
                return []
            return val if isinstance(val, list) else [val]

        content_types_list = _to_list(content_types_raw)
        opaque_types_list = _to_list(opaque_types_raw)

        # 合并两类字段，保持原顺序，确保同时检测含混合记录的帧
        # Wireshark 对于同一条记录仅会输出其中一个字段，因此简单拼接即可
        type_fields = content_types_list + [
            v for v in opaque_types_list if v not in content_types_list
        ]
        if not type_fields:
            continue

        # 判断是否包含 23 (十进制) 或 0x17 (十六进制)
        def _is_23(value: str) -> bool:
            return value.strip() in {"23", "0x17", "17"}

        indices_23 = [idx for idx, v in enumerate(type_fields) if _is_23(v)]
        if not indices_23:
            continue

        # 记录长度字段，同样可能是 str / list[str]
        rec_lengths_raw = layers.get("tls.record.length")
        app_data_raw = layers.get("tls.app_data")

        # 修正"索引错配"问题的关键：
        # tshark 的 app_data 字段只包含23类型的载荷，其列表长度可能小于 content_type 列表。
        # 因此，我们为 app_data 创建一个迭代器，每遇到一个23类型记录，就从中消耗一个值。
        app_data_iter = iter(_to_list(app_data_raw))

        rec_lengths: list[int] = []
        zero_cnt_for_frame = 0

        # 不再使用 `indices_23`，而是完整遍历所有记录类型，
        # 这样可以正确处理长度和 `app_data` 的对应关系。
        for idx, type_val in enumerate(type_fields):
            if not _is_23(type_val):
                continue

            # 处理长度
            try:
                length_val = rec_lengths_raw[idx] if rec_lengths_raw else None
                rec_lengths.append(int(length_val) if length_val is not None else -1)
            except (IndexError, ValueError, TypeError):
                rec_lengths.append(-1)

            # 从迭代器安全地获取下一个 app_data
            try:
                ad_hex = next(app_data_iter)
                if ad_hex:
                    payload_bytes = _hex_to_bytes(str(ad_hex))
                    zero_cnt_for_frame += payload_bytes.count(0)
            except StopIteration:
                # app_data 已经用完，说明 tshark JSON 输出存在不一致，跳过后续统计
                pass

        frame_no = layers.get("frame.number")
        protocols = layers.get("frame.protocols")
        stream_id = layers.get("tcp.stream")

        # 这两个字段来自 -e 同样为 str 或 list[str]
        if isinstance(frame_no, list):
            frame_no = frame_no[0]
        if isinstance(protocols, list):
            protocols = protocols[0]
        if isinstance(stream_id, list):
            stream_id = stream_id[0]

        try:
            frame_no_int = int(frame_no)  # type: ignore[arg-type]
            stream_int = int(stream_id) if stream_id is not None else -1
        except (TypeError, ValueError):
            continue

        num_records = len(indices_23)

        hit: dict[str, str | int] = {"frame": frame_no_int, "path": str(protocols)}
        if not args.legacy:
            hit["num_records"] = num_records
            hit["lengths"] = rec_lengths

        hits.append(hit)
        frame_record_counts[frame_no_int] = num_records
        if stream_int >= 0:
            hits_by_stream.setdefault(stream_int, set()).add(frame_no_int)
        if zero_cnt_for_frame > 0:
            zero_bytes_count[frame_no_int] = zero_cnt_for_frame

    if args.verbose:
        sys.stdout.write(f"[tls23-marker] 显式扫描命中 {len(hits)} 帧。\n")

    # -------------------- 阶段 3：缺头补标实现 -------------------- #

    # 以 streamID -> set(frame_no) 形式补充 hits
    supplemented_frames: dict[int, set[int]] = {
        k: set(v) for k, v in hits_by_stream.items()
    }

    for stream_id in hits_by_stream.keys():
        stream_cmd = [
            tshark_exec,
            "-2",
            "-r",
            str(args.pcap),
            "-Y",
            f"tcp.stream == {stream_id}",
            "-T",
            "json",
            "-e",
            "frame.number",
            "-e",
            "frame.protocols",
            "-e",
            "tcp.seq_relative",
            "-e",
            "tcp.len",
            "-e",
            "tcp.payload",
            "-E",
            "occurrence=a",
            "-o",
            "tcp.desegment_tcp_streams:TRUE",
        ]

        try:
            # Use hidden subprocess to prevent cmd window popup on Windows
            from ..utils.subprocess_utils import run_hidden_subprocess

            completed_stream = run_hidden_subprocess(
                stream_cmd,
                check=True,
                text=True,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
            )
        except subprocess.CalledProcessError:
            continue  # 跳过无法解析的流

        import json as _json  # 避免与外层 json 混淆

        try:
            pkt_list = _json.loads(completed_stream.stdout)
        except _json.JSONDecodeError:
            continue

        segments: list[tuple[int, bytes, int, str]] = []
        min_seq = None

        for p in pkt_list:
            layers2 = p.get("_source", {}).get("layers", {})  # type: ignore[arg-type]
            frame_no_raw = layers2.get("frame.number")
            protocols2 = layers2.get("frame.protocols")
            seq_raw = layers2.get("tcp.seq_relative") or layers2.get("tcp.seq")
            payload_raw = layers2.get("tcp.payload")

            if isinstance(frame_no_raw, list):
                frame_no_raw = frame_no_raw[0]
            if isinstance(protocols2, list):
                protocols2 = protocols2[0]
            if isinstance(seq_raw, list):
                seq_raw = seq_raw[0]
            if isinstance(payload_raw, list):
                payload_raw = payload_raw[0]

            try:
                frame_no_i = int(frame_no_raw)  # type: ignore[arg-type]
                seq_i = int(seq_raw)
            except (TypeError, ValueError):
                continue

            payload_bytes = _hex_to_bytes(str(payload_raw or ""))

            if not payload_bytes:
                continue

            segments.append((seq_i, payload_bytes, frame_no_i, str(protocols2)))
            if min_seq is None or seq_i < min_seq:
                min_seq = seq_i

        if not segments or min_seq is None:
            continue

        # 按 seq 排序
        segments.sort(key=lambda x: x[0])

        # 计算总长度
        max_end = max(s[0] + len(s[1]) for s in segments)
        total_len = max_end - min_seq

        data = bytearray(total_len)
        frame_map: list[int] = [-1] * total_len
        proto_map: dict[int, str] = {}

        for seq_i, payload_bytes, frame_no_i, proto_str in segments:
            offset = seq_i - min_seq
            for idx, b in enumerate(payload_bytes):
                pos = offset + idx
                if 0 <= pos < total_len and frame_map[pos] == -1:
                    data[pos] = b
                    frame_map[pos] = frame_no_i
            proto_map[frame_no_i] = proto_str

        # 扫描 TLS 记录
        cursor = 0
        while cursor + 5 <= total_len:
            content_type = data[cursor]
            rec_len = int.from_bytes(data[cursor + 3 : cursor + 5], "big")
            total_rec_len = 5 + rec_len

            # 若解析到异常长度 / 剩余数据不足，则滑动 1 字节重新同步，而非直接结束
            if total_rec_len <= 0 or cursor + total_rec_len > total_len:
                cursor += 1
                continue

            if content_type == 0x17:
                # 计算该 TLS Application Data 记录中值为 0x00 的字节数量，并按 frame 归档
                # payload_start = cursor + 5  # 跳过 TLS 记录头 (type+version+length)
                cursor + total_rec_len

                # Phase 3 的零字节统计逻辑存在缺陷且与Phase 2重复，予以禁用，统一依赖Phase 2的结果
                # for pos in range(payload_start, payload_end):
                #     if data[pos] == 0:
                #         _frame_idx = frame_map[pos]
                #         if _frame_idx != -1:
                #             zero_bytes_count[_frame_idx] += 1

                frames_set = {
                    frame_map[i]
                    for i in range(cursor, cursor + total_rec_len)
                    if frame_map[i] != -1
                }
                supplemented_frames[stream_id].update(frames_set)
                for _f in frames_set:
                    frame_record_counts[_f] += 1

            cursor += total_rec_len

        # end stream loop

    # 合并补标结果到 hits
    existing_frames = {item["frame"] for item in hits}
    for stream_id, frames_set in supplemented_frames.items():
        for frame_no in frames_set:
            if frame_no in existing_frames:
                continue

            path_str = "eth:ip:tcp:tls"  # fallback

            new_hit: dict[str, str | int] = {"frame": frame_no, "path": path_str}
            if not args.legacy:
                new_hit["num_records"] = frame_record_counts.get(frame_no, 1)
            hits.append(new_hit)

    # 先根据最终统计结果同步每帧的 num_records 字段（非 legacy 模式）
    if not args.legacy:
        frame_to_hit = {h["frame"]: h for h in hits}
        for _f, _cnt in frame_record_counts.items():
            if _f in frame_to_hit:
                frame_to_hit[_f]["num_records"] = _cnt

        # 合并零字节统计信息
        for _f, _z in zero_bytes_count.items():
            if _f in frame_to_hit:
                frame_to_hit[_f]["zero_bytes"] = _z

        # 对于未统计到零字节的帧，默认填充 0
        for h in hits:
            if "zero_bytes" not in h:
                h["zero_bytes"] = 0

    total_frames = len(hits)

    # -------------------- 汇总统计 (Stage 5) -------------------- #
    total_records = 0
    path_counter: Counter[str] = Counter()

    for item in hits:
        num_rec = item.get("num_records", 1) if not args.legacy else 1
        if not isinstance(num_rec, int):
            try:
                num_rec = int(num_rec)
            except Exception:
                num_rec = 1
        total_records += num_rec
        path_counter[item["path"]] += num_rec

    summary_info = {
        "total_frames": total_frames,
        "total_records": total_records,
        "by_path": dict(sorted(path_counter.items(), key=lambda kv: (-kv[1], kv[0]))),
        # 兼容旧字段
        "total_matches": total_frames,
    }

    if args.verbose:
        sys.stdout.write(
            f"[tls23-marker] 补标后共 {total_records} 条记录分布于 {total_frames} 帧，{len(path_counter)} 个协议路径。\n"
        )

    # -------------------- 输出结果 -------------------- #
    output_dir = Path(args.output_dir) if args.output_dir else Path(args.pcap).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    formats = [fmt.strip().lower() for fmt in args.formats.split(",") if fmt.strip()]

    stem = Path(args.pcap).stem
    if "json" in formats:
        json_path = output_dir / f"{stem}_tls23_frames.json"
        with json_path.open("w", encoding="utf-8") as fp:
            json.dump(
                {"summary": summary_info, "matches": hits},
                fp,
                ensure_ascii=False,
                indent=2,
            )
        if args.verbose:
            sys.stdout.write(f"[tls23-marker] Wrote JSON: {json_path}\n")

    if "tsv" in formats:
        tsv_path = output_dir / f"{stem}_tls23_frames.tsv"
        with tsv_path.open("w", encoding="utf-8") as fp:
            # Header lines with summary
            fp.write(f"# total_frames\t{total_frames}\n")
            fp.write(f"# total_records\t{total_records}\n")
            for path, cnt in summary_info["by_path"].items():
                fp.write(f"# {path}\t{cnt}\n")

            # Detail rows
            for item in hits:
                base_cols = f"{item['frame']}\t{item['path']}"
                if not args.legacy:
                    num_rec = item.get("num_records", 1)
                    lengths_txt = (
                        ",".join(map(str, item.get("lengths", [])))
                        if item.get("lengths")
                        else ""
                    )
                    zero_bytes = item.get("zero_bytes", 0)
                    fp.write(f"{base_cols}\t{num_rec}\t{lengths_txt}\t{zero_bytes}\n")
                else:
                    fp.write(f"{base_cols}\n")

    # -------------------- Annotation (Stage 4) -------------------- #

    if not args.no_annotate:
        import shutil

        editcap_exec = shutil.which("editcap")
        if editcap_exec is None:
            sys.stderr.write(
                "[tls23-marker] Warning: 'editcap' not found. Skip annotation.\n"
            )
        else:
            annotated_path = output_dir / f"{stem}_annotated.pcapng"

            # Build file-level capture comment summarizing statistics in English
            capture_comment_parts = [
                f"TLS23 Marker: {total_records} records in {total_frames} packets",
            ]
            capture_comment_parts += [
                f"{path}={cnt}" for path, cnt in summary_info["by_path"].items()
            ]
            capture_comment = "; ".join(capture_comment_parts)

            editcap_cmd: list[str] = [
                editcap_exec,
                "--capture-comment",
                capture_comment,
            ]

            # Per-frame comments
            for item in sorted(hits, key=lambda x: int(x["frame"])):
                if not args.legacy and item.get("num_records", 1) > 1:
                    comment_text = (
                        f"TLS23 Application Data ({item['num_records']} records)"
                    )
                else:
                    comment_text = "TLS23 Application Data"
                editcap_cmd += ["-a", f"{item['frame']}:{comment_text}"]

            editcap_cmd += [str(args.pcap), str(annotated_path)]

            if args.verbose:
                short_preview = " ".join(editcap_cmd[:15]) + (
                    " ..." if len(editcap_cmd) > 15 else ""
                )
                sys.stdout.write(
                    f"[tls23-marker] Calling editcap for annotation: {short_preview}\n"
                )

            try:
                # Use hidden subprocess to prevent cmd window popup on Windows
                from ..utils.subprocess_utils import run_hidden_subprocess

                run_hidden_subprocess(
                    editcap_cmd, check=True, encoding="utf-8", errors="replace"
                )
                if args.verbose:
                    sys.stdout.write(
                        f"[tls23-marker] Generated annotated file: {annotated_path}\n"
                    )
            except subprocess.CalledProcessError as exc:
                sys.stderr.write(
                    f"[tls23-marker] Warning: editcap annotation failed: {exc}\n"
                )

    # Success exit
    sys.exit(0)


if __name__ == "__main__":
    main()


# ---------------------------------------------------------------------------
# Helper functions (moved to top of file to avoid duplication)
# ---------------------------------------------------------------------------
