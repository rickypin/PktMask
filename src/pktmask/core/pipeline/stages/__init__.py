# 直接导入具体类，简化导入机制
from pktmask.core.pipeline.stages.mask_payload_v2.stage import (
    NewMaskPayloadStage as MaskStage,
)
from pktmask.core.pipeline.stages.dedup import DeduplicationStage
from pktmask.core.pipeline.stages.ip_anonymization_unified import (
    UnifiedIPAnonymizationStage as AnonStage,
)

__all__ = ["MaskStage", "DeduplicationStage", "AnonStage"]
