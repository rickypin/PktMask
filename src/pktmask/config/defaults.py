"""
配置默认值和常量

集中管理所有配置的默认值，便于维护和更新。
"""

# 用户界面默认值
DEFAULT_UI_CONFIG = {
    'window_width': 1200,
    'window_height': 800,
    'window_maximized': False,
    'theme': 'auto',
    'font_size': 10,
    'default_dedup': True,
    'default_mask_ip': True,
    'default_trim': False,
    'remember_last_dir': True,
    'auto_open_output': False,
    'show_progress_details': True,
    'show_statistics': True,
    'confirm_on_exit': True,
    'auto_scroll_logs': True
}

# 处理参数默认值
DEFAULT_PROCESSING_CONFIG = {
    'chunk_size': 10,
    'max_retry_attempts': 3,
    'timeout_seconds': 300,
    'max_workers': 4,
    'preserve_subnet_structure': True,
    'preserve_original_segments': True,
    'ip_mapping_consistency': True,
    'preserve_tls_handshake': True,
    'preserve_tls_alerts': True,
    'dedup_algorithm': 'sha256',
    'strict_dedup_mode': False,
    'create_backup': False,
    'output_format': 'pcap',
    'temp_dir_cleanup': True
}

# 日志默认值
DEFAULT_LOGGING_CONFIG = {
    'log_level': 'INFO',
    'log_to_file': True,
    'log_file_max_size': 10 * 1024 * 1024,  # 10MB
    'log_backup_count': 5,
    'performance_logging': False
}

# 文件和路径常量
CONFIG_CONSTANTS = {
    'config_dir_name': '.pktmask',
    'default_config_file': 'config.yaml',
    'legacy_config_files': ['config.json', 'app_config.yaml', 'pktmask_config.yaml'],
    'log_file_name': 'pktmask.log',
    'supported_extensions': ['.pcap', '.pcapng'],
    'temp_dir_prefix': 'pktmask_temp_',
    'output_dir_name': 'PktMask_Output'
}

# 验证约束
VALIDATION_CONSTRAINTS = {
    'min_window_width': 800,
    'min_window_height': 600,
    'max_window_width': 3840,
    'max_window_height': 2160,
    'min_chunk_size': 1,
    'max_chunk_size': 1000,
    'min_timeout': 30,
    'max_timeout': 3600,
    'min_workers': 1,
    'max_workers': 16,
    'min_font_size': 8,
    'max_font_size': 24,
    'valid_themes': ['auto', 'light', 'dark'],
    'valid_log_levels': ['DEBUG', 'INFO', 'WARNING', 'ERROR'],
    'valid_dedup_algorithms': ['md5', 'sha1', 'sha256'],
    'valid_output_formats': ['pcap', 'pcapng']
}

# 处理器默认配置
PROCESSOR_DEFAULTS = {
    'ip_anonymizer': {
        'enabled': True,
        'preserve_subnet_structure': True,
        'preserve_original_segments': True,
        'anonymization_strategy': 'hierarchical'
    },
    'deduplicator': {
        'enabled': True,
        'algorithm': 'sha256',
        'strict_mode': False,
        'memory_efficient': True
    },
    'trimmer': {
        'enabled': False,
        'preserve_tls_handshake': True,
        'preserve_tls_alerts': True,
        'trim_threshold': 1024
    }
}

# 性能默认配置
PERFORMANCE_DEFAULTS = {
    'chunk_processing': True,
    'parallel_processing': True,
    'memory_optimization': True,
    'progress_reporting_interval': 100,
    'statistics_collection': True
}

# GUI默认配置
GUI_DEFAULTS = {
    'main_window': {
        'title': 'PktMask - Packet Processing Tool',
        'icon': None,
        'resizable': True,
        'center_on_screen': True
    },
    'dialogs': {
        'remember_choices': True,
        'default_file_dialog_dir': None,
        'show_hidden_files': False
    },
    'progress': {
        'show_percentage': True,
        'show_elapsed_time': True,
        'show_estimated_time': True,
        'update_interval_ms': 100
    }
}

# 错误处理默认配置
ERROR_HANDLING_DEFAULTS = {
    'max_retry_attempts': 3,
    'retry_delay_seconds': 1,
    'show_error_details': True,
    'auto_save_error_log': True,
    'continue_on_error': False
}


def get_default_config_dict():
    """获取完整的默认配置字典"""
    return {
        'ui': DEFAULT_UI_CONFIG,
        'processing': DEFAULT_PROCESSING_CONFIG,
        'logging': DEFAULT_LOGGING_CONFIG,
        'config_version': '2.0',
        'created_at': None,
        'updated_at': None
    }


def get_processor_config(processor_name: str) -> dict:
    """获取特定处理器的默认配置"""
    return PROCESSOR_DEFAULTS.get(processor_name, {})


def get_validation_constraint(key: str):
    """获取验证约束值"""
    return VALIDATION_CONSTRAINTS.get(key)


def is_valid_theme(theme: str) -> bool:
    """验证主题名称是否有效"""
    return theme in VALIDATION_CONSTRAINTS['valid_themes']


def is_valid_log_level(level: str) -> bool:
    """验证日志级别是否有效"""
    return level in VALIDATION_CONSTRAINTS['valid_log_levels']


def is_valid_dedup_algorithm(algorithm: str) -> bool:
    """验证去重算法是否有效"""
    return algorithm in VALIDATION_CONSTRAINTS['valid_dedup_algorithms']


def get_supported_file_extensions() -> list:
    """获取支持的文件扩展名列表"""
    return CONFIG_CONSTANTS['supported_extensions'].copy()


def get_legacy_config_files() -> list:
    """获取旧版配置文件名列表"""
    return CONFIG_CONSTANTS['legacy_config_files'].copy() 