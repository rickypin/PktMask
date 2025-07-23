#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
核心错误处理器
统一的异常处理、记录、报告和恢复机制
"""

import sys
import traceback
from typing import Dict, Any, Optional, Callable, List, Type, Union
from datetime import datetime
from pathlib import Path

from ...common.exceptions import PktMaskError, create_error_from_exception
from ...common.enums import ErrorSeverity
from ...infrastructure.logging import get_logger, log_exception
from .context import ErrorContext, create_error_context, get_context_manager
from .recovery import (
    ErrorRecoveryManager,
    RecoveryResult,
    RecoveryAction,
    get_recovery_manager,
)
from .reporter import ErrorReporter, get_error_reporter

logger = get_logger(__name__)


class ErrorHandler:
    """统一错误处理器"""

    def __init__(self):
        self.context_manager = get_context_manager()
        self.recovery_manager = get_recovery_manager()
        self.error_reporter = get_error_reporter()

        # 错误处理配置
        self.auto_recovery_enabled = True
        self.user_notification_enabled = True
        self.detailed_logging_enabled = True

        # 错误处理统计
        self.stats = {
            "total_errors": 0,
            "handled_errors": 0,
            "unhandled_errors": 0,
            "recovered_errors": 0,
            "severity_counts": {severity.name: 0 for severity in ErrorSeverity},
        }

        # 错误回调
        self.error_callbacks: List[Callable] = []

        logger.debug("Error handler initialized")

    def handle_exception(
        self,
        exception: Exception,
        operation: Optional[str] = None,
        component: Optional[str] = None,
        user_action: Optional[str] = None,
        custom_data: Optional[Dict[str, Any]] = None,
        auto_recover: bool = True,
    ) -> Optional[Any]:
        """
        处理异常的主要入口点

        Args:
            exception: 发生的异常
            operation: 当前操作
            component: 当前组件
            user_action: 用户操作描述
            custom_data: 自定义数据
            auto_recover: 是否尝试自动恢复

        Returns:
            恢复结果（如果有）
        """
        self.stats["total_errors"] += 1

        # 转换为PktMask异常
        if isinstance(exception, PktMaskError):
            error = exception
        else:
            error = create_error_from_exception(exception, custom_data)

        # 更新严重性统计
        self.stats["severity_counts"][error.severity.name] += 1

        # 创建错误上下文
        context = create_error_context(
            exception=error,
            operation=operation,
            component=component,
            user_action=user_action,
            custom_data=custom_data,
        )

        # 记录错误
        self._log_error(error, context)

        # 尝试恢复
        recovery_result = None
        if auto_recover and self.auto_recovery_enabled:
            recovery_result = self._attempt_recovery(error, context)

        # 生成错误报告
        self._generate_error_report(error, context, recovery_result)

        # 通知用户（如果需要）
        if self.user_notification_enabled:
            self._notify_user(error, context, recovery_result)

        # 调用错误回调
        self._call_error_callbacks(error, context, recovery_result)

        # 更新统计
        if recovery_result and recovery_result.success:
            self.stats["recovered_errors"] += 1

        self.stats["handled_errors"] += 1

        logger.debug(f"Error handling completed for: {error.__class__.__name__}")

        return recovery_result

    def _log_error(self, error: PktMaskError, context: ErrorContext) -> None:
        """记录错误信息"""
        try:
            # 基本错误记录
            log_exception(
                error,
                logger_name=context.component or "error_handler",
                context={"error_context": context.to_dict()},
            )

            # 详细日志（如果启用）
            if self.detailed_logging_enabled:
                logger.debug(f"Error context details: {context.to_dict()}")

        except Exception as log_error:
            # 记录日志失败不应该影响错误处理
            print(f"Failed to log error: {log_error}", file=sys.stderr)

    def _attempt_recovery(
        self, error: PktMaskError, context: ErrorContext
    ) -> Optional[RecoveryResult]:
        """尝试错误恢复"""
        try:
            recovery_result = self.recovery_manager.attempt_recovery(error, context)

            if recovery_result.success:
                logger.info(f"Error recovery successful: {recovery_result.message}")
            else:
                logger.warning(f"Error recovery failed: {recovery_result.message}")

            return recovery_result

        except Exception as recovery_error:
            logger.error(f"Recovery attempt failed: {recovery_error}")
            return None

    def _generate_error_report(
        self,
        error: PktMaskError,
        context: ErrorContext,
        recovery_result: Optional[RecoveryResult],
    ) -> None:
        """生成错误报告"""
        try:
            self.error_reporter.report_error(error, context, recovery_result)
        except Exception as report_error:
            logger.error(f"Failed to generate error report: {report_error}")

    def _notify_user(
        self,
        error: PktMaskError,
        context: ErrorContext,
        recovery_result: Optional[RecoveryResult],
    ) -> None:
        """通知用户错误信息"""
        # 这里可以根据错误严重性决定通知方式
        # 对于高严重性错误，可能需要显示对话框
        # 对于低严重性错误，可能只需要状态栏通知

        if error.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
            logger.warning(f"Critical error occurred: {error.message}")
            # TODO: 显示用户对话框
        else:
            logger.info(f"Error handled: {error.message}")

    def _call_error_callbacks(
        self,
        error: PktMaskError,
        context: ErrorContext,
        recovery_result: Optional[RecoveryResult],
    ) -> None:
        """调用错误回调函数"""
        for callback in self.error_callbacks:
            try:
                callback(error, context, recovery_result)
            except Exception as callback_error:
                logger.error(f"Error callback failed: {callback_error}")

    def register_error_callback(self, callback: Callable) -> None:
        """注册错误回调函数"""
        self.error_callbacks.append(callback)
        logger.debug(f"Registered error callback: {callback.__name__}")

    def unregister_error_callback(self, callback: Callable) -> None:
        """取消注册错误回调函数"""
        if callback in self.error_callbacks:
            self.error_callbacks.remove(callback)
            logger.debug(f"Unregistered error callback: {callback.__name__}")

    def set_auto_recovery_enabled(self, enabled: bool) -> None:
        """设置是否启用自动恢复"""
        self.auto_recovery_enabled = enabled
        logger.debug(f"Auto recovery {'enabled' if enabled else 'disabled'}")

    def set_user_notification_enabled(self, enabled: bool) -> None:
        """设置是否启用用户通知"""
        self.user_notification_enabled = enabled
        logger.debug(f"User notification {'enabled' if enabled else 'disabled'}")

    def set_detailed_logging_enabled(self, enabled: bool) -> None:
        """设置是否启用详细日志"""
        self.detailed_logging_enabled = enabled
        logger.debug(f"Detailed logging {'enabled' if enabled else 'disabled'}")

    def get_error_stats(self) -> Dict[str, Any]:
        """获取错误处理统计信息"""
        stats = self.stats.copy()
        stats["recovery_stats"] = self.recovery_manager.get_recovery_stats()
        return stats

    def reset_stats(self) -> None:
        """重置统计信息"""
        self.stats = {
            "total_errors": 0,
            "handled_errors": 0,
            "unhandled_errors": 0,
            "recovered_errors": 0,
            "severity_counts": {severity.name: 0 for severity in ErrorSeverity},
        }
        self.recovery_manager.reset_stats()
        logger.debug("Error handler statistics reset")

    def handle_critical_error(
        self, error: Exception, context_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """处理严重错误"""
        # 强制创建PktMask异常
        if isinstance(error, PktMaskError):
            pkt_error = error
        else:
            pkt_error = create_error_from_exception(error, context_data)

        # 设置为严重错误
        pkt_error.severity = ErrorSeverity.CRITICAL

        # 记录严重错误
        logger.critical(f"Critical error: {pkt_error.message}")

        # 处理错误（不尝试自动恢复）
        self.handle_exception(pkt_error, auto_recover=False)

    def handle_file_processing_error(
        self, error: Exception, file_path: str
    ) -> Optional[RecoveryResult]:
        """处理文件处理错误"""
        self.context_manager.set_current_file(file_path)

        return self.handle_exception(
            error,
            operation="file_processing",
            component="file_processor",
            custom_data={"file_path": file_path},
        )

    def handle_gui_error(
        self, error: Exception, component: str, user_action: str
    ) -> Optional[RecoveryResult]:
        """处理GUI错误"""
        return self.handle_exception(
            error,
            operation="gui_operation",
            component=component,
            user_action=user_action,
        )

    def handle_config_error(
        self, error: Exception, config_key: Optional[str] = None
    ) -> Optional[RecoveryResult]:
        """处理配置错误"""
        custom_data = {"config_key": config_key} if config_key else None

        return self.handle_exception(
            error,
            operation="configuration",
            component="config_manager",
            custom_data=custom_data,
        )


class GlobalExceptionHandler:
    """全局异常处理器"""

    def __init__(self, error_handler: ErrorHandler):
        self.error_handler = error_handler
        self.original_excepthook = sys.excepthook
        self.installed = False

    def install(self) -> None:
        """安装全局异常处理器"""
        if not self.installed:
            sys.excepthook = self.handle_exception
            self.installed = True
            logger.debug("Global exception handler installed")

    def uninstall(self) -> None:
        """卸载全局异常处理器"""
        if self.installed:
            sys.excepthook = self.original_excepthook
            self.installed = False
            logger.debug("Global exception handler uninstalled")

    def handle_exception(
        self, exc_type: Type[BaseException], exc_value: BaseException, exc_traceback
    ) -> None:
        """处理未捕获的异常"""
        # 忽略KeyboardInterrupt等系统异常
        if issubclass(exc_type, (KeyboardInterrupt, SystemExit)):
            self.original_excepthook(exc_type, exc_value, exc_traceback)
            return

        logger.critical(f"Unhandled exception: {exc_type.__name__}: {exc_value}")

        # 使用错误处理器处理
        self.error_handler.handle_critical_error(exc_value)

        # 调用原始处理器（通常是打印到stderr）
        self.original_excepthook(exc_type, exc_value, exc_traceback)


# 全局错误处理器实例
_error_handler = ErrorHandler()
_global_exception_handler = GlobalExceptionHandler(_error_handler)


def get_error_handler() -> ErrorHandler:
    """获取全局错误处理器"""
    return _error_handler


def install_global_exception_handler() -> None:
    """安装全局异常处理器"""
    _global_exception_handler.install()


def uninstall_global_exception_handler() -> None:
    """卸载全局异常处理器"""
    _global_exception_handler.uninstall()


# 便利函数
def handle_error(exception: Exception, **kwargs) -> Optional[Any]:
    """便利函数：处理错误"""
    return _error_handler.handle_exception(exception, **kwargs)


def handle_critical_error(
    error: Exception, context_data: Optional[Dict[str, Any]] = None
) -> None:
    """便利函数：处理严重错误"""
    _error_handler.handle_critical_error(error, context_data)


def handle_file_error(error: Exception, file_path: str) -> Optional[RecoveryResult]:
    """便利函数：处理文件错误"""
    return _error_handler.handle_file_processing_error(error, file_path)


def handle_gui_error(
    error: Exception, component: str, user_action: str
) -> Optional[RecoveryResult]:
    """便利函数：处理GUI错误"""
    return _error_handler.handle_gui_error(error, component, user_action)


def handle_config_error(
    error: Exception, config_key: Optional[str] = None
) -> Optional[RecoveryResult]:
    """便利函数：处理配置错误"""
    return _error_handler.handle_config_error(error, config_key)
