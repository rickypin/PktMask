from enum import Enum, auto

class PipelineEvents(Enum):
    """Defines the types of events emitted during the pipeline execution."""
    PIPELINE_START = auto()
    PIPELINE_END = auto()
    SUBDIR_START = auto()
    SUBDIR_END = auto()
    FILE_START = auto()
    FILE_END = auto()
    PACKETS_SCANNED = auto()
    STEP_START = auto()
    STEP_END = auto()
    STEP_SUMMARY = auto()
    FILE_RESULT = auto()
    LOG = auto()
    ERROR = auto() 