"""
增强策略工厂验证测试

验证双策略系统集成的策略工厂功能，包括策略选择、A/B测试、性能对比等。

作者: PktMask Team
创建时间: 2025-01-15
版本: 1.0.0
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import time
from typing import Dict, Any, List

try:
    from src.pktmask.core.trim.strategies.factory import (
        EnhancedStrategyFactory,
        ComparisonWrapper,
        StrategyRegistry,
        get_enhanced_strategy_factory
    )
    from src.pktmask.core.trim.strategies.base_strategy import BaseStrategy, ProtocolInfo, TrimContext
    from src.pktmask.config.http_strategy_config import (
        HttpStrategyConfiguration,
        StrategyMode,
        get_default_http_strategy_config,
        create_ab_test_config
    )
    FACTORY_AVAILABLE = True
except ImportError:
    FACTORY_AVAILABLE = False


class MockStrategy(BaseStrategy):
    """测试用的模拟策略"""
    
    def __init__(self, config: Dict[str, Any], name: str = "mock", protocols: List[str] = None):
        super().__init__(config)
        self._name = name
        self._protocols = protocols or ["http"]
        self.can_handle_calls = 0
        self.analyze_calls = 0
        
    @property
    def strategy_name(self) -> str:
        return self._name
    
    @property
    def supported_protocols(self) -> List[str]:
        return self._protocols
    
    def can_handle(self, protocol_info: ProtocolInfo, context: TrimContext) -> bool:
        self.can_handle_calls += 1
        return True
    
    def analyze_payload(self, payload: bytes, protocol_info: ProtocolInfo,
                       context: TrimContext) -> Dict[str, Any]:
        self.analyze_calls += 1
        return {
            'strategy_used': self._name,
            'payload_size': len(payload),
            'analysis_time': time.time()
        }
    
    def generate_mask_spec(self, payload: bytes, protocol_info: ProtocolInfo,
                          context: TrimContext, analysis: Dict[str, Any]) -> Any:
        return {
            'mask_type': 'test_mask',
            'preserve_bytes': min(len(payload), 100)
        }


class TestStrategyRegistry(unittest.TestCase):
    """策略注册表测试"""
    
    def setUp(self):
        """测试准备"""
        if not FACTORY_AVAILABLE:
            self.skipTest("策略工厂模块不可用")
            
        self.registry = StrategyRegistry()
        
    def test_strategy_registration(self):
        """测试策略注册"""
        mock_strategy = MockStrategy
        
        # 注册策略
        self.registry.register(mock_strategy)
        
        # 验证注册成功
        registered_strategies = self.registry.list_all_strategies()
        self.assertIn("mock", registered_strategies)
        
        # 验证协议映射
        http_strategies = self.registry.get_strategies_for_protocol("http")
        self.assertIn("mock", http_strategies)
        
    def test_strategy_unregistration(self):
        """测试策略注销"""
        mock_strategy = MockStrategy
        
        # 先注册
        self.registry.register(mock_strategy)
        self.assertIn("mock", self.registry.list_all_strategies())
        
        # 再注销
        success = self.registry.unregister("mock")
        self.assertTrue(success)
        self.assertNotIn("mock", self.registry.list_all_strategies())
        
        # 重复注销应该失败
        success = self.registry.unregister("mock")
        self.assertFalse(success)
        
    def test_strategy_retrieval(self):
        """测试策略检索"""
        mock_strategy = MockStrategy
        
        # 注册策略
        self.registry.register(mock_strategy)
        
        # 获取策略类
        strategy_class = self.registry.get_strategy_class("mock")
        self.assertEqual(strategy_class, mock_strategy)
        
        # 获取不存在的策略
        missing_strategy = self.registry.get_strategy_class("nonexistent")
        self.assertIsNone(missing_strategy)
        
    def test_protocol_mapping(self):
        """测试协议映射"""
        # 注册支持不同协议的策略
        http_strategy = type("HTTPStrategy", (MockStrategy,), {
            "__init__": lambda self, config: MockStrategy.__init__(self, config, "http_strategy", ["http"])
        })
        tls_strategy = type("TLSStrategy", (MockStrategy,), {
            "__init__": lambda self, config: MockStrategy.__init__(self, config, "tls_strategy", ["tls"])
        })
        multi_strategy = type("MultiStrategy", (MockStrategy,), {
            "__init__": lambda self, config: MockStrategy.__init__(self, config, "multi_strategy", ["http", "tls"])
        })
        
        self.registry.register(http_strategy)
        self.registry.register(tls_strategy)
        self.registry.register(multi_strategy)
        
        # 验证协议映射
        http_strategies = self.registry.get_strategies_for_protocol("http")
        self.assertIn("http_strategy", http_strategies)
        self.assertIn("multi_strategy", http_strategies)
        self.assertNotIn("tls_strategy", http_strategies)
        
        tls_strategies = self.registry.get_strategies_for_protocol("tls")
        self.assertIn("tls_strategy", tls_strategies)
        self.assertIn("multi_strategy", tls_strategies)
        self.assertNotIn("http_strategy", tls_strategies)


class TestEnhancedStrategyFactory(unittest.TestCase):
    """增强策略工厂测试"""
    
    def setUp(self):
        """测试准备"""
        if not FACTORY_AVAILABLE:
            self.skipTest("策略工厂模块不可用")
            
        self.http_config = get_default_http_strategy_config()
        self.factory = EnhancedStrategyFactory(self.http_config)
        
        # 创建模拟的协议信息和上下文
        self.protocol_info = Mock(spec=ProtocolInfo)
        self.protocol_info.protocol = "http"
        
        self.context = Mock(spec=TrimContext)
        self.context.input_file = "test_file.pcap"
        
    @patch('src.pktmask.core.trim.strategies.factory.get_strategy_factory')
    def test_legacy_strategy_selection(self, mock_get_factory):
        """测试Legacy策略选择"""
        # 模拟策略工厂
        mock_factory = Mock()
        mock_strategy = MockStrategy({}, "legacy_http")
        mock_factory.get_strategy_by_name.return_value = mock_strategy
        mock_get_factory.return_value = mock_factory
        
        # 配置为使用Legacy策略
        self.http_config.strategy.primary_strategy = StrategyMode.LEGACY
        
        # 获取策略
        strategy = self.factory.get_http_strategy(self.protocol_info, self.context, {})
        
        # 验证调用了Legacy策略
        mock_factory.get_strategy_by_name.assert_called_with("http_trim", {})
        self.assertEqual(strategy, mock_strategy)
        
    @patch('src.pktmask.core.trim.strategies.factory.get_strategy_factory')
    def test_scanning_strategy_selection(self, mock_get_factory):
        """测试Scanning策略选择"""
        # 模拟策略工厂
        mock_factory = Mock()
        mock_strategy = MockStrategy({}, "scanning_http")
        mock_factory.get_strategy_by_name.return_value = mock_strategy
        mock_get_factory.return_value = mock_factory
        
        # 配置为使用Scanning策略
        self.http_config.strategy.primary_strategy = StrategyMode.SCANNING
        
        # 获取策略
        strategy = self.factory.get_http_strategy(self.protocol_info, self.context, {})
        
        # 验证调用了Scanning策略
        mock_factory.get_strategy_by_name.assert_called_with("http_scanning", {})
        self.assertEqual(strategy, mock_strategy)
        
    @patch('src.pktmask.core.trim.strategies.factory.get_strategy_factory')
    def test_ab_test_strategy_selection(self, mock_get_factory):
        """测试A/B测试策略选择"""
        # 模拟策略工厂
        mock_factory = Mock()
        legacy_strategy = MockStrategy({}, "legacy_http")
        scanning_strategy = MockStrategy({}, "scanning_http")
        
        def mock_get_strategy(name, config):
            if name == "http_trim":
                return legacy_strategy
            elif name == "http_scanning":
                return scanning_strategy
            return None
            
        mock_factory.get_strategy_by_name.side_effect = mock_get_strategy
        mock_get_factory.return_value = mock_factory
        
        # 配置为A/B测试模式
        self.http_config.strategy.primary_strategy = StrategyMode.AB_TEST
        self.http_config.strategy.enable_ab_testing = True
        self.http_config.strategy.ab_test_ratio = 0.5
        
        # 多次获取策略，验证一致性
        strategy1 = self.factory.get_http_strategy(self.protocol_info, self.context, {})
        strategy2 = self.factory.get_http_strategy(self.protocol_info, self.context, {})
        
        # 相同文件应该返回相同策略类型
        self.assertEqual(type(strategy1), type(strategy2))
        
        # 验证返回的是预期的策略之一
        self.assertIn(strategy1, [legacy_strategy, scanning_strategy])
        
    @patch('src.pktmask.core.trim.strategies.factory.get_strategy_factory')
    def test_comparison_mode_strategy(self, mock_get_factory):
        """测试性能对比模式策略"""
        # 模拟策略工厂
        mock_factory = Mock()
        legacy_strategy = MockStrategy({}, "legacy_http")
        scanning_strategy = MockStrategy({}, "scanning_http")
        
        def mock_get_strategy(name, config):
            if name == "http_trim":
                return legacy_strategy
            elif name == "http_scanning":
                return scanning_strategy
            return None
            
        mock_factory.get_strategy_by_name.side_effect = mock_get_strategy
        mock_get_factory.return_value = mock_factory
        
        # 配置为对比模式
        self.http_config.strategy.primary_strategy = StrategyMode.COMPARISON
        
        # 获取策略
        strategy = self.factory.get_http_strategy(self.protocol_info, self.context, {})
        
        # 验证返回了ComparisonWrapper
        self.assertIsInstance(strategy, ComparisonWrapper)
        self.assertEqual(strategy.legacy_strategy, legacy_strategy)
        self.assertEqual(strategy.scanning_strategy, scanning_strategy)
        
    def test_auto_strategy_selection(self):
        """测试自动策略选择"""
        # 配置为自动模式
        self.http_config.strategy.primary_strategy = StrategyMode.AUTO
        
        # 目前自动模式应该返回None（回退到默认逻辑）
        strategy = self.factory.get_http_strategy(self.protocol_info, self.context, {})
        self.assertIsNone(strategy)
        
    def test_config_update(self):
        """测试配置更新"""
        new_config = create_ab_test_config(0.2)
        
        # 更新配置
        self.factory.update_config(new_config)
        
        # 验证配置已更新
        self.assertEqual(self.factory.http_config.strategy.ab_test_ratio, 0.2)
        self.assertTrue(self.factory.http_config.strategy.enable_ab_testing)


class TestComparisonWrapper(unittest.TestCase):
    """对比包装器测试"""
    
    def setUp(self):
        """测试准备"""
        if not FACTORY_AVAILABLE:
            self.skipTest("策略工厂模块不可用")
            
        self.legacy_strategy = MockStrategy({}, "legacy", ["http"])
        self.scanning_strategy = MockStrategy({}, "scanning", ["http"])
        self.http_config = get_default_http_strategy_config()
        
        self.wrapper = ComparisonWrapper(
            self.legacy_strategy, 
            self.scanning_strategy, 
            {}, 
            self.http_config
        )
        
        # 创建模拟的协议信息和上下文
        self.protocol_info = Mock(spec=ProtocolInfo)
        self.protocol_info.protocol = "http"
        
        self.context = Mock(spec=TrimContext)
        self.context.input_file = "test_file.pcap"
        
    def test_wrapper_properties(self):
        """测试包装器属性"""
        self.assertEqual(self.wrapper.strategy_name, "comparison_wrapper")
        
        # 验证支持的协议是两个策略的并集
        supported_protocols = self.wrapper.supported_protocols
        self.assertIn("http", supported_protocols)
        
    def test_can_handle(self):
        """测试能力检查"""
        # 只要任一策略能处理即可
        result = self.wrapper.can_handle(self.protocol_info, self.context)
        self.assertTrue(result)
        
        # 验证调用了两个策略的can_handle
        self.assertGreater(self.legacy_strategy.can_handle_calls, 0)
        self.assertGreater(self.scanning_strategy.can_handle_calls, 0)
        
    def test_analyze_payload(self):
        """测试载荷分析"""
        test_payload = b"GET / HTTP/1.1\r\nHost: example.com\r\n\r\n"
        
        # 执行分析
        result = self.wrapper.analyze_payload(test_payload, self.protocol_info, self.context)
        
        # 验证返回了对比数据
        self.assertIn('comparison_metadata', result)
        self.assertEqual(result['comparison_metadata']['payload_size'], len(test_payload))
        
        # 验证调用了两个策略的analyze_payload
        self.assertGreater(self.legacy_strategy.analyze_calls, 0)
        self.assertGreater(self.scanning_strategy.analyze_calls, 0)
        
    def test_comparison_data_collection(self):
        """测试对比数据收集"""
        test_payload = b"GET / HTTP/1.1\r\nHost: example.com\r\n\r\n"
        
        # 执行几次分析收集数据
        for i in range(3):
            self.wrapper.analyze_payload(test_payload, self.protocol_info, self.context)
            
        # 验证收集了对比数据
        comparison_data = self.wrapper.comparison_data
        self.assertEqual(len(comparison_data), 3)
        
        # 验证数据结构
        for data in comparison_data:
            self.assertIn('comparison_metadata', data)
            self.assertIn('payload_size', data['comparison_metadata'])


class TestFactoryIntegration(unittest.TestCase):
    """工厂集成测试"""
    
    def setUp(self):
        """测试准备"""
        if not FACTORY_AVAILABLE:
            self.skipTest("策略工厂模块不可用")
            
    def test_get_enhanced_strategy_factory(self):
        """测试获取增强策略工厂"""
        factory = get_enhanced_strategy_factory()
        
        self.assertIsInstance(factory, EnhancedStrategyFactory)
        self.assertIsNotNone(factory.http_config)
        
    def test_factory_with_custom_config(self):
        """测试使用自定义配置的工厂"""
        custom_config = create_ab_test_config(0.15)
        factory = get_enhanced_strategy_factory(custom_config)
        
        self.assertEqual(factory.http_config.strategy.ab_test_ratio, 0.15)
        self.assertTrue(factory.http_config.strategy.enable_ab_testing)
        
    @patch('src.pktmask.core.trim.strategies.factory.HTTP_STRATEGY_CONFIG_AVAILABLE', False)
    def test_factory_without_config_module(self):
        """测试没有配置模块时的工厂行为"""
        factory = get_enhanced_strategy_factory()
        
        # 应该能正常创建但配置为None
        self.assertIsInstance(factory, EnhancedStrategyFactory)


class TestErrorHandling(unittest.TestCase):
    """错误处理测试"""
    
    def setUp(self):
        """测试准备"""
        if not FACTORY_AVAILABLE:
            self.skipTest("策略工厂模块不可用")
            
    def test_invalid_strategy_registration(self):
        """测试无效策略注册"""
        registry = StrategyRegistry()
        
        # 尝试注册非策略类
        with self.assertRaises(TypeError):
            registry.register(str)  # str不是BaseStrategy的子类
            
    def test_strategy_creation_failure(self):
        """测试策略创建失败"""
        # 创建一个会抛出异常的策略类
        class FailingStrategy(BaseStrategy):
            def __init__(self, config):
                raise ValueError("策略创建失败")
                
            @property
            def strategy_name(self):
                return "failing"
                
            @property
            def supported_protocols(self):
                return ["test"]
                
        registry = StrategyRegistry()
        
        # 注册失败的策略应该抛出异常
        with self.assertRaises(ValueError):
            registry.register(FailingStrategy)
            
    def test_missing_strategy_handling(self):
        """测试缺失策略处理"""
        factory = EnhancedStrategyFactory()
        
        # 创建模拟的协议信息和上下文
        protocol_info = Mock(spec=ProtocolInfo)
        protocol_info.protocol = "unknown"
        
        context = Mock(spec=TrimContext)
        context.input_file = "test.pcap"
        
        # 尝试获取不存在的策略
        strategy = factory.get_http_strategy(protocol_info, context, {})
        
        # 应该返回None而不是抛出异常
        self.assertIsNone(strategy)


if __name__ == '__main__':
    unittest.main() 