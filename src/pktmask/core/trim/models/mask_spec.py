"""
掩码规范定义

定义了各种掩码应用策略的数据结构，用于指导如何对载荷进行裁切。
"""

from abc import ABC, abstractmethod
from typing import List, Tuple
from dataclasses import dataclass
from ..exceptions import MaskSpecError


class MaskSpec(ABC):
    """
    掩码规范抽象基类
    
    定义了掩码应用的通用接口，所有具体的掩码策略都必须继承此类。
    """
    
    @abstractmethod
    def apply_to_payload(self, payload: bytes) -> bytes:
        """
        将掩码应用到载荷数据
        
        Args:
            payload: 原始载荷数据
            
        Returns:
            应用掩码后的载荷数据
        """
        pass
    
    @abstractmethod
    def get_description(self) -> str:
        """
        获取掩码规范的描述信息
        
        Returns:
            描述字符串
        """
        pass


@dataclass
class MaskAfter(MaskSpec):
    """
    保留前N字节掩码规范
    
    保留载荷的前keep_bytes个字节，其余部分置零。
    当keep_bytes=0时，整个载荷都被置零。
    """
    
    keep_bytes: int
    
    def __post_init__(self):
        if self.keep_bytes < 0:
            raise MaskSpecError(
                mask_type="MaskAfter",
                message="keep_bytes必须为非负数",
                mask_params={"keep_bytes": self.keep_bytes}
            )
    
    def apply_to_payload(self, payload: bytes) -> bytes:
        """应用前N字节保留掩码"""
        if not payload:
            return payload
        
        if self.keep_bytes == 0:
            # 全部置零
            return b'\x00' * len(payload)
        elif self.keep_bytes >= len(payload):
            # 保留全部
            return payload
        else:
            # 保留前N字节，后续置零
            keep_part = payload[:self.keep_bytes]
            zero_part = b'\x00' * (len(payload) - self.keep_bytes)
            return keep_part + zero_part
    
    def get_description(self) -> str:
        if self.keep_bytes == 0:
            return "全部载荷置零"
        else:
            return f"保留前{self.keep_bytes}字节，其余置零"


@dataclass  
class MaskRange(MaskSpec):
    """
    指定区间掩码规范
    
    对指定的字节区间进行置零操作，其他部分保持不变。
    ranges是一个元组列表，每个元组包含(start, end)偏移量。
    """
    
    ranges: List[Tuple[int, int]]
    
    def __post_init__(self):
        if not self.ranges:
            raise MaskSpecError(
                mask_type="MaskRange",
                message="区间列表不能为空",
                mask_params={"ranges": self.ranges}
            )
        
        for i, (start, end) in enumerate(self.ranges):
            if start < 0 or end < 0:
                raise MaskSpecError(
                    mask_type="MaskRange", 
                    message=f"区间{i}的偏移量必须为非负数",
                    mask_params={"range_index": i, "start": start, "end": end}
                )
            if start >= end:
                raise MaskSpecError(
                    mask_type="MaskRange",
                    message=f"区间{i}的起始位置必须小于结束位置", 
                    mask_params={"range_index": i, "start": start, "end": end}
                )
        
        # 对区间进行排序和验证
        self.ranges = sorted(self.ranges)
        
        # 检查区间是否有重叠
        for i in range(len(self.ranges) - 1):
            if self.ranges[i][1] > self.ranges[i + 1][0]:
                raise MaskSpecError(
                    mask_type="MaskRange",
                    message=f"区间{i}和区间{i+1}发生重叠",
                    mask_params={
                        "range1": self.ranges[i],
                        "range2": self.ranges[i + 1]
                    }
                )
    
    def apply_to_payload(self, payload: bytes) -> bytes:
        """应用区间掩码"""
        if not payload:
            return payload
        
        # 转换为可变字节数组
        result = bytearray(payload)
        
        # 对每个指定区间进行置零
        for start, end in self.ranges:
            # 确保不超出载荷边界
            actual_start = min(start, len(result))
            actual_end = min(end, len(result))
            
            # 置零指定区间
            for i in range(actual_start, actual_end):
                result[i] = 0
        
        return bytes(result)
    
    def get_description(self) -> str:
        range_strs = [f"[{start}:{end})" for start, end in self.ranges]
        return f"置零区间: {', '.join(range_strs)}"


class KeepAll(MaskSpec):
    """
    完全保留掩码规范
    
    不对载荷进行任何修改，完全保留原始数据。
    """
    
    def apply_to_payload(self, payload: bytes) -> bytes:
        """完全保留载荷"""
        return payload
    
    def get_description(self) -> str:
        return "完全保留载荷"





def create_tls_record_mask(record_header_length: int = 5) -> MaskSpec:
    """
    创建TLS记录头保留掩码
    
    Args:
        record_header_length: TLS记录头长度，默认5字节
        
    Returns:
        保留TLS记录头的掩码规范
    """
    return MaskAfter(record_header_length)


def create_full_payload_mask() -> MaskSpec:
    """
    创建全载荷置零掩码
    
    Returns:
        全载荷置零的掩码规范
    """
    return MaskAfter(0)


def create_preserve_all_mask() -> MaskSpec:
    """
    创建完全保留掩码
    
    Returns:
        完全保留的掩码规范
    """
    return KeepAll() 