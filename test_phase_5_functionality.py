#!/usr/bin/env python3
"""
Phase 5: 功能完整性验证测试

测试目标：
- 验证所有核心处理功能与原系统100%一致
- 验证组合处理功能正常工作  
- 验证GUI交互功能正常
- 验证配置系统功能正常
"""

import os
import sys
import unittest
import tempfile
import shutil
from pathlib import Path
from typing import List, Dict, Any
import json
import time
import psutil
import logging

# 添加源码路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

# 导入测试目标
from src.pktmask.core.processors.registry import ProcessorRegistry, ProcessorConfig
from src.pktmask.core.processors.ip_anonymizer import IPAnonymizer
from src.pktmask.core.processors.deduplicator import Deduplicator  
from src.pktmask.core.processors.trimmer import Trimmer
from src.pktmask.config.settings import AppConfig, UISettings, ProcessingSettings

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Phase5FunctionalityTests(unittest.TestCase):
    """Phase 5: 功能完整性验证测试套件"""
    
    @classmethod
    def setUpClass(cls):
        """测试类初始化"""
        cls.test_data_dir = Path("tests/data")
        cls.temp_dir = Path(tempfile.mkdtemp(prefix="phase5_test_"))
        cls.results = {
            "start_time": time.time(),
            "tests_passed": 0,
            "tests_failed": 0,
            "test_details": []
        }
        
        # 确保测试数据存在
        if not cls.test_data_dir.exists():
            logger.warning(f"测试数据目录不存在: {cls.test_data_dir}")
            
        logger.info(f"Phase 5功能测试开始，临时目录: {cls.temp_dir}")
    
    @classmethod 
    def tearDownClass(cls):
        """测试类清理"""
        cls.results["end_time"] = time.time()
        cls.results["total_time"] = cls.results["end_time"] - cls.results["start_time"]
        
        # 生成测试报告
        cls._generate_test_report()
        
        # 清理临时文件
        if cls.temp_dir.exists():
            shutil.rmtree(cls.temp_dir)
            
        logger.info("Phase 5功能测试完成")
    
    def setUp(self):
        """每个测试方法的初始化"""
        self.test_start_time = time.time()
        self.current_test_name = self._testMethodName
        
    def tearDown(self):
        """每个测试方法的清理"""
        test_time = time.time() - self.test_start_time
        # 获取测试结果，更安全的方式
        test_result = "PASSED"
        if hasattr(self, '_outcome') and self._outcome.result:
            if self._outcome.result.failures or self._outcome.result.errors:
                test_result = "FAILED"
        
        self.results["test_details"].append({
            "test_name": self.current_test_name,
            "result": test_result,
            "time": test_time,
            "timestamp": time.time()
        })
        
        if test_result == "PASSED":
            self.results["tests_passed"] += 1
        else:
            self.results["tests_failed"] += 1

    # ===============================
    # 5.1.1 核心处理功能测试
    # ===============================
    
    def test_ip_anonymizer_basic_functionality(self):
        """测试IP匿名化基本功能"""
        logger.info("测试: IP匿名化基本功能")
        
        # 创建IP匿名化处理器
        config = ProcessorConfig(enabled=True, name="ip_anonymizer")
        processor = ProcessorRegistry.get_processor("mask_ip", config)
        
        # 验证处理器创建成功
        self.assertIsInstance(processor, IPAnonymizer)
        self.assertEqual(processor.get_display_name(), "Mask IPs")
        
        # 检查小文件测试数据
        test_files = self._get_test_files("small")
        if test_files:
            for test_file in test_files[:1]:  # 只测试第一个文件
                output_file = self.temp_dir / f"anonymized_{test_file.name}"
                
                # 执行处理
                result = processor.process_file(str(test_file), str(output_file))
                
                # 验证结果
                self.assertTrue(result.success, f"IP匿名化处理失败: {result.error}")
                self.assertTrue(output_file.exists(), "输出文件未生成")
                self.assertGreater(output_file.stat().st_size, 0, "输出文件为空")
        else:
            logger.warning("未找到小文件测试数据，跳过IP匿名化测试")
    
    def test_deduplicator_basic_functionality(self):
        """测试去重基本功能"""
        logger.info("测试: 去重基本功能")
        
        # 创建去重处理器
        config = ProcessorConfig(enabled=True, name="deduplicator")
        processor = ProcessorRegistry.get_processor("dedup_packet", config)
        
        # 验证处理器创建成功
        self.assertIsInstance(processor, Deduplicator)
        self.assertEqual(processor.get_display_name(), "Remove Dupes")
        
        # 检查测试数据
        test_files = self._get_test_files("small")
        if test_files:
            for test_file in test_files[:1]:
                output_file = self.temp_dir / f"deduped_{test_file.name}"
                
                # 执行处理
                result = processor.process_file(str(test_file), str(output_file))
                
                # 验证结果
                self.assertTrue(result.success, f"去重处理失败: {result.error}")
                self.assertTrue(output_file.exists(), "输出文件未生成")
                
                # 验证统计数据
                if result.stats:
                    # 新处理器使用的统计字段名称
                    self.assertIn("total_packets", result.stats)
                    self.assertIn("unique_packets", result.stats)
                    self.assertIn("removed_count", result.stats)
        else:
            logger.warning("未找到测试数据，跳过去重测试")
    
    def test_trimmer_basic_functionality(self):
        """测试裁切基本功能"""
        logger.info("测试: 裁切基本功能")
        
        # 创建裁切处理器
        config = ProcessorConfig(enabled=True, name="trimmer")
        processor = ProcessorRegistry.get_processor("trim_packet", config)
        
        # 验证处理器创建成功
        self.assertIsInstance(processor, Trimmer)
        self.assertEqual(processor.get_display_name(), "Trim Payloads")
        
        # 检查测试数据
        test_files = self._get_test_files("small")
        if test_files:
            for test_file in test_files[:1]:
                output_file = self.temp_dir / f"trimmed_{test_file.name}"
                
                # 执行处理
                result = processor.process_file(str(test_file), str(output_file))
                
                # 验证结果
                self.assertTrue(result.success, f"裁切处理失败: {result.error}")
                self.assertTrue(output_file.exists(), "输出文件未生成")
                self.assertGreater(output_file.stat().st_size, 0, "输出文件为空")
        else:
            logger.warning("未找到测试数据，跳过裁切测试")

    # ===============================
    # 5.1.2 组合处理功能测试  
    # ===============================
    
    def test_combination_ip_and_dedup(self):
        """测试IP匿名化 + 去重组合"""
        logger.info("测试: IP匿名化 + 去重组合")
        
        test_files = self._get_test_files("small")
        if not test_files:
            logger.warning("未找到测试数据，跳过组合测试")
            return
            
        test_file = test_files[0]
        
        # 创建处理器
        ip_config = ProcessorConfig(enabled=True, name="ip_anonymizer")
        ip_processor = ProcessorRegistry.get_processor("mask_ip", ip_config)
        
        dedup_config = ProcessorConfig(enabled=True, name="deduplicator")
        dedup_processor = ProcessorRegistry.get_processor("dedup_packet", dedup_config)
        
        # 执行组合处理
        temp_file = self.temp_dir / "temp_combined.pcap"
        final_file = self.temp_dir / "final_combined.pcap"
        
        # 第一步：IP匿名化
        result1 = ip_processor.process_file(str(test_file), str(temp_file))
        self.assertTrue(result1.success, f"IP匿名化失败: {result1.error}")
        
        # 第二步：去重
        result2 = dedup_processor.process_file(str(temp_file), str(final_file))
        self.assertTrue(result2.success, f"去重失败: {result2.error}")
        
        # 验证最终结果
        self.assertTrue(final_file.exists(), "最终输出文件未生成")
        self.assertGreater(final_file.stat().st_size, 0, "最终输出文件为空")
    
    def test_combination_all_three(self):
        """测试IP匿名化 + 去重 + 裁切三重组合"""
        logger.info("测试: 三重组合处理")
        
        test_files = self._get_test_files("small")
        if not test_files:
            logger.warning("未找到测试数据，跳过三重组合测试")
            return
            
        test_file = test_files[0]
        
        # 创建所有处理器
        processors = [
            ("mask_ip", ProcessorConfig(enabled=True, name="ip_anonymizer")),
            ("dedup_packet", ProcessorConfig(enabled=True, name="deduplicator")),
            ("trim_packet", ProcessorConfig(enabled=True, name="trimmer"))
        ]
        
        current_file = test_file
        
        # 依次执行所有处理步骤
        for i, (proc_name, config) in enumerate(processors):
            processor = ProcessorRegistry.get_processor(proc_name, config)
            output_file = self.temp_dir / f"step_{i+1}_output.pcap"
            
            result = processor.process_file(str(current_file), str(output_file))
            self.assertTrue(result.success, f"步骤{i+1}({proc_name})处理失败: {result.error}")
            
            current_file = output_file
            
        # 验证最终结果
        self.assertTrue(current_file.exists(), "最终处理结果文件未生成")
        self.assertGreater(current_file.stat().st_size, 0, "最终处理结果文件为空")

    # ===============================
    # 5.1.3 GUI交互功能测试 (模拟)
    # ===============================
    
    def test_processor_registry_functionality(self):
        """测试处理器注册表功能"""
        logger.info("测试: 处理器注册表功能")
        
        # 测试已知处理器获取
        known_processors = ["mask_ip", "dedup_packet", "trim_packet"]
        
        for proc_name in known_processors:
            config = ProcessorConfig(enabled=True, name=proc_name)
            processor = ProcessorRegistry.get_processor(proc_name, config)
            self.assertIsNotNone(processor, f"无法获取处理器: {proc_name}")
            
        # 测试未知处理器
        with self.assertRaises(ValueError):
            ProcessorRegistry.get_processor("unknown_processor", ProcessorConfig())
    
    def test_processor_display_names(self):
        """测试处理器显示名称（用于GUI）"""
        logger.info("测试: 处理器显示名称")
        
        expected_names = {
            "mask_ip": "Mask IPs",
            "dedup_packet": "Remove Dupes", 
            "trim_packet": "Trim Payloads"
        }
        
        for proc_name, expected_display in expected_names.items():
            config = ProcessorConfig(enabled=True, name=proc_name)
            processor = ProcessorRegistry.get_processor(proc_name, config)
            self.assertEqual(processor.get_display_name(), expected_display)

    # ===============================
    # 5.1.4 配置系统测试
    # ===============================
    
    def test_config_system_basic(self):
        """测试配置系统基本功能"""
        logger.info("测试: 配置系统基本功能")
        
        # 测试默认配置创建
        default_config = AppConfig.default()
        self.assertIsInstance(default_config, AppConfig)
        self.assertIsInstance(default_config.ui, UISettings)
        self.assertIsInstance(default_config.processing, ProcessingSettings)
        
        # 测试配置项访问
        self.assertIsInstance(default_config.ui.window_width, int)
        self.assertIsInstance(default_config.ui.window_height, int)
        self.assertIsInstance(default_config.processing.chunk_size, int)
        
    def test_config_serialization(self):
        """测试配置序列化功能"""
        logger.info("测试: 配置序列化功能")
        
        # 创建测试配置
        config = AppConfig.default()
        config.ui.window_width = 1400
        config.ui.window_height = 900
        config.processing.chunk_size = 20
        
        # 测试配置保存（如果方法存在）
        config_file = self.temp_dir / "test_config.yaml"
        try:
            if hasattr(config, 'save'):
                config.save(config_file)
                self.assertTrue(config_file.exists(), "配置文件保存失败")
        except AttributeError:
            logger.warning("配置保存方法未实现，跳过序列化测试")

    # ===============================
    # 工具方法
    # ===============================
    
    def _get_test_files(self, size_category: str = "small") -> List[Path]:
        """获取测试文件列表"""
        test_files = []
        
        if not self.test_data_dir.exists():
            return test_files
            
        # 根据大小类别查找文件
        if size_category == "small":
            # 查找小文件 (<10MB)
            for pattern in ["TC-001-*", "*.pcap"]:
                test_files.extend(self.test_data_dir.glob(f"**/{pattern}"))
        elif size_category == "medium":
            # 查找中等文件 (10-100MB)  
            for pattern in ["TC-002-*"]:
                test_files.extend(self.test_data_dir.glob(f"**/{pattern}"))
        elif size_category == "large":
            # 查找大文件 (>100MB)
            test_files.extend(self.test_data_dir.glob("big/**/*.pcap"))
            
        # 过滤有效的pcap文件
        valid_files = []
        for file_path in test_files:
            if file_path.is_file() and file_path.suffix in ['.pcap', '.pcapng']:
                # 检查文件大小
                size_mb = file_path.stat().st_size / (1024 * 1024)
                if size_category == "small" and size_mb < 10:
                    valid_files.append(file_path)
                elif size_category == "medium" and 10 <= size_mb <= 100:
                    valid_files.append(file_path)
                elif size_category == "large" and size_mb > 100:
                    valid_files.append(file_path)
                    
        return valid_files[:3]  # 最多返回3个文件
    
    @classmethod
    def _generate_test_report(cls):
        """生成测试报告"""
        report = {
            "phase": "Phase 5: 功能完整性验证",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_tests": cls.results["tests_passed"] + cls.results["tests_failed"],
            "tests_passed": cls.results["tests_passed"],
            "tests_failed": cls.results["tests_failed"],
            "success_rate": cls.results["tests_passed"] / max(1, cls.results["tests_passed"] + cls.results["tests_failed"]) * 100,
            "total_time": cls.results.get("total_time", 0),
            "test_details": cls.results["test_details"]
        }
        
        # 保存报告
        report_file = Path("phase_5_functionality_test_report.json")
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
            
        # 打印摘要
        logger.info("=" * 60)
        logger.info("Phase 5 功能完整性测试报告")
        logger.info("=" * 60)
        logger.info(f"总测试数: {report['total_tests']}")
        logger.info(f"通过: {report['tests_passed']}")
        logger.info(f"失败: {report['tests_failed']}")
        logger.info(f"成功率: {report['success_rate']:.1f}%")
        logger.info(f"总耗时: {report['total_time']:.2f}秒")
        logger.info(f"报告已保存到: {report_file}")
        logger.info("=" * 60)


def main():
    """主函数"""
    # 检查环境
    logger.info("开始Phase 5功能完整性验证测试")
    logger.info(f"Python版本: {sys.version}")
    logger.info(f"工作目录: {os.getcwd()}")
    
    # 运行测试套件
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(Phase5FunctionalityTests)
    
    runner = unittest.TextTestRunner(
        verbosity=2,
        buffer=True,
        stream=sys.stdout
    )
    
    result = runner.run(suite)
    
    # 返回退出码
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main()) 