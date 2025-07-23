"""
应用配置模块

包含PktMask应用的所有配置相关功能。
"""

from .settings import (
    AppConfig,
    UISettings,
    ProcessingSettings,
    LoggingSettings,
    get_app_config,
    reload_app_config,
    save_app_config,
)
from .defaults import (
    DEFAULT_UI_CONFIG,
    DEFAULT_PROCESSING_CONFIG,
    DEFAULT_LOGGING_CONFIG,
    get_default_config_dict,
    get_processor_config,
    is_valid_theme,
    is_valid_log_level,
    is_valid_dedup_algorithm,
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
