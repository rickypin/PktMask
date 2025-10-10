#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Simplified error handler
Provides basic exception handling and logging
"""

import sys
import traceback
from typing import Any, Callable, Dict, Optional

from ...common.enums import ErrorSeverity
from ...common.exceptions import PktMaskError, create_error_from_exception
from ...infrastructure.logging import get_logger, log_exception

logger = get_logger(__name__)


class ErrorHandler:
    """Simplified unified error handler"""

    def __init__(self):
        # Error handling statistics
        self.stats = {
            "total_errors": 0,
            "handled_errors": 0,
            "severity_counts": {severity.name: 0 for severity in ErrorSeverity},
        }

        logger.debug("Error handler initialized")

    def handle_exception(
        self,
        exception: Exception,
        operation: Optional[str] = None,
        component: Optional[str] = None,
        custom_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Main entry point for exception handling

        Args:
            exception: The exception that occurred
            operation: Current operation description
            component: Current component name
            custom_data: Additional context data
        """
        self.stats["total_errors"] += 1

        # Convert to PktMask exception
        if isinstance(exception, PktMaskError):
            error = exception
        else:
            error = create_error_from_exception(exception, custom_data)

        # Update severity statistics
        self.stats["severity_counts"][error.severity.name] += 1

        # Log error with context
        self._log_error(error, operation, component, custom_data)

        self.stats["handled_errors"] += 1

        logger.debug(f"Error handling completed for: {error.__class__.__name__}")

    def _log_error(
        self,
        error: PktMaskError,
        operation: Optional[str],
        component: Optional[str],
        custom_data: Optional[Dict[str, Any]],
    ) -> None:
        """Log error information"""
        try:
            context_info = {
                "operation": operation,
                "component": component,
                "error_code": error.error_code,
                "severity": error.severity.name,
            }
            if custom_data:
                context_info["custom_data"] = custom_data

            log_exception(
                error,
                logger_name=component or "error_handler",
                context=context_info,
            )

        except Exception as log_error:
            # Logging failure should not affect error handling
            print(f"Failed to log error: {log_error}", file=sys.stderr)

    def get_error_stats(self) -> Dict[str, Any]:
        """Get error handling statistics"""
        return self.stats.copy()

    def reset_stats(self) -> None:
        """Reset statistics"""
        self.stats = {
            "total_errors": 0,
            "handled_errors": 0,
            "severity_counts": {severity.name: 0 for severity in ErrorSeverity},
        }
        logger.debug("Error handler statistics reset")

    def handle_critical_error(self, error: Exception, context_data: Optional[Dict[str, Any]] = None) -> None:
        """Handle critical error"""
        # Force create PktMask exception
        if isinstance(error, PktMaskError):
            pkt_error = error
        else:
            pkt_error = create_error_from_exception(error, context_data)

        # Set as critical error
        pkt_error.severity = ErrorSeverity.CRITICAL

        # Log critical error
        logger.critical(f"Critical error: {pkt_error.message}")

        # Handle error
        self.handle_exception(pkt_error, custom_data=context_data)


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

    def handle_exception(self, exc_type: Type[BaseException], exc_value: BaseException, exc_traceback) -> None:
        """Handle uncaught exceptions"""
        # Ignore system exceptions like KeyboardInterrupt
        if issubclass(exc_type, (KeyboardInterrupt, SystemExit)):
            self.original_excepthook(exc_type, exc_value, exc_traceback)
            return

        logger.critical(f"Unhandled exception: {exc_type.__name__}: {exc_value}")

        # Use error handler to process
        self.error_handler.handle_critical_error(exc_value)

        # Call original handler (usually print to stderr)
        self.original_excepthook(exc_type, exc_value, exc_traceback)


# Global error handler instances
_error_handler = ErrorHandler()
_global_exception_handler = GlobalExceptionHandler(_error_handler)


def get_error_handler() -> ErrorHandler:
    """Get global error handler"""
    return _error_handler


def install_global_exception_handler() -> None:
    """Install global exception handler"""
    _global_exception_handler.install()


def uninstall_global_exception_handler() -> None:
    """Uninstall global exception handler"""
    _global_exception_handler.uninstall()


# Convenience functions
def handle_error(exception: Exception, **kwargs) -> None:
    """Convenience function: handle error"""
    _error_handler.handle_exception(exception, **kwargs)


def handle_critical_error(error: Exception, context_data: Optional[Dict[str, Any]] = None) -> None:
    """Convenience function: handle critical error"""
    _error_handler.handle_critical_error(error, context_data)


def handle_file_error(error: Exception, file_path: str) -> None:
    """Convenience function: handle file error"""
    _error_handler.handle_exception(
        error,
        operation="file_processing",
        component="file_processor",
        custom_data={"file_path": file_path},
    )


def handle_gui_error(error: Exception, component: str) -> None:
    """Convenience function: handle GUI error"""
    _error_handler.handle_exception(
        error,
        operation="gui_operation",
        component=component,
    )


def handle_config_error(error: Exception, config_key: Optional[str] = None) -> None:
    """Convenience function: handle configuration error"""
    custom_data = {"config_key": config_key} if config_key else None
    _error_handler.handle_exception(
        error,
        operation="configuration",
        component="config_manager",
        custom_data=custom_data,
    )
