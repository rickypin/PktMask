"""
TCP载荷掩码器 - 验证器模块

提供掩码配方验证功能，确保输入数据的正确性和一致性。
这是Phase 1.4实现的一部分：API封装和文件处理。
"""

import logging
import os
from typing import List, Optional, Dict
from scapy.all import PcapReader, rdpcap

from .types import MaskingRecipe, PacketMaskInstruction

logger = logging.getLogger(__name__)


def validate_masking_recipe(
    recipe: MaskingRecipe,
    input_file: Optional[str] = None
) -> List[str]:
    """
    验证掩码配方的有效性
    
    执行多层次的验证检查：
    1. 基础数据结构验证
    2. 文件存在性和可读性验证  
    3. 配方与文件内容的一致性验证
    4. 指令合理性检查
    
    Args:
        recipe: 要验证的掩码配方
        input_file: 可选的输入文件路径，用于文件一致性验证
        
    Returns:
        List[str]: 错误信息列表，空列表表示验证通过
    """
    errors = []
    
    try:
        logger.debug("开始验证掩码配方")
        
        # 1. 基础数据结构验证
        basic_errors = _validate_basic_structure(recipe)
        errors.extend(basic_errors)
        
        # 2. 文件验证（如果提供了文件路径）
        if input_file:
            file_errors = _validate_input_file(input_file)
            errors.extend(file_errors)
            
            # 只有文件有效时才进行一致性验证
            if not file_errors:
                consistency_errors = _validate_recipe_file_consistency(recipe, input_file)
                errors.extend(consistency_errors)
        
        # 3. 指令合理性验证
        instruction_errors = _validate_instructions(recipe)
        errors.extend(instruction_errors)
        
        if not errors:
            logger.debug("掩码配方验证通过")
        else:
            logger.warning(f"掩码配方验证失败: {len(errors)}个错误")
        
        return errors
        
    except Exception as e:
        error_msg = f"验证过程中发生异常: {str(e)}"
        logger.error(error_msg)
        return [error_msg]


def validate_packet_instruction(
    instruction: PacketMaskInstruction
) -> List[str]:
    """
    验证单个包掩码指令的有效性
    
    Args:
        instruction: 要验证的包掩码指令
        
    Returns:
        List[str]: 错误信息列表
    """
    errors = []
    
    try:
        # 验证包索引
        if instruction.packet_index < 0:
            errors.append(f"包索引不能为负数: {instruction.packet_index}")
        
        # 验证时间戳格式
        if not instruction.packet_timestamp:
            errors.append("包时间戳不能为空")
        else:
            try:
                float(instruction.packet_timestamp)
            except ValueError:
                errors.append(f"无效的时间戳格式: {instruction.packet_timestamp}")
        
        # 验证载荷偏移
        if instruction.payload_offset < 0:
            errors.append(f"载荷偏移不能为负数: {instruction.payload_offset}")
        elif instruction.payload_offset < 14:  # 最小以太网头部
            errors.append(f"载荷偏移{instruction.payload_offset}过小，可能无法到达TCP载荷")
        elif instruction.payload_offset > 1500:  # 超过标准MTU
            errors.append(f"载荷偏移{instruction.payload_offset}过大，可能超出包长度")
        
        # 验证掩码规范
        if not instruction.mask_spec:
            errors.append("掩码规范不能为空")
        
    except Exception as e:
        errors.append(f"指令验证异常: {str(e)}")
    
    return errors


def check_file_accessibility(file_path: str) -> List[str]:
    """
    检查文件的可访问性
    
    Args:
        file_path: 要检查的文件路径
        
    Returns:
        List[str]: 错误信息列表
    """
    errors = []
    
    if not file_path:
        errors.append("文件路径不能为空")
        return errors
    
    if not os.path.exists(file_path):
        errors.append(f"文件不存在: {file_path}")
        return errors
    
    if not os.path.isfile(file_path):
        errors.append(f"路径不是文件: {file_path}")
        return errors
    
    if not os.access(file_path, os.R_OK):
        errors.append(f"文件不可读: {file_path}")
    
    # 尝试获取文件大小
    try:
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            errors.append(f"文件为空: {file_path}")
        elif file_size > 10 * 1024 * 1024 * 1024:  # 10GB
            errors.append(f"文件过大(>{10}GB): {file_path}")
    except OSError as e:
        errors.append(f"获取文件信息失败: {e}")
    
    return errors


def estimate_memory_usage(
    recipe: MaskingRecipe,
    input_file: Optional[str] = None
) -> Dict[str, int]:
    """
    估算内存使用情况
    
    Args:
        recipe: 掩码配方
        input_file: 输入文件路径
        
    Returns:
        Dict: 内存使用估算信息
    """
    try:
        # 基础内存：配方本身
        instruction_count = len(recipe.instructions)
        recipe_memory = instruction_count * 200  # 假设每个指令约200字节
        
        # 文件相关内存估算
        file_memory = 0
        if input_file and os.path.exists(input_file):
            file_size = os.path.getsize(input_file)
            # 假设需要加载整个文件到内存进行处理
            file_memory = file_size * 2  # 输入+输出
        
        # 总内存估算
        total_memory = recipe_memory + file_memory
        
        return {
            "recipe_memory_bytes": recipe_memory,
            "file_memory_bytes": file_memory,
            "total_memory_bytes": total_memory,
            "total_memory_mb": total_memory // (1024 * 1024)
        }
        
    except Exception as e:
        logger.warning(f"内存估算失败: {e}")
        return {
            "recipe_memory_bytes": 0,
            "file_memory_bytes": 0,
            "total_memory_bytes": 0,
            "total_memory_mb": 0
        }


# ============================================================================
# 私有辅助函数
# ============================================================================

def _validate_basic_structure(recipe: MaskingRecipe) -> List[str]:
    """验证配方的基础数据结构"""
    errors = []
    
    # 检查类型
    if not isinstance(recipe, MaskingRecipe):
        errors.append("配方必须是MaskingRecipe类型")
        return errors
    
    # 检查指令字典
    if not hasattr(recipe, 'instructions'):
        errors.append("配方缺少instructions属性")
        return errors
    
    if not recipe.instructions:
        errors.append("配方中没有任何掩码指令")
    
    # 检查总包数
    if not hasattr(recipe, 'total_packets'):
        errors.append("配方缺少total_packets属性")
    elif recipe.total_packets <= 0:
        errors.append(f"总包数必须大于0，当前值: {recipe.total_packets}")
    
    # 检查指令数量与总包数的关系
    if recipe.instructions and recipe.total_packets:
        if len(recipe.instructions) > recipe.total_packets:
            errors.append(
                f"指令数量({len(recipe.instructions)})不能超过总包数({recipe.total_packets})"
            )
    
    return errors


def _validate_input_file(input_file: str) -> List[str]:
    """验证输入文件"""
    errors = []
    
    # 基础文件检查
    file_errors = check_file_accessibility(input_file)
    errors.extend(file_errors)
    
    if file_errors:
        return errors  # 如果基础检查失败，不进行后续检查
    
    # PCAP文件格式检查
    try:
        # 尝试读取文件头部来验证格式
        with PcapReader(input_file) as reader:
            # 尝试读取第一个包
            try:
                first_packet = next(iter(reader))
                if first_packet is None:
                    errors.append("PCAP文件没有包含数据包")
            except StopIteration:
                errors.append("PCAP文件为空")
            except Exception as e:
                errors.append(f"读取PCAP文件失败: {e}")
                
    except Exception as e:
        errors.append(f"无效的PCAP文件格式: {e}")
    
    return errors


def _validate_recipe_file_consistency(
    recipe: MaskingRecipe,
    input_file: str
) -> List[str]:
    """验证配方与文件内容的一致性"""
    errors = []
    
    try:
        logger.debug(f"验证配方与文件一致性: {input_file}")
        
        # 计算实际包数
        actual_packet_count = 0
        timestamps = {}
        
        with PcapReader(input_file) as reader:
            for index, packet in enumerate(reader):
                actual_packet_count += 1
                timestamps[index] = str(packet.time)
                
                # 限制检查数量，避免大文件性能问题
                if actual_packet_count > 10000:
                    logger.warning("文件包数过多，仅验证前10000个包的一致性")
                    break
        
        # 检查总包数一致性（考虑可能的截断）
        if recipe.total_packets != actual_packet_count and actual_packet_count <= 10000:
            errors.append(
                f"配方总包数({recipe.total_packets})与文件实际包数({actual_packet_count})不一致"
            )
        
        # 检查指令包索引和时间戳
        for (index, timestamp), instruction in recipe.instructions.items():
            if index >= actual_packet_count:
                errors.append(
                    f"指令包索引{index}超出文件包数范围[0, {actual_packet_count-1}]"
                )
            elif index in timestamps:
                # 检查时间戳匹配（允许小的浮点误差）
                actual_timestamp = timestamps[index]
                try:
                    if abs(float(timestamp) - float(actual_timestamp)) > 0.000001:
                        errors.append(
                            f"包{index}时间戳不匹配: 配方'{timestamp}' vs 文件'{actual_timestamp}'"
                        )
                except ValueError:
                    errors.append(f"包{index}时间戳格式错误: '{timestamp}'")
    
    except Exception as e:
        errors.append(f"文件一致性检查失败: {str(e)}")
    
    return errors


def _validate_instructions(recipe: MaskingRecipe) -> List[str]:
    """验证所有指令的合理性"""
    errors = []
    
    instruction_indices = set()
    
    for (index, timestamp), instruction in recipe.instructions.items():
        # 验证单个指令
        instruction_errors = validate_packet_instruction(instruction)
        errors.extend(instruction_errors)
        
        # 检查键的一致性
        if instruction.packet_index != index:
            errors.append(
                f"指令键索引({index})与指令内容索引({instruction.packet_index})不一致"
            )
        
        if instruction.packet_timestamp != timestamp:
            errors.append(
                f"指令键时间戳({timestamp})与指令内容时间戳({instruction.packet_timestamp})不一致"
            )
        
        # 检查重复索引
        if index in instruction_indices:
            errors.append(f"包索引{index}有重复的指令")
        else:
            instruction_indices.add(index)
    
    return errors 