#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
算法性能基准测试套件
用于测试和比较各种算法的性能指标
"""

import os
import sys
import time
import tempfile
import shutil
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

# 添加src路径到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from pktmask.core.strategy import HierarchicalAnonymizationStrategy
from pktmask.core.strategy_optimized import OptimizedHierarchicalAnonymizationStrategy
from pktmask.steps.trimming import IntelligentTrimmingStep
from pktmask.steps.deduplication import DeduplicationStep
from pktmask.steps.trimming_optimized import OptimizedIntelligentTrimmingStep
from pktmask.steps.deduplication_optimized import OptimizedDeduplicationStep
from pktmask.infrastructure.logging import get_logger
from pktmask.utils.time import get_performance_metrics
from performance_monitor import PerformanceMonitor


@dataclass
class BenchmarkResult:
    """基准测试结果"""
    algorithm_name: str
    file_size_mb: float
    processing_time_seconds: float
    memory_usage_mb: float
    packets_processed: int
    files_processed: int
    throughput_mbps: float
    packets_per_second: float
    success: bool
    error_message: Optional[str] = None


class AlgorithmBenchmark:
    """算法性能基准测试套件"""
    
    def __init__(self, test_data_dir: str = None):
        """
        初始化基准测试套件
        
        Args:
            test_data_dir: 测试数据目录路径
        """
        self._logger = get_logger('benchmark')
        self.test_data_dir = test_data_dir or self._get_default_test_data_dir()
        self.performance_monitor = PerformanceMonitor()
        self.results: List[BenchmarkResult] = []
        
        # 确保测试数据目录存在
        if not os.path.exists(self.test_data_dir):
            self._logger.warning(f"测试数据目录不存在: {self.test_data_dir}")
            
    def _get_default_test_data_dir(self) -> str:
        """获取默认测试数据目录"""
        current_dir = Path(__file__).parent.parent
        return str(current_dir / "data")
    
    def _get_test_files_by_size(self) -> Dict[str, List[str]]:
        """根据文件大小分类测试文件"""
        size_categories = {
            'small': [],    # < 10MB
            'medium': [],   # 10MB - 100MB  
            'large': []     # > 100MB
        }
        
        if not os.path.exists(self.test_data_dir):
            return size_categories
            
        for root, dirs, files in os.walk(self.test_data_dir):
            for file in files:
                if file.endswith(('.pcap', '.pcapng')):
                    file_path = os.path.join(root, file)
                    try:
                        size_mb = os.path.getsize(file_path) / (1024 * 1024)
                        if size_mb < 10:
                            size_categories['small'].append(file_path)
                        elif size_mb < 100:
                            size_categories['medium'].append(file_path)
                        else:
                            size_categories['large'].append(file_path)
                    except OSError:
                        continue
                        
        return size_categories
    
    def benchmark_ip_anonymization(self, test_files: Optional[List[str]] = None) -> List[BenchmarkResult]:
        """
        IP匿名化算法基准测试（原版本）
        
        Args:
            test_files: 指定的测试文件列表，如果为None则使用默认分类
            
        Returns:
            List[BenchmarkResult]: 基准测试结果列表
        """
        self._logger.info("开始IP匿名化算法基准测试（原版本）")
        results = []
        
        if test_files is None:
            file_categories = self._get_test_files_by_size()
            test_files = []
            for category, files in file_categories.items():
                if files:
                    test_files.extend(files[:2])  # 每个类别最多测试2个文件
        
        strategy = HierarchicalAnonymizationStrategy()
        
        for file_path in test_files:
            result = self._benchmark_single_algorithm(
                algorithm_name="IP_Anonymization_Original",
                file_path=file_path,
                algorithm_func=lambda: self._run_ip_anonymization(strategy, file_path)
            )
            results.append(result)
            
        self._logger.info(f"IP匿名化基准测试（原版本）完成，测试了{len(results)}个文件")
        return results
    
    def benchmark_ip_anonymization_optimized(self, test_files: Optional[List[str]] = None) -> List[BenchmarkResult]:
        """
        IP匿名化算法基准测试（优化版本）
        
        Args:
            test_files: 指定的测试文件列表，如果为None则使用默认分类
            
        Returns:
            List[BenchmarkResult]: 基准测试结果列表
        """
        self._logger.info("开始IP匿名化算法基准测试（优化版本）")
        results = []
        
        if test_files is None:
            file_categories = self._get_test_files_by_size()
            test_files = []
            for category, files in file_categories.items():
                if files:
                    test_files.extend(files[:2])  # 每个类别最多测试2个文件
        
        strategy = OptimizedHierarchicalAnonymizationStrategy()
        
        for file_path in test_files:
            result = self._benchmark_single_algorithm(
                algorithm_name="IP_Anonymization_Optimized",
                file_path=file_path,
                algorithm_func=lambda: self._run_ip_anonymization(strategy, file_path)
            )
            results.append(result)
            
        self._logger.info(f"IP匿名化基准测试（优化版本）完成，测试了{len(results)}个文件")
        return results
    
    def benchmark_packet_trimming(self, test_files: Optional[List[str]] = None) -> List[BenchmarkResult]:
        """
        数据包裁切算法基准测试
        
        Args:
            test_files: 指定的测试文件列表
            
        Returns:
            List[BenchmarkResult]: 基准测试结果列表
        """
        self._logger.info("开始数据包裁切算法基准测试")
        results = []
        
        if test_files is None:
            file_categories = self._get_test_files_by_size()
            test_files = []
            for category, files in file_categories.items():
                if files:
                    test_files.extend(files[:2])
        
        trimming_step = IntelligentTrimmingStep()
        
        for file_path in test_files:
            result = self._benchmark_single_algorithm(
                algorithm_name="Packet_Trimming",
                file_path=file_path,
                algorithm_func=lambda: self._run_packet_trimming(trimming_step, file_path)
            )
            results.append(result)
            
        self._logger.info(f"数据包裁切基准测试完成，测试了{len(results)}个文件")
        return results
    
    def benchmark_deduplication(self, test_files: Optional[List[str]] = None) -> List[BenchmarkResult]:
        """
        去重算法基准测试
        
        Args:
            test_files: 指定的测试文件列表
            
        Returns:
            List[BenchmarkResult]: 基准测试结果列表
        """
        self._logger.info("开始去重算法基准测试")
        results = []
        
        if test_files is None:
            file_categories = self._get_test_files_by_size()
            test_files = []
            for category, files in file_categories.items():
                if files:
                    test_files.extend(files[:2])
        
        dedup_step = DeduplicationStep()
        
        for file_path in test_files:
            result = self._benchmark_single_algorithm(
                algorithm_name="Deduplication",
                file_path=file_path,
                algorithm_func=lambda: self._run_deduplication(dedup_step, file_path)
            )
            results.append(result)
            
        self._logger.info(f"去重算法基准测试完成，测试了{len(results)}个文件")
        return results
    
    def benchmark_packet_trimming_optimized(self, pcap_file: str) -> Dict[str, float]:
        """基准测试优化版本的数据包裁切算法"""
        self._logger.info(f"开始优化数据包裁切基准测试: {pcap_file}")
        
        # 创建优化版本的裁切步骤
        trimmer = OptimizedIntelligentTrimmingStep()
        
        # 准备测试数据
        start_time = time.time()
        memory_before = self.performance_monitor.get_memory_usage()
        
        # 创建临时输出文件
        output_file = f"/tmp/benchmark_trimmed_optimized_{int(time.time())}.pcap"
        
        try:
            # 执行裁切操作
            result = trimmer.process_file(pcap_file, output_file)
            
            end_time = time.time()
            memory_after = self.performance_monitor.get_memory_usage()
            
            # 计算性能指标
            duration = end_time - start_time
            file_size = os.path.getsize(pcap_file)
            packet_count = result['total_packets'] if result else 0
            
            throughput_mbps = (file_size / (1024 * 1024)) / duration if duration > 0 else 0
            packets_per_second = packet_count / duration if duration > 0 else 0
            memory_used = max(0, memory_after - memory_before)
            
            metrics = {
                'duration': duration,
                'throughput_mbps': throughput_mbps,
                'packets_per_second': packets_per_second,
                'memory_used_mb': memory_used,
                'total_packets': packet_count,
                'cache_hits': result.get('cache_hits', 0) if result else 0
            }
            
            self._logger.info(f"优化裁切完成 - 吞吐量: {throughput_mbps:.2f} MB/s, "
                           f"包处理速度: {packets_per_second:.0f} packets/s, "
                           f"内存使用: {memory_used:.1f} MB, "
                           f"缓存命中: {metrics['cache_hits']}")
            
            return metrics
            
        finally:
            # 清理临时文件
            if os.path.exists(output_file):
                os.remove(output_file)

    def benchmark_packet_deduplication_optimized(self, pcap_file: str) -> Dict[str, float]:
        """基准测试优化版本的数据包去重算法"""
        self._logger.info(f"开始优化数据包去重基准测试: {pcap_file}")
        
        # 创建优化版本的去重步骤
        deduper = OptimizedDeduplicationStep()
        
        # 准备测试数据
        start_time = time.time()
        memory_before = self.performance_monitor.get_memory_usage()
        
        # 创建临时输出文件
        output_file = f"/tmp/benchmark_deduped_optimized_{int(time.time())}.pcap"
        
        try:
            # 执行去重操作
            result = deduper.process_file(pcap_file, output_file)
            
            end_time = time.time()
            memory_after = self.performance_monitor.get_memory_usage()
            
            # 计算性能指标
            duration = end_time - start_time
            file_size = os.path.getsize(pcap_file)
            packet_count = result['total_packets'] if result else 0
            
            throughput_mbps = (file_size / (1024 * 1024)) / duration if duration > 0 else 0
            packets_per_second = packet_count / duration if duration > 0 else 0
            memory_used = max(0, memory_after - memory_before)
            
            metrics = {
                'duration': duration,
                'throughput_mbps': throughput_mbps,
                'packets_per_second': packets_per_second,
                'memory_used_mb': memory_used,
                'total_packets': packet_count,
                'cache_hits': result.get('cache_hits', 0) if result else 0
            }
            
            self._logger.info(f"优化去重完成 - 吞吐量: {throughput_mbps:.2f} MB/s, "
                           f"包处理速度: {packets_per_second:.0f} packets/s, "
                           f"内存使用: {memory_used:.1f} MB, "
                           f"缓存命中: {metrics['cache_hits']}")
            
            return metrics
            
        finally:
            # 清理临时文件
            if os.path.exists(output_file):
                os.remove(output_file)

    def compare_packet_processing_algorithms(self, pcap_file: str) -> Dict[str, Dict[str, float]]:
        """比较原始和优化版本的数据包处理算法性能"""
        self._logger.info(f"开始数据包处理算法性能比较: {pcap_file}")
        
        results = {}
        
        # 测试原始裁切算法
        trim_orig_result = self.benchmark_packet_trimming([pcap_file])[0]
        results['trimming_original'] = {
            'throughput_mbps': trim_orig_result.throughput_mbps,
            'packets_per_second': trim_orig_result.packets_per_second,
            'memory_used_mb': trim_orig_result.memory_usage_mb,
            'duration': trim_orig_result.processing_time_seconds,
            'total_packets': trim_orig_result.packets_processed
        }
        
        # 测试优化裁切算法
        results['trimming_optimized'] = self.benchmark_packet_trimming_optimized(pcap_file)
        
        # 测试原始去重算法
        dedup_orig_result = self.benchmark_deduplication([pcap_file])[0]
        results['deduplication_original'] = {
            'throughput_mbps': dedup_orig_result.throughput_mbps,
            'packets_per_second': dedup_orig_result.packets_per_second,
            'memory_used_mb': dedup_orig_result.memory_usage_mb,
            'duration': dedup_orig_result.processing_time_seconds,
            'total_packets': dedup_orig_result.packets_processed
        }
        
        # 测试优化去重算法
        results['deduplication_optimized'] = self.benchmark_packet_deduplication_optimized(pcap_file)
        
        # 计算改进百分比
        improvements = {}
        
        # 裁切算法改进
        trim_orig = results['trimming_original']
        trim_opt = results['trimming_optimized']
        improvements['trimming'] = {
            'throughput_improvement': ((trim_opt['throughput_mbps'] - trim_orig['throughput_mbps']) / trim_orig['throughput_mbps'] * 100) if trim_orig['throughput_mbps'] > 0 else 0,
            'speed_improvement': ((trim_opt['packets_per_second'] - trim_orig['packets_per_second']) / trim_orig['packets_per_second'] * 100) if trim_orig['packets_per_second'] > 0 else 0,
            'memory_improvement': ((trim_orig['memory_used_mb'] - trim_opt['memory_used_mb']) / trim_orig['memory_used_mb'] * 100) if trim_orig['memory_used_mb'] > 0 else 0
        }
        
        # 去重算法改进
        dedup_orig = results['deduplication_original']
        dedup_opt = results['deduplication_optimized']
        improvements['deduplication'] = {
            'throughput_improvement': ((dedup_opt['throughput_mbps'] - dedup_orig['throughput_mbps']) / dedup_orig['throughput_mbps'] * 100) if dedup_orig['throughput_mbps'] > 0 else 0,
            'speed_improvement': ((dedup_opt['packets_per_second'] - dedup_orig['packets_per_second']) / dedup_orig['packets_per_second'] * 100) if dedup_orig['packets_per_second'] > 0 else 0,
            'memory_improvement': ((dedup_orig['memory_used_mb'] - dedup_opt['memory_used_mb']) / dedup_orig['memory_used_mb'] * 100) if dedup_orig['memory_used_mb'] > 0 else 0
        }
        
        results['improvements'] = improvements
        
        # 记录比较结果
        self._logger.info("=== 数据包处理算法性能比较结果 ===")
        self._logger.info(f"裁切算法改进 - 吞吐量: {improvements['trimming']['throughput_improvement']:+.1f}%, "
                        f"处理速度: {improvements['trimming']['speed_improvement']:+.1f}%, "
                        f"内存优化: {improvements['trimming']['memory_improvement']:+.1f}%")
        self._logger.info(f"去重算法改进 - 吞吐量: {improvements['deduplication']['throughput_improvement']:+.1f}%, "
                        f"处理速度: {improvements['deduplication']['speed_improvement']:+.1f}%, "
                        f"内存优化: {improvements['deduplication']['memory_improvement']:+.1f}%")
        
        return results
    
    def _benchmark_single_algorithm(self, algorithm_name: str, file_path: str, 
                                   algorithm_func) -> BenchmarkResult:
        """
        对单个算法进行基准测试
        
        Args:
            algorithm_name: 算法名称
            file_path: 测试文件路径
            algorithm_func: 算法执行函数
            
        Returns:
            BenchmarkResult: 基准测试结果
        """
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        self._logger.debug(f"开始测试 {algorithm_name} - 文件: {os.path.basename(file_path)} ({file_size_mb:.2f}MB)")
        
        # 开始性能监控
        start_memory = self.performance_monitor.get_memory_usage()
        start_time = time.time()
        
        try:
            # 执行算法
            algorithm_result = algorithm_func()
            
            # 记录性能指标
            end_time = time.time()
            end_memory = self.performance_monitor.get_memory_usage()
            processing_time = end_time - start_time
            memory_usage = max(end_memory - start_memory, 0)
            
            # 计算吞吐量指标
            throughput_mbps = file_size_mb / processing_time if processing_time > 0 else 0
            packets_per_second = algorithm_result.get('packets_processed', 0) / processing_time if processing_time > 0 else 0
            
            result = BenchmarkResult(
                algorithm_name=algorithm_name,
                file_size_mb=file_size_mb,
                processing_time_seconds=processing_time,
                memory_usage_mb=memory_usage,
                packets_processed=algorithm_result.get('packets_processed', 0),
                files_processed=1,
                throughput_mbps=throughput_mbps,
                packets_per_second=packets_per_second,
                success=True
            )
            
            self._logger.info(f"{algorithm_name} 测试完成: {processing_time:.2f}s, {throughput_mbps:.2f}MB/s")
            
        except Exception as e:
            self._logger.error(f"{algorithm_name} 测试失败: {str(e)}")
            result = BenchmarkResult(
                algorithm_name=algorithm_name,
                file_size_mb=file_size_mb,
                processing_time_seconds=0,
                memory_usage_mb=0,
                packets_processed=0,
                files_processed=0,
                throughput_mbps=0,
                packets_per_second=0,
                success=False,
                error_message=str(e)
            )
        
        self.results.append(result)
        return result
    
    def _run_ip_anonymization(self, strategy: HierarchicalAnonymizationStrategy, 
                            file_path: str) -> Dict[str, Any]:
        """运行IP匿名化算法"""
        # 构建映射
        files_to_process = [os.path.basename(file_path)]
        subdir_path = os.path.dirname(file_path)
        error_log = []
        
        mapping = strategy.create_mapping(files_to_process, subdir_path, error_log)
        
        # 计算处理的数据包数（估算）
        packet_count = 0
        try:
            from scapy.all import PcapReader, PcapNgReader
            ext = os.path.splitext(file_path)[1].lower()
            reader_class = PcapNgReader if ext == ".pcapng" else PcapReader
            
            with reader_class(file_path) as reader:
                for _ in reader:
                    packet_count += 1
        except Exception:
            packet_count = 0
            
        return {
            'packets_processed': packet_count,
            'mapping_size': len(mapping),
            'errors': len(error_log)
        }
    
    def _run_packet_trimming(self, trimming_step: IntelligentTrimmingStep, 
                           file_path: str) -> Dict[str, Any]:
        """运行数据包裁切算法"""
        with tempfile.NamedTemporaryFile(suffix='.pcap', delete=False) as temp_file:
            temp_output = temp_file.name
        
        try:
            result = trimming_step.process_file(file_path, temp_output)
            return {
                'packets_processed': result.get('total_packets', 0),
                'trimmed_packets': result.get('trimmed_packets', 0),
                'trim_rate': result.get('trim_rate', 0)
            }
        finally:
            if os.path.exists(temp_output):
                os.unlink(temp_output)
    
    def _run_deduplication(self, dedup_step: DeduplicationStep, 
                         file_path: str) -> Dict[str, Any]:
        """运行去重算法"""
        with tempfile.NamedTemporaryFile(suffix='.pcap', delete=False) as temp_file:
            temp_output = temp_file.name
        
        try:
            result = dedup_step.process_file(file_path, temp_output)
            return {
                'packets_processed': result.get('total_packets', 0),
                'unique_packets': result.get('unique_packets', 0),
                'removed_count': result.get('removed_count', 0)
            }
        finally:
            if os.path.exists(temp_output):
                os.unlink(temp_output)
    
    def run_full_benchmark_suite(self) -> Dict[str, List[BenchmarkResult]]:
        """
        运行完整的基准测试套件
        
        Returns:
            Dict[str, List[BenchmarkResult]]: 所有算法的基准测试结果
        """
        self._logger.info("开始运行完整基准测试套件")
        
        results = {}
        
        # 运行各算法基准测试
        results['ip_anonymization_original'] = self.benchmark_ip_anonymization()
        results['ip_anonymization_optimized'] = self.benchmark_ip_anonymization_optimized()
        results['packet_trimming'] = self.benchmark_packet_trimming()
        results['deduplication'] = self.benchmark_deduplication()
        
        # 生成汇总报告
        self._generate_summary_report(results)
        
        self._logger.info("完整基准测试套件运行完成")
        return results
    
    def _generate_summary_report(self, results: Dict[str, List[BenchmarkResult]]):
        """生成基准测试汇总报告"""
        self._logger.info("=== 基准测试汇总报告 ===")
        
        for algorithm, result_list in results.items():
            if not result_list:
                continue
                
            successful_results = [r for r in result_list if r.success]
            if not successful_results:
                self._logger.warning(f"{algorithm}: 所有测试都失败了")
                continue
            
            avg_throughput = sum(r.throughput_mbps for r in successful_results) / len(successful_results)
            avg_packets_per_sec = sum(r.packets_per_second for r in successful_results) / len(successful_results)
            avg_memory = sum(r.memory_usage_mb for r in successful_results) / len(successful_results)
            
            self._logger.info(f"{algorithm}:")
            self._logger.info(f"  平均吞吐量: {avg_throughput:.2f} MB/s")
            self._logger.info(f"  平均处理速度: {avg_packets_per_sec:.0f} packets/s") 
            self._logger.info(f"  平均内存使用: {avg_memory:.1f} MB")
            self._logger.info(f"  成功测试: {len(successful_results)}/{len(result_list)}")
    
    def export_results(self, output_file: str = "benchmark_results.json"):
        """
        导出基准测试结果到文件
        
        Args:
            output_file: 输出文件路径
        """
        import json
        from dataclasses import asdict
        
        export_data = {
            'timestamp': time.time(),
            'results': [asdict(result) for result in self.results]
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
            
        self._logger.info(f"基准测试结果已导出到: {output_file}") 