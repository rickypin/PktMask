"""
统一的处理器注册表

简化的StageBase处理器注册表，提供统一的处理器访问接口。
所有处理器都基于StageBase架构，使用标准化配置。
"""
import logging
from typing import Dict, Type, List, Optional, Any
from ..pipeline.base_stage import StageBase


class ProcessorRegistry:
    """统一处理器注册表

    简化的StageBase处理器注册表，所有处理器都使用统一的配置格式。
    """

    # StageBase处理器映射 (延迟导入避免循环依赖)
    _processors: Dict[str, Type[StageBase]] = {}
    _default_configs: Dict[str, Dict[str, Any]] = {}
    _loaded = False
    
    @classmethod
    def _load_builtin_processors(cls):
        """Lazy load built-in processors and their default configurations"""
        if cls._loaded:
            return

        try:
            # Import all StageBase implementations
            from ..pipeline.stages.mask_payload_v2.stage import NewMaskPayloadStage as MaskingProcessor
            from ..pipeline.stages.ip_anonymization_unified import UnifiedIPAnonymizationStage
            from ..pipeline.stages.deduplication_unified import UnifiedDeduplicationStage

            # Register processors with standard naming
            cls._processors.update({
                # Standard naming keys (consistent with GUI interface)
                'anonymize_ips': UnifiedIPAnonymizationStage,
                'remove_dupes': UnifiedDeduplicationStage,
                'mask_payloads': MaskingProcessor,

                # Legacy aliases for backward compatibility
                'anon_ip': UnifiedIPAnonymizationStage,
                'dedup_packet': UnifiedDeduplicationStage,
                'mask_payload': MaskingProcessor,
            })

            # Define default configurations for each processor type
            cls._default_configs = {
                'anonymize_ips': cls._get_ip_anonymization_config(),
                'remove_dupes': cls._get_deduplication_config(),
                'mask_payloads': cls._get_mask_payload_config(),
            }

            cls._loaded = True

        except ImportError as e:
            logging.error(f"Error loading built-in processors: {e}")
            raise RuntimeError(f"Failed to load required processors: {e}")
    
    @classmethod
    def get_processor(cls, name: str, config: Optional[Dict[str, Any]] = None) -> StageBase:
        """获取处理器实例

        Args:
            name: 处理器名称
            config: 可选的配置字典，如果未提供则使用默认配置

        Returns:
            StageBase: 处理器实例
        """
        cls._load_builtin_processors()

        if name not in cls._processors:
            available = list(cls._processors.keys())
            raise ValueError(f"Unknown processor: {name}. Available processors: {available}")

        processor_class = cls._processors[name]

        # 获取标准化名称（处理别名）
        standard_name = cls._get_standard_name(name)

        # 使用提供的配置或默认配置
        if config is None:
            stage_config = cls._default_configs[standard_name].copy()
        else:
            # 合并用户配置和默认配置
            stage_config = cls._default_configs[standard_name].copy()
            stage_config.update(config)

        logger = logging.getLogger(__name__)
        logger.info(f"Creating {standard_name} processor with config: {stage_config}")

        return processor_class(stage_config)
    
    @classmethod
    def register_processor(cls, name: str, processor_class: Type[StageBase],
                          default_config: Optional[Dict[str, Any]] = None):
        """注册新的处理器

        Args:
            name: 处理器名称
            processor_class: 处理器类（必须继承自StageBase）
            default_config: 默认配置字典
        """
        if not issubclass(processor_class, StageBase):
            raise TypeError(f"Processor class must inherit from StageBase: {processor_class}")

        cls._processors[name] = processor_class
        if default_config:
            cls._default_configs[name] = default_config

        logger = logging.getLogger(__name__)
        logger.info(f"Registered processor: {name} -> {processor_class.__name__}")

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
        standard_name = cls._get_standard_name(name)

        # 使用默认配置创建临时实例获取信息
        temp_config = cls._default_configs[standard_name].copy()
        temp_instance = processor_class(temp_config)

        return {
            'name': name,
            'display_name': temp_instance.get_display_name(),
            'description': temp_instance.get_description(),
            'class': processor_class.__name__
        }
    
    @classmethod
    def create_processor_set(cls, processor_names: List[str],
                           configs: Optional[Dict[str, Dict[str, Any]]] = None) -> List[StageBase]:
        """创建一组处理器实例

        Args:
            processor_names: 处理器名称列表
            configs: 可选的配置字典，键为处理器名称，值为配置字典

        Returns:
            List[StageBase]: 处理器实例列表
        """
        processors = []

        for name in processor_names:
            config = configs.get(name) if configs else None
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
            if name in cls._default_configs:
                del cls._default_configs[name]
            return True
        return False

    @classmethod
    def clear_registry(cls):
        """清空注册表 (主要用于测试)"""
        cls._processors.clear()
        cls._default_configs.clear()
        cls._loaded = False

    @classmethod
    def _get_standard_name(cls, name: str) -> str:
        """获取标准化处理器名称（处理别名映射）"""
        alias_mapping = {
            'anon_ip': 'anonymize_ips',
            'dedup_packet': 'remove_dupes',
            'mask_payload': 'mask_payloads',
        }
        return alias_mapping.get(name, name)

    @classmethod
    def _get_mask_payload_config(cls) -> Dict[str, Any]:
        """获取载荷掩码处理器的默认配置"""
        # 获取应用配置中的 TShark 路径
        try:
            from pktmask.config.settings import get_app_config
            app_config = get_app_config()
            tshark_path = app_config.tools.tshark.custom_executable
        except Exception:
            # 如果获取配置失败，使用默认值
            tshark_path = "tshark"

        return {
            "protocol": "tls",
            "mode": "enhanced",
            "marker_config": {
                "tshark_path": tshark_path,
                "preserve": {
                    "application_data": False,  # 确保 TLS-23 ApplicationData 被掩码
                    "handshake": True,
                    "alert": True,
                    "change_cipher_spec": True,
                    "heartbeat": True
                }
            },
            "masker_config": {
                "chunk_size": 1000,
                "verify_checksums": True
            }
        }

    @classmethod
    def _get_ip_anonymization_config(cls) -> Dict[str, Any]:
        """获取IP匿名化处理器的默认配置"""
        return {
            "method": "prefix_preserving",  # 默认匿名化方法
            "ipv4_prefix": 24,  # IPv4 前缀长度
            "ipv6_prefix": 64,  # IPv6 前缀长度
            "enabled": True,
            "name": "ip_anonymization",
            "priority": 0
        }

    @classmethod
    def _get_deduplication_config(cls) -> Dict[str, Any]:
        """获取去重处理器的默认配置"""
        return {
            "algorithm": "md5",  # 默认哈希算法（与原实现保持一致）
            "enabled": True,
            "name": "deduplication",
            "priority": 0
        }

    @classmethod
    def is_enhanced_mode_enabled(cls) -> bool:
        """检查是否启用了增强模式 - 基于双模块架构"""
        # 双模块架构(NewMaskPayloadStage)始终为增强模式
        return True