"""
PktMask 适配器模块

统一管理所有适配器，提供简洁的导入接口。
"""

# 适配器版本信息
__version__ = "1.0.0"

# 核心适配器
# PipelineProcessorAdapter已删除，直接使用StageBase架构
from .encapsulation_adapter import ProcessingAdapter
from .statistics_adapter import StatisticsDataAdapter

# 兼容性适配器已移除 - 直接使用 core.pipeline.stages 中的实现

# 异常类
from .adapter_exceptions import (
    AdapterError,
    ConfigurationError,
    MissingConfigError,
    InvalidConfigError,
    DataFormatError,
    InputFormatError,
    OutputFormatError,
    CompatibilityError,
    VersionMismatchError,
    FeatureNotSupportedError,
    ProcessingError,
    TimeoutError,
    ResourceError
)

__all__ = [
    # 版本
    '__version__',
    
    # 核心适配器
    'ProcessingAdapter',
    'StatisticsDataAdapter',
    
    # 兼容性适配器已移除
    
    # 异常类
    'AdapterError',
    'ConfigurationError',
    'MissingConfigError',
    'InvalidConfigError',
    'DataFormatError',
    'InputFormatError',
    'OutputFormatError',
    'CompatibilityError',
    'VersionMismatchError',
    'FeatureNotSupportedError',
    'ProcessingError',
    'TimeoutError',
    'ResourceError',
]
