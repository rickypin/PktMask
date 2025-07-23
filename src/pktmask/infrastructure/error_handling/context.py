#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
错误上下文管理
提供错误发生时的上下文信息收集和管理
"""

import sys
import threading
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ...infrastructure.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ErrorContext:
    """错误上下文信息"""

    # 基本信息
    timestamp: datetime = field(default_factory=datetime.now)
    thread_id: int = field(default_factory=lambda: threading.get_ident())
    thread_name: str = field(default_factory=lambda: threading.current_thread().name)

    # 异常信息
    exception_type: Optional[str] = None
    exception_message: Optional[str] = None
    traceback_str: Optional[str] = None

    # 应用状态
    operation: Optional[str] = None
    component: Optional[str] = None
    file_path: Optional[str] = None
    user_action: Optional[str] = None

    # 系统信息
    python_version: str = field(default_factory=lambda: sys.version)
    platform: str = field(default_factory=lambda: sys.platform)
    cwd: str = field(default_factory=lambda: str(Path.cwd()))

    # 自定义数据
    custom_data: Dict[str, Any] = field(default_factory=dict)

    # 性能信息
    memory_usage_mb: Optional[float] = None
    cpu_percent: Optional[float] = None

    # 用户环境
    config_values: Dict[str, Any] = field(default_factory=dict)
    recent_actions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "thread_id": self.thread_id,
            "thread_name": self.thread_name,
            "exception": {
                "type": self.exception_type,
                "message": self.exception_message,
                "traceback": self.traceback_str,
            },
            "application": {
                "operation": self.operation,
                "component": self.component,
                "file_path": self.file_path,
                "user_action": self.user_action,
            },
            "system": {
                "python_version": self.python_version,
                "platform": self.platform,
                "cwd": self.cwd,
                "memory_usage_mb": self.memory_usage_mb,
                "cpu_percent": self.cpu_percent,
            },
            "user_environment": {
                "config_values": self.config_values,
                "recent_actions": self.recent_actions,
            },
            "custom_data": self.custom_data,
        }

    def add_custom_data(self, key: str, value: Any) -> None:
        """添加自定义数据"""
        self.custom_data[key] = value

    def add_recent_action(self, action: str) -> None:
        """添加最近的用户操作"""
        self.recent_actions.append(f"{datetime.now().isoformat()}: {action}")
        # 只保留最近的10个操作
        if len(self.recent_actions) > 10:
            self.recent_actions.pop(0)


class ErrorContextManager:
    """错误上下文管理器"""

    def __init__(self):
        self._current_operation: Optional[str] = None
        self._current_component: Optional[str] = None
        self._current_file: Optional[str] = None
        self._recent_actions: List[str] = []
        self._config_snapshot: Dict[str, Any] = {}

    def set_current_operation(self, operation: str) -> None:
        """设置当前操作"""
        self._current_operation = operation
        self.add_recent_action(f"Started operation: {operation}")
        logger.debug(f"Error context: Set operation to '{operation}'")

    def set_current_component(self, component: str) -> None:
        """设置当前组件"""
        self._current_component = component
        logger.debug(f"Error context: Set component to '{component}'")

    def set_current_file(self, file_path: Union[str, Path]) -> None:
        """设置当前处理的文件"""
        self._current_file = str(file_path)
        logger.debug(f"Error context: Set file to '{self._current_file}'")

    def add_recent_action(self, action: str) -> None:
        """添加最近的操作"""
        timestamp = datetime.now().isoformat()
        self._recent_actions.append(f"{timestamp}: {action}")

        # 只保留最近的20个操作
        if len(self._recent_actions) > 20:
            self._recent_actions.pop(0)

        logger.debug(f"Error context: Added action '{action}'")

    def update_config_snapshot(self, config_data: Dict[str, Any]) -> None:
        """更新配置快照"""
        self._config_snapshot = config_data.copy()
        logger.debug("Error context: Updated config snapshot")

    def clear_operation(self) -> None:
        """清除当前操作"""
        if self._current_operation:
            self.add_recent_action(f"Completed operation: {self._current_operation}")
            self._current_operation = None

    def get_system_info(self) -> Dict[str, Any]:
        """获取系统信息"""
        try:
            import psutil

            process = psutil.Process()
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
            cpu_percent = process.cpu_percent()
        except ImportError:
            memory_mb = None
            cpu_percent = None
            logger.debug("psutil not available, skipping performance metrics")
        except Exception as e:
            logger.warning(f"Failed to get system info: {e}")
            memory_mb = None
            cpu_percent = None

        return {
            "memory_usage_mb": memory_mb,
            "cpu_percent": cpu_percent,
            "python_version": sys.version,
            "platform": sys.platform,
            "cwd": str(Path.cwd()),
        }

    def create_context(
        self,
        exception: Optional[Exception] = None,
        operation: Optional[str] = None,
        component: Optional[str] = None,
        user_action: Optional[str] = None,
        custom_data: Optional[Dict[str, Any]] = None,
    ) -> ErrorContext:
        """创建错误上下文"""

        # 异常信息
        exception_type = None
        exception_message = None
        traceback_str = None

        if exception:
            exception_type = type(exception).__name__
            exception_message = str(exception)
            traceback_str = traceback.format_exc()

        # 系统信息
        system_info = self.get_system_info()

        # 创建上下文
        context = ErrorContext(
            exception_type=exception_type,
            exception_message=exception_message,
            traceback_str=traceback_str,
            operation=operation or self._current_operation,
            component=component or self._current_component,
            file_path=self._current_file,
            user_action=user_action,
            memory_usage_mb=system_info.get("memory_usage_mb"),
            cpu_percent=system_info.get("cpu_percent"),
            config_values=self._config_snapshot.copy(),
            recent_actions=self._recent_actions.copy(),
            custom_data=custom_data or {},
        )

        logger.debug(f"Created error context for operation '{context.operation}'")
        return context


# 全局上下文管理器实例
_context_manager = ErrorContextManager()


def get_context_manager() -> ErrorContextManager:
    """获取全局错误上下文管理器"""
    return _context_manager


def create_error_context(
    exception: Optional[Exception] = None,
    operation: Optional[str] = None,
    component: Optional[str] = None,
    user_action: Optional[str] = None,
    custom_data: Optional[Dict[str, Any]] = None,
) -> ErrorContext:
    """便利函数：创建错误上下文"""
    return _context_manager.create_context(
        exception=exception,
        operation=operation,
        component=component,
        user_action=user_action,
        custom_data=custom_data,
    )


def set_current_operation(operation: str) -> None:
    """便利函数：设置当前操作"""
    _context_manager.set_current_operation(operation)


def set_current_component(component: str) -> None:
    """便利函数：设置当前组件"""
    _context_manager.set_current_component(component)


def set_current_file(file_path: Union[str, Path]) -> None:
    """便利函数：设置当前文件"""
    _context_manager.set_current_file(file_path)


def add_recent_action(action: str) -> None:
    """便利函数：添加最近操作"""
    _context_manager.add_recent_action(action)


def clear_operation() -> None:
    """便利函数：清除当前操作"""
    _context_manager.clear_operation()


class ErrorContextDecorator:
    """错误上下文装饰器"""

    def __init__(
        self, operation: Optional[str] = None, component: Optional[str] = None
    ):
        self.operation = operation
        self.component = component

    def __call__(self, func):
        def wrapper(*args, **kwargs):
            # 设置上下文
            if self.operation:
                set_current_operation(self.operation)
            if self.component:
                set_current_component(self.component)

            try:
                result = func(*args, **kwargs)
                return result
            finally:
                # 清理上下文
                if self.operation:
                    clear_operation()

        return wrapper


def with_context(operation: Optional[str] = None, component: Optional[str] = None):
    """上下文装饰器"""
    return ErrorContextDecorator(operation=operation, component=component)
