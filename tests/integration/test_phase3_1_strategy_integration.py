"""
Phase 3.1 策略框架集成测试

验证策略框架与现有PktMask系统的集成效果，包括：
- 策略框架与多阶段执行器的集成
- 策略框架与配置系统的集成
- 策略框架与事件系统的集成
- 策略选择和应用的完整流程
- 与现有组件的兼容性验证

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

# PktMask核心组件
from src.pktmask.config.settings import AppConfig
from src.pktmask.gui.managers.event_coordinator import EventCoordinator
from src.pktmask.core.events import PipelineEvents

# Trim组件
from src.pktmask.core.trim.multi_stage_executor import MultiStageExecutor
from src.pktmask.core.trim.stages.base_stage import BaseStage, StageContext
from src.pktmask.core.trim.stages.stage_result import StageResult
from src.pktmask.core.trim.models.simple_execution_result import SimpleExecutionResult

# 策略框架组件
from src.pktmask.core.trim.strategies import (
    BaseStrategy, ProtocolInfo, TrimContext, TrimResult,
    ProtocolStrategyFactory, get_strategy_factory, DefaultStrategy
)
from src.pktmask.core.trim.models.mask_spec import MaskAfter, MaskRange, KeepAll


class MockProtocolStrategy(BaseStrategy):
    """模拟协议策略用于测试"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.trim_calls = []
        
    @property
    def supported_protocols(self) -> List[str]:
        return ['HTTP', 'TEST']
        
    @property
    def strategy_name(self) -> str:
        return 'mock_protocol'
        
    @property
    def priority(self) -> int:
        return 80  # 高于默认策略
        
    def can_handle(self, protocol_info: ProtocolInfo, context: TrimContext) -> bool:
        return protocol_info.name in self.supported_protocols
        
    def analyze_payload(self, payload: bytes, protocol_info: ProtocolInfo, 
                       context: TrimContext) -> Dict[str, Any]:
        return {
            'payload_size': len(payload),
            'protocol': protocol_info.name,
            'mock_analysis': True
        }
        
    def generate_mask_spec(self, payload: bytes, protocol_info: ProtocolInfo,
                          context: TrimContext, analysis: Dict[str, Any]) -> TrimResult:
        # 记录调用
        self.trim_calls.append({
            'payload_size': len(payload),
            'protocol': protocol_info.name,
            'timestamp': time.time()
        })
        
        # 模拟协议特定的裁切策略
        preserve_bytes = min(32, len(payload))
        return TrimResult(
            success=True,
            mask_spec=MaskAfter(preserve_bytes),
            preserved_bytes=preserve_bytes,
            trimmed_bytes=len(payload) - preserve_bytes,
            confidence=0.9,
            reason=f"Mock {protocol_info.name} 策略应用",
            warnings=[],
            metadata={'mock': True, 'protocol': protocol_info.name}
        )


class MockAnalyzerStage(BaseStage):
    """模拟分析器Stage，用于测试策略集成"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.strategy_factory = get_strategy_factory()
        
    @property
    def stage_name(self) -> str:
        return "MockAnalyzer"
        
    def initialize(self) -> bool:
        """初始化Stage"""
        return True
        
    def execute(self, context: StageContext) -> StageResult:
        """执行分析并应用策略"""
        self.logger.info("执行模拟协议分析和策略应用")
        
        # 模拟协议检测
        protocols_detected = [
            ProtocolInfo('HTTP', '1.1', 7, 80, {'method': 'GET'}),
            ProtocolInfo('TEST', None, 7, None, {}),
            ProtocolInfo('UNKNOWN', None, 7, None, {})
        ]
        
        total_preserved = 0
        total_trimmed = 0
        strategy_results = []
        
        # 为每个协议选择和应用策略
        for protocol in protocols_detected:
            # 创建裁切上下文
            trim_context = TrimContext(
                packet_index=0,
                stream_id='test_stream',
                direction='client_to_server',
                previous_packets=[],
                packet_size=1000,
                timestamp=time.time(),
                metadata={}
            )
            
            # 获取最佳策略
            strategy = self.strategy_factory.get_best_strategy(
                protocol, trim_context, self.config
            )
            
            if strategy:
                # 模拟载荷
                payload = b'X' * 1000
                
                # 应用策略
                result = strategy.trim_payload(payload, protocol, trim_context)
                strategy_results.append({
                    'protocol': protocol.name,
                    'strategy': strategy.strategy_name,
                    'success': result.success,
                    'preserved_bytes': result.preserved_bytes,
                    'trimmed_bytes': result.trimmed_bytes,
                    'confidence': result.confidence
                })
                
                total_preserved += result.preserved_bytes
                total_trimmed += result.trimmed_bytes
                
                self.logger.info(f"协议 {protocol.name} 使用策略 {strategy.strategy_name}, "
                               f"保留 {result.preserved_bytes} 字节")
        
        # 返回结果
        return StageResult(
            stage_name=self.stage_name,
            success=True,
            processing_time=0.1,
            input_file=context.input_file,
            output_file=context.input_file,  # 分析阶段不改变文件
            bytes_processed=len(protocols_detected) * 1000,
            packets_processed=len(protocols_detected),
            error_message=None,
            warnings=[],
            metadata={
                'protocols_detected': len(protocols_detected),
                'strategy_results': strategy_results,
                'total_preserved': total_preserved,
                'total_trimmed': total_trimmed
            }
        )


class TestPhase31StrategyIntegration:
    """Phase 3.1 策略框架集成测试"""
    
    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)
        
    @pytest.fixture
    def mock_config(self):
        """创建模拟配置"""
        return {
            'trim': {
                'enabled': True,
                'default_preserve_bytes': 64,
                'preserve_ratio': 0.1,
                'enable_adaptive': True
            },
            'strategies': {
                'mock_protocol': {
                    'enabled': True,
                    'priority': 80
                },
                'default': {
                    'enabled': True,
                    'preserve_ratio': 0.2
                }
            }
        }
        
    @pytest.fixture
    def event_coordinator(self):
        """创建事件协调器"""
        return EventCoordinator()
        
    @pytest.fixture
    def strategy_factory(self):
        """创建并配置策略工厂"""
        factory = get_strategy_factory()
        
        # 注册测试策略
        factory.register_strategy(MockProtocolStrategy)
        factory.register_strategy(DefaultStrategy)
        
        return factory
    
    def test_strategy_factory_integration_with_config(self, mock_config, strategy_factory):
        """测试策略工厂与配置系统的集成"""
        
        # 测试策略创建与配置集成
        config = mock_config['strategies']['mock_protocol']
        strategy = strategy_factory.create_strategy('mock_protocol', config)
        
        assert strategy is not None
        assert strategy.config == config
        assert strategy.strategy_name == 'mock_protocol'
        
        # 测试默认策略配置
        default_config = mock_config['strategies']['default']
        default_strategy = strategy_factory.create_strategy('default', default_config)
        
        assert default_strategy is not None
        assert default_strategy.config == default_config
    
    def test_strategy_selection_with_protocol_info(self, mock_config, strategy_factory):
        """测试基于协议信息的策略选择"""
        
        config = mock_config['trim']
        
        # 测试HTTP协议策略选择
        http_protocol = ProtocolInfo('HTTP', '1.1', 7, 80, {'method': 'GET'})
        context = TrimContext(0, 'test', 'client_to_server', [], 1000, 0.0, {})
        
        strategy = strategy_factory.get_best_strategy(http_protocol, context, config)
        
        assert strategy is not None
        assert isinstance(strategy, MockProtocolStrategy)
        assert strategy.can_handle(http_protocol, context)
        
        # 测试未知协议的默认策略选择
        unknown_protocol = ProtocolInfo('UNKNOWN', None, 7, None, {})
        strategy = strategy_factory.get_best_strategy(unknown_protocol, context, config)
        
        assert strategy is not None
        assert isinstance(strategy, DefaultStrategy)
        assert strategy.can_handle(unknown_protocol, context)
    
    def test_strategy_application_in_stage_context(self, temp_dir, mock_config, 
                                                   event_coordinator, strategy_factory):
        """测试策略在Stage上下文中的应用"""
        
        # 创建模拟输入文件
        input_file = temp_dir / "test.pcap"
        input_file.write_bytes(b'mock pcap data')
        
        # 创建Stage上下文
        context = StageContext(
            input_file=str(input_file),
            config=mock_config,
            event_coordinator=event_coordinator,
            temp_dir=str(temp_dir)
        )
        
        # 创建模拟分析器Stage
        analyzer = MockAnalyzerStage(mock_config['trim'])
        
        # 执行Stage
        result = analyzer.execute(context)
        
        assert result.success is True
        assert result.stage_name == "MockAnalyzer"
        assert 'strategy_results' in result.metadata
        assert 'protocols_detected' in result.metadata
        
        # 验证策略应用结果
        strategy_results = result.metadata['strategy_results']
        assert len(strategy_results) == 3  # HTTP, TEST, UNKNOWN
        
        # 验证HTTP协议使用了Mock策略
        http_result = next(r for r in strategy_results if r['protocol'] == 'HTTP')
        assert http_result['strategy'] == 'mock_protocol'
        assert http_result['success'] is True
        
        # 验证UNKNOWN协议使用了默认策略
        unknown_result = next(r for r in strategy_results if r['protocol'] == 'UNKNOWN')
        assert unknown_result['strategy'] == 'default'
        assert unknown_result['success'] is True
    
    def test_multi_stage_executor_with_strategy_integration(self, temp_dir, mock_config, 
                                                           event_coordinator, strategy_factory):
        """测试多阶段执行器与策略框架的集成"""
        
        # 创建测试文件
        input_file = temp_dir / "input.pcap"
        input_file.write_bytes(b'test pcap content')
        
        # 创建多阶段执行器
        executor = MultiStageExecutor(event_coordinator, str(temp_dir))
        
        # 添加模拟分析器Stage
        stages = [MockAnalyzerStage(mock_config['trim'])]
        
        # 执行多阶段处理
        result = executor.execute_stages(stages, str(input_file), mock_config)
        
        assert isinstance(result, SimpleExecutionResult)
        assert result.success is True
        assert len(result.stage_results) == 1
        
        # 验证策略应用的结果
        stage_result = result.stage_results[0]
        assert 'strategy_results' in stage_result.metadata
        
        strategy_results = stage_result.metadata['strategy_results']
        
        # 验证每种协议都有对应的策略处理结果
        protocols = [r['protocol'] for r in strategy_results]
        assert 'HTTP' in protocols
        assert 'TEST' in protocols  
        assert 'UNKNOWN' in protocols
    
    def test_event_system_integration(self, temp_dir, mock_config, event_coordinator, strategy_factory):
        """测试策略框架与事件系统的集成"""
        
        events_received = []
        
        def event_handler(event_type, **kwargs):
            events_received.append({
                'type': event_type,
                'kwargs': kwargs,
                'timestamp': time.time()
            })
        
        # 注册事件处理器
        event_coordinator.register_handler(PipelineEvents.STEP_START, event_handler)
        event_coordinator.register_handler(PipelineEvents.STEP_END, event_handler)
        
        # 创建测试文件
        input_file = temp_dir / "test.pcap"
        input_file.write_bytes(b'test content')
        
        # 创建并执行多阶段处理
        executor = MultiStageExecutor(event_coordinator, str(temp_dir))
        stages = [MockAnalyzerStage(mock_config['trim'])]
        
        result = executor.execute_stages(stages, str(input_file), mock_config)
        
        assert result.success is True
        assert len(events_received) >= 2  # 至少有STEP_START和STEP_END
        
        # 验证事件包含正确信息
        start_events = [e for e in events_received if e['type'] == PipelineEvents.STEP_START]
        end_events = [e for e in events_received if e['type'] == PipelineEvents.STEP_END]
        
        assert len(start_events) >= 1
        assert len(end_events) >= 1
    
    def test_strategy_configuration_validation(self, strategy_factory):
        """测试策略配置验证"""
        
        # 测试有效配置
        valid_config = {
            'enable_adaptive': True,
            'preserve_ratio': 0.2,
            'confidence_threshold': 0.8
        }
        
        strategy = strategy_factory.create_strategy('default', valid_config)
        assert strategy is not None
        assert strategy.get_config_value('enable_adaptive') is True
        
        # 测试无效配置
        invalid_config = {
            'preserve_ratio': 1.5,  # 超出范围
        }
        
        strategy = strategy_factory.create_strategy('default', invalid_config)
        assert strategy is None  # 创建应该失败
    
    def test_strategy_error_handling_and_fallback(self, mock_config, strategy_factory):
        """测试策略错误处理和回退机制"""
        
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
                return 90
                
            def can_handle(self, protocol_info, context):
                return protocol_info.name == 'ERROR'
                
            def analyze_payload(self, payload, protocol_info, context):
                raise RuntimeError("策略分析错误")
                
            def generate_mask_spec(self, payload, protocol_info, context, analysis):
                raise RuntimeError("策略生成错误")
        
        # 注册错误策略
        strategy_factory.register_strategy(ErrorStrategy)
        
        # 测试错误处理
        error_protocol = ProtocolInfo('ERROR', None, 7, None, {})
        context = TrimContext(0, 'test', 'client_to_server', [], 100, 0.0, {})
        
        strategy = strategy_factory.get_best_strategy(error_protocol, context, mock_config['trim'])
        
        if strategy:
            payload = b'test payload'
            result = strategy.trim_payload(payload, error_protocol, context)
            
            # 错误策略应该返回失败结果
            assert result.success is False
            assert result.preserved_bytes == len(payload)  # 保持原始载荷
            assert result.trimmed_bytes == 0
    
    def test_strategy_performance_and_caching(self, mock_config, strategy_factory):
        """测试策略性能和缓存机制"""
        
        start_time = time.time()
        
        # 多次创建相同策略
        strategies = []
        for _ in range(10):
            strategy = strategy_factory.create_strategy('default', mock_config['strategies']['default'])
            strategies.append(strategy)
        
        creation_time = time.time() - start_time
        
        # 验证创建时间合理 (应该很快)
        assert creation_time < 1.0  # 10个策略创建应该在1秒内完成
        
        # 验证所有策略都成功创建
        assert all(s is not None for s in strategies)
        assert len(set(id(s) for s in strategies)) == 10  # 每次都是新实例
    
    def test_comprehensive_integration_workflow(self, temp_dir, mock_config, 
                                              event_coordinator, strategy_factory):
        """测试完整的集成工作流程"""
        
        # 1. 准备测试环境
        input_file = temp_dir / "comprehensive_test.pcap"
        input_file.write_bytes(b'comprehensive test pcap data')
        
        # 2. 配置事件监听
        workflow_events = []
        
        def workflow_handler(event_type, **kwargs):
            workflow_events.append({
                'event': event_type,
                'data': kwargs,
                'timestamp': time.time()
            })
        
        for event_type in [PipelineEvents.PIPELINE_START, PipelineEvents.PIPELINE_END,
                          PipelineEvents.STEP_START, PipelineEvents.STEP_END]:
            event_coordinator.register_handler(event_type, workflow_handler)
        
        # 3. 执行完整的多阶段处理
        executor = MultiStageExecutor(event_coordinator, str(temp_dir))
        stages = [
            MockAnalyzerStage(mock_config['trim'])
        ]
        
        start_time = time.time()
        result = executor.execute_stages(stages, str(input_file), mock_config)
        execution_time = time.time() - start_time
        
        # 4. 验证执行结果
        assert result.success is True
        assert execution_time < 5.0  # 应该在5秒内完成
        assert len(result.stage_results) == 1
        
        # 5. 验证事件流
        assert len(workflow_events) >= 4  # 至少包含pipeline和step的开始结束事件
        
        # 6. 验证策略应用效果
        stage_result = result.stage_results[0]
        strategy_results = stage_result.metadata['strategy_results']
        
        # 验证协议覆盖
        protocols_handled = set(r['protocol'] for r in strategy_results)
        assert 'HTTP' in protocols_handled
        assert 'TEST' in protocols_handled
        assert 'UNKNOWN' in protocols_handled
        
        # 验证策略选择
        strategies_used = set(r['strategy'] for r in strategy_results)
        assert 'mock_protocol' in strategies_used  # HTTP和TEST应该使用mock策略
        assert 'default' in strategies_used      # UNKNOWN应该使用默认策略
        
        # 验证处理统计
        total_preserved = stage_result.metadata['total_preserved']
        total_trimmed = stage_result.metadata['total_trimmed']
        assert total_preserved > 0
        assert total_trimmed > 0
        assert total_preserved + total_trimmed == 3000  # 3个协议 * 1000字节
        
        # 7. 性能验证
        assert stage_result.processing_time < 1.0  # Stage执行应该很快
        
        print(f"✅ 综合集成测试完成:")
        print(f"   执行时间: {execution_time:.3f}s")
        print(f"   协议处理: {len(protocols_handled)} 种")
        print(f"   策略使用: {len(strategies_used)} 个")
        print(f"   事件触发: {len(workflow_events)} 次")
        print(f"   数据处理: 保留 {total_preserved} 字节, 裁切 {total_trimmed} 字节")


if __name__ == '__main__':
    # 运行集成测试
    pytest.main([__file__, '-v', '--tb=short']) 