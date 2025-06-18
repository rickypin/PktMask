"""
PktMask 集中性能测试模块

整合分散在各个测试文件中的性能测试，提供统一的性能基准和测试标准。
根据重复测试项分析报告的建议创建。
"""
import unittest
import tempfile
import os
from unittest.mock import patch, Mock

import pytest

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from conftest import PerformanceTestSuite, BasePcapProcessingTest, ErrorHandlingTestMixin

# 导入需要测试的模块
try:
    from src.pktmask.core.processors import EnhancedTrimmer, _process_pcap_data_enhanced, _process_pcap_data
    from src.pktmask.core.encapsulation.adapter import ProcessingAdapter
    from src.pktmask.infrastructure.logging import log_performance
except ImportError as e:
    pytest.skip(f"无法导入模块: {e}", allow_module_level=True)


@pytest.mark.performance
class TestCentralizedPerformance(unittest.TestCase):
    """集中性能测试类
    
    将分散在各个测试文件中的性能测试整合到这里，
    提供统一的性能基准和测试标准。
    """
    
    def setUp(self):
        """设置测试环境"""
        self.performance_suite = PerformanceTestSuite()
        self.pcap_test_base = BasePcapProcessingTest()
        self.adapter = ProcessingAdapter()
    
    def tearDown(self):
        """清理测试环境"""
        if hasattr(self, 'adapter'):
            self.adapter.reset_stats()
    
    def test_pcap_data_processing_performance_benchmark(self):
        """PCAP数据处理性能基准测试"""
        # 创建不同大小的测试数据集
        test_cases = [
            ("small", BasePcapProcessingTest.create_test_packets("plain"), 2),
            ("medium", BasePcapProcessingTest.create_test_packets("mixed") * 5, 10),
            ("large", BasePcapProcessingTest.create_test_packets("vlan") * 25, 50),
        ]
        
        for case_name, packets, expected_count in test_cases:
            with self.subTest(case=case_name):
                # 基础版本性能测试
                basic_result = PerformanceTestSuite.measure_processing_performance(
                    _process_pcap_data,
                    packets,
                    iterations=3
                )
                
                # 增强版本性能测试
                enhanced_result = PerformanceTestSuite.measure_processing_performance(
                    lambda p: _process_pcap_data_enhanced(p, self.adapter),
                    packets,
                    iterations=3
                )
                
                # 验证性能报告
                PerformanceTestSuite.verify_performance_report(basic_result)
                PerformanceTestSuite.verify_performance_report(enhanced_result)
                
                # 验证性能阈值
                if case_name == "small":
                    PerformanceTestSuite.assert_performance_threshold(
                        basic_result["avg_time"], "processing_time"
                    )
                    PerformanceTestSuite.assert_performance_threshold(
                        enhanced_result["avg_time"], "processing_time"
                    )
                elif case_name == "medium":
                    PerformanceTestSuite.assert_performance_threshold(
                        basic_result["avg_time"], "small_file_processing"
                    )
                    PerformanceTestSuite.assert_performance_threshold(
                        enhanced_result["avg_time"], "small_file_processing"
                    )
                
                # 性能比较分析
                comparison = PerformanceTestSuite.compare_performance(
                    basic_result, enhanced_result, tolerance=0.2  # 允许20%性能差异
                )
                
                # 记录性能比较结果
                print(f"\n性能比较 - {case_name}:")
                print(f"  基础版本: {basic_result['avg_time']:.4f}s")
                print(f"  增强版本: {enhanced_result['avg_time']:.4f}s")
                print(f"  性能比率: {comparison['performance_ratio']:.2f}")
                
                # 增强版本性能不应显著劣化（超过50%）
                self.assertLess(comparison['performance_ratio'], 1.5, 
                               f"{case_name} 增强版本性能劣化过多")
    
    def test_file_processing_performance_benchmark(self):
        """文件处理性能基准测试"""
        test_packets = BasePcapProcessingTest.create_test_packets("mixed") * 10
        
        # 创建临时文件
        input_path = BasePcapProcessingTest.create_temp_pcap_file(test_packets)
        output_path = input_path.replace('.pcap', '_output.pcap')
        
        try:
            # 文件处理性能测试
            def file_processing_func(_):
                step = IntelligentTrimmingStep()
                return step.process_file(input_path, output_path)
            
            performance_result = PerformanceTestSuite.measure_processing_performance(
                file_processing_func,
                None,
                iterations=3
            )
            
            # 验证性能报告
            PerformanceTestSuite.verify_performance_report(performance_result)
            
            # 验证性能阈值
            PerformanceTestSuite.assert_performance_threshold(
                performance_result["avg_time"],
                "small_file_processing"
            )
            
            # 验证结果正确性
            results = performance_result["results"]
            for result in results:
                self.assertIsNotNone(result)
                self.assertIn("total_packets", result)
                self.assertEqual(result["total_packets"], 20)  # 10个混合包 * 2包/混合
                
        finally:
            BasePcapProcessingTest.cleanup_temp_file(input_path)
            BasePcapProcessingTest.cleanup_temp_file(output_path)
    
    def test_performance_logging_overhead(self):
        """性能日志开销测试"""
        packets = BasePcapProcessingTest.create_test_packets("plain")
        
        # 测试无日志情况
        no_log_result = PerformanceTestSuite.measure_processing_performance(
            _process_pcap_data,
            packets,
            iterations=10
        )
        
        # 测试有日志情况（模拟）
        def processing_with_logging(data):
            with patch('src.pktmask.infrastructure.logging.log_performance'):
                return _process_pcap_data(data)
        
        with_log_result = PerformanceTestSuite.measure_processing_performance(
            processing_with_logging,
            packets,
            iterations=10
        )
        
        # 验证日志开销在可接受范围内（<10%）
        comparison = PerformanceTestSuite.compare_performance(
            no_log_result, with_log_result, tolerance=0.1
        )
        
        self.assertLess(comparison['performance_ratio'], 1.1,
                       "性能日志开销过大")
        
        print(f"\n性能日志开销分析:")
        print(f"  无日志: {no_log_result['avg_time']:.4f}s")
        print(f"  有日志: {with_log_result['avg_time']:.4f}s")
        print(f"  开销比率: {comparison['performance_ratio']:.2f}")
    
    def test_memory_efficiency_benchmark(self):
        """内存效率基准测试"""
        # 创建大数据集
        large_packets = BasePcapProcessingTest.create_test_packets("mixed") * 100
        
        # 重置适配器统计
        self.adapter.reset_stats()
        
        # 测试内存使用（模拟）
        def memory_test_func(data):
            # 模拟大数据处理
            result = _process_pcap_data_enhanced(data, self.adapter)
            
            # 验证统计信息正确累计
            stats = self.adapter.get_processing_stats()
            BasePcapProcessingTest.verify_encapsulation_stats(
                stats, 
                expected_total=200,  # 100个混合包 * 2包/混合
                expected_encap_count=100  # 混合包中一半是VLAN
            )
            
            return result
        
        # 执行内存效率测试
        memory_result = PerformanceTestSuite.measure_processing_performance(
            memory_test_func,
            large_packets,
            iterations=1  # 大数据集只运行一次
        )
        
        # 验证性能在大数据集下仍然可接受
        PerformanceTestSuite.assert_performance_threshold(
            memory_result["avg_time"],
            "large_file_processing"
        )
        
        print(f"\n大数据集处理性能:")
        print(f"  数据包数: {len(large_packets)}")
        print(f"  处理时间: {memory_result['avg_time']:.4f}s")
        print(f"  吞吐量: {len(large_packets)/memory_result['avg_time']:.1f} 包/秒")
    
    def test_error_handling_performance_impact(self):
        """错误处理性能影响测试"""
        # 创建正常数据包
        normal_packets = BasePcapProcessingTest.create_test_packets("plain")
        
        # 创建包含错误的数据包
        error_data = ErrorHandlingTestMixin.create_error_inducing_data()
        error_packets = [error_data["invalid_packet"]] + normal_packets
        
        # 测试正常情况性能
        normal_result = PerformanceTestSuite.measure_processing_performance(
            lambda p: _process_pcap_data_enhanced(p, self.adapter),
            normal_packets,
            iterations=10
        )
        
        # 测试错误情况性能
        error_result = PerformanceTestSuite.measure_processing_performance(
            lambda p: ErrorHandlingTestMixin.assert_graceful_error_handling(
                _process_pcap_data_enhanced, p, self.adapter, expected_result_type=tuple
            ),
            error_packets,
            iterations=10
        )
        
        # 验证错误处理不会显著影响性能（<30%）
        comparison = PerformanceTestSuite.compare_performance(
            normal_result, error_result, tolerance=0.3
        )
        
        self.assertLess(comparison['performance_ratio'], 1.3,
                       "错误处理性能影响过大")
        
        print(f"\n错误处理性能影响分析:")
        print(f"  正常情况: {normal_result['avg_time']:.4f}s")
        print(f"  错误情况: {error_result['avg_time']:.4f}s")
        print(f"  影响比率: {comparison['performance_ratio']:.2f}")
    
    def test_performance_regression_detection(self):
        """性能回归检测测试"""
        # 模拟基线性能数据
        baseline_performance = {
            "avg_time": 0.005,  # 5ms基线
            "total_time": 0.050,
            "iterations": 10
        }
        
        # 当前性能测试
        packets = BasePcapProcessingTest.create_test_packets("mixed")
        current_result = PerformanceTestSuite.measure_processing_performance(
            lambda p: _process_pcap_data_enhanced(p, self.adapter),
            packets,
            iterations=10
        )
        
        # 性能回归检测
        comparison = PerformanceTestSuite.compare_performance(
            baseline_performance, current_result, tolerance=0.1
        )
        
        # 如果有显著回归，发出警告
        if comparison['regression']:
            print(f"\n⚠️  检测到性能回归:")
            print(f"   基线性能: {baseline_performance['avg_time']:.4f}s")
            print(f"   当前性能: {current_result['avg_time']:.4f}s")
            print(f"   回归程度: {(comparison['performance_ratio'] - 1) * 100:.1f}%")
        
        # 验证性能仍在可接受范围内
        PerformanceTestSuite.assert_performance_threshold(
            current_result["avg_time"],
            "processing_time"
        )


@pytest.mark.performance
class TestPerformanceUtilities(unittest.TestCase):
    """性能测试工具测试"""
    
    def test_performance_suite_functionality(self):
        """测试性能测试套件功能"""
        # 测试性能测量
        def simple_func(data):
            import time
            time.sleep(0.001)  # 模拟1ms处理时间
            return data
        
        result = PerformanceTestSuite.measure_processing_performance(
            simple_func, "test_data", iterations=3
        )
        
        # 验证测量结果
        PerformanceTestSuite.verify_performance_report(result)
        self.assertGreaterEqual(result["avg_time"], 0.001)
        self.assertEqual(result["iterations"], 3)
    
    def test_performance_comparison(self):
        """测试性能比较功能"""
        baseline = {"avg_time": 0.010}
        current = {"avg_time": 0.012}
        
        comparison = PerformanceTestSuite.compare_performance(baseline, current)
        
        self.assertAlmostEqual(comparison["performance_ratio"], 1.2, places=1)
        self.assertFalse(comparison["regression"])  # 20%变化在tolerance内
    
    def test_performance_threshold_validation(self):
        """测试性能阈值验证"""
        # 正常情况
        PerformanceTestSuite.assert_performance_threshold(0.0005, "detection_time")
        
        # 异常情况
        with self.assertRaises(AssertionError):
            PerformanceTestSuite.assert_performance_threshold(0.002, "detection_time")
        
        # 自定义阈值
        PerformanceTestSuite.assert_performance_threshold(0.015, "custom", custom_threshold=0.020)


if __name__ == '__main__':
    # 运行性能测试
    print("🚀 运行PktMask集中性能测试...")
    unittest.main(verbosity=2) 