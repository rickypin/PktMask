#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Phase 6.3 算法配置化测试 - 完整验证
测试算法配置模型、配置管理器、模板系统和集成功能
"""

import unittest
import tempfile
import shutil
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from unittest.mock import Mock, MagicMock

# 导入待测试的模块
from src.pktmask.config.algorithm_configs import (
    IPAnonymizationConfig, PacketProcessingConfig, DeduplicationConfig,
    CustomAlgorithmConfig, AlgorithmConfigFactory, ConfigTemplateManager,
    config_template_manager, AnonymizationMethod, CacheStrategy
)
from src.pktmask.config.config_manager import (
    AlgorithmConfigManager, ConfigChangeEvent, ConfigVersion
)
from src.pktmask.algorithms.registry.config_integration import (
    AlgorithmConfigIntegrator, ConfiguredAlgorithmProxy
)
from src.pktmask.algorithms.interfaces.algorithm_interface import (
    AlgorithmInterface, AlgorithmInfo, AlgorithmType, AlgorithmConfig,
    ValidationResult
)


class MockConfigurableAlgorithm(AlgorithmInterface):
    """支持配置热更新的模拟算法"""
    
    def __init__(self, name: str, algorithm_type: str):
        self._name = name
        self._algorithm_type = algorithm_type
        self._config: Optional[AlgorithmConfig] = None
        self._config_update_count = 0
    
    def get_algorithm_info(self) -> AlgorithmInfo:
        return AlgorithmInfo(
            name=self._name,
            version="1.0.0",
            algorithm_type=AlgorithmType.IP_ANONYMIZATION,
            description=f"Mock {self._algorithm_type} algorithm",
            author="Test Suite",
            supported_formats=["pcap", "json"],
            requirements={}
        )
    
    def process(self, data: Any) -> Any:
        return f"Processed by {self._name}: {data}"
    
    def update_config(self, config: AlgorithmConfig):
        """支持配置热更新"""
        self._config = config
        self._config_update_count += 1
    
    def get_current_config(self) -> Optional[AlgorithmConfig]:
        return self._config
    
    def get_config_update_count(self) -> int:
        return self._config_update_count
    
    def get_default_config(self) -> AlgorithmConfig:
        """获取默认配置"""
        return AlgorithmConfig()
    
    def validate_config(self, config: AlgorithmConfig) -> ValidationResult:
        """验证配置"""
        return ValidationResult(is_valid=True)
    
    def _apply_config(self, config: AlgorithmConfig) -> bool:
        """应用配置"""
        return True
    
    def _do_initialize(self) -> bool:
        """初始化"""
        return True
    
    def _do_cleanup(self):
        """清理"""
        pass
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """获取性能指标"""
        return {"processed_count": 0, "processing_time": 0.0}
    
    def _do_reset_metrics(self):
        """重置指标"""
        pass


class TestAlgorithmConfigs(unittest.TestCase):
    """测试算法配置模型"""
    
    def test_ip_anonymization_config(self):
        """测试IP匿名化配置"""
        # 测试默认配置
        config = IPAnonymizationConfig()
        self.assertEqual(config.anonymization_method, AnonymizationMethod.HIERARCHICAL)
        self.assertEqual(config.preserve_subnet_bits, 24)
        self.assertEqual(config.cache_strategy, CacheStrategy.LRU)
        self.assertEqual(config.cache_size, 10000)
        
        # 测试自定义配置
        config = IPAnonymizationConfig(
            anonymization_method=AnonymizationMethod.HASH,
            preserve_subnet_bits=16,
            cache_size=50000,
            batch_size=2000
        )
        self.assertEqual(config.anonymization_method, AnonymizationMethod.HASH)
        self.assertEqual(config.preserve_subnet_bits, 16)
        self.assertEqual(config.cache_size, 50000)
        self.assertEqual(config.batch_size, 2000)
    
    def test_ip_anonymization_config_validation(self):
        """测试IP匿名化配置验证"""
        # 测试匿名化级别验证
        with self.assertRaises(ValueError):
            IPAnonymizationConfig(anonymization_levels=[])  # 空列表
        
        with self.assertRaises(ValueError):
            IPAnonymizationConfig(anonymization_levels=[5, 16, 24])  # 包含无效值
        
        with self.assertRaises(ValueError):
            IPAnonymizationConfig(anonymization_levels=[16, 16, 24])  # 重复值
        
        # 测试哈希算法验证
        with self.assertRaises(ValueError):
            IPAnonymizationConfig(hash_algorithm="invalid")
        
        # 正确的配置应该通过验证
        config = IPAnonymizationConfig(
            anonymization_levels=[8, 16, 24],
            hash_algorithm="sha256"
        )
        self.assertEqual(config.anonymization_levels, [8, 16, 24])
        self.assertEqual(config.hash_algorithm, "sha256")
    
    def test_packet_processing_config(self):
        """测试数据包处理配置"""
        config = PacketProcessingConfig(
            processing_mode="batch",
            filter_protocols=["TCP", "UDP"],
            min_packet_size=128,
            max_packet_size=1500,
            trim_size=200,
            enable_compression=True
        )
        
        self.assertEqual(config.processing_mode, "batch")
        self.assertEqual(config.filter_protocols, ["TCP", "UDP"])
        self.assertEqual(config.min_packet_size, 128)
        self.assertEqual(config.max_packet_size, 1500)
        self.assertEqual(config.trim_size, 200)
        self.assertTrue(config.enable_compression)
    
    def test_packet_processing_config_validation(self):
        """测试数据包处理配置验证"""
        # 测试处理模式验证
        with self.assertRaises(ValueError):
            PacketProcessingConfig(processing_mode="invalid")
        
        # 测试协议验证
        with self.assertRaises(ValueError):
            PacketProcessingConfig(filter_protocols=["INVALID"])
        
        # 测试数据包大小验证
        with self.assertRaises(ValueError):
            PacketProcessingConfig(min_packet_size=1000, max_packet_size=500)
    
    def test_deduplication_config(self):
        """测试去重配置"""
        config = DeduplicationConfig(
            hash_algorithm="sha256",
            time_window_seconds=120,
            max_cache_entries=200000,
            enable_parallel_processing=True
        )
        
        self.assertEqual(config.hash_algorithm, "sha256")
        self.assertEqual(config.time_window_seconds, 120)
        self.assertEqual(config.max_cache_entries, 200000)
        self.assertTrue(config.enable_parallel_processing)
    
    def test_custom_algorithm_config(self):
        """测试自定义算法配置"""
        config = CustomAlgorithmConfig(
            custom_parameters={"param1": "value1", "param2": 42},
            plugin_name="test_plugin",
            plugin_version="2.0.0"
        )
        
        self.assertEqual(config.custom_parameters["param1"], "value1")
        self.assertEqual(config.custom_parameters["param2"], 42)
        self.assertEqual(config.plugin_name, "test_plugin")
        self.assertEqual(config.plugin_version, "2.0.0")


class TestAlgorithmConfigFactory(unittest.TestCase):
    """测试算法配置工厂"""
    
    def test_create_ip_anonymization_config(self):
        """测试创建IP匿名化配置"""
        config = AlgorithmConfigFactory.create_config(
            AlgorithmType.IP_ANONYMIZATION,
            anonymization_method="hash",
            cache_size=20000
        )
        
        self.assertIsInstance(config, IPAnonymizationConfig)
        self.assertEqual(config.anonymization_method, AnonymizationMethod.HASH)
        self.assertEqual(config.cache_size, 20000)
    
    def test_create_packet_processing_config(self):
        """测试创建数据包处理配置"""
        config = AlgorithmConfigFactory.create_config(
            AlgorithmType.PACKET_PROCESSING,
            processing_mode="streaming",
            enable_compression=True
        )
        
        self.assertIsInstance(config, PacketProcessingConfig)
        self.assertEqual(config.processing_mode, "streaming")
        self.assertTrue(config.enable_compression)
    
    def test_create_deduplication_config(self):
        """测试创建去重配置"""
        config = AlgorithmConfigFactory.create_config(
            AlgorithmType.DEDUPLICATION,
            hash_algorithm="md5",
            time_window_seconds=300
        )
        
        self.assertIsInstance(config, DeduplicationConfig)
        self.assertEqual(config.hash_algorithm, "md5")
        self.assertEqual(config.time_window_seconds, 300)
    
    def test_unsupported_algorithm_type(self):
        """测试不支持的算法类型"""
        with self.assertRaises(ValueError):
            # 创建一个不存在的算法类型（使用字符串代替枚举）
            AlgorithmConfigFactory.create_config("UNSUPPORTED_TYPE")


class TestConfigTemplateManager(unittest.TestCase):
    """测试配置模板管理器"""
    
    def setUp(self):
        self.template_manager = ConfigTemplateManager()
    
    def test_default_templates(self):
        """测试默认模板"""
        templates = self.template_manager.list_templates()
        self.assertGreater(len(templates), 0)
        
        # 检查IP匿名化默认模板
        ip_template = self.template_manager.get_template("ip_anonymization_default")
        self.assertIsNotNone(ip_template)
        self.assertEqual(ip_template.algorithm_type, AlgorithmType.IP_ANONYMIZATION)
        self.assertIn("default", ip_template.tags)
    
    def test_create_config_from_template(self):
        """测试从模板创建配置"""
        config = self.template_manager.create_config_from_template(
            "ip_anonymization_default"
        )
        
        self.assertIsInstance(config, IPAnonymizationConfig)
        self.assertEqual(config.anonymization_method, AnonymizationMethod.HIERARCHICAL)
    
    def test_create_config_with_overrides(self):
        """测试带覆盖参数的模板配置创建"""
        config = self.template_manager.create_config_from_template(
            "ip_anonymization_default",
            overrides={"cache_size": 50000, "batch_size": 2000}
        )
        
        self.assertIsInstance(config, IPAnonymizationConfig)
        self.assertEqual(config.cache_size, 50000)
        self.assertEqual(config.batch_size, 2000)
        # 其他参数应保持模板默认值
        self.assertEqual(config.anonymization_method, AnonymizationMethod.HIERARCHICAL)
    
    def test_filter_templates(self):
        """测试模板筛选"""
        # 按算法类型筛选
        ip_templates = self.template_manager.list_templates(
            algorithm_type=AlgorithmType.IP_ANONYMIZATION
        )
        self.assertTrue(all(t.algorithm_type == AlgorithmType.IP_ANONYMIZATION for t in ip_templates))
        
        # 按标签筛选
        performance_templates = self.template_manager.list_templates(
            tags=["performance"]
        )
        self.assertTrue(all("performance" in t.tags for t in performance_templates))


class TestAlgorithmConfigManager(unittest.TestCase):
    """测试算法配置管理器"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_manager = AlgorithmConfigManager(config_directory=self.temp_dir)
        self.config_events = []
        
        def event_handler(event: ConfigChangeEvent):
            self.config_events.append(event)
        
        self.config_manager.add_change_handler(event_handler)
    
    def tearDown(self):
        self.config_manager.cleanup()
        shutil.rmtree(self.temp_dir)
    
    def test_create_config(self):
        """测试创建配置"""
        config = self.config_manager.create_config(
            name="test_ip_config",
            algorithm_type=AlgorithmType.IP_ANONYMIZATION,
            config_data={"cache_size": 30000}
        )
        
        self.assertIsInstance(config, IPAnonymizationConfig)
        self.assertEqual(config.cache_size, 30000)
        
        # 检查事件
        self.assertEqual(len(self.config_events), 1)
        self.assertEqual(self.config_events[0].change_type, "created")
        self.assertEqual(self.config_events[0].config_name, "test_ip_config")
    
    def test_create_config_from_template(self):
        """测试从模板创建配置"""
        config = self.config_manager.create_config(
            name="test_template_config",
            algorithm_type=AlgorithmType.IP_ANONYMIZATION,
            template_name="ip_anonymization_default",
            config_data={"batch_size": 3000}
        )
        
        self.assertIsInstance(config, IPAnonymizationConfig)
        self.assertEqual(config.batch_size, 3000)
        self.assertEqual(config.anonymization_method, AnonymizationMethod.HIERARCHICAL)
    
    def test_update_config(self):
        """测试更新配置"""
        # 先创建配置
        self.config_manager.create_config(
            name="test_update_config",
            algorithm_type=AlgorithmType.IP_ANONYMIZATION,
            config_data={"cache_size": 10000}
        )
        
        # 清空事件
        self.config_events.clear()
        
        # 更新配置
        updated_config = self.config_manager.update_config(
            name="test_update_config",
            config_data={"cache_size": 20000, "batch_size": 1500},
            comment="增加缓存大小"
        )
        
        self.assertEqual(updated_config.cache_size, 20000)
        self.assertEqual(updated_config.batch_size, 1500)
        
        # 检查事件
        self.assertEqual(len(self.config_events), 1)
        self.assertEqual(self.config_events[0].change_type, "updated")
    
    def test_config_versions(self):
        """测试配置版本管理"""
        # 创建配置
        self.config_manager.create_config(
            name="test_version_config",
            algorithm_type=AlgorithmType.IP_ANONYMIZATION,
            config_data={"cache_size": 10000}
        )
        
        # 更新配置
        self.config_manager.update_config(
            name="test_version_config",
            config_data={"cache_size": 20000},
            comment="第一次更新"
        )
        
        self.config_manager.update_config(
            name="test_version_config",
            config_data={"cache_size": 30000},
            comment="第二次更新"
        )
        
        # 检查版本历史
        versions = self.config_manager.get_config_versions("test_version_config")
        self.assertEqual(len(versions), 3)  # 初始创建 + 2次更新
        self.assertEqual(versions[0].comment, "初始创建")
        self.assertEqual(versions[1].comment, "第一次更新")
        self.assertEqual(versions[2].comment, "第二次更新")
    
    def test_file_operations(self):
        """测试文件操作"""
        # 创建配置并保存到文件
        config = self.config_manager.create_config(
            name="test_file_config",
            algorithm_type=AlgorithmType.PACKET_PROCESSING,
            config_data={"processing_mode": "batch"}
        )
        
        # 检查文件是否创建
        config_file = Path(self.temp_dir) / "test_file_config.json"
        self.assertTrue(config_file.exists())
        
        # 导出配置
        export_file = Path(self.temp_dir) / "exported_config.json"
        self.config_manager.export_config(
            "test_file_config",
            export_file,
            format="json"
        )
        self.assertTrue(export_file.exists())
        
        # 从文件加载配置
        self.config_manager.delete_config("test_file_config")
        loaded_name = self.config_manager.load_config_from_file(export_file)
        
        self.assertEqual(loaded_name, "test_file_config")
        loaded_config = self.config_manager.get_config("test_file_config")
        self.assertIsNotNone(loaded_config)
        self.assertEqual(loaded_config.processing_mode, "batch")


class TestAlgorithmConfigIntegrator(unittest.TestCase):
    """测试算法配置集成器"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_manager = AlgorithmConfigManager(config_directory=self.temp_dir)
        self.integrator = AlgorithmConfigIntegrator(config_manager=self.config_manager)
        
        # 创建模拟算法
        self.mock_algorithm = MockConfigurableAlgorithm("TestAlgorithm", "IP Anonymization")
    
    def tearDown(self):
        self.integrator.cleanup()
        self.config_manager.cleanup()
        shutil.rmtree(self.temp_dir)
    
    def test_register_algorithm_with_config(self):
        """测试注册带配置的算法"""
        proxy = self.integrator.register_algorithm_with_config(
            algorithm_id="test_algorithm",
            algorithm=self.mock_algorithm,
            config_data={"cache_size": 15000}
        )
        
        self.assertIsInstance(proxy, ConfiguredAlgorithmProxy)
        
        # 检查配置是否创建
        config = self.integrator.get_algorithm_config("test_algorithm")
        self.assertIsNotNone(config)
        self.assertEqual(config.cache_size, 15000)
        
        # 检查算法是否收到配置
        self.assertEqual(self.mock_algorithm.get_config_update_count(), 1)
    
    def test_register_algorithm_with_template(self):
        """测试使用模板注册算法"""
        proxy = self.integrator.register_algorithm_with_config(
            algorithm_id="template_algorithm",
            algorithm=self.mock_algorithm,
            template_name="ip_anonymization_default",
            config_data={"batch_size": 2500}
        )
        
        config = self.integrator.get_algorithm_config("template_algorithm")
        self.assertIsNotNone(config)
        self.assertEqual(config.batch_size, 2500)
        self.assertEqual(config.anonymization_method, AnonymizationMethod.HIERARCHICAL)
    
    def test_hot_config_update(self):
        """测试配置热更新"""
        # 注册算法
        self.integrator.register_algorithm_with_config(
            algorithm_id="hot_update_algorithm",
            algorithm=self.mock_algorithm,
            config_data={"cache_size": 10000}
        )
        
        initial_update_count = self.mock_algorithm.get_config_update_count()
        
        # 更新配置
        success = self.integrator.update_algorithm_config(
            algorithm_id="hot_update_algorithm",
            config_data={"cache_size": 25000},
            comment="热更新测试"
        )
        
        self.assertTrue(success)
        
        # 给事件处理一些时间
        time.sleep(0.1)
        
        # 检查算法是否收到更新
        new_update_count = self.mock_algorithm.get_config_update_count()
        self.assertEqual(new_update_count, initial_update_count + 1)
        
        # 检查配置是否更新
        config = self.integrator.get_algorithm_config("hot_update_algorithm")
        self.assertEqual(config.cache_size, 25000)
    
    def test_export_import_configs(self):
        """测试配置导入导出"""
        # 注册多个算法
        for i in range(3):
            algorithm = MockConfigurableAlgorithm(f"Algorithm{i}", "Test")
            self.integrator.register_algorithm_with_config(
                algorithm_id=f"algorithm_{i}",
                algorithm=algorithm,
                config_data={"cache_size": 10000 + i * 1000}
            )
        
        # 导出配置
        export_dir = Path(self.temp_dir) / "exports"
        self.integrator.export_algorithm_configs(str(export_dir))
        
        # 检查导出文件
        self.assertTrue(export_dir.exists())
        export_files = list(export_dir.glob("*.json"))
        self.assertEqual(len(export_files), 3)
        
        # 清理配置
        for i in range(3):
            self.integrator.unregister_algorithm(f"algorithm_{i}")
        
        # 导入配置
        self.integrator.import_algorithm_configs(str(export_dir))
        
        # 检查导入的配置
        imported_configs = self.config_manager.list_configs()
        self.assertGreaterEqual(len(imported_configs), 3)


class TestConfigHotReload(unittest.TestCase):
    """测试配置热重载功能"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_manager = AlgorithmConfigManager(config_directory=self.temp_dir)
        self.config_manager.start_watching()
        
        self.integrator = AlgorithmConfigIntegrator(config_manager=self.config_manager)
        self.mock_algorithm = MockConfigurableAlgorithm("HotReloadAlgorithm", "Test")
    
    def tearDown(self):
        self.config_manager.stop_watching()
        self.integrator.cleanup()
        self.config_manager.cleanup()
        shutil.rmtree(self.temp_dir)
    
    def test_file_change_hot_reload(self):
        """测试文件变更触发的热重载"""
        # 注册算法
        self.integrator.register_algorithm_with_config(
            algorithm_id="file_reload_algorithm",
            algorithm=self.mock_algorithm,
            config_data={"cache_size": 10000}
        )
        
        initial_update_count = self.mock_algorithm.get_config_update_count()
        
        # 直接修改配置文件
        config_file = Path(self.temp_dir) / "file_reload_algorithm_config.json"
        with open(config_file, 'r') as f:
            config_data = json.load(f)
        
        config_data['config']['cache_size'] = 30000
        
        with open(config_file, 'w') as f:
            json.dump(config_data, f, indent=2)
        
        # 等待文件监控器处理变更
        time.sleep(1)
        
        # 检查配置是否更新
        new_update_count = self.mock_algorithm.get_config_update_count()
        self.assertGreater(new_update_count, initial_update_count)
        
        # 检查配置值
        config = self.integrator.get_algorithm_config("file_reload_algorithm")
        self.assertEqual(config.cache_size, 30000)


class TestConfigValidation(unittest.TestCase):
    """测试配置验证功能"""
    
    def setUp(self):
        self.config_manager = AlgorithmConfigManager()
        
        # 添加自定义验证处理器
        def ip_config_validator(name: str, config: AlgorithmConfig) -> ValidationResult:
            result = ValidationResult(is_valid=True)
            if hasattr(config, 'cache_size') and config.cache_size > 100000:
                result.add_warning("缓存大小过大，可能影响内存使用")
            return result
        
        self.config_manager.add_validation_handler(
            AlgorithmType.IP_ANONYMIZATION,
            ip_config_validator
        )
    
    def tearDown(self):
        self.config_manager.cleanup()
    
    def test_custom_validation(self):
        """测试自定义验证"""
        # 创建配置，触发验证
        config = self.config_manager.create_config(
            name="validation_test_config",
            algorithm_type=AlgorithmType.IP_ANONYMIZATION,
            config_data={"cache_size": 150000}  # 触发警告
        )
        
        # 配置应该创建成功，但有警告
        self.assertIsNotNone(config)
        self.assertEqual(config.cache_size, 150000)


def run_phase_6_3_tests():
    """运行Phase 6.3所有测试"""
    print("🧪 开始运行 Phase 6.3 算法配置化测试...")
    print("=" * 70)
    
    # 创建测试套件
    test_suite = unittest.TestSuite()
    
    # 添加测试类
    test_classes = [
        TestAlgorithmConfigs,
        TestAlgorithmConfigFactory,
        TestConfigTemplateManager,
        TestAlgorithmConfigManager,
        TestAlgorithmConfigIntegrator,
        TestConfigHotReload,
        TestConfigValidation
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # 输出结果统计
    print("\n" + "=" * 70)
    print("📊 Phase 6.3 测试结果统计:")
    print(f"✅ 总测试数: {result.testsRun}")
    print(f"✅ 成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"❌ 失败: {len(result.failures)}")
    print(f"💥 错误: {len(result.errors)}")
    
    if result.failures:
        print("\n❌ 失败的测试:")
        for test, traceback in result.failures:
            print(f"  - {test}: {traceback.split('AssertionError: ')[-1].split()[0] if 'AssertionError:' in traceback else 'Unknown error'}")
    
    if result.errors:
        print("\n💥 错误的测试:")
        for test, traceback in result.errors:
            print(f"  - {test}: {traceback.splitlines()[-1]}")
    
    # 计算成功率
    success_rate = (result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100
    print(f"\n🎯 测试成功率: {success_rate:.1f}%")
    
    if success_rate == 100:
        print("🎉 Phase 6.3 算法配置化测试全部通过!")
        return True
    else:
        print("⚠️  部分测试未通过，需要修复")
        return False


if __name__ == "__main__":
    success = run_phase_6_3_tests()
    exit(0 if success else 1) 