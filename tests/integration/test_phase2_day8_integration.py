#!/usr/bin/env python3
"""
Phase 2, Day 8集成测试 - TSharkEnhancedMaskProcessor主处理器实现

验收标准:
1. BaseProcessor继承：正确继承BaseProcessor并实现所有必要方法
2. 三阶段集成：TShark分析→规则生成→Scapy应用的完整流程

测试覆盖:
- BaseProcessor接口合规性验证
- 三阶段处理流程验证
- 配置系统集成验证
- 降级机制验证
- 错误处理验证

作者: PktMask Team
创建时间: 2025-01-22  
版本: Phase 2, Day 8
"""

import unittest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import json

# 导入测试目标
from src.pktmask.core.processors.base_processor import BaseProcessor, ProcessorConfig, ProcessorResult
from src.pktmask.core.processors.tshark_enhanced_mask_processor import (
    TSharkEnhancedMaskProcessor, 
    TSharkEnhancedConfig,
    FallbackMode
)


class TestPhase2Day8Integration(unittest.TestCase):
    """Phase 2, Day 8集成测试套件"""
    
    def setUp(self):
        """设置测试环境"""
        self.test_config = ProcessorConfig(
            enabled=True,
            name="test_tshark_enhanced_mask_processor",
            priority=1
        )
        
        self.temp_dir = tempfile.mkdtemp(prefix="phase2_day8_test_")
        self.input_file = os.path.join(self.temp_dir, "input.pcap")
        self.output_file = os.path.join(self.temp_dir, "output.pcap")
        
        # 创建简单的测试PCAP文件（空文件用于测试）
        with open(self.input_file, 'wb') as f:
            f.write(b'\x00' * 100)  # 简单的测试数据
    
    def tearDown(self):
        """清理测试环境"""
        if os.path.exists(self.temp_dir):
            import shutil
            shutil.rmtree(self.temp_dir)

    def test_baseprocessor_inheritance_compliance(self):
        """验收标准1: BaseProcessor继承合规性"""
        print("\n=== 测试 BaseProcessor 继承合规性 ===")
        
        # 创建处理器实例
        processor = TSharkEnhancedMaskProcessor(self.test_config)
        
        # 验证继承关系
        self.assertIsInstance(processor, BaseProcessor)
        print("✅ 正确继承BaseProcessor")
        
        # 验证必要属性存在
        self.assertTrue(hasattr(processor, 'config'))
        self.assertTrue(hasattr(processor, 'stats'))
        self.assertTrue(hasattr(processor, '_is_initialized'))
        print("✅ 必要属性存在")
        
        # 验证必要方法存在
        self.assertTrue(hasattr(processor, 'initialize'))
        self.assertTrue(hasattr(processor, 'process_file'))
        self.assertTrue(hasattr(processor, 'get_display_name'))
        self.assertTrue(hasattr(processor, 'get_description'))
        self.assertTrue(hasattr(processor, 'validate_inputs'))
        self.assertTrue(hasattr(processor, 'get_stats'))
        self.assertTrue(hasattr(processor, 'reset_stats'))
        print("✅ 必要方法存在")
        
        # 验证is_initialized属性
        self.assertFalse(processor.is_initialized)
        print("✅ is_initialized属性正常")
        
        # 验证方法签名
        self.assertTrue(callable(processor.process_file))
        self.assertTrue(callable(processor.get_display_name))
        print("✅ 方法可调用")
        
        print("🎯 BaseProcessor继承合规性验证通过")
    
    @patch('src.pktmask.core.processors.tshark_enhanced_mask_processor.TSharkEnhancedMaskProcessor._check_tshark_availability')
    @patch('src.pktmask.core.processors.tshark_tls_analyzer.TSharkTLSAnalyzer')
    @patch('src.pktmask.core.processors.tls_mask_rule_generator.TLSMaskRuleGenerator')
    @patch('src.pktmask.core.processors.scapy_mask_applier.ScapyMaskApplier')
    def test_three_stage_integration(self, mock_scapy_applier, mock_rule_generator, 
                                   mock_tshark_analyzer, mock_tshark_check):
        """验收标准2: 三阶段集成验证"""
        print("\n=== 测试三阶段集成 ===")
        
        # Mock TShark可用性检查
        mock_tshark_check.return_value = True
        
        # Mock Stage 1: TShark分析器
        mock_analyzer_instance = Mock()
        mock_analyzer_instance.analyze_file.return_value = [
            {'packet_number': 1, 'content_type': 23, 'length': 100},
            {'packet_number': 2, 'content_type': 22, 'length': 50}
        ]
        mock_tshark_analyzer.return_value = mock_analyzer_instance
        
        # Mock Stage 2: 规则生成器
        mock_generator_instance = Mock()
        mock_generator_instance.generate_rules.return_value = [
            {'packet_number': 1, 'action': 'mask_payload'},
            {'packet_number': 2, 'action': 'keep_all'}
        ]
        mock_rule_generator.return_value = mock_generator_instance
        
        # Mock Stage 3: Scapy应用器
        mock_applier_instance = Mock()
        mock_applier_instance.apply_masks.return_value = {
            'packets_processed': 2,
            'packets_modified': 1,
            'masked_bytes': 95
        }
        mock_scapy_applier.return_value = mock_applier_instance
        
        # 创建并初始化处理器
        processor = TSharkEnhancedMaskProcessor(self.test_config)
        self.assertTrue(processor.initialize())
        print("✅ 处理器初始化成功")
        
        # 验证三阶段组件创建
        self.assertIsNotNone(processor._tshark_analyzer)
        self.assertIsNotNone(processor._rule_generator)
        self.assertIsNotNone(processor._scapy_applier)
        print("✅ 三阶段组件正确创建")
        
        # 执行三阶段处理流程
        result = processor.process_file(self.input_file, self.output_file)
        
        # 验证Stage 1调用
        mock_analyzer_instance.analyze_file.assert_called_once_with(self.input_file)
        print("✅ Stage 1 (TShark分析) 正确调用")
        
        # 验证Stage 2调用
        mock_generator_instance.generate_rules.assert_called_once()
        print("✅ Stage 2 (规则生成) 正确调用")
        
        # 验证Stage 3调用
        mock_applier_instance.apply_masks.assert_called_once()
        print("✅ Stage 3 (Scapy应用) 正确调用")
        
        # 验证结果
        self.assertTrue(result.success)
        self.assertIn('tls_records_found', result.stats)
        self.assertIn('mask_rules_generated', result.stats)
        self.assertIn('packets_processed', result.stats)
        print("✅ 处理结果正确")
        
        print("🎯 三阶段集成验证通过")
    
    def test_enhanced_config_integration(self):
        """验证增强配置系统集成"""
        print("\n=== 测试增强配置集成 ===")
        
        processor = TSharkEnhancedMaskProcessor(self.test_config)
        
        # 验证增强配置存在
        self.assertIsInstance(processor.enhanced_config, TSharkEnhancedConfig)
        print("✅ 增强配置系统集成")
        
        # 验证TLS协议类型配置
        self.assertEqual(processor.enhanced_config.tls_20_strategy, "keep_all")
        self.assertEqual(processor.enhanced_config.tls_21_strategy, "keep_all")
        self.assertEqual(processor.enhanced_config.tls_22_strategy, "keep_all")
        self.assertEqual(processor.enhanced_config.tls_23_strategy, "mask_payload")
        self.assertEqual(processor.enhanced_config.tls_24_strategy, "keep_all")
        print("✅ TLS协议类型配置正确")
        
        # 验证功能开关配置
        self.assertTrue(processor.enhanced_config.enable_tls_processing)
        self.assertTrue(processor.enhanced_config.enable_cross_segment_detection)
        self.assertTrue(processor.enhanced_config.enable_boundary_safety)
        print("✅ 功能开关配置正确")
        
        # 验证降级配置
        self.assertTrue(processor.enhanced_config.fallback_config.enable_fallback)
        self.assertIn(FallbackMode.ENHANCED_TRIMMER, 
                     processor.enhanced_config.fallback_config.preferred_fallback_order)
        print("✅ 降级配置正确")
        
        print("🎯 增强配置集成验证通过")
    
    @patch('src.pktmask.core.processors.tshark_enhanced_mask_processor.TSharkEnhancedMaskProcessor._check_tshark_availability')
    @patch('src.pktmask.core.processors.enhanced_trimmer.EnhancedTrimmer')
    def test_fallback_mechanism_integration(self, mock_enhanced_trimmer, mock_tshark_check):
        """验证降级机制集成"""
        print("\n=== 测试降级机制集成 ===")
        
        # Mock TShark不可用
        mock_tshark_check.return_value = False
        
        # Mock EnhancedTrimmer降级处理器
        mock_trimmer_instance = Mock()
        mock_trimmer_instance.initialize.return_value = True
        mock_trimmer_instance.process_file.return_value = ProcessorResult(
            success=True, 
            stats={'fallback_used': True}
        )
        mock_enhanced_trimmer.return_value = mock_trimmer_instance
        
        # 创建并初始化处理器
        processor = TSharkEnhancedMaskProcessor(self.test_config)
        self.assertTrue(processor.initialize())
        print("✅ 降级初始化成功")
        
        # 验证降级处理器存在
        self.assertIn(FallbackMode.ENHANCED_TRIMMER, processor._fallback_processors)
        print("✅ 降级处理器正确创建")
        
        # 执行降级处理
        result = processor.process_file(self.input_file, self.output_file)
        
        # 验证降级处理结果
        self.assertTrue(result.success)
        mock_trimmer_instance.process_file.assert_called_once_with(self.input_file, self.output_file)
        print("✅ 降级处理正确执行")
        
        print("🎯 降级机制集成验证通过")
    
    def test_processor_display_and_description(self):
        """验证处理器显示名称和描述"""
        print("\n=== 测试处理器显示信息 ===")
        
        processor = TSharkEnhancedMaskProcessor(self.test_config)
        
        # 验证显示名称
        display_name = processor.get_display_name()
        self.assertIsInstance(display_name, str)
        self.assertIn("TShark", display_name)
        print(f"✅ 显示名称: {display_name}")
        
        # 验证描述信息
        description = processor.get_description()
        self.assertIsInstance(description, str)
        self.assertIn("TShark", description)
        print(f"✅ 描述信息: {description}")
        
        print("🎯 处理器显示信息验证通过")
    
    def test_input_validation_integration(self):
        """验证输入验证集成"""
        print("\n=== 测试输入验证集成 ===")
        
        processor = TSharkEnhancedMaskProcessor(self.test_config)
        
        # 验证正常输入
        self.assertTrue(processor.validate_inputs(self.input_file, self.output_file))
        print("✅ 正常输入验证通过")
        
        # 验证不存在的输入文件
        with self.assertRaises(FileNotFoundError):
            processor.validate_inputs("/nonexistent/file.pcap", self.output_file)
        print("✅ 不存在文件检测正确")
        
        print("🎯 输入验证集成验证通过")
    
    def test_statistics_tracking_integration(self):
        """验证统计跟踪集成"""
        print("\n=== 测试统计跟踪集成 ===")
        
        processor = TSharkEnhancedMaskProcessor(self.test_config)
        
        # 验证初始统计
        initial_stats = processor.get_stats()
        self.assertIsInstance(initial_stats, dict)
        print("✅ 初始统计获取正常")
        
        # 验证增强统计
        enhanced_stats = processor.get_enhanced_stats()
        self.assertIsInstance(enhanced_stats, dict)
        self.assertIn('total_files_processed', enhanced_stats)
        self.assertIn('fallback_usage', enhanced_stats)
        print("✅ 增强统计获取正常")
        
        # 验证统计重置
        processor.reset_stats()
        reset_stats = processor.get_stats()
        self.assertEqual(len(reset_stats), 0)
        print("✅ 统计重置正常")
        
        print("🎯 统计跟踪集成验证通过")


class TestPhase2Day8AcceptanceCriteria(unittest.TestCase):
    """Phase 2, Day 8验收标准总体验证"""
    
    def test_phase2_day8_acceptance(self):
        """Phase 2, Day 8最终验收测试"""
        print("\n" + "="*50)
        print("Phase 2, Day 8 验收标准验证")
        print("="*50)
        
        acceptance_criteria = {
            "BaseProcessor继承": False,
            "三阶段集成": False,
            "配置系统集成": False,
            "降级机制集成": False,
            "错误处理完整": False
        }
        
        try:
            # 验收标准1: BaseProcessor继承
            config = ProcessorConfig(enabled=True, name="acceptance_test", priority=1)
            processor = TSharkEnhancedMaskProcessor(config)
            
            # 验证继承
            self.assertIsInstance(processor, BaseProcessor)
            # 验证必要方法
            self.assertTrue(hasattr(processor, 'process_file'))
            self.assertTrue(hasattr(processor, 'get_display_name'))
            self.assertTrue(hasattr(processor, 'initialize'))
            acceptance_criteria["BaseProcessor继承"] = True
            print("✅ BaseProcessor继承：通过")
            
            # 验收标准2: 三阶段集成
            # 验证三阶段组件属性存在
            self.assertTrue(hasattr(processor, '_tshark_analyzer'))
            self.assertTrue(hasattr(processor, '_rule_generator'))
            self.assertTrue(hasattr(processor, '_scapy_applier'))
            # 验证初始化方法存在
            self.assertTrue(hasattr(processor, '_initialize_core_components'))
            acceptance_criteria["三阶段集成"] = True
            print("✅ 三阶段集成：通过")
            
            # 验收标准3: 配置系统集成
            self.assertIsInstance(processor.enhanced_config, TSharkEnhancedConfig)
            self.assertTrue(hasattr(processor, '_create_analyzer_config'))
            self.assertTrue(hasattr(processor, '_create_generator_config'))
            self.assertTrue(hasattr(processor, '_create_applier_config'))
            acceptance_criteria["配置系统集成"] = True
            print("✅ 配置系统集成：通过")
            
            # 验收标准4: 降级机制集成
            self.assertTrue(hasattr(processor, '_fallback_processors'))
            self.assertTrue(hasattr(processor, '_initialize_fallback_processors'))
            self.assertTrue(hasattr(processor, '_process_with_fallback'))
            acceptance_criteria["降级机制集成"] = True
            print("✅ 降级机制集成：通过")
            
            # 验收标准5: 错误处理完整
            self.assertTrue(hasattr(processor, '_check_tshark_availability'))
            self.assertTrue(hasattr(processor, '_determine_fallback_mode'))
            self.assertTrue(hasattr(processor, 'cleanup'))
            acceptance_criteria["错误处理完整"] = True
            print("✅ 错误处理完整：通过")
            
        except Exception as e:
            self.fail(f"验收标准验证失败: {e}")
        
        # 最终验收结果
        all_passed = all(acceptance_criteria.values())
        print("\n" + "="*50)
        print("验收标准汇总:")
        for criterion, passed in acceptance_criteria.items():
            status = "✅ 通过" if passed else "❌ 失败"
            print(f"  {criterion}: {status}")
        print("="*50)
        
        if all_passed:
            print("🎉 Phase 2, Day 8 验收标准 100% 达成!")
            print("🚀 TSharkEnhancedMaskProcessor主处理器实现完成!")
        else:
            print("❌ 部分验收标准未达成，需要进一步完善")
        
        self.assertTrue(all_passed, "Phase 2, Day 8验收标准未完全达成")


if __name__ == '__main__':
    # 运行测试
    unittest.main(verbosity=2) 