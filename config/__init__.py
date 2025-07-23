"""
PktMask 统一配置管理模块

整合了应用配置、模板文件和Item配置，提供统一的配置访问接口。
"""

# 为了保持向后兼容，重新导出原有的配置接口
import sys
from pathlib import Path

# 添加app子目录到Python路径
config_app_path = Path(__file__).parent / "app"
if str(config_app_path) not in sys.path:
    sys.path.insert(0, str(config_app_path))

# 导入配置类和函数
from .app.settings import (
    AppConfig,
    UISettings,
    ProcessingSettings,
    LoggingSettings,
    get_app_config,
    reload_app_config,
    save_app_config,
)
from .app.defaults import (
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
    # Global配置管理
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
