"""
Phase 3.1 策略框架单元测试

测试协议策略框架的基础功能，包括：
- 基础策略接口
- 策略工厂和注册表
- 默认策略实现

作者: PktMask Team
创建时间: 2025-01-15
版本: 1.0.0
"""

import pytest
from typing import Dict, Any, List
from unittest.mock import Mock, patch

from src.pktmask.core.trim.strategies.base_strategy import (
    BaseStrategy, ProtocolInfo, TrimContext, TrimResult
)
from src.pktmask.core.trim.strategies.factory import (
    ProtocolStrategyFactory, StrategyRegistry, get_strategy_factory
)
from src.pktmask.core.trim.strategies.default_strategy import DefaultStrategy
from src.pktmask.core.trim.models.mask_spec import MaskAfter, MaskRange, KeepAll


class TestStrategy(BaseStrategy):
    """测试用策略实现"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
    @property
    def supported_protocols(self) -> List[str]:
        return ['TEST']
        
    @property
    def strategy_name(self) -> str:
        return 'test_strategy'
        
    @property
    def priority(self) -> int:
        return 50
        
    def can_handle(self, protocol_info: ProtocolInfo, context: TrimContext) -> bool:
        return protocol_info.name == 'TEST'
        
    def analyze_payload(self, payload: bytes, protocol_info: ProtocolInfo, 
                       context: TrimContext) -> Dict[str, Any]:
        return {'test': True, 'payload_size': len(payload)}
        
    def generate_mask_spec(self, payload: bytes, protocol_info: ProtocolInfo,
                          context: TrimContext, analysis: Dict[str, Any]) -> TrimResult:
        return TrimResult(
            success=True,
            mask_spec=MaskAfter(10),
            preserved_bytes=10,
            trimmed_bytes=len(payload) - 10,
            confidence=0.8,
            reason="测试策略",
            warnings=[],
            metadata={}
        )


class TestProtocolInfo:
    """测试ProtocolInfo数据类"""
    
    def test_protocol_info_creation(self):
        """测试协议信息创建"""
        info = ProtocolInfo(
            name='HTTP',
            version='1.1',
            layer=7,
            port=80,
            characteristics={'encrypted': False}
        )
        
        assert info.name == 'HTTP'
        assert info.version == '1.1'
        assert info.layer == 7
        assert info.port == 80
        assert info.characteristics['encrypted'] is False


class TestTrimContext:
    """测试TrimContext数据类"""
    
    def test_trim_context_creation(self):
        """测试裁切上下文创建"""
        context = TrimContext(
            packet_index=1,
            stream_id='stream_1',
            flow_direction='client_to_server',
            protocol_stack=['ETH', 'IP', 'TCP', 'HTTP'],
            payload_size=1024,
            timestamp=1642694400.0,
            metadata={'test': True}
        )
        
        assert context.packet_index == 1
        assert context.stream_id == 'stream_1'
        assert context.flow_direction == 'client_to_server'
        assert context.protocol_stack == ['ETH', 'IP', 'TCP', 'HTTP']
        assert context.payload_size == 1024
        assert context.timestamp == 1642694400.0
        assert context.metadata['test'] is True


class TestTrimResult:
    """测试TrimResult数据类"""
    
    def test_trim_result_creation(self):
        """测试裁切结果创建"""
        mask_spec = MaskAfter(64)
        result = TrimResult(
            success=True,
            mask_spec=mask_spec,
            preserved_bytes=64,
            trimmed_bytes=960,
            confidence=0.85,
            reason="HTTP策略裁切",
            warnings=["警告信息"],
            metadata={'strategy': 'http'}
        )
        
        assert result.success is True
        assert result.mask_spec == mask_spec
        assert result.preserved_bytes == 64
        assert result.trimmed_bytes == 960
        assert result.confidence == 0.85
        assert result.reason == "HTTP策略裁切"
        assert result.warnings == ["警告信息"]
        assert result.metadata['strategy'] == 'http'


class TestBaseStrategy:
    """测试BaseStrategy基类"""
    
    def test_strategy_initialization(self):
        """测试策略初始化"""
        config = {'test_param': 'value'}
        strategy = TestStrategy(config)
        
        assert strategy.config == config
        assert strategy.strategy_name == 'test_strategy'
        assert strategy.supported_protocols == ['TEST']
        assert strategy.priority == 50
        
    def test_trim_payload_success(self):
        """测试载荷裁切成功场景"""
        strategy = TestStrategy({})
        protocol_info = ProtocolInfo('TEST', None, 7, None, {})
        context = TrimContext(0, 'test', 'client_to_server', [], 100, 0.0, {})
        payload = b'x' * 100
        
        result = strategy.trim_payload(payload, protocol_info, context)
        
        assert result.success is True
        assert result.preserved_bytes == 10
        assert result.trimmed_bytes == 90
        assert result.confidence == 0.8
        
    def test_trim_payload_unsupported_protocol(self):
        """测试不支持的协议"""
        strategy = TestStrategy({})
        protocol_info = ProtocolInfo('UNSUPPORTED', None, 7, None, {})
        context = TrimContext(0, 'test', 'client_to_server', [], 100, 0.0, {})
        payload = b'x' * 100
        
        result = strategy.trim_payload(payload, protocol_info, context)
        
        assert result.success is False
        assert result.preserved_bytes == 100
        assert result.trimmed_bytes == 0
        assert result.confidence == 0.0
        assert "不支持协议" in result.reason
        
    def test_config_validation(self):
        """测试配置验证"""
        # 有效配置
        strategy = TestStrategy({'valid': True})
        assert strategy.config['valid'] is True
        
        # 无效配置类型
        with pytest.raises(ValueError, match="配置必须是字典类型"):
            TestStrategy("invalid")
            
    def test_config_operations(self):
        """测试配置操作"""
        strategy = TestStrategy({'key1': 'value1'})
        
        # 获取配置值
        assert strategy.get_config_value('key1') == 'value1'
        assert strategy.get_config_value('missing', 'default') == 'default'
        
        # 更新配置
        strategy.update_config({'key2': 'value2'})
        assert strategy.get_config_value('key2') == 'value2'


class TestStrategyRegistry:
    """测试策略注册表"""
    
    def test_strategy_registration(self):
        """测试策略注册"""
        registry = StrategyRegistry()
        
        # 注册策略
        registry.register(TestStrategy)
        
        # 验证注册
        assert 'test_strategy' in registry.list_all_strategies()
        assert 'TEST' in registry.list_all_protocols()
        assert 'test_strategy' in registry.get_strategies_for_protocol('TEST')
        
    def test_strategy_unregistration(self):
        """测试策略注销"""
        registry = StrategyRegistry()
        registry.register(TestStrategy)
        
        # 注销策略
        result = registry.unregister('test_strategy')
        assert result is True
        
        # 验证注销
        assert 'test_strategy' not in registry.list_all_strategies()
        assert registry.get_strategies_for_protocol('TEST') == []
        
        # 注销不存在的策略
        result = registry.unregister('non_existent')
        assert result is False
        
    def test_get_strategy_class(self):
        """测试获取策略类"""
        registry = StrategyRegistry()
        registry.register(TestStrategy)
        
        # 获取存在的策略
        strategy_class = registry.get_strategy_class('test_strategy')
        assert strategy_class == TestStrategy
        
        # 获取不存在的策略
        strategy_class = registry.get_strategy_class('non_existent')
        assert strategy_class is None
        
    def test_invalid_strategy_registration(self):
        """测试无效策略注册"""
        registry = StrategyRegistry()
        
        # 尝试注册非策略类
        class InvalidStrategy:
            pass
            
        with pytest.raises(TypeError, match="必须继承自 BaseStrategy"):
            registry.register(InvalidStrategy)


class TestProtocolStrategyFactory:
    """测试协议策略工厂"""
    
    def test_factory_initialization(self):
        """测试工厂初始化"""
        factory = ProtocolStrategyFactory()
        assert factory.registry is not None
        
    def test_strategy_registration_and_creation(self):
        """测试策略注册和创建"""
        factory = ProtocolStrategyFactory()
        factory.register_strategy(TestStrategy)
        
        # 创建策略实例
        strategy = factory.create_strategy('test_strategy', {'test': True})
        assert strategy is not None
        assert isinstance(strategy, TestStrategy)
        assert strategy.config['test'] is True
        
        # 创建不存在的策略
        strategy = factory.create_strategy('non_existent', {})
        assert strategy is None
        
    def test_get_best_strategy(self):
        """测试获取最佳策略"""
        factory = ProtocolStrategyFactory()
        factory.register_strategy(TestStrategy)
        factory.register_strategy(DefaultStrategy)
        
        protocol_info = ProtocolInfo('TEST', None, 7, None, {})
        context = TrimContext(0, 'test', 'client_to_server', [], 100, 0.0, {})
        
        # 获取TEST协议的最佳策略
        best_strategy = factory.get_best_strategy(protocol_info, context, {})
        assert best_strategy is not None
        assert isinstance(best_strategy, TestStrategy)  # 优先级高于默认策略
        
        # 获取不支持协议的策略（应该返回默认策略）
        protocol_info_unknown = ProtocolInfo('UNKNOWN', None, 7, None, {})
        best_strategy = factory.get_best_strategy(protocol_info_unknown, context, {})
        assert best_strategy is not None
        assert isinstance(best_strategy, DefaultStrategy)
        
    def test_get_strategy_by_name(self):
        """测试根据名称获取策略"""
        factory = ProtocolStrategyFactory()
        factory.register_strategy(TestStrategy)
        
        strategy = factory.get_strategy_by_name('test_strategy', {})
        assert strategy is not None
        assert isinstance(strategy, TestStrategy)
        
        strategy = factory.get_strategy_by_name('non_existent', {})
        assert strategy is None
        
    def test_list_available_strategies(self):
        """测试列出可用策略"""
        factory = ProtocolStrategyFactory()
        factory.register_strategy(TestStrategy)
        factory.register_strategy(DefaultStrategy)
        
        strategies = factory.list_available_strategies()
        assert 'test_strategy' in strategies
        assert 'default' in strategies
        assert strategies['test_strategy'] == ['TEST']
        assert strategies['default'] == ['*']


class TestDefaultStrategy:
    """测试默认策略"""
    
    def test_default_strategy_initialization(self):
        """测试默认策略初始化"""
        strategy = DefaultStrategy({})
        
        assert strategy.strategy_name == 'default'
        assert strategy.supported_protocols == ['*']
        assert strategy.priority == 0
        
    def test_default_strategy_can_handle_any_protocol(self):
        """测试默认策略可以处理任意协议"""
        strategy = DefaultStrategy({})
        
        for protocol_name in ['HTTP', 'TLS', 'UNKNOWN', 'TEST']:
            protocol_info = ProtocolInfo(protocol_name, None, 7, None, {})
            context = TrimContext(0, 'test', 'client_to_server', [], 100, 0.0, {})
            
            assert strategy.can_handle(protocol_info, context) is True
            
    def test_default_strategy_payload_analysis(self):
        """测试默认策略载荷分析"""
        strategy = DefaultStrategy({})
        protocol_info = ProtocolInfo('UNKNOWN', None, 7, None, {})
        context = TrimContext(0, 'test', 'client_to_server', [], 100, 0.0, {})
        
        # 测试文本载荷
        text_payload = b'GET /index.html HTTP/1.1\r\nHost: example.com\r\n\r\n'
        analysis = strategy.analyze_payload(text_payload, protocol_info, context)
        
        assert analysis['payload_size'] == len(text_payload)
        assert analysis['printable_ratio'] > 0.5  # 大部分是可打印字符
        assert 'entropy' in analysis
        
        # 测试二进制载荷
        binary_payload = bytes(range(256))
        analysis = strategy.analyze_payload(binary_payload, protocol_info, context)
        
        assert analysis['payload_size'] == 256
        assert analysis['printable_ratio'] < 0.5  # 大部分不是可打印字符
        
    def test_default_strategy_mask_generation(self):
        """测试默认策略掩码生成"""
        strategy = DefaultStrategy({})
        protocol_info = ProtocolInfo('UNKNOWN', None, 7, None, {})
        context = TrimContext(0, 'test', 'client_to_server', [], 100, 0.0, {})
        
        payload = b'x' * 200
        result = strategy.trim_payload(payload, protocol_info, context)
        
        assert result.success is True
        assert result.mask_spec is not None
        assert result.preserved_bytes > 0
        assert result.trimmed_bytes >= 0
        assert 0.0 <= result.confidence <= 1.0
        assert "默认策略应用" in result.reason
        
    def test_default_strategy_config_options(self):
        """测试默认策略配置选项"""
        config = {
            'default_preserve_bytes': 128,
            'min_preserve_bytes': 50,
            'max_preserve_bytes': 512,
            'preserve_ratio': 0.2,
            'trim_strategy': 'mask_range',
            'enable_adaptive': False
        }
        
        strategy = DefaultStrategy(config)
        protocol_info = ProtocolInfo('UNKNOWN', None, 7, None, {})
        context = TrimContext(0, 'test', 'client_to_server', [], 1000, 0.0, {})
        
        payload = b'x' * 1000
        result = strategy.trim_payload(payload, protocol_info, context)
        
        assert result.success is True
        # 非自适应模式应该使用固定值
        assert result.preserved_bytes <= 128
        
    def test_default_strategy_config_validation(self):
        """测试默认策略配置验证"""
        # 无效的preserve_bytes
        with pytest.raises(ValueError, match="default_preserve_bytes 必须是非负整数"):
            DefaultStrategy({'default_preserve_bytes': -1})
            
        # 无效的preserve_ratio
        with pytest.raises(ValueError, match="preserve_ratio 必须在 0.0-1.0 范围内"):
            DefaultStrategy({'preserve_ratio': 1.5})
            
        # 无效的trim_strategy
        with pytest.raises(ValueError, match="trim_strategy 必须是"):
            DefaultStrategy({'trim_strategy': 'invalid'})


class TestGlobalStrategyFactory:
    """测试全局策略工厂"""
    
    def test_get_strategy_factory_singleton(self):
        """测试获取策略工厂单例"""
        factory1 = get_strategy_factory()
        factory2 = get_strategy_factory()
        
        assert factory1 is factory2  # 应该是同一个实例
        assert isinstance(factory1, ProtocolStrategyFactory)


if __name__ == '__main__':
    pytest.main([__file__]) 