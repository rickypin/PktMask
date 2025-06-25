#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PyShark分析器 - Phase 2重构版本

使用PyShark对经过TShark预处理的PCAP文件进行深度协议分析，
基于TCP序列号绝对值范围生成掩码表，支持方向性TCP流处理。
这是Enhanced Trim Payloads处理流程的第二阶段。

重构要点：
1. 支持方向性TCP流ID生成
2. 基于序列号范围的掩码表生成
3. 重构TLS协议处理逻辑
4. 建立多协议掩码策略框架
"""

import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple, Set
from collections import defaultdict
from dataclasses import dataclass, field
import gc

try:
    import pyshark
except ImportError:
    pyshark = None

from .base_stage import BaseStage, StageContext
from .stage_result import StageResult, StageStatus, StageMetrics
from ...processors.base_processor import ProcessorResult
# Phase 2: 使用新的序列号掩码表
from ..models.sequence_mask_table import SequenceMaskTable, MaskEntry
from ..models.tcp_stream import TCPStreamManager, ConnectionDirection, detect_packet_direction
from ..models.mask_spec import MaskAfter, MaskRange, KeepAll, create_http_header_mask, create_tls_record_mask
from ..exceptions import StreamMaskTableError

# ---- Phase 2 Revised Implementation: alias PySharkAnalyzer to EnhancedPySharkAnalyzer ----


@dataclass
class StreamInfo:
    """TCP/UDP流信息 - Phase 2增强版本"""
    stream_id: str
    src_ip: str
    dst_ip: str
    src_port: int
    dst_port: int
    protocol: str  # 'TCP' or 'UDP'
    direction: Optional[ConnectionDirection] = None  # Phase 2: 添加方向信息
    application_protocol: Optional[str] = None  # 'HTTP', 'TLS', etc.
    packet_count: int = 0
    total_bytes: int = 0
    first_seen: Optional[float] = None
    last_seen: Optional[float] = None
    # Phase 2: 添加序列号跟踪
    initial_seq: Optional[int] = None
    last_seq: Optional[int] = None


@dataclass
class PacketAnalysis:
    """数据包分析结果 - Phase 2增强版本"""
    packet_number: int
    timestamp: float
    stream_id: str
    seq_number: Optional[int] = None
    payload_length: int = 0
    application_layer: Optional[str] = None
    # Phase 2: 增强TLS分析结果
    is_tls_handshake: bool = False
    is_tls_application_data: bool = False
    is_tls_change_cipher_spec: bool = False  # content_type = 20
    is_tls_alert: bool = False               # content_type = 21  
    is_tls_heartbeat: bool = False           # content_type = 24
    tls_content_type: Optional[int] = None   # 存储原始content_type值
    tls_record_length: Optional[int] = None
    # Phase 2: TLS重组相关属性
    tls_reassembled: bool = False           # 是否是TLS重组包
    tls_reassembly_info: Dict[str, Any] = field(default_factory=dict)  # TLS重组信息
    # Phase 2: 序列号范围计算
    absolute_seq_start: Optional[int] = None
    absolute_seq_end: Optional[int] = None
    relative_seq_start: Optional[int] = None
    relative_seq_end: Optional[int] = None


class PySharkAnalyzer(BaseStage):
    """PyShark分析器 - Phase 2重构版本
    
    Phase 2重构要点：
    1. 支持方向性TCP流ID生成（含_forward/_reverse后缀）
    2. 基于序列号绝对值范围生成掩码表
    3. 重构TLS协议处理，精确识别不同content type
    4. 建立多协议掩码策略框架
    5. 实现序列号范围计算和映射算法
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化PyShark分析器"""
        super().__init__("PyShark分析器", config)
        
        # 协议配置
        self._analyze_tls = self.get_config_value('analyze_tls', True)
        self._analyze_tcp = self.get_config_value('analyze_tcp', True)
        self._analyze_udp = self.get_config_value('analyze_udp', True)
        
        # TLS协议配置  
        self._tls_keep_handshake = self.get_config_value('tls_keep_handshake', True)
        self._tls_mask_application_data = self.get_config_value('tls_mask_application_data', True)
        
        # 性能配置
        self._max_packets_per_batch = self.get_config_value('max_packets_per_batch', 1000)
        self._memory_cleanup_interval = self.get_config_value('memory_cleanup_interval', 5000)
        self._timeout_seconds = self.get_config_value('analysis_timeout_seconds', 600)
        
        # Phase 2: 使用新的核心组件
        self._tcp_stream_manager = TCPStreamManager()
        self._streams: Dict[str, StreamInfo] = {}
        self._packet_analyses: List[PacketAnalysis] = []
        self._sequence_mask_table: Optional[SequenceMaskTable] = None
        
    def _initialize_impl(self) -> None:
        """初始化PyShark分析器"""
        # 检查PyShark是否可用
        if pyshark is None:
            raise RuntimeError("PyShark未安装，请运行: pip install pyshark")
        
        # 检查PyShark版本
        try:
            version = pyshark.__version__
            self._logger.info(f"PyShark版本: {version}")
        except AttributeError:
            self._logger.warning("无法获取PyShark版本信息")
        
        # 重置内部状态
        self._tcp_stream_manager.clear()
        self._streams.clear()
        self._packet_analyses.clear()
        self._sequence_mask_table = None
        
        self._logger.info("PyShark分析器初始化完成 - Phase 2重构版本")
    
    def validate_inputs(self, context: StageContext) -> bool:
        """验证输入参数"""
        # 检查输入文件（应该是TShark预处理器的输出）
        if context.tshark_output is None:
            self._logger.error("缺少TShark预处理器输出文件")
            return False
        
        input_file = Path(context.tshark_output)
        if not input_file.exists():
            self._logger.error(f"TShark输出文件不存在: {input_file}")
            return False
        
        if input_file.stat().st_size == 0:
            self._logger.error(f"TShark输出文件为空: {input_file}")
            return False
        
        # 检查PyShark可用性
        if not self.is_initialized:
            self._logger.error("PyShark分析器未正确初始化")
            return False
        
        return True
    
    def execute(self, context: StageContext) -> ProcessorResult:
        """执行PyShark分析"""
        context.current_stage = self.name
        progress_callback = self.get_progress_callback(context)
        
        start_time = time.time()
        
        try:
            self._logger.info("开始PyShark协议分析... (Phase 2重构版本)")
            
            # 阶段1: 打开PCAP文件
            progress_callback(0.0)
            input_file = Path(context.tshark_output)
            cap = self._open_pcap_file(input_file)
            
            # 阶段2: 分析数据包
            progress_callback(0.1)
            packet_count = self._analyze_packets(cap, progress_callback)
            
            # 阶段3: 计算序列号范围
            progress_callback(0.7)
            self._calculate_sequence_ranges()
            
            # 阶段4: 生成序列号掩码表
            progress_callback(0.8)
            self._sequence_mask_table = self._generate_sequence_mask_table()
            
            # 阶段5: 保存结果到上下文
            progress_callback(0.9)
            context.mask_table = self._sequence_mask_table  # Phase 2: 使用新的掩码表
            context.pyshark_results = {
                'streams': self._streams,
                'packet_analyses': self._packet_analyses,
                'tcp_streams': self._tcp_stream_manager.get_all_stream_ids()
            }
            
            # 生成统计信息
            duration = time.time() - start_time
            stats = self._generate_statistics()
            self._update_stats(context, packet_count, duration)
            
            progress_callback(1.0)
            self._logger.info(f"PyShark分析完成，耗时 {duration:.2f} 秒，处理 {packet_count} 个数据包")
            
            return ProcessorResult(
                success=True,
                data={
                    'message': f"PyShark分析完成，处理 {packet_count} 个数据包",
                    'packet_count': packet_count,
                    'stream_count': len(self._streams),
                    'mask_entries': self._sequence_mask_table.get_total_entry_count() if self._sequence_mask_table else 0,
                    'processing_time': duration,
                    'statistics': stats
                },
                stats=stats
            )
            
        except Exception as e:
            self._logger.error(f"PyShark分析失败: {e}", exc_info=True)
            return ProcessorResult(
                success=False,
                data={'error': str(e)},
                error=f"PyShark分析失败: {str(e)}"
            )
        finally:
            self._cleanup_memory()
    
    def _open_pcap_file(self, pcap_file: Path) -> pyshark.FileCapture:
        """打开PCAP文件
        
        Args:
            pcap_file: PCAP文件路径
            
        Returns:
            PyShark文件捕获对象
        """
        try:
            cap = pyshark.FileCapture(
                str(pcap_file),
                keep_packets=False,  # 不在内存中保留数据包以节省内存
                use_json=False,      # 禁用JSON，避免多记录解析问题
                include_raw=False    # 不包含原始数据以节省内存
            )
            self._logger.info(f"成功打开PCAP文件: {pcap_file}")
            return cap
            
        except Exception as e:
            self._logger.error(f"打开PCAP文件失败: {e}")
            raise RuntimeError(f"打开PCAP文件失败: {e}")
    
    def _analyze_packets(self, cap: pyshark.FileCapture, progress_callback) -> int:
        """分析数据包
        
        Args:
            cap: PyShark文件捕获对象
            progress_callback: 进度回调函数
            
        Returns:
            处理的数据包数量
        """
        packet_count = 0
        batch_count = 0
        
        try:
            for packet in cap:
                try:
                    # 分析单个数据包
                    analysis = self._analyze_single_packet(packet)
                    if analysis:
                        self._packet_analyses.append(analysis)
                        self._update_stream_info(analysis)
                    
                    packet_count += 1
                    
                    # 更新进度 (10% - 80%)
                    if packet_count % 100 == 0 or packet_count <= 10:
                        progress = 0.1 + (0.7 * min(1.0, packet_count / 10000))
                        progress_callback(progress)
                    
                    # 定期清理内存
                    if packet_count % self._memory_cleanup_interval == 0:
                        gc.collect()
                        self._logger.debug(f"已处理{packet_count}个数据包，执行内存清理")
                    
                    # 检查超时
                    batch_count += 1
                    if batch_count % self._max_packets_per_batch == 0:
                        # 可以在这里添加超时检查
                        pass
                        
                except Exception as e:
                    self._logger.warning(f"分析数据包{packet_count + 1}时出错: {e}")
                    continue
            
            self._logger.info(f"数据包分析完成，共处理{packet_count}个数据包")
            return packet_count
            
        except Exception as e:
            self._logger.error(f"数据包分析过程中出错: {e}")
            raise
        finally:
            try:
                cap.close()
            except:
                pass
    
    def _analyze_single_packet(self, packet) -> Optional[PacketAnalysis]:
        """分析单个数据包 - 扩展协议识别支持ICMP和DNS
        
        Args:
            packet: PyShark数据包对象
            
        Returns:
            数据包分析结果，如果不是目标协议则返回None
        """
        try:
            # 基本信息
            packet_number = int(packet.number)
            timestamp = float(packet.sniff_timestamp)
            
            # 特别调试数据包14和15
            if packet_number in [14, 15]:
                self._logger.info(f"=== PyShark调试数据包{packet_number} 详细信息 ===")
                self._logger.info(f"PyShark数据包{packet_number}: {packet}")
                self._logger.info(f"PyShark数据包{packet_number} 协议层: {[layer.layer_name for layer in packet.layers]}")
                
                if hasattr(packet, 'tcp'):
                    tcp_layer = packet.tcp
                    self._logger.info(f"PyShark数据包{packet_number} TCP层存在")
                    self._logger.info(f"PyShark数据包{packet_number} TCP序列号: {getattr(tcp_layer, 'seq', 'N/A')}")
                    self._logger.info(f"PyShark数据包{packet_number} TCP载荷长度: {getattr(tcp_layer, 'len', 'N/A')}")
                    
                    # 检查是否有数据载荷
                    if hasattr(tcp_layer, 'payload'):
                        self._logger.info(f"PyShark数据包{packet_number} TCP有载荷字段")
                    else:
                        self._logger.info(f"PyShark数据包{packet_number} TCP无载荷字段")
                        
                if hasattr(packet, 'tls'):
                    tls_layer = packet.tls
                    self._logger.info(f"PyShark数据包{packet_number} TLS层存在")
                    self._logger.info(f"PyShark数据包{packet_number} TLS记录类型: {getattr(tls_layer, 'record_content_type', 'N/A')}")
                    self._logger.info(f"PyShark数据包{packet_number} TLS记录长度: {getattr(tls_layer, 'record_length', 'N/A')}")
                    
                self._logger.info(f"=== PyShark数据包{packet_number} 调试结束 ===")
            
            # 扩展协议识别：支持TCP、UDP、ICMP、DNS
            analysis = None
            
            # 检查TCP协议
            if hasattr(packet, 'tcp'):
                analysis = self._analyze_tcp_packet(packet, packet_number, timestamp)
                
            # 检查UDP协议
            elif hasattr(packet, 'udp') and self._analyze_udp:
                analysis = self._analyze_udp_packet(packet, packet_number, timestamp)
                
            # 新增：检查ICMP协议
            elif hasattr(packet, 'icmp'):
                analysis = self._analyze_icmp_packet(packet, packet_number, timestamp)
                
            # 新增：检查DNS协议 (可能在UDP或TCP上)
            elif hasattr(packet, 'dns'):
                analysis = self._analyze_dns_packet(packet, packet_number, timestamp)
                
            # 如果有分析结果，进一步检查应用层协议
            if analysis:
                # 新增ICMP识别
                if hasattr(packet, 'icmp'):
                    analysis.application_layer = 'ICMP'
                    self._logger.debug(f"识别到ICMP协议包: {packet.number}")
                
                # 新增DNS识别  
                elif hasattr(packet, 'dns'):
                    analysis.application_layer = 'DNS'
                    self._logger.debug(f"识别到DNS协议包: {packet.number}")
                
                # 现有TLS识别逻辑保持不变
                elif hasattr(packet, 'tls'):
                    self._analyze_tls_layer(packet.tls, analysis)
            
            return analysis
                
        except Exception as e:
            self._logger.debug(f"分析数据包时出错: {e}")
            return None
    
    def _analyze_tcp_packet(self, packet, packet_number: int, timestamp: float) -> Optional[PacketAnalysis]:
        """分析TCP数据包
        
        Args:
            packet: PyShark数据包对象
            packet_number: 数据包编号
            timestamp: 时间戳
            
        Returns:
            TCP数据包分析结果
        """
        try:
            # 提取基本TCP信息
            tcp_layer = packet.tcp
            ip_layer = packet.ip if hasattr(packet, 'ip') else packet.ipv6
            
            src_ip = ip_layer.src
            dst_ip = ip_layer.dst
            src_port = int(tcp_layer.srcport)
            dst_port = int(tcp_layer.dstport)
            seq_number = int(tcp_layer.seq) if hasattr(tcp_layer, 'seq') else None
            
            # 生成流ID
            stream_id = self._generate_stream_id(src_ip, dst_ip, src_port, dst_port, 'TCP')
            
            # 获取载荷长度 - 使用正确的PyShark方法
            payload_length = 0
            if hasattr(tcp_layer, 'payload') and tcp_layer.payload:
                try:
                    # 方法1: 使用binary_value获取实际载荷长度
                    if hasattr(tcp_layer.payload, 'binary_value'):
                        payload_length = len(tcp_layer.payload.binary_value)
                        self._logger.debug(f"数据包{packet_number}: 使用binary_value获取TCP载荷长度 = {payload_length}字节")
                    elif hasattr(tcp_layer.payload, 'raw_value'):
                        payload_length = len(tcp_layer.payload.raw_value) // 2  # hex string
                        self._logger.debug(f"数据包{packet_number}: 使用raw_value获取TCP载荷长度 = {payload_length}字节")
                    else:
                        raise ValueError("无法获取payload的binary_value或raw_value")
                except Exception as payload_error:
                    # 回退到tcp.len计算方法
                    self._logger.debug(f"数据包{packet_number}: 获取payload失败，使用tcp.len计算: {payload_error}")
                    if hasattr(tcp_layer, 'len'):
                        total_len = int(tcp_layer.len)
                        payload_length = total_len  # tcp.len本身就是TCP载荷长度
                        self._logger.debug(f"数据包{packet_number}: 使用tcp.len获取载荷长度 = {payload_length}字节")
            elif hasattr(tcp_layer, 'len'):
                # 无载荷数据但有tcp.len字段
                total_len = int(tcp_layer.len)
                payload_length = total_len
                self._logger.debug(f"数据包{packet_number}: 无payload对象，使用tcp.len = {payload_length}字节")
            
            # 创建基本分析结果
            analysis = PacketAnalysis(
                packet_number=packet_number,
                timestamp=timestamp,
                stream_id=stream_id,
                seq_number=seq_number,
                payload_length=payload_length
            )
            
            # 添加详细的协议层调试信息
            has_tls = hasattr(packet, 'tls')
            has_ssl = hasattr(packet, 'ssl') 
            has_http = hasattr(packet, 'http')
            
            self._logger.debug(f"数据包{packet_number}: payload_len={payload_length}, has_tls={has_tls}, has_ssl={has_ssl}, has_http={has_http}, port={src_port}->{dst_port}")
            
            # 检查应用层协议（移除HTTP支持）
            if self._analyze_tls and (has_tls or has_ssl):
                tls_layer = packet.tls if has_tls else packet.ssl
                self._logger.debug(f"数据包{packet_number}: 识别为TLS/SSL")
                # 🔧 关键修复：设置应用层协议为TLS
                analysis.application_layer = 'TLS'
                self._analyze_tls_layer(tls_layer, analysis)
                self._logger.debug(f"数据包{packet_number}: 已设置应用层协议为TLS")
            else:
                self._logger.debug(f"数据包{packet_number}: 未识别为TLS，载荷长度={payload_length}")
            
            return analysis
            
        except Exception as e:
            self._logger.debug(f"分析TCP数据包时出错: {e}")
            return None
    
    def _analyze_udp_packet(self, packet, packet_number: int, timestamp: float) -> Optional[PacketAnalysis]:
        """分析UDP数据包
        
        Args:
            packet: PyShark数据包对象
            packet_number: 数据包编号
            timestamp: 时间戳
            
        Returns:
            UDP数据包分析结果
        """
        try:
            # 提取基本UDP信息
            udp_layer = packet.udp
            ip_layer = packet.ip if hasattr(packet, 'ip') else packet.ipv6
            
            src_ip = ip_layer.src
            dst_ip = ip_layer.dst
            src_port = int(udp_layer.srcport)
            dst_port = int(udp_layer.dstport)
            
            # 生成流ID
            stream_id = self._generate_stream_id(src_ip, dst_ip, src_port, dst_port, 'UDP')
            
            # 获取载荷长度 - 使用正确的PyShark方法
            payload_length = 0
            if hasattr(udp_layer, 'payload') and udp_layer.payload:
                try:
                    # 方法1: 使用binary_value获取实际载荷长度
                    if hasattr(udp_layer.payload, 'binary_value'):
                        payload_length = len(udp_layer.payload.binary_value)
                        self._logger.debug(f"数据包{packet_number}: 使用binary_value获取UDP载荷长度 = {payload_length}字节")
                    elif hasattr(udp_layer.payload, 'raw_value'):
                        payload_length = len(udp_layer.payload.raw_value) // 2  # hex string
                        self._logger.debug(f"数据包{packet_number}: 使用raw_value获取UDP载荷长度 = {payload_length}字节")
                    else:
                        raise ValueError("无法获取payload的binary_value或raw_value")
                except Exception as payload_error:
                    # 回退到udp.length计算方法
                    self._logger.debug(f"数据包{packet_number}: 获取UDP payload失败，使用udp.length计算: {payload_error}")
                    if hasattr(udp_layer, 'length'):
                        udp_header_len = 8  # UDP头部固定8字节
                        total_len = int(udp_layer.length)
                        payload_length = max(0, total_len - udp_header_len)
                        self._logger.debug(f"数据包{packet_number}: 使用udp.length计算载荷长度 = {payload_length}字节")
            elif hasattr(udp_layer, 'length'):
                # 无载荷数据但有udp.length字段
                udp_header_len = 8  # UDP头部固定8字节
                total_len = int(udp_layer.length)
                payload_length = max(0, total_len - udp_header_len)
                self._logger.debug(f"数据包{packet_number}: 无payload对象，使用udp.length计算 = {payload_length}字节")
            
            # 创建分析结果
            analysis = PacketAnalysis(
                packet_number=packet_number,
                timestamp=timestamp,
                stream_id=stream_id,
                seq_number=None,  # UDP没有序列号
                payload_length=payload_length
            )
            
            # UDP通常不承载HTTP或TLS，但可以检查其他协议
            return analysis
            
        except Exception as e:
            self._logger.debug(f"分析UDP数据包时出错: {e}")
            return None
    
    def _analyze_icmp_packet(self, packet, packet_number: int, timestamp: float) -> Optional[PacketAnalysis]:
        """分析ICMP数据包
        
        Args:
            packet: PyShark数据包对象
            packet_number: 数据包编号
            timestamp: 时间戳
            
        Returns:
            ICMP数据包分析结果
        """
        try:
            # 提取基本ICMP信息
            icmp_layer = packet.icmp
            ip_layer = packet.ip if hasattr(packet, 'ip') else packet.ipv6
            
            src_ip = ip_layer.src
            dst_ip = ip_layer.dst
            
            # ICMP没有端口概念，使用类型和代码作为标识
            icmp_type = int(icmp_layer.type) if hasattr(icmp_layer, 'type') else 0
            icmp_code = int(icmp_layer.code) if hasattr(icmp_layer, 'code') else 0
            
            # 生成ICMP流ID (使用特殊格式)
            stream_id = f"ICMP_{src_ip}_{dst_ip}_{icmp_type}_{icmp_code}"
            
            # 获取ICMP载荷长度
            payload_length = 0
            if hasattr(icmp_layer, 'data') and icmp_layer.data:
                try:
                    if hasattr(icmp_layer.data, 'binary_value'):
                        payload_length = len(icmp_layer.data.binary_value)
                    elif hasattr(icmp_layer.data, 'raw_value'):
                        payload_length = len(icmp_layer.data.raw_value) // 2
                except Exception:
                    # 对于ICMP，如果无法获取数据长度，设为8字节（最小ICMP包大小）
                    payload_length = 8
            else:
                # ICMP最小包大小
                payload_length = 8
            
            # 创建分析结果
            analysis = PacketAnalysis(
                packet_number=packet_number,
                timestamp=timestamp,
                stream_id=stream_id,
                seq_number=None,  # ICMP没有序列号
                payload_length=payload_length,
                application_layer='ICMP'
            )
            
            self._logger.debug(f"数据包{packet_number}: 识别为ICMP，类型={icmp_type}，代码={icmp_code}，载荷长度={payload_length}字节")
            return analysis
            
        except Exception as e:
            self._logger.debug(f"分析ICMP数据包时出错: {e}")
            return None
    
    def _analyze_dns_packet(self, packet, packet_number: int, timestamp: float) -> Optional[PacketAnalysis]:
        """分析DNS数据包
        
        Args:
            packet: PyShark数据包对象
            packet_number: 数据包编号
            timestamp: 时间戳
            
        Returns:
            DNS数据包分析结果
        """
        try:
            # 提取基本DNS信息
            dns_layer = packet.dns
            ip_layer = packet.ip if hasattr(packet, 'ip') else packet.ipv6
            
            src_ip = ip_layer.src
            dst_ip = ip_layer.dst
            
            # DNS可能基于UDP或TCP
            if hasattr(packet, 'udp'):
                udp_layer = packet.udp
                src_port = int(udp_layer.srcport)
                dst_port = int(udp_layer.dstport)
                transport_protocol = 'UDP'
            elif hasattr(packet, 'tcp'):
                tcp_layer = packet.tcp
                src_port = int(tcp_layer.srcport)
                dst_port = int(tcp_layer.dstport)
                transport_protocol = 'TCP'
            else:
                # 默认UDP端口53
                src_port = 53
                dst_port = 53
                transport_protocol = 'UDP'
            
            # 生成DNS流ID
            stream_id = f"DNS_{src_ip}:{src_port}_{dst_ip}:{dst_port}_{transport_protocol}"
            
            # 获取DNS载荷长度
            payload_length = 0
            try:
                # DNS查询和响应的长度计算
                if hasattr(packet, 'udp') and hasattr(packet.udp, 'length'):
                    udp_header_len = 8
                    total_len = int(packet.udp.length)
                    payload_length = max(0, total_len - udp_header_len)
                elif hasattr(packet, 'tcp') and hasattr(packet.tcp, 'len'):
                    payload_length = int(packet.tcp.len)
                else:
                    # 默认DNS最小包大小
                    payload_length = 12  # DNS头部大小
            except Exception:
                payload_length = 12
            
            # 创建分析结果
            analysis = PacketAnalysis(
                packet_number=packet_number,
                timestamp=timestamp,
                stream_id=stream_id,
                seq_number=None,  # DNS通常基于UDP，没有序列号
                payload_length=payload_length,
                application_layer='DNS'
            )
            
            # 提取DNS查询信息用于调试
            dns_qr = getattr(dns_layer, 'qr', 'N/A')  # 0=查询, 1=响应
            dns_opcode = getattr(dns_layer, 'opcode', 'N/A')
            
            self._logger.debug(f"数据包{packet_number}: 识别为DNS，QR={dns_qr}，OPCODE={dns_opcode}，载荷长度={payload_length}字节，传输协议={transport_protocol}")
            return analysis
            
        except Exception as e:
            self._logger.debug(f"分析DNS数据包时出错: {e}")
            return None
    
    def _analyze_tls_layer(self, tls_layer, analysis: PacketAnalysis) -> None:
        """分析TLS/SSL层，兼容不同协议版本
        
        Args:
            tls_layer: PyShark TLS/SSL层对象
            analysis: 数据包分析结果对象
        """
        try:
            # PyShark可能将单个记录或多个记录作为列表返回
            records_raw = tls_layer.record if hasattr(tls_layer, 'record') else tls_layer
            records = records_raw if isinstance(records_raw, list) else [records_raw]
            self._logger.debug(f"Pkt {analysis.packet_number}: 发现 {len(records)} 个TLS记录")
            
            # 🔧 调试：打印TLS层的所有可用属性
            if analysis.packet_number in [14, 15]:
                self._logger.info(f"=== TLS调试数据包{analysis.packet_number} ===")
                self._logger.info(f"TLS层类型: {type(tls_layer)}")
                self._logger.info(f"TLS层属性: {dir(tls_layer)}")
                if hasattr(tls_layer, 'record'):
                    self._logger.info(f"TLS record类型: {type(tls_layer.record)}")
                    if hasattr(tls_layer.record, '__len__'):
                        self._logger.info(f"TLS record长度: {len(tls_layer.record)}")
                    self._logger.info(f"TLS record属性: {dir(tls_layer.record)}")
                self._logger.info(f"=== TLS调试结束 ===")
            
            # 用于汇总信息的变量
            total_length = 0
            all_content_types: Set[int] = set()

            # 重置所有相关的布尔标志，以确保从干净的状态开始处理多记录包
            analysis.is_tls_change_cipher_spec = False
            analysis.is_tls_alert = False
            analysis.is_tls_handshake = False
            analysis.is_tls_application_data = False
            analysis.is_tls_heartbeat = False
            
            for i, record in enumerate(records):
                # 🔧 修复：使用PyShark正确的属性访问方式
                content_type_str = None
                record_length_str = None
                
                try:
                    # 🔧 修复：使用TLS层的直接属性访问（不再访问record对象的属性）
                    # PyShark在record容器中有多个记录，但TLS层本身有汇总的属性
                    if i == 0:  # 只在第一个记录时从TLS层获取属性
                        # 从TLS层获取content_type
                        if hasattr(tls_layer, 'record_content_type'):
                            content_type_str = str(tls_layer.record_content_type)
                        
                        # 从TLS层获取记录长度
                        if hasattr(tls_layer, 'record_length'):
                            record_length_str = str(tls_layer.record_length)
                    else:
                        # 对于后续记录，目前跳过（这个文件只有一个TLS记录类型）
                        continue
                        
                except Exception as access_error:
                    self._logger.debug(f"记录 {i+1}: 访问TLS属性失败: {access_error}")
                    continue
                
                if content_type_str is None:
                    self._logger.debug(f"记录 {i+1}: 未找到 content_type")
                    continue
                
                try:
                    content_type = int(content_type_str)
                    all_content_types.add(content_type)
                    self._logger.debug(f"记录 {i+1}: content_type={content_type}")
                    
                    # 处理不同类型的TLS记录
                    self._process_tls_content_type(content_type, analysis, {})
                    
                    # 累加记录长度
                    if record_length_str:
                        total_length += int(record_length_str)
                        
                except (ValueError, TypeError) as e:
                    self._logger.warning(f"无法解析TLS content_type: '{content_type_str}', 错误: {e}")

            if all_content_types:
                analysis.tls_record_length = 5 * len(records) + total_length  # 5字节头/记录
                self._logger.debug(f"总TLS记录长度: {analysis.tls_record_length} (来自 {len(records)} 个记录)")

                # 确定一个最终的 content_type 用于分类
                # 优先级: Handshake > Change Cipher Spec > Alert > Heartbeat > Application Data
                # 这个优先级确保任何信令类型的存在都会让整个包被当作信令包处理
                if 22 in all_content_types:      # Handshake
                    analysis.tls_content_type = 22
                elif 20 in all_content_types:    # Change Cipher Spec
                    analysis.tls_content_type = 20
                elif 21 in all_content_types:    # Alert
                    analysis.tls_content_type = 21
                elif 24 in all_content_types:    # Heartbeat
                    analysis.tls_content_type = 24
                elif 23 in all_content_types:    # Application Data (最后考虑)
                    analysis.tls_content_type = 23
            else:
                self._logger.debug(f"数据包{analysis.packet_number}: 未找到TLS/SSL content type信息")
                
        except Exception as e:
            self._logger.warning(f"分析TLS/SSL层时出错: {e}", exc_info=True)
            # 设置一些默认值以避免完全失败
            analysis.tls_content_type = None
    
    def _process_tls_content_type(self, content_type: int, analysis: PacketAnalysis, record: dict) -> None:
        """处理具体的TLS content type
        
        Args:
            content_type: TLS内容类型
            analysis: 数据包分析结果
            record: TLS记录字典
        """
        # 这个方法是累积性的，如果一个包里有多种类型，都会被标记为True
        if content_type == 20:
            analysis.is_tls_change_cipher_spec = True
        elif content_type == 21:
            analysis.is_tls_alert = True
        elif content_type == 22:
            analysis.is_tls_handshake = True
        elif content_type == 23:
            analysis.is_tls_application_data = True
        elif content_type == 24:
            analysis.is_tls_heartbeat = True
        else:
            self._logger.debug(f"未知的TLS content_type: {content_type}")
    
    def _generate_stream_id(self, src_ip: str, dst_ip: str, src_port: int, dst_port: int, protocol: str) -> str:
        """生成流ID - Phase 2重构版本，支持方向性
        
        Args:
            src_ip: 源IP地址
            dst_ip: 目标IP地址
            src_port: 源端口
            dst_port: 目标端口
            protocol: 协议类型
            
        Returns:
            流ID字符串（TCP协议包含方向性）
        """
        if protocol == 'TCP':
            # Phase 2: 使用TCPStreamManager生成方向性流ID
            direction = detect_packet_direction(
                src_ip, src_port, dst_ip, dst_port,
                src_ip, src_port, dst_ip, dst_port  # 基础连接就是当前包的方向
            )
            return self._tcp_stream_manager.generate_stream_id(
                src_ip, src_port, dst_ip, dst_port, direction
            )
        else:
            # 对于UDP等无连接协议，仍使用无方向的流ID
            if (src_ip, src_port) <= (dst_ip, dst_port):
                return f"{protocol}_{src_ip}:{src_port}_{dst_ip}:{dst_port}"
            else:
                return f"{protocol}_{dst_ip}:{dst_port}_{src_ip}:{src_port}"
    
    def _update_stream_info(self, analysis: PacketAnalysis) -> None:
        """更新流信息 - Phase 2增强版本，支持方向性和序列号跟踪
        
        Args:
            analysis: 数据包分析结果
        """
        stream_id = analysis.stream_id
        
        if stream_id not in self._streams:
            # 根据协议类型解析流信息
            parts = stream_id.split('_')
            protocol = parts[0]
            direction = None
            
            if protocol == 'ICMP':
                # ICMP流ID格式: ICMP_src_ip_dst_ip_type_code
                src_ip = parts[1]
                dst_ip = parts[2]
                icmp_type = parts[3]
                icmp_code = parts[4]
                
                # 创建ICMP流信息
                self._streams[stream_id] = StreamInfo(
                    stream_id=stream_id,
                    src_ip=src_ip,
                    dst_ip=dst_ip,
                    src_port=int(icmp_type),  # 使用type作为port
                    dst_port=int(icmp_code),  # 使用code作为port
                    protocol=protocol,
                    application_protocol=analysis.application_layer,
                    first_seen=analysis.timestamp,
                    last_seen=analysis.timestamp
                )
            elif protocol == 'DNS':
                # DNS流ID格式: DNS_src_ip:src_port_dst_ip:dst_port_transport_protocol
                src_endpoint = parts[1]
                dst_endpoint = parts[2]
                
                src_ip, src_port = src_endpoint.rsplit(':', 1)
                dst_ip, dst_port = dst_endpoint.rsplit(':', 1)
                
                # 创建DNS流信息
                self._streams[stream_id] = StreamInfo(
                    stream_id=stream_id,
                    src_ip=src_ip,
                    dst_ip=dst_ip,
                    src_port=int(src_port),
                    dst_port=int(dst_port),
                    protocol=protocol,
                    application_protocol=analysis.application_layer,
                    first_seen=analysis.timestamp,
                    last_seen=analysis.timestamp
                )
            elif protocol == 'TCP':
                # Phase 2: TCP流ID格式: TCP_src_ip:src_port_dst_ip:dst_port_direction
                if len(parts) >= 4:
                    src_endpoint = parts[1]
                    dst_endpoint = parts[2]
                    direction_str = parts[3] if len(parts) > 3 else 'forward'
                    
                    src_ip, src_port = src_endpoint.rsplit(':', 1)
                    dst_ip, dst_port = dst_endpoint.rsplit(':', 1)
                    
                    # 解析方向
                    direction = ConnectionDirection.FORWARD if direction_str == 'forward' else ConnectionDirection.REVERSE
                    
                    # 创建TCP流信息（包含方向）
                    self._streams[stream_id] = StreamInfo(
                        stream_id=stream_id,
                        src_ip=src_ip,
                        dst_ip=dst_ip,
                        src_port=int(src_port),
                        dst_port=int(dst_port),
                        protocol=protocol,
                        direction=direction,  # Phase 2: 添加方向信息
                        application_protocol=analysis.application_layer,
                        first_seen=analysis.timestamp,
                        last_seen=analysis.timestamp,
                        # Phase 2: 添加序列号跟踪
                        initial_seq=analysis.seq_number,
                        last_seq=analysis.seq_number
                    )
            else:
                # 标准UDP流ID格式: PROTOCOL_src_ip:src_port_dst_ip:dst_port
                src_endpoint = parts[1]
                dst_endpoint = parts[2]
                
                src_ip, src_port = src_endpoint.rsplit(':', 1)
                dst_ip, dst_port = dst_endpoint.rsplit(':', 1)
                
                # 创建标准流信息
                self._streams[stream_id] = StreamInfo(
                    stream_id=stream_id,
                    src_ip=src_ip,
                    dst_ip=dst_ip,
                    src_port=int(src_port),
                    dst_port=int(dst_port),
                    protocol=protocol,
                    application_protocol=analysis.application_layer,
                    first_seen=analysis.timestamp,
                    last_seen=analysis.timestamp
                )
        
        # 更新流统计信息
        stream_info = self._streams[stream_id]
        stream_info.packet_count += 1
        stream_info.total_bytes += analysis.payload_length
        stream_info.last_seen = analysis.timestamp
        
        # Phase 2: 更新序列号跟踪（仅对TCP协议）
        if stream_info.protocol == 'TCP' and analysis.seq_number is not None:
            if stream_info.initial_seq is None:
                stream_info.initial_seq = analysis.seq_number
                stream_info.last_seq = analysis.seq_number
            else:
                # 更新序列号范围
                stream_info.initial_seq = min(stream_info.initial_seq, analysis.seq_number)
                if analysis.seq_number + analysis.payload_length > stream_info.last_seq:
                    stream_info.last_seq = analysis.seq_number + analysis.payload_length
        
        # 更新应用层协议信息
        if analysis.application_layer and not stream_info.application_protocol:
            stream_info.application_protocol = analysis.application_layer
    
    def _calculate_sequence_ranges(self) -> None:
        """计算序列号范围"""
        for analysis in self._packet_analyses:
            if analysis.seq_number is not None:
                stream_id = analysis.stream_id
                if stream_id not in self._streams:
                    self._logger.warning(f"流{stream_id}缺少流信息，跳过")
                    continue
                
                stream_info = self._streams[stream_id]
                if stream_info.initial_seq is None or stream_info.last_seq is None:
                    stream_info.initial_seq = analysis.seq_number
                    stream_info.last_seq = analysis.seq_number
                else:
                    stream_info.initial_seq = min(stream_info.initial_seq, analysis.seq_number)
                    stream_info.last_seq = max(stream_info.last_seq, analysis.seq_number)
    
    def _generate_sequence_mask_table(self) -> SequenceMaskTable:
        """生成序列号掩码表"""
        self._logger.info("开始生成序列号掩码表...")
        
        sequence_mask_table = SequenceMaskTable()
        
        # 按流分组处理数据包分析结果
        stream_packets = defaultdict(list)
        for analysis in self._packet_analyses:
            stream_packets[analysis.stream_id].append(analysis)
        
        # 为每个流生成掩码条目（移除HTTP支持）
        for stream_id, packets in stream_packets.items():
            stream_info = self._streams.get(stream_id)
            if not stream_info:
                self._logger.warning(f"流{stream_id}缺少流信息，跳过")
                continue
            
            self._logger.info(f"处理流{stream_id}: 协议={stream_info.application_protocol}, 包数={len(packets)}")
            
            # 根据应用层协议生成不同的掩码策略（移除HTTP）
            if stream_info.application_protocol == 'TLS':
                self._logger.info(f"使用TLS掩码策略处理流{stream_id}")
                self._generate_tls_masks(sequence_mask_table, stream_id, packets)
            elif stream_info.application_protocol in ['ICMP', 'DNS']:
                # 新增：对ICMP和DNS协议使用完全保留策略
                self._logger.info(f"使用完全保留策略处理{stream_info.application_protocol}流{stream_id}")
                self._generate_preserve_all_masks(sequence_mask_table, stream_id, packets)
            else:
                # 对于其他协议（包括原来的HTTP），使用通用策略
                self._logger.info(f"使用通用掩码策略处理流{stream_id}，协议={stream_info.application_protocol}")
                self._generate_generic_masks(sequence_mask_table, stream_id, packets)
        
        # 完成序列号掩码表构建
        sequence_mask_table.finalize()
        
        self._logger.info(f"序列号掩码表生成完成，包含{sequence_mask_table.get_total_entry_count()}个条目")
        return sequence_mask_table
    
    def _generate_tls_masks(self, sequence_mask_table: SequenceMaskTable, stream_id: str, packets: List[PacketAnalysis]) -> None:
        """为TLS流生成掩码 - 简化版本
        
        Args:
            sequence_mask_table: 序列号掩码表
            stream_id: 流ID
            packets: 该流的数据包分析结果列表
        """
        # 先进行TLS流重组分析
        reassembled_packets = self._reassemble_tls_stream(packets)
        
        self._logger.info(f"生成TLS掩码：流{stream_id}，共{len(reassembled_packets)}个数据包")
        
        for packet in reassembled_packets:
            if packet.seq_number is None or packet.payload_length == 0:
                self._logger.debug(f"跳过数据包{packet.packet_number}: seq_number={packet.seq_number}, payload_length={packet.payload_length}")
                continue
            
            seq_start = packet.seq_number
            seq_end = seq_start + packet.payload_length
            
            # 简化的TLS策略：根据content type决定处理方式
            if packet.tls_content_type in [20, 21, 22, 24]:
                # TLS content type 20(ChangeCipherSpec), 21(Alert), 22(Handshake), 24(Heartbeat)
                # 完全保留这些重要的TLS控制和握手消息
                mask_spec = KeepAll()
                
                tls_type_name = {
                    20: "ChangeCipherSpec",
                    21: "Alert", 
                    22: "Handshake",
                    24: "Heartbeat"
                }.get(packet.tls_content_type, "Unknown")
                self._logger.info(f"TLS {tls_type_name}包{packet.packet_number}: 完全保留{packet.payload_length}字节")
                
            elif packet.tls_content_type == 23:
                # TLS content type 23 (ApplicationData)
                # 简化处理：全部置零，不保留任何载荷
                mask_spec = MaskAfter(0)
                self._logger.info(f"TLS ApplicationData包{packet.packet_number}: 全部掩码{packet.payload_length}字节")
                
            elif getattr(packet, 'tls_reassembled', False):
                # TLS重组包：根据重组记录类型决定掩码策略
                reassembly_info = getattr(packet, 'tls_reassembly_info', {})
                record_type = reassembly_info.get('record_type', 'Unknown')
                
                if record_type == 'ApplicationData':
                    # 重组的ApplicationData包按简化策略处理
                    mask_spec = MaskAfter(0)
                    self._logger.info(f"TLS重组包{packet.packet_number}: 全部掩码{packet.payload_length}字节 (ApplicationData重组)")
                else:
                    # 其他类型的重组包（Handshake, Alert等）完全保留
                    mask_spec = KeepAll()
                    self._logger.info(f"TLS重组包{packet.packet_number}: 完全保留{packet.payload_length}字节 ({record_type}重组)")
                    
            else:
                # 其他TLS包或未识别content_type的包：为安全起见，完全保留
                mask_spec = KeepAll()
                self._logger.warning(
                    f"TLS包{packet.packet_number}: 未能识别具体的Content Type或为其他类型。 "
                    f"为安全起见，将完全保留其载荷({packet.payload_length}字节)。"
                )
            
            # Phase 2: 确定掩码类型
            mask_type = "tls_unknown"
            if packet.tls_content_type == 22:
                mask_type = "tls_handshake"
            elif packet.tls_content_type == 23:
                mask_type = "tls_application_data"
            elif packet.tls_content_type in [20, 21, 24]:
                type_names = {20: "tls_change_cipher_spec", 21: "tls_alert", 24: "tls_heartbeat"}
                mask_type = type_names[packet.tls_content_type]
            elif getattr(packet, 'tls_reassembled', False):
                reassembly_info = getattr(packet, 'tls_reassembly_info', {})
                record_type = reassembly_info.get('record_type', 'Unknown')
                if record_type == 'ApplicationData':
                    mask_type = "tls_application_data_reassembled"
                else:
                    mask_type = "tls_reassembled"
            
            try:
                # Phase 2: 使用正确的序列号掩码表API
                sequence_mask_table.add_mask_range(
                    tcp_stream_id=stream_id,
                    seq_start=seq_start,
                    seq_end=seq_end,
                    mask_type=mask_type,
                    mask_spec=mask_spec
                )
                self._logger.debug(f"成功添加TLS掩码条目: {mask_type} [{seq_start}:{seq_end})")
            except StreamMaskTableError as e:
                self._logger.warning(f"添加TLS掩码条目失败: {e}")
    
    def _reassemble_tls_stream(self, packets: List[PacketAnalysis]) -> List[PacketAnalysis]:
        """TLS流重组逻辑，处理跨TCP段的TLS消息
        
        Args:
            packets: 原始数据包分析结果列表
            
        Returns:
            增强的数据包分析结果列表，包含TLS重组信息
        """
        # 按序列号排序
        sorted_packets = sorted(packets, key=lambda p: p.seq_number or 0)
        
        self._logger.debug(f"开始TLS流重组分析，共{len(sorted_packets)}个数据包")
        
        # 第一步：识别所有TLS跨段情况并标记
        for i, packet in enumerate(sorted_packets):
            # 检查是否是TLS包
            if packet.is_tls_handshake or packet.is_tls_application_data or \
               packet.is_tls_change_cipher_spec or packet.is_tls_alert or packet.is_tls_heartbeat:
                
                # 这是一个已识别的TLS包，检查是否需要向前重组
                tls_record_start = packet.seq_number
                tls_record_type = None
                
                if packet.is_tls_handshake:
                    tls_record_type = "Handshake"
                elif packet.is_tls_application_data:
                    tls_record_type = "ApplicationData"
                elif packet.is_tls_change_cipher_spec:
                    tls_record_type = "ChangeCipherSpec"
                elif packet.is_tls_alert:
                    tls_record_type = "Alert"
                elif packet.is_tls_heartbeat:
                    tls_record_type = "Heartbeat"
                
                self._logger.debug(f"发现TLS包{packet.packet_number} ({tls_record_type}), seq={packet.seq_number}, len={packet.payload_length}")
                
                # 向前查找可能的前导包
                j = i - 1
                
                self._logger.debug(f"开始向前查找前导包，当前索引i={i}, 开始索引j={j}, TLS包序列号={tls_record_start}")
                
                while j >= 0:
                    prev_packet = sorted_packets[j]
                    
                    self._logger.debug(f"检查前导包{prev_packet.packet_number}: seq={prev_packet.seq_number}, len={prev_packet.payload_length}, end={prev_packet.seq_number + prev_packet.payload_length if prev_packet.seq_number else None}, target_start={tls_record_start}")
                    
                    # 检查前一个包是否紧接着当前TLS包
                    if prev_packet.seq_number is not None and \
                       prev_packet.seq_number + prev_packet.payload_length == tls_record_start:
                        
                        self._logger.debug(f"前导包{prev_packet.packet_number}序列号连续，检查是否为TLS")
                        
                        # 检查前一个包是否可能是TLS但未被识别
                        if not (prev_packet.is_tls_handshake or prev_packet.is_tls_application_data or 
                               prev_packet.is_tls_change_cipher_spec or prev_packet.is_tls_alert or 
                               prev_packet.is_tls_heartbeat) and \
                           not getattr(prev_packet, 'tls_reassembled', False):  # 避免重复标记
                            
                            self._logger.info(f"检测到TLS跨段：包{prev_packet.packet_number} (seq={prev_packet.seq_number}, len={prev_packet.payload_length}) + 包{packet.packet_number} (seq={packet.seq_number}, len={packet.payload_length}) 组成{tls_record_type}")
                            
                            # 标记前一个包为TLS重组包
                            prev_packet.tls_reassembled = True
                            prev_packet.tls_reassembly_info = {
                                'record_type': tls_record_type,
                                'main_packet': packet.packet_number,
                                'position': 'preceding'
                            }
                            
                            tls_record_start = prev_packet.seq_number
                            j -= 1
                        else:
                            # 前一个包已经是TLS包或已被标记，停止向前查找
                            self._logger.debug(f"前导包{prev_packet.packet_number}已经是TLS包或已被标记，停止向前查找")
                            break
                    else:
                        # 序列号不连续，停止向前查找
                        self._logger.debug(f"前导包{prev_packet.packet_number}序列号不连续，停止向前查找")
                        break
        
        # 第二步：返回所有包（已经标记了重组信息）
        self._logger.info(f"TLS流重组完成，标记了{sum(1 for p in sorted_packets if getattr(p, 'tls_reassembled', False))}个重组包")
        return sorted_packets
    
    def _generate_preserve_all_masks(self, sequence_mask_table: SequenceMaskTable, stream_id: str, packets: List[PacketAnalysis]) -> None:
        """为需要完全保留的协议生成掩码（用于ICMP/DNS等）
        
        Args:
            sequence_mask_table: 序列号掩码表
            stream_id: 流ID
            packets: 该流的数据包分析结果列表
        """
        for packet in packets:
            if packet.payload_length == 0:
                self._logger.debug(f"跳过数据包{packet.packet_number}: 载荷长度为0")
                continue
            
            # 对于ICMP和DNS协议，完全保留所有内容
            mask_spec = KeepAll()
            
            if packet.application_layer == 'ICMP':
                # ICMP使用特殊的流ID格式，使用包编号作为序列号
                try:
                    sequence_mask_table.add_mask_range(
                        tcp_stream_id=stream_id,
                        seq_start=packet.packet_number,  # 使用包编号代替序列号
                        seq_end=packet.packet_number + packet.payload_length,
                        mask_type="icmp_preserve_all",
                        mask_spec=mask_spec
                    )
                    self._logger.info(f"ICMP包{packet.packet_number}: 完全保留{packet.payload_length}字节")
                except StreamMaskTableError as e:
                    self._logger.warning(f"添加ICMP掩码条目失败: {e}")
                    
            elif packet.application_layer == 'DNS':
                # DNS也没有序列号概念（基于UDP时），使用包编号作为序列号
                try:
                    sequence_mask_table.add_mask_range(
                        tcp_stream_id=stream_id,
                        seq_start=packet.packet_number,  # 使用包编号代替序列号
                        seq_end=packet.packet_number + packet.payload_length,
                        mask_type="dns_preserve_all",
                        mask_spec=mask_spec
                    )
                    self._logger.info(f"DNS包{packet.packet_number}: 完全保留{packet.payload_length}字节")
                except StreamMaskTableError as e:
                    self._logger.warning(f"添加DNS掩码条目失败: {e}")
            else:
                # 其他需要完全保留的协议，使用标准方式
                if packet.seq_number is not None:
                    seq_start = packet.seq_number
                    seq_end = seq_start + packet.payload_length
                    try:
                        sequence_mask_table.add_mask_range(
                            tcp_stream_id=stream_id,
                            seq_start=seq_start,
                            seq_end=seq_end,
                            mask_type=f"{packet.application_layer.lower()}_preserve_all",
                            mask_spec=mask_spec
                        )
                        self._logger.info(f"{packet.application_layer}包{packet.packet_number}: 完全保留{packet.payload_length}字节")
                    except StreamMaskTableError as e:
                        self._logger.warning(f"添加{packet.application_layer}掩码条目失败: {e}")
    
    def _generate_generic_masks(self, sequence_mask_table: SequenceMaskTable, stream_id: str, packets: List[PacketAnalysis]) -> None:
        """为通用流生成掩码
        
        Args:
            sequence_mask_table: 序列号掩码表
            stream_id: 流ID
            packets: 该流的数据包分析结果列表
        """
        for packet in packets:
            if packet.seq_number is None or packet.payload_length == 0:
                continue
            
            seq_start = packet.seq_number
            seq_end = seq_start + packet.payload_length
            
            # 对于未识别的协议，默认保留全部载荷
            mask_spec = KeepAll()
            
            try:
                sequence_mask_table.add_mask_range(
                    tcp_stream_id=stream_id,
                    seq_start=seq_start,
                    seq_end=seq_end,
                    mask_type="generic_mask_after",
                    mask_spec=mask_spec
                )
            except StreamMaskTableError as e:
                self._logger.warning(f"添加通用掩码条目失败: {e}")
    
    def _generate_statistics(self) -> Dict[str, Any]:
        """生成统计信息
        
        Returns:
            统计信息字典
        """
        total_packets = len(self._packet_analyses)
        total_streams = len(self._streams)
        
        # 按协议统计
        protocol_stats = defaultdict(int)
        application_stats = defaultdict(int)
        
        for analysis in self._packet_analyses:
            # 从stream_id提取传输层协议
            protocol = analysis.stream_id.split('_')[0]
            protocol_stats[protocol] += 1
            
            if analysis.application_layer:
                application_stats[analysis.application_layer] += 1
        
        # 按流统计
        stream_stats = {}
        for stream_id, stream_info in self._streams.items():
            stream_stats[stream_id] = {
                'packet_count': stream_info.packet_count,
                'total_bytes': stream_info.total_bytes,
                'application_protocol': stream_info.application_protocol,
                'duration': stream_info.last_seen - stream_info.first_seen if stream_info.last_seen and stream_info.first_seen else 0
            }
        
        return {
            'total_packets': total_packets,
            'total_streams': total_streams,
            'protocol_distribution': dict(protocol_stats),
            'application_distribution': dict(application_stats),
            'stream_details': stream_stats
        }
    
    def _update_stats(self, context: StageContext, packet_count: int, duration: float) -> None:
        """更新统计信息
        
        Args:
            context: 阶段执行上下文
            packet_count: 处理的数据包数量
            duration: 处理时间
        """
        # 统计各种TLS记录类型
        tls_change_cipher_spec_count = sum(1 for a in self._packet_analyses if a.is_tls_change_cipher_spec)
        tls_alert_count = sum(1 for a in self._packet_analyses if a.is_tls_alert)
        tls_handshake_count = sum(1 for a in self._packet_analyses if a.is_tls_handshake)
        tls_application_data_count = sum(1 for a in self._packet_analyses if a.is_tls_application_data)
        tls_heartbeat_count = sum(1 for a in self._packet_analyses if a.is_tls_heartbeat)
        
        self.stats.update({
            'packets_processed': packet_count,
            'streams_identified': len(self._streams),
            'execution_duration_seconds': duration,
            'packets_per_second': packet_count / duration if duration > 0 else 0,
            'mask_entries_generated': self._sequence_mask_table.get_total_entry_count() if self._sequence_mask_table else 0,
            'http_packets': sum(1 for a in self._packet_analyses if a.application_layer == 'HTTP'),
            'tls_packets': sum(1 for a in self._packet_analyses if a.application_layer == 'TLS'),
            'tls_change_cipher_spec_packets': tls_change_cipher_spec_count,
            'tls_alert_packets': tls_alert_count,
            'tls_handshake_packets': tls_handshake_count,
            'tls_application_data_packets': tls_application_data_count,
            'tls_heartbeat_packets': tls_heartbeat_count,
            'memory_cleanup_count': packet_count // self._memory_cleanup_interval
        })
        
        # 更新上下文统计信息
        context.stats.update(self.stats)
    
    def _cleanup_memory(self) -> None:
        """清理内存"""
        # 清理大型数据结构
        if hasattr(self, '_packet_analyses'):
            self._packet_analyses.clear()
        
        # 强制垃圾回收
        gc.collect()
        
        self._logger.debug("内存清理完成")
    
    def get_estimated_duration(self, context: StageContext) -> float:
        """估算处理时间
        
        Args:
            context: 阶段执行上下文
            
        Returns:
            估算的处理时间（秒）
        """
        if context.tshark_output:
            input_file = Path(context.tshark_output)
            if input_file.exists():
                file_size_mb = input_file.stat().st_size / (1024 * 1024)
                # PyShark分析比较耗时，估算每MB需要2秒
                return max(2.0, file_size_mb * 2.0)
        return 10.0
    
    def get_required_tools(self) -> List[str]:
        """获取所需工具列表
        
        Returns:
            工具名称列表
        """
        return ['pyshark']
    
    def check_tool_availability(self) -> Dict[str, bool]:
        """检查工具可用性
        
        Returns:
            工具可用性字典
        """
        return {
            'pyshark': pyshark is not None
        }
    
    def get_description(self) -> str:
        """获取Stage描述
        
        Returns:
            描述字符串
        """
        return ("使用PyShark分析网络协议，识别HTTP、TLS等应用层协议，"
                "提取流信息并生成智能掩码表，为载荷裁切提供精确指导")
    
    def _cleanup_impl(self, context: StageContext) -> None:
        """清理Stage资源
        
        Args:
            context: 阶段执行上下文
        """
        self._cleanup_memory()
        self._streams.clear()
        self._sequence_mask_table = None 

# ---- Phase 2 Revised Implementation(系统集成)：将旧 PySharkAnalyzer 别名到 EnhancedPySharkAnalyzer ----
from .enhanced_pyshark_analyzer import EnhancedPySharkAnalyzer as _EnhancedPySharkAnalyzer
PySharkAnalyzer = _EnhancedPySharkAnalyzer  # type: ignore
__all__ = ['PySharkAnalyzer'] 