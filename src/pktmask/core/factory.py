"""
简化的Factory模块

保留基本的兼容性接口，移除Legacy Steps相关代码。
现代处理器使用ProcessorRegistry系统。
"""

from typing import Dict, Callable, List, TYPE_CHECKING

if TYPE_CHECKING:
    from .pipeline.executor import PipelineExecutor


def create_pipeline(steps_config: list) -> "PipelineExecutor":
    """
    兼容性函数：创建Pipeline实例

    注意：现代系统使用PipelineExecutor，此函数仅为测试兼容性保留
    """
    from .pipeline.executor import PipelineExecutor

    # 返回空配置的PipelineExecutor，实际处理由新系统完成
    return PipelineExecutor({})


# 兼容性存根 - 测试可能需要这些函数存在
def get_step_instance(step_name: str):
    """兼容性存根"""
    raise NotImplementedError(
        "Legacy Steps系统已移除。请使用ProcessorRegistry.get_processor()代替。"
    )


STEP_REGISTRY = {}  # 兼容性存根
