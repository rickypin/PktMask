#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
错误处理基础设施
提供统一的异常处理、错误恢复和用户通知机制
"""

from .handler import (
    ErrorHandler, get_error_handler, install_global_exception_handler, 
    uninstall_global_exception_handler, handle_error, handle_critical_error,
    handle_file_error, handle_gui_error, handle_config_error
)
from .recovery import (
    ErrorRecoveryManager, RecoveryStrategy, RecoveryAction, RecoveryResult,
    get_recovery_manager, attempt_recovery
)
from .context import (
    ErrorContext, create_error_context, get_context_manager,
    set_current_operation, set_current_component, set_current_file,
    add_recent_action, clear_operation, with_context
)
from .decorators import (
    handle_errors, handle_gui_errors, handle_processing_errors,
    handle_config_errors, safe_operation, retry_on_failure,
    validate_arguments, ErrorHandlingContext
)
from .reporter import ErrorReporter, ErrorReport, get_error_reporter
from .registry import (
    ErrorHandlerRegistry, get_error_handler_registry,
    register_error_handler, get_error_handler_by_id,
    enable_error_handler, disable_error_handler
)

__all__ = [
    # 核心处理器
    'ErrorHandler',
    'get_error_handler',
    'install_global_exception_handler',
    'uninstall_global_exception_handler',
    'handle_error',
    'handle_critical_error',
    'handle_file_error',
    'handle_gui_error',
    'handle_config_error',
    
    # 错误恢复
    'ErrorRecoveryManager',
    'RecoveryStrategy', 
    'RecoveryAction',
    'RecoveryResult',
    'get_recovery_manager',
    'attempt_recovery',
    
    # 上下文管理
    'ErrorContext',
    'create_error_context',
    'get_context_manager',
    'set_current_operation',
    'set_current_component',
    'set_current_file',
    'add_recent_action',
    'clear_operation',
    'with_context',
    
    # 装饰器
    'handle_errors',
    'handle_gui_errors', 
    'handle_processing_errors',
    'handle_config_errors',
    'safe_operation',
    'retry_on_failure',
    'validate_arguments',
    'ErrorHandlingContext',
    
    # 报告系统
    'ErrorReporter',
    'ErrorReport',
    'get_error_reporter',
    
    # 注册表
    'ErrorHandlerRegistry',
    'get_error_handler_registry',
    'register_error_handler',
    'get_error_handler_by_id',
    'enable_error_handler',
    'disable_error_handler'
]

# 版本信息
__version__ = '1.0.0' 