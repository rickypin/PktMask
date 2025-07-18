#!/usr/bin/env python3
"""Enhanced TLS Marker Tool - 支持所有TLS协议类型检测

本模块实现了增强版 TLS marker 工具，能够检测和分析所有 TLS 协议类型(20-24)：
- TLS-20: ChangeCipherSpec  
- TLS-21: Alert
- TLS-22: Handshake
- TLS-23: ApplicationData
- TLS-24: Heartbeat

主要用于双模块架构(Marker + Masker)的验证和测试。

使用示例：
    python -m pktmask.tools.enhanced_tls_marker --pcap input.pcapng
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple


MIN_TSHARK_VERSION: Tuple[int, int, int] = (4, 2, 0)

# TLS协议类型映射
TLS_CONTENT_TYPES = {
    20: "ChangeCipherSpec",
    21: "Alert", 
    22: "Handshake",
    23: "ApplicationData",
    24: "Heartbeat"
}

# TLS处理策略映射（根据设计方案）
TLS_PROCESSING_STRATEGIES = {
    20: "keep_all",      # ChangeCipherSpec - 完全保留
    21: "keep_all",      # Alert - 完全保留
    22: "keep_all",      # Handshake - 完全保留
    23: "mask_payload",  # ApplicationData - 智能掩码(保留5字节头部)
    24: "keep_all"       # Heartbeat - 完全保留
}


def _parse_tshark_version(output: str) -> Tuple[int, int, int] | None:
    """从 `tshark -v` 输出解析版本号。"""
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", output)
    if not m:
        return None
    return tuple(map(int, m.groups()))  # type: ignore [return-value]


def _check_tshark_version(tshark_path: str | None, verbose: bool = False) -> str:
    """验证本地 tshark 可用且版本足够，返回实际可执行路径。"""
    executable = tshark_path or "tshark"

    try:
        # Use hidden subprocess to prevent cmd window popup on Windows
        from ..utils.subprocess_utils import run_hidden_subprocess
        completed = run_hidden_subprocess(
            [executable, "-v"], check=True, text=True, capture_output=True, encoding='utf-8', errors='replace'
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        sys.stderr.write(
            f"[enhanced-tls-marker] 错误: 无法执行 '{executable}': {exc}\n"
        )
        sys.exit(1)

    version = _parse_tshark_version(completed.stdout + completed.stderr)
    if version is None:
        sys.stderr.write("[enhanced-tls-marker] 错误: 无法解析 tshark 版本号。\n")
        sys.exit(1)

    if version < MIN_TSHARK_VERSION:
        ver_str = ".".join(map(str, version))
        min_str = ".".join(map(str, MIN_TSHARK_VERSION))
        sys.stderr.write(
            f"[enhanced-tls-marker] 错误: tshark 版本过低 ({ver_str})，需要 ≥ {min_str}.\n"
        )
        sys.exit(1)

    if verbose:
        sys.stdout.write(
            f"[enhanced-tls-marker] 检测到 tshark {'.'.join(map(str, version))} 于 {executable}\n"
        )

    return executable


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


def _to_list(val: Any) -> List[str]:
    """统一转换为列表格式"""
    if val is None:
        return []
    return val if isinstance(val, list) else [val]


def _is_target_content_type(value: str, target_types: set[int] = None) -> Tuple[bool, int]:
    """判断是否为目标TLS内容类型，返回(是否匹配, 协议类型)"""
    if target_types is None:
        target_types = set(TLS_CONTENT_TYPES.keys())  # 默认检测所有类型
    
    value = value.strip()
    
    # 检查十进制格式
    try:
        decimal_val = int(value)
        if decimal_val in target_types:
            return True, decimal_val
    except ValueError:
        pass
    
    # 检查十六进制格式
    if value.startswith("0x"):
        try:
            hex_val = int(value, 16)
            if hex_val in target_types:
                return True, hex_val
        except ValueError:
            pass
    
    return False, -1


def _analyze_tls_records(packets: List[Dict], target_types: set[int] = None, verbose: bool = False) -> Dict[str, Any]:
    """分析TLS记录，返回详细的协议类型统计信息"""
    if target_types is None:
        target_types = set(TLS_CONTENT_TYPES.keys())
    
    hits: List[Dict[str, Any]] = []
    hits_by_stream: Dict[int, set[int]] = {}
    frame_record_counts: Dict[int, int] = defaultdict(int)
    zero_bytes_count: Dict[int, int] = defaultdict(int)
    protocol_type_stats: Dict[int, int] = defaultdict(int)
    frame_protocol_types: Dict[int, List[int]] = defaultdict(list)

    for pkt in packets:
        layers = pkt.get("_source", {}).get("layers", {})
        if not layers:
            continue

        # 获取TLS协议类型字段
        content_types_raw = layers.get("tls.record.content_type")
        opaque_types_raw = layers.get("tls.record.opaque_type")

        content_types_list = _to_list(content_types_raw)
        opaque_types_list = _to_list(opaque_types_raw)

        # 合并协议类型字段
        type_fields = content_types_list + [v for v in opaque_types_list if v not in content_types_list]
        if not type_fields:
            continue

        # 检查目标协议类型
        target_indices = []
        target_protocol_types = []
        
        for idx, type_val in enumerate(type_fields):
            is_target, protocol_type = _is_target_content_type(type_val, target_types)
            if is_target:
                target_indices.append(idx)
                target_protocol_types.append(protocol_type)
                protocol_type_stats[protocol_type] += 1

        if not target_indices:
            continue

        # 获取其他字段
        frame_no = layers.get("frame.number")
        protocols = layers.get("frame.protocols") 
        stream_id = layers.get("tcp.stream")
        rec_lengths_raw = layers.get("tls.record.length")
        app_data_raw = layers.get("tls.app_data")

        # 标准化字段格式
        if isinstance(frame_no, list):
            frame_no = frame_no[0]
        if isinstance(protocols, list):
            protocols = protocols[0]
        if isinstance(stream_id, list):
            stream_id = stream_id[0]

        try:
            frame_no_int = int(frame_no)
            stream_int = int(stream_id) if stream_id is not None else -1
        except (TypeError, ValueError):
            continue

        # 处理记录长度和数据
        rec_lengths: List[int] = []
        zero_cnt_for_frame = 0
        app_data_iter = iter(_to_list(app_data_raw))

        for idx in target_indices:
            # 处理长度
            try:
                length_val = rec_lengths_raw[idx] if rec_lengths_raw else None
                rec_lengths.append(int(length_val) if length_val is not None else -1)
            except (IndexError, ValueError, TypeError):
                rec_lengths.append(-1)

            # 处理应用数据（主要用于TLS-23）
            if target_protocol_types[target_indices.index(idx)] == 23:
                try:
                    ad_hex = next(app_data_iter)
                    if ad_hex:
                        payload_bytes = _hex_to_bytes(str(ad_hex))
                        zero_cnt_for_frame += payload_bytes.count(0)
                except StopIteration:
                    pass

        # 构建命中记录
        hit: Dict[str, Any] = {
            "frame": frame_no_int,
            "path": str(protocols),
            "protocol_types": target_protocol_types,
            "num_records": len(target_indices),
            "lengths": rec_lengths,
            "processing_strategies": [TLS_PROCESSING_STRATEGIES[pt] for pt in target_protocol_types]
        }

        hits.append(hit)
        frame_record_counts[frame_no_int] = len(target_indices)
        frame_protocol_types[frame_no_int] = target_protocol_types
        
        if stream_int >= 0:
            hits_by_stream.setdefault(stream_int, set()).add(frame_no_int)
        if zero_cnt_for_frame > 0:
            zero_bytes_count[frame_no_int] = zero_cnt_for_frame

    if verbose:
        sys.stdout.write(f"[enhanced-tls-marker] 检测到 {len(hits)} 个TLS记录帧\n")
        for ptype, count in protocol_type_stats.items():
            type_name = TLS_CONTENT_TYPES.get(ptype, f"Unknown-{ptype}")
            sys.stdout.write(f"  TLS-{ptype} ({type_name}): {count} 记录\n")

    return {
        "hits": hits,
        "hits_by_stream": hits_by_stream,
        "frame_record_counts": frame_record_counts,
        "zero_bytes_count": zero_bytes_count,
        "protocol_type_stats": protocol_type_stats,
        "frame_protocol_types": frame_protocol_types
    }


# _hex_to_bytes function already defined above - removed duplicate

def _to_list(val: Any) -> List[str]:
    """统一转换为列表格式"""
    if val is None:
        return []
    return val if isinstance(val, list) else [val]


def _is_target_content_type(value: str, target_types: set[int] = None) -> Tuple[bool, int]:
    """判断是否为目标TLS内容类型，返回(是否匹配, 协议类型)"""
    if target_types is None:
        target_types = set(TLS_CONTENT_TYPES.keys())  # 默认检测所有类型
    
    value = value.strip()
    
    # 检查十进制格式
    try:
        decimal_val = int(value)
        if decimal_val in target_types:
            return True, decimal_val
    except ValueError:
        pass
    
    # 检查十六进制格式
    if value.startswith("0x"):
        try:
            hex_val = int(value, 16)
            if hex_val in target_types:
                return True, hex_val
        except ValueError:
            pass
    
    return False, -1


def _analyze_tls_records(packets: List[Dict], target_types: set[int] = None, verbose: bool = False) -> Dict[str, Any]:
    """分析TLS记录，返回详细的协议类型统计信息"""
    if target_types is None:
        target_types = set(TLS_CONTENT_TYPES.keys())
    
    hits: List[Dict[str, Any]] = []
    hits_by_stream: Dict[int, set[int]] = {}
    frame_record_counts: Dict[int, int] = defaultdict(int)
    zero_bytes_count: Dict[int, int] = defaultdict(int)
    protocol_type_stats: Dict[int, int] = defaultdict(int)
    frame_protocol_types: Dict[int, List[int]] = defaultdict(list)

    for pkt in packets:
        layers = pkt.get("_source", {}).get("layers", {})
        if not layers:
            continue

        # 获取TLS协议类型字段
        content_types_raw = layers.get("tls.record.content_type")
        opaque_types_raw = layers.get("tls.record.opaque_type")

        content_types_list = _to_list(content_types_raw)
        opaque_types_list = _to_list(opaque_types_raw)

        # 合并协议类型字段
        type_fields = content_types_list + [v for v in opaque_types_list if v not in content_types_list]
        if not type_fields:
            continue

        # 检查目标协议类型
        target_indices = []
        target_protocol_types = []
        
        for idx, type_val in enumerate(type_fields):
            is_target, protocol_type = _is_target_content_type(type_val, target_types)
            if is_target:
                target_indices.append(idx)
                target_protocol_types.append(protocol_type)
                protocol_type_stats[protocol_type] += 1

        if not target_indices:
            continue

        # 获取其他字段
        frame_no = layers.get("frame.number")
        protocols = layers.get("frame.protocols") 
        stream_id = layers.get("tcp.stream")
        rec_lengths_raw = layers.get("tls.record.length")
        app_data_raw = layers.get("tls.app_data")

        # 标准化字段格式
        if isinstance(frame_no, list):
            frame_no = frame_no[0]
        if isinstance(protocols, list):
            protocols = protocols[0]
        if isinstance(stream_id, list):
            stream_id = stream_id[0]

        try:
            frame_no_int = int(frame_no)
            stream_int = int(stream_id) if stream_id is not None else -1
        except (TypeError, ValueError):
            continue

        # 处理记录长度和数据
        rec_lengths: List[int] = []
        zero_cnt_for_frame = 0
        app_data_iter = iter(_to_list(app_data_raw))

        for idx in target_indices:
            # 处理长度
            try:
                length_val = rec_lengths_raw[idx] if rec_lengths_raw else None
                rec_lengths.append(int(length_val) if length_val is not None else -1)
            except (IndexError, ValueError, TypeError):
                rec_lengths.append(-1)

            # 处理应用数据（主要用于TLS-23）
            if target_protocol_types[target_indices.index(idx)] == 23:
                try:
                    ad_hex = next(app_data_iter)
                    if ad_hex:
                        payload_bytes = _hex_to_bytes(str(ad_hex))
                        zero_cnt_for_frame += payload_bytes.count(0)
                except StopIteration:
                    pass

        # 构建命中记录
        hit: Dict[str, Any] = {
            "frame": frame_no_int,
            "path": str(protocols),
            "protocol_types": target_protocol_types,
            "num_records": len(target_indices),
            "lengths": rec_lengths,
            "processing_strategies": [TLS_PROCESSING_STRATEGIES[pt] for pt in target_protocol_types]
        }

        hits.append(hit)
        frame_record_counts[frame_no_int] = len(target_indices)
        frame_protocol_types[frame_no_int] = target_protocol_types
        
        if stream_int >= 0:
            hits_by_stream.setdefault(stream_int, set()).add(frame_no_int)
        if zero_cnt_for_frame > 0:
            zero_bytes_count[frame_no_int] = zero_cnt_for_frame

    if verbose:
        sys.stdout.write(f"[enhanced-tls-marker] 检测到 {len(hits)} 个TLS记录帧\n")
        for ptype, count in protocol_type_stats.items():
            type_name = TLS_CONTENT_TYPES.get(ptype, f"Unknown-{ptype}")
            sys.stdout.write(f"  TLS-{ptype} ({type_name}): {count} 记录\n")

    return {
        "hits": hits,
        "hits_by_stream": hits_by_stream,
        "frame_record_counts": frame_record_counts,
        "zero_bytes_count": zero_bytes_count,
        "protocol_type_stats": protocol_type_stats,
        "frame_protocol_types": frame_protocol_types
    }


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="enhanced_tls_marker",
        description="增强版TLS协议类型检测工具 - 支持TLS 20-24所有类型",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument("--pcap", required=True, help="待分析的 pcap/pcapng 文件路径")
    parser.add_argument(
        "--types",
        default="20,21,22,23,24",
        help="检测的TLS协议类型，逗号分隔 (默认: 20,21,22,23,24)"
    )
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
    parser.add_argument(
        "--verbose", action="store_true", help="输出调试信息"
    )

    return parser


def main(argv: list[str] | None = None) -> None:
    """主函数"""
    argv = argv if argv is not None else sys.argv[1:]
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    # 环境检测
    tshark_exec = _check_tshark_version(args.tshark_path, args.verbose)

    # 解析目标协议类型
    try:
        target_types = set(int(t.strip()) for t in args.types.split(",") if t.strip())
        # 验证协议类型范围
        invalid_types = target_types - set(TLS_CONTENT_TYPES.keys())
        if invalid_types:
            sys.stderr.write(f"[enhanced-tls-marker] 错误: 无效的TLS协议类型: {invalid_types}\n")
            sys.exit(1)
    except ValueError as e:
        sys.stderr.write(f"[enhanced-tls-marker] 错误: 无法解析协议类型 '{args.types}': {e}\n")
        sys.exit(1)

    if args.verbose:
        target_names = [f"TLS-{t} ({TLS_CONTENT_TYPES[t]})" for t in sorted(target_types)]
        sys.stdout.write(
            f"[enhanced-tls-marker] Input file: {args.pcap}\n"
            f"[enhanced-tls-marker] Target protocol types: {', '.join(target_names)}\n"
            f"[enhanced-tls-marker] Output directory: {args.output_dir or Path(args.pcap).parent}\n"
            f"[enhanced-tls-marker] Output formats: {args.formats}\n"
            f"[enhanced-tls-marker] tshark executable: {tshark_exec}\n"
        )

    # 构造 tshark 命令
    tshark_cmd: List[str] = [
        tshark_exec,
        "-2",  # 两遍分析，启用重组
        "-r",
        str(args.pcap),
        "-T",
        "json",
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
        "tls.app_data",
        "-e",
        "tcp.stream",
        "-E",
        "occurrence=a",
        "-o",
        "tcp.desegment_tcp_streams:TRUE",
    ]

    # 处理 decode-as
    if args.decode_as:
        for spec in args.decode_as:
            tshark_cmd += ["-d", spec]

    if args.verbose:
        sys.stdout.write(f"[enhanced-tls-marker] Running command: {' '.join(tshark_cmd)}\n")

    # 执行 tshark
    try:
        # Use hidden subprocess to prevent cmd window popup on Windows
        from ..utils.subprocess_utils import run_hidden_subprocess
        completed = run_hidden_subprocess(
            tshark_cmd,
            check=True,
            text=True,
            capture_output=True,
            encoding='utf-8',
            errors='replace'
        )
    except subprocess.CalledProcessError as exc:
        sys.stderr.write(f"[enhanced-tls-marker] Error: tshark execution failed: {exc}\n")
        sys.exit(3)

    # 解析 JSON 输出
    try:
        packets = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"[enhanced-tls-marker] Error: tshark JSON parsing failed: {exc}\n")
        sys.exit(3)

    # 分析TLS记录
    analysis_result = _analyze_tls_records(packets, target_types, args.verbose)
    hits = analysis_result["hits"]
    protocol_type_stats = analysis_result["protocol_type_stats"]

    # 设置输出目录
    output_dir = args.output_dir or Path(args.pcap).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 生成输出文件名
    pcap_stem = Path(args.pcap).stem
    
    # 输出结果
    formats = [f.strip().lower() for f in args.formats.split(",")]
    
    if "json" in formats:
        json_output = {
            "metadata": {
                "input_file": str(args.pcap),
                "target_types": sorted(target_types),
                "total_frames": len(hits),
                "protocol_type_stats": protocol_type_stats,
                "tls_content_types": TLS_CONTENT_TYPES,
                "processing_strategies": TLS_PROCESSING_STRATEGIES
            },
            "matches": hits
        }
        
        json_path = output_dir / f"{pcap_stem}_enhanced_tls_frames.json"
        with json_path.open("w", encoding="utf-8") as f:
            json.dump(json_output, f, ensure_ascii=False, indent=2)
        
        if args.verbose:
            sys.stdout.write(f"[enhanced-tls-marker] JSON 输出: {json_path}\n")
    
    if "tsv" in formats:
        tsv_path = output_dir / f"{pcap_stem}_enhanced_tls_frames.tsv"
        with tsv_path.open("w", encoding="utf-8") as f:
            f.write("frame\tprotocol_types\tnum_records\tprocessing_strategies\tlengths\tpath\n")
            for hit in hits:
                protocol_types_str = ",".join(map(str, hit["protocol_types"]))
                strategies_str = ",".join(hit["processing_strategies"])
                lengths_str = ",".join(map(str, hit["lengths"]))
                f.write(f"{hit['frame']}\t{protocol_types_str}\t{hit['num_records']}\t{strategies_str}\t{lengths_str}\t{hit['path']}\n")
        
        if args.verbose:
            sys.stdout.write(f"[enhanced-tls-marker] TSV 输出: {tsv_path}\n")

    # 输出统计信息
    sys.stdout.write(f"[enhanced-tls-marker] ✅ 完成分析，检测到 {len(hits)} 个TLS记录帧\n")
    for ptype in sorted(protocol_type_stats.keys()):
        type_name = TLS_CONTENT_TYPES[ptype]
        strategy = TLS_PROCESSING_STRATEGIES[ptype]
        count = protocol_type_stats[ptype]
        sys.stdout.write(f"  TLS-{ptype} ({type_name}, {strategy}): {count} 记录\n")


if __name__ == "__main__":
    main() 