"""
统一的处理器注册表

简化的StageBase处理器注册表，提供统一的处理器访问接口。
所有处理器都基于StageBase架构，使用标准化配置。
"""

import logging
from typing import Any, Dict, List, Optional, Type

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
            from ..pipeline.stages.anonymization_stage import AnonymizationStage
            from ..pipeline.stages.deduplication_stage import DeduplicationStage
            from ..pipeline.stages.masking_stage.stage import MaskingStage

            # Register processors with standard naming only
            cls._processors.update(
                {
                    # Standard naming keys (consistent with GUI interface)
                    "anonymize_ips": AnonymizationStage,
                    "remove_dupes": DeduplicationStage,
                    "mask_payloads": MaskingStage,
                }
            )

            # Define default configurations for each processor type
            cls._default_configs = {
                "anonymize_ips": cls._get_ip_anonymization_config(),
                "remove_dupes": cls._get_deduplication_config(),
                "mask_payloads": cls._get_mask_payload_config(),
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
    def register_processor(
        cls,
        name: str,
        processor_class: Type[StageBase],
        default_config: Optional[Dict[str, Any]] = None,
    ):
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
            "name": name,
            "display_name": temp_instance.get_display_name(),
            "description": temp_instance.get_description(),
            "class": processor_class.__name__,
        }

    @classmethod
    def create_processor_set(
        cls,
        processor_names: List[str],
        configs: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> List[StageBase]:
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
        """Unregister processor (mainly for testing)"""
        if name in cls._processors:
            del cls._processors[name]
            if name in cls._default_configs:
                del cls._default_configs[name]
            return True
        return False

    @classmethod
    def clear_registry(cls):
        """Clear registry (mainly for testing)"""
        cls._processors.clear()
        cls._default_configs.clear()
        cls._loaded = False

    @classmethod
    def _get_standard_name(cls, name: str) -> str:
        """Get standardized processor name (handle alias mapping)"""
        alias_mapping = {
            "anon_ip": "anonymize_ips",
            "dedup_packet": "remove_dupes",
            "mask_payload": "mask_payloads",
        }
        return alias_mapping.get(name, name)

    @classmethod
    def _get_mask_payload_config(cls) -> Dict[str, Any]:
        """Get default configuration for payload masking processor"""
        # Get TShark path from application configuration
        try:
            from pktmask.config.settings import get_app_config

            app_config = get_app_config()
            tshark_path = app_config.tools.tshark.custom_executable
        except Exception:
            # Use default value if configuration retrieval fails
            tshark_path = "tshark"

        return {
            "protocol": "tls",
            "marker_config": {
                "tshark_path": tshark_path,
                "preserve": {
                    "application_data": False,  # Ensure TLS-23 ApplicationData is masked
                    "handshake": True,
                    "alert": True,
                    "change_cipher_spec": True,
                    "heartbeat": True,
                },
            },
            "masker_config": {"chunk_size": 1000, "verify_checksums": True},
        }

    @classmethod
    def _get_ip_anonymization_config(cls) -> Dict[str, Any]:
        """Get default configuration for IP anonymization processor"""
        return {
            "method": "prefix_preserving",  # Default anonymization method
            "ipv4_prefix": 24,  # IPv4 prefix length
            "ipv6_prefix": 64,  # IPv6 prefix length
            "enabled": True,
            "name": "ip_anonymization",
            "priority": 0,
        }

    @classmethod
    def _get_deduplication_config(cls) -> Dict[str, Any]:
        """Get default configuration for deduplication processor"""
        return {
            "algorithm": "md5",  # Default hash algorithm (consistent with original implementation)
            "enabled": True,
            "name": "deduplication",
            "priority": 0,
        }

    @classmethod
    def is_enhanced_mode_enabled(cls) -> bool:
        """Check if enhanced mode is enabled - based on dual-module architecture"""
        # Dual-module architecture (NewMaskPayloadStage) is always enhanced mode
        return True
