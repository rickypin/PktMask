"""
配置服务接口
提供统一的配置构建和验证服务
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pktmask.infrastructure.logging import get_logger

logger = get_logger("ConfigService")


class MaskMode(Enum):
    """掩码模式枚举"""

    BASIC = "basic"
    ENHANCED = "enhanced"


@dataclass
class ProcessingOptions:
    """处理选项配置"""

    enable_dedup: bool = False
    enable_anon: bool = False
    enable_mask: bool = False
    mask_mode: MaskMode = MaskMode.ENHANCED
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
        if options.enable_dedup:
            config["remove_dupes"] = {"enabled": True}

        # IP匿名化配置
        if options.enable_anon:
            config["anonymize_ips"] = {"enabled": True}

        # 载荷掩码配置
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
        从CLI参数创建处理选项

        Args:
            enable_dedup: 启用去重
            enable_anon: 启用IP匿名化
            enable_mask: 启用载荷掩码
            mask_mode: 掩码模式
            mask_protocol: 掩码协议
            tshark_path: TShark路径

        Returns:
            处理选项配置
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
        从GUI状态创建处理选项

        Args:
            dedup_checked: 去重复选框状态
            anon_checked: IP匿名化复选框状态
            mask_checked: 载荷掩码复选框状态

        Returns:
            处理选项配置
        """
        return ProcessingOptions(
            enable_dedup=dedup_checked,
            enable_anon=anon_checked,
            enable_mask=mask_checked,
            mask_mode=MaskMode.ENHANCED,  # GUI默认使用增强模式
            mask_protocol="tls",  # GUI默认使用TLS协议
        )

    def get_available_modes(self) -> List[str]:
        """获取可用的掩码模式"""
        return [mode.value for mode in MaskMode]

    def get_available_protocols(self) -> List[str]:
        """获取可用的协议类型"""
        return ["tls", "http"]

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


# 便捷函数
def build_config_from_cli_args(**kwargs) -> Dict[str, Any]:
    """从CLI参数构建配置"""
    service = get_config_service()
    options = service.create_options_from_cli_args(**kwargs)
    return service.build_pipeline_config(options)


def build_config_from_gui(dedup: bool, anon: bool, mask: bool) -> Dict[str, Any]:
    """从GUI状态构建配置"""
    service = get_config_service()
    options = service.create_options_from_gui(dedup, anon, mask)
    return service.build_pipeline_config(options)


def validate_pipeline_config(config: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """验证管道配置"""
    service = get_config_service()
    return service.validate_config(config)
