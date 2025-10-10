#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Simplified error handling decorators
Provides basic error handling decorators for different scenarios
"""

import functools
import time
from typing import Any, Callable, Optional

from ...infrastructure.logging import get_logger
from .handler import get_error_handler

logger = get_logger(__name__)


def handle_errors(
    operation: Optional[str] = None,
    component: Optional[str] = None,
    reraise: bool = True,
    fallback_return_value: Any = None,
):
    """
    General error handling decorator

    Args:
        operation: Operation name
        component: Component name
        reraise: Whether to re-raise exception after logging
        fallback_return_value: Default return value on error (if reraise=False)
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            error_handler = get_error_handler()
            operation_name = operation or func.__name__
            component_name = component or func.__module__.split(".")[-1]

            try:
                return func(*args, **kwargs)

            except Exception as e:
                logger.error(f"Error in {operation_name}: {e}")

                # Handle error
                error_handler.handle_exception(
                    e,
                    operation=operation_name,
                    component=component_name,
                )

                if reraise:
                    raise
                else:
                    return fallback_return_value

        return wrapper

    return decorator


def handle_gui_errors(component: str, fallback_return_value: Any = None):
    """
    GUI error handling decorator

    Args:
        component: GUI component name
        fallback_return_value: Return value on error
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            error_handler = get_error_handler()

            try:
                return func(*args, **kwargs)

            except Exception as e:
                logger.error(f"GUI error in {component}.{func.__name__}: {e}")

                # Handle GUI error
                error_handler.handle_gui_error(e, component=component)

                # GUI errors typically don't retry, return fallback value
                return fallback_return_value

        return wrapper

    return decorator


# Removed: handle_processing_errors, handle_config_errors - overly complex and unused
# Use simple handle_errors decorator instead


def retry_on_failure(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff_factor: float = 2.0,
):
    """
    Retry decorator for failed operations

    Args:
        max_attempts: Maximum number of attempts
        delay: Initial delay in seconds
        backoff_factor: Delay multiplier for each retry
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 1
            current_delay = delay

            while attempt <= max_attempts:
                try:
                    return func(*args, **kwargs)

                except Exception as e:
                    if attempt == max_attempts:
                        logger.error(f"Function {func.__name__} failed after {max_attempts} attempts")
                        raise

                    logger.warning(
                        f"Attempt {attempt} of {func.__name__} failed: {e}. Retrying in {current_delay:.1f}s"
                    )
                    time.sleep(current_delay)

                    attempt += 1
                    current_delay *= backoff_factor

        return wrapper

    return decorator


# Removed: validate_arguments, ErrorHandlingContext - overly complex and unused  # 不抑制异常
