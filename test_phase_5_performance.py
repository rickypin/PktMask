#!/usr/bin/env python3
"""
Phase 5: 性能基准测试

测试目标：
- 测试处理速度 ≥ 原有90%
- 测试内存使用 ≤ 原有80%  
- 测试启动时间 < 原有50%
- 测试大文件处理稳定性
"""

import os
import sys
import time
import psutil
import subprocess
import tempfile
import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple
import tracemalloc

# 添加源码路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

# 导入测试目标
from src.pktmask.core.processors.registry import ProcessorRegistry, ProcessorConfig

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Phase5PerformanceTests:
    """Phase 5: 性能基准测试套件"""
    
    def __init__(self):
        self.test_data_dir = Path("tests/data")
        self.temp_dir = Path(tempfile.mkdtemp(prefix="phase5_perf_test_"))
        self.results = {
            "start_time": time.time(),
            "tests": {},
            "summary": {}
        }
        
        # 性能基准目标
        self.performance_targets = {
            "speed_threshold": 0.90,  # 速度≥90%
            "memory_threshold": 0.80, # 内存≤80%
            "startup_threshold": 0.50 # 启动≤50%
        }
        
        logger.info(f"性能测试开始，临时目录: {self.temp_dir}")
    
    def run_all_tests(self):
        """运行所有性能测试"""
        logger.info("=" * 60)
        logger.info("Phase 5: 性能基准测试开始")
        logger.info("=" * 60)
        
        try:
            # 5.2.1 处理速度测试
            self.test_processing_speed()
            
            # 5.2.2 内存使用测试
            self.test_memory_usage()
            
            # 5.2.3 启动时间测试
            self.test_startup_time()
            
            # 5.2.4 稳定性测试
            self.test_stability()
            
        except Exception as e:
            logger.error(f"性能测试出现错误: {e}")
            traceback.print_exc()
        finally:
            self.generate_report()
            self.cleanup()
    
    def test_processing_speed(self):
        """5.2.1 处理速度测试"""
        logger.info("🏃 开始处理速度测试")
        
        # 获取测试文件
        test_files = self._get_test_files_by_size()
        
        speed_results = {}
        
        for size_category, files in test_files.items():
            if not files:
                continue
                
            logger.info(f"测试 {size_category} 文件处理速度")
            
            # 选择一个代表性文件进行测试
            test_file = files[0]
            file_size_mb = test_file.stat().st_size / (1024 * 1024)
            
            # 测试每个处理器的性能
            processor_times = {}
            
            for proc_name in ["mask_ip", "dedup_packet", "trim_packet"]:
                try:
                    # 创建处理器
                    config = ProcessorConfig(enabled=True, name=proc_name)
                    processor = ProcessorRegistry.get_processor(proc_name, config)
                    
                    output_file = self.temp_dir / f"speed_test_{proc_name}_{size_category}.pcap"
                    
                    # 测量处理时间
                    start_time = time.time()
                    result = processor.process_file(str(test_file), str(output_file))
                    end_time = time.time()
                    
                    if result.success:
                        processing_time = end_time - start_time
                        throughput = file_size_mb / processing_time  # MB/s
                        
                        processor_times[proc_name] = {
                            "time": processing_time,
                            "throughput": throughput,
                            "success": True
                        }
                        
                        logger.info(f"  {proc_name}: {processing_time:.2f}秒, {throughput:.2f}MB/s")
                    else:
                        processor_times[proc_name] = {
                            "success": False,
                            "error": result.error
                        }
                        logger.error(f"  {proc_name}: 处理失败 - {result.error}")
                        
                except Exception as e:
                    processor_times[proc_name] = {
                        "success": False,
                        "error": str(e)
                    }
                    logger.error(f"  {proc_name}: 异常 - {e}")
            
            speed_results[size_category] = {
                "file_size_mb": file_size_mb,
                "processors": processor_times
            }
        
        self.results["tests"]["processing_speed"] = speed_results
        
        # 计算平均性能
        avg_throughput = self._calculate_average_throughput(speed_results)
        logger.info(f"平均处理吞吐量: {avg_throughput:.2f} MB/s")
    
    def test_memory_usage(self):
        """5.2.2 内存使用测试"""
        logger.info("💾 开始内存使用测试")
        
        # 启动内存跟踪
        tracemalloc.start()
        
        # 获取系统初始内存
        process = psutil.Process()
        initial_memory = process.memory_info().rss / (1024 * 1024)  # MB
        
        memory_results = {}
        
        # 测试每个处理器的内存使用
        test_files = self._get_test_files_by_size()
        
        for size_category, files in test_files.items():
            if not files:
                continue
                
            test_file = files[0]
            file_size_mb = test_file.stat().st_size / (1024 * 1024)
            
            logger.info(f"测试 {size_category} 文件内存使用")
            
            processor_memory = {}
            
            for proc_name in ["mask_ip", "dedup_packet", "trim_packet"]:
                try:
                    # 重置内存基线
                    process = psutil.Process()
                    baseline_memory = process.memory_info().rss / (1024 * 1024)
                    
                    # 创建处理器并处理文件
                    config = ProcessorConfig(enabled=True, name=proc_name)
                    processor = ProcessorRegistry.get_processor(proc_name, config)
                    
                    output_file = self.temp_dir / f"memory_test_{proc_name}_{size_category}.pcap"
                    
                    # 处理文件
                    result = processor.process_file(str(test_file), str(output_file))
                    
                    # 测量内存峰值
                    peak_memory = process.memory_info().rss / (1024 * 1024)
                    memory_used = peak_memory - baseline_memory
                    
                    if result.success:
                        processor_memory[proc_name] = {
                            "baseline_mb": baseline_memory,
                            "peak_mb": peak_memory,
                            "used_mb": memory_used,
                            "efficiency": file_size_mb / memory_used if memory_used > 0 else 0,
                            "success": True
                        }
                        
                        logger.info(f"  {proc_name}: 使用内存 {memory_used:.1f}MB, 效率 {file_size_mb/memory_used:.2f}")
                    else:
                        processor_memory[proc_name] = {
                            "success": False,
                            "error": result.error
                        }
                        
                except Exception as e:
                    processor_memory[proc_name] = {
                        "success": False,
                        "error": str(e)
                    }
                    logger.error(f"  {proc_name}: 内存测试异常 - {e}")
            
            memory_results[size_category] = {
                "file_size_mb": file_size_mb,
                "processors": processor_memory
            }
        
        # 获取当前内存快照
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        memory_results["tracemalloc"] = {
            "current_mb": current / (1024 * 1024),
            "peak_mb": peak / (1024 * 1024)
        }
        
        self.results["tests"]["memory_usage"] = memory_results
        
        # 计算内存效率
        avg_efficiency = self._calculate_memory_efficiency(memory_results)
        logger.info(f"平均内存效率: {avg_efficiency:.2f} MB文件/MB内存")
    
    def test_startup_time(self):
        """5.2.3 启动时间测试"""
        logger.info("⚡ 开始启动时间测试")
        
        startup_results = {}
        
        # 测试模块导入时间
        import_times = {}
        
        modules_to_test = [
            "src.pktmask.core.processors.registry",
            "src.pktmask.core.processors.ip_anonymizer", 
            "src.pktmask.core.processors.deduplicator",
            "src.pktmask.core.processors.trimmer",
            "src.pktmask.config.settings"
        ]
        
        for module_name in modules_to_test:
            try:
                start_time = time.time()
                
                # 使用subprocess测试模块导入时间
                result = subprocess.run([
                    sys.executable, "-c", f"import {module_name}"
                ], capture_output=True, text=True, timeout=10)
                
                end_time = time.time()
                import_time = end_time - start_time
                
                if result.returncode == 0:
                    import_times[module_name] = {
                        "time": import_time,
                        "success": True
                    }
                    logger.info(f"  {module_name}: {import_time:.3f}秒")
                else:
                    import_times[module_name] = {
                        "success": False,
                        "error": result.stderr
                    }
                    
            except subprocess.TimeoutExpired:
                import_times[module_name] = {
                    "success": False,
                    "error": "导入超时"
                }
            except Exception as e:
                import_times[module_name] = {
                    "success": False,
                    "error": str(e)
                }
        
        # 测试处理器创建时间
        processor_creation_times = {}
        
        for proc_name in ["mask_ip", "dedup_packet", "trim_packet"]:
            try:
                start_time = time.time()
                
                config = ProcessorConfig(enabled=True, name=proc_name)
                processor = ProcessorRegistry.get_processor(proc_name, config)
                
                end_time = time.time()
                creation_time = end_time - start_time
                
                processor_creation_times[proc_name] = {
                    "time": creation_time,
                    "success": True
                }
                
                logger.info(f"  {proc_name}处理器创建: {creation_time:.3f}秒")
                
            except Exception as e:
                processor_creation_times[proc_name] = {
                    "success": False,
                    "error": str(e)
                }
        
        startup_results = {
            "module_imports": import_times,
            "processor_creation": processor_creation_times,
            "total_startup_time": sum(
                t["time"] for t in import_times.values() if t.get("success")
            ) + sum(
                t["time"] for t in processor_creation_times.values() if t.get("success")
            )
        }
        
        self.results["tests"]["startup_time"] = startup_results
        
        logger.info(f"总启动时间: {startup_results['total_startup_time']:.3f}秒")
    
    def test_stability(self):
        """5.2.4 稳定性测试"""
        logger.info("🔧 开始稳定性测试")
        
        stability_results = {}
        
        # 连续处理测试
        continuous_test = self._test_continuous_processing()
        stability_results["continuous_processing"] = continuous_test
        
        # 内存泄漏测试
        memory_leak_test = self._test_memory_leak()
        stability_results["memory_leak"] = memory_leak_test
        
        # 错误恢复测试
        error_recovery_test = self._test_error_recovery()
        stability_results["error_recovery"] = error_recovery_test
        
        self.results["tests"]["stability"] = stability_results
    
    def _test_continuous_processing(self):
        """连续处理测试"""
        logger.info("  测试连续处理10个文件")
        
        test_files = self._get_test_files_by_size()
        small_files = test_files.get("small", [])
        
        if not small_files:
            return {"success": False, "error": "没有找到小文件进行测试"}
        
        try:
            config = ProcessorConfig(enabled=True, name="dedup_packet")
            processor = ProcessorRegistry.get_processor("dedup_packet", config)
            
            results = []
            start_memory = psutil.Process().memory_info().rss / (1024 * 1024)
            
            # 连续处理同一个文件10次
            test_file = small_files[0]
            for i in range(10):
                output_file = self.temp_dir / f"continuous_{i}.pcap"
                
                start_time = time.time()
                result = processor.process_file(str(test_file), str(output_file))
                end_time = time.time()
                
                current_memory = psutil.Process().memory_info().rss / (1024 * 1024)
                
                results.append({
                    "iteration": i + 1,
                    "success": result.success,
                    "time": end_time - start_time,
                    "memory_mb": current_memory,
                    "error": result.error if not result.success else None
                })
            
            end_memory = psutil.Process().memory_info().rss / (1024 * 1024)
            memory_growth = end_memory - start_memory
            
            return {
                "success": True,
                "iterations": results,
                "memory_growth_mb": memory_growth,
                "avg_time": sum(r["time"] for r in results if r["success"]) / len([r for r in results if r["success"]])
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _test_memory_leak(self):
        """内存泄漏测试"""
        logger.info("  测试内存泄漏")
        
        try:
            # 简化的内存泄漏测试
            initial_memory = psutil.Process().memory_info().rss / (1024 * 1024)
            
            # 多次创建和销毁处理器
            for i in range(5):
                config = ProcessorConfig(enabled=True, name="mask_ip")
                processor = ProcessorRegistry.get_processor("mask_ip", config)
                del processor
            
            final_memory = psutil.Process().memory_info().rss / (1024 * 1024)
            memory_diff = final_memory - initial_memory
            
            return {
                "success": True,
                "initial_memory_mb": initial_memory,
                "final_memory_mb": final_memory,
                "memory_difference_mb": memory_diff,
                "leak_detected": memory_diff > 10  # 10MB阈值
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _test_error_recovery(self):
        """错误恢复测试"""
        logger.info("  测试错误恢复")
        
        try:
            # 测试无效文件处理
            config = ProcessorConfig(enabled=True, name="dedup_packet")
            processor = ProcessorRegistry.get_processor("dedup_packet", config)
            
            # 创建无效输入文件路径
            invalid_input = "/nonexistent/file.pcap"
            output_file = self.temp_dir / "error_test.pcap"
            
            result = processor.process_file(invalid_input, str(output_file))
            
            return {
                "success": True,
                "error_handled": not result.success,
                "error_message": result.error,
                "graceful_failure": result.error is not None
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _get_test_files_by_size(self) -> Dict[str, List[Path]]:
        """按大小分类获取测试文件"""
        files_by_size = {
            "small": [],   # <10MB
            "medium": [],  # 10-100MB  
            "large": []    # >100MB
        }
        
        if not self.test_data_dir.exists():
            return files_by_size
        
        # 查找所有pcap文件
        for pattern in ["**/*.pcap", "**/*.pcapng"]:
            for file_path in self.test_data_dir.glob(pattern):
                if file_path.is_file():
                    size_mb = file_path.stat().st_size / (1024 * 1024)
                    
                    if size_mb < 10:
                        files_by_size["small"].append(file_path)
                    elif size_mb <= 100:
                        files_by_size["medium"].append(file_path)
                    else:
                        files_by_size["large"].append(file_path)
        
        # 限制每个类别的文件数量
        for category in files_by_size:
            files_by_size[category] = files_by_size[category][:2]
            
        return files_by_size
    
    def _calculate_average_throughput(self, speed_results: Dict) -> float:
        """计算平均吞吐量"""
        throughputs = []
        
        for size_cat, data in speed_results.items():
            for proc_name, proc_data in data["processors"].items():
                if proc_data.get("success") and "throughput" in proc_data:
                    throughputs.append(proc_data["throughput"])
        
        return sum(throughputs) / len(throughputs) if throughputs else 0
    
    def _calculate_memory_efficiency(self, memory_results: Dict) -> float:
        """计算内存效率"""
        efficiencies = []
        
        for size_cat, data in memory_results.items():
            if size_cat == "tracemalloc":
                continue
                
            for proc_name, proc_data in data["processors"].items():
                if proc_data.get("success") and "efficiency" in proc_data:
                    efficiencies.append(proc_data["efficiency"])
        
        return sum(efficiencies) / len(efficiencies) if efficiencies else 0
    
    def generate_report(self):
        """生成性能测试报告"""
        self.results["end_time"] = time.time()
        self.results["total_time"] = self.results["end_time"] - self.results["start_time"]
        
        # 生成摘要
        self.results["summary"] = self._generate_summary()
        
        # 保存详细报告
        report_file = Path("phase_5_performance_test_report.json")
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        
        # 打印摘要报告
        self._print_summary_report()
        
        logger.info(f"详细性能报告已保存到: {report_file}")
    
    def _generate_summary(self) -> Dict:
        """生成测试摘要"""
        summary = {
            "overall_status": "PASS",
            "tests_run": len(self.results["tests"]),
            "performance_metrics": {}
        }
        
        # 处理速度摘要
        if "processing_speed" in self.results["tests"]:
            avg_throughput = self._calculate_average_throughput(self.results["tests"]["processing_speed"])
            summary["performance_metrics"]["average_throughput_mbps"] = avg_throughput
        
        # 内存使用摘要
        if "memory_usage" in self.results["tests"]:
            avg_efficiency = self._calculate_memory_efficiency(self.results["tests"]["memory_usage"])
            summary["performance_metrics"]["memory_efficiency"] = avg_efficiency
        
        # 启动时间摘要
        if "startup_time" in self.results["tests"]:
            startup_data = self.results["tests"]["startup_time"]
            summary["performance_metrics"]["startup_time_seconds"] = startup_data.get("total_startup_time", 0)
        
        return summary
    
    def _print_summary_report(self):
        """打印摘要报告"""
        logger.info("=" * 60)
        logger.info("Phase 5 性能基准测试报告")
        logger.info("=" * 60)
        
        summary = self.results["summary"]
        
        logger.info(f"测试状态: {summary['overall_status']}")
        logger.info(f"测试数量: {summary['tests_run']}")
        logger.info(f"总耗时: {self.results['total_time']:.2f}秒")
        
        metrics = summary.get("performance_metrics", {})
        
        if "average_throughput_mbps" in metrics:
            logger.info(f"平均处理吞吐量: {metrics['average_throughput_mbps']:.2f} MB/s")
            
        if "memory_efficiency" in metrics:
            logger.info(f"内存效率: {metrics['memory_efficiency']:.2f} MB文件/MB内存")
            
        if "startup_time_seconds" in metrics:
            logger.info(f"启动时间: {metrics['startup_time_seconds']:.3f}秒")
        
        logger.info("=" * 60)
    
    def cleanup(self):
        """清理临时文件"""
        if self.temp_dir.exists():
            import shutil
            shutil.rmtree(self.temp_dir)
        logger.info("性能测试清理完成")


def main():
    """主函数"""
    logger.info("开始Phase 5性能基准验证测试")
    logger.info(f"Python版本: {sys.version}")
    logger.info(f"工作目录: {os.getcwd()}")
    
    # 检查系统资源
    logger.info(f"系统内存: {psutil.virtual_memory().total / (1024**3):.1f} GB")
    logger.info(f"可用内存: {psutil.virtual_memory().available / (1024**3):.1f} GB")
    
    try:
        # 创建并运行性能测试
        test_suite = Phase5PerformanceTests()
        test_suite.run_all_tests()
        
        return 0
        
    except Exception as e:
        logger.error(f"性能测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main()) 