#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
算法配置模型系统 - Phase 6.3
为不同类型的算法定义专门的配置模型
"""

from typing import Dict, List, Optional, Union, Any
from enum import Enum
from pydantic import BaseModel, Field, validator, model_validator
from pathlib import Path

from ..algorithms.interfaces.algorithm_interface import AlgorithmConfig, AlgorithmType


class CacheStrategy(str, Enum):
    """缓存策略枚举"""
    NONE = "none"
    LRU = "lru"
    FIFO = "fifo"
    TTL = "ttl"
    ADAPTIVE = "adaptive"


class CompressionLevel(str, Enum):
    """压缩级别枚举"""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    MAXIMUM = "maximum"


class AnonymizationMethod(str, Enum):
    """匿名化方法枚举"""
    HASH = "hash"
    ENCRYPT = "encrypt"
    MASK = "mask"
    RANDOMIZE = "randomize"
    HIERARCHICAL = "hierarchical"


class DeduplicationStrategy(str, Enum):
    """去重策略枚举"""
    HASH_BASED = "hash_based"
    CONTENT_BASED = "content_based"
    TIMESTAMP_BASED = "timestamp_based"
    HYBRID = "hybrid"


# ===== IP匿名化算法配置 =====

class IPAnonymizationConfig(AlgorithmConfig):
    """IP匿名化算法配置"""
    
    # 匿名化方法配置
    anonymization_method: AnonymizationMethod = Field(
        default=AnonymizationMethod.HIERARCHICAL,
        description="IP匿名化方法"
    )
    
    # 分层匿名化配置
    preserve_subnet_bits: int = Field(
        default=24,
        ge=8,
        le=32,
        description="保留的子网位数"
    )
    
    anonymization_levels: List[int] = Field(
        default=[8, 16, 24],
        description="分层匿名化级别"
    )
    
    # 哈希配置
    hash_algorithm: str = Field(
        default="sha256",
        description="哈希算法类型"
    )
    
    hash_salt: Optional[str] = Field(
        default=None,
        description="哈希盐值"
    )
    
    # 加密配置
    encryption_key: Optional[str] = Field(
        default=None,
        description="加密密钥"
    )
    
    # 缓存配置
    cache_strategy: CacheStrategy = Field(
        default=CacheStrategy.LRU,
        description="缓存策略"
    )
    
    cache_size: int = Field(
        default=10000,
        ge=100,
        le=1000000,
        description="缓存大小"
    )
    
    cache_ttl_seconds: int = Field(
        default=3600,
        ge=60,
        le=86400,
        description="缓存TTL(秒)"
    )
    
    # 性能配置
    batch_size: int = Field(
        default=1000,
        ge=1,
        le=10000,
        description="批处理大小"
    )
    
    parallel_workers: int = Field(
        default=4,
        ge=1,
        le=16,
        description="并行工作线程数"
    )
    
    @validator('anonymization_levels')
    def validate_anonymization_levels(cls, v):
        if not v:
            raise ValueError("匿名化级别不能为空")
        if not all(8 <= level <= 32 for level in v):
            raise ValueError("匿名化级别必须在8-32之间")
        if len(set(v)) != len(v):
            raise ValueError("匿名化级别不能重复")
        return sorted(v)
    
    @validator('hash_algorithm')
    def validate_hash_algorithm(cls, v):
        allowed_algorithms = ['md5', 'sha1', 'sha256', 'sha512']
        if v.lower() not in allowed_algorithms:
            raise ValueError(f"哈希算法必须是: {', '.join(allowed_algorithms)}")
        return v.lower()


# ===== 数据包处理算法配置 =====

class PacketProcessingConfig(AlgorithmConfig):
    """数据包处理算法配置"""
    
    # 处理模式
    processing_mode: str = Field(
        default="streaming",
        description="处理模式: streaming, batch, hybrid"
    )
    
    # 过滤配置
    enable_filtering: bool = Field(
        default=True,
        description="是否启用数据包过滤"
    )
    
    filter_protocols: List[str] = Field(
        default=["TCP", "UDP", "ICMP"],
        description="要处理的协议类型"
    )
    
    filter_ports: List[int] = Field(
        default=[],
        description="要过滤的端口号"
    )
    
    min_packet_size: int = Field(
        default=64,
        ge=1,
        le=65535,
        description="最小数据包大小(字节)"
    )
    
    max_packet_size: int = Field(
        default=65535,
        ge=64,
        le=65535,
        description="最大数据包大小(字节)"
    )
    
    # 裁切配置
    enable_trimming: bool = Field(
        default=True,
        description="是否启用数据包裁切"
    )
    
    trim_size: int = Field(
        default=96,
        ge=64,
        le=1500,
        description="裁切后的数据包大小"
    )
    
    preserve_headers: bool = Field(
        default=True,
        description="是否保留协议头部"
    )
    
    # 压缩配置
    enable_compression: bool = Field(
        default=False,
        description="是否启用压缩"
    )
    
    compression_level: CompressionLevel = Field(
        default=CompressionLevel.MEDIUM,
        description="压缩级别"
    )
    
    compression_algorithm: str = Field(
        default="gzip",
        description="压缩算法"
    )
    
    # 缓存配置
    enable_result_cache: bool = Field(
        default=True,
        description="是否启用结果缓存"
    )
    
    cache_strategy: CacheStrategy = Field(
        default=CacheStrategy.ADAPTIVE,
        description="缓存策略"
    )
    
    cache_size: int = Field(
        default=50000,
        ge=1000,
        le=1000000,
        description="缓存大小"
    )
    
    # 性能配置
    buffer_size: int = Field(
        default=8192,
        ge=1024,
        le=65536,
        description="缓冲区大小"
    )
    
    worker_threads: int = Field(
        default=8,
        ge=1,
        le=32,
        description="工作线程数"
    )
    
    io_timeout_seconds: int = Field(
        default=30,
        ge=5,
        le=300,
        description="IO超时时间(秒)"
    )
    
    @validator('processing_mode')
    def validate_processing_mode(cls, v):
        allowed_modes = ['streaming', 'batch', 'hybrid']
        if v not in allowed_modes:
            raise ValueError(f"处理模式必须是: {', '.join(allowed_modes)}")
        return v
    
    @validator('filter_protocols')
    def validate_filter_protocols(cls, v):
        allowed_protocols = ['TCP', 'UDP', 'ICMP', 'HTTP', 'HTTPS', 'FTP', 'SSH']
        for protocol in v:
            if protocol.upper() not in allowed_protocols:
                raise ValueError(f"不支持的协议: {protocol}")
        return [p.upper() for p in v]
    
    @model_validator(mode='after')
    def validate_packet_sizes(self):
        if self.min_packet_size >= self.max_packet_size:
            raise ValueError("最小数据包大小必须小于最大数据包大小")
        return self


# ===== 去重算法配置 =====

class DeduplicationConfig(AlgorithmConfig):
    """去重算法配置"""
    
    # 去重策略
    deduplication_strategy: DeduplicationStrategy = Field(
        default=DeduplicationStrategy.HASH_BASED,
        description="去重策略"
    )
    
    # 哈希配置
    hash_algorithm: str = Field(
        default="md5",
        description="哈希算法类型"
    )
    
    hash_chunk_size: int = Field(
        default=8192,
        ge=1024,
        le=65536,
        description="哈希块大小"
    )
    
    # 比较配置
    enable_deep_comparison: bool = Field(
        default=False,
        description="是否启用深度比较"
    )
    
    comparison_fields: List[str] = Field(
        default=["src_ip", "dst_ip", "src_port", "dst_port", "protocol"],
        description="比较字段列表"
    )
    
    # 时间窗口配置
    time_window_seconds: int = Field(
        default=60,
        ge=1,
        le=3600,
        description="时间窗口大小(秒)"
    )
    
    enable_sliding_window: bool = Field(
        default=True,
        description="是否启用滑动窗口"
    )
    
    # 缓存配置
    cache_strategy: CacheStrategy = Field(
        default=CacheStrategy.TTL,
        description="缓存策略"
    )
    
    max_cache_entries: int = Field(
        default=100000,
        ge=1000,
        le=10000000,
        description="最大缓存条目数"
    )
    
    cache_cleanup_interval: int = Field(
        default=300,
        ge=60,
        le=3600,
        description="缓存清理间隔(秒)"
    )
    
    # 性能配置
    batch_processing_size: int = Field(
        default=5000,
        ge=100,
        le=50000,
        description="批处理大小"
    )
    
    max_memory_usage_mb: int = Field(
        default=1024,
        ge=256,
        le=8192,
        description="最大内存使用(MB)"
    )
    
    enable_parallel_processing: bool = Field(
        default=True,
        description="是否启用并行处理"
    )
    
    parallel_threshold: int = Field(
        default=1000,
        ge=100,
        le=10000,
        description="并行处理阈值"
    )
    
    @validator('hash_algorithm')
    def validate_hash_algorithm(cls, v):
        allowed_algorithms = ['md5', 'sha1', 'sha256', 'crc32']
        if v.lower() not in allowed_algorithms:
            raise ValueError(f"哈希算法必须是: {', '.join(allowed_algorithms)}")
        return v.lower()
    
    @validator('comparison_fields')
    def validate_comparison_fields(cls, v):
        allowed_fields = [
            'src_ip', 'dst_ip', 'src_port', 'dst_port', 'protocol',
            'timestamp', 'payload', 'packet_size', 'flags'
        ]
        for field in v:
            if field not in allowed_fields:
                raise ValueError(f"不支持的比较字段: {field}")
        return v


# ===== 自定义算法配置 =====

class CustomAlgorithmConfig(AlgorithmConfig):
    """自定义算法配置基类"""
    
    # 自定义参数字典
    custom_parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="自定义参数字典"
    )
    
    # 配置文件路径
    config_file_path: Optional[str] = Field(
        default=None,
        description="外部配置文件路径"
    )
    
    # 插件配置
    plugin_name: Optional[str] = Field(
        default=None,
        description="插件名称"
    )
    
    plugin_version: Optional[str] = Field(
        default=None,
        description="插件版本"
    )
    
    # 扩展配置
    extensions: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="扩展配置"
    )
    
    # 验证钩子
    validation_hooks: List[str] = Field(
        default_factory=list,
        description="验证钩子函数名列表"
    )
    
    @validator('config_file_path')
    def validate_config_file_path(cls, v):
        if v is not None:
            path = Path(v)
            if not path.suffix.lower() in ['.json', '.yaml', '.yml', '.toml']:
                raise ValueError("配置文件必须是 .json, .yaml, .yml 或 .toml 格式")
        return v


# ===== 配置工厂类 =====

class AlgorithmConfigFactory:
    """算法配置工厂类"""
    
    _config_mapping = {
        AlgorithmType.IP_ANONYMIZATION: IPAnonymizationConfig,
        AlgorithmType.PACKET_PROCESSING: PacketProcessingConfig,
        AlgorithmType.DEDUPLICATION: DeduplicationConfig,
        AlgorithmType.CUSTOM: CustomAlgorithmConfig,
    }
    
    @classmethod
    def create_config(
        cls,
        algorithm_type: AlgorithmType,
        **kwargs
    ) -> AlgorithmConfig:
        """
        创建指定类型的算法配置
        
        Args:
            algorithm_type: 算法类型
            **kwargs: 配置参数
            
        Returns:
            AlgorithmConfig: 算法配置实例
        """
        config_class = cls._config_mapping.get(algorithm_type)
        if config_class is None:
            raise ValueError(f"不支持的算法类型: {algorithm_type}")
        
        return config_class(**kwargs)
    
    @classmethod
    def get_config_class(cls, algorithm_type: AlgorithmType) -> type:
        """
        获取指定算法类型的配置类
        
        Args:
            algorithm_type: 算法类型
            
        Returns:
            type: 配置类
        """
        config_class = cls._config_mapping.get(algorithm_type)
        if config_class is None:
            raise ValueError(f"不支持的算法类型: {algorithm_type}")
        return config_class
    
    @classmethod
    def register_config_class(
        cls,
        algorithm_type: AlgorithmType,
        config_class: type
    ):
        """
        注册新的配置类
        
        Args:
            algorithm_type: 算法类型
            config_class: 配置类
        """
        if not issubclass(config_class, AlgorithmConfig):
            raise ValueError("配置类必须继承自AlgorithmConfig")
        
        cls._config_mapping[algorithm_type] = config_class
    
    @classmethod
    def list_supported_types(cls) -> List[AlgorithmType]:
        """
        列出支持的算法类型
        
        Returns:
            List[AlgorithmType]: 支持的算法类型列表
        """
        return list(cls._config_mapping.keys())


# ===== 配置模板管理 =====

class ConfigTemplate(BaseModel):
    """配置模板"""
    name: str = Field(description="模板名称")
    description: str = Field(description="模板描述")
    algorithm_type: AlgorithmType = Field(description="算法类型")
    config_data: Dict[str, Any] = Field(description="配置数据")
    tags: List[str] = Field(default_factory=list, description="标签")
    author: Optional[str] = Field(default=None, description="作者")
    version: str = Field(default="1.0.0", description="版本")
    created_at: Optional[str] = Field(default=None, description="创建时间")


class ConfigTemplateManager:
    """配置模板管理器"""
    
    def __init__(self):
        self._templates: Dict[str, ConfigTemplate] = {}
        self._load_default_templates()
    
    def _load_default_templates(self):
        """加载默认模板"""
        # IP匿名化默认模板
        self.add_template(ConfigTemplate(
            name="ip_anonymization_default",
            description="IP匿名化默认配置",
            algorithm_type=AlgorithmType.IP_ANONYMIZATION,
            config_data={
                "anonymization_method": "hierarchical",
                "preserve_subnet_bits": 24,
                "cache_strategy": "lru",
                "cache_size": 10000,
                "batch_size": 1000
            },
            tags=["default", "ip", "anonymization"]
        ))
        
        # 高性能IP匿名化模板
        self.add_template(ConfigTemplate(
            name="ip_anonymization_high_performance",
            description="高性能IP匿名化配置",
            algorithm_type=AlgorithmType.IP_ANONYMIZATION,
            config_data={
                "anonymization_method": "hash",
                "hash_algorithm": "md5",
                "cache_strategy": "adaptive",
                "cache_size": 100000,
                "batch_size": 5000,
                "parallel_workers": 8
            },
            tags=["performance", "ip", "anonymization"]
        ))
        
        # 数据包处理默认模板
        self.add_template(ConfigTemplate(
            name="packet_processing_default",
            description="数据包处理默认配置",
            algorithm_type=AlgorithmType.PACKET_PROCESSING,
            config_data={
                "processing_mode": "streaming",
                "enable_filtering": True,
                "filter_protocols": ["TCP", "UDP"],
                "enable_trimming": True,
                "trim_size": 96,
                "cache_strategy": "adaptive"
            },
            tags=["default", "packet", "processing"]
        ))
        
        # 去重算法默认模板
        self.add_template(ConfigTemplate(
            name="deduplication_default",
            description="去重算法默认配置",
            algorithm_type=AlgorithmType.DEDUPLICATION,
            config_data={
                "deduplication_strategy": "hash_based",
                "hash_algorithm": "md5",
                "time_window_seconds": 60,
                "cache_strategy": "ttl",
                "max_cache_entries": 100000
            },
            tags=["default", "deduplication"]
        ))
    
    def add_template(self, template: ConfigTemplate):
        """添加配置模板"""
        self._templates[template.name] = template
    
    def get_template(self, name: str) -> Optional[ConfigTemplate]:
        """获取配置模板"""
        return self._templates.get(name)
    
    def list_templates(
        self,
        algorithm_type: Optional[AlgorithmType] = None,
        tags: Optional[List[str]] = None
    ) -> List[ConfigTemplate]:
        """列出配置模板"""
        templates = list(self._templates.values())
        
        if algorithm_type:
            templates = [t for t in templates if t.algorithm_type == algorithm_type]
        
        if tags:
            templates = [
                t for t in templates
                if any(tag in t.tags for tag in tags)
            ]
        
        return templates
    
    def create_config_from_template(
        self,
        template_name: str,
        overrides: Optional[Dict[str, Any]] = None
    ) -> AlgorithmConfig:
        """从模板创建配置"""
        template = self.get_template(template_name)
        if template is None:
            raise ValueError(f"模板不存在: {template_name}")
        
        config_data = template.config_data.copy()
        if overrides:
            config_data.update(overrides)
        
        return AlgorithmConfigFactory.create_config(
            template.algorithm_type,
            **config_data
        )


# 全局配置模板管理器实例
config_template_manager = ConfigTemplateManager() 