"""
性能跟踪器

用于跟踪和分析双策略的性能数据，支持实时监控、统计分析和报告生成。

作者: PktMask Team
创建时间: 2025-06-16
版本: 1.0.0
"""

import time
import json
import logging
from dataclasses import dataclass, asdict
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from collections import defaultdict
import statistics
from enum import Enum


class MetricType(Enum):
    """指标类型"""
    PROCESSING_TIME = "processing_time"
    MEMORY_USAGE = "memory_usage"
    ACCURACY = "accuracy"
    ERROR_RATE = "error_rate"
    THROUGHPUT = "throughput"


@dataclass
class PerformanceMetric:
    """性能指标数据"""
    timestamp: float
    strategy_name: str
    metric_type: MetricType
    value: float
    unit: str
    metadata: Dict[str, Any]


@dataclass
class ComparisonResult:
    """对比结果数据"""
    timestamp: float
    file_path: str
    payload_size: int
    
    # Legacy策略结果
    legacy_processing_time: float
    legacy_memory_usage: float
    legacy_success: bool
    legacy_preserved_bytes: int
    legacy_error: Optional[str]
    
    # Scanning策略结果
    scanning_processing_time: float
    scanning_memory_usage: float
    scanning_success: bool
    scanning_preserved_bytes: int
    scanning_error: Optional[str]
    
    # 对比分析
    speed_improvement: float
    memory_efficiency: float
    results_match: bool
    accuracy_delta: float


@dataclass
class PerformanceSummary:
    """性能摘要统计"""
    total_comparisons: int
    success_rate_legacy: float
    success_rate_scanning: float
    
    # 性能对比统计
    avg_speed_improvement: float
    median_speed_improvement: float
    std_speed_improvement: float
    
    avg_memory_efficiency: float
    median_memory_efficiency: float
    
    # 准确性统计
    results_match_rate: float
    avg_accuracy_delta: float
    
    # 处理时间统计
    avg_legacy_time: float
    avg_scanning_time: float
    
    # 内存使用统计
    avg_legacy_memory: float
    avg_scanning_memory: float


class PerformanceTracker:
    """
    性能跟踪器
    
    负责收集、存储和分析双策略的性能数据。
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化性能跟踪器
        
        Args:
            config: 配置参数
        """
        self.config = config or {}
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        
        # 数据存储
        self.metrics: List[PerformanceMetric] = []
        self.comparisons: List[ComparisonResult] = []
        
        # 统计缓存
        self._summary_cache: Optional[PerformanceSummary] = None
        self._cache_timestamp: float = 0
        self._cache_ttl: float = self.config.get('cache_ttl', 300)  # 5分钟缓存
        
        # 文件输出配置
        self.output_dir = Path(self.config.get('output_dir', 'reports'))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger.info("PerformanceTracker初始化完成")
    
    def record_metric(self, strategy_name: str, metric_type: MetricType, 
                     value: float, unit: str = "", metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        记录性能指标
        
        Args:
            strategy_name: 策略名称
            metric_type: 指标类型
            value: 指标值
            unit: 单位
            metadata: 额外元数据
        """
        metric = PerformanceMetric(
            timestamp=time.time(),
            strategy_name=strategy_name,
            metric_type=metric_type,
            value=value,
            unit=unit,
            metadata=metadata or {}
        )
        
        self.metrics.append(metric)
        self._invalidate_cache()
        
        self.logger.debug(f"记录性能指标: {strategy_name} {metric_type.value} = {value} {unit}")
    
    def record_comparison(self, comparison_data: Dict[str, Any]) -> None:
        """
        记录策略对比数据
        
        Args:
            comparison_data: 对比数据字典
        """
        try:
            # 提取对比元数据
            metadata = comparison_data.get('comparison_metadata', {})
            legacy_result = comparison_data.get('legacy_result', {})
            scanning_result = comparison_data.get('scanning_result', {})
            performance_comparison = comparison_data.get('performance_comparison', {})
            
            # 创建对比结果
            comparison = ComparisonResult(
                timestamp=metadata.get('timestamp', time.time()),
                file_path=metadata.get('file_path', 'unknown'),
                payload_size=metadata.get('payload_size', 0),
                
                # Legacy策略数据
                legacy_processing_time=legacy_result.get('duration_ms', 0.0),
                legacy_memory_usage=legacy_result.get('memory_usage_mb', 0.0),
                legacy_success=legacy_result.get('success', False),
                legacy_preserved_bytes=self._extract_preserved_bytes(legacy_result.get('analysis', {})),
                legacy_error=legacy_result.get('error'),
                
                # Scanning策略数据
                scanning_processing_time=scanning_result.get('duration_ms', 0.0),
                scanning_memory_usage=scanning_result.get('memory_usage_mb', 0.0),
                scanning_success=scanning_result.get('success', False),
                scanning_preserved_bytes=self._extract_preserved_bytes(scanning_result.get('analysis', {})),
                scanning_error=scanning_result.get('error'),
                
                # 对比分析
                speed_improvement=performance_comparison.get('speed_improvement', 0.0),
                memory_efficiency=self._calculate_memory_efficiency(
                    legacy_result.get('memory_usage_mb', 0.0),
                    scanning_result.get('memory_usage_mb', 0.0)
                ),
                results_match=performance_comparison.get('results_match', False),
                accuracy_delta=self._calculate_accuracy_delta(legacy_result, scanning_result)
            )
            
            self.comparisons.append(comparison)
            self._invalidate_cache()
            
            self.logger.debug(f"记录策略对比: {comparison.file_path}, "
                            f"速度提升: {comparison.speed_improvement:.2%}, "
                            f"结果匹配: {comparison.results_match}")
            
        except Exception as e:
            self.logger.error(f"记录对比数据失败: {e}", exc_info=True)
    
    def get_performance_summary(self, force_refresh: bool = False) -> PerformanceSummary:
        """
        获取性能摘要统计
        
        Args:
            force_refresh: 是否强制刷新缓存
            
        Returns:
            性能摘要数据
        """
        current_time = time.time()
        
        # 检查缓存有效性
        if (not force_refresh and 
            self._summary_cache is not None and 
            current_time - self._cache_timestamp < self._cache_ttl):
            return self._summary_cache
        
        # 计算摘要统计
        if not self.comparisons:
            return PerformanceSummary(
                total_comparisons=0,
                success_rate_legacy=0.0,
                success_rate_scanning=0.0,
                avg_speed_improvement=0.0,
                median_speed_improvement=0.0,
                std_speed_improvement=0.0,
                avg_memory_efficiency=0.0,
                median_memory_efficiency=0.0,
                results_match_rate=0.0,
                avg_accuracy_delta=0.0,
                avg_legacy_time=0.0,
                avg_scanning_time=0.0,
                avg_legacy_memory=0.0,
                avg_scanning_memory=0.0
            )
        
        total_comparisons = len(self.comparisons)
        
        # 成功率统计
        legacy_success_count = sum(1 for c in self.comparisons if c.legacy_success)
        scanning_success_count = sum(1 for c in self.comparisons if c.scanning_success)
        
        success_rate_legacy = legacy_success_count / total_comparisons
        success_rate_scanning = scanning_success_count / total_comparisons
        
        # 性能改进统计
        speed_improvements = [c.speed_improvement for c in self.comparisons]
        avg_speed_improvement = statistics.mean(speed_improvements)
        median_speed_improvement = statistics.median(speed_improvements)
        std_speed_improvement = statistics.stdev(speed_improvements) if len(speed_improvements) > 1 else 0.0
        
        # 内存效率统计
        memory_efficiencies = [c.memory_efficiency for c in self.comparisons]
        avg_memory_efficiency = statistics.mean(memory_efficiencies)
        median_memory_efficiency = statistics.median(memory_efficiencies)
        
        # 准确性统计
        results_match_count = sum(1 for c in self.comparisons if c.results_match)
        results_match_rate = results_match_count / total_comparisons
        
        accuracy_deltas = [c.accuracy_delta for c in self.comparisons]
        avg_accuracy_delta = statistics.mean(accuracy_deltas)
        
        # 时间统计
        legacy_times = [c.legacy_processing_time for c in self.comparisons]
        scanning_times = [c.scanning_processing_time for c in self.comparisons]
        avg_legacy_time = statistics.mean(legacy_times)
        avg_scanning_time = statistics.mean(scanning_times)
        
        # 内存统计
        legacy_memories = [c.legacy_memory_usage for c in self.comparisons]
        scanning_memories = [c.scanning_memory_usage for c in self.comparisons]
        avg_legacy_memory = statistics.mean(legacy_memories)
        avg_scanning_memory = statistics.mean(scanning_memories)
        
        # 创建摘要
        summary = PerformanceSummary(
            total_comparisons=total_comparisons,
            success_rate_legacy=success_rate_legacy,
            success_rate_scanning=success_rate_scanning,
            avg_speed_improvement=avg_speed_improvement,
            median_speed_improvement=median_speed_improvement,
            std_speed_improvement=std_speed_improvement,
            avg_memory_efficiency=avg_memory_efficiency,
            median_memory_efficiency=median_memory_efficiency,
            results_match_rate=results_match_rate,
            avg_accuracy_delta=avg_accuracy_delta,
            avg_legacy_time=avg_legacy_time,
            avg_scanning_time=avg_scanning_time,
            avg_legacy_memory=avg_legacy_memory,
            avg_scanning_memory=avg_scanning_memory
        )
        
        # 更新缓存
        self._summary_cache = summary
        self._cache_timestamp = current_time
        
        self.logger.info(f"生成性能摘要: {total_comparisons}次对比, "
                        f"速度提升: {avg_speed_improvement:.2%}, "
                        f"结果匹配率: {results_match_rate:.2%}")
        
        return summary
    
    def export_performance_report(self, filepath: Optional[Path] = None) -> Path:
        """
        导出性能报告
        
        Args:
            filepath: 输出文件路径
            
        Returns:
            实际输出文件路径
        """
        if filepath is None:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filepath = self.output_dir / f"performance_report_{timestamp}.json"
        
        # 获取摘要统计
        summary = self.get_performance_summary()
        
        # 构建报告数据
        report = {
            'metadata': {
                'generated_at': time.time(),
                'generated_at_human': time.strftime("%Y-%m-%d %H:%M:%S"),
                'tracker_version': '1.0.0',
                'total_metrics': len(self.metrics),
                'total_comparisons': len(self.comparisons)
            },
            'summary': asdict(summary),
            'detailed_comparisons': [asdict(c) for c in self.comparisons[-100:]],  # 最近100次对比
            'metrics_by_strategy': self._group_metrics_by_strategy(),
            'performance_trends': self._calculate_performance_trends()
        }
        
        # 写入文件
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"性能报告已导出: {filepath}")
        return filepath
    
    def clear_data(self) -> None:
        """清空所有数据"""
        self.metrics.clear()
        self.comparisons.clear()
        self._invalidate_cache()
        self.logger.info("性能跟踪数据已清空")
    
    def get_strategy_metrics(self, strategy_name: str, metric_type: Optional[MetricType] = None) -> List[PerformanceMetric]:
        """
        获取特定策略的指标数据
        
        Args:
            strategy_name: 策略名称
            metric_type: 指标类型（可选）
            
        Returns:
            指标数据列表
        """
        metrics = [m for m in self.metrics if m.strategy_name == strategy_name]
        
        if metric_type:
            metrics = [m for m in metrics if m.metric_type == metric_type]
        
        return metrics
    
    def _extract_preserved_bytes(self, analysis: Dict[str, Any]) -> int:
        """从分析结果中提取保留字节数"""
        return analysis.get('preserved_bytes', analysis.get('header_boundary', 0))
    
    def _calculate_memory_efficiency(self, legacy_memory: float, scanning_memory: float) -> float:
        """计算内存效率改进比例"""
        if legacy_memory <= 0:
            return 0.0
        return (legacy_memory - scanning_memory) / legacy_memory
    
    def _calculate_accuracy_delta(self, legacy_result: Dict[str, Any], scanning_result: Dict[str, Any]) -> float:
        """计算准确性差异"""
        legacy_analysis = legacy_result.get('analysis', {})
        scanning_analysis = scanning_result.get('analysis', {})
        
        legacy_boundary = legacy_analysis.get('header_boundary', 0)
        scanning_boundary = scanning_analysis.get('header_boundary', 0)
        
        if legacy_boundary == 0 and scanning_boundary == 0:
            return 0.0
        
        max_boundary = max(legacy_boundary, scanning_boundary)
        if max_boundary == 0:
            return 0.0
        
        return abs(legacy_boundary - scanning_boundary) / max_boundary
    
    def _invalidate_cache(self) -> None:
        """使缓存失效"""
        self._summary_cache = None
        self._cache_timestamp = 0
    
    def _group_metrics_by_strategy(self) -> Dict[str, Dict[str, List[float]]]:
        """按策略分组指标"""
        grouped = defaultdict(lambda: defaultdict(list))
        
        for metric in self.metrics:
            grouped[metric.strategy_name][metric.metric_type.value].append(metric.value)
        
        return dict(grouped)
    
    def _calculate_performance_trends(self) -> Dict[str, Any]:
        """计算性能趋势"""
        if len(self.comparisons) < 2:
            return {}
        
        # 按时间排序
        sorted_comparisons = sorted(self.comparisons, key=lambda c: c.timestamp)
        
        # 计算趋势（简单线性趋势）
        n = len(sorted_comparisons)
        mid_point = n // 2
        
        first_half = sorted_comparisons[:mid_point]
        second_half = sorted_comparisons[mid_point:]
        
        first_half_speed = statistics.mean([c.speed_improvement for c in first_half])
        second_half_speed = statistics.mean([c.speed_improvement for c in second_half])
        
        first_half_memory = statistics.mean([c.memory_efficiency for c in first_half])
        second_half_memory = statistics.mean([c.memory_efficiency for c in second_half])
        
        first_half_match = sum(1 for c in first_half if c.results_match) / len(first_half)
        second_half_match = sum(1 for c in second_half if c.results_match) / len(second_half)
        
        return {
            'speed_improvement_trend': second_half_speed - first_half_speed,
            'memory_efficiency_trend': second_half_memory - first_half_memory,
            'results_match_trend': second_half_match - first_half_match,
            'sample_size': n,
            'trend_confidence': 'low' if n < 20 else 'medium' if n < 50 else 'high'
        } 