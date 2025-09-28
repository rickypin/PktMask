#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
错误处理装饰器
提供便捷的错误处理装饰器用于不同场景
"""

import functools
from typing import Any, Callable, List, Optional, Type, Union

from ...infrastructure.logging import get_logger
from .context import (
    add_recent_action,
    clear_operation,
    set_current_component,
    set_current_operation,
)
from .handler import get_error_handler
from .recovery import RecoveryAction

logger = get_logger(__name__)


def handle_errors(
    operation: Optional[str] = None,
    component: Optional[str] = None,
    auto_recover: bool = True,
    reraise_on_failure: bool = False,
    fallback_return_value: Any = None,
    log_success: bool = False,
):
    """
    通用错误处理装饰器

    Args:
        operation: 操作名称
        component: 组件名称
        auto_recover: 是否自动尝试恢复
        reraise_on_failure: 恢复失败时是否重新抛出异常
        fallback_return_value: 失败时的默认返回值
        log_success: 是否记录成功完成
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            error_handler = get_error_handler()
            operation_name = operation or func.__name__
            component_name = component or func.__module__.split(".")[-1]

            # 设置上下文
            if operation_name:
                set_current_operation(operation_name)
            if component_name:
                set_current_component(component_name)

            add_recent_action(f"Starting {operation_name}")

            try:
                result = func(*args, **kwargs)

                if log_success:
                    logger.debug(f"Successfully completed {operation_name}")
                    add_recent_action(f"Completed {operation_name}")

                return result

            except Exception as e:
                logger.warning(f"Error in {operation_name}: {e}")
                add_recent_action(f"Error in {operation_name}: {e}")

                # 处理错误
                recovery_result = error_handler.handle_exception(
                    e,
                    operation=operation_name,
                    component=component_name,
                    auto_recover=auto_recover,
                )

                # 根据恢复结果决定下一步行动
                if recovery_result:
                    if recovery_result.action == RecoveryAction.RETRY:
                        logger.info(f"Retrying {operation_name}")
                        add_recent_action(f"Retrying {operation_name}")
                        return wrapper(*args, **kwargs)  # 递归重试

                    elif recovery_result.action == RecoveryAction.CONTINUE:
                        logger.info(f"Continuing after error in {operation_name}")
                        return fallback_return_value

                    elif recovery_result.action == RecoveryAction.SKIP_ITEM:
                        logger.info(f"Skipping current item in {operation_name}")
                        return fallback_return_value

                # 如果恢复失败或不可恢复
                if reraise_on_failure:
                    raise
                else:
                    logger.warning(f"Returning fallback value for {operation_name}")
                    return fallback_return_value

            finally:
                # 清理上下文
                if operation_name:
                    clear_operation()

        return wrapper

    return decorator


def handle_gui_errors(
    component: str, show_user_dialog: bool = True, fallback_return_value: Any = None
):
    """
    GUI错误处理装饰器

    Args:
        component: GUI组件名称
        show_user_dialog: 是否显示用户错误对话框
        fallback_return_value: 错误时的返回值
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            error_handler = get_error_handler()

            try:
                return func(*args, **kwargs)

            except Exception as e:
                logger.error(f"GUI error in {component}.{func.__name__}: {e}")

                # 处理GUI错误
                error_handler.handle_gui_error(
                    e, component=component, user_action=func.__name__
                )

                # GUI错误通常不重试，直接返回fallback值
                if show_user_dialog:
                    # TODO: 显示用户错误对话框
                    pass

                return fallback_return_value

        return wrapper

    return decorator


def handle_processing_errors(
    step_name: str,
    file_path_arg: str = "file_path",
    skip_on_error: bool = True,
    max_retries: int = 3,
):
    """
    处理步骤错误装饰器

    Args:
        step_name: 处理步骤名称
        file_path_arg: 文件路径参数名
        skip_on_error: 错误时是否跳过文件
        max_retries: 最大重试次数
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            error_handler = get_error_handler()

            # 尝试获取文件路径
            file_path = None
            if file_path_arg in kwargs:
                file_path = kwargs[file_path_arg]
            elif len(args) > 0 and hasattr(args[0], "name"):
                file_path = str(args[0])

            retry_count = 0

            while retry_count <= max_retries:
                try:
                    add_recent_action(
                        f"Processing {step_name}"
                        + (f" for {file_path}" if file_path else "")
                    )
                    result = func(*args, **kwargs)

                    if retry_count > 0:
                        logger.info(
                            f"Successfully completed {step_name} after {retry_count} retries"
                        )

                    return result

                except Exception as e:
                    retry_count += 1

                    logger.warning(f"Error in {step_name} (attempt {retry_count}): {e}")

                    # 处理处理错误
                    recovery_result = error_handler.handle_file_processing_error(
                        e, file_path or "unknown"
                    )

                    if recovery_result:
                        if (
                            recovery_result.action == RecoveryAction.RETRY
                            and retry_count <= max_retries
                        ):
                            logger.info(
                                f"Retrying {step_name} (attempt {retry_count + 1})"
                            )
                            continue
                        elif recovery_result.action == RecoveryAction.SKIP_ITEM:
                            logger.warning(f"Skipping file due to error in {step_name}")
                            return None

                    # 如果达到最大重试次数或不可恢复
                    if retry_count > max_retries:
                        if skip_on_error:
                            logger.error(
                                f"Skipping file after {max_retries} failed attempts in {step_name}"
                            )
                            return None
                        else:
                            logger.error(
                                f"Failed {step_name} after {max_retries} attempts, re-raising"
                            )
                            raise

        return wrapper

    return decorator


def handle_config_errors(
    config_key: Optional[str] = None,
    use_defaults: bool = True,
    default_value: Any = None,
):
    """
    配置错误处理装饰器

    Args:
        config_key: 配置键名
        use_defaults: 是否使用默认值
        default_value: 默认值
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            error_handler = get_error_handler()

            try:
                return func(*args, **kwargs)

            except Exception as e:
                logger.error(f"Configuration error in {func.__name__}: {e}")

                # 处理配置错误
                error_handler.handle_config_error(e, config_key)

                if use_defaults:
                    logger.warning(
                        f"Using default value for configuration in {func.__name__}"
                    )
                    return default_value
                else:
                    raise

        return wrapper

    return decorator


def safe_operation(
    exceptions: Union[Type[Exception], List[Type[Exception]]] = Exception,
    return_value: Any = None,
    log_error: bool = True,
    operation_name: Optional[str] = None,
):
    """
    安全操作装饰器 - 捕获特定异常并返回安全值

    Args:
        exceptions: 要捕获的异常类型
        return_value: 异常时返回的值
        log_error: 是否记录错误
        operation_name: 操作名称
    """
    if not isinstance(exceptions, (list, tuple)):
        exceptions = [exceptions]

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            op_name = operation_name or func.__name__

            try:
                return func(*args, **kwargs)

            except tuple(exceptions) as e:
                if log_error:
                    logger.warning(f"Safe operation {op_name} caught exception: {e}")

                return return_value

        return wrapper

    return decorator


def retry_on_failure(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: Union[Type[Exception], List[Type[Exception]]] = Exception,
):
    """
    失败重试装饰器

    Args:
        max_attempts: 最大尝试次数
        delay: 初始延迟时间（秒）
        backoff_factor: 延迟递增因子
        exceptions: 触发重试的异常类型
    """
    import time

    if not isinstance(exceptions, (list, tuple)):
        exceptions = [exceptions]

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 1
            current_delay = delay

            while attempt <= max_attempts:
                try:
                    return func(*args, **kwargs)

                except tuple(exceptions) as e:
                    if attempt == max_attempts:
                        logger.error(
                            f"Function {func.__name__} failed after {max_attempts} attempts"
                        )
                        raise

                    logger.warning(
                        f"Attempt {attempt} of {func.__name__} failed: {e}. Retrying in {current_delay:.1f}s"
                    )
                    time.sleep(current_delay)

                    attempt += 1
                    current_delay *= backoff_factor

        return wrapper

    return decorator


def validate_arguments(**validators):
    """
    参数验证装饰器

    Args:
        **validators: 参数名到验证函数的映射
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 获取函数签名
            import inspect

            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()

            # 验证参数
            for param_name, validator in validators.items():
                if param_name in bound_args.arguments:
                    value = bound_args.arguments[param_name]
                    try:
                        if not validator(value):
                            raise ValueError(
                                f"Validation failed for parameter '{param_name}' with value: {value}"
                            )
                    except Exception as e:
                        logger.error(
                            f"Parameter validation error in {func.__name__}: {e}"
                        )
                        raise ValueError(
                            f"Invalid value for parameter '{param_name}': {e}"
                        )

            return func(*args, **kwargs)

        return wrapper

    return decorator


class ErrorHandlingContext:
    """错误处理上下文管理器"""

    def __init__(
        self, operation: str, component: Optional[str] = None, auto_recover: bool = True
    ):
        self.operation = operation
        self.component = component
        self.auto_recover = auto_recover
        self.error_handler = get_error_handler()

    def __enter__(self):
        set_current_operation(self.operation)
        if self.component:
            set_current_component(self.component)
        add_recent_action(f"Entered context: {self.operation}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            logger.warning(f"Exception in context {self.operation}: {exc_val}")

            recovery_result = self.error_handler.handle_exception(
                exc_val,
                operation=self.operation,
                component=self.component,
                auto_recover=self.auto_recover,
            )

            # 如果恢复成功，抑制异常
            if recovery_result and recovery_result.success:
                if recovery_result.action in [
                    RecoveryAction.CONTINUE,
                    RecoveryAction.SKIP_ITEM,
                ]:
                    return True  # 抑制异常

        add_recent_action(f"Exited context: {self.operation}")
        clear_operation()
        return False  # 不抑制异常
