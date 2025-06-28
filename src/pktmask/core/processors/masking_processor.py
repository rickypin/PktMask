from warnings import warn

# ... existing code ...
from .enhanced_trimmer import EnhancedTrimmer


class MaskingProcessor(EnhancedTrimmer):
    """新版官方载荷掩码处理器，功能与EnhancedTrimmer相同。

    该类作为`EnhancedTrimmer`的替代名称，后者将逐步弃用。
    """

    # 仅重载显示名称与描述，其他逻辑沿用父类

    def get_display_name(self) -> str:  # type: ignore[override]
        return "Mask Payloads"

    def get_description(self) -> str:  # type: ignore[override]
        return (
            "智能载荷掩码处理器 (原 EnhancedTrimmer)，"
            "支持多阶段裁切并向后兼容旧接口。"
        ) 