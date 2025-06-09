#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
增强的插件管理器 - Phase 6.2
支持版本管理、依赖检查、动态发现、热插拔和监控功能
"""

import os
import sys
import json
import time
import threading
import importlib
import importlib.util
from pathlib import Path
from typing import Dict, List, Optional, Type, Any, Callable, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from ..interfaces.algorithm_interface import (
    AlgorithmInterface, AlgorithmInfo, AlgorithmType, AlgorithmStatus,
    AlgorithmDependency, DependencyType, PluginConfig, AlgorithmConfig
)
from ...infrastructure.logging import get_logger


@dataclass
class PluginMetrics:
    """插件性能指标"""
    load_time_ms: float = 0.0
    total_executions: int = 0
    total_execution_time_ms: float = 0.0
    average_execution_time_ms: float = 0.0
    last_execution_time: Optional[datetime] = None
    error_count: int = 0
    last_error_time: Optional[datetime] = None
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0
    
    def update_execution_metrics(self, execution_time_ms: float):
        """更新执行指标"""
        self.total_executions += 1
        self.total_execution_time_ms += execution_time_ms
        self.average_execution_time_ms = self.total_execution_time_ms / self.total_executions
        self.last_execution_time = datetime.now()
    
    def record_error(self):
        """记录错误"""
        self.error_count += 1
        self.last_error_time = datetime.now()


@dataclass
class PluginRegistration:
    """增强的插件注册信息"""
    algorithm_class: Type[AlgorithmInterface]
    algorithm_info: AlgorithmInfo
    plugin_config: PluginConfig
    instance: Optional[AlgorithmInterface] = None
    registration_time: datetime = field(default_factory=datetime.now)
    last_health_check: Optional[datetime] = None
    health_status: str = "unknown"
    restart_count: int = 0
    metrics: PluginMetrics = field(default_factory=PluginMetrics)
    config_file_path: Optional[str] = None
    module_path: Optional[str] = None
    is_active: bool = True
    
    def get_instance(self) -> AlgorithmInterface:
        """获取算法实例（单例模式）"""
        if self.instance is None:
            start_time = time.time()
            self.instance = self.algorithm_class()
            load_time = (time.time() - start_time) * 1000
            self.metrics.load_time_ms = load_time
        return self.instance
    
    def reset_instance(self):
        """重置算法实例"""
        if self.instance is not None:
            try:
                self.instance.cleanup()
            except Exception:
                pass
        self.instance = None
    
    def can_restart(self) -> bool:
        """检查是否可以重启"""
        return self.restart_count < self.plugin_config.max_restart_attempts


class DependencyManager:
    """依赖管理器"""
    
    def __init__(self):
        self._logger = get_logger('plugin.dependency')
        self._installed_packages: Dict[str, str] = {}
        self._refresh_installed_packages()
    
    def _refresh_installed_packages(self):
        """刷新已安装包的信息"""
        try:
            import pkg_resources
            for package in pkg_resources.working_set:
                self._installed_packages[package.project_name.lower()] = package.version
        except Exception as e:
            self._logger.warning(f"无法获取已安装包信息: {e}")
    
    def check_dependencies(self, dependencies: List[AlgorithmDependency]) -> List[str]:
        """检查依赖关系，返回缺失或不兼容的依赖列表"""
        missing_deps = []
        
        for dep in dependencies:
            package_name = dep.name.lower()
            
            if package_name not in self._installed_packages:
                if dep.dependency_type == DependencyType.REQUIRED:
                    missing_deps.append(f"缺少必需依赖: {dep.name}")
                elif dep.dependency_type == DependencyType.OPTIONAL:
                    self._logger.info(f"缺少可选依赖: {dep.name}")
                continue
            
            installed_version = self._installed_packages[package_name]
            if not dep.is_version_compatible(installed_version):
                missing_deps.append(
                    f"依赖版本不兼容: {dep.name} "
                    f"(需要 {dep.version_spec}, 已安装 {installed_version})"
                )
        
        return missing_deps
    
    def get_python_version(self) -> str:
        """获取当前Python版本"""
        return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


class PluginDiscovery:
    """插件发现机制"""
    
    def __init__(self, search_paths: List[str]):
        self._logger = get_logger('plugin.discovery')
        self._search_paths = search_paths
        self._plugin_cache: Dict[str, Dict[str, Any]] = {}
        self._last_scan_time: Optional[datetime] = None
    
    def discover_plugins(self, force_rescan: bool = False) -> List[Dict[str, Any]]:
        """发现所有可用的插件"""
        if not force_rescan and self._last_scan_time:
            cache_age = datetime.now() - self._last_scan_time
            if cache_age < timedelta(minutes=5):
                return list(self._plugin_cache.values())
        
        self._plugin_cache.clear()
        discovered_plugins = []
        
        for search_path in self._search_paths:
            path = Path(search_path)
            if not path.exists():
                continue
                
            self._logger.info(f"扫描插件目录: {path}")
            plugins = self._scan_directory(path)
            discovered_plugins.extend(plugins)
        
        self._last_scan_time = datetime.now()
        self._logger.info(f"发现 {len(discovered_plugins)} 个插件")
        return discovered_plugins
    
    def _scan_directory(self, directory: Path) -> List[Dict[str, Any]]:
        """扫描目录中的插件"""
        plugins = []
        
        for py_file in directory.rglob("*.py"):
            if py_file.name.startswith("__"):
                continue
                
            plugin_info = self._analyze_python_file(py_file)
            if plugin_info:
                plugins.append(plugin_info)
        
        return plugins
    
    def _analyze_python_file(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """分析Python文件，查找插件类"""
        try:
            module_name = f"plugin_{file_path.stem}_{hash(str(file_path))}"
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec is None or spec.loader is None:
                return None
                
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and 
                    issubclass(attr, AlgorithmInterface) and 
                    attr != AlgorithmInterface):
                    
                    temp_instance = attr()
                    algorithm_info = temp_instance.get_algorithm_info()
                    
                    plugin_info = {
                        'name': algorithm_info.name,
                        'version': algorithm_info.version,
                        'type': algorithm_info.algorithm_type,
                        'class_name': attr_name,
                        'module_path': str(file_path),
                        'algorithm_info': algorithm_info,
                        'algorithm_class': attr
                    }
                    
                    self._plugin_cache[algorithm_info.name] = plugin_info
                    return plugin_info
                    
        except Exception as e:
            self._logger.debug(f"分析文件 {file_path} 时出错: {e}")
        
        return None


class PluginMonitor:
    """插件监控器"""
    
    def __init__(self, registry):
        self._logger = get_logger('plugin.monitor')
        self._registry = registry
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_monitor = threading.Event()
        self._executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="plugin-monitor")
    
    def start_monitoring(self):
        """开始监控"""
        if self._monitor_thread and self._monitor_thread.is_alive():
            return
            
        self._stop_monitor.clear()
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            name="plugin-monitor-main",
            daemon=True
        )
        self._monitor_thread.start()
        self._logger.info("插件监控已启动")
    
    def stop_monitoring(self):
        """停止监控"""
        self._stop_monitor.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        self._executor.shutdown(wait=True)
        self._logger.info("插件监控已停止")
    
    def _monitor_loop(self):
        """监控主循环"""
        while not self._stop_monitor.is_set():
            try:
                self._perform_health_checks()
                self._collect_metrics()
                self._cleanup_failed_plugins()
                
                self._stop_monitor.wait(timeout=30)
                
            except Exception as e:
                self._logger.error(f"监控循环出错: {e}")
    
    def _perform_health_checks(self):
        """执行健康检查"""
        registrations = self._registry.get_all_registrations()
        
        for name, registration in registrations.items():
            if not registration.plugin_config.enable_monitoring:
                continue
                
            self._executor.submit(self._check_plugin_health, name, registration)
    
    def _check_plugin_health(self, plugin_name: str, registration: PluginRegistration):
        """检查单个插件健康状态"""
        try:
            now = datetime.now()
            interval = registration.plugin_config.health_check_interval
            
            if (registration.last_health_check and 
                (now - registration.last_health_check).total_seconds() < interval):
                return
            
            if registration.instance:
                status = registration.instance.get_status()
                if status == AlgorithmStatus.ERROR:
                    registration.health_status = "error"
                    self._handle_unhealthy_plugin(plugin_name, registration)
                else:
                    registration.health_status = "healthy"
            else:
                registration.health_status = "not_loaded"
            
            registration.last_health_check = now
            
        except Exception as e:
            self._logger.error(f"插件 {plugin_name} 健康检查失败: {e}")
            registration.health_status = "check_failed"
            registration.metrics.record_error()
    
    def _collect_metrics(self):
        """收集性能指标"""
        try:
            import psutil
            
            registrations = self._registry.get_all_registrations()
            for name, registration in registrations.items():
                if registration.instance:
                    try:
                        process = psutil.Process()
                        registration.metrics.memory_usage_mb = process.memory_info().rss / 1024 / 1024
                        registration.metrics.cpu_usage_percent = process.cpu_percent()
                    except Exception:
                        pass
                        
        except ImportError:
            pass
        except Exception as e:
            self._logger.debug(f"收集系统指标时出错: {e}")
    
    def _handle_unhealthy_plugin(self, plugin_name: str, registration: PluginRegistration):
        """处理不健康的插件"""
        if registration.can_restart():
            self._logger.warning(f"尝试重启插件: {plugin_name}")
            try:
                registration.reset_instance()
                registration.restart_count += 1
                registration.get_instance()
                self._logger.info(f"插件 {plugin_name} 重启成功")
                
            except Exception as e:
                self._logger.error(f"插件 {plugin_name} 重启失败: {e}")
                registration.is_active = False
        else:
            self._logger.error(f"插件 {plugin_name} 超过最大重启次数，标记为不活跃")
            registration.is_active = False
    
    def _cleanup_failed_plugins(self):
        """清理失败的插件"""
        registrations = self._registry.get_all_registrations()
        
        for name, registration in registrations.items():
            if (not registration.is_active and 
                registration.health_status in ["error", "check_failed"]):
                
                registration.reset_instance()
                self._logger.info(f"清理失败插件的资源: {name}")


class EnhancedPluginManager:
    """增强的插件管理器"""
    
    def __init__(self, search_paths: Optional[List[str]] = None):
        self._logger = get_logger('plugin.manager')
        
        # 核心组件
        self._registrations: Dict[str, PluginRegistration] = {}
        self._type_index: Dict[AlgorithmType, Set[str]] = defaultdict(set)
        self._lock = threading.RLock()
        
        # 增强功能组件
        self._dependency_manager = DependencyManager()
        self._discovery = PluginDiscovery(search_paths or self._get_default_search_paths())
        self._monitor = PluginMonitor(self)
        
        # 事件处理
        self._event_handlers: Dict[str, List[Callable]] = defaultdict(list)
        
        self._logger.info("增强插件管理器初始化完成")
    
    def _get_default_search_paths(self) -> List[str]:
        """获取默认的插件搜索路径"""
        current_dir = Path(__file__).parent.parent
        return [
            str(current_dir / "implementations"),
            str(Path.cwd() / "plugins"),
            str(Path.home() / ".pktmask" / "plugins")
        ]
    
    def start(self):
        """启动插件管理器"""
        self._monitor.start_monitoring()
        self.auto_discover_and_register()
        self._logger.info("增强插件管理器已启动")
    
    def stop(self):
        """停止插件管理器"""
        self._monitor.stop_monitoring()
        self.cleanup_all()
        self._logger.info("增强插件管理器已停止")
    
    def auto_discover_and_register(self) -> int:
        """自动发现并注册插件"""
        discovered_plugins = self._discovery.discover_plugins()
        registered_count = 0
        
        for plugin_info in discovered_plugins:
            try:
                algorithm_class = plugin_info.get('algorithm_class')
                if algorithm_class:
                    plugin_config = PluginConfig()
                    if self.register_plugin(algorithm_class, plugin_config=plugin_config):
                        registered_count += 1
                        
            except Exception as e:
                self._logger.error(f"自动注册插件失败 {plugin_info.get('name', 'unknown')}: {e}")
        
        self._logger.info(f"自动发现并注册了 {registered_count} 个插件")
        return registered_count
    
    def register_plugin(
        self,
        algorithm_class: Type[AlgorithmInterface],
        plugin_config: Optional[PluginConfig] = None,
        algorithm_name: Optional[str] = None
    ) -> bool:
        """注册插件"""
        with self._lock:
            try:
                temp_instance = algorithm_class()
                algorithm_info = temp_instance.get_algorithm_info()
                name = algorithm_name or algorithm_info.name
                
                # 检查Python版本兼容性
                python_version = self._dependency_manager.get_python_version()
                if not algorithm_info.is_compatible_with_python(python_version):
                    self._logger.error(f"插件 {name} 与Python {python_version} 不兼容")
                    return False
                
                # 检查依赖关系
                missing_deps = self._dependency_manager.check_dependencies(algorithm_info.dependencies)
                if missing_deps:
                    self._logger.error(f"插件 {name} 依赖检查失败: {'; '.join(missing_deps)}")
                    return False
                
                if plugin_config is None:
                    plugin_config = PluginConfig()
                
                if name in self._registrations:
                    existing_reg = self._registrations[name]
                    if existing_reg.is_active:
                        self._logger.warning(f"插件 {name} 已经注册，跳过重复注册")
                        return False
                    else:
                        self._remove_from_type_index(name, existing_reg.algorithm_info.algorithm_type)
                
                registration = PluginRegistration(
                    algorithm_class=algorithm_class,
                    algorithm_info=algorithm_info,
                    plugin_config=plugin_config
                )
                
                self._registrations[name] = registration
                self._type_index[algorithm_info.algorithm_type].add(name)
                
                self._trigger_event('plugin_registered', {
                    'name': name,
                    'type': algorithm_info.algorithm_type,
                    'version': algorithm_info.version,
                    'registration': registration
                })
                
                self._logger.info(f"成功注册插件: {name} v{algorithm_info.version}")
                return True
                
            except Exception as e:
                self._logger.error(f"注册插件失败 {algorithm_class.__name__}: {e}")
                return False
    
    def unregister_plugin(self, plugin_name: str) -> bool:
        """注销插件"""
        with self._lock:
            if plugin_name not in self._registrations:
                self._logger.warning(f"插件 {plugin_name} 未注册")
                return False
            
            try:
                registration = self._registrations[plugin_name]
                registration.reset_instance()
                self._remove_from_type_index(plugin_name, registration.algorithm_info.algorithm_type)
                del self._registrations[plugin_name]
                
                self._trigger_event('plugin_unregistered', {
                    'name': plugin_name,
                    'registration': registration
                })
                
                self._logger.info(f"成功注销插件: {plugin_name}")
                return True
                
            except Exception as e:
                self._logger.error(f"注销插件失败 {plugin_name}: {e}")
                return False
    
    def reload_plugin(self, plugin_name: str) -> bool:
        """热重载插件"""
        with self._lock:
            if plugin_name not in self._registrations:
                self._logger.warning(f"插件 {plugin_name} 未注册")
                return False
            
            try:
                registration = self._registrations[plugin_name]
                
                if not registration.plugin_config.hot_reload:
                    self._logger.warning(f"插件 {plugin_name} 不支持热重载")
                    return False
                
                self._logger.info(f"开始热重载插件: {plugin_name}")
                
                old_config = registration.instance.get_config() if registration.instance else None
                registration.reset_instance()
                new_instance = registration.get_instance()
                
                if old_config:
                    new_instance.configure(old_config)
                
                self._trigger_event('plugin_reloaded', {
                    'name': plugin_name,
                    'registration': registration
                })
                
                self._logger.info(f"插件 {plugin_name} 热重载成功")
                return True
                
            except Exception as e:
                self._logger.error(f"热重载插件失败 {plugin_name}: {e}")
                return False
    
    def get_plugin(self, plugin_name: str) -> Optional[AlgorithmInterface]:
        """获取插件实例"""
        with self._lock:
            registration = self._registrations.get(plugin_name)
            if registration is None or not registration.is_active:
                return None
            
            try:
                start_time = time.time()
                instance = registration.get_instance()
                execution_time = (time.time() - start_time) * 1000
                
                registration.metrics.update_execution_metrics(execution_time)
                
                return instance
                
            except Exception as e:
                self._logger.error(f"获取插件实例失败 {plugin_name}: {e}")
                registration.metrics.record_error()
                return None
    
    def get_plugins_by_type(self, algorithm_type: AlgorithmType) -> List[AlgorithmInterface]:
        """根据类型获取插件实例列表"""
        plugins = []
        plugin_names = list(self._type_index.get(algorithm_type, set()))
        
        for name in plugin_names:
            plugin = self.get_plugin(name)
            if plugin is not None:
                plugins.append(plugin)
        
        return plugins
    
    def list_plugins(self, include_inactive: bool = False) -> List[str]:
        """列出所有插件名称"""
        with self._lock:
            if include_inactive:
                return list(self._registrations.keys())
            else:
                return [name for name, reg in self._registrations.items() if reg.is_active]
    
    def get_plugin_info(self, plugin_name: str) -> Optional[AlgorithmInfo]:
        """获取插件信息"""
        with self._lock:
            registration = self._registrations.get(plugin_name)
            if registration is None:
                return None
            return registration.algorithm_info
    
    def get_plugin_metrics(self, plugin_name: str) -> Optional[PluginMetrics]:
        """获取插件性能指标"""
        with self._lock:
            registration = self._registrations.get(plugin_name)
            if registration is None:
                return None
            return registration.metrics
    
    def get_all_registrations(self) -> Dict[str, PluginRegistration]:
        """获取所有注册信息（用于监控）"""
        with self._lock:
            return dict(self._registrations)
    
    def get_manager_stats(self) -> Dict[str, Any]:
        """获取管理器统计信息"""
        with self._lock:
            stats = {
                'total_plugins': len(self._registrations),
                'active_plugins': len([reg for reg in self._registrations.values() if reg.is_active]),
                'plugins_by_type': {},
                'total_executions': 0,
                'total_errors': 0,
                'average_load_time_ms': 0.0
            }
            
            for plugin_type, plugin_names in self._type_index.items():
                stats['plugins_by_type'][plugin_type.value] = len(plugin_names)
            
            if self._registrations:
                total_load_time = sum(reg.metrics.load_time_ms for reg in self._registrations.values())
                stats['average_load_time_ms'] = total_load_time / len(self._registrations)
                
                stats['total_executions'] = sum(reg.metrics.total_executions for reg in self._registrations.values())
                stats['total_errors'] = sum(reg.metrics.error_count for reg in self._registrations.values())
            
            return stats
    
    def cleanup_all(self):
        """清理所有插件"""
        with self._lock:
            plugin_names = list(self._registrations.keys())
            for name in plugin_names:
                try:
                    self.unregister_plugin(name)
                except Exception as e:
                    self._logger.error(f"清理插件失败 {name}: {e}")
            
            self._logger.info("所有插件已清理")
    
    def _remove_from_type_index(self, plugin_name: str, algorithm_type: AlgorithmType):
        """从类型索引中移除插件"""
        if algorithm_type in self._type_index:
            self._type_index[algorithm_type].discard(plugin_name)
            if not self._type_index[algorithm_type]:
                del self._type_index[algorithm_type]
    
    def _trigger_event(self, event_type: str, event_data: Dict[str, Any]):
        """触发事件"""
        handlers = self._event_handlers.get(event_type, [])
        for handler in handlers:
            try:
                handler(event_data)
            except Exception as e:
                self._logger.error(f"事件处理器执行失败 {event_type}: {e}")
    
    def add_event_handler(self, event_type: str, handler: Callable):
        """添加事件处理器"""
        self._event_handlers[event_type].append(handler)
    
    def remove_event_handler(self, event_type: str, handler: Callable):
        """移除事件处理器"""
        if event_type in self._event_handlers:
            try:
                self._event_handlers[event_type].remove(handler)
            except ValueError:
                pass


# 全局插件管理器实例
_plugin_manager: Optional[EnhancedPluginManager] = None


def get_plugin_manager() -> EnhancedPluginManager:
    """获取全局插件管理器实例"""
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = EnhancedPluginManager()
    return _plugin_manager


def initialize_plugin_system(search_paths: Optional[List[str]] = None):
    """初始化插件系统"""
    global _plugin_manager
    _plugin_manager = EnhancedPluginManager(search_paths)
    _plugin_manager.start()
    return _plugin_manager


def cleanup_plugin_system():
    """清理插件系统"""
    global _plugin_manager
    if _plugin_manager:
        _plugin_manager.stop()
        _plugin_manager = None 