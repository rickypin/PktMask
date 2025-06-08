#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
配置管理器
提供统一的配置管理服务，包括加载、保存、验证和更新
"""

import os
from typing import Dict, Any, Optional, List, Callable
from pathlib import Path
from threading import Lock

from ..infrastructure.logging import get_logger
from ..common.exceptions import ConfigError, ValidationError
from .models import PktMaskConfig
from .loader import ConfigLoader, ConfigDefaults
from .validators import ConfigValidator


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_file: Optional[str] = None):
        """
        初始化配置管理器
        
        Args:
            config_file: 配置文件路径，None时使用默认路径
        """
        self.logger = get_logger(__name__)
        self._config: Optional[PktMaskConfig] = None
        self._config_file: Optional[Path] = None
        self._loader = ConfigLoader()
        self._validator = ConfigValidator()
        self._lock = Lock()
        
        # 配置变更回调
        self._change_callbacks: List[Callable[[PktMaskConfig], None]] = []
        
        # 设置配置文件路径
        if config_file:
            self._config_file = Path(config_file)
        else:
            self._set_default_config_path()
        
        # 加载配置
        self._load_config()
    
    def _set_default_config_path(self) -> None:
        """设置默认配置文件路径"""
        # 优先使用用户配置目录
        if os.name == 'nt':  # Windows
            config_dir = Path(os.environ.get('APPDATA', '')) / 'PktMask'
        else:  # Unix-like
            config_dir = Path.home() / '.config' / 'pktmask'
        
        config_dir.mkdir(parents=True, exist_ok=True)
        self._config_file = config_dir / 'config.yaml'
        
        self.logger.info(f"配置文件路径: {self._config_file}")
    
    def _load_config(self) -> None:
        """加载配置"""
        try:
            if self._config_file and self._config_file.exists():
                self._config = self._loader.load_config(self._config_file)
            else:
                # 创建默认配置
                self._config = PktMaskConfig()
                if self._config_file:
                    self._save_config()
                
            # 验证配置
            is_valid, errors, warnings = self._validator.validate_config(self._config)
            
            if not is_valid:
                self.logger.error(f"配置验证失败: {errors}")
                # 使用默认配置
                self._config = PktMaskConfig()
            
            if warnings:
                for warning in warnings:
                    self.logger.warning(f"配置警告: {warning}")
                    
        except Exception as e:
            self.logger.error(f"加载配置失败: {e}")
            self._config = PktMaskConfig()
    
    def _save_config(self) -> None:
        """保存配置"""
        if not self._config_file or not self._config:
            return
            
        try:
            self._loader.save_config(self._config, self._config_file)
        except Exception as e:
            self.logger.error(f"保存配置失败: {e}")
            raise ConfigError(f"Failed to save config: {e}")
    
    @property
    def config(self) -> PktMaskConfig:
        """获取当前配置"""
        if self._config is None:
            self._config = PktMaskConfig()
        return self._config
    
    def get_ui_config(self):
        """获取UI配置"""
        return self.config.ui
    
    def get_processing_config(self):
        """获取处理配置"""
        return self.config.processing
    
    def get_performance_config(self):
        """获取性能配置"""
        return self.config.performance
    
    def get_file_config(self):
        """获取文件配置"""
        return self.config.file
    
    def get_logging_config(self):
        """获取日志配置"""
        return self.config.logging
    
    def update_config(self, updates: Dict[str, Any]) -> bool:
        """
        更新配置
        
        Args:
            updates: 配置更新字典
            
        Returns:
            bool: 更新是否成功
        """
        with self._lock:
            try:
                # 创建更新后的配置
                updated_config = self._loader.merge_configs(self.config, updates)
                
                # 验证更新后的配置
                is_valid, errors, warnings = self._validator.validate_config(updated_config)
                
                if not is_valid:
                    self.logger.error(f"配置更新验证失败: {errors}")
                    return False
                
                if warnings:
                    for warning in warnings:
                        self.logger.warning(f"配置更新警告: {warning}")
                
                # 应用配置更新
                old_config = self._config
                self._config = updated_config
                
                # 保存配置
                self._save_config()
                
                # 触发回调
                self._notify_config_changed()
                
                self.logger.info("配置更新成功")
                return True
                
            except Exception as e:
                self.logger.error(f"配置更新失败: {e}")
                return False
    
    def update_ui_config(self, **kwargs) -> bool:
        """更新UI配置"""
        return self.update_config({'ui': kwargs})
    
    def update_processing_config(self, **kwargs) -> bool:
        """更新处理配置"""
        return self.update_config({'processing': kwargs})
    
    def update_performance_config(self, **kwargs) -> bool:
        """更新性能配置"""
        return self.update_config({'performance': kwargs})
    
    def update_file_config(self, **kwargs) -> bool:
        """更新文件配置"""
        return self.update_config({'file': kwargs})
    
    def update_logging_config(self, **kwargs) -> bool:
        """更新日志配置"""
        return self.update_config({'logging': kwargs})
    
    def reset_to_defaults(self, section: Optional[str] = None) -> bool:
        """
        重置配置为默认值
        
        Args:
            section: 要重置的配置段，None表示重置全部
            
        Returns:
            bool: 重置是否成功
        """
        try:
            if section is None:
                # 重置全部配置
                self._config = PktMaskConfig()
            else:
                # 重置指定段
                default_config = PktMaskConfig()
                if hasattr(default_config, section):
                    setattr(self._config, section, getattr(default_config, section))
                else:
                    raise ValueError(f"Unknown config section: {section}")
            
            self._save_config()
            self._notify_config_changed()
            
            self.logger.info(f"配置已重置为默认值: {section or 'all'}")
            return True
            
        except Exception as e:
            self.logger.error(f"配置重置失败: {e}")
            return False
    
    def validate_config(self) -> Dict[str, Any]:
        """
        验证当前配置
        
        Returns:
            Dict: 验证结果
        """
        is_valid, errors, warnings = self._validator.validate_config(self.config)
        
        return {
            'valid': is_valid,
            'errors': errors,
            'warnings': warnings,
            'config': self.config
        }
    
    def export_config(self, file_path: str, format_type: str = 'yaml') -> bool:
        """
        导出配置到文件
        
        Args:
            file_path: 导出文件路径
            format_type: 文件格式
            
        Returns:
            bool: 导出是否成功
        """
        try:
            self._loader.save_config(self.config, file_path, format_type)
            self.logger.info(f"配置已导出到: {file_path}")
            return True
        except Exception as e:
            self.logger.error(f"导出配置失败: {e}")
            return False
    
    def import_config(self, file_path: str) -> bool:
        """
        从文件导入配置
        
        Args:
            file_path: 配置文件路径
            
        Returns:
            bool: 导入是否成功
        """
        try:
            imported_config = self._loader.load_config(file_path)
            
            # 验证导入的配置
            is_valid, errors, warnings = self._validator.validate_config(imported_config)
            
            if not is_valid:
                self.logger.error(f"导入的配置无效: {errors}")
                return False
            
            if warnings:
                for warning in warnings:
                    self.logger.warning(f"导入配置警告: {warning}")
            
            # 应用导入的配置
            self._config = imported_config
            self._save_config()
            self._notify_config_changed()
            
            self.logger.info(f"配置已从文件导入: {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"导入配置失败: {e}")
            return False
    
    def backup_config(self, backup_path: Optional[str] = None) -> bool:
        """
        备份当前配置
        
        Args:
            backup_path: 备份文件路径，None时自动生成
            
        Returns:
            bool: 备份是否成功
        """
        try:
            if backup_path is None:
                from ..utils.time import current_timestamp
                timestamp = current_timestamp()
                backup_name = f"config_backup_{timestamp}.yaml"
                backup_path = self._config_file.parent / backup_name
            
            self._loader.save_config(self.config, backup_path)
            self.logger.info(f"配置已备份到: {backup_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"备份配置失败: {e}")
            return False
    
    def register_change_callback(self, callback: Callable[[PktMaskConfig], None]) -> None:
        """
        注册配置变更回调
        
        Args:
            callback: 回调函数
        """
        if callback not in self._change_callbacks:
            self._change_callbacks.append(callback)
    
    def unregister_change_callback(self, callback: Callable[[PktMaskConfig], None]) -> None:
        """
        取消注册配置变更回调
        
        Args:
            callback: 回调函数
        """
        if callback in self._change_callbacks:
            self._change_callbacks.remove(callback)
    
    def _notify_config_changed(self) -> None:
        """通知配置已变更"""
        for callback in self._change_callbacks:
            try:
                callback(self.config)
            except Exception as e:
                self.logger.error(f"配置变更回调执行失败: {e}")
    
    def get_config_info(self) -> Dict[str, Any]:
        """获取配置信息"""
        return {
            'config_file': str(self._config_file) if self._config_file else None,
            'config_version': self.config.config_version,
            'created_at': self.config.created_at,
            'updated_at': self.config.updated_at,
            'valid': self.validate_config()['valid']
        }
    
    def reload_config(self) -> bool:
        """重新加载配置文件"""
        try:
            old_config = self._config
            self._load_config()
            
            if self._config != old_config:
                self._notify_config_changed()
                self.logger.info("配置已重新加载")
            
            return True
            
        except Exception as e:
            self.logger.error(f"重新加载配置失败: {e}")
            return False


# 全局配置管理器实例
_config_manager: Optional[ConfigManager] = None


def get_config_manager(config_file: Optional[str] = None) -> ConfigManager:
    """
    获取全局配置管理器实例
    
    Args:
        config_file: 配置文件路径
        
    Returns:
        ConfigManager: 配置管理器实例
    """
    global _config_manager
    
    if _config_manager is None:
        _config_manager = ConfigManager(config_file)
    
    return _config_manager


def get_config() -> PktMaskConfig:
    """获取当前配置"""
    return get_config_manager().config


def update_config(updates: Dict[str, Any]) -> bool:
    """更新配置"""
    return get_config_manager().update_config(updates) 