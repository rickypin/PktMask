"""
Scapy掩码应用器

基于MaskRule列表对数据包进行精确掩码应用的组件。
这是TSharkEnhancedMaskProcessor的第三阶段处理器。

功能特性：
1. 边界安全处理：确保掩码操作不会超出TLS记录边界
2. 分类掩码应用：根据TLS类型应用不同的掩码策略
3. 多规则处理：支持单个数据包应用多个掩码规则
4. 校验和重计算：自动处理TCP/IP校验和
5. 错误恢复：异常情况下优雅降级
"""

import logging
import time
from collections import defaultdict
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path

try:
    from scapy.all import rdpcap, wrpcap, Packet, TCP, Raw, IP
    SCAPY_AVAILABLE = True
except ImportError:
    rdpcap = wrpcap = Packet = TCP = Raw = IP = None
    SCAPY_AVAILABLE = False

from ..trim.models.tls_models import MaskRule, MaskAction


class ScapyMaskApplier:
    """Scapy掩码应用器
    
    将TLS掩码规则精确应用到数据包，处理TLS记录边界安全。
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化Scapy掩码应用器
        
        Args:
            config: 配置参数字典
        """
        self.config = config or {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # 配置参数
        self._mask_byte_value = self.config.get('mask_byte_value', 0x00)
        self._recalculate_checksums = self.config.get('recalculate_checksums', True)
        self._preserve_timestamps = self.config.get('preserve_timestamps', True)
        self._batch_size = self.config.get('batch_size', 1000)
        self._validate_boundaries = self.config.get('validate_boundaries', True)
        
        # 调试配置
        self._verbose = self.config.get('verbose', False)
        self._debug_packet_numbers = self.config.get('debug_packet_numbers', [])
        
        # 内部状态
        self._processed_packets_count = 0
        self._modified_packets_count = 0
        self._masked_bytes_count = 0
        self._applied_rules_count = 0
        self._boundary_violations_count = 0
        
    def check_dependencies(self) -> bool:
        """检查Scapy依赖是否可用
        
        Returns:
            是否可用
        """
        if not SCAPY_AVAILABLE:
            self.logger.error("Scapy库不可用，无法进行掩码应用")
            return False
        return True
    
    def apply_masks(
        self, 
        input_file: str, 
        output_file: str, 
        mask_rules: List[MaskRule]
    ) -> Dict[str, Any]:
        """对PCAP文件应用掩码规则
        
        Args:
            input_file: 输入PCAP文件路径
            output_file: 输出PCAP文件路径
            mask_rules: 掩码规则列表
            
        Returns:
            处理结果字典
            
        Raises:
            RuntimeError: 掩码应用失败时抛出
            FileNotFoundError: 输入文件不存在时抛出
            ImportError: Scapy不可用时抛出
        """
        if not self.check_dependencies():
            raise ImportError("Scapy库不可用，无法进行掩码应用")
        
        if not Path(input_file).exists():
            raise FileNotFoundError(f"输入文件不存在: {input_file}")
        
        self.logger.info(f"开始应用掩码规则: {input_file} -> {output_file}")
        self.logger.info(f"掩码规则数量: {len(mask_rules)}")
        
        self._reset_statistics()
        start_time = time.time()
        
        try:
            # 组织掩码规则（按包编号分组）
            packet_rules = self._organize_rules_by_packet(mask_rules)
            
            # 读取数据包
            self.logger.info("读取输入PCAP文件...")
            packets = rdpcap(input_file)
            total_packets = len(packets)
            
            self.logger.info(f"成功读取{total_packets}个数据包")
            
            # 应用掩码规则
            modified_packets = self._apply_masks_to_packets(packets, packet_rules)
            
            # 写入输出文件
            self.logger.info(f"写入输出PCAP文件: {output_file}")
            self._write_packets(modified_packets, output_file)
            
            # 计算处理统计
            processing_time = time.time() - start_time
            
            result = self._generate_result_statistics(
                total_packets, processing_time
            )
            
            self.logger.info(f"掩码应用完成：处理{total_packets}个包，修改{self._modified_packets_count}个包")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Scapy掩码应用失败: {e}")
            raise RuntimeError(f"掩码应用失败: {e}") from e
    
    def _organize_rules_by_packet(self, mask_rules: List[MaskRule]) -> Dict[int, List[MaskRule]]:
        """按包编号组织掩码规则
        
        Args:
            mask_rules: 掩码规则列表
            
        Returns:
            按包编号分组的规则字典
        """
        packet_rules = defaultdict(list)
        
        for rule in mask_rules:
            packet_rules[rule.packet_number].append(rule)
        
        # 对每个包的规则按偏移量排序
        for packet_number, rules in packet_rules.items():
            rules.sort(key=lambda r: r.tls_record_offset)
        
        self.logger.debug(f"规则组织完成：{len(packet_rules)}个包有掩码规则")
        
        return packet_rules
    
    def _apply_masks_to_packets(
        self, 
        packets: List[Packet], 
        packet_rules: Dict[int, List[MaskRule]]
    ) -> List[Packet]:
        """对数据包列表应用掩码规则
        
        Args:
            packets: 数据包列表
            packet_rules: 按包编号分组的规则
            
        Returns:
            处理后的数据包列表
        """
        modified_packets = []
        
        for i, packet in enumerate(packets):
            packet_number = i + 1  # 包编号从1开始
            self._processed_packets_count += 1
            
            # 检查是否有适用的规则
            if packet_number not in packet_rules:
                # 无规则，原样保留
                modified_packets.append(packet)
                continue
            
            # 检查是否需要调试输出
            debug_this_packet = (
                packet_number in self._debug_packet_numbers or 
                self._verbose
            )
            
            if debug_this_packet:
                self.logger.info(f"=== 处理包{packet_number} ===")
            
            # 应用掩码规则
            try:
                modified_packet = self._apply_mask_rules_to_packet(
                    packet, packet_rules[packet_number], packet_number
                )
                modified_packets.append(modified_packet)
                
                if debug_this_packet:
                    self.logger.info(f"包{packet_number}处理完成")
                    
            except Exception as e:
                self.logger.warning(f"包{packet_number}掩码应用失败: {e}")
                # 失败时保留原包
                modified_packets.append(packet)
            
            # 进度报告
            if self._processed_packets_count % self._batch_size == 0:
                self.logger.debug(f"已处理{self._processed_packets_count}个包")
        
        return modified_packets
    
    def _apply_mask_rules_to_packet(
        self, 
        packet: Packet, 
        rules: List[MaskRule],
        packet_number: int
    ) -> Packet:
        """对单个数据包应用多个掩码规则
        
        Args:
            packet: 原始数据包
            rules: 该包的掩码规则列表
            packet_number: 包编号（用于调试）
            
        Returns:
            处理后的数据包
        """
        if not rules:
            return packet
        
        # 检查包是否有TCP层
        if not packet.haslayer(TCP):
            self.logger.warning(f"包{packet_number}没有TCP层，跳过掩码应用")
            return packet
        
        # 获取TCP载荷
        tcp_payload = self._extract_tcp_payload(packet)
        if not tcp_payload:
            self.logger.debug(f"包{packet_number}没有TCP载荷，跳过掩码应用")
            return packet
        
        # 复制数据包
        modified_packet = packet.copy()
        
        # 创建可修改的载荷缓冲区
        masked_payload = bytearray(tcp_payload)
        original_length = len(masked_payload)
        
        # 应用所有掩码规则
        packet_was_modified = False
        
        for rule in rules:
            if self._apply_single_mask_rule(
                masked_payload, rule, packet_number, original_length
            ):
                packet_was_modified = True
        
        # 更新数据包载荷
        if packet_was_modified:
            self._update_packet_payload(modified_packet, bytes(masked_payload))
            self._modified_packets_count += 1
            
            # 重新计算校验和（如果启用）
            if self._recalculate_checksums:
                self._recalculate_packet_checksums(modified_packet)
        
        return modified_packet
    
    def _apply_single_mask_rule(
        self, 
        payload_buffer: bytearray, 
        rule: MaskRule,
        packet_number: int,
        payload_length: int
    ) -> bool:
        """应用单个掩码规则到载荷缓冲区
        
        Args:
            payload_buffer: 可修改的载荷缓冲区
            rule: 掩码规则
            packet_number: 包编号
            payload_length: 载荷总长度
            
        Returns:
            是否应用了掩码
        """
        # 检查规则是否为实际掩码操作
        if not rule.is_mask_operation:
            self.logger.debug(f"规则{rule.get_description()}：保留操作，跳过")
            return False
        
        # 计算绝对偏移量
        abs_start = rule.absolute_mask_start
        abs_end = rule.absolute_mask_end
        
        # 边界安全检查
        if self._validate_boundaries:
            if not self._validate_mask_boundaries(
                abs_start, abs_end, payload_length, rule, packet_number
            ):
                return False
        
        # 应用掩码
        try:
            # 确保不会超出载荷边界
            actual_start = max(0, min(abs_start, payload_length))
            actual_end = max(actual_start, min(abs_end, payload_length))
            
            if actual_start < actual_end:
                # 应用掩码字节
                for i in range(actual_start, actual_end):
                    payload_buffer[i] = self._mask_byte_value
                
                masked_bytes = actual_end - actual_start
                self._masked_bytes_count += masked_bytes
                self._applied_rules_count += 1
                
                self.logger.debug(
                    f"TLS-{rule.tls_record_type} 掩码应用成功: "
                    f"偏移{actual_start}-{actual_end}, 掩码{masked_bytes}字节"
                )
                
                return True
            else:
                self.logger.debug(f"掩码范围无效: {actual_start}-{actual_end}")
                return False
                
        except Exception as e:
            self.logger.error(f"应用掩码规则失败: {e}")
            return False
    
    def _validate_mask_boundaries(
        self, 
        abs_start: int, 
        abs_end: int, 
        payload_length: int,
        rule: MaskRule,
        packet_number: int
    ) -> bool:
        """验证掩码边界安全性
        
        Args:
            abs_start: 绝对起始偏移
            abs_end: 绝对结束偏移
            payload_length: 载荷长度
            rule: 掩码规则
            packet_number: 包编号
            
        Returns:
            边界是否安全
        """
        if abs_start < 0:
            self.logger.warning(
                f"包{packet_number}掩码起始偏移为负数: {abs_start}"
            )
            self._boundary_violations_count += 1
            return False
        
        if abs_end > payload_length:
            self.logger.warning(
                f"包{packet_number}掩码结束偏移超出载荷范围: "
                f"{abs_end} > {payload_length} (TLS记录类型{rule.tls_record_type})"
            )
            self._boundary_violations_count += 1
            return False
        
        if abs_start >= abs_end:
            self.logger.warning(
                f"包{packet_number}掩码范围无效: {abs_start} >= {abs_end}"
            )
            self._boundary_violations_count += 1
            return False
        
        return True
    
    def _extract_tcp_payload(self, packet: Packet) -> Optional[bytes]:
        """提取TCP载荷
        
        Args:
            packet: 数据包
            
        Returns:
            TCP载荷字节串，如果没有则返回None
        """
        try:
            if packet.haslayer(TCP):
                tcp_layer = packet[TCP]
                if tcp_layer.payload:
                    return bytes(tcp_layer.payload)
            return None
        except Exception as e:
            self.logger.debug(f"提取TCP载荷失败: {e}")
            return None
    
    def _update_packet_payload(self, packet: Packet, new_payload: bytes) -> None:
        """更新数据包的TCP载荷
        
        Args:
            packet: 数据包
            new_payload: 新载荷
        """
        try:
            if packet.haslayer(TCP):
                # 移除旧载荷
                packet[TCP].remove_payload()
                # 添加新载荷
                if new_payload:
                    packet[TCP].add_payload(Raw(load=new_payload))
        except Exception as e:
            self.logger.warning(f"更新数据包载荷失败: {e}")
    
    def _recalculate_packet_checksums(self, packet: Packet) -> None:
        """重新计算数据包校验和
        
        Args:
            packet: 数据包
        """
        try:
            # 删除现有校验和，让Scapy自动重新计算
            if packet.haslayer(IP):
                if hasattr(packet[IP], 'chksum'):
                    del packet[IP].chksum
            
            if packet.haslayer(TCP):
                if hasattr(packet[TCP], 'chksum'):
                    del packet[TCP].chksum
        except Exception as e:
            self.logger.debug(f"重新计算校验和失败: {e}")
    
    def _write_packets(self, packets: List[Packet], output_file: str) -> None:
        """写入数据包到PCAP文件
        
        Args:
            packets: 数据包列表
            output_file: 输出文件路径
        """
        try:
            # 确保输出目录存在
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 写入PCAP文件
            wrpcap(output_file, packets)
            
            self.logger.info(f"成功写入{len(packets)}个包到{output_file}")
            
        except Exception as e:
            self.logger.error(f"写入PCAP文件失败: {e}")
            raise
    
    def _reset_statistics(self) -> None:
        """重置统计信息"""
        self._processed_packets_count = 0
        self._modified_packets_count = 0
        self._masked_bytes_count = 0
        self._applied_rules_count = 0
        self._boundary_violations_count = 0
    
    def _generate_result_statistics(
        self, 
        total_packets: int, 
        processing_time: float
    ) -> Dict[str, Any]:
        """生成处理结果统计信息
        
        Args:
            total_packets: 总包数
            processing_time: 处理时间
            
        Returns:
            统计信息字典
        """
        processing_rate = total_packets / processing_time if processing_time > 0 else 0
        
        return {
            'packets_processed': self._processed_packets_count,
            'packets_modified': self._modified_packets_count,
            'bytes_masked': self._masked_bytes_count,
            'rules_applied': self._applied_rules_count,
            'boundary_violations': self._boundary_violations_count,
            'processing_time_seconds': processing_time,
            'processing_rate_pps': processing_rate,
            'modification_ratio': (
                self._modified_packets_count / self._processed_packets_count 
                if self._processed_packets_count > 0 else 0
            ),
            'mask_byte_value': self._mask_byte_value,
            'checksums_recalculated': self._recalculate_checksums,
            'scapy_version': getattr(__import__('scapy'), '__version__', 'unknown')
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取当前统计信息
        
        Returns:
            统计信息字典
        """
        return {
            'processed_packets': self._processed_packets_count,
            'modified_packets': self._modified_packets_count,
            'masked_bytes': self._masked_bytes_count,
            'applied_rules': self._applied_rules_count,
            'boundary_violations': self._boundary_violations_count
        } 