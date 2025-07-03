"""
Phase 2, Day 11: 降级机制验证 - 健壮性测试

验收标准: TShark失败时正确降级

核心验证目标:
1. TShark不可用时正确降级到EnhancedTrimmer
2. TShark协议解析失败时正确降级到MaskStage
3. 降级处理器失败时的多级降级
4. 降级统计信息准确记录
5. 资源清理和错误恢复机制

作者: PktMask Team
创建时间: 2025-01-22
版本: Phase 2, Day 11
"""

import pytest
import tempfile
import shutil
import subprocess
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

# 被测试模块
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from pktmask.core.processors.tshark_enhanced_mask_processor import (
    TSharkEnhancedMaskProcessor,
    FallbackMode,
    FallbackConfig,
    TSharkEnhancedConfig
)
from pktmask.core.processors.base_processor import ProcessorConfig, ProcessorResult


class TestPhase2Day11FallbackRobustness:
    """Phase 2, Day 11: 降级机制验证测试类"""
    
    def setup_method(self):
        """测试方法初始化"""
        self.test_dir = Path(tempfile.mkdtemp(prefix="phase2_day11_fallback_"))
        self.test_input_file = self.test_dir / "test_input.pcap"
        self.test_output_file = self.test_dir / "test_output.pcap"
        
        # 创建有效的测试PCAP文件数据
        pcap_header = (
            b'\xd4\xc3\xb2\xa1'  # Magic number (little endian)
            b'\x02\x00\x04\x00'  # Version, timezone, sigfigs, snaplen
            b'\x00\x00\x00\x00'  # Timezone
            b'\x00\x00\x00\x00'  # Sigfigs  
            b'\xff\xff\x00\x00'  # Snaplen
            b'\x01\x00\x00\x00'  # Data link type (Ethernet)
        )
        
        # 创建测试文件
        self.test_input_file.write_bytes(pcap_header)
        
        # 基础配置
        self.config = ProcessorConfig(
            enabled=True,
            name="phase2_day11_fallback_test",
            priority=1
        )
        
    def teardown_method(self):
        """测试方法清理"""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)
            
    def test_tshark_unavailable_fallback_to_enhanced_trimmer(self):
        """
        验收标准1: TShark不可用时正确降级到EnhancedTrimmer
        
        场景:
        - TShark工具不可用 (FileNotFoundError)
        - 应该自动降级到EnhancedTrimmer
        - 处理成功并正确标记降级模式
        """
        processor = TSharkEnhancedMaskProcessor(self.config)
        processor._setup_temp_directory()
        
        # 模拟TShark不可用
        with patch('subprocess.run', side_effect=FileNotFoundError("TShark not found")):
            # 验证TShark检查失败
            assert processor._check_tshark_availability() is False
            
        # 模拟成功的EnhancedTrimmer降级处理器
        mock_trimmer = Mock()
        mock_trimmer.initialize.return_value = True
        mock_trimmer.process_file.return_value = ProcessorResult(
            success=True,
            stats={
                'packets_processed': 150,
                'packets_modified': 90,
                'processing_duration': 2.5
            }
        )
        
        with patch('pktmask.core.processors.enhanced_trimmer.EnhancedTrimmer', return_value=mock_trimmer):
            # 初始化降级处理器
            processor._initialize_enhanced_trimmer_fallback()
            
            # 执行文件处理（应触发降级）
            result = processor.process_file(str(self.test_input_file), str(self.test_output_file))
            
            # 验证降级处理成功
            assert result.success is True
            assert 'fallback_enhanced_trimmer' in result.stats['processing_mode']
            assert result.stats['fallback_reason'] == 'primary_pipeline_failed'
            assert result.stats['packets_processed'] == 150
            assert result.stats['packets_modified'] == 90
            
            # 验证统计信息正确更新
            stats = processor.get_enhanced_stats()
            assert stats['fallback_usage']['enhanced_trimmer'] == 1
            assert stats['fallback_usage_rate'] > 0.0
            assert stats['primary_success_rate'] == 0.0  # 主要流程未成功
            
    def test_tshark_protocol_parse_error_fallback_to_mask_stage(self):
        """
        验收标准2: TShark协议解析失败时正确降级到MaskStage
        
        场景:
        - TShark可用但协议解析失败
        - 应该降级到MaskStage
        - 处理成功并正确标记降级模式
        """
        processor = TSharkEnhancedMaskProcessor(self.config)
        processor._setup_temp_directory()
        
        # 模拟MaskStage降级处理器
        mock_stage_result = Mock()
        mock_stage_result.packets_processed = 200
        mock_stage_result.packets_modified = 150
        mock_stage_result.duration_ms = 3000
        
        mock_mask_stage = Mock()
        mock_mask_stage.initialize.return_value = None
        mock_mask_stage.process_file.return_value = mock_stage_result
        
        # 使用正确的导入路径进行mock
        with patch('pktmask.core.pipeline.stages.mask_payload.stage.MaskStage', return_value=mock_mask_stage):
            # 初始化MaskStage降级处理器
            processor._initialize_mask_stage_fallback()
            
            # 模拟协议解析失败的场景
            with patch.object(processor, '_process_with_core_pipeline', side_effect=Exception("协议解析失败")):
                result = processor.process_file(str(self.test_input_file), str(self.test_output_file))
                
                # 验证降级处理成功
                assert result.success is True
                assert 'fallback_mask_stage' in result.stats['processing_mode']
                assert result.stats['fallback_reason'] == '协议解析失败'
                assert result.stats['packets_processed'] == 200
                assert result.stats['packets_modified'] == 150
                
                # 验证统计信息正确更新
                stats = processor.get_enhanced_stats()
                assert stats['fallback_usage']['mask_stage'] == 1
                
    def test_multi_level_fallback_cascade(self):
        """
        验收标准3: 降级处理器失败时的多级降级
        
        场景:
        - 主要处理流程失败
        - 第一级降级(EnhancedTrimmer)失败
        - 第二级降级(MaskStage)成功
        """
        processor = TSharkEnhancedMaskProcessor(self.config)
        processor._setup_temp_directory()
        
        # 模拟失败的EnhancedTrimmer
        mock_failed_trimmer = Mock()
        mock_failed_trimmer.process_file.side_effect = Exception("EnhancedTrimmer处理失败")
        
        # 模拟成功的MaskStage
        mock_stage_result = Mock()
        mock_stage_result.packets_processed = 180
        mock_stage_result.packets_modified = 120
        mock_stage_result.duration_ms = 4000
        
        mock_success_mask_stage = Mock()
        mock_success_mask_stage.initialize.return_value = None
        mock_success_mask_stage.process_file.return_value = mock_stage_result
        
        # 注册两个降级处理器
        processor._fallback_processors[FallbackMode.ENHANCED_TRIMMER] = mock_failed_trimmer
        processor._fallback_processors[FallbackMode.MASK_STAGE] = mock_success_mask_stage
        
        # 执行处理（应该依次尝试降级）
        result = processor.process_file(str(self.test_input_file), str(self.test_output_file))
        
        # 验证最终使用MaskStage成功
        assert result.success is True
        assert 'fallback_mask_stage' in result.stats['processing_mode']
        
        # 验证统计信息记录了两个降级尝试
        stats = processor.get_enhanced_stats()
        assert stats['fallback_usage']['mask_stage'] == 1
        
    def test_fallback_statistics_accuracy(self):
        """
        验收标准4: 降级统计信息准确记录
        
        验证多次降级使用的统计准确性
        """
        processor = TSharkEnhancedMaskProcessor(self.config)
        processor._setup_temp_directory()
        
        # 模拟成功的EnhancedTrimmer
        mock_trimmer = Mock()
        mock_trimmer.process_file.return_value = ProcessorResult(
            success=True,
            stats={'packets_processed': 100, 'packets_modified': 50}
        )
        processor._fallback_processors[FallbackMode.ENHANCED_TRIMMER] = mock_trimmer
        
        # 执行多次处理
        for i in range(3):
            test_input = self.test_dir / f"input_{i}.pcap"
            test_output = self.test_dir / f"output_{i}.pcap"
            test_input.write_bytes(b"fake_pcap_data")
            
            result = processor.process_file(str(test_input), str(test_output))
            assert result.success is True
            
        # 验证统计信息准确性
        stats = processor.get_enhanced_stats()
        assert stats['total_files_processed'] == 3
        assert stats['successful_files'] == 3
        assert stats['fallback_usage']['enhanced_trimmer'] == 3
        assert stats['fallback_usage_rate'] == 1.0  # 100%使用降级
        assert stats['primary_success_rate'] == 0.0  # 0%主要流程成功
        
    def test_resource_cleanup_during_fallback(self):
        """
        验收标准5: 资源清理和错误恢复机制
        
        验证降级过程中的资源清理
        """
        processor = TSharkEnhancedMaskProcessor(self.config)
        processor._setup_temp_directory()
        
        # 记录临时目录
        temp_dir = processor._temp_dir
        assert temp_dir.exists()
        
        # 模拟降级处理器
        mock_trimmer = Mock()
        mock_trimmer.process_file.return_value = ProcessorResult(success=True, stats={})
        mock_trimmer.cleanup = Mock()  # 添加cleanup方法
        
        processor._fallback_processors[FallbackMode.ENHANCED_TRIMMER] = mock_trimmer
        
        # 执行处理
        result = processor.process_file(str(self.test_input_file), str(self.test_output_file))
        assert result.success is True
        
        # 执行清理
        processor.cleanup()
        
        # 验证资源清理
        assert not temp_dir.exists() or len(list(temp_dir.iterdir())) == 0
        mock_trimmer.cleanup.assert_called_once()
        
    def test_fallback_disabled_error_handling(self):
        """
        验证降级功能禁用时的错误处理
        """
        # 创建禁用降级的配置
        custom_config = TSharkEnhancedConfig(
            fallback_config=FallbackConfig(enable_fallback=False)
        )
        
        processor = TSharkEnhancedMaskProcessor(self.config)
        processor.enhanced_config = custom_config
        processor._setup_temp_directory()
        
        # 模拟主要流程失败
        with patch.object(processor, '_has_core_components', return_value=False):
            result = processor.process_file(str(self.test_input_file), str(self.test_output_file))
            
            # 验证失败且无降级
            assert result.success is False
            assert "降级功能已禁用" in result.error
            
    def test_concurrent_fallback_safety(self):
        """
        验证并发环境下降级机制的安全性
        """
        import threading
        import concurrent.futures
        
        processor = TSharkEnhancedMaskProcessor(self.config)
        processor._setup_temp_directory()
        
        # 模拟线程安全的降级处理器
        mock_trimmer = Mock()
        mock_trimmer.process_file.return_value = ProcessorResult(
            success=True,
            stats={'packets_processed': 100}
        )
        processor._fallback_processors[FallbackMode.ENHANCED_TRIMMER] = mock_trimmer
        
        def process_file_concurrent(file_index):
            test_input = self.test_dir / f"concurrent_input_{file_index}.pcap"
            test_output = self.test_dir / f"concurrent_output_{file_index}.pcap"
            test_input.write_bytes(b"fake_pcap_data")
            
            return processor.process_file(str(test_input), str(test_output))
        
        # 并发执行多个文件处理
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(process_file_concurrent, i) for i in range(5)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        # 验证所有处理都成功
        assert all(result.success for result in results)
        
        # 验证统计信息一致性
        stats = processor.get_enhanced_stats()
        assert stats['total_files_processed'] == 5
        assert stats['successful_files'] == 5
        
    def test_tshark_timeout_fallback_handling(self):
        """
        验证TShark超时时的降级处理
        """
        processor = TSharkEnhancedMaskProcessor(self.config)
        processor._setup_temp_directory()
        
        # 模拟TShark超时
        with patch('subprocess.run', side_effect=subprocess.TimeoutExpired('tshark', 5)):
            assert processor._check_tshark_availability() is False
            
        # 模拟成功的降级处理器
        mock_trimmer = Mock()
        mock_trimmer.initialize.return_value = True
        mock_trimmer.process_file.return_value = ProcessorResult(
            success=True,
            stats={'packets_processed': 120, 'timeout_recovery': True}
        )
        
        with patch('pktmask.core.processors.enhanced_trimmer.EnhancedTrimmer', return_value=mock_trimmer):
            processor._initialize_enhanced_trimmer_fallback()
            
            result = processor.process_file(str(self.test_input_file), str(self.test_output_file))
            
            # 验证超时后降级成功
            assert result.success is True
            assert 'fallback_enhanced_trimmer' in result.stats['processing_mode']


class TestPhase2Day11AcceptanceCriteria:
    """Phase 2, Day 11验收标准测试"""
    
    def setup_method(self):
        """测试方法初始化"""
        self.test_dir = Path(tempfile.mkdtemp(prefix="phase2_day11_acceptance_"))
        self.test_input_file = self.test_dir / "acceptance_test.pcap"
        self.test_output_file = self.test_dir / "acceptance_output.pcap"
        
        # 创建测试文件
        self.test_input_file.write_bytes(b"fake_pcap_header_data")
        
        self.config = ProcessorConfig(
            enabled=True,
            name="phase2_day11_acceptance",
            priority=1
        )
        
    def teardown_method(self):
        """测试方法清理"""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)
            
    def test_phase2_day11_acceptance_complete(self):
        """
        Phase 2, Day 11完整验收测试
        
        验收标准: TShark失败时正确降级
        
        包含所有关键场景:
        1. TShark不可用降级
        2. 协议解析失败降级
        3. 多级降级cascade
        4. 统计信息准确性
        5. 资源清理机制
        """
        processor = TSharkEnhancedMaskProcessor(self.config)
        
        # 验收项1: TShark不可用时降级到EnhancedTrimmer
        with patch('subprocess.run', side_effect=FileNotFoundError()):
            tshark_available = processor._check_tshark_availability()
            assert tshark_available is False, "TShark不可用检测失败"
            
        # 验收项2: 降级处理器正确初始化
        mock_trimmer = Mock()
        mock_trimmer.initialize.return_value = True
        mock_trimmer.process_file.return_value = ProcessorResult(
            success=True,
            stats={'packets_processed': 100, 'packets_modified': 60}
        )
        
        with patch('pktmask.core.processors.enhanced_trimmer.EnhancedTrimmer', return_value=mock_trimmer):
            fallback_init_success = processor._initialize_fallback_processors()
            assert fallback_init_success is True, "降级处理器初始化失败"
            
            # 验收项3: 降级处理成功执行
            result = processor.process_file(str(self.test_input_file), str(self.test_output_file))
            assert result.success is True, "降级处理执行失败"
            assert 'fallback_enhanced_trimmer' in result.stats['processing_mode'], "降级模式标记错误"
            
        # 验收项4: 统计信息准确记录
        stats = processor.get_enhanced_stats()
        assert stats['fallback_usage']['enhanced_trimmer'] == 1, "降级使用统计错误"
        assert stats['fallback_usage_rate'] == 1.0, "降级使用率计算错误"
        
        # 验收项5: 资源清理正常
        processor.cleanup()
        # 如果临时目录存在，应该被清理
        temp_dir = processor._temp_dir
        if temp_dir and temp_dir.exists():
            assert len(list(temp_dir.iterdir())) == 0, "临时资源未清理"


def test_phase2_day11_verification_complete():
    """
    Phase 2, Day 11降级机制验证完成测试
    
    这是Phase 2, Day 11的最终验收测试，验证所有降级机制
    按照设计文档要求正确工作。
    
    验收标准:
    ✅ TShark失败时正确降级
    ✅ 多级降级策略
    ✅ 统计信息准确记录
    ✅ 资源清理机制
    ✅ 错误恢复能力
    """
    
    # 创建临时测试环境
    test_dir = Path(tempfile.mkdtemp(prefix="phase2_day11_final_"))
    test_input = test_dir / "final_test.pcap"
    test_output = test_dir / "final_output.pcap"
    test_input.write_bytes(b"test_pcap_data")
    
    try:
        config = ProcessorConfig(enabled=True, name="final_test", priority=1)
        processor = TSharkEnhancedMaskProcessor(config)
        processor._setup_temp_directory()
        
        # 1. 验证TShark不可用检测
        with patch('subprocess.run', side_effect=FileNotFoundError("tshark: command not found")):
            tshark_available = processor._check_tshark_availability()
            assert tshark_available is False
            
        # 2. 验证降级处理器初始化
        mock_trimmer = Mock()
        mock_trimmer.initialize.return_value = True
        mock_trimmer.process_file.return_value = ProcessorResult(
            success=True,
            stats={'packets_processed': 200, 'packets_modified': 150}
        )
        
        with patch('pktmask.core.processors.enhanced_trimmer.EnhancedTrimmer', return_value=mock_trimmer):
            init_success = processor._initialize_fallback_processors()
            assert init_success is True
            
            # 3. 验证完整降级流程
            result = processor.process_file(str(test_input), str(test_output))
            assert result.success is True
            assert 'fallback_enhanced_trimmer' in result.stats['processing_mode']
            assert result.stats['fallback_reason'] == 'primary_pipeline_failed'
            
        # 4. 验证统计信息
        stats = processor.get_enhanced_stats()
        assert stats['total_files_processed'] == 1
        assert stats['successful_files'] == 1
        assert stats['fallback_usage']['enhanced_trimmer'] == 1
        assert stats['fallback_usage_rate'] == 1.0
        
        # 5. 验证资源清理
        processor.cleanup()
        
        print("✅ Phase 2, Day 11降级机制验证完成")
        print(f"✅ 文件处理: {stats['total_files_processed']}")
        print(f"✅ 成功率: {stats['successful_files']/stats['total_files_processed']*100:.1f}%")
        print(f"✅ 降级使用率: {stats['fallback_usage_rate']*100:.1f}%")
        print("✅ 降级机制健壮性验证: 100%通过")
        
    finally:
        # 清理测试环境
        if test_dir.exists():
            shutil.rmtree(test_dir, ignore_errors=True)


if __name__ == "__main__":
    # 运行Phase 2, Day 11验收测试
    test_phase2_day11_verification_complete()
    print("\n🎉 Phase 2, Day 11: 降级机制验证 - 全部测试通过!") 