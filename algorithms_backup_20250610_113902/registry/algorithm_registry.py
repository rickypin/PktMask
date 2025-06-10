#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
算法注册中心
管理所有算法插件的注册、发现和生命周期
"""

import threading
from typing import Dict, List, Optional, Type, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict

from ..interfaces.algorithm_interface import AlgorithmInterface, AlgorithmInfo, AlgorithmType, AlgorithmStatus
from ...infrastructure.logging import get_logger


@dataclass
class AlgorithmRegistration:
    """算法注册信息"""
    algorithm_class: Type[AlgorithmInterface]
    algorithm_info: AlgorithmInfo
    instance: Optional[AlgorithmInterface] = None
    registration_time: datetime = field(default_factory=datetime.now)
    is_active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_instance(self) -> AlgorithmInterface:
        """获取算法实例（单例模式）"""
        if self.instance is None:
            self.instance = self.algorithm_class()
        return self.instance
    
    def reset_instance(self):
        """重置算法实例"""
        if self.instance is not None:
            try:
                self.instance.cleanup()
            except Exception:
                pass
        self.instance = None


class AlgorithmRegistry:
    """算法注册中心"""
    
    def __init__(self):
        self._logger = get_logger('algorithm.registry')
        self._registrations: Dict[str, AlgorithmRegistration] = {}
        self._type_index: Dict[AlgorithmType, List[str]] = defaultdict(list)
        self._lock = threading.RLock()
        self._event_handlers: Dict[str, List[Callable]] = defaultdict(list)
        
        self._logger.info("算法注册中心初始化完成")
    
    def register_algorithm(
        self, 
        algorithm_class: Type[AlgorithmInterface],
        algorithm_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        注册算法插件
        
        Args:
            algorithm_class: 算法类
            algorithm_name: 算法名称（可选，默认使用类中定义的名称）
            metadata: 额外的元数据
            
        Returns:
            bool: 注册是否成功
        """
        with self._lock:
            try:
                # 创建临时实例获取信息
                temp_instance = algorithm_class()
                algorithm_info = temp_instance.get_algorithm_info()
                
                # 使用指定名称或默认名称
                name = algorithm_name or algorithm_info.name
                
                # 检查是否已注册
                if name in self._registrations:
                    existing_reg = self._registrations[name]
                    if existing_reg.is_active:
                        self._logger.warning(f"算法 {name} 已经注册，跳过重复注册")
                        return False
                    else:
                        # 替换非活跃的注册
                        self._logger.info(f"替换非活跃的算法注册: {name}")
                        self._remove_from_type_index(name, existing_reg.algorithm_info.algorithm_type)
                
                # 创建注册信息
                registration = AlgorithmRegistration(
                    algorithm_class=algorithm_class,
                    algorithm_info=algorithm_info,
                    metadata=metadata or {}
                )
                
                # 注册
                self._registrations[name] = registration
                self._type_index[algorithm_info.algorithm_type].append(name)
                
                # 触发注册事件
                self._trigger_event('algorithm_registered', {
                    'name': name,
                    'type': algorithm_info.algorithm_type,
                    'registration': registration
                })
                
                self._logger.info(f"成功注册算法: {name} (类型: {algorithm_info.algorithm_type.value})")
                return True
                
            except Exception as e:
                self._logger.error(f"注册算法失败 {algorithm_class.__name__}: {e}")
                return False
    
    def unregister_algorithm(self, algorithm_name: str) -> bool:
        """
        注销算法插件
        
        Args:
            algorithm_name: 算法名称
            
        Returns:
            bool: 注销是否成功
        """
        with self._lock:
            if algorithm_name not in self._registrations:
                self._logger.warning(f"算法 {algorithm_name} 未注册")
                return False
            
            try:
                registration = self._registrations[algorithm_name]
                
                # 清理实例
                registration.reset_instance()
                
                # 从索引中移除
                self._remove_from_type_index(algorithm_name, registration.algorithm_info.algorithm_type)
                
                # 从注册表中移除
                del self._registrations[algorithm_name]
                
                # 触发注销事件
                self._trigger_event('algorithm_unregistered', {
                    'name': algorithm_name,
                    'registration': registration
                })
                
                self._logger.info(f"成功注销算法: {algorithm_name}")
                return True
                
            except Exception as e:
                self._logger.error(f"注销算法失败 {algorithm_name}: {e}")
                return False
    
    def get_algorithm(self, algorithm_name: str) -> Optional[AlgorithmInterface]:
        """
        获取算法实例
        
        Args:
            algorithm_name: 算法名称
            
        Returns:
            Optional[AlgorithmInterface]: 算法实例，未找到返回None
        """
        with self._lock:
            registration = self._registrations.get(algorithm_name)
            if registration is None or not registration.is_active:
                return None
            
            try:
                return registration.get_instance()
            except Exception as e:
                self._logger.error(f"创建算法实例失败 {algorithm_name}: {e}")
                return None
    
    def get_algorithms_by_type(self, algorithm_type: AlgorithmType) -> List[AlgorithmInterface]:
        """
        根据类型获取算法实例列表
        
        Args:
            algorithm_type: 算法类型
            
        Returns:
            List[AlgorithmInterface]: 算法实例列表
        """
        algorithms = []
        algorithm_names = self._type_index.get(algorithm_type, [])
        
        for name in algorithm_names:
            algorithm = self.get_algorithm(name)
            if algorithm is not None:
                algorithms.append(algorithm)
        
        return algorithms
    
    def list_registered_algorithms(self) -> List[str]:
        """
        列出所有已注册的算法名称
        
        Returns:
            List[str]: 算法名称列表
        """
        with self._lock:
            return [name for name, reg in self._registrations.items() if reg.is_active]
    
    def get_algorithm_info(self, algorithm_name: str) -> Optional[AlgorithmInfo]:
        """
        获取算法信息
        
        Args:
            algorithm_name: 算法名称
            
        Returns:
            Optional[AlgorithmInfo]: 算法信息，未找到返回None
        """
        with self._lock:
            registration = self._registrations.get(algorithm_name)
            if registration is None or not registration.is_active:
                return None
            return registration.algorithm_info
    
    def get_algorithms_info_by_type(self, algorithm_type: AlgorithmType) -> List[AlgorithmInfo]:
        """
        根据类型获取算法信息列表
        
        Args:
            algorithm_type: 算法类型
            
        Returns:
            List[AlgorithmInfo]: 算法信息列表
        """
        infos = []
        algorithm_names = self._type_index.get(algorithm_type, [])
        
        for name in algorithm_names:
            info = self.get_algorithm_info(name)
            if info is not None:
                infos.append(info)
        
        return infos
    
    def is_registered(self, algorithm_name: str) -> bool:
        """
        检查算法是否已注册
        
        Args:
            algorithm_name: 算法名称
            
        Returns:
            bool: 是否已注册
        """
        with self._lock:
            registration = self._registrations.get(algorithm_name)
            return registration is not None and registration.is_active
    
    def get_algorithm_status(self, algorithm_name: str) -> Optional[AlgorithmStatus]:
        """
        获取算法状态
        
        Args:
            algorithm_name: 算法名称
            
        Returns:
            Optional[AlgorithmStatus]: 算法状态，未找到返回None
        """
        algorithm = self.get_algorithm(algorithm_name)
        if algorithm is None:
            return None
        return algorithm.get_status()
    
    def initialize_algorithm(self, algorithm_name: str) -> bool:
        """
        初始化算法
        
        Args:
            algorithm_name: 算法名称
            
        Returns:
            bool: 初始化是否成功
        """
        algorithm = self.get_algorithm(algorithm_name)
        if algorithm is None:
            self._logger.error(f"算法 {algorithm_name} 未注册")
            return False
        
        try:
            return algorithm.initialize()
        except Exception as e:
            self._logger.error(f"初始化算法失败 {algorithm_name}: {e}")
            return False
    
    def cleanup_algorithm(self, algorithm_name: str):
        """
        清理算法资源
        
        Args:
            algorithm_name: 算法名称
        """
        with self._lock:
            registration = self._registrations.get(algorithm_name)
            if registration is not None:
                registration.reset_instance()
    
    def cleanup_all(self):
        """清理所有算法资源"""
        with self._lock:
            for registration in self._registrations.values():
                registration.reset_instance()
            self._logger.info("所有算法资源已清理")
    
    def get_registry_stats(self) -> Dict[str, Any]:
        """
        获取注册中心统计信息
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        with self._lock:
            active_registrations = [reg for reg in self._registrations.values() if reg.is_active]
            
            type_counts = {}
            for algo_type in AlgorithmType:
                type_counts[algo_type.value] = len(self._type_index.get(algo_type, []))
            
            stats = {
                'total_registered': len(active_registrations),
                'total_inactive': len(self._registrations) - len(active_registrations),
                'type_distribution': type_counts,
                'oldest_registration': min(
                    (reg.registration_time for reg in active_registrations),
                    default=None
                ),
                'newest_registration': max(
                    (reg.registration_time for reg in active_registrations),
                    default=None
                )
            }
            
            return stats
    
    # === 事件处理机制 ===
    
    def add_event_handler(self, event_type: str, handler: Callable):
        """
        添加事件处理器
        
        Args:
            event_type: 事件类型 ('algorithm_registered', 'algorithm_unregistered')
            handler: 事件处理函数
        """
        with self._lock:
            self._event_handlers[event_type].append(handler)
    
    def remove_event_handler(self, event_type: str, handler: Callable):
        """
        移除事件处理器
        
        Args:
            event_type: 事件类型
            handler: 事件处理函数
        """
        with self._lock:
            if handler in self._event_handlers[event_type]:
                self._event_handlers[event_type].remove(handler)
    
    def _trigger_event(self, event_type: str, event_data: Dict[str, Any]):
        """触发事件"""
        handlers = self._event_handlers.get(event_type, [])
        for handler in handlers:
            try:
                handler(event_data)
            except Exception as e:
                self._logger.error(f"事件处理器执行失败 {event_type}: {e}")
    
    def _remove_from_type_index(self, algorithm_name: str, algorithm_type: AlgorithmType):
        """从类型索引中移除算法"""
        if algorithm_name in self._type_index[algorithm_type]:
            self._type_index[algorithm_type].remove(algorithm_name)
    
    # === 装饰器支持 ===
    
    def register(self, name: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
        """
        装饰器形式的注册
        
        Args:
            name: 算法名称
            metadata: 元数据
            
        Returns:
            装饰器函数
        """
        def decorator(algorithm_class: Type[AlgorithmInterface]):
            self.register_algorithm(algorithm_class, name, metadata)
            return algorithm_class
        return decorator
    
    def __contains__(self, algorithm_name: str) -> bool:
        """支持 'name' in registry 语法"""
        return self.is_registered(algorithm_name)
    
    def __len__(self) -> int:
        """获取注册算法数量"""
        with self._lock:
            return len([reg for reg in self._registrations.values() if reg.is_active])
    
    def __iter__(self):
        """支持迭代"""
        with self._lock:
            return iter(name for name, reg in self._registrations.items() if reg.is_active)


# 全局注册中心实例
_global_registry: Optional[AlgorithmRegistry] = None


def get_algorithm_registry() -> AlgorithmRegistry:
    """获取全局算法注册中心实例"""
    global _global_registry
    if _global_registry is None:
        _global_registry = AlgorithmRegistry()
    return _global_registry


# 便捷函数
def register_algorithm(algorithm_class: Type[AlgorithmInterface], name: Optional[str] = None) -> bool:
    """注册算法（便捷函数）"""
    return get_algorithm_registry().register_algorithm(algorithm_class, name)


def get_algorithm(algorithm_name: str) -> Optional[AlgorithmInterface]:
    """获取算法实例（便捷函数）"""
    return get_algorithm_registry().get_algorithm(algorithm_name)


def list_algorithms() -> List[str]:
    """列出所有算法（便捷函数）"""
    return get_algorithm_registry().list_registered_algorithms() 