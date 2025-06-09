#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
性能测试运行器
自动化运行基准测试并生成报告
"""

import os
import sys
import time
import json
from typing import Dict, List, Any, Optional
from pathlib import Path

# 添加src路径到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from pktmask.infrastructure.logging import get_logger
from pktmask.utils.time import current_timestamp
from benchmark_suite import AlgorithmBenchmark, BenchmarkResult
from performance_monitor import PerformanceMonitor


class PerformanceTestRunner:
    """性能测试运行器"""
    
    def __init__(self, output_dir: str = "performance_results"):
        """
        初始化测试运行器
        
        Args:
            output_dir: 结果输出目录
        """
        self._logger = get_logger('performance_test_runner')
        self.output_dir = output_dir
        self.test_session_id = current_timestamp()
        
        # 确保输出目录存在
        os.makedirs(self.output_dir, exist_ok=True)
        
        self._logger.info(f"性能测试运行器初始化完成，输出目录: {self.output_dir}")
        self._logger.info(f"测试会话ID: {self.test_session_id}")
    
    def run_baseline_establishment(self) -> Dict[str, Any]:
        """
        运行基线建立测试
        
        Returns:
            Dict[str, Any]: 基线测试结果
        """
        self._logger.info("开始建立性能基线")
        
        # 创建基准测试套件
        benchmark = AlgorithmBenchmark()
        
        # 启动性能监控
        with PerformanceMonitor(sampling_interval=0.5) as monitor:
            start_time = time.time()
            
            # 运行完整基准测试套件
            results = benchmark.run_full_benchmark_suite()
            
            end_time = time.time()
            
            # 获取性能监控数据
            monitoring_summary = monitor.get_performance_summary(start_time, end_time)
        
        # 生成基线报告
        baseline_report = self._generate_baseline_report(results, monitoring_summary)
        
        # 保存结果
        self._save_baseline_results(baseline_report, results, monitoring_summary)
        
        self._logger.info("性能基线建立完成")
        return baseline_report
    
    def _generate_baseline_report(self, benchmark_results: Dict[str, List[BenchmarkResult]], 
                                monitoring_summary: Dict[str, Any]) -> Dict[str, Any]:
        """生成基线报告"""
        report = {
            'session_id': self.test_session_id,
            'timestamp': time.time(),
            'baseline_metrics': {},
            'system_info': monitoring_summary,
            'test_summary': {
                'total_algorithms': len(benchmark_results),
                'total_tests': sum(len(results) for results in benchmark_results.values()),
                'successful_tests': 0,
                'failed_tests': 0
            }
        }
        
        # 为每个算法生成基线指标
        for algorithm_name, results in benchmark_results.items():
            successful_results = [r for r in results if r.success]
            failed_results = [r for r in results if not r.success]
            
            report['test_summary']['successful_tests'] += len(successful_results)
            report['test_summary']['failed_tests'] += len(failed_results)
            
            if successful_results:
                # 计算基线指标
                baseline_metrics = {
                    'throughput_mbps': {
                        'min': min(r.throughput_mbps for r in successful_results),
                        'max': max(r.throughput_mbps for r in successful_results),
                        'avg': sum(r.throughput_mbps for r in successful_results) / len(successful_results),
                        'median': self._calculate_median([r.throughput_mbps for r in successful_results])
                    },
                    'packets_per_second': {
                        'min': min(r.packets_per_second for r in successful_results),
                        'max': max(r.packets_per_second for r in successful_results),
                        'avg': sum(r.packets_per_second for r in successful_results) / len(successful_results),
                        'median': self._calculate_median([r.packets_per_second for r in successful_results])
                    },
                    'memory_usage_mb': {
                        'min': min(r.memory_usage_mb for r in successful_results),
                        'max': max(r.memory_usage_mb for r in successful_results),
                        'avg': sum(r.memory_usage_mb for r in successful_results) / len(successful_results),
                        'median': self._calculate_median([r.memory_usage_mb for r in successful_results])
                    },
                    'processing_time_seconds': {
                        'min': min(r.processing_time_seconds for r in successful_results),
                        'max': max(r.processing_time_seconds for r in successful_results),
                        'avg': sum(r.processing_time_seconds for r in successful_results) / len(successful_results),
                        'median': self._calculate_median([r.processing_time_seconds for r in successful_results])
                    },
                    'test_count': len(successful_results),
                    'success_rate': len(successful_results) / len(results) if results else 0
                }
                
                report['baseline_metrics'][algorithm_name] = baseline_metrics
                
                self._logger.info(f"{algorithm_name} 基线指标:")
                self._logger.info(f"  平均吞吐量: {baseline_metrics['throughput_mbps']['avg']:.2f} MB/s")
                self._logger.info(f"  平均处理速度: {baseline_metrics['packets_per_second']['avg']:.0f} packets/s")
                self._logger.info(f"  平均内存使用: {baseline_metrics['memory_usage_mb']['avg']:.1f} MB")
                self._logger.info(f"  成功率: {baseline_metrics['success_rate']:.1%}")
        
        return report
    
    def _calculate_median(self, values: List[float]) -> float:
        """计算中位数"""
        if not values:
            return 0.0
        
        sorted_values = sorted(values)
        n = len(sorted_values)
        
        if n % 2 == 0:
            return (sorted_values[n//2 - 1] + sorted_values[n//2]) / 2
        else:
            return sorted_values[n//2]
    
    def _save_baseline_results(self, baseline_report: Dict[str, Any], 
                             benchmark_results: Dict[str, List[BenchmarkResult]],
                             monitoring_summary: Dict[str, Any]):
        """保存基线结果到文件"""
        
        # 保存基线报告
        baseline_file = os.path.join(self.output_dir, f"baseline_report_{self.test_session_id}.json")
        with open(baseline_file, 'w', encoding='utf-8') as f:
            json.dump(baseline_report, f, indent=2, ensure_ascii=False)
        
        # 保存详细基准测试结果
        detailed_results = {}
        for algorithm_name, results in benchmark_results.items():
            detailed_results[algorithm_name] = [
                {
                    'algorithm_name': r.algorithm_name,
                    'file_size_mb': r.file_size_mb,
                    'processing_time_seconds': r.processing_time_seconds,
                    'memory_usage_mb': r.memory_usage_mb,
                    'packets_processed': r.packets_processed,
                    'files_processed': r.files_processed,
                    'throughput_mbps': r.throughput_mbps,
                    'packets_per_second': r.packets_per_second,
                    'success': r.success,
                    'error_message': r.error_message
                }
                for r in results
            ]
        
        detailed_file = os.path.join(self.output_dir, f"detailed_results_{self.test_session_id}.json")
        with open(detailed_file, 'w', encoding='utf-8') as f:
            json.dump(detailed_results, f, indent=2, ensure_ascii=False)
        
        # 保存监控数据
        monitoring_file = os.path.join(self.output_dir, f"monitoring_summary_{self.test_session_id}.json")
        with open(monitoring_file, 'w', encoding='utf-8') as f:
            json.dump(monitoring_summary, f, indent=2, ensure_ascii=False)
        
        self._logger.info(f"基线结果已保存到: {baseline_file}")
        self._logger.info(f"详细结果已保存到: {detailed_file}")
        self._logger.info(f"监控数据已保存到: {monitoring_file}")
    
    def compare_with_baseline(self, baseline_file: str, 
                            current_results: Dict[str, List[BenchmarkResult]]) -> Dict[str, Any]:
        """
        与基线进行比较
        
        Args:
            baseline_file: 基线文件路径
            current_results: 当前测试结果
            
        Returns:
            Dict[str, Any]: 比较结果
        """
        self._logger.info(f"开始与基线比较: {baseline_file}")
        
        # 加载基线数据
        try:
            with open(baseline_file, 'r', encoding='utf-8') as f:
                baseline_data = json.load(f)
        except Exception as e:
            self._logger.error(f"加载基线文件失败: {e}")
            return {'error': f'加载基线文件失败: {e}'}
        
        comparison_report = {
            'baseline_session': baseline_data.get('session_id'),
            'current_session': self.test_session_id,
            'comparison_timestamp': time.time(),
            'algorithm_comparisons': {},
            'overall_summary': {
                'improved_algorithms': 0,
                'degraded_algorithms': 0,
                'stable_algorithms': 0
            }
        }
        
        baseline_metrics = baseline_data.get('baseline_metrics', {})
        
        for algorithm_name, current_results_list in current_results.items():
            if algorithm_name not in baseline_metrics:
                self._logger.warning(f"算法 {algorithm_name} 在基线中不存在，跳过比较")
                continue
            
            baseline_algo_metrics = baseline_metrics[algorithm_name]
            successful_current = [r for r in current_results_list if r.success]
            
            if not successful_current:
                self._logger.warning(f"算法 {algorithm_name} 当前测试全部失败，跳过比较")
                continue
            
            # 计算当前指标
            current_metrics = {
                'throughput_mbps': sum(r.throughput_mbps for r in successful_current) / len(successful_current),
                'packets_per_second': sum(r.packets_per_second for r in successful_current) / len(successful_current),
                'memory_usage_mb': sum(r.memory_usage_mb for r in successful_current) / len(successful_current),
                'processing_time_seconds': sum(r.processing_time_seconds for r in successful_current) / len(successful_current)
            }
            
            # 计算改进百分比
            improvements = {}
            for metric_name in current_metrics:
                baseline_value = baseline_algo_metrics[metric_name]['avg']
                current_value = current_metrics[metric_name]
                
                if baseline_value > 0:
                    if metric_name in ['throughput_mbps', 'packets_per_second']:
                        # 这些指标越高越好
                        improvement = ((current_value - baseline_value) / baseline_value) * 100
                    else:
                        # 内存使用和处理时间越低越好
                        improvement = ((baseline_value - current_value) / baseline_value) * 100
                else:
                    improvement = 0
                
                improvements[metric_name] = improvement
            
            # 评估总体改进情况
            avg_improvement = sum(improvements.values()) / len(improvements)
            
            if avg_improvement > 5:  # 改进超过5%
                status = 'improved'
                comparison_report['overall_summary']['improved_algorithms'] += 1
            elif avg_improvement < -5:  # 退化超过5%
                status = 'degraded'
                comparison_report['overall_summary']['degraded_algorithms'] += 1
            else:
                status = 'stable'
                comparison_report['overall_summary']['stable_algorithms'] += 1
            
            comparison_report['algorithm_comparisons'][algorithm_name] = {
                'status': status,
                'average_improvement_percent': avg_improvement,
                'metric_improvements': improvements,
                'baseline_metrics': baseline_algo_metrics,
                'current_metrics': current_metrics,
                'test_count': len(successful_current)
            }
            
            self._logger.info(f"{algorithm_name} 比较结果: {status} (平均改进: {avg_improvement:.1f}%)")
        
        # 保存比较报告
        comparison_file = os.path.join(self.output_dir, f"comparison_report_{self.test_session_id}.json")
        with open(comparison_file, 'w', encoding='utf-8') as f:
            json.dump(comparison_report, f, indent=2, ensure_ascii=False)
        
        self._logger.info(f"比较报告已保存到: {comparison_file}")
        self._logger.info(f"总体结果: 改进={comparison_report['overall_summary']['improved_algorithms']}, "
                         f"退化={comparison_report['overall_summary']['degraded_algorithms']}, "
                         f"稳定={comparison_report['overall_summary']['stable_algorithms']}")
        
        return comparison_report
    
    def generate_html_report(self, baseline_report: Dict[str, Any], 
                           comparison_report: Optional[Dict[str, Any]] = None) -> str:
        """
        生成HTML性能报告
        
        Args:
            baseline_report: 基线报告
            comparison_report: 比较报告（可选）
            
        Returns:
            str: HTML报告文件路径
        """
        html_content = self._create_html_template()
        
        # 替换基线数据
        baseline_section = self._generate_baseline_html_section(baseline_report)
        html_content = html_content.replace('{{BASELINE_SECTION}}', baseline_section)
        
        # 替换比较数据
        if comparison_report:
            comparison_section = self._generate_comparison_html_section(comparison_report)
            html_content = html_content.replace('{{COMPARISON_SECTION}}', comparison_section)
        else:
            html_content = html_content.replace('{{COMPARISON_SECTION}}', 
                                              '<p>暂无比较数据</p>')
        
        # 保存HTML文件
        html_file = os.path.join(self.output_dir, f"performance_report_{self.test_session_id}.html")
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        self._logger.info(f"HTML报告已生成: {html_file}")
        return html_file
    
    def _create_html_template(self) -> str:
        """创建HTML模板"""
        return """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PktMask 性能测试报告</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 20px; background-color: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1, h2, h3 { color: #333; }
        .metric-card { background: #f8f9fa; padding: 15px; margin: 10px 0; border-radius: 5px; border-left: 4px solid #007bff; }
        .metric-value { font-size: 1.2em; font-weight: bold; color: #007bff; }
        .improvement { color: #28a745; }
        .degradation { color: #dc3545; }
        .stable { color: #6c757d; }
        table { width: 100%; border-collapse: collapse; margin: 15px 0; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background-color: #f8f9fa; font-weight: 600; }
        .status-improved { background-color: #d4edda; }
        .status-degraded { background-color: #f8d7da; }
        .status-stable { background-color: #e2e3e5; }
    </style>
</head>
<body>
    <div class="container">
        <h1>PktMask 算法性能测试报告</h1>
        <p>生成时间: <span id="generation-time"></span></p>
        
        <h2>基线性能指标</h2>
        {{BASELINE_SECTION}}
        
        <h2>性能比较分析</h2>
        {{COMPARISON_SECTION}}
    </div>
    
    <script>
        document.getElementById('generation-time').textContent = new Date().toLocaleString('zh-CN');
    </script>
</body>
</html>
        """
    
    def _generate_baseline_html_section(self, baseline_report: Dict[str, Any]) -> str:
        """生成基线HTML部分"""
        html = ""
        
        for algorithm_name, metrics in baseline_report.get('baseline_metrics', {}).items():
            html += f"""
            <div class="metric-card">
                <h3>{algorithm_name}</h3>
                <p>平均吞吐量: <span class="metric-value">{metrics['throughput_mbps']['avg']:.2f} MB/s</span></p>
                <p>平均处理速度: <span class="metric-value">{metrics['packets_per_second']['avg']:.0f} packets/s</span></p>
                <p>平均内存使用: <span class="metric-value">{metrics['memory_usage_mb']['avg']:.1f} MB</span></p>
                <p>成功率: <span class="metric-value">{metrics['success_rate']:.1%}</span></p>
            </div>
            """
        
        return html
    
    def _generate_comparison_html_section(self, comparison_report: Dict[str, Any]) -> str:
        """生成比较HTML部分"""
        html = "<table>"
        html += "<tr><th>算法</th><th>状态</th><th>平均改进</th><th>吞吐量改进</th><th>内存优化</th></tr>"
        
        for algorithm_name, comp_data in comparison_report.get('algorithm_comparisons', {}).items():
            status = comp_data['status']
            avg_improvement = comp_data['average_improvement_percent']
            throughput_improvement = comp_data['metric_improvements'].get('throughput_mbps', 0)
            memory_improvement = comp_data['metric_improvements'].get('memory_usage_mb', 0)
            
            status_class = f"status-{status}"
            
            html += f"""
            <tr class="{status_class}">
                <td>{algorithm_name}</td>
                <td class="{status}">{status}</td>
                <td>{avg_improvement:+.1f}%</td>
                <td>{throughput_improvement:+.1f}%</td>
                <td>{memory_improvement:+.1f}%</td>
            </tr>
            """
        
        html += "</table>"
        return html 