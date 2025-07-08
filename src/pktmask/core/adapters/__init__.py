"""
适配器模块

提供不同组件间的适配功能，实现跨架构的兼容性。
"""

from .processor_adapter import PipelineProcessorAdapter

__all__ = [
    'PipelineProcessorAdapter',
]
