from importlib import import_module

# 延迟加载，避免不必要的依赖

def __getattr__(name: str):
    if name == "MaskStage":
        module = import_module("pktmask.core.pipeline.stages.mask_payload.stage")
        return getattr(module, name)
    if name == "DedupStage":
        module = import_module("pktmask.core.pipeline.stages.dedup")
        return getattr(module, name)
    if name == "AnonStage":
        module = import_module("pktmask.core.pipeline.stages.anon_ip")
        return getattr(module, name)
    raise AttributeError(name)

__all__ = ["MaskStage", "DedupStage", "AnonStage"] 