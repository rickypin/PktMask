import warnings

warnings.warn(
    "pktmask.steps 和 *Step 后缀已废弃，请使用 pktmask.stages 和 *Stage 后缀。",
    DeprecationWarning,
    stacklevel=2
)

# 统一映射到 Stage 实现
from ..stages import (
    DeduplicationStage as DeduplicationStep,
    IpAnonymizationStage as IpAnonymizationStep,
    IntelligentTrimmingStage as IntelligentTrimmingStep,
)

__all__ = [
    'DeduplicationStep',
    'IpAnonymizationStep',
    'IntelligentTrimmingStep',
]

