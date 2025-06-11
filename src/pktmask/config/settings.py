"""
简化的配置系统

替代复杂的企业级配置管理，提供简单直观的配置管理功能。
支持基本的用户界面设置和处理参数配置。
"""
import os
import yaml
import json
from pathlib import Path
from typing import Optional, Dict, Any, Union
from dataclasses import dataclass, asdict, field
from datetime import datetime


@dataclass
class UISettings:
    """用户界面设置"""
    # 窗口设置
    window_width: int = 1200
    window_height: int = 800
    window_min_width: int = 800
    window_min_height: int = 600
    window_maximized: bool = False
    
    # 主题和外观
    theme: str = "auto"  # auto, light, dark
    font_size: int = 10
    
    # 默认选项
    default_dedup: bool = True
    default_mask_ip: bool = True
    default_trim: bool = False
    
    # 文件处理设置
    remember_last_dir: bool = True
    last_input_dir: Optional[str] = None
    last_output_dir: Optional[str] = None
    auto_open_output: bool = False
    
    # 输出目录设置
    default_output_dir: Optional[str] = None
    output_dir_pattern: str = "{input_dir_name}-Masked-{timestamp}"
    
    # 高级界面选项
    show_progress_details: bool = True
    show_statistics: bool = True
    confirm_on_exit: bool = True
    auto_scroll_logs: bool = True


@dataclass
class ProcessingSettings:
    """处理参数设置"""
    # 处理性能
    chunk_size: int = 10
    max_retry_attempts: int = 3
    timeout_seconds: int = 300
    max_workers: int = 4
    
    # IP匿名化设置
    preserve_subnet_structure: bool = True
    preserve_original_segments: bool = True
    ip_mapping_consistency: bool = True
    
    # TLS处理设置
    preserve_tls_handshake: bool = True
    preserve_tls_alerts: bool = True
    
    # 去重设置
    dedup_algorithm: str = "sha256"  # md5, sha1, sha256
    strict_dedup_mode: bool = False
    
    # 文件处理
    create_backup: bool = False
    output_format: str = "pcap"  # pcap, pcapng
    temp_dir_cleanup: bool = True


@dataclass
class LoggingSettings:
    """日志设置"""
    log_level: str = "INFO"  # DEBUG, INFO, WARNING, ERROR
    log_to_file: bool = True
    log_file_max_size: int = 10 * 1024 * 1024  # 10MB
    log_backup_count: int = 5
    performance_logging: bool = False
    
    
@dataclass 
class AppConfig:
    """应用程序主配置
    
    简化的配置管理，替代复杂的企业级配置系统。
    支持基本的加载、保存和验证功能。
    """
    ui: UISettings = field(default_factory=UISettings)
    processing: ProcessingSettings = field(default_factory=ProcessingSettings)
    logging: LoggingSettings = field(default_factory=LoggingSettings)
    
    # 元数据
    config_version: str = "2.0"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
    
    @classmethod
    def load(cls, config_path: Optional[Union[str, Path]] = None) -> 'AppConfig':
        """加载配置文件"""
        if config_path is None:
            config_path = cls.get_default_config_path()
        
        config_path = Path(config_path)
        
        if not config_path.exists():
            # 配置文件不存在，返回默认配置
            return cls.default()
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                if config_path.suffix.lower() == '.json':
                    data = json.load(f)
                else:
                    data = yaml.safe_load(f)
            
            # 递归转换嵌套字典为数据类
            ui_data = data.get('ui', {})
            processing_data = data.get('processing', {})
            logging_data = data.get('logging', {})
            
            return cls(
                ui=UISettings(**ui_data) if ui_data else UISettings(),
                processing=ProcessingSettings(**processing_data) if processing_data else ProcessingSettings(),
                logging=LoggingSettings(**logging_data) if logging_data else LoggingSettings(),
                config_version=data.get('config_version', '2.0'),
                created_at=data.get('created_at'),
                updated_at=data.get('updated_at')
            )
            
        except Exception as e:
            print(f"配置加载失败: {e}，使用默认配置")
            return cls.default()
    
    def save(self, config_path: Optional[Union[str, Path]] = None) -> bool:
        """保存配置文件"""
        if config_path is None:
            config_path = self.get_default_config_path()
        
        config_path = Path(config_path)
        
        try:
            # 确保目录存在
            config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 更新时间戳
            self.updated_at = datetime.now().isoformat()
            
            # 转换为字典
            data = asdict(self)
            
            # 保存文件
            with open(config_path, 'w', encoding='utf-8') as f:
                if config_path.suffix.lower() == '.json':
                    json.dump(data, f, indent=2, ensure_ascii=False)
                else:
                    yaml.dump(data, f, default_flow_style=False, 
                             allow_unicode=True, indent=2)
            
            return True
            
        except Exception as e:
            print(f"配置保存失败: {e}")
            return False
    
    @classmethod
    def default(cls) -> 'AppConfig':
        """获取默认配置"""
        return cls()
    
    @staticmethod
    def get_default_config_path() -> Path:
        """获取默认配置文件路径"""
        home_dir = Path.home()
        config_dir = home_dir / ".pktmask"
        return config_dir / "config.yaml"
    
    @staticmethod
    def get_legacy_config_paths() -> list:
        """获取旧版配置文件路径列表"""
        home_dir = Path.home()
        config_dir = home_dir / ".pktmask"
        
        return [
            config_dir / "config.json",
            config_dir / "app_config.yaml",
            config_dir / "pktmask_config.yaml"
        ]
    
    def validate(self) -> tuple[bool, list]:
        """验证配置有效性"""
        errors = []
        warnings = []
        
        # 验证UI设置
        if self.ui.window_width < 800 or self.ui.window_height < 600:
            warnings.append("窗口尺寸可能过小，建议至少800x600")
        
        if self.ui.theme not in ['auto', 'light', 'dark']:
            errors.append(f"无效的主题设置: {self.ui.theme}")
        
        # 验证处理设置
        if self.processing.chunk_size <= 0:
            errors.append("chunk_size必须大于0")
        
        if self.processing.max_workers <= 0:
            errors.append("max_workers必须大于0")
        
        if self.processing.timeout_seconds <= 0:
            errors.append("timeout_seconds必须大于0")
        
        if self.processing.dedup_algorithm not in ['md5', 'sha1', 'sha256']:
            errors.append(f"无效的去重算法: {self.processing.dedup_algorithm}")
        
        # 验证日志设置
        valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR']
        if self.logging.log_level not in valid_log_levels:
            errors.append(f"无效的日志级别: {self.logging.log_level}")
        
        if self.logging.log_file_max_size <= 0:
            errors.append("log_file_max_size必须大于0")
        
        return len(errors) == 0, errors + warnings
    
    def get_processing_config(self) -> Dict[str, Any]:
        """获取处理器配置字典"""
        return {
            'chunk_size': self.processing.chunk_size,
            'max_retry_attempts': self.processing.max_retry_attempts,
            'timeout_seconds': self.processing.timeout_seconds,
            'max_workers': self.processing.max_workers,
            'preserve_subnet_structure': self.processing.preserve_subnet_structure,
            'preserve_tls_handshake': self.processing.preserve_tls_handshake,
            'dedup_algorithm': self.processing.dedup_algorithm,
            'create_backup': self.processing.create_backup
        }
    
    def get_ui_config(self) -> Dict[str, Any]:
        """获取UI配置字典"""
        return {
            'default_dedup': self.ui.default_dedup,
            'default_mask_ip': self.ui.default_mask_ip,
            'default_trim': self.ui.default_trim,
            'remember_last_dir': self.ui.remember_last_dir,
            'last_input_dir': self.ui.last_input_dir,
            'last_output_dir': self.ui.last_output_dir,
            'auto_open_output': self.ui.auto_open_output,
            'theme': self.ui.theme
        }
    
    def update_last_directories(self, input_dir: Optional[str] = None, 
                              output_dir: Optional[str] = None):
        """更新最后使用的目录"""
        if input_dir and self.ui.remember_last_dir:
            self.ui.last_input_dir = str(Path(input_dir).resolve())
        
        if output_dir and self.ui.remember_last_dir:
            self.ui.last_output_dir = str(Path(output_dir).resolve())
    
    def migrate_from_legacy(self) -> bool:
        """从旧版配置文件迁移"""
        for legacy_path in self.get_legacy_config_paths():
            if legacy_path.exists():
                try:
                    legacy_config = self.load(legacy_path)
                    
                    # 合并配置（保留新配置的结构）
                    self.ui.last_input_dir = legacy_config.ui.last_input_dir
                    self.ui.last_output_dir = legacy_config.ui.last_output_dir
                    
                    # 保存迁移后的配置
                    if self.save():
                        print(f"成功从 {legacy_path} 迁移配置")
                        return True
                        
                except Exception as e:
                    print(f"从 {legacy_path} 迁移配置失败: {e}")
                    continue
        
        return False


# 全局配置实例
_app_config: Optional[AppConfig] = None


def get_app_config() -> AppConfig:
    """获取全局应用配置实例"""
    global _app_config
    if _app_config is None:
        _app_config = AppConfig.load()
    return _app_config


def reload_app_config():
    """重新加载配置"""
    global _app_config
    _app_config = AppConfig.load()


def save_app_config() -> bool:
    """保存当前配置"""
    global _app_config
    if _app_config is not None:
        return _app_config.save()
    return False 