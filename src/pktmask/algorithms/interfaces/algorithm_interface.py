#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
核心算法接口定义
所有算法插件必须实现的基础接口
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Set, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from packaging import version as pkg_version
from pydantic import BaseModel, Field, validator

from ...infrastructure.logging import get_logger
from ...common.exceptions import ProcessingError, ValidationError


class AlgorithmType(Enum):
    """算法类型枚举"""
    IP_ANONYMIZATION = "ip_anonymization"
    PACKET_PROCESSING = "packet_processing"
    DEDUPLICATION = "deduplication"
    CUSTOM = "custom"


class AlgorithmStatus(Enum):
    """算法状态枚举"""
    IDLE = "idle"
    CONFIGURED = "configured"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"
    STOPPED = "stopped"
    LOADING = "loading"
    UNLOADING = "unloading"


class DependencyType(Enum):
    """依赖类型枚举"""
    REQUIRED = "required"
    OPTIONAL = "optional"
    DEVELOPMENT = "development"


@dataclass
class AlgorithmDependency:
    """算法依赖信息"""
    name: str
    version_spec: str  # 版本规范，如 ">=1.0.0,<2.0.0"
    dependency_type: DependencyType = DependencyType.REQUIRED
    description: Optional[str] = None
    
    def is_version_compatible(self, installed_version: str) -> bool:
        """检查版本兼容性"""
        try:
            from packaging import specifiers
            spec_set = specifiers.SpecifierSet(self.version_spec)
            return pkg_version.parse(installed_version) in spec_set
        except Exception:
            return False


@dataclass
class AlgorithmMetadata:
    """算法元数据"""
    tags: Set[str] = field(default_factory=set)
    category: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    homepage: Optional[str] = None
    documentation: Optional[str] = None
    license: Optional[str] = None
    changelog: Optional[str] = None
    config_schema: Optional[Dict[str, Any]] = None


@dataclass
class AlgorithmInfo:
    """算法信息"""
    name: str
    version: str
    algorithm_type: AlgorithmType
    author: str
    description: str
    supported_formats: List[str]
    requirements: Dict[str, str]
    dependencies: List[AlgorithmDependency] = field(default_factory=list)
    metadata: AlgorithmMetadata = field(default_factory=AlgorithmMetadata)
    performance_baseline: Optional[Dict[str, float]] = None
    created_at: Optional[datetime] = None
    min_python_version: str = "3.8"
    max_python_version: Optional[str] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
    
    def is_compatible_with_python(self, python_version: str) -> bool:
        """检查Python版本兼容性"""
        try:
            current_version = pkg_version.parse(python_version)
            min_version = pkg_version.parse(self.min_python_version)
            
            if current_version < min_version:
                return False
                
            if self.max_python_version:
                max_version = pkg_version.parse(self.max_python_version)
                if current_version > max_version:
                    return False
                    
            return True
        except Exception:
            return False
    
    def get_required_dependencies(self) -> List[AlgorithmDependency]:
        """获取必需的依赖"""
        return [dep for dep in self.dependencies if dep.dependency_type == DependencyType.REQUIRED]
    
    def get_optional_dependencies(self) -> List[AlgorithmDependency]:
        """获取可选的依赖"""
        return [dep for dep in self.dependencies if dep.dependency_type == DependencyType.OPTIONAL]


class AlgorithmConfig(BaseModel):
    """算法配置基类"""
    enabled: bool = Field(default=True, description="是否启用算法")
    priority: int = Field(default=0, ge=-10, le=10, description="算法优先级")
    timeout_seconds: int = Field(default=300, ge=60, description="算法超时时间")
    max_memory_mb: int = Field(default=512, ge=64, le=4096, description="最大内存使用(MB)")
    enable_caching: bool = Field(default=True, description="是否启用缓存")
    debug_mode: bool = Field(default=False, description="调试模式")
    hot_reload: bool = Field(default=False, description="是否支持热重载")
    performance_monitoring: bool = Field(default=True, description="是否启用性能监控")
    
    class Config:
        extra = "allow"  # 允许子类添加额外字段


class PluginConfig(BaseModel):
    """插件级配置"""
    auto_register: bool = Field(default=True, description="是否自动注册")
    load_on_startup: bool = Field(default=True, description="启动时是否加载")
    config_file: Optional[str] = Field(default=None, description="独立配置文件路径")
    enable_monitoring: bool = Field(default=True, description="是否启用监控")
    health_check_interval: int = Field(default=60, ge=10, description="健康检查间隔(秒)")
    max_restart_attempts: int = Field(default=3, ge=0, description="最大重启尝试次数")
    hot_reload: bool = Field(default=False, description="是否支持热重载")
    
    @validator('config_file')
    def validate_config_file(cls, v):
        if v and not v.endswith(('.json', '.yaml', '.yml', '.toml')):
            raise ValueError("配置文件必须是 .json, .yaml, .yml 或 .toml 格式")
        return v


class ValidationResult(BaseModel):
    """验证结果"""
    is_valid: bool = Field(description="验证是否通过")
    errors: List[str] = Field(default_factory=list, description="错误信息列表")
    warnings: List[str] = Field(default_factory=list, description="警告信息列表")
    suggestions: List[str] = Field(default_factory=list, description="建议信息列表")
    
    def add_error(self, message: str):
        """添加错误信息"""
        self.errors.append(message)
        self.is_valid = False
        
    def add_warning(self, message: str):
        """添加警告信息"""
        self.warnings.append(message)
        
    def add_suggestion(self, message: str):
        """添加建议信息"""
        self.suggestions.append(message)


class ProcessingResult(BaseModel):
    """处理结果"""
    success: bool = Field(description="处理是否成功")
    data: Any = Field(description="处理结果数据")
    metrics: Optional[Dict[str, Any]] = Field(default=None, description="性能指标")
    errors: List[str] = Field(default_factory=list, description="错误信息")
    warnings: List[str] = Field(default_factory=list, description="警告信息")
    processing_time_ms: float = Field(default=0.0, description="处理时间(毫秒)")
    
    class Config:
        arbitrary_types_allowed = True


class AlgorithmInterface(ABC):
    """算法插件统一接口"""
    
    def __init__(self):
        self._logger = get_logger(f'algorithm.{self.__class__.__name__}')
        self._status = AlgorithmStatus.IDLE
        self._config: Optional[AlgorithmConfig] = None
        self._initialized = False
        
    # === 基础信息方法 ===
    
    @abstractmethod
    def get_algorithm_info(self) -> AlgorithmInfo:
        """
        获取算法基本信息
        
        Returns:
            AlgorithmInfo: 算法信息对象
        """
        pass
    
    @abstractmethod
    def get_default_config(self) -> AlgorithmConfig:
        """
        获取默认配置
        
        Returns:
            AlgorithmConfig: 默认配置对象
        """
        pass
    
    # === 配置管理方法 ===
    
    @abstractmethod
    def validate_config(self, config: AlgorithmConfig) -> ValidationResult:
        """
        验证配置参数
        
        Args:
            config: 待验证的配置
            
        Returns:
            ValidationResult: 验证结果
        """
        pass
    
    def configure(self, config: AlgorithmConfig) -> bool:
        """
        配置算法参数
        
        Args:
            config: 算法配置
            
        Returns:
            bool: 配置是否成功
        """
        try:
            # 验证配置
            validation_result = self.validate_config(config)
            if not validation_result.is_valid:
                self._logger.error(f"配置验证失败: {validation_result.errors}")
                return False
            
            # 记录警告
            for warning in validation_result.warnings:
                self._logger.warning(f"配置警告: {warning}")
            
            # 应用配置
            self._config = config
            success = self._apply_config(config)
            
            if success:
                self._logger.info(f"算法 {self.get_algorithm_info().name} 配置成功")
            else:
                self._logger.error(f"算法 {self.get_algorithm_info().name} 配置失败")
                
            return success
            
        except Exception as e:
            self._logger.error(f"配置算法时发生错误: {e}")
            return False
    
    @abstractmethod
    def _apply_config(self, config: AlgorithmConfig) -> bool:
        """
        应用配置（由子类实现具体逻辑）
        
        Args:
            config: 已验证的配置
            
        Returns:
            bool: 应用是否成功
        """
        pass
    
    # === 生命周期管理方法 ===
    
    def initialize(self) -> bool:
        """
        初始化算法
        
        Returns:
            bool: 初始化是否成功
        """
        try:
            if self._initialized:
                self._logger.warning("算法已经初始化")
                return True
                
            success = self._do_initialize()
            if success:
                self._initialized = True
                self._status = AlgorithmStatus.IDLE
                self._logger.info(f"算法 {self.get_algorithm_info().name} 初始化成功")
            else:
                self._logger.error(f"算法 {self.get_algorithm_info().name} 初始化失败")
                
            return success
            
        except Exception as e:
            self._logger.error(f"初始化算法时发生错误: {e}")
            return False
    
    @abstractmethod
    def _do_initialize(self) -> bool:
        """
        执行具体的初始化逻辑（由子类实现）
        
        Returns:
            bool: 初始化是否成功
        """
        pass
    
    def cleanup(self):
        """清理资源"""
        try:
            self._do_cleanup()
            self._status = AlgorithmStatus.STOPPED
            self._initialized = False
            self._logger.info(f"算法 {self.get_algorithm_info().name} 清理完成")
        except Exception as e:
            self._logger.error(f"清理算法资源时发生错误: {e}")
    
    @abstractmethod
    def _do_cleanup(self):
        """
        执行具体的清理逻辑（由子类实现）
        """
        pass
    
    # === 状态管理方法 ===
    
    def get_status(self) -> AlgorithmStatus:
        """获取算法状态"""
        return self._status
    
    def is_ready(self) -> bool:
        """检查算法是否就绪"""
        return self._initialized and self._status == AlgorithmStatus.IDLE
    
    def get_config(self) -> Optional[AlgorithmConfig]:
        """获取当前配置"""
        return self._config
    
    # === 性能监控方法 ===
    
    @abstractmethod
    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        获取性能指标
        
        Returns:
            Dict[str, Any]: 性能指标字典
        """
        pass
    
    def reset_performance_metrics(self):
        """重置性能指标"""
        try:
            self._do_reset_metrics()
            self._logger.debug("性能指标已重置")
        except Exception as e:
            self._logger.error(f"重置性能指标时发生错误: {e}")
    
    @abstractmethod
    def _do_reset_metrics(self):
        """
        执行具体的指标重置逻辑（由子类实现）
        """
        pass
    
    # === 通用辅助方法 ===
    
    def _check_ready(self):
        """检查算法是否就绪，不就绪则抛出异常"""
        if not self.is_ready():
            raise ProcessingError(f"算法 {self.get_algorithm_info().name} 未就绪，当前状态: {self._status}")
    
    def _set_status(self, status: AlgorithmStatus):
        """设置算法状态"""
        old_status = self._status
        self._status = status
        self._logger.debug(f"算法状态变更: {old_status} -> {status}")
    
    def __str__(self) -> str:
        """字符串表示"""
        info = self.get_algorithm_info()
        return f"{info.name} v{info.version} ({info.algorithm_type.value})"
    
    def __repr__(self) -> str:
        """详细字符串表示"""
        return f"<{self.__class__.__name__}: {self}>" 