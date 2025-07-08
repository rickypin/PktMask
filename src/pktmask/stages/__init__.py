import warnings

# 废弃警告
warnings.warn(
    "pktmask.stages 已废弃，请使用 pktmask.core.pipeline.stages 替代。",
    DeprecationWarning,
    stacklevel=2
)

# 重新导入到新实现（带兼容性适配）
from .adapters.dedup_compat import DeduplicationStageCompat as DeduplicationStage
from .adapters.anon_compat import IpAnonymizationStageCompat as IpAnonymizationStage

# 这个还没有对应实现，暂时保持原有
from .trimming import IntelligentTrimmingStage

__all__ = [
    "DeduplicationStage",
    "IpAnonymizationStage", 
    "IntelligentTrimmingStage",
]
