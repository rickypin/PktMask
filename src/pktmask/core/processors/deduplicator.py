"""
去重处理器

直接实现去重功能，不依赖Legacy Steps。
"""
import os
from typing import Optional, Set, Dict
import hashlib
import time

from .base_processor import BaseProcessor, ProcessorConfig, ProcessorResult
from ...infrastructure.logging import get_logger

try:
    from scapy.all import rdpcap, wrpcap, Packet
except ImportError:
    rdpcap = wrpcap = Packet = None


class DeduplicationProcessor(BaseProcessor):
    """去重处理器
    
    直接实现数据包去重功能。
    """
    
    def __init__(self, config: ProcessorConfig):
        super().__init__(config)
        self._logger = get_logger('deduplicator')
        self._packet_hashes: Set[str] = set()
        
    def _initialize_impl(self):
        """初始化去重组件"""
        try:
            if rdpcap is None:
                raise ImportError("Scapy库未安装，无法进行去重处理")
            
            self._packet_hashes.clear()
            self._logger.info("去重处理器初始化成功")
            
        except Exception as e:
            self._logger.error(f"去重处理器初始化失败: {e}")
            raise
            
    def process_file(self, input_path: str, output_path: str) -> ProcessorResult:
        """处理单个文件的去重"""
        if not self._is_initialized:
            if not self.initialize():
                return ProcessorResult(
                    success=False, 
                    error="处理器未正确初始化"
                )
        
        try:
            # 验证输入
            self.validate_inputs(input_path, output_path)
            
            # 重置统计信息
            self.reset_stats()
            
            self._logger.info(f"开始去重处理: {input_path} -> {output_path}")
            
            start_time = time.time()
            
            # 读取数据包
            packets = rdpcap(input_path)
            total_packets = len(packets)
            
            # 去重处理
            unique_packets = []
            removed_count = 0
            
            for packet in packets:
                # 生成数据包哈希
                packet_hash = self._generate_packet_hash(packet)
                
                if packet_hash not in self._packet_hashes:
                    self._packet_hashes.add(packet_hash)
                    unique_packets.append(packet)
                else:
                    removed_count += 1
            
            # 保存去重后的数据包
            if unique_packets:
                wrpcap(output_path, unique_packets)
            else:
                # 如果没有唯一数据包，创建空文件
                open(output_path, 'a').close()
            
            processing_time = time.time() - start_time
            
            # 构建结果数据
            result_data = {
                'total_packets': total_packets,
                'unique_packets': len(unique_packets),
                'removed_count': removed_count,
                'processing_time': processing_time
            }
            
            # 更新统计信息
            self.stats.update({
                'total_packets': result_data.get('total_packets', 0),
                'unique_packets': result_data.get('unique_packets', 0),
                'removed_count': result_data.get('removed_count', 0),
                'deduplication_rate': self._calculate_deduplication_rate(result_data),
                'space_saved': self._calculate_space_saved(input_path, output_path)
            })
            
            removed_count = result_data.get('removed_count', 0)
            self._logger.info(f"去重完成: 移除 {removed_count} 个重复数据包")
            
            return ProcessorResult(
                success=True,
                data=result_data,
                stats=self.stats
            )
            
        except FileNotFoundError as e:
            error_msg = f"文件未找到: {e}"
            self._logger.error(error_msg)
            return ProcessorResult(success=False, error=error_msg)
            
        except Exception as e:
            error_msg = f"去重处理失败: {e}"
            self._logger.error(error_msg)
            return ProcessorResult(success=False, error=error_msg)
    
    def get_display_name(self) -> str:
        """获取用户友好的显示名称"""
        return "Remove Dupes"
    
    def get_description(self) -> str:
        """获取处理器描述"""
        return "移除完全重复的数据包，减少文件大小"
        
    def _calculate_deduplication_rate(self, result_data: dict) -> float:
        """计算去重比率"""
        total_packets = result_data.get('total_packets', 0)
        removed_count = result_data.get('removed_count', 0)
        
        if total_packets == 0:
            return 0.0
        
        return (removed_count / total_packets) * 100.0
        
    def _calculate_space_saved(self, input_path: str, output_path: str) -> dict:
        """计算空间节省情况"""
        try:
            if not os.path.exists(input_path) or not os.path.exists(output_path):
                return {'input_size': 0, 'output_size': 0, 'saved_bytes': 0, 'saved_percentage': 0.0}
            
            input_size = os.path.getsize(input_path)
            output_size = os.path.getsize(output_path)
            saved_bytes = input_size - output_size
            saved_percentage = (saved_bytes / input_size * 100.0) if input_size > 0 else 0.0
            
            return {
                'input_size': input_size,
                'output_size': output_size,
                'saved_bytes': saved_bytes,
                'saved_percentage': saved_percentage
            }
            
        except Exception as e:
            self._logger.warning(f"计算空间节省失败: {e}")
            return {'input_size': 0, 'output_size': 0, 'saved_bytes': 0, 'saved_percentage': 0.0}
            
    def get_duplication_stats(self) -> dict:
        """获取去重统计信息"""
        return {
            'total_processed': self.stats.get('total_packets', 0),
            'unique_found': self.stats.get('unique_packets', 0),
            'duplicates_removed': self.stats.get('removed_count', 0),
            'deduplication_rate': self.stats.get('deduplication_rate', 0.0),
            'space_saved': self.stats.get('space_saved', {})
        }
    
    def _generate_packet_hash(self, packet: 'Packet') -> str:
        """生成数据包的哈希值"""
        try:
            # 使用数据包的原始字节生成哈希
            packet_bytes = bytes(packet)
            return hashlib.md5(packet_bytes).hexdigest()
        except Exception as e:
            self._logger.warning(f"生成数据包哈希失败: {e}")
            # 备用方案：使用字符串表示
            return hashlib.md5(str(packet).encode()).hexdigest()


# 兼容性别名 - 保持向后兼容
class Deduplicator(DeduplicationProcessor):
    """兼容性别名，请使用 DeduplicationProcessor 代替。
    
    .. deprecated:: 当前版本
       请使用 :class:`DeduplicationProcessor` 代替 :class:`Deduplicator`
    """
    
    def __init__(self, config: ProcessorConfig):
        import warnings
        warnings.warn(
            "Deduplicator 已废弃，请使用 DeduplicationProcessor 代替",
            DeprecationWarning,
            stacklevel=2
        )
        super().__init__(config)
