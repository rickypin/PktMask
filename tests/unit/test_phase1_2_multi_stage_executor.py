#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Phase 1.2: 多阶段执行器框架测试

测试MultiStageExecutor、BaseStage、StageContext等核心组件。
"""

import pytest
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch

from pktmask.core.trim.multi_stage_executor import (
    MultiStageExecutor, StageResult
)
from pktmask.core.trim.stages.base_stage import (
    BaseStage, StageContext
)
from pktmask.core.trim.stages.stage_result import (
    StageStatus, StageMetrics, StageResultCollection
)
from pktmask.core.trim.models.simple_execution_result import (
    SimpleExecutionResult, SimpleStageState
)
from pktmask.core.processors.base_processor import ProcessorResult
from pktmask.core.events import PipelineEvents
from pktmask.core.trim.exceptions import StageExecutionError, PipelineExecutionError


class MockStage(BaseStage):
    """模拟Stage实现，用于测试"""
    
    def __init__(self, name: str, should_succeed: bool = True, 
                 execution_time: float = 0.1, config: dict = None):
        super().__init__(name, config)
        self.should_succeed = should_succeed
        self.execution_time = execution_time
        self.validate_called = False
        self.execute_called = False
        self.cleanup_called = False
    
    def validate_inputs(self, context: StageContext) -> bool:
        self.validate_called = True
        return True
    
    def execute(self, context: StageContext) -> ProcessorResult:
        self.execute_called = True
        
        # 模拟执行时间
        time.sleep(self.execution_time)
        
        if self.should_succeed:
            return ProcessorResult(
                success=True,
                data={'processed': True},
                stats={'execution_time': self.execution_time}
            )
        else:
            return ProcessorResult(
                success=False,
                error=f"Mock stage {self.name} failed"
            )
    
    def _cleanup_impl(self, context: StageContext) -> None:
        self.cleanup_called = True


class TestStageContext:
    """测试StageContext类"""
    
    def test_stage_context_creation(self):
        """测试StageContext创建"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_file = temp_path / "input.pcap"
            output_file = temp_path / "output.pcap"
            work_dir = temp_path / "work"
            
            # 创建测试文件
            input_file.touch()
            work_dir.mkdir()
            
            context = StageContext(input_file, output_file, work_dir)
            
            assert context.input_file == input_file
            assert context.output_file == output_file
            assert context.work_dir == work_dir
            assert context.current_stage == ""
            assert context.stage_progress == 0.0
            assert context.stats == {}
            assert context.temp_files == []
    
    def test_temp_file_management(self):
        """测试临时文件管理"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_file = temp_path / "input.pcap"
            output_file = temp_path / "output.pcap"
            work_dir = temp_path / "work"
            
            input_file.touch()
            work_dir.mkdir()
            
            context = StageContext(input_file, output_file, work_dir)
            
            # 创建临时文件并注册
            temp_file1 = temp_path / "temp1.tmp"
            temp_file2 = temp_path / "temp2.tmp"
            temp_file1.touch()
            temp_file2.touch()
            
            context.register_temp_file(temp_file1)
            context.register_temp_file(temp_file2)
            
            assert len(context.temp_files) == 2
            assert temp_file1.exists()
            assert temp_file2.exists()
            
            # 清理临时文件
            context.cleanup_temp_files()
            
            assert len(context.temp_files) == 0
            assert not temp_file1.exists()
            assert not temp_file2.exists()


class TestBaseStage:
    """测试BaseStage抽象基类"""
    
    def test_stage_initialization(self):
        """测试Stage初始化"""
        config = {'param1': 'value1', 'param2': 42}
        stage = MockStage("test_stage", config=config)
        
        assert stage.name == "test_stage"
        assert stage.config == config
        assert not stage.is_initialized
        assert stage.get_config_value('param1') == 'value1'
        assert stage.get_config_value('param2') == 42
        assert stage.get_config_value('nonexistent', 'default') == 'default'
    
    def test_stage_initialization_process(self):
        """测试Stage初始化过程"""
        stage = MockStage("test_stage")
        
        assert not stage.is_initialized
        
        success = stage.initialize()
        
        assert success
        assert stage.is_initialized
    
    def test_stage_progress_callback(self):
        """测试Stage进度回调"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_file = temp_path / "input.pcap"
            output_file = temp_path / "output.pcap"
            work_dir = temp_path / "work"
            
            input_file.touch()
            work_dir.mkdir()
            
            context = StageContext(input_file, output_file, work_dir)
            stage = MockStage("test_stage")
            
            progress_callback = stage.get_progress_callback(context)
            
            # 测试进度更新
            progress_callback(0.5)
            assert context.stage_progress == 0.5
            
            progress_callback(1.0)
            assert context.stage_progress == 1.0
            
            # 测试边界值
            progress_callback(1.5)  # 应该被限制为1.0
            assert context.stage_progress == 1.0
            
            progress_callback(-0.1)  # 应该被限制为0.0
            assert context.stage_progress == 0.0
    
    def test_stage_estimated_duration(self):
        """测试Stage时间估算"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_file = temp_path / "input.pcap"
            output_file = temp_path / "output.pcap"
            work_dir = temp_path / "work"
            
            # 创建测试文件（1MB）
            input_file.write_bytes(b'x' * 1024 * 1024)
            work_dir.mkdir()
            
            context = StageContext(input_file, output_file, work_dir)
            stage = MockStage("test_stage")
            
            duration = stage.get_estimated_duration(context)
            
            # 应该基于文件大小估算，但最小值为0.5s
            # 1MB * 0.1s/MB = 0.1s，但max(0.5, 0.1) = 0.5s
            assert duration == pytest.approx(0.5, rel=0.1)


class TestMultiStageExecutor:
    """测试MultiStageExecutor类"""
    
    def test_executor_creation(self):
        """测试执行器创建"""
        with tempfile.TemporaryDirectory() as temp_dir:
            work_dir = Path(temp_dir)
            
            executor = MultiStageExecutor(work_dir=work_dir)
            
            assert executor.work_dir == work_dir
            assert len(executor.stages) == 0
            assert executor._current_context is None
            assert len(executor._execution_results) == 0
    
    def test_stage_registration(self):
        """测试Stage注册"""
        executor = MultiStageExecutor()
        
        stage1 = MockStage("stage1")
        stage2 = MockStage("stage2")
        
        executor.register_stage(stage1)
        executor.register_stage(stage2)
        
        assert len(executor.stages) == 2
        assert executor.stages[0] == stage1
        assert executor.stages[1] == stage2
        
        # 测试清除Stage
        executor.clear_stages()
        assert len(executor.stages) == 0
    
    def test_successful_pipeline_execution(self):
        """测试成功的管道执行"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_file = temp_path / "input.pcap"
            output_file = temp_path / "output.pcap"
            
            # 创建测试文件
            input_file.write_bytes(b'test data')
            
            # 创建执行器和Stage
            events_received = []
            
            def event_callback(event_type, data):
                events_received.append((event_type, data))
            
            executor = MultiStageExecutor(
                work_dir=temp_path / "work",
                event_callback=event_callback
            )
            
            stage1 = MockStage("preprocessing", execution_time=0.05)
            stage2 = MockStage("analysis", execution_time=0.03)
            stage3 = MockStage("rewriting", execution_time=0.02)
            
            executor.register_stage(stage1)
            executor.register_stage(stage2)
            executor.register_stage(stage3)
            
            # 执行管道
            result = executor.execute_pipeline(input_file, output_file)
            
            # 验证结果
            assert result.success
            assert result.state == SimpleStageState.COMPLETED
            assert result.duration > 0
            assert len(result.stage_results) == 3
            
            # 验证所有Stage都被调用
            assert stage1.validate_called
            assert stage1.execute_called
            assert stage1.cleanup_called
            
            assert stage2.validate_called
            assert stage2.execute_called
            assert stage2.cleanup_called
            
            assert stage3.validate_called
            assert stage3.execute_called
            assert stage3.cleanup_called
            
            # 验证事件
            assert len(events_received) >= 6  # START + 3*STEP_START + 3*STEP_END + END
            
            # 检查开始和结束事件
            start_events = [e for e in events_received if e[0] == PipelineEvents.PIPELINE_START]
            end_events = [e for e in events_received if e[0] == PipelineEvents.PIPELINE_END]
            
            assert len(start_events) == 1
            assert len(end_events) == 1
    
    def test_failed_pipeline_execution(self):
        """测试失败的管道执行"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_file = temp_path / "input.pcap"
            output_file = temp_path / "output.pcap"
            
            # 创建测试文件
            input_file.write_bytes(b'test data')
            
            events_received = []
            
            def event_callback(event_type, data):
                events_received.append((event_type, data))
            
            executor = MultiStageExecutor(
                work_dir=temp_path / "work",
                event_callback=event_callback
            )
            
            stage1 = MockStage("preprocessing", should_succeed=True)
            stage2 = MockStage("analysis", should_succeed=False)  # 这个Stage会失败
            stage3 = MockStage("rewriting", should_succeed=True)
            
            executor.register_stage(stage1)
            executor.register_stage(stage2)
            executor.register_stage(stage3)
            
            # 执行管道应该抛出异常
            with pytest.raises(StageExecutionError) as exc_info:
                executor.execute_pipeline(input_file, output_file)
            
            # 验证异常信息
            assert exc_info.value.stage_name == "analysis"
            assert "Mock stage analysis failed" in str(exc_info.value)
            
            # 验证只有前两个Stage被执行
            assert stage1.execute_called
            assert stage2.execute_called
            assert not stage3.execute_called  # 第三个Stage不应该被执行
            
            # 验证错误事件
            error_events = [e for e in events_received if e[0] == PipelineEvents.ERROR]
            assert len(error_events) >= 1
    
    def test_empty_pipeline_execution(self):
        """测试空管道执行"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_file = temp_path / "input.pcap"
            output_file = temp_path / "output.pcap"
            
            input_file.write_bytes(b'test data')
            
            executor = MultiStageExecutor()
            
            # 没有注册任何Stage，应该抛出异常
            with pytest.raises(PipelineExecutionError) as exc_info:
                executor.execute_pipeline(input_file, output_file)
            
            # 验证异常信息
            assert "没有注册任何处理Stage" in str(exc_info.value)
    
    def test_progress_tracking(self):
        """测试进度跟踪"""
        executor = MultiStageExecutor()
        
        stage1 = MockStage("stage1")
        stage2 = MockStage("stage2")
        stage3 = MockStage("stage3")
        
        executor.register_stage(stage1)
        executor.register_stage(stage2)
        executor.register_stage(stage3)
        
        # 初始进度应该为0
        assert executor.get_current_progress() == 0.0
        
        # 模拟一些执行结果
        result1 = StageResult("stage1", True, 1.0)
        executor._execution_results.append(result1)
        
        # 进度应该是1/3
        assert executor.get_current_progress() == pytest.approx(1.0/3.0, rel=0.1)
        
        result2 = StageResult("stage2", True, 1.0)
        executor._execution_results.append(result2)
        
        # 进度应该是2/3
        assert executor.get_current_progress() == pytest.approx(2.0/3.0, rel=0.1)
    
    def test_execution_summary(self):
        """测试执行摘要"""
        executor = MultiStageExecutor()
        
        stage1 = MockStage("stage1")
        stage2 = MockStage("stage2")
        
        executor.register_stage(stage1)
        executor.register_stage(stage2)
        
        # 模拟执行结果
        result1 = StageResult("stage1", True, 1.5)
        result2 = StageResult("stage2", False, 0.8)
        
        executor._execution_results.extend([result1, result2])
        
        summary = executor.get_execution_summary()
        
        assert summary['total_stages'] == 2
        assert summary['completed_stages'] == 2
        assert summary['successful_stages'] == 1
        assert summary['failed_stages'] == 1
        assert summary['total_duration'] == pytest.approx(2.3, rel=0.1)
        assert len(summary['stage_results']) == 2


class TestStageResultCollection:
    """测试StageResultCollection类"""
    
    def test_result_collection_operations(self):
        """测试结果集合操作"""
        from pktmask.core.trim.stages.stage_result import StageResult as DetailedStageResult
        
        collection = StageResultCollection()
        
        # 创建测试结果
        result1 = DetailedStageResult("stage1", StageStatus.COMPLETED)
        result1.mark_completed(success=True)
        
        result2 = DetailedStageResult("stage2", StageStatus.COMPLETED)
        result2.mark_completed(success=False, error="Test error")
        
        result3 = DetailedStageResult("stage3", StageStatus.COMPLETED)
        result3.mark_completed(success=True)
        
        # 添加结果
        collection.add_result(result1)
        collection.add_result(result2)
        collection.add_result(result3)
        
        # 测试统计
        assert collection.get_successful_count() == 2
        assert collection.get_failed_count() == 1
        assert not collection.is_all_successful()
        
        # 测试查询
        assert collection.get_result("stage1") == result1
        assert collection.get_result("nonexistent") is None
        
        # 测试摘要
        summary = collection.get_summary()
        assert summary['total_stages'] == 3
        assert summary['successful_stages'] == 2
        assert summary['failed_stages'] == 1
        assert not summary['all_successful']


if __name__ == '__main__':
    pytest.main([__file__, '-v']) 