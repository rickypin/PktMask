"""
TLS协议特定裁切策略

这个模块实现了TLS/SSL协议的专门裁切策略，能够精确识别TLS Record结构，
智能处理握手消息和应用数据，提供安全的载荷裁切方案。

支持TLS 1.0-1.3、SSL 3.0，能够识别握手、应用数据、警告等记录类型。

作者: PktMask Team
创建时间: 2025-01-15
版本: 1.0.0
"""

from typing import Dict, Any, List, Optional, Tuple, Union
import struct
import logging
from enum import IntEnum

from .base_strategy import BaseStrategy, ProtocolInfo, TrimContext, TrimResult
from ..models.mask_spec import MaskSpec, MaskAfter, MaskRange, KeepAll


class TLSContentType(IntEnum):
    """TLS内容类型常量"""
    CHANGE_CIPHER_SPEC = 20
    ALERT = 21
    HANDSHAKE = 22
    APPLICATION_DATA = 23
    HEARTBEAT = 24


class TLSHandshakeType(IntEnum):
    """TLS握手消息类型常量"""
    HELLO_REQUEST = 0
    CLIENT_HELLO = 1
    SERVER_HELLO = 2
    HELLO_VERIFY_REQUEST = 3
    NEW_SESSION_TICKET = 4
    END_OF_EARLY_DATA = 5
    HELLO_RETRY_REQUEST = 6
    ENCRYPTED_EXTENSIONS = 8
    CERTIFICATE = 11
    SERVER_KEY_EXCHANGE = 12
    CERTIFICATE_REQUEST = 13
    SERVER_HELLO_DONE = 14
    CERTIFICATE_VERIFY = 15
    CLIENT_KEY_EXCHANGE = 16
    FINISHED = 20
    CERTIFICATE_URL = 21
    CERTIFICATE_STATUS = 22
    SUPPLEMENTAL_DATA = 23
    KEY_UPDATE = 24
    NEXT_PROTOCOL = 67
    MESSAGE_HASH = 254


class TLSVersion:
    """TLS版本定义"""
    SSL_3_0 = (3, 0)
    TLS_1_0 = (3, 1)
    TLS_1_1 = (3, 2)
    TLS_1_2 = (3, 3)
    TLS_1_3 = (3, 4)
    
    @classmethod
    def to_string(cls, version: Tuple[int, int]) -> str:
        """将版本元组转换为字符串"""
        version_map = {
            cls.SSL_3_0: "SSL 3.0",
            cls.TLS_1_0: "TLS 1.0",
            cls.TLS_1_1: "TLS 1.1",
            cls.TLS_1_2: "TLS 1.2",
            cls.TLS_1_3: "TLS 1.3"
        }
        return version_map.get(version, f"Unknown ({version[0]}.{version[1]})")


class TLSTrimStrategy(BaseStrategy):
    """
    TLS协议特定裁切策略
    
    专门处理TLS/SSL协议的载荷裁切，能够精确识别TLS Record结构，
    智能处理握手消息和应用数据，确保TLS会话的完整性。
    """
    
    # TLS Record头部固定长度
    TLS_RECORD_HEADER_SIZE = 5
    
    # TLS握手消息头部长度
    TLS_HANDSHAKE_HEADER_SIZE = 4
    
    # 支持的TLS版本
    SUPPORTED_VERSIONS = [
        TLSVersion.SSL_3_0,
        TLSVersion.TLS_1_0,
        TLSVersion.TLS_1_1,
        TLSVersion.TLS_1_2,
        TLSVersion.TLS_1_3
    ]
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化TLS策略
        
        Args:
            config: 策略配置字典
        """
        super().__init__(config)
        
        # TLS策略默认配置
        self._default_config = {
            # 握手消息处理配置
            'preserve_handshake': True,           # 是否保留握手消息
            'preserve_client_hello': True,        # 是否保留ClientHello
            'preserve_server_hello': True,        # 是否保留ServerHello
            'preserve_certificate': True,         # 是否保留证书消息
            'preserve_finished': True,            # 是否保留Finished消息
            'preserve_key_exchange': False,       # 是否保留密钥交换消息
            
            # 应用数据处理配置
            'mask_application_data': True,        # 是否掩码应用数据
            'app_data_preserve_bytes': 32,        # 应用数据保留字节数
            'max_app_data_preserve_ratio': 0.05,  # 应用数据最大保留比例
            'min_app_data_preserve': 16,          # 应用数据最小保留字节数
            'max_app_data_preserve': 512,         # 应用数据最大保留字节数
            
            # 警告和控制消息
            'preserve_alerts': True,              # 是否保留警告消息
            'preserve_change_cipher_spec': True,  # 是否保留CCS消息
            'preserve_heartbeat': False,          # 是否保留心跳消息
            
            # TLS版本支持
            'min_tls_version': TLSVersion.TLS_1_0,  # 最小支持版本
            'max_tls_version': TLSVersion.TLS_1_3,  # 最大支持版本
            'strict_version_check': False,        # 严格版本检查
            
            # 安全和质量控制
            'preserve_record_boundaries': True,   # 保持Record边界完整
            'validate_record_integrity': True,    # 验证Record完整性
            'confidence_threshold': 0.85,         # 置信度阈值
            'enable_deep_inspection': True,       # 启用深度检查
            'max_record_size': 16384 + 2048,     # 最大Record大小 (16KB + 加密开销)
            
            # 性能优化
            'parse_extensions': True,             # 是否解析扩展
            'cache_handshake_type': True,         # 缓存握手类型分析
            'early_termination': True             # 启用早期终止优化
        }
        
        # 合并用户配置和默认配置
        for key, default_value in self._default_config.items():
            if key not in self.config:
                self.config[key] = default_value
                
    @property
    def supported_protocols(self) -> List[str]:
        """返回支持的协议列表"""
        return ['TLS', 'SSL', 'HTTPS']
        
    @property
    def strategy_name(self) -> str:
        """返回策略名称"""
        return 'tls'
        
    @property
    def priority(self) -> int:
        """返回策略优先级"""
        # TLS策略具有很高优先级，因为它是安全关键协议
        return 90
        
    def can_handle(self, protocol_info: ProtocolInfo, context: TrimContext) -> bool:
        """
        判断是否可以处理指定的协议和上下文
        
        Args:
            protocol_info: 协议信息
            context: 裁切上下文
            
        Returns:
            True 如果可以处理，False 否则
        """
        # 检查协议名称
        if protocol_info.name.upper() not in self.supported_protocols:
            return False
            
        # 检查是否是应用层协议
        if protocol_info.layer != 7:
            return False
            
        # 检查协议特征
        if hasattr(protocol_info, 'characteristics'):
            encrypted = protocol_info.characteristics.get('encrypted', False)
            if not encrypted:
                # TLS应该是加密的
                return False
                
        # 检查端口号（可选）
        if protocol_info.port:
            # 常见TLS/SSL端口
            tls_ports = {443, 8443, 9443, 993, 995, 465, 636, 989, 990, 992, 5223}
            if protocol_info.port in tls_ports:
                return True
            # 端口不匹配时，仍然可能是TLS，通过内容检测
            
        return True
        
    def analyze_payload(self, payload: bytes, protocol_info: ProtocolInfo, 
                       context: TrimContext) -> Dict[str, Any]:
        """
        分析TLS载荷结构
        
        Args:
            payload: 原始载荷数据
            protocol_info: 协议信息
            context: 裁切上下文
            
        Returns:
            TLS载荷分析结果字典
        """
        analysis = {
            'payload_size': len(payload),
            'is_tls': False,
            'tls_version': None,
            'tls_version_string': None,
            'records': [],
            'total_records': 0,
            'handshake_messages': [],
            'application_data_records': [],
            'alert_records': [],
            'has_complete_records': False,
            'confidence': 0.0,
            'warnings': [],
            'parsing_errors': []
        }
        
        if not payload or len(payload) < self.TLS_RECORD_HEADER_SIZE:
            if payload:
                analysis['warnings'].append(f"载荷太短，小于TLS Record头部最小长度({self.TLS_RECORD_HEADER_SIZE}字节)")
            return analysis
            
        try:
            # 解析TLS Records
            self._parse_tls_records(payload, analysis)
            
            # 验证TLS结构
            self._validate_tls_structure(analysis)
            
            # 计算置信度
            analysis['confidence'] = self._calculate_tls_confidence(analysis)
            
        except Exception as e:
            analysis['parsing_errors'].append(f"TLS解析异常: {str(e)}")
            self.logger.warning(f"TLS载荷解析失败: {e}", exc_info=True)
            
        return analysis
        
    def generate_mask_spec(self, payload: bytes, protocol_info: ProtocolInfo,
                          context: TrimContext, analysis: Dict[str, Any]) -> TrimResult:
        """
        生成TLS掩码规范
        
        Args:
            payload: 原始载荷数据
            protocol_info: 协议信息
            context: 裁切上下文
            analysis: 载荷分析结果
            
        Returns:
            裁切结果
        """
        try:
            # 验证分析结果
            if not analysis.get('is_tls', False):
                return TrimResult(
                    success=False,
                    mask_spec=None,
                    preserved_bytes=len(payload),
                    trimmed_bytes=0,
                    confidence=0.0,
                    reason="不是有效的TLS载荷",
                    warnings=analysis.get('warnings', []),
                    metadata={'analysis': analysis}
                )
                
            # 检查置信度阈值
            confidence = analysis.get('confidence', 0.0)
            threshold = self.get_config_value('confidence_threshold', 0.85)
            if confidence < threshold:
                return TrimResult(
                    success=False,
                    mask_spec=None,
                    preserved_bytes=len(payload),
                    trimmed_bytes=0,
                    confidence=confidence,
                    reason=f"TLS识别置信度不足 ({confidence:.2f} < {threshold})",
                    warnings=analysis.get('warnings', []),
                    metadata={'analysis': analysis}
                )
                
            # 生成TLS掩码规范
            mask_spec = self._create_tls_mask_spec(payload, analysis)
            
            # 计算保留和裁切字节数
            preserved_bytes = self._calculate_preserved_bytes(payload, mask_spec)
            trimmed_bytes = len(payload) - preserved_bytes
            
            # 生成裁切原因
            reason = self._generate_trim_reason(analysis)
            
            return TrimResult(
                success=True,
                mask_spec=mask_spec,
                preserved_bytes=preserved_bytes,
                trimmed_bytes=trimmed_bytes,
                confidence=confidence,
                reason=reason,
                warnings=analysis.get('warnings', []),
                metadata={
                    'analysis': analysis,
                    'tls_version': analysis.get('tls_version_string'),
                    'record_count': analysis.get('total_records', 0),
                    'handshake_count': len(analysis.get('handshake_messages', [])),
                    'app_data_count': len(analysis.get('application_data_records', []))
                }
            )
            
        except Exception as e:
            self.logger.error(f"TLS掩码规范生成失败: {e}", exc_info=True)
            return TrimResult(
                success=False,
                mask_spec=None,
                preserved_bytes=len(payload),
                trimmed_bytes=0,
                confidence=0.0,
                reason=f"掩码生成异常: {str(e)}",
                warnings=analysis.get('warnings', []),
                metadata={'analysis': analysis, 'error': str(e)}
            )
            
    def _parse_tls_records(self, payload: bytes, analysis: Dict[str, Any]) -> None:
        """
        解析TLS Records
        
        Args:
            payload: TLS载荷数据
            analysis: 分析结果字典（会被修改）
        """
        offset = 0
        records = []
        
        while offset + self.TLS_RECORD_HEADER_SIZE <= len(payload):
            try:
                # 解析Record头部
                record_header = payload[offset:offset + self.TLS_RECORD_HEADER_SIZE]
                content_type, major_version, minor_version, length = struct.unpack(
                    '>BBBH', record_header
                )
                
                # 验证内容类型
                if content_type not in [t.value for t in TLSContentType]:
                    # 可能不是TLS，或者是损坏的数据
                    analysis['warnings'].append(f"未知的TLS内容类型: {content_type}")
                    break
                    
                # 验证版本
                version = (major_version, minor_version)
                if version not in self.SUPPORTED_VERSIONS:
                    analysis['warnings'].append(f"不支持的TLS版本: {major_version}.{minor_version}")
                    # 继续解析，可能是新版本或者轻微的版本差异
                    
                # 验证长度
                if length > self.get_config_value('max_record_size', 18432):
                    analysis['warnings'].append(f"TLS Record长度异常: {length}")
                    break
                    
                # 检查是否有完整的Record数据
                record_end = offset + self.TLS_RECORD_HEADER_SIZE + length
                if record_end > len(payload):
                    analysis['warnings'].append("TLS Record不完整")
                    # 记录不完整的Record信息
                    record_info = {
                        'offset': offset,
                        'content_type': content_type,
                        'content_type_name': TLSContentType(content_type).name,
                        'version': version,
                        'version_string': TLSVersion.to_string(version),
                        'length': length,
                        'complete': False,
                        'available_data_length': len(payload) - offset - self.TLS_RECORD_HEADER_SIZE
                    }
                    records.append(record_info)
                    break
                    
                # 提取Record数据
                record_data = payload[offset + self.TLS_RECORD_HEADER_SIZE:record_end]
                
                # 创建Record信息
                record_info = {
                    'offset': offset,
                    'content_type': content_type,
                    'content_type_name': TLSContentType(content_type).name,
                    'version': version,
                    'version_string': TLSVersion.to_string(version),
                    'length': length,
                    'complete': True,
                    'data': record_data
                }
                
                # 特殊处理不同类型的Record
                if content_type == TLSContentType.HANDSHAKE:
                    self._parse_handshake_record(record_data, record_info, analysis)
                elif content_type == TLSContentType.APPLICATION_DATA:
                    analysis['application_data_records'].append(record_info)
                elif content_type == TLSContentType.ALERT:
                    analysis['alert_records'].append(record_info)
                    
                records.append(record_info)
                
                # 设置或验证TLS版本
                if analysis['tls_version'] is None:
                    analysis['tls_version'] = version
                    analysis['tls_version_string'] = TLSVersion.to_string(version)
                elif analysis['tls_version'] != version:
                    analysis['warnings'].append(
                        f"TLS版本不一致: {TLSVersion.to_string(analysis['tls_version'])} vs {TLSVersion.to_string(version)}"
                    )
                    
                # 移动到下一个Record
                offset = record_end
                
            except (struct.error, ValueError) as e:
                analysis['parsing_errors'].append(f"Record解析错误 at offset {offset}: {str(e)}")
                break
            except Exception as e:
                analysis['parsing_errors'].append(f"未知解析错误 at offset {offset}: {str(e)}")
                break
                
        analysis['records'] = records
        analysis['total_records'] = len(records)
        analysis['has_complete_records'] = any(r.get('complete', False) for r in records)
        
        # 如果成功解析了至少一个完整的Record，认为是TLS
        if analysis['has_complete_records'] and not analysis['parsing_errors']:
            analysis['is_tls'] = True
            
    def _parse_handshake_record(self, record_data: bytes, record_info: Dict[str, Any], 
                               analysis: Dict[str, Any]) -> None:
        """
        解析握手Record
        
        Args:
            record_data: 握手Record数据
            record_info: Record信息字典（会被修改）
            analysis: 分析结果字典（会被修改）
        """
        handshake_messages = []
        offset = 0
        
        while offset + self.TLS_HANDSHAKE_HEADER_SIZE <= len(record_data):
            try:
                # 解析握手消息头部
                handshake_header = record_data[offset:offset + self.TLS_HANDSHAKE_HEADER_SIZE]
                # TLS握手消息头部：1字节类型 + 3字节长度
                msg_type = handshake_header[0]
                msg_length = struct.unpack('>I', b'\x00' + handshake_header[1:4])[0]
                
                # 验证握手消息类型
                try:
                    handshake_type_name = TLSHandshakeType(msg_type).name
                except ValueError:
                    handshake_type_name = f"UNKNOWN_{msg_type}"
                    analysis['warnings'].append(f"未知的握手消息类型: {msg_type}")
                    
                # 检查消息长度
                msg_end = offset + self.TLS_HANDSHAKE_HEADER_SIZE + msg_length
                if msg_end > len(record_data):
                    analysis['warnings'].append(f"握手消息不完整: {handshake_type_name}")
                    break
                    
                # 提取握手消息数据
                msg_data = record_data[offset + self.TLS_HANDSHAKE_HEADER_SIZE:msg_end]
                
                handshake_msg = {
                    'type': msg_type,
                    'type_name': handshake_type_name,
                    'length': msg_length,
                    'offset_in_record': offset,
                    'data': msg_data
                }
                
                handshake_messages.append(handshake_msg)
                analysis['handshake_messages'].append(handshake_msg)
                
                # 移动到下一个握手消息
                offset = msg_end
                
            except (struct.error, ValueError) as e:
                analysis['parsing_errors'].append(f"握手消息解析错误: {str(e)}")
                break
                
        record_info['handshake_messages'] = handshake_messages
        
    def _validate_tls_structure(self, analysis: Dict[str, Any]) -> None:
        """
        验证TLS结构的合理性
        
        Args:
            analysis: 分析结果字典（会被修改）
        """
        if not analysis['records']:
            return
            
        # 检查版本一致性
        versions = set()
        for record in analysis['records']:
            if record.get('complete', False):
                versions.add(record['version'])
                
        if len(versions) > 1:
            analysis['warnings'].append(f"检测到多个TLS版本: {[TLSVersion.to_string(v) for v in versions]}")
            
        # 检查Record类型分布合理性
        content_types = {}
        for record in analysis['records']:
            if record.get('complete', False):
                ct_name = record['content_type_name']
                content_types[ct_name] = content_types.get(ct_name, 0) + 1
                
        # 如果只有应用数据，可能不是完整的TLS会话开始
        if content_types.get('APPLICATION_DATA', 0) > 0 and content_types.get('HANDSHAKE', 0) == 0:
            analysis['warnings'].append("只检测到应用数据，没有握手消息")
            
        # 验证握手消息的合理性
        handshake_types = set()
        for msg in analysis['handshake_messages']:
            handshake_types.add(msg['type'])
            
        # 检查常见握手消息组合
        if TLSHandshakeType.CLIENT_HELLO in handshake_types:
            analysis['has_client_hello'] = True
        if TLSHandshakeType.SERVER_HELLO in handshake_types:
            analysis['has_server_hello'] = True
            
    def _calculate_tls_confidence(self, analysis: Dict[str, Any]) -> float:
        """
        计算TLS识别置信度
        
        Args:
            analysis: 分析结果字典
            
        Returns:
            置信度分数 (0.0-1.0)
        """
        confidence = 0.0
        
        # 基础结构检查 (40分)
        if analysis.get('has_complete_records', False):
            confidence += 0.4
            
        # 版本有效性 (20分)
        tls_version = analysis.get('tls_version')
        if tls_version and tls_version in self.SUPPORTED_VERSIONS:
            confidence += 0.2
            
        # Record类型多样性 (20分)
        record_types = set()
        for record in analysis.get('records', []):
            if record.get('complete', False):
                record_types.add(record['content_type'])
                
        if TLSContentType.HANDSHAKE in record_types:
            confidence += 0.1
        if TLSContentType.APPLICATION_DATA in record_types:
            confidence += 0.05
        if len(record_types) >= 2:
            confidence += 0.05
            
        # 握手消息合理性 (15分)
        handshake_messages = analysis.get('handshake_messages', [])
        if handshake_messages:
            # 检查握手消息类型的合理性
            handshake_types = {msg['type'] for msg in handshake_messages}
            
            if TLSHandshakeType.CLIENT_HELLO in handshake_types:
                confidence += 0.05
            if TLSHandshakeType.SERVER_HELLO in handshake_types:
                confidence += 0.05
            if TLSHandshakeType.CERTIFICATE in handshake_types:
                confidence += 0.03
            if TLSHandshakeType.FINISHED in handshake_types:
                confidence += 0.02
                
        # 错误惩罚 (最多-30分)
        error_count = len(analysis.get('parsing_errors', []))
        warning_count = len(analysis.get('warnings', []))
        
        confidence -= min(0.3, error_count * 0.1 + warning_count * 0.02)
        
        # 数据完整性奖励 (5分)
        total_records = analysis.get('total_records', 0)
        complete_records = sum(1 for r in analysis.get('records', []) if r.get('complete', False))
        
        if total_records > 0:
            completeness_ratio = complete_records / total_records
            confidence += 0.05 * completeness_ratio
            
        return max(0.0, min(1.0, confidence))
        
    def _create_tls_mask_spec(self, payload: bytes, analysis: Dict[str, Any]) -> MaskSpec:
        """
        创建TLS掩码规范
        
        Args:
            payload: 原始载荷数据
            analysis: TLS分析结果
            
        Returns:
            掩码规范对象
        """
        preserve_ranges = []
        
        for record in analysis.get('records', []):
            if not record.get('complete', False):
                continue
                
            record_start = record['offset']
            record_header_end = record_start + self.TLS_RECORD_HEADER_SIZE
            record_end = record_start + self.TLS_RECORD_HEADER_SIZE + record['length']
            
            content_type = record['content_type']
            
            if content_type == TLSContentType.HANDSHAKE:
                # 握手消息处理
                if self.get_config_value('preserve_handshake', True):
                    preserve_ranges.append((record_start, record_end))
                else:
                    # 仅保留Record头部
                    preserve_ranges.append((record_start, record_header_end))
                    
            elif content_type == TLSContentType.APPLICATION_DATA:
                # 应用数据处理
                if self.get_config_value('mask_application_data', True):
                    # 保留Record头部
                    preserve_ranges.append((record_start, record_header_end))
                    
                    # 计算应用数据保留字节数
                    app_data_size = record['length']
                    preserve_bytes = self._calculate_app_data_preserve_bytes(app_data_size)
                    
                    if preserve_bytes > 0:
                        preserve_end = min(record_header_end + preserve_bytes, record_end)
                        preserve_ranges.append((record_header_end, preserve_end))
                else:
                    # 保留整个应用数据Record
                    preserve_ranges.append((record_start, record_end))
                    
            elif content_type == TLSContentType.ALERT:
                # 警告消息处理
                if self.get_config_value('preserve_alerts', True):
                    preserve_ranges.append((record_start, record_end))
                else:
                    preserve_ranges.append((record_start, record_header_end))
                    
            elif content_type == TLSContentType.CHANGE_CIPHER_SPEC:
                # CCS消息处理
                if self.get_config_value('preserve_change_cipher_spec', True):
                    preserve_ranges.append((record_start, record_end))
                else:
                    preserve_ranges.append((record_start, record_header_end))
                    
            elif content_type == TLSContentType.HEARTBEAT:
                # 心跳消息处理
                if self.get_config_value('preserve_heartbeat', False):
                    preserve_ranges.append((record_start, record_end))
                else:
                    preserve_ranges.append((record_start, record_header_end))
                    
            else:
                # 未知类型，保守处理 - 保留头部
                preserve_ranges.append((record_start, record_header_end))
                
        # 合并重叠的范围
        merged_ranges = self._merge_ranges(preserve_ranges)
        
        # 根据合并后的范围创建掩码规范
        if not merged_ranges:
            # 没有要保留的内容，全部掩码
            return MaskAfter(0)
            
        if len(merged_ranges) == 1 and merged_ranges[0] == (0, len(payload)):
            # 保留所有内容
            return KeepAll()
            
        if len(merged_ranges) == 1:
            start, end = merged_ranges[0]
            if start == 0:
                # 从开头保留到某个位置
                return MaskAfter(end)
            else:
                # 保留中间的一段
                return MaskRange(start, end)
        else:
            # 多个范围，使用第一个范围
            # 注意：当前MaskSpec设计不支持多个不连续范围
            # 这里选择最重要的范围（通常是第一个）
            start, end = merged_ranges[0]
            if start == 0:
                return MaskAfter(end)
            else:
                return MaskRange(start, end)
                
    def _calculate_app_data_preserve_bytes(self, app_data_size: int) -> int:
        """
        计算应用数据保留字节数
        
        Args:
            app_data_size: 应用数据大小
            
        Returns:
            应该保留的字节数
        """
        # 基础保留字节数
        base_preserve = self.get_config_value('app_data_preserve_bytes', 32)
        
        # 比例限制
        max_ratio = self.get_config_value('max_app_data_preserve_ratio', 0.05)
        ratio_limit = int(app_data_size * max_ratio)
        
        # 绝对限制
        min_preserve = self.get_config_value('min_app_data_preserve', 16)
        max_preserve = self.get_config_value('max_app_data_preserve', 512)
        
        # 计算最终保留字节数
        preserve_bytes = min(base_preserve, ratio_limit, max_preserve)
        preserve_bytes = max(preserve_bytes, min_preserve)
        preserve_bytes = min(preserve_bytes, app_data_size)
        
        return preserve_bytes
        
    def _merge_ranges(self, ranges: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        """
        合并重叠的范围
        
        Args:
            ranges: 范围列表，每个范围是(start, end)元组
            
        Returns:
            合并后的范围列表
        """
        if not ranges:
            return []
            
        # 按起始位置排序
        sorted_ranges = sorted(ranges)
        merged = [sorted_ranges[0]]
        
        for start, end in sorted_ranges[1:]:
            last_start, last_end = merged[-1]
            
            if start <= last_end:
                # 有重叠，合并
                merged[-1] = (last_start, max(last_end, end))
            else:
                # 没有重叠，添加新范围
                merged.append((start, end))
                
        return merged
        
    def _calculate_preserved_bytes(self, payload: bytes, mask_spec: MaskSpec) -> int:
        """
        计算保留的字节数
        
        Args:
            payload: 原始载荷数据
            mask_spec: 掩码规范
            
        Returns:
            保留的字节数
        """
        payload_size = len(payload)
        
        if isinstance(mask_spec, KeepAll):
            return payload_size
        elif isinstance(mask_spec, MaskAfter):
            return min(mask_spec.keep_bytes, payload_size)
        elif isinstance(mask_spec, MaskRange):
            start = min(mask_spec.start_byte, payload_size)
            end = min(mask_spec.end_byte, payload_size)
            return max(0, end - start)
        else:
            return 0
            
    def _generate_trim_reason(self, analysis: Dict[str, Any]) -> str:
        """
        生成裁切原因说明
        
        Args:
            analysis: TLS分析结果
            
        Returns:
            裁切原因字符串
        """
        version_str = analysis.get('tls_version_string', '未知版本')
        record_count = analysis.get('total_records', 0)
        handshake_count = len(analysis.get('handshake_messages', []))
        app_data_count = len(analysis.get('application_data_records', []))
        
        components = [f"TLS {version_str}"]
        
        if record_count > 0:
            components.append(f"{record_count}个记录")
            
        if handshake_count > 0:
            components.append(f"{handshake_count}个握手消息")
            
        if app_data_count > 0:
            components.append(f"{app_data_count}个应用数据记录")
            
        reason = "TLS协议智能裁切: " + ", ".join(components)
        
        # 添加配置说明
        config_notes = []
        if self.get_config_value('preserve_handshake', True):
            config_notes.append("保留握手消息")
        if self.get_config_value('mask_application_data', True):
            config_notes.append("掩码应用数据")
        if self.get_config_value('preserve_alerts', True):
            config_notes.append("保留警告消息")
            
        if config_notes:
            reason += f" (配置: {', '.join(config_notes)})"
            
        return reason
        
    def _validate_config(self) -> None:
        """验证配置参数的有效性"""
        super()._validate_config()
        
        # 验证字节数配置
        byte_configs = [
            'app_data_preserve_bytes',
            'min_app_data_preserve', 
            'max_app_data_preserve'
        ]
        
        for config_key in byte_configs:
            value = self.get_config_value(config_key, 0)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"配置 {config_key} 必须是非负整数")
                
        # 验证比例配置
        ratio_configs = [
            'max_app_data_preserve_ratio',
            'confidence_threshold'
        ]
        
        for config_key in ratio_configs:
            value = self.get_config_value(config_key, 0.0)
            if not isinstance(value, (int, float)) or not 0.0 <= value <= 1.0:
                raise ValueError(f"配置 {config_key} 必须是0-1之间的数值")
                
        # 验证版本配置
        min_version = self.get_config_value('min_tls_version', TLSVersion.TLS_1_0)
        max_version = self.get_config_value('max_tls_version', TLSVersion.TLS_1_3)
        
        if min_version not in self.SUPPORTED_VERSIONS:
            raise ValueError(f"不支持的最小TLS版本: {min_version}")
        if max_version not in self.SUPPORTED_VERSIONS:
            raise ValueError(f"不支持的最大TLS版本: {max_version}")
        if min_version > max_version:
            raise ValueError("最小TLS版本不能大于最大TLS版本")