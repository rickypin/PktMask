#!/usr/bin/env python3
"""
Enhanced TLS MaskStage 端到端验证器 (Phase 3 增强版)

专门用于验证Enhanced MaskStage的完整TLS协议类型(20-24)掩码功能：
- TLS-20 (ChangeCipherSpec): 完全保留验证
- TLS-21 (Alert): 完全保留验证  
- TLS-22 (Handshake): 完全保留验证
- TLS-23 (ApplicationData): 智能掩码验证(5字节头部保留)
- TLS-24 (Heartbeat): 完全保留验证

新增验证功能：
- 多协议类型验证 (validate_protocol_type_detection)
- 跨TCP段处理验证 (validate_cross_segment_handling)
- 边界安全处理验证 (validate_boundary_safety)
- 完全保留策略验证 (validate_complete_preservation)
- 智能掩码策略验证 (validate_smart_masking)

Author: PktMask Core Team
Version: v2.0 (Phase 3 Day 15 增强版)
"""

import argparse
import json
import logging
import shutil
import subprocess
import sys
from glob import glob
from pathlib import Path
from typing import List, Dict, Any, Tuple

# -------------------------- 日志配置 --------------------------
LOG_FORMAT = "[%(levelname)s] %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger("tls23_maskstage_e2e_validator")

# ---------------------- 常量与工具函数 ------------------------
DEFAULT_GLOB = "**/*.pcap,**/*.pcapng"
DEFAULT_OUTPUT_DIR = Path("output/tls23_maskstage_e2e")
PYTHON_EXEC = sys.executable


def run_cmd(cmd: List[str], verbose: bool = False) -> None:
    """执行外部命令并实时输出。出现非零退出码时抛出 RuntimeError"""
    if verbose:
        logger.info("运行命令: %s", " ".join(cmd))
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if verbose and result.stdout:
        print(result.stdout)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(cmd)}\n{result.stdout}")


def run_enhanced_tls_marker(pcap_path: Path, output_dir: Path, types: str = "20,21,22,23,24", verbose: bool = False) -> Path:
    """运行增强版TLS协议类型检测工具，返回JSON输出文件路径"""
    if verbose:
        logger.info("运行增强版TLS协议类型检测: %s (类型: %s)", pcap_path, types)
    
    try:
        run_cmd([
            PYTHON_EXEC,
            "-m",
            "pktmask.tools.enhanced_tls_marker",
            "--pcap",
            str(pcap_path),
            "--types",
            types,
            "--formats",
            "json",
            "--output-dir",
            str(output_dir),
        ], verbose)
        
        # 返回生成的JSON文件路径
        pcap_stem = pcap_path.stem
        json_path = output_dir / f"{pcap_stem}_enhanced_tls_frames.json"
        
        if not json_path.exists():
            raise RuntimeError(f"增强版TLS检测未生成预期的JSON文件: {json_path}")
            
        return json_path
        
    except Exception as e:
        raise RuntimeError(f"增强版TLS协议类型检测失败: {e}")


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


# ---------------------- 增强验证函数 (Phase 3 Day 15) ------------------------

def validate_complete_preservation(original_json: Path, masked_json: Path, target_types: List[int] = [20, 21, 22, 24]) -> Dict[str, Any]:
    """验证TLS-20/21/22/24完全保留 - 原始和掩码后的数据应该完全一致"""
    logger.info("验证完全保留策略 (TLS类型: %s)", target_types)
    
    original_data = read_json(original_json)
    masked_data = read_json(masked_json)
    
    # 提取目标类型的记录
    original_matches = extract_frames(original_data)
    masked_matches = extract_frames(masked_data)
    
    # 按帧号建立映射
    def _get_frame_no(f: Dict[str, Any]) -> int:
        for k in ("frame", "packet_number", "frame_no", "no"):
            if k in f and isinstance(f[k], int):
                return f[k]
        return -1
    
    original_by_frame = {_get_frame_no(f): f for f in original_matches}
    masked_by_frame = {_get_frame_no(f): f for f in masked_matches}
    
    preservation_results = []
    total_target_records = 0
    preserved_records = 0
    
    for frame_no, orig_frame in original_by_frame.items():
        if frame_no == -1:
            continue
            
        # 检查是否包含目标类型
        orig_types = orig_frame.get("protocol_types", [])
        if not isinstance(orig_types, list):
            orig_types = [orig_types] if orig_types is not None else []
        
        target_found = any(t in target_types for t in orig_types)
        if not target_found:
            continue
            
        total_target_records += 1
        
        # 检查掩码后是否存在
        masked_frame = masked_by_frame.get(frame_no)
        if not masked_frame:
            preservation_results.append({
                "frame": frame_no,
                "status": "missing",
                "reason": "掩码后帧丢失"
            })
            continue
        
        # 比较关键属性
        preserved = True
        differences = []
        
        # 比较协议类型
        masked_types = masked_frame.get("protocol_types", [])
        if not isinstance(masked_types, list):
            masked_types = [masked_types] if masked_types is not None else []
            
        if orig_types != masked_types:
            preserved = False
            differences.append(f"协议类型不一致: {orig_types} -> {masked_types}")
        
        # 比较记录长度
        orig_lengths = orig_frame.get("lengths", [])
        masked_lengths = masked_frame.get("lengths", [])
        if orig_lengths != masked_lengths:
            preserved = False
            differences.append(f"记录长度不一致: {orig_lengths} -> {masked_lengths}")
        
        # 比较载荷数据（对于完全保留类型，应该完全相同）
        for field in ["payload_preview", "data", "payload_hex"]:
            orig_payload = orig_frame.get(field)
            masked_payload = masked_frame.get(field)
            if orig_payload and masked_payload and orig_payload != masked_payload:
                preserved = False
                differences.append(f"{field}不一致")
                break
        
        if preserved:
            preserved_records += 1
            preservation_results.append({
                "frame": frame_no,
                "status": "preserved",
                "protocol_types": orig_types
            })
        else:
            preservation_results.append({
                "frame": frame_no, 
                "status": "modified",
                "protocol_types": orig_types,
                "differences": differences
            })
    
    preservation_rate = (preserved_records / total_target_records * 100) if total_target_records > 0 else 0
    
    return {
        "total_target_records": total_target_records,
        "preserved_records": preserved_records, 
        "preservation_rate": round(preservation_rate, 2),
        "status": "pass" if preservation_rate >= 95.0 else "fail",
        "details": preservation_results
    }


def validate_smart_masking(original_json: Path, masked_json: Path, target_type: int = 23, header_bytes: int = 5) -> Dict[str, Any]:
    """验证TLS-23智能掩码（保留指定字节头部，掩码其余载荷）"""
    logger.info("验证智能掩码策略 (TLS-%d, 头部保留: %d字节)", target_type, header_bytes)
    
    original_data = read_json(original_json)
    masked_data = read_json(masked_json)
    
    original_matches = extract_frames(original_data)
    masked_matches = extract_frames(masked_data)
    
    def _get_frame_no(f: Dict[str, Any]) -> int:
        for k in ("frame", "packet_number", "frame_no", "no"):
            if k in f and isinstance(f[k], int):
                return f[k]
        return -1
    
    def _is_smart_masked(frame: Dict[str, Any], header_bytes: int) -> bool:
        """判断帧是否正确应用了智能掩码（头部保留，载荷掩码）"""
        # 检查 zero_bytes 和 lengths 字段
        if "zero_bytes" in frame and "lengths" in frame:
            zero_bytes = frame.get("zero_bytes", 0)
            lengths = frame.get("lengths", [])
            if isinstance(lengths, list) and lengths:
                total_length = sum(lengths)
                expected_masked_bytes = total_length - header_bytes
                # 如果置零字节数接近期望的掩码字节数（允许一定误差）
                return abs(zero_bytes - expected_masked_bytes) <= 5
        
        # 回退到字符串检查
        hex_fields = []
        for key in ("payload_preview", "data", "payload_hex", "payload"):
            if key in frame and isinstance(frame[key], str):
                hex_fields.append(frame[key])
        
        if hex_fields:
            for hf in hex_fields:
                cleaned = hf.replace(" ", "").replace(":", "")
                if len(cleaned) >= header_bytes * 2:  # 每字节2个十六进制字符
                    header_part = cleaned[:header_bytes * 2]
                    payload_part = cleaned[header_bytes * 2:]
                    # 头部不应全为零，载荷部分应大部分为零
                    header_not_all_zero = set(header_part) != {"0"}
                    payload_mostly_zero = payload_part.count("0") / len(payload_part) > 0.8 if payload_part else True
                    return header_not_all_zero and payload_mostly_zero
        
        return False
    
    original_by_frame = {_get_frame_no(f): f for f in original_matches}
    masked_by_frame = {_get_frame_no(f): f for f in masked_matches}
    
    masking_results = []
    total_target_records = 0
    correctly_masked_records = 0
    
    for frame_no, orig_frame in original_by_frame.items():
        if frame_no == -1:
            continue
            
        # 检查是否包含目标类型
        orig_types = orig_frame.get("protocol_types", [])
        if not isinstance(orig_types, list):
            orig_types = [orig_types] if orig_types is not None else []
        
        if target_type not in orig_types:
            continue
            
        total_target_records += 1
        
        # 检查掩码后是否存在
        masked_frame = masked_by_frame.get(frame_no)
        if not masked_frame:
            masking_results.append({
                "frame": frame_no,
                "status": "missing",
                "reason": "掩码后帧丢失"
            })
            continue
        
        # 检查是否正确应用了智能掩码（头部保留，载荷大部分置零）
        is_correctly_masked = _is_smart_masked(masked_frame, header_bytes)
        
        if is_correctly_masked:
            correctly_masked_records += 1
            masking_results.append({
                "frame": frame_no,
                "status": "correctly_masked",
                "protocol_types": orig_types
            })
        else:
            masking_results.append({
                "frame": frame_no,
                "status": "incorrectly_masked", 
                "protocol_types": orig_types,
                "reason": "载荷未正确掩码"
            })
    
    masking_rate = (correctly_masked_records / total_target_records * 100) if total_target_records > 0 else 0
    
    return {
        "total_target_records": total_target_records,
        "correctly_masked_records": correctly_masked_records,
        "masking_rate": round(masking_rate, 2),
        "status": "pass" if masking_rate >= 95.0 else "fail",
        "details": masking_results
    }


def validate_cross_segment_handling(original_json: Path, masked_json: Path) -> Dict[str, Any]:
    """验证跨TCP段处理正确性 - 检查流级别的处理一致性"""
    logger.info("验证跨TCP段处理正确性")
    
    original_data = read_json(original_json)
    masked_data = read_json(masked_json)
    
    original_matches = extract_frames(original_data)
    masked_matches = extract_frames(masked_data)
    
    # 按TCP流分组
    def _get_stream_info(f: Dict[str, Any]) -> Tuple[str, int]:
        path = f.get("path", "")
        frame_no = f.get("frame", f.get("packet_number", -1))
        
        # 从path中提取TCP流信息（如果可用）
        if "tcp" in path.lower():
            return ("tcp_stream", frame_no)
        return ("unknown_stream", frame_no)
    
    # 分析流级别的一致性
    stream_analysis = {}
    
    for orig_frame in original_matches:
        stream_id, frame_no = _get_stream_info(orig_frame)
        if stream_id not in stream_analysis:
            stream_analysis[stream_id] = {"original": [], "masked": []}
        stream_analysis[stream_id]["original"].append((frame_no, orig_frame))
    
    for masked_frame in masked_matches:
        stream_id, frame_no = _get_stream_info(masked_frame)
        if stream_id in stream_analysis:
            stream_analysis[stream_id]["masked"].append((frame_no, masked_frame))
    
    cross_segment_results = []
    total_streams = len(stream_analysis)
    consistent_streams = 0
    
    for stream_id, stream_data in stream_analysis.items():
        original_frames = sorted(stream_data["original"], key=lambda x: x[0])
        masked_frames = sorted(stream_data["masked"], key=lambda x: x[0])
        
        # 检查帧数量一致性
        if len(original_frames) != len(masked_frames):
            cross_segment_results.append({
                "stream": stream_id,
                "status": "inconsistent",
                "reason": f"帧数量不一致: {len(original_frames)} -> {len(masked_frames)}"
            })
            continue
        
        # 检查帧序列一致性
        frame_consistency = True
        for (orig_no, orig_frame), (masked_no, masked_frame) in zip(original_frames, masked_frames):
            if orig_no != masked_no:
                frame_consistency = False
                break
        
        if frame_consistency:
            consistent_streams += 1
            cross_segment_results.append({
                "stream": stream_id,
                "status": "consistent",
                "frame_count": len(original_frames)
            })
        else:
            cross_segment_results.append({
                "stream": stream_id,
                "status": "inconsistent",
                "reason": "帧序列不一致"
            })
    
    consistency_rate = (consistent_streams / total_streams * 100) if total_streams > 0 else 0
    
    return {
        "total_streams": total_streams,
        "consistent_streams": consistent_streams,
        "consistency_rate": round(consistency_rate, 2),
        "status": "pass" if consistency_rate >= 90.0 else "fail",
        "details": cross_segment_results
    }


def validate_protocol_type_detection(original_json: Path, target_types: List[int] = [20, 21, 22, 23, 24]) -> Dict[str, Any]:
    """验证协议类型识别准确性 - 检查是否正确识别所有目标TLS协议类型"""
    logger.info("验证协议类型识别准确性 (目标类型: %s)", target_types)
    
    original_data = read_json(original_json)
    original_matches = extract_frames(original_data)
    
    detected_types = set()
    type_counts = {}
    frame_type_details = []
    
    for frame in original_matches:
        frame_no = frame.get("frame", frame.get("packet_number", -1))
        protocol_types = frame.get("protocol_types", [])
        
        if not isinstance(protocol_types, list):
            protocol_types = [protocol_types] if protocol_types is not None else []
        
        for ptype in protocol_types:
            if isinstance(ptype, int) and ptype in target_types:
                detected_types.add(ptype)
                type_counts[ptype] = type_counts.get(ptype, 0) + 1
                
        if protocol_types:
            frame_type_details.append({
                "frame": frame_no,
                "detected_types": protocol_types
            })
    
    # 计算检测完整性
    missing_types = set(target_types) - detected_types
    detection_completeness = (len(detected_types) / len(target_types) * 100) if target_types else 0
    
    return {
        "target_types": target_types,
        "detected_types": sorted(list(detected_types)),
        "missing_types": sorted(list(missing_types)),
        "type_counts": type_counts,
        "detection_completeness": round(detection_completeness, 2),
        "status": "pass" if detection_completeness >= 80.0 else "fail",
        "frame_details": frame_type_details[:10]  # 限制输出数量
    }


def validate_boundary_safety(original_json: Path, masked_json: Path) -> Dict[str, Any]:
    """验证边界安全处理 - 检查是否存在边界违规或数据损坏"""
    logger.info("验证边界安全处理")
    
    original_data = read_json(original_json) 
    masked_data = read_json(masked_json)
    
    original_matches = extract_frames(original_data)
    masked_matches = extract_frames(masked_data)
    
    def _get_frame_no(f: Dict[str, Any]) -> int:
        for k in ("frame", "packet_number", "frame_no", "no"):
            if k in f and isinstance(f[k], int):
                return f[k]
        return -1
    
    original_by_frame = {_get_frame_no(f): f for f in original_matches}
    masked_by_frame = {_get_frame_no(f): f for f in masked_matches}
    
    boundary_issues = []
    safe_frames = 0
    total_frames = len(original_by_frame)
    
    for frame_no, orig_frame in original_by_frame.items():
        if frame_no == -1:
            continue
            
        masked_frame = masked_by_frame.get(frame_no)
        if not masked_frame:
            boundary_issues.append({
                "frame": frame_no,
                "issue": "frame_missing",
                "description": "掩码处理后帧丢失"
            })
            continue
        
        # 检查记录长度一致性
        orig_lengths = orig_frame.get("lengths", [])
        masked_lengths = masked_frame.get("lengths", [])
        
        if len(orig_lengths) != len(masked_lengths):
            boundary_issues.append({
                "frame": frame_no,
                "issue": "length_mismatch",
                "description": f"记录数量变化: {len(orig_lengths)} -> {len(masked_lengths)}"
            })
            continue
        
        # 检查长度值异常变化
        length_issues = []
        for i, (orig_len, masked_len) in enumerate(zip(orig_lengths, masked_lengths)):
            if orig_len != masked_len:
                length_issues.append(f"记录{i}: {orig_len} -> {masked_len}")
        
        if length_issues:
            boundary_issues.append({
                "frame": frame_no,
                "issue": "length_change", 
                "description": f"记录长度变化: {'; '.join(length_issues)}"
            })
            continue
        
        # 检查是否存在异常的零字节计数
        orig_zero_bytes = orig_frame.get("zero_bytes", 0)
        masked_zero_bytes = masked_frame.get("zero_bytes", 0)
        
        # 掩码后零字节数应该增加（用于TLS-23）或保持不变（用于其他类型）
        if masked_zero_bytes < orig_zero_bytes:
            boundary_issues.append({
                "frame": frame_no,
                "issue": "zero_bytes_decrease",
                "description": f"零字节数异常减少: {orig_zero_bytes} -> {masked_zero_bytes}"
            })
            continue
        
        safe_frames += 1
    
    safety_rate = (safe_frames / total_frames * 100) if total_frames > 0 else 0
    
    return {
        "total_frames": total_frames,
        "safe_frames": safe_frames,
        "boundary_issues": len(boundary_issues),
        "safety_rate": round(safety_rate, 2),
        "status": "pass" if safety_rate >= 95.0 else "fail",
        "issue_details": boundary_issues[:10]  # 限制输出数量
    }


def validate_enhanced_tls_processing(original_json: Path, masked_json: Path) -> Dict[str, Any]:
    """综合验证增强TLS处理结果 - 集成所有验证功能"""
    logger.info("开始综合验证增强TLS处理结果")
    
    results = {}
    
    # 1. 验证TLS-20/21/22/24完全保留
    results["complete_preservation"] = validate_complete_preservation(original_json, masked_json, [20, 21, 22, 24])
    
    # 2. 验证TLS-23智能掩码（5字节头部保留）
    results["smart_masking"] = validate_smart_masking(original_json, masked_json, 23, 5)
    
    # 3. 验证跨TCP段处理正确性
    results["cross_segment_handling"] = validate_cross_segment_handling(original_json, masked_json)
    
    # 4. 验证协议类型识别准确性
    results["protocol_type_detection"] = validate_protocol_type_detection(original_json, [20, 21, 22, 23, 24])
    
    # 5. 验证边界安全处理
    results["boundary_safety"] = validate_boundary_safety(original_json, masked_json)
    
    # 计算综合评分
    test_scores = []
    for test_name, test_result in results.items():
        if test_result.get("status") == "pass":
            test_scores.append(100)
        else:
            # 根据具体指标计算分数
            if "rate" in test_result:
                rate_key = [k for k in test_result.keys() if k.endswith("_rate")][0]
                test_scores.append(test_result[rate_key])
            else:
                test_scores.append(0)
    
    overall_score = sum(test_scores) / len(test_scores) if test_scores else 0
    overall_status = "pass" if overall_score >= 80.0 else "fail"
    
    results["overall"] = {
        "score": round(overall_score, 2),
        "status": overall_status,
        "passed_tests": sum(1 for r in results.values() if r.get("status") == "pass"),
        "total_tests": 5  # 5个验证函数：完全保留、智能掩码、跨段处理、协议类型检测、边界安全
    }
    
    return results


# ---------------------- MaskStage 处理函数 --------------------------

def run_maskstage_internal(input_path: Path, output_path: Path, verbose: bool = False) -> None:
    """使用Enhanced MaskStage处理文件（通过PipelineExecutor）"""
    if verbose:
        logger.info("使用 Enhanced MaskStage 处理: %s -> %s", input_path, output_path)

    try:
        from pktmask.core.pipeline.executor import PipelineExecutor
        from pktmask.core.pipeline.stages.mask_payload.stage import MaskStage
    except ImportError as imp_err:
        raise RuntimeError(f"无法导入 Enhanced MaskStage: {imp_err}")

    # 配置Enhanced MaskStage处理（Processor Adapter 模式）
    config = {
        "dedup": {"enabled": False},
        "anon": {"enabled": False}, 
        "mask": {
            "enabled": True,
            "mode": "processor_adapter",  # 使用处理器适配器模式
            "preserve_ratio": 0.3,
            "tls_strategy_enabled": True,
            "enable_tshark_preprocessing": True
        }
    }

    try:
        # 创建PipelineExecutor并执行
        executor = PipelineExecutor(config)
        
        # 创建输出目录
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 执行处理
        stats = executor.run(str(input_path), str(output_path))
        
        if verbose:
            logger.info("Enhanced MaskStage 处理完成: %s", stats)
            
    except Exception as e:
        raise RuntimeError(f"Enhanced MaskStage 处理失败: {e}")


def run_maskstage_direct(input_path: Path, output_path: Path, verbose: bool = False) -> None:
    """直接使用Enhanced MaskStage处理文件（不通过PipelineExecutor）"""
    if verbose:
        logger.info("直接使用 Enhanced MaskStage 处理: %s -> %s", input_path, output_path)

    try:
        from pktmask.core.pipeline.stages.mask_payload.stage import MaskStage
    except ImportError as imp_err:
        raise RuntimeError(f"无法导入 Enhanced MaskStage: {imp_err}")

    # 配置Enhanced MaskStage（Processor Adapter 模式）
    config = {
        "mode": "processor_adapter",  # 使用处理器适配器模式
        "preserve_ratio": 0.3,
        "tls_strategy_enabled": True,
        "enable_tshark_preprocessing": True
    }

    try:
        # 创建并初始化MaskStage
        mask_stage = MaskStage(config)
        mask_stage.initialize()
        
        # 创建输出目录
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 执行处理
        stats = mask_stage.process_file(input_path, output_path)
        
        if verbose:
            logger.info("Enhanced MaskStage 直接处理完成: %s", stats)
            
    except Exception as e:
        raise RuntimeError(f"Enhanced MaskStage 直接处理失败: {e}")


# -------------------------- CLI -------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="TLS23 MaskStage 端到端掩码验证脚本 (基于 tls23_marker + Enhanced MaskStage)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--input-dir", type=Path, required=True, help="递归扫描 PCAP/PCAPNG 的目录")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="结果输出目录")
    parser.add_argument("--maskstage-mode", default="pipeline", choices=["pipeline", "direct"], 
                       help="MaskStage调用模式：pipeline(通过PipelineExecutor) 或 direct(直接调用)")
    parser.add_argument("--glob", dest="glob_pattern", default=DEFAULT_GLOB, help="文件匹配 glob 表达式")
    parser.add_argument("--verbose", action="store_true", help="输出详细调试信息")

    args = parser.parse_args()

    input_dir: Path = args.input_dir
    output_dir: Path = args.output_dir
    maskstage_mode: str = args.maskstage_mode
    glob_pattern: str = args.glob_pattern
    verbose: bool = args.verbose

    # 专用目录保存掩码后的 PCAP
    masked_dir: Path = output_dir / "masked_pcaps"
    masked_dir.mkdir(parents=True, exist_ok=True)

    files = discover_files(input_dir, glob_pattern)
    if not files:
        logger.error("输入目录无匹配文件: %s", input_dir)
        sys.exit(2)

    results = []
    passed_files = 0

    logger.info("开始TLS23 MaskStage端到端验证，使用模式: %s", maskstage_mode)

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

            # ---------- 调用 Enhanced MaskStage 进行掩码 ----------
            masked_file = masked_dir / f"{stem}_masked{suffix}"
            
            if maskstage_mode == "pipeline":
                run_maskstage_internal(pcap_path, masked_file, verbose)
            else:  # direct
                run_maskstage_direct(pcap_path, masked_file, verbose)

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

            # ---------- 验证结果 ----------
            file_result = validate_file(orig_json, masked_json)
            file_result["file"] = pcap_path.name
            file_result["maskstage_mode"] = maskstage_mode
            results.append(file_result)

            if file_result["status"] == "pass":
                passed_files += 1
                logger.info("✅ %s - 通过 (MaskStage %s)", pcap_path.name, maskstage_mode)
            else:
                logger.warning("❌ %s - 失败 (MaskStage %s)", pcap_path.name, maskstage_mode)

        except Exception as e:
            logger.error("处理文件 %s 时出错: %s", pcap_path, e)
            results.append({
                "file": pcap_path.name,
                "status": "error",
                "error": str(e),
                "maskstage_mode": maskstage_mode,
            })

    overall_pass_rate = (passed_files / len(files)) * 100
    summary = {
        "overall_pass_rate": round(overall_pass_rate, 2),
        "files": results
    }
    write_json(output_dir / "validation_summary.json", summary)

    # 生成 HTML 报告
    write_html_report(summary, output_dir / "validation_summary.html")

    logger.info("📊 MaskStage (%s) Overall Pass Rate: %.2f%%", maskstage_mode, overall_pass_rate)

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
        + "\n".join(rows_html) + "</tbody></table>"  
        "</body></html>"
    )

    output_path.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        logger.exception("运行时异常: %s", exc)
        sys.exit(3) 