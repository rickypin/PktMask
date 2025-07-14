#!/usr/bin/env python3
"""
PktMask 流方向识别一致性验证工具

验证Marker和Masker模块的流方向识别逻辑是否一致，
特别是在处理TLS-23消息时的方向判断。
严格禁止修改主程序代码，仅用于问题诊断。
"""

import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Any, Tuple
import tempfile
import os

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DirectionConsistencyAnalyzer:
    """流方向识别一致性分析器"""
    
    def __init__(self):
        self.test_data_dir = Path("tests/data/tls")
        
    def analyze_direction_consistency(self):
        """分析方向识别一致性"""
        logger.info("开始分析流方向识别一致性")
        
        # 分析失败案例
        test_cases = [
            "tls_1_2_pop_mix.pcapng",  # 完全未掩码
            "tls_1_2-2.pcapng"         # 成功案例（对比）
        ]
        
        for test_case in test_cases:
            logger.info(f"\n{'='*60}")
            logger.info(f"分析测试案例: {test_case}")
            self._analyze_single_case_directions(test_case)
    
    def _analyze_single_case_directions(self, test_file: str):
        """分析单个测试案例的方向识别"""
        file_path = self.test_data_dir / test_file
        
        if not file_path.exists():
            logger.error(f"测试文件不存在: {file_path}")
            return
        
        # 1. 获取所有TCP包的详细信息（按时间顺序）
        logger.info("步骤1: 获取TCP包时间序列")
        tcp_packets = self._get_tcp_packet_sequence(file_path)
        
        # 2. 模拟Marker模块的方向识别（基于tshark分析顺序）
        logger.info("步骤2: 模拟Marker模块方向识别")
        marker_directions = self._simulate_marker_directions(file_path)
        
        # 3. 模拟Masker模块的方向识别（基于scapy处理顺序）
        logger.info("步骤3: 模拟Masker模块方向识别")
        masker_directions = self._simulate_masker_directions(tcp_packets)
        
        # 4. 对比TLS-23消息的方向识别结果
        logger.info("步骤4: 对比TLS-23消息方向识别")
        self._compare_tls23_directions(file_path, marker_directions, masker_directions)
    
    def _get_tcp_packet_sequence(self, file_path: Path) -> List[Dict[str, Any]]:
        """获取TCP包的时间序列"""
        logger.info(f"获取TCP包序列: {file_path}")
        
        try:
            # 使用tshark按时间顺序提取所有TCP包
            cmd = [
                "tshark", "-r", str(file_path), "-T", "json",
                "-Y", "tcp",
                "-e", "frame.number",
                "-e", "frame.time_relative",
                "-e", "tcp.stream",
                "-e", "ip.src", "-e", "ip.dst",
                "-e", "tcp.srcport", "-e", "tcp.dstport",
                "-e", "tcp.seq_raw", "-e", "tcp.len",
                "-e", "tcp.flags.syn", "-e", "tcp.flags.ack"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            packets = json.loads(result.stdout) if result.stdout.strip() else []
            
            tcp_sequence = []
            for packet in packets:
                layers = packet.get("_source", {}).get("layers", {})
                tcp_sequence.append({
                    "frame": self._get_first_value(layers.get("frame.number", "")),
                    "time": self._get_first_value(layers.get("frame.time_relative", "")),
                    "stream": self._get_first_value(layers.get("tcp.stream", "")),
                    "src_ip": self._get_first_value(layers.get("ip.src", "")),
                    "dst_ip": self._get_first_value(layers.get("ip.dst", "")),
                    "src_port": self._get_first_value(layers.get("tcp.srcport", "")),
                    "dst_port": self._get_first_value(layers.get("tcp.dstport", "")),
                    "tcp_seq": self._get_first_value(layers.get("tcp.seq_raw", "")),
                    "tcp_len": self._get_first_value(layers.get("tcp.len", "")),
                    "syn": self._get_first_value(layers.get("tcp.flags.syn", "")),
                    "ack": self._get_first_value(layers.get("tcp.flags.ack", ""))
                })
            
            logger.info(f"获取到 {len(tcp_sequence)} 个TCP包")
            
            # 显示前几个包的信息
            for i, pkt in enumerate(tcp_sequence[:5]):
                logger.info(f"  包 {i+1}: Frame {pkt['frame']}, Stream {pkt['stream']}, "
                           f"{pkt['src_ip']}:{pkt['src_port']} -> {pkt['dst_ip']}:{pkt['dst_port']}")
            
            return tcp_sequence
            
        except subprocess.CalledProcessError as e:
            logger.error(f"TCP包序列获取失败: {e}")
            return []
        except Exception as e:
            logger.error(f"TCP包序列分析异常: {e}")
            return []
    
    def _simulate_marker_directions(self, file_path: Path) -> Dict[str, Dict[str, Any]]:
        """模拟Marker模块的方向识别"""
        logger.info("模拟Marker模块方向识别（基于tshark分析）")
        
        try:
            # Marker模块使用tshark分析TCP流，按流分组
            cmd = [
                "tshark", "-r", str(file_path), "-T", "json",
                "-Y", "tcp",
                "-e", "frame.number",
                "-e", "tcp.stream",
                "-e", "ip.src", "-e", "ip.dst",
                "-e", "tcp.srcport", "-e", "tcp.dstport"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            packets = json.loads(result.stdout) if result.stdout.strip() else []
            
            # 按流分组并确定方向
            flows = {}
            for packet in packets:
                layers = packet.get("_source", {}).get("layers", {})
                stream_id = self._get_first_value(layers.get("tcp.stream", ""))
                
                if stream_id not in flows:
                    flows[stream_id] = {
                        "packets": [],
                        "directions": None
                    }
                
                flows[stream_id]["packets"].append({
                    "frame": self._get_first_value(layers.get("frame.number", "")),
                    "src_ip": self._get_first_value(layers.get("ip.src", "")),
                    "dst_ip": self._get_first_value(layers.get("ip.dst", "")),
                    "src_port": self._get_first_value(layers.get("tcp.srcport", "")),
                    "dst_port": self._get_first_value(layers.get("tcp.dstport", ""))
                })
            
            # 为每个流确定方向（模拟Marker模块逻辑）
            for stream_id, flow_info in flows.items():
                packets = flow_info["packets"]
                if packets:
                    # 第一个包定义forward方向
                    first_packet = packets[0]
                    directions = {
                        "forward": {
                            "src_ip": first_packet["src_ip"],
                            "dst_ip": first_packet["dst_ip"],
                            "src_port": first_packet["src_port"],
                            "dst_port": first_packet["dst_port"]
                        },
                        "reverse": {
                            "src_ip": first_packet["dst_ip"],
                            "dst_ip": first_packet["src_ip"],
                            "src_port": first_packet["dst_port"],
                            "dst_port": first_packet["src_port"]
                        }
                    }
                    flow_info["directions"] = directions
                    
                    logger.info(f"Marker流 {stream_id} 方向定义:")
                    logger.info(f"  Forward: {directions['forward']['src_ip']}:{directions['forward']['src_port']} -> "
                               f"{directions['forward']['dst_ip']}:{directions['forward']['dst_port']}")
            
            return flows
            
        except Exception as e:
            logger.error(f"Marker方向模拟失败: {e}")
            return {}
    
    def _simulate_masker_directions(self, tcp_packets: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """模拟Masker模块的方向识别"""
        logger.info("模拟Masker模块方向识别（基于scapy处理顺序）")
        
        # 模拟Masker模块的流ID分配和方向识别逻辑
        tuple_to_stream_id = {}
        flow_id_counter = 0
        flow_directions = {}
        flows = {}
        
        for packet in tcp_packets:
            src_ip = packet["src_ip"]
            dst_ip = packet["dst_ip"]
            src_port = packet["src_port"]
            dst_port = packet["dst_port"]
            
            # 构建标准化的五元组（较小的IP:端口在前）
            if (src_ip, src_port) < (dst_ip, dst_port):
                tuple_key = f"{src_ip}:{src_port}-{dst_ip}:{dst_port}"
            else:
                tuple_key = f"{dst_ip}:{dst_port}-{src_ip}:{src_port}"
            
            # 检查是否已为此流分配了stream_id
            if tuple_key not in tuple_to_stream_id:
                tuple_to_stream_id[tuple_key] = str(flow_id_counter)
                flow_id_counter += 1
            
            stream_id = tuple_to_stream_id[tuple_key]
            
            # 初始化流信息
            if stream_id not in flows:
                flows[stream_id] = {
                    "packets": [],
                    "directions": None
                }
            
            flows[stream_id]["packets"].append(packet)
            
            # 确定流方向（模拟Masker模块逻辑）
            if stream_id not in flow_directions:
                # 第一次遇到此流，建立方向信息
                flow_directions[stream_id] = {
                    "forward": {
                        "src_ip": src_ip,
                        "dst_ip": dst_ip,
                        "src_port": src_port,
                        "dst_port": dst_port
                    },
                    "reverse": {
                        "src_ip": dst_ip,
                        "dst_ip": src_ip,
                        "src_port": dst_port,
                        "dst_port": src_port
                    }
                }
                flows[stream_id]["directions"] = flow_directions[stream_id]
                
                logger.info(f"Masker流 {stream_id} 方向定义:")
                logger.info(f"  Forward: {src_ip}:{src_port} -> {dst_ip}:{dst_port}")
        
        return flows
    
    def _compare_tls23_directions(self, file_path: Path, 
                                 marker_directions: Dict[str, Dict[str, Any]], 
                                 masker_directions: Dict[str, Dict[str, Any]]):
        """对比TLS-23消息的方向识别结果"""
        logger.info("对比TLS-23消息方向识别结果")
        
        try:
            # 获取TLS-23消息信息
            cmd = [
                "tshark", "-r", str(file_path), "-T", "json",
                "-Y", "tls.record.content_type == 23",
                "-e", "frame.number",
                "-e", "tcp.stream",
                "-e", "ip.src", "-e", "ip.dst",
                "-e", "tcp.srcport", "-e", "tcp.dstport"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            packets = json.loads(result.stdout) if result.stdout.strip() else []
            
            logger.info(f"分析 {len(packets)} 个TLS-23消息的方向识别")
            
            direction_mismatches = 0
            
            for i, packet in enumerate(packets):
                layers = packet.get("_source", {}).get("layers", {})
                frame = self._get_first_value(layers.get("frame.number", ""))
                stream_id = self._get_first_value(layers.get("tcp.stream", ""))
                src_ip = self._get_first_value(layers.get("ip.src", ""))
                src_port = self._get_first_value(layers.get("tcp.srcport", ""))
                dst_ip = self._get_first_value(layers.get("ip.dst", ""))
                dst_port = self._get_first_value(layers.get("tcp.dstport", ""))
                
                # 计算Marker模块的方向判断
                marker_direction = self._get_packet_direction_marker(
                    src_ip, src_port, dst_ip, dst_port, 
                    marker_directions.get(stream_id, {}).get("directions", {})
                )
                
                # 计算Masker模块的方向判断
                masker_direction = self._get_packet_direction_masker(
                    src_ip, src_port, dst_ip, dst_port,
                    masker_directions.get(stream_id, {}).get("directions", {})
                )
                
                logger.info(f"TLS-23 消息 {i+1}: Frame {frame}, Stream {stream_id}")
                logger.info(f"  包方向: {src_ip}:{src_port} -> {dst_ip}:{dst_port}")
                logger.info(f"  Marker方向: {marker_direction}")
                logger.info(f"  Masker方向: {masker_direction}")
                
                if marker_direction != masker_direction:
                    direction_mismatches += 1
                    logger.error(f"  ❌ 方向识别不一致！")
                else:
                    logger.info(f"  ✅ 方向识别一致")
                logger.info("")
            
            if direction_mismatches > 0:
                logger.error(f"发现 {direction_mismatches} 个方向识别不一致的TLS-23消息")
                logger.error("这可能是导致掩码失败的根本原因！")
            else:
                logger.info("所有TLS-23消息的方向识别都一致")
                logger.info("方向识别不是问题根因，需要检查其他方面")
            
        except Exception as e:
            logger.error(f"TLS-23方向对比失败: {e}")
    
    def _get_packet_direction_marker(self, src_ip: str, src_port: str, dst_ip: str, dst_port: str,
                                   directions: Dict[str, Any]) -> str:
        """计算Marker模块的包方向判断"""
        if not directions:
            return "unknown"
        
        forward_info = directions.get("forward", {})
        
        if (src_ip == forward_info.get("src_ip") and
            str(src_port) == str(forward_info.get("src_port")) and
            dst_ip == forward_info.get("dst_ip") and
            str(dst_port) == str(forward_info.get("dst_port"))):
            return "forward"
        else:
            return "reverse"
    
    def _get_packet_direction_masker(self, src_ip: str, src_port: str, dst_ip: str, dst_port: str,
                                   directions: Dict[str, Any]) -> str:
        """计算Masker模块的包方向判断"""
        if not directions:
            return "unknown"
        
        forward_info = directions.get("forward", {})
        
        if (src_ip == forward_info.get("src_ip") and
            str(src_port) == str(forward_info.get("src_port")) and
            dst_ip == forward_info.get("dst_ip") and
            str(dst_port) == str(forward_info.get("dst_port"))):
            return "forward"
        else:
            return "reverse"
    
    def _get_first_value(self, value):
        """获取第一个值（处理tshark的数组输出）"""
        if isinstance(value, list) and value:
            return value[0]
        return value

def main():
    """主函数"""
    analyzer = DirectionConsistencyAnalyzer()
    analyzer.analyze_direction_consistency()

if __name__ == "__main__":
    main()
