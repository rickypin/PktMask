"""
Phase 3.1 策略框架集成测试 (简化版)

验证策略框架与PktMask核心系统的集成效果，避免GUI依赖。
重点测试：
- 策略框架的基础功能集成
- 策略选择和应用逻辑
- 配置系统集成
- 错误处理和回退机制

作者: PktMask Team  
创建时间: 2025-06-13
版本: 1.0.0
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, List
from unittest.mock import Mock, patch, MagicMock
import json
import time

# 策略框架组件
from src.pktmask.core.trim.strategies import (
    BaseStrategy, ProtocolInfo, TrimContext, TrimResult,
    ProtocolStrategyFactory, get_strategy_factory, DefaultStrategy
)
from src.pktmask.core.trim.models.mask_spec import MaskAfter, MaskRange, KeepAll


class TestProtocolStrategy(BaseStrategy):
    """测试协议策略"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.call_log = []
        
    @property
    def supported_protocols(self) -> List[str]:
        return ['HTTP', 'HTTPS', 'TEST']
        
    @property
    def strategy_name(self) -> str:
        return 'test_protocol'
        
    @property
    def priority(self) -> int:
        return 85  # 高于默认策略
        
    def can_handle(self, protocol_info: ProtocolInfo, context: TrimContext) -> bool:
        return protocol_info.name in self.supported_protocols
        
    def analyze_payload(self, payload: bytes, protocol_info: ProtocolInfo, 
                       context: TrimContext) -> Dict[str, Any]:
        self.call_log.append(f"analyze_{protocol_info.name}")
        return {
            'payload_size': len(payload),
            'protocol': protocol_info.name,
            'test_analysis': True,
            'confidence': 0.95
        }
        
    def generate_mask_spec(self, payload: bytes, protocol_info: ProtocolInfo,
                          context: TrimContext, analysis: Dict[str, Any]) -> TrimResult:
        self.call_log.append(f"generate_{protocol_info.name}")
        
        # 根据协议类型选择不同策略
        if protocol_info.name == 'HTTP':
            preserve_bytes = min(48, len(payload))
        elif protocol_info.name == 'HTTPS':
            preserve_bytes = min(64, len(payload))  
        else:
            preserve_bytes = min(32, len(payload))
            
        return TrimResult(
            success=True,
            mask_spec=MaskAfter(preserve_bytes),
            preserved_bytes=preserve_bytes,
            trimmed_bytes=len(payload) - preserve_bytes,
            confidence=0.95,
            reason=f"测试{protocol_info.name}策略应用",
            warnings=[],
            metadata={
                'test_strategy': True,
                'protocol': protocol_info.name,
                'analysis_confidence': 0.95
            }
        )


class TestPhase31StrategyIntegrationSimplified:
    """Phase 3.1 策略框架集成测试 (简化版)"""
    
    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)
        
    @pytest.fixture
    def test_config(self):
        """创建测试配置"""
        return {
            'trim': {
                'enabled': True,
                'default_preserve_bytes': 64,
                'preserve_ratio': 0.15,
                'enable_adaptive': True,
                'confidence_threshold': 0.8
            },
            'test_protocol': {
                'enabled': True,
                'priority': 85,
                'specific_param': 'test_value'
            },
            'default': {
                'enabled': True,
                'preserve_ratio': 0.2,
                'default_preserve_bytes': 32
            }
        }
        
    @pytest.fixture
    def strategy_factory(self):
        """创建并配置策略工厂"""
        factory = get_strategy_factory()
        
        # 注册测试策略
        factory.register_strategy(TestProtocolStrategy)
        factory.register_strategy(DefaultStrategy)
        
        return factory
    
    def test_strategy_registration_and_discovery(self, strategy_factory):
        """测试策略注册和发现机制"""
        
        # 验证策略注册
        available_strategies = strategy_factory.list_available_strategies()
        
        assert 'test_protocol' in available_strategies
        assert 'default' in available_strategies
        
        # 验证协议支持
        assert 'HTTP' in available_strategies['test_protocol']
        assert 'HTTPS' in available_strategies['test_protocol']
        assert 'TEST' in available_strategies['test_protocol']
        assert '*' in available_strategies['default']
    
    def test_best_strategy_selection_logic(self, test_config, strategy_factory):
        """测试最佳策略选择逻辑"""
        
        config = test_config['trim']
        context = TrimContext(0, 'test_stream', 'client_to_server', [], 1000, 0.0, {})
        
        # 测试HTTP协议 - 应该选择测试协议策略
        http_protocol = ProtocolInfo('HTTP', '1.1', 7, 80, {'method': 'GET'})
        strategy = strategy_factory.get_best_strategy(http_protocol, context, config)
        
        assert strategy is not None
        assert isinstance(strategy, TestProtocolStrategy)
        assert strategy.strategy_name == 'test_protocol'
        
        # 测试HTTPS协议 - 也应该选择测试协议策略
        https_protocol = ProtocolInfo('HTTPS', '1.1', 7, 443, {'method': 'GET'})
        strategy = strategy_factory.get_best_strategy(https_protocol, context, config)
        
        assert strategy is not None
        assert isinstance(strategy, TestProtocolStrategy)
        
        # 测试未知协议 - 应该选择默认策略
        unknown_protocol = ProtocolInfo('UNKNOWN', None, 7, None, {})
        strategy = strategy_factory.get_best_strategy(unknown_protocol, context, config)
        
        assert strategy is not None
        assert isinstance(strategy, DefaultStrategy)
        assert strategy.strategy_name == 'default'
    
    def test_strategy_execution_with_different_protocols(self, test_config, strategy_factory):
        """测试不同协议的策略执行效果"""
        
        config = test_config['trim']
        context = TrimContext(0, 'test_stream', 'client_to_server', [], 1000, 0.0, {})
        payload = b'X' * 1000
        
        protocols_to_test = [
            ('HTTP', 48),   # HTTP应该保留48字节
            ('HTTPS', 64),  # HTTPS应该保留64字节
            ('TEST', 32),   # TEST应该保留32字节
        ]
        
        results = []
        
        for protocol_name, expected_preserved in protocols_to_test:
            protocol = ProtocolInfo(protocol_name, None, 7, None, {})
            strategy = strategy_factory.get_best_strategy(protocol, context, config)
            
            assert strategy is not None
            assert isinstance(strategy, TestProtocolStrategy)
            
            result = strategy.trim_payload(payload, protocol, context)
            
            assert result.success is True
            assert result.preserved_bytes == expected_preserved
            assert result.trimmed_bytes == 1000 - expected_preserved
            assert result.confidence == 0.95
            assert f"测试{protocol_name}策略应用" in result.reason
            
            results.append({
                'protocol': protocol_name,
                'preserved': result.preserved_bytes,
                'trimmed': result.trimmed_bytes,
                'confidence': result.confidence
            })
        
        # 验证不同协议有不同的处理结果
        preserved_values = [r['preserved'] for r in results]
        assert len(set(preserved_values)) == 3  # 三种不同的保留字节数
        
        # 验证策略调用日志
        test_strategy = strategy
        expected_calls = ['analyze_HTTP', 'generate_HTTP', 'analyze_HTTPS', 'generate_HTTPS', 
                         'analyze_TEST', 'generate_TEST']
        assert len(test_strategy.call_log) == 6
    
    def test_default_strategy_fallback_mechanism(self, test_config, strategy_factory):
        """测试默认策略回退机制"""
        
        config = test_config['trim']
        
        # 测试不支持的协议列表
        unsupported_protocols = ['FTP', 'SMTP', 'SSH', 'DNS', 'TELNET']
        
        for protocol_name in unsupported_protocols:
            protocol = ProtocolInfo(protocol_name, None, 7, None, {})
            context = TrimContext(0, 'test_stream', 'client_to_server', [], 500, 0.0, {})
            
            strategy = strategy_factory.get_best_strategy(protocol, context, config)
            
            # 应该回退到默认策略
            assert strategy is not None
            assert isinstance(strategy, DefaultStrategy)
            assert strategy.can_handle(protocol, context) is True
            
            # 测试默认策略的处理效果
            payload = b'Y' * 500
            result = strategy.trim_payload(payload, protocol, context)
            
            assert result.success is True
            assert result.preserved_bytes > 0
            assert result.trimmed_bytes >= 0
            assert result.preserved_bytes + result.trimmed_bytes == 500
            assert "默认策略应用" in result.reason
    
    def test_configuration_integration_and_validation(self, test_config, strategy_factory):
        """测试配置集成和验证"""
        
        # 测试有效配置的策略创建
        valid_config = test_config['default']
        strategy = strategy_factory.create_strategy('default', valid_config)
        
        assert strategy is not None
        assert strategy.get_config_value('preserve_ratio') == 0.2
        assert strategy.get_config_value('default_preserve_bytes') == 32
        
        # 测试无效配置的处理
        invalid_configs = [
            {'preserve_ratio': 1.5},  # 超出范围
            {'preserve_ratio': -0.1}, # 负值
            {'default_preserve_bytes': -10}, # 负值
        ]
        
        for invalid_config in invalid_configs:
            strategy = strategy_factory.create_strategy('default', invalid_config)
            assert strategy is None  # 应该创建失败
    
    def test_strategy_error_handling_and_robustness(self, test_config, strategy_factory):
        """测试策略错误处理和健壮性"""
        
        # 创建会抛出异常的策略
        class ErrorStrategy(BaseStrategy):
            def __init__(self, config):
                super().__init__(config)
                
            @property
            def supported_protocols(self):
                return ['ERROR']
                
            @property 
            def strategy_name(self):
                return 'error_strategy'
                
            @property
            def priority(self):
                return 95
                
            def can_handle(self, protocol_info, context):
                return protocol_info.name == 'ERROR'
                
            def analyze_payload(self, payload, protocol_info, context):
                raise RuntimeError("模拟分析错误")
                
            def generate_mask_spec(self, payload, protocol_info, context, analysis):
                raise RuntimeError("模拟生成错误")
        
        # 注册错误策略
        strategy_factory.register_strategy(ErrorStrategy)
        
        # 测试错误处理
        error_protocol = ProtocolInfo('ERROR', None, 7, None, {})
        context = TrimContext(0, 'test', 'client_to_server', [], 100, 0.0, {})
        
        strategy = strategy_factory.get_best_strategy(error_protocol, context, test_config['trim'])
        
        if strategy:
            payload = b'error test payload'
            result = strategy.trim_payload(payload, error_protocol, context)
            
            # 错误策略应该优雅降级
            assert result.success is False
            assert result.preserved_bytes == len(payload)  # 保持原始载荷
            assert result.trimmed_bytes == 0
            assert "错误" in result.reason or "异常" in result.reason
    
    def test_strategy_performance_characteristics(self, test_config, strategy_factory):
        """测试策略性能特征"""
        
        config = test_config['trim']
        
        # 测试策略创建性能
        start_time = time.time()
        
        strategies = []
        for _ in range(20):
            strategy = strategy_factory.create_strategy('default', test_config['default'])
            strategies.append(strategy)
        
        creation_time = time.time() - start_time
        
        # 20个策略创建应该很快
        assert creation_time < 0.5  
        assert all(s is not None for s in strategies)
        
        # 测试策略执行性能
        protocol = ProtocolInfo('HTTP', '1.1', 7, 80, {})
        context = TrimContext(0, 'perf_test', 'client_to_server', [], 10000, 0.0, {})
        strategy = strategy_factory.get_best_strategy(protocol, context, config)
        
        assert strategy is not None
        
        # 测试大载荷处理性能
        large_payload = b'X' * 10000
        
        start_time = time.time()
        result = strategy.trim_payload(large_payload, protocol, context)
        execution_time = time.time() - start_time
        
        # 大载荷处理应该很快
        assert execution_time < 0.1
        assert result.success is True
        assert result.preserved_bytes > 0
    
    def test_comprehensive_workflow_integration(self, test_config, strategy_factory):
        """测试综合工作流集成"""
        
        # 模拟完整的协议处理工作流
        protocols_detected = [
            ProtocolInfo('HTTP', '1.1', 7, 80, {'method': 'GET'}),
            ProtocolInfo('HTTPS', '1.1', 7, 443, {'method': 'POST'}),
            ProtocolInfo('TEST', None, 7, None, {}),
            ProtocolInfo('DNS', None, 17, 53, {}),  # UDP协议
            ProtocolInfo('UNKNOWN', None, 7, None, {})
        ]
        
        config = test_config['trim']
        workflow_results = []
        total_preserved = 0
        total_trimmed = 0
        
        for i, protocol in enumerate(protocols_detected):
            context = TrimContext(
                packet_index=i,
                stream_id=f'stream_{i}',
                direction='client_to_server' if i % 2 == 0 else 'server_to_client',
                previous_packets=[],
                packet_size=1000,
                timestamp=time.time(),
                metadata={'packet_id': i}
            )
            
            # 1. 选择最佳策略
            strategy = strategy_factory.get_best_strategy(protocol, context, config)
            assert strategy is not None
            
            # 2. 应用策略
            payload = b'X' * 1000
            result = strategy.trim_payload(payload, protocol, context)
            
            # 3. 记录结果
            workflow_results.append({
                'protocol': protocol.name,
                'strategy': strategy.strategy_name,
                'success': result.success,
                'preserved': result.preserved_bytes,
                'trimmed': result.trimmed_bytes,
                'confidence': result.confidence,
                'direction': context.direction
            })
            
            total_preserved += result.preserved_bytes
            total_trimmed += result.trimmed_bytes
        
        # 验证工作流结果
        assert len(workflow_results) == 5
        assert all(r['success'] for r in workflow_results)
        assert total_preserved + total_trimmed == 5000  # 5个协议 * 1000字节
        
        # 验证策略分配
        http_results = [r for r in workflow_results if r['protocol'] in ['HTTP', 'HTTPS', 'TEST']]
        default_results = [r for r in workflow_results if r['strategy'] == 'default']
        
        assert len(http_results) == 3  # HTTP, HTTPS, TEST使用测试策略
        assert len(default_results) == 2  # DNS, UNKNOWN使用默认策略
        
        # 验证不同协议有不同的处理效果
        http_preserved = next(r['preserved'] for r in workflow_results if r['protocol'] == 'HTTP')
        https_preserved = next(r['preserved'] for r in workflow_results if r['protocol'] == 'HTTPS')
        test_preserved = next(r['preserved'] for r in workflow_results if r['protocol'] == 'TEST')
        
        assert http_preserved == 48   # HTTP
        assert https_preserved == 64  # HTTPS  
        assert test_preserved == 32   # TEST
        
        print(f"✅ 综合工作流集成测试完成:")
        print(f"   协议处理: {len(workflow_results)} 种")
        print(f"   总保留字节: {total_preserved}")
        print(f"   总裁切字节: {total_trimmed}")
        print(f"   平均置信度: {sum(r['confidence'] for r in workflow_results)/len(workflow_results):.3f}")


if __name__ == '__main__':
    # 运行简化集成测试
    pytest.main([__file__, '-v', '--tb=short']) 