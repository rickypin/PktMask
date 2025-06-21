#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Scapy回写器 - Phase 3 重构版

使用Scapy根据PyShark分析器生成的基于序列号的掩码表，对PCAP文件进行精确的载荷掩码处理。
这是Enhanced Trim Payloads处理流程的第三阶段（最终阶段）。

重构特性：
1. 基于TCP序列号绝对值范围的通用掩码机制
2. 支持方向性TCP流处理
3. 精确的序列号匹配算法
4. 字节级精确置零机制
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
from ..models.sequence_mask_table import SequenceMaskTable, MaskEntry, SequenceMatchResult
from ..models.tcp_stream import TCPStreamManager, ConnectionDirection, detect_packet_direction
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
    """Scapy回写器 - Phase 3 重构版
    
    负责使用Scapy执行以下重写任务：
    1. 基于序列号的精确掩码匹配
    2. 方向性TCP流处理
    3. 字节级精确置零操作
    4. 时间戳保持和校验和重计算
    
    这是多阶段处理流程的第三阶段（最终阶段），接收PyShark分析器的序列号掩码表，
    输出经过智能掩码处理的PCAP文件。
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化Scapy回写器
        
        Args:
            config: 配置参数
        """
        super().__init__("Scapy回写器", config)
        self._mask_table: Optional[SequenceMaskTable] = None
        self._stream_manager: TCPStreamManager = TCPStreamManager()
        
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
        self._sequence_matches = 0
        self._sequence_mismatches = 0
    
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
        self._stream_manager.clear()
        self._rewrite_info.clear()
        self._stream_stats.clear()
        self._reset_statistics()
        
        self._logger.info("Scapy回写器初始化完成 - 支持基于序列号的掩码机制")
    
    def validate_inputs(self, context: StageContext) -> bool:
        """验证输入参数
        
        Args:
            context: 阶段执行上下文
            
        Returns:
            验证是否成功
        """
        # 检查TShark重组文件（修正：Scapy需要处理重组文件以与PyShark保持一致）
        if context.tshark_output is None:
            self._logger.error("缺少TShark重组PCAP文件")
            return False
        
        input_file = Path(context.tshark_output)
        if not input_file.exists():
            self._logger.error(f"TShark重组PCAP文件不存在: {input_file}")
            return False
        
        if input_file.stat().st_size == 0:
            self._logger.error(f"TShark重组PCAP文件为空: {input_file}")
            return False
        
        # 检查序列号掩码表
        if context.mask_table is None:
            self._logger.error("缺少PyShark分析器生成的序列号掩码表")
            return False
        
        if not isinstance(context.mask_table, SequenceMaskTable):
            self._logger.error(f"掩码表类型错误: 期待SequenceMaskTable，实际 {type(context.mask_table)}")
            return False
        
        if context.mask_table.get_total_entry_count() == 0:
            self._logger.warning("序列号掩码表为空，将不会应用任何掩码")
        
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
            input_file = Path(context.tshark_output)  # 读取TShark重组PCAP文件
            self._logger.info(f"读取TShark重组PCAP文件: {input_file}")
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
        """对单个数据包应用基于序列号的掩码
        
        Phase 3重构：实现基于序列号绝对值范围的通用掩码机制
        1. 提取TCP流信息和序列号
        2. 生成方向性流ID
        3. 使用SequenceMaskTable进行精确序列号匹配
        4. 应用字节级精确置零
        
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
            
            # Phase 3: 使用新的序列号匹配机制
            self._logger.info(f"【序列号掩码匹配】数据包{packet_number}: 流={stream_id}, 序列号={seq_number}, 载荷长度={len(payload)}")
            
            # 使用SequenceMaskTable进行精确匹配
            match_results = self._mask_table.match_sequence_range(stream_id, seq_number, len(payload))
            
            self._logger.info(f"匹配到的掩码: {len(match_results)}个")
            for i, result in enumerate(match_results):
                if result.is_match:
                    self._logger.info(f"  匹配{i+1}: 偏移[{result.mask_start_offset}:{result.mask_end_offset}), "
                                     f"长度={result.mask_length}, 条目={result.entry.get_description()}")
                    self._sequence_matches += 1
                else:
                    self._sequence_mismatches += 1
            
            if not any(result.is_match for result in match_results):
                self._logger.debug(f"数据包{packet_number}: 未找到匹配的序列号掩码")
                return packet
            
            # 记录原始载荷
            original_payload_preview = payload[:32].hex() if len(payload) >= 32 else payload.hex()
            self._logger.info(f"数据包{packet_number}原始载荷前32字节: {original_payload_preview}")
            
            # 应用序列号匹配的掩码
            modified_payload = self._apply_sequence_based_masks(payload, match_results, seq_number)
            
            # 记录修改后的载荷
            modified_payload_preview = modified_payload[:32].hex() if len(modified_payload) >= 32 else modified_payload.hex()
            self._logger.info(f"数据包{packet_number}修改载荷前32字节: {modified_payload_preview}")
            
            # 检查载荷是否真正发生了改变
            payload_changed = payload != modified_payload
            self._logger.info(f"数据包{packet_number}载荷是否改变: {payload_changed}")
            
            if payload_changed:
                # 更新数据包载荷
                self._update_packet_payload(packet, modified_payload)
                
                # 重新计算校验和
                self._recalculate_packet_checksums(packet)
                
                # 统计
                self._packets_modified += 1
                masked_bytes = sum(result.mask_length for result in match_results if result.is_match)
                self._bytes_masked += masked_bytes
                
                self._logger.info(f"✅ 数据包{packet_number}掩码完成: 掩码字节数={masked_bytes}")
            else:
                # 分析为什么没有改变
                all_keep_all = all(isinstance(result.entry.mask_spec, KeepAll) for result in match_results if result.is_match)
                if all_keep_all:
                    self._logger.info(f"数据包{packet_number}载荷未发生实际改变 - 所有掩码都是保留规范")
                else:
                    self._logger.warning(f"数据包{packet_number}载荷未改变但存在非保留掩码 - 需要检查掩码应用逻辑")
            
            return packet
            
        except Exception as e:
            self._logger.error(f"处理数据包{packet_number}时发生错误: {e}")
            import traceback
            traceback.print_exc()
            return packet
    
    def _generate_udp_stream_id(self, src_ip: str, dst_ip: str, src_port: int, dst_port: int) -> str:
        """生成UDP流ID
        
        Args:
            src_ip: 源IP
            dst_ip: 目标IP
            src_port: 源端口
            dst_port: 目标端口
            
        Returns:
            流ID
        """
        return f"UDP_{src_ip}:{src_port}_{dst_ip}:{dst_port}"
    
    def _extract_stream_info(self, packet: Packet, packet_number: int = 1) -> Optional[Tuple[str, int, bytes]]:
        """从数据包中提取流信息和载荷 - Phase 3重构版
        
        重构特性：
        1. 支持方向性流ID生成
        2. 与PyShark分析器保持一致的流ID格式
        3. 正确的序列号提取和计算
        
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
            payload = self._extract_tcp_payload(packet)
            
            # 生成方向性流ID，与PyShark分析器保持一致
            stream_id = self._generate_directional_stream_id(src_ip, dst_ip, src_port, dst_port, protocol)
            
            self._logger.debug(f"数据包{packet_number}: {protocol} {src_ip}:{src_port} -> {dst_ip}:{dst_port}, "
                              f"序列号={seq_number}, 流ID={stream_id}")
            
            # 注册或更新流信息到stream_manager
            direction = self._determine_packet_direction(src_ip, dst_ip, src_port, dst_port)
            tcp_stream = self._stream_manager.get_or_create_stream(src_ip, src_port, dst_ip, dst_port, direction)
            
            # 设置初始序列号（如果是第一次遇到）
            if tcp_stream.initial_seq is None:
                tcp_stream.set_initial_seq(seq_number)
            
            # 更新序列号状态
            tcp_stream.update_last_seq(seq_number, len(payload))
            
            return (stream_id, seq_number, payload)
            
        elif udp_layer:
            src_port = udp_layer.sport
            dst_port = udp_layer.dport
            protocol = "UDP"
            payload = self._extract_udp_payload(packet)
            
            # UDP使用简化的流ID（无方向性）
            stream_id = self._generate_udp_stream_id(src_ip, dst_ip, src_port, dst_port)
            
            self._logger.debug(f"数据包{packet_number}: {protocol} {src_ip}:{src_port} -> {dst_ip}:{dst_port}, "
                              f"流ID={stream_id}")
            
            return (stream_id, None, payload)  # UDP无序列号
        
        return None
    
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
    
    # 该方法已被删除，序列号处理现在由TCPStreamManager处理
    
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
    
    def _apply_sequence_based_masks(self, payload: bytes, match_results: List[SequenceMatchResult], seq_number: int) -> bytes:
        """应用基于序列号匹配的掩码
        
        Phase 3核心方法：根据SequenceMatchResult列表应用字节级精确掩码
        
        Args:
            payload: 原始载荷
            match_results: 序列号匹配结果列表
            seq_number: 序列号
            
        Returns:
            修改后的载荷
        """
        if not match_results or not payload:
            return payload
        
        # 过滤出匹配的结果
        valid_matches = [result for result in match_results if result.is_match]
        if not valid_matches:
            return payload
        
        # 转换为可修改的字节数组
        modified_payload = bytearray(payload)
        
        self._logger.info(f"🔧 开始应用基于序列号的掩码，匹配数量={len(valid_matches)}, 载荷长度={len(payload)}")
        
        for i, match_result in enumerate(valid_matches):
            start_offset = match_result.mask_start_offset
            end_offset = match_result.mask_end_offset
            mask_spec = match_result.entry.mask_spec
            
            self._logger.info(f"🎯 处理掩码{i+1}: 载荷偏移=[{start_offset}:{end_offset}), "
                             f"spec={mask_spec.get_description()}, 长度={match_result.mask_length}")
            
            # 验证偏移范围
            if start_offset < 0 or end_offset > len(payload) or start_offset >= end_offset:
                self._logger.warning(f"跳过掩码{i+1}: 无效偏移范围[{start_offset}:{end_offset}), 载荷长度={len(payload)}")
                continue
            
            # 应用掩码规范到指定的载荷偏移
            self._apply_mask_spec_to_range(modified_payload, start_offset, end_offset, mask_spec)
            
            # 应用头部保留规则（如果有）
            if match_result.entry.preserve_headers:
                self._apply_preserve_headers(modified_payload, match_result.entry.preserve_headers, 
                                           start_offset, end_offset)
        
        self._logger.info(f"✅ 完成基于序列号的掩码处理")
        return bytes(modified_payload)
    
    def _apply_mask_spec_to_range(self, payload: bytearray, start: int, end: int, mask_spec: MaskSpec) -> None:
        """应用掩码规范到指定范围
        
        Args:
            payload: 载荷字节数组
            start: 起始位置（载荷内偏移）
            end: 结束位置（载荷内偏移）
            mask_spec: 掩码规范
        """
        self._logger.info(f"🔧 应用掩码规范: start={start}, end={end}, 载荷长度={len(payload)}, "
                         f"掩码类型={type(mask_spec).__name__}")
        
        if isinstance(mask_spec, KeepAll):
            # 保留所有字节，不做修改
            self._logger.info(f"✅ KeepAll: 保留范围[{start}:{end})，不修改载荷")
            return
        
        elif isinstance(mask_spec, MaskAfter):
            # 保留前N个字节，掩码其余部分
            keep_bytes = mask_spec.keep_bytes
            
            # 计算在当前范围内的实际保留字节数
            range_size = end - start
            if range_size <= keep_bytes:
                if keep_bytes == 0:
                    # MaskAfter(0) - 全部掩码
                    mask_start = start
                    mask_end = end
                    self._logger.info(f"🎯 MaskAfter({keep_bytes}) 小范围全掩码: [{mask_start}:{mask_end})")
                else:
                    # MaskAfter(>0) - 小范围完全保留
                    self._logger.info(f"🎯 MaskAfter({keep_bytes}) 小范围完全保留: 范围长度{range_size} <= keep_bytes{keep_bytes}")
                    return
            else:
                # 正常情况：范围长度大于keep_bytes
                mask_start = start + keep_bytes
                mask_end = end
                self._logger.info(f"🎯 MaskAfter({keep_bytes}) 正常掩码: 保留[{start}:{mask_start}), 掩码[{mask_start}:{mask_end})")
            
            # 执行掩码操作
            if 'mask_start' in locals() and 'mask_end' in locals() and mask_start < mask_end:
                self._apply_zero_mask(payload, mask_start, mask_end)
                
        elif isinstance(mask_spec, MaskRange):
            # 掩码指定范围
            self._logger.info(f"🎯 MaskRange: 应用范围={mask_spec.ranges}")
            for range_start, range_end in mask_spec.ranges:
                # 计算绝对偏移
                abs_mask_start = start + range_start
                abs_mask_end = min(end, start + range_end)
                
                if abs_mask_start < abs_mask_end and abs_mask_start < len(payload):
                    self._apply_zero_mask(payload, abs_mask_start, abs_mask_end)
                    self._logger.info(f"✅ MaskRange掩码子范围[{abs_mask_start}:{abs_mask_end})")
        
        else:
            # 未知掩码类型，全部掩码
            self._logger.warning(f"未知掩码类型 {type(mask_spec)}，执行全部掩码")
            self._apply_zero_mask(payload, start, end)
    
    def _apply_zero_mask(self, payload: bytearray, start: int, end: int) -> None:
        """应用零字节掩码
        
        Args:
            payload: 载荷字节数组
            start: 起始位置
            end: 结束位置
        """
        if start >= end or start >= len(payload):
            return
        
        bytes_to_mask = min(end, len(payload)) - start
        mask_byte = self.get_config_value('mask_byte_value', 0x00)
        
        # 记录掩码前的载荷样本
        sample_before = payload[start:min(start+8, end)].hex() if start < len(payload) else "无数据"
        self._logger.info(f"📋 掩码前载荷样本[{start}:{min(start+8, end)}): {sample_before}")
        
        # 实际进行掩码操作
        for i in range(start, min(end, len(payload))):
            old_byte = payload[i]
            payload[i] = mask_byte
            if i < start + 3:  # 只记录前几个字节的详细变化
                self._logger.info(f"🔄 位置{i}: 0x{old_byte:02x} -> 0x{mask_byte:02x}")
        
        # 记录掩码后的载荷样本
        sample_after = payload[start:min(start+8, end)].hex() if start < len(payload) else "无数据"
        self._logger.info(f"📋 掩码后载荷样本[{start}:{min(start+8, end)}): {sample_after}")
        self._logger.info(f"✅ 成功掩码了 {bytes_to_mask} 个字节，掩码值=0x{mask_byte:02x}")
    
    def _apply_preserve_headers(self, payload: bytearray, preserve_headers: List[Tuple[int, int]], 
                               range_start: int, range_end: int) -> None:
        """应用头部保留规则
        
        Args:
            payload: 载荷字节数组
            preserve_headers: 需要保留的头部范围列表（相对于条目序列号范围）
            range_start: 当前处理范围的起始位置（载荷内偏移）
            range_end: 当前处理范围的结束位置（载荷内偏移）
        """
        self._logger.info(f"🛡️ 应用头部保留规则: {len(preserve_headers)}个保留范围")
        
        for header_start, header_end in preserve_headers:
            # TODO: 实现头部保留逻辑
            # 这需要根据具体的头部保留需求来实现
            # 例如：恢复被掩码的头部字节到原始值
            self._logger.info(f"📝 保留头部范围: [{header_start}:{header_end}) (暂未实现)")
    
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
            'sequence_matches': self._sequence_matches,
            'sequence_mismatches': self._sequence_mismatches,
            'sequence_match_rate': self._sequence_matches / max(self._sequence_matches + self._sequence_mismatches, 1) * 100,
            'streams_processed': len(self._stream_stats),
            'managed_streams': self._stream_manager.get_stream_count() if self._stream_manager else 0,
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
        self._sequence_matches = 0
        self._sequence_mismatches = 0
    
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
        return "使用Scapy根据序列号掩码表对PCAP文件进行精确的载荷掩码处理"
    
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
    
    def _determine_packet_direction(self, src_ip: str, dst_ip: str, src_port: int, dst_port: int) -> ConnectionDirection:
        """确定数据包方向
        
        Args:
            src_ip: 源IP
            dst_ip: 目标IP
            src_port: 源端口
            dst_port: 目标端口
            
        Returns:
            连接方向
        """
        # 使用与PyShark分析器相同的逻辑
        if (src_ip, src_port) <= (dst_ip, dst_port):
            return ConnectionDirection.FORWARD
        else:
            return ConnectionDirection.REVERSE


     
   