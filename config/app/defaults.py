"""
配置默认值和常量

集中管理所有配置的默认值，便于维护和更新。
"""

# 用户界面默认值（使用标准GUI命名）
DEFAULT_UI_CONFIG = {
    "window_width": 1200,
    "window_height": 800,
    "window_maximized": False,
    "theme": "auto",
    "font_size": 10,
    "default_remove_dupes": True,
    "default_anonymize_ips": True,
    "default_mask_payloads": True,
    "remember_last_dir": True,
    "auto_open_output": False,
    "show_progress_details": True,
    "show_statistics": True,
    "confirm_on_exit": True,
    "auto_scroll_logs": True,
}

# 处理参数默认值
DEFAULT_PROCESSING_CONFIG = {
    "chunk_size": 10,
    "max_retry_attempts": 3,
    "timeout_seconds": 300,
    "max_workers": 4,
    "preserve_subnet_structure": True,
    "preserve_original_segments": True,
    "ip_mapping_consistency": True,
    "preserve_tls_handshake": True,
    "preserve_tls_alerts": True,
    "dedup_algorithm": "sha256",
    "strict_dedup_mode": False,
    "create_backup": False,
    "output_format": "pcap",
    "temp_dir_cleanup": True,
}

# 日志默认值
DEFAULT_LOGGING_CONFIG = {
    "log_level": "INFO",
    "log_to_file": True,
    "log_file_max_size": 10 * 1024 * 1024,  # 10MB
    "log_backup_count": 5,
    "performance_logging": False,
    "enable_protocol_parsing_logs": False,  # 默认关闭协议栈解析详细日志
}

# 文件和路径常量
CONFIG_CONSTANTS = {
    "config_dir_name": ".pktmask",
    "default_config_file": "config.yaml",
    "legacy_config_files": ["config.json", "app_config.yaml"],
    "log_file_name": "pktmask.log",
    "supported_extensions": [".pcap", ".pcapng"],
    "temp_dir_prefix": "pktmask_temp_",
    "output_dir_name": "PktMask_Output",
}

# 验证约束
VALIDATION_CONSTRAINTS = {
    "min_window_width": 800,
    "min_window_height": 600,
    "max_window_width": 3840,
    "max_window_height": 2160,
    "min_chunk_size": 1,
    "max_chunk_size": 1000,
    "min_timeout": 30,
    "max_timeout": 3600,
    "min_workers": 1,
    "max_workers": 16,
    "min_font_size": 8,
    "max_font_size": 24,
    "valid_themes": ["auto", "light", "dark"],
    "valid_log_levels": ["DEBUG", "INFO", "WARNING", "ERROR"],
    "valid_dedup_algorithms": ["md5", "sha1", "sha256"],
    "valid_output_formats": ["pcap", "pcapng"],
}

# 处理器默认配置（使用标准命名）
PROCESSOR_DEFAULTS = {
    "anonymize_ips": {
        "enabled": True,
        "preserve_subnet_structure": True,
        "preserve_original_segments": True,
        "anonymization_strategy": "hierarchical",
    },
    "remove_dupes": {
        "enabled": True,
        "algorithm": "sha256",
        "strict_mode": False,
        "memory_efficient": True,
    },
    "mask_payloads": {
        "enabled": True,
        "mode": "enhanced",
        "preserve_tls_handshake": True,
        "preserve_tls_alerts": True,
    },
}

# 性能默认配置
PERFORMANCE_DEFAULTS = {
    "chunk_processing": True,
    "parallel_processing": True,
    "memory_optimization": True,
    "progress_reporting_interval": 100,
    "statistics_collection": True,
}

# GUI默认配置
GUI_DEFAULTS = {
    "main_window": {
        "title": "PktMask - Packet Processing Tool",
        "icon": None,
        "resizable": True,
        "center_on_screen": True,
    },
    "dialogs": {
        "remember_choices": True,
        "default_file_dialog_dir": None,
        "show_hidden_files": False,
    },
    "progress": {
        "show_percentage": True,
        "show_elapsed_time": True,
        "show_estimated_time": True,
        "update_interval_ms": 100,
    },
}

# 错误处理默认配置
ERROR_HANDLING_DEFAULTS = {
    "max_retry_attempts": 3,
    "retry_delay_seconds": 1,
    "show_error_details": True,
    "auto_save_error_log": True,
    "continue_on_error": False,
}

# External tools configuration
EXTERNAL_TOOLS_DEFAULTS = {
    "tshark": {
        "executable_paths": [
            "/usr/bin/tshark",
            "/usr/local/bin/tshark",
            "/opt/wireshark/bin/tshark",
            "C:\\Program Files\\Wireshark\\tshark.exe",
            "C:\\Program Files (x86)\\Wireshark\\tshark.exe",
            "/Applications/Wireshark.app/Contents/MacOS/tshark",
        ],
        "custom_executable": None,
        "enable_reassembly": True,
        "enable_defragmentation": True,
        "timeout_seconds": 300,
        "max_memory_mb": 1024,
        "quiet_mode": True,
    }
}


def get_default_config_dict():
    """Get complete default configuration dictionary"""
    return {
        "ui": DEFAULT_UI_CONFIG,
        "processing": DEFAULT_PROCESSING_CONFIG,
        "logging": DEFAULT_LOGGING_CONFIG,
        "tools": EXTERNAL_TOOLS_DEFAULTS,
        "config_version": "2.0",
        "created_at": None,
        "updated_at": None,
    }


def get_processor_config(processor_name: str) -> dict:
    """Get default configuration for specific processor"""
    return PROCESSOR_DEFAULTS.get(processor_name, {})


def get_validation_constraint(key: str):
    """Get validation constraint value"""
    return VALIDATION_CONSTRAINTS.get(key)


def is_valid_theme(theme: str) -> bool:
    """Validate if theme name is valid"""
    return theme in VALIDATION_CONSTRAINTS["valid_themes"]


def is_valid_log_level(level: str) -> bool:
    """Validate if log level is valid"""
    return level in VALIDATION_CONSTRAINTS["valid_log_levels"]


def is_valid_dedup_algorithm(algorithm: str) -> bool:
    """Validate if deduplication algorithm is valid"""
    return algorithm in VALIDATION_CONSTRAINTS["valid_dedup_algorithms"]


def get_supported_file_extensions() -> list:
    """Get list of supported file extensions"""
    return CONFIG_CONSTANTS["supported_extensions"].copy()


def get_legacy_config_files() -> list:
    """Get list of legacy configuration file names"""
    return CONFIG_CONSTANTS["legacy_config_files"].copy()


def get_tool_config(tool_name: str) -> dict:
    """Get default configuration for specific tool"""
    return EXTERNAL_TOOLS_DEFAULTS.get(tool_name, {})


def get_tshark_paths() -> list:
    """Get default search paths for TShark executable"""
    return EXTERNAL_TOOLS_DEFAULTS.get("tshark", {}).get("executable_paths", [])
