#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Phase 1 集成测试

验证Enhanced Trim Payloads Phase 1组件与现有PktMask系统的集成效果。

测试范围:
1. 数据结构兼容性测试
2. 多阶段执行器与现有处理器系统的集成
3. 事件系统集成测试
4. 配置系统兼容性测试
5. 错误处理机制验证
"""

import pytest
import tempfile
import logging
from pathlib import Path
from typing import List, Dict, Any
from unittest.mock import Mock, patch

# 修复导入路径
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# 现有系统组件
from src.pktmask.core.processors.base_processor import BaseProcessor, ProcessorConfig, ProcessorResult
from src.pktmask.core.processors.registry import ProcessorRegistry

# Phase 1 新实现的组件
from src.pktmask.core.trim.multi_stage_executor import MultiStageExecutor, StageResult
from src.pktmask.core.trim.stages.base_stage import BaseStage, StageContext
from src.pktmask.core.trim.models.mask_table import StreamMaskTable, StreamMaskEntry
from src.pktmask.core.trim.models.mask_spec import MaskAfter, MaskRange, KeepAll
from src.pktmask.core.trim.models.execution_result import ExecutionResult
from src.pktmask.core.trim.models.simple_execution_result import SimpleExecutionResult
from src.pktmask.core.trim.exceptions import StageExecutionError, PipelineExecutionError


class MockStage(BaseStage):
    """模拟Stage用于测试"""
    
    def __init__(self, name: str, should_fail: bool = False):
        super().__init__(name)
        self.should_fail = should_fail
        self.executed = False
        
    def execute(self, context: StageContext) -> ProcessorResult:
        """实现BaseStage的execute方法"""
        self.executed = True
        if self.should_fail:
            return ProcessorResult(success=False, error=f"Mock stage {self.name} 故意失败")
        
        return ProcessorResult(
            success=True, 
            data={"processed": True, "stage": self.name},
            stats={"stage_name": self.name, "executed": True}
        )
    
    def validate_inputs(self, context: StageContext) -> bool:
        """实现BaseStage的validate_inputs方法"""
        return context.input_file.exists()


class TestPhase1Integration:
    """Phase 1 集成测试套件"""
    
    def setup_method(self):
        """测试设置"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.input_file = self.temp_dir / "input.pcap" 
        self.output_file = self.temp_dir / "output.pcap"
        
        # 创建模拟输入文件
        self.input_file.write_bytes(b"mock pcap data")
        
        # 设置日志
        logging.basicConfig(level=logging.DEBUG)
        
    def teardown_method(self):
        """测试清理"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_data_structures_compatibility(self):
        """测试1: 数据结构与现有系统的兼容性"""
        
        # 测试掩码表基础功能
        mask_table = StreamMaskTable()
        
        # 添加各种类型的掩码规范
        mask_after = MaskAfter(keep_bytes=10)
        mask_range = MaskRange(ranges=[(0, 50)])  # 修正为正确的API
        keep_all = KeepAll()
        
        mask_table.add_mask_range("tcp_stream_1", 1000, 2000, mask_after)
        mask_table.add_mask_range("tcp_stream_2", 500, 1500, mask_range)
        mask_table.add_mask_range("tcp_stream_3", 0, 100, keep_all)
        
        mask_table.finalize()
        
        # 验证查询功能
        result1 = mask_table.lookup("tcp_stream_1", 1500, 100)
        assert result1 is not None
        assert isinstance(result1, MaskAfter)
        assert result1.keep_bytes == 10
        
        # 验证统计信息
        stats = mask_table.get_statistics()
        assert stats['total_streams'] == 3
        assert stats['total_entries'] == 3
        
        print("✅ 数据结构兼容性测试通过")
    
    def test_multi_stage_executor_basic_functionality(self):
        """测试2: 多阶段执行器基础功能"""
        
        # 创建执行器
        executor = MultiStageExecutor(
            work_dir=self.temp_dir,
            event_callback=None
        )
        
        # 注册模拟Stage
        stage1 = MockStage("preprocess")
        stage2 = MockStage("analyze") 
        stage3 = MockStage("rewrite")
        
        executor.register_stage(stage1)
        executor.register_stage(stage2)
        executor.register_stage(stage3)
        
        # 执行管道
        result = executor.execute_pipeline(self.input_file, self.output_file)
        
        # 验证结果
        assert isinstance(result, SimpleExecutionResult)
        assert result.success
        assert result.total_stages == 3
        assert all([stage1.executed, stage2.executed, stage3.executed])
        
        # 验证执行摘要
        summary = executor.get_execution_summary()
        assert summary['total_stages'] == 3
        assert summary['successful_stages'] == 3
        assert summary['failed_stages'] == 0
        
        print("✅ 多阶段执行器基础功能测试通过")
    
    def test_event_system_integration(self):
        """测试3: 事件系统集成测试"""
        
        # 创建事件回调记录器
        events_received = []
        
        def event_callback(event_type, data):
            events_received.append({
                'type': event_type,
                'data': data
            })
        
        # 创建带事件回调的执行器
        executor = MultiStageExecutor(
            work_dir=self.temp_dir,
            event_callback=event_callback
        )
        
        # 注册Stage
        stage = MockStage("test_stage")
        executor.register_stage(stage)
        
        # 执行管道
        result = executor.execute_pipeline(self.input_file, self.output_file)
        
        # 验证事件
        assert len(events_received) >= 2  # 至少有开始和结束事件
        
        # 检查事件类型
        event_types = [event['type'] for event in events_received]
        assert 'PIPELINE_START' in event_types
        assert 'PIPELINE_END' in event_types
        
        print("✅ 事件系统集成测试通过")
    
    def test_error_handling_integration(self):
        """测试4: 错误处理机制验证"""
        
        # 创建会失败的执行器
        executor = MultiStageExecutor(work_dir=self.temp_dir)
        
        # 注册一个成功的Stage和一个失败的Stage
        stage1 = MockStage("success_stage", should_fail=False)
        stage2 = MockStage("fail_stage", should_fail=True)
        
        executor.register_stage(stage1)
        executor.register_stage(stage2)
        
        # 验证异常处理
        with pytest.raises(StageExecutionError) as exc_info:
            executor.execute_pipeline(self.input_file, self.output_file)
        
        # 验证异常信息
        assert exc_info.value.stage_name == "fail_stage"
        assert "故意失败" in str(exc_info.value)
        
        # 验证第一个Stage执行成功，第二个Stage失败
        assert stage1.executed
        assert stage2.executed
        
        print("✅ 错误处理机制验证通过")
    
    def test_processor_registry_extensibility(self):
        """测试5: 处理器注册表扩展性测试"""
        
        # 创建一个模拟的Enhanced Trimmer处理器
        class MockEnhancedTrimmer(BaseProcessor):
            def __init__(self, config: ProcessorConfig):
                super().__init__(config)
                self.multi_stage_executor = MultiStageExecutor()
            
            def process_file(self, input_path: str, output_path: str) -> ProcessorResult:
                # 模拟多阶段处理
                try:
                    # 注册测试Stage
                    test_stage = MockStage("enhanced_trim")
                    self.multi_stage_executor.register_stage(test_stage)
                    
                    # 初始化Stage
                    if not test_stage.initialize():
                        return ProcessorResult(success=False, error="Stage初始化失败")
                    
                    # 执行处理
                    result = self.multi_stage_executor.execute_pipeline(
                        Path(input_path), Path(output_path)
                    )
                    
                    return ProcessorResult(
                        success=result.success,
                        stats={"stages_executed": result.total_stages}
                    )
                except Exception as e:
                    return ProcessorResult(success=False, error=str(e))
            
            def get_display_name(self) -> str:
                return "Enhanced Trimmer"
        
        # 测试注册新处理器
        ProcessorRegistry.register_processor("enhanced_trim", MockEnhancedTrimmer)
        
        # 验证注册成功
        assert ProcessorRegistry.is_processor_available("enhanced_trim")
        assert "enhanced_trim" in ProcessorRegistry.list_processors()
        
        # 测试创建和使用处理器
        config = ProcessorConfig(name="enhanced_trim", enabled=True)
        processor = ProcessorRegistry.get_processor("enhanced_trim", config)
        
        assert isinstance(processor, MockEnhancedTrimmer)
        assert processor.get_display_name() == "Enhanced Trimmer"
        
        # 测试处理器功能
        result = processor.process_file(str(self.input_file), str(self.output_file))
        assert result.success
        assert result.stats["stages_executed"] == 1
        
        # 清理
        ProcessorRegistry.unregister_processor("enhanced_trim")
        
        print("✅ 处理器注册表扩展性测试通过")
    
    def test_configuration_compatibility(self):
        """测试6: 配置系统兼容性测试"""
        
        # 需要先导入TrimmerConfig
        from src.pktmask.core.trim.models.execution_result import TrimmerConfig
        
        # 测试ExecutionResult与现有系统的兼容性
        config = TrimmerConfig()
        execution_result = ExecutionResult(
            input_file=str(self.input_file),
            output_file=str(self.output_file),
            config=config
        )
        
        # 添加阶段并设置状态
        preprocess_stage = execution_result.add_stage("preprocess")
        analyze_stage = execution_result.add_stage("analyze")
        rewrite_stage = execution_result.add_stage("rewrite")
        
        preprocess_stage.mark_completed()
        analyze_stage.mark_started()
        # rewrite_stage保持NOT_STARTED状态
        
        # 验证状态设置
        assert execution_result.get_stage("preprocess").is_successful()
        assert execution_result.get_stage("analyze").status.value == "running"
        assert execution_result.get_stage("rewrite").status.value == "not_started"
        
        # 验证整体状态
        assert not execution_result.is_successful()  # 还有阶段未完成
        
        # 完成所有阶段
        analyze_stage.mark_completed()
        rewrite_stage.mark_completed()
        execution_result.mark_completed()
        assert execution_result.is_successful()
        
        print("✅ 配置系统兼容性测试通过")
    
    def test_resource_management(self):
        """测试7: 资源管理测试"""
        
        # 创建执行器
        executor = MultiStageExecutor(work_dir=self.temp_dir)
        
        # 创建Stage上下文
        context = StageContext(
            input_file=self.input_file,
            output_file=self.output_file,
            work_dir=self.temp_dir
        )
        
        # 添加一些临时文件
        temp_file1 = context.create_temp_file("stage1", ".tmp")
        temp_file2 = context.create_temp_file("stage2", ".tmp")
        
        # 验证临时文件创建
        assert temp_file1.exists()
        assert temp_file2.exists()
        assert len(context.temp_files) == 2
        
        # 清理资源
        context.cleanup()
        
        # 验证清理效果
        assert not temp_file1.exists()
        assert not temp_file2.exists()
        assert len(context.temp_files) == 0
        
        print("✅ 资源管理测试通过")
    
    def test_performance_baseline(self):
        """测试8: 性能基线测试"""
        
        import time
        
        # 创建执行器
        executor = MultiStageExecutor(work_dir=self.temp_dir)
        
        # 注册多个Stage
        for i in range(5):
            stage = MockStage(f"stage_{i}")
            executor.register_stage(stage)
        
        # 测量执行时间
        start_time = time.time()
        result = executor.execute_pipeline(self.input_file, self.output_file)
        execution_time = time.time() - start_time
        
        # 验证性能要求 (执行时间应该在合理范围内)
        assert execution_time < 5.0  # 5秒内完成
        assert result.success
        assert result.duration > 0
        
        # 验证进度计算
        progress = executor.get_current_progress()
        assert progress == 100.0  # 执行完成后应该是100%
        
        print(f"✅ 性能基线测试通过 - 执行时间: {execution_time:.3f}s")
    
    def run_integration_test_suite(self):
        """运行完整的集成测试套件"""
        
        test_methods = [
            self.test_data_structures_compatibility,
            self.test_multi_stage_executor_basic_functionality,
            self.test_event_system_integration,
            self.test_error_handling_integration,
            self.test_processor_registry_extensibility,
            self.test_configuration_compatibility,
            self.test_resource_management,
            self.test_performance_baseline
        ]
        
        passed_tests = 0
        failed_tests = 0
        
        print("🚀 开始Phase 1集成测试...")
        print("=" * 60)
        
        for test_method in test_methods:
            try:
                print(f"\n📋 运行测试: {test_method.__name__}")
                test_method()
                passed_tests += 1
            except Exception as e:
                print(f"❌ 测试失败: {test_method.__name__}: {str(e)}")
                failed_tests += 1
        
        print("\n" + "=" * 60)
        print(f"📊 测试结果:")
        print(f"   ✅ 通过: {passed_tests}")
        print(f"   ❌ 失败: {failed_tests}")
        print(f"   📈 成功率: {passed_tests/(passed_tests+failed_tests)*100:.1f}%")
        
        if failed_tests == 0:
            print("\n🎉 所有集成测试通过！Phase 1与现有系统集成良好。")
        else:
            print(f"\n⚠️  发现 {failed_tests} 个集成问题，需要进一步调查。")
        
        return failed_tests == 0


if __name__ == "__main__":
    # 运行集成测试
    test_suite = TestPhase1Integration()
    test_suite.setup_method()
    
    try:
        success = test_suite.run_integration_test_suite()
        exit(0 if success else 1)
    finally:
        test_suite.teardown_method() 