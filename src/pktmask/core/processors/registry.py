"""
简化的处理器注册表

替代复杂的插件发现、依赖管理、沙箱等企业级功能，
使用简单直观的注册表模式。
"""
import logging
from typing import Dict, Type, List, Optional
from .base_processor import BaseProcessor, ProcessorConfig


class ProcessorRegistry:
    """处理器注册表
    
    简单的注册表系统，替代复杂的插件管理架构。
    支持基本的处理器注册、获取和发现功能。
    """
    
    # 内置处理器映射 (延迟导入避免循环依赖)
    _processors: Dict[str, Type[BaseProcessor]] = {}
    _loaded = False
    
    @classmethod
    def _load_builtin_processors(cls):
        """Lazy load built-in processors"""
        if cls._loaded:
            return
            
        try:
            # Lazy import to avoid circular dependencies
            from .ip_anonymizer import IPAnonymizer  # Legacy BaseProcessor implementation
            from .deduplicator import Deduplicator
            from ..pipeline.stages.mask_payload_v2.stage import NewMaskPayloadStage as MaskingProcessor
            from ..pipeline.stages.ip_anonymization import IPAnonymizationStage  # New StageBase implementation
            from ..pipeline.stages.dedup import DeduplicationStage  # New StageBase implementation

            cls._processors.update({
                # Standard naming keys (consistent with GUI interface)
                'anonymize_ips': IPAnonymizationStage,  # Migrated to StageBase
                'remove_dupes': DeduplicationStage,  # Migrated to StageBase (Phase 2)
                'mask_payloads': MaskingProcessor,

                # Old keys → aliases, maintain backward compatibility and throw DeprecationWarning
                'anon_ip': IPAnonymizationStage,  # Migrated to StageBase
                'dedup_packet': DeduplicationStage,  # Migrated to StageBase (Phase 2)
                'mask_payload': MaskingProcessor,
            })
            cls._loaded = True
            
        except ImportError as e:
            print(f"Error loading built-in processors: {e}")
            print("Warning: Unable to load payload trimming processor")
    
    @classmethod
    def get_processor(cls, name: str, config: ProcessorConfig) -> BaseProcessor:
        """获取处理器实例"""
        cls._load_builtin_processors()

        if name not in cls._processors:
            available = list(cls._processors.keys())
            raise ValueError(f"Unknown processor: {name}. Available processors: {available}")

        processor_class = cls._processors[name]

        # 特殊处理：为 StageBase 实现提供正确的配置格式
        if name in ['anonymize_ips', 'anon_ip']:
            # 转换 ProcessorConfig 为 IPAnonymizationStage 期望的字典格式
            stage_config = cls._create_ip_anonymization_config(config)
            logger = logging.getLogger(__name__)
            logger.info(f"Created IP anonymization config for StageBase: method=prefix_preserving")
            return processor_class(stage_config)
        elif name in ['remove_dupes', 'dedup_packet']:
            # 转换 ProcessorConfig 为 DeduplicationStage 期望的字典格式
            stage_config = cls._create_deduplication_config(config)
            logger = logging.getLogger(__name__)
            logger.info(f"Created deduplication config for StageBase")
            return processor_class(stage_config)
        elif name in ['mask_payloads', 'mask_payload']:
            # 转换 ProcessorConfig 为 NewMaskPayloadStage 期望的字典格式
            stage_config = cls._create_mask_payload_config(config)
            logger = logging.getLogger(__name__)
            logger.info(f"Created mask payload config for GUI: preserve_application_data=False")
            return processor_class(stage_config)

        # BaseProcessor 实现使用原有配置
        return processor_class(config)
    
    @classmethod
    def register_processor(cls, name: str, processor_class: Type[BaseProcessor]):
        """注册新的处理器"""
        if not issubclass(processor_class, BaseProcessor):
            raise TypeError(f"Processor class must inherit from BaseProcessor: {processor_class}")
            
        cls._processors[name] = processor_class
        print(f"Registered processor: {name} -> {processor_class.__name__}")
    
    @classmethod
    def list_processors(cls) -> List[str]:
        """列出所有可用处理器"""
        cls._load_builtin_processors()
        return list(cls._processors.keys())
    
    @classmethod
    def get_processor_info(cls, name: str) -> Dict[str, str]:
        """获取处理器信息"""
        cls._load_builtin_processors()

        if name not in cls._processors:
            raise ValueError(f"Unknown processor: {name}")

        processor_class = cls._processors[name]

        # 根据处理器类型创建临时实例获取信息
        if name in ['anonymize_ips', 'anon_ip']:
            # StageBase 实现需要字典配置
            temp_config = cls._create_ip_anonymization_config(ProcessorConfig(name=name))
            temp_instance = processor_class(temp_config)
        elif name in ['mask_payloads', 'mask_payload']:
            # StageBase 实现需要字典配置
            temp_config = cls._create_mask_payload_config(ProcessorConfig(name=name))
            temp_instance = processor_class(temp_config)
        else:
            # BaseProcessor 实现使用 ProcessorConfig
            temp_config = ProcessorConfig(name=name)
            temp_instance = processor_class(temp_config)

        return {
            'name': name,
            'display_name': temp_instance.get_display_name(),
            'description': temp_instance.get_description(),
            'class': processor_class.__name__
        }
    
    @classmethod
    def create_processor_set(cls, processor_names: List[str]) -> List[BaseProcessor]:
        """创建一组处理器实例"""
        processors = []
        
        for name in processor_names:
            config = ProcessorConfig(enabled=True, name=name)
            processor = cls.get_processor(name, config)
            processors.append(processor)
            
        return processors
    
    @classmethod
    def is_processor_available(cls, name: str) -> bool:
        """检查处理器是否可用"""
        cls._load_builtin_processors()
        return name in cls._processors
    
    @classmethod
    def unregister_processor(cls, name: str) -> bool:
        """注销处理器 (主要用于测试)"""
        if name in cls._processors:
            del cls._processors[name]
            return True
        return False
        
    @classmethod
    def clear_registry(cls):
        """清空注册表 (主要用于测试)"""
        cls._processors.clear()
        cls._loaded = False

    @classmethod
    def _create_mask_payload_config(cls, processor_config: ProcessorConfig) -> Dict:
        """为 NewMaskPayloadStage 创建正确的配置格式

        Args:
            processor_config: ProcessorConfig 对象

        Returns:
            NewMaskPayloadStage 期望的字典配置
        """
        # 获取应用配置中的 TShark 路径
        try:
            from pktmask.config.settings import get_app_config
            app_config = get_app_config()
            tshark_path = app_config.tools.tshark.custom_executable
        except Exception:
            # 如果获取配置失败，使用默认值
            tshark_path = "tshark"

        # 创建 NewMaskPayloadStage 期望的配置格式
        stage_config = {
            "protocol": "tls",
            "mode": "enhanced",
            "marker_config": {
                "tshark_path": tshark_path,
                "preserve": {
                    # 关键修复：确保 TLS-23 ApplicationData 被掩码
                    "application_data": False,  # 这是修复 TLS-23 掩码失效的关键
                    "handshake": True,
                    "alert": True,
                    "change_cipher_spec": True,
                    "heartbeat": True
                }
            },
            "masker_config": {
                "chunk_size": 1000,
                "verify_checksums": True,
                "preserve_ratio": 0.3
            }
        }

        return stage_config

    @classmethod
    def _create_ip_anonymization_config(cls, processor_config: ProcessorConfig) -> Dict:
        """为 IPAnonymizationStage 创建正确的配置格式

        Args:
            processor_config: ProcessorConfig 对象

        Returns:
            IPAnonymizationStage 期望的字典配置
        """
        # 创建 IPAnonymizationStage 期望的配置格式
        stage_config = {
            "method": "prefix_preserving",  # 默认匿名化方法
            "ipv4_prefix": 24,  # IPv4 前缀长度
            "ipv6_prefix": 64,  # IPv6 前缀长度
            "enabled": processor_config.enabled,
            "name": processor_config.name or "ip_anonymization",
            "priority": processor_config.priority
        }

        return stage_config

    @classmethod
    def _create_deduplication_config(cls, processor_config: ProcessorConfig) -> Dict:
        """为 DeduplicationStage 创建正确的配置格式

        Args:
            processor_config: ProcessorConfig 对象

        Returns:
            DeduplicationStage 期望的字典配置
        """
        # 创建 DeduplicationStage 期望的配置格式
        stage_config = {
            "enabled": processor_config.enabled,
            "name": processor_config.name or "deduplication",
            "priority": processor_config.priority,
            # DeduplicationStage 目前不需要额外配置参数
            # 保留扩展性，未来可以添加去重算法选择等配置
        }

        return stage_config

    # Phase 4.2: 新增便利方法
    @classmethod
    def get_active_trimmer_class(cls) -> Type[BaseProcessor]:
        """获取当前活跃的载荷裁切处理器类"""
        cls._load_builtin_processors()
        return cls._processors.get('trim_packet', None)
        
    @classmethod
    def is_enhanced_mode_enabled(cls) -> bool:
        """检查是否启用了增强模式 - 现在基于双模块架构"""
        # 双模块架构(NewMaskPayloadStage)始终为增强模式
        return True