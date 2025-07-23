#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
配置管理模块 - 兼容性代理

此模块现在作为兼容性代理，重定向到统一的配置目录。
新的配置文件位于项目根目录的 config/ 目录中。
"""

import warnings
import sys
from pathlib import Path

# 发出迁移警告
warnings.warn(
    "从 src.pktmask.config 导入配置已废弃。请使用 'from config import ...' 代替。",
    DeprecationWarning,
    stacklevel=2,
)

# 添加新配置目录到Python路径
project_root = Path(__file__).parent.parent.parent.parent
config_path = project_root / "config"
if str(config_path) not in sys.path:
    sys.path.insert(0, str(config_path))

# 重新导出配置接口
try:
    from config.app.settings import (
        AppConfig,
        UISettings,
        ProcessingSettings,
        LoggingSettings,
        get_app_config,
        reload_app_config,
        save_app_config,
    )
    from config.app.defaults import (
        DEFAULT_UI_CONFIG,
        DEFAULT_PROCESSING_CONFIG,
        DEFAULT_LOGGING_CONFIG,
        get_default_config_dict,
        get_processor_config,
        is_valid_theme,
        is_valid_log_level,
        is_valid_dedup_algorithm,
    )
except ImportError:
    # 如果无法导入，直接从本地导入
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
