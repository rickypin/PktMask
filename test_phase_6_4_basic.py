#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Phase 6.4 基础功能测试
测试核心组件的基本功能
"""

import unittest
import tempfile
import shutil
from pathlib import Path

# 导入测试目标
from src.pktmask.algorithms.registry.plugin_discovery import (
    PluginDiscoveryEngine, PluginCandidate, PluginSource, PluginScanner
)
from src.pktmask.algorithms.interfaces.algorithm_interface import (
    AlgorithmInterface, AlgorithmInfo, AlgorithmType
)


class MockSimpleAlgorithm(AlgorithmInterface):
    """简单的测试算法"""
    
    def get_algorithm_info(self) -> AlgorithmInfo:
        from src.pktmask.algorithms.interfaces.algorithm_interface import AlgorithmInfo
        return AlgorithmInfo(
            name="MockSimpleAlgorithm",
            version="1.0.0",
            description="简单测试算法",
            algorithm_type=AlgorithmType.CUSTOM,
            author="Test Author",
            supported_formats=["pcap", "json"],
            requirements={}
        )
    
    def get_default_config(self):
        from src.pktmask.algorithms.interfaces.algorithm_interface import AlgorithmConfig
        return AlgorithmConfig()
    
    def validate_config(self, config):
        from src.pktmask.algorithms.interfaces.algorithm_interface import ValidationResult
        return ValidationResult(is_valid=True)
    
    def _apply_config(self, config):
        return True
    
    def _do_initialize(self):
        return True
    
    def _do_cleanup(self):
        pass
    
    def get_performance_metrics(self):
        return {"processed_count": 0, "total_time": 0.0}
    
    def _do_reset_metrics(self):
        pass
    
    def process(self, data, **kwargs):
        return f"Processed: {data}"


class TestBasicFunctionality(unittest.TestCase):
    """基础功能测试"""
    
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_plugin_source_creation(self):
        """测试插件源创建"""
        source = PluginSource(
            path=self.temp_dir,
            source_type="directory",
            name="test_source",
            priority=5
        )
        
        self.assertEqual(source.name, "test_source")
        self.assertEqual(source.priority, 5)
        self.assertEqual(source.source_type, "directory")
        self.assertTrue(source.enabled)
    
    def test_plugin_candidate_creation(self):
        """测试插件候选项创建"""
        candidate = PluginCandidate(
            module_path="test.module",
            file_path=Path("test.py")
        )
        
        self.assertEqual(candidate.module_path, "test.module")
        self.assertEqual(candidate.file_path, Path("test.py"))
        self.assertFalse(candidate.is_valid)
    
    def test_discovery_engine_creation(self):
        """测试发现引擎创建"""
        engine = PluginDiscoveryEngine()
        
        self.assertIsNotNone(engine)
        
        # 测试基本方法
        sources = engine.get_sources()
        self.assertIsInstance(sources, list)
        
        stats = engine.get_discovery_stats()
        self.assertIsInstance(stats, dict)
        self.assertIn("total_sources", stats)
        
        # 清理
        engine.cleanup()
    
    def test_plugin_scanner_creation(self):
        """测试插件扫描器创建"""
        scanner = PluginScanner()
        
        self.assertIsNotNone(scanner)
        
        # 测试扫描空目录
        candidates = scanner.scan_directory(self.temp_dir)
        self.assertEqual(len(candidates), 0)
    
    def test_algorithm_interface(self):
        """测试算法接口"""
        algorithm = MockSimpleAlgorithm()
        
        # 测试基本方法
        info = algorithm.get_algorithm_info()
        self.assertEqual(info.name, "MockSimpleAlgorithm")
        self.assertEqual(info.version, "1.0.0")
        
        # 测试处理方法
        result = algorithm.process("test_data")
        self.assertEqual(result, "Processed: test_data")
        
        # 测试清理方法
        algorithm.cleanup()  # 应该不抛出异常


def run_basic_tests():
    """运行基础测试"""
    test_suite = unittest.TestSuite()
    
    # 添加测试类
    tests = unittest.TestLoader().loadTestsFromTestCase(TestBasicFunctionality)
    test_suite.addTests(tests)
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # 打印结果
    print(f"\n{'='*50}")
    print("Phase 6.4 基础功能测试完成")
    print(f"{'='*50}")
    print(f"总测试数: {result.testsRun}")
    print(f"成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失败: {len(result.failures)}")
    print(f"错误: {len(result.errors)}")
    
    if result.failures:
        print(f"\n失败的测试:")
        for test, traceback in result.failures:
            print(f"  - {test}: {traceback}")
    
    if result.errors:
        print(f"\n错误的测试:")
        for test, traceback in result.errors:
            print(f"  - {test}: {traceback}")
    
    print(f"{'='*50}")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_basic_tests()
    exit(0 if success else 1) 