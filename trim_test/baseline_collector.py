import json
import logging
import pathlib
import shutil
import subprocess
from typing import List, Optional, Tuple, Dict, Any

# --- 配置 ---
# 设置日志
logging.basicConfig(level=logging.INFO, format='[%(asctime)s - %(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

# 定义路径
SCRIPT_DIR = pathlib.Path(__file__).parent
WORKSPACE_ROOT = SCRIPT_DIR.parent
OUTPUT_DIR = SCRIPT_DIR / "output"
SAMPLES_DIR = WORKSPACE_ROOT / "tests" / "data" / "tls"
BASELINE_STATS_FILE = OUTPUT_DIR / "baseline_stats.json"

TSHARK_COMMAND = 'tshark'

def find_tshark() -> Optional[str]:
    """智能查找 TShark 可执行文件。"""
    # 尝试使用 shutil.which 从 PATH 查找
    tshark_path = shutil.which(TSHARK_COMMAND)
    if tshark_path:
        logging.info(f"在 PATH 中找到 TShark: {tshark_path}")
        return tshark_path

    # 检查常见硬编码路径
    common_paths = [
        '/Applications/Wireshark.app/Contents/MacOS/tshark',
        '/usr/bin/tshark',
        '/usr/local/bin/tshark',
    ]
    for path in common_paths:
        if pathlib.Path(path).exists():
            logging.info(f"在常见路径中找到 TShark: {path}")
            return path

    logging.error("无法找到 TShark 可执行文件。请确保 Wireshark 已安装，或在此脚本中指定路径。")
    return None

def get_baseline_stats(filepath: pathlib.Path, tshark_path: str) -> Dict[str, Any]:
    """
    使用 TShark 分析 PCAP 文件，根据原始验证方案统计基线数据。
    """
    stats = {
        "app_records": 0,
        "app_packets": 0,
        "frame_numbers": [],
        "error": None
    }
    
    cmd = [
        tshark_path,
        "-r", str(filepath),
        "-Y", "tls.record.content_type == 23",
        "-T", "fields",
        "-e", "frame.number"
    ]

    try:
        process = subprocess.run(
            cmd, capture_output=True, text=True, check=True, timeout=60
        )
        stdout = process.stdout.strip()
        
        if not stdout:
            return stats

        frame_numbers = [int(n) for n in stdout.splitlines() if n.strip().isdigit()]
        
        stats["app_records"] = len(frame_numbers)
        stats["app_packets"] = len(set(frame_numbers))
        stats["frame_numbers"] = sorted(list(set(frame_numbers)))

    except FileNotFoundError:
        msg = f"TShark 命令 '{tshark_path}' 未找到。"
        logging.error(msg)
        stats["error"] = msg
    except subprocess.CalledProcessError as e:
        # TShark 在找不到匹配项时返回非零退出码，这不是一个真正的错误
        if e.returncode == 2 and not e.stdout and not e.stderr:
             logging.info(f"在 {filepath.name} 中未找到 TLS Application Data 记录。")
        else:
            msg = f"执行 TShark 命令失败。返回码: {e.returncode}, 错误: {e.stderr}"
            logging.error(msg)
            stats["error"] = msg
    except Exception as e:
        msg = f"处理 {filepath.name} 时发生未知错误: {e}"
        logging.error(msg)
        stats["error"] = msg

    return stats

def main():
    """主执行函数。"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    tshark_path = find_tshark()
    if not tshark_path:
        return

    logging.info(f"开始基线数据统计...")
    
    sample_files = sorted(list(SAMPLES_DIR.glob("*.pcap")) + list(SAMPLES_DIR.glob("*.pcapng")))

    if not sample_files:
        logging.error(f"在 {SAMPLES_DIR} 中未找到样本文件。")
        return

    logging.info(f"找到 {len(sample_files)} 个样本文件进行处理。")

    all_stats: Dict[str, Any] = {}
    for filepath in sample_files:
        logging.info(f"--- 正在处理: {filepath.name} ---")
        stats = get_baseline_stats(filepath, tshark_path)
        all_stats[filepath.name] = stats
        
        if stats["error"]:
            logging.warning(f"处理 {filepath.name} 时遇到错误，结果可能不完整。")
        else:
            logging.info(f"统计完成: {stats['app_records']} 条记录, {stats['app_packets']} 个包。")

    logging.info(f"正在将基线数据写入 {BASELINE_STATS_FILE}")
    with open(BASELINE_STATS_FILE, "w") as f:
        json.dump(all_stats, f, indent=4)

    logging.info("基线数据统计成功完成。")

if __name__ == "__main__":
    main()
