#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PktMask 异常定义
统一管理应用程序中的所有异常类型
"""

from typing import Optional, Dict, Any
from .enums import ErrorSeverity


class PktMaskError(Exception):
    """PktMask应用程序基础异常类"""
    
    def __init__(
        self, 
        message: str, 
        error_code: Optional[str] = None,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.severity = severity
        self.context = context or {}
    
    def __str__(self) -> str:
        if self.error_code:
            return f"[{self.error_code}] {self.message}"
        return self.message
    
    def to_dict(self) -> Dict[str, Any]:
        """将异常信息转换为字典格式"""
        return {
            'type': self.__class__.__name__,
            'message': self.message,
            'error_code': self.error_code,
            'severity': self.severity.name,
            'context': self.context
        }


class ConfigurationError(PktMaskError):
    """配置相关错误"""
    
    def __init__(self, message: str, config_key: Optional[str] = None, **kwargs):
        super().__init__(message, error_code="CONFIG_ERROR", **kwargs)
        self.config_key = config_key


# 配置错误的别名，保持向后兼容
ConfigError = ConfigurationError


class ProcessingError(PktMaskError):
    """处理过程相关错误"""
    
    def __init__(
        self, 
        message: str, 
        file_path: Optional[str] = None, 
        step_name: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, error_code="PROCESSING_ERROR", **kwargs)
        self.file_path = file_path
        self.step_name = step_name


class ValidationError(PktMaskError):
    """验证相关错误"""
    
    def __init__(
        self, 
        message: str, 
        field_name: Optional[str] = None, 
        field_value: Optional[Any] = None,
        **kwargs
    ):
        super().__init__(message, error_code="VALIDATION_ERROR", **kwargs)
        self.field_name = field_name
        self.field_value = field_value


class FileError(PktMaskError):
    """文件操作相关错误"""
    
    def __init__(
        self, 
        message: str, 
        file_path: Optional[str] = None, 
        operation: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, error_code="FILE_ERROR", **kwargs)
        self.file_path = file_path
        self.operation = operation


class NetworkError(PktMaskError):
    """网络处理相关错误"""
    
    def __init__(
        self, 
        message: str, 
        packet_info: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        super().__init__(message, error_code="NETWORK_ERROR", **kwargs)
        self.packet_info = packet_info or {}


class UIError(PktMaskError):
    """用户界面相关错误"""
    
    def __init__(
        self, 
        message: str, 
        component_name: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, error_code="UI_ERROR", **kwargs)
        self.component_name = component_name


class PluginError(PktMaskError):
    """插件系统相关错误"""
    
    def __init__(
        self, 
        message: str, 
        plugin_name: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, error_code="PLUGIN_ERROR", **kwargs)
        self.plugin_name = plugin_name


class DependencyError(PktMaskError):
    """依赖相关错误"""
    
    def __init__(
        self, 
        message: str, 
        dependency_name: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, error_code="DEPENDENCY_ERROR", **kwargs)
        self.dependency_name = dependency_name


class ResourceError(PktMaskError):
    """资源相关错误（内存、磁盘空间等）"""
    
    def __init__(
        self, 
        message: str, 
        resource_type: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, error_code="RESOURCE_ERROR", **kwargs)
        self.resource_type = resource_type


# 便利函数
def create_error_from_exception(exc: Exception, context: Optional[Dict[str, Any]] = None) -> PktMaskError:
    """从标准异常创建PktMask异常"""
    if isinstance(exc, PktMaskError):
        return exc
    
    error_message = str(exc)
    error_type = type(exc).__name__
    
    # 根据异常类型选择适当的PktMask异常类
    if isinstance(exc, (IOError, OSError)):
        return FileError(error_message, context=context)
    elif isinstance(exc, ValueError):
        return ValidationError(error_message, context=context)
    elif isinstance(exc, ImportError):
        return DependencyError(error_message, context=context)
    elif isinstance(exc, MemoryError):
        return ResourceError(error_message, resource_type="memory", context=context)
    else:
        return PktMaskError(
            f"{error_type}: {error_message}",
            error_code="UNKNOWN_ERROR",
            context=context
        )


def format_error_for_user(error: PktMaskError) -> str:
    """格式化错误信息以便向用户显示"""
    base_message = error.message
    
    # 根据错误类型添加额外信息
    if isinstance(error, FileError) and error.file_path:
        return f"{base_message}\n文件: {error.file_path}"
    elif isinstance(error, ProcessingError) and error.step_name:
        return f"{base_message}\n处理步骤: {error.step_name}"
    elif isinstance(error, ConfigurationError) and error.config_key:
        return f"{base_message}\n配置项: {error.config_key}"
    
    return base_message 