from pktmask.core.ip_processor import IpAnonymizationStep
from pktmask.core.strategy import HierarchicalAnonymizationStrategy
from pktmask.utils.pcap_dedup import DeduplicationStep
from pktmask.utils.reporting import FileReporter

# 使用 lambda 来处理需要复杂初始化的步骤
STEP_REGISTRY = {
    "remove_dupes": DeduplicationStep,
    "mask_ip": lambda: IpAnonymizationStep(
        strategy=HierarchicalAnonymizationStrategy(),
        reporter=FileReporter()
    )
}

def create_step(name: str):
    """
    根据名称从注册表创建并返回一个处理步骤实例。

    Args:
        name (str): 步骤的唯一标识符 (e.g., 'deduplicate').

    Returns:
        一个 ProcessingStep 的实例。
        
    Raises:
        ValueError: 如果请求的名称在注册表中不存在。
    """
    builder = STEP_REGISTRY.get(name)
    if not builder:
        raise ValueError(f"Unknown processing step: {name}")
    
    # 调用构造函数或lambda函数来创建实例
    return builder() 