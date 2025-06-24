"""
TCP载荷掩码器辅助函数

提供数据转换、格式化等辅助功能。
"""

from typing import Dict, Any
from ..api.types import MaskingRecipe, PacketMaskInstruction
from ...trim.models.mask_spec import MaskSpec, MaskAfter, MaskRange, KeepAll


def create_masking_recipe_from_dict(data: Dict[str, Any]) -> MaskingRecipe:
    """
    从字典格式创建掩码配方
    
    Args:
        data: 包含配方数据的字典
        
    Returns:
        创建的掩码配方对象
        
    Raises:
        ValueError: 数据格式不正确时
    """
    if not isinstance(data, dict):
        raise ValueError("输入数据必须是字典格式")
    
    # 提取基础信息
    total_packets = data.get("total_packets", 0)
    metadata = data.get("metadata", {})
    instructions_data = data.get("instructions", {})
    
    # 转换指令
    instructions = {}
    for key, instruction_data in instructions_data.items():
        # 解析键（可能是字符串格式的元组）
        if isinstance(key, str):
            # 假设格式为 "index,timestamp"
            parts = key.split(",", 1)
            if len(parts) != 2:
                raise ValueError(f"无效的指令键格式: {key}")
            try:
                index = int(parts[0])
                timestamp = parts[1]
            except ValueError:
                raise ValueError(f"无法解析指令键: {key}")
        elif isinstance(key, (list, tuple)) and len(key) == 2:
            index, timestamp = key
        else:
            raise ValueError(f"无效的指令键类型: {type(key)}")
        
        # 创建掩码规范
        mask_spec = _create_mask_spec_from_dict(instruction_data.get("mask_spec", {}))
        
        # 创建指令
        instruction = PacketMaskInstruction(
            packet_index=instruction_data.get("packet_index", index),
            packet_timestamp=instruction_data.get("packet_timestamp", str(timestamp)),
            payload_offset=instruction_data.get("payload_offset", 0),
            mask_spec=mask_spec,
            metadata=instruction_data.get("metadata", {})
        )
        
        instructions[(index, str(timestamp))] = instruction
    
    return MaskingRecipe(
        instructions=instructions,
        total_packets=total_packets,
        metadata=metadata
    )


def _create_mask_spec_from_dict(data: Dict[str, Any]) -> MaskSpec:
    """从字典创建掩码规范"""
    mask_type = data.get("type", "")
    
    if mask_type == "MaskAfter":
        return MaskAfter(keep_bytes=data.get("keep_bytes", 0))
    elif mask_type == "MaskRange":
        ranges_data = data.get("ranges", [])
        ranges = []
        for range_data in ranges_data:
            if isinstance(range_data, (list, tuple)) and len(range_data) == 2:
                ranges.append((range_data[0], range_data[1]))
            elif isinstance(range_data, dict):
                ranges.append((range_data.get("start", 0), range_data.get("end", 0)))
            else:
                raise ValueError(f"无效的范围数据格式: {range_data}")
        return MaskRange(ranges=ranges)
    elif mask_type == "KeepAll":
        return KeepAll()
    else:
        raise ValueError(f"未知的掩码类型: {mask_type}")


def masking_recipe_to_dict(recipe: MaskingRecipe) -> Dict[str, Any]:
    """
    将掩码配方转换为字典格式
    
    Args:
        recipe: 掩码配方对象
        
    Returns:
        字典格式的配方数据
    """
    instructions_dict = {}
    for (index, timestamp), instruction in recipe.instructions.items():
        key = f"{index},{timestamp}"
        instructions_dict[key] = {
            "packet_index": instruction.packet_index,
            "packet_timestamp": instruction.packet_timestamp,
            "payload_offset": instruction.payload_offset,
            "mask_spec": _mask_spec_to_dict(instruction.mask_spec),
            "metadata": instruction.metadata
        }
    
    return {
        "total_packets": recipe.total_packets,
        "metadata": recipe.metadata,
        "instructions": instructions_dict
    }


def _mask_spec_to_dict(mask_spec: MaskSpec) -> Dict[str, Any]:
    """将掩码规范转换为字典"""
    if isinstance(mask_spec, MaskAfter):
        return {
            "type": "MaskAfter",
            "keep_bytes": mask_spec.keep_bytes
        }
    elif isinstance(mask_spec, MaskRange):
        return {
            "type": "MaskRange", 
            "ranges": [{"start": start, "end": end} for start, end in mask_spec.ranges]
        }
    elif isinstance(mask_spec, KeepAll):
        return {
            "type": "KeepAll"
        }
    else:
        return {
            "type": "Unknown",
            "description": mask_spec.get_description()
        }


def format_timestamp(timestamp: float) -> str:
    """
    格式化时间戳为字符串
    
    Args:
        timestamp: 浮点数时间戳
        
    Returns:
        格式化后的时间戳字符串
    """
    return f"{timestamp:.9f}"


def parse_timestamp(timestamp_str: str) -> float:
    """
    解析时间戳字符串为浮点数
    
    Args:
        timestamp_str: 时间戳字符串
        
    Returns:
        浮点数时间戳
        
    Raises:
        ValueError: 无法解析时间戳时
    """
    try:
        return float(timestamp_str)
    except ValueError:
        raise ValueError(f"无法解析时间戳: {timestamp_str}")


def estimate_recipe_memory_usage(recipe: MaskingRecipe) -> int:
    """
    估算掩码配方的内存使用量（字节）
    
    Args:
        recipe: 掩码配方
        
    Returns:
        估算的内存使用量（字节）
    """
    # 简单估算：每个指令约200字节
    base_size = len(recipe.instructions) * 200
    
    # 元数据大小估算
    metadata_size = len(str(recipe.metadata)) * 2
    
    return base_size + metadata_size 