#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PktMask 常量定义
统一管理应用程序中的所有常量，避免硬编码
"""

from pathlib import Path


class UIConstants:
    """界面相关常量"""
    # 窗口尺寸
    WINDOW_MIN_WIDTH = 1200
    WINDOW_MIN_HEIGHT = 800
    DEFAULT_WINDOW_WIDTH = 1200
    DEFAULT_WINDOW_HEIGHT = 800
    
    # 对话框尺寸
    GUIDE_DIALOG_MIN_WIDTH = 700
    GUIDE_DIALOG_MIN_HEIGHT = 500
    ABOUT_DIALOG_WIDTH = 700
    ABOUT_DIALOG_HEIGHT = 500
    
    # 字体设置
    DEFAULT_FONT_SIZE = 12
    LOG_FONT_SIZE = 12
    SUMMARY_FONT_SIZE = 12
    
    # 布局间距
    LAYOUT_SPACING = 18
    LAYOUT_MARGINS = 15
    GROUP_BOX_MARGINS = 15
    GROUP_BOX_SPACING = 12
    GROUP_BOX_INNER_SPACING = 10
    
    # 组件高度
    GROUP_BOX_MAX_HEIGHT = 100
    DIRS_GROUP_HEIGHT = 100
    ROW2_WIDGET_HEIGHT = 90
    PIPELINE_GROUP_HEIGHT = 85
    EXECUTE_GROUP_HEIGHT = 85
    DASHBOARD_GROUP_HEIGHT = 140
    
    BUTTON_MAX_HEIGHT = 30
    BUTTON_MIN_HEIGHT = 35
    LABEL_MAX_HEIGHT = 20
    INPUT_LABEL_HEIGHT = 20
    
    # 内边距设置
    DIRS_LAYOUT_PADDING = (15, 12, 15, 12)
    PIPELINE_LAYOUT_PADDING = (15, 12, 15, 12)
    EXECUTE_LAYOUT_PADDING = (15, 20, 15, 20)
    DASHBOARD_LAYOUT_PADDING = (15, 20, 15, 12)
    LOG_LAYOUT_PADDING = (12, 20, 12, 12)
    SUMMARY_LAYOUT_PADDING = (12, 20, 12, 12)
    
    # 进度条设置
    PROGRESS_BAR_HEIGHT = 25
    PROGRESS_BAR_FIXED_HEIGHT = 18
    PROGRESS_ANIMATION_DURATION = 300  # ms
    
    # 定时器设置
    TIMER_UPDATE_INTERVAL = 50  # ms
    THREAD_WAIT_TIMEOUT = 3000  # ms
    
    # 显示格式
    TIME_FORMAT_INITIAL = "00:00.00"
    SEPARATOR_LENGTH = 70
    
    # 列布局权重
    LEFT_COLUMN_STRETCH = 2
    RIGHT_COLUMN_STRETCH = 3
    
    # 主题检测阈值
    THEME_LIGHTNESS_THRESHOLD = 128
    
    # 主题
    DEFAULT_THEME = "auto"  # auto, light, dark
    
    # 语言
    DEFAULT_LANGUAGE = "zh_CN"


class ProcessingConstants:
    """处理过程相关常量"""
    # TLS 相关
    TLS_SIGNALING_TYPES = {20, 21, 22}
    
    # 处理参数
    DEFAULT_CHUNK_SIZE = 10
    MAX_RETRY_ATTEMPTS = 3
    DEFAULT_TIMEOUT_SECONDS = 300
    DEFAULT_MAX_WORKERS = 4
    
    # 文件处理
    SUPPORTED_EXTENSIONS = ('.pcap', '.pcapng')
    TEMP_FILE_SUFFIX = '.tmp'
    
    # IP 匿名化相关
    IPV4_MIN_SEGMENT = 1
    IPV4_MAX_SEGMENT = 255
    IPV6_MIN_SEGMENT = 0
    IPV6_MAX_SEGMENT = 65535
    
    # IP地址段处理
    IPV4_SEGMENTS_COUNT = 4
    IPV6_SEGMENTS_COUNT = 8
    
    # 算法参数
    HIGH_FREQUENCY_THRESHOLD = 2
    HASH_DIGEST_LENGTH = 8
    HEX_BASE = 16
    PERCENTAGE_MULTIPLIER = 100
    
    # IP排序权重
    IPV4_SORT_WEIGHT = 4
    IPV6_SORT_WEIGHT = 6
    UNKNOWN_IP_SORT_WEIGHT = 99
    
    # 匿名化算法参数
    SEGMENT_DELTA_VALUES = {
        1: 3,
        2: 5,
        3: 20,
        4: 32,
        5: 128,
        'default': 256
    }
    
    # 目录处理参数
    IP_MAPPING_SAMPLE_COUNT = 3
    ERROR_DISPLAY_LIMIT = 5
    
    # 处理步骤后缀
    MASK_IP_SUFFIX = "-Masked"
    TRIM_PACKET_SUFFIX = "-Trimmed"
    DEDUP_PACKET_SUFFIX = "-Deduped"


class FileConstants:
    """文件和路径相关常量"""
    # 配置文件
    CONFIG_DIR_NAME = ".pktmask"
    DEFAULT_CONFIG_FILE = "config.yaml"
    LEGACY_CONFIG_FILE = "config.json"
    
    # 日志文件
    LOG_FILE_NAME = "pktmask.log"
    LOG_MAX_SIZE = 10 * 1024 * 1024  # 10MB
    LOG_BACKUP_COUNT = 5
    
    # 报告文件
    REPORT_FILE_PREFIX = "summary_report"
    REPORT_FILE_EXTENSION = ".json"
    
    # 临时文件
    TEMP_DIR_PREFIX = "pktmask_"
    
    # 默认路径
    DEFAULT_DESKTOP_PATH = Path.home() / "Desktop"
    DEFAULT_OUTPUT_DIR_NAME = "PktMask_Output"


class NetworkConstants:
    """网络相关常量"""
    # IP 版本
    IPV4_VERSION = 4
    IPV6_VERSION = 6
    
    # 端口范围
    MIN_PORT = 1
    MAX_PORT = 65535
    
    # 协议
    TCP_PROTOCOL = 6
    UDP_PROTOCOL = 17


class ValidationConstants:
    """验证相关常量"""
    # 文件大小限制 (bytes)
    MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB
    MIN_FILE_SIZE = 24  # 最小的pcap文件头大小
    
    # 字符串长度限制
    MAX_PATH_LENGTH = 260
    MAX_FILENAME_LENGTH = 255
    
    # 正则表达式
    IPV4_PATTERN = r'^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$'
    IPV6_PATTERN = r'^(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$'


class FormatConstants:
    """格式化相关常量"""
    # 数值格式
    PERCENTAGE_DECIMAL_PLACES = 1
    TIME_DECIMAL_PLACES = 2
    RATE_DECIMAL_PLACES = 1
    
    # 字符串格式
    IP_DISPLAY_WIDTH = 16
    STEP_NAME_WIDTH = 18
    NUMBER_DISPLAY_WIDTH_SMALL = 3
    NUMBER_DISPLAY_WIDTH_MEDIUM = 4
    NUMBER_DISPLAY_WIDTH_LARGE = 5
    
    # 分隔符
    IP_MAPPING_SEPARATOR = " → "
    STEP_SEPARATOR = "="
    LOG_SEPARATOR = "-"
    SEPARATOR_LENGTH = 70
    
    # 对齐
    RIGHT_ALIGN = ">"
    LEFT_ALIGN = "<"
    CENTER_ALIGN = "^"


class SystemConstants:
    """系统相关常量"""
    # 操作系统检测
    MACOS_SYSTEM_NAME = "Darwin"
    WINDOWS_SYSTEM_NAME = "Windows"
    LINUX_SYSTEM_NAME = "Linux"
    
    # 系统命令
    MACOS_OPEN_COMMAND = "open"
    WINDOWS_OPEN_COMMAND = "explorer"
    LINUX_OPEN_COMMAND = "xdg-open"
    
    # 时间计算
    MILLISECONDS_PER_SECOND = 1000
    SECONDS_PER_MINUTE = 60
    MINUTES_PER_HOUR = 60
    MILLISECONDS_DISPLAY_DIVISOR = 10


# 显示名称映射
PROCESS_DISPLAY_NAMES = {
    "mask_ip": "Mask IP",
    "dedup_packet": "Remove Dupes", 
    "trim_packet": "Trim Packet"
}

# 错误消息
ERROR_MESSAGES = {
    "file_not_found": "文件未找到: {path}",
    "invalid_file_format": "不支持的文件格式: {format}",
    "processing_failed": "处理失败: {reason}",
    "config_load_failed": "配置加载失败: {reason}",
    "permission_denied": "权限不足: {path}",
    "disk_space_insufficient": "磁盘空间不足",
    "invalid_input": "输入无效: {input}"
} 