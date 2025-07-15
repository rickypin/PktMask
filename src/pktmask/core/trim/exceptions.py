#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Enhanced Trim Payloads 专用异常类

定义更具体的异常类型，提供更好的错误处理和调试信息。
"""

from typing import Optional, Dict, Any


class EnhancedTrimError(Exception):
    """Enhanced Trim Payloads 基础异常类"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.details = details or {}
    
    def __str__(self) -> str:
        if self.details:
            details_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            return f"{super().__str__()} (Details: {details_str})"
        return super().__str__()


class StageExecutionError(EnhancedTrimError):
    """Stage执行异常
    
    当Stage处理过程中发生错误时抛出。
    """
    
    def __init__(self, stage_name: str, message: str, 
                 original_error: Optional[Exception] = None,
                 stage_data: Optional[Dict[str, Any]] = None):
        details = {"stage_name": stage_name}
        if original_error:
            details["original_error"] = str(original_error)
            details["error_type"] = type(original_error).__name__
        if stage_data:
            details.update(stage_data)
        
        super().__init__(f"Stage '{stage_name}' 执行失败: {message}", details)
        self.stage_name = stage_name
        self.original_error = original_error


class ConfigValidationError(EnhancedTrimError):
    """配置验证异常
    
    当配置参数验证失败时抛出。
    """
    
    def __init__(self, config_key: str, config_value: Any, reason: str):
        details = {
            "config_key": config_key,
            "config_value": config_value,
            "validation_reason": reason
        }
        super().__init__(f"Configuration item '{config_key}' validation failed: {reason}", details)
        self.config_key = config_key
        self.config_value = config_value


class MaskSpecError(EnhancedTrimError):
    """掩码规范异常
    
    当掩码规范创建或应用失败时抛出。
    """
    
    def __init__(self, mask_type: str, message: str, mask_params: Optional[Dict] = None):
        details = {"mask_type": mask_type}
        if mask_params:
            details["mask_params"] = mask_params
        
        super().__init__(f"Mask specification '{mask_type}' error: {message}", details)
        self.mask_type = mask_type


class StreamMaskTableError(EnhancedTrimError):
    """流掩码表异常
    
    当流掩码表操作失败时抛出。
    """
    
    def __init__(self, operation: str, stream_id: str, message: str):
        details = {
            "operation": operation,
            "stream_id": stream_id
        }
        super().__init__(f"Stream mask table operation '{operation}' failed: {message}", details)
        self.operation = operation
        self.stream_id = stream_id


class ToolAvailabilityError(EnhancedTrimError):
    """外部工具可用性异常
    
    当必需的外部工具不可用时抛出。
    """
    
    def __init__(self, tool_name: str, reason: str, suggestions: Optional[list] = None):
        details = {
            "tool_name": tool_name,
            "availability_reason": reason
        }
        if suggestions:
            details["suggestions"] = suggestions
        
        super().__init__(f"External tool '{tool_name}' unavailable: {reason}", details)
        self.tool_name = tool_name
        self.suggestions = suggestions or []


class PipelineExecutionError(EnhancedTrimError):
    """多阶段管道执行异常
    
    当整个处理管道执行失败时抛出。
    """
    
    def __init__(self, message: str, failed_stage: Optional[str] = None,
                 pipeline_stats: Optional[Dict[str, Any]] = None):
        details = {}
        if failed_stage:
            details["failed_stage"] = failed_stage
        if pipeline_stats:
            details["pipeline_stats"] = pipeline_stats
        
        super().__init__(f"管道执行失败: {message}", details)
        self.failed_stage = failed_stage


class ContextError(EnhancedTrimError):
    """执行上下文异常
    
    当Stage执行上下文出现问题时抛出。
    """
    
    def __init__(self, context_issue: str, current_stage: Optional[str] = None):
        details = {"context_issue": context_issue}
        if current_stage:
            details["current_stage"] = current_stage
        
        super().__init__(f"执行上下文错误: {context_issue}", details)
        self.current_stage = current_stage


class ResourceManagementError(EnhancedTrimError):
    """资源管理异常
    
    当临时文件、内存等资源管理失败时抛出。
    """
    
    def __init__(self, resource_type: str, operation: str, message: str):
        details = {
            "resource_type": resource_type,
            "operation": operation
        }
        super().__init__(f"Resource management failed ({resource_type}:{operation}): {message}", details)
        self.resource_type = resource_type
        self.operation = operation 