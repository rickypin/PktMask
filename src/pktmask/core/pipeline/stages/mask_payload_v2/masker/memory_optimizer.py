"""
内存优化器

提供内存监控、垃圾回收优化和内存使用限制功能。
"""

from __future__ import annotations

import gc
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Callable
import weakref


@dataclass
class MemoryStats:
    """内存统计信息"""
    current_usage: int      # 当前内存使用量（字节）
    peak_usage: int         # 峰值内存使用量（字节）
    gc_collections: int     # 垃圾回收次数
    last_gc_time: float     # 上次垃圾回收时间
    memory_pressure: float  # 内存压力指数 (0.0-1.0)


class MemoryOptimizer:
    """内存优化器
    
    提供内存监控、自动垃圾回收和内存使用限制功能。
    """
    
    def __init__(self, config: Dict[str, Any]):
        """初始化内存优化器
        
        Args:
            config: 配置字典
        """
        self.config = config
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        
        # 配置参数
        self.max_memory_mb = config.get('max_memory_mb', 2048)  # 2GB默认限制
        self.gc_threshold = config.get('gc_threshold', 0.8)     # 80%内存使用率触发GC
        self.monitoring_interval = config.get('monitoring_interval', 100)  # 每100个操作监控一次
        self.enable_aggressive_gc = config.get('enable_aggressive_gc', False)
        
        # 内部状态
        self.operation_count = 0
        self.gc_count = 0
        self.peak_memory = 0
        self.last_gc_time = time.time()
        self.memory_callbacks = []  # 内存压力回调函数
        
        # 弱引用缓存，用于跟踪大对象
        self.large_objects = weakref.WeakSet()
        
        self.logger.info(f"内存优化器初始化: 最大内存={self.max_memory_mb}MB, "
                        f"GC阈值={self.gc_threshold*100}%")
    
    def get_memory_stats(self) -> MemoryStats:
        """获取当前内存统计信息"""
        try:
            import psutil
            process = psutil.Process()
            current_memory = process.memory_info().rss
            
            # 更新峰值内存
            if current_memory > self.peak_memory:
                self.peak_memory = current_memory
            
            # 计算内存压力
            max_memory_bytes = self.max_memory_mb * 1024 * 1024
            memory_pressure = min(1.0, current_memory / max_memory_bytes)
            
            return MemoryStats(
                current_usage=current_memory,
                peak_usage=self.peak_memory,
                gc_collections=self.gc_count,
                last_gc_time=self.last_gc_time,
                memory_pressure=memory_pressure
            )
        except ImportError:
            # 如果没有psutil，返回基础统计
            return MemoryStats(
                current_usage=0,
                peak_usage=0,
                gc_collections=self.gc_count,
                last_gc_time=self.last_gc_time,
                memory_pressure=0.0
            )
    
    def check_memory_pressure(self) -> bool:
        """检查内存压力，如果需要则触发优化
        
        Returns:
            是否触发了内存优化
        """
        self.operation_count += 1
        
        # 定期检查内存使用
        if self.operation_count % self.monitoring_interval == 0:
            stats = self.get_memory_stats()
            
            # 如果内存压力过高，触发优化
            if stats.memory_pressure >= self.gc_threshold:
                self.logger.warning(f"内存压力过高: {stats.memory_pressure*100:.1f}%, "
                                  f"当前使用: {stats.current_usage/1024/1024:.1f}MB")
                
                # 触发垃圾回收
                self._trigger_garbage_collection()
                
                # 调用内存压力回调
                self._notify_memory_pressure(stats)
                
                return True
        
        return False
    
    def register_memory_callback(self, callback: Callable[[MemoryStats], None]):
        """注册内存压力回调函数
        
        Args:
            callback: 回调函数，接收MemoryStats参数
        """
        self.memory_callbacks.append(callback)
    
    def track_large_object(self, obj: Any, size_hint: Optional[int] = None):
        """跟踪大对象，用于内存监控
        
        Args:
            obj: 要跟踪的对象
            size_hint: 对象大小提示（字节）
        """
        self.large_objects.add(obj)
        if size_hint and size_hint > 10 * 1024 * 1024:  # 10MB以上的对象
            self.logger.debug(f"跟踪大对象: {type(obj).__name__}, 大小约: {size_hint/1024/1024:.1f}MB")
    
    def optimize_memory(self, force: bool = False) -> Dict[str, Any]:
        """执行内存优化
        
        Args:
            force: 是否强制执行优化
            
        Returns:
            优化结果统计
        """
        start_time = time.time()
        stats_before = self.get_memory_stats()
        
        # 执行垃圾回收
        collected = self._trigger_garbage_collection()
        
        # 清理弱引用缓存
        self._cleanup_weak_references()
        
        # 如果启用激进GC，执行额外的清理
        if self.enable_aggressive_gc or force:
            self._aggressive_cleanup()
        
        stats_after = self.get_memory_stats()
        optimization_time = time.time() - start_time
        
        result = {
            'memory_before_mb': stats_before.current_usage / 1024 / 1024,
            'memory_after_mb': stats_after.current_usage / 1024 / 1024,
            'memory_freed_mb': (stats_before.current_usage - stats_after.current_usage) / 1024 / 1024,
            'gc_collected': collected,
            'optimization_time': optimization_time,
            'large_objects_tracked': len(self.large_objects)
        }
        
        self.logger.info(f"内存优化完成: 释放 {result['memory_freed_mb']:.1f}MB, "
                        f"耗时 {optimization_time:.3f}秒")
        
        return result
    
    def _trigger_garbage_collection(self) -> int:
        """触发垃圾回收"""
        collected = gc.collect()
        self.gc_count += 1
        self.last_gc_time = time.time()
        
        self.logger.debug(f"垃圾回收完成: 回收对象数={collected}")
        return collected
    
    def _cleanup_weak_references(self):
        """清理弱引用缓存"""
        # WeakSet会自动清理失效的引用，这里只是触发清理
        initial_count = len(self.large_objects)
        # 强制访问所有元素以触发清理
        _ = list(self.large_objects)
        final_count = len(self.large_objects)
        
        if initial_count != final_count:
            self.logger.debug(f"清理弱引用: {initial_count} -> {final_count}")
    
    def _aggressive_cleanup(self):
        """激进的内存清理"""
        # 强制执行所有代的垃圾回收
        for generation in range(3):
            gc.collect(generation)
        
        # 清理模块级缓存（如果安全的话）
        try:
            # 清理一些常见的缓存
            if hasattr(gc, 'get_stats'):
                # Python 3.4+
                stats = gc.get_stats()
                self.logger.debug(f"GC统计: {stats}")
        except Exception as e:
            self.logger.debug(f"激进清理时出现异常: {e}")
    
    def _notify_memory_pressure(self, stats: MemoryStats):
        """通知内存压力回调"""
        for callback in self.memory_callbacks:
            try:
                callback(stats)
            except Exception as e:
                self.logger.warning(f"内存压力回调执行失败: {e}")
    
    def get_optimization_report(self) -> Dict[str, Any]:
        """获取优化报告"""
        stats = self.get_memory_stats()
        
        return {
            'current_memory_mb': stats.current_usage / 1024 / 1024,
            'peak_memory_mb': stats.peak_usage / 1024 / 1024,
            'memory_pressure': stats.memory_pressure,
            'gc_collections': stats.gc_collections,
            'operations_processed': self.operation_count,
            'large_objects_tracked': len(self.large_objects),
            'config': {
                'max_memory_mb': self.max_memory_mb,
                'gc_threshold': self.gc_threshold,
                'monitoring_interval': self.monitoring_interval,
                'aggressive_gc': self.enable_aggressive_gc
            }
        }


def create_memory_optimizer(config: Dict[str, Any]) -> MemoryOptimizer:
    """创建内存优化器实例的工厂函数
    
    Args:
        config: 配置字典
        
    Returns:
        MemoryOptimizer: 内存优化器实例
    """
    return MemoryOptimizer(config)
