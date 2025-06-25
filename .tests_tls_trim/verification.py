import json
import logging
import pathlib
import subprocess
import shutil
from typing import Dict, Any, List, Tuple, Optional

from scapy.all import rdpcap, TCP

# --- 配置 ---
# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 定义路径
# 使用相对路径，以脚本所在位置为基准
SCRIPT_DIR = pathlib.Path(__file__).parent
WORKSPACE_ROOT = SCRIPT_DIR.parent
OUTPUT_DIR = WORKSPACE_ROOT / ".tests_tls_trim" / "output"
BASELINE_STATS_FILE = OUTPUT_DIR / "baseline_stats.json"
TRIM_RESULTS_FILE = OUTPUT_DIR / "trim_results.json"
VERIFICATION_JSON_FILE = OUTPUT_DIR / "verification.json"
VERIFICATION_MD_FILE = OUTPUT_DIR / "verification_report.md"

TSHARK_COMMAND = 'tshark'


def read_json_file(file_path: pathlib.Path) -> Optional[Dict[str, Any]]:
    """读取并解析 JSON 文件。"""
    if not file_path.exists():
        logging.error(f"JSON 文件未找到: {file_path}")
        return None
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        logging.error(f"无法解码 JSON 文件: {file_path}")
        return None

def write_json_file(file_path: pathlib.Path, data: Dict[str, Any]):
    """将数据写入 JSON 文件。"""
    try:
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=4)
        logging.info(f"成功写入 JSON 文件: {file_path}")
    except IOError as e:
        logging.error(f"写入 JSON 文件失败: {file_path}, 错误: {e}")


def find_tshark() -> Optional[str]:
    """智能查找 TShark 可执行文件。"""
    common_paths = [
        '/Applications/Wireshark.app/Contents/MacOS/tshark',
        '/usr/bin/tshark',
        '/usr/local/bin/tshark',
    ]
    # 检查 shutil.which (从PATH)
    tshark_path = shutil.which(TSHARK_COMMAND)
    if tshark_path:
        logging.info(f"在 PATH 中找到 TShark: {tshark_path}")
        return tshark_path

    # 检查常见路径
    for path in common_paths:
        if pathlib.Path(path).exists():
            logging.info(f"在常见路径中找到 TShark: {path}")
            return path

    logging.error("无法找到 TShark 可执行文件。请确保 Wireshark 已安装并且 tshark 在您的系统 PATH 中，或在此脚本中指定路径。")
    return None


def run_tshark_on_file(pcap_file: pathlib.Path, tshark_path: str) -> Tuple[int, int]:
    """使用 TShark 分析文件，返回 app_records 和 app_packets 数量。"""
    if not pcap_file.exists():
        logging.warning(f"TShark: 文件不存在，跳过分析: {pcap_file}")
        return 0, 0

    cmd = [
        tshark_path,
        '-r', str(pcap_file),
        '-Y', "tls.record.content_type == 23",
        '-T', 'fields',
        '-e', 'frame.number'
    ]
    try:
        process = subprocess.run(cmd, capture_output=True, text=True, check=True)
        output = process.stdout.strip()
        if not output:
            return 0, 0

        frame_numbers = [int(f) for f in output.splitlines()]
        app_records_after = len(frame_numbers)
        app_packets_after = len(set(frame_numbers))
        return app_records_after, app_packets_after
    except subprocess.CalledProcessError as e:
        logging.error(f"执行 TShark 失败: {e}")
        return 0, 0
    except FileNotFoundError:
        logging.error(f"执行 TShark 失败: [Errno 2] No such file or directory: '{tshark_path}'")
        return 0, 0


def verify_payload_with_scapy(pcap_file: pathlib.Path, frame_numbers: List[int]) -> Tuple[int, bool]:
    """使用 Scapy 验证指定帧的 TCP 载荷是否被正确裁切。"""
    if not pcap_file.exists():
        logging.warning(f"Scapy: 文件不存在，跳过分析: {pcap_file}")
        return 0, False

    try:
        packets = rdpcap(str(pcap_file))
    except Exception as e:
        logging.error(f"Scapy 读取文件失败 {pcap_file}: {e}")
        return 0, False

    masked_bytes = 0
    all_verified = True

    # Scapy 的数据包列表是 0-indexed, tshark 帧号是 1-indexed
    for frame_num in frame_numbers:
        if frame_num > len(packets):
            logging.warning(f"帧号 {frame_num} 超出文件 {pcap_file.name} 的包总数 {len(packets)}")
            all_verified = False
            continue

        packet = packets[frame_num - 1]
        if not packet.haslayer(TCP) or not hasattr(packet[TCP], 'load'):
            logging.warning(f"帧 {frame_num} 在 {pcap_file.name} 中没有 TCP 载荷")
            all_verified = False
            continue

        payload = packet[TCP].load
        payload_len = len(payload)

        if payload_len > 5:
            bytes_to_mask = payload_len - 5
            expected_masked_part = b'\x00' * bytes_to_mask
            actual_masked_part = payload[5:]

            if actual_masked_part == expected_masked_part:
                masked_bytes += bytes_to_mask
            else:
                logging.warning(f"文件 {pcap_file.name}, 帧 {frame_num}: 载荷验证失败。")
                all_verified = False

    return masked_bytes, all_verified


def verify_trimmed_packets_scapy(pcap_path: pathlib.Path, baseline_frames: List[int]) -> int:
    """
    使用 Scapy 验证指定帧的 TCP 载荷是否已被正确裁切（保留5字节）。

    Args:
        pcap_path: 裁切后的 PCAP 文件路径。
        baseline_frames: 基线中包含 Application Data 的帧号列表。

    Returns:
        累计置零的字节数。如果验证失败则返回 -1。
    """
    if not pcap_path.exists():
        logging.warning(f"Scapy: 文件不存在，跳过验证: {pcap_path}")
        return 0
    
    try:
        packets = rdpcap(str(pcap_path))
    except Exception as e:
        logging.error(f"Scapy 无法读取文件 {pcap_path}: {e}")
        return -1

    total_masked_bytes = 0
    
    for i, packet in enumerate(packets):
        frame_num = i + 1
        if frame_num in baseline_frames:
            if not packet.haslayer("TCP") or not hasattr(packet["TCP"], "payload"):
                logging.error(f"Scapy 验证失败 (帧 {frame_num}): 期望有 TCP 载荷但未找到。")
                return -1

            payload = bytes(packet["TCP"].payload)
            ptr = 0

            while ptr + 5 <= len(payload):
                content_type = payload[ptr]
                length = int.from_bytes(payload[ptr+3:ptr+5], "big")
                header_end = ptr + 5
                record_end = header_end + length

                # 边界检查
                if record_end > len(payload):
                    logging.warning(
                        f"Scapy 验证 (帧 {frame_num}): TLS 记录超出边界 length={length}, payload_len={len(payload)}"
                    )
                    break

                if content_type == 23:  # Application Data
                    record_payload = payload[header_end:record_end]
                    if any(b != 0 for b in record_payload):
                        logging.error(
                            f"Scapy 验证失败 (帧 {frame_num}): Application Data 区段未被完全置零。"
                        )
                        logging.error(f"  - 非零前20字节: {record_payload[:20].hex()}")
                        return -1
                    total_masked_bytes += len(record_payload)

                # 继续解析下一个记录
                ptr = record_end

    return total_masked_bytes


def generate_markdown_report(verification_data: Dict[str, Any]):
    """根据验证结果生成 Markdown 报告。"""
    report_path = VERIFICATION_MD_FILE
    md_content = "# TLS Trim 端到端验证报告\n\n"
    md_content += "| 文件名 | 原始记录 | 原始包 | 裁切后记录 | 裁切后包 | 修改包(来自执行) | 掩码字节(来自验证) | 验证状态 |\n"
    md_content += "|---|---|---|---|---|---|---|---|\n"

    overall_success = True
    for filename, data in sorted(verification_data.items()):
        baseline = data.get("baseline", {})
        execution = data.get("execution", {})
        verification = data.get("verification", {})

        # 从各处获取数据
        app_records_before = baseline.get("app_records", 0)
        app_packets_before = baseline.get("app_packets", 0)
        
        modified_packets_exec = execution.get("modified_packets", "N/A")
        
        app_records_after = verification.get("app_records_after", 0)
        app_packets_after = verification.get("app_packets_after", 0)
        masked_bytes_scapy = verification.get("scapy_masked_bytes_validated", 0)

        # 定义验证状态
        status = "❌ 失败"
        # 基本成功条件：如果原始文件没有app data，且裁切后也没有，则通过
        if app_packets_before == 0 and app_packets_after == 0:
            status = "✅ 通过"
        # 主要成功条件：包数和记录数不变，且scapy验证有结果
        elif (app_records_before == app_records_after and 
              app_packets_before == app_packets_after and 
              masked_bytes_scapy > 0):
            status = "✅ 通过"
        # 如果原始文件有包，但裁切后文件不存在，则为失败
        elif app_packets_before > 0 and not pathlib.Path(verification.get("trimmed_pcap_file", "")).exists():
            status = "❌ 失败"

        if status == "❌ 失败":
            overall_success = False

        # 写入表格行
        md_content += (
            f"| `{filename}` "
            f"| {app_records_before} "
            f"| {app_packets_before} "
            f"| {app_records_after} "
            f"| {app_packets_after} "
            f"| {modified_packets_exec} "
            f"| {masked_bytes_scapy} "
            f"| **{status}** |\n"
        )
    
    summary_status = "✅ 全体验证通过" if overall_success else "❌ 部分验证失败"
    md_content += f"\n## 总结\n\n**{summary_status}**\n"
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    logging.info(f"Markdown 报告已生成: {report_path}")


def main():
    """主执行函数，负责整个验证流程。"""
    logging.info("开始执行 TLS Trim 验证脚本...")

    # 确保输出目录存在
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 读取输入文件
    baseline_data = read_json_file(BASELINE_STATS_FILE)
    trim_results = read_json_file(TRIM_RESULTS_FILE)

    if not baseline_data or not trim_results:
        return

    all_results = {}
    tshark_executable = find_tshark()
    if not tshark_executable:
        return

    # 将 trim_results 转换为以原始文件名（不带-TRIMMED后缀）为键的字典，以便快速查找
    trim_map = {
        result.get("source_file"): result.get("stats", {})
        for result in trim_results.get("results", []) if result.get("status") == "success"
    }

    for file_name, baseline_stat in baseline_data.items():
        logging.info(f"--- 正在验证: {file_name} ---")

        trimmed_pcap_name = f"{pathlib.Path(file_name).stem}-TRIMMED{pathlib.Path(file_name).suffix}"
        trimmed_pcap_path = OUTPUT_DIR / trimmed_pcap_name

        execution_stat = trim_map.get(file_name, {})
        
        # TShark 验证
        app_records_after, app_packets_after = run_tshark_on_file(trimmed_pcap_path, tshark_executable)
        logging.info(f"TShark 统计 (裁切后): {app_records_after} 条记录, {app_packets_after} 个包")
        
        # Scapy 验证
        masked_bytes_count = 0
        if baseline_stat.get("app_packets", 0) > 0 and trimmed_pcap_path.exists():
            logging.info("文件包含 Application Data, 开始 Scapy 验证...")
            masked_bytes_count = verify_trimmed_packets_scapy(trimmed_pcap_path, baseline_stat.get("frame_numbers", []))
            logging.info(f"Scapy 验证完成, 发现 {masked_bytes_count} 个掩码字节。")
        else:
            logging.info("文件中无 Application Data, 跳过 Scapy 验证。")
            
        # 整合所有结果
        all_results[file_name] = {
            "baseline": baseline_stat,
            "execution": execution_stat,
            "verification": {
                "trimmed_pcap_file": str(trimmed_pcap_path),
                "app_records_after": app_records_after,
                "app_packets_after": app_packets_after,
                "scapy_masked_bytes_validated": masked_bytes_count,
            }
        }

    # 保存和生成报告
    write_json_file(VERIFICATION_JSON_FILE, all_results)
    generate_markdown_report(all_results)
    logging.info("验证脚本执行完毕。")


if __name__ == "__main__":
    main()
