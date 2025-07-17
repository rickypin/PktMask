#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PktMask 枚举定义
统一管理应用程序中的所有枚举类型
"""

from enum import Enum, IntEnum, auto


class ProcessingStepType(Enum):
    """处理步骤类型枚举（使用标准GUI命名）"""
    ANONYMIZE_IPS = "anonymize_ips"
    REMOVE_DUPES = "remove_dupes"
    MASK_PAYLOADS = "mask_payloads"
    WEB_FOCUSED = "web_focused"  # HTTP功能已移除，保留向后兼容

    # 旧枚举值 - 保持向后兼容
    MASK_IP = "mask_ip"  # 废弃，使用 ANONYMIZE_IPS
    DEDUP_PACKET = "dedup_packet"  # 废弃，使用 REMOVE_DUPES
    TRIM_PACKET = "trim_packet"  # 废弃，使用 MASK_PAYLOADS


class PipelineStatus(Enum):
    """管道处理状态枚举"""
    IDLE = "idle"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"
    COMPLETED = "completed"


class LogLevel(IntEnum):
    """日志级别枚举"""
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


class FileType(Enum):
    """文件类型枚举"""
    PCAP = ".pcap"
    PCAPNG = ".pcapng"
    UNKNOWN = "unknown"


class IPVersion(IntEnum):
    """IP版本枚举"""
    IPV4 = 4
    IPV6 = 6


class NetworkProtocol(IntEnum):
    """网络协议枚举"""
    TCP = 6
    UDP = 17
    ICMP = 1
    ICMPv6 = 58


class ThemeType(Enum):
    """主题类型枚举"""
    AUTO = "auto"
    LIGHT = "light"
    DARK = "dark"


class LanguageType(Enum):
    """语言类型枚举"""
    CHINESE = "zh_CN"
    ENGLISH = "en_US"


class ValidationResult(Enum):
    """验证结果枚举"""
    VALID = "valid"
    INVALID_FORMAT = "invalid_format"
    FILE_NOT_FOUND = "file_not_found"
    PERMISSION_DENIED = "permission_denied"
    FILE_TOO_LARGE = "file_too_large"
    FILE_TOO_SMALL = "file_too_small"


class ProcessingResult(Enum):
    """处理结果枚举"""
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    PARTIAL = "partial"


class AnonymizationStrategy(Enum):
    """匿名化策略枚举"""
    HIERARCHICAL = "hierarchical"
    RANDOM = "random"
    CRYPTOGRAPHIC = "cryptographic"


class ReportFormat(Enum):
    """报告格式枚举"""
    JSON = "json"
    HTML = "html"
    CSV = "csv"
    XML = "xml"


class ConfigFormat(Enum):
    """配置文件格式枚举"""
    YAML = "yaml"
    JSON = "json"
    TOML = "toml"


class ErrorSeverity(IntEnum):
    """错误严重级别枚举"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class UIEvent(Enum):
    """UI事件类型枚举"""
    DIRECTORY_SELECTED = auto()
    PROCESSING_STARTED = auto()
    PROCESSING_STOPPED = auto()
    PROCESSING_COMPLETED = auto()
    CONFIGURATION_CHANGED = auto()
    THEME_CHANGED = auto()
    LANGUAGE_CHANGED = auto()


class ProcessingEvent(Enum):
    """处理事件类型枚举"""
    FILE_STARTED = auto()
    FILE_COMPLETED = auto()
    STEP_STARTED = auto()
    STEP_COMPLETED = auto()
    PROGRESS_UPDATED = auto()
    ERROR_OCCURRED = auto()


# 便利函数
def get_enum_values(enum_class):
    """获取枚举类的所有值"""
    return [item.value for item in enum_class]


def get_enum_names(enum_class):
    """获取枚举类的所有名称"""
    return [item.name for item in enum_class]


def find_enum_by_value(enum_class, value):
    """根据值查找枚举项"""
    for item in enum_class:
        if item.value == value:
            return item
    return None


class UIStrings(Enum):
    """UI界面字符串常量"""
    # 窗口标题
    WINDOW_TITLE = "PktMask"
    
    # 按钮文本
    BUTTON_START = "Start"
    BUTTON_STOP = "Stop"
    BUTTON_CLOSE = "Close"
    
    # 菜单项
    MENU_FILE = "File"
    MENU_HELP = "Help"
    MENU_EXIT = "Exit"
    MENU_ABOUT = "About"
    
    # 标签文本
    LABEL_INPUT = "Input:"
    LABEL_OUTPUT = "Output:"
    LABEL_FILES_PROCESSED = "Files Processed"
    LABEL_PACKETS_PROCESSED = "Packets Processed"
    LABEL_TIME_ELAPSED = "Time Elapsed"
    
    # 组框标题
    GROUP_DIRECTORIES = "Set Working Directories"
    GROUP_OPTIONS = "Set Actions"
    GROUP_PROCESSING = "Run Processing"
    GROUP_DASHBOARD = "Live Dashboard"
    GROUP_LOG = "Log"
    GROUP_SUMMARY = "Summary Report"
    
    # 复选框文本（使用标准GUI命名）
    CHECKBOX_REMOVE_DUPES = "Remove Dupes"
    CHECKBOX_ANONYMIZE_IPS = "Anonymize IPs"
    CHECKBOX_MASK_PAYLOADS = "Mask Payloads"
    CHECKBOX_WEB_FOCUSED = "Web-Focused Traffic Only (功能已移除)"
    
    # 路径标签默认文本
    PATH_INPUT_DEFAULT = "Click and pick your pcap directory"
    PATH_OUTPUT_DEFAULT = "Auto-create or click for custom"
    
    # 时间格式
    TIME_INITIAL = "00:00.00"
    
    # 处理步骤名称（统一使用GUI标准命名）
    STEP_REMOVE_DUPES = "Remove Dupes"
    STEP_ANONYMIZE_IPS = "Anonymize IPs"
    STEP_MASK_PAYLOADS = "Mask Payloads"
    
    # 消息框标题
    MSG_WARNING = "Warning"
    MSG_ERROR = "Error"
    
    # 工具提示信息（使用标准GUI命名）
    TOOLTIP_REMOVE_DUPES = "Remove duplicate packets based on content hash to reduce file size."
    TOOLTIP_ANONYMIZE_IPS = "Replace IP addresses with anonymized versions while preserving network structure."
    TOOLTIP_MASK_PAYLOADS = "Intelligently trims packet payloads while preserving TLS handshake data."
    TOOLTIP_WEB_FOCUSED = "HTTP协议处理功能已从本版本中移除。仅支持TLS、IP匿名化和去重功能。"

