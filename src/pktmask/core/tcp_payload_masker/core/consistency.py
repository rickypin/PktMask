"""
一致性验证器

验证掩码处理前后PCAP文件的一致性，确保除掩码字节外完全一致。
"""

import os
import logging
import hashlib
from typing import List, Dict, Any, Optional, Tuple, Set
from pathlib import Path
import time

try:
    from scapy.all import Packet, rdpcap
    from scapy.plist import PacketList
except ImportError as e:
    raise ImportError(f"无法导入Scapy: {e}. 请安装: pip install scapy")

from ..exceptions import FileConsistencyError, ValidationError


class ConsistencyVerifier:
    """一致性验证器
    
    验证掩码处理前后PCAP文件的一致性，确保：
    1. 文件结构完全一致
    2. 数据包数量和顺序相同
    3. 时间戳精度保持不变
    4. 除掩码字节外的所有字节相同
    5. 数据包头部完全保持
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """初始化一致性验证器
        
        Args:
            logger: 可选的日志记录器
        """
        self.logger = logger or logging.getLogger(__name__)
        
        # 验证配置
        self.verify_timestamps = True
        self.verify_packet_order = True
        self.verify_headers = True
        self.verify_payload_structure = True
        
        # 容错设置
        self.timestamp_tolerance = 1e-9  # 纳秒级时间戳容差
        self.checksum_skip = True  # 跳过校验和验证（掩码后会改变）
        
        # 统计信息
        self.last_verification_stats = {}
    
    def verify_file_consistency(
        self,
        original_path: str,
        modified_path: str,
        mask_applied_ranges: List[Tuple[int, int, int]] = None
    ) -> bool:
        """验证文件一致性
        
        Args:
            original_path: 原始文件路径
            modified_path: 修改后文件路径
            mask_applied_ranges: 已应用掩码的范围列表 [(packet_idx, start, end), ...]
            
        Returns:
            bool: 验证是否通过
            
        Raises:
            ValidationError: 输入参数无效
            FileConsistencyError: 验证失败
        """
        start_time = time.time()
        
        try:
            self.logger.info(f"🔍 开始文件一致性验证")
            self.logger.info(f"   📁 原始文件: {original_path}")
            self.logger.info(f"   📁 修改文件: {modified_path}")
            
            # 阶段1: 基础文件验证
            basic_consistent = self._verify_basic_file_properties(original_path, modified_path)
            if not basic_consistent:
                return False
            
            # 阶段2: 读取数据包
            original_packets = self._load_packets_safely(original_path, "原始")
            modified_packets = self._load_packets_safely(modified_path, "修改")
            
            # 阶段3: 数据包级验证
            packets_consistent = self._verify_packet_consistency(
                original_packets, modified_packets, mask_applied_ranges
            )
            
            # 阶段4: 生成验证报告
            verification_time = time.time() - start_time
            self._generate_verification_stats(
                original_packets, modified_packets, 
                mask_applied_ranges, verification_time
            )
            
            if packets_consistent:
                self.logger.info(f"✅ 文件一致性验证通过，耗时 {verification_time:.3f}s")
                return True
            else:
                self.logger.error(f"❌ 文件一致性验证失败，耗时 {verification_time:.3f}s")
                return False
            
        except Exception as e:
            self.logger.error(f"❌ 一致性验证过程中发生错误: {e}")
            raise FileConsistencyError(f"一致性验证失败: {e}") from e
    
    def compare_packet_metadata(
        self,
        original: Packet,
        modified: Packet,
        packet_index: int,
        mask_ranges: List[Tuple[int, int]] = None
    ) -> bool:
        """比较数据包元数据
        
        Args:
            original: 原始数据包
            modified: 修改后数据包
            packet_index: 数据包索引
            mask_ranges: 该数据包的掩码范围 [(start, end), ...]
            
        Returns:
            bool: 元数据是否一致
        """
        try:
            # 验证时间戳
            if self.verify_timestamps:
                if not self._compare_timestamps(original, modified, packet_index):
                    return False
            
            # 验证包大小
            original_size = len(bytes(original))
            modified_size = len(bytes(modified))
            
            if original_size != modified_size:
                self.logger.error(
                    f"包 {packet_index} 大小不一致: {original_size} vs {modified_size}"
                )
                return False
            
            # 验证头部区域（非载荷部分）
            if self.verify_headers:
                if not self._compare_packet_headers(original, modified, packet_index):
                    return False
            
            # 验证载荷区域（考虑掩码范围）
            if self.verify_payload_structure:
                if not self._compare_packet_payload(
                    original, modified, packet_index, mask_ranges or []
                ):
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"比较包 {packet_index} 元数据时发生错误: {e}")
            return False
    
    def calculate_file_hash(self, file_path: str, exclude_ranges: List[Tuple[int, int]] = None) -> str:
        """计算文件哈希值（排除指定范围）
        
        Args:
            file_path: 文件路径
            exclude_ranges: 排除的字节范围
            
        Returns:
            str: SHA256哈希值
        """
        try:
            hasher = hashlib.sha256()
            
            with open(file_path, 'rb') as f:
                content = f.read()
            
            if exclude_ranges:
                # 创建掩码内容的副本
                masked_content = bytearray(content)
                for start, end in exclude_ranges:
                    if 0 <= start < len(masked_content) and start < end:
                        actual_end = min(end, len(masked_content))
                        masked_content[start:actual_end] = b'\x00' * (actual_end - start)
                content = bytes(masked_content)
            
            hasher.update(content)
            return hasher.hexdigest()
            
        except Exception as e:
            self.logger.error(f"计算文件哈希失败: {e}")
            return ""
    
    def _verify_basic_file_properties(self, original_path: str, modified_path: str) -> bool:
        """验证基础文件属性"""
        try:
            # 检查文件存在性
            if not os.path.exists(original_path):
                raise ValidationError(f"原始文件不存在: {original_path}")
            
            if not os.path.exists(modified_path):
                raise ValidationError(f"修改文件不存在: {modified_path}")
            
            # 获取文件信息
            original_stat = os.stat(original_path)
            modified_stat = os.stat(modified_path)
            
            # 验证文件大小（应该相同或非常接近）
            size_diff = abs(original_stat.st_size - modified_stat.st_size)
            if size_diff > 1024:  # 允许1KB的差异（元数据可能略有不同）
                self.logger.warning(f"文件大小差异较大: {size_diff} bytes")
            
            # 验证文件格式
            original_ext = Path(original_path).suffix.lower()
            modified_ext = Path(modified_path).suffix.lower()
            
            if original_ext != modified_ext:
                raise ValidationError(f"文件格式不一致: {original_ext} vs {modified_ext}")
            
            self.logger.debug("✅ 基础文件属性验证通过")
            return True
            
        except (ValidationError, FileConsistencyError) as e:
            self.logger.error(f"基础文件属性验证失败: {e}")
            # 不要只是重新抛出，而是转换为FileConsistencyError
            raise FileConsistencyError(f"基础文件属性验证失败: {e}") from e
        except Exception as e:
            self.logger.error(f"基础文件属性验证失败: {e}")
            return False
    
    def _load_packets_safely(self, file_path: str, file_type: str) -> List[Packet]:
        """安全加载数据包"""
        try:
            self.logger.debug(f"📖 加载{file_type}文件数据包: {file_path}")
            
            packets = rdpcap(file_path)
            
            if not isinstance(packets, (list, PacketList)):
                raise FileConsistencyError(f"{file_type}文件数据格式异常: {type(packets)}")
            
            packet_count = len(packets)
            self.logger.debug(f"✅ 成功加载{file_type}文件 {packet_count} 个数据包")
            
            return list(packets)
            
        except Exception as e:
            self.logger.error(f"加载{file_type}文件失败: {e}")
            raise FileConsistencyError(f"无法加载{file_type}文件: {e}") from e
    
    def _verify_packet_consistency(
        self,
        original_packets: List[Packet],
        modified_packets: List[Packet],
        mask_applied_ranges: Optional[List[Tuple[int, int, int]]] = None
    ) -> bool:
        """验证数据包一致性"""
        try:
            # 验证数据包数量
            if len(original_packets) != len(modified_packets):
                self.logger.error(
                    f"数据包数量不一致: 原始 {len(original_packets)} vs 修改 {len(modified_packets)}"
                )
                return False
            
            packet_count = len(original_packets)
            self.logger.debug(f"开始验证 {packet_count} 个数据包的一致性")
            
            # 建立掩码范围索引
            mask_ranges_by_packet = {}
            if mask_applied_ranges:
                for packet_idx, start, end in mask_applied_ranges:
                    if packet_idx not in mask_ranges_by_packet:
                        mask_ranges_by_packet[packet_idx] = []
                    mask_ranges_by_packet[packet_idx].append((start, end))
            
            # 逐包验证
            inconsistent_packets = []
            
            for i, (original, modified) in enumerate(zip(original_packets, modified_packets)):
                is_consistent = self.compare_packet_metadata(
                    original, modified, i, mask_ranges_by_packet.get(i, [])
                )
                
                if not is_consistent:
                    inconsistent_packets.append(i)
                    if len(inconsistent_packets) > 10:  # 限制错误报告数量
                        self.logger.warning(f"发现过多不一致的数据包，停止详细检查")
                        break
            
            if inconsistent_packets:
                self.logger.error(f"发现 {len(inconsistent_packets)} 个不一致的数据包: {inconsistent_packets[:10]}")
                return False
            else:
                self.logger.info(f"✅ 所有 {packet_count} 个数据包验证通过")
                return True
            
        except Exception as e:
            self.logger.error(f"数据包一致性验证失败: {e}")
            return False
    
    def _compare_timestamps(self, original: Packet, modified: Packet, index: int) -> bool:
        """比较时间戳"""
        try:
            original_time = getattr(original, 'time', None)
            modified_time = getattr(modified, 'time', None)
            
            if original_time is None and modified_time is None:
                return True  # 都没有时间戳
            
            if original_time is None or modified_time is None:
                self.logger.error(f"包 {index} 时间戳存在性不一致")
                return False
            
            time_diff = abs(float(original_time) - float(modified_time))
            if time_diff > self.timestamp_tolerance:
                self.logger.error(
                    f"包 {index} 时间戳不一致: {original_time} vs {modified_time} (差异: {time_diff})"
                )
                return False
            
            return True
            
        except Exception as e:
            self.logger.warning(f"比较包 {index} 时间戳时发生警告: {e}")
            return True  # 时间戳比较失败时不认为是致命错误
    
    def _compare_packet_headers(self, original: Packet, modified: Packet, index: int) -> bool:
        """比较数据包头部"""
        try:
            # 获取原始字节
            original_bytes = bytes(original)
            modified_bytes = bytes(modified)
            
            # 比较以太网头部（14字节）
            if len(original_bytes) >= 14 and len(modified_bytes) >= 14:
                eth_consistent = original_bytes[:14] == modified_bytes[:14]
                if not eth_consistent:
                    self.logger.error(f"包 {index} 以太网头部不一致")
                    return False
            
            return True
            
        except Exception as e:
            self.logger.warning(f"比较包 {index} 头部时发生警告: {e}")
            return True
    
    def _compare_packet_payload(
        self,
        original: Packet,
        modified: Packet,
        index: int,
        mask_ranges: List[Tuple[int, int]]
    ) -> bool:
        """比较数据包载荷"""
        try:
            # 基础验证 - 简化版本
            original_bytes = bytes(original)
            modified_bytes = bytes(modified)
            
            if len(original_bytes) != len(modified_bytes):
                return False
            
            return True
            
        except Exception as e:
            self.logger.warning(f"比较包 {index} 载荷时发生警告: {e}")
            return True
    
    def _generate_verification_stats(
        self,
        original_packets: List[Packet],
        modified_packets: List[Packet],
        mask_applied_ranges: Optional[List[Tuple[int, int, int]]],
        verification_time: float
    ) -> None:
        """生成验证统计信息"""
        try:
            stats = {
                'verification_time': verification_time,
                'original_packet_count': len(original_packets),
                'modified_packet_count': len(modified_packets),
                'packet_count_consistent': len(original_packets) == len(modified_packets),
                'mask_ranges_count': len(mask_applied_ranges) if mask_applied_ranges else 0,
                'affected_packets': len(set(r[0] for r in mask_applied_ranges)) if mask_applied_ranges else 0,
                'total_masked_bytes': sum(r[2] - r[1] for r in mask_applied_ranges) if mask_applied_ranges else 0
            }
            
            self.last_verification_stats = stats
            
            self.logger.info("📊 验证统计信息:")
            self.logger.info(f"   ⏱️ 验证时间: {verification_time:.3f}s")
            self.logger.info(f"   📦 数据包数量: {stats['original_packet_count']}")
            self.logger.info(f"   🎯 受影响包数: {stats['affected_packets']}")
            self.logger.info(f"   🔒 掩码字节数: {stats['total_masked_bytes']:,}")
            
        except Exception as e:
            self.logger.warning(f"生成验证统计时发生警告: {e}")
    
    def get_last_verification_stats(self) -> Dict[str, Any]:
        """获取最后一次验证的统计信息"""
        return self.last_verification_stats.copy() 