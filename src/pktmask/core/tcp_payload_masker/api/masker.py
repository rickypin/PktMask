"""
TCP载荷掩码器 - 主API实现

提供基于包级指令的掩码处理API，支持完全独立的掩码执行。
这是Phase 1.4的核心实现：API封装和文件处理。
"""

import logging
import os
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from scapy.all import PcapReader, wrpcap, Ether, raw

from .types import PacketMaskInstruction, MaskingRecipe, PacketMaskingResult
from .validator import validate_masking_recipe
from ..core.consistency import ConsistencyVerifier
from ..utils.stats import MaskingStatistics

logger = logging.getLogger(__name__)


def mask_pcap_with_instructions(
    input_file: str,
    output_file: str,
    masking_recipe: MaskingRecipe,
    verify_consistency: bool = True,
    progress_callback: Optional[callable] = None
) -> PacketMaskingResult:
    """
    使用包级指令对PCAP文件进行掩码处理
    
    这是TCP载荷掩码器的主要API入口，接收精确的包级掩码指令，
    执行纯字节级的掩码操作，完全不依赖协议解析。
    
    Args:
        input_file: 输入PCAP文件路径
        output_file: 输出PCAP文件路径  
        masking_recipe: 包含所有掩码指令的配方
        verify_consistency: 是否验证输入输出一致性
        progress_callback: 进度回调函数(current, total)
        
    Returns:
        PacketMaskingResult: 处理结果，包含统计信息和错误信息
        
    Raises:
        FileNotFoundError: 输入文件不存在
        ValueError: 参数验证失败
        IOError: 文件操作失败
    """
    logger.info(f"开始掩码处理: {input_file} -> {output_file}")
    logger.info(f"掩码配方包含 {len(masking_recipe.instructions)} 个指令")
    
    # 初始化结果对象
    result = PacketMaskingResult(
        success=False,
        processed_packets=0,
        modified_packets=0,
        output_file="",
        errors=[],
        statistics={}
    )
    
    try:
        # 1. 验证输入参数
        validation_errors = _validate_inputs(input_file, output_file, masking_recipe)
        if validation_errors:
            result.errors.extend(validation_errors)
            logger.error(f"输入验证失败: {validation_errors}")
            return result
        
        # 2. 验证掩码配方
        recipe_errors = validate_masking_recipe(masking_recipe, input_file)
        if recipe_errors:
            result.errors.extend(recipe_errors)
            logger.error(f"掩码配方验证失败: {recipe_errors}")
            return result
        
        # 3. 创建输出目录
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        # 4. 执行掩码处理
        processing_result = _process_packets(
            input_file, 
            output_file, 
            masking_recipe,
            progress_callback
        )
        
        # 5. 更新结果
        result.processed_packets = processing_result['processed_packets']
        result.modified_packets = processing_result['modified_packets']
        result.output_file = output_file
        result.statistics = processing_result['statistics']
        
        # 6. 一致性验证（如果启用）
        if verify_consistency:
            logger.info("开始一致性验证...")
            consistency_errors = _verify_file_consistency(
                input_file, 
                output_file, 
                masking_recipe
            )
            result.errors.extend(consistency_errors)
            if consistency_errors:
                logger.warning(f"一致性验证发现问题: {consistency_errors}")
        
        # 7. 设置成功状态
        result.success = len(result.errors) == 0
        
        if result.success:
            logger.info(f"掩码处理成功完成: 处理 {result.processed_packets} 个包，修改 {result.modified_packets} 个包")
        else:
            logger.error(f"掩码处理失败: {result.errors}")
            
    except Exception as e:
        logger.exception(f"掩码处理过程中发生异常: {e}")
        result.errors.append(f"处理异常: {str(e)}")
        result.success = False
    
    return result


def create_masking_recipe_from_dict(
    instructions_dict: Dict[str, Dict]
) -> MaskingRecipe:
    """
    【已废弃】从字典格式创建掩码配方
    
    注意：此函数已废弃，因为依赖的 BlindPacketMasker 已被移除。
    请使用 utils.helpers.create_masking_recipe_from_dict 替代，
    或直接使用新的智能处理器模式（processor_adapter）。
    
    Args:
        instructions_dict: 指令字典，键为"index_timestamp"格式
        
    Returns:
        MaskingRecipe: 掩码配方对象
        
    Raises:
        NotImplementedError: 此函数已被废弃
    """
    raise NotImplementedError(
        "create_masking_recipe_from_dict 已废弃（BlindPacketMasker 已移除）。"
        "请使用 pktmask.core.tcp_payload_masker.utils.helpers.create_masking_recipe_from_dict 替代，"
        "或使用新的智能处理器模式（processor_adapter）进行自动协议分析。"
    )


def _validate_inputs(
    input_file: str, 
    output_file: str, 
    masking_recipe: MaskingRecipe
) -> List[str]:
    """验证API输入参数"""
    errors = []
    
    # 检查输入文件
    if not input_file:
        errors.append("输入文件路径不能为空")
    elif not os.path.exists(input_file):
        errors.append(f"输入文件不存在: {input_file}")
    elif not os.path.isfile(input_file):
        errors.append(f"输入路径不是文件: {input_file}")
    
    # 检查输出文件路径
    if not output_file:
        errors.append("输出文件路径不能为空")
    else:
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir, exist_ok=True)
            except OSError as e:
                errors.append(f"无法创建输出目录 {output_dir}: {e}")
    
    # 检查掩码配方
    if not isinstance(masking_recipe, MaskingRecipe):
        errors.append("掩码配方必须是MaskingRecipe类型")
    elif not masking_recipe.instructions:
        errors.append("掩码配方不能为空")
    
    return errors


def _process_packets(
    input_file: str,
    output_file: str, 
    masking_recipe: MaskingRecipe,
    progress_callback: Optional[callable] = None
) -> Dict:
    """
    执行核心的包处理逻辑
    
    Returns:
        处理统计信息字典
    """
    # BlindPacketMasker 已被移除，此函数已废弃
    raise NotImplementedError("BlindPacketMasker 已被移除，此API函数已废弃")
    modified_packets = []
    
    try:
        # 预估总包数（用于进度回调）
        total_packets = masking_recipe.total_packets
        processed_count = 0
        
        logger.info(f"开始处理PCAP文件，预估包数: {total_packets}")
        
        # 逐包处理
        with PcapReader(input_file) as pcap_reader:
            for packet_index, packet in enumerate(pcap_reader):
                try:
                    # 处理单个包
                    processed_bytes, is_modified = masker.process_packet(packet_index, packet)
                    
                    if is_modified and processed_bytes is not None:
                        # 包被修改了，需要重新构造
                        modified_packet = Ether(processed_bytes)
                        # 关键修复：从原始包中复制高精度时间戳
                        modified_packet.time = packet.time
                        modified_packets.append(modified_packet)
                        # 注意：不在这里计数，BlindPacketMasker内部已经计数了
                        logger.debug(f"包 {packet_index} 已被修改")
                    else:
                        # 包未修改
                        modified_packets.append(packet)
                    
                    # 注意：不在这里计数，BlindPacketMasker内部已经计数了
                    processed_count += 1
                    
                    # 进度回调
                    if progress_callback and processed_count % 100 == 0:
                        progress_callback(processed_count, total_packets)
                        
                except Exception as e:
                    logger.warning(f"处理包 {packet_index} 时出错: {e}")
                    # 保留原包
                    modified_packets.append(packet)
                    # 错误包计数仍然需要在BlindPacketMasker内部处理
                    # 这里只需要增加本地计数用于进度回调
                    processed_count += 1
        
        # 写入输出文件
        logger.info(f"写入输出文件: {output_file}")
        wrpcap(output_file, modified_packets)
        
        # 最终进度回调
        if progress_callback:
            progress_callback(processed_count, total_packets)
        
        logger.info(f"包处理完成: 处理 {masker.stats.processed_packets} 个包，修改 {masker.stats.modified_packets} 个包")
        
        return {
            'processed_packets': masker.stats.processed_packets,
            'modified_packets': masker.stats.modified_packets,
            'statistics': masker.stats.to_dict()
        }
        
    except Exception as e:
        logger.error(f"处理包时发生异常: {e}")
        raise


def _verify_file_consistency(
    input_file: str,
    output_file: str, 
    masking_recipe: MaskingRecipe
) -> List[str]:
    """验证输入输出文件的一致性"""
    try:
        verifier = ConsistencyVerifier()
        return verifier.verify_files(input_file, output_file, masking_recipe)
    except Exception as e:
        logger.warning(f"一致性验证过程中出错: {e}")
        return [f"一致性验证失败: {str(e)}"]


# 辅助函数
def get_api_version() -> str:
    """获取API版本信息"""
    return "1.0.0"


def get_supported_formats() -> List[str]:
    """获取支持的文件格式"""
    return ["pcap", "pcapng"]


def estimate_processing_time(
    input_file: str, 
    masking_recipe: MaskingRecipe
) -> float:
    """
    估算处理时间（秒）
    
    基于文件大小和指令数量的简单估算
    """
    try:
        file_size_mb = os.path.getsize(input_file) / (1024 * 1024)
        instruction_count = len(masking_recipe.instructions)
        
        # 简单的估算公式：基于文件大小和指令数量
        # 假设每MB需要0.5秒，每个指令增加0.001秒
        estimated_time = file_size_mb * 0.5 + instruction_count * 0.001
        return max(estimated_time, 0.1)  # 最少0.1秒
        
    except Exception:
        return 10.0  # 默认估算10秒 