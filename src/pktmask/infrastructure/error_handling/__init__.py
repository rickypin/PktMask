#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Simplified error handling infrastructure
Provides basic exception handling and logging
"""

from .decorators import (
    handle_errors,
    handle_gui_errors,
    retry_on_failure,
)
from .handler import (
    ErrorHandler,
    get_error_handler,
    handle_config_error,
    handle_critical_error,
    handle_error,
    handle_file_error,
    handle_gui_error,
    install_global_exception_handler,
    uninstall_global_exception_handler,
)

__all__ = [
    # Core handlers
    "ErrorHandler",
    "get_error_handler",
    "install_global_exception_handler",
    "uninstall_global_exception_handler",
    "handle_error",
    "handle_critical_error",
    "handle_file_error",
    "handle_gui_error",
    "handle_config_error",
    # Decorators
    "handle_errors",
    "handle_gui_errors",
    "retry_on_failure",
]

# Version info
__version__ = "2.0.0"  # Simplified version
