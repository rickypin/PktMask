"""
HTTP扫描式载荷处理策略

基于"算力换复杂度"的设计理念，使用简单特征扫描替代复杂HTTP协议解析，
实现更可靠、更高效、更易维护的HTTP头部保留系统。

设计原则:
1. 保守安全策略：宁可多保留，不可误掩码
2. 简单逻辑优先：用多次简单扫描替代复杂解析  
3. 零破坏集成：完全兼容BaseStrategy接口
4. 性能优先：算力换复杂度，提升处理性能

作者: PktMask Team
创建时间: 2025-01-16
版本: 1.0.0
"""

from typing import Dict, Any, List, Optional, Tuple
import re
import logging
import time
from dataclasses import dataclass

from .base_strategy import BaseStrategy, ProtocolInfo, TrimContext, TrimResult
from ..models.mask_spec import MaskSpec, MaskAfter, MaskRange, KeepAll
from ..models.scan_result import (
    ScanResult, MessageBoundary, ChunkInfo, ChunkedAnalysis,
    HttpPatterns, ScanConstants
)
from ..algorithms.boundary_detection import (
    BoundaryDetector, 
    BoundaryDetectionResult,
    HeaderBoundaryPattern,
    MessageBoundaryInfo
)
from ..algorithms.content_length_parser import (
    ContentLengthParser,
    ContentLengthResult,
    ChunkedEncoder,
    ChunkedAnalysisResult
)


class HTTPScanningStrategy(BaseStrategy):
    """
    HTTP扫描式载荷处理策略
    
    基于特征模式匹配的HTTP处理策略，专注于HTTP/1.x明文协议的高效处理。
    使用四层扫描算法替代复杂的协议解析，提供可靠的载荷裁切能力。
    
    支持场景:
    - HTTP/1.0 和 HTTP/1.1 明文协议
    - Content-Length定长消息体
    - Transfer-Encoding: chunked (智能采样策略)
    - Keep-Alive多消息 (保守处理策略)
    - 跨数据包HTTP头部 (基于TShark重组)
    - 大文件下载场景 (窗口扫描优化)
    
    不支持场景:
    - HTTP/2 二进制协议
    - HTTP/3 QUIC协议
    - HTTPS TLS加密协议 (已有专门TLS策略)
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化扫描式HTTP策略
        
        Args:
            config: 策略配置字典
        """
        super().__init__(config)
        
        # 扫描策略默认配置
        self._default_config = {
            # 扫描窗口配置
            'max_scan_window': ScanConstants.MAX_SCAN_WINDOW,
            'header_boundary_timeout_ms': ScanConstants.SCAN_TIMEOUT_MS,
            
            # Chunked处理配置
            'chunked_sample_size': ScanConstants.CHUNKED_SAMPLE_SIZE,
            'max_chunks_to_analyze': ScanConstants.MAX_CHUNKS_TO_ANALYZE,
            
            # 多消息处理配置
            'multi_message_mode': 'conservative',  # "conservative" | "aggressive"
            'max_messages_per_payload': ScanConstants.MAX_MESSAGES_PER_PAYLOAD,
            
            # 保守策略配置
            'fallback_on_error': True,
            'conservative_preserve_ratio': ScanConstants.CONSERVATIVE_PRESERVE_RATIO,
            
            # 调试和监控
            'enable_scan_logging': False,
            'performance_metrics_enabled': True,
            
            # 质量控制
            'confidence_threshold': ScanConstants.MEDIUM_CONFIDENCE,
            'enable_multi_pattern_matching': True
        }
        
        # 合并用户配置和默认配置
        for key, default_value in self._default_config.items():
            if key not in self.config:
                self.config[key] = default_value
        
        # 初始化扫描模式缓存
        self._pattern_cache = {}
        
        # 初始化优化算法引擎
        self._boundary_detector = BoundaryDetector(
            max_scan_distance=self.config['max_scan_window'],
            enable_logging=self.config.get('enable_scan_logging', False)
        )
        
        self._content_parser = ContentLengthParser(
            enable_logging=self.config.get('enable_scan_logging', False)
        )
        
        self._chunked_encoder = ChunkedEncoder(
            max_chunks=self.config.get('max_chunks_to_analyze', 50),
            enable_logging=self.config.get('enable_scan_logging', False)
        )
        
        self.logger.info("=== HTTP扫描式策略初始化 ===")
        self.logger.info(f"协议支持: HTTP/1.0, HTTP/1.1 明文协议")
        self.logger.info(f"扫描窗口: {self.config['max_scan_window']} 字节")
        self.logger.info(f"置信度阈值: {self.config['confidence_threshold']:.2f}")
        self.logger.info(f"Chunked样本大小: {self.config['chunked_sample_size']} 字节")
        self.logger.info(f"算法引擎: 优化边界检测、内容长度解析、Chunked编码处理")
        
    @property
    def supported_protocols(self) -> List[str]:
        """返回支持的协议列表"""
        return ['HTTP']  # 仅支持明文HTTP，HTTPS由TLS策略处理
        
    @property
    def strategy_name(self) -> str:
        """返回策略名称"""
        return 'http_scanning'
        
    @property
    def priority(self) -> int:
        """返回策略优先级"""
        # 扫描策略优先级略低于原HTTP策略，支持双策略共存
        return 75
        
    def can_handle(self, protocol_info: ProtocolInfo, context: TrimContext) -> bool:
        """
        判断是否可以处理指定的协议和上下文
        
        Args:
            protocol_info: 协议信息
            context: 裁切上下文
            
        Returns:
            True 如果可以处理，False 否则
        """
        # 扫描策略能力判断日志
        if self.config.get('enable_scan_logging'):
            self.logger.debug(f"包{getattr(context, 'packet_index', 'N/A')}: "
                             f"评估扫描策略处理能力 - 协议={protocol_info.name}")
        
        # 检查协议名称 - 仅支持明文HTTP
        if protocol_info.name.upper() != 'HTTP':
            return False
            
        # 检查是否是应用层协议
        if protocol_info.layer != 7:
            return False
            
        # 检查端口号（可选，更宽松的匹配）
        if protocol_info.port:
            # HTTP常见端口范围
            http_ports = {80, 8080, 8000, 8008, 3000, 5000, 9000, 8888, 9999}
            if protocol_info.port not in http_ports:
                # 端口不匹配但仍可能是HTTP，通过内容检测
                if self.config.get('enable_scan_logging'):
                    self.logger.debug(f"端口{protocol_info.port}不在HTTP标准端口，"
                                     f"将通过内容特征检测")
        
        return True
        
    def analyze_payload(self, payload: bytes, protocol_info: ProtocolInfo, 
                       context: TrimContext) -> Dict[str, Any]:
        """
        分析HTTP载荷结构 - 四层扫描算法
        
        Args:
            payload: 原始载荷数据
            protocol_info: 协议信息
            context: 裁切上下文
            
        Returns:
            HTTP载荷分析结果字典
        """
        start_time = time.perf_counter()
        packet_id = getattr(context, 'packet_index', 'N/A')
        
        if self.config.get('enable_scan_logging'):
            self.logger.debug(f"包{packet_id}: === HTTP载荷扫描分析开始 ===")
            self.logger.debug(f"包{packet_id}: 载荷大小={len(payload)}字节")
        
        try:
            # Step 1: 协议和结构识别扫描 (5-15ms)
            scan_result = self._scan_protocol_features(payload, packet_id)
            
            if not scan_result.is_http:
                # 不是HTTP协议，返回失败结果
                return {
                    'scan_result': scan_result,
                    'is_http': False,
                    'analysis_duration_ms': (time.perf_counter() - start_time) * 1000
                }
            
            # Step 2: 消息边界精确检测 (10-40ms)
            self._detect_message_boundaries(payload, scan_result, packet_id)
            
            # Step 3: 智能保留策略生成 (5-20ms)
            self._generate_preserve_strategy(payload, scan_result, packet_id)
            
            # Step 4: 安全性验证和最终调整 (2-8ms)
            self._validate_and_adjust_result(payload, scan_result, packet_id)
            
            # 记录扫描耗时
            scan_duration = (time.perf_counter() - start_time) * 1000
            scan_result.scan_duration_ms = scan_duration
            
            if self.config.get('enable_scan_logging'):
                self.logger.debug(f"包{packet_id}: 扫描完成，耗时{scan_duration:.2f}ms，"
                                 f"置信度{scan_result.confidence:.2f}")
            
            return {
                'scan_result': scan_result,
                'is_http': scan_result.is_http,
                'header_boundary': scan_result.header_boundary,
                'confidence': scan_result.confidence,
                'scan_method': scan_result.scan_method,
                'preserve_bytes': scan_result.total_preserve_bytes,
                'analysis_duration_ms': scan_duration
            }
            
        except Exception as e:
            # 异常情况保守回退
            self.logger.warning(f"包{packet_id}: 扫描异常 - {str(e)}")
            fallback_result = ScanResult.conservative_fallback(f"扫描异常: {str(e)}")
            return {
                'scan_result': fallback_result,
                'is_http': False,
                'error': str(e),
                'analysis_duration_ms': (time.perf_counter() - start_time) * 1000
            }
    
    def generate_mask_spec(self, payload: bytes, protocol_info: ProtocolInfo,
                          context: TrimContext, analysis: Dict[str, Any]) -> TrimResult:
        """
        生成HTTP掩码规范
        
        Args:
            payload: 原始载荷数据
            protocol_info: 协议信息
            context: 裁切上下文
            analysis: 载荷分析结果
            
        Returns:
            裁切结果
        """
        start_time = time.perf_counter()
        packet_id = getattr(context, 'packet_index', 'N/A')
        
        try:
            # 验证分析结果
            scan_result = analysis.get('scan_result')
            if not scan_result or not isinstance(scan_result, ScanResult):
                return TrimResult(
                    success=False,
                    mask_spec=KeepAll(),
                    preserved_bytes=len(payload),
                    trimmed_bytes=0,
                    confidence=0.0,
                    reason="无效的扫描分析结果",
                    warnings=["分析结果格式错误"],
                    metadata={'strategy': 'scanning_validation_failed'}
                )
            
            # 检查HTTP识别结果
            if not scan_result.is_http:
                return TrimResult(
                    success=False,
                    mask_spec=KeepAll(),
                    preserved_bytes=len(payload),
                    trimmed_bytes=0,
                    confidence=0.0,
                    reason="未识别为HTTP协议",
                    warnings=scan_result.warnings,
                    metadata={'strategy': 'scanning_not_http', 'scan_result': scan_result}
                )
            
            # 检查置信度阈值
            confidence_threshold = self.config.get('confidence_threshold', ScanConstants.MEDIUM_CONFIDENCE)
            if scan_result.confidence < confidence_threshold:
                return TrimResult(
                    success=False,
                    mask_spec=KeepAll(),
                    preserved_bytes=len(payload),
                    trimmed_bytes=0,
                    confidence=scan_result.confidence,
                    reason=f"HTTP识别置信度不足 ({scan_result.confidence:.2f} < {confidence_threshold})",
                    warnings=scan_result.warnings,
                    metadata={'strategy': 'scanning_low_confidence', 'scan_result': scan_result}
                )
            
            # 创建掩码规范
            mask_spec = self._create_scanning_mask_spec(payload, scan_result, packet_id)
            
            # 计算保留和裁切字节数
            preserved_bytes = scan_result.preserve_bytes or len(payload)
            preserved_bytes = min(preserved_bytes, len(payload))  # 确保不超过载荷大小
            trimmed_bytes = len(payload) - preserved_bytes
            
            # 生成处理原因
            reason = self._generate_scanning_reason(scan_result, preserved_bytes, trimmed_bytes)
            
            # 记录处理耗时
            processing_duration = (time.perf_counter() - start_time) * 1000
            
            if self.config.get('enable_scan_logging'):
                self.logger.debug(f"包{packet_id}: 掩码生成完成，"
                                 f"保留{preserved_bytes}字节，裁切{trimmed_bytes}字节，"
                                 f"耗时{processing_duration:.2f}ms")
            
            return TrimResult(
                success=True,
                mask_spec=mask_spec,
                preserved_bytes=preserved_bytes,
                trimmed_bytes=trimmed_bytes,
                confidence=scan_result.confidence,
                reason=reason,
                warnings=scan_result.warnings,
                metadata={
                    'strategy': 'scanning',
                    'scan_method': scan_result.scan_method,
                    'preserve_strategy': scan_result.preserve_strategy,
                    'processing_duration_ms': processing_duration,
                    'scan_result': scan_result
                }
            )
            
        except Exception as e:
            self.logger.error(f"包{packet_id}: HTTP扫描策略掩码生成异常: {e}", exc_info=True)
            return TrimResult(
                success=False,
                mask_spec=KeepAll(),
                preserved_bytes=len(payload),
                trimmed_bytes=0,
                confidence=0.0,
                reason=f"掩码生成异常: {str(e)}",
                warnings=[f"掩码生成异常，保守保留所有内容"],
                metadata={'strategy': 'scanning_error_fallback'}
            )

    def _create_scanning_mask_spec(self, payload: bytes, scan_result: ScanResult, 
                                 packet_id: str) -> MaskSpec:
        """
        创建扫描式掩码规范
        
        Args:
            payload: 载荷数据
            scan_result: 扫描结果
            packet_id: 数据包ID
            
        Returns:
            掩码规范
        """
        preserve_bytes = scan_result.preserve_bytes or len(payload)
        
        if preserve_bytes >= len(payload):
            # 保留全部内容
            return KeepAll()
        elif preserve_bytes <= 0:
            # 异常情况，保守处理
            return KeepAll()
        else:
            # 保留前N字节，掩码其余部分
            return MaskAfter(preserve_bytes)

    def _generate_scanning_reason(self, scan_result: ScanResult, 
                                preserved_bytes: int, trimmed_bytes: int) -> str:
        """
        生成扫描处理原因
        
        Args:
            scan_result: 扫描结果
            preserved_bytes: 保留字节数
            trimmed_bytes: 裁切字节数
            
        Returns:
            处理原因字符串
        """
        if scan_result.is_chunked:
            return (f"HTTP Chunked响应扫描处理: 保留{preserved_bytes}字节头部和样本数据, "
                   f"裁切{trimmed_bytes}字节消息体")
        elif hasattr(scan_result, 'message_count') and scan_result.message_count and scan_result.message_count > 1:
            return (f"HTTP多消息扫描处理: 检测到{scan_result.message_count}个消息, "
                   f"保留{preserved_bytes}字节头部, 裁切{trimmed_bytes}字节消息体")
        elif len(scan_result.message_boundaries) > 1:
            return (f"HTTP多消息扫描处理: 检测到{len(scan_result.message_boundaries)}个消息, "
                   f"保留{preserved_bytes}字节头部, 裁切{trimmed_bytes}字节消息体")
        else:
            return (f"HTTP单消息扫描处理: 保留{preserved_bytes}字节头部, "
                   f"裁切{trimmed_bytes}字节消息体")

    def _scan_protocol_features(self, payload: bytes, packet_id: str) -> ScanResult:
        """
        Step 1: 协议特征识别扫描
        
        Args:
            payload: 载荷数据
            packet_id: 数据包ID
            
        Returns:
            初步扫描结果
        """
        # 限制扫描窗口避免性能问题
        scan_window = payload[:self.config['max_scan_window']]
        
        # 首先检测是否为chunked编码
        is_chunked = any(pattern in scan_window 
                        for pattern in HttpPatterns.CHUNKED_INDICATORS)
        
        # 检测HTTP请求特征
        for pattern in HttpPatterns.REQUEST_METHODS:
            if scan_window.startswith(pattern):
                result = ScanResult.create_success(
                    header_boundary=0,  # 临时值，后续更新
                    confidence=ScanConstants.HIGH_CONFIDENCE,
                    scan_method='request_pattern_match',
                    message_type='request',
                    method=pattern.decode('ascii').strip()
                )
                # 如果检测到chunked，设置标志
                if is_chunked:
                    result.is_chunked = True
                    result.scan_method += '_chunked'
                return result
        
        # 检测HTTP响应特征
        for pattern in HttpPatterns.RESPONSE_VERSIONS:
            if scan_window.startswith(pattern):
                result = ScanResult.create_success(
                    header_boundary=0,  # 临时值，后续更新
                    confidence=ScanConstants.HIGH_CONFIDENCE,
                    scan_method='response_pattern_match',
                    message_type='response',
                    http_version=pattern.decode('ascii').strip()
                )
                # 如果检测到chunked，设置标志
                if is_chunked:
                    result.is_chunked = True
                    result.scan_method += '_chunked'
                return result
        
        # 如果发现chunked编码特征，但没有明确的HTTP开头
        if is_chunked:
            # 发现chunked编码特征，但需要进一步验证HTTP头
            result = self._try_find_http_in_window(scan_window, packet_id)
            if result.is_http:
                result.is_chunked = True
                result.scan_method = 'chunked_pattern_match'
                return result
        
        # 尝试在窗口中查找HTTP特征
        return self._try_find_http_in_window(scan_window, packet_id)
    
    def _try_find_http_in_window(self, scan_window: bytes, packet_id: str) -> ScanResult:
        """
        在扫描窗口中尝试查找HTTP特征
        
        Args:
            scan_window: 扫描窗口数据
            packet_id: 数据包ID
            
        Returns:
            扫描结果
        """
        # 检查是否包含HTTP版本信息
        http_version_match = re.search(rb'HTTP/(\d+\.\d+)', scan_window)
        if http_version_match:
            version = http_version_match.group(1).decode('ascii')
            if version in ['1.0', '1.1']:
                return ScanResult.create_success(
                    header_boundary=0,  # 临时值
                    confidence=ScanConstants.MEDIUM_CONFIDENCE,
                    scan_method='version_pattern_match',
                    http_version=f"HTTP/{version}"
                )
        
        # 检查是否包含HTTP内容指示器
        content_indicators_found = sum(1 for pattern in HttpPatterns.CONTENT_INDICATORS
                                     if pattern in scan_window)
        
        if content_indicators_found >= 2:
            # 找到多个内容指示器，可能是HTTP
            return ScanResult.create_success(
                header_boundary=0,  # 临时值
                confidence=ScanConstants.MEDIUM_CONFIDENCE,
                scan_method='content_indicators_match'
            )
        
        # 未找到明确的HTTP特征
        return ScanResult.conservative_fallback("未检测到HTTP协议特征")
    
    def _detect_message_boundaries(self, payload: bytes, scan_result: ScanResult, 
                                  packet_id: str):
        """
        Step 2: 消息边界精确检测
        
        Args:
            payload: 载荷数据
            scan_result: 扫描结果（会被修改）
            packet_id: 数据包ID
        """
        if scan_result.is_chunked:
            self._detect_chunked_boundaries(payload, scan_result, packet_id)
        else:
            self._detect_standard_boundaries(payload, scan_result, packet_id)
    
    def _detect_standard_boundaries(self, payload: bytes, scan_result: ScanResult,
                                   packet_id: str):
        """检测标准HTTP消息边界 - 使用优化的边界检测算法"""
        
        # 使用优化的边界检测算法
        boundary_result = self._boundary_detector.detect_header_boundary(payload)
        
        if not boundary_result.found:
            scan_result.header_boundary = -1
            scan_result.confidence = 0.0
            scan_result.add_warning("未找到HTTP头部边界")
            if self.config.get('enable_scan_logging'):
                self.logger.debug(f"包{packet_id}: 边界检测失败 - {boundary_result.scan_method}")
            return
        
        scan_result.header_boundary = boundary_result.position
        scan_result.confidence = max(scan_result.confidence, boundary_result.confidence)
        scan_result.scan_method += '_single_message_optimized'
        
        if self.config.get('enable_scan_logging'):
            self.logger.debug(f"包{packet_id}: 优化边界检测成功 位置={boundary_result.position}, "
                             f"模式={boundary_result.pattern.name}, "
                             f"置信度={boundary_result.confidence:.2f}")
        
        # 使用优化的Content-Length解析算法
        header_content = payload[:boundary_result.body_start_position]
        content_result = self._content_parser.parse_content_length(header_content)
        
        if content_result.found:
            scan_result.content_length = content_result.length
            scan_result.has_content_length = True
            scan_result.confidence = max(scan_result.confidence, content_result.confidence)
            
            if self.config.get('enable_scan_logging'):
                self.logger.debug(f"包{packet_id}: Content-Length={content_result.length}, "
                                 f"置信度={content_result.confidence:.2f}, "
                                 f"方法={content_result.parsing_method}")
        else:
            # 未找到Content-Length时的处理
            scan_result.has_content_length = False
            if self.config.get('enable_scan_logging'):
                self.logger.debug(f"包{packet_id}: 未找到Content-Length，采用保守策略")
    
    def _detect_chunked_boundaries(self, payload: bytes, scan_result: ScanResult,
                                  packet_id: str):
        """
        检测Chunked编码边界 - 使用优化的Chunked处理算法
        
        Args:
            payload: 载荷数据
            scan_result: 扫描结果（会被修改）
            packet_id: 数据包ID
        """
        if self.config.get('enable_scan_logging'):
            self.logger.debug(f"包{packet_id}: 开始优化Chunked边界检测")
            
        # 步骤1: 使用优化的边界检测算法查找HTTP头部边界
        boundary_result = self._boundary_detector.detect_header_boundary(payload)
        
        if not boundary_result.found:
            scan_result.header_boundary = -1
            scan_result.confidence = 0.0
            scan_result.add_warning("Chunked响应未找到HTTP头部边界")
            if self.config.get('enable_scan_logging'):
                self.logger.debug(f"包{packet_id}: Chunked头部边界检测失败")
            return
            
        scan_result.header_boundary = boundary_result.position
        scan_result.confidence = max(scan_result.confidence, boundary_result.confidence)
        
        # 步骤2: 使用优化的Chunked编码分析器
        chunk_data_start = boundary_result.body_start_position
        chunked_analysis_result = self._chunked_encoder.analyze_chunked_structure(payload, chunk_data_start)
        
        if not chunked_analysis_result.is_chunked:
            # Chunked检测失败，回退到标准处理
            scan_result.confidence = ScanConstants.LOW_CONFIDENCE
            scan_result.add_warning("Chunked结构分析失败，回退到标准处理")
            if self.config.get('enable_scan_logging'):
                self.logger.debug(f"包{packet_id}: Chunked结构分析失败，方法={chunked_analysis_result.analysis_method}")
            return
            
        # 步骤3: 根据优化的Chunked分析结果确定保留策略
        scan_result.scan_method += '_chunked_optimized'
        scan_result.confidence = max(scan_result.confidence, chunked_analysis_result.confidence)
        
        if self.config.get('enable_scan_logging'):
            self.logger.debug(f"包{packet_id}: Chunked结构分析成功: "
                             f"{len(chunked_analysis_result.chunks)}个chunk, "
                             f"总数据{chunked_analysis_result.total_data_size}字节, "
                             f"完整性={chunked_analysis_result.is_complete}")
        
        if chunked_analysis_result.is_complete:
            # 完整的Chunked响应 - 使用优化策略
            self._apply_complete_chunked_strategy_optimized(payload, scan_result, chunked_analysis_result, packet_id)
        else:
            # 不完整的Chunked响应 - 使用保守策略
            self._apply_incomplete_chunked_strategy_optimized(payload, scan_result, chunked_analysis_result, packet_id)

    def _analyze_chunked_structure(self, payload: bytes, chunk_start: int, 
                                 packet_id: str) -> Optional[ChunkedAnalysis]:
        """
        分析Chunked数据结构 - 完整实现
        
        Args:
            payload: 载荷数据
            chunk_start: Chunk数据起始位置
            packet_id: 数据包ID
            
        Returns:
            Chunked分析结果，失败时返回None
        """
        chunks = []
        offset = chunk_start
        total_data_size = 0
        is_complete = False
        parse_errors = 0
        max_errors = 3  # 最多允许3个解析错误
        
        try:
            max_chunks = self.config.get('max_chunks_to_analyze', ScanConstants.MAX_CHUNKS_TO_ANALYZE)
            
            while offset < len(payload) and len(chunks) < max_chunks:
                # 查找chunk大小行结束位置
                size_line_end = payload.find(b'\r\n', offset)
                if size_line_end == -1:
                    # 未找到完整的size行
                    break
                
                try:
                    # 解析chunk大小（十六进制）
                    size_hex = payload[offset:size_line_end].decode('ascii').strip()
                    
                    # 处理chunk扩展（如果有的话）
                    if ';' in size_hex:
                        size_hex = size_hex.split(';')[0].strip()
                    
                    chunk_size = int(size_hex, 16)
                    
                    if chunk_size == 0:
                        # 结束chunk（0\r\n\r\n）
                        trailer_end = payload.find(b'\r\n', size_line_end + 2)
                        if trailer_end != -1:
                            is_complete = True
                        break
                    
                    # 计算chunk数据位置
                    chunk_data_start = size_line_end + 2  # skip \r\n
                    chunk_data_end = chunk_data_start + chunk_size
                    
                    # 检查chunk数据是否完整
                    if chunk_data_end + 2 > len(payload):  # +2 for trailing \r\n
                        # chunk数据不完整
                        break
                    
                    # 验证chunk结尾的\r\n
                    if payload[chunk_data_end:chunk_data_end + 2] != b'\r\n':
                        parse_errors += 1
                        if parse_errors > max_errors:
                            break
                        # 尝试查找下一个可能的chunk
                        offset = chunk_data_end + 1
                        continue
                    
                    # 创建chunk信息
                    chunk_info = ChunkInfo(
                        size_start=offset,
                        size_end=size_line_end,
                        data_start=chunk_data_start,
                        data_end=chunk_data_end,
                        size_value=chunk_size
                    )
                    
                    chunks.append(chunk_info)
                    total_data_size += chunk_size
                    offset = chunk_data_end + 2  # 移动到下一个chunk
                    
                except (ValueError, UnicodeDecodeError) as e:
                    # chunk格式解析错误
                    parse_errors += 1
                    if parse_errors > max_errors:
                        break
                    
                    if self.config.get('enable_scan_logging'):
                        self.logger.debug(f"包{packet_id}: Chunk解析错误在位置{offset}: {e}")
                    
                    # 尝试跳过这个错误，继续查找
                    offset += 1
                    continue
            
            if self.config.get('enable_scan_logging'):
                self.logger.debug(f"包{packet_id}: Chunked分析完成: "
                                 f"{len(chunks)}个chunk, 总数据{total_data_size}字节, "
                                 f"完整性: {is_complete}, 错误: {parse_errors}")
            
            return ChunkedAnalysis(
                chunks=chunks,
                total_data_size=total_data_size,
                is_complete=is_complete,
                last_offset=offset,
                parsing_errors=[]
            )
            
        except Exception as e:
            if self.config.get('enable_scan_logging'):
                self.logger.warning(f"包{packet_id}: Chunked结构分析异常: {e}")
            return None

    def _apply_complete_chunked_strategy_optimized(self, payload: bytes, scan_result: ScanResult,
                                                 chunked_analysis_result: ChunkedAnalysisResult, packet_id: str):
        """
        应用完整Chunked响应的优化保留策略
        
        Args:
            payload: 载荷数据
            scan_result: 扫描结果（会被修改）
            chunked_analysis_result: 优化的Chunked分析结果
            packet_id: 数据包ID
        """
        header_size = scan_result.header_boundary + 4  # +4 for \r\n\r\n
        
        # 优化策略：智能采样前N个chunk
        sample_size = self.config.get('chunked_sample_size', ScanConstants.CHUNKED_SAMPLE_SIZE)
        max_sample_chunks = min(3, len(chunked_analysis_result.chunks))
        
        sample_data_size = 0
        preserved_chunks = 0
        
        for i in range(max_sample_chunks):
            chunk = chunked_analysis_result.chunks[i]
            # 计算整个chunk的总大小（包括大小行、数据、结尾符）
            chunk_total_size = chunk.total_chunk_length
            
            if sample_data_size + chunk_total_size <= sample_size:
                sample_data_size += chunk_total_size
                preserved_chunks += 1
            else:
                # 部分保留最后一个chunk的数据部分
                remaining_space = sample_size - sample_data_size
                if remaining_space > (chunk.size_line_end - chunk.size_line_start + 2):  # 至少保留size行
                    partial_data_size = remaining_space - (chunk.size_line_end - chunk.size_line_start + 2)
                    sample_data_size += remaining_space
                    preserved_chunks += 0.5  # 标记为部分保留
                break
        
        preserve_bytes = header_size + sample_data_size
        
        scan_result.preserve_bytes = preserve_bytes
        scan_result.preserve_strategy = 'chunked_complete_optimized_sampling'
        scan_result.confidence = ScanConstants.HIGH_CONFIDENCE
        
        if self.config.get('enable_scan_logging'):
            self.logger.debug(f"包{packet_id}: 优化完整Chunked策略: "
                             f"保留{preserve_bytes}字节 "
                             f"(头部{header_size} + {preserved_chunks}个chunk样本{sample_data_size}字节)")
    
    def _apply_complete_chunked_strategy(self, payload: bytes, scan_result: ScanResult,
                                       chunked_analysis: ChunkedAnalysis, packet_id: str):
        """
        应用完整Chunked响应的保留策略 (Legacy方法保留)
        
        Args:
            payload: 载荷数据
            scan_result: 扫描结果（会被修改）
            chunked_analysis: Chunked分析结果
            packet_id: 数据包ID
        """
        header_size = scan_result.header_boundary + 4  # +4 for \r\n\r\n
        
        # 保留策略：头部 + 前几个chunk的样本数据
        sample_size = self.config.get('chunked_sample_size', ScanConstants.CHUNKED_SAMPLE_SIZE)
        max_sample_chunks = min(3, len(chunked_analysis.chunks))  # 最多前3个chunk
        
        sample_data_size = 0
        for i in range(max_sample_chunks):
            chunk = chunked_analysis.chunks[i]
            chunk_total_size = chunk.data_end - chunk.size_start + 2  # 包含size行和trailing \r\n
            
            if sample_data_size + chunk_total_size <= sample_size:
                sample_data_size += chunk_total_size
            else:
                # 部分保留最后一个chunk
                remaining_space = sample_size - sample_data_size
                if remaining_space > 0:
                    sample_data_size += remaining_space
                break
        
        preserve_bytes = header_size + sample_data_size
        
        scan_result.preserve_bytes = preserve_bytes
        scan_result.preserve_strategy = 'chunked_complete_sampling'
        scan_result.confidence = ScanConstants.HIGH_CONFIDENCE
        
        if self.config.get('enable_scan_logging'):
            self.logger.debug(f"包{packet_id}: 完整Chunked策略: "
                             f"保留{preserve_bytes}字节 "
                             f"(头部{header_size} + 样本{sample_data_size})")

    def _apply_incomplete_chunked_strategy_optimized(self, payload: bytes, scan_result: ScanResult,
                                                   chunked_analysis_result: ChunkedAnalysisResult, packet_id: str):
        """
        应用不完整Chunked响应的优化保留策略
        
        Args:
            payload: 载荷数据
            scan_result: 扫描结果（会被修改）
            chunked_analysis_result: 优化的Chunked分析结果
            packet_id: 数据包ID
        """
        header_size = scan_result.header_boundary + 4  # +4 for \r\n\r\n
        existing_data_size = len(payload) - header_size
        
        # 优化保守策略：基于已检测chunk的智能保留
        if len(chunked_analysis_result.chunks) > 0:
            # 已成功解析部分chunk，保留这些chunk + 额外保守数据
            parsed_chunk_size = sum(chunk.total_chunk_length for chunk in chunked_analysis_result.chunks)
            remaining_data_size = existing_data_size - parsed_chunk_size
            
            # 保留所有已解析chunk + 剩余数据的80%
            conservative_ratio = self.config.get('conservative_preserve_ratio', 
                                               ScanConstants.CONSERVATIVE_PRESERVE_RATIO)
            conservative_remaining = int(remaining_data_size * conservative_ratio)
            preserve_data_size = parsed_chunk_size + conservative_remaining
        else:
            # 未成功解析任何chunk，使用标准保守策略
            conservative_ratio = self.config.get('conservative_preserve_ratio', 
                                               ScanConstants.CONSERVATIVE_PRESERVE_RATIO)
            preserve_data_size = int(existing_data_size * conservative_ratio)
        
        preserve_bytes = header_size + preserve_data_size
        
        scan_result.preserve_bytes = preserve_bytes
        scan_result.preserve_strategy = 'chunked_incomplete_optimized_conservative'
        scan_result.confidence = ScanConstants.MEDIUM_CONFIDENCE  # 降低置信度
        scan_result.add_warning(f"不完整Chunked响应，成功解析{len(chunked_analysis_result.chunks)}个chunk，"
                               f"解析错误{chunked_analysis_result.parsing_errors}个")
        
        if self.config.get('enable_scan_logging'):
            self.logger.debug(f"包{packet_id}: 优化不完整Chunked策略: "
                             f"保留{preserve_bytes}字节 "
                             f"(头部{header_size} + 数据{preserve_data_size}字节), "
                             f"成功chunk={len(chunked_analysis_result.chunks)}")
    
    def _apply_incomplete_chunked_strategy(self, payload: bytes, scan_result: ScanResult,
                                         chunked_analysis: ChunkedAnalysis, packet_id: str):
        """
        应用不完整Chunked响应的保留策略 (Legacy方法保留)
        
        Args:
            payload: 载荷数据
            scan_result: 扫描结果（会被修改）
            chunked_analysis: Chunked分析结果
            packet_id: 数据包ID
        """
        header_size = scan_result.header_boundary + 4  # +4 for \r\n\r\n
        existing_data_size = len(payload) - header_size
        
        # 保守策略：保留头部 + 现有数据的80%
        conservative_ratio = self.config.get('conservative_preserve_ratio', 
                                           ScanConstants.CONSERVATIVE_PRESERVE_RATIO)
        preserve_data_size = int(existing_data_size * conservative_ratio)
        preserve_bytes = header_size + preserve_data_size
        
        scan_result.preserve_bytes = preserve_bytes
        scan_result.preserve_strategy = 'chunked_incomplete_conservative'
        scan_result.confidence = ScanConstants.MEDIUM_CONFIDENCE  # 降低置信度
        scan_result.add_warning(f"不完整Chunked响应，检测到{len(chunked_analysis.chunks)}个chunk")
        
        if self.config.get('enable_scan_logging'):
            self.logger.debug(f"包{packet_id}: 不完整Chunked策略: "
                             f"保留{preserve_bytes}字节 "
                             f"(头部{header_size} + {conservative_ratio*100}%数据{preserve_data_size})")

    def _find_header_boundary_at_position(self, payload: bytes, start_pos: int) -> int:
        """在指定位置查找HTTP头部边界 - 使用优化算法"""
        boundary_result = self._boundary_detector.detect_header_boundary(payload, start_pos)
        return boundary_result.position if boundary_result.found else -1
    
    def _extract_content_length_at_position(self, payload: bytes, start_pos: int,
                                           end_pos: int) -> Optional[int]:
        """在指定范围内提取Content-Length - 使用优化解析器"""
        header_data = payload[start_pos:end_pos + 4]
        content_result = self._content_parser.parse_content_length(header_data)
        return content_result.length if content_result.found else None

    def _generate_preserve_strategy(self, payload: bytes, scan_result: ScanResult,
                                   packet_id: str):
        """
        Step 3: 智能保留策略生成
        
        Args:
            payload: 载荷数据
            scan_result: 扫描结果（会被修改）
            packet_id: 数据包ID
        """
        if not scan_result.is_successful:
            return
        
        header_size = scan_result.header_boundary + 4  # +4 for \r\n\r\n
        body_size = len(payload) - header_size
        
        # 简化的保留策略
        if scan_result.is_chunked:
            # Chunked: 保留头部 + 1KB样本
            preserve_bytes = header_size + min(1024, body_size)
            scan_result.preserve_strategy = 'chunked_sampling'
        else:
            # 标准: 保留头部 + 64字节body
            preserve_bytes = header_size + min(64, body_size)
            scan_result.preserve_strategy = 'standard'
        
        scan_result.preserve_bytes = preserve_bytes
    
    def _validate_and_adjust_result(self, payload: bytes, scan_result: ScanResult,
                                   packet_id: str):
        """
        Step 4: 安全性验证和最终调整
        
        Args:
            payload: 载荷数据
            scan_result: 扫描结果（会被修改）
            packet_id: 数据包ID
        """
        if scan_result.preserve_bytes is not None:
            # 确保不超过载荷大小
            scan_result.preserve_bytes = min(scan_result.preserve_bytes, len(payload))
            
            # 确保最小保留
            min_preserve = max(64, scan_result.header_boundary + 4)
            scan_result.preserve_bytes = max(scan_result.preserve_bytes, min_preserve) 