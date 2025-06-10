#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
IP匿名化算法接口
定义IP匿名化算法的标准接口和配置
"""

from abc import abstractmethod
from typing import Dict, List, Optional, Tuple, Any
from pydantic import BaseModel, Field

from .algorithm_interface import AlgorithmInterface, AlgorithmConfig, AlgorithmInfo, AlgorithmType, ValidationResult, ProcessingResult


class IPAnonymizationConfig(AlgorithmConfig):
    """IP匿名化算法配置"""
    
    # 匿名化策略
    strategy: str = Field(default="hierarchical", description="匿名化策略")
    preserve_subnet_structure: bool = Field(default=True, description="保持子网结构")
    consistency_level: str = Field(default="high", description="一致性级别")
    
    # 缓存配置
    ip_cache_size_mb: int = Field(default=128, ge=64, le=512, description="IP缓存大小(MB)")
    mapping_cache_size: int = Field(default=10000, ge=1000, le=100000, description="映射缓存大小")
    
    # 处理配置
    batch_size: int = Field(default=1000, ge=100, le=10000, description="批处理大小")
    enable_ipv6: bool = Field(default=True, description="启用IPv6支持")
    enable_frequency_analysis: bool = Field(default=True, description="启用频率分析")
    
    # 网段配置
    min_frequency_threshold: int = Field(default=2, ge=1, le=100, description="最小频率阈值")
    preserve_high_frequency_subnets: bool = Field(default=True, description="保留高频子网")
    
    # 安全配置
    randomization_seed: Optional[str] = Field(default=None, description="随机化种子")
    anonymization_strength: str = Field(default="medium", description="匿名化强度")
    
    class Config:
        extra = "allow"


class IPMappingResult(BaseModel):
    """IP映射结果"""
    original_ip: str = Field(description="原始IP地址")
    anonymized_ip: str = Field(description="匿名化IP地址")
    ip_version: int = Field(description="IP版本 (4或6)")
    subnet_preserved: bool = Field(default=False, description="是否保留了子网结构")
    frequency_tier: str = Field(default="low", description="频率等级")
    
    class Config:
        extra = "allow"


class IPFrequencyData(BaseModel):
    """IP频率数据"""
    ipv4_frequencies: Dict[str, Dict[str, int]] = Field(default_factory=dict, description="IPv4各级频率")
    ipv6_frequencies: Dict[str, Dict[str, int]] = Field(default_factory=dict, description="IPv6各级频率")
    unique_ips: int = Field(default=0, ge=0, description="唯一IP数量")
    total_packets: int = Field(default=0, ge=0, description="总数据包数")
    
    class Config:
        extra = "allow"


class IPAnonymizationResult(ProcessingResult):
    """IP匿名化处理结果"""
    ip_mappings: List[IPMappingResult] = Field(default_factory=list, description="IP映射列表")
    frequency_data: Optional[IPFrequencyData] = Field(default=None, description="频率数据")
    subnet_consistency_report: Dict[str, Any] = Field(default_factory=dict, description="子网一致性报告")
    
    def add_mapping(self, original: str, anonymized: str, **kwargs):
        """添加IP映射"""
        mapping = IPMappingResult(
            original_ip=original,
            anonymized_ip=anonymized,
            ip_version=6 if ':' in original else 4,
            **kwargs
        )
        self.ip_mappings.append(mapping)
    
    def get_mapping_count(self) -> int:
        """获取映射数量"""
        return len(self.ip_mappings)
    
    def get_ipv4_mappings(self) -> List[IPMappingResult]:
        """获取IPv4映射"""
        return [m for m in self.ip_mappings if m.ip_version == 4]
    
    def get_ipv6_mappings(self) -> List[IPMappingResult]:
        """获取IPv6映射"""
        return [m for m in self.ip_mappings if m.ip_version == 6]


class IPAnonymizationInterface(AlgorithmInterface):
    """IP匿名化算法接口"""
    
    def get_algorithm_info(self) -> AlgorithmInfo:
        """获取算法信息（需要子类实现具体信息）"""
        # 子类应该重写此方法提供具体信息
        return AlgorithmInfo(
            name="Generic IP Anonymization",
            version="1.0.0",
            algorithm_type=AlgorithmType.IP_ANONYMIZATION,
            author="PktMask Team",
            description="通用IP匿名化算法接口",
            supported_formats=[".pcap", ".pcapng"],
            requirements={"scapy": ">=2.4.0"}
        )
    
    def get_default_config(self) -> IPAnonymizationConfig:
        """获取默认配置"""
        return IPAnonymizationConfig()
    
    def validate_config(self, config: AlgorithmConfig) -> ValidationResult:
        """验证配置"""
        result = ValidationResult(is_valid=True)
        
        if not isinstance(config, IPAnonymizationConfig):
            result.add_error("配置必须是IPAnonymizationConfig类型")
            return result
        
        # 验证策略
        valid_strategies = ["hierarchical", "random", "cryptographic", "prefix_preserving"]
        if config.strategy not in valid_strategies:
            result.add_error(f"不支持的匿名化策略: {config.strategy}")
        
        # 验证一致性级别
        valid_consistency = ["low", "medium", "high"]
        if config.consistency_level not in valid_consistency:
            result.add_error(f"不支持的一致性级别: {config.consistency_level}")
        
        # 验证匿名化强度
        valid_strength = ["low", "medium", "high", "maximum"]
        if config.anonymization_strength not in valid_strength:
            result.add_error(f"不支持的匿名化强度: {config.anonymization_strength}")
        
        # 验证缓存配置
        if config.ip_cache_size_mb < 64:
            result.add_warning("IP缓存大小可能过小，建议至少64MB")
        elif config.ip_cache_size_mb > 512:
            result.add_warning("IP缓存大小较大，注意内存使用")
        
        # 验证批处理大小
        if config.batch_size < 100:
            result.add_warning("批处理大小过小，可能影响性能")
        elif config.batch_size > 10000:
            result.add_warning("批处理大小过大，可能消耗过多内存")
        
        return result
    
    # === 核心IP匿名化方法 ===
    
    @abstractmethod
    def prescan_files(self, file_paths: List[str]) -> IPFrequencyData:
        """
        预扫描文件以收集IP频率信息
        
        Args:
            file_paths: 待扫描的文件路径列表
            
        Returns:
            IPFrequencyData: IP频率数据
        """
        pass
    
    @abstractmethod
    def build_ip_mapping(self, frequency_data: IPFrequencyData) -> Dict[str, str]:
        """
        基于频率数据构建IP映射
        
        Args:
            frequency_data: IP频率数据
            
        Returns:
            Dict[str, str]: 原始IP到匿名化IP的映射
        """
        pass
    
    @abstractmethod
    def anonymize_ip(self, ip_address: str) -> str:
        """
        匿名化单个IP地址
        
        Args:
            ip_address: 原始IP地址
            
        Returns:
            str: 匿名化后的IP地址
        """
        pass
    
    @abstractmethod
    def anonymize_packet(self, packet) -> Tuple[object, bool]:
        """
        匿名化数据包中的IP地址
        
        Args:
            packet: 数据包对象
            
        Returns:
            Tuple[object, bool]: (匿名化后的数据包, 是否进行了修改)
        """
        pass
    
    @abstractmethod
    def batch_anonymize_packets(self, packets: List) -> List[Tuple[object, bool]]:
        """
        批量匿名化数据包
        
        Args:
            packets: 数据包列表
            
        Returns:
            List[Tuple[object, bool]]: 匿名化结果列表
        """
        pass
    
    # === 高级功能方法 ===
    
    def process_file(self, input_path: str, output_path: str) -> IPAnonymizationResult:
        """
        处理单个文件的IP匿名化
        
        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径
            
        Returns:
            IPAnonymizationResult: 处理结果
        """
        self._check_ready()
        
        try:
            # 使用性能跟踪
            tracker = self._get_performance_tracker()
            
            with tracker.track_operation(f"anonymize_file_{input_path}"):
                result = self._do_process_file(input_path, output_path)
                
            # 添加性能指标
            result.metrics = tracker.get_current_metrics().to_dict()
            
            return result
            
        except Exception as e:
            self._logger.error(f"处理文件失败 {input_path}: {e}")
            return IPAnonymizationResult(
                success=False,
                data=None,
                errors=[str(e)]
            )
    
    @abstractmethod
    def _do_process_file(self, input_path: str, output_path: str) -> IPAnonymizationResult:
        """
        执行具体的文件处理逻辑（由子类实现）
        
        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径
            
        Returns:
            IPAnonymizationResult: 处理结果
        """
        pass
    
    def get_ip_mapping(self) -> Dict[str, str]:
        """
        获取当前的IP映射
        
        Returns:
            Dict[str, str]: IP映射字典
        """
        return self._get_current_mapping()
    
    @abstractmethod
    def _get_current_mapping(self) -> Dict[str, str]:
        """获取当前映射（由子类实现）"""
        pass
    
    def reset_mapping(self):
        """重置IP映射"""
        try:
            self._do_reset_mapping()
            self._logger.info("IP映射已重置")
        except Exception as e:
            self._logger.error(f"重置IP映射失败: {e}")
    
    @abstractmethod
    def _do_reset_mapping(self):
        """执行映射重置（由子类实现）"""
        pass
    
    def validate_subnet_consistency(self) -> Dict[str, Any]:
        """
        验证子网一致性
        
        Returns:
            Dict[str, Any]: 一致性验证报告
        """
        try:
            return self._do_validate_consistency()
        except Exception as e:
            self._logger.error(f"验证子网一致性失败: {e}")
            return {"error": str(e), "valid": False}
    
    @abstractmethod
    def _do_validate_consistency(self) -> Dict[str, Any]:
        """执行一致性验证（由子类实现）"""
        pass
    
    # === 性能监控相关 ===
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """获取性能指标"""
        base_metrics = super().get_performance_metrics() if hasattr(super(), 'get_performance_metrics') else {}
        
        # 添加IP匿名化特定的指标
        ip_metrics = {
            'ip_mapping_size': len(self.get_ip_mapping()),
            'ipv4_mappings': len([k for k in self.get_ip_mapping().keys() if '.' in k]),
            'ipv6_mappings': len([k for k in self.get_ip_mapping().keys() if ':' in k]),
        }
        
        base_metrics.update(ip_metrics)
        return base_metrics
    
    def _get_performance_tracker(self):
        """获取性能跟踪器"""
        from .performance_interface import get_algorithm_tracker
        return get_algorithm_tracker(self.get_algorithm_info().name)
    
    # === 辅助方法 ===
    
    def is_ipv4(self, ip_address: str) -> bool:
        """检查是否为IPv4地址"""
        return '.' in ip_address and ':' not in ip_address
    
    def is_ipv6(self, ip_address: str) -> bool:
        """检查是否为IPv6地址"""
        return ':' in ip_address
    
    def extract_subnet_prefix(self, ip_address: str, prefix_length: int) -> str:
        """提取子网前缀"""
        try:
            import ipaddress
            if self.is_ipv4(ip_address):
                network = ipaddress.IPv4Network(f"{ip_address}/{prefix_length}", strict=False)
                return str(network.network_address)
            else:
                network = ipaddress.IPv6Network(f"{ip_address}/{prefix_length}", strict=False)
                return str(network.network_address)
        except Exception as e:
            self._logger.warning(f"提取子网前缀失败 {ip_address}: {e}")
            return ip_address 