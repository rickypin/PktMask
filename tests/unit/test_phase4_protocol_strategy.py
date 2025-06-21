"""
Phase 4 协议策略框架单元测试

测试协议掩码策略系统的各个组件：
1. ProtocolMaskStrategy抽象基类
2. HTTPMaskStrategy HTTP协议策略
3. ProtocolMaskFactory策略工厂
4. 混合协议场景处理

作者: PktMask Team
创建时间: 2025年6月21日
版本: Phase 4.0.0
"""

import unittest
from unittest.mock import Mock, patch
import logging
from typing import List, Dict, Any, Set

# Phase 4: 导入核心组件
from src.pktmask.core.trim.strategies.protocol_mask_strategy import (
    ProtocolMaskStrategy, PacketAnalysis, ProtocolDetectionResult,
    MaskGenerationContext, GenericProtocolMaskStrategy
)
from src.pktmask.core.trim.strategies.http_mask_strategy import HTTPMaskStrategy
from src.pktmask.core.trim.strategies.protocol_mask_factory import (
    ProtocolMaskFactory, ProtocolMaskRegistry, get_protocol_mask_factory
)
from src.pktmask.core.trim.models.sequence_mask_table import MaskEntry
from src.pktmask.core.trim.models.mask_spec import MaskAfter, KeepAll
from src.pktmask.core.trim.models.tcp_stream import ConnectionDirection


class TestProtocolMaskStrategy(unittest.TestCase):
    """测试ProtocolMaskStrategy抽象基类"""
    
    def setUp(self):
        """设置测试环境"""
        # 禁用日志输出以保持测试输出简洁
        logging.disable(logging.CRITICAL)
        
        # 创建测试策略类
        class TestStrategy(ProtocolMaskStrategy):
            @property
            def strategy_name(self) -> str:
                return "test_strategy"
            
            @property
            def supported_protocols(self) -> Set[str]:
                return {"TEST_PROTOCOL"}
            
            @property
            def priority(self) -> int:
                return 50
            
            def detect_protocol(self, packet: PacketAnalysis) -> ProtocolDetectionResult:
                # 简单的测试检测逻辑
                if packet.application_layer == "TEST_PROTOCOL":
                    return ProtocolDetectionResult(
                        is_protocol_match=True,
                        protocol_name="TEST_PROTOCOL",
                        confidence=0.9,
                        protocol_version="1.0",
                        attributes={"test": True}
                    )
                return ProtocolDetectionResult(
                    is_protocol_match=False,
                    protocol_name="TEST_PROTOCOL",
                    confidence=0.0,
                    protocol_version=None,
                    attributes={}
                )
            
            def generate_mask_entries(self, context: MaskGenerationContext) -> List[MaskEntry]:
                entries = []
                for packet in context.packets:
                    if packet.payload_length > 0:
                        entry = self._create_mask_entry(
                            stream_id=packet.stream_id,
                            seq_start=packet.seq_number,
                            seq_end=packet.seq_number + packet.payload_length - 1,
                            mask_type="test_mask",
                            mask_spec=MaskAfter(10)
                        )
                        entries.append(entry)
                return entries
        
        self.test_strategy_class = TestStrategy
        self.test_strategy = TestStrategy({})
    
    def tearDown(self):
        """清理测试环境"""
        logging.disable(logging.NOTSET)
    
    def test_strategy_properties(self):
        """测试策略属性"""
        self.assertEqual(self.test_strategy.strategy_name, "test_strategy")
        self.assertEqual(self.test_strategy.supported_protocols, {"TEST_PROTOCOL"})
        self.assertEqual(self.test_strategy.priority, 50)
        self.assertFalse(self.test_strategy.can_handle_mixed_protocols())
    
    def test_detect_protocol(self):
        """测试协议检测"""
        # 创建测试数据包
        packet = PacketAnalysis(
            packet_number=1,
            timestamp=1234567890.0,
            stream_id="TCP_test_stream_forward",
            seq_number=1000,
            payload_length=100,
            application_layer="TEST_PROTOCOL"
        )
        
        result = self.test_strategy.detect_protocol(packet)
        self.assertTrue(result.is_protocol_match)
        self.assertEqual(result.protocol_name, "TEST_PROTOCOL")
        self.assertEqual(result.confidence, 0.9)
        self.assertEqual(result.protocol_version, "1.0")
        self.assertTrue(result.attributes.get("test"))
    
    def test_generate_mask_entries(self):
        """测试掩码条目生成"""
        packets = [
            PacketAnalysis(
                packet_number=1,
                timestamp=1234567890.0,
                stream_id="TCP_test_stream_forward",
                seq_number=1000,
                payload_length=100,
                application_layer="TEST_PROTOCOL"
            ),
            PacketAnalysis(
                packet_number=2,
                timestamp=1234567891.0,
                stream_id="TCP_test_stream_forward", 
                seq_number=1100,
                payload_length=150,
                application_layer="TEST_PROTOCOL"
            )
        ]
        
        context = MaskGenerationContext(
            stream_id="TCP_test_stream_forward",
            direction=ConnectionDirection.FORWARD,
            packets=packets,
            flow_metadata={}
        )
        
        entries = self.test_strategy.generate_mask_entries(context)
        
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0].tcp_stream_id, "TCP_test_stream_forward")
        self.assertEqual(entries[0].seq_start, 1000)
        self.assertEqual(entries[0].seq_end, 1099)
        self.assertEqual(entries[0].mask_type, "test_mask")
        self.assertIsInstance(entries[0].mask_spec, MaskAfter)
    
    def test_analyze_stream(self):
        """测试流分析"""
        packets = [
            PacketAnalysis(
                packet_number=1,
                timestamp=1234567890.0,
                stream_id="TCP_test_stream_forward",
                seq_number=1000,
                payload_length=100,
                application_layer="TEST_PROTOCOL"
            )
        ]
        
        analysis = self.test_strategy.analyze_stream(packets)
        self.assertEqual(analysis['packet_count'], 1)
        self.assertEqual(analysis['total_bytes'], 100)
        self.assertEqual(len(analysis['protocol_packets']), 1)
    
    def test_config_handling(self):
        """测试配置处理"""
        config = {'test_param': 'value'}
        strategy = self.test_strategy_class(config)
        
        self.assertEqual(strategy.get_config_value('test_param'), 'value')
        self.assertEqual(strategy.get_config_value('nonexistent', 'default'), 'default')


class TestGenericProtocolMaskStrategy(unittest.TestCase):
    """测试通用协议掩码策略"""
    
    def setUp(self):
        """设置测试环境"""
        logging.disable(logging.CRITICAL)
        self.strategy = GenericProtocolMaskStrategy({})
    
    def tearDown(self):
        """清理测试环境"""
        logging.disable(logging.NOTSET)
    
    def test_strategy_properties(self):
        """测试通用策略属性"""
        self.assertEqual(self.strategy.strategy_name, "generic")
        self.assertEqual(self.strategy.supported_protocols, {"*"})
        self.assertEqual(self.strategy.priority, 0)  # 最低优先级
        self.assertTrue(self.strategy.can_handle_mixed_protocols())
    
    def test_detect_protocol(self):
        """测试通用协议检测"""
        packet = PacketAnalysis(
            packet_number=1,
            timestamp=1234567890.0,
            stream_id="TCP_test_stream_forward",
            seq_number=1000,
            payload_length=100,
            application_layer="UNKNOWN"
        )
        
        result = self.strategy.detect_protocol(packet)
        self.assertTrue(result.is_protocol_match)
        self.assertEqual(result.protocol_name, "generic")
        self.assertEqual(result.confidence, 0.5)
    
    def test_generate_mask_entries(self):
        """测试通用掩码条目生成"""
        packets = [
            PacketAnalysis(
                packet_number=1,
                timestamp=1234567890.0,
                stream_id="TCP_test_stream_forward",
                seq_number=1000,
                payload_length=100,
                application_layer="UNKNOWN"
            )
        ]
        
        context = MaskGenerationContext(
            stream_id="TCP_test_stream_forward",
            direction=ConnectionDirection.FORWARD,
            packets=packets,
            flow_metadata={}
        )
        
        entries = self.strategy.generate_mask_entries(context)
        
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].mask_type, "generic_keepall")
        self.assertIsInstance(entries[0].mask_spec, KeepAll)


class TestHTTPMaskStrategy(unittest.TestCase):
    """测试HTTP协议掩码策略"""
    
    def setUp(self):
        """设置测试环境"""
        logging.disable(logging.CRITICAL)
        self.strategy = HTTPMaskStrategy({
            'preserve_headers': True,
            'preserve_body_bytes': 50,
            'min_confidence': 0.8
        })
    
    def tearDown(self):
        """清理测试环境"""
        logging.disable(logging.NOTSET)
    
    def test_strategy_properties(self):
        """测试HTTP策略属性"""
        self.assertEqual(self.strategy.strategy_name, "http_mask_strategy")
        self.assertEqual(self.strategy.supported_protocols, {"HTTP", "HTTPS"})
        self.assertEqual(self.strategy.priority, 80)
        self.assertTrue(self.strategy.can_handle_mixed_protocols())
    
    def test_detect_http_request(self):
        """测试HTTP请求检测"""
        http_request = b"GET /path HTTP/1.1\r\nHost: example.com\r\n\r\n"
        
        packet = PacketAnalysis(
            packet_number=1,
            timestamp=1234567890.0,
            stream_id="TCP_test_stream_forward",
            seq_number=1000,
            payload_length=len(http_request),
            application_layer="HTTP",
            protocol_attributes={'payload': http_request}
        )
        
        result = self.strategy.detect_protocol(packet)
        self.assertTrue(result.is_protocol_match)
        self.assertEqual(result.protocol_name, "HTTP")
        self.assertEqual(result.confidence, 0.95)
        self.assertEqual(result.attributes['message_type'], 'request')
        self.assertEqual(result.attributes['method'], 'GET')
    
    def test_detect_http_response(self):
        """测试HTTP响应检测"""
        http_response = b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n<html>content</html>"
        
        packet = PacketAnalysis(
            packet_number=1,
            timestamp=1234567890.0,
            stream_id="TCP_test_stream_forward",
            seq_number=1000,
            payload_length=len(http_response),
            application_layer="HTTP",
            protocol_attributes={'payload': http_response}
        )
        
        result = self.strategy.detect_protocol(packet)
        self.assertTrue(result.is_protocol_match)
        self.assertEqual(result.protocol_name, "HTTP")
        self.assertEqual(result.confidence, 0.95)
        self.assertEqual(result.attributes['message_type'], 'response')
        self.assertEqual(result.attributes['status_code'], 200)
    
    def test_generate_http_mask_entries(self):
        """测试HTTP掩码条目生成"""
        http_request = b"GET /path HTTP/1.1\r\nHost: example.com\r\nContent-Length: 10\r\n\r\n0123456789"
        
        packet = PacketAnalysis(
            packet_number=1,
            timestamp=1234567890.0,
            stream_id="TCP_test_stream_forward",
            seq_number=1000,
            payload_length=len(http_request),
            application_layer="HTTP",
            protocol_attributes={'payload': http_request}
        )
        
        context = MaskGenerationContext(
            stream_id="TCP_test_stream_forward",
            direction=ConnectionDirection.FORWARD,
            packets=[packet],
            flow_metadata={}
        )
        
        entries = self.strategy.generate_mask_entries(context)
        
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry.tcp_stream_id, "TCP_test_stream_forward")
        self.assertEqual(entry.seq_start, 1000)
        self.assertEqual(entry.seq_end, 1000 + len(http_request) - 1)
        self.assertIn("http_request", entry.mask_type)
        self.assertIsInstance(entry.mask_spec, MaskAfter)
    
    def test_http_message_parsing(self):
        """测试HTTP消息解析"""
        http_request = b"GET /path HTTP/1.1\r\nHost: example.com\r\nContent-Length: 5\r\n\r\nhello"
        
        attributes = {
            'message_type': 'request',
            'method': 'GET',
            'uri': '/path',
            'version': '1.1'
        }
        
        message = self.strategy._parse_http_message(http_request, attributes)
        
        self.assertIsNotNone(message)
        self.assertEqual(message.message_type, 'request')
        self.assertEqual(message.method, 'GET')
        self.assertEqual(message.uri, '/path')
        self.assertEqual(message.version, '1.1')
        self.assertEqual(message.body_length, 5)
        self.assertIn('host', message.headers)
        self.assertEqual(message.headers['host'], 'example.com')


class TestProtocolMaskRegistry(unittest.TestCase):
    """测试协议掩码策略注册表"""
    
    def setUp(self):
        """设置测试环境"""
        logging.disable(logging.CRITICAL)
        self.registry = ProtocolMaskRegistry()
    
    def tearDown(self):
        """清理测试环境"""
        logging.disable(logging.NOTSET)
    
    def test_register_strategy(self):
        """测试策略注册"""
        self.registry.register(GenericProtocolMaskStrategy)
        
        strategies = self.registry.list_all_strategies()
        self.assertIn("generic", strategies)
        
        protocols = self.registry.list_all_protocols()
        self.assertIn("*", protocols)
    
    def test_get_strategies_for_protocol(self):
        """测试获取协议策略"""
        self.registry.register(GenericProtocolMaskStrategy)
        
        strategies = self.registry.get_strategies_for_protocol("HTTP")
        self.assertIn("generic", strategies)
        
        strategies = self.registry.get_strategies_for_protocol("*")
        self.assertIn("generic", strategies)
    
    def test_strategy_priority_sorting(self):
        """测试策略优先级排序"""
        # 创建两个测试策略，优先级不同
        class HighPriorityStrategy(GenericProtocolMaskStrategy):
            @property
            def strategy_name(self) -> str:
                return "high_priority"
            
            @property
            def priority(self) -> int:
                return 90
        
        class LowPriorityStrategy(GenericProtocolMaskStrategy):
            @property
            def strategy_name(self) -> str:
                return "low_priority"
            
            @property
            def priority(self) -> int:
                return 10
        
        self.registry.register(LowPriorityStrategy)
        self.registry.register(HighPriorityStrategy)
        
        strategies = self.registry.get_strategies_for_protocol("*")
        # 高优先级的策略应该排在前面
        self.assertEqual(strategies[0], "high_priority")
        self.assertEqual(strategies[1], "low_priority")
    
    def test_unregister_strategy(self):
        """测试策略注销"""
        self.registry.register(GenericProtocolMaskStrategy)
        self.assertTrue(self.registry.unregister("generic"))
        
        strategies = self.registry.list_all_strategies()
        self.assertNotIn("generic", strategies)
        
        # 尝试注销不存在的策略
        self.assertFalse(self.registry.unregister("nonexistent"))
    
    def test_get_strategy_info(self):
        """测试获取策略信息"""
        self.registry.register(GenericProtocolMaskStrategy)
        
        info = self.registry.get_strategy_info("generic")
        self.assertIsNotNone(info)
        self.assertEqual(info['name'], "generic")
        self.assertEqual(info['priority'], 0)
        self.assertTrue(info['can_handle_mixed'])
        
        # 获取不存在的策略信息
        info = self.registry.get_strategy_info("nonexistent")
        self.assertIsNone(info)


class TestProtocolMaskFactory(unittest.TestCase):
    """测试协议掩码策略工厂"""
    
    def setUp(self):
        """设置测试环境"""
        logging.disable(logging.CRITICAL)
        self.factory_config = {
            'default_confidence_threshold': 0.7,
            'enable_mixed_protocols': True,
            'max_strategies_per_protocol': 3
        }
        self.factory = ProtocolMaskFactory(self.factory_config)
    
    def tearDown(self):
        """清理测试环境"""
        logging.disable(logging.NOTSET)
    
    def test_factory_initialization(self):
        """测试工厂初始化"""
        self.assertIsNotNone(self.factory.registry)
        self.assertEqual(self.factory._default_confidence_threshold, 0.7)
        self.assertTrue(self.factory._enable_mixed_protocols)
        
        # 检查是否自动注册了内置策略
        strategies = self.factory.registry.list_all_strategies()
        self.assertIn("generic", strategies)
    
    def test_register_strategy(self):
        """测试策略注册"""
        initial_count = len(self.factory.registry.list_all_strategies())
        
        # 注册HTTP策略
        self.factory.register_strategy(HTTPMaskStrategy)
        
        final_count = len(self.factory.registry.list_all_strategies())
        self.assertEqual(final_count, initial_count + 1)
        
        strategies = self.factory.registry.list_all_strategies()
        self.assertIn("http_mask_strategy", strategies)
    
    def test_create_strategy(self):
        """测试策略实例创建"""
        strategy_config = {'test_param': 'value'}
        strategy = self.factory.create_strategy("generic", strategy_config)
        
        self.assertIsNotNone(strategy)
        self.assertIsInstance(strategy, GenericProtocolMaskStrategy)
        
        # 尝试创建不存在的策略
        strategy = self.factory.create_strategy("nonexistent", {})
        self.assertIsNone(strategy)
    
    def test_detect_protocols(self):
        """测试协议检测"""
        # 注册HTTP策略
        self.factory.register_strategy(HTTPMaskStrategy)
        
        http_request = b"GET /path HTTP/1.1\r\nHost: example.com\r\n\r\n"
        packets = [
            PacketAnalysis(
                packet_number=1,
                timestamp=1234567890.0,
                stream_id="TCP_test_stream_forward",
                seq_number=1000,
                payload_length=len(http_request),
                application_layer="HTTP",
                protocol_attributes={'payload': http_request}
            )
        ]
        
        protocol_matches = self.factory.detect_protocols(packets)
        
        self.assertIn("HTTP", protocol_matches)
        self.assertTrue(len(protocol_matches["HTTP"]) > 0)
        
        match = protocol_matches["HTTP"][0]
        self.assertEqual(match.protocol_name, "HTTP")
        self.assertGreaterEqual(match.confidence, 0.7)
    
    def test_select_best_strategies(self):
        """测试最佳策略选择"""
        # 创建模拟的策略匹配
        from src.pktmask.core.trim.strategies.protocol_mask_factory import StrategyMatch
        
        generic_strategy = GenericProtocolMaskStrategy({})
        http_strategy = HTTPMaskStrategy({})
        
        protocol_matches = {
            "HTTP": [
                StrategyMatch(
                    strategy=http_strategy,
                    confidence=0.95,
                    protocol_name="HTTP",
                    protocol_version="1.1",
                    attributes={}
                ),
                StrategyMatch(
                    strategy=generic_strategy,
                    confidence=0.5,
                    protocol_name="HTTP",
                    protocol_version=None,
                    attributes={}
                )
            ]
        }
        
        best_strategies = self.factory.select_best_strategies(protocol_matches)
        
        self.assertIn("HTTP", best_strategies)
        self.assertEqual(best_strategies["HTTP"], http_strategy)
    
    def test_generate_mask_entries_for_stream(self):
        """测试为流生成掩码条目"""
        packets = [
            PacketAnalysis(
                packet_number=1,
                timestamp=1234567890.0,
                stream_id="TCP_test_stream_forward",
                seq_number=1000,
                payload_length=100,
                application_layer="UNKNOWN"
            )
        ]
        
        entries = self.factory.generate_mask_entries_for_stream(
            stream_id="TCP_test_stream_forward",
            direction=ConnectionDirection.FORWARD,
            packets=packets,
            flow_metadata={}
        )
        
        # 应该使用通用策略生成条目
        self.assertTrue(len(entries) > 0)
        self.assertEqual(entries[0].tcp_stream_id, "TCP_test_stream_forward")
    
    def test_mixed_protocol_handling(self):
        """测试混合协议处理"""
        # 注册HTTP策略
        self.factory.register_strategy(HTTPMaskStrategy)
        
        http_request = b"GET /path HTTP/1.1\r\nHost: example.com\r\n\r\n"
        packets = [
            # HTTP数据包
            PacketAnalysis(
                packet_number=1,
                timestamp=1234567890.0,
                stream_id="TCP_test_stream_forward",
                seq_number=1000,
                payload_length=len(http_request),
                application_layer="HTTP",
                protocol_attributes={'payload': http_request}
            ),
            # 未知协议数据包
            PacketAnalysis(
                packet_number=2,
                timestamp=1234567891.0,
                stream_id="TCP_test_stream_forward",
                seq_number=2000,
                payload_length=100,
                application_layer="UNKNOWN"
            )
        ]
        
        entries = self.factory.generate_mask_entries_for_stream(
            stream_id="TCP_test_stream_forward",
            direction=ConnectionDirection.FORWARD,
            packets=packets,
            flow_metadata={}
        )
        
        # 应该为混合协议生成多个条目
        self.assertTrue(len(entries) > 0)
    
    def test_get_factory_info(self):
        """测试获取工厂信息"""
        info = self.factory.get_factory_info()
        
        self.assertIn('registered_strategies', info)
        self.assertIn('supported_protocols', info)
        self.assertIn('config', info)
        
        config = info['config']
        self.assertEqual(config['confidence_threshold'], 0.7)
        self.assertTrue(config['mixed_protocols_enabled'])


class TestPhase4Integration(unittest.TestCase):
    """Phase 4集成测试"""
    
    def setUp(self):
        """设置测试环境"""
        logging.disable(logging.CRITICAL)
    
    def tearDown(self):
        """清理测试环境"""
        logging.disable(logging.NOTSET)
    
    def test_global_factory_singleton(self):
        """测试全局工厂单例模式"""
        factory1 = get_protocol_mask_factory()
        factory2 = get_protocol_mask_factory()
        
        self.assertIs(factory1, factory2)
        self.assertIsInstance(factory1, ProtocolMaskFactory)
    
    def test_end_to_end_http_processing(self):
        """测试HTTP协议端到端处理"""
        # 获取全局工厂并注册HTTP策略
        factory = get_protocol_mask_factory()
        factory.register_strategy(HTTPMaskStrategy)
        
        # 创建HTTP请求数据包
        http_request = b"POST /api/data HTTP/1.1\r\nHost: api.example.com\r\nContent-Length: 20\r\n\r\n{\"key\": \"test_value\"}"
        
        packet = PacketAnalysis(
            packet_number=1,
            timestamp=1234567890.0,
            stream_id="TCP_192.168.1.100:12345_10.0.0.1:80_forward",
            seq_number=1000,
            payload_length=len(http_request),
            application_layer="HTTP",
            protocol_attributes={'payload': http_request}
        )
        
        # 生成掩码条目
        entries = factory.generate_mask_entries_for_stream(
            stream_id="TCP_192.168.1.100:12345_10.0.0.1:80_forward",
            direction=ConnectionDirection.FORWARD,
            packets=[packet],
            flow_metadata={}
        )
        
        # 验证结果
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        
        self.assertEqual(entry.tcp_stream_id, "TCP_192.168.1.100:12345_10.0.0.1:80_forward")
        self.assertEqual(entry.seq_start, 1000)
        self.assertEqual(entry.seq_end, 1000 + len(http_request) - 1)
        self.assertIn("http_request", entry.mask_type)
        self.assertIsInstance(entry.mask_spec, MaskAfter)
        
        # 验证保留了HTTP头部
        mask_spec = entry.mask_spec
        self.assertIsInstance(mask_spec, MaskAfter)
        # HTTP头部应该被保留（包括消息体的前50字节，根据配置）
        self.assertGreater(mask_spec.preserve_bytes, 50)  # 头部长度
    
    def test_protocol_strategy_framework_completeness(self):
        """测试协议策略框架的完整性"""
        # 验证所有Phase 4要求的组件都已实现
        
        # 1. 抽象协议掩码策略接口
        self.assertTrue(hasattr(ProtocolMaskStrategy, 'detect_protocol'))
        self.assertTrue(hasattr(ProtocolMaskStrategy, 'generate_mask_entries'))
        self.assertTrue(hasattr(ProtocolMaskStrategy, 'supported_protocols'))
        
        # 2. HTTP协议掩码策略
        http_strategy = HTTPMaskStrategy({})
        self.assertIn("HTTP", http_strategy.supported_protocols)
        self.assertEqual(http_strategy.strategy_name, "http_mask_strategy")
        
        # 3. 策略注册和动态加载机制
        factory = ProtocolMaskFactory({})
        self.assertIsNotNone(factory.registry)
        
        # 注册策略
        factory.register_strategy(HTTPMaskStrategy)
        self.assertIn("http_mask_strategy", factory.registry.list_all_strategies())
        
        # 4. 混合协议场景支持
        self.assertTrue(factory._enable_mixed_protocols)
        self.assertTrue(http_strategy.can_handle_mixed_protocols())


if __name__ == '__main__':
    unittest.main() 