"""
兼容性适配器模块

为保持向后兼容而设计的适配器集合。
"""

from .anon_compat import IpAnonymizationStageCompat
from .dedup_compat import DeduplicationStageCompat

__all__ = [
    'IpAnonymizationStageCompat',
    'DeduplicationStageCompat',
]
