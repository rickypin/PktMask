"""
PktMask 适配器模块

统一管理所有适配器，提供简洁的导入接口。
"""

# 适配器版本信息
__version__ = "1.0.0"

# 核心适配器
from .encapsulation_adapter import ProcessingAdapter
from .statistics_adapter import StatisticsDataAdapter

# 异常类
from .adapter_exceptions import (
    AdapterError,
    ConfigurationError,
    MissingConfigError,
    InvalidConfigError,
    DataFormatError,
    InputFormatError,
    OutputFormatError,
    ProcessingError
)

__all__ = [
    # 版本
    '__version__',
    
    # 核心适配器
    'ProcessingAdapter',
    'StatisticsDataAdapter',
    

    
    # 异常类
    'AdapterError',
    'ConfigurationError',
    'MissingConfigError',
    'InvalidConfigError',
    'DataFormatError',
    'InputFormatError',
    'OutputFormatError',
    'ProcessingError',
]
