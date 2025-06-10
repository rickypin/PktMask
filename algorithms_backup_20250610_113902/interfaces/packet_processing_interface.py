#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
数据包处理算法接口
定义数据包处理算法的标准接口和配置
"""

from abc import abstractmethod
from typing import Dict, List, Optional, Any, Tuple
from pydantic import BaseModel, Field
from enum import Enum

from .algorithm_interface import AlgorithmInterface, AlgorithmConfig, AlgorithmInfo, AlgorithmType, ValidationResult, ProcessingResult


class PacketProcessingStrategy(Enum):
    """数据包处理策略枚举"""
    INTELLIGENT_TRIMMING = "intelligent_trimming"
    PAYLOAD_FILTERING = "payload_filtering"
    HEADER_MODIFICATION = "header_modification"
    COMPRESSION = "compression"


class PacketProcessingConfig(AlgorithmConfig):
    """数据包处理算法配置"""
    
    # 处理策略
    strategy: PacketProcessingStrategy = Field(default=PacketProcessingStrategy.INTELLIGENT_TRIMMING, description="处理策略")
    
    # 裁切配置
    trim_payload: bool = Field(default=True, description="是否裁切载荷")
    preserve_headers: bool = Field(default=True, description="保留协议头")
    min_packet_size: int = Field(default=64, ge=14, le=1500, description="最小数据包大小")
    max_packet_size: int = Field(default=1500, ge=64, le=9000, description="最大数据包大小")
    
    # TLS处理配置
    preserve_tls_handshake: bool = Field(default=True, description="保留TLS握手")
    preserve_certificates: bool = Field(default=True, description="保留证书")
    
    # 批处理配置
    batch_size: int = Field(default=1000, ge=100, le=10000, description="批处理大小")
    enable_caching: bool = Field(default=True, description="启用缓存")
    
    class Config:
        extra = "allow"


class PacketProcessingResult(ProcessingResult):
    """数据包处理结果"""
    original_packets: int = Field(default=0, ge=0, description="原始数据包数")
    processed_packets: int = Field(default=0, ge=0, description="处理后数据包数")
    trimmed_packets: int = Field(default=0, ge=0, description="被裁切的数据包数")
    preserved_packets: int = Field(default=0, ge=0, description="保留的数据包数")
    
    # 统计信息
    bytes_before: int = Field(default=0, ge=0, description="处理前字节数")
    bytes_after: int = Field(default=0, ge=0, description="处理后字节数")
    compression_ratio: float = Field(default=0.0, ge=0.0, description="压缩比率")
    
    def calculate_compression_ratio(self):
        """计算压缩比率"""
        if self.bytes_before > 0:
            self.compression_ratio = (self.bytes_before - self.bytes_after) / self.bytes_before * 100.0
    
    def get_processing_rate(self) -> float:
        """获取处理率"""
        if self.original_packets > 0:
            return (self.processed_packets / self.original_packets) * 100.0
        return 0.0


class PacketProcessingInterface(AlgorithmInterface):
    """数据包处理算法接口"""
    
    def get_algorithm_info(self) -> AlgorithmInfo:
        """获取算法信息（需要子类实现具体信息）"""
        return AlgorithmInfo(
            name="Generic Packet Processing",
            version="1.0.0",
            algorithm_type=AlgorithmType.PACKET_PROCESSING,
            author="PktMask Team",
            description="通用数据包处理算法接口",
            supported_formats=[".pcap", ".pcapng"],
            requirements={"scapy": ">=2.4.0"}
        )
    
    def get_default_config(self) -> PacketProcessingConfig:
        """获取默认配置"""
        return PacketProcessingConfig()
    
    def validate_config(self, config) -> ValidationResult:
        """验证配置"""
        result = ValidationResult(is_valid=True)
        
        if not isinstance(config, PacketProcessingConfig):
            result.add_error("配置必须是PacketProcessingConfig类型")
            return result
        
        # 验证数据包大小
        if config.min_packet_size >= config.max_packet_size:
            result.add_error("最小数据包大小必须小于最大数据包大小")
        
        if config.min_packet_size < 14:
            result.add_error("最小数据包大小不能小于14字节（以太网头长度）")
        
        # 验证批处理大小
        if config.batch_size < 100:
            result.add_warning("批处理大小过小，可能影响性能")
        elif config.batch_size > 10000:
            result.add_warning("批处理大小过大，可能消耗过多内存")
        
        return result
    
    # === 核心数据包处理方法 ===
    
    @abstractmethod
    def process_packet(self, packet) -> Tuple[object, bool]:
        """
        处理单个数据包
        
        Args:
            packet: 数据包对象
            
        Returns:
            Tuple[object, bool]: (处理后的数据包, 是否被修改)
        """
        pass
    
    @abstractmethod
    def batch_process_packets(self, packets: List) -> List[Tuple[object, bool]]:
        """
        批量处理数据包
        
        Args:
            packets: 数据包列表
            
        Returns:
            List[Tuple[object, bool]]: 处理结果列表
        """
        pass
    
    @abstractmethod
    def should_preserve_packet(self, packet) -> bool:
        """
        判断是否应该保留数据包
        
        Args:
            packet: 数据包对象
            
        Returns:
            bool: 是否保留
        """
        pass
    
    @abstractmethod
    def trim_packet_payload(self, packet, target_size: Optional[int] = None) -> object:
        """
        裁切数据包载荷
        
        Args:
            packet: 数据包对象
            target_size: 目标大小（可选）
            
        Returns:
            object: 裁切后的数据包
        """
        pass
    
    # === 高级功能方法 ===
    
    def process_file(self, input_path: str, output_path: str) -> PacketProcessingResult:
        """
        处理单个文件的数据包
        
        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径
            
        Returns:
            PacketProcessingResult: 处理结果
        """
        self._check_ready()
        
        try:
            # 使用性能跟踪
            tracker = self._get_performance_tracker()
            
            with tracker.track_operation(f"process_file_{input_path}"):
                result = self._do_process_file(input_path, output_path)
                
            # 添加性能指标
            result.metrics = tracker.get_current_metrics().to_dict()
            
            return result
            
        except Exception as e:
            self._logger.error(f"处理文件失败 {input_path}: {e}")
            return PacketProcessingResult(
                success=False,
                data=None,
                errors=[str(e)]
            )
    
    @abstractmethod
    def _do_process_file(self, input_path: str, output_path: str) -> PacketProcessingResult:
        """
        执行具体的文件处理逻辑（由子类实现）
        
        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径
            
        Returns:
            PacketProcessingResult: 处理结果
        """
        pass
    
    def get_processing_statistics(self) -> Dict[str, Any]:
        """
        获取处理统计信息
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        try:
            return self._get_processing_stats()
        except Exception as e:
            self._logger.error(f"获取处理统计失败: {e}")
            return {"error": str(e)}
    
    @abstractmethod
    def _get_processing_stats(self) -> Dict[str, Any]:
        """获取处理统计（由子类实现）"""
        pass
    
    def reset_statistics(self):
        """重置处理统计"""
        try:
            self._do_reset_stats()
            self._logger.info("处理统计已重置")
        except Exception as e:
            self._logger.error(f"重置处理统计失败: {e}")
    
    @abstractmethod
    def _do_reset_stats(self):
        """执行统计重置（由子类实现）"""
        pass
    
    # === 性能监控相关 ===
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """获取性能指标"""
        base_metrics = super().get_performance_metrics() if hasattr(super(), 'get_performance_metrics') else {}
        
        # 添加数据包处理特定的指标
        processing_metrics = {
            'processing_stats': self.get_processing_statistics(),
        }
        
        base_metrics.update(processing_metrics)
        return base_metrics
    
    def _get_performance_tracker(self):
        """获取性能跟踪器"""
        from .performance_interface import get_algorithm_tracker
        return get_algorithm_tracker(self.get_algorithm_info().name) 