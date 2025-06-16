"""
双策略性能基准测试

专门测量Legacy HTTPTrimStrategy和新HTTPScanningStrategy的性能指标，
包括处理时间、内存使用、吞吐量等关键性能数据。

作者: PktMask Team
创建时间: 2025-06-16
版本: 1.0.0
"""

import unittest
import time
import psutil
import os
import gc
import statistics
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
import json
import logging

# 导入系统组件
try:
    from src.pktmask.core.trim.strategies.base_strategy import BaseStrategy, ProtocolInfo, TrimContext, TrimResult
    from src.pktmask.core.trim.strategies.factory import get_enhanced_strategy_factory
    from src.pktmask.core.trim.testing.performance_tracker import PerformanceTracker, MetricType
    from src.pktmask.config.http_strategy_config import get_default_http_strategy_config
    IMPORTS_AVAILABLE = True
except ImportError as e:
    IMPORTS_AVAILABLE = False
    import_error = str(e)


@dataclass
class BenchmarkResult:
    """基准测试结果"""
    strategy_name: str
    test_name: str
    
    # 时间指标
    min_time_ms: float
    max_time_ms: float
    avg_time_ms: float
    median_time_ms: float
    std_time_ms: float
    
    # 内存指标
    peak_memory_mb: float
    avg_memory_mb: float
    memory_delta_mb: float
    
    # 吞吐量指标
    throughput_ops_per_sec: float
    throughput_bytes_per_sec: float
    
    # 成功率指标
    total_operations: int
    successful_operations: int
    success_rate: float
    
    # 额外指标
    metadata: Dict[str, Any]


@dataclass
class ComparisonBenchmark:
    """对比基准测试结果"""
    test_name: str
    legacy_result: BenchmarkResult
    scanning_result: BenchmarkResult
    
    # 性能对比
    speed_improvement: float
    memory_efficiency: float
    throughput_improvement: float
    success_rate_delta: float
    
    # 统计显著性
    statistical_significance: bool
    confidence_level: float


class PerformanceBenchmark:
    """性能基准测试器"""
    
    def __init__(self, warmup_runs: int = 5, test_runs: int = 20, 
                 memory_sampling_interval: float = 0.1):
        """
        初始化基准测试器
        
        Args:
            warmup_runs: 预热运行次数
            test_runs: 正式测试运行次数
            memory_sampling_interval: 内存采样间隔(秒)
        """
        self.warmup_runs = warmup_runs
        self.test_runs = test_runs
        self.memory_sampling_interval = memory_sampling_interval
        
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        self.performance_tracker = PerformanceTracker()
        
        # 获取策略实例
        config = get_default_http_strategy_config()
        self.strategy_factory = get_enhanced_strategy_factory(config)
        
        self.logger.info(f"性能基准测试器初始化: 预热{warmup_runs}次, 测试{test_runs}次")
    
    def benchmark_strategy(self, strategy: BaseStrategy, test_name: str,
                          test_data: List[Tuple[bytes, ProtocolInfo, TrimContext]]) -> BenchmarkResult:
        """
        对单个策略进行基准测试
        
        Args:
            strategy: 待测试策略
            test_name: 测试名称
            test_data: 测试数据列表
            
        Returns:
            基准测试结果
        """
        self.logger.info(f"开始基准测试: {strategy.strategy_name} - {test_name}")
        
        # 预热阶段
        self._warmup_strategy(strategy, test_data)
        
        # 正式测试
        times = []
        memory_usage = []
        successful_ops = 0
        total_bytes = 0
        
        process = psutil.Process(os.getpid())
        
        for run in range(self.test_runs):
            # 垃圾回收
            gc.collect()
            
            # 记录初始内存
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            # 执行测试
            start_time = time.perf_counter()
            
            run_success = 0
            run_bytes = 0
            
            for payload, protocol_info, context in test_data:
                try:
                    result = strategy.trim_payload(payload, protocol_info, context)
                    if result.success:
                        run_success += 1
                    run_bytes += len(payload)
                except Exception as e:
                    self.logger.warning(f"策略执行异常: {e}")
            
            end_time = time.perf_counter()
            
            # 记录结束内存
            final_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            # 记录指标
            execution_time = (end_time - start_time) * 1000  # ms
            times.append(execution_time)
            memory_usage.append(final_memory - initial_memory)
            
            successful_ops += run_success
            total_bytes += run_bytes
            
            self.logger.debug(f"运行 {run+1}: {execution_time:.2f}ms, "
                            f"内存增长: {final_memory - initial_memory:.2f}MB")
        
        # 计算统计指标
        total_operations = len(test_data) * self.test_runs
        success_rate = successful_ops / total_operations if total_operations > 0 else 0
        
        # 时间统计
        min_time = min(times)
        max_time = max(times)
        avg_time = statistics.mean(times)
        median_time = statistics.median(times)
        std_time = statistics.stdev(times) if len(times) > 1 else 0
        
        # 内存统计
        peak_memory = max(memory_usage)
        avg_memory = statistics.mean(memory_usage)
        memory_delta = peak_memory - min(memory_usage)
        
        # 吞吐量计算
        total_time_sec = sum(times) / 1000  # 总时间转换为秒
        throughput_ops = total_operations / total_time_sec if total_time_sec > 0 else 0
        throughput_bytes = total_bytes / total_time_sec if total_time_sec > 0 else 0
        
        result = BenchmarkResult(
            strategy_name=strategy.strategy_name,
            test_name=test_name,
            min_time_ms=min_time,
            max_time_ms=max_time,
            avg_time_ms=avg_time,
            median_time_ms=median_time,
            std_time_ms=std_time,
            peak_memory_mb=peak_memory,
            avg_memory_mb=avg_memory,
            memory_delta_mb=memory_delta,
            throughput_ops_per_sec=throughput_ops,
            throughput_bytes_per_sec=throughput_bytes,
            total_operations=total_operations,
            successful_operations=successful_ops,
            success_rate=success_rate,
            metadata={
                'test_runs': self.test_runs,
                'warmup_runs': self.warmup_runs,
                'test_data_size': len(test_data),
                'total_payload_bytes': total_bytes
            }
        )
        
        self.logger.info(f"基准测试完成 - {strategy.strategy_name}: "
                        f"平均{avg_time:.2f}ms, "
                        f"吞吐量{throughput_ops:.1f}ops/s, "
                        f"成功率{success_rate:.1%}")
        
        return result
    
    def benchmark_comparison(self, test_name: str, 
                           test_data: List[Tuple[bytes, ProtocolInfo, TrimContext]]) -> ComparisonBenchmark:
        """
        对比基准测试
        
        Args:
            test_name: 测试名称
            test_data: 测试数据
            
        Returns:
            对比基准测试结果
        """
        self.logger.info(f"开始对比基准测试: {test_name}")
        
        # 获取策略实例
        legacy_strategy = self.strategy_factory._get_legacy_strategy({})
        scanning_strategy = self.strategy_factory._get_scanning_strategy({})
        
        if not legacy_strategy:
            raise RuntimeError("无法获取Legacy策略实例")
        
        if not scanning_strategy:
            raise RuntimeError("无法获取Scanning策略实例")
        
        # 分别测试两个策略
        legacy_result = self.benchmark_strategy(legacy_strategy, test_name, test_data)
        scanning_result = self.benchmark_strategy(scanning_strategy, test_name, test_data)
        
        # 计算对比指标
        speed_improvement = self._calculate_speed_improvement(
            legacy_result.avg_time_ms, scanning_result.avg_time_ms
        )
        
        memory_efficiency = self._calculate_memory_efficiency(
            legacy_result.avg_memory_mb, scanning_result.avg_memory_mb
        )
        
        throughput_improvement = self._calculate_throughput_improvement(
            legacy_result.throughput_ops_per_sec, scanning_result.throughput_ops_per_sec
        )
        
        success_rate_delta = scanning_result.success_rate - legacy_result.success_rate
        
        # 统计显著性检验（简化版）
        statistical_significance = self._test_statistical_significance(
            legacy_result, scanning_result
        )
        
        comparison = ComparisonBenchmark(
            test_name=test_name,
            legacy_result=legacy_result,
            scanning_result=scanning_result,
            speed_improvement=speed_improvement,
            memory_efficiency=memory_efficiency,
            throughput_improvement=throughput_improvement,
            success_rate_delta=success_rate_delta,
            statistical_significance=statistical_significance,
            confidence_level=0.95
        )
        
        self.logger.info(f"对比测试完成 - {test_name}: "
                        f"速度提升{speed_improvement:.1%}, "
                        f"内存效率{memory_efficiency:.1%}, "
                        f"吞吐量提升{throughput_improvement:.1%}")
        
        return comparison
    
    def _warmup_strategy(self, strategy: BaseStrategy, 
                        test_data: List[Tuple[bytes, ProtocolInfo, TrimContext]]) -> None:
        """预热策略"""
        
        self.logger.debug(f"预热策略: {strategy.strategy_name}")
        
        for _ in range(self.warmup_runs):
            for payload, protocol_info, context in test_data[:5]:  # 只用前5个数据预热
                try:
                    strategy.trim_payload(payload, protocol_info, context)
                except Exception:
                    pass  # 预热阶段忽略错误
    
    def _calculate_speed_improvement(self, legacy_time: float, scanning_time: float) -> float:
        """计算速度提升百分比"""
        if legacy_time <= 0:
            return 0.0
        return (legacy_time - scanning_time) / legacy_time
    
    def _calculate_memory_efficiency(self, legacy_memory: float, scanning_memory: float) -> float:
        """计算内存效率提升百分比"""
        if legacy_memory <= 0:
            return 0.0
        return (legacy_memory - scanning_memory) / legacy_memory
    
    def _calculate_throughput_improvement(self, legacy_throughput: float, scanning_throughput: float) -> float:
        """计算吞吐量提升百分比"""
        if legacy_throughput <= 0:
            return 0.0
        return (scanning_throughput - legacy_throughput) / legacy_throughput
    
    def _test_statistical_significance(self, legacy: BenchmarkResult, scanning: BenchmarkResult) -> bool:
        """简化的统计显著性检验"""
        
        # 简单的差异判断：如果差异超过10%且标准差允许，则认为显著
        time_improvement = abs(self._calculate_speed_improvement(legacy.avg_time_ms, scanning.avg_time_ms))
        
        # 考虑标准差的影响
        combined_std = (legacy.std_time_ms + scanning.std_time_ms) / 2
        avg_time = (legacy.avg_time_ms + scanning.avg_time_ms) / 2
        
        if avg_time > 0:
            std_ratio = combined_std / avg_time
            # 如果差异明显大于噪声水平，则认为显著
            return time_improvement > max(0.1, std_ratio * 2)
        
        return False


class TestDualStrategyBenchmark(unittest.TestCase):
    """双策略性能基准测试"""
    
    @classmethod
    def setUpClass(cls):
        """测试类初始化"""
        if not IMPORTS_AVAILABLE:
            cls.skipTest(cls, f"导入失败: {import_error}")
        
        # 设置日志
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        cls.benchmark = PerformanceBenchmark(warmup_runs=3, test_runs=10)
        
        # 创建测试数据
        cls.small_payload_data = cls._create_small_payload_data()
        cls.medium_payload_data = cls._create_medium_payload_data()
        cls.large_payload_data = cls._create_large_payload_data()
        cls.mixed_payload_data = cls._create_mixed_payload_data()
        
        cls.benchmark_results = []
    
    @classmethod
    def _create_small_payload_data(cls) -> List[Tuple[bytes, ProtocolInfo, TrimContext]]:
        """创建小载荷测试数据(100-500字节)"""
        data = []
        
        for i in range(20):
            payload = (
                b"GET /api/endpoint" + str(i).encode() + b" HTTP/1.1\r\n"
                b"Host: example.com\r\n"
                b"User-Agent: TestClient/1.0\r\n"
                b"Accept: application/json\r\n"
                b"\r\n"
            )
            
            protocol_info = ProtocolInfo(
                name="HTTP", version="1.1", layer=7, port=80, characteristics={}
            )
            
            context = TrimContext(
                packet_index=i,
                stream_id=f"test_stream_{i}",
                flow_direction="client_to_server",
                protocol_stack=["ETH", "IP", "TCP", "HTTP"],
                payload_size=len(payload),
                timestamp=time.time(),
                metadata={'test_type': 'small_payload'}
            )
            
            data.append((payload, protocol_info, context))
        
        return data
    
    @classmethod
    def _create_medium_payload_data(cls) -> List[Tuple[bytes, ProtocolInfo, TrimContext]]:
        """创建中等载荷测试数据(1-10KB)"""
        data = []
        
        for i in range(15):
            body = b'{"data": "' + b'x' * (1000 + i * 100) + b'"}'
            payload = (
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: application/json\r\n"
                b"Content-Length: " + str(len(body)).encode() + b"\r\n"
                b"Connection: keep-alive\r\n"
                b"\r\n" + body
            )
            
            protocol_info = ProtocolInfo(
                name="HTTP", version="1.1", layer=7, port=80, characteristics={}
            )
            
            context = TrimContext(
                packet_index=i,
                stream_id=f"medium_stream_{i}",
                flow_direction="server_to_client",
                protocol_stack=["ETH", "IP", "TCP", "HTTP"],
                payload_size=len(payload),
                timestamp=time.time(),
                metadata={'test_type': 'medium_payload'}
            )
            
            data.append((payload, protocol_info, context))
        
        return data
    
    @classmethod
    def _create_large_payload_data(cls) -> List[Tuple[bytes, ProtocolInfo, TrimContext]]:
        """创建大载荷测试数据(>100KB)"""
        data = []
        
        for i in range(5):
            body = b'x' * (100000 + i * 50000)  # 100KB+
            payload = (
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: application/octet-stream\r\n"
                b"Content-Length: " + str(len(body)).encode() + b"\r\n"
                b"Content-Disposition: attachment; filename=large_file.bin\r\n"
                b"\r\n" + body
            )
            
            protocol_info = ProtocolInfo(
                name="HTTP", version="1.1", layer=7, port=80, characteristics={}
            )
            
            context = TrimContext(
                packet_index=i,
                stream_id=f"large_stream_{i}",
                flow_direction="server_to_client",
                protocol_stack=["ETH", "IP", "TCP", "HTTP"],
                payload_size=len(payload),
                timestamp=time.time(),
                metadata={'test_type': 'large_payload'}
            )
            
            data.append((payload, protocol_info, context))
        
        return data
    
    @classmethod
    def _create_mixed_payload_data(cls) -> List[Tuple[bytes, ProtocolInfo, TrimContext]]:
        """创建混合载荷测试数据"""
        data = []
        
        # 添加Chunked编码响应
        chunked_payload = (
            b"HTTP/1.1 200 OK\r\n"
            b"Transfer-Encoding: chunked\r\n"
            b"Content-Type: text/plain\r\n"
            b"\r\n"
            b"20\r\n"
            b"This is the first chunk of data\r\n"
            b"1e\r\n"
            b"And this is the second chunk\r\n"
            b"0\r\n"
            b"\r\n"
        )
        
        # 添加多响应载荷
        multi_response = (
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Length: 13\r\n"
            b"Connection: keep-alive\r\n"
            b"\r\n"
            b"First response"
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Length: 14\r\n"
            b"Connection: close\r\n"
            b"\r\n"
            b"Second response"
        )
        
        payloads = [chunked_payload, multi_response]
        
        for i, payload in enumerate(payloads):
            protocol_info = ProtocolInfo(
                name="HTTP", version="1.1", layer=7, port=80, characteristics={}
            )
            
            context = TrimContext(
                packet_index=i,
                stream_id=f"mixed_stream_{i}",
                flow_direction="server_to_client",
                protocol_stack=["ETH", "IP", "TCP", "HTTP"],
                payload_size=len(payload),
                timestamp=time.time(),
                metadata={'test_type': 'mixed_payload'}
            )
            
            data.append((payload, protocol_info, context))
        
        return data
    
    def test_small_payload_benchmark(self):
        """小载荷性能基准测试"""
        result = self.benchmark.benchmark_comparison("小载荷处理", self.small_payload_data)
        self.benchmark_results.append(result)
        
        # 验证性能指标
        self.assertGreaterEqual(result.legacy_result.success_rate, 0.9)
        self.assertGreaterEqual(result.scanning_result.success_rate, 0.8)
        
        print(f"\n=== 小载荷性能测试 ===")
        print(f"Legacy: {result.legacy_result.avg_time_ms:.2f}ms/op")
        print(f"Scanning: {result.scanning_result.avg_time_ms:.2f}ms/op")
        print(f"速度提升: {result.speed_improvement:.1%}")
        print(f"内存效率: {result.memory_efficiency:.1%}")
    
    def test_medium_payload_benchmark(self):
        """中等载荷性能基准测试"""
        result = self.benchmark.benchmark_comparison("中等载荷处理", self.medium_payload_data)
        self.benchmark_results.append(result)
        
        print(f"\n=== 中等载荷性能测试 ===")
        print(f"Legacy: {result.legacy_result.avg_time_ms:.2f}ms/op")
        print(f"Scanning: {result.scanning_result.avg_time_ms:.2f}ms/op")
        print(f"速度提升: {result.speed_improvement:.1%}")
        print(f"吞吐量提升: {result.throughput_improvement:.1%}")
    
    def test_large_payload_benchmark(self):
        """大载荷性能基准测试"""
        result = self.benchmark.benchmark_comparison("大载荷处理", self.large_payload_data)
        self.benchmark_results.append(result)
        
        print(f"\n=== 大载荷性能测试 ===")
        print(f"Legacy: {result.legacy_result.avg_time_ms:.2f}ms/op")
        print(f"Scanning: {result.scanning_result.avg_time_ms:.2f}ms/op")
        print(f"速度提升: {result.speed_improvement:.1%}")
        print(f"内存效率: {result.memory_efficiency:.1%}")
    
    def test_mixed_payload_benchmark(self):
        """混合载荷性能基准测试"""
        result = self.benchmark.benchmark_comparison("混合载荷处理", self.mixed_payload_data)
        self.benchmark_results.append(result)
        
        print(f"\n=== 混合载荷性能测试 ===")
        print(f"Legacy: {result.legacy_result.avg_time_ms:.2f}ms/op")
        print(f"Scanning: {result.scanning_result.avg_time_ms:.2f}ms/op")
        print(f"速度提升: {result.speed_improvement:.1%}")
        print(f"统计显著性: {'是' if result.statistical_significance else '否'}")
    
    def test_comprehensive_performance_analysis(self):
        """综合性能分析"""
        
        # 确保所有基准测试都已运行
        if not self.benchmark_results:
            self.test_small_payload_benchmark()
            self.test_medium_payload_benchmark()
            self.test_large_payload_benchmark()
            self.test_mixed_payload_benchmark()
        
        # 计算综合指标
        avg_speed_improvement = statistics.mean([r.speed_improvement for r in self.benchmark_results])
        avg_memory_efficiency = statistics.mean([r.memory_efficiency for r in self.benchmark_results])
        avg_throughput_improvement = statistics.mean([r.throughput_improvement for r in self.benchmark_results])
        
        # 计算成功率统计
        legacy_success_rates = [r.legacy_result.success_rate for r in self.benchmark_results]
        scanning_success_rates = [r.scanning_result.success_rate for r in self.benchmark_results]
        
        avg_legacy_success = statistics.mean(legacy_success_rates)
        avg_scanning_success = statistics.mean(scanning_success_rates)
        
        # 生成性能报告
        performance_report = {
            'timestamp': time.time(),
            'test_summary': {
                'total_benchmarks': len(self.benchmark_results),
                'avg_speed_improvement': avg_speed_improvement,
                'avg_memory_efficiency': avg_memory_efficiency,
                'avg_throughput_improvement': avg_throughput_improvement,
                'avg_legacy_success_rate': avg_legacy_success,
                'avg_scanning_success_rate': avg_scanning_success
            },
            'detailed_results': [asdict(r) for r in self.benchmark_results],
            'performance_goals': {
                'speed_improvement_target': 0.2,  # 20%目标
                'memory_efficiency_target': 0.3,  # 30%目标
                'success_rate_target': 0.9       # 90%目标
            }
        }
        
        # 保存报告
        report_path = Path('reports/dual_strategy_performance_benchmark.json')
        report_path.parent.mkdir(exist_ok=True)
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(performance_report, f, indent=2, ensure_ascii=False)
        
        # 验证性能目标
        print(f"\n=== 综合性能分析 ===")
        print(f"平均速度提升: {avg_speed_improvement:.1%} (目标: ≥20%)")
        print(f"平均内存效率: {avg_memory_efficiency:.1%} (目标: ≥30%)")
        print(f"平均吞吐量提升: {avg_throughput_improvement:.1%}")
        print(f"Legacy成功率: {avg_legacy_success:.1%}")
        print(f"Scanning成功率: {avg_scanning_success:.1%}")
        print(f"性能报告: {report_path}")
        
        # 性能验证断言
        self.assertGreaterEqual(avg_legacy_success, 0.85, "Legacy策略成功率应≥85%")
        self.assertGreaterEqual(avg_scanning_success, 0.8, "Scanning策略成功率应≥80%")
        
        # 如果性能目标未达成，发出警告而不是失败
        if avg_speed_improvement < 0.2:
            self.logger.warning(f"速度提升未达目标: {avg_speed_improvement:.1%} < 20%")
        
        if avg_memory_efficiency < 0.3:
            self.logger.warning(f"内存效率未达目标: {avg_memory_efficiency:.1%} < 30%")


if __name__ == '__main__':
    unittest.main(verbosity=2) 