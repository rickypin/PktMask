"""
双策略集成测试

简化版测试，专注验证配置系统和策略工厂的核心集成功能。

作者: PktMask Team
创建时间: 2025-01-15
版本: 1.0.0
"""

import unittest
from unittest.mock import Mock, patch
import time

try:
    from src.pktmask.config.http_strategy_config import (
        HttpStrategyConfiguration,
        StrategyMode,
        get_default_http_strategy_config,
        create_production_config,
        create_ab_test_config
    )
    from src.pktmask.core.trim.strategies.factory import (
        get_enhanced_strategy_factory,
        HTTP_STRATEGY_CONFIG_AVAILABLE
    )
    INTEGRATION_AVAILABLE = True
except ImportError:
    INTEGRATION_AVAILABLE = False


class TestDualStrategyConfigIntegration(unittest.TestCase):
    """双策略配置集成测试"""
    
    def setUp(self):
        """测试准备"""
        if not INTEGRATION_AVAILABLE:
            self.skipTest("双策略集成模块不可用")
            
    def test_default_configuration_workflow(self):
        """测试默认配置工作流程"""
        # 1. 创建默认配置
        config = get_default_http_strategy_config()
        
        # 2. 验证默认值
        self.assertEqual(config.strategy.primary_strategy, StrategyMode.LEGACY)
        self.assertFalse(config.strategy.enable_ab_testing)
        self.assertEqual(config.scanning.max_scan_window, 8192)
        
        # 3. 验证配置有效性
        is_valid, errors = config.validate()
        self.assertTrue(is_valid, f"默认配置验证失败: {errors}")
        
        # 4. 验证策略选择
        self.assertFalse(config.should_use_scanning_strategy())
        self.assertEqual(config.get_strategy_name(), "http_trim")
        
    def test_production_configuration_workflow(self):
        """测试生产环境配置工作流程"""
        # 1. 创建生产配置
        config = create_production_config()
        
        # 2. 验证生产环境设置
        self.assertEqual(config.strategy.primary_strategy, StrategyMode.LEGACY)
        self.assertTrue(config.strategy.auto_fallback_enabled)
        self.assertFalse(config.scanning.enable_scan_logging)
        self.assertTrue(config.monitoring.health_check_enabled)
        
        # 3. 验证配置有效性
        is_valid, errors = config.validate()
        self.assertTrue(is_valid, f"生产配置验证失败: {errors}")
        
    def test_ab_test_configuration_workflow(self):
        """测试A/B测试配置工作流程"""
        # 1. 创建A/B测试配置
        test_ratio = 0.05
        config = create_ab_test_config(test_ratio)
        
        # 2. 验证A/B测试设置
        self.assertEqual(config.strategy.primary_strategy, StrategyMode.AB_TEST)
        self.assertTrue(config.strategy.enable_ab_testing)
        self.assertEqual(config.strategy.ab_test_ratio, test_ratio)
        
        # 3. 验证配置有效性
        is_valid, errors = config.validate()
        self.assertTrue(is_valid, f"A/B测试配置验证失败: {errors}")
        
        # 4. 验证策略选择的一致性
        test_file = "test.pcap"
        result1 = config.should_use_scanning_strategy(test_file)
        result2 = config.should_use_scanning_strategy(test_file)
        self.assertEqual(result1, result2, "相同文件应返回相同策略选择")
        
    def test_strategy_mode_switching(self):
        """测试策略模式切换功能"""
        config = get_default_http_strategy_config()
        
        # 测试Legacy模式
        config.strategy.primary_strategy = StrategyMode.LEGACY
        self.assertFalse(config.should_use_scanning_strategy())
        self.assertEqual(config.get_strategy_name(), "http_trim")
        
        # 测试Scanning模式
        config.strategy.primary_strategy = StrategyMode.SCANNING
        self.assertTrue(config.should_use_scanning_strategy())
        self.assertEqual(config.get_strategy_name(), "http_scanning")
        
        # 测试AUTO模式
        config.strategy.primary_strategy = StrategyMode.AUTO
        self.assertFalse(config.should_use_scanning_strategy())  # 当前自动选择逻辑默认Legacy
        
    def test_configuration_validation_comprehensive(self):
        """测试配置验证的全面性"""
        config = get_default_http_strategy_config()
        
        # 正常配置应该通过验证
        is_valid, errors = config.validate()
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
        
        # 修改为无效配置
        config.strategy.enable_ab_testing = True
        config.strategy.ab_test_ratio = 1.5  # 超出范围
        config.scanning.max_scan_window = -100  # 负数
        config.scanning.conservative_preserve_ratio = 2.0  # 超出范围
        
        # 应该检测到多个错误
        is_valid, errors = config.validate()
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)
        
        # 验证具体错误消息
        error_text = " ".join(errors)
        self.assertIn("ab_test_ratio", error_text)
        self.assertIn("max_scan_window", error_text)
        self.assertIn("conservative_preserve_ratio", error_text)


class TestEnhancedStrategyFactoryIntegration(unittest.TestCase):
    """增强策略工厂集成测试"""
    
    def setUp(self):
        """测试准备"""
        if not INTEGRATION_AVAILABLE:
            self.skipTest("双策略集成模块不可用")
            
    def test_factory_creation_with_config(self):
        """测试使用配置创建增强策略工厂"""
        # 使用默认配置
        factory1 = get_enhanced_strategy_factory()
        self.assertIsNotNone(factory1)
        self.assertIsNotNone(factory1.http_config)
        
        # 使用自定义配置
        custom_config = create_ab_test_config(0.15)
        factory2 = get_enhanced_strategy_factory(custom_config)
        self.assertIsNotNone(factory2)
        self.assertEqual(factory2.http_config.strategy.ab_test_ratio, 0.15)
        
    def test_config_availability_detection(self):
        """测试配置可用性检测"""
        # HTTP_STRATEGY_CONFIG_AVAILABLE应该为True
        self.assertTrue(HTTP_STRATEGY_CONFIG_AVAILABLE)
        
    def test_factory_config_update(self):
        """测试工厂配置更新功能"""
        factory = get_enhanced_strategy_factory()
        
        # 原始配置
        original_ratio = factory.http_config.strategy.ab_test_ratio
        
        # 更新配置
        new_config = create_ab_test_config(0.2)
        factory.update_config(new_config)
        
        # 验证更新
        self.assertEqual(factory.http_config.strategy.ab_test_ratio, 0.2)
        self.assertNotEqual(factory.http_config.strategy.ab_test_ratio, original_ratio)


class TestConfigurationPersistenceAndSerialization(unittest.TestCase):
    """配置持久化和序列化测试"""
    
    def setUp(self):
        """测试准备"""
        if not INTEGRATION_AVAILABLE:
            self.skipTest("双策略集成模块不可用")
            
    def test_configuration_timing_metadata(self):
        """测试配置时间戳元数据"""
        config = get_default_http_strategy_config()
        
        # 验证创建时间
        self.assertIsNotNone(config.created_at)
        self.assertIsNotNone(config.updated_at)
        self.assertGreater(config.created_at, 0)
        self.assertGreater(config.updated_at, 0)
        
        # 创建时间应该等于更新时间
        self.assertEqual(config.created_at, config.updated_at)
        
    def test_configuration_version_info(self):
        """测试配置版本信息"""
        config = get_default_http_strategy_config()
        
        self.assertEqual(config.config_version, "1.0.0")
        self.assertIsInstance(config.config_version, str)
        
    def test_basic_serialization_compatibility(self):
        """测试基础序列化兼容性"""
        config = get_default_http_strategy_config()
        
        # 基础字段应该能够提取为简单字典
        basic_data = {
            'strategy_mode': config.strategy.primary_strategy.value,
            'ab_test_enabled': config.strategy.enable_ab_testing,
            'scan_window': config.scanning.max_scan_window,
            'config_version': config.config_version
        }
        
        # 验证基础数据类型
        self.assertIsInstance(basic_data['strategy_mode'], str)
        self.assertIsInstance(basic_data['ab_test_enabled'], bool)
        self.assertIsInstance(basic_data['scan_window'], int)
        self.assertIsInstance(basic_data['config_version'], str)


class TestErrorHandlingAndEdgeCases(unittest.TestCase):
    """错误处理和边缘情况测试"""
    
    def setUp(self):
        """测试准备"""
        if not INTEGRATION_AVAILABLE:
            self.skipTest("双策略集成模块不可用")
            
    def test_invalid_strategy_mode_handling(self):
        """测试无效策略模式处理"""
        config = get_default_http_strategy_config()
        
        # 设置无效策略模式（通过直接修改枚举值）
        with patch.object(config.strategy, 'primary_strategy', 'invalid_mode'):
            # 应该回退到False（Legacy策略）
            result = config.should_use_scanning_strategy()
            self.assertFalse(result)
            
    def test_missing_file_path_in_ab_test(self):
        """测试A/B测试中缺失文件路径的处理"""
        config = create_ab_test_config(0.5)
        
        # 无文件路径时应该能正常工作
        result1 = config.should_use_scanning_strategy(None)
        result2 = config.should_use_scanning_strategy("")
        
        # 结果应该是布尔值
        self.assertIsInstance(result1, bool)
        self.assertIsInstance(result2, bool)
        
    def test_extreme_ab_test_ratios(self):
        """测试极端A/B测试比例"""
        # 0%比例
        config_0 = create_ab_test_config(0.0)
        for i in range(10):
            result = config_0.should_use_scanning_strategy(f"file_{i}.pcap")
            self.assertFalse(result, "0%比例应该总是选择Legacy策略")
            
        # 100%比例
        config_100 = create_ab_test_config(1.0)
        for i in range(10):
            result = config_100.should_use_scanning_strategy(f"file_{i}.pcap")
            self.assertTrue(result, "100%比例应该总是选择Scanning策略")
            
    def test_configuration_defensive_validation(self):
        """测试配置防御性验证"""
        config = get_default_http_strategy_config()
        
        # 测试各种边界值
        test_cases = [
            # (字段设置, 期望有效性)
            (lambda c: setattr(c.scanning, 'max_scan_window', 1), True),      # 最小有效值
            (lambda c: setattr(c.scanning, 'max_scan_window', 0), False),     # 边界无效值
            (lambda c: setattr(c.scanning, 'conservative_preserve_ratio', 0.0), True),  # 边界有效值
            (lambda c: setattr(c.scanning, 'conservative_preserve_ratio', 1.0), True),  # 边界有效值
            (lambda c: setattr(c.scanning, 'conservative_preserve_ratio', -0.1), False), # 边界无效值
            (lambda c: setattr(c.scanning, 'conservative_preserve_ratio', 1.1), False),  # 边界无效值
        ]
        
        for field_setter, expected_valid in test_cases:
            # 重置配置
            test_config = get_default_http_strategy_config()
            
            # 应用测试设置
            field_setter(test_config)
            
            # 验证结果
            is_valid, errors = test_config.validate()
            self.assertEqual(is_valid, expected_valid, 
                           f"配置验证结果不符合预期: {errors}")


if __name__ == '__main__':
    unittest.main() 