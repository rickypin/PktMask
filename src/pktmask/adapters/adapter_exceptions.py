"""
适配器异常定义

提供适配器模块统一的异常处理机制。
"""

from typing import Any, Dict, Optional


class AdapterError(Exception):
    """
    适配器基础异常类

    所有适配器异常的基类，提供统一的错误信息格式。

    Attributes:
        message: 错误消息
        error_code: 错误代码
        context: 额外的上下文信息
    """

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.context = context or {}
        super().__init__(self.format_message())

    def format_message(self) -> str:
        """Format error message"""
        base_msg = f"[{self.error_code}] {self.message}"
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{base_msg} (Context: {context_str})"
        return base_msg


class ConfigurationError(AdapterError):
    """配置相关异常"""


class MissingConfigError(ConfigurationError):
    """缺少必要配置"""

    def __init__(self, config_key: str, adapter_name: str):
        super().__init__(
            f"Missing required configuration: {config_key}",
            context={"adapter": adapter_name, "missing_key": config_key},
        )


class InvalidConfigError(ConfigurationError):
    """配置格式错误"""

    def __init__(self, config_key: str, expected_type: str, actual_value):
        super().__init__(
            f"Invalid configuration value for {config_key}",
            context={
                "key": config_key,
                "expected_type": expected_type,
                "actual_value": str(actual_value),
            },
        )


class DataFormatError(AdapterError):
    """数据格式异常"""


class InputFormatError(DataFormatError):
    """输入格式错误"""

    def __init__(self, expected: str, actual: str):
        super().__init__(
            f"Invalid input format: expected {expected}, got {actual}",
            context={"expected": expected, "actual": actual},
        )


class OutputFormatError(DataFormatError):
    """输出格式错误"""

    def __init__(self, expected: str, actual: str):
        super().__init__(
            f"Invalid output format: expected {expected}, got {actual}",
            context={"expected": expected, "actual": actual},
        )


class ProcessingError(AdapterError):
    """处理过程异常"""
