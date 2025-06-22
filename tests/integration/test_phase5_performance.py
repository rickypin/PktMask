"""
Phase 5: 性能基准测试

专门测试独立PCAP掩码处理器的性能指标，包括处理速度、内存使用、
扩展性行为等关键性能指标。
"""

import pytest
import tempfile
import os
import time
import psutil
import threading
import gc
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
import logging
import statistics

from src.pktmask.core.independent_pcap_masker.core.masker import IndependentPcapMasker
from src.pktmask.core.independent_pcap_masker.core.models import (
    SequenceMaskTable, MaskEntry, MaskingResult
)

# 测试配置
SAMPLES_DIR = Path("tests/samples")
PERFORMANCE_THRESHOLDS = {
    'small_file_pps': 1000,      # 小文件处理速度目标
    'medium_file_pps': 500,      # 中等文件处理速度目标
    'large_file_pps': 100,       # 大文件处理速度目标
    'memory_limit_mb': 512,      # 内存使用限制
    'processing_timeout': 60     # 处理超时时间
}


class PerformanceMonitor:
    """性能监控工具类"""
    
    def __init__(self):
        self.process = psutil.Process()
        self.initial_memory = 0
        self.peak_memory = 0
        self.start_time = 0
        self.monitoring = False
        self._monitor_thread = None
        self._memory_samples = []
    
    def start_monitoring(self):
        """开始性能监控"""
        self.initial_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        self.peak_memory = self.initial_memory
        self.start_time = time.time()
        self.monitoring = True
        self._memory_samples = []
        
        # 启动内存监控线程
        self._monitor_thread = threading.Thread(target=self._monitor_memory)
        self._monitor_thread.daemon = True
        self._monitor_thread.start()
    
    def stop_monitoring(self) -> Dict[str, float]:
        """停止监控并返回性能指标"""
        self.monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=1.0)
        
        end_time = time.time()
        final_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        
        return {
            'initial_memory_mb': self.initial_memory,
            'final_memory_mb': final_memory,
            'peak_memory_mb': self.peak_memory,
            'memory_growth_mb': final_memory - self.initial_memory,
            'memory_growth_peak_mb': self.peak_memory - self.initial_memory,
            'duration_seconds': end_time - self.start_time,
            'avg_memory_mb': statistics.mean(self._memory_samples) if self._memory_samples else final_memory
        }
    
    def _monitor_memory(self):
        """内存监控线程"""
        while self.monitoring:
            try:
                current_memory = self.process.memory_info().rss / 1024 / 1024  # MB
                self.peak_memory = max(self.peak_memory, current_memory)
                self._memory_samples.append(current_memory)
                time.sleep(0.1)  # 每100ms采样一次
            except:
                break


class TestPerformanceBenchmarks:
    """性能基准测试类"""
    
    def setup_method(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
        self.masker = IndependentPcapMasker({
            'log_level': 'WARNING',  # 减少日志输出提高性能
            'strict_consistency_mode': False,
            'recalculate_checksums': False  # 禁用校验和重计算提高性能
        })
        self.monitor = PerformanceMonitor()
        
        # 强制垃圾回收
        gc.collect()
    
    def teardown_method(self):
        """测试后清理"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        gc.collect()
    
    @pytest.mark.performance
    def test_processing_speed_small_files(self):
        """小文件处理速度测试 (< 1MB)
        
        目标: ≥ 1000 pps
        """
        small_files = self._find_files_by_size(max_size_mb=1)
        if not small_files:
            pytest.skip("没有找到小文件样本")
        
        results = []
        for input_file in small_files[:3]:  # 测试前3个文件
            result = self._benchmark_single_file(
                input_file, 
                f"small_{input_file.stem}",
                expected_min_pps=PERFORMANCE_THRESHOLDS['small_file_pps']
            )
            results.append(result)
        
        # 计算平均性能
        avg_pps = statistics.mean([r['pps'] for r in results])
        logging.info(f"小文件平均处理速度: {avg_pps:.2f} pps")
        
        assert avg_pps >= PERFORMANCE_THRESHOLDS['small_file_pps'], \
            f"小文件处理速度不达标: {avg_pps:.2f} pps < {PERFORMANCE_THRESHOLDS['small_file_pps']} pps"
    
    @pytest.mark.performance
    def test_processing_speed_medium_files(self):
        """中等文件处理速度测试 (1-50MB)
        
        目标: ≥ 500 pps  
        """
        medium_files = self._find_files_by_size(min_size_mb=1, max_size_mb=50)
        if not medium_files:
            pytest.skip("没有找到中等文件样本")
        
        results = []
        for input_file in medium_files[:2]:  # 测试前2个文件
            result = self._benchmark_single_file(
                input_file,
                f"medium_{input_file.stem}",
                expected_min_pps=PERFORMANCE_THRESHOLDS['medium_file_pps']
            )
            results.append(result)
        
        # 计算平均性能
        avg_pps = statistics.mean([r['pps'] for r in results])
        logging.info(f"中等文件平均处理速度: {avg_pps:.2f} pps")
        
        assert avg_pps >= PERFORMANCE_THRESHOLDS['medium_file_pps'], \
            f"中等文件处理速度不达标: {avg_pps:.2f} pps < {PERFORMANCE_THRESHOLDS['medium_file_pps']} pps"
    
    @pytest.mark.performance
    def test_processing_speed_large_files(self):
        """大文件处理速度测试 (> 50MB)
        
        目标: ≥ 100 pps
        """
        large_files = self._find_files_by_size(min_size_mb=50)
        if not large_files:
            pytest.skip("没有找到大文件样本")
        
        # 只测试最大的文件
        input_file = max(large_files, key=lambda f: f.stat().st_size)
        result = self._benchmark_single_file(
            input_file,
            f"large_{input_file.stem}",
            expected_min_pps=PERFORMANCE_THRESHOLDS['large_file_pps']
        )
        
        logging.info(f"大文件处理速度: {result['pps']:.2f} pps")
        
        assert result['pps'] >= PERFORMANCE_THRESHOLDS['large_file_pps'], \
            f"大文件处理速度不达标: {result['pps']:.2f} pps < {PERFORMANCE_THRESHOLDS['large_file_pps']} pps"
    
    @pytest.mark.performance
    def test_memory_usage_efficiency(self):
        """内存使用效率测试
        
        目标: 内存增长 < 512MB
        """
        # 查找合适大小的测试文件
        test_files = self._find_files_by_size(min_size_mb=0.1, max_size_mb=10)
        if not test_files:
            pytest.skip("没有找到合适的测试文件")
        
        input_file = test_files[0]
        file_size_mb = input_file.stat().st_size / 1024 / 1024
        output_file = os.path.join(self.temp_dir, "memory_test.pcap")
        
        # 创建适度复杂的掩码表
        mask_table = self._create_comprehensive_mask_table()
        
        # 开始内存监控
        self.monitor.start_monitoring()
        
        # 执行处理
        result = self.masker.mask_pcap_with_sequences(
            str(input_file), mask_table, output_file
        )
        
        # 停止监控并获取指标
        perf_metrics = self.monitor.stop_monitoring()
        
        # 验证结果
        assert result.success, f"处理失败: {result.error_message}"
        
        # 验证内存使用效率
        memory_growth = perf_metrics['memory_growth_mb']
        
        logging.info(f"内存使用: 初始 {perf_metrics['initial_memory_mb']:.2f} MB, "
                    f"峰值 {perf_metrics['peak_memory_mb']:.2f} MB, "
                    f"增长 {memory_growth:.2f} MB, "
                    f"文件大小 {file_size_mb:.2f} MB")
        
        assert memory_growth < PERFORMANCE_THRESHOLDS['memory_limit_mb'], \
            f"内存增长过大: {memory_growth:.2f} MB > {PERFORMANCE_THRESHOLDS['memory_limit_mb']} MB"
    
    @pytest.mark.performance
    def test_scaling_behavior(self):
        """扩展性行为测试
        
        测试处理性能随文件大小的扩展行为
        """
        # 收集不同大小的文件
        all_files = []
        for sample_dir in SAMPLES_DIR.iterdir():
            if sample_dir.is_dir():
                for pcap_file in sample_dir.glob("*.pcap*"):
                    all_files.append(pcap_file)
        
        if len(all_files) < 3:
            pytest.skip("样本文件不足，无法进行扩展性测试")
        
        # 按文件大小排序
        all_files.sort(key=lambda f: f.stat().st_size)
        
        # 选择小、中、大三个文件
        test_files = [
            all_files[0],                    # 最小文件
            all_files[len(all_files)//2],    # 中等文件  
            all_files[-1]                    # 最大文件
        ]
        
        scaling_results = []
        
        for i, input_file in enumerate(test_files):
            file_size_mb = input_file.stat().st_size / 1024 / 1024
            
            result = self._benchmark_single_file(
                input_file,
                f"scaling_{i}",
                expected_min_pps=50  # 较低的基准要求
            )
            
            scaling_results.append({
                'file_size_mb': file_size_mb,
                'pps': result['pps'],
                'packets': result['packets'],
                'processing_time': result['processing_time']
            })
        
        # 分析扩展性趋势
        logging.info("扩展性测试结果:")
        for i, result in enumerate(scaling_results):
            logging.info(f"  文件{i+1}: {result['file_size_mb']:.2f} MB, "
                        f"{result['pps']:.2f} pps, "
                        f"{result['packets']} packets")
        
        # 验证：处理时间应该与数据包数量大致成正比
        if len(scaling_results) >= 2:
            # 计算处理效率（pps）的稳定性
            pps_values = [r['pps'] for r in scaling_results if r['pps'] > 0]
            if len(pps_values) >= 2:
                pps_variance = statistics.pvariance(pps_values)
                pps_mean = statistics.mean(pps_values)
                
                # 处理效率的变异系数应该在合理范围内
                cv = (pps_variance ** 0.5) / pps_mean if pps_mean > 0 else float('inf')
                
                logging.info(f"处理效率稳定性: CV = {cv:.3f}")
                
                # 允许较大的变异（因为文件特征可能差异很大）
                assert cv < 2.0, f"处理效率变异过大: {cv:.3f}"
    
    def _benchmark_single_file(
        self, 
        input_file: Path, 
        test_name: str, 
        expected_min_pps: float = 100
    ) -> Dict[str, Any]:
        """对单个文件进行基准测试"""
        output_file = os.path.join(self.temp_dir, f"{test_name}.pcap")
        mask_table = self._create_performance_mask_table()
        
        # 开始监控
        self.monitor.start_monitoring()
        
        # 执行处理
        start_time = time.time()
        result = self.masker.mask_pcap_with_sequences(
            str(input_file), mask_table, output_file
        )
        processing_time = time.time() - start_time
        
        # 停止监控
        perf_metrics = self.monitor.stop_monitoring()
        
        # 计算性能指标
        pps = result.total_packets / processing_time if processing_time > 0 else 0
        file_size_mb = input_file.stat().st_size / 1024 / 1024
        
        benchmark_result = {
            'file_name': input_file.name,
            'file_size_mb': file_size_mb,
            'packets': result.total_packets,
            'modified_packets': result.modified_packets,
            'processing_time': processing_time,
            'pps': pps,
            'success': result.success,
            'memory_metrics': perf_metrics,
            'error': result.error_message
        }
        
        logging.info(f"{test_name}: {pps:.2f} pps, "
                    f"{file_size_mb:.2f} MB, "
                    f"{result.total_packets} packets, "
                    f"{processing_time:.3f}s")
        
        # 基本验证
        assert result.success, f"处理失败: {result.error_message}"
        assert pps >= expected_min_pps, \
            f"性能不达标: {pps:.2f} pps < {expected_min_pps} pps"
        
        return benchmark_result
    
    def _find_files_by_size(
        self, 
        min_size_mb: float = 0, 
        max_size_mb: float = float('inf')
    ) -> List[Path]:
        """按文件大小查找样本文件"""
        matching_files = []
        
        for sample_dir in SAMPLES_DIR.iterdir():
            if sample_dir.is_dir():
                for pcap_file in sample_dir.glob("*.pcap*"):
                    size_mb = pcap_file.stat().st_size / 1024 / 1024
                    if min_size_mb <= size_mb <= max_size_mb:
                        matching_files.append(pcap_file)
        
        return sorted(matching_files, key=lambda f: f.stat().st_size)
    
    def _create_performance_mask_table(self) -> SequenceMaskTable:
        """创建性能测试用掩码表"""
        mask_table = SequenceMaskTable()
        
        # 添加几个轻量级的掩码条目
        entries = [
            MaskEntry(
                stream_id=f"TCP_perf_test_{i}",
                sequence_start=i * 1000,
                sequence_end=(i + 1) * 1000,
                mask_type="mask_after",
                mask_params={"keep_bytes": 5}
            )
            for i in range(5)  # 5个条目，不要太多
        ]
        
        for entry in entries:
            mask_table.add_entry(entry)
        
        return mask_table
    
    def _create_comprehensive_mask_table(self) -> SequenceMaskTable:
        """创建更全面的掩码表（用于内存测试）"""
        mask_table = SequenceMaskTable()
        
        # 添加各种类型的掩码条目
        entries = []
        
        # MaskAfter类型
        for i in range(20):
            entries.append(MaskEntry(
                stream_id=f"TCP_mask_after_{i}",
                sequence_start=i * 1000,
                sequence_end=(i + 1) * 1000,
                mask_type="mask_after",
                mask_params={"keep_bytes": 5}
            ))
        
        # MaskRange类型
        for i in range(15):
            entries.append(MaskEntry(
                stream_id=f"TCP_mask_range_{i}",
                sequence_start=i * 2000,
                sequence_end=(i + 1) * 2000,
                mask_type="mask_range",
                mask_params={"ranges": [(100, 500), (700, 900)]}
            ))
        
        # KeepAll类型
        for i in range(10):
            entries.append(MaskEntry(
                stream_id=f"TCP_keep_all_{i}",
                sequence_start=i * 3000,
                sequence_end=(i + 1) * 3000,
                mask_type="keep_all",
                mask_params={}
            ))
        
        for entry in entries:
            mask_table.add_entry(entry)
        
        return mask_table 