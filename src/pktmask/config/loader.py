#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
配置文件加载器
支持YAML和JSON格式的配置文件读写
"""

import os
import json
from typing import Dict, Any, Optional, Union
from pathlib import Path

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

from ..infrastructure.logging import get_logger
from ..common.exceptions import FileError, ConfigError
from .models import PktMaskConfig


class ConfigLoader:
    """配置文件加载器"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        
    def load_config(self, file_path: Union[str, Path]) -> PktMaskConfig:
        """
        从文件加载配置
        
        Args:
            file_path: 配置文件路径
            
        Returns:
            PktMaskConfig: 配置对象
            
        Raises:
            FileError: 文件不存在或无法读取
            ConfigError: 配置格式错误
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            self.logger.warning(f"配置文件不存在: {file_path}")
            return PktMaskConfig()  # 返回默认配置
            
        if not file_path.is_file():
            raise FileError(f"Path is not a file: {file_path}")
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                if file_path.suffix.lower() in ['.yaml', '.yml']:
                    if not YAML_AVAILABLE:
                        raise ConfigError("YAML support not available. Install PyYAML.")
                    data = yaml.safe_load(f)
                elif file_path.suffix.lower() == '.json':
                    data = json.load(f)
                else:
                    raise ConfigError(f"Unsupported config file format: {file_path.suffix}")
                    
            if data is None:
                data = {}
                
            config = PktMaskConfig(**data)
            self.logger.info(f"配置加载成功: {file_path}")
            return config
            
        except yaml.YAMLError as e:
            raise ConfigError(f"YAML解析错误: {e}")
        except json.JSONDecodeError as e:
            raise ConfigError(f"JSON解析错误: {e}")
        except Exception as e:
            raise ConfigError(f"配置加载失败: {e}")
    
    def save_config(self, config: PktMaskConfig, file_path: Union[str, Path], 
                   format_type: str = 'yaml') -> None:
        """
        保存配置到文件
        
        Args:
            config: 配置对象
            file_path: 配置文件路径
            format_type: 文件格式 ('yaml', 'json')
            
        Raises:
            ConfigError: 保存失败
        """
        file_path = Path(file_path)
        
        # 确保目录存在
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 更新时间戳
        config.update_timestamp()
        
        try:
            data = config.dict_for_serialization()
            
            with open(file_path, 'w', encoding='utf-8') as f:
                if format_type.lower() == 'yaml':
                    if not YAML_AVAILABLE:
                        raise ConfigError("YAML support not available. Install PyYAML.")
                    yaml.dump(data, f, default_flow_style=False, 
                             allow_unicode=True, indent=2, sort_keys=False)
                elif format_type.lower() == 'json':
                    json.dump(data, f, ensure_ascii=False, indent=2)
                else:
                    raise ConfigError(f"Unsupported format: {format_type}")
                    
            self.logger.info(f"配置保存成功: {file_path}")
            
        except Exception as e:
            raise ConfigError(f"配置保存失败: {e}")
    
    def create_default_config_file(self, file_path: Union[str, Path]) -> PktMaskConfig:
        """
        创建默认配置文件
        
        Args:
            file_path: 配置文件路径
            
        Returns:
            PktMaskConfig: 默认配置对象
        """
        config = PktMaskConfig()
        self.save_config(config, file_path)
        self.logger.info(f"默认配置文件已创建: {file_path}")
        return config
    
    def validate_config_file(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        验证配置文件格式
        
        Args:
            file_path: 配置文件路径
            
        Returns:
            Dict: 验证结果
        """
        result = {
            'valid': False,
            'errors': [],
            'warnings': []
        }
        
        try:
            config = self.load_config(file_path)
            result['valid'] = True
            result['config'] = config
            
        except ConfigError as e:
            result['errors'].append(str(e))
        except Exception as e:
            result['errors'].append(f"Unexpected error: {e}")
            
        return result
    
    def merge_configs(self, base_config: PktMaskConfig, 
                     override_config: Dict[str, Any]) -> PktMaskConfig:
        """
        合并配置
        
        Args:
            base_config: 基础配置
            override_config: 覆盖配置字典
            
        Returns:
            PktMaskConfig: 合并后的配置
        """
        base_dict = base_config.dict()
        merged_dict = self._deep_merge(base_dict, override_config)
        
        try:
            return PktMaskConfig(**merged_dict)
        except Exception as e:
            self.logger.error(f"配置合并失败: {e}")
            return base_config
    
    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """
        深度合并字典
        
        Args:
            base: 基础字典
            override: 覆盖字典
            
        Returns:
            Dict: 合并后的字典
        """
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
                
        return result
    
    def export_config_template(self, file_path: Union[str, Path]) -> None:
        """
        导出配置模板文件
        
        Args:
            file_path: 模板文件路径
        """
        template_config = PktMaskConfig()
        
        # 添加注释信息
        template_data = {
            '_comment': 'PktMask Configuration Template',
            '_version': template_config.config_version,
            '_description': {
                'ui': '用户界面相关配置',
                'processing': '数据处理相关配置',
                'performance': '性能调优配置',
                'file': '文件处理配置',
                'logging': '日志配置'
            }
        }
        
        # 合并实际配置
        config_data = template_config.dict_for_serialization()
        template_data.update(config_data)
        
        file_path = Path(file_path)
        with open(file_path, 'w', encoding='utf-8') as f:
            if file_path.suffix.lower() in ['.yaml', '.yml']:
                if YAML_AVAILABLE:
                    yaml.dump(template_data, f, default_flow_style=False, 
                             allow_unicode=True, indent=2, sort_keys=False)
                else:
                    raise ConfigError("YAML support not available. Install PyYAML.")
            else:
                json.dump(template_data, f, ensure_ascii=False, indent=2)
                
        self.logger.info(f"配置模板已导出: {file_path}")


class ConfigDefaults:
    """配置默认值管理"""
    
    @staticmethod
    def get_system_defaults() -> Dict[str, Any]:
        """获取系统默认配置"""
        return {
            'ui': {
                'window_width': 1200,
                'window_height': 800,
                'theme': 'auto',
                'language': 'zh_CN'
            },
            'processing': {
                'chunk_size': 10,
                'max_retry_attempts': 3,
                'timeout_seconds': 300
            },
            'performance': {
                'max_workers': min(4, os.cpu_count() or 1),
                'memory_limit_mb': 1024
            },
            'file': {
                'max_file_size_gb': 2.0,
                'supported_extensions': ['.pcap', '.pcapng']
            },
            'logging': {
                'console_level': 'INFO',
                'file_level': 'DEBUG'
            }
        }
    
    @staticmethod
    def get_user_defaults() -> Dict[str, Any]:
        """获取用户默认配置（可被用户自定义覆盖）"""
        return {
            'ui': {
                'default_dedup': True,
                'default_mask_ip': True,
                'default_trim': False,
                'remember_last_dir': True,
                'auto_open_output': False
            },
            'processing': {
                'preserve_subnet_structure': True,
                'consistent_mapping': True,
                'preserve_tls_handshake': True
            },
            'file': {
                'generate_html_report': True,
                'generate_json_report': True,
                'cleanup_temp_files': True
            }
        } 