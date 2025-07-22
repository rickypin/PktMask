"""
统一去重阶段 - 纯StageBase实现

完全移除BaseProcessor依赖，直接集成SHA256哈希去重算法。
消除适配器层，统一返回StageStats格式。
"""
from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path
from typing import Dict, Any, Optional, Set

from pktmask.core.pipeline.base_stage import StageBase
from pktmask.core.pipeline.models import StageStats
from pktmask.infrastructure.logging import get_logger


class UnifiedDeduplicationStage(StageBase):
    """统一去重阶段 - 消除BaseProcessor依赖
    
    直接集成SHA256哈希去重算法，无适配器层，统一接口。
    保持所有现有功能：字节级去重、统计信息收集、空间节省计算。
    """
    
    name: str = "UnifiedDeduplicationStage"
    
    def __init__(self, config: Dict[str, Any]):
        """初始化统一去重阶段
        
        Args:
            config: 配置字典，支持以下参数：
                - algorithm: 去重算法 (默认: "md5")
                - enabled: 是否启用 (默认: True)
                - name: 阶段名称
                - priority: 优先级
        """
        super().__init__()
        
        # 配置解析
        self.algorithm = config.get('algorithm', 'md5')
        self.enabled = config.get('enabled', True)
        self.stage_name = config.get('name', 'deduplication')
        self.priority = config.get('priority', 0)
        
        # 日志记录器
        self.logger = get_logger('unified_deduplication')
        
        # 去重状态
        self._packet_hashes: Set[str] = set()
        
        # 统计信息
        self._stats = {}
        
        self.logger.info(f"UnifiedDeduplicationStage created: algorithm={self.algorithm}")
    
    def initialize(self, config: Optional[Dict] = None) -> None:
        """初始化去重组件"""
        try:
            # 检查Scapy可用性
            from scapy.all import rdpcap, wrpcap
            
            # 清空哈希集合
            self._packet_hashes.clear()
            
            super().initialize(config)
            self.logger.info("Unified deduplication stage initialization successful")
            
        except ImportError as e:
            error_msg = f"Scapy library not available: {e}"
            self.logger.error(error_msg)
            raise RuntimeError(error_msg)
        except Exception as e:
            self.logger.error(f"Unified deduplication stage initialization failed: {e}")
            raise
    
    def process_file(self, input_path: str | Path, output_path: str | Path) -> StageStats:
        """处理文件 - 直接实现去重逻辑，无适配器层
        
        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径
            
        Returns:
            StageStats: 标准统计信息格式
        """
        if not self._initialized:
            self.initialize()
            if not self._initialized:
                raise RuntimeError("UnifiedDeduplicationStage 未初始化")
        
        # 路径标准化
        input_path = Path(input_path)
        output_path = Path(output_path)
        
        # 验证输入
        if not input_path.exists():
            raise FileNotFoundError(f"输入文件不存在: {input_path}")
        if not input_path.is_file():
            raise ValueError(f"输入路径不是文件: {input_path}")
        
        self.logger.info(f"Starting deduplication: {input_path} -> {output_path}")
        
        start_time = time.time()
        
        try:
            # 重置统计信息和去重状态
            self._stats.clear()
            self._packet_hashes.clear()  # 清空哈希集合，确保每个文件独立处理

            # 使用Scapy处理PCAP文件
            from scapy.all import rdpcap, wrpcap
            
            # 读取数据包
            packets = rdpcap(str(input_path))
            total_packets = len(packets)
            
            self.logger.info(f"Loaded {total_packets} packets from {input_path}")
            
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
                wrpcap(str(output_path), unique_packets)
                self.logger.info(f"Saved {len(unique_packets)} unique packets to {output_path}")
            else:
                # 如果没有唯一数据包，创建空文件
                output_path.touch()
                self.logger.warning("No unique packets found, created empty output file")
            
            processing_time = time.time() - start_time
            duration_ms = processing_time * 1000
            
            # 计算去重率
            deduplication_rate = (removed_count / total_packets * 100.0) if total_packets > 0 else 0.0
            
            # 计算空间节省
            space_saved = self._calculate_space_saved(input_path, output_path)
            
            # 更新内部统计
            self._stats.update({
                'total_packets': total_packets,
                'unique_packets': len(unique_packets),
                'removed_count': removed_count,
                'deduplication_rate': deduplication_rate,
                'space_saved': space_saved,
                'processing_time': processing_time
            })
            
            self.logger.info(
                f"Deduplication completed: removed {removed_count}/{total_packets} duplicate packets "
                f"({deduplication_rate:.1f}% deduplication rate)"
            )
            
            # 返回标准StageStats格式
            return StageStats(
                stage_name=self.name,
                packets_processed=total_packets,
                packets_modified=removed_count,
                duration_ms=duration_ms,
                extra_metrics={
                    'algorithm': self.algorithm,
                    'total_packets': total_packets,
                    'unique_packets': len(unique_packets),
                    'removed_count': removed_count,
                    'deduplication_rate': deduplication_rate,
                    'space_saved': space_saved,
                    'processing_time': processing_time,
                    'enabled': self.enabled,
                    'stage_name': self.stage_name,
                    'success': True
                }
            )
            
        except FileNotFoundError as e:
            error_msg = f"File not found: {e}"
            self.logger.error(error_msg)
            raise
            
        except Exception as e:
            error_msg = f"Deduplication processing failed: {e}"
            self.logger.error(error_msg)
            raise
    
    def get_display_name(self) -> str:
        """获取显示名称"""
        return "Remove Dupes"
    
    def get_description(self) -> str:
        """获取描述"""
        return "Remove completely duplicate packets to reduce file size"
    
    def _generate_packet_hash(self, packet) -> str:
        """生成数据包哈希值"""
        try:
            # 使用数据包的原始字节生成哈希
            packet_bytes = bytes(packet)
            if self.algorithm == 'sha256':
                return hashlib.sha256(packet_bytes).hexdigest()
            else:
                # 默认使用MD5（与原实现保持一致）
                return hashlib.md5(packet_bytes).hexdigest()
        except Exception as e:
            self.logger.warning(f"Failed to generate packet hash: {e}")
            # 回退：使用字符串表示
            packet_str = str(packet).encode()
            if self.algorithm == 'sha256':
                return hashlib.sha256(packet_str).hexdigest()
            else:
                return hashlib.md5(packet_str).hexdigest()
    
    def _calculate_space_saved(self, input_path: Path, output_path: Path) -> dict:
        """计算空间节省"""
        try:
            if not input_path.exists() or not output_path.exists():
                return {'input_size': 0, 'output_size': 0, 'saved_bytes': 0, 'saved_percentage': 0.0}
            
            input_size = input_path.stat().st_size
            output_size = output_path.stat().st_size
            saved_bytes = input_size - output_size
            saved_percentage = (saved_bytes / input_size * 100.0) if input_size > 0 else 0.0
            
            return {
                'input_size': input_size,
                'output_size': output_size,
                'saved_bytes': saved_bytes,
                'saved_percentage': saved_percentage
            }
            
        except Exception as e:
            self.logger.warning(f"Failed to calculate space saved: {e}")
            return {'input_size': 0, 'output_size': 0, 'saved_bytes': 0, 'saved_percentage': 0.0}
    
    def get_duplication_stats(self) -> dict:
        """获取去重统计信息"""
        return {
            'total_processed': self._stats.get('total_packets', 0),
            'unique_found': self._stats.get('unique_packets', 0),
            'duplicates_removed': self._stats.get('removed_count', 0),
            'deduplication_rate': self._stats.get('deduplication_rate', 0.0),
            'space_saved': self._stats.get('space_saved', {})
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """获取处理统计信息"""
        return self._stats.copy()
    
    def reset_stats(self):
        """重置统计信息"""
        self._stats.clear()
        self._packet_hashes.clear()
