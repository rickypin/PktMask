#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Phase 6.4 动态加载系统测试
测试插件发现、依赖管理、沙箱和动态加载功能
"""

import unittest
import tempfile
import shutil
import json
import zipfile
import threading
import time
from pathlib import Path
from unittest.mock import Mock, patch
from datetime import datetime

# 导入测试目标
from src.pktmask.algorithms.registry.plugin_discovery import (
    PluginDiscoveryEngine, PluginCandidate, PluginSource, PluginScanner
)
from src.pktmask.algorithms.registry.dependency_resolver import (
    DependencyResolver, DependencyGraph, PackageInstaller, DependencyStatus
)
from src.pktmask.algorithms.registry.plugin_sandbox import (
    PluginSandbox, SandboxManager, SandboxLevel, SandboxConfig, ResourceLimits
)
from src.pktmask.algorithms.registry.dynamic_loader import (
    DynamicPluginLoader, LoadingConfig, LoadingStrategy, PluginState
)
from src.pktmask.algorithms.registry.plugin_marketplace import (
    PluginMarketplace, PluginManifest, PluginCategory, PluginLicense, PluginValidator
)
from src.pktmask.algorithms.interfaces.algorithm_interface import (
    AlgorithmInterface, AlgorithmInfo, AlgorithmType, AlgorithmDependency, DependencyType,
    AlgorithmConfig, ValidationResult
)
from typing import Dict, Any


class MockTestAlgorithm(AlgorithmInterface):
    """测试用的模拟算法"""
    
    def __init__(self, name="TestAlgorithm", version="1.0.0"):
        super().__init__()
        self._name = name
        self._version = version
    
    def get_algorithm_info(self) -> AlgorithmInfo:
        return AlgorithmInfo(
            name=self._name,
            version=self._version,
            description="测试算法",
            algorithm_type=AlgorithmType.CUSTOM,
            author="Test Author",
            supported_formats=[".test"],
            requirements={},
            dependencies=[
                AlgorithmDependency(
                    name="numpy",
                    version_spec=">=1.20.0",
                    dependency_type=DependencyType.REQUIRED
                )
            ]
        )
    
    def get_default_config(self) -> AlgorithmConfig:
        """获取默认配置"""
        return AlgorithmConfig()
    
    def validate_config(self, config) -> ValidationResult:
        """验证配置"""
        return ValidationResult(is_valid=True)
    
    def _apply_config(self, config: AlgorithmConfig) -> bool:
        """应用配置"""
        return True
    
    def _do_initialize(self) -> bool:
        """执行初始化"""
        return True
    
    def _do_cleanup(self):
        """执行清理"""
        pass
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """获取性能指标"""
        return {"test_metric": 1.0}
    
    def _do_reset_metrics(self):
        """重置性能指标"""
        pass
    
    def process(self, data, **kwargs):
        return f"Processed: {data}"
    
    def cleanup(self):
        pass


class TestPluginDiscovery(unittest.TestCase):
    """插件发现引擎测试"""
    
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.discovery_engine = PluginDiscoveryEngine()
        
    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        self.discovery_engine.cleanup()
    
    def test_create_plugin_source(self):
        """测试创建插件源"""
        source = PluginSource(
            path=self.temp_dir,
            source_type="directory",
            name="test_source",
            priority=5,
            trusted=True
        )
        
        self.assertEqual(source.name, "test_source")
        self.assertEqual(source.priority, 5)
        self.assertTrue(source.trusted)
    
    def test_add_and_remove_source(self):
        """测试添加和移除插件源"""
        source = PluginSource(
            path=self.temp_dir,
            source_type="directory",
            name="test_source"
        )
        
        # 添加源
        self.discovery_engine.add_source(source)
        sources = self.discovery_engine.get_sources()
        self.assertTrue(any(s.name == "test_source" for s in sources))
        
        # 移除源
        result = self.discovery_engine.remove_source("test_source")
        self.assertTrue(result)
        sources = self.discovery_engine.get_sources()
        self.assertFalse(any(s.name == "test_source" for s in sources))
    
    def test_create_test_plugin_file(self):
        """测试创建测试插件文件"""
        plugin_content = '''
from src.pktmask.algorithms.interfaces.algorithm_interface import AlgorithmInterface, AlgorithmInfo, AlgorithmType

class TestPlugin(AlgorithmInterface):
    def get_algorithm_info(self):
        return AlgorithmInfo(
            name="TestPlugin",
            version="1.0.0",
            description="Test plugin",
            algorithm_type=AlgorithmType.CUSTOM,
            author="Test"
        )
    
    def process(self, data, **kwargs):
        return data
    
    def cleanup(self):
        pass
        '''
        
        plugin_file = self.temp_dir / "test_plugin.py"
        plugin_file.write_text(plugin_content)
        
        self.assertTrue(plugin_file.exists())
    
    def test_scanner_functionality(self):
        """测试扫描器功能"""
        scanner = PluginScanner()
        
        # 扫描空目录
        candidates = scanner.scan_directory(self.temp_dir)
        self.assertEqual(len(candidates), 0)
        
        # 创建测试文件
        test_file = self.temp_dir / "not_a_plugin.py"
        test_file.write_text("# 这不是一个插件文件")
        
        candidates = scanner.scan_directory(self.temp_dir)
        # 由于不是有效插件，应该没有候选项
        self.assertEqual(len(candidates), 0)
    
    def test_discovery_stats(self):
        """测试发现统计信息"""
        stats = self.discovery_engine.get_discovery_stats()
        
        self.assertIn("total_sources", stats)
        self.assertIn("enabled_sources", stats)
        self.assertIn("total_plugins", stats)
        self.assertIn("valid_plugins", stats)
        self.assertIsInstance(stats["total_sources"], int)


class TestDependencyResolver(unittest.TestCase):
    """依赖解析器测试"""
    
    def setUp(self):
        self.resolver = DependencyResolver()
    
    def tearDown(self):
        self.resolver.cleanup()
    
    def test_dependency_graph_creation(self):
        """测试依赖图创建"""
        graph = DependencyGraph()
        
        dependency = AlgorithmDependency(
            name="numpy",
            version_spec=">=1.20.0",
            dependency_type=DependencyType.REQUIRED
        )
        
        graph.add_dependency("test_plugin", dependency)
        
        self.assertIn("numpy", graph.nodes)
        self.assertEqual(graph.nodes["numpy"].name, "numpy")
        self.assertEqual(graph.nodes["numpy"].version_spec, ">=1.20.0")
    
    def test_package_installer(self):
        """测试包安装器"""
        installer = PackageInstaller()
        
        # 测试试运行模式
        result = installer.install_package("nonexistent-package", dry_run=True)
        # 由于是试运行，应该返回某种结果（取决于实现）
        self.assertIsInstance(result, bool)
    
    def test_check_dependencies(self):
        """测试依赖检查"""
        # 创建模拟候选项
        mock_algorithm = MockTestAlgorithm()
        candidate = PluginCandidate(
            module_path="test.module",
            file_path=Path("test.py"),
            plugin_class=MockTestAlgorithm,
            algorithm_info=mock_algorithm.get_algorithm_info(),
            is_valid=True
        )
        
        results = self.resolver.check_dependencies([candidate])
        
        self.assertIn("TestAlgorithm", results)
        self.assertIsNotNone(results["TestAlgorithm"])
    
    def test_resolver_stats(self):
        """测试解析器统计"""
        stats = self.resolver.get_resolver_stats()
        
        self.assertIn("installed_packages", stats)
        self.assertIn("cache_size", stats)
        self.assertIsInstance(stats["installed_packages"], int)


class TestPluginSandbox(unittest.TestCase):
    """插件沙箱测试"""
    
    def setUp(self):
        self.config = SandboxConfig(
            level=SandboxLevel.BASIC,
            resource_limits=ResourceLimits(
                max_memory_mb=128,
                max_execution_time=30,
                max_cpu_percent=50.0
            )
        )
        self.sandbox = PluginSandbox(self.config)
        self.manager = SandboxManager()
    
    def tearDown(self):
        self.sandbox.cleanup()
        self.manager.cleanup_all()
    
    def test_sandbox_creation(self):
        """测试沙箱创建"""
        sandbox_id = "test_sandbox"
        sandbox = self.manager.create_sandbox(sandbox_id, self.config)
        
        self.assertIsNotNone(sandbox)
        retrieved_sandbox = self.manager.get_sandbox(sandbox_id)
        self.assertEqual(sandbox, retrieved_sandbox)
    
    def test_plugin_execution(self):
        """测试插件执行"""
        mock_algorithm = MockTestAlgorithm()
        
        result = self.sandbox.execute_plugin(
            mock_algorithm,
            "process",
            "test_data"
        )
        
        self.assertIsNotNone(result)
        self.assertIsInstance(result.success, bool)
        self.assertIsInstance(result.execution_time, float)
    
    def test_resource_limits(self):
        """测试资源限制"""
        config = SandboxConfig(
            level=SandboxLevel.RESTRICTED,
            resource_limits=ResourceLimits(
                max_execution_time=1,  # 1秒超时
                max_memory_mb=64
            )
        )
        
        self.assertEqual(config.resource_limits.max_execution_time, 1)
        self.assertEqual(config.resource_limits.max_memory_mb, 64)
    
    def test_sandbox_manager_operations(self):
        """测试沙箱管理器操作"""
        sandbox_id = "test_manager"
        
        # 创建沙箱
        sandbox = self.manager.create_sandbox(sandbox_id)
        self.assertIsNotNone(sandbox)
        
        # 列出沙箱
        sandboxes = self.manager.list_sandboxes()
        self.assertTrue(any(sid == sandbox_id for sid, _ in sandboxes))
        
        # 移除沙箱
        result = self.manager.remove_sandbox(sandbox_id)
        self.assertTrue(result)
        
        # 确认移除
        retrieved = self.manager.get_sandbox(sandbox_id)
        self.assertIsNone(retrieved)


class TestDynamicLoader(unittest.TestCase):
    """动态加载器测试"""
    
    def setUp(self):
        self.config = LoadingConfig(
            strategy=LoadingStrategy.LAZY,
            sandbox_level=SandboxLevel.BASIC,
            max_concurrent_loads=2
        )
        self.loader = DynamicPluginLoader(self.config)
    
    def tearDown(self):
        self.loader.cleanup()
    
    def test_loading_config(self):
        """测试加载配置"""
        self.assertEqual(self.config.strategy, LoadingStrategy.LAZY)
        self.assertEqual(self.config.sandbox_level, SandboxLevel.BASIC)
        self.assertEqual(self.config.max_concurrent_loads, 2)
    
    def test_discover_plugins(self):
        """测试插件发现"""
        plugin_names = self.loader.discover_plugins()
        self.assertIsInstance(plugin_names, list)
        # 由于是空环境，可能为空列表
    
    def test_plugin_states(self):
        """测试插件状态"""
        # 测试所有状态枚举
        states = [state for state in PluginState]
        self.assertGreater(len(states), 0)
        self.assertIn(PluginState.DISCOVERED, states)
        self.assertIn(PluginState.LOADED, states)
    
    def test_loading_stats(self):
        """测试加载统计"""
        stats = self.loader.get_loading_stats()
        
        self.assertIn("total_plugins", stats)
        self.assertIn("loaded_plugins", stats)
        self.assertIn("error_plugins", stats)
        self.assertIn("plugins_by_state", stats)
        self.assertIsInstance(stats["total_plugins"], int)
    
    def test_lifecycle_hooks(self):
        """测试生命周期钩子"""
        hook_called = {"value": False}
        
        def test_hook(plugin, **kwargs):
            hook_called["value"] = True
        
        self.loader.add_lifecycle_hook("pre_load", test_hook)
        
        # 验证钩子已添加
        self.assertIn(test_hook, self.loader._lifecycle_manager._lifecycle_hooks["pre_load"])
        
        # 移除钩子
        self.loader.remove_lifecycle_hook("pre_load", test_hook)
        self.assertNotIn(test_hook, self.loader._lifecycle_manager._lifecycle_hooks["pre_load"])


class TestPluginMarketplace(unittest.TestCase):
    """插件市场测试"""
    
    def setUp(self):
        self.marketplace = PluginMarketplace()
        self.validator = PluginValidator()
        self.temp_dir = Path(tempfile.mkdtemp())
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_plugin_manifest_creation(self):
        """测试插件清单创建"""
        manifest = PluginManifest(
            name="test_plugin",
            version="1.0.0",
            description="测试插件",
            author="Test Author",
            author_email="test@example.com",
            category=PluginCategory.CUSTOM,
            license=PluginLicense.MIT
        )
        
        self.assertEqual(manifest.name, "test_plugin")
        self.assertEqual(manifest.version, "1.0.0")
        self.assertEqual(manifest.category, PluginCategory.CUSTOM)
        self.assertEqual(manifest.license, PluginLicense.MIT)
    
    def test_manifest_validation(self):
        """测试清单验证"""
        # 有效清单
        valid_manifest = PluginManifest(
            name="valid_plugin",
            version="1.0.0",
            description="有效插件",
            author="Valid Author",
            author_email="valid@example.com"
        )
        
        errors = self.validator.validate_manifest(valid_manifest)
        self.assertEqual(len(errors), 0)
        
        # 无效清单
        invalid_manifest = PluginManifest(
            name="",  # 空名称
            version="invalid.version",  # 无效版本
            description="",  # 空描述
            author="",  # 空作者
            author_email="invalid@example.com"
        )
        
        errors = self.validator.validate_manifest(invalid_manifest)
        self.assertGreater(len(errors), 0)
    
    def test_manifest_serialization(self):
        """测试清单序列化"""
        manifest = PluginManifest(
            name="serialization_test",
            version="1.0.0",
            description="序列化测试",
            author="Test Author",
            author_email="test@example.com"
        )
        
        # 转换为字典
        manifest_dict = manifest.to_dict()
        self.assertIsInstance(manifest_dict, dict)
        self.assertEqual(manifest_dict["name"], "serialization_test")
        
        # 从字典重建
        restored_manifest = PluginManifest.from_dict(manifest_dict)
        self.assertEqual(restored_manifest.name, manifest.name)
        self.assertEqual(restored_manifest.version, manifest.version)
    
    def test_plugin_template_creation(self):
        """测试插件模板创建"""
        plugin_name = "test_template_plugin"
        result = self.marketplace.create_plugin_template(plugin_name, self.temp_dir)
        
        self.assertTrue(result)
        
        # 检查文件是否创建
        template_dir = self.temp_dir / plugin_name
        self.assertTrue(template_dir.exists())
        self.assertTrue((template_dir / "manifest.json").exists())
        self.assertTrue((template_dir / "plugin.py").exists())
        self.assertTrue((template_dir / "README.md").exists())
    
    def test_plugin_packaging(self):
        """测试插件打包"""
        # 先创建模板
        plugin_name = "packaging_test"
        self.marketplace.create_plugin_template(plugin_name, self.temp_dir)
        
        plugin_dir = self.temp_dir / plugin_name
        
        # 打包插件
        package_path = self.marketplace.package_plugin(plugin_dir)
        
        if package_path:  # 如果打包成功
            self.assertTrue(package_path.exists())
            self.assertTrue(package_path.suffix == '.zip')
            
            # 验证ZIP内容
            with zipfile.ZipFile(package_path, 'r') as zip_file:
                files = zip_file.namelist()
                self.assertIn('manifest.json', files)
                self.assertIn('plugin.py', files)
    
    def test_marketplace_stats(self):
        """测试市场统计"""
        stats = self.marketplace.get_marketplace_stats()
        
        self.assertIn("repositories", stats)
        self.assertIn("installed_plugins", stats)
        self.assertIn("repository_list", stats)
        self.assertIn("installed_list", stats)
        self.assertIsInstance(stats["repositories"], int)


class TestIntegration(unittest.TestCase):
    """集成测试"""
    
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.loader = DynamicPluginLoader()
        self.marketplace = PluginMarketplace()
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        self.loader.cleanup()
    
    def test_end_to_end_workflow(self):
        """测试端到端工作流程"""
        # 1. 创建插件模板
        plugin_name = "e2e_test_plugin"
        template_result = self.marketplace.create_plugin_template(plugin_name, self.temp_dir)
        self.assertTrue(template_result)
        
        # 2. 打包插件
        plugin_dir = self.temp_dir / plugin_name
        package_path = self.marketplace.package_plugin(plugin_dir)
        
        if package_path:
            self.assertTrue(package_path.exists())
        
        # 3. 验证组件状态
        discovery_stats = self.loader._discovery_engine.get_discovery_stats()
        self.assertIsInstance(discovery_stats, dict)
        
        resolver_stats = self.loader._dependency_resolver.get_resolver_stats()
        self.assertIsInstance(resolver_stats, dict)
        
        marketplace_stats = self.marketplace.get_marketplace_stats()
        self.assertIsInstance(marketplace_stats, dict)
    
    def test_component_interaction(self):
        """测试组件交互"""
        # 测试发现引擎和加载器的交互
        loader_stats = self.loader.get_loading_stats()
        self.assertIsInstance(loader_stats, dict)
        
        # 测试沙箱管理器
        sandbox_manager = self.loader._sandbox_manager
        sandboxes = sandbox_manager.list_sandboxes()
        self.assertIsInstance(sandboxes, list)
    
    def test_concurrent_operations(self):
        """测试并发操作"""
        def discovery_worker():
            return self.loader.discover_plugins()
        
        def stats_worker():
            return self.loader.get_loading_stats()
        
        # 启动并发操作
        threads = []
        for _ in range(3):
            t1 = threading.Thread(target=discovery_worker)
            t2 = threading.Thread(target=stats_worker)
            threads.extend([t1, t2])
        
        # 启动线程
        for t in threads:
            t.start()
        
        # 等待完成
        for t in threads:
            t.join(timeout=5.0)  # 5秒超时
        
        # 验证系统仍然正常
        final_stats = self.loader.get_loading_stats()
        self.assertIsInstance(final_stats, dict)


def run_phase_6_4_tests():
    """运行Phase 6.4的所有测试"""
    # 创建测试套件
    test_suite = unittest.TestSuite()
    
    # 添加所有测试类
    test_classes = [
        TestPluginDiscovery,
        TestDependencyResolver,
        TestPluginSandbox,
        TestDynamicLoader,
        TestPluginMarketplace,
        TestIntegration
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # 打印统计信息
    print(f"\n{'='*60}")
    print("Phase 6.4 动态加载系统测试完成")
    print(f"{'='*60}")
    print(f"总测试数: {result.testsRun}")
    print(f"成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失败: {len(result.failures)}")
    print(f"错误: {len(result.errors)}")
    print(f"成功率: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    
    if result.failures:
        print(f"\n失败的测试:")
        for test, traceback in result.failures:
            print(f"  - {test}")
    
    if result.errors:
        print(f"\n错误的测试:")
        for test, traceback in result.errors:
            print(f"  - {test}")
    
    print(f"{'='*60}")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_phase_6_4_tests()
    exit(0 if success else 1) 