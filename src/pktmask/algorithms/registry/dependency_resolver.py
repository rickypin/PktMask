#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
插件依赖管理系统 - Phase 6.4
自动解析和管理插件依赖关系
"""

import sys
import subprocess
import importlib
import pkg_resources
import threading
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import networkx as nx
from packaging import specifiers, version as pkg_version

from ..interfaces.algorithm_interface import (
    AlgorithmDependency, DependencyType, ValidationResult
)
from .plugin_discovery import PluginCandidate
from ...infrastructure.logging import get_logger
from ...common.exceptions import DependencyError, ValidationError


class DependencyStatus(Enum):
    """依赖状态枚举"""
    UNKNOWN = "unknown"
    SATISFIED = "satisfied"
    MISSING = "missing"
    VERSION_CONFLICT = "version_conflict"
    INSTALLING = "installing"
    FAILED = "failed"


@dataclass
class InstalledPackage:
    """已安装包信息"""
    name: str
    version: str
    location: str
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    install_time: Optional[datetime] = None


@dataclass
class DependencyNode:
    """依赖节点"""
    name: str
    version_spec: str
    dependency_type: DependencyType
    required_by: Set[str] = field(default_factory=set)
    status: DependencyStatus = DependencyStatus.UNKNOWN
    installed_version: Optional[str] = None
    error_message: Optional[str] = None
    children: Set[str] = field(default_factory=set)


@dataclass
class DependencyGraph:
    """依赖图"""
    nodes: Dict[str, DependencyNode] = field(default_factory=dict)
    graph: nx.DiGraph = field(default_factory=nx.DiGraph)
    
    def add_dependency(self, parent: str, dependency: AlgorithmDependency):
        """添加依赖关系"""
        dep_name = dependency.name
        
        # 添加或更新节点
        if dep_name not in self.nodes:
            self.nodes[dep_name] = DependencyNode(
                name=dep_name,
                version_spec=dependency.version_spec,
                dependency_type=dependency.dependency_type
            )
        
        self.nodes[dep_name].required_by.add(parent)
        
        # 添加到图中
        self.graph.add_edge(parent, dep_name)
    
    def has_cycles(self) -> bool:
        """检查是否有循环依赖"""
        return not nx.is_directed_acyclic_graph(self.graph)
    
    def get_install_order(self) -> List[str]:
        """获取安装顺序（拓扑排序）"""
        try:
            return list(nx.topological_sort(self.graph))
        except nx.NetworkXError:
            return []


class PackageInstaller:
    """包安装器"""
    
    def __init__(self):
        self._logger = get_logger('dependency.installer')
        self._install_lock = threading.RLock()
    
    def install_package(
        self,
        package_name: str,
        version_spec: Optional[str] = None,
        dry_run: bool = False
    ) -> bool:
        """
        安装包
        
        Args:
            package_name: 包名
            version_spec: 版本规范
            dry_run: 是否为试运行
            
        Returns:
            bool: 安装是否成功
        """
        with self._install_lock:
            try:
                # 构建安装命令
                install_spec = package_name
                if version_spec:
                    install_spec = f"{package_name}{version_spec}"
                
                self._logger.info(f"{'试运行' if dry_run else ''}安装包: {install_spec}")
                
                if dry_run:
                    # 试运行：检查包是否存在
                    return self._check_package_exists(package_name, version_spec)
                
                # 执行实际安装
                cmd = [sys.executable, "-m", "pip", "install", install_spec]
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=300  # 5分钟超时
                )
                
                if result.returncode == 0:
                    self._logger.info(f"成功安装包: {install_spec}")
                    return True
                else:
                    self._logger.error(f"安装包失败 {install_spec}: {result.stderr}")
                    return False
                    
            except subprocess.TimeoutExpired:
                self._logger.error(f"安装包超时: {install_spec}")
                return False
            except Exception as e:
                self._logger.error(f"安装包异常 {install_spec}: {e}")
                return False
    
    def uninstall_package(self, package_name: str, dry_run: bool = False) -> bool:
        """
        卸载包
        
        Args:
            package_name: 包名
            dry_run: 是否为试运行
            
        Returns:
            bool: 卸载是否成功
        """
        with self._install_lock:
            try:
                self._logger.info(f"{'试运行' if dry_run else ''}卸载包: {package_name}")
                
                if dry_run:
                    # 试运行：检查包是否已安装
                    return self._is_package_installed(package_name)
                
                # 执行实际卸载
                cmd = [sys.executable, "-m", "pip", "uninstall", "-y", package_name]
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                if result.returncode == 0:
                    self._logger.info(f"成功卸载包: {package_name}")
                    return True
                else:
                    self._logger.error(f"卸载包失败 {package_name}: {result.stderr}")
                    return False
                    
            except subprocess.TimeoutExpired:
                self._logger.error(f"卸载包超时: {package_name}")
                return False
            except Exception as e:
                self._logger.error(f"卸载包异常 {package_name}: {e}")
                return False
    
    def _check_package_exists(
        self,
        package_name: str,
        version_spec: Optional[str] = None
    ) -> bool:
        """检查包是否存在（在PyPI上）"""
        try:
            # 使用pip search的替代方案
            cmd = [sys.executable, "-m", "pip", "index", "versions", package_name]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            return result.returncode == 0
            
        except Exception:
            # 如果无法检查，假设存在
            return True
    
    def _is_package_installed(self, package_name: str) -> bool:
        """检查包是否已安装"""
        try:
            pkg_resources.get_distribution(package_name)
            return True
        except pkg_resources.DistributionNotFound:
            return False


class DependencyResolver:
    """依赖解析器"""
    
    def __init__(self):
        self._logger = get_logger('dependency.resolver')
        self._installer = PackageInstaller()
        self._installed_packages: Dict[str, InstalledPackage] = {}
        self._dependency_cache: Dict[str, List[AlgorithmDependency]] = {}
        self._lock = threading.RLock()
        
        # 初始化时扫描已安装包
        self._scan_installed_packages()
    
    def _scan_installed_packages(self):
        """扫描已安装的包"""
        try:
            installed_packages = [d for d in pkg_resources.working_set]
            
            for dist in installed_packages:
                package = InstalledPackage(
                    name=dist.project_name,
                    version=dist.version,
                    location=dist.location,
                    dependencies=[str(req) for req in dist.requires()],
                    metadata={
                        "platform": getattr(dist, 'platform', None),
                        "py_version": getattr(dist, 'py_version', None),
                    }
                )
                self._installed_packages[dist.project_name.lower()] = package
            
            self._logger.info(f"扫描到 {len(self._installed_packages)} 个已安装包")
            
        except Exception as e:
            self._logger.error(f"扫描已安装包失败: {e}")
    
    def check_dependencies(
        self,
        plugin_candidates: List[PluginCandidate]
    ) -> Dict[str, ValidationResult]:
        """
        检查插件依赖
        
        Args:
            plugin_candidates: 插件候选项列表
            
        Returns:
            Dict[str, ValidationResult]: 插件名到验证结果的映射
        """
        results = {}
        
        with self._lock:
            for candidate in plugin_candidates:
                if not candidate.algorithm_info:
                    continue
                
                plugin_name = candidate.algorithm_info.name
                result = ValidationResult(is_valid=True)
                
                try:
                    # 检查每个依赖
                    for dependency in candidate.algorithm_info.dependencies:
                        dep_result = self._check_single_dependency(dependency)
                        
                        if not dep_result.is_valid:
                            result.is_valid = False
                            result.errors.extend(dep_result.errors)
                        
                        result.warnings.extend(dep_result.warnings)
                    
                    # 检查Python版本兼容性
                    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
                    if not candidate.algorithm_info.is_compatible_with_python(python_version):
                        result.is_valid = False
                        result.add_error(f"Python版本不兼容，需要 {candidate.algorithm_info.min_python_version}+")
                    
                except Exception as e:
                    result.is_valid = False
                    result.add_error(f"检查依赖时发生错误: {e}")
                
                results[plugin_name] = result
        
        return results
    
    def _check_single_dependency(self, dependency: AlgorithmDependency) -> ValidationResult:
        """检查单个依赖"""
        result = ValidationResult(is_valid=True)
        
        package_name = dependency.name.lower()
        
        # 检查是否已安装
        if package_name not in self._installed_packages:
            if dependency.dependency_type == DependencyType.REQUIRED:
                result.add_error(f"缺少必需依赖: {dependency.name}")
            else:
                result.add_warning(f"缺少可选依赖: {dependency.name}")
            return result
        
        # 检查版本兼容性
        installed_package = self._installed_packages[package_name]
        if not dependency.is_version_compatible(installed_package.version):
            if dependency.dependency_type == DependencyType.REQUIRED:
                result.add_error(
                    f"依赖版本不兼容: {dependency.name} "
                    f"(已安装: {installed_package.version}, 需要: {dependency.version_spec})"
                )
            else:
                result.add_warning(
                    f"可选依赖版本不兼容: {dependency.name} "
                    f"(已安装: {installed_package.version}, 建议: {dependency.version_spec})"
                )
        
        return result
    
    def resolve_dependencies(
        self,
        plugin_candidates: List[PluginCandidate],
        auto_install: bool = False,
        dry_run: bool = False
    ) -> Tuple[DependencyGraph, Dict[str, ValidationResult]]:
        """
        解析依赖关系
        
        Args:
            plugin_candidates: 插件候选项列表
            auto_install: 是否自动安装缺失的依赖
            dry_run: 是否为试运行
            
        Returns:
            Tuple[DependencyGraph, Dict[str, ValidationResult]]: 依赖图和验证结果
        """
        graph = DependencyGraph()
        results = {}
        
        with self._lock:
            # 构建依赖图
            for candidate in plugin_candidates:
                if not candidate.algorithm_info:
                    continue
                
                plugin_name = candidate.algorithm_info.name
                
                # 添加插件依赖到图中
                for dependency in candidate.algorithm_info.dependencies:
                    graph.add_dependency(plugin_name, dependency)
            
            # 检查循环依赖
            if graph.has_cycles():
                error_result = ValidationResult(is_valid=False)
                error_result.add_error("检测到循环依赖")
                for plugin_name in [c.algorithm_info.name for c in plugin_candidates if c.algorithm_info]:
                    results[plugin_name] = error_result
                return graph, results
            
            # 解析每个依赖节点
            for node_name, node in graph.nodes.items():
                self._resolve_dependency_node(node)
            
            # 如果启用自动安装，安装缺失的依赖
            if auto_install:
                self._auto_install_dependencies(graph, dry_run)
            
            # 重新检查依赖状态
            dependency_results = self.check_dependencies(plugin_candidates)
            results.update(dependency_results)
        
        return graph, results
    
    def _resolve_dependency_node(self, node: DependencyNode):
        """解析单个依赖节点"""
        package_name = node.name.lower()
        
        # 检查是否已安装
        if package_name in self._installed_packages:
            installed_package = self._installed_packages[package_name]
            node.installed_version = installed_package.version
            
            # 检查版本兼容性
            try:
                spec_set = specifiers.SpecifierSet(node.version_spec)
                installed_version = pkg_version.parse(installed_package.version)
                
                if installed_version in spec_set:
                    node.status = DependencyStatus.SATISFIED
                else:
                    node.status = DependencyStatus.VERSION_CONFLICT
                    node.error_message = f"版本冲突: 已安装 {installed_package.version}, 需要 {node.version_spec}"
            except Exception as e:
                node.status = DependencyStatus.VERSION_CONFLICT
                node.error_message = f"版本检查失败: {e}"
        else:
            node.status = DependencyStatus.MISSING
            node.error_message = f"包未安装: {node.name}"
    
    def _auto_install_dependencies(self, graph: DependencyGraph, dry_run: bool):
        """自动安装依赖"""
        # 获取安装顺序
        install_order = graph.get_install_order()
        
        # 只安装缺失的必需依赖
        to_install = [
            node_name for node_name in install_order
            if (node_name in graph.nodes and 
                graph.nodes[node_name].status == DependencyStatus.MISSING and
                graph.nodes[node_name].dependency_type == DependencyType.REQUIRED)
        ]
        
        if not to_install:
            self._logger.info("没有需要安装的依赖")
            return
        
        self._logger.info(f"{'试运行' if dry_run else ''}安装 {len(to_install)} 个依赖: {to_install}")
        
        # 并行安装（限制并发数）
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_to_node = {}
            
            for node_name in to_install:
                node = graph.nodes[node_name]
                node.status = DependencyStatus.INSTALLING
                
                future = executor.submit(
                    self._installer.install_package,
                    node.name,
                    node.version_spec,
                    dry_run
                )
                future_to_node[future] = node
            
            # 等待安装完成
            for future in as_completed(future_to_node):
                node = future_to_node[future]
                try:
                    success = future.result()
                    if success:
                        node.status = DependencyStatus.SATISFIED
                        node.error_message = None
                        self._logger.info(f"成功{'模拟' if dry_run else ''}安装: {node.name}")
                    else:
                        node.status = DependencyStatus.FAILED
                        node.error_message = "安装失败"
                        self._logger.error(f"{'模拟' if dry_run else ''}安装失败: {node.name}")
                except Exception as e:
                    node.status = DependencyStatus.FAILED
                    node.error_message = f"安装异常: {e}"
                    self._logger.error(f"{'模拟' if dry_run else ''}安装异常 {node.name}: {e}")
        
        # 如果不是试运行，重新扫描已安装包
        if not dry_run:
            self._scan_installed_packages()
    
    def get_installed_packages(self) -> List[InstalledPackage]:
        """获取已安装包列表"""
        with self._lock:
            return list(self._installed_packages.values())
    
    def is_package_installed(self, package_name: str, version_spec: Optional[str] = None) -> bool:
        """检查包是否已安装"""
        with self._lock:
            package_name = package_name.lower()
            
            if package_name not in self._installed_packages:
                return False
            
            if version_spec is None:
                return True
            
            # 检查版本
            try:
                installed_package = self._installed_packages[package_name]
                spec_set = specifiers.SpecifierSet(version_spec)
                installed_version = pkg_version.parse(installed_package.version)
                return installed_version in spec_set
            except Exception:
                return False
    
    def get_dependency_info(self, package_name: str) -> Optional[InstalledPackage]:
        """获取依赖信息"""
        with self._lock:
            return self._installed_packages.get(package_name.lower())
    
    def get_resolver_stats(self) -> Dict[str, Any]:
        """获取解析器统计信息"""
        with self._lock:
            return {
                "installed_packages": len(self._installed_packages),
                "cache_size": len(self._dependency_cache),
                "packages_by_location": {},
                "recent_packages": []
            }
    
    def cleanup(self):
        """清理资源"""
        with self._lock:
            self._dependency_cache.clear()
        self._logger.info("依赖解析器资源已清理")


# 全局依赖解析器实例
_dependency_resolver: Optional[DependencyResolver] = None


def get_dependency_resolver() -> DependencyResolver:
    """获取全局依赖解析器实例"""
    global _dependency_resolver
    if _dependency_resolver is None:
        _dependency_resolver = DependencyResolver()
    return _dependency_resolver 