#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
插件发现引擎 - Phase 6.4
自动扫描和识别插件，支持多种插件来源
"""

import os
import sys
import importlib
import importlib.util
import inspect
import threading
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Union, Type, Callable
from dataclasses import dataclass, field
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import zipfile
import hashlib
import json

from ..interfaces.algorithm_interface import (
    AlgorithmInterface, AlgorithmInfo, AlgorithmType, AlgorithmDependency,
    DependencyType, ValidationResult
)
from ...infrastructure.logging import get_logger
from ...common.exceptions import PluginError, ValidationError


@dataclass
class PluginSource:
    """插件源信息"""
    path: Path
    source_type: str  # directory, zip, git, pypi, url
    name: str
    priority: int = 0
    enabled: bool = True
    trusted: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    last_scan: Optional[datetime] = None
    scan_count: int = 0


@dataclass
class PluginCandidate:
    """插件候选项"""
    module_path: str
    file_path: Path
    plugin_class: Optional[Type] = None
    algorithm_info: Optional[AlgorithmInfo] = None
    source: Optional[PluginSource] = None
    validation_errors: List[str] = field(default_factory=list)
    is_valid: bool = False
    discovered_at: datetime = field(default_factory=datetime.now)
    file_hash: Optional[str] = None


class PluginScanner:
    """插件扫描器"""
    
    def __init__(self):
        self._logger = get_logger('plugin.scanner')
        self._supported_extensions = {'.py', '.pyd', '.so', '.dll'}
        self._excluded_patterns = {
            '__pycache__', '*.pyc', '*.pyo', '.git', '.svn',
            'test_*', '*_test.py', 'tests', 'docs'
        }
    
    def scan_directory(self, directory: Path, recursive: bool = True) -> List[PluginCandidate]:
        """扫描目录中的插件"""
        candidates = []
        
        if not directory.exists() or not directory.is_dir():
            self._logger.warning(f"目录不存在或不是目录: {directory}")
            return candidates
        
        try:
            # 获取Python文件
            if recursive:
                python_files = list(directory.rglob("*.py"))
            else:
                python_files = list(directory.glob("*.py"))
            
            # 过滤掉排除的文件
            python_files = [f for f in python_files if self._should_include_file(f)]
            
            self._logger.info(f"在 {directory} 中发现 {len(python_files)} 个Python文件")
            
            # 并行扫描文件
            with ThreadPoolExecutor(max_workers=4) as executor:
                future_to_file = {
                    executor.submit(self._scan_python_file, f): f 
                    for f in python_files
                }
                
                for future in as_completed(future_to_file):
                    file_path = future_to_file[future]
                    try:
                        candidate = future.result()
                        if candidate:
                            candidates.append(candidate)
                    except Exception as e:
                        self._logger.error(f"扫描文件失败 {file_path}: {e}")
            
            self._logger.info(f"在 {directory} 中发现 {len(candidates)} 个有效插件候选项")
            
        except Exception as e:
            self._logger.error(f"扫描目录失败 {directory}: {e}")
        
        return candidates
    
    def _should_include_file(self, file_path: Path) -> bool:
        """检查文件是否应该包含在扫描中"""
        # 检查文件扩展名
        if file_path.suffix not in self._supported_extensions:
            return False
        
        # 检查排除模式
        path_str = str(file_path)
        for pattern in self._excluded_patterns:
            if pattern.startswith('*') and path_str.endswith(pattern[1:]):
                return False
            elif pattern.endswith('*') and pattern[:-1] in path_str:
                return False
            elif pattern in path_str:
                return False
        
        return True
    
    def _scan_python_file(self, file_path: Path) -> Optional[PluginCandidate]:
        """扫描单个Python文件"""
        try:
            # 计算文件哈希
            file_hash = self._calculate_file_hash(file_path)
            
            # 生成模块路径
            module_path = self._generate_module_path(file_path)
            
            # 创建候选项
            candidate = PluginCandidate(
                module_path=module_path,
                file_path=file_path,
                file_hash=file_hash
            )
            
            # 尝试加载和验证模块
            self._load_and_validate_candidate(candidate)
            
            return candidate if candidate.is_valid else None
            
        except Exception as e:
            self._logger.error(f"扫描文件失败 {file_path}: {e}")
            return None
    
    def _load_and_validate_candidate(self, candidate: PluginCandidate):
        """加载和验证插件候选项"""
        try:
            # 动态导入模块
            spec = importlib.util.spec_from_file_location(
                candidate.module_path, 
                candidate.file_path
            )
            
            if spec is None or spec.loader is None:
                candidate.validation_errors.append("无法创建模块规范")
                return
            
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # 查找算法接口实现
            algorithm_classes = self._find_algorithm_classes(module)
            
            if not algorithm_classes:
                candidate.validation_errors.append("未找到AlgorithmInterface实现")
                return
            
            if len(algorithm_classes) > 1:
                candidate.validation_errors.append("找到多个AlgorithmInterface实现")
                return
            
            # 验证算法类
            algorithm_class = algorithm_classes[0]
            self._validate_algorithm_class(candidate, algorithm_class)
            
        except Exception as e:
            candidate.validation_errors.append(f"加载模块失败: {e}")
    
    def _find_algorithm_classes(self, module) -> List[Type]:
        """查找模块中的算法接口实现"""
        algorithm_classes = []
        
        for name in dir(module):
            try:
                obj = getattr(module, name)
                if (inspect.isclass(obj) and 
                    issubclass(obj, AlgorithmInterface) and 
                    obj != AlgorithmInterface):
                    algorithm_classes.append(obj)
            except Exception:
                continue
        
        return algorithm_classes
    
    def _validate_algorithm_class(self, candidate: PluginCandidate, algorithm_class: Type):
        """验证算法类"""
        try:
            # 检查类是否可实例化
            if inspect.isabstract(algorithm_class):
                candidate.validation_errors.append("算法类是抽象类，无法实例化")
                return
            
            # 尝试创建实例
            algorithm_instance = algorithm_class()
            
            # 获取算法信息
            algorithm_info = algorithm_instance.get_algorithm_info()
            
            # 验证算法信息
            if not algorithm_info.name:
                candidate.validation_errors.append("算法名称不能为空")
                return
            
            if not algorithm_info.version:
                candidate.validation_errors.append("算法版本不能为空")
                return
            
            # 设置候选项信息
            candidate.plugin_class = algorithm_class
            candidate.algorithm_info = algorithm_info
            candidate.is_valid = True
            
            self._logger.debug(f"验证算法类成功: {algorithm_info.name} v{algorithm_info.version}")
            
        except Exception as e:
            candidate.validation_errors.append(f"验证算法类失败: {e}")
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """计算文件哈希"""
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
                return hashlib.sha256(content).hexdigest()
        except Exception:
            return ""
    
    def _generate_module_path(self, file_path: Path) -> str:
        """生成模块路径"""
        # 将文件路径转换为模块路径
        module_path = str(file_path.with_suffix(''))
        module_path = module_path.replace(os.sep, '.')
        
        # 移除前导点
        while module_path.startswith('.'):
            module_path = module_path[1:]
        
        return module_path


class PluginDiscoveryEngine:
    """插件发现引擎"""
    
    def __init__(self):
        self._logger = get_logger('plugin.discovery')
        self._scanner = PluginScanner()
        self._sources: Dict[str, PluginSource] = {}
        self._discovered_plugins: Dict[str, PluginCandidate] = {}
        self._discovery_callbacks: List[Callable[[PluginCandidate], None]] = []
        self._lock = threading.RLock()
        
        # 默认插件源
        self._add_default_sources()
    
    def _add_default_sources(self):
        """添加默认插件源"""
        # 内置插件目录
        builtin_dir = Path(__file__).parent.parent / "implementations"
        if builtin_dir.exists():
            self.add_source(PluginSource(
                path=builtin_dir,
                source_type="directory",
                name="builtin",
                priority=10,
                trusted=True
            ))
        
        # 用户插件目录
        user_plugins_dir = Path.home() / ".pktmask" / "plugins"
        user_plugins_dir.mkdir(parents=True, exist_ok=True)
        self.add_source(PluginSource(
            path=user_plugins_dir,
            source_type="directory",
            name="user",
            priority=5,
            trusted=False
        ))
        
        # 当前工作目录的plugins子目录
        local_plugins_dir = Path.cwd() / "plugins"
        if local_plugins_dir.exists():
            self.add_source(PluginSource(
                path=local_plugins_dir,
                source_type="directory",
                name="local",
                priority=1,
                trusted=False
            ))
    
    def add_source(self, source: PluginSource):
        """添加插件源"""
        with self._lock:
            self._sources[source.name] = source
            self._logger.info(f"添加插件源: {source.name} ({source.path})")
    
    def remove_source(self, source_name: str) -> bool:
        """移除插件源"""
        with self._lock:
            if source_name in self._sources:
                del self._sources[source_name]
                self._logger.info(f"移除插件源: {source_name}")
                return True
            return False
    
    def get_sources(self) -> List[PluginSource]:
        """获取所有插件源"""
        with self._lock:
            return list(self._sources.values())
    
    def discover_plugins(self, force_rescan: bool = False) -> List[PluginCandidate]:
        """发现插件"""
        discovered = []
        
        with self._lock:
            # 按优先级排序源
            sources = sorted(self._sources.values(), key=lambda s: s.priority, reverse=True)
            
            for source in sources:
                if not source.enabled:
                    continue
                
                try:
                    self._logger.info(f"扫描插件源: {source.name}")
                    
                    # 扫描插件源
                    candidates = self._scan_source(source, force_rescan)
                    
                    # 更新源信息
                    source.last_scan = datetime.now()
                    source.scan_count += 1
                    
                    # 处理发现的插件
                    for candidate in candidates:
                        candidate.source = source
                        plugin_key = f"{source.name}:{candidate.module_path}"
                        
                        # 检查是否已存在
                        if plugin_key in self._discovered_plugins and not force_rescan:
                            existing = self._discovered_plugins[plugin_key]
                            if existing.file_hash == candidate.file_hash:
                                discovered.append(existing)
                                continue
                        
                        # 添加新插件或更新已有插件
                        self._discovered_plugins[plugin_key] = candidate
                        discovered.append(candidate)
                        
                        # 触发发现回调
                        self._trigger_discovery_callbacks(candidate)
                    
                    self._logger.info(f"在源 {source.name} 中发现 {len(candidates)} 个插件")
                    
                except Exception as e:
                    self._logger.error(f"扫描插件源失败 {source.name}: {e}")
        
        self._logger.info(f"总共发现 {len(discovered)} 个插件")
        return discovered
    
    def _scan_source(self, source: PluginSource, force_rescan: bool) -> List[PluginCandidate]:
        """扫描单个插件源"""
        candidates = []
        
        if source.source_type == "directory":
            candidates = self._scanner.scan_directory(source.path, recursive=True)
        else:
            self._logger.warning(f"不支持的插件源类型: {source.source_type}")
        
        return candidates
    
    def get_discovered_plugins(self) -> List[PluginCandidate]:
        """获取已发现的插件"""
        with self._lock:
            return list(self._discovered_plugins.values())
    
    def find_plugin_by_name(self, name: str) -> Optional[PluginCandidate]:
        """根据名称查找插件"""
        with self._lock:
            for candidate in self._discovered_plugins.values():
                if candidate.algorithm_info and candidate.algorithm_info.name == name:
                    return candidate
            return None
    
    def find_plugins_by_type(self, algorithm_type: AlgorithmType) -> List[PluginCandidate]:
        """根据类型查找插件"""
        plugins = []
        with self._lock:
            for candidate in self._discovered_plugins.values():
                if (candidate.algorithm_info and 
                    candidate.algorithm_info.algorithm_type == algorithm_type):
                    plugins.append(candidate)
        return plugins
    
    def add_discovery_callback(self, callback: Callable[[PluginCandidate], None]):
        """添加插件发现回调"""
        self._discovery_callbacks.append(callback)
    
    def remove_discovery_callback(self, callback: Callable[[PluginCandidate], None]):
        """移除插件发现回调"""
        if callback in self._discovery_callbacks:
            self._discovery_callbacks.remove(callback)
    
    def _trigger_discovery_callbacks(self, candidate: PluginCandidate):
        """触发插件发现回调"""
        for callback in self._discovery_callbacks:
            try:
                callback(candidate)
            except Exception as e:
                self._logger.error(f"插件发现回调失败: {e}")
    
    def get_discovery_stats(self) -> Dict[str, Any]:
        """获取发现统计信息"""
        with self._lock:
            stats = {
                "total_sources": len(self._sources),
                "enabled_sources": len([s for s in self._sources.values() if s.enabled]),
                "total_plugins": len(self._discovered_plugins),
                "valid_plugins": len([p for p in self._discovered_plugins.values() if p.is_valid]),
                "plugins_by_type": {},
                "plugins_by_source": {},
                "last_discovery": None
            }
            
            # 按类型统计
            for candidate in self._discovered_plugins.values():
                if candidate.algorithm_info:
                    algo_type = candidate.algorithm_info.algorithm_type.value
                    stats["plugins_by_type"][algo_type] = stats["plugins_by_type"].get(algo_type, 0) + 1
            
            # 按源统计
            for candidate in self._discovered_plugins.values():
                if candidate.source:
                    source_name = candidate.source.name
                    stats["plugins_by_source"][source_name] = stats["plugins_by_source"].get(source_name, 0) + 1
            
            # 最近发现时间
            if self._discovered_plugins:
                latest_discovery = max(
                    (p.discovered_at for p in self._discovered_plugins.values()),
                    default=None
                )
                if latest_discovery:
                    stats["last_discovery"] = latest_discovery.isoformat()
            
            return stats
    
    def cleanup(self):
        """清理资源"""
        with self._lock:
            self._discovered_plugins.clear()
            self._discovery_callbacks.clear()
        self._logger.info("插件发现引擎资源已清理")


# 全局插件发现引擎实例
_discovery_engine: Optional[PluginDiscoveryEngine] = None


def get_plugin_discovery_engine() -> PluginDiscoveryEngine:
    """获取全局插件发现引擎实例"""
    global _discovery_engine
    if _discovery_engine is None:
        _discovery_engine = PluginDiscoveryEngine()
    return _discovery_engine 