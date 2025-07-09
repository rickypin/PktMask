"""
适配器模块

提供新旧数据模型之间的转换适配器，确保向后兼容性。
"""

from .statistics_adapter import StatisticsDataAdapter

__all__ = [
    'StatisticsDataAdapter'
]