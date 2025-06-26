#!/usr/bin/env python3
"""
独立PCAP掩码处理器 - 性能测试示例

本示例提供了完整的性能测试框架，包括：
- 性能监控器
- 基准测试套件
- 内存使用分析
- 性能报告生成
- 性能回归测试

作者: PktMask开发团队
版本: 1.0.0
日期: 2025-06-22
"""

import os
import sys
import time
import json
import platform
import statistics
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Tuple
from contextlib import contextmanager

# 添加项目路径到sys.path以便导入模块
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from pktmask.core.independent_pcap_masker import (
    IndependentPcapMasker,
    SequenceMaskTable, 
    MaskEntry, 
    MaskingResult
)


@dataclass
class PerformanceMetrics:
    """性能指标数据类"""
    test_name: str
    file_name: str
    file_size: int
    total_packets: int
    modified_packets: int
    bytes_masked: int
    processing_time: float
    memory_before: float
    memory_after: float
    memory_peak: float
    cpu_usage: float
    success: bool
    error_message: Optional[str] = None
    
    @property
    def processing_speed_pps(self) -> float:
        """处理速度（包/秒）"""
        return self.total_packets / self.processing_time if self.processing_time > 0 else 0
    
    @property
    def memory_delta(self) -> float:
        """内存增长（MB）"""
        return self.memory_after - self.memory_before
    
    @property
    def bytes_per_second(self) -> float:
        """字节处理速度（B/s）"""
        return self.file_size / self.processing_time if self.processing_time > 0 else 0
    
    @property
    def modification_rate(self) -> float:
        """修改率（%）"""
        return (self.modified_packets / self.total_packets * 100) if self.total_packets > 0 else 0


class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self):
        self.metrics: List[PerformanceMetrics] = []
        self._psutil_available = self._check_psutil()
    
    def _check_psutil(self) -> bool:
        """检查psutil是否可用"""
        try:
            import psutil
            return True
        except ImportError:
            print("⚠️  psutil未安装，内存和CPU监控功能受限")
            return False
    
    def get_memory_usage(self) -> float:
        """获取内存使用量（MB）"""
        if self._psutil_available:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        return 0.0
    
    def get_cpu_usage(self) -> float:
        """获取CPU使用率（%）"""
        if self._psutil_available:
            import psutil
            return psutil.cpu_percent(interval=0.1)
        return 0.0
    
    @contextmanager
    def monitor_test(self, test_name: str, file_path: str):
        """性能监控上下文管理器"""
        # 获取文件信息
        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
        
        # 开始监控
        memory_before = self.get_memory_usage()
        cpu_before = self.get_cpu_usage()
        start_time = time.time()
        
        print(f"🏁 开始性能测试: {test_name}")
        print(f"   文件: {os.path.basename(file_path)} ({file_size:,} bytes)")
        
        test_result = {
            "test_name": test_name,
            "file_name": os.path.basename(file_path),
            "file_size": file_size,
            "memory_before": memory_before,
            "start_time": start_time,
            "success": True,
            "error_message": None
        }
        
        try:
            yield test_result
        except Exception as e:
            test_result["success"] = False
            test_result["error_message"] = str(e)
            print(f"❌ 性能测试异常: {e}")
        finally:
            # 结束监控
            end_time = time.time()
            memory_after = self.get_memory_usage()
            cpu_after = self.get_cpu_usage()
            
            processing_time = end_time - start_time
            memory_delta = memory_after - memory_before
            avg_cpu = (cpu_before + cpu_after) / 2
            
            print(f"⏱️  测试完成: {test_name}")
            print(f"   处理时间: {processing_time:.3f} 秒")
            print(f"   内存增长: {memory_delta:+.2f} MB")
            print(f"   CPU使用率: {avg_cpu:.1f}%")
            
            # 创建性能指标
            metrics = PerformanceMetrics(
                test_name=test_name,
                file_name=test_result["file_name"],
                file_size=file_size,
                total_packets=test_result.get("total_packets", 0),
                modified_packets=test_result.get("modified_packets", 0),
                bytes_masked=test_result.get("bytes_masked", 0),
                processing_time=processing_time,
                memory_before=memory_before,
                memory_after=memory_after,
                memory_peak=max(memory_before, memory_after),
                cpu_usage=avg_cpu,
                success=test_result["success"],
                error_message=test_result.get("error_message")
            )
            
            self.metrics.append(metrics)
            
            if metrics.success and metrics.total_packets > 0:
                print(f"   处理速度: {metrics.processing_speed_pps:.1f} pps")
                print(f"   修改率: {metrics.modification_rate:.1f}%")
    
    def get_system_info(self) -> Dict:
        """获取系统信息"""
        info = {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "cpu_count": os.cpu_count(),
            "architecture": platform.architecture()[0]
        }
        
        if self._psutil_available:
            import psutil
            info.update({
                "total_memory": psutil.virtual_memory().total / 1024 / 1024 / 1024,  # GB
                "available_memory": psutil.virtual_memory().available / 1024 / 1024 / 1024,  # GB
                "cpu_freq": psutil.cpu_freq().current if psutil.cpu_freq() else "Unknown"
            })
        
        return info
    
    def generate_report(self, output_file: Path):
        """生成性能测试报告"""
        report = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "system_info": self.get_system_info(),
            "test_summary": self._generate_summary(),
            "detailed_metrics": [asdict(m) for m in self.metrics]
        }
        
        # 写入JSON报告
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"📊 性能报告已保存: {output_file}")
        
        # 显示摘要
        self._print_summary()
    
    def _generate_summary(self) -> Dict:
        """生成测试摘要"""
        if not self.metrics:
            return {}
        
        successful_tests = [m for m in self.metrics if m.success]
        
        if not successful_tests:
            return {"total_tests": len(self.metrics), "successful_tests": 0}
        
        processing_times = [m.processing_time for m in successful_tests]
        speeds = [m.processing_speed_pps for m in successful_tests]
        memory_deltas = [m.memory_delta for m in successful_tests]
        
        return {
            "total_tests": len(self.metrics),
            "successful_tests": len(successful_tests),
            "failed_tests": len(self.metrics) - len(successful_tests),
            "avg_processing_time": statistics.mean(processing_times),
            "min_processing_time": min(processing_times),
            "max_processing_time": max(processing_times),
            "avg_processing_speed": statistics.mean(speeds),
            "max_processing_speed": max(speeds),
            "min_processing_speed": min(speeds),
            "avg_memory_delta": statistics.mean(memory_deltas),
            "max_memory_delta": max(memory_deltas),
            "total_packets_processed": sum(m.total_packets for m in successful_tests),
            "total_bytes_masked": sum(m.bytes_masked for m in successful_tests)
        }
    
    def _print_summary(self):
        """打印测试摘要"""
        summary = self._generate_summary()
        
        if not summary:
            print("⚠️  无性能数据可显示")
            return
        
        print("\n" + "=" * 60)
        print("性能测试摘要")
        print("=" * 60)
        
        print(f"总测试数: {summary['total_tests']}")
        print(f"成功测试: {summary['successful_tests']}")
        print(f"失败测试: {summary['failed_tests']}")
        
        if summary['successful_tests'] > 0:
            print(f"\n处理时间统计:")
            print(f"   平均: {summary['avg_processing_time']:.3f} 秒")
            print(f"   最快: {summary['min_processing_time']:.3f} 秒")
            print(f"   最慢: {summary['max_processing_time']:.3f} 秒")
            
            print(f"\n处理速度统计:")
            print(f"   平均: {summary['avg_processing_speed']:.1f} pps")
            print(f"   最快: {summary['max_processing_speed']:.1f} pps")
            print(f"   最慢: {summary['min_processing_speed']:.1f} pps")
            
            print(f"\n内存使用统计:")
            print(f"   平均增长: {summary['avg_memory_delta']:.2f} MB")
            print(f"   最大增长: {summary['max_memory_delta']:.2f} MB")
            
            print(f"\n总体统计:")
            print(f"   处理数据包: {summary['total_packets_processed']:,}")
            print(f"   掩码字节数: {summary['total_bytes_masked']:,}")


class BenchmarkSuite:
    """基准测试套件"""
    
    def __init__(self, monitor: PerformanceMonitor):
        self.monitor = monitor
    
    def run_initialization_benchmark(self):
        """初始化性能基准测试"""
        print("\n" + "=" * 60)
        print("基准测试1: 初始化性能")
        print("=" * 60)
        
        configs = [
            ("默认配置", {}),
            ("最小配置", {
                'log_level': 'ERROR',
                'recalculate_checksums': False,
                'strict_consistency_mode': False
            }),
            ("完整配置", {
                'log_level': 'DEBUG',
                'recalculate_checksums': True,
                'strict_consistency_mode': True,
                'processing_batch_size': 500,
                'memory_limit_mb': 256
            })
        ]
        
        for config_name, config in configs:
            with self.monitor.monitor_test(f"初始化-{config_name}", "dummy_file") as test_result:
                start_time = time.time()
                masker = IndependentPcapMasker(config)
                end_time = time.time()
                
                initialization_time = end_time - start_time
                print(f"   {config_name} 初始化时间: {initialization_time:.4f} 秒")
                
                test_result.update({
                    "total_packets": 0,
                    "modified_packets": 0,
                    "bytes_masked": 0
                })
    
    def run_mask_table_benchmark(self):
        """掩码表性能基准测试"""
        print("\n" + "=" * 60)
        print("基准测试2: 掩码表性能")
        print("=" * 60)
        
        table_sizes = [10, 100, 1000, 5000]
        
        for size in table_sizes:
            with self.monitor.monitor_test(f"掩码表-{size}条目", "dummy_file") as test_result:
                # 创建指定大小的掩码表
                mask_table = SequenceMaskTable()
                
                start_time = time.time()
                
                for i in range(size):
                    mask_table.add_entry(MaskEntry(
                        stream_id=f"TCP_192.168.1.{i%255}:443_10.0.0.{i%255}:54321_forward",
                        sequence_start=i * 1000,
                        sequence_end=(i + 1) * 1000,
                        mask_type="mask_after",
                        mask_params={"keep_bytes": 5}
                    ))
                
                creation_time = time.time() - start_time
                
                # 测试查找性能
                search_start = time.time()
                for i in range(1000):
                    stream_id = f"TCP_192.168.1.{i%255}:443_10.0.0.{i%255}:54321_forward"
                    sequence = (i % size) * 1000 + 500
                    matches = mask_table.find_matches(stream_id, sequence)
                
                search_time = time.time() - search_start
                
                print(f"   {size} 条目表:")
                print(f"     创建时间: {creation_time:.4f} 秒")
                print(f"     1000次查找: {search_time:.4f} 秒")
                print(f"     平均查找: {search_time/1000*1000:.4f} ms")
                
                test_result.update({
                    "total_packets": size,
                    "modified_packets": 0,
                    "bytes_masked": 0
                })
    
    def run_file_processing_benchmark(self, test_files: List[Tuple[str, str]]):
        """文件处理性能基准测试"""
        print("\n" + "=" * 60)
        print("基准测试3: 文件处理性能")
        print("=" * 60)
        
        # 创建标准掩码表
        mask_table = SequenceMaskTable()
        mask_table.add_entry(MaskEntry(
            stream_id="TCP_192.168.1.100:443_10.0.0.1:54321_forward",
            sequence_start=1000,
            sequence_end=5000,
            mask_type="mask_after",
            mask_params={"keep_bytes": 5}
        ))
        
        # 测试不同的配置
        configs = [
            ("快速模式", {
                'recalculate_checksums': False,
                'strict_consistency_mode': False,
                'log_level': 'ERROR',
                'processing_batch_size': 2000
            }),
            ("标准模式", {}),
            ("高质量模式", {
                'recalculate_checksums': True,
                'strict_consistency_mode': True,
                'log_level': 'INFO',
                'processing_batch_size': 500
            })
        ]
        
        for file_name, file_path in test_files:
            if not os.path.exists(file_path):
                print(f"⚠️  测试文件不存在: {file_path}")
                continue
            
            print(f"\n测试文件: {file_name}")
            
            for config_name, config in configs:
                test_name = f"文件处理-{file_name}-{config_name}"
                output_file = f"examples/output/processed/benchmark_{file_name}_{config_name.replace(' ', '_')}.pcap"
                
                # 确保输出目录存在
                os.makedirs(os.path.dirname(output_file), exist_ok=True)
                
                with self.monitor.monitor_test(test_name, file_path) as test_result:
                    masker = IndependentPcapMasker(config)
                    
                    result = masker.mask_pcap_with_sequences(
                        file_path, mask_table, output_file
                    )
                    
                    if result.success:
                        test_result.update({
                            "total_packets": result.total_packets,
                            "modified_packets": result.modified_packets,
                            "bytes_masked": result.bytes_masked
                        })
                        
                        print(f"     {config_name}: {result.modified_packets}/{result.total_packets} 包被修改")
                    else:
                        test_result["success"] = False
                        test_result["error_message"] = result.error_message
                        print(f"     {config_name}: 处理失败 - {result.error_message}")
    
    def run_stress_test(self, test_file: str, iterations: int = 10):
        """压力测试"""
        print("\n" + "=" * 60)
        print(f"基准测试4: 压力测试 ({iterations} 次迭代)")
        print("=" * 60)
        
        if not os.path.exists(test_file):
            print(f"⚠️  测试文件不存在: {test_file}")
            return
        
        mask_table = SequenceMaskTable()
        mask_table.add_entry(MaskEntry(
            stream_id="TCP_192.168.1.100:443_10.0.0.1:54321_forward",
            sequence_start=1000,
            sequence_end=3000,
            mask_type="mask_after",
            mask_params={"keep_bytes": 8}
        ))
        
        masker = IndependentPcapMasker({
            'log_level': 'ERROR'  # 减少日志输出
        })
        
        with self.monitor.monitor_test(f"压力测试-{iterations}次", test_file) as test_result:
            times = []
            total_packets = 0
            total_modified = 0
            total_bytes_masked = 0
            
            for i in range(iterations):
                output_file = f"examples/output/processed/stress_test_{i}.pcap"
                
                iteration_start = time.time()
                result = masker.mask_pcap_with_sequences(test_file, mask_table, output_file)
                iteration_end = time.time()
                
                if result.success:
                    times.append(iteration_end - iteration_start)
                    total_packets = result.total_packets  # 应该每次都相同
                    total_modified += result.modified_packets
                    total_bytes_masked += result.bytes_masked
                    
                    # 清理临时文件
                    if os.path.exists(output_file):
                        os.remove(output_file)
                else:
                    print(f"   迭代 {i+1} 失败: {result.error_message}")
            
            if times:
                avg_time = statistics.mean(times)
                min_time = min(times)
                max_time = max(times)
                std_dev = statistics.stdev(times) if len(times) > 1 else 0
                
                print(f"   成功完成 {len(times)}/{iterations} 次迭代")
                print(f"   平均时间: {avg_time:.3f} 秒")
                print(f"   最快时间: {min_time:.3f} 秒")
                print(f"   最慢时间: {max_time:.3f} 秒")
                print(f"   标准差: {std_dev:.3f} 秒")
                print(f"   变异系数: {std_dev/avg_time*100:.1f}%" if avg_time > 0 else "")
                
                test_result.update({
                    "total_packets": total_packets,
                    "modified_packets": total_modified // len(times),  # 平均值
                    "bytes_masked": total_bytes_masked // len(times)   # 平均值
                })
            else:
                test_result["success"] = False
                test_result["error_message"] = "所有迭代都失败"


def find_test_files() -> List[Tuple[str, str]]:
    """查找可用的测试文件"""
    test_files = []
    
    # 预定义的测试文件位置
    candidate_files = [
        ("tls-single", "tests/samples/tls-single/tls_sample.pcap"),
        ("http-sample", "tests/samples/http/http_sample.pcap"),
        ("small-pcap", "tests/samples/small.pcap"),
        ("mixed-traffic", "tests/samples/mixed_traffic.pcap")
    ]
    
    # 查找实际存在的文件
    for name, path in candidate_files:
        if os.path.exists(path):
            test_files.append((name, path))
    
    # 如果没有找到预定义文件，搜索samples目录
    if not test_files:
        samples_dir = Path("tests/samples")
        if samples_dir.exists():
            for pcap_file in samples_dir.rglob("*.pcap"):
                if pcap_file.stat().st_size > 0:  # 确保文件不为空
                    relative_name = str(pcap_file.relative_to(samples_dir)).replace("/", "-")
                    test_files.append((relative_name, str(pcap_file)))
                    if len(test_files) >= 3:  # 限制测试文件数量
                        break
    
    return test_files


def main():
    """主函数，运行完整的性能测试套件"""
    print("独立PCAP掩码处理器 - 性能测试套件")
    print("=" * 60)
    print("本测试套件将全面评估掩码处理器的性能特征")
    print()
    
    # 创建输出目录
    output_dir = Path("examples/output")
    output_dir.mkdir(exist_ok=True)
    
    # 创建性能监控器
    monitor = PerformanceMonitor()
    
    # 显示系统信息
    system_info = monitor.get_system_info()
    print("系统信息:")
    for key, value in system_info.items():
        print(f"   {key}: {value}")
    
    # 创建基准测试套件
    benchmark_suite = BenchmarkSuite(monitor)
    
    # 查找测试文件
    test_files = find_test_files()
    
    if test_files:
        print(f"\n发现 {len(test_files)} 个测试文件:")
        for name, path in test_files:
            size = os.path.getsize(path)
            print(f"   {name}: {size:,} bytes")
    else:
        print("\n⚠️  未找到测试文件，部分基准测试将被跳过")
    
    # 运行基准测试套件
    try:
        # 1. 初始化性能测试
        benchmark_suite.run_initialization_benchmark()
        
        # 2. 掩码表性能测试
        benchmark_suite.run_mask_table_benchmark()
        
        # 3. 文件处理性能测试
        if test_files:
            benchmark_suite.run_file_processing_benchmark(test_files)
        
        # 4. 压力测试（使用第一个可用文件）
        if test_files:
            stress_test_file = test_files[0][1]
            benchmark_suite.run_stress_test(stress_test_file, iterations=5)
        
    except KeyboardInterrupt:
        print("\n⚠️  用户中断测试")
    except Exception as e:
        print(f"\n❌ 测试套件执行异常: {str(e)}")
    
    # 生成性能报告
    report_file = output_dir / "performance_test_report.json"
    monitor.generate_report(report_file)
    
    print("\n性能测试完成！")
    print(f"详细报告已保存至: {report_file}")
    
    # 清理临时文件
    print("\n🗑️  清理临时文件...")
    temp_files = list(output_dir.glob("benchmark_*.pcap")) + list(output_dir.glob("stress_test_*.pcap"))
    
    for temp_file in temp_files:
        try:
            temp_file.unlink()
            print(f"   清理: {temp_file.name}")
        except Exception as e:
            print(f"   清理失败: {temp_file.name} - {e}")
    
    print("性能测试套件执行完成！")


if __name__ == "__main__":
    main() 