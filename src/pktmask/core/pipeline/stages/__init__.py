from importlib import import_module

# 延迟加载，避免不必要的依赖

def __getattr__(name: str):
    if name == "MaskStage":
        # 直接使用新版双模块架构实现
        module = import_module("pktmask.core.pipeline.stages.mask_payload_v2.stage")
        return getattr(module, "NewMaskPayloadStage")
    if name == "DedupStage":
        module = import_module("pktmask.core.pipeline.stages.dedup")
        return getattr(module, name)
    if name == "AnonStage":
        module = import_module("pktmask.core.pipeline.stages.anon_ip")
        return getattr(module, name)
    raise AttributeError(name)

__all__ = ["MaskStage", "DedupStage", "AnonStage"] 