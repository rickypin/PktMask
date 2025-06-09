#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
插件沙箱系统 - Phase 6.4
提供插件隔离执行环境，确保安全性和稳定性
"""

import os
import sys
import threading
import multiprocessing
import tempfile
import shutil
import signal
import time
import traceback
import resource
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Type, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, TimeoutError, Future
import psutil

from ..interfaces.algorithm_interface import AlgorithmInterface, AlgorithmInfo
from .plugin_discovery import PluginCandidate
from ...infrastructure.logging import get_logger
from ...common.exceptions import PluginError, SecurityError


class SandboxLevel(Enum):
    """沙箱安全级别"""
    NONE = "none"           # 无限制
    BASIC = "basic"         # 基础限制
    RESTRICTED = "restricted"  # 受限模式
    ISOLATED = "isolated"   # 完全隔离


class ExecutionMode(Enum):
    """执行模式"""
    DIRECT = "direct"       # 直接执行
    THREAD = "thread"       # 线程执行
    PROCESS = "process"     # 进程执行


@dataclass
class ResourceLimits:
    """资源限制"""
    max_memory_mb: int = 512         # 最大内存使用（MB）
    max_cpu_percent: float = 50.0    # 最大CPU使用率（%）
    max_execution_time: int = 300    # 最大执行时间（秒）
    max_file_descriptors: int = 100  # 最大文件描述符数量
    max_threads: int = 10            # 最大线程数量
    max_disk_usage_mb: int = 100     # 最大磁盘使用（MB）
    allow_network: bool = False      # 是否允许网络访问
    allow_subprocess: bool = False   # 是否允许子进程


@dataclass
class SandboxConfig:
    """沙箱配置"""
    level: SandboxLevel = SandboxLevel.BASIC
    execution_mode: ExecutionMode = ExecutionMode.THREAD
    resource_limits: ResourceLimits = field(default_factory=ResourceLimits)
    allowed_modules: List[str] = field(default_factory=list)
    blocked_modules: List[str] = field(default_factory=lambda: [
        'subprocess', 'os', 'sys', 'shutil', 'socket',
        'urllib', 'requests', 'http', 'ftplib', 'smtplib'
    ])
    allowed_paths: List[str] = field(default_factory=list)
    blocked_paths: List[str] = field(default_factory=lambda: [
        '/etc', '/usr', '/bin', '/sbin', '/var'
    ])
    temp_directory: Optional[str] = None
    cleanup_on_exit: bool = True


@dataclass
class ExecutionResult:
    """执行结果"""
    success: bool
    result: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0
    peak_memory_mb: float = 0.0
    cpu_usage_percent: float = 0.0
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ResourceMonitor:
    """资源监控器"""
    
    def __init__(self, limits: ResourceLimits):
        self._limits = limits
        self._logger = get_logger('sandbox.monitor')
        self._monitoring = False
        self._start_time = None
        self._peak_memory = 0.0
        self._total_cpu_time = 0.0
        self._process = psutil.Process()
        self._initial_memory = self._process.memory_info().rss / 1024 / 1024
    
    def start_monitoring(self):
        """开始监控"""
        self._monitoring = True
        self._start_time = time.time()
        self._peak_memory = self._initial_memory
        self._total_cpu_time = 0.0
    
    def stop_monitoring(self) -> Dict[str, float]:
        """停止监控并返回统计信息"""
        self._monitoring = False
        
        if self._start_time is None:
            return {}
        
        execution_time = time.time() - self._start_time
        
        return {
            "execution_time": execution_time,
            "peak_memory_mb": self._peak_memory,
            "cpu_usage_percent": self._total_cpu_time / execution_time * 100 if execution_time > 0 else 0
        }
    
    def check_limits(self) -> List[str]:
        """检查资源限制"""
        violations = []
        
        if not self._monitoring or self._start_time is None:
            return violations
        
        try:
            # 检查执行时间
            execution_time = time.time() - self._start_time
            if execution_time > self._limits.max_execution_time:
                violations.append(f"执行时间超限: {execution_time:.1f}s > {self._limits.max_execution_time}s")
            
            # 检查内存使用
            current_memory = self._process.memory_info().rss / 1024 / 1024
            memory_usage = current_memory - self._initial_memory
            if memory_usage > self._limits.max_memory_mb:
                violations.append(f"内存使用超限: {memory_usage:.1f}MB > {self._limits.max_memory_mb}MB")
            
            self._peak_memory = max(self._peak_memory, memory_usage)
            
            # 检查CPU使用率
            cpu_percent = self._process.cpu_percent()
            if cpu_percent > self._limits.max_cpu_percent:
                violations.append(f"CPU使用率超限: {cpu_percent:.1f}% > {self._limits.max_cpu_percent}%")
            
            # 检查线程数量
            if hasattr(self._process, 'num_threads'):
                thread_count = self._process.num_threads()
                if thread_count > self._limits.max_threads:
                    violations.append(f"线程数量超限: {thread_count} > {self._limits.max_threads}")
            
            # 检查文件描述符
            if hasattr(self._process, 'num_fds'):
                fd_count = self._process.num_fds()
                if fd_count > self._limits.max_file_descriptors:
                    violations.append(f"文件描述符数量超限: {fd_count} > {self._limits.max_file_descriptors}")
        
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        except Exception as e:
            self._logger.warning(f"检查资源限制时发生错误: {e}")
        
        return violations


class SecurityManager:
    """安全管理器"""
    
    def __init__(self, config: SandboxConfig):
        self._config = config
        self._logger = get_logger('sandbox.security')
        self._original_import = None
        self._original_open = None
        self._blocked_operations = []
    
    @contextmanager
    def secure_environment(self):
        """安全环境上下文管理器"""
        if self._config.level == SandboxLevel.NONE:
            yield
            return
        
        # 保存原始函数
        self._original_import = __builtins__['__import__']
        self._original_open = open
        
        try:
            # 应用安全限制
            self._apply_security_restrictions()
            yield
        finally:
            # 恢复原始函数
            self._restore_original_functions()
    
    def _apply_security_restrictions(self):
        """应用安全限制"""
        if self._config.level in [SandboxLevel.RESTRICTED, SandboxLevel.ISOLATED]:
            # 限制导入
            __builtins__['__import__'] = self._secure_import
            
            # 限制文件操作
            __builtins__['open'] = self._secure_open
            
            # 设置资源限制
            self._set_resource_limits()
    
    def _restore_original_functions(self):
        """恢复原始函数"""
        if self._original_import:
            __builtins__['__import__'] = self._original_import
        
        if self._original_open:
            __builtins__['open'] = self._original_open
    
    def _secure_import(self, name, *args, **kwargs):
        """安全的导入函数"""
        # 检查模块是否被阻止
        if name in self._config.blocked_modules:
            raise SecurityError(f"模块 '{name}' 被禁止导入")
        
        # 检查模块是否在允许列表中（如果有的话）
        if self._config.allowed_modules and name not in self._config.allowed_modules:
            raise SecurityError(f"模块 '{name}' 不在允许列表中")
        
        # 使用原始导入函数
        return self._original_import(name, *args, **kwargs)
    
    def _secure_open(self, file, mode='r', *args, **kwargs):
        """安全的文件打开函数"""
        file_path = Path(file).resolve()
        
        # 检查路径是否被阻止
        for blocked_path in self._config.blocked_paths:
            if str(file_path).startswith(blocked_path):
                raise SecurityError(f"路径 '{file_path}' 被禁止访问")
        
        # 检查路径是否在允许列表中（如果有的话）
        if self._config.allowed_paths:
            allowed = False
            for allowed_path in self._config.allowed_paths:
                if str(file_path).startswith(allowed_path):
                    allowed = True
                    break
            
            if not allowed:
                raise SecurityError(f"路径 '{file_path}' 不在允许列表中")
        
        # 使用原始打开函数
        return self._original_open(file, mode, *args, **kwargs)
    
    def _set_resource_limits(self):
        """设置系统资源限制"""
        try:
            limits = self._config.resource_limits
            
            # 设置内存限制
            if hasattr(resource, 'RLIMIT_AS'):
                memory_limit = limits.max_memory_mb * 1024 * 1024
                resource.setrlimit(resource.RLIMIT_AS, (memory_limit, memory_limit))
            
            # 设置CPU时间限制
            if hasattr(resource, 'RLIMIT_CPU'):
                resource.setrlimit(resource.RLIMIT_CPU, (limits.max_execution_time, limits.max_execution_time))
            
            # 设置文件描述符限制
            if hasattr(resource, 'RLIMIT_NOFILE'):
                resource.setrlimit(resource.RLIMIT_NOFILE, (limits.max_file_descriptors, limits.max_file_descriptors))
        
        except Exception as e:
            self._logger.warning(f"设置资源限制失败: {e}")


class PluginSandbox:
    """插件沙箱"""
    
    def __init__(self, config: SandboxConfig):
        self._config = config
        self._logger = get_logger('sandbox.executor')
        self._security_manager = SecurityManager(config)
        self._temp_dir = None
        self._active_executions: Dict[str, Future] = {}
        self._execution_lock = threading.RLock()
        
        # 创建临时目录
        self._setup_temp_directory()
    
    def _setup_temp_directory(self):
        """设置临时目录"""
        if self._config.temp_directory:
            self._temp_dir = Path(self._config.temp_directory)
            self._temp_dir.mkdir(parents=True, exist_ok=True)
        else:
            self._temp_dir = Path(tempfile.mkdtemp(prefix="pktmask_sandbox_"))
        
        self._logger.info(f"沙箱临时目录: {self._temp_dir}")
    
    def execute_plugin(
        self,
        plugin_instance: AlgorithmInterface,
        method_name: str,
        *args,
        **kwargs
    ) -> ExecutionResult:
        """
        在沙箱中执行插件方法
        
        Args:
            plugin_instance: 插件实例
            method_name: 方法名
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            ExecutionResult: 执行结果
        """
        execution_id = f"{id(plugin_instance)}_{method_name}_{time.time()}"
        
        with self._execution_lock:
            if self._config.execution_mode == ExecutionMode.DIRECT:
                return self._execute_direct(plugin_instance, method_name, *args, **kwargs)
            elif self._config.execution_mode == ExecutionMode.THREAD:
                return self._execute_in_thread(plugin_instance, method_name, *args, **kwargs)
            elif self._config.execution_mode == ExecutionMode.PROCESS:
                return self._execute_in_process(plugin_instance, method_name, *args, **kwargs)
            else:
                raise ValueError(f"不支持的执行模式: {self._config.execution_mode}")
    
    def _execute_direct(
        self,
        plugin_instance: AlgorithmInterface,
        method_name: str,
        *args,
        **kwargs
    ) -> ExecutionResult:
        """直接执行"""
        monitor = ResourceMonitor(self._config.resource_limits)
        result = ExecutionResult(success=False)
        
        try:
            with self._security_manager.secure_environment():
                monitor.start_monitoring()
                start_time = time.time()
                
                # 获取并执行方法
                method = getattr(plugin_instance, method_name)
                if not callable(method):
                    raise ValueError(f"'{method_name}' 不是可调用的方法")
                
                # 定期检查资源限制
                def resource_checker():
                    while monitor._monitoring:
                        violations = monitor.check_limits()
                        if violations:
                            raise ResourceError(f"资源限制违规: {', '.join(violations)}")
                        time.sleep(0.1)
                
                # 启动资源监控线程
                monitor_thread = None
                if self._config.level != SandboxLevel.NONE:
                    monitor_thread = threading.Thread(target=resource_checker, daemon=True)
                    monitor_thread.start()
                
                try:
                    # 执行方法
                    result.result = method(*args, **kwargs)
                    result.success = True
                except Exception as e:
                    result.error = f"{type(e).__name__}: {str(e)}"
                    self._logger.error(f"插件执行失败: {result.error}")
                finally:
                    # 停止监控
                    stats = monitor.stop_monitoring()
                    result.execution_time = stats.get("execution_time", 0.0)
                    result.peak_memory_mb = stats.get("peak_memory_mb", 0.0)
                    result.cpu_usage_percent = stats.get("cpu_usage_percent", 0.0)
        
        except Exception as e:
            result.error = f"沙箱执行异常: {e}"
            self._logger.error(f"沙箱执行失败: {result.error}")
        
        return result
    
    def _execute_in_thread(
        self,
        plugin_instance: AlgorithmInterface,
        method_name: str,
        *args,
        **kwargs
    ) -> ExecutionResult:
        """在线程中执行"""
        result = ExecutionResult(success=False)
        
        def thread_worker():
            return self._execute_direct(plugin_instance, method_name, *args, **kwargs)
        
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(thread_worker)
                
                try:
                    result = future.result(timeout=self._config.resource_limits.max_execution_time)
                except TimeoutError:
                    result.error = f"执行超时 ({self._config.resource_limits.max_execution_time}s)"
                    self._logger.error(f"线程执行超时: {method_name}")
        
        except Exception as e:
            result.error = f"线程执行异常: {e}"
            self._logger.error(f"线程执行失败: {result.error}")
        
        return result
    
    def _execute_in_process(
        self,
        plugin_instance: AlgorithmInterface,
        method_name: str,
        *args,
        **kwargs
    ) -> ExecutionResult:
        """在独立进程中执行"""
        result = ExecutionResult(success=False)
        
        def process_worker(plugin_class, method_name, args, kwargs):
            """进程工作函数"""
            try:
                # 在子进程中重新创建插件实例
                instance = plugin_class()
                method = getattr(instance, method_name)
                return method(*args, **kwargs)
            except Exception as e:
                raise e
        
        try:
            with ProcessPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    process_worker,
                    type(plugin_instance),
                    method_name,
                    args,
                    kwargs
                )
                
                try:
                    start_time = time.time()
                    result.result = future.result(timeout=self._config.resource_limits.max_execution_time)
                    result.execution_time = time.time() - start_time
                    result.success = True
                except TimeoutError:
                    result.error = f"执行超时 ({self._config.resource_limits.max_execution_time}s)"
                    self._logger.error(f"进程执行超时: {method_name}")
                except Exception as e:
                    result.error = f"进程执行异常: {e}"
                    self._logger.error(f"进程执行失败: {result.error}")
        
        except Exception as e:
            result.error = f"进程创建异常: {e}"
            self._logger.error(f"进程创建失败: {result.error}")
        
        return result
    
    def get_temp_directory(self) -> Path:
        """获取临时目录"""
        return self._temp_dir
    
    def cleanup(self):
        """清理沙箱资源"""
        try:
            # 等待所有执行完成
            with self._execution_lock:
                for execution_id, future in self._active_executions.items():
                    try:
                        future.cancel()
                    except Exception:
                        pass
                self._active_executions.clear()
            
            # 清理临时目录
            if self._config.cleanup_on_exit and self._temp_dir and self._temp_dir.exists():
                shutil.rmtree(self._temp_dir, ignore_errors=True)
                self._logger.info(f"清理沙箱临时目录: {self._temp_dir}")
        
        except Exception as e:
            self._logger.error(f"清理沙箱资源失败: {e}")


class SandboxManager:
    """沙箱管理器"""
    
    def __init__(self):
        self._logger = get_logger('sandbox.manager')
        self._sandboxes: Dict[str, PluginSandbox] = {}
        self._configs: Dict[str, SandboxConfig] = {}
        self._lock = threading.RLock()
        
        # 默认配置
        self._default_configs = {
            SandboxLevel.NONE.value: SandboxConfig(
                level=SandboxLevel.NONE,
                execution_mode=ExecutionMode.DIRECT
            ),
            SandboxLevel.BASIC.value: SandboxConfig(
                level=SandboxLevel.BASIC,
                execution_mode=ExecutionMode.THREAD,
                resource_limits=ResourceLimits(
                    max_memory_mb=256,
                    max_execution_time=120,
                    max_cpu_percent=30.0
                )
            ),
            SandboxLevel.RESTRICTED.value: SandboxConfig(
                level=SandboxLevel.RESTRICTED,
                execution_mode=ExecutionMode.THREAD,
                resource_limits=ResourceLimits(
                    max_memory_mb=128,
                    max_execution_time=60,
                    max_cpu_percent=20.0,
                    allow_network=False,
                    allow_subprocess=False
                )
            ),
            SandboxLevel.ISOLATED.value: SandboxConfig(
                level=SandboxLevel.ISOLATED,
                execution_mode=ExecutionMode.PROCESS,
                resource_limits=ResourceLimits(
                    max_memory_mb=64,
                    max_execution_time=30,
                    max_cpu_percent=10.0,
                    allow_network=False,
                    allow_subprocess=False
                )
            )
        }
    
    def create_sandbox(
        self,
        sandbox_id: str,
        config: Optional[SandboxConfig] = None
    ) -> PluginSandbox:
        """
        创建沙箱
        
        Args:
            sandbox_id: 沙箱ID
            config: 沙箱配置
            
        Returns:
            PluginSandbox: 沙箱实例
        """
        with self._lock:
            if sandbox_id in self._sandboxes:
                return self._sandboxes[sandbox_id]
            
            if config is None:
                config = self._default_configs[SandboxLevel.BASIC.value]
            
            sandbox = PluginSandbox(config)
            self._sandboxes[sandbox_id] = sandbox
            self._configs[sandbox_id] = config
            
            self._logger.info(f"创建沙箱: {sandbox_id} (级别: {config.level.value})")
            return sandbox
    
    def get_sandbox(self, sandbox_id: str) -> Optional[PluginSandbox]:
        """获取沙箱"""
        with self._lock:
            return self._sandboxes.get(sandbox_id)
    
    def remove_sandbox(self, sandbox_id: str) -> bool:
        """移除沙箱"""
        with self._lock:
            if sandbox_id in self._sandboxes:
                sandbox = self._sandboxes[sandbox_id]
                sandbox.cleanup()
                del self._sandboxes[sandbox_id]
                del self._configs[sandbox_id]
                self._logger.info(f"移除沙箱: {sandbox_id}")
                return True
            return False
    
    def list_sandboxes(self) -> List[Tuple[str, SandboxConfig]]:
        """列出所有沙箱"""
        with self._lock:
            return [(sid, self._configs[sid]) for sid in self._sandboxes.keys()]
    
    def execute_in_sandbox(
        self,
        sandbox_id: str,
        plugin_instance: AlgorithmInterface,
        method_name: str,
        *args,
        **kwargs
    ) -> ExecutionResult:
        """在指定沙箱中执行插件方法"""
        sandbox = self.get_sandbox(sandbox_id)
        if sandbox is None:
            return ExecutionResult(
                success=False,
                error=f"沙箱不存在: {sandbox_id}"
            )
        
        return sandbox.execute_plugin(plugin_instance, method_name, *args, **kwargs)
    
    def get_default_config(self, level: SandboxLevel) -> SandboxConfig:
        """获取默认配置"""
        return self._default_configs.get(level.value, self._default_configs[SandboxLevel.BASIC.value])
    
    def cleanup_all(self):
        """清理所有沙箱"""
        with self._lock:
            for sandbox_id in list(self._sandboxes.keys()):
                self.remove_sandbox(sandbox_id)
        self._logger.info("清理所有沙箱完成")


# 自定义异常
class ResourceError(Exception):
    """资源限制异常"""
    pass


# 全局沙箱管理器实例
_sandbox_manager: Optional[SandboxManager] = None


def get_sandbox_manager() -> SandboxManager:
    """获取全局沙箱管理器实例"""
    global _sandbox_manager
    if _sandbox_manager is None:
        _sandbox_manager = SandboxManager()
    return _sandbox_manager 