#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
配置管理模块

统一的配置管理系统，提供应用程序配置、默认值和验证功能。
"""

# 从本地模块导出配置接口
from .defaults import (
    DEFAULT_LOGGING_CONFIG,
    DEFAULT_PROCESSING_CONFIG,
    DEFAULT_UI_CONFIG,
    get_default_config_dict,
    get_processor_config,
    is_valid_dedup_algorithm,
    is_valid_log_level,
    is_valid_theme,
)
from .settings import (
    AppConfig,
    LoggingSettings,
    ProcessingSettings,
    UISettings,
    get_app_config,
    reload_app_config,
    save_app_config,
)

__all__ = [
    # 主要配置类
    "AppConfig",
    "UISettings",
    "ProcessingSettings",
    "LoggingSettings",
    # 全局配置管理
    "get_app_config",
    "reload_app_config",
    "save_app_config",
    # 默认值和常量
    "DEFAULT_UI_CONFIG",
    "DEFAULT_PROCESSING_CONFIG",
    "DEFAULT_LOGGING_CONFIG",
    "get_default_config_dict",
    "get_processor_config",
    # 验证函数
    "is_valid_theme",
    "is_valid_log_level",
    "is_valid_dedup_algorithm",
]
