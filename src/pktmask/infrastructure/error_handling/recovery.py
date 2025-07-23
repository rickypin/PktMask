#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
错误恢复管理
提供自动和手动的错误恢复策略
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from ...common.enums import ErrorSeverity
from ...common.exceptions import PktMaskError
from ...infrastructure.logging import get_logger
from .context import ErrorContext

logger = get_logger(__name__)


class RecoveryStrategy(Enum):
    """恢复策略类型"""

    NONE = "none"  # 不尝试恢复
    RETRY = "retry"  # 重试操作
    SKIP = "skip"  # 跳过当前项目
    FALLBACK = "fallback"  # 使用备用方法
    USER_PROMPT = "user_prompt"  # 提示用户决定
    RESTART_COMPONENT = "restart"  # 重启组件
    SAFE_MODE = "safe_mode"  # 安全模式


class RecoveryAction(Enum):
    """恢复操作类型"""

    CONTINUE = "continue"  # 继续处理
    ABORT = "abort"  # 中止操作
    RETRY = "retry"  # 重试
    SKIP_ITEM = "skip_item"  # 跳过当前项
    RESTART = "restart"  # 重新开始
    MANUAL_FIX = "manual_fix"  # 需要手动修复


@dataclass
class RecoveryResult:
    """恢复结果"""

    action: RecoveryAction
    success: bool
    message: str
    retry_count: int = 0
    custom_data: Dict[str, Any] = None

    def __post_init__(self):
        if self.custom_data is None:
            self.custom_data = {}


class RecoveryHandler(ABC):
    """恢复处理器基类"""

    @abstractmethod
    def can_handle(self, error: PktMaskError, context: ErrorContext) -> bool:
        """判断是否可以处理此错误"""

    @abstractmethod
    def recover(self, error: PktMaskError, context: ErrorContext) -> RecoveryResult:
        """执行恢复操作"""

    @property
    @abstractmethod
    def strategy(self) -> RecoveryStrategy:
        """恢复策略"""


class RetryRecoveryHandler(RecoveryHandler):
    """重试恢复处理器"""

    def __init__(
        self,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        backoff_factor: float = 2.0,
    ):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.backoff_factor = backoff_factor
        self._retry_counts: Dict[str, int] = {}

    @property
    def strategy(self) -> RecoveryStrategy:
        return RecoveryStrategy.RETRY

    def can_handle(self, error: PktMaskError, context: ErrorContext) -> bool:
        """判断是否可以重试"""
        # 某些错误类型不适合重试
        non_retryable_errors = ["ValidationError", "ConfigError", "DependencyError"]

        if error.__class__.__name__ in non_retryable_errors:
            return False

        # 检查重试次数
        operation_key = f"{context.operation}:{context.component}:{context.file_path}"
        current_retries = self._retry_counts.get(operation_key, 0)

        return current_retries < self.max_retries

    def recover(self, error: PktMaskError, context: ErrorContext) -> RecoveryResult:
        """执行重试恢复"""
        operation_key = f"{context.operation}:{context.component}:{context.file_path}"
        current_retries = self._retry_counts.get(operation_key, 0)

        if current_retries >= self.max_retries:
            return RecoveryResult(
                action=RecoveryAction.ABORT,
                success=False,
                message=f"Maximum retries ({self.max_retries}) exceeded",
                retry_count=current_retries,
            )

        # 增加重试计数
        self._retry_counts[operation_key] = current_retries + 1

        # 计算延迟时间
        delay = self.retry_delay * (self.backoff_factor**current_retries)

        logger.info(
            f"Retrying operation after {delay:.1f}s (attempt {current_retries + 1}/{self.max_retries})"
        )
        time.sleep(delay)

        return RecoveryResult(
            action=RecoveryAction.RETRY,
            success=True,
            message=f"Retrying operation (attempt {current_retries + 1})",
            retry_count=current_retries + 1,
        )

    def reset_retry_count(self, operation_key: str) -> None:
        """重置重试计数"""
        if operation_key in self._retry_counts:
            del self._retry_counts[operation_key]


class SkipRecoveryHandler(RecoveryHandler):
    """跳过恢复处理器"""

    @property
    def strategy(self) -> RecoveryStrategy:
        return RecoveryStrategy.SKIP

    def can_handle(self, error: PktMaskError, context: ErrorContext) -> bool:
        """文件处理错误通常可以跳过"""
        skippable_errors = ["FileError", "NetworkError", "ProcessingError"]
        return error.__class__.__name__ in skippable_errors

    def recover(self, error: PktMaskError, context: ErrorContext) -> RecoveryResult:
        """跳过当前项"""
        logger.warning(
            f"Skipping failed item: {context.file_path or context.operation}"
        )

        return RecoveryResult(
            action=RecoveryAction.SKIP_ITEM,
            success=True,
            message=f"Skipped failed item: {error.message}",
            custom_data={"skipped_item": context.file_path or context.operation},
        )


class FallbackRecoveryHandler(RecoveryHandler):
    """备用方案恢复处理器"""

    def __init__(self, fallback_handlers: Dict[str, Callable] = None):
        self.fallback_handlers = fallback_handlers or {}

    @property
    def strategy(self) -> RecoveryStrategy:
        return RecoveryStrategy.FALLBACK

    def can_handle(self, error: PktMaskError, context: ErrorContext) -> bool:
        """检查是否有备用处理器"""
        operation = context.operation or "default"
        return operation in self.fallback_handlers

    def recover(self, error: PktMaskError, context: ErrorContext) -> RecoveryResult:
        """使用备用方案"""
        operation = context.operation or "default"
        fallback_handler = self.fallback_handlers[operation]

        try:
            result = fallback_handler(error, context)
            logger.info(f"Fallback recovery successful for operation: {operation}")

            return RecoveryResult(
                action=RecoveryAction.CONTINUE,
                success=True,
                message=f"Fallback recovery completed for {operation}",
                custom_data={"fallback_result": result},
            )

        except Exception as e:
            logger.error(f"Fallback recovery failed: {e}")

            return RecoveryResult(
                action=RecoveryAction.ABORT,
                success=False,
                message=f"Fallback recovery failed: {e}",
            )

    def register_fallback(self, operation: str, handler: Callable) -> None:
        """注册备用处理器"""
        self.fallback_handlers[operation] = handler
        logger.debug(f"Registered fallback handler for operation: {operation}")


class UserPromptRecoveryHandler(RecoveryHandler):
    """用户提示恢复处理器"""

    def __init__(self, prompt_callback: Optional[Callable] = None):
        self.prompt_callback = prompt_callback

    @property
    def strategy(self) -> RecoveryStrategy:
        return RecoveryStrategy.USER_PROMPT

    def can_handle(self, error: PktMaskError, context: ErrorContext) -> bool:
        """如果有提示回调且是重要错误，可以处理"""
        return self.prompt_callback is not None and error.severity in [
            ErrorSeverity.HIGH,
            ErrorSeverity.CRITICAL,
        ]

    def recover(self, error: PktMaskError, context: ErrorContext) -> RecoveryResult:
        """提示用户选择恢复操作"""
        if not self.prompt_callback:
            return RecoveryResult(
                action=RecoveryAction.ABORT,
                success=False,
                message="No user prompt callback available",
            )

        try:
            user_choice = self.prompt_callback(error, context)

            action_map = {
                "continue": RecoveryAction.CONTINUE,
                "retry": RecoveryAction.RETRY,
                "skip": RecoveryAction.SKIP_ITEM,
                "abort": RecoveryAction.ABORT,
            }

            action = action_map.get(user_choice, RecoveryAction.ABORT)

            return RecoveryResult(
                action=action,
                success=True,
                message=f"User selected: {user_choice}",
                custom_data={"user_choice": user_choice},
            )

        except Exception as e:
            logger.error(f"User prompt failed: {e}")

            return RecoveryResult(
                action=RecoveryAction.ABORT,
                success=False,
                message=f"User prompt failed: {e}",
            )


class ErrorRecoveryManager:
    """错误恢复管理器"""

    def __init__(self):
        self.handlers: List[RecoveryHandler] = []
        self.default_strategy = RecoveryStrategy.RETRY
        self.recovery_stats = {
            "total_recoveries": 0,
            "successful_recoveries": 0,
            "failed_recoveries": 0,
            "strategy_usage": {},
        }

        # 注册默认处理器
        self._register_default_handlers()

    def _register_default_handlers(self) -> None:
        """注册默认恢复处理器"""
        self.register_handler(RetryRecoveryHandler(max_retries=3))
        self.register_handler(SkipRecoveryHandler())
        self.register_handler(FallbackRecoveryHandler())

    def register_handler(self, handler: RecoveryHandler) -> None:
        """注册恢复处理器"""
        self.handlers.append(handler)
        logger.debug(f"Registered recovery handler: {handler.__class__.__name__}")

    def set_user_prompt_callback(self, callback: Callable) -> None:
        """设置用户提示回调"""
        user_handler = UserPromptRecoveryHandler(callback)
        self.register_handler(user_handler)
        logger.debug("Registered user prompt recovery handler")

    def attempt_recovery(
        self, error: PktMaskError, context: ErrorContext
    ) -> RecoveryResult:
        """尝试错误恢复"""
        self.recovery_stats["total_recoveries"] += 1

        logger.info(f"Attempting recovery for error: {error.__class__.__name__}")

        # 找到合适的处理器
        for handler in self.handlers:
            if handler.can_handle(error, context):
                logger.debug(f"Using recovery handler: {handler.__class__.__name__}")

                try:
                    result = handler.recover(error, context)

                    # 更新统计
                    strategy_name = handler.strategy.value
                    self.recovery_stats["strategy_usage"][strategy_name] = (
                        self.recovery_stats["strategy_usage"].get(strategy_name, 0) + 1
                    )

                    if result.success:
                        self.recovery_stats["successful_recoveries"] += 1
                        logger.info(f"Recovery successful: {result.message}")
                    else:
                        self.recovery_stats["failed_recoveries"] += 1
                        logger.warning(f"Recovery failed: {result.message}")

                    return result

                except Exception as recovery_error:
                    logger.error(f"Recovery handler failed: {recovery_error}")
                    self.recovery_stats["failed_recoveries"] += 1

        # 没有找到合适的处理器
        logger.warning("No suitable recovery handler found")
        self.recovery_stats["failed_recoveries"] += 1

        return RecoveryResult(
            action=RecoveryAction.ABORT,
            success=False,
            message="No suitable recovery strategy available",
        )

    def get_recovery_stats(self) -> Dict[str, Any]:
        """获取恢复统计信息"""
        return self.recovery_stats.copy()

    def reset_stats(self) -> None:
        """重置统计信息"""
        self.recovery_stats = {
            "total_recoveries": 0,
            "successful_recoveries": 0,
            "failed_recoveries": 0,
            "strategy_usage": {},
        }
        logger.debug("Recovery statistics reset")


# 全局恢复管理器实例
_recovery_manager = ErrorRecoveryManager()


def get_recovery_manager() -> ErrorRecoveryManager:
    """获取全局错误恢复管理器"""
    return _recovery_manager


def attempt_recovery(error: PktMaskError, context: ErrorContext) -> RecoveryResult:
    """便利函数：尝试错误恢复"""
    return _recovery_manager.attempt_recovery(error, context)
