#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
性能监控器
提供实时性能指标监控功能
"""

import time
import sys
import threading
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# 添加src路径到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from pktmask.infrastructure.logging import get_logger


@dataclass
class PerformanceSnapshot:
    """性能快照"""
    timestamp: float
    memory_usage_mb: float
    cpu_percent: float
    process_id: int
    thread_count: int
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'timestamp': self.timestamp,
            'memory_usage_mb': self.memory_usage_mb,
            'cpu_percent': self.cpu_percent,
            'process_id': self.process_id,
            'thread_count': self.thread_count
        }


class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self, sampling_interval: float = 1.0):
        """
        初始化性能监控器
        
        Args:
            sampling_interval: 采样间隔（秒）
        """
        self._logger = get_logger('performance_monitor')
        self.sampling_interval = sampling_interval
        
        # 性能数据存储
        self.snapshots: List[PerformanceSnapshot] = []
        self.max_snapshots = 1000  # 最多保存1000个快照
        
        # 监控状态
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        
        # 检查依赖
        self._psutil_available = self._check_psutil()
        if not self._psutil_available:
            self._logger.warning("psutil不可用，部分性能监控功能将被禁用")
    
    def _check_psutil(self) -> bool:
        """检查psutil是否可用"""
        try:
            import psutil
            return True
        except ImportError:
            return False
    
    def get_memory_usage(self) -> float:
        """
        获取当前内存使用量（MB）
        
        Returns:
            float: 内存使用量（MB），如果获取失败返回0
        """
        if not self._psutil_available:
            return 0.0
            
        try:
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
            return memory_info.rss / 1024 / 1024  # 转换为MB
        except Exception as e:
            self._logger.debug(f"获取内存使用量失败: {e}")
            return 0.0
    
    def get_cpu_percent(self) -> float:
        """
        获取CPU使用率
        
        Returns:
            float: CPU使用率百分比，如果获取失败返回0
        """
        if not self._psutil_available:
            return 0.0
            
        try:
            import psutil
            process = psutil.Process()
            return process.cpu_percent()
        except Exception as e:
            self._logger.debug(f"获取CPU使用率失败: {e}")
            return 0.0
    
    def get_system_info(self) -> Dict[str, Any]:
        """
        获取系统信息
        
        Returns:
            Dict[str, Any]: 系统信息字典
        """
        info = {
            'psutil_available': self._psutil_available,
            'memory_usage_mb': self.get_memory_usage(),
            'cpu_percent': self.get_cpu_percent(),
        }
        
        if self._psutil_available:
            try:
                import psutil
                import os
                
                process = psutil.Process()
                info.update({
                    'process_id': os.getpid(),
                    'thread_count': process.num_threads(),
                    'cpu_count': psutil.cpu_count(),
                    'total_memory_gb': psutil.virtual_memory().total / (1024**3),
                    'available_memory_gb': psutil.virtual_memory().available / (1024**3)
                })
            except Exception as e:
                self._logger.debug(f"获取扩展系统信息失败: {e}")
        
        return info
    
    def start_monitoring(self):
        """开始持续监控"""
        if self._monitoring:
            self._logger.warning("性能监控已在运行中")
            return
        
        self._monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        self._logger.info("开始性能监控")
    
    def stop_monitoring(self):
        """停止监控"""
        if not self._monitoring:
            return
        
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2.0)
        self._logger.info("停止性能监控")
    
    def _monitor_loop(self):
        """监控循环"""
        while self._monitoring:
            try:
                snapshot = self._take_snapshot()
                self.snapshots.append(snapshot)
                
                # 限制快照数量
                if len(self.snapshots) > self.max_snapshots:
                    self.snapshots.pop(0)
                
                time.sleep(self.sampling_interval)
                
            except Exception as e:
                self._logger.error(f"性能监控循环出错: {e}")
                time.sleep(1.0)  # 出错时稍作等待
    
    def _take_snapshot(self) -> PerformanceSnapshot:
        """拍摄性能快照"""
        import os
        
        memory_mb = self.get_memory_usage()
        cpu_percent = self.get_cpu_percent()
        
        thread_count = 1
        if self._psutil_available:
            try:
                import psutil
                process = psutil.Process()
                thread_count = process.num_threads()
            except Exception:
                pass
        
        return PerformanceSnapshot(
            timestamp=time.time(),
            memory_usage_mb=memory_mb,
            cpu_percent=cpu_percent,
            process_id=os.getpid(),
            thread_count=thread_count
        )
    
    def get_performance_summary(self, start_time: Optional[float] = None,
                              end_time: Optional[float] = None) -> Dict[str, Any]:
        """
        获取性能汇总统计
        
        Args:
            start_time: 开始时间戳，None表示从最早开始
            end_time: 结束时间戳，None表示到最新结束
            
        Returns:
            Dict[str, Any]: 性能汇总统计
        """
        if not self.snapshots:
            return {
                'error': '没有性能数据',
                'snapshot_count': 0
            }
        
        # 筛选时间范围内的快照
        filtered_snapshots = []
        for snapshot in self.snapshots:
            if start_time and snapshot.timestamp < start_time:
                continue
            if end_time and snapshot.timestamp > end_time:
                continue
            filtered_snapshots.append(snapshot)
        
        if not filtered_snapshots:
            return {
                'error': '指定时间范围内没有数据',
                'snapshot_count': 0
            }
        
        # 计算统计值
        memory_values = [s.memory_usage_mb for s in filtered_snapshots]
        cpu_values = [s.cpu_percent for s in filtered_snapshots]
        
        summary = {
            'snapshot_count': len(filtered_snapshots),
            'time_span_seconds': filtered_snapshots[-1].timestamp - filtered_snapshots[0].timestamp,
            'memory_stats': {
                'min_mb': min(memory_values),
                'max_mb': max(memory_values),
                'avg_mb': sum(memory_values) / len(memory_values),
                'peak_mb': max(memory_values)
            },
            'cpu_stats': {
                'min_percent': min(cpu_values),
                'max_percent': max(cpu_values), 
                'avg_percent': sum(cpu_values) / len(cpu_values)
            },
            'first_snapshot': filtered_snapshots[0].to_dict(),
            'last_snapshot': filtered_snapshots[-1].to_dict()
        }
        
        return summary
    
    def export_snapshots(self, output_file: str, start_time: Optional[float] = None,
                        end_time: Optional[float] = None):
        """
        导出性能快照数据
        
        Args:
            output_file: 输出文件路径
            start_time: 开始时间戳
            end_time: 结束时间戳
        """
        import json
        
        # 筛选数据
        filtered_snapshots = []
        for snapshot in self.snapshots:
            if start_time and snapshot.timestamp < start_time:
                continue
            if end_time and snapshot.timestamp > end_time:
                continue
            filtered_snapshots.append(snapshot.to_dict())
        
        export_data = {
            'metadata': {
                'export_time': time.time(),
                'sampling_interval': self.sampling_interval,
                'snapshot_count': len(filtered_snapshots),
                'time_range': {
                    'start': start_time,
                    'end': end_time
                }
            },
            'snapshots': filtered_snapshots,
            'summary': self.get_performance_summary(start_time, end_time)
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        self._logger.info(f"性能数据已导出到: {output_file}")
    
    def clear_snapshots(self):
        """清空所有快照数据"""
        self.snapshots.clear()
        self._logger.debug("性能快照数据已清空")
    
    def get_peak_memory_usage(self, start_time: Optional[float] = None,
                             end_time: Optional[float] = None) -> float:
        """
        获取峰值内存使用量
        
        Args:
            start_time: 开始时间戳
            end_time: 结束时间戳
            
        Returns:
            float: 峰值内存使用量（MB）
        """
        if not self.snapshots:
            return 0.0
        
        peak_memory = 0.0
        for snapshot in self.snapshots:
            if start_time and snapshot.timestamp < start_time:
                continue
            if end_time and snapshot.timestamp > end_time:
                continue
            peak_memory = max(peak_memory, snapshot.memory_usage_mb)
        
        return peak_memory
    
    def __enter__(self):
        """上下文管理器入口"""
        self.start_monitoring()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.stop_monitoring() 