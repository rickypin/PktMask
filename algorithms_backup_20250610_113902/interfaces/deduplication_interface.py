#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
去重算法接口
定义数据包去重算法的标准接口和配置
"""

from abc import abstractmethod
from typing import Dict, List, Optional, Set, Any, Tuple
from pydantic import BaseModel, Field
from enum import Enum

from .algorithm_interface import AlgorithmInterface, AlgorithmConfig, AlgorithmInfo, AlgorithmType, ValidationResult, ProcessingResult


class DeduplicationStrategy(Enum):
    """去重策略枚举"""
    HASH_BASED = "hash_based"
    CONTENT_BASED = "content_based"
    HYBRID = "hybrid"
    SIGNATURE_BASED = "signature_based"


class HashAlgorithm(Enum):
    """哈希算法枚举"""
    MD5 = "md5"
    SHA1 = "sha1"
    SHA256 = "sha256"
    CRC32 = "crc32"
    CUSTOM = "custom"


class DeduplicationConfig(AlgorithmConfig):
    """去重算法配置"""
    
    # 去重策略
    strategy: DeduplicationStrategy = Field(default=DeduplicationStrategy.HASH_BASED, description="去重策略")
    hash_algorithm: HashAlgorithm = Field(default=HashAlgorithm.MD5, description="哈希算法")
    
    # 智能哈希配置
    use_smart_hashing: bool = Field(default=True, description="启用智能哈希策略")
    large_packet_threshold: int = Field(default=100, ge=50, le=1000, description="大包阈值(字节)")
    hash_prefix_length: int = Field(default=100, ge=32, le=1024, description="哈希前缀长度")
    
    # 批处理配置
    batch_size: int = Field(default=1000, ge=100, le=10000, description="批处理大小")
    enable_batch_processing: bool = Field(default=True, description="启用批处理")
    
    # 缓存配置
    hash_cache_size: int = Field(default=50000, ge=1000, le=1000000, description="哈希缓存大小")
    enable_hash_caching: bool = Field(default=True, description="启用哈希缓存")
    cache_cleanup_interval: int = Field(default=10000, ge=1000, le=100000, description="缓存清理间隔")
    
    # 性能优化
    parallel_processing: bool = Field(default=False, description="并行处理")
    memory_efficient_mode: bool = Field(default=True, description="内存高效模式")
    enable_statistics: bool = Field(default=True, description="启用统计信息")
    
    # 精确性配置
    strict_comparison: bool = Field(default=False, description="严格比较模式")
    ignore_timestamp: bool = Field(default=True, description="忽略时间戳差异")
    ignore_checksums: bool = Field(default=True, description="忽略校验和差异")
    
    class Config:
        extra = "allow"


class PacketSignature(BaseModel):
    """数据包签名"""
    hash_value: str = Field(description="哈希值")
    packet_size: int = Field(description="数据包大小")
    protocol_info: str = Field(description="协议信息")
    header_fingerprint: Optional[str] = Field(default=None, description="包头指纹")
    payload_sample: Optional[str] = Field(default=None, description="载荷样本")
    
    class Config:
        extra = "allow"


class DeduplicationStats(BaseModel):
    """去重统计信息"""
    total_packets: int = Field(default=0, ge=0, description="总数据包数")
    unique_packets: int = Field(default=0, ge=0, description="唯一数据包数")
    duplicate_packets: int = Field(default=0, ge=0, description="重复数据包数")
    deduplication_rate: float = Field(default=0.0, ge=0.0, le=100.0, description="去重率(%)")
    
    # 缓存统计
    cache_hits: int = Field(default=0, ge=0, description="缓存命中次数")
    cache_misses: int = Field(default=0, ge=0, description="缓存未命中次数")
    cache_hit_rate: float = Field(default=0.0, ge=0.0, le=100.0, description="缓存命中率(%)")
    
    # 性能统计
    processing_time_ms: float = Field(default=0.0, ge=0.0, description="处理时间(毫秒)")
    throughput_packets_per_sec: float = Field(default=0.0, ge=0.0, description="吞吐量(包/秒)")
    memory_usage_mb: float = Field(default=0.0, ge=0.0, description="内存使用(MB)")
    
    def update_deduplication_rate(self):
        """更新去重率"""
        if self.total_packets > 0:
            self.deduplication_rate = (self.duplicate_packets / self.total_packets) * 100.0
    
    def update_cache_hit_rate(self):
        """更新缓存命中率"""
        total_requests = self.cache_hits + self.cache_misses
        if total_requests > 0:
            self.cache_hit_rate = (self.cache_hits / total_requests) * 100.0
    
    def update_throughput(self):
        """更新吞吐量"""
        if self.processing_time_ms > 0:
            seconds = self.processing_time_ms / 1000.0
            self.throughput_packets_per_sec = self.total_packets / seconds


class DeduplicationResult(ProcessingResult):
    """去重处理结果"""
    stats: DeduplicationStats = Field(default_factory=DeduplicationStats, description="去重统计")
    duplicate_signatures: List[PacketSignature] = Field(default_factory=list, description="重复包签名")
    unique_signatures: List[PacketSignature] = Field(default_factory=list, description="唯一包签名")
    processing_summary: Dict[str, Any] = Field(default_factory=dict, description="处理摘要")
    
    def add_duplicate(self, signature: PacketSignature):
        """添加重复包签名"""
        self.duplicate_signatures.append(signature)
        self.stats.duplicate_packets += 1
    
    def add_unique(self, signature: PacketSignature):
        """添加唯一包签名"""
        self.unique_signatures.append(signature)
        self.stats.unique_packets += 1


class DeduplicationInterface(AlgorithmInterface):
    """去重算法接口"""
    
    def get_algorithm_info(self) -> AlgorithmInfo:
        """获取算法信息（需要子类实现具体信息）"""
        return AlgorithmInfo(
            name="Generic Packet Deduplication",
            version="1.0.0",
            algorithm_type=AlgorithmType.DEDUPLICATION,
            author="PktMask Team",
            description="通用数据包去重算法接口",
            supported_formats=[".pcap", ".pcapng"],
            requirements={"scapy": ">=2.4.0"}
        )
    
    def get_default_config(self) -> DeduplicationConfig:
        """获取默认配置"""
        return DeduplicationConfig()
    
    def validate_config(self, config: AlgorithmConfig) -> ValidationResult:
        """验证配置"""
        result = ValidationResult(is_valid=True)
        
        if not isinstance(config, DeduplicationConfig):
            result.add_error("配置必须是DeduplicationConfig类型")
            return result
        
        # 验证哈希算法
        if config.hash_algorithm == HashAlgorithm.CUSTOM:
            result.add_warning("使用自定义哈希算法，请确保实现正确")
        
        # 验证大包阈值
        if config.large_packet_threshold < 32:
            result.add_warning("大包阈值过小，可能影响智能哈希效果")
        elif config.large_packet_threshold > 1000:
            result.add_warning("大包阈值过大，可能降低去重效率")
        
        return result
    
    # === 核心去重方法 ===
    
    @abstractmethod
    def compute_packet_signature(self, packet) -> PacketSignature:
        """
        计算数据包签名
        
        Args:
            packet: 数据包对象
            
        Returns:
            PacketSignature: 数据包签名
        """
        pass
    
    @abstractmethod
    def is_duplicate(self, signature: PacketSignature) -> bool:
        """
        检查是否为重复包
        
        Args:
            signature: 数据包签名
            
        Returns:
            bool: 是否为重复包
        """
        pass
    
    @abstractmethod
    def add_unique_signature(self, signature: PacketSignature):
        """
        添加唯一包签名到缓存
        
        Args:
            signature: 数据包签名
        """
        pass
    
    def process_file(self, input_path: str, output_path: str) -> DeduplicationResult:
        """
        处理单个文件的去重
        
        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径
            
        Returns:
            DeduplicationResult: 处理结果
        """
        self._check_ready()
        
        try:
            # 使用性能跟踪
            tracker = self._get_performance_tracker()
            
            with tracker.track_operation(f"deduplicate_file_{input_path}"):
                result = self._do_process_file(input_path, output_path)
                
            # 添加性能指标
            result.metrics = tracker.get_current_metrics().to_dict()
            
            return result
            
        except Exception as e:
            self._logger.error(f"处理文件失败 {input_path}: {e}")
            return DeduplicationResult(
                success=False,
                data=None,
                errors=[str(e)]
            )
    
    @abstractmethod
    def _do_process_file(self, input_path: str, output_path: str) -> DeduplicationResult:
        """
        执行具体的文件处理逻辑（由子类实现）
        
        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径
            
        Returns:
            DeduplicationResult: 处理结果
        """
        pass
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """获取性能指标"""
        return {}
    
    def _get_performance_tracker(self):
        """获取性能跟踪器"""
        from .performance_interface import get_algorithm_tracker
        return get_algorithm_tracker(self.get_algorithm_info().name) 