from ..stages import (
    DeduplicationStage as DeduplicationStep,
    IpAnonymizationStage as IpAnonymizationStep,
    IntelligentTrimmingStage as IntelligentTrimmingStep,
)

import warnings
warnings.warn(
    "pktmask.steps is deprecated, use pktmask.stages", 
    DeprecationWarning
)

