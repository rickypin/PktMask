#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PyShark分析器

使用PyShark对经过TShark预处理的PCAP文件进行深度协议分析，
识别HTTP、TLS等应用层协议，提取流信息，并生成掩码表。
这是Enhanced Trim Payloads处理流程的第二阶段。
"""

import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple, Set
from collections import defaultdict
from dataclasses import dataclass
import gc

try:
    import pyshark
except ImportError:
    pyshark = None

from .base_stage import BaseStage, StageContext
from .stage_result import StageResult, StageStatus, StageMetrics
from ...processors.base_processor import ProcessorResult
from ..models.mask_table import StreamMaskTable, StreamMaskEntry
from ..models.mask_spec import MaskAfter, MaskRange, KeepAll, create_http_header_mask, create_tls_record_mask
from ..exceptions import StreamMaskTableError


@dataclass
class StreamInfo:
    """TCP/UDP流信息"""
    stream_id: str
    src_ip: str
    dst_ip: str
    src_port: int
    dst_port: int
    protocol: str  # 'TCP' or 'UDP'
    application_protocol: Optional[str] = None  # 'HTTP', 'TLS', etc.
    packet_count: int = 0
    total_bytes: int = 0
    first_seen: Optional[float] = None
    last_seen: Optional[float] = None


@dataclass
class PacketAnalysis:
    """数据包分析结果"""
    packet_number: int
    timestamp: float
    stream_id: str
    seq_number: Optional[int] = None
    payload_length: int = 0
    application_layer: Optional[str] = None
    is_http_request: bool = False
    is_http_response: bool = False
    is_tls_handshake: bool = False
    is_tls_application_data: bool = False
    is_tls_change_cipher_spec: bool = False  # content_type = 20
    is_tls_alert: bool = False               # content_type = 21  
    is_tls_heartbeat: bool = False           # content_type = 24
    tls_content_type: Optional[int] = None   # 存储原始content_type值
    http_header_length: Optional[int] = None
    tls_record_length: Optional[int] = None


class PySharkAnalyzer(BaseStage):
    """PyShark分析器
    
    负责使用PyShark执行以下分析任务：
    1. 协议识别 - 识别HTTP、TLS等应用层协议
    2. 流信息提取 - 提取TCP/UDP流的详细信息
    3. 掩码表生成 - 根据协议分析结果生成掩码表
    
    这是多阶段处理流程的第二阶段，接收TShark预处理器的输出，
    为Scapy回写器提供详细的掩码规范。
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化PyShark分析器
        
        Args:
            config: 配置参数字典，包含协议分析相关设置
        """
        super().__init__("PyShark分析器", config)
        
        # 协议配置
        self._analyze_http = self.get_config_value('analyze_http', True)
        self._analyze_tls = self.get_config_value('analyze_tls', True)
        self._analyze_tcp = self.get_config_value('analyze_tcp', True)
        self._analyze_udp = self.get_config_value('analyze_udp', True)
        
        # HTTP协议配置
        self._http_keep_headers = self.get_config_value('http_keep_headers', True)
        self._http_mask_body = self.get_config_value('http_mask_body', True)
        
        # TLS协议配置
        self._tls_keep_handshake = self.get_config_value('tls_keep_handshake', True)
        self._tls_mask_application_data = self.get_config_value('tls_mask_application_data', True)
        
        # 性能配置
        self._max_packets_per_batch = self.get_config_value('max_packets_per_batch', 1000)
        self._memory_cleanup_interval = self.get_config_value('memory_cleanup_interval', 5000)
        self._timeout_seconds = self.get_config_value('analysis_timeout_seconds', 600)
        
        # 内部状态
        self._streams: Dict[str, StreamInfo] = {}
        self._packet_analyses: List[PacketAnalysis] = []
        self._mask_table: Optional[StreamMaskTable] = None
        
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
        self._streams.clear()
        self._packet_analyses.clear()
        self._mask_table = None
        
        self._logger.info("PyShark分析器初始化完成")
    
    def validate_inputs(self, context: StageContext) -> bool:
        """验证输入参数
        
        Args:
            context: 阶段执行上下文
            
        Returns:
            验证是否成功
        """
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
        """执行PyShark分析
        
        Args:
            context: 阶段执行上下文
            
        Returns:
            处理结果
        """
        context.current_stage = self.name
        progress_callback = self.get_progress_callback(context)
        
        start_time = time.time()
        
        try:
            self._logger.info("开始PyShark协议分析...")
            
            # 临时启用DEBUG级别日志以便调试
            original_level = self._logger.level
            self._logger.setLevel(logging.DEBUG)
            
            # 阶段1: 打开PCAP文件
            progress_callback(0.0)
            input_file = Path(context.tshark_output)
            cap = self._open_pcap_file(input_file)
            
            # 阶段2: 分析数据包
            progress_callback(0.1)
            packet_count = self._analyze_packets(cap, progress_callback)
            
            # 阶段3: 生成掩码表
            progress_callback(0.8)
            self._mask_table = self._generate_mask_table()
            
            # 阶段4: 保存结果到上下文
            progress_callback(0.9)
            context.mask_table = self._mask_table
            context.pyshark_results = {
                'streams': self._streams,
                'packet_analyses': self._packet_analyses,
                'statistics': self._generate_statistics()
            }
            
            # 生成处理结果
            duration = time.time() - start_time
            self.record_execution_time(duration)
            
            # 更新统计信息
            self._update_stats(context, packet_count, duration)
            
            progress_callback(1.0)
            
            result = ProcessorResult(
                success=True,
                data=f"PyShark分析完成，处理{packet_count}个数据包，识别{len(self._streams)}个流",
                stats=self.get_stats()
            )
            
            self._logger.info(f"PyShark分析完成: {packet_count}个数据包, {len(self._streams)}个流, 耗时{duration:.2f}秒")
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            self._logger.error(f"PyShark分析失败: {e}")
            
            return ProcessorResult(
                success=False,
                error=f"PyShark分析失败: {str(e)}",
                stats=self.get_stats()
            )
        finally:
            # 清理内存
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
                use_json=True,       # 使用JSON输出以提高性能
                include_raw=False    # 不包含原始数据以节省内存
            )
            
            self._logger.debug(f"成功打开PCAP文件: {pcap_file}")
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
        """分析单个数据包
        
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
            
            # 检查是否为TCP或UDP
            if hasattr(packet, 'tcp'):
                return self._analyze_tcp_packet(packet, packet_number, timestamp)
            elif hasattr(packet, 'udp') and self._analyze_udp:
                return self._analyze_udp_packet(packet, packet_number, timestamp)
            else:
                return None
                
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
            
            # 检查应用层协议
            if self._analyze_http and has_http:
                self._logger.debug(f"数据包{packet_number}: 识别为HTTP")
                self._analyze_http_layer(packet.http, analysis)
            elif self._analyze_tls and (has_tls or has_ssl):
                tls_layer = packet.tls if has_tls else packet.ssl
                self._logger.debug(f"数据包{packet_number}: 识别为TLS/SSL")
                self._analyze_tls_layer(tls_layer, analysis)
            else:
                self._logger.debug(f"数据包{packet_number}: 未识别为HTTP/TLS，载荷长度={payload_length}")
            
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
    
    def _analyze_http_layer(self, http_layer, analysis: PacketAnalysis) -> None:
        """分析HTTP层
        
        Args:
            http_layer: PyShark HTTP层对象
            analysis: 数据包分析结果对象
        """
        try:
            analysis.application_layer = 'HTTP'
            
            # 检查是否为HTTP请求
            if hasattr(http_layer, 'request_method'):
                analysis.is_http_request = True
                
                # 计算HTTP头长度
                if hasattr(http_layer, 'request_full_uri'):
                    # 这是一个粗略的估算，实际实现可能需要更精确的计算
                    header_lines = []
                    if hasattr(http_layer, 'request_line'):
                        header_lines.append(http_layer.request_line)
                    
                    # 添加其他HTTP头字段
                    for field_name, field_value in http_layer._all_fields.items():
                        if field_name.startswith('http.'):
                            header_lines.append(f"{field_name}: {field_value}")
                    
                    # 估算头长度 (包括CRLF)
                    analysis.http_header_length = sum(len(line) + 2 for line in header_lines) + 2
            
            # 检查是否为HTTP响应
            elif hasattr(http_layer, 'response_code'):
                analysis.is_http_response = True
                
                # 计算HTTP响应头长度
                header_lines = []
                if hasattr(http_layer, 'response_line'):
                    header_lines.append(http_layer.response_line)
                
                # 添加响应头字段
                for field_name, field_value in http_layer._all_fields.items():
                    if field_name.startswith('http.'):
                        header_lines.append(f"{field_name}: {field_value}")
                
                analysis.http_header_length = sum(len(line) + 2 for line in header_lines) + 2
                
        except Exception as e:
            self._logger.debug(f"分析HTTP层时出错: {e}")
    
    def _analyze_tls_layer(self, tls_layer, analysis: PacketAnalysis) -> None:
        """分析TLS层
        
        Args:
            tls_layer: PyShark TLS层对象
            analysis: 数据包分析结果对象
        """
        try:
            analysis.application_layer = 'TLS'
            
            self._logger.debug(f"发现TLS包，数据包{analysis.packet_number}")
            
            # 检查TLS记录结构
            # PyShark将TLS信息存储在 tls_layer._all_fields 中
            all_fields = getattr(tls_layer, '_all_fields', {})
            
            # 查找TLS记录信息
            records_found = 0
            content_types_found = []
            
            # 方法1: 检查 tls.record 字段
            if 'tls.record' in all_fields:
                tls_record = all_fields['tls.record']
                
                # 处理单个记录和记录数组
                if isinstance(tls_record, list):
                    # 多个TLS记录
                    for i, record in enumerate(tls_record):
                        if isinstance(record, dict) and 'tls.record.content_type' in record:
                            content_type = int(record['tls.record.content_type'])
                            content_types_found.append(content_type)
                            records_found += 1
                            self._logger.debug(f"TLS记录{i+1}: content_type={content_type}")
                            
                            # 分析具体的content type
                            self._process_tls_content_type(content_type, analysis, record)
                            
                elif isinstance(tls_record, dict) and 'tls.record.content_type' in tls_record:
                    # 单个TLS记录
                    content_type = int(tls_record['tls.record.content_type'])
                    content_types_found.append(content_type)
                    records_found += 1
                    self._logger.debug(f"TLS记录: content_type={content_type}")
                    
                    # 分析具体的content type
                    self._process_tls_content_type(content_type, analysis, tls_record)
            
            # 方法2: 直接检查各种可能的字段名称
            if records_found == 0:
                possible_fields = [
                    'record_content_type', 'content_type', 
                    'tls.record.content_type', 'record.content_type'
                ]
                
                for field_name in possible_fields:
                    if hasattr(tls_layer, field_name):
                        content_type = int(getattr(tls_layer, field_name))
                        content_types_found.append(content_type)
                        records_found += 1
                        self._logger.debug(f"通过字段{field_name}找到content_type={content_type}")
                        
                        # 分析具体的content type
                        self._process_tls_content_type(content_type, analysis, {})
                        break
            
            if records_found > 0:
                self._logger.debug(f"数据包{analysis.packet_number}: 找到{records_found}个TLS记录，content_types={content_types_found}")
            else:
                self._logger.debug(f"数据包{analysis.packet_number}: 未找到TLS content type信息")
                # 如果找不到具体类型，但有TLS层，记录为通用TLS
                # 这样至少可以应用通用的TLS策略
                
        except Exception as e:
            self._logger.warning(f"分析TLS层时出错: {e}")
    
    def _process_tls_content_type(self, content_type: int, analysis: PacketAnalysis, record: dict) -> None:
        """处理具体的TLS content type
        
        Args:
            content_type: TLS内容类型
            analysis: 数据包分析结果
            record: TLS记录字典
        """
        # 存储原始content_type值
        analysis.tls_content_type = content_type
        
        # TLS记录类型识别
        if content_type == 20:
            analysis.is_tls_change_cipher_spec = True
            self._logger.debug(f"TLS ChangeCipherSpec包: 数据包{analysis.packet_number}")
        elif content_type == 21:
            analysis.is_tls_alert = True
            self._logger.debug(f"TLS Alert包: 数据包{analysis.packet_number}")
        elif content_type == 22:
            analysis.is_tls_handshake = True
            self._logger.debug(f"TLS Handshake包: 数据包{analysis.packet_number}")
        elif content_type == 23:
            analysis.is_tls_application_data = True
            self._logger.debug(f"TLS ApplicationData包: 数据包{analysis.packet_number}，载荷长度={analysis.payload_length}")
        elif content_type == 24:
            analysis.is_tls_heartbeat = True
            self._logger.debug(f"TLS Heartbeat包: 数据包{analysis.packet_number}")
        else:
            self._logger.warning(f"未知的TLS content_type: {content_type}，数据包{analysis.packet_number}")
            
        # TLS记录长度 (5字节头 + 记录长度)
        if 'tls.record.length' in record:
            try:
                record_length = int(record['tls.record.length'])
                analysis.tls_record_length = 5 + record_length
                self._logger.debug(f"TLS记录长度: 头部5字节 + 数据{record_length}字节 = {analysis.tls_record_length}字节")
            except (ValueError, TypeError):
                pass
    
    def _generate_stream_id(self, src_ip: str, dst_ip: str, src_port: int, dst_port: int, protocol: str) -> str:
        """生成流ID
        
        Args:
            src_ip: 源IP地址
            dst_ip: 目标IP地址
            src_port: 源端口
            dst_port: 目标端口
            protocol: 协议类型
            
        Returns:
            流ID字符串
        """
        # 对于TCP协议，需要区分方向以避免序列号冲突
        if protocol == 'TCP':
            # 生成基础流ID（标准化端点顺序）
            if (src_ip, src_port) <= (dst_ip, dst_port):
                base_stream_id = f"{protocol}_{src_ip}:{src_port}_{dst_ip}:{dst_port}"
                direction = "forward"  # 数据包方向与标准流方向一致
            else:
                base_stream_id = f"{protocol}_{dst_ip}:{dst_port}_{src_ip}:{src_port}"
                direction = "reverse"  # 数据包方向与标准流方向相反
            
            # 添加方向后缀以区分双向TCP流的序列号空间
            return f"{base_stream_id}_{direction}"
        else:
            # 对于UDP等无连接协议，仍使用无方向的流ID
            if (src_ip, src_port) <= (dst_ip, dst_port):
                return f"{protocol}_{src_ip}:{src_port}_{dst_ip}:{dst_port}"
            else:
                return f"{protocol}_{dst_ip}:{dst_port}_{src_ip}:{src_port}"
    
    def _update_stream_info(self, analysis: PacketAnalysis) -> None:
        """更新流信息
        
        Args:
            analysis: 数据包分析结果
        """
        stream_id = analysis.stream_id
        
        if stream_id not in self._streams:
            # 从stream_id解析流信息
            parts = stream_id.split('_')
            protocol = parts[0]
            src_endpoint = parts[1]
            dst_endpoint = parts[2]
            
            src_ip, src_port = src_endpoint.rsplit(':', 1)
            dst_ip, dst_port = dst_endpoint.rsplit(':', 1)
            
            # 创建新的流信息
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
        
        # 更新应用层协议信息
        if analysis.application_layer and not stream_info.application_protocol:
            stream_info.application_protocol = analysis.application_layer
    
    def _generate_mask_table(self) -> StreamMaskTable:
        """生成掩码表
        
        Returns:
            生成的流掩码表
        """
        self._logger.info("开始生成掩码表...")
        
        mask_table = StreamMaskTable()
        
        # 按流分组处理数据包分析结果
        stream_packets = defaultdict(list)
        for analysis in self._packet_analyses:
            stream_packets[analysis.stream_id].append(analysis)
        
        # 为每个流生成掩码条目
        for stream_id, packets in stream_packets.items():
            stream_info = self._streams.get(stream_id)
            if not stream_info:
                self._logger.warning(f"流{stream_id}缺少流信息，跳过")
                continue
            
            self._logger.info(f"处理流{stream_id}: 协议={stream_info.application_protocol}, 包数={len(packets)}")
            
            # 根据应用层协议生成不同的掩码策略
            if stream_info.application_protocol == 'HTTP':
                self._logger.info(f"使用HTTP掩码策略处理流{stream_id}")
                self._generate_http_masks(mask_table, stream_id, packets)
            elif stream_info.application_protocol == 'TLS':
                self._logger.info(f"使用TLS掩码策略处理流{stream_id}")
                self._generate_tls_masks(mask_table, stream_id, packets)
            else:
                # 对于其他协议，使用通用策略
                self._logger.info(f"使用通用掩码策略处理流{stream_id}，协议={stream_info.application_protocol}")
                self._generate_generic_masks(mask_table, stream_id, packets)
        
        # 完成掩码表构建
        mask_table.finalize()
        
        self._logger.info(f"掩码表生成完成，包含{mask_table.get_total_entry_count()}个条目")
        return mask_table
    
    def _generate_http_masks(self, mask_table: StreamMaskTable, stream_id: str, packets: List[PacketAnalysis]) -> None:
        """为HTTP流生成掩码
        
        Args:
            mask_table: 掩码表
            stream_id: 流ID
            packets: 该流的数据包分析结果列表
        """
        for packet in packets:
            if not packet.is_http_request and not packet.is_http_response:
                continue
            
            if packet.seq_number is None or packet.payload_length == 0:
                continue
            
            seq_start = packet.seq_number
            seq_end = seq_start + packet.payload_length
            
            # 根据配置决定掩码策略
            if self._http_keep_headers and packet.http_header_length:
                # 保留HTTP头，掩码消息体
                if packet.http_header_length < packet.payload_length:
                    mask_spec = MaskAfter(packet.http_header_length)
                else:
                    mask_spec = KeepAll()
            elif self._http_mask_body:
                # 完全掩码HTTP载荷
                mask_spec = MaskAfter(0)
            else:
                # 保留全部
                mask_spec = KeepAll()
            
            try:
                mask_table.add_mask_range(stream_id, seq_start, seq_end, mask_spec)
            except StreamMaskTableError as e:
                self._logger.warning(f"添加HTTP掩码条目失败: {e}")
    
    def _generate_tls_masks(self, mask_table: StreamMaskTable, stream_id: str, packets: List[PacketAnalysis]) -> None:
        """为TLS流生成掩码
        
        Args:
            mask_table: 掩码表
            stream_id: 流ID
            packets: 该流的数据包分析结果列表
        """
        self._logger.info(f"为TLS流{stream_id}生成掩码，包含{len(packets)}个数据包")
        
        # 新增：TLS流重组逻辑，处理跨TCP段的TLS消息
        packets_with_tls_context = self._reassemble_tls_stream(packets)
        
        for packet in packets_with_tls_context:
            self._logger.debug(f"检查数据包{packet.packet_number}: content_type={packet.tls_content_type}, payload_len={packet.payload_length}, tls_reassembled={getattr(packet, 'tls_reassembled', False)}")
            
            # 检查是否是TLS包或TLS重组包
            is_tls_packet = (packet.is_tls_handshake or packet.is_tls_application_data or 
                           packet.is_tls_change_cipher_spec or packet.is_tls_alert or packet.is_tls_heartbeat or
                           getattr(packet, 'tls_reassembled', False))
            
            if not is_tls_packet:
                self._logger.debug(f"跳过数据包{packet.packet_number}: 不是TLS包")
                continue
            
            if packet.seq_number is None or packet.payload_length == 0:
                self._logger.debug(f"跳过数据包{packet.packet_number}: seq_number={packet.seq_number}, payload_length={packet.payload_length}")
                continue
            
            seq_start = packet.seq_number
            seq_end = seq_start + packet.payload_length
            
            # 根据TLS记录类型或重组状态决定掩码策略
            if packet.tls_content_type == 23 and packet.is_tls_application_data and self._tls_mask_application_data:
                # 23 (ApplicationData): 保留TLS记录头，掩码应用数据
                if packet.tls_record_length and packet.tls_record_length >= 5:
                    mask_spec = MaskAfter(5)  # 保留5字节TLS记录头
                    self._logger.info(f"TLS ApplicationData包{packet.packet_number}: 保留5字节头，掩码其余{packet.payload_length-5}字节")
                    self._logger.info(f"    序列号范围: {seq_start}-{seq_end} (载荷长度={packet.payload_length})")
                else:
                    mask_spec = MaskAfter(0)  # 完全掩码
                    self._logger.info(f"TLS ApplicationData包{packet.packet_number}: 完全掩码{packet.payload_length}字节")
            elif getattr(packet, 'tls_reassembled', False):
                # TLS重组包：根据重组记录类型决定掩码策略
                reassembly_info = getattr(packet, 'tls_reassembly_info', {})
                record_type = reassembly_info.get('record_type', 'Unknown')
                
                if record_type == 'ApplicationData' and self._tls_mask_application_data:
                    # 重组的ApplicationData包仍然应用掩码策略
                    mask_spec = MaskAfter(5)
                    self._logger.info(f"TLS重组包{packet.packet_number}: 保留5字节头，掩码其余{packet.payload_length - 5}字节 (属于{record_type})")
                else:
                    # 其他类型的重组包（Handshake, Alert等）保留全部载荷
                    mask_spec = KeepAll()
                    self._logger.info(f"TLS重组包{packet.packet_number}: 保留全部载荷{packet.payload_length}字节 (属于{record_type})")
            elif (packet.tls_content_type in [20, 21, 22, 24] and 
                  (packet.is_tls_change_cipher_spec or packet.is_tls_alert or 
                   packet.is_tls_handshake or packet.is_tls_heartbeat)):
                # 20 (ChangeCipherSpec), 21 (Alert), 22 (Handshake), 24 (Heartbeat): 保留全包
                mask_spec = KeepAll()
                
                tls_type_name = {
                    20: "ChangeCipherSpec",
                    21: "Alert", 
                    22: "Handshake",
                    24: "Heartbeat"
                }.get(packet.tls_content_type, "Unknown")
                self._logger.info(f"TLS {tls_type_name}包{packet.packet_number}: 保留全部载荷{packet.payload_length}字节")
            else:
                # 其他情况，根据配置决定
                if self._tls_keep_handshake:
                    mask_spec = KeepAll()
                    self._logger.info(f"TLS包{packet.packet_number}: 保留全部载荷 (配置决定)")
                else:
                    mask_spec = MaskAfter(0)
                    self._logger.info(f"TLS包{packet.packet_number}: 完全掩码 (配置决定)")
            
            try:
                mask_table.add_mask_range(stream_id, seq_start, seq_end, mask_spec)
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
    
    def _generate_generic_masks(self, mask_table: StreamMaskTable, stream_id: str, packets: List[PacketAnalysis]) -> None:
        """为通用流生成掩码
        
        Args:
            mask_table: 掩码表
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
                mask_table.add_mask_range(stream_id, seq_start, seq_end, mask_spec)
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
            'mask_entries_generated': self._mask_table.get_total_entry_count() if self._mask_table else 0,
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
        self._mask_table = None 