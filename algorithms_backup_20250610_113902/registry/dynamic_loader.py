#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
动态插件加载系统 - Phase 6.4
集成插件发现、依赖管理和沙箱系统的核心组件
"""

import threading
import time
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Type, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..interfaces.algorithm_interface import (
    AlgorithmInterface, AlgorithmInfo, AlgorithmType, ValidationResult
)
from .plugin_discovery import (
    PluginDiscoveryEngine, PluginCandidate, PluginSource, get_plugin_discovery_engine
)
from .dependency_resolver import (
    DependencyResolver, DependencyGraph, get_dependency_resolver
)
from .plugin_sandbox import (
    SandboxManager, SandboxLevel, SandboxConfig, ExecutionResult, get_sandbox_manager
)
from .enhanced_plugin_manager import (
    EnhancedPluginManager, PluginRegistration, get_enhanced_plugin_manager
)
from ...infrastructure.logging import get_logger
from ...common.exceptions import PluginError, DependencyError


class LoadingStrategy(Enum):
    """加载策略"""
    LAZY = "lazy"           # 懒加载
    EAGER = "eager"         # 立即加载
    ON_DEMAND = "on_demand" # 按需加载
    PRELOAD = "preload"     # 预加载


class PluginState(Enum):
    """插件状态"""
    DISCOVERED = "discovered"       # 已发现
    LOADING = "loading"             # 正在加载
    LOADED = "loaded"               # 已加载
    ACTIVE = "active"               # 激活状态
    INACTIVE = "inactive"           # 非激活状态
    ERROR = "error"                 # 错误状态
    UNLOADING = "unloading"         # 正在卸载
    UNLOADED = "unloaded"           # 已卸载


@dataclass
class LoadingConfig:
    """加载配置"""
    strategy: LoadingStrategy = LoadingStrategy.LAZY
    sandbox_level: SandboxLevel = SandboxLevel.BASIC
    auto_resolve_dependencies: bool = True
    auto_install_dependencies: bool = False
    max_concurrent_loads: int = 5
    load_timeout: int = 60
    enable_hot_reload: bool = True
    cache_instances: bool = True
    validation_required: bool = True


@dataclass
class LoadedPlugin:
    """已加载插件信息"""
    candidate: PluginCandidate
    instance: Optional[AlgorithmInterface] = None
    registration: Optional[PluginRegistration] = None
    state: PluginState = PluginState.DISCOVERED
    load_time: Optional[datetime] = None
    last_access: Optional[datetime] = None
    access_count: int = 0
    sandbox_id: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class PluginLifecycleManager:
    """插件生命周期管理器"""
    
    def __init__(self, loader):
        self._loader = loader
        self._logger = get_logger('loader.lifecycle')
        self._lifecycle_hooks: Dict[str, List[Callable]] = {
            'pre_load': [],
            'post_load': [],
            'pre_unload': [],
            'post_unload': [],
            'on_error': [],
            'on_state_change': []
        }
    
    def add_hook(self, event: str, callback: Callable):
        """添加生命周期钩子"""
        if event in self._lifecycle_hooks:
            self._lifecycle_hooks[event].append(callback)
    
    def remove_hook(self, event: str, callback: Callable):
        """移除生命周期钩子"""
        if event in self._lifecycle_hooks and callback in self._lifecycle_hooks[event]:
            self._lifecycle_hooks[event].remove(callback)
    
    def trigger_hooks(self, event: str, plugin: LoadedPlugin, **kwargs):
        """触发生命周期钩子"""
        for callback in self._lifecycle_hooks.get(event, []):
            try:
                callback(plugin, **kwargs)
            except Exception as e:
                self._logger.error(f"生命周期钩子执行失败 {event}: {e}")
    
    def change_state(self, plugin: LoadedPlugin, new_state: PluginState, error_message: Optional[str] = None):
        """更改插件状态"""
        old_state = plugin.state
        plugin.state = new_state
        
        if error_message:
            plugin.error_message = error_message
        
        self._logger.info(f"插件状态变更: {plugin.candidate.algorithm_info.name} {old_state.value} -> {new_state.value}")
        
        self.trigger_hooks('on_state_change', plugin, old_state=old_state, new_state=new_state)
        
        if new_state == PluginState.ERROR:
            self.trigger_hooks('on_error', plugin, error_message=error_message)


class DynamicPluginLoader:
    """动态插件加载器"""
    
    def __init__(self, config: Optional[LoadingConfig] = None):
        self._config = config or LoadingConfig()
        self._logger = get_logger('plugin.loader')
        
        # 核心组件
        self._discovery_engine = get_plugin_discovery_engine()
        self._dependency_resolver = get_dependency_resolver()
        self._sandbox_manager = get_sandbox_manager()
        self._plugin_manager = get_enhanced_plugin_manager()
        
        # 生命周期管理
        self._lifecycle_manager = PluginLifecycleManager(self)
        
        # 插件状态管理
        self._loaded_plugins: Dict[str, LoadedPlugin] = {}
        self._plugin_instances: Dict[str, AlgorithmInterface] = {}
        self._load_order: List[str] = []
        self._lock = threading.RLock()
        
        # 线程池
        self._executor = ThreadPoolExecutor(max_workers=self._config.max_concurrent_loads)
        
        # 注册发现回调
        self._discovery_engine.add_discovery_callback(self._on_plugin_discovered)
        
        self._logger.info("动态插件加载器初始化完成")
    
    def _on_plugin_discovered(self, candidate: PluginCandidate):
        """插件发现回调"""
        if not candidate.is_valid or not candidate.algorithm_info:
            return
        
        plugin_name = candidate.algorithm_info.name
        
        with self._lock:
            if plugin_name not in self._loaded_plugins:
                loaded_plugin = LoadedPlugin(candidate=candidate)
                self._loaded_plugins[plugin_name] = loaded_plugin
                
                self._logger.info(f"发现新插件: {plugin_name}")
                
                # 根据加载策略决定是否立即加载
                if self._config.strategy == LoadingStrategy.EAGER:
                    self._async_load_plugin(plugin_name)
                elif self._config.strategy == LoadingStrategy.PRELOAD:
                    # 预加载：验证但不创建实例
                    self._async_preload_plugin(plugin_name)
    
    def discover_plugins(self, force_rescan: bool = False) -> List[str]:
        """
        发现插件
        
        Args:
            force_rescan: 是否强制重新扫描
            
        Returns:
            List[str]: 发现的插件名称列表
        """
        candidates = self._discovery_engine.discover_plugins(force_rescan)
        plugin_names = []
        
        for candidate in candidates:
            if candidate.is_valid and candidate.algorithm_info:
                plugin_names.append(candidate.algorithm_info.name)
        
        self._logger.info(f"发现 {len(plugin_names)} 个有效插件")
        return plugin_names
    
    def load_plugin(self, plugin_name: str, force_reload: bool = False) -> bool:
        """
        加载插件
        
        Args:
            plugin_name: 插件名称
            force_reload: 是否强制重新加载
            
        Returns:
            bool: 是否加载成功
        """
        with self._lock:
            if plugin_name not in self._loaded_plugins:
                self._logger.error(f"插件未发现: {plugin_name}")
                return False
            
            loaded_plugin = self._loaded_plugins[plugin_name]
            
            # 检查是否已加载
            if loaded_plugin.state == PluginState.LOADED and not force_reload:
                self._logger.info(f"插件已加载: {plugin_name}")
                return True
            
            # 检查是否正在加载
            if loaded_plugin.state == PluginState.LOADING:
                self._logger.info(f"插件正在加载: {plugin_name}")
                return False
            
            return self._load_plugin_sync(loaded_plugin)
    
    def _load_plugin_sync(self, loaded_plugin: LoadedPlugin) -> bool:
        """同步加载插件"""
        plugin_name = loaded_plugin.candidate.algorithm_info.name
        
        try:
            self._lifecycle_manager.change_state(loaded_plugin, PluginState.LOADING)
            self._lifecycle_manager.trigger_hooks('pre_load', loaded_plugin)
            
            # 依赖检查和解析
            if self._config.auto_resolve_dependencies:
                if not self._resolve_dependencies([loaded_plugin.candidate]):
                    self._lifecycle_manager.change_state(
                        loaded_plugin, 
                        PluginState.ERROR, 
                        "依赖解析失败"
                    )
                    return False
            
            # 创建沙箱
            sandbox_id = f"plugin_{plugin_name}_{int(time.time())}"
            sandbox = self._sandbox_manager.create_sandbox(
                sandbox_id,
                self._sandbox_manager.get_default_config(self._config.sandbox_level)
            )
            loaded_plugin.sandbox_id = sandbox_id
            
            # 创建插件实例
            plugin_class = loaded_plugin.candidate.plugin_class
            plugin_instance = plugin_class()
            
            # 验证插件
            if self._config.validation_required:
                validation_result = self._validate_plugin_instance(plugin_instance)
                if not validation_result.is_valid:
                    error_msg = f"插件验证失败: {', '.join(validation_result.errors)}"
                    self._lifecycle_manager.change_state(loaded_plugin, PluginState.ERROR, error_msg)
                    return False
            
            # 注册插件
            registration = self._plugin_manager.register_algorithm(
                plugin_instance,
                metadata=loaded_plugin.candidate.source.metadata if loaded_plugin.candidate.source else {}
            )
            
            # 更新加载信息
            loaded_plugin.instance = plugin_instance
            loaded_plugin.registration = registration
            loaded_plugin.load_time = datetime.now()
            
            # 缓存实例
            if self._config.cache_instances:
                self._plugin_instances[plugin_name] = plugin_instance
            
            # 更新加载顺序
            if plugin_name not in self._load_order:
                self._load_order.append(plugin_name)
            
            self._lifecycle_manager.change_state(loaded_plugin, PluginState.LOADED)
            self._lifecycle_manager.trigger_hooks('post_load', loaded_plugin)
            
            self._logger.info(f"成功加载插件: {plugin_name}")
            return True
            
        except Exception as e:
            error_msg = f"加载插件失败: {e}"
            self._lifecycle_manager.change_state(loaded_plugin, PluginState.ERROR, error_msg)
            self._logger.error(error_msg)
            return False
    
    def _async_load_plugin(self, plugin_name: str):
        """异步加载插件"""
        future = self._executor.submit(self.load_plugin, plugin_name)
        future.add_done_callback(
            lambda f: self._logger.info(f"异步加载完成: {plugin_name}, 结果: {f.result()}")
        )
    
    def _async_preload_plugin(self, plugin_name: str):
        """异步预加载插件"""
        def preload():
            with self._lock:
                if plugin_name in self._loaded_plugins:
                    loaded_plugin = self._loaded_plugins[plugin_name]
                    # 只进行依赖检查，不创建实例
                    if self._config.auto_resolve_dependencies:
                        self._resolve_dependencies([loaded_plugin.candidate])
        
        future = self._executor.submit(preload)
        future.add_done_callback(
            lambda f: self._logger.info(f"预加载完成: {plugin_name}")
        )
    
    def unload_plugin(self, plugin_name: str) -> bool:
        """
        卸载插件
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            bool: 是否卸载成功
        """
        with self._lock:
            if plugin_name not in self._loaded_plugins:
                return False
            
            loaded_plugin = self._loaded_plugins[plugin_name]
            
            if loaded_plugin.state not in [PluginState.LOADED, PluginState.ACTIVE, PluginState.INACTIVE]:
                return False
            
            try:
                self._lifecycle_manager.change_state(loaded_plugin, PluginState.UNLOADING)
                self._lifecycle_manager.trigger_hooks('pre_unload', loaded_plugin)
                
                # 注销插件
                if loaded_plugin.registration:
                    self._plugin_manager.unregister_algorithm(loaded_plugin.registration.algorithm_id)
                
                # 清理沙箱
                if loaded_plugin.sandbox_id:
                    self._sandbox_manager.remove_sandbox(loaded_plugin.sandbox_id)
                
                # 清理实例缓存
                if plugin_name in self._plugin_instances:
                    del self._plugin_instances[plugin_name]
                
                # 更新加载顺序
                if plugin_name in self._load_order:
                    self._load_order.remove(plugin_name)
                
                # 重置插件状态
                loaded_plugin.instance = None
                loaded_plugin.registration = None
                loaded_plugin.sandbox_id = None
                loaded_plugin.load_time = None
                
                self._lifecycle_manager.change_state(loaded_plugin, PluginState.UNLOADED)
                self._lifecycle_manager.trigger_hooks('post_unload', loaded_plugin)
                
                self._logger.info(f"成功卸载插件: {plugin_name}")
                return True
                
            except Exception as e:
                error_msg = f"卸载插件失败: {e}"
                self._lifecycle_manager.change_state(loaded_plugin, PluginState.ERROR, error_msg)
                self._logger.error(error_msg)
                return False
    
    def get_plugin_instance(self, plugin_name: str) -> Optional[AlgorithmInterface]:
        """
        获取插件实例
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            Optional[AlgorithmInterface]: 插件实例
        """
        with self._lock:
            # 按需加载
            if (self._config.strategy == LoadingStrategy.ON_DEMAND and 
                plugin_name in self._loaded_plugins and
                self._loaded_plugins[plugin_name].state == PluginState.DISCOVERED):
                self.load_plugin(plugin_name)
            
            # 从缓存获取
            if plugin_name in self._plugin_instances:
                loaded_plugin = self._loaded_plugins[plugin_name]
                loaded_plugin.last_access = datetime.now()
                loaded_plugin.access_count += 1
                return self._plugin_instances[plugin_name]
            
            return None
    
    def execute_plugin_method(
        self,
        plugin_name: str,
        method_name: str,
        *args,
        **kwargs
    ) -> ExecutionResult:
        """
        在沙箱中执行插件方法
        
        Args:
            plugin_name: 插件名称
            method_name: 方法名称
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            ExecutionResult: 执行结果
        """
        plugin_instance = self.get_plugin_instance(plugin_name)
        if plugin_instance is None:
            return ExecutionResult(
                success=False,
                error=f"插件未加载或不存在: {plugin_name}"
            )
        
        with self._lock:
            loaded_plugin = self._loaded_plugins[plugin_name]
            if loaded_plugin.sandbox_id is None:
                return ExecutionResult(
                    success=False,
                    error=f"插件沙箱未创建: {plugin_name}"
                )
            
            return self._sandbox_manager.execute_in_sandbox(
                loaded_plugin.sandbox_id,
                plugin_instance,
                method_name,
                *args,
                **kwargs
            )
    
    def _resolve_dependencies(self, candidates: List[PluginCandidate]) -> bool:
        """解析依赖"""
        try:
            graph, results = self._dependency_resolver.resolve_dependencies(
                candidates,
                auto_install=self._config.auto_install_dependencies,
                dry_run=not self._config.auto_install_dependencies
            )
            
            # 检查是否有失败的依赖
            for plugin_name, result in results.items():
                if not result.is_valid:
                    self._logger.error(f"插件依赖检查失败 {plugin_name}: {', '.join(result.errors)}")
                    return False
            
            return True
            
        except Exception as e:
            self._logger.error(f"依赖解析失败: {e}")
            return False
    
    def _validate_plugin_instance(self, instance: AlgorithmInterface) -> ValidationResult:
        """验证插件实例"""
        result = ValidationResult(is_valid=True)
        
        try:
            # 检查必需方法
            required_methods = ['get_algorithm_info', 'process', 'cleanup']
            for method in required_methods:
                if not hasattr(instance, method) or not callable(getattr(instance, method)):
                    result.add_error(f"缺少必需方法: {method}")
            
            # 检查算法信息
            if hasattr(instance, 'get_algorithm_info'):
                algorithm_info = instance.get_algorithm_info()
                if not algorithm_info.name:
                    result.add_error("算法名称不能为空")
                if not algorithm_info.version:
                    result.add_error("算法版本不能为空")
            
        except Exception as e:
            result.add_error(f"验证过程中发生错误: {e}")
        
        return result
    
    def list_loaded_plugins(self) -> List[LoadedPlugin]:
        """列出已加载的插件"""
        with self._lock:
            return [p for p in self._loaded_plugins.values() if p.state == PluginState.LOADED]
    
    def get_plugin_info(self, plugin_name: str) -> Optional[LoadedPlugin]:
        """获取插件信息"""
        with self._lock:
            return self._loaded_plugins.get(plugin_name)
    
    def get_loading_stats(self) -> Dict[str, Any]:
        """获取加载统计信息"""
        with self._lock:
            stats = {
                "total_plugins": len(self._loaded_plugins),
                "loaded_plugins": len([p for p in self._loaded_plugins.values() if p.state == PluginState.LOADED]),
                "error_plugins": len([p for p in self._loaded_plugins.values() if p.state == PluginState.ERROR]),
                "plugins_by_state": {},
                "load_order": self._load_order.copy(),
                "most_accessed": None,
                "least_accessed": None
            }
            
            # 按状态统计
            for plugin in self._loaded_plugins.values():
                state = plugin.state.value
                stats["plugins_by_state"][state] = stats["plugins_by_state"].get(state, 0) + 1
            
            # 访问统计
            loaded_plugins = [p for p in self._loaded_plugins.values() if p.state == PluginState.LOADED]
            if loaded_plugins:
                most_accessed = max(loaded_plugins, key=lambda p: p.access_count)
                least_accessed = min(loaded_plugins, key=lambda p: p.access_count)
                stats["most_accessed"] = {
                    "name": most_accessed.candidate.algorithm_info.name,
                    "count": most_accessed.access_count
                }
                stats["least_accessed"] = {
                    "name": least_accessed.candidate.algorithm_info.name,
                    "count": least_accessed.access_count
                }
            
            return stats
    
    def add_lifecycle_hook(self, event: str, callback: Callable):
        """添加生命周期钩子"""
        self._lifecycle_manager.add_hook(event, callback)
    
    def remove_lifecycle_hook(self, event: str, callback: Callable):
        """移除生命周期钩子"""
        self._lifecycle_manager.remove_hook(event, callback)
    
    def cleanup(self):
        """清理资源"""
        self._logger.info("开始清理动态加载器资源...")
        
        # 卸载所有插件
        with self._lock:
            plugin_names = list(self._loaded_plugins.keys())
            for plugin_name in plugin_names:
                self.unload_plugin(plugin_name)
        
        # 关闭线程池
        self._executor.shutdown(wait=True)
        
        # 清理沙箱
        self._sandbox_manager.cleanup_all()
        
        self._logger.info("动态加载器资源清理完成")


# 全局动态加载器实例
_dynamic_loader: Optional[DynamicPluginLoader] = None


def get_dynamic_plugin_loader() -> DynamicPluginLoader:
    """获取全局动态加载器实例"""
    global _dynamic_loader
    if _dynamic_loader is None:
        _dynamic_loader = DynamicPluginLoader()
    return _dynamic_loader 