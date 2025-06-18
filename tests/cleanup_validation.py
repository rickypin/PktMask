#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Legacy Steps 清理验证测试

验证Legacy Steps清理后系统的功能完整性。
"""

import sys
import unittest
import tempfile
import os
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

class LegacyCleanupValidationTest(unittest.TestCase):
    """Legacy清理验证测试"""
    
    def setUp(self):
        """测试准备"""
        self.temp_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """测试清理"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_legacy_files_removed(self):
        """验证Legacy文件已被移除"""
        legacy_files = [
            "src/pktmask/steps/__init__.py",
            "src/pktmask/steps/deduplication.py",
            "src/pktmask/steps/ip_anonymization.py", 
            "src/pktmask/steps/trimming.py"
        ]
        
        project_root = Path(__file__).parent.parent
        
        for file_path in legacy_files:
            full_path = project_root / file_path
            self.assertFalse(full_path.exists(), 
                           f"Legacy文件仍然存在: {file_path}")
        
        # 验证整个steps目录已移除
        steps_dir = project_root / "src/pktmask/steps"
        self.assertFalse(steps_dir.exists(), 
                        "Legacy steps目录仍然存在")
    
    def test_processor_registry_functional(self):
        """验证ProcessorRegistry功能正常"""
        from pktmask.core.processors import ProcessorRegistry, ProcessorConfig
        
        # 测试获取处理器列表
        processors = ProcessorRegistry.list_processors()
        self.assertIsInstance(processors, list)
        self.assertGreater(len(processors), 0, "处理器列表为空")
        
        expected_processors = ['mask_ip', 'dedup_packet', 'trim_packet']
        for proc in expected_processors:
            self.assertIn(proc, processors, f"缺少预期处理器: {proc}")
        
        # 测试增强模式检测
        enhanced = ProcessorRegistry.is_enhanced_mode_enabled()
        self.assertIsInstance(enhanced, bool)
        
        # 测试处理器创建
        for proc_name in processors:
            config = ProcessorConfig(name=proc_name)
            processor = ProcessorRegistry.get_processor(proc_name, config)
            self.assertIsNotNone(processor, f"处理器创建失败: {proc_name}")
            self.assertTrue(hasattr(processor, 'process_file'), 
                          f"处理器缺少process_file方法: {proc_name}")
    
    def test_processor_adapter_compatibility(self):
        """验证ProcessorAdapter向后兼容性"""
        from pktmask.core.processors import ProcessorRegistry, ProcessorConfig
        from pktmask.core.processors.pipeline_adapter import ProcessorAdapter, adapt_processors_to_pipeline
        
        # 创建处理器实例
        config = ProcessorConfig(name='dedup_packet')
        processor = ProcessorRegistry.get_processor('dedup_packet', config)
        
        # 测试适配器包装
        adapter = ProcessorAdapter(processor)
        self.assertTrue(hasattr(adapter, 'name'), "适配器缺少name属性")
        self.assertTrue(hasattr(adapter, 'suffix'), "适配器缺少suffix属性")
        self.assertTrue(hasattr(adapter, 'process_file'), "适配器缺少process_file方法")
        
        # 测试批量适配
        processors = [
            ProcessorRegistry.get_processor('mask_ip', ProcessorConfig(name='mask_ip')),
            ProcessorRegistry.get_processor('dedup_packet', ProcessorConfig(name='dedup_packet'))
        ]
        steps = adapt_processors_to_pipeline(processors)
        self.assertEqual(len(steps), 2, "批量适配失败")
        
    def test_factory_compatibility_stubs(self):
        """验证Factory兼容性存根"""
        from pktmask.core.factory import create_pipeline, get_step_instance, STEP_REGISTRY
        
        # 测试create_pipeline存根
        pipeline = create_pipeline([])
        self.assertIsNotNone(pipeline, "create_pipeline存根失败")
        
        # 测试get_step_instance存根
        with self.assertRaises(NotImplementedError):
            get_step_instance("any_step")
        
        # 测试STEP_REGISTRY存根  
        self.assertIsInstance(STEP_REGISTRY, dict, "STEP_REGISTRY存根失败")
    
    def test_pipeline_integration(self):
        """验证Pipeline集成功能"""
        from pktmask.core.pipeline import Pipeline
        from pktmask.core.processors import ProcessorRegistry, ProcessorConfig
        from pktmask.core.processors.pipeline_adapter import adapt_processors_to_pipeline
        
        # 创建处理器并适配为步骤
        processors = []
        processor_names = ['mask_ip', 'dedup_packet']
        
        for name in processor_names:
            config = ProcessorConfig(name=name)
            processor = ProcessorRegistry.get_processor(name, config)
            processors.append(processor)
        
        steps = adapt_processors_to_pipeline(processors)
        
        # 创建Pipeline
        pipeline = Pipeline(steps)
        self.assertIsNotNone(pipeline, "Pipeline创建失败")
        self.assertEqual(len(pipeline._steps), 2, "Pipeline步骤数量错误")
    
    def test_gui_integration_paths(self):
        """验证GUI集成路径"""
        try:
            # 测试PipelineManager导入
            from pktmask.gui.managers.pipeline_manager import PipelineManager
            self.assertTrue(hasattr(PipelineManager, '_build_pipeline_steps'), 
                          "PipelineManager缺少_build_pipeline_steps方法")
            
            # 测试关键导入路径
            from pktmask.core.processors import ProcessorRegistry, ProcessorConfig, adapt_processors_to_pipeline
            self.assertIsNotNone(ProcessorRegistry)
            self.assertIsNotNone(ProcessorConfig)
            self.assertIsNotNone(adapt_processors_to_pipeline)
            
        except ImportError as e:
            self.fail(f"GUI集成导入失败: {e}")
    
    def test_no_legacy_imports_remain(self):
        """验证没有残留的Legacy导入"""
        import subprocess
        
        project_root = Path(__file__).parent.parent
        
        # 搜索可能的Legacy导入
        try:
            result = subprocess.run(
                ["grep", "-r", "from.*steps.*import", "src/pktmask/core/processors/"],
                cwd=project_root,
                capture_output=True,
                text=True
            )
            
            # 如果grep找到了匹配，检查是否为Legacy导入
            if result.returncode == 0 and result.stdout.strip():
                legacy_imports = [line for line in result.stdout.split('\n') 
                                if 'from ...steps' in line or 'from ..steps' in line]
                
                self.assertEqual(len(legacy_imports), 0, 
                               f"发现残留的Legacy导入: {legacy_imports}")
                
        except subprocess.CalledProcessError:
            # grep没有找到匹配，这是好事
            pass
    
    def test_enhanced_trimmer_functionality(self):
        """验证Enhanced Trimmer功能"""
        from pktmask.core.processors import ProcessorRegistry, ProcessorConfig
        
        # 获取载荷裁切处理器
        config = ProcessorConfig(name='trim_packet')
        trimmer = ProcessorRegistry.get_processor('trim_packet', config)
        
        # 验证是Enhanced版本
        self.assertEqual(trimmer.__class__.__name__, 'EnhancedTrimmer', 
                        "载荷裁切器不是Enhanced版本")
        
        # 验证增强模式
        enhanced_mode = ProcessorRegistry.is_enhanced_mode_enabled()
        self.assertTrue(enhanced_mode, "增强模式未启用")
    
    def test_ip_anonymization_functionality(self):
        """验证IP匿名化功能"""
        from pktmask.core.processors import ProcessorRegistry, ProcessorConfig
        
        # 获取IP匿名化处理器
        config = ProcessorConfig(name='mask_ip')
        anonymizer = ProcessorRegistry.get_processor('mask_ip', config)
        
        # 验证是现代版本
        self.assertEqual(anonymizer.__class__.__name__, 'IPAnonymizer',
                        "IP匿名化器不是现代版本")
        
        # 验证有必要的方法
        self.assertTrue(hasattr(anonymizer, 'process_file'),
                       "IP匿名化器缺少process_file方法")
    
    def test_deduplication_functionality(self):
        """验证去重功能"""
        from pktmask.core.processors import ProcessorRegistry, ProcessorConfig
        
        # 获取去重处理器
        config = ProcessorConfig(name='dedup_packet')
        deduplicator = ProcessorRegistry.get_processor('dedup_packet', config)
        
        # 验证是现代版本
        self.assertEqual(deduplicator.__class__.__name__, 'Deduplicator',
                        "去重器不是现代版本")
        
        # 验证有必要的方法
        self.assertTrue(hasattr(deduplicator, 'process_file'),
                       "去重器缺少process_file方法")

class PerformanceRegressionTest(unittest.TestCase):
    """性能回归测试"""
    
    def test_processor_creation_performance(self):
        """测试处理器创建性能"""
        import time
        from pktmask.core.processors import ProcessorRegistry, ProcessorConfig
        
        start_time = time.time()
        
        # 创建多个处理器实例
        for _ in range(10):
            for proc_name in ['mask_ip', 'dedup_packet', 'trim_packet']:
                config = ProcessorConfig(name=proc_name)
                processor = ProcessorRegistry.get_processor(proc_name, config)
                self.assertIsNotNone(processor)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # 性能基准：30个处理器创建应该在1秒内完成
        self.assertLess(duration, 1.0, 
                       f"处理器创建性能下降，耗时: {duration:.2f}s")
    
    def test_registry_lookup_performance(self):
        """测试注册表查找性能"""
        import time
        from pktmask.core.processors import ProcessorRegistry
        
        start_time = time.time()
        
        # 大量查找操作
        for _ in range(1000):
            processors = ProcessorRegistry.list_processors()
            self.assertGreater(len(processors), 0)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # 性能基准：1000次查找应该在0.1秒内完成
        self.assertLess(duration, 0.1,
                       f"注册表查找性能下降，耗时: {duration:.2f}s")

def run_validation_tests():
    """运行验证测试"""
    print("🧪 开始运行Legacy Steps清理验证测试")
    print("="*50)
    
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 添加验证测试
    suite.addTest(loader.loadTestsFromTestCase(LegacyCleanupValidationTest))
    suite.addTest(loader.loadTestsFromTestCase(PerformanceRegressionTest))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 输出结果
    print("\n" + "="*50)
    print("🧪 验证测试结果")
    print("="*50)
    
    if result.wasSuccessful():
        print("✅ 所有验证测试通过!")
        print("✅ Legacy Steps清理成功，系统功能完整")
        return True
    else:
        print("❌ 验证测试失败!")
        print(f"❌ 失败测试数: {len(result.failures)}")
        print(f"❌ 错误测试数: {len(result.errors)}")
        
        if result.failures:
            print("\n💥 测试失败详情:")
            for test, traceback in result.failures:
                print(f"  - {test}: {traceback}")
        
        if result.errors:
            print("\n💥 测试错误详情:")
            for test, traceback in result.errors:
                print(f"  - {test}: {traceback}")
        
        return False

if __name__ == "__main__":
    success = run_validation_tests()
    sys.exit(0 if success else 1) 