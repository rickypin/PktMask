"""
简化的处理器系统

替代复杂的插件架构，提供简单直观的处理器模式。
"""

from .base_processor import BaseProcessor, ProcessorConfig, ProcessorResult
from .registry import ProcessorRegistry
from .ip_anonymizer import IPAnonymizer
from .deduplicator import Deduplicator
from .trimmer import Trimmer
# NOTE: ProcessorAdapter 已废弃，请使用 ProcessorStageAdapter
# from .pipeline_adapter import ProcessorAdapter, adapt_processors_to_pipeline

__all__ = [
    'BaseProcessor',
    'ProcessorConfig', 
    'ProcessorResult',
    'ProcessorRegistry',
    'IPAnonymizer',
    'Deduplicator',
    'Trimmer',
    # NOTE: ProcessorAdapter 已废弃，请使用 ProcessorStageAdapter
    # 'ProcessorAdapter',
    # 'adapt_processors_to_pipeline'
]
