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
    
    # 默认选项（使用标准GUI命名）
    default_remove_dupes: bool = True
    default_anonymize_ips: bool = True
    default_mask_payloads: bool = True
    
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
    enable_protocol_parsing_logs: bool = False  # 控制协议栈解析详细日志输出


@dataclass
class TSharkSettings:
    """TShark工具设置"""
    executable_paths: list = field(default_factory=lambda: [
        '/usr/bin/tshark',
        '/usr/local/bin/tshark',
        '/opt/wireshark/bin/tshark',
        'C:\\Program Files\\Wireshark\\tshark.exe',
        'C:\\Program Files (x86)\\Wireshark\\tshark.exe',
        '/Applications/Wireshark.app/Contents/MacOS/tshark'
    ])
    custom_executable: Optional[str] = None
    enable_reassembly: bool = True
    enable_defragmentation: bool = True
    timeout_seconds: int = 300
    max_memory_mb: int = 1024
    quiet_mode: bool = True


@dataclass
class FallbackConfig:
    """TShark增强处理器降级机制配置"""
    enable_fallback: bool = True
    max_retries: int = 2
    retry_delay_seconds: float = 1.0
    tshark_check_timeout: float = 5.0
    fallback_on_tshark_unavailable: bool = True
    fallback_on_parse_error: bool = True
    fallback_on_other_errors: bool = True
    preferred_fallback_order: list = field(default_factory=lambda: [
        "mask_stage"
    ])


@dataclass
class TSharkEnhancedSettings:
    """TShark增强掩码处理器配置"""
    
    # 核心功能配置
    enable_tls_processing: bool = True
    enable_cross_segment_detection: bool = True
    enable_boundary_safety: bool = True
    
    # TLS协议类型处理配置
    tls_20_strategy: str = "keep_all"      # ChangeCipherSpec: 完全保留
    tls_21_strategy: str = "keep_all"      # Alert: 完全保留  
    tls_22_strategy: str = "keep_all"      # Handshake: 完全保留
    tls_23_strategy: str = "mask_payload"  # ApplicationData: 智能掩码
    tls_24_strategy: str = "keep_all"      # Heartbeat: 完全保留
    tls_23_header_preserve_bytes: int = 5  # TLS-23头部保留字节数
    
    # 性能配置
    temp_dir: Optional[str] = None
    cleanup_temp_files: bool = True
    enable_parallel_processing: bool = False
    chunk_size: int = 1000
    
    # 调试配置
    enable_detailed_logging: bool = False
    enable_performance_monitoring: bool = True  # 添加缺失的性能监控配置
    keep_intermediate_files: bool = False
    enable_stage_timing: bool = True
    
    # 降级机制配置
    fallback_config: FallbackConfig = field(default_factory=FallbackConfig)


@dataclass 
class ToolsSettings:
    """外部工具设置"""
    tshark: TSharkSettings = field(default_factory=TSharkSettings)
    tshark_enhanced: TSharkEnhancedSettings = field(default_factory=TSharkEnhancedSettings)
    
    
@dataclass 
class AppConfig:
    """应用程序主配置
    
    简化的配置管理，替代复杂的企业级配置系统。
    支持基本的加载、保存和验证功能。
    """
    ui: UISettings = field(default_factory=UISettings)
    processing: ProcessingSettings = field(default_factory=ProcessingSettings)
    logging: LoggingSettings = field(default_factory=LoggingSettings)
    tools: ToolsSettings = field(default_factory=ToolsSettings)
    
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
            tools_data = data.get('tools', {})
            
            # 处理工具配置的嵌套结构
            tools_settings = ToolsSettings()
            if tools_data:
                tshark_data = tools_data.get('tshark', {})
                if tshark_data:
                    tools_settings.tshark = TSharkSettings(**tshark_data)
                
                # 处理TShark增强配置
                tshark_enhanced_data = tools_data.get('tshark_enhanced', {})
                if tshark_enhanced_data:
                    # 处理降级配置的嵌套结构
                    fallback_data = tshark_enhanced_data.get('fallback_config', {})
                    if fallback_data:
                        fallback_config = FallbackConfig(**fallback_data)
                        tshark_enhanced_data['fallback_config'] = fallback_config
                    
                    tools_settings.tshark_enhanced = TSharkEnhancedSettings(**tshark_enhanced_data)
            
            return cls(
                ui=UISettings(**ui_data) if ui_data else UISettings(),
                processing=ProcessingSettings(**processing_data) if processing_data else ProcessingSettings(),
                logging=LoggingSettings(**logging_data) if logging_data else LoggingSettings(),
                tools=tools_settings,
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
            config_dir / "pktconfig/default/mask_config.yaml"
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
        """获取UI配置字典（使用标准命名规范）"""
        return {
            'default_remove_dupes': self.ui.default_remove_dupes,
            'default_anonymize_ips': self.ui.default_anonymize_ips,
            'default_mask_payloads': self.ui.default_mask_payloads,
            'remember_last_dir': self.ui.remember_last_dir,
            'last_input_dir': self.ui.last_input_dir,
            'last_output_dir': self.ui.last_output_dir,
            'auto_open_output': self.ui.auto_open_output,
            'theme': self.ui.theme
        }
    
    def get_tools_config(self) -> Dict[str, Any]:
        """获取工具配置字典"""
        return {
            'tshark_executable_paths': self.tools.tshark.executable_paths,
            'tshark_custom_executable': self.tools.tshark.custom_executable,
            'tshark_enable_reassembly': self.tools.tshark.enable_reassembly,
            'tshark_enable_defragmentation': self.tools.tshark.enable_defragmentation,
            'tshark_timeout_seconds': self.tools.tshark.timeout_seconds,
            'tshark_max_memory_mb': self.tools.tshark.max_memory_mb,
            'tshark_quiet_mode': self.tools.tshark.quiet_mode
        }
    
    def get_tshark_enhanced_config(self) -> Dict[str, Any]:
        """获取TShark增强配置字典"""
        enhanced = self.tools.tshark_enhanced
        return {
            # 核心功能配置
            'enable_tls_processing': enhanced.enable_tls_processing,
            'enable_cross_segment_detection': enhanced.enable_cross_segment_detection,
            'enable_boundary_safety': enhanced.enable_boundary_safety,
            
            # TLS协议类型处理配置
            'tls_20_strategy': enhanced.tls_20_strategy,
            'tls_21_strategy': enhanced.tls_21_strategy,
            'tls_22_strategy': enhanced.tls_22_strategy,
            'tls_23_strategy': enhanced.tls_23_strategy,
            'tls_24_strategy': enhanced.tls_24_strategy,
            'tls_23_header_preserve_bytes': enhanced.tls_23_header_preserve_bytes,
            
            # 性能配置
            'temp_dir': enhanced.temp_dir,
            'cleanup_temp_files': enhanced.cleanup_temp_files,
            'enable_parallel_processing': enhanced.enable_parallel_processing,
            'chunk_size': enhanced.chunk_size,
            
            # 调试配置
            'enable_detailed_logging': enhanced.enable_detailed_logging,
            'enable_performance_monitoring': enhanced.enable_performance_monitoring,
            'keep_intermediate_files': enhanced.keep_intermediate_files,
            'enable_stage_timing': enhanced.enable_stage_timing,
            
            # 降级机制配置
            'fallback_enable_fallback': enhanced.fallback_config.enable_fallback,
            'fallback_max_retries': enhanced.fallback_config.max_retries,
            'fallback_retry_delay_seconds': enhanced.fallback_config.retry_delay_seconds,
            'fallback_tshark_check_timeout': enhanced.fallback_config.tshark_check_timeout,
            'fallback_on_tshark_unavailable': enhanced.fallback_config.fallback_on_tshark_unavailable,
            'fallback_on_parse_error': enhanced.fallback_config.fallback_on_parse_error,
            'fallback_on_other_errors': enhanced.fallback_config.fallback_on_other_errors,
            'fallback_preferred_fallback_order': enhanced.fallback_config.preferred_fallback_order
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