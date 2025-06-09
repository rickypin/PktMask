#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
算法性能监控接口
提供统一的性能跟踪和度量功能
"""

import time
import threading
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
from contextlib import contextmanager

from ...infrastructure.logging import get_logger


class PerformanceMetrics(BaseModel):
    """性能指标数据模型"""
    
    # 基础指标
    processing_time_ms: float = Field(default=0.0, ge=0.0, description="处理时间(毫秒)")
    items_processed: int = Field(default=0, ge=0, description="处理项目数量")
    throughput_per_second: float = Field(default=0.0, ge=0.0, description="吞吐量(项/秒)")
    
    # 内存指标  
    memory_usage_mb: float = Field(default=0.0, ge=0.0, description="内存使用(MB)")
    peak_memory_mb: float = Field(default=0.0, ge=0.0, description="峰值内存(MB)")
    memory_efficiency: float = Field(default=0.0, ge=0.0, le=100.0, description="内存效率(%)")
    
    # 缓存指标
    cache_hits: int = Field(default=0, ge=0, description="缓存命中次数")
    cache_misses: int = Field(default=0, ge=0, description="缓存未命中次数")
    cache_hit_rate: float = Field(default=0.0, ge=0.0, le=100.0, description="缓存命中率(%)")
    
    # 错误指标
    error_count: int = Field(default=0, ge=0, description="错误次数")
    warning_count: int = Field(default=0, ge=0, description="警告次数")
    error_rate: float = Field(default=0.0, ge=0.0, le=100.0, description="错误率(%)")
    
    # 时间戳
    start_time: Optional[datetime] = Field(default=None, description="开始时间")
    end_time: Optional[datetime] = Field(default=None, description="结束时间")
    last_updated: datetime = Field(default_factory=datetime.now, description="最后更新时间")
    
    def update_cache_hit_rate(self):
        """更新缓存命中率"""
        total_requests = self.cache_hits + self.cache_misses
        if total_requests > 0:
            self.cache_hit_rate = (self.cache_hits / total_requests) * 100.0
        else:
            self.cache_hit_rate = 0.0
    
    def update_error_rate(self):
        """更新错误率"""
        if self.items_processed > 0:
            self.error_rate = (self.error_count / self.items_processed) * 100.0
        else:
            self.error_rate = 0.0
    
    def update_throughput(self):
        """更新吞吐量"""
        if self.processing_time_ms > 0:
            seconds = self.processing_time_ms / 1000.0
            self.throughput_per_second = self.items_processed / seconds
        else:
            self.throughput_per_second = 0.0
    
    def update_all_calculated_fields(self):
        """更新所有计算字段"""
        self.update_cache_hit_rate()
        self.update_error_rate()
        self.update_throughput()
        self.last_updated = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        self.update_all_calculated_fields()
        return self.dict()


@dataclass
class PerformanceSnapshot:
    """性能快照"""
    timestamp: datetime = field(default_factory=datetime.now)
    metrics: PerformanceMetrics = field(default_factory=PerformanceMetrics)
    algorithm_name: str = ""
    operation: str = ""
    context: Dict[str, Any] = field(default_factory=dict)


class AlgorithmPerformanceTracker:
    """算法性能跟踪器"""
    
    def __init__(self, algorithm_name: str, enable_detailed_tracking: bool = True):
        self.algorithm_name = algorithm_name
        self.enable_detailed_tracking = enable_detailed_tracking
        self._logger = get_logger(f'performance.{algorithm_name}')
        
        # 性能数据
        self._metrics = PerformanceMetrics()
        self._snapshots: List[PerformanceSnapshot] = []
        self._max_snapshots = 100  # 最多保留100个快照
        
        # 跟踪状态
        self._tracking_active = False
        self._operation_start_time: Optional[float] = None
        self._current_operation = ""
        
        # 线程安全
        self._lock = threading.RLock()
        
        self._logger.debug(f"性能跟踪器初始化: {algorithm_name}")
    
    def start_tracking(self, operation: str = "default"):
        """开始跟踪"""
        with self._lock:
            if self._tracking_active:
                self._logger.warning(f"跟踪已活跃，操作: {self._current_operation}")
                return
            
            self._tracking_active = True
            self._current_operation = operation
            self._operation_start_time = time.time()
            self._metrics.start_time = datetime.now()
            
            self._logger.debug(f"开始性能跟踪: {operation}")
    
    def stop_tracking(self):
        """停止跟踪"""
        with self._lock:
            if not self._tracking_active:
                self._logger.warning("跟踪未活跃")
                return
            
            if self._operation_start_time:
                elapsed_ms = (time.time() - self._operation_start_time) * 1000
                self._metrics.processing_time_ms += elapsed_ms
            
            self._metrics.end_time = datetime.now()
            self._tracking_active = False
            
            # 创建快照
            self._create_snapshot()
            
            self._logger.debug(f"停止性能跟踪: {self._current_operation}")
            self._current_operation = ""
            self._operation_start_time = None
    
    @contextmanager
    def track_operation(self, operation: str = "operation"):
        """上下文管理器形式的操作跟踪"""
        self.start_tracking(operation)
        try:
            yield self
        finally:
            self.stop_tracking()
    
    def record_item_processed(self, count: int = 1):
        """记录处理项目数量"""
        with self._lock:
            self._metrics.items_processed += count
    
    def record_cache_hit(self, count: int = 1):
        """记录缓存命中"""
        with self._lock:
            self._metrics.cache_hits += count
    
    def record_cache_miss(self, count: int = 1):
        """记录缓存未命中"""
        with self._lock:
            self._metrics.cache_misses += count
    
    def record_error(self, count: int = 1):
        """记录错误"""
        with self._lock:
            self._metrics.error_count += count
    
    def record_warning(self, count: int = 1):
        """记录警告"""
        with self._lock:
            self._metrics.warning_count += count
    
    def update_memory_usage(self, current_mb: float, peak_mb: Optional[float] = None):
        """更新内存使用情况"""
        with self._lock:
            self._metrics.memory_usage_mb = current_mb
            if peak_mb is not None:
                self._metrics.peak_memory_mb = max(self._metrics.peak_memory_mb, peak_mb)
            else:
                self._metrics.peak_memory_mb = max(self._metrics.peak_memory_mb, current_mb)
    
    def get_current_metrics(self) -> PerformanceMetrics:
        """获取当前性能指标"""
        with self._lock:
            # 如果正在跟踪，更新当前时间
            if self._tracking_active and self._operation_start_time:
                current_elapsed = (time.time() - self._operation_start_time) * 1000
                self._metrics.processing_time_ms += current_elapsed
                self._operation_start_time = time.time()  # 重置起始时间
            
            # 更新计算字段
            self._metrics.update_all_calculated_fields()
            
            # 返回拷贝
            return self._metrics.copy()
    
    def get_snapshots(self, limit: Optional[int] = None) -> List[PerformanceSnapshot]:
        """获取性能快照列表"""
        with self._lock:
            if limit is None:
                return self._snapshots.copy()
            else:
                return self._snapshots[-limit:].copy()
    
    def reset_metrics(self):
        """重置性能指标"""
        with self._lock:
            self._metrics = PerformanceMetrics()
            self._snapshots.clear()
            self._tracking_active = False
            self._current_operation = ""
            self._operation_start_time = None
            
            self._logger.debug("性能指标已重置")
    
    def _create_snapshot(self):
        """创建性能快照"""
        if not self.enable_detailed_tracking:
            return
        
        snapshot = PerformanceSnapshot(
            metrics=self._metrics.copy(),
            algorithm_name=self.algorithm_name,
            operation=self._current_operation,
            context={
                'tracking_active': self._tracking_active,
                'snapshots_count': len(self._snapshots)
            }
        )
        
        self._snapshots.append(snapshot)
        
        # 限制快照数量
        if len(self._snapshots) > self._max_snapshots:
            self._snapshots = self._snapshots[-self._max_snapshots:]
    
    def export_metrics(self, format: str = 'dict') -> Any:
        """导出性能指标"""
        metrics = self.get_current_metrics()
        
        if format == 'dict':
            return metrics.to_dict()
        elif format == 'json':
            return metrics.json()
        else:
            raise ValueError(f"不支持的导出格式: {format}")
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """获取性能摘要"""
        metrics = self.get_current_metrics()
        
        return {
            'algorithm': self.algorithm_name,
            'total_items': metrics.items_processed,
            'processing_time_sec': metrics.processing_time_ms / 1000.0,
            'throughput': metrics.throughput_per_second,
            'cache_hit_rate': metrics.cache_hit_rate,
            'error_rate': metrics.error_rate,
            'memory_usage_mb': metrics.memory_usage_mb,
            'peak_memory_mb': metrics.peak_memory_mb,
            'last_updated': metrics.last_updated.isoformat()
        }
    
    def __enter__(self):
        """支持上下文管理器"""
        self.start_tracking()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """支持上下文管理器"""
        if exc_type is not None:
            self.record_error()
        self.stop_tracking()


class PerformanceProfiler:
    """性能分析器 - 用于分析多个算法的性能"""
    
    def __init__(self):
        self._trackers: Dict[str, AlgorithmPerformanceTracker] = {}
        self._logger = get_logger('performance.profiler')
    
    def get_or_create_tracker(self, algorithm_name: str) -> AlgorithmPerformanceTracker:
        """获取或创建性能跟踪器"""
        if algorithm_name not in self._trackers:
            self._trackers[algorithm_name] = AlgorithmPerformanceTracker(algorithm_name)
        return self._trackers[algorithm_name]
    
    def get_tracker(self, algorithm_name: str) -> Optional[AlgorithmPerformanceTracker]:
        """获取性能跟踪器"""
        return self._trackers.get(algorithm_name)
    
    def compare_algorithms(self, algorithm_names: List[str]) -> Dict[str, Any]:
        """比较多个算法的性能"""
        comparison = {
            'algorithms': {},
            'comparison_time': datetime.now().isoformat(),
            'best_performer': {},
            'summary': {}
        }
        
        # 收集各算法指标
        all_metrics = {}
        for name in algorithm_names:
            tracker = self._trackers.get(name)
            if tracker:
                all_metrics[name] = tracker.get_performance_summary()
                comparison['algorithms'][name] = all_metrics[name]
        
        if not all_metrics:
            return comparison
        
        # 找出最佳表现者
        best_throughput = max(all_metrics.items(), key=lambda x: x[1]['throughput'])
        best_cache_hit = max(all_metrics.items(), key=lambda x: x[1]['cache_hit_rate'])
        lowest_error = min(all_metrics.items(), key=lambda x: x[1]['error_rate'])
        
        comparison['best_performer'] = {
            'throughput': {'algorithm': best_throughput[0], 'value': best_throughput[1]['throughput']},
            'cache_hit_rate': {'algorithm': best_cache_hit[0], 'value': best_cache_hit[1]['cache_hit_rate']},
            'error_rate': {'algorithm': lowest_error[0], 'value': lowest_error[1]['error_rate']}
        }
        
        # 生成摘要
        total_items = sum(metrics['total_items'] for metrics in all_metrics.values())
        avg_throughput = sum(metrics['throughput'] for metrics in all_metrics.values()) / len(all_metrics)
        
        comparison['summary'] = {
            'total_algorithms': len(all_metrics),
            'total_items_processed': total_items,
            'average_throughput': avg_throughput
        }
        
        return comparison
    
    def export_all_metrics(self, format: str = 'dict') -> Dict[str, Any]:
        """导出所有算法的性能指标"""
        export_data = {
            'export_time': datetime.now().isoformat(),
            'algorithms': {}
        }
        
        for name, tracker in self._trackers.items():
            export_data['algorithms'][name] = tracker.export_metrics(format)
        
        return export_data


# 全局性能分析器实例
_global_profiler: Optional[PerformanceProfiler] = None


def get_global_profiler() -> PerformanceProfiler:
    """获取全局性能分析器实例"""
    global _global_profiler
    if _global_profiler is None:
        _global_profiler = PerformanceProfiler()
    return _global_profiler


def get_algorithm_tracker(algorithm_name: str) -> AlgorithmPerformanceTracker:
    """获取指定算法的性能跟踪器"""
    return get_global_profiler().get_or_create_tracker(algorithm_name) 