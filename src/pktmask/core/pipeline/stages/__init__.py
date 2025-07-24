# Direct import of unified versions, eliminating wrapper layers
from pktmask.core.pipeline.stages.deduplication_unified import (
    DeduplicationStage,
)
from pktmask.core.pipeline.stages.ip_anonymization_unified import (
    AnonymizationStage,
)
from pktmask.core.pipeline.stages.mask_payload_v2.stage import (
    MaskingStage,
)

__all__ = ["MaskingStage", "DeduplicationStage", "AnonymizationStage"]
