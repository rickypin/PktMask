from functools import partial
from typing import Dict, Callable, List, TYPE_CHECKING

if TYPE_CHECKING:
    from .pipeline import Pipeline

from .strategy import AnonymizationStrategy, HierarchicalAnonymizationStrategy
from ..steps import DeduplicationStep, IpAnonymizationStep, IntelligentTrimmingStep
from ..utils.reporting import FileReporter

# 使用 functools.partial 来处理需要复杂初始化的步骤，这比 lambda 更易于 introspect
STEP_REGISTRY: Dict[str, Callable[[], 'ProcessingStep']] = {
    "dedup_packet": DeduplicationStep,
    "trim_packet": IntelligentTrimmingStep,
    "mask_ip": lambda: IpAnonymizationStep(
        strategy=HierarchicalAnonymizationStrategy(), 
        reporter=FileReporter()
    )
}

def get_step_instance(step_name: str) -> 'ProcessingStep':
    """
    工厂函数，根据名称创建并返回一个处理步骤的实例。
    """
    builder = STEP_REGISTRY.get(step_name)
    
    if not builder:
        raise ValueError(f"Unknown processing step: {step_name}")
    
    # 调用构造函数或lambda函数来创建实例
    return builder()

def create_pipeline(steps_config: list) -> "Pipeline":
    step_map = {
        "dedup_packet": DeduplicationStep,
        "trim_packet": IntelligentTrimmingStep,
        "mask_ip": IpAnonymizationStep,
    }
    # ... existing code ... 