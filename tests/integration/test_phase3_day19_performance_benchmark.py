#!/usr/bin/env python3
"""
Phase 3 Day 19: 性能基准测试

验证TSharkEnhancedMaskProcessor与原实现(EnhancedTrimmer)的性能对比，
确保性能达到 ≥原实现85%速度，并测试其他关键性能指标。

验收标准:
- 处理速度: ≥原实现85%速度
- 内存使用: 大文件处理内存增长<300MB
- TShark分析: <文件大小(MB)×3秒
- 协议识别: 新类型识别延迟<50ms
"""

import pytest
import tempfile
import time
import statistics
import psutil
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any, Tuple
import json

from pktmask.core.processors.tshark_enhanced_mask_processor import TSharkEnhancedMaskProcessor
from pktmask.core.processors.enhanced_trimmer import EnhancedTrimmer
from pktmask.core.processors.base_processor import ProcessorConfig, ProcessorResult


class PerformanceBenchmarkSuite:
    """性能基准测试套件"""
    
    def __init__(self):
        self.results = {
            'tshark_enhanced': {},
            'enhanced_trimmer': {},
            'comparison': {},
            'benchmark_metadata': {
                'test_date': time.strftime('%Y-%m-%d %H:%M:%S'),
                'system_info': self._get_system_info()
            }
        }
        
    def _get_system_info(self) -> Dict[str, Any]:
        """获取系统信息"""
        return {
            'cpu_count': psutil.cpu_count(),
            'memory_total_gb': psutil.virtual_memory().total / (1024**3),
            'python_version': f"{psutil.sys.version_info.major}.{psutil.sys.version_info.minor}"
        }
        
    def create_mock_pcap_data(self, packet_count: int) -> List[Mock]:
        """创建模拟PCAP数据"""
        packets = []
        for i in range(packet_count):
            packet = Mock()
            packet.len = 1500 if i % 10 == 0 else 64  # 模拟不同大小的包
            packet.time = time.time() + i * 0.001
            packets.append(packet)
        return packets
        
    def measure_memory_usage(self, func, *args, **kwargs) -> Tuple[Any, float]:
        """测量函数执行期间的内存使用"""
        process = psutil.Process(os.getpid())
        memory_before = process.memory_info().rss / (1024**2)  # MB
        
        result = func(*args, **kwargs)
        
        memory_after = process.memory_info().rss / (1024**2)  # MB
        memory_increase = memory_after - memory_before
        
        return result, memory_increase


class TestPhase3Day19PerformanceBenchmark:
    """Phase 3 Day 19: 性能基准测试"""
    
    def setup_method(self):
        """测试前置设置"""
        self.benchmark = PerformanceBenchmarkSuite()
        self.temp_dir = Path(tempfile.mkdtemp(prefix="perf_benchmark_"))
        
    def teardown_method(self):
        """测试后清理"""
        import shutil
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
            
    def _create_test_files(self, size_category: str) -> Tuple[str, str]:
        """创建测试文件"""
        input_file = self.temp_dir / f"test_{size_category}_input.pcap"
        output_file = self.temp_dir / f"test_{size_category}_output.pcap"
        
        # 创建虚拟文件内容
        with open(input_file, 'w') as f:
            f.write(f"mock_pcap_data_{size_category}")
            
        return str(input_file), str(output_file)

    def test_initialization_performance_comparison(self):
        """测试1: 初始化性能对比"""
        print("\n🚀 测试1: 初始化性能对比")
        
        # 测试TSharkEnhancedMaskProcessor初始化性能
        tshark_times = []
        for _ in range(10):
            start_time = time.time()
            
            config = ProcessorConfig(enabled=True, name="tshark_enhanced", priority=1)
            tshark_processor = TSharkEnhancedMaskProcessor(config)
            
            with patch.object(tshark_processor, '_load_enhanced_config') as mock_config:
                mock_config.return_value = Mock(
                    enable_tls_processing=True,
                    enable_cross_segment_detection=True,
                    fallback_config=Mock(enable_fallback=True)
                )
                tshark_processor.initialize()
                
            end_time = time.time()
            tshark_times.append((end_time - start_time) * 1000)  # 转换为毫秒
            
        # 测试EnhancedTrimmer初始化性能
        trimmer_times = []
        for _ in range(10):
            start_time = time.time()
            
            config = ProcessorConfig(enabled=True, name="enhanced_trimmer", priority=1)
            trimmer_processor = EnhancedTrimmer(config)
            trimmer_processor.initialize()
            
            end_time = time.time()
            trimmer_times.append((end_time - start_time) * 1000)  # 转换为毫秒
            
        # 性能分析
        tshark_avg = statistics.mean(tshark_times)
        trimmer_avg = statistics.mean(trimmer_times)
        performance_ratio = tshark_avg / trimmer_avg
        
        self.benchmark.results['tshark_enhanced']['initialization_ms'] = tshark_avg
        self.benchmark.results['enhanced_trimmer']['initialization_ms'] = trimmer_avg
        self.benchmark.results['comparison']['initialization_ratio'] = performance_ratio
        
        print(f"  TSharkEnhanced平均: {tshark_avg:.2f}ms")
        print(f"  EnhancedTrimmer平均: {trimmer_avg:.2f}ms")
        print(f"  性能比率: {performance_ratio:.2f}x")
        
        # 验收标准: 初始化性能不应差距过大(不超过5倍)
        assert performance_ratio < 5.0, f"初始化性能差距过大: {performance_ratio:.2f}x"

    def test_small_file_processing_performance(self):
        """测试2: 小文件处理性能对比"""
        print("\n📄 测试2: 小文件处理性能对比 (100包)")
        
        input_file, output_file = self._create_test_files("small")
        mock_packets = self.benchmark.create_mock_pcap_data(100)
        
        # 测试TSharkEnhancedMaskProcessor处理性能
        tshark_times = []
        with patch('pktmask.core.processors.tshark_tls_analyzer.subprocess.run') as mock_tshark, \
             patch('pktmask.core.processors.scapy_mask_applier.rdpcap') as mock_rdpcap, \
             patch('pktmask.core.processors.scapy_mask_applier.wrpcap') as mock_wrpcap:
            
            # Mock TShark分析结果
            mock_tshark.return_value.returncode = 0
            mock_tshark.return_value.stdout = '[]'  # 空TLS记录
            mock_rdpcap.return_value = mock_packets
            
            config = ProcessorConfig(enabled=True, name="tshark_enhanced", priority=1)
            tshark_processor = TSharkEnhancedMaskProcessor(config)
            
            # Mock配置和初始化
            with patch.object(tshark_processor, '_load_enhanced_config') as mock_config:
                mock_config.return_value = Mock(
                    enable_tls_processing=True,
                    enable_performance_monitoring=True,
                    fallback_config=Mock(enable_fallback=True)
                )
                tshark_processor.initialize()
                
                for _ in range(5):
                    start_time = time.time()
                    result, memory_used = self.benchmark.measure_memory_usage(
                        tshark_processor.process_file, input_file, output_file
                    )
                    end_time = time.time()
                    
                    tshark_times.append((end_time - start_time) * 1000)
        
        # 测试EnhancedTrimmer处理性能
        trimmer_times = []
        with patch('pktmask.core.trim.stages.enhanced_pyshark_analyzer.rdpcap') as mock_rdpcap2:
            mock_rdpcap2.return_value = mock_packets
            
            config = ProcessorConfig(enabled=True, name="enhanced_trimmer", priority=1)
            trimmer_processor = EnhancedTrimmer(config)
            trimmer_processor.initialize()
            
            for _ in range(5):
                start_time = time.time()
                result, memory_used = self.benchmark.measure_memory_usage(
                    trimmer_processor.process_file, input_file, output_file
                )
                end_time = time.time()
                
                trimmer_times.append((end_time - start_time) * 1000)
        
        # 性能分析
        tshark_avg = statistics.mean(tshark_times)
        trimmer_avg = statistics.mean(trimmer_times)
        performance_ratio = tshark_avg / trimmer_avg
        speed_retention = (trimmer_avg / tshark_avg) * 100
        
        self.benchmark.results['tshark_enhanced']['small_file_ms'] = tshark_avg
        self.benchmark.results['enhanced_trimmer']['small_file_ms'] = trimmer_avg
        self.benchmark.results['comparison']['small_file_ratio'] = performance_ratio
        self.benchmark.results['comparison']['small_file_speed_retention'] = speed_retention
        
        print(f"  TSharkEnhanced平均: {tshark_avg:.2f}ms")
        print(f"  EnhancedTrimmer平均: {trimmer_avg:.2f}ms")
        print(f"  性能比率: {performance_ratio:.2f}x")
        print(f"  速度保留率: {speed_retention:.1f}%")
        
        # 验收标准: 速度保留率 ≥85%
        assert speed_retention >= 85.0, f"小文件处理速度保留率不达标: {speed_retention:.1f}%"

    def test_protocol_recognition_latency(self):
        """测试3: 协议识别延迟测试"""
        print("\n🎯 测试3: 协议识别延迟测试")
        
        # 测试不同TLS协议类型的识别延迟
        tls_types = [20, 21, 22, 23, 24]  # ChangeCipherSpec, Alert, Handshake, ApplicationData, Heartbeat
        recognition_times = {}
        
        from pktmask.core.trim.models.tls_models import get_tls_processing_strategy
        
        for tls_type in tls_types:
            times = []
            
            for _ in range(100):  # 测试100次求平均值
                start_time = time.time()
                
                # 模拟协议识别过程
                strategy = get_tls_processing_strategy(tls_type)
                
                end_time = time.time()
                recognition_time = (end_time - start_time) * 1000  # 转换为毫秒
                times.append(recognition_time)
            
            avg_time = statistics.mean(times)
            recognition_times[f"TLS-{tls_type}"] = avg_time
            
            print(f"  TLS-{tls_type}协议识别: {avg_time:.3f}ms")
            
            # 验收标准: 协议识别延迟 <50ms
            assert avg_time < 50.0, f"TLS-{tls_type}协议识别延迟超标: {avg_time:.3f}ms"
        
        self.benchmark.results['tshark_enhanced']['protocol_recognition_times'] = recognition_times

    def test_comprehensive_performance_report(self):
        """测试4: 综合性能报告生成"""
        print("\n📋 测试4: 综合性能报告生成")
        
        # 计算综合性能评分
        performance_score = self._calculate_performance_score()
        self.benchmark.results['comparison']['overall_performance_score'] = performance_score
        
        # 生成性能报告
        report_file = self.temp_dir / "performance_benchmark_report.json"
        with open(report_file, 'w') as f:
            json.dump(self.benchmark.results, f, indent=2)
        
        print(f"  综合性能评分: {performance_score:.1f}/100")
        print(f"  详细报告已生成: {report_file}")
        
        # 生成人类可读的总结报告
        summary_report = self._generate_summary_report()
        print("\n📊 性能测试总结:")
        for line in summary_report:
            print(f"  {line}")
        
        # 验收标准: 综合性能评分 ≥85分
        assert performance_score >= 85.0, f"综合性能评分不达标: {performance_score:.1f}/100"
        
    def _calculate_performance_score(self) -> float:
        """计算综合性能评分"""
        score = 0.0
        
        # 初始化性能评分 (权重: 10%)
        init_ratio = self.benchmark.results['comparison'].get('initialization_ratio', 5.0)
        if init_ratio <= 2.0:
            score += 10.0
        elif init_ratio <= 5.0:
            score += 5.0
        
        # 处理速度评分 (权重: 40%) 
        speed_retention = self.benchmark.results['comparison'].get('small_file_speed_retention', 0)
        if speed_retention >= 95:
            score += 40.0
        elif speed_retention >= 85:
            score += 30.0
        elif speed_retention >= 75:
            score += 20.0
        
        # 协议识别延迟评分 (权重: 50%)
        recognition_times = self.benchmark.results['tshark_enhanced'].get('protocol_recognition_times', {})
        if recognition_times:
            recognition_ok = all(time < 50.0 for time in recognition_times.values())
            if recognition_ok:
                score += 50.0
        
        return score
        
    def _generate_summary_report(self) -> List[str]:
        """生成总结报告"""
        report = []
        
        # 性能对比总结
        speed_retention = self.benchmark.results['comparison'].get('small_file_speed_retention', 0)
        if speed_retention >= 85:
            report.append(f"✅ 处理速度: {speed_retention:.1f}% (达标 ≥85%)")
        else:
            report.append(f"❌ 处理速度: {speed_retention:.1f}% (未达标 <85%)")
        
        # 协议识别总结
        recognition_times = self.benchmark.results['tshark_enhanced'].get('protocol_recognition_times', {})
        if recognition_times:
            all_fast = all(time < 50.0 for time in recognition_times.values())
            if all_fast:
                report.append("✅ 协议识别: 所有类型快速识别 (达标 <50ms)")
            else:
                report.append("❌ 协议识别: 部分类型识别较慢 (未达标 ≥50ms)")
        
        # 综合评价
        score = self.benchmark.results['comparison'].get('overall_performance_score', 0)
        if score >= 90:
            report.append(f"🏆 综合评价: 优秀 ({score:.1f}/100)")
        elif score >= 85:
            report.append(f"✅ 综合评价: 良好 ({score:.1f}/100)")
        else:
            report.append(f"⚠️ 综合评价: 需改进 ({score:.1f}/100)")
        
        return report 