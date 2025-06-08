from enum import Enum, auto

class PipelineEvents(Enum):
    """Defines the types of events emitted during the pipeline execution."""
    # 管道级别事件
    PIPELINE_START = auto()
    PIPELINE_STARTED = auto()  # 别名，为了向后兼容
    PIPELINE_END = auto()
    PIPELINE_COMPLETED = auto()  # 别名，为了向后兼容
    
    # 目录级别事件
    SUBDIR_START = auto()
    SUBDIR_END = auto()
    
    # 文件级别事件
    FILE_START = auto()
    FILE_STARTED = auto()  # 别名，为了向后兼容
    FILE_END = auto()
    FILE_COMPLETED = auto()  # 别名，为了向后兼容
    
    # 步骤级别事件
    STEP_START = auto()
    STEP_STARTED = auto()  # 别名，为了向后兼容
    STEP_END = auto()
    STEP_COMPLETED = auto()  # 别名，为了向后兼容
    STEP_SUMMARY = auto()
    
    # 其他事件
    PACKETS_SCANNED = auto()
    FILE_RESULT = auto()
    LOG = auto()
    ERROR = auto() 