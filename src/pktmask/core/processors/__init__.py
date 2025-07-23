"""
统一的处理器系统

简化的StageBase处理器系统，提供统一的处理器访问接口。
所有处理器都基于StageBase架构，使用标准化配置。
"""

from .registry import ProcessorRegistry

__all__ = [
    "ProcessorRegistry",
]
