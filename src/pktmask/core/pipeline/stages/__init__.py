# Direct import of unified versions, eliminating wrapper layers
from pktmask.core.pipeline.stages.deduplication_stage import (
    DeduplicationStage,
)
from pktmask.core.pipeline.stages.anonymization_stage import (
    AnonymizationStage,
)
from pktmask.core.pipeline.stages.masking_stage.stage import (
    MaskingStage,
)

__all__ = ["MaskingStage", "DeduplicationStage", "AnonymizationStage"]
