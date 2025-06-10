#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
算法插件加载器
支持算法插件的动态发现、加载和管理
"""

import os
import sys
import importlib
import importlib.util
import inspect
from typing import Dict, List, Optional, Type, Any, Set
from pathlib import Path
from dataclasses import dataclass

from ..interfaces.algorithm_interface import AlgorithmInterface, AlgorithmType
from ...infrastructure.logging import get_logger
from ...common.exceptions import PluginError


@dataclass
class PluginScanResult:
    """插件扫描结果"""
    found_plugins: List[Type[AlgorithmInterface]]
    scan_paths: List[str]
    errors: List[str]
    scan_duration: float


class PluginLoader:
    """算法插件加载器"""
    
    def __init__(self):
        self._logger = get_logger('algorithm.plugin_loader')
        self._loaded_plugins: Dict[str, Type[AlgorithmInterface]] = {}
        self._plugin_modules: Dict[str, Any] = {}
        self._scan_cache: Dict[str, PluginScanResult] = {}
        
        self._logger.info("插件加载器初始化完成")
    
    def discover_plugins(self, scan_paths: List[str], 
                        recursive: bool = True,
                        use_cache: bool = True) -> PluginScanResult:
        """
        发现插件
        
        Args:
            scan_paths: 扫描路径列表
            recursive: 是否递归扫描
            use_cache: 是否使用缓存
            
        Returns:
            PluginScanResult: 发现结果
        """
        import time
        start_time = time.time()
        
        # 检查缓存
        cache_key = f"{sorted(scan_paths)}_{recursive}"
        if use_cache and cache_key in self._scan_cache:
            cached_result = self._scan_cache[cache_key]
            self._logger.debug(f"使用缓存的插件扫描结果: {len(cached_result.found_plugins)}个插件")
            return cached_result
        
        found_plugins = []
        errors = []
        
        self._logger.info(f"开始扫描插件 - 路径: {scan_paths}, 递归: {recursive}")
        
        for scan_path in scan_paths:
            try:
                plugins_in_path = self._scan_directory(scan_path, recursive)
                found_plugins.extend(plugins_in_path)
                self._logger.debug(f"路径 {scan_path} 发现 {len(plugins_in_path)} 个插件")
            except Exception as e:
                error_msg = f"扫描路径失败 {scan_path}: {e}"
                errors.append(error_msg)
                self._logger.error(error_msg)
        
        # 去重
        unique_plugins = []
        plugin_names = set()
        for plugin_class in found_plugins:
            plugin_name = plugin_class.__name__
            if plugin_name not in plugin_names:
                unique_plugins.append(plugin_class)
                plugin_names.add(plugin_name)
        
        duration = time.time() - start_time
        
        result = PluginScanResult(
            found_plugins=unique_plugins,
            scan_paths=scan_paths,
            errors=errors,
            scan_duration=duration
        )
        
        # 缓存结果
        self._scan_cache[cache_key] = result
        
        self._logger.info(f"插件扫描完成 - 发现 {len(unique_plugins)} 个唯一插件, 耗时 {duration:.3f}秒")
        if errors:
            self._logger.warning(f"扫描过程中发生 {len(errors)} 个错误")
        
        return result
    
    def _scan_directory(self, directory: str, recursive: bool) -> List[Type[AlgorithmInterface]]:
        """扫描目录中的插件"""
        plugins = []
        directory_path = Path(directory)
        
        if not directory_path.exists():
            raise PluginError(f"目录不存在: {directory}")
        
        if not directory_path.is_dir():
            raise PluginError(f"路径不是目录: {directory}")
        
        # 获取Python文件
        if recursive:
            python_files = list(directory_path.rglob("*.py"))
        else:
            python_files = list(directory_path.glob("*.py"))
        
        for py_file in python_files:
            if py_file.name.startswith('__'):
                continue  # 跳过__init__.py等
            
            try:
                plugins_in_file = self._load_plugins_from_file(py_file)
                plugins.extend(plugins_in_file)
            except Exception as e:
                self._logger.warning(f"加载文件插件失败 {py_file}: {e}")
        
        return plugins
    
    def _load_plugins_from_file(self, file_path: Path) -> List[Type[AlgorithmInterface]]:
        """从文件中加载插件"""
        plugins = []
        module_name = f"pktmask_plugin_{file_path.stem}"
        
        try:
            # 动态导入模块
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec is None or spec.loader is None:
                return plugins
            
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            
            # 缓存模块
            self._plugin_modules[str(file_path)] = module
            
            # 查找算法插件类
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if self._is_valid_plugin_class(obj):
                    plugins.append(obj)
                    self._loaded_plugins[obj.__name__] = obj
                    self._logger.debug(f"发现插件类: {obj.__name__} 在 {file_path}")
        
        except Exception as e:
            raise PluginError(f"加载插件文件失败 {file_path}: {e}", plugin_name=str(file_path))
        
        return plugins
    
    def _is_valid_plugin_class(self, cls: Type) -> bool:
        """检查是否为有效的插件类"""
        try:
            # 必须是AlgorithmInterface的子类
            if not issubclass(cls, AlgorithmInterface):
                return False
            
            # 不能是抽象类本身
            if cls is AlgorithmInterface:
                return False
            
            # 不能是抽象类
            if inspect.isabstract(cls):
                return False
            
            # 必须能够实例化（基本检查）
            try:
                # 尝试获取算法信息（不创建实例）
                if hasattr(cls, 'get_algorithm_info'):
                    return True
            except Exception:
                pass
            
            return True
            
        except Exception:
            return False
    
    def load_plugin_by_name(self, plugin_name: str, search_paths: Optional[List[str]] = None) -> Optional[Type[AlgorithmInterface]]:
        """
        根据名称加载特定插件
        
        Args:
            plugin_name: 插件名称
            search_paths: 搜索路径
            
        Returns:
            Optional[Type[AlgorithmInterface]]: 插件类，未找到返回None
        """
        # 首先检查已加载的插件
        if plugin_name in self._loaded_plugins:
            return self._loaded_plugins[plugin_name]
        
        # 动态搜索
        if search_paths:
            result = self.discover_plugins(search_paths, recursive=True, use_cache=False)
            for plugin_class in result.found_plugins:
                if plugin_class.__name__ == plugin_name:
                    return plugin_class
        
        self._logger.warning(f"未找到插件: {plugin_name}")
        return None
    
    def get_plugins_by_type(self, algorithm_type: AlgorithmType) -> List[Type[AlgorithmInterface]]:
        """
        根据类型获取插件
        
        Args:
            algorithm_type: 算法类型
            
        Returns:
            List[Type[AlgorithmInterface]]: 插件类列表
        """
        plugins = []
        for plugin_class in self._loaded_plugins.values():
            try:
                # 创建临时实例获取信息
                instance = plugin_class()
                info = instance.get_algorithm_info()
                if info.algorithm_type == algorithm_type:
                    plugins.append(plugin_class)
            except Exception as e:
                self._logger.warning(f"获取插件类型失败 {plugin_class.__name__}: {e}")
        
        return plugins
    
    def list_loaded_plugins(self) -> Dict[str, Dict[str, Any]]:
        """
        列出已加载的插件
        
        Returns:
            Dict[str, Dict[str, Any]]: 插件信息字典
        """
        plugin_info = {}
        
        for name, plugin_class in self._loaded_plugins.items():
            try:
                instance = plugin_class()
                info = instance.get_algorithm_info()
                
                plugin_info[name] = {
                    'class': plugin_class.__name__,
                    'module': plugin_class.__module__,
                    'algorithm_type': info.algorithm_type.value,
                    'version': info.version,
                    'author': info.author,
                    'description': info.description
                }
            except Exception as e:
                plugin_info[name] = {
                    'class': plugin_class.__name__,
                    'module': plugin_class.__module__,
                    'error': str(e)
                }
        
        return plugin_info
    
    def reload_plugin(self, plugin_name: str) -> bool:
        """
        重新加载插件
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            bool: 重新加载是否成功
        """
        if plugin_name not in self._loaded_plugins:
            self._logger.warning(f"插件未加载: {plugin_name}")
            return False
        
        try:
            plugin_class = self._loaded_plugins[plugin_name]
            module = plugin_class.__module__
            
            # 重新加载模块
            if module in sys.modules:
                importlib.reload(sys.modules[module])
                self._logger.info(f"插件重新加载成功: {plugin_name}")
                return True
            else:
                self._logger.warning(f"插件模块未找到: {module}")
                return False
                
        except Exception as e:
            self._logger.error(f"重新加载插件失败 {plugin_name}: {e}")
            return False
    
    def unload_plugin(self, plugin_name: str) -> bool:
        """
        卸载插件
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            bool: 卸载是否成功
        """
        if plugin_name in self._loaded_plugins:
            del self._loaded_plugins[plugin_name]
            self._logger.info(f"插件已卸载: {plugin_name}")
            return True
        
        return False
    
    def clear_cache(self):
        """清理扫描缓存"""
        self._scan_cache.clear()
        self._logger.debug("插件扫描缓存已清理")
    
    def get_plugin_statistics(self) -> Dict[str, Any]:
        """获取插件统计信息"""
        type_counts = {}
        
        for plugin_class in self._loaded_plugins.values():
            try:
                instance = plugin_class()
                info = instance.get_algorithm_info()
                algorithm_type = info.algorithm_type.value
                type_counts[algorithm_type] = type_counts.get(algorithm_type, 0) + 1
            except Exception:
                type_counts['unknown'] = type_counts.get('unknown', 0) + 1
        
        return {
            'total_plugins': len(self._loaded_plugins),
            'plugins_by_type': type_counts,
            'loaded_modules': len(self._plugin_modules),
            'cache_size': len(self._scan_cache)
        }


# 全局插件加载器实例
_plugin_loader: Optional[PluginLoader] = None


def get_plugin_loader() -> PluginLoader:
    """获取全局插件加载器实例"""
    global _plugin_loader
    if _plugin_loader is None:
        _plugin_loader = PluginLoader()
    return _plugin_loader


def discover_builtin_plugins() -> List[Type[AlgorithmInterface]]:
    """发现内置插件"""
    loader = get_plugin_loader()
    
    # 扫描当前包中的实现目录
    current_dir = Path(__file__).parent.parent
    scan_paths = [
        str(current_dir / "implementations"),
        str(current_dir / "builtin")
    ]
    
    # 过滤存在的路径
    existing_paths = [path for path in scan_paths if Path(path).exists()]
    
    if existing_paths:
        result = loader.discover_plugins(existing_paths, recursive=True)
        return result.found_plugins
    
    return [] 