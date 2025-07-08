"""
Steps模块基础测试
专注于实际函数调用和覆盖率提升
"""
import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch

from pktmask.stages.deduplication import DeduplicationStage
from pktmask.stages.ip_anonymization import IpAnonymizationStage  
from pktmask.stages.trimming import IntelligentTrimmingStage


class TestStepsBasic:
    """Steps模块基础测试"""
    
    def test_deduplication_step_properties(self):
        """测试去重步骤基本属性"""
        step = DeduplicationStage()
        assert step.name == "Remove Dupes"
        assert hasattr(step, 'suffix')
        assert step.suffix.endswith("Deduped")
    
    def test_ip_anonymization_step_properties(self):
        """测试IP匿名化步骤基本属性"""
        # 创建mock策略和报告器
        mock_strategy = Mock()
        mock_reporter = Mock()
        
        step = IpAnonymizationStage(strategy=mock_strategy, reporter=mock_reporter)
        assert step.name == "Mask IP"
        assert hasattr(step, 'suffix')
        assert step.suffix.endswith("Masked")
    
    def test_trimming_step_properties(self):
        """测试载荷裁切步骤基本属性"""
        step = IntelligentTrimmingStage()
        assert step.name == "Intelligent Trim"
        assert hasattr(step, 'suffix')
        assert step.suffix.endswith("Trimmed")
    
    def test_all_steps_have_required_methods(self):
        """测试所有步骤都有必需的方法"""
        # 为IP匿名化步骤创建mock参数
        mock_strategy = Mock()
        mock_reporter = Mock()
        
        steps = [
            DeduplicationStage(), 
            IpAnonymizationStage(strategy=mock_strategy, reporter=mock_reporter), 
            IntelligentTrimmingStage()
        ]
        
        # 所有步骤都应该有process_file方法
        for step in steps:
            assert hasattr(step, 'process_file')
            assert callable(step.process_file)
        
        # 只有去重步骤有process_directory方法
        dedup_step = steps[0]
        assert hasattr(dedup_step, 'process_directory')
        assert callable(dedup_step.process_directory)
    
    @patch('pktmask.stages.deduplication.select_files')
    def test_deduplication_empty_directory(self, mock_select_files):
        """测试去重处理空目录"""
        mock_select_files.return_value = ([], "无文件")
        
        step = DeduplicationStage()
        callback_calls = []
        
        def mock_callback(event, data):
            callback_calls.append((event, data))
        
        with tempfile.TemporaryDirectory() as temp_dir:
            step.process_directory(temp_dir, progress_callback=mock_callback)
        
        assert len(callback_calls) > 0
        assert any("无文件" in str(call) for call in callback_calls) 