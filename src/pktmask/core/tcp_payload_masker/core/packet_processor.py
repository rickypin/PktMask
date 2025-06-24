"""
数据包处理器

负责PCAP文件的读取、处理和写入，以及Scapy校验和的自动修复。
"""

import os
import time
import logging
from typing import List, Iterator
from scapy.all import PcapReader, PcapWriter, Ether, IP, TCP, UDP, raw
from scapy.packet import Packet

from ..api.types import (
    MaskingRecipe, 
    PacketMaskingResult, 
    MaskingStatistics
)
from .blind_masker import BlindPacketMasker


logger = logging.getLogger(__name__)


class PacketProcessor:
    """
    数据包处理器
    
    负责：
    1. PCAP文件的读取和写入
    2. 调用BlindPacketMasker进行掩码处理
    3. Scapy校验和的自动修复
    4. 处理进度和错误管理
    """
    
    def __init__(self, enable_checksum_fix: bool = True):
        """
        初始化包处理器
        
        Args:
            enable_checksum_fix: 是否启用自动校验和修复
        """
        self.enable_checksum_fix = enable_checksum_fix
        self.logger = logger.getChild("PacketProcessor")
    
    def process_pcap_file(
        self, 
        input_file: str, 
        output_file: str, 
        masking_recipe: MaskingRecipe
    ) -> PacketMaskingResult:
        """
        处理整个PCAP文件
        
        Args:
            input_file: 输入PCAP文件路径
            output_file: 输出PCAP文件路径
            masking_recipe: 掩码配方
            
        Returns:
            处理结果
        """
        start_time = time.time()
        self.logger.info(f"开始处理PCAP文件: {input_file} -> {output_file}")
        
        try:
            # 验证输入文件
            if not os.path.exists(input_file):
                return PacketMaskingResult(
                    success=False,
                    processed_packets=0,
                    modified_packets=0,
                    output_file="",
                    errors=[f"输入文件不存在: {input_file}"],
                    execution_time=time.time() - start_time
                )
            
            # 创建输出目录
            output_dir = os.path.dirname(output_file)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
            
            # 创建掩码器
            masker = BlindPacketMasker(masking_recipe)
            
            # 处理数据包
            result = self._process_packets(input_file, output_file, masker)
            
            # 更新执行时间
            result.execution_time = time.time() - start_time
            
            self.logger.info(
                f"处理完成: {result.processed_packets}包处理，"
                f"{result.modified_packets}包修改，耗时{result.execution_time:.2f}秒"
            )
            
            return result
            
        except Exception as e:
            error_msg = f"处理PCAP文件时发生错误: {e}"
            self.logger.error(error_msg)
            return PacketMaskingResult(
                success=False,
                processed_packets=0,
                modified_packets=0,
                output_file="",
                errors=[error_msg],
                execution_time=time.time() - start_time
            )
    
    def _process_packets(
        self, 
        input_file: str, 
        output_file: str, 
        masker: BlindPacketMasker
    ) -> PacketMaskingResult:
        """
        处理数据包的核心逻辑
        
        Args:
            input_file: 输入文件
            output_file: 输出文件  
            masker: 掩码器实例
            
        Returns:
            处理结果
        """
        processed_packets = []
        errors = []
        
        try:
            # 打开输入文件
            with PcapReader(input_file) as reader:
                packet_index = 0
                
                for packet in reader:
                    try:
                        # 处理单个包
                        modified_bytes, was_modified = masker.process_packet(packet_index, packet)
                        
                        if was_modified and modified_bytes:
                            # 从修改后的字节流重构数据包
                            modified_packet = self._reconstruct_packet(modified_bytes)
                            
                            # 修复校验和（如果启用）
                            if self.enable_checksum_fix:
                                modified_packet = self._fix_checksums(modified_packet)
                            
                            processed_packets.append(modified_packet)
                        else:
                            # 包未修改，直接使用原包
                            processed_packets.append(packet)
                        
                        packet_index += 1
                        
                        # 每处理1000个包记录一次进度
                        if packet_index % 1000 == 0:
                            self.logger.debug(f"已处理{packet_index}个包")
                    
                    except Exception as e:
                        error_msg = f"处理包{packet_index}时发生错误: {e}"
                        self.logger.error(error_msg)
                        errors.append(error_msg)
                        
                        # 对于错误的包，仍然加入原包以保持完整性
                        processed_packets.append(packet)
                        packet_index += 1
            
            # 写入输出文件
            self._write_packets(output_file, processed_packets)
            
            # 获取统计信息
            stats = masker.get_statistics()
            
            return PacketMaskingResult(
                success=len(errors) == 0,
                processed_packets=stats.processed_packets,
                modified_packets=stats.modified_packets,
                output_file=output_file,
                errors=errors,
                statistics=stats.to_dict()
            )
            
        except Exception as e:
            error_msg = f"文件处理过程中发生错误: {e}"
            self.logger.error(error_msg)
            errors.append(error_msg)
            
            return PacketMaskingResult(
                success=False,
                processed_packets=0,
                modified_packets=0,
                output_file="",
                errors=errors
            )
    
    def _reconstruct_packet(self, packet_bytes: bytes) -> Packet:
        """
        从字节流重构数据包
        
        Args:
            packet_bytes: 数据包字节流
            
        Returns:
            重构的Scapy数据包
        """
        try:
            # 尝试解析为以太网包
            return Ether(packet_bytes)
        except Exception:
            # 如果解析失败，创建原始数据包
            from scapy.layers.l2 import Raw
            return Raw(packet_bytes)
    
    def _fix_checksums(self, packet: Packet) -> Packet:
        """
        修复数据包的校验和
        
        Args:
            packet: 数据包
            
        Returns:
            校验和修复后的数据包
        """
        try:
            # 删除现有的校验和，让Scapy自动重新计算
            if packet.haslayer(IP):
                ip_layer = packet[IP]
                if hasattr(ip_layer, 'chksum'):
                    del ip_layer.chksum
                
                # 修复TCP校验和
                if packet.haslayer(TCP):
                    tcp_layer = packet[TCP]
                    if hasattr(tcp_layer, 'chksum'):
                        del tcp_layer.chksum
                
                # 修复UDP校验和
                if packet.haslayer(UDP):
                    udp_layer = packet[UDP]
                    if hasattr(udp_layer, 'chksum'):
                        del udp_layer.chksum
            
            # 重新构建数据包以触发校验和计算
            packet = Ether(raw(packet))
            
            return packet
            
        except Exception as e:
            self.logger.warning(f"修复校验和时发生错误: {e}，返回原包")
            return packet
    
    def _write_packets(self, output_file: str, packets: List[Packet]):
        """
        将数据包写入PCAP文件
        
        Args:
            output_file: 输出文件路径
            packets: 数据包列表
        """
        try:
            with PcapWriter(output_file, append=False, sync=True) as writer:
                for packet in packets:
                    writer.write(packet)
            
            self.logger.info(f"成功写入{len(packets)}个包到{output_file}")
            
        except Exception as e:
            self.logger.error(f"写入文件{output_file}时发生错误: {e}")
            raise
    
    def verify_output_file(self, output_file: str) -> bool:
        """
        验证输出文件的有效性
        
        Args:
            output_file: 输出文件路径
            
        Returns:
            文件是否有效
        """
        try:
            if not os.path.exists(output_file):
                return False
            
            # 尝试读取文件的前几个包
            packet_count = 0
            with PcapReader(output_file) as reader:
                for packet in reader:
                    packet_count += 1
                    if packet_count >= 5:  # 只检查前5个包
                        break
            
            return packet_count > 0
            
        except Exception as e:
            self.logger.error(f"验证输出文件{output_file}时发生错误: {e}")
            return False 