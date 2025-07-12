"""
数据完整性验证器

提供输入验证、输出验证和中间状态检查功能。
"""

from __future__ import annotations

import hashlib
import logging
import os
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    from scapy.all import PcapReader
except ImportError:
    PcapReader = None


@dataclass
class ValidationResult:
    """验证结果"""
    is_valid: bool
    error_message: Optional[str] = None
    warnings: List[str] = None
    details: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
        if self.details is None:
            self.details = {}


class DataValidator:
    """数据完整性验证器
    
    提供输入验证、输出验证和中间状态检查功能。
    """
    
    def __init__(self, config: Dict[str, Any]):
        """初始化数据验证器
        
        Args:
            config: 配置字典
        """
        self.config = config
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        
        # 配置参数
        self.enable_checksum_validation = config.get('enable_checksum_validation', True)
        self.enable_packet_count_validation = config.get('enable_packet_count_validation', True)
        self.enable_file_size_validation = config.get('enable_file_size_validation', True)
        self.max_file_size_mb = config.get('max_file_size_mb', 1024)  # 1GB默认限制
        self.min_file_size_bytes = config.get('min_file_size_bytes', 24)  # PCAP文件头最小大小
        
        self.logger.info(f"数据验证器初始化: 校验和验证={'启用' if self.enable_checksum_validation else '禁用'}")
    
    def validate_input_file(self, file_path: Union[str, Path]) -> ValidationResult:
        """验证输入文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            ValidationResult: 验证结果
        """
        file_path = Path(file_path)
        result = ValidationResult(is_valid=True)
        
        try:
            # 1. 检查文件是否存在
            if not file_path.exists():
                return ValidationResult(
                    is_valid=False,
                    error_message=f"输入文件不存在: {file_path}"
                )
            
            # 2. 检查文件是否为普通文件
            if not file_path.is_file():
                return ValidationResult(
                    is_valid=False,
                    error_message=f"输入路径不是文件: {file_path}"
                )
            
            # 3. 检查文件大小
            file_size = file_path.stat().st_size
            result.details['file_size_bytes'] = file_size
            
            if self.enable_file_size_validation:
                if file_size < self.min_file_size_bytes:
                    return ValidationResult(
                        is_valid=False,
                        error_message=f"文件太小，可能不是有效的PCAP文件: {file_size} bytes"
                    )
                
                max_size_bytes = self.max_file_size_mb * 1024 * 1024
                if file_size > max_size_bytes:
                    result.warnings.append(f"文件较大: {file_size / 1024 / 1024:.1f}MB")
            
            # 4. 检查文件权限
            if not os.access(file_path, os.R_OK):
                return ValidationResult(
                    is_valid=False,
                    error_message=f"无法读取文件: {file_path}"
                )
            
            # 5. 验证PCAP文件格式
            pcap_validation = self._validate_pcap_format(file_path)
            if not pcap_validation.is_valid:
                return pcap_validation
            
            result.details.update(pcap_validation.details)
            result.warnings.extend(pcap_validation.warnings)
            
            # 6. 计算文件校验和
            if self.enable_checksum_validation:
                result.details['file_checksum'] = self._calculate_file_checksum(file_path)
            
            self.logger.debug(f"输入文件验证通过: {file_path}")
            
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                error_message=f"验证输入文件时发生错误: {e}"
            )
        
        return result
    
    def validate_output_file(self, file_path: Union[str, Path], 
                           expected_packet_count: Optional[int] = None) -> ValidationResult:
        """验证输出文件
        
        Args:
            file_path: 文件路径
            expected_packet_count: 期望的数据包数量
            
        Returns:
            ValidationResult: 验证结果
        """
        file_path = Path(file_path)
        result = ValidationResult(is_valid=True)
        
        try:
            # 1. 检查文件是否存在
            if not file_path.exists():
                return ValidationResult(
                    is_valid=False,
                    error_message=f"输出文件不存在: {file_path}"
                )
            
            # 2. 检查文件大小
            file_size = file_path.stat().st_size
            result.details['file_size_bytes'] = file_size
            
            if file_size < self.min_file_size_bytes:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"输出文件太小: {file_size} bytes"
                )
            
            # 3. 验证PCAP文件格式
            pcap_validation = self._validate_pcap_format(file_path)
            if not pcap_validation.is_valid:
                return pcap_validation
            
            result.details.update(pcap_validation.details)
            
            # 4. 验证数据包数量
            if self.enable_packet_count_validation and expected_packet_count is not None:
                actual_count = result.details.get('packet_count', 0)
                if actual_count != expected_packet_count:
                    result.warnings.append(
                        f"数据包数量不匹配: 期望{expected_packet_count}, 实际{actual_count}"
                    )
            
            # 5. 计算文件校验和
            if self.enable_checksum_validation:
                result.details['file_checksum'] = self._calculate_file_checksum(file_path)
            
            self.logger.debug(f"输出文件验证通过: {file_path}")
            
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                error_message=f"验证输出文件时发生错误: {e}"
            )
        
        return result
    
    def validate_processing_state(self, processed_packets: int, 
                                 modified_packets: int,
                                 error_count: int = 0) -> ValidationResult:
        """验证处理状态
        
        Args:
            processed_packets: 已处理的数据包数量
            modified_packets: 已修改的数据包数量
            error_count: 错误数量
            
        Returns:
            ValidationResult: 验证结果
        """
        result = ValidationResult(is_valid=True)
        
        try:
            # 1. 检查数据包数量的合理性
            if processed_packets < 0:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"处理的数据包数量不能为负数: {processed_packets}"
                )
            
            if modified_packets < 0:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"修改的数据包数量不能为负数: {modified_packets}"
                )
            
            if modified_packets > processed_packets:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"修改的数据包数量不能超过处理的数量: {modified_packets} > {processed_packets}"
                )
            
            # 2. 检查错误率
            if error_count > 0:
                error_rate = error_count / max(processed_packets, 1)
                result.details['error_rate'] = error_rate
                
                if error_rate > 0.1:  # 10%错误率
                    result.warnings.append(f"错误率较高: {error_rate*100:.1f}%")
                elif error_rate > 0.05:  # 5%错误率
                    result.warnings.append(f"错误率偏高: {error_rate*100:.1f}%")
            
            # 3. 检查修改率
            if processed_packets > 0:
                modification_rate = modified_packets / processed_packets
                result.details['modification_rate'] = modification_rate
                
                if modification_rate == 0:
                    result.warnings.append("没有数据包被修改，请检查掩码规则")
                elif modification_rate > 0.8:  # 80%修改率
                    result.warnings.append(f"修改率较高: {modification_rate*100:.1f}%")
            
            result.details.update({
                'processed_packets': processed_packets,
                'modified_packets': modified_packets,
                'error_count': error_count
            })
            
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                error_message=f"验证处理状态时发生错误: {e}"
            )
        
        return result
    
    def _validate_pcap_format(self, file_path: Path) -> ValidationResult:
        """验证PCAP文件格式"""
        result = ValidationResult(is_valid=True)
        
        try:
            # 读取文件头
            with open(file_path, 'rb') as f:
                header = f.read(24)
                
                if len(header) < 24:
                    return ValidationResult(
                        is_valid=False,
                        error_message="PCAP文件头不完整"
                    )
                
                # 检查魔数
                magic = struct.unpack('<I', header[:4])[0]
                if magic not in [0xa1b2c3d4, 0xd4c3b2a1, 0xa1b23c4d, 0x4d3cb2a1]:
                    return ValidationResult(
                        is_valid=False,
                        error_message=f"无效的PCAP魔数: 0x{magic:08x}"
                    )
                
                # 解析版本信息
                version_major, version_minor = struct.unpack('<HH', header[4:8])
                result.details['pcap_version'] = f"{version_major}.{version_minor}"
                
                # 解析链路类型
                linktype = struct.unpack('<I', header[20:24])[0]
                result.details['linktype'] = linktype
            
            # 如果有scapy，进行更详细的验证
            if PcapReader is not None:
                try:
                    packet_count = 0
                    with PcapReader(str(file_path)) as reader:
                        for packet in reader:
                            packet_count += 1
                            if packet_count > 10:  # 只检查前10个包
                                break
                    
                    result.details['packet_count'] = packet_count
                    if packet_count == 0:
                        result.warnings.append("文件中没有找到数据包")
                        
                except Exception as e:
                    result.warnings.append(f"Scapy验证失败: {e}")
            
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                error_message=f"PCAP格式验证失败: {e}"
            )
        
        return result
    
    def _calculate_file_checksum(self, file_path: Path) -> str:
        """计算文件校验和"""
        hash_md5 = hashlib.md5()
        
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        
        return hash_md5.hexdigest()
    
    def compare_files(self, file1: Union[str, Path], 
                     file2: Union[str, Path]) -> ValidationResult:
        """比较两个文件
        
        Args:
            file1: 第一个文件路径
            file2: 第二个文件路径
            
        Returns:
            ValidationResult: 比较结果
        """
        result = ValidationResult(is_valid=True)
        
        try:
            file1, file2 = Path(file1), Path(file2)
            
            # 比较文件大小
            size1 = file1.stat().st_size
            size2 = file2.stat().st_size
            
            result.details['file1_size'] = size1
            result.details['file2_size'] = size2
            result.details['size_difference'] = abs(size1 - size2)
            
            if size1 != size2:
                result.warnings.append(f"文件大小不同: {size1} vs {size2}")
            
            # 比较校验和
            if self.enable_checksum_validation:
                checksum1 = self._calculate_file_checksum(file1)
                checksum2 = self._calculate_file_checksum(file2)
                
                result.details['file1_checksum'] = checksum1
                result.details['file2_checksum'] = checksum2
                result.details['checksums_match'] = checksum1 == checksum2
                
                if checksum1 != checksum2:
                    result.warnings.append("文件校验和不匹配")
            
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                error_message=f"文件比较失败: {e}"
            )
        
        return result


def create_data_validator(config: Dict[str, Any]) -> DataValidator:
    """创建数据验证器实例的工厂函数
    
    Args:
        config: 配置字典
        
    Returns:
        DataValidator: 数据验证器实例
    """
    return DataValidator(config)
