"""
TLS策略单元测试

测试TLS协议裁切策略的各项功能

作者: PktMask Team
创建时间: 2025-01-15
版本: 1.0.0
"""

import pytest
import struct

from src.pktmask.core.trim.strategies.tls_strategy import (
    TLSTrimStrategy,
    TLSContentType,
    TLSHandshakeType,
    TLSVersion
)
from src.pktmask.core.trim.strategies.base_strategy import (
    ProtocolInfo,
    TrimContext
)
from src.pktmask.core.trim.models.mask_spec import (
    MaskAfter,
    KeepAll
)


class TestTLSTrimStrategy:
    """TLS策略测试类"""
    
    def setup_method(self):
        """设置测试环境"""
        self.config = {
            'preserve_handshake': True,
            'mask_application_data': True,
            'app_data_preserve_bytes': 32,
            'confidence_threshold': 0.85
        }
        self.strategy = TLSTrimStrategy(self.config)
        
        # 创建测试用的协议信息和上下文
        self.tls_protocol_info = ProtocolInfo(
            name='TLS',
            version='1.2',
            layer=7,
            port=443,
            characteristics={'encrypted': True}
        )
        
        self.trim_context = TrimContext(
            packet_index=0,
            stream_id='test_stream',
            flow_direction='client_to_server',
            protocol_stack=['ETH', 'IP', 'TCP', 'TLS'],
            payload_size=0,
            timestamp=1234567890.0,
            metadata={}
        )
        
    def test_strategy_properties(self):
        """测试策略基本属性"""
        assert self.strategy.strategy_name == 'tls'
        assert self.strategy.priority == 90
        assert 'TLS' in self.strategy.supported_protocols
        assert 'SSL' in self.strategy.supported_protocols
        assert 'HTTPS' in self.strategy.supported_protocols
        
    def test_can_handle_valid_tls(self):
        """测试TLS协议识别"""
        assert self.strategy.can_handle(self.tls_protocol_info, self.trim_context)
        
    def test_empty_payload_analysis(self):
        """测试空载荷分析"""
        payload = b''
        analysis = self.strategy.analyze_payload(payload, self.tls_protocol_info, self.trim_context)
        
        assert analysis['payload_size'] == 0
        assert not analysis['is_tls']
        assert analysis['confidence'] == 0.0
        assert analysis['total_records'] == 0
        
    def test_client_hello_analysis(self):
        """测试ClientHello消息分析"""
        # 构造一个简单的TLS ClientHello Record
        content_type = TLSContentType.HANDSHAKE
        version_major, version_minor = TLSVersion.TLS_1_2
        
        # 握手消息内容（简化的ClientHello）
        handshake_type = TLSHandshakeType.CLIENT_HELLO
        handshake_data = b'\x00' * 32  # 简化的ClientHello数据
        handshake_length = len(handshake_data)
        # TLS握手消息头部：1字节类型 + 3字节长度
        handshake_msg = struct.pack('>B', handshake_type) + struct.pack('>I', handshake_length)[1:] + handshake_data
        
        # TLS Record
        record_length = len(handshake_msg)
        record_header = struct.pack('>BBBH', content_type, version_major, version_minor, record_length)
        payload = record_header + handshake_msg
        
        analysis = self.strategy.analyze_payload(payload, self.tls_protocol_info, self.trim_context)
        
        assert analysis['is_tls']
        assert analysis['tls_version'] == TLSVersion.TLS_1_2
        assert analysis['tls_version_string'] == 'TLS 1.2'
        assert analysis['total_records'] == 1
        assert analysis['has_complete_records']
        assert len(analysis['handshake_messages']) == 1
        assert analysis['handshake_messages'][0]['type'] == TLSHandshakeType.CLIENT_HELLO
        assert analysis['handshake_messages'][0]['type_name'] == 'CLIENT_HELLO'
        assert analysis['confidence'] > 0.5
        
    def test_tls_version_string_conversion(self):
        """测试TLS版本字符串转换"""
        assert TLSVersion.to_string(TLSVersion.TLS_1_0) == "TLS 1.0"
        assert TLSVersion.to_string(TLSVersion.TLS_1_2) == "TLS 1.2"
        assert TLSVersion.to_string(TLSVersion.TLS_1_3) == "TLS 1.3"
        assert TLSVersion.to_string((99, 99)) == "Unknown (99.99)"


if __name__ == '__main__':
    pytest.main([__file__]) 