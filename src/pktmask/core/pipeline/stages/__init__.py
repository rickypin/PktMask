# 直接导入统一版本，消除包装层
from pktmask.core.pipeline.stages.deduplication_unified import (
    UnifiedDeduplicationStage,
)
from pktmask.core.pipeline.stages.ip_anonymization_unified import (
    UnifiedIPAnonymizationStage,
)
from pktmask.core.pipeline.stages.mask_payload_v2.stage import (
    NewMaskPayloadStage,
)

__all__ = ["NewMaskPayloadStage", "UnifiedDeduplicationStage", "UnifiedIPAnonymizationStage"]
