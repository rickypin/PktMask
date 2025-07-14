#!/usr/bin/env python3
"""
GUI配置格式反向测试工具

基于tls23_maskstage_e2e_validator.py，但修改配置格式与GUI完全一致，
用于验证配置格式差异是否是导致TLS-23掩码失效的根本原因。

主要修改：
1. 使用GUI的marker_config.preserve配置格式
2. 保持其他逻辑完全不变
3. 对比测试结果差异

使用方法：
    python scripts/debug/gui_config_reverse_test.py --input-dir tests/data/tls --output-dir output/gui_config_test
"""

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Dict, Any

# Add src directory to Python path for module imports
script_dir = Path(__file__).parent.absolute()
project_root = script_dir.parent.parent  # Go up two levels to project root
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# 日志配置
LOG_FORMAT = "[%(levelname)s] %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger("gui_config_reverse_test")

# 常量
DEFAULT_OUTPUT_DIR = Path("output/gui_config_test")
PYTHON_EXEC = sys.executable


def run_cmd(cmd: List[str], verbose: bool = False) -> None:
    """执行外部命令并实时输出。出现非零退出码时抛出 RuntimeError"""
    if verbose:
        logger.info("运行命令: %s", " ".join(cmd))
    
    # Set up environment with PYTHONPATH
    env = os.environ.copy()
    env['PYTHONPATH'] = str(src_path)
    
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
    if verbose and result.stdout:
        print(result.stdout)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(cmd)}\n{result.stdout}")


def discover_pcap_files(input_dir: Path) -> List[Path]:
    """发现PCAP文件"""
    pcap_files = []
    for ext in ['*.pcap', '*.pcapng']:
        pcap_files.extend(input_dir.glob(f"**/{ext}"))
    return [f for f in pcap_files if f.is_file()]


def read_json(path: Path) -> Any:
    """读取JSON文件"""
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    """写入JSON文件"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def extract_frames(data: Any) -> List[Dict[str, Any]]:
    """提取帧列表"""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("frames", "records", "packets", "matches"):
            if key in data and isinstance(data[key], list):
                return data[key]
    return []


def is_zero_payload(frame: Dict[str, Any]) -> bool:
    """判断frame是否已全部置零"""
    # 新版 numeric 判断
    if "zero_bytes" in frame:
        zb = frame.get("zero_bytes", 0)
        if "lengths" in frame and isinstance(frame["lengths"], list) and frame["lengths"]:
            total_len = sum(frame["lengths"])
            return zb >= total_len
        return zb > 0

    # 旧版字符串判断
    hex_fields = []
    for key in ("payload_preview", "data", "payload_hex", "payload"):
        if key in frame and isinstance(frame[key], str):
            hex_fields.append(frame[key])
    if not hex_fields:
        return True
    for hf in hex_fields:
        cleaned = hf.replace(" ", "").replace(":", "")
        if cleaned and set(cleaned) != {"0"}:
            return False
    return True


def validate_file(original_json: Path, masked_json: Path) -> Dict[str, Any]:
    """比较原始与掩码后的结果"""
    original_frames = extract_frames(read_json(original_json))
    masked_frames = extract_frames(read_json(masked_json))

    def _get_frame_no(f: Dict[str, Any]) -> int:
        for k in ("packet_number", "frame", "frame_no", "no"):
            if k in f and isinstance(f[k], int):
                return f[k]
        return -1

    masked_by_no = {_get_frame_no(f): f for f in masked_frames}

    failed_frames: List[int] = []
    masked_ok_frames: List[int] = []
    masked_zero_count = 0

    for no, m_frame in masked_by_no.items():
        if no == -1:
            continue
        if is_zero_payload(m_frame):
            masked_ok_frames.append(no)
            masked_zero_count += 1
        else:
            failed_frames.append(no)

    input_tls23_count = len(original_frames)
    output_tls23_count = len(masked_frames)
    masked_records = len(masked_ok_frames)
    unmasked_records = len(failed_frames)

    status = "pass" if unmasked_records == 0 else "fail"

    return {
        "status": status,
        "records_before": len(original_frames),
        "records_after": len(masked_frames),
        "input_tls23_pkts": input_tls23_count,
        "masked_zero_pkts": masked_zero_count,
        "output_tls23_pkts": output_tls23_count,
        "masked_records": masked_records,
        "unmasked_records": unmasked_records,
        "masked_ok_frames": sorted(masked_ok_frames),
        "failed_frames": sorted(failed_frames),
    }


def run_maskstage_with_gui_config(input_path: Path, output_path: Path, mode: str = "pipeline", verbose: bool = False) -> None:
    """使用GUI配置格式运行MaskStage"""
    if verbose:
        logger.info("使用GUI配置格式处理: %s -> %s (模式: %s)", input_path, output_path, mode)

    try:
        if mode == "pipeline":
            from pktmask.core.pipeline.executor import PipelineExecutor
            
            # 🔑 关键修改：使用与GUI完全一致的配置格式
            config = {
                "dedup": {"enabled": False},
                "anon": {"enabled": False},
                "mask": {
                    "enabled": True,
                    "protocol": "tls",
                    "mode": "enhanced",
                    "marker_config": {
                        "preserve": {                    # ✅ 使用GUI的preserve格式
                            "handshake": True,
                            "application_data": False,   # ✅ TLS-23应该被掩码
                            "alert": True,
                            "change_cipher_spec": True,
                            "heartbeat": True
                        }
                    },
                    "masker_config": {
                        "preserve_ratio": 0.3
                    }
                }
            }
            
            executor = PipelineExecutor(config)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            stats = executor.run(str(input_path), str(output_path))
            
            if verbose:
                logger.info("GUI配置格式处理完成: %s", stats)
                
        else:  # direct mode
            from pktmask.core.pipeline.stages.mask_payload_v2.stage import NewMaskPayloadStage
            
            # 🔑 关键修改：直接模式也使用GUI配置格式
            config = {
                "protocol": "tls",
                "mode": "enhanced",
                "marker_config": {
                    "preserve": {                    # ✅ 使用GUI的preserve格式
                        "handshake": True,
                        "application_data": False,   # ✅ TLS-23应该被掩码
                        "alert": True,
                        "change_cipher_spec": True,
                        "heartbeat": True
                    }
                },
                "masker_config": {
                    "preserve_ratio": 0.3
                }
            }
            
            mask_stage = NewMaskPayloadStage(config)
            mask_stage.initialize()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            stats = mask_stage.process_file(str(input_path), str(output_path))
            
            if verbose:
                logger.info("GUI配置格式直接处理完成: %s", stats)
                
    except Exception as e:
        raise RuntimeError(f"GUI配置格式处理失败: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="GUI配置格式反向测试工具 - 验证配置格式对TLS-23掩码的影响",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--input-dir", type=Path, required=True, help="输入PCAP文件目录")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="输出目录")
    parser.add_argument("--mode", default="pipeline", choices=["pipeline", "direct"], 
                       help="MaskStage调用模式")
    parser.add_argument("--verbose", action="store_true", help="详细输出")

    args = parser.parse_args()

    input_dir: Path = args.input_dir
    output_dir: Path = args.output_dir
    mode: str = args.mode
    verbose: bool = args.verbose

    # 创建输出目录
    masked_dir: Path = output_dir / "masked_pcaps"
    masked_dir.mkdir(parents=True, exist_ok=True)

    # 发现PCAP文件
    files = discover_pcap_files(input_dir)
    if not files:
        logger.error("输入目录无匹配文件: %s", input_dir)
        sys.exit(2)

    results = []
    passed_files = 0

    logger.info("🔄 开始GUI配置格式反向测试，模式: %s", mode)
    logger.info("📁 发现 %d 个PCAP文件", len(files))

    for pcap_path in files:
        stem = pcap_path.stem
        suffix = pcap_path.suffix
        orig_json = output_dir / f"{stem}_orig_tls23.json"
        masked_json = output_dir / f"{stem}_masked_tls23.json"

        try:
            logger.info("🔍 处理文件: %s", pcap_path.name)
            
            # 第一次扫描：原始文件
            run_cmd([
                PYTHON_EXEC, "-m", "pktmask.tools.tls23_marker",
                "--pcap", str(pcap_path),
                "--no-annotate", "--formats", "json",
                "--output-dir", str(output_dir),
            ], verbose)
            
            tmp_json = output_dir / f"{stem}_tls23_frames.json"
            if tmp_json.exists():
                shutil.move(tmp_json, orig_json)

            # 使用GUI配置格式进行掩码处理
            masked_file = masked_dir / f"{stem}_masked{suffix}"
            run_maskstage_with_gui_config(pcap_path, masked_file, mode, verbose)

            # 第二次扫描：掩码后文件
            run_cmd([
                PYTHON_EXEC, "-m", "pktmask.tools.tls23_marker",
                "--pcap", str(masked_file),
                "--no-annotate", "--formats", "json",
                "--output-dir", str(output_dir),
            ], verbose)
            
            tmp_json_masked = output_dir / f"{stem}_masked_tls23_frames.json"
            if not tmp_json_masked.exists():
                generic_tmp = output_dir / f"{stem}_tls23_frames.json"
                if generic_tmp.exists():
                    tmp_json_masked = generic_tmp
            if tmp_json_masked.exists():
                shutil.move(tmp_json_masked, masked_json)

            # 验证结果
            file_result = validate_file(orig_json, masked_json)
            file_result["file"] = pcap_path.name
            file_result["config_format"] = "gui_preserve_format"
            file_result["mode"] = mode
            results.append(file_result)

            if file_result["status"] == "pass":
                passed_files += 1
                logger.info("✅ %s - 通过 (GUI配置格式)", pcap_path.name)
            else:
                logger.warning("❌ %s - 失败 (GUI配置格式)", pcap_path.name)
                logger.warning("   未掩码记录: %d, 已掩码记录: %d", 
                             file_result["unmasked_records"], file_result["masked_records"])

        except Exception as e:
            logger.error("处理文件 %s 时出错: %s", pcap_path, e)
            results.append({
                "file": pcap_path.name,
                "status": "error",
                "error": str(e),
                "config_format": "gui_preserve_format",
                "mode": mode,
            })

    # 生成结果摘要
    overall_pass_rate = (passed_files / len(files)) * 100
    summary = {
        "test_type": "gui_config_reverse_test",
        "config_format": "gui_preserve_format",
        "overall_pass_rate": round(overall_pass_rate, 2),
        "mode": mode,
        "total_files": len(files),
        "passed_files": passed_files,
        "failed_files": len(files) - passed_files,
        "files": results
    }
    
    # 保存结果
    summary_file = output_dir / "gui_config_reverse_test_summary.json"
    write_json(summary_file, summary)

    # 输出结果
    logger.info("📊 GUI配置格式反向测试完成")
    logger.info("📈 总体通过率: %.2f%% (%d/%d)", overall_pass_rate, passed_files, len(files))
    logger.info("📄 详细结果: %s", summary_file)
    
    # 对比分析
    if overall_pass_rate > 0:
        logger.info("🎯 GUI配置格式测试结果显示有效掩码！")
        logger.info("💡 这表明配置格式差异可能是导致TLS-23掩码失效的关键因素")
    else:
        logger.info("⚠️ GUI配置格式测试仍然失败")
        logger.info("💡 问题可能不在配置格式，需要进一步调查")

    # 退出码
    sys.exit(0 if passed_files == len(files) else 1)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        logger.exception("运行时异常: %s", exc)
        sys.exit(3)
