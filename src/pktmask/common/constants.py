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

    # Padding settings
    DIRS_LAYOUT_PADDING = (15, 12, 15, 12)
    PIPELINE_LAYOUT_PADDING = (15, 12, 15, 12)
    EXECUTE_LAYOUT_PADDING = (15, 20, 15, 20)
    DASHBOARD_LAYOUT_PADDING = (15, 20, 15, 12)
    LOG_LAYOUT_PADDING = (12, 20, 12, 12)
    SUMMARY_LAYOUT_PADDING = (12, 20, 12, 12)

    # Progress bar settings
    PROGRESS_BAR_HEIGHT = 25
    PROGRESS_BAR_FIXED_HEIGHT = 18
    PROGRESS_ANIMATION_DURATION = 300  # ms

    # Timer settings
    TIMER_UPDATE_INTERVAL = 50  # ms
    THREAD_WAIT_TIMEOUT = 3000  # ms

    # Display format
    TIME_FORMAT_INITIAL = "00:00.00"
    SEPARATOR_LENGTH = 70

    # Column layout weights
    LEFT_COLUMN_STRETCH = 2
    RIGHT_COLUMN_STRETCH = 3

    # Theme detection threshold
    THEME_LIGHTNESS_THRESHOLD = 128

    # Theme
    DEFAULT_THEME = "auto"  # auto, light, dark

    # Language
    DEFAULT_LANGUAGE = "en_US"


class ProcessingConstants:
    """Processing-related constants"""

    # TLS related
    TLS_SIGNALING_TYPES = {20, 21, 22}

    # Processing parameters
    DEFAULT_CHUNK_SIZE = 10
    MAX_RETRY_ATTEMPTS = 3
    DEFAULT_TIMEOUT_SECONDS = 300
    DEFAULT_MAX_WORKERS = 4

    # File processing
    SUPPORTED_EXTENSIONS = (".pcap", ".pcapng")
    TEMP_FILE_SUFFIX = ".tmp"

    # IP anonymization related
    IPV4_MIN_SEGMENT = 1
    IPV4_MAX_SEGMENT = 255
    IPV6_MIN_SEGMENT = 0
    IPV6_MAX_SEGMENT = 65535

    # IP address segment processing
    IPV4_SEGMENTS_COUNT = 4
    IPV6_SEGMENTS_COUNT = 8

    # Algorithm parameters
    HIGH_FREQUENCY_THRESHOLD = 2
    HASH_DIGEST_LENGTH = 8
    HEX_BASE = 16
    PERCENTAGE_MULTIPLIER = 100

    # IP sorting weights
    IPV4_SORT_WEIGHT = 4
    IPV6_SORT_WEIGHT = 6
    UNKNOWN_IP_SORT_WEIGHT = 99

    # Anonymization algorithm parameters
    SEGMENT_DELTA_VALUES = {1: 3, 2: 5, 3: 20, 4: 32, 5: 128, "default": 256}

    # Directory processing parameters
    IP_MAPPING_SAMPLE_COUNT = 3
    ERROR_DISPLAY_LIMIT = 5

    # Processing step suffixes
    ANONYMIZE_IPS_SUFFIX = "-Anonymized"
    MASK_PAYLOADS_SUFFIX = "-Masked"
    DEDUP_PACKET_SUFFIX = "-Deduped"


class FileConstants:
    """File and path related constants"""

    # Configuration files
    CONFIG_DIR_NAME = ".pktmask"
    DEFAULT_CONFIG_FILE = "config.yaml"
    LEGACY_CONFIG_FILE = "config.json"

    # Log files
    LOG_FILE_NAME = "pktmask.log"
    LOG_MAX_SIZE = 10 * 1024 * 1024  # 10MB
    LOG_BACKUP_COUNT = 5

    # Report files
    REPORT_FILE_PREFIX = "summary_report"
    REPORT_FILE_EXTENSION = ".json"

    # Temporary files
    TEMP_DIR_PREFIX = "pktmask_"

    # Default paths
    DEFAULT_DESKTOP_PATH = Path.home() / "Desktop"
    DEFAULT_OUTPUT_DIR_NAME = "PktMask_Output"


class NetworkConstants:
    """Network-related constants"""

    # IP versions
    IPV4_VERSION = 4
    IPV6_VERSION = 6

    # Port range
    MIN_PORT = 1
    MAX_PORT = 65535

    # Protocols
    TCP_PROTOCOL = 6
    UDP_PROTOCOL = 17


class ValidationConstants:
    """Validation-related constants"""

    # File size limits (bytes)
    MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB
    MIN_FILE_SIZE = 24  # Minimum pcap file header size

    # String length limits
    MAX_PATH_LENGTH = 260
    MAX_FILENAME_LENGTH = 255

    # Regular expressions
    IPV4_PATTERN = r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$"
    IPV6_PATTERN = r"^(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$"


class FormatConstants:
    """Formatting-related constants"""

    # Number formats
    PERCENTAGE_DECIMAL_PLACES = 1
    TIME_DECIMAL_PLACES = 2
    RATE_DECIMAL_PLACES = 1

    # String formats
    IP_DISPLAY_WIDTH = 16
    STEP_NAME_WIDTH = 18
    NUMBER_DISPLAY_WIDTH_SMALL = 3
    NUMBER_DISPLAY_WIDTH_MEDIUM = 4
    NUMBER_DISPLAY_WIDTH_LARGE = 5

    # Separators
    IP_MAPPING_SEPARATOR = " → "
    STEP_SEPARATOR = "="
    LOG_SEPARATOR = "-"
    SEPARATOR_LENGTH = 70

    # Alignment
    RIGHT_ALIGN = ">"
    LEFT_ALIGN = "<"
    CENTER_ALIGN = "^"


class SystemConstants:
    """System-related constants"""

    # Operating system detection
    MACOS_SYSTEM_NAME = "Darwin"
    WINDOWS_SYSTEM_NAME = "Windows"
    LINUX_SYSTEM_NAME = "Linux"

    # System commands
    MACOS_OPEN_COMMAND = "open"
    WINDOWS_OPEN_COMMAND = "explorer"
    LINUX_OPEN_COMMAND = "xdg-open"

    # Time calculations
    MILLISECONDS_PER_SECOND = 1000
    SECONDS_PER_MINUTE = 60
    MINUTES_PER_HOUR = 60
    MILLISECONDS_DISPLAY_DIVISOR = 10


# Display name mapping (using standard GUI naming)
PROCESS_DISPLAY_NAMES = {
    # Standard naming
    "anonymize_ips": "Anonymize IPs",
    "remove_dupes": "Remove Dupes",
    "mask_payloads": "Mask Payloads",
    # Legacy naming - maintain backward compatibility (non-standard naming removed)
}

# Error messages
ERROR_MESSAGES = {
    "file_not_found": "File not found: {path}",
    "invalid_file_format": "Unsupported file format: {format}",
    "processing_failed": "Processing failed: {reason}",
    "config_load_failed": "Configuration loading failed: {reason}",
    "permission_denied": "Permission denied: {path}",
    "disk_space_insufficient": "Insufficient disk space",
    "invalid_input": "Invalid input: {input}",
}
