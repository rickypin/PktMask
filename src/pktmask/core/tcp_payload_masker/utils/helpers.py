"""
TCP载荷掩码器辅助函数

提供数据转换、格式化等辅助功能。
"""

from typing import Dict, Any, List
from ..api.types import MaskingRecipe, PacketMaskInstruction, KeepAll, MaskAfter, MaskRange

# 兼容旧工具函数的类型检查（避免 NameError）
try:
    from ...trim.models.mask_spec import MaskSpec as _LegacyMaskSpec  # type: ignore
except Exception:  # pragma: no cover
    _LegacyMaskSpec = object  # Fallback placeholder

# 无论导入是否成功，都暴露 `MaskSpec` 名称供类型注解解析
MaskSpec = _LegacyMaskSpec  # type: ignore  # noqa: N816


def create_masking_recipe_from_dict(data: Dict[str, Any]) -> MaskingRecipe:
    """根据 JSON 字典创建 ``MaskingRecipe`` 实例。

    该实现支持两种主流格式：

    1. **列表格式** （推荐，见 ``config/samples/*.json``）：

       ```json
       {
         "total_packets": 10,
         "instructions": [
           {"packet_index": 1, "mask_spec_type": "MaskAfter", ...},
           {"packet_index": 1, "mask_spec_type": "MaskRange", ...}
         ]
       }
       ```

    2. **旧版字典格式** （键为 "index,timestamp" 的字符串或元组）。

    Args:
        data: 解析后的 JSON / YAML 字典。

    Returns:
        MaskingRecipe 对象，可直接被 ``BlindPacketMasker`` 使用。
    """

    if not isinstance(data, dict):
        raise ValueError("配方数据必须是字典格式")

    total_packets: int = int(data.get("total_packets", 0))
    metadata: Dict[str, Any] = data.get("metadata", {})

    packet_instructions: Dict[int, List[PacketMaskInstruction]] = {}

    raw_instructions = data.get("instructions", [])

    # ------------------------------------------------------------------
    # 新版格式：列表
    # ------------------------------------------------------------------
    if isinstance(raw_instructions, list):
        for instr_data in raw_instructions:
            if not isinstance(instr_data, dict):
                raise ValueError("指令必须是字典对象")

            pkt_idx = int(instr_data.get("packet_index", -1))
            if pkt_idx < 0:
                raise ValueError("packet_index 缺失或非法")

            mask_spec_type = instr_data.get("mask_spec_type")
            mask_params = instr_data.get("mask_spec_params", {}) or {}

            instruction_obj = _create_instruction(mask_spec_type, mask_params)

            packet_instructions.setdefault(pkt_idx, []).append(instruction_obj)

    # ------------------------------------------------------------------
    # 旧版格式：字典（键为 index,timestamp）
    # ------------------------------------------------------------------
    elif isinstance(raw_instructions, dict):
        for key, instr_data in raw_instructions.items():
            # 解析键格式 "index,timestamp" → index
            if isinstance(key, str):
                try:
                    pkt_idx = int(key.split(",", 1)[0])
                except Exception as exc:  # pylint: disable=broad-except
                    raise ValueError(f"无法解析指令键 '{key}': {exc}") from exc
            elif isinstance(key, (list, tuple)) and len(key) >= 1:
                pkt_idx = int(key[0])
            else:
                raise ValueError(f"未知的指令键类型: {type(key)}")

            mask_spec_type = instr_data.get("mask_spec_type") or instr_data.get("mask_type")
            mask_params = (
                instr_data.get("mask_spec_params")
                or instr_data.get("mask_params")
                or {}
            )

            instruction_obj = _create_instruction(mask_spec_type, mask_params)

            packet_instructions.setdefault(pkt_idx, []).append(instruction_obj)
    else:
        raise ValueError("'instructions' 字段必须为列表或字典")

    return MaskingRecipe(
        total_packets=total_packets,
        packet_instructions=packet_instructions,
        metadata=metadata,
    )


def _create_instruction(mask_spec_type: str, params: Dict[str, Any]) -> PacketMaskInstruction:
    """根据类型字符串和参数创建具体的掩码指令对象。"""

    if mask_spec_type == "KeepAll":
        return KeepAll()
    if mask_spec_type == "MaskAll":
        return MaskAfter(keep_bytes=0)  # MaskAll 等价于 keep_bytes=0
    if mask_spec_type == "MaskAfter":
        keep_bytes = int(params.get("keep_bytes", 0))
        return MaskAfter(keep_bytes=keep_bytes)
    if mask_spec_type == "MaskRange":
        ranges = params.get("ranges", [])
        if not ranges:
            raise ValueError("MaskRange 指令需要提供 'ranges'")

        # MaskRange (api.types) 只支持单区间，若给多个区间则拆成多个指令
        first_range = ranges[0]
        if isinstance(first_range, dict):
            start = int(first_range.get("start", 0))
            end = int(first_range.get("end", 0))
        else:
            # 假设为列表/元组
            start, end = int(first_range[0]), int(first_range[1])

        return MaskRange(start=start, end=end)

    raise ValueError(f"未知的 mask_spec_type: {mask_spec_type}")


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