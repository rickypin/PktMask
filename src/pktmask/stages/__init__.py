"""
统一的处理阶段导入 - 直接使用新实现

兼容层已移除，直接导入 core.pipeline.stages 中的实现。
"""

# 直接导入新的pipeline stages实现
from ..core.pipeline.stages.dedup import DeduplicationStage
from ..core.pipeline.stages.anon_ip import AnonStage as IpAnonymizationStage
from ..core.pipeline.stages.mask_payload import MaskStage as IntelligentTrimmingStage

__all__ = [
    "DeduplicationStage",
    "IpAnonymizationStage",
    "IntelligentTrimmingStage",
]
