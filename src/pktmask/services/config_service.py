"""
Configuration service interface
Provides unified configuration building and validation services
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pktmask.infrastructure.logging import get_logger

logger = get_logger("ConfigService")


class MaskMode(Enum):
    """Mask mode enumeration"""

    BASIC = "basic"
    ENHANCED = "enhanced"


@dataclass
class ProcessingOptions:
    """Processing options configuration"""

    enable_dedup: bool = False
    enable_anon: bool = False
    enable_mask: bool = False
    mask_mode: MaskMode = MaskMode.ENHANCED
    mask_protocol: str = "tls"

    # TShark configuration
    tshark_path: Optional[str] = None

    # Advanced options
    preserve_handshake: bool = True
    preserve_alert: bool = True
    preserve_change_cipher_spec: bool = True
    preserve_heartbeat: bool = True
    preserve_application_data: bool = False


class ConfigService:
    """Unified configuration service"""

    def __init__(self):
        self._app_config = None
        self._load_app_config()

    def _load_app_config(self):
        """Load application configuration"""
        try:
            from pktmask.config.settings import get_app_config

            self._app_config = get_app_config()
        except Exception as e:
            logger.warning(f"Failed to load app config: {e}")
            self._app_config = None

    def build_pipeline_config(self, options: ProcessingOptions) -> Dict[str, Any]:
        """
        Build pipeline configuration (unified interface)

        Args:
            options: Processing options configuration

        Returns:
            Pipeline configuration dictionary
        """
        config: Dict[str, Any] = {}

        # Deduplication configuration
        if options.enable_dedup:
            config["remove_dupes"] = {"enabled": True}

        # IP anonymization configuration
        if options.enable_anon:
            config["anonymize_ips"] = {"enabled": True}

        # Payload masking configuration
        if options.enable_mask:
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
            "mode": options.mask_mode.value,
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
        Validate configuration validity

        Args:
            config: Configuration dictionary

        Returns:
            (is_valid, error_message)
        """
        if not config:
            return False, "Configuration is empty"

        # Check if at least one processing stage is enabled
        enabled_stages = []
        for stage_name, stage_config in config.items():
            if isinstance(stage_config, dict) and stage_config.get("enabled", False):
                enabled_stages.append(stage_name)

        if not enabled_stages:
            return False, "No processing stages enabled"

        # Validate mask configuration
        if "mask_payloads" in config:
            mask_config = config["mask_payloads"]
            if mask_config.get("enabled", False):
                mode = mask_config.get("mode", "enhanced")
                if mode not in ["basic", "enhanced"]:
                    return False, f"Invalid mask mode: {mode}"

                protocol = mask_config.get("protocol", "tls")
                if protocol not in ["tls", "http"]:
                    return False, f"Invalid protocol: {protocol}"

        logger.debug(f"Config validation passed for stages: {enabled_stages}")
        return True, None

    def create_options_from_cli_args(
        self,
        enable_dedup: bool = False,
        enable_anon: bool = False,
        enable_mask: bool = False,
        mask_mode: str = "enhanced",
        mask_protocol: str = "tls",
        tshark_path: Optional[str] = None,
    ) -> ProcessingOptions:
        """
        Create processing options from CLI arguments

        Args:
            enable_dedup: Enable deduplication
            enable_anon: Enable IP anonymization
            enable_mask: Enable payload masking
            mask_mode: Mask mode
            mask_protocol: Mask protocol
            tshark_path: TShark path

        Returns:
            Processing options configuration
        """
        try:
            mode_enum = MaskMode(mask_mode.lower())
        except ValueError:
            logger.warning(f"Invalid mask mode '{mask_mode}', using 'enhanced'")
            mode_enum = MaskMode.ENHANCED

        return ProcessingOptions(
            enable_dedup=enable_dedup,
            enable_anon=enable_anon,
            enable_mask=enable_mask,
            mask_mode=mode_enum,
            mask_protocol=mask_protocol,
            tshark_path=tshark_path,
        )

    def create_options_from_gui(
        self, dedup_checked: bool, anon_checked: bool, mask_checked: bool
    ) -> ProcessingOptions:
        """
        Create processing options from GUI state

        Args:
            dedup_checked: Deduplication checkbox state
            anon_checked: IP anonymization checkbox state
            mask_checked: Payload masking checkbox state

        Returns:
            Processing options configuration
        """
        return ProcessingOptions(
            enable_dedup=dedup_checked,
            enable_anon=anon_checked,
            enable_mask=mask_checked,
            mask_mode=MaskMode.ENHANCED,  # GUI defaults to enhanced mode
            mask_protocol="tls",  # GUI defaults to TLS protocol
        )

    def get_available_modes(self) -> List[str]:
        """Get available mask modes"""
        return [mode.value for mode in MaskMode]

    def get_available_protocols(self) -> List[str]:
        """Get available protocol types"""
        return ["tls", "http"]

    def get_default_tshark_path(self) -> Optional[str]:
        """Get default TShark path"""
        if self._app_config:
            return self._app_config.tools.tshark.custom_executable
        return None


# Global configuration service instance
_config_service = None


def get_config_service() -> ConfigService:
    """Get configuration service instance (singleton pattern)"""
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


def build_config_from_gui(dedup: bool, anon: bool, mask: bool) -> Dict[str, Any]:
    """Build configuration from GUI state"""
    service = get_config_service()
    options = service.create_options_from_gui(dedup, anon, mask)
    return service.build_pipeline_config(options)


def validate_pipeline_config(config: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Validate pipeline configuration"""
    service = get_config_service()
    return service.validate_config(config)
