"""
配置服务接口
提供统一的配置构建和验证服务
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from pktmask.infrastructure.logging import get_logger

logger = get_logger("ConfigService")


@dataclass
class ProcessingOptions:
    """处理选项配置"""

    enable_remove_dupes: bool = False
    enable_anonymize_ips: bool = False
    enable_mask_payloads: bool = False
    mask_protocol: str = "tls"

    # TShark配置
    tshark_path: Optional[str] = None

    # 高级选项
    preserve_handshake: bool = True
    preserve_alert: bool = True
    preserve_change_cipher_spec: bool = True
    preserve_heartbeat: bool = True
    preserve_application_data: bool = False


class ConfigService:
    """统一配置服务"""

    def __init__(self):
        self._app_config = None
        self._load_app_config()

    def _load_app_config(self):
        """加载应用配置"""
        try:
            from pktmask.config.settings import get_app_config

            self._app_config = get_app_config()
        except Exception as e:
            logger.warning(f"Failed to load app config: {e}")
            self._app_config = None

    def build_pipeline_config(self, options: ProcessingOptions) -> Dict[str, Any]:
        """
        构建管道配置（统一接口）

        Args:
            options: 处理选项配置

        Returns:
            管道配置字典
        """
        config: Dict[str, Any] = {}

        # 去重配置
        if options.enable_remove_dupes:
            config["remove_dupes"] = {"enabled": True}

        # IP匿名化配置
        if options.enable_anonymize_ips:
            config["anonymize_ips"] = {"enabled": True}

        # 载荷掩码配置
        if options.enable_mask_payloads:
            config["mask_payloads"] = self._build_mask_config(options)

        logger.debug(f"Built pipeline config with {len(config)} stages")
        return config

    def _build_mask_config(self, options: ProcessingOptions) -> Dict[str, Any]:
        """Build mask configuration"""
        # Get TShark path
        tshark_path = options.tshark_path
        if not tshark_path and self._app_config:
            tshark_path = self._app_config.tools.tshark.custom_executable

        mask_config = {
            "enabled": True,
            "protocol": options.mask_protocol,
            "mode": "enhanced",  # Always use enhanced mode
            "marker_config": {
                "preserve": {
                    "application_data": options.preserve_application_data,
                    "handshake": options.preserve_handshake,
                    "alert": options.preserve_alert,
                    "change_cipher_spec": options.preserve_change_cipher_spec,
                    "heartbeat": options.preserve_heartbeat,
                }
            },
            "masker_config": {"chunk_size": 1000, "verify_checksums": True},
        }

        # Add TShark path (if available)
        if tshark_path:
            mask_config["marker_config"]["tshark_path"] = tshark_path

        return mask_config

    def validate_config(self, config: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        验证配置有效性

        Args:
            config: 配置字典

        Returns:
            (是否有效, 错误信息)
        """
        if not config:
            return False, "Configuration is empty"

        # 检查是否至少启用了一个处理阶段
        enabled_stages = []
        for stage_name, stage_config in config.items():
            if isinstance(stage_config, dict) and stage_config.get("enabled", False):
                enabled_stages.append(stage_name)

        if not enabled_stages:
            return False, "No processing stages enabled"

        # 验证掩码配置
        if "mask_payloads" in config:
            mask_config = config["mask_payloads"]
            if mask_config.get("enabled", False):
                protocol = mask_config.get("protocol", "tls")
                if protocol not in ["tls", "http"]:
                    return False, f"Invalid protocol: {protocol}"

        logger.debug(f"Config validation passed for stages: {enabled_stages}")
        return True, None

    def create_options_from_cli_args(
        self,
        remove_dupes: bool = False,
        anonymize_ips: bool = False,
        mask_payloads: bool = False,
        mask_protocol: str = "tls",
        tshark_path: Optional[str] = None,
    ) -> ProcessingOptions:
        """
        Create processing options from CLI arguments

        Args:
            remove_dupes: Enable deduplication processing
            anonymize_ips: Enable IP anonymization processing
            mask_payloads: Enable payload masking processing
            mask_protocol: Masking protocol
            tshark_path: TShark executable path

        Returns:
            Processing options configuration
        """
        return ProcessingOptions(
            enable_remove_dupes=remove_dupes,
            enable_anonymize_ips=anonymize_ips,
            enable_mask_payloads=mask_payloads,
            mask_protocol=mask_protocol,
            tshark_path=tshark_path,
        )

    def create_options_from_gui(
        self,
        remove_dupes_checked: bool,
        anonymize_ips_checked: bool,
        mask_payloads_checked: bool,
    ) -> ProcessingOptions:
        """
        Create processing options from GUI state

        Args:
            remove_dupes_checked: Remove dupes checkbox state
            anonymize_ips_checked: Anonymize IPs checkbox state
            mask_payloads_checked: Mask payloads checkbox state

        Returns:
            Processing options configuration
        """
        return ProcessingOptions(
            enable_remove_dupes=remove_dupes_checked,
            enable_anonymize_ips=anonymize_ips_checked,
            enable_mask_payloads=mask_payloads_checked,
            mask_protocol="tls",  # GUI defaults to TLS protocol
        )

    def create_options_from_unified_args(
        self,
        dedup: bool = False,
        anon: bool = False,
        mask: bool = False,
        protocol: str = "tls",
        tshark_path: Optional[str] = None,
    ) -> ProcessingOptions:
        """
        Create processing options from unified CLI arguments

        This method provides a direct mapping from the new unified CLI parameter names
        to the internal ProcessingOptions structure.

        Args:
            dedup: Enable deduplication processing
            anon: Enable IP anonymization processing
            mask: Enable payload masking processing
            protocol: Masking protocol
            tshark_path: TShark executable path

        Returns:
            Processing options configuration
        """
        return ProcessingOptions(
            enable_remove_dupes=dedup,
            enable_anonymize_ips=anon,
            enable_mask_payloads=mask,
            mask_protocol=protocol,
            tshark_path=tshark_path,
        )

    def get_available_modes(self) -> List[str]:
        """Get available masking modes - only enhanced mode is supported"""
        return ["enhanced"]

    def get_available_protocols(self) -> List[str]:
        """Get available protocol types"""
        return ["tls"]  # Only TLS is currently implemented

    def get_default_tshark_path(self) -> Optional[str]:
        """获取默认TShark路径"""
        if self._app_config:
            return self._app_config.tools.tshark.custom_executable
        return None


# 全局配置服务实例
_config_service = None


def get_config_service() -> ConfigService:
    """获取配置服务实例（单例模式）"""
    global _config_service
    if _config_service is None:
        _config_service = ConfigService()
    return _config_service


# Convenience functions
def build_config_from_cli_args(**kwargs) -> Dict[str, Any]:
    """Build configuration from CLI arguments"""
    service = get_config_service()
    options = service.create_options_from_cli_args(**kwargs)
    return service.build_pipeline_config(options)


def build_config_from_gui(
    remove_dupes: bool, anonymize_ips: bool, mask_payloads: bool
) -> Dict[str, Any]:
    """Build configuration from GUI state"""
    service = get_config_service()
    options = service.create_options_from_gui(
        remove_dupes, anonymize_ips, mask_payloads
    )
    return service.build_pipeline_config(options)


def build_config_from_unified_args(**kwargs) -> Dict[str, Any]:
    """Build configuration from unified CLI arguments"""
    service = get_config_service()
    options = service.create_options_from_unified_args(**kwargs)
    return service.build_pipeline_config(options)


def validate_pipeline_config(config: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Validate pipeline configuration"""
    service = get_config_service()
    return service.validate_config(config)
