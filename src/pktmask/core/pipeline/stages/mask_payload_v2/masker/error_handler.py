"""
错误处理和恢复系统

提供完善的异常处理、错误恢复和错误报告机制。
"""

from __future__ import annotations

import logging
import time
import traceback
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union


class ErrorSeverity(Enum):
    """错误严重程度"""

    LOW = "low"  # 轻微错误，可以继续处理
    MEDIUM = "medium"  # 中等错误，需要警告但可以恢复
    HIGH = "high"  # 严重错误，需要停止当前操作
    CRITICAL = "critical"  # 致命错误，需要立即停止所有操作


class ErrorCategory(Enum):
    """错误类别"""

    INPUT_ERROR = "input_error"  # 输入文件错误
    OUTPUT_ERROR = "output_error"  # 输出文件错误
    PROCESSING_ERROR = "processing_error"  # 处理过程错误
    MEMORY_ERROR = "memory_error"  # 内存相关错误
    NETWORK_ERROR = "network_error"  # 网络相关错误
    SYSTEM_ERROR = "system_error"  # 系统级错误
    VALIDATION_ERROR = "validation_error"  # 数据验证错误


@dataclass
class ErrorInfo:
    """错误信息"""

    timestamp: float
    severity: ErrorSeverity
    category: ErrorCategory
    message: str
    exception: Optional[Exception] = None
    traceback_str: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    recovery_attempted: bool = False
    recovery_successful: bool = False
    recovery_details: Optional[str] = None


class ErrorRecoveryHandler:
    """错误恢复处理器

    提供完善的异常处理、错误恢复和错误报告机制。
    """

    def __init__(self, config: Dict[str, Any]):
        """初始化错误处理器

        Args:
            config: 配置字典
        """
        self.config = config
        self.logger = logging.getLogger(
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )

        # 配置参数
        self.max_retry_attempts = config.get("max_retry_attempts", 3)
        self.retry_delay = config.get("retry_delay", 1.0)  # 秒
        self.enable_auto_recovery = config.get("enable_auto_recovery", True)
        self.fail_fast = config.get("fail_fast", False)  # 是否快速失败
        self.error_log_file = config.get("error_log_file", None)

        # 内部状态
        self.error_history: List[ErrorInfo] = []
        self.recovery_handlers: Dict[ErrorCategory, List[Callable]] = {}
        self.error_count_by_category: Dict[ErrorCategory, int] = {}
        self.total_errors = 0

        # 注册默认的恢复处理器
        self._register_default_recovery_handlers()

        self.logger.info(
            f"错误处理器初始化: 最大重试={self.max_retry_attempts}, "
            f"自动恢复={'启用' if self.enable_auto_recovery else '禁用'}"
        )

    def handle_error(
        self,
        error: Union[Exception, str],
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        category: ErrorCategory = ErrorCategory.PROCESSING_ERROR,
        context: Optional[Dict[str, Any]] = None,
        attempt_recovery: bool = True,
    ) -> ErrorInfo:
        """处理错误

        Args:
            error: 错误对象或错误消息
            severity: 错误严重程度
            category: 错误类别
            context: 错误上下文信息
            attempt_recovery: 是否尝试恢复

        Returns:
            ErrorInfo: 错误信息对象
        """
        # 创建错误信息
        error_info = ErrorInfo(
            timestamp=time.time(),
            severity=severity,
            category=category,
            message=str(error),
            exception=error if isinstance(error, Exception) else None,
            traceback_str=(
                traceback.format_exc() if isinstance(error, Exception) else None
            ),
            context=context or {},
        )

        # 记录错误
        self._log_error(error_info)

        # 更新统计
        self.total_errors += 1
        self.error_count_by_category[category] = (
            self.error_count_by_category.get(category, 0) + 1
        )

        # 添加到历史记录
        self.error_history.append(error_info)

        # 尝试恢复
        if attempt_recovery and self.enable_auto_recovery:
            self._attempt_recovery(error_info)

        # 检查是否需要快速失败
        if self.fail_fast and severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
            raise RuntimeError(f"快速失败模式: {error_info.message}")

        return error_info

    def register_recovery_handler(
        self, category: ErrorCategory, handler: Callable[[ErrorInfo], bool]
    ):
        """注册错误恢复处理器

        Args:
            category: 错误类别
            handler: 恢复处理函数，返回True表示恢复成功
        """
        if category not in self.recovery_handlers:
            self.recovery_handlers[category] = []
        self.recovery_handlers[category].append(handler)

        self.logger.debug(f"注册恢复处理器: {category.value}")

    def retry_operation(
        self,
        operation: Callable,
        max_attempts: Optional[int] = None,
        delay: Optional[float] = None,
        error_category: ErrorCategory = ErrorCategory.PROCESSING_ERROR,
    ) -> Any:
        """重试操作

        Args:
            operation: 要重试的操作
            max_attempts: 最大重试次数
            delay: 重试延迟
            error_category: 错误类别

        Returns:
            操作结果

        Raises:
            最后一次尝试的异常
        """
        max_attempts = max_attempts or self.max_retry_attempts
        delay = delay or self.retry_delay

        last_exception = None

        for attempt in range(max_attempts):
            try:
                result = operation()
                if attempt > 0:
                    self.logger.info(f"操作在第{attempt + 1}次尝试后成功")
                return result
            except Exception as e:
                last_exception = e

                if attempt < max_attempts - 1:
                    self.logger.warning(f"操作失败，第{attempt + 1}次尝试: {e}")
                    self.handle_error(
                        e,
                        ErrorSeverity.MEDIUM,
                        error_category,
                        {"attempt": attempt + 1, "max_attempts": max_attempts},
                        attempt_recovery=False,
                    )

                    if delay > 0:
                        time.sleep(delay)
                else:
                    self.logger.error(f"操作在{max_attempts}次尝试后仍然失败: {e}")
                    self.handle_error(
                        e,
                        ErrorSeverity.HIGH,
                        error_category,
                        {"final_attempt": True, "total_attempts": max_attempts},
                    )

        raise last_exception

    def _log_error(self, error_info: ErrorInfo):
        """记录错误日志"""
        log_message = f"[{error_info.category.value.upper()}] {error_info.message}"

        if error_info.context:
            context_str = ", ".join(f"{k}={v}" for k, v in error_info.context.items())
            log_message += f" (上下文: {context_str})"

        # 根据严重程度选择日志级别
        if error_info.severity == ErrorSeverity.LOW:
            self.logger.debug(log_message)
        elif error_info.severity == ErrorSeverity.MEDIUM:
            self.logger.warning(log_message)
        elif error_info.severity == ErrorSeverity.HIGH:
            self.logger.error(log_message)
        else:  # CRITICAL
            self.logger.critical(log_message)

        # 如果有异常和堆栈跟踪，记录详细信息
        if error_info.exception and error_info.traceback_str:
            self.logger.debug(f"异常详情:\n{error_info.traceback_str}")

        # 写入错误日志文件
        if self.error_log_file:
            self._write_error_log_file(error_info)

    def _attempt_recovery(self, error_info: ErrorInfo):
        """尝试错误恢复"""
        error_info.recovery_attempted = True

        # 获取对应类别的恢复处理器
        handlers = self.recovery_handlers.get(error_info.category, [])

        for handler in handlers:
            try:
                if handler(error_info):
                    error_info.recovery_successful = True
                    error_info.recovery_details = (
                        f"通过处理器 {handler.__name__} 恢复成功"
                    )
                    self.logger.info(f"错误恢复成功: {error_info.recovery_details}")
                    return
            except Exception as recovery_error:
                self.logger.warning(
                    f"恢复处理器 {handler.__name__} 执行失败: {recovery_error}"
                )

        error_info.recovery_details = "所有恢复尝试均失败"
        self.logger.warning(f"错误恢复失败: {error_info.message}")

    def _register_default_recovery_handlers(self):
        """注册默认的恢复处理器"""

        def memory_error_recovery(error_info: ErrorInfo) -> bool:
            """内存错误恢复"""
            try:
                import gc

                gc.collect()
                self.logger.info("执行垃圾回收以释放内存")
                return True
            except Exception:
                return False

        def file_error_recovery(error_info: ErrorInfo) -> bool:
            """文件错误恢复"""
            try:
                # 检查文件路径是否存在
                if "file_path" in error_info.context:
                    file_path = Path(error_info.context["file_path"])
                    if not file_path.exists():
                        self.logger.warning(f"文件不存在: {file_path}")
                        return False

                    # 检查文件权限
                    if not file_path.is_file() or not file_path.stat().st_size > 0:
                        self.logger.warning(f"文件无效或为空: {file_path}")
                        return False

                return True
            except Exception:
                return False

        # 注册默认处理器
        self.register_recovery_handler(
            ErrorCategory.MEMORY_ERROR, memory_error_recovery
        )
        self.register_recovery_handler(ErrorCategory.INPUT_ERROR, file_error_recovery)
        self.register_recovery_handler(ErrorCategory.OUTPUT_ERROR, file_error_recovery)

    def _write_error_log_file(self, error_info: ErrorInfo):
        """Write error log file"""
        try:
            log_file = Path(self.error_log_file)
            log_file.parent.mkdir(parents=True, exist_ok=True)

            with open(log_file, "a", encoding="utf-8") as f:
                f.write(
                    f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(error_info.timestamp))}\n"
                )
                f.write(f"Severity: {error_info.severity.value}\n")
                f.write(f"Category: {error_info.category.value}\n")
                f.write(f"Message: {error_info.message}\n")
                if error_info.context:
                    f.write(f"Context: {error_info.context}\n")
                if error_info.traceback_str:
                    f.write(f"Stack trace:\n{error_info.traceback_str}\n")
                f.write("-" * 80 + "\n")
        except Exception as e:
            self.logger.warning(f"Failed to write error log file: {e}")

    def get_error_summary(self) -> Dict[str, Any]:
        """获取错误摘要"""
        return {
            "total_errors": self.total_errors,
            "errors_by_category": dict(self.error_count_by_category),
            "recent_errors": [
                {
                    "timestamp": error.timestamp,
                    "severity": error.severity.value,
                    "category": error.category.value,
                    "message": error.message,
                    "recovery_successful": error.recovery_successful,
                }
                for error in self.error_history[-10:]  # 最近10个错误
            ],
            "recovery_success_rate": self._calculate_recovery_success_rate(),
        }

    def _calculate_recovery_success_rate(self) -> float:
        """计算恢复成功率"""
        attempted_recoveries = [e for e in self.error_history if e.recovery_attempted]
        if not attempted_recoveries:
            return 0.0

        successful_recoveries = [
            e for e in attempted_recoveries if e.recovery_successful
        ]
        return len(successful_recoveries) / len(attempted_recoveries)

    def clear_error_history(self):
        """清空错误历史"""
        self.error_history.clear()
        self.error_count_by_category.clear()
        self.total_errors = 0
        self.logger.info("错误历史已清空")


def create_error_handler(config: Dict[str, Any]) -> ErrorRecoveryHandler:
    """创建错误处理器实例的工厂函数

    Args:
        config: 配置字典

    Returns:
        ErrorRecoveryHandler: 错误处理器实例
    """
    return ErrorRecoveryHandler(config)
