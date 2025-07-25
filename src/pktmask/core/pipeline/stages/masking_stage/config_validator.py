"""
配置验证器 - 简化版本

提供基础的配置验证功能，确保配置参数的有效性和一致性。
这是架构文档中 ConfigValidator 的简化实现版本。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class ValidationResult:
    """配置验证结果"""

    is_valid: bool
    errors: List[str]
    warnings: List[str]
    normalized_config: Dict[str, Any]


class ConfigValidator:
    """配置验证器 - 简化版本

    提供基础的配置参数验证功能。
    """

    def __init__(self):
        self.logger = logging.getLogger(
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )
        self.validation_rules = {
            "protocol": self._validate_protocol,
            "marker_config": self._validate_marker_config,
            "masker_config": self._validate_masker_config,
            "mode": self._validate_mode,
        }

    def validate_config(self, config: Dict) -> ValidationResult:
        """验证配置参数的有效性"""
        errors = []
        warnings = []

        # 基础结构验证
        if not isinstance(config, dict):
            return ValidationResult(
                is_valid=False,
                errors=["配置必须是字典类型"],
                warnings=[],
                normalized_config={},
            )

        # 逐项验证
        for key, value in config.items():
            if key in self.validation_rules:
                try:
                    result = self.validation_rules[key](value, config)
                    errors.extend(result.get("errors", []))
                    warnings.extend(result.get("warnings", []))
                except Exception as e:
                    errors.append(f"验证{key}时发生错误: {e}")
            else:
                # 对于未知配置项，只记录调试信息，不产生警告
                self.logger.debug(f"未知配置项: {key}")

        # 交叉验证
        cross_validation_result = self._cross_validate(config)
        errors.extend(cross_validation_result.get("errors", []))
        warnings.extend(cross_validation_result.get("warnings", []))

        # 生成标准化配置
        normalized_config = self._normalize_config(config) if not errors else {}

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            normalized_config=normalized_config,
        )

    def _validate_protocol(self, protocol: str, full_config: Dict) -> Dict:
        """验证协议配置"""
        errors = []
        warnings = []

        valid_protocols = ["tls", "http", "auto"]
        if protocol not in valid_protocols:
            errors.append(f"不支持的协议: {protocol}，支持的协议: {valid_protocols}")

        return {"errors": errors, "warnings": warnings}

    def _validate_marker_config(self, marker_config: Dict, full_config: Dict) -> Dict:
        """验证Marker模块配置"""
        errors = []
        warnings = []

        if not isinstance(marker_config, dict):
            errors.append("marker_config必须是字典类型")
            return {"errors": errors, "warnings": warnings}

        protocol = full_config.get("protocol", "tls")
        if protocol in marker_config:
            protocol_config = marker_config[protocol]
            if protocol == "tls":
                # 验证TLS特定配置
                tls_keys = [
                    "preserve_handshake",
                    "preserve_application_data",
                    "preserve_alert",
                ]
                for key in tls_keys:
                    if key in protocol_config and not isinstance(
                        protocol_config[key], bool
                    ):
                        errors.append(f"TLS配置项{key}必须是布尔值")

        return {"errors": errors, "warnings": warnings}

    def _validate_masker_config(self, masker_config: Dict, full_config: Dict) -> Dict:
        """验证Masker模块配置"""
        errors = []
        warnings = []

        if not isinstance(masker_config, dict):
            errors.append("masker_config必须是字典类型")
            return {"errors": errors, "warnings": warnings}

        # 验证chunk_size
        chunk_size = masker_config.get("chunk_size", 1000)
        if not isinstance(chunk_size, int) or chunk_size <= 0:
            errors.append("chunk_size必须是正整数")
        elif chunk_size > 10000:
            warnings.append("chunk_size过大可能影响性能")

        # 验证verify_checksums
        verify_checksums = masker_config.get("verify_checksums", True)
        if not isinstance(verify_checksums, bool):
            errors.append("verify_checksums必须是布尔值")

        return {"errors": errors, "warnings": warnings}

    def _validate_mode(self, mode: str, full_config: Dict) -> Dict:
        """验证处理模式 - 现在只支持enhanced模式"""
        errors = []
        warnings = []

        # 只支持enhanced模式，但保持向后兼容
        if mode not in ["enhanced"]:
            warnings.append(f"模式 '{mode}' 已废弃，自动使用 'enhanced' 模式")

        return {"errors": errors, "warnings": warnings}

    def _cross_validate(self, config: Dict) -> Dict:
        """交叉验证配置项之间的一致性"""
        errors = []
        warnings = []

        # 检查协议与marker配置的一致性
        protocol = config.get("protocol", "tls")
        marker_config = config.get("marker_config", {})
        if protocol not in marker_config and protocol != "auto":
            warnings.append(f"协议{protocol}缺少对应的marker配置")

        return {"errors": errors, "warnings": warnings}

    def _normalize_config(self, config: Dict) -> Dict:
        """标准化配置，填充默认值"""
        normalized = config.copy()

        # 设置默认值
        normalized.setdefault("protocol", "tls")
        normalized.setdefault("mode", "enhanced")
        normalized.setdefault("marker_config", {})
        normalized.setdefault(
            "masker_config", {"chunk_size": 1000, "verify_checksums": True}
        )

        return normalized
