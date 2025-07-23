#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PktMask Logging system
Provides unified logging management functionality
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional

from ...common.constants import FileConstants
from ...common.enums import LogLevel


class PktMaskLogger:
    """PktMaskApplication log manager"""

    _instance: Optional["PktMaskLogger"] = None
    _initialized: bool = False

    def __new__(cls) -> "PktMaskLogger":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if PktMaskLogger._initialized:
            return

        self._loggers: Dict[str, logging.Logger] = {}
        self._setup_root_logger()
        PktMaskLogger._initialized = True

    def _setup_root_logger(self):
        """Setup root logger"""
        root_logger = logging.getLogger("pktmask")
        root_logger.setLevel(logging.DEBUG)

        # Avoid duplicate additionhandler
        if root_logger.handlers:
            return

        # Try to get log level from configuration
        console_level = logging.INFO  # Default level
        try:
            from ...config import get_app_config

            config = get_app_config()
            level_str = config.logging.log_level.upper()
            console_level = getattr(logging, level_str, logging.INFO)
        except Exception:
            # If configuration retrieval fails, use default level
            pass

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(console_level)
        console_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

        # File handler
        try:
            log_dir = Path.home() / FileConstants.CONFIG_DIR_NAME
            log_dir.mkdir(exist_ok=True)
            log_file = log_dir / FileConstants.LOG_FILE_NAME

            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=FileConstants.LOG_MAX_SIZE,
                backupCount=FileConstants.LOG_BACKUP_COUNT,
                encoding="utf-8",
            )
            file_handler.setLevel(logging.DEBUG)
            file_formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            file_handler.setFormatter(file_formatter)
            root_logger.addHandler(file_handler)
        except Exception as e:
            # If file logging setup fails, at least ensure console logging is available
            root_logger.warning(f"Failed to setup file logging: {e}")

        self._loggers["root"] = root_logger

    def get_logger(self, name: str) -> logging.Logger:
        """Get logger with specified name"""
        if name not in self._loggers:
            logger = logging.getLogger(f"pktmask.{name}")
            self._loggers[name] = logger
        return self._loggers[name]

    def set_level(self, level: LogLevel):
        """Set log level"""
        for logger in self._loggers.values():
            logger.setLevel(level.value)

    def reconfigure_from_config(self):
        """Reconfigure logging system based on configuration"""
        try:
            from ...config import get_app_config

            config = get_app_config()

            # Get configured log level
            level_str = config.logging.log_level.upper()
            console_level = getattr(logging, level_str, logging.INFO)

            # Update level of all existing handlers
            pktmask_logger = logging.getLogger("pktmask")
            for handler in pktmask_logger.handlers:
                if (
                    isinstance(handler, logging.StreamHandler)
                    and handler.stream == sys.stdout
                ):
                    # This is console handler
                    handler.setLevel(console_level)

        except Exception as e:
            # If reconfiguration fails, log warning but don't interrupt program
            logging.getLogger("pktmask").warning(
                f"Failed to reconfigure logging system: {e}"
            )

    def log_exception(
        self, logger_name: str, exc: Exception, context: Optional[Dict[str, Any]] = None
    ):
        """Log exception information"""
        logger = self.get_logger(logger_name)
        context_str = ""
        if context:
            context_str = f" Context: {context}"
        logger.error(
            f"Exception occurred: {type(exc).__name__}: {exc}{context_str}",
            exc_info=True,
        )

    def log_performance(
        self, logger_name: str, operation: str, duration: float, **kwargs
    ):
        """Log performance information"""
        logger = self.get_logger(logger_name)
        extra_info = " ".join(f"{k}={v}" for k, v in kwargs.items())
        logger.info(f"Performance: {operation} took {duration:.3f}s {extra_info}")


# Global log manager instance
_logger_manager = PktMaskLogger()


def get_logger(name: str = "root") -> logging.Logger:
    """Convenience function to get logger"""
    return _logger_manager.get_logger(name)


def set_log_level(level: LogLevel):
    """Convenience function to set global log level"""
    _logger_manager.set_level(level)


def reconfigure_logging():
    """Convenience function to reconfigure logging system based on current configuration"""
    _logger_manager.reconfigure_from_config()


def log_exception(
    exc: Exception, logger_name: str = "root", context: Optional[Dict[str, Any]] = None
):
    """Convenience function to log exceptions"""
    _logger_manager.log_exception(logger_name, exc, context)


def log_performance(
    operation: str, duration: float, logger_name: str = "performance", **kwargs
):
    """Convenience function to log performance"""
    _logger_manager.log_performance(logger_name, operation, duration, **kwargs)


# Decorator：Automatically log function execution time
def log_execution_time(logger_name: str = "performance"):
    """Decorator：Automatically log function execution time"""

    def decorator(func):
        import functools
        import time

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                log_performance(func.__name__, duration, logger_name)
                return result
            except Exception:
                duration = time.time() - start_time
                log_performance(f"{func.__name__} (failed)", duration, logger_name)
                raise

        return wrapper

    return decorator
