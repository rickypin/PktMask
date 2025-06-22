#!/usr/bin/env python3
"""
独立的Scapy掩码测试脚本

用于验证序列号掩码机制是否能正确工作。
测试目标：从 10.171.250.80:33492 到 10.50.50.161:443 方向的TCP流的 sequence number 649-817 置零
"""

import sys
import os
from pathlib import Path
from scapy.all import *
from typing import Dict, List, Optional, Tuple
import json
import logging

# 添加项目路径到Python路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.pktmask.core.trim.models.sequence_mask_table import SequenceMaskTable, MaskEntry
from src.pktmask.core.trim.models.mask_spec import MaskAfter, KeepAll, MaskRange
from src.pktmask.core.trim.models.tcp_stream import TCPStreamManager, ConnectionDirection

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class StandaloneMaskingTest:
    """独立的掩码测试类"""
    
    def __init__(self):
        self.mask_table = SequenceMaskTable()
        self.stream_manager = TCPStreamManager()
        self.packets_modified = 0
        self.bytes_masked = 0
        
    def create_test_mask_table(self):
        """创建测试用的掩码表"""
        logger.info("创建测试掩码表...")
        
        # 目标流ID：从 10.171.250.80:33492 到 10.50.50.161:443 方向
        stream_id = "TCP_10.171.250.80:33492_10.50.50.161:443_forward"
        
        # 创建掩码条目：序列号范围 649-817，使用MaskRange全部置零
        mask_entry = MaskEntry(
            tcp_stream_id=stream_id,
            seq_start=649,  # 相对序列号起始
            seq_end=817,    # 相对序列号结束
            mask_type="test_zero_mask",
            mask_spec=MaskRange(ranges=[(0, 168)])  # 649-817 = 168字节，全部置零
        )
        
        self.mask_table.add_entry(mask_entry)
        self.mask_table.finalize()
        
        logger.info(f"掩码表创建完成：{mask_entry.get_description()}")
        
        # 打印掩码表统计
        stats = self.mask_table.get_statistics()
        logger.info(f"掩码表统计：{stats}")
        
    def analyze_pcap_file(self, pcap_file: str):
        """分析PCAP文件，了解数据包结构"""
        logger.info(f"分析PCAP文件：{pcap_file}")
        
        packets = rdpcap(pcap_file)
        logger.info(f"读取到 {len(packets)} 个数据包")
        
        # 分析TCP流
        tcp_packets = []
        for i, packet in enumerate(packets, 1):
            if packet.haslayer(TCP) and packet.haslayer(IP):
                ip_layer = packet[IP]
                tcp_layer = packet[TCP]
                
                src_ip = ip_layer.src
                dst_ip = ip_layer.dst
                src_port = tcp_layer.sport
                dst_port = tcp_layer.dport
                seq_num = tcp_layer.seq
                
                # 检查是否是目标流
                if (src_ip == "10.171.250.80" and dst_ip == "10.50.50.161" and 
                    src_port == 33492 and dst_port == 443):
                    
                    # 提取载荷
                    payload = self._extract_tcp_payload(packet)
                    
                    logger.info(f"数据包{i}: {src_ip}:{src_port} -> {dst_ip}:{dst_port}, "
                              f"绝对序列号={seq_num}, 载荷长度={len(payload)}")
                    
                    if payload:
                        logger.info(f"  载荷前32字节: {payload[:32].hex()}")
                    
                    tcp_packets.append({
                        'packet_num': i,
                        'src_ip': src_ip,
                        'dst_ip': dst_ip,
                        'src_port': src_port,
                        'dst_port': dst_port,
                        'seq_num': seq_num,
                        'payload_len': len(payload),
                        'payload': payload
                    })
        
        logger.info(f"找到目标流的 {len(tcp_packets)} 个数据包")
        return tcp_packets
        
    def apply_masking(self, input_file: str, output_file: str):
        """应用掩码到PCAP文件"""
        logger.info(f"开始掩码处理：{input_file} -> {output_file}")
        
        # 读取数据包
        packets = rdpcap(input_file)
        modified_packets = []
        
        # 初始化流管理器（模拟初始序列号）
        # 从分析结果得知，我们需要设置初始序列号
        target_stream = self.stream_manager.get_or_create_stream(
            "10.171.250.80", 33492, "10.50.50.161", 443, ConnectionDirection.FORWARD
        )
        
        # 设置一个模拟的初始序列号（需要根据实际情况调整）
        # 从日志看到绝对序列号是2422050299，相对序列号是518
        # 所以初始序列号应该是 2422050299 - 518 = 2422049781
        target_stream.set_initial_seq(2422049781)
        
        logger.info(f"设置目标流初始序列号：{target_stream.initial_seq}")
        
        for i, packet in enumerate(packets, 1):
            modified_packet = self._apply_mask_to_packet(packet, i)
            modified_packets.append(modified_packet)
        
        # 写入输出文件
        wrpcap(output_file, modified_packets)
        logger.info(f"输出文件已保存：{output_file}")
        logger.info(f"掩码处理统计：修改了 {self.packets_modified} 个数据包，掩码了 {self.bytes_masked} 字节")
        
    def _extract_tcp_payload(self, packet) -> bytes:
        """提取TCP载荷"""
        if packet.haslayer(Raw):
            return bytes(packet[Raw])
        elif packet.haslayer(TCP):
            tcp_layer = packet[TCP]
            if hasattr(tcp_layer, 'payload') and tcp_layer.payload:
                return bytes(tcp_layer.payload)
        return b""
        
    def _apply_mask_to_packet(self, packet, packet_number: int):
        """对单个数据包应用掩码"""
        try:
            # 只处理TCP数据包
            if not (packet.haslayer(TCP) and packet.haslayer(IP)):
                return packet
                
            ip_layer = packet[IP]
            tcp_layer = packet[TCP]
            
            src_ip = ip_layer.src
            dst_ip = ip_layer.dst
            src_port = tcp_layer.sport
            dst_port = tcp_layer.dport
            seq_num = tcp_layer.seq
            
            # 只处理目标流
            if not (src_ip == "10.171.250.80" and dst_ip == "10.50.50.161" and 
                   src_port == 33492 and dst_port == 443):
                return packet
                
            # 提取载荷
            payload = self._extract_tcp_payload(packet)
            if not payload:
                logger.debug(f"数据包{packet_number}: 无载荷，跳过")
                return packet
                
            # 生成流ID
            stream_id = "TCP_10.171.250.80:33492_10.50.50.161:443_forward"
            
            # 转换为相对序列号
            tcp_stream = self.stream_manager.get_stream_by_id(stream_id)
            if tcp_stream and tcp_stream.initial_seq is not None:
                relative_seq = tcp_stream.get_relative_seq(seq_num)
                logger.info(f"数据包{packet_number}: 序列号转换 绝对={seq_num} -> 相对={relative_seq}")
            else:
                relative_seq = seq_num
                logger.warning(f"数据包{packet_number}: 无流信息，使用绝对序列号={seq_num}")
                
            # 查找掩码
            match_results = self.mask_table.match_sequence_range(stream_id, relative_seq, len(payload))
            
            logger.info(f"数据包{packet_number}: 流={stream_id}, 相对序列号={relative_seq}, "
                       f"载荷长度={len(payload)}, 匹配掩码={len(match_results)}个")
            
            if not any(result.is_match for result in match_results):
                logger.debug(f"数据包{packet_number}: 未匹配到掩码")
                return packet
                
            # 应用掩码
            original_payload = payload
            modified_payload = bytearray(payload)
            
            for result in match_results:
                if result.is_match:
                    logger.info(f"  应用掩码: 偏移[{result.mask_start_offset}:{result.mask_end_offset}), "
                               f"长度={result.mask_length}")
                    
                    # 应用掩码规范
                    mask_spec = result.entry.mask_spec
                    start_offset = result.mask_start_offset
                    end_offset = result.mask_end_offset
                    
                    if isinstance(mask_spec, MaskRange):
                        # 置零指定范围
                        for range_start, range_end in mask_spec.ranges:
                            mask_start = start_offset + range_start
                            mask_end = start_offset + range_end
                            mask_end = min(mask_end, end_offset, len(modified_payload))
                            
                            if mask_start < len(modified_payload):
                                logger.info(f"    MaskRange: 置零范围[{mask_start}:{mask_end})")
                                for j in range(mask_start, mask_end):
                                    modified_payload[j] = 0
                                self.bytes_masked += (mask_end - mask_start)
                    
            # 检查是否有修改
            if bytes(modified_payload) != original_payload:
                logger.info(f"数据包{packet_number}: 载荷已修改")
                logger.info(f"  原始载荷前32字节: {original_payload[:32].hex()}")
                logger.info(f"  修改载荷前32字节: {bytes(modified_payload)[:32].hex()}")
                
                # 更新数据包载荷
                packet = self._update_packet_payload(packet, bytes(modified_payload))
                self.packets_modified += 1
            else:
                logger.debug(f"数据包{packet_number}: 载荷未修改")
                
            return packet
            
        except Exception as e:
            logger.error(f"处理数据包{packet_number}时出错: {e}")
            import traceback
            traceback.print_exc()
            return packet
            
    def _update_packet_payload(self, packet, new_payload: bytes):
        """更新数据包载荷"""
        # 创建新的数据包
        new_packet = packet.copy()
        
        # 移除原有的载荷层
        if new_packet.haslayer(Raw):
            new_packet[Raw] = Raw(load=new_payload)
        else:
            # 在TCP层后添加Raw层
            tcp_layer = new_packet[TCP]
            tcp_layer.remove_payload()
            new_packet = new_packet / Raw(load=new_payload)
            
        # 重新计算校验和
        del new_packet[IP].chksum
        del new_packet[TCP].chksum
        
        return new_packet

def main():
    """主函数"""
    input_file = "/Users/ricky/Downloads/samples/tls-single/tls_sample.pcap"
    output_file = "/tmp/tls_sample_masked_standalone.pcap"
    
    logger.info("=" * 60)
    logger.info("独立Scapy掩码测试")
    logger.info("=" * 60)
    logger.info(f"输入文件: {input_file}")
    logger.info(f"输出文件: {output_file}")
    
    # 检查输入文件
    if not os.path.exists(input_file):
        logger.error(f"输入文件不存在: {input_file}")
        return 1
        
    # 创建测试实例
    test = StandaloneMaskingTest()
    
    try:
        # 1. 创建掩码表
        test.create_test_mask_table()
        
        # 2. 分析PCAP文件
        tcp_packets = test.analyze_pcap_file(input_file)
        
        # 3. 应用掩码
        test.apply_masking(input_file, output_file)
        
        logger.info("=" * 60)
        logger.info("测试完成！")
        logger.info(f"输出文件: {output_file}")
        logger.info("=" * 60)
        
        return 0
        
    except Exception as e:
        logger.error(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main()) 