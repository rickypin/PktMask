#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Phase 6.2 增强插件系统测试
测试版本管理、依赖检查、动态发现、热插拔和监控功能
"""

import sys
import time
import unittest
from pathlib import Path
from datetime import datetime

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.pktmask.algorithms.interfaces.algorithm_interface import (
    AlgorithmInterface, AlgorithmInfo, AlgorithmType, AlgorithmStatus,
    AlgorithmDependency, DependencyType, PluginConfig, AlgorithmConfig,
    AlgorithmMetadata
)
from src.pktmask.algorithms.registry.enhanced_plugin_manager import (
    EnhancedPluginManager, PluginMetrics, PluginRegistration,
    DependencyManager, PluginDiscovery
)


class MockAlgorithm(AlgorithmInterface):
    """模拟算法实现"""
    
    def __init__(self):
        super().__init__()
        self._performance_metrics = {
            'processed_items': 0,
            'processing_time_ms': 0.0
        }
    
    def get_algorithm_info(self) -> AlgorithmInfo:
        return AlgorithmInfo(
            name="mock_algorithm",
            version="1.0.0",
            algorithm_type=AlgorithmType.CUSTOM,
            author="Test Author",
            description="模拟算法用于测试",
            supported_formats=["test"],
            requirements={"python": ">=3.8"},
            dependencies=[
                AlgorithmDependency(
                    name="pytest",
                    version_spec=">=6.0.0",
                    dependency_type=DependencyType.OPTIONAL,
                    description="测试依赖"
                )
            ],
            metadata=AlgorithmMetadata(
                tags={"test", "mock"},
                category="testing",
                keywords=["test", "mock", "algorithm"]
            )
        )
    
    def get_default_config(self) -> AlgorithmConfig:
        return AlgorithmConfig(
            enabled=True,
            priority=0,
            hot_reload=True,
            performance_monitoring=True
        )
    
    def validate_config(self, config: AlgorithmConfig):
        from src.pktmask.algorithms.interfaces.algorithm_interface import ValidationResult
        result = ValidationResult(is_valid=True)
        return result
    
    def _apply_config(self, config: AlgorithmConfig) -> bool:
        return True
    
    def _do_initialize(self) -> bool:
        self._status = AlgorithmStatus.IDLE
        return True
    
    def _do_cleanup(self):
        pass
    
    def get_performance_metrics(self) -> dict:
        return self._performance_metrics.copy()
    
    def _do_reset_metrics(self):
        self._performance_metrics = {
            'processed_items': 0,
            'processing_time_ms': 0.0
        }
    
    def process_data(self, data):
        """模拟数据处理"""
        start_time = time.time()
        time.sleep(0.001)  # 模拟处理时间
        self._performance_metrics['processed_items'] += 1
        self._performance_metrics['processing_time_ms'] += (time.time() - start_time) * 1000
        return f"processed: {data}"


class MockOptimizedAlgorithm(MockAlgorithm):
    """优化版本的模拟算法"""
    
    def get_algorithm_info(self) -> AlgorithmInfo:
        info = super().get_algorithm_info()
        info.name = "mock_optimized_algorithm"
        info.version = "2.0.0"
        info.description = "优化版本的模拟算法"
        info.metadata.tags.add("optimized")
        return info


class TestPhase62EnhancedPlugins(unittest.TestCase):
    """Phase 6.2 增强插件系统测试"""
    
    def setUp(self):
        """测试准备"""
        self.manager = EnhancedPluginManager()
        
    def tearDown(self):
        """测试清理"""
        self.manager.cleanup_all()
    
    def test_01_dependency_manager(self):
        """测试依赖管理器"""
        print("\n=== 测试依赖管理器 ===")
        
        dep_manager = DependencyManager()
        
        # 测试Python版本检查
        python_version = dep_manager.get_python_version()
        print(f"当前Python版本: {python_version}")
        self.assertIsNotNone(python_version)
        
        # 测试依赖检查
        dependencies = [
            AlgorithmDependency(
                name="sys",  # 系统内置模块，应该存在
                version_spec="*",  # 任意版本
                dependency_type=DependencyType.REQUIRED
            ),
            AlgorithmDependency(
                name="nonexistent_package_12345",
                version_spec=">=1.0.0",
                dependency_type=DependencyType.REQUIRED
            )
        ]
        
        missing_deps = dep_manager.check_dependencies(dependencies)
        print(f"缺失依赖: {missing_deps}")
        
        # 应该有一个缺失的依赖
        self.assertGreater(len(missing_deps), 0)
        self.assertTrue(any("nonexistent_package" in dep for dep in missing_deps))
    
    def test_02_plugin_registration_with_dependencies(self):
        """测试带依赖检查的插件注册"""
        print("\n=== 测试插件注册与依赖检查 ===")
        
        # 注册模拟算法
        success = self.manager.register_plugin(MockAlgorithm)
        self.assertTrue(success)
        print("✅ 插件注册成功")
        
        # 验证插件信息
        plugin_info = self.manager.get_plugin_info("mock_algorithm")
        self.assertIsNotNone(plugin_info)
        self.assertEqual(plugin_info.name, "mock_algorithm")
        self.assertEqual(plugin_info.version, "1.0.0")
        print(f"✅ 插件信息验证成功: {plugin_info.name} v{plugin_info.version}")
        
        # 检查依赖信息
        self.assertEqual(len(plugin_info.dependencies), 1)
        self.assertEqual(plugin_info.dependencies[0].name, "pytest")
        print("✅ 依赖信息验证成功")
    
    def test_03_plugin_metrics_tracking(self):
        """测试插件性能指标跟踪"""
        print("\n=== 测试插件性能指标跟踪 ===")
        
        # 注册插件
        self.manager.register_plugin(MockAlgorithm)
        
        # 获取插件实例并执行操作
        plugin = self.manager.get_plugin("mock_algorithm")
        self.assertIsNotNone(plugin)
        
        # 模拟多次操作
        for i in range(5):
            result = plugin.process_data(f"test_data_{i}")
            self.assertIsNotNone(result)
        
        # 检查性能指标
        metrics = self.manager.get_plugin_metrics("mock_algorithm")
        self.assertIsNotNone(metrics)
        self.assertGreater(metrics.total_executions, 0)
        self.assertGreater(metrics.load_time_ms, 0)
        self.assertGreater(metrics.average_execution_time_ms, 0)
        
        print(f"✅ 性能指标跟踪成功:")
        print(f"   - 总执行次数: {metrics.total_executions}")
        print(f"   - 加载时间: {metrics.load_time_ms:.2f}ms")
        print(f"   - 平均执行时间: {metrics.average_execution_time_ms:.2f}ms")
    
    def test_04_plugin_hot_reload(self):
        """测试插件热重载功能"""
        print("\n=== 测试插件热重载功能 ===")
        
        # 注册支持热重载的插件
        plugin_config = PluginConfig(hot_reload=True)
        success = self.manager.register_plugin(
            MockAlgorithm, 
            plugin_config=plugin_config
        )
        self.assertTrue(success)
        
        # 获取原始实例
        original_plugin = self.manager.get_plugin("mock_algorithm")
        self.assertIsNotNone(original_plugin)
        original_id = id(original_plugin)
        
        # 执行热重载
        reload_success = self.manager.reload_plugin("mock_algorithm")
        self.assertTrue(reload_success)
        print("✅ 热重载执行成功")
        
        # 获取新实例
        new_plugin = self.manager.get_plugin("mock_algorithm")
        self.assertIsNotNone(new_plugin)
        new_id = id(new_plugin)
        
        # 验证实例已更新
        self.assertNotEqual(original_id, new_id)
        print("✅ 插件实例已更新")
    
    def test_05_plugin_versioning(self):
        """测试插件版本管理"""
        print("\n=== 测试插件版本管理 ===")
        
        # 注册原版本
        success1 = self.manager.register_plugin(MockAlgorithm)
        self.assertTrue(success1)
        
        # 尝试注册优化版本（应该被拒绝，因为名称不同）
        success2 = self.manager.register_plugin(MockOptimizedAlgorithm)
        self.assertTrue(success2)  # 不同名称，应该成功
        
        # 检查两个版本都存在
        plugins = self.manager.list_plugins()
        self.assertIn("mock_algorithm", plugins)
        self.assertIn("mock_optimized_algorithm", plugins)
        
        # 检查版本信息
        info1 = self.manager.get_plugin_info("mock_algorithm")
        info2 = self.manager.get_plugin_info("mock_optimized_algorithm")
        
        self.assertEqual(info1.version, "1.0.0")
        self.assertEqual(info2.version, "2.0.0")
        
        print(f"✅ 版本管理验证成功:")
        print(f"   - 原版本: {info1.name} v{info1.version}")
        print(f"   - 优化版本: {info2.name} v{info2.version}")
    
    def test_06_plugin_metadata_handling(self):
        """测试插件元数据处理"""
        print("\n=== 测试插件元数据处理 ===")
        
        # 注册插件
        self.manager.register_plugin(MockAlgorithm)
        
        # 获取插件信息
        info = self.manager.get_plugin_info("mock_algorithm")
        self.assertIsNotNone(info)
        
        # 验证元数据
        metadata = info.metadata
        self.assertIn("test", metadata.tags)
        self.assertIn("mock", metadata.tags)
        self.assertEqual(metadata.category, "testing")
        self.assertIn("test", metadata.keywords)
        
        print(f"✅ 元数据验证成功:")
        print(f"   - 标签: {metadata.tags}")
        print(f"   - 分类: {metadata.category}")
        print(f"   - 关键词: {metadata.keywords}")
    
    def test_07_plugin_configuration_management(self):
        """测试插件配置管理"""
        print("\n=== 测试插件配置管理 ===")
        
        # 创建自定义配置
        plugin_config = PluginConfig(
            auto_register=True,
            load_on_startup=True,
            enable_monitoring=True,
            health_check_interval=30,
            max_restart_attempts=2
        )
        
        # 注册插件
        success = self.manager.register_plugin(
            MockAlgorithm,
            plugin_config=plugin_config
        )
        self.assertTrue(success)
        
        # 获取注册信息
        registrations = self.manager.get_all_registrations()
        self.assertIn("mock_algorithm", registrations)
        
        registration = registrations["mock_algorithm"]
        self.assertEqual(registration.plugin_config.health_check_interval, 30)
        self.assertEqual(registration.plugin_config.max_restart_attempts, 2)
        self.assertTrue(registration.plugin_config.enable_monitoring)
        
        print("✅ 插件配置管理验证成功")
    
    def test_08_manager_statistics(self):
        """测试管理器统计信息"""
        print("\n=== 测试管理器统计信息 ===")
        
        # 注册多个插件
        self.manager.register_plugin(MockAlgorithm)
        self.manager.register_plugin(MockOptimizedAlgorithm)
        
        # 获取统计信息
        stats = self.manager.get_manager_stats()
        
        self.assertEqual(stats['total_plugins'], 2)
        self.assertEqual(stats['active_plugins'], 2)
        self.assertIn('plugins_by_type', stats)
        self.assertIn(AlgorithmType.CUSTOM.value, stats['plugins_by_type'])
        self.assertEqual(stats['plugins_by_type'][AlgorithmType.CUSTOM.value], 2)
        
        print(f"✅ 管理器统计信息:")
        print(f"   - 总插件数: {stats['total_plugins']}")
        print(f"   - 活跃插件数: {stats['active_plugins']}")
        print(f"   - 按类型分布: {stats['plugins_by_type']}")
    
    def test_09_plugin_lifecycle_management(self):
        """测试插件生命周期管理"""
        print("\n=== 测试插件生命周期管理 ===")
        
        # 注册插件
        success = self.manager.register_plugin(MockAlgorithm)
        self.assertTrue(success)
        print("✅ 插件注册成功")
        
        # 验证插件存在
        plugins = self.manager.list_plugins()
        self.assertIn("mock_algorithm", plugins)
        
        # 获取插件实例
        plugin = self.manager.get_plugin("mock_algorithm")
        self.assertIsNotNone(plugin)
        print("✅ 插件实例获取成功")
        
        # 注销插件
        unregister_success = self.manager.unregister_plugin("mock_algorithm")
        self.assertTrue(unregister_success)
        print("✅ 插件注销成功")
        
        # 验证插件已移除
        plugins_after = self.manager.list_plugins()
        self.assertNotIn("mock_algorithm", plugins_after)
        
        # 尝试获取已注销的插件
        plugin_after = self.manager.get_plugin("mock_algorithm")
        self.assertIsNone(plugin_after)
        print("✅ 插件生命周期管理验证成功")
    
    def test_10_comprehensive_integration(self):
        """综合集成测试"""
        print("\n=== 综合集成测试 ===")
        
        start_time = time.time()
        
        # 1. 注册多个插件
        self.manager.register_plugin(MockAlgorithm)
        self.manager.register_plugin(MockOptimizedAlgorithm)
        
        # 2. 执行操作并收集指标
        plugin1 = self.manager.get_plugin("mock_algorithm")
        plugin2 = self.manager.get_plugin("mock_optimized_algorithm")
        
        for i in range(3):
            plugin1.process_data(f"data1_{i}")
            plugin2.process_data(f"data2_{i}")
        
        # 3. 检查所有指标
        stats = self.manager.get_manager_stats()
        metrics1 = self.manager.get_plugin_metrics("mock_algorithm")
        metrics2 = self.manager.get_plugin_metrics("mock_optimized_algorithm")
        
        # 4. 验证结果
        self.assertEqual(stats['total_plugins'], 2)
        self.assertEqual(stats['active_plugins'], 2)
        self.assertGreater(metrics1.total_executions, 0)
        self.assertGreater(metrics2.total_executions, 0)
        
        # 5. 清理测试
        self.manager.cleanup_all()
        final_stats = self.manager.get_manager_stats()
        self.assertEqual(final_stats['total_plugins'], 0)
        
        end_time = time.time()
        execution_time = (end_time - start_time) * 1000
        
        print(f"✅ 综合集成测试完成")
        print(f"   - 执行时间: {execution_time:.2f}ms")
        print(f"   - 插件1执行次数: {metrics1.total_executions}")
        print(f"   - 插件2执行次数: {metrics2.total_executions}")


def run_phase_6_2_tests():
    """运行Phase 6.2测试套件"""
    print("🚀 开始 Phase 6.2 增强插件系统测试")
    print("=" * 60)
    
    # 创建测试套件
    suite = unittest.TestLoader().loadTestsFromTestCase(TestPhase62EnhancedPlugins)
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 输出测试总结
    print("\n" + "=" * 60)
    print("📊 Phase 6.2 测试总结")
    print(f"   - 总测试数: {result.testsRun}")
    print(f"   - 成功测试: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"   - 失败测试: {len(result.failures)}")
    print(f"   - 错误测试: {len(result.errors)}")
    
    if result.failures:
        print("\n❌ 失败的测试:")
        for test, traceback in result.failures:
            print(f"   - {test}: {traceback.split('AssertionError:')[-1].strip()}")
    
    if result.errors:
        print("\n🔥 错误的测试:")
        for test, traceback in result.errors:
            print(f"   - {test}: {traceback.split('Exception:')[-1].strip()}")
    
    success_rate = (result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100
    print(f"\n✅ 测试成功率: {success_rate:.1f}%")
    
    if success_rate >= 90:
        print("🎉 Phase 6.2 增强插件系统测试通过！")
        return True
    else:
        print("⚠️  部分测试未通过，需要进一步调试")
        return False


if __name__ == "__main__":
    run_phase_6_2_tests() 