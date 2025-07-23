from .base_stage import StageBase  # noqa: F401
from .executor import PipelineExecutor  # noqa: F401
from .models import PacketList, ProcessResult, StageStats  # noqa: F401

__all__ = [
    "PacketList",
    "StageStats",
    "ProcessResult",
    "StageBase",
    "PipelineExecutor",
]

# ---------------------------------------------------------------------------
# 向后兼容别名
# ---------------------------------------------------------------------------


class Pipeline(PipelineExecutor):
    """已废弃别名，兼容旧测试/代码。"""

    pass


__all__.append("Pipeline")
