"""
TCP流方向性标识机制单元测试

验证Phase 1重构中TCP流ID生成、方向检测和序列号管理功能的正确性。
"""

import pytest
import logging
from unittest.mock import patch

from src.pktmask.core.trim.models.tcp_stream import (
    ConnectionDirection,
    TCPConnection, 
    DirectionalTCPStream,
    TCPStreamManager,
    detect_packet_direction
)
from src.pktmask.core.trim.exceptions import StreamMaskTableError


class TestConnectionDirection:
    """测试连接方向枚举"""
    
    def test_direction_values(self):
        """测试方向枚举值"""
        assert ConnectionDirection.FORWARD.value == "forward"
        assert ConnectionDirection.REVERSE.value == "reverse"


class TestTCPConnection:
    """测试TCP连接标识"""
    
    def test_create_valid_connection(self):
        """测试创建有效的TCP连接"""
        conn = TCPConnection("192.168.1.100", 12345, "10.0.0.1", 443)
        
        assert conn.src_ip == "192.168.1.100"
        assert conn.src_port == 12345
        assert conn.dst_ip == "10.0.0.1"
        assert conn.dst_port == 443
    
    def test_invalid_ip_address(self):
        """测试无效IP地址抛出异常"""
        with pytest.raises(StreamMaskTableError) as exc_info:
            TCPConnection("invalid_ip", 12345, "10.0.0.1", 443)
        
        assert "无效的IP地址" in str(exc_info.value)
    
    def test_invalid_port_range(self):
        """测试无效端口范围抛出异常"""
        with pytest.raises(StreamMaskTableError) as exc_info:
            TCPConnection("192.168.1.100", 0, "10.0.0.1", 443)
        
        assert "端口号必须在1-65535范围内" in str(exc_info.value)
        
        with pytest.raises(StreamMaskTableError):
            TCPConnection("192.168.1.100", 12345, "10.0.0.1", 65536)
    
    def test_get_reverse(self):
        """测试获取反向连接"""
        conn = TCPConnection("192.168.1.100", 12345, "10.0.0.1", 443)
        reverse = conn.get_reverse()
        
        assert reverse.src_ip == "10.0.0.1"
        assert reverse.src_port == 443
        assert reverse.dst_ip == "192.168.1.100"
        assert reverse.dst_port == 12345
    
    def test_to_stream_base(self):
        """测试转换为基础流标识符"""
        conn = TCPConnection("192.168.1.100", 12345, "10.0.0.1", 443)
        base_id = conn.to_stream_base()
        
        expected = "TCP_192.168.1.100:12345_10.0.0.1:443"
        assert base_id == expected
    
    def test_ipv6_support(self):
        """测试IPv6地址支持"""
        conn = TCPConnection("2001:db8::1", 12345, "2001:db8::2", 443)
        
        assert conn.src_ip == "2001:db8::1"
        assert conn.dst_ip == "2001:db8::2"


class TestDirectionalTCPStream:
    """测试方向性TCP流"""
    
    def test_create_stream(self):
        """测试创建方向性TCP流"""
        conn = TCPConnection("192.168.1.100", 12345, "10.0.0.1", 443)
        stream = DirectionalTCPStream(conn, ConnectionDirection.FORWARD)
        
        assert stream.connection == conn
        assert stream.direction == ConnectionDirection.FORWARD
        assert stream.initial_seq is None
    
    def test_stream_id_generation(self):
        """测试流ID生成"""
        conn = TCPConnection("192.168.1.100", 12345, "10.0.0.1", 443)
        
        forward_stream = DirectionalTCPStream(conn, ConnectionDirection.FORWARD)
        reverse_stream = DirectionalTCPStream(conn, ConnectionDirection.REVERSE)
        
        expected_forward = "TCP_192.168.1.100:12345_10.0.0.1:443_forward"
        expected_reverse = "TCP_192.168.1.100:12345_10.0.0.1:443_reverse"
        
        assert forward_stream.stream_id == expected_forward
        assert reverse_stream.stream_id == expected_reverse
    
    def test_initial_seq_management(self):
        """测试初始序列号管理"""
        conn = TCPConnection("192.168.1.100", 12345, "10.0.0.1", 443)
        stream = DirectionalTCPStream(conn, ConnectionDirection.FORWARD)
        
        # 设置初始序列号
        stream.set_initial_seq(1000)
        assert stream.initial_seq == 1000
        
        # 重复设置相同值应该正常
        stream.set_initial_seq(1000)
        assert stream.initial_seq == 1000
        
        # 设置不同值应该产生警告日志（但仍会更新）
        with patch.object(stream._logger, 'warning') as mock_warning:
            stream.set_initial_seq(2000)
            mock_warning.assert_called_once()
            assert stream.initial_seq == 2000
    
    def test_sequence_number_conversion(self):
        """测试序列号转换"""
        conn = TCPConnection("192.168.1.100", 12345, "10.0.0.1", 443)
        stream = DirectionalTCPStream(conn, ConnectionDirection.FORWARD)
        
        # 未设置初始序列号时应该抛出异常
        with pytest.raises(StreamMaskTableError) as exc_info:
            stream.get_relative_seq(1500)
        assert "尚未设置初始序列号" in str(exc_info.value)
        
        with pytest.raises(StreamMaskTableError):
            stream.get_absolute_seq(500)
        
        # 设置初始序列号后进行转换
        stream.set_initial_seq(1000)
        
        # 测试相对序列号转换
        assert stream.get_relative_seq(1000) == 0
        assert stream.get_relative_seq(1500) == 500
        assert stream.get_relative_seq(2000) == 1000
        
        # 测试绝对序列号转换
        assert stream.get_absolute_seq(0) == 1000
        assert stream.get_absolute_seq(500) == 1500
        assert stream.get_absolute_seq(1000) == 2000


class TestTCPStreamManager:
    """测试TCP流管理器"""
    
    def test_create_manager(self):
        """测试创建流管理器"""
        manager = TCPStreamManager()
        assert manager.get_stream_count() == 0
        assert manager.get_all_stream_ids() == []
    
    def test_get_or_create_stream(self):
        """测试获取或创建流"""
        manager = TCPStreamManager()
        
        # 创建新流
        stream1 = manager.get_or_create_stream(
            "192.168.1.100", 12345, "10.0.0.1", 443, ConnectionDirection.FORWARD
        )
        
        assert stream1 is not None
        assert manager.get_stream_count() == 1
        
        # 获取相同流应该返回同一对象
        stream2 = manager.get_or_create_stream(
            "192.168.1.100", 12345, "10.0.0.1", 443, ConnectionDirection.FORWARD
        )
        
        assert stream1 is stream2
        assert manager.get_stream_count() == 1
        
        # 创建反向流应该是不同对象
        reverse_stream = manager.get_or_create_stream(
            "192.168.1.100", 12345, "10.0.0.1", 443, ConnectionDirection.REVERSE
        )
        
        assert reverse_stream is not stream1
        assert manager.get_stream_count() == 2
    
    def test_generate_stream_id(self):
        """测试生成流ID"""
        manager = TCPStreamManager()
        
        forward_id = manager.generate_stream_id(
            "192.168.1.100", 12345, "10.0.0.1", 443, ConnectionDirection.FORWARD
        )
        reverse_id = manager.generate_stream_id(
            "192.168.1.100", 12345, "10.0.0.1", 443, ConnectionDirection.REVERSE
        )
        
        expected_forward = "TCP_192.168.1.100:12345_10.0.0.1:443_forward"
        expected_reverse = "TCP_192.168.1.100:12345_10.0.0.1:443_reverse"
        
        assert forward_id == expected_forward
        assert reverse_id == expected_reverse


class TestDetectPacketDirection:
    """测试数据包方向检测"""
    
    def test_forward_direction(self):
        """测试正向方向检测"""
        direction = detect_packet_direction(
            packet_src_ip="192.168.1.100", packet_src_port=12345,
            packet_dst_ip="10.0.0.1", packet_dst_port=443,
            connection_src_ip="192.168.1.100", connection_src_port=12345,
            connection_dst_ip="10.0.0.1", connection_dst_port=443
        )
        
        assert direction == ConnectionDirection.FORWARD
    
    def test_reverse_direction(self):
        """测试反向方向检测"""
        direction = detect_packet_direction(
            packet_src_ip="10.0.0.1", packet_src_port=443,
            packet_dst_ip="192.168.1.100", packet_dst_port=12345,
            connection_src_ip="192.168.1.100", connection_src_port=12345,
            connection_dst_ip="10.0.0.1", connection_dst_port=443
        )
        
        assert direction == ConnectionDirection.REVERSE


if __name__ == "__main__":
    # 配置日志以便调试
    logging.basicConfig(level=logging.DEBUG)
    
    # 运行测试
    pytest.main([__file__, "-v"]) 