"""
TCP载荷掩码器 - 一致性验证器

提供输入输出文件一致性验证功能，确保掩码操作的正确性。
这是Phase 1.4实现的一部分：API封装和文件处理。
"""

import logging
import os
from typing import List, Dict, Tuple, Optional
from scapy.all import PcapReader, rdpcap, raw

from .api.types import MaskingRecipe, PacketMaskInstruction
from ..trim.models.mask_spec import MaskAfter, MaskRange, KeepAll

logger = logging.getLogger(__name__)


class ConsistencyVerifier:
    """一致性验证器
    
    验证输入输出文件在除掩码区域外的其他部分保持完全一致。
    """
    
    def __init__(self):
        self.verification_errors: List[str] = []
        self.statistics = {
            'total_packets': 0,
            'verified_packets': 0,
            'modified_packets': 0,
            'error_packets': 0,
            'skipped_packets': 0
        }
    
    def verify_files(
        self,
        input_file: str,
        output_file: str,
        masking_recipe: MaskingRecipe,
        max_packets: Optional[int] = None
    ) -> List[str]:
        """
        验证输入输出文件的一致性
        
        Args:
            input_file: 输入文件路径
            output_file: 输出文件路径  
            masking_recipe: 使用的掩码配方
            max_packets: 最大验证包数（None表示验证所有包）
            
        Returns:
            List[str]: 发现的不一致错误列表
        """
        logger.info(f"开始验证文件一致性: {input_file} vs {output_file}")
        
        self.verification_errors = []
        self._reset_statistics()
        
        try:
            # 1. 基础文件检查
            basic_errors = self._verify_basic_files(input_file, output_file)
            if basic_errors:
                self.verification_errors.extend(basic_errors)
                return self.verification_errors
            
            # 2. 包级别一致性验证
            packet_errors = self._verify_packet_consistency(
                input_file, 
                output_file, 
                masking_recipe,
                max_packets
            )
            self.verification_errors.extend(packet_errors)
            
            # 3. 记录验证结果
            self._log_verification_results()
            
            return self.verification_errors
            
        except Exception as e:
            error_msg = f"一致性验证过程中发生异常: {str(e)}"
            logger.error(error_msg)
            self.verification_errors.append(error_msg)
            return self.verification_errors
    
    def get_verification_statistics(self) -> Dict:
        """获取验证统计信息"""
        return self.statistics.copy()
    
    def _verify_basic_files(self, input_file: str, output_file: str) -> List[str]:
        """验证文件基础信息"""
        errors = []
        
        # 检查输出文件是否存在
        if not os.path.exists(output_file):
            errors.append(f"输出文件不存在: {output_file}")
            return errors
        
        # 检查文件可读性
        if not os.access(input_file, os.R_OK):
            errors.append(f"输入文件不可读: {input_file}")
        
        if not os.access(output_file, os.R_OK):
            errors.append(f"输出文件不可读: {output_file}")
        
        return errors
    
    def _verify_packet_consistency(
        self,
        input_file: str,
        output_file: str,
        masking_recipe: MaskingRecipe,
        max_packets: Optional[int]
    ) -> List[str]:
        """验证包级别的一致性"""
        errors = []
        
        try:
            # 使用PcapReader流式读取，避免大文件内存问题
            with PcapReader(input_file) as input_reader, \
                 PcapReader(output_file) as output_reader:
                
                for packet_index, (input_packet, output_packet) in enumerate(zip(input_reader, output_reader)):
                    # 检查是否达到最大验证数量
                    if max_packets and packet_index >= max_packets:
                        logger.info(f"达到最大验证包数限制: {max_packets}")
                        break
                    
                    self.statistics['total_packets'] += 1
                    
                    try:
                        # 验证单个包的一致性
                        packet_errors = self._verify_single_packet(
                            input_packet,
                            output_packet,
                            packet_index,
                            masking_recipe
                        )
                        
                        if packet_errors:
                            errors.extend(packet_errors)
                            self.statistics['error_packets'] += 1
                        else:
                            self.statistics['verified_packets'] += 1
                            
                    except Exception as e:
                        error_msg = f"验证包{packet_index}时出错: {str(e)}"
                        errors.append(error_msg)
                        self.statistics['error_packets'] += 1
                        logger.debug(error_msg)
                
                # 检查是否有额外的包
                extra_errors = self._check_extra_packets(
                    input_reader, output_reader, packet_index + 1
                )
                errors.extend(extra_errors)
                
        except Exception as e:
            errors.append(f"读取PCAP文件时出错: {str(e)}")
        
        return errors
    
    def _verify_single_packet(
        self,
        input_packet,
        output_packet,
        packet_index: int,
        masking_recipe: MaskingRecipe
    ) -> List[str]:
        """验证单个包的一致性"""
        errors = []
        
        try:
            # 获取包的时间戳
            input_timestamp = str(input_packet.time)
            output_timestamp = str(output_packet.time)
            
            # 验证时间戳一致性
            if abs(float(input_timestamp) - float(output_timestamp)) > 0.000001:
                errors.append(f"包{packet_index}时间戳不一致")
                return errors
            
            # 检查是否有掩码指令
            instruction = masking_recipe.get_instruction_for_packet(packet_index, input_timestamp)
            
            if instruction:
                # 有掩码的包，验证掩码应用是否正确
                mask_errors = self._verify_masked_packet(
                    input_packet,
                    output_packet,
                    instruction,
                    packet_index
                )
                errors.extend(mask_errors)
                if not mask_errors:
                    self.statistics['modified_packets'] += 1
            else:
                # 无掩码的包，应该完全一致
                if raw(input_packet) != raw(output_packet):
                    errors.append(f"非掩码包{packet_index}内容不一致")
                    
        except Exception as e:
            errors.append(f"包{packet_index}验证过程出错: {str(e)}")
        
        return errors
    
    def _verify_masked_packet(
        self,
        input_packet,
        output_packet,
        instruction: PacketMaskInstruction,
        packet_index: int
    ) -> List[str]:
        """验证掩码包的正确性"""
        errors = []
        
        try:
            input_raw = raw(input_packet)
            output_raw = raw(output_packet)
            
            # 验证包长度一致性
            if len(input_raw) != len(output_raw):
                errors.append(f"掩码包{packet_index}长度不一致: {len(input_raw)} vs {len(output_raw)}")
                return errors
            
            payload_offset = instruction.payload_offset
            mask_spec = instruction.mask_spec
            
            # 验证头部（载荷偏移之前）完全一致
            if payload_offset > 0:
                input_header = input_raw[:payload_offset]
                output_header = output_raw[:payload_offset]
                
                if input_header != output_header:
                    errors.append(f"掩码包{packet_index}头部不一致（偏移{payload_offset}之前）")
                    return errors
            
            # 验证掩码应用的正确性
            if payload_offset < len(input_raw):
                mask_errors = self._verify_mask_application(
                    input_raw[payload_offset:],
                    output_raw[payload_offset:],
                    mask_spec,
                    packet_index
                )
                errors.extend(mask_errors)
            
        except Exception as e:
            errors.append(f"掩码包{packet_index}验证过程出错: {str(e)}")
        
        return errors
    
    def _verify_mask_application(
        self,
        input_payload: bytes,
        output_payload: bytes,
        mask_spec,
        packet_index: int
    ) -> List[str]:
        """验证掩码应用的正确性"""
        errors = []
        
        try:
            if isinstance(mask_spec, KeepAll):
                # KeepAll：载荷应该完全一致
                if input_payload != output_payload:
                    errors.append(f"包{packet_index} KeepAll掩码应用错误：载荷不一致")
                    
            elif isinstance(mask_spec, MaskAfter):
                # MaskAfter：保留前N字节，后续字节应该被置零
                keep_bytes = mask_spec.keep_bytes
                
                if keep_bytes > 0 and len(input_payload) > 0:
                    # 验证保留部分
                    keep_end = min(keep_bytes, len(input_payload))
                    if input_payload[:keep_end] != output_payload[:keep_end]:
                        errors.append(f"包{packet_index} MaskAfter保留部分不一致")
                
                # 验证掩码部分
                if len(input_payload) > keep_bytes:
                    mask_start = keep_bytes
                    expected_mask = b'\x00' * (len(input_payload) - mask_start)
                    actual_mask = output_payload[mask_start:]
                    
                    if expected_mask != actual_mask:
                        errors.append(f"包{packet_index} MaskAfter掩码部分不正确")
                        
            elif isinstance(mask_spec, MaskRange):
                # MaskRange：指定范围被置零，其他部分保持不变
                expected_output = bytearray(input_payload)
                
                for range_spec in mask_spec.ranges:
                    start = range_spec.start
                    length = range_spec.length
                    end = min(start + length, len(expected_output))
                    
                    if start < len(expected_output):
                        expected_output[start:end] = b'\x00' * (end - start)
                
                if bytes(expected_output) != output_payload:
                    errors.append(f"包{packet_index} MaskRange掩码应用错误")
            else:
                errors.append(f"包{packet_index}使用了未知的掩码类型: {type(mask_spec)}")
                
        except Exception as e:
            errors.append(f"包{packet_index}掩码验证过程出错: {str(e)}")
        
        return errors
    
    def _check_extra_packets(
        self,
        input_reader,
        output_reader,
        current_index: int
    ) -> List[str]:
        """检查是否有额外的包"""
        errors = []
        
        try:
            # 检查输入文件是否还有额外包
            input_extra = 0
            for _ in input_reader:
                input_extra += 1
            
            # 检查输出文件是否还有额外包
            output_extra = 0
            for _ in output_reader:
                output_extra += 1
            
            if input_extra > 0:
                errors.append(f"输入文件在索引{current_index}后还有{input_extra}个额外包")
            
            if output_extra > 0:
                errors.append(f"输出文件在索引{current_index}后还有{output_extra}个额外包")
                
        except Exception as e:
            errors.append(f"检查额外包时出错: {str(e)}")
        
        return errors
    
    def _reset_statistics(self):
        """重置统计信息"""
        self.statistics = {
            'total_packets': 0,
            'verified_packets': 0,
            'modified_packets': 0,
            'error_packets': 0,
            'skipped_packets': 0
        }
    
    def _log_verification_results(self):
        """记录验证结果"""
        total = self.statistics['total_packets']
        verified = self.statistics['verified_packets']
        modified = self.statistics['modified_packets']
        errors = self.statistics['error_packets']
        
        if not self.verification_errors:
            logger.info(f"一致性验证通过: 总计{total}包，验证{verified}包，修改{modified}包")
        else:
            logger.warning(
                f"一致性验证发现{len(self.verification_errors)}个问题: "
                f"总计{total}包，验证{verified}包，修改{modified}包，错误{errors}包"
            )


def verify_file_consistency(
    input_file: str,
    output_file: str,
    masking_recipe: MaskingRecipe,
    max_packets: Optional[int] = None
) -> List[str]:
    """
    验证输入输出文件的一致性（便捷函数）
    
    Args:
        input_file: 输入文件路径
        output_file: 输出文件路径
        masking_recipe: 使用的掩码配方
        max_packets: 最大验证包数
        
    Returns:
        List[str]: 发现的不一致错误列表
    """
    verifier = ConsistencyVerifier()
    return verifier.verify_files(input_file, output_file, masking_recipe, max_packets)


def quick_consistency_check(
    input_file: str,
    output_file: str,
    sample_size: int = 100
) -> Dict[str, any]:
    """
    快速一致性检查（采样验证）
    
    Args:
        input_file: 输入文件路径
        output_file: 输出文件路径
        sample_size: 采样大小
        
    Returns:
        Dict: 快速检查结果
    """
    result = {
        'consistent': True,
        'total_packets': 0,
        'sampled_packets': 0,
        'differences': 0,
        'errors': []
    }
    
    try:
        with PcapReader(input_file) as input_reader, \
             PcapReader(output_file) as output_reader:
            
            for index, (input_packet, output_packet) in enumerate(zip(input_reader, output_reader)):
                result['total_packets'] += 1
                
                # 采样检查
                if index % (max(1, result['total_packets'] // sample_size)) == 0:
                    result['sampled_packets'] += 1
                    
                    if raw(input_packet) != raw(output_packet):
                        result['differences'] += 1
                        
                    # 限制采样数量
                    if result['sampled_packets'] >= sample_size:
                        break
        
        result['consistent'] = result['differences'] == 0
        
    except Exception as e:
        result['consistent'] = False
        result['errors'].append(f"快速检查失败: {str(e)}")
    
    return result 