"""
PktMask 适配器模块

统一管理所有适配器，提供简洁的导入接口。
"""

# 适配器版本信息
__version__ = "1.0.0"

# 核心适配器
from .processor_adapter import PipelineProcessorAdapter
from .encapsulation_adapter import ProcessingAdapter
from .event_adapter import EventDataAdapter
from .statistics_adapter import StatisticsDataAdapter

# 兼容性适配器
from .compatibility.anon_compat import IpAnonymizationStageCompat
from .compatibility.dedup_compat import DeduplicationStageCompat

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
    'PipelineProcessorAdapter',
    'ProcessingAdapter',
    'EventDataAdapter',
    'StatisticsDataAdapter',
    
    # 兼容性适配器
    'IpAnonymizationStageCompat',
    'DeduplicationStageCompat',
    
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
