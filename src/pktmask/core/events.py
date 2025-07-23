from enum import Enum, auto


class PipelineEvents(Enum):
    """Defines the types of events emitted during the pipeline execution."""

    # Pipeline level events
    PIPELINE_START = auto()
    PIPELINE_STARTED = auto()  # Alias for backward compatibility
    PIPELINE_END = auto()
    PIPELINE_COMPLETED = auto()  # Alias for backward compatibility

    # Directory level events
    SUBDIR_START = auto()
    SUBDIR_END = auto()

    # File level events
    FILE_START = auto()
    FILE_STARTED = auto()  # Alias for backward compatibility
    FILE_END = auto()
    FILE_COMPLETED = auto()  # Alias for backward compatibility

    # Step level events
    STEP_START = auto()
    STEP_STARTED = auto()  # Alias for backward compatibility
    STEP_END = auto()
    STEP_COMPLETED = auto()  # Alias for backward compatibility
    STEP_SUMMARY = auto()

    # Other events
    PACKETS_SCANNED = auto()
    FILE_RESULT = auto()
    LOG = auto()
    ERROR = auto()
