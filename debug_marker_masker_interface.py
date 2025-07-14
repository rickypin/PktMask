#!/usr/bin/env python3
"""
PktMask Marker-Masker模块接口分析工具

深入分析Marker模块生成的保留规则和Masker模块的应用逻辑，
识别双模块间数据传递和一致性问题。
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

class MarkerMaskerInterfaceAnalyzer:
    """Marker-Masker模块接口分析器"""
    
    def __init__(self):
        self.test_data_dir = Path("tests/data/tls")
        
    def analyze_interface_issues(self):
        """分析接口问题"""
        logger.info("开始分析Marker-Masker模块接口问题")
        
        # 分析关键失败案例
        test_cases = [
            "tls_1_2_pop_mix.pcapng",  # 完全未掩码
            "tls_1_2-2.pcapng"         # 成功案例（对比）
        ]
        
        for test_case in test_cases:
            logger.info(f"\n{'='*60}")
            logger.info(f"分析测试案例: {test_case}")
            self._analyze_single_interface(test_case)
    
    def _analyze_single_interface(self, test_file: str):
        """分析单个测试案例的接口问题"""
        file_path = self.test_data_dir / test_file
        
        if not file_path.exists():
            logger.error(f"测试文件不存在: {file_path}")
            return
        
        # 1. 分析TCP流结构
        logger.info("步骤1: 分析TCP流结构")
        tcp_flows = self._analyze_tcp_flows(file_path)
        
        # 2. 分析TLS消息分布
        logger.info("步骤2: 分析TLS消息分布")
        tls_messages = self._analyze_tls_distribution(file_path)
        
        # 3. 模拟Marker模块的流ID构建逻辑
        logger.info("步骤3: 模拟Marker模块流ID构建")
        marker_flow_ids = self._simulate_marker_flow_ids(file_path)
        
        # 4. 模拟Masker模块的流ID构建逻辑
        logger.info("步骤4: 模拟Masker模块流ID构建")
        masker_flow_ids = self._simulate_masker_flow_ids(file_path)
        
        # 5. 对比流ID一致性
        logger.info("步骤5: 对比流ID一致性")
        self._compare_flow_id_consistency(marker_flow_ids, masker_flow_ids)
        
        # 6. 分析序列号计算
        logger.info("步骤6: 分析序列号计算")
        self._analyze_sequence_numbers(file_path, tls_messages)
    
    def _analyze_tcp_flows(self, file_path: Path) -> Dict[str, Any]:
        """分析TCP流结构"""
        logger.info(f"分析TCP流: {file_path}")
        
        try:
            # 使用tshark提取TCP流信息
            cmd = [
                "tshark", "-r", str(file_path), "-T", "json",
                "-e", "frame.number",
                "-e", "tcp.stream",
                "-e", "ip.src", "-e", "ip.dst",
                "-e", "tcp.srcport", "-e", "tcp.dstport",
                "-e", "tcp.seq_raw", "-e", "tcp.len"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            packets = json.loads(result.stdout) if result.stdout.strip() else []
            
            # 统计TCP流信息
            flows = {}
            for packet in packets:
                layers = packet.get("_source", {}).get("layers", {})
                stream_id = self._get_first_value(layers.get("tcp.stream", ""))
                
                if stream_id not in flows:
                    flows[stream_id] = {
                        "packets": [],
                        "src_ips": set(),
                        "dst_ips": set(),
                        "src_ports": set(),
                        "dst_ports": set()
                    }
                
                flows[stream_id]["packets"].append({
                    "frame": self._get_first_value(layers.get("frame.number", "")),
                    "src_ip": self._get_first_value(layers.get("ip.src", "")),
                    "dst_ip": self._get_first_value(layers.get("ip.dst", "")),
                    "src_port": self._get_first_value(layers.get("tcp.srcport", "")),
                    "dst_port": self._get_first_value(layers.get("tcp.dstport", "")),
                    "tcp_seq": self._get_first_value(layers.get("tcp.seq_raw", "")),
                    "tcp_len": self._get_first_value(layers.get("tcp.len", ""))
                })
                
                flows[stream_id]["src_ips"].add(self._get_first_value(layers.get("ip.src", "")))
                flows[stream_id]["dst_ips"].add(self._get_first_value(layers.get("ip.dst", "")))
                flows[stream_id]["src_ports"].add(self._get_first_value(layers.get("tcp.srcport", "")))
                flows[stream_id]["dst_ports"].add(self._get_first_value(layers.get("tcp.dstport", "")))
            
            # 转换set为list以便JSON序列化
            for stream_id in flows:
                flows[stream_id]["src_ips"] = list(flows[stream_id]["src_ips"])
                flows[stream_id]["dst_ips"] = list(flows[stream_id]["dst_ips"])
                flows[stream_id]["src_ports"] = list(flows[stream_id]["src_ports"])
                flows[stream_id]["dst_ports"] = list(flows[stream_id]["dst_ports"])
            
            logger.info(f"发现 {len(flows)} 个TCP流")
            for stream_id, flow_info in flows.items():
                logger.info(f"  流 {stream_id}: {len(flow_info['packets'])} 个包, "
                           f"IP: {flow_info['src_ips']} <-> {flow_info['dst_ips']}, "
                           f"端口: {flow_info['src_ports']} <-> {flow_info['dst_ports']}")
            
            return flows
            
        except subprocess.CalledProcessError as e:
            logger.error(f"TCP流分析失败: {e}")
            return {}
        except Exception as e:
            logger.error(f"TCP流分析异常: {e}")
            return {}
    
    def _analyze_tls_distribution(self, file_path: Path) -> Dict[str, Any]:
        """分析TLS消息分布"""
        logger.info(f"分析TLS消息分布: {file_path}")
        
        try:
            # 使用tshark提取TLS消息信息
            cmd = [
                "tshark", "-r", str(file_path), "-T", "json",
                "-Y", "tls.record.content_type == 23",
                "-e", "frame.number",
                "-e", "tcp.stream",
                "-e", "ip.src", "-e", "ip.dst",
                "-e", "tcp.srcport", "-e", "tcp.dstport",
                "-e", "tcp.seq_raw", "-e", "tcp.len",
                "-e", "tls.record.content_type",
                "-e", "tls.record.length"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            packets = json.loads(result.stdout) if result.stdout.strip() else []
            
            tls_messages = []
            for packet in packets:
                layers = packet.get("_source", {}).get("layers", {})
                tls_messages.append({
                    "frame": self._get_first_value(layers.get("frame.number", "")),
                    "stream": self._get_first_value(layers.get("tcp.stream", "")),
                    "src_ip": self._get_first_value(layers.get("ip.src", "")),
                    "dst_ip": self._get_first_value(layers.get("ip.dst", "")),
                    "src_port": self._get_first_value(layers.get("tcp.srcport", "")),
                    "dst_port": self._get_first_value(layers.get("tcp.dstport", "")),
                    "tcp_seq": self._get_first_value(layers.get("tcp.seq_raw", "")),
                    "tcp_len": self._get_first_value(layers.get("tcp.len", "")),
                    "tls_length": self._get_first_value(layers.get("tls.record.length", ""))
                })
            
            logger.info(f"发现 {len(tls_messages)} 个TLS-23消息")
            for i, msg in enumerate(tls_messages[:3]):  # 显示前3个
                logger.info(f"  TLS-23 #{i+1}: Frame {msg['frame']}, Stream {msg['stream']}, "
                           f"TCP序列号 {msg['tcp_seq']}, TLS长度 {msg['tls_length']}")
            
            return {"messages": tls_messages, "count": len(tls_messages)}
            
        except subprocess.CalledProcessError as e:
            logger.error(f"TLS消息分析失败: {e}")
            return {"messages": [], "count": 0}
        except Exception as e:
            logger.error(f"TLS消息分析异常: {e}")
            return {"messages": [], "count": 0}
    
    def _simulate_marker_flow_ids(self, file_path: Path) -> Dict[str, Any]:
        """模拟Marker模块的流ID构建逻辑"""
        logger.info("模拟Marker模块流ID构建（基于tshark的tcp.stream）")
        
        # Marker模块直接使用tshark的tcp.stream字段
        try:
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
            
            marker_flows = {}
            for packet in packets:
                layers = packet.get("_source", {}).get("layers", {})
                frame = self._get_first_value(layers.get("frame.number", ""))
                stream_id = self._get_first_value(layers.get("tcp.stream", ""))
                
                if stream_id not in marker_flows:
                    marker_flows[stream_id] = []
                
                marker_flows[stream_id].append({
                    "frame": frame,
                    "src_ip": self._get_first_value(layers.get("ip.src", "")),
                    "dst_ip": self._get_first_value(layers.get("ip.dst", "")),
                    "src_port": self._get_first_value(layers.get("tcp.srcport", "")),
                    "dst_port": self._get_first_value(layers.get("tcp.dstport", ""))
                })
            
            logger.info(f"Marker模块识别的流: {list(marker_flows.keys())}")
            return marker_flows
            
        except Exception as e:
            logger.error(f"Marker流ID模拟失败: {e}")
            return {}
    
    def _simulate_masker_flow_ids(self, file_path: Path) -> Dict[str, Any]:
        """模拟Masker模块的流ID构建逻辑"""
        logger.info("模拟Masker模块流ID构建（基于五元组标准化）")
        
        # Masker模块基于五元组构建流ID，需要模拟其逻辑
        try:
            cmd = [
                "tshark", "-r", str(file_path), "-T", "json",
                "-Y", "tls.record.content_type == 23",
                "-e", "frame.number",
                "-e", "ip.src", "-e", "ip.dst",
                "-e", "tcp.srcport", "-e", "tcp.dstport"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            packets = json.loads(result.stdout) if result.stdout.strip() else []
            
            # 模拟Masker模块的流ID分配逻辑
            tuple_to_stream_id = {}
            flow_id_counter = 0
            masker_flows = {}
            
            for packet in packets:
                layers = packet.get("_source", {}).get("layers", {})
                frame = self._get_first_value(layers.get("frame.number", ""))
                src_ip = self._get_first_value(layers.get("ip.src", ""))
                dst_ip = self._get_first_value(layers.get("ip.dst", ""))
                src_port = self._get_first_value(layers.get("tcp.srcport", ""))
                dst_port = self._get_first_value(layers.get("tcp.dstport", ""))
                
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
                
                if stream_id not in masker_flows:
                    masker_flows[stream_id] = []
                
                masker_flows[stream_id].append({
                    "frame": frame,
                    "src_ip": src_ip,
                    "dst_ip": dst_ip,
                    "src_port": src_port,
                    "dst_port": dst_port,
                    "tuple_key": tuple_key
                })
            
            logger.info(f"Masker模块识别的流: {list(masker_flows.keys())}")
            logger.info(f"五元组映射: {tuple_to_stream_id}")
            return masker_flows
            
        except Exception as e:
            logger.error(f"Masker流ID模拟失败: {e}")
            return {}
    
    def _compare_flow_id_consistency(self, marker_flows: Dict[str, Any], masker_flows: Dict[str, Any]):
        """对比流ID一致性"""
        logger.info("对比Marker和Masker模块的流ID一致性")
        
        marker_stream_ids = set(marker_flows.keys())
        masker_stream_ids = set(masker_flows.keys())
        
        logger.info(f"Marker流ID: {sorted(marker_stream_ids)}")
        logger.info(f"Masker流ID: {sorted(masker_stream_ids)}")
        
        if marker_stream_ids == masker_stream_ids:
            logger.info("✅ 流ID完全一致")
        else:
            logger.error("❌ 流ID不一致！")
            logger.error(f"  仅在Marker中: {marker_stream_ids - masker_stream_ids}")
            logger.error(f"  仅在Masker中: {masker_stream_ids - marker_stream_ids}")
            logger.error("这可能是导致掩码失败的根本原因！")
    
    def _analyze_sequence_numbers(self, file_path: Path, tls_messages: Dict[str, Any]):
        """分析序列号计算"""
        logger.info("分析序列号计算逻辑")
        
        messages = tls_messages.get("messages", [])
        if not messages:
            logger.warning("没有TLS消息可分析")
            return
        
        logger.info("TLS消息序列号分析:")
        for i, msg in enumerate(messages[:3]):  # 分析前3个消息
            tcp_seq = msg.get("tcp_seq", "")
            tcp_len = msg.get("tcp_len", "")
            tls_len = msg.get("tls_length", "")
            
            logger.info(f"  消息 {i+1}: Frame {msg['frame']}")
            logger.info(f"    TCP序列号: {tcp_seq}")
            logger.info(f"    TCP载荷长度: {tcp_len}")
            logger.info(f"    TLS记录长度: {tls_len}")
            
            # 计算TLS头部和载荷的序列号范围
            if tcp_seq and tls_len:
                try:
                    seq_start = int(tcp_seq)
                    tls_record_len = int(tls_len)
                    
                    # TLS记录头部（5字节）
                    header_end = seq_start + 5
                    # TLS记录载荷
                    payload_end = seq_start + 5 + tls_record_len
                    
                    logger.info(f"    TLS头部范围: [{seq_start}, {header_end})")
                    logger.info(f"    TLS载荷范围: [{header_end}, {payload_end})")
                    logger.info(f"    预期掩码策略: 保留头部，掩码载荷")
                    
                except ValueError:
                    logger.warning(f"    序列号解析失败: tcp_seq={tcp_seq}, tls_len={tls_len}")
    
    def _get_first_value(self, value):
        """获取第一个值（处理tshark的数组输出）"""
        if isinstance(value, list) and value:
            return value[0]
        return value

def main():
    """主函数"""
    analyzer = MarkerMaskerInterfaceAnalyzer()
    analyzer.analyze_interface_issues()

if __name__ == "__main__":
    main()
