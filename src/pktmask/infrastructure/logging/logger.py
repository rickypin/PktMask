#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PktMask 日志系统
提供统一的日志管理功能
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional

from ...common.constants import FileConstants
from ...common.enums import LogLevel


class PktMaskLogger:
    """PktMask应用程序日志管理器"""

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
        """设置根日志记录器"""
        root_logger = logging.getLogger("pktmask")
        root_logger.setLevel(logging.DEBUG)

        # 避免重复添加handler
        if root_logger.handlers:
            return

        # 尝试从配置获取日志级别
        console_level = logging.INFO  # 默认级别
        try:
            from ...config import get_app_config

            config = get_app_config()
            level_str = config.logging.log_level.upper()
            console_level = getattr(logging, level_str, logging.INFO)
        except Exception:
            # 如果配置获取失败，使用默认级别
            pass

        # 控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(console_level)
        console_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

        # 文件处理器
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
            # 如果文件日志设置失败，至少保证控制台日志可用
            root_logger.warning(f"Failed to setup file logging: {e}")

        self._loggers["root"] = root_logger

    def get_logger(self, name: str) -> logging.Logger:
        """获取指定名称的日志记录器"""
        if name not in self._loggers:
            logger = logging.getLogger(f"pktmask.{name}")
            self._loggers[name] = logger
        return self._loggers[name]

    def set_level(self, level: LogLevel):
        """设置日志级别"""
        for logger in self._loggers.values():
            logger.setLevel(level.value)

    def reconfigure_from_config(self):
        """根据配置重新配置日志系统"""
        try:
            from ...config import get_app_config

            config = get_app_config()

            # 获取配置的日志级别
            level_str = config.logging.log_level.upper()
            console_level = getattr(logging, level_str, logging.INFO)

            # 更新所有现有处理器的级别
            pktmask_logger = logging.getLogger("pktmask")
            for handler in pktmask_logger.handlers:
                if (
                    isinstance(handler, logging.StreamHandler)
                    and handler.stream == sys.stdout
                ):
                    # 这是控制台处理器
                    handler.setLevel(console_level)

        except Exception as e:
            # 如果重新配置失败，记录警告但不中断程序
            logging.getLogger("pktmask").warning(
                f"Failed to reconfigure logging system: {e}"
            )

    def log_exception(
        self, logger_name: str, exc: Exception, context: Optional[Dict[str, Any]] = None
    ):
        """记录异常信息"""
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
        """记录性能信息"""
        logger = self.get_logger(logger_name)
        extra_info = " ".join(f"{k}={v}" for k, v in kwargs.items())
        logger.info(f"Performance: {operation} took {duration:.3f}s {extra_info}")


# 全局日志管理器实例
_logger_manager = PktMaskLogger()


def get_logger(name: str = "root") -> logging.Logger:
    """获取日志记录器的便利函数"""
    return _logger_manager.get_logger(name)


def set_log_level(level: LogLevel):
    """设置全局日志级别的便利函数"""
    _logger_manager.set_level(level)


def reconfigure_logging():
    """根据当前配置重新配置日志系统的便利函数"""
    _logger_manager.reconfigure_from_config()


def log_exception(
    exc: Exception, logger_name: str = "root", context: Optional[Dict[str, Any]] = None
):
    """记录异常的便利函数"""
    _logger_manager.log_exception(logger_name, exc, context)


def log_performance(
    operation: str, duration: float, logger_name: str = "performance", **kwargs
):
    """记录性能的便利函数"""
    _logger_manager.log_performance(logger_name, operation, duration, **kwargs)


# 装饰器：自动记录函数执行时间
def log_execution_time(logger_name: str = "performance"):
    """装饰器：自动记录函数执行时间"""

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
