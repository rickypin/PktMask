"""
HTTP策略配置验证测试

验证双策略配置系统的正确性，包括配置验证、策略选择逻辑、A/B测试配置等。

作者: PktMask Team
创建时间: 2025-01-15
版本: 1.0.0
"""

import unittest
from unittest.mock import Mock, patch
import time
import json
from typing import Dict, Any

try:
    from src.pktmask.config.http_strategy_config import (
        HttpStrategyConfiguration, 
        HttpStrategyConfig,
        ScanningStrategyConfig,
        ABTestConfig,
        StrategyMode,
        MultiMessageMode,
        get_default_http_strategy_config,
        create_production_config,
        create_ab_test_config
    )
    CONFIG_AVAILABLE = True
except ImportError:
    CONFIG_AVAILABLE = False


class TestHttpStrategyConfig(unittest.TestCase):
    """HTTP策略配置基础功能测试"""
    
    def setUp(self):
        """测试准备"""
        if not CONFIG_AVAILABLE:
            self.skipTest("HTTP策略配置模块不可用")
    
    def test_default_config_creation(self):
        """测试默认配置创建"""
        config = get_default_http_strategy_config()
        
        # 验证基础配置
        self.assertIsInstance(config, HttpStrategyConfiguration)
        self.assertEqual(config.strategy.primary_strategy, StrategyMode.LEGACY)
        self.assertFalse(config.strategy.enable_ab_testing)
        self.assertEqual(config.strategy.ab_test_ratio, 0.1)
        
        # 验证扫描策略配置
        self.assertEqual(config.scanning.max_scan_window, 8192)
        self.assertEqual(config.scanning.multi_message_mode, MultiMessageMode.CONSERVATIVE)
        
    def test_production_config_creation(self):
        """测试生产环境配置创建"""
        config = create_production_config()
        
        # 生产环境应该使用Legacy策略，关闭调试功能
        self.assertEqual(config.strategy.primary_strategy, StrategyMode.LEGACY)
        self.assertTrue(config.strategy.auto_fallback_enabled)
        self.assertFalse(config.scanning.enable_scan_logging)
        self.assertTrue(config.scanning.fallback_on_error)
        
    def test_ab_test_config_creation(self):
        """测试A/B测试配置创建"""
        test_ratio = 0.05
        config = create_ab_test_config(test_ratio)
        
        self.assertEqual(config.strategy.primary_strategy, StrategyMode.AB_TEST)
        self.assertTrue(config.strategy.enable_ab_testing)
        self.assertEqual(config.strategy.ab_test_ratio, test_ratio)
        
    def test_config_validation_success(self):
        """测试配置验证成功情况"""
        config = get_default_http_strategy_config()
        
        is_valid, errors = config.validate()
        
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
        
    def test_config_validation_failures(self):
        """测试配置验证失败情况"""
        config = get_default_http_strategy_config()
        
        # 设置无效的A/B测试比例
        config.strategy.enable_ab_testing = True
        config.strategy.ab_test_ratio = 1.5  # 超出0-1范围
        
        # 设置无效的扫描窗口
        config.scanning.max_scan_window = -100
        
        # 设置无效的保留比例
        config.scanning.conservative_preserve_ratio = 2.0
        
        is_valid, errors = config.validate()
        
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("ab_test_ratio" in error for error in errors))
        self.assertTrue(any("max_scan_window" in error for error in errors))
        self.assertTrue(any("conservative_preserve_ratio" in error for error in errors))


class TestStrategySelection(unittest.TestCase):
    """策略选择逻辑测试"""
    
    def setUp(self):
        """测试准备"""
        if not CONFIG_AVAILABLE:
            self.skipTest("HTTP策略配置模块不可用")
            
        self.config = get_default_http_strategy_config()
        
    def test_legacy_strategy_selection(self):
        """测试Legacy策略选择"""
        self.config.strategy.primary_strategy = StrategyMode.LEGACY
        
        self.assertFalse(self.config.should_use_scanning_strategy())
        self.assertEqual(self.config.get_strategy_name(), "http_trim")
        
    def test_scanning_strategy_selection(self):
        """测试Scanning策略选择"""
        self.config.strategy.primary_strategy = StrategyMode.SCANNING
        
        self.assertTrue(self.config.should_use_scanning_strategy())
        self.assertEqual(self.config.get_strategy_name(), "http_scanning")
        
    def test_ab_test_strategy_selection(self):
        """测试A/B测试策略选择"""
        self.config.strategy.primary_strategy = StrategyMode.AB_TEST
        self.config.strategy.enable_ab_testing = True
        self.config.strategy.ab_test_ratio = 0.5  # 50%几率
        
        # 测试多次选择，结果应该基于文件路径一致
        test_file = "test_file.pcap"
        result1 = self.config.should_use_scanning_strategy(test_file)
        result2 = self.config.should_use_scanning_strategy(test_file)
        
        # 相同文件路径应该返回相同结果
        self.assertEqual(result1, result2)
        
        # 不同文件路径可能返回不同结果
        different_results = set()
        for i in range(100):
            result = self.config.should_use_scanning_strategy(f"file_{i}.pcap")
            different_results.add(result)
            if len(different_results) == 2:  # 已经有两种结果了
                break
                
        # 应该能看到两种不同的结果（True和False）
        self.assertEqual(len(different_results), 2)
        
    def test_auto_strategy_selection(self):
        """测试自动策略选择"""
        self.config.strategy.primary_strategy = StrategyMode.AUTO
        
        # 当前自动选择逻辑默认返回Legacy
        self.assertFalse(self.config.should_use_scanning_strategy())
        
    def test_fallback_strategy_selection(self):
        """测试回退策略选择"""
        # 设置一个不支持的策略模式
        self.config.strategy.primary_strategy = "invalid_mode"
        
        # 应该回退到Legacy策略
        self.assertFalse(self.config.should_use_scanning_strategy())


class TestABTestConfig(unittest.TestCase):
    """A/B测试配置测试"""
    
    def setUp(self):
        """测试准备"""
        if not CONFIG_AVAILABLE:
            self.skipTest("HTTP策略配置模块不可用")
            
    def test_ab_test_config_defaults(self):
        """测试A/B测试配置默认值"""
        config = ABTestConfig()
        
        self.assertEqual(config.control_ratio, 0.9)
        self.assertEqual(config.treatment_ratio, 0.1)
        self.assertEqual(config.sampling_strategy, "hash_based")
        self.assertEqual(config.hash_seed, 42)
        self.assertTrue(config.metrics_collection_enabled)
        self.assertEqual(config.min_sample_size, 100)
        self.assertEqual(config.confidence_level, 0.95)
        
    def test_ab_test_config_validation(self):
        """测试A/B测试配置参数验证"""
        config = ABTestConfig()
        
        # 测试比例设置
        config.control_ratio = 0.8
        config.treatment_ratio = 0.2
        
        # 比例总和应该为1.0
        total_ratio = config.control_ratio + config.treatment_ratio
        self.assertAlmostEqual(total_ratio, 1.0, places=2)
        
    def test_ab_test_timing(self):
        """测试A/B测试时间管理"""
        config = ABTestConfig()
        
        current_time = time.time()
        config.start_time = current_time
        config.end_time = current_time + 3600  # 1小时后
        
        self.assertIsNotNone(config.start_time)
        self.assertIsNotNone(config.end_time)
        self.assertGreater(config.end_time, config.start_time)


class TestScanningStrategyConfig(unittest.TestCase):
    """扫描式策略配置测试"""
    
    def setUp(self):
        """测试准备"""
        if not CONFIG_AVAILABLE:
            self.skipTest("HTTP策略配置模块不可用")
            
    def test_scanning_config_defaults(self):
        """测试扫描策略配置默认值"""
        config = ScanningStrategyConfig()
        
        self.assertEqual(config.max_scan_window, 8192)
        self.assertEqual(config.chunked_sample_size, 1024)
        self.assertEqual(config.max_chunks_to_analyze, 10)
        self.assertEqual(config.multi_message_mode, MultiMessageMode.CONSERVATIVE)
        self.assertEqual(config.max_messages_per_payload, 5)
        self.assertTrue(config.fallback_on_error)
        self.assertTrue(config.enable_caching)
        
    def test_scanning_config_performance_settings(self):
        """测试扫描策略性能配置"""
        config = ScanningStrategyConfig()
        
        # 验证性能相关配置
        self.assertEqual(config.cache_ttl_seconds, 300)  # 5分钟
        self.assertTrue(config.performance_metrics_enabled)
        self.assertEqual(config.large_file_threshold, 1024 * 1024)  # 1MB
        
    def test_scanning_config_conservative_settings(self):
        """测试扫描策略保守配置"""
        config = ScanningStrategyConfig()
        
        # 验证保守策略配置
        self.assertEqual(config.conservative_preserve_ratio, 0.8)
        self.assertEqual(config.min_preserve_bytes, 64)
        self.assertEqual(config.max_preserve_bytes, 8192)
        self.assertTrue(config.detailed_warnings)


class TestConfigurationIntegration(unittest.TestCase):
    """配置系统集成测试"""
    
    def setUp(self):
        """测试准备"""
        if not CONFIG_AVAILABLE:
            self.skipTest("HTTP策略配置模块不可用")
            
    def test_full_configuration_workflow(self):
        """测试完整配置工作流程"""
        # 1. 创建默认配置
        config = get_default_http_strategy_config()
        
        # 2. 验证配置
        is_valid, errors = config.validate()
        self.assertTrue(is_valid, f"配置验证失败: {errors}")
        
        # 3. 配置A/B测试
        config.strategy.primary_strategy = StrategyMode.AB_TEST
        config.strategy.enable_ab_testing = True
        config.strategy.ab_test_ratio = 0.1
        
        # 4. 再次验证配置
        is_valid, errors = config.validate()
        self.assertTrue(is_valid, f"A/B测试配置验证失败: {errors}")
        
        # 5. 测试策略选择
        strategy_name = config.get_strategy_name("test_file.pcap")
        self.assertIn(strategy_name, ["http_trim", "http_scanning"])
        
    def test_config_serialization(self):
        """测试配置序列化"""
        config = get_default_http_strategy_config()
        
        # 配置应该能够序列化为JSON（通过dataclass）
        try:
            config_dict = {
                'strategy_mode': config.strategy.primary_strategy.value,
                'ab_test_enabled': config.strategy.enable_ab_testing,
                'scan_window': config.scanning.max_scan_window
            }
            json.dumps(config_dict)  # 验证能够序列化
        except (TypeError, ValueError) as e:
            self.fail(f"配置序列化失败: {e}")
            
    def test_config_backward_compatibility(self):
        """测试配置向后兼容性"""
        # 验证Legacy配置保持不变
        config = get_default_http_strategy_config()
        
        # Legacy配置应该保持现有结构
        self.assertTrue(config.legacy.preserve_existing_config)
        
        # 默认情况下应该使用Legacy策略
        self.assertEqual(config.strategy.primary_strategy, StrategyMode.LEGACY)
        self.assertFalse(config.should_use_scanning_strategy())


class TestConfigErrorHandling(unittest.TestCase):
    """配置错误处理测试"""
    
    def setUp(self):
        """测试准备"""
        if not CONFIG_AVAILABLE:
            self.skipTest("HTTP策略配置模块不可用")
            
    def test_invalid_strategy_mode_handling(self):
        """测试无效策略模式处理"""
        config = get_default_http_strategy_config()
        
        # 测试处理无效的策略模式
        with patch.object(config.strategy, 'primary_strategy', 'invalid_mode'):
            # 应该回退到默认行为（Legacy策略）
            result = config.should_use_scanning_strategy()
            self.assertFalse(result)
            
    def test_missing_file_path_handling(self):
        """测试缺失文件路径的处理"""
        config = get_default_http_strategy_config()
        config.strategy.primary_strategy = StrategyMode.AB_TEST
        config.strategy.enable_ab_testing = True
        
        # 没有文件路径时应该能正常工作
        result1 = config.should_use_scanning_strategy(None)
        result2 = config.should_use_scanning_strategy(None)
        
        # 结果应该是布尔值
        self.assertIsInstance(result1, bool)
        self.assertIsInstance(result2, bool)
        
    def test_extreme_config_values(self):
        """测试极端配置值处理"""
        config = get_default_http_strategy_config()
        
        # 测试极端的扫描窗口大小
        config.scanning.max_scan_window = 0
        is_valid, errors = config.validate()
        self.assertFalse(is_valid)
        self.assertTrue(any("max_scan_window" in error for error in errors))
        
        # 重置配置以测试下一个错误
        config = get_default_http_strategy_config()
        
        # 测试极端的A/B测试比例 - 需要先启用A/B测试
        config.strategy.enable_ab_testing = True
        config.strategy.ab_test_ratio = -0.1
        is_valid, errors = config.validate()
        self.assertFalse(is_valid)
        self.assertTrue(any("ab_test_ratio" in error for error in errors))


if __name__ == '__main__':
    unittest.main() 