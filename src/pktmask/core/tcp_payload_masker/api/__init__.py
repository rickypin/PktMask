"""
TCP载荷掩码器API模块

提供基于包级指令的独立掩码执行接口。
"""

from .types import (
    PacketMaskInstruction,
    MaskingRecipe,
    PacketMaskingResult
)

# API函数将在Phase 1.3-1.4中实现
# from .masker import (
#     mask_pcap_with_instructions,
#     validate_masking_recipe,
#     create_masking_recipe_from_dict
# )

__all__ = [
    # 数据类型
    "PacketMaskInstruction", 
    "MaskingRecipe",
    "PacketMaskingResult",
    
    # API函数 - Phase 1.3-1.4中实现
    # "mask_pcap_with_instructions",
    # "validate_masking_recipe", 
    # "create_masking_recipe_from_dict"
] 