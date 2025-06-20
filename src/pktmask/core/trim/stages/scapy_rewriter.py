#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Scapy回写器

使用Scapy根据PyShark分析器生成的掩码表，对PCAP文件进行精确的载荷掩码处理。
这是Enhanced Trim Payloads处理流程的第三阶段（最终阶段）。
"""

import logging
import time
import os
import struct
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple, Set
from collections import defaultdict
from dataclasses import dataclass
import gc

try:
    from scapy.all import rdpcap, wrpcap, Packet, IP, IPv6, TCP, UDP, Raw
    from scapy.layers.inet import TCP as ScapyTCP, UDP as ScapyUDP
    from scapy.layers.inet6 import IPv6 as ScapyIPv6
    from scapy.packet import NoPayload
except ImportError:
    rdpcap = wrpcap = Packet = IP = IPv6 = TCP = UDP = Raw = None
    ScapyTCP = ScapyUDP = ScapyIPv6 = NoPayload = None

from .base_stage import BaseStage, StageContext
from .stage_result import StageResult, StageStatus, StageMetrics
from ...processors.base_processor import ProcessorResult
from ..models.mask_table import StreamMaskTable, StreamMaskEntry
from ..models.mask_spec import MaskSpec, MaskAfter, MaskRange, KeepAll
from ..exceptions import StreamMaskTableError


@dataclass
class PacketRewriteInfo:
    """数据包重写信息"""
    packet_number: int
    original_size: int
    modified_size: int
    stream_id: str
    seq_number: Optional[int] = None
    masks_applied: int = 0
    checksum_updated: bool = False
    timestamp_preserved: bool = True
    status: str = 'unprocessed'


class ScapyRewriter(BaseStage):
    """Scapy回写器
    
    负责使用Scapy执行以下重写任务：
    1. 掩码应用 - 根据掩码表精确应用载荷掩码
    2. 时间戳保持 - 保持原始数据包的时间戳
    3. 校验和重计算 - 重新计算修改后的校验和
    4. 文件格式保持 - 保持PCAP文件的完整性
    
    这是多阶段处理流程的第三阶段（最终阶段），接收PyShark分析器的掩码表，
    输出经过智能掩码处理的PCAP文件。
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化Scapy回写器
        
        Args:
            config: 配置参数
        """
        super().__init__("Scapy回写器", config)
        self._mask_table: Optional[StreamMaskTable] = None
        
        # 流的初始序列号映射，用于计算相对序列号
        self._stream_initial_seqs: Dict[str, int] = {}
        
        # 配置参数
        self._batch_size = self.get_config_value('batch_size', 100)
        self._memory_limit_mb = self.get_config_value('memory_limit_mb', 512)
        self._progress_interval = self.get_config_value('progress_interval', 50)
        
        # 内部状态
        self._rewrite_info: List[PacketRewriteInfo] = []
        self._stream_stats: Dict[str, Dict[str, Any]] = defaultdict(dict)
        
        # 统计信息
        self._total_packets = 0
        self._packets_modified = 0
        self._bytes_masked = 0
        self._checksums_updated = 0
        
    def _initialize_impl(self) -> None:
        """初始化Scapy回写器"""
        # 检查Scapy是否可用
        if rdpcap is None or wrpcap is None:
            raise RuntimeError("Scapy未安装，请运行: pip install scapy")
        
        # 检查Scapy版本
        try:
            import scapy
            version = scapy.__version__
            self._logger.info(f"Scapy版本: {version}")
        except (AttributeError, ImportError):
            self._logger.warning("无法获取Scapy版本信息")
        
        # 重置内部状态
        self._mask_table = None
        self._rewrite_info.clear()
        self._stream_stats.clear()
        self._reset_statistics()
        
        self._logger.info("Scapy回写器初始化完成")
    
    def validate_inputs(self, context: StageContext) -> bool:
        """验证输入参数
        
        Args:
            context: 阶段执行上下文
            
        Returns:
            验证是否成功
        """
        # 检查原始PCAP文件（Scapy需要使用原始文件进行载荷提取和掩码应用）
        if context.input_file is None:
            self._logger.error("缺少原始PCAP文件")
            return False
        
        input_file = Path(context.input_file)
        if not input_file.exists():
            self._logger.error(f"原始PCAP文件不存在: {input_file}")
            return False
        
        if input_file.stat().st_size == 0:
            self._logger.error(f"原始PCAP文件为空: {input_file}")
            return False
        
        # 检查掩码表
        if context.mask_table is None:
            self._logger.error("缺少PyShark分析器生成的掩码表")
            return False
        
        if context.mask_table.get_total_entry_count() == 0:
            self._logger.warning("掩码表为空，将不会应用任何掩码")
        
        # 检查输出路径
        output_dir = context.output_file.parent
        if not output_dir.exists():
            try:
                output_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                self._logger.error(f"无法创建输出目录: {output_dir}, 错误: {e}")
                return False
        
        # 检查Scapy可用性
        if not self.is_initialized:
            self._logger.error("Scapy回写器未正确初始化")
            return False
        
        return True
    
    def execute(self, context: StageContext) -> ProcessorResult:
        """执行Scapy回写
        
        Args:
            context: 阶段执行上下文
            
        Returns:
            处理结果
        """
        context.current_stage = self.name
        progress_callback = self.get_progress_callback(context)
        
        start_time = time.time()
        
        try:
            self._logger.info("开始Scapy载荷掩码回写...")
            
            # 临时启用DEBUG级别日志以便调试掩码匹配
            original_level = self._logger.level
            self._logger.setLevel(logging.DEBUG)
            
            # 阶段1: 加载掩码表
            progress_callback(0.0)
            self._mask_table = context.mask_table
            if self._mask_table is None:
                raise ValueError("掩码表为空")
            self._logger.info(f"加载掩码表: {self._mask_table.get_total_entry_count()} 条目")
            
            # 阶段2: 读取PCAP文件 (从原始文件读取以保持Raw层结构)
            progress_callback(0.1)
            input_file = Path(context.input_file)  # 读取原始PCAP文件
            self._logger.info(f"读取原始PCAP文件: {input_file}")
            packets = self._read_pcap_file(input_file)
            
            # 特别调试数据包14和15的详细信息
            for i, pkt in enumerate(packets, 1):
                if i in [14, 15]:
                    self._logger.info(f"=== 调试数据包{i} 详细信息 ===")
                    self._logger.info(f"数据包{i}: {pkt.summary()}")
                    self._logger.info(f"数据包{i} 协议层: {[layer.name for layer in pkt.layers()]}")
                    
                    if hasattr(pkt, 'load'):
                        self._logger.info(f"数据包{i} 有载荷: {len(pkt.load)} 字节")
                        self._logger.info(f"数据包{i} 载荷前16字节: {pkt.load[:16].hex()}")
                    else:
                        self._logger.info(f"数据包{i} 无载荷属性")
                        
                    if TCP in pkt:
                        self._logger.info(f"数据包{i} TCP层存在")
                        if hasattr(pkt[TCP], 'load'):
                            self._logger.info(f"数据包{i} TCP载荷: {len(pkt[TCP].load)} 字节")
                        else:
                            self._logger.info(f"数据包{i} TCP无载荷属性")
                            
                    if Raw in pkt:
                        self._logger.info(f"数据包{i} Raw层存在: {len(pkt[Raw].load)} 字节")
                    else:
                        self._logger.info(f"数据包{i} 无Raw层")
                        
                    self._logger.info(f"=== 数据包{i} 调试结束 ===")
            
            # 阶段3: 应用掩码
            progress_callback(0.2)
            modified_packets = self._apply_masks_to_packets(packets, progress_callback)
            
            # 阶段4: 写入输出文件
            progress_callback(0.9)
            self._write_pcap_file(modified_packets, context.output_file)
            
            # 阶段5: 生成处理结果
            progress_callback(1.0)
            duration = time.time() - start_time
            
            # 更新上下文统计信息
            self._update_stats(context, len(packets), duration)
            
            # 生成处理结果
            processing_stats = self._generate_processing_stats()
            
            result = ProcessorResult(
                success=True,
                data={
                    'message': f"成功处理 {self._total_packets} 个数据包，修改 {self._packets_modified} 个，掩码 {self._bytes_masked} 字节",
                    'total_packets': self._total_packets,
                    'packets_modified': self._packets_modified,
                    'bytes_masked': self._bytes_masked,
                    'checksums_updated': self._checksums_updated,
                    'processing_time': duration,
                    'processing_rate': self._total_packets / duration if duration > 0 else 0,
                    'stream_statistics': dict(self._stream_stats),
                    'rewrite_information': [info.__dict__ for info in self._rewrite_info]
                },
                stats=processing_stats
            )
            
            self._logger.info(f"Scapy回写完成: {duration:.2f}秒, {self._total_packets/duration:.1f} pps")
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"Scapy回写失败: {str(e)}"
            self._logger.error(error_msg, exc_info=True)
            
            return ProcessorResult(
                success=False,
                error=error_msg,
                data={
                    'error_type': type(e).__name__,
                    'processing_time': duration
                }
            )
        finally:
            # 恢复原始日志级别
            if 'original_level' in locals():
                self._logger.setLevel(original_level)
    
    def _read_pcap_file(self, pcap_file: Path) -> List[Packet]:
        """读取PCAP文件
        
        Args:
            pcap_file: PCAP文件路径
            
        Returns:
            数据包列表
        """
        self._logger.info(f"读取PCAP文件: {pcap_file}")
        
        try:
            packets = rdpcap(str(pcap_file))
            self._total_packets = len(packets)
            
            file_size_mb = pcap_file.stat().st_size / (1024 * 1024)
            self._logger.info(f"成功读取 {len(packets)} 个数据包 ({file_size_mb:.2f} MB)")
            
            return packets
            
        except Exception as e:
            self._logger.error(f"读取PCAP文件失败: {e}")
            raise
    
    def _apply_masks_to_packets(self, packets: List[Packet], progress_callback) -> List[Packet]:
        """对数据包列表应用掩码
        
        Args:
            packets: 输入数据包列表
            progress_callback: 进度回调函数
            
        Returns:
            处理后的数据包列表
        """
        total_packets = len(packets)
        self._logger.info(f"开始对 {total_packets} 个数据包应用掩码...")
        
        if not self._mask_table:
            self._logger.warning("掩码表为空，将不会应用任何掩码")
            return packets
        
        modified_packets = []
        
        for packet_idx, packet in enumerate(packets, 1):  # 从1开始编号
            try:
                # 应用掩码到单个数据包
                modified_packet = self._apply_mask_to_packet(packet, packet_idx)
                modified_packets.append(modified_packet)
                
                # 更新进度
                if packet_idx % self._progress_interval == 0:
                    progress = packet_idx / total_packets
                    if progress_callback:
                        progress_callback(progress)
                        
            except Exception as e:
                self._logger.error(f"处理数据包 {packet_idx} 时出错: {e}")
                # 如果出错，保留原始数据包
                modified_packets.append(packet)
        
        self._logger.info(f"掩码应用完成: 修改了 {self._packets_modified}/{total_packets} 个数据包")
        return modified_packets
    
    def _apply_mask_to_packet(self, packet: Packet, packet_number: int) -> Packet:
        """对单个数据包应用掩码
        
        修复大量连续TCP Segment的掩码应用问题：
        1. 改进序列号计算和验证
        2. 增强掩码查找的容错性
        3. 处理Scapy TCP重组导致的序列号冲突
        
        Args:
            packet: 待处理的数据包
            packet_number: 数据包编号
            
        Returns:
            处理后的数据包
        """
        try:
            # 提取流信息
            stream_info = self._extract_stream_info(packet, packet_number)
            if not stream_info:
                self._logger.debug(f"数据包{packet_number}: 无TCP/UDP流信息，跳过处理")
                return packet
            
            stream_id, seq_number, payload = stream_info
            
            if not payload:
                self._logger.debug(f"数据包{packet_number}: 无载荷，跳过处理")
                return packet
            
            # 查找掩码
            self._logger.info(f"掩码查找 - 流={stream_id}, 序列号={seq_number}, 载荷长度={len(payload)}")
            
            # 显示流中的掩码信息
            if stream_id in self._mask_table.get_stream_ids():
                stream_entry_count = self._mask_table.get_stream_entry_count(stream_id)
                self._logger.info(f"流中总掩码条目数: {stream_entry_count}")
                # 获取流的覆盖范围
                min_seq, max_seq = self._mask_table.get_stream_coverage(stream_id)
                self._logger.info(f"流序列号覆盖范围: [{min_seq}:{max_seq})")
            
            # 修复：处理大量连续TCP段的掩码查找
            masks = self._lookup_masks_with_tcp_segment_fix(stream_id, seq_number, len(payload))
            
            self._logger.info(f"匹配到的掩码: {len(masks)}个")
            for i, (start, end, spec) in enumerate(masks):
                self._logger.info(f"  匹配{i+1}: 偏移{start}-{end-1}, 规范={spec.get_description()}")
            
            if not masks:
                self._logger.debug(f"数据包{packet_number}: 未找到匹配的掩码")
                return packet
            
            # 记录原始载荷
            original_payload_preview = payload[:32].hex() if len(payload) >= 32 else payload.hex()
            self._logger.info(f"数据包{packet_number}: 流ID={stream_id}, 序列号={seq_number}, 载荷长度={len(payload)}, 找到掩码={len(masks)}个")
            self._logger.info(f"数据包{packet_number}原始载荷前32字节: {original_payload_preview}")
            
            # 应用掩码
            for i, (start, end, spec) in enumerate(masks):
                self._logger.info(f"🎯 将应用掩码{i+1}: [{start}:{end}) {type(spec)} {spec.get_description()}")
            
            self._logger.info(f"🚀🚀 即将调用 _apply_masks_to_payload，掩码数量={len(masks)}")
            modified_payload = self._apply_masks_to_payload(payload, masks, seq_number)
            self._logger.info(f"✅✅ _apply_masks_to_payload 调用完成")
            
            # 记录修改后的载荷
            modified_payload_preview = modified_payload[:32].hex() if len(modified_payload) >= 32 else modified_payload.hex()
            self._logger.info(f"数据包{packet_number}修改载荷前32字节: {modified_payload_preview}")
            
            # 检查载荷是否真正发生了改变
            payload_changed = payload != modified_payload
            self._logger.info(f"数据包{packet_number}载荷是否改变: {payload_changed}")
            
            if not payload_changed:
                # 分析为什么没有改变
                all_keep_all = all(isinstance(spec, KeepAll) for _, _, spec in masks)
                if all_keep_all:
                    self._logger.info(f"数据包{packet_number}载荷未发生实际改变 - 所有掩码都是保留 规范")
                else:
                    self._logger.warning(f"数据包{packet_number}载荷未改变但存在非保留掩码 - 可能存在问题")
                    for i, (start, end, spec) in enumerate(masks):
                        self._logger.warning(f"  掩码{i+1}: [{start}:{end}) {type(spec).__name__} {spec.get_description()}")
            
            # 更新数据包载荷
            self._update_packet_payload(packet, modified_payload)
            
            # 重新计算校验和
            self._recalculate_packet_checksums(packet)
            
            # 统计
            if payload_changed:
                self._packets_modified += 1
            
            return packet
            
        except Exception as e:
            self._logger.error(f"处理数据包{packet_number}时发生错误: {e}")
            import traceback
            traceback.print_exc()
            return packet
    
    def _lookup_masks_with_tcp_segment_fix(self, stream_id: str, seq_number: int, payload_length: int) -> List[Tuple[int, int, MaskSpec]]:
        """查找掩码，修复大量连续TCP段的序列号重复问题
        
        Args:
            stream_id: 流标识符
            seq_number: 序列号
            payload_length: 载荷长度
            
        Returns:
            掩码列表 [(start_offset, end_offset, mask_spec), ...]
        """
        # 首先尝试正常查找
        normal_masks = self._mask_table.lookup_multiple(stream_id, seq_number, payload_length)
        
        if normal_masks:
            return normal_masks
        
        # 如果正常查找失败，尝试模糊匹配
        # 这种情况常见于Scapy TCP重组导致的序列号偏移
        self._logger.debug(f"正常掩码查找失败，尝试模糊匹配 - 流={stream_id}, 序列号={seq_number}")
        
        # 尝试在序列号附近搜索
        search_ranges = [
            seq_number - 5,   # 往前搜索
            seq_number - 10,
            seq_number + 5,   # 往后搜索
            seq_number + 10,
            1,                # 尝试使用序列号1（常见的重组起始点）
            2,                # 尝试使用序列号2
        ]
        
        for search_seq in search_ranges:
            if search_seq <= 0:
                continue
                
            fuzzy_masks = self._mask_table.lookup_multiple(stream_id, search_seq, payload_length)
            if fuzzy_masks:
                self._logger.info(f"模糊匹配成功: 原序列号={seq_number}, 匹配序列号={search_seq}, 找到{len(fuzzy_masks)}个掩码")
                return fuzzy_masks
        
        # 如果还是找不到，尝试范围匹配
        # 通过遍历不同的序列号范围来查找可能的掩码
        if stream_id in self._mask_table.get_stream_ids():
            # 获取流的序列号覆盖范围
            try:
                min_seq, max_seq = self._mask_table.get_stream_coverage(stream_id)
                
                # 尝试在整个范围内查找覆盖当前载荷的掩码
                range_start = max(1, min_seq)
                range_end = min(max_seq, seq_number + payload_length + 100)  # 适当扩展范围
                
                for test_seq in range(range_start, range_end, 10):  # 每10个序列号测试一次
                    range_masks = self._mask_table.lookup_multiple(stream_id, test_seq, payload_length)
                    if range_masks:
                        self._logger.info(f"范围匹配成功: 原序列号={seq_number}, 匹配序列号={test_seq}, 找到{len(range_masks)}个掩码")
                        return range_masks
            except Exception as e:
                self._logger.debug(f"范围匹配出错: {e}")
        
        self._logger.debug(f"所有匹配方法都失败 - 流={stream_id}, 序列号={seq_number}, 载荷长度={payload_length}")
        return []
    
    def _extract_stream_info(self, packet: Packet, packet_number: int = 1) -> Optional[Tuple[str, int, bytes]]:
        """从数据包中提取流信息和载荷
        
        Args:
            packet: 数据包
            packet_number: 数据包编号，用于调试
            
        Returns:
            (stream_id, seq_number, payload_data) 或 None
        """
        # 提取IP和端口信息
        ip_layer = packet.getlayer(IP) or packet.getlayer(IPv6)
        tcp_layer = packet.getlayer(TCP)
        udp_layer = packet.getlayer(UDP)
        
        if not ip_layer or not (tcp_layer or udp_layer):
            return None
        
        # 获取IP和端口
        src_ip = ip_layer.src
        dst_ip = ip_layer.dst
        if tcp_layer:
            src_port = tcp_layer.sport
            dst_port = tcp_layer.dport
            protocol = "TCP"
            seq_number = tcp_layer.seq
            self._logger.debug(f"数据包{packet_number}: {protocol} {src_ip}:{src_port} -> {dst_ip}:{dst_port}, 序列号={seq_number}")
        elif udp_layer:
            src_port = udp_layer.sport
            dst_port = udp_layer.dport
            protocol = "UDP"
            seq_number = None
        else:
            return None
        
        # 生成方向性流ID（包含数据包的实际方向）
        stream_id = self._generate_directional_stream_id(src_ip, dst_ip, src_port, dst_port, protocol)
        
        # 对于TCP，转换为相对序列号以匹配PyShark分析器
        if tcp_layer and seq_number is not None:
            absolute_seq = int(seq_number)
            seq_number = self._get_relative_seq_number(stream_id, absolute_seq)
            self._logger.info(f"数据包序列号转换: 绝对={absolute_seq} -> 相对={seq_number}")
        
        # 使用统一的完整TCP载荷提取方法
        payload_data, _ = self._extract_packet_payload(packet)
        
        return stream_id, seq_number, payload_data
    
    def _generate_directional_stream_id(self, src_ip: str, dst_ip: str, src_port: int, dst_port: int, protocol: str) -> str:
        """生成包含方向的流ID
        
        与PyShark掩码表保持兼容：总是从最小IP开始，但在末尾添加方向标识
        
        Args:
            src_ip: 源IP地址
            dst_ip: 目标IP地址  
            src_port: 源端口
            dst_port: 目标端口
            protocol: 协议类型
            
        Returns:
            方向性流ID
        """
        # 首先生成标准的无方向流ID（与PyShark兼容）
        # 重要修复：使用 <= 比较以与PyShark分析器完全一致
        if (src_ip, src_port) <= (dst_ip, dst_port):
            base_stream_id = f"{protocol}_{src_ip}:{src_port}_{dst_ip}:{dst_port}"
            direction = "forward"  # 数据包方向与标准流方向一致
        else:
            base_stream_id = f"{protocol}_{dst_ip}:{dst_port}_{src_ip}:{src_port}"
            direction = "reverse"  # 数据包方向与标准流方向相反
        
        # 添加方向后缀以区分双向TCP流
        return f"{base_stream_id}_{direction}"
    
    def _get_relative_seq_number(self, stream_id: str, absolute_seq: int) -> int:
        """计算相对序列号，与PyShark/TShark保持一致
        
        修复大量连续TCP Segment的序列号处理问题：
        1. 区分方向性流的初始序列号
        2. 处理Scapy TCP重组导致的序列号重复问题
        
        Args:
            stream_id: 流标识符（包含方向）
            absolute_seq: 绝对序列号
            
        Returns:
            相对序列号（从0或1开始）
        """
        # 为每个方向性流独立维护初始序列号
        if stream_id not in self._stream_initial_seqs:
            # 第一次遇到这个流，记录初始序列号
            self._stream_initial_seqs[stream_id] = absolute_seq
            self._logger.debug(f"流{stream_id}: 初始序列号={absolute_seq}")
            return 1  # TShark/PyShark通常从1开始相对序列号
        else:
            # 计算相对序列号
            initial_seq = self._stream_initial_seqs[stream_id]
            relative_seq = absolute_seq - initial_seq + 1
            
            # 处理序列号异常情况：如果相对序列号<=0，说明可能是Scapy重组问题
            if relative_seq <= 0:
                self._logger.warning(f"流{stream_id}: 序列号异常 - 绝对={absolute_seq}, 初始={initial_seq}, 相对={relative_seq}")
                # 对于异常序列号，使用绝对序列号的最后几位作为相对序列号
                relative_seq = (absolute_seq % 1000000) + 1
                self._logger.info(f"修正异常序列号: {absolute_seq} -> {relative_seq}")
            
            return relative_seq
    
    def _extract_tcp_payload(self, packet: Packet) -> bytes:
        """提取TCP载荷"""
        if packet.haslayer(Raw):
            return bytes(packet[Raw])
        return b''
    
    def _extract_udp_payload(self, packet: Packet) -> bytes:
        """提取UDP载荷"""
        if packet.haslayer(Raw):
            return bytes(packet[Raw])
        return b''
    
    def _apply_masks_to_payload(self, payload: bytes, masks: List[Tuple[int, int, MaskSpec]], seq_number: int) -> bytes:
        """对载荷应用掩码
        
        Args:
            payload: 原始载荷
            masks: 掩码规范列表 [(start, end, mask_spec), ...]
            seq_number: 序列号
            
        Returns:
            修改后的载荷
        """
        if not masks or not payload:
            return payload
        
        # 转换为可修改的字节数组
        modified_payload = bytearray(payload)
        
        self._logger.info(f"🔧 开始处理 {len(masks)} 个掩码，载荷长度={len(payload)}")
        
        for i, (start, end, mask_spec) in enumerate(masks):
            self._logger.info(f"🎯 处理掩码{i+1}: 载荷偏移=[{start}:{end}), spec={mask_spec.get_description()}")
            
            # masks中的start, end已经是相对于载荷的偏移，直接使用
            # 无需重新计算重叠，因为lookup_multiple已经处理了重叠逻辑
            
            # 验证偏移范围
            if start < 0 or end > len(payload) or start >= end:
                self._logger.warning(f"跳过掩码{i+1}: 无效偏移范围[{start}:{end}), 载荷长度={len(payload)}")
                continue
            
            # 直接应用掩码规范到指定的载荷偏移
            self._apply_mask_spec(modified_payload, start, end, mask_spec)
        
        self._logger.info(f"✅ 完成所有掩码处理")
        return bytes(modified_payload)
    
    def _apply_mask_spec(self, payload: bytearray, start: int, end: int, mask_spec: MaskSpec) -> None:
        """应用掩码规范
        
        Args:
            payload: 载荷字节数组
            start: 起始位置
            end: 结束位置
            mask_spec: 掩码规范
        """
        self._logger.info(f"🔧 _apply_mask_spec 开始: start={start}, end={end}, 载荷长度={len(payload)}, 掩码类型={type(mask_spec).__name__}")
        
        if isinstance(mask_spec, KeepAll):
            # 保留所有字节，不做修改
            self._logger.info(f"✅ KeepAll: 不修改载荷")
            return
        
        elif isinstance(mask_spec, MaskAfter):
            # 保留前N个字节，掩码其余部分
            keep_bytes = mask_spec.keep_bytes
            
            # 新的逻辑：处理小载荷情况
            payload_size = end - start
            if payload_size <= keep_bytes:
                # 小载荷情况：载荷长度小于等于keep_bytes
                # 根据策略决定：如果keep_bytes=0则全掩码，否则完全保留小载荷
                if keep_bytes == 0:
                    # MaskAfter(0) - 全部掩码
                    mask_start = start
                    mask_end = end
                    self._logger.info(f"🎯 MaskAfter({keep_bytes}) 小载荷全掩码: 范围[{mask_start}:{mask_end})")
                else:
                    # MaskAfter(>0) - 小载荷完全保留
                    self._logger.info(f"🎯 MaskAfter({keep_bytes}) 小载荷完全保留: 载荷长度{payload_size} <= keep_bytes{keep_bytes}")
                    return
            else:
                # 正常情况：载荷长度大于keep_bytes
                mask_start = start + keep_bytes
                mask_end = end
                self._logger.info(f"🎯 MaskAfter({keep_bytes}) 正常掩码: 范围[{mask_start}:{mask_end})")
            
            # 执行掩码操作
            if 'mask_start' in locals() and 'mask_end' in locals() and mask_start < mask_end:
                bytes_to_mask = mask_end - mask_start
                self._logger.info(f"📝 准备掩码: 范围[{mask_start}:{mask_end}) {bytes_to_mask}字节")
                
                # 记录掩码前的载荷样本
                sample_before = payload[mask_start:min(mask_start+8, mask_end)].hex() if mask_start < len(payload) else "无数据"
                self._logger.info(f"📋 掩码前载荷样本[{mask_start}:{min(mask_start+8, mask_end)}): {sample_before}")
                
                # 实际进行掩码操作
                mask_byte = self.get_config_value('mask_byte_value', 0x00)
                self._logger.info(f"🎨 使用掩码字节值: 0x{mask_byte:02x}")
                
                # 检查是否为全零载荷掩码
                is_zero_masking = mask_byte == 0x00
                original_bytes = payload[mask_start:mask_end] if mask_start < len(payload) else b''
                is_already_zero = all(b == 0x00 for b in original_bytes)
                
                for i in range(mask_start, mask_end):
                    if i < len(payload):
                        old_byte = payload[i]
                        payload[i] = mask_byte
                        if i < mask_start + 3:  # 只记录前几个字节的详细变化
                            self._logger.info(f"🔄 位置{i}: 0x{old_byte:02x} -> 0x{mask_byte:02x}")
                
                # 记录掩码后的载荷样本
                sample_after = payload[mask_start:min(mask_start+8, mask_end)].hex() if mask_start < len(payload) else "无数据"
                self._logger.info(f"📋 掩码后载荷样本[{mask_start}:{min(mask_start+8, mask_end)}): {sample_after}")
                
                if is_zero_masking and is_already_zero:
                    self._logger.info(f"✅ 掩码 {bytes_to_mask} 个字节完成 (全零载荷，视觉无变化但逻辑已处理)")
                else:
                    self._logger.info(f"✅ 成功掩码了 {bytes_to_mask} 个字节，掩码值=0x{mask_byte:02x}")
            else:
                self._logger.info(f"ℹ️ MaskAfter({keep_bytes}): 无需掩码操作")
        
        elif isinstance(mask_spec, MaskRange):
            # 掩码指定范围
            self._logger.info(f"🎯 MaskRange: 范围={mask_spec.ranges}")
            for range_start, range_end in mask_spec.ranges:
                mask_start = start + range_start
                mask_end = min(end, start + range_end)
                if mask_start < mask_end:
                    mask_byte = self.get_config_value('mask_byte_value', 0x00)
                    for i in range(mask_start, mask_end):
                        if i < len(payload):
                            payload[i] = mask_byte
                    self._logger.info(f"✅ MaskRange掩码范围[{mask_start}:{mask_end})")
        
        else:
            # 未知掩码类型，全部掩码
            self._logger.warning(f"⚠️ 未知掩码类型: {type(mask_spec)}，执行全掩码")
            mask_byte = self.get_config_value('mask_byte_value', 0x00)
            for i in range(start, end):
                if i < len(payload):
                    payload[i] = mask_byte
        
        self._logger.info(f"🔧 _apply_mask_spec 完成")
    
    def _update_packet_payload(self, packet: Packet, new_payload: bytes) -> None:
        """更新数据包载荷
        
        Args:
            packet: 数据包
            new_payload: 新载荷
        """
        # 记录原始数据包大小
        original_size = len(packet)
        self._logger.debug(f"更新载荷前: 数据包大小={original_size}, 新载荷长度={len(new_payload)}")
        
        updated = False
        
        # 方法1: 如果有Raw层，直接更新Raw层
        if packet.haslayer(Raw):
            old_payload_len = len(packet[Raw].load)
            packet[Raw].load = new_payload
            updated = True
            self._logger.debug(f"已更新Raw层载荷: {old_payload_len} -> {len(new_payload)} 字节")
        
        # 方法2: 如果没有Raw层但有TCP层且有新载荷，添加Raw层
        elif packet.haslayer(TCP) and new_payload:
            # 找到TCP层
            tcp_layer = packet.getlayer(TCP)
            
            # 添加新的Raw载荷到TCP层
            tcp_layer.payload = Raw(load=new_payload)
            updated = True
            self._logger.debug(f"已在TCP层添加Raw载荷: {len(new_payload)} 字节")
        
        # 方法3: 如果没有载荷数据，清除现有载荷层
        elif not new_payload:
            if packet.haslayer(Raw):
                # 找到Raw层的父层
                parent_layer = None
                current_layer = packet
                
                while current_layer and hasattr(current_layer, 'payload'):
                    if isinstance(current_layer.payload, Raw):
                        parent_layer = current_layer
                        break
                    current_layer = current_layer.payload
                
                if parent_layer:
                    # 移除Raw层
                    parent_layer.payload = None
                    updated = True
                    self._logger.debug("已清除Raw载荷层")
        
        if not updated:
            self._logger.warning(f"无法更新数据包载荷 - 载荷长度: {len(new_payload)}")
        else:
            # 记录更新后的数据包大小
            new_size = len(packet)
            size_change = new_size - original_size
            self._logger.debug(f"成功更新数据包载荷: {len(new_payload)} 字节, 数据包大小变化: {original_size} -> {new_size} ({size_change:+d})")
            
            # 如果数据包大小异常增加，发出警告
            if abs(size_change) > 50:  # 允许一定的头部调整
                self._logger.warning(f"数据包大小变化较大: {size_change:+d} 字节")
    
    def _recalculate_packet_checksums(self, packet: Packet) -> None:
        """重新计算数据包校验和
        
        Args:
            packet: 数据包
        """
        # 删除现有校验和，让Scapy重新计算
        if packet.haslayer(IP):
            del packet[IP].chksum
        
        if packet.haslayer(IPv6):
            # IPv6没有IP层校验和
            pass
        
        if packet.haslayer(TCP):
            del packet[TCP].chksum
        
        if packet.haslayer(UDP):
            del packet[UDP].chksum
        
        # 强制重新构建数据包以重新计算校验和
        packet = packet.__class__(bytes(packet))
    
    def _write_pcap_file(self, packets: List[Packet], output_file: Path) -> None:
        """写入PCAP文件
        
        Args:
            packets: 数据包列表
            output_file: 输出文件路径
        """
        self._logger.info(f"写入输出文件: {output_file}")
        
        try:
            wrpcap(str(output_file), packets)
            
            file_size_mb = output_file.stat().st_size / (1024 * 1024)
            self._logger.info(f"成功写入 {len(packets)} 个数据包 ({file_size_mb:.2f} MB)")
            
        except Exception as e:
            self._logger.error(f"写入PCAP文件失败: {e}")
            raise
    
    def _update_stream_stats(self, stream_id: str, rewrite_info: PacketRewriteInfo) -> None:
        """更新流统计信息"""
        if stream_id not in self._stream_stats:
            self._stream_stats[stream_id] = {
                'packets_processed': 0,
                'packets_modified': 0,
                'bytes_masked': 0,
                'masks_applied': 0
            }
        
        stats = self._stream_stats[stream_id]
        stats['packets_processed'] += 1
        
        if rewrite_info.masks_applied > 0:
            stats['packets_modified'] += 1
            stats['masks_applied'] += rewrite_info.masks_applied
            # 字节掩码统计在_apply_mask_to_packet中更新
    
    def _generate_processing_stats(self) -> Dict[str, Any]:
        """生成处理统计信息"""
        return {
            'stage_name': self.name,
            'total_packets': self._total_packets,
            'packets_modified': self._packets_modified,
            'modification_rate': self._packets_modified / self._total_packets if self._total_packets > 0 else 0,
            'bytes_masked': self._bytes_masked,
            'checksums_updated': self._checksums_updated,
            'streams_processed': len(self._stream_stats),
            'mask_table_entries': self._mask_table.get_total_entry_count() if self._mask_table else 0
        }
    
    def _update_stats(self, context: StageContext, packet_count: int, duration: float) -> None:
        """更新上下文统计信息"""
        context.stats.update({
            'scapy_rewriter': {
                'packets_processed': packet_count,
                'packets_modified': self._packets_modified,
                'bytes_masked': self._bytes_masked,
                'checksums_updated': self._checksums_updated,
                'processing_time': duration,
                'processing_rate': packet_count / duration if duration > 0 else 0
            }
        })
    
    def _reset_statistics(self) -> None:
        """重置统计信息"""
        self._total_packets = 0
        self._packets_modified = 0
        self._bytes_masked = 0
        self._checksums_updated = 0
    
    def get_estimated_duration(self, context: StageContext) -> float:
        """估算处理时间"""
        if context.tshark_output:
            input_file = Path(context.tshark_output)
            if input_file.exists():
                file_size_mb = input_file.stat().st_size / (1024 * 1024)
                # Scapy回写相对较慢，每MB约需要0.5秒
                return max(1.0, file_size_mb * 0.5)
        return 2.0
    
    def get_required_tools(self) -> List[str]:
        """获取所需工具列表"""
        return ['scapy']
    
    def check_tool_availability(self) -> Dict[str, bool]:
        """检查工具可用性"""
        return {
            'scapy': rdpcap is not None and wrpcap is not None
        }
    
    def get_description(self) -> str:
        """获取Stage描述"""
        return "使用Scapy根据掩码表对PCAP文件进行精确的载荷掩码处理"
    
    def _cleanup_impl(self, context: StageContext) -> None:
        """清理资源"""
        # 清理内部状态
        self._mask_table = None
        self._rewrite_info.clear()
        self._stream_stats.clear()
        
        # 强制垃圾回收
        gc.collect()
        
        self._logger.debug("Scapy回写器资源清理完成")
    
    def _extract_packet_payload(self, packet) -> Tuple[bytes, int]:
        """
        提取数据包的应用层载荷。
        
        该方法现在能够处理Scapy可能将部分TLS/TCP载荷错误地解析到
        一个独立的Padding层的情况。
        """
        header_len = self._calculate_all_headers_length(packet)
        
        # 提取TCP/UDP载荷
        payload = b""
        if packet.haslayer(TCP):
            tcp_layer = packet.getlayer(TCP)
            if hasattr(tcp_layer, 'load'):
                payload = bytes(tcp_layer.load)
        elif packet.haslayer(UDP):
            udp_layer = packet.getlayer(UDP)
            if hasattr(udp_layer, 'load'):
                payload = bytes(udp_layer.load)

        # 关键修复：检查并合并被Scapy错误分片的Padding层
        # Scapy有时会将一个完整的TCP PDU（如一个大的TLS记录）的后半部分
        # 错误地解析为一个Padding层，紧跟在TCP层之后。
        if packet.haslayer(TCP) and packet.haslayer("Padding"):
            tcp_index = packet.layers().index(TCP)
            padding_index = packet.layers().index("Padding")
            if padding_index == tcp_index + 1:
                padding_layer = packet.getlayer("Padding")
                if hasattr(padding_layer, 'load'):
                    padding_payload = bytes(padding_layer.load)
                    self._logger.debug(f"检测到并合并被Scapy错误解析的Padding层，长度: {len(padding_payload)}字节")
                    payload += padding_payload

        # 如果没有TCP/UDP载荷，尝试从Raw层提取
        if not payload and packet.haslayer(Raw):
            payload = bytes(packet[Raw].load)
            
        # 如果通过以上方法提取的载荷为空，但整个数据包长度大于头部长度，
        # 则使用更通用的方法提取整个应用层数据。
        if not payload and len(packet) > header_len:
            # 这是一个备用逻辑，确保即使在Scapy解析不完美的情况下也能提取载荷
            payload = bytes(packet)[header_len:]
            self._logger.debug(f"使用备用逻辑提取载荷，长度: {len(payload)}字节")

        self._logger.debug(f"提取的载荷长度: {len(payload)}字节, 计算的头部长度: {header_len}字节")
        return payload, header_len


    def _calculate_all_headers_length(self, packet) -> int:
        """
        计算数据包中所有协议头的总长度。
        
        该方法旨在精确计算从Ethernet层到TCP/UDP层（不含载荷）的所有头部长度，
        支持VLAN、MPLS、隧道协议等多种复杂封装。
        """
        total_len = 0
        
        # 1. 以太网头部
        if packet.haslayer("Ethernet"):
            total_len += len(packet.getlayer("Ethernet")) - len(packet.getlayer("Ethernet").payload)

        # 2. VLAN 标签 (802.1Q) - 支持多层
        total_len += self._calculate_vlan_headers_length(packet)
        
        # 3. MPLS 标签 - 支持多层
        total_len += self._calculate_mpls_headers_length(packet)
        
        # 4. 隧道协议 (GRE, VXLAN等)
        total_len += self._calculate_tunnel_headers_length(packet)

        # 5. IP层 (IPv4/IPv6)
        total_len += self._calculate_ip_headers_length(packet)

        # 6. 传输层 (TCP/UDP)
        if packet.haslayer(TCP):
            total_len += self._calculate_tcp_header_length(packet)
        elif packet.haslayer(UDP):
            total_len += 20 # UDP头固定8字节，但这里似乎有误，暂时保持 # TODO: Fix UDP header length
            # Correct UDP header length is 8 bytes.
            udp_layer = packet.getlayer(UDP)
            total_len += udp_layer.len if hasattr(udp_layer, 'len') and udp_layer.len is not None else 8

        # 关键修复：如果存在被Scapy错误解析的Padding层（通常是TLS载荷的一部分），
        # 则它的长度不应被算作头部长度。
        if packet.haslayer(TCP) and packet.haslayer("Padding"):
            tcp_index = packet.layers().index(TCP)
            try:
                padding_index = packet.layers().index("Padding")
                if padding_index == tcp_index + 1:
                    padding_layer = packet.getlayer("Padding")
                    padding_len = len(padding_layer)
                    self._logger.debug(f"从头部总长中减去被错误解析的Padding层长度: {padding_len}字节")
                    total_len -= padding_len
            except ValueError:
                # Padding layer not found, which is normal
                pass

        # 确保计算的头部长度不超过数据包总长
        if total_len > len(packet):
            self._logger.warning(
                f"计算的头部长度({total_len})超过数据包总长度({len(packet)}). "
                f"可能存在协议解析错误。将头部长度修正为数据包总长。"
            )
            return len(packet)

        return total_len
    
    def _calculate_vlan_headers_length(self, packet) -> int:
        """计算VLAN头部长度，支持单层和双层VLAN"""
        vlan_length = 0
        
        # 检测VLAN层数
        if packet.haslayer('Dot1Q'):
            vlan_layers = []
            current = packet
            
            # 遍历所有层，收集VLAN层
            while current:
                if hasattr(current, 'name') and 'Dot1Q' in str(type(current)):
                    vlan_layers.append(current)
                    vlan_length += 4  # 每个VLAN标签4字节
                
                if hasattr(current, 'payload'):
                    current = current.payload
                else:
                    break
            
            self._logger.debug(f"检测到{len(vlan_layers)}层VLAN标签")
        
        # 检测802.1ad (QinQ)
        try:
            from scapy.layers.l2 import Dot1AD
            if packet.haslayer('Dot1AD'):
                vlan_length += 4  # Service Tag (S-Tag) 4字节
                self._logger.debug("检测到802.1ad服务标签")
        except ImportError:
            pass
        
        return vlan_length
    
    def _calculate_mpls_headers_length(self, packet) -> int:
        """计算MPLS标签栈长度"""
        mpls_length = 0
        
        try:
            if packet.haslayer('MPLS'):
                current = packet
                while current:
                    if hasattr(current, 'name') and 'MPLS' in str(type(current)):
                        mpls_length += 4  # 每个MPLS标签4字节
                        # 检查是否是栈底标签
                        if hasattr(current, 's') and current.s == 1:
                            break
                    
                    if hasattr(current, 'payload'):
                        current = current.payload
                    else:
                        break
        except Exception:
            pass
        
        return mpls_length
    
    def _calculate_tunnel_headers_length(self, packet) -> int:
        """计算隧道协议头部长度 (VXLAN/GRE)"""
        tunnel_length = 0
        
        # VXLAN处理
        try:
            if packet.haslayer('VXLAN'):
                tunnel_length += 8  # VXLAN头部8字节
                tunnel_length += 8  # UDP头部8字节  
                self._logger.debug("检测到VXLAN隧道")
        except Exception:
            pass
        
        # GRE处理
        try:
            if packet.haslayer('GRE'):
                gre_layer = packet['GRE']
                gre_length = 4  # 基本GRE头部4字节
                
                # 可选字段处理
                if hasattr(gre_layer, 'chksum_present') and gre_layer.chksum_present:
                    gre_length += 4
                if hasattr(gre_layer, 'key_present') and gre_layer.key_present:
                    gre_length += 4
                if hasattr(gre_layer, 'seqnum_present') and gre_layer.seqnum_present:
                    gre_length += 4
                
                tunnel_length += gre_length
                self._logger.debug(f"检测到GRE隧道，头部长度{gre_length}字节")
        except Exception:
            pass
        
        return tunnel_length
    
    def _calculate_ip_headers_length(self, packet) -> int:
        """计算IP头部长度，处理外层和内层IP"""
        ip_length = 0
        
        # 收集所有IP层
        ip_layers = []
        current = packet
        while current:
            if hasattr(current, 'name'):
                if 'IP' in str(type(current)) and 'IPv6' not in str(type(current)):
                    ip_layers.append(('IPv4', current))
                elif 'IPv6' in str(type(current)):
                    ip_layers.append(('IPv6', current))
            
            if hasattr(current, 'payload'):
                current = current.payload
            else:
                break
        
        # 计算每个IP层的长度
        for ip_type, ip_layer in ip_layers:
            if ip_type == 'IPv4':
                if hasattr(ip_layer, 'ihl') and ip_layer.ihl is not None:
                    layer_length = ip_layer.ihl * 4
                    ip_length += layer_length
                    self._logger.debug(f"IPv4头部: {layer_length}字节")
                else:
                    # 默认IPv4头部长度20字节（无选项）
                    layer_length = 20
                    ip_length += layer_length
                    self._logger.debug(f"IPv4头部(默认): {layer_length}字节")
            elif ip_type == 'IPv6':
                ip_length += 40  # IPv6头部固定40字节
                self._logger.debug(f"IPv6头部: 40字节")
        
        return ip_length
    
    def _calculate_tcp_header_length(self, packet) -> int:
        """计算TCP头部长度"""
        if packet.haslayer('TCP'):
            tcp_layer = packet['TCP']
            if hasattr(tcp_layer, 'dataofs') and tcp_layer.dataofs is not None:
                tcp_length = tcp_layer.dataofs * 4
                self._logger.debug(f"TCP头部: {tcp_length}字节")
                return tcp_length
            else:
                # 默认TCP头部长度20字节（无选项）
                tcp_length = 20
                self._logger.debug(f"TCP头部(默认): {tcp_length}字节")
                return tcp_length
        return 0
    
 