#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
应用配置模型
为测试兼容性提供AppConfig类
"""

from typing import Optional, List, Dict, Any, Union
from pathlib import Path
from pydantic import BaseModel, Field, field_validator
import logging

from .models import PktMaskConfig, UIConfig, ProcessingConfig, PerformanceConfig, FileConfig, LoggingConfig


class AppConfig(BaseModel):
    """应用配置类 - 为测试兼容性提供的简化接口"""
    
    # 基本配置
    debug: bool = Field(default=False, description="调试模式")
    log_level: str = Field(default="INFO", description="日志级别")
    ui_theme: str = Field(default="auto", description="UI主题")
    language: str = Field(default="zh_CN", description="界面语言")
    processing_threads: int = Field(default=4, ge=1, le=16, description="处理线程数")
    
    # 高级配置
    config_version: str = Field(default="1.0", description="配置版本")
    enable_caching: bool = Field(default=True, description="启用缓存")
    timeout_seconds: int = Field(default=300, description="超时时间")
    
    # 可选的完整配置引用
    full_config: Optional[PktMaskConfig] = Field(default=None, exclude=True)
    
    @field_validator('log_level')
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """验证日志级别"""
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}")
        return v.upper()
    
    @field_validator('ui_theme')
    @classmethod
    def validate_theme(cls, v: str) -> str:
        """验证UI主题"""
        valid_themes = ['auto', 'light', 'dark']
        if v not in valid_themes:
            raise ValueError(f"Theme must be one of {valid_themes}")
        return v
    
    @field_validator('language')
    @classmethod
    def validate_language(cls, v: str) -> str:
        """验证语言设置"""
        valid_languages = ['zh_CN', 'en_US']
        if v not in valid_languages:
            raise ValueError(f"Language must be one of {valid_languages}")
        return v
    
    model_config = {
        "extra": "allow",
        "validate_assignment": True,
        "use_enum_values": True
    }
    
    @classmethod
    def from_full_config(cls, full_config: PktMaskConfig) -> 'AppConfig':
        """从完整配置创建AppConfig实例"""
        return cls(
            debug=full_config.logging.file_level == "DEBUG",
            log_level=full_config.logging.console_level,
            ui_theme=full_config.ui.theme,
            language=full_config.ui.language,
            processing_threads=full_config.performance.max_workers,
            config_version=full_config.config_version,
            enable_caching=full_config.performance.enable_caching,
            timeout_seconds=full_config.processing.timeout_seconds,
            full_config=full_config
        )
    
    def to_full_config(self) -> PktMaskConfig:
        """转换为完整配置"""
        if self.full_config:
            # 更新现有配置
            self.full_config.logging.console_level = self.log_level
            self.full_config.logging.file_level = "DEBUG" if self.debug else "INFO"
            self.full_config.ui.theme = self.ui_theme
            self.full_config.ui.language = self.language
            self.full_config.performance.max_workers = self.processing_threads
            self.full_config.config_version = self.config_version
            self.full_config.performance.enable_caching = self.enable_caching
            self.full_config.processing.timeout_seconds = self.timeout_seconds
            return self.full_config
        else:
            # 创建新的完整配置
            return PktMaskConfig(
                config_version=self.config_version,
                ui=UIConfig(
                    theme=self.ui_theme,
                    language=self.language
                ),
                processing=ProcessingConfig(
                    timeout_seconds=self.timeout_seconds
                ),
                performance=PerformanceConfig(
                    max_workers=self.processing_threads,
                    enable_caching=self.enable_caching
                ),
                file=FileConfig(),
                logging=LoggingConfig(
                    console_level=self.log_level,
                    file_level="DEBUG" if self.debug else "INFO"
                )
            )
    
    def dict_for_serialization(self) -> Dict[str, Any]:
        """返回用于序列化的字典"""
        return self.model_dump(exclude={'full_config'})
    
    def update_from_dict(self, data: Dict[str, Any]) -> None:
        """从字典更新配置"""
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)


# 兼容性别名
ApplicationConfig = AppConfig


def create_default_app_config() -> AppConfig:
    """创建默认应用配置"""
    return AppConfig()


def load_app_config_from_file(config_path: Union[str, Path]) -> AppConfig:
    """从文件加载应用配置"""
    from .loader import ConfigLoader
    
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    loader = ConfigLoader()
    full_config = loader.load_config(config_path)
    
    return AppConfig.from_full_config(full_config)


def save_app_config_to_file(config: AppConfig, config_path: Union[str, Path]) -> None:
    """保存应用配置到文件"""
    from .manager import ConfigManager
    
    config_path = Path(config_path)
    full_config = config.to_full_config()
    
    manager = ConfigManager(config_path.parent)
    manager.save_config(full_config, config_path.name) 