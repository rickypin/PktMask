#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Stage结果类

封装单个Stage的处理结果和相关信息。
"""

from typing import Any, Optional, Dict
from dataclasses import dataclass, field
import time
from enum import Enum, auto


class StageStatus(Enum):
    """Stage执行状态枚举"""
    PENDING = auto()      # 等待执行
    RUNNING = auto()      # 正在执行
    COMPLETED = auto()    # 执行成功
    FAILED = auto()       # 执行失败
    CANCELLED = auto()    # 已取消


@dataclass
class StageMetrics:
    """Stage执行指标"""
    execution_time: float = 0.0          # 执行时间（秒）
    memory_usage_mb: float = 0.0         # 内存使用量（MB）
    input_size_bytes: int = 0            # 输入大小（字节）
    output_size_bytes: int = 0           # 输出大小（字节）
    processed_packets: int = 0           # 处理的包数量
    processed_flows: int = 0             # 处理的流数量
    
    # 性能指标
    packets_per_second: float = 0.0      # 每秒处理包数
    throughput_mbps: float = 0.0         # 吞吐量（Mbps）
    
    def calculate_derived_metrics(self) -> None:
        """计算派生指标"""
        if self.execution_time > 0:
            self.packets_per_second = self.processed_packets / self.execution_time
            if self.input_size_bytes > 0:
                self.throughput_mbps = (self.input_size_bytes / (1024 * 1024)) / self.execution_time


@dataclass
class StageResult:
    """Stage处理结果
    
    封装单个Stage的处理结果、统计信息和元数据。
    """
    
    # 基本信息
    stage_name: str
    status: StageStatus
    
    # 时间信息
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    
    # 结果信息
    success: bool = False
    data: Any = None
    error: Optional[str] = None
    warning_count: int = 0
    
    # 指标信息
    metrics: StageMetrics = field(default_factory=StageMetrics)
    
    # 统计信息
    stats: Dict[str, Any] = field(default_factory=dict)
    
    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def mark_completed(self, success: bool = True, data: Any = None, 
                      error: Optional[str] = None) -> None:
        """标记Stage完成
        
        Args:
            success: 是否成功
            data: 结果数据
            error: 错误信息
        """
        self.end_time = time.time()
        self.success = success
        self.data = data
        self.error = error
        self.status = StageStatus.COMPLETED if success else StageStatus.FAILED
        
        # 计算执行时间
        self.metrics.execution_time = self.end_time - self.start_time
        
        # 计算派生指标
        self.metrics.calculate_derived_metrics()
    
    def mark_failed(self, error: str) -> None:
        """标记Stage失败
        
        Args:
            error: 错误信息
        """
        self.mark_completed(success=False, error=error)
    
    def mark_cancelled(self) -> None:
        """标记Stage取消"""
        self.end_time = time.time()
        self.status = StageStatus.CANCELLED
        self.metrics.execution_time = self.end_time - self.start_time
    
    def add_warning(self, message: str) -> None:
        """添加警告信息
        
        Args:
            message: 警告消息
        """
        self.warning_count += 1
        warnings = self.metadata.setdefault('warnings', [])
        warnings.append({
            'timestamp': time.time(),
            'message': message
        })
    
    def update_metrics(self, **kwargs) -> None:
        """更新指标
        
        Args:
            **kwargs: 指标键值对
        """
        for key, value in kwargs.items():
            if hasattr(self.metrics, key):
                setattr(self.metrics, key, value)
        
        # 重新计算派生指标
        self.metrics.calculate_derived_metrics()
    
    def update_stats(self, stats: Dict[str, Any]) -> None:
        """更新统计信息
        
        Args:
            stats: 统计信息字典
        """
        self.stats.update(stats)
    
    def get_duration(self) -> float:
        """获取执行时长
        
        Returns:
            执行时长（秒）
        """
        if self.end_time is None:
            return time.time() - self.start_time
        return self.end_time - self.start_time
    
    def is_running(self) -> bool:
        """检查是否正在执行"""
        return self.status == StageStatus.RUNNING
    
    def is_completed(self) -> bool:
        """检查是否已完成"""
        return self.status in (StageStatus.COMPLETED, StageStatus.FAILED, StageStatus.CANCELLED)
    
    def get_summary(self) -> Dict[str, Any]:
        """获取结果摘要
        
        Returns:
            结果摘要字典
        """
        return {
            'stage_name': self.stage_name,
            'status': self.status.name,
            'success': self.success,
            'duration': self.get_duration(),
            'processed_packets': self.metrics.processed_packets,
            'processed_flows': self.metrics.processed_flows,
            'warning_count': self.warning_count,
            'error': self.error
        }
    
    def get_detailed_stats(self) -> Dict[str, Any]:
        """获取详细统计信息
        
        Returns:
            详细统计信息字典
        """
        detailed_stats = {
            'basic_info': {
                'stage_name': self.stage_name,
                'status': self.status.name,
                'success': self.success,
                'start_time': self.start_time,
                'end_time': self.end_time,
                'duration': self.get_duration()
            },
            'metrics': {
                'execution_time': self.metrics.execution_time,
                'memory_usage_mb': self.metrics.memory_usage_mb,
                'input_size_bytes': self.metrics.input_size_bytes,
                'output_size_bytes': self.metrics.output_size_bytes,
                'processed_packets': self.metrics.processed_packets,
                'processed_flows': self.metrics.processed_flows,
                'packets_per_second': self.metrics.packets_per_second,
                'throughput_mbps': self.metrics.throughput_mbps
            },
            'stats': self.stats.copy(),
            'warnings': self.warning_count,
            'error': self.error
        }
        
        if self.metadata:
            detailed_stats['metadata'] = self.metadata.copy()
        
        return detailed_stats
    
    def __bool__(self) -> bool:
        """布尔转换：成功时为True"""
        return self.success
    
    def __str__(self) -> str:
        """字符串表示"""
        status_str = "成功" if self.success else "失败"
        duration_str = f"{self.get_duration():.2f}s"
        
        if self.status == StageStatus.RUNNING:
            return f"[{self.stage_name}] 正在执行... - 已用时: {duration_str}"
        else:
            return f"[{self.stage_name}] {status_str} - 耗时: {duration_str}"
    
    def __repr__(self) -> str:
        """调试表示"""
        return f"StageResult(name='{self.stage_name}', status={self.status.name}, success={self.success})"


class StageResultCollection:
    """Stage结果集合
    
    管理多个Stage的结果，提供汇总和查询功能。
    """
    
    def __init__(self):
        self.results: Dict[str, StageResult] = {}
        self._execution_order: list = []
    
    def add_result(self, result: StageResult) -> None:
        """添加Stage结果
        
        Args:
            result: Stage结果
        """
        self.results[result.stage_name] = result
        if result.stage_name not in self._execution_order:
            self._execution_order.append(result.stage_name)
    
    def get_result(self, stage_name: str) -> Optional[StageResult]:
        """获取指定Stage的结果
        
        Args:
            stage_name: Stage名称
            
        Returns:
            Stage结果，如果不存在则返回None
        """
        return self.results.get(stage_name)
    
    def get_all_results(self) -> list:
        """获取所有结果（按执行顺序）
        
        Returns:
            所有Stage结果列表
        """
        return [self.results[name] for name in self._execution_order if name in self.results]
    
    def get_successful_count(self) -> int:
        """获取成功的Stage数量"""
        return sum(1 for result in self.results.values() if result.success)
    
    def get_failed_count(self) -> int:
        """获取失败的Stage数量"""
        return sum(1 for result in self.results.values() if not result.success)
    
    def get_total_duration(self) -> float:
        """获取总执行时间"""
        return sum(result.get_duration() for result in self.results.values())
    
    def is_all_successful(self) -> bool:
        """检查是否所有Stage都成功"""
        return all(result.success for result in self.results.values())
    
    def get_summary(self) -> Dict[str, Any]:
        """获取整体摘要
        
        Returns:
            整体摘要字典
        """
        return {
            'total_stages': len(self.results),
            'successful_stages': self.get_successful_count(),
            'failed_stages': self.get_failed_count(),
            'total_duration': self.get_total_duration(),
            'all_successful': self.is_all_successful(),
            'stage_summaries': [result.get_summary() for result in self.get_all_results()]
        } 