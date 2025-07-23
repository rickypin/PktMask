#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PktMask Enumeration Definitions
Unified management of all enumeration types in the application
"""

from enum import Enum, IntEnum, auto


class ProcessingStepType(Enum):
    """Processing stage type enumeration (based on unified StageBase architecture)"""

    ANONYMIZE_IPS = "anonymize_ips"  # UnifiedIPAnonymizationStage
    REMOVE_DUPES = "remove_dupes"  # UnifiedDeduplicationStage
    MASK_PAYLOADS = "mask_payloads"  # NewMaskPayloadStage (dual module)
    WEB_FOCUSED = "web_focused"  # HTTP functionality removed, kept for backward compatibility

    # Legacy enum values - maintain backward compatibility
    MASK_IP = "mask_ip"  # Deprecated, use ANONYMIZE_IPS
    DEDUP_PACKET = "dedup_packet"  # Deprecated, use REMOVE_DUPES
    TRIM_PACKET = "trim_packet"  # Deprecated, use MASK_PAYLOADS


class PipelineStatus(Enum):
    """Pipeline processing status enumeration"""

    IDLE = "idle"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"
    COMPLETED = "completed"


class LogLevel(IntEnum):
    """Log level enumeration"""

    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


class FileType(Enum):
    """File type enumeration"""

    PCAP = ".pcap"
    PCAPNG = ".pcapng"
    UNKNOWN = "unknown"


class IPVersion(IntEnum):
    """IP version enumeration"""

    IPV4 = 4
    IPV6 = 6


class NetworkProtocol(IntEnum):
    """Network protocol enumeration"""

    TCP = 6
    UDP = 17
    ICMP = 1
    ICMPv6 = 58


class ThemeType(Enum):
    """Theme type enumeration"""

    AUTO = "auto"
    LIGHT = "light"
    DARK = "dark"


class LanguageType(Enum):
    """Language type enumeration"""

    CHINESE = "zh_CN"
    ENGLISH = "en_US"


class ValidationResult(Enum):
    """Validation result enumeration"""

    VALID = "valid"
    INVALID_FORMAT = "invalid_format"
    FILE_NOT_FOUND = "file_not_found"
    PERMISSION_DENIED = "permission_denied"
    FILE_TOO_LARGE = "file_too_large"
    FILE_TOO_SMALL = "file_too_small"


class ProcessingResult(Enum):
    """Processing result enumeration"""

    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    PARTIAL = "partial"


class AnonymizationStrategy(Enum):
    """Anonymization strategy enumeration"""

    HIERARCHICAL = "hierarchical"
    RANDOM = "random"
    CRYPTOGRAPHIC = "cryptographic"


class ReportFormat(Enum):
    """Report format enumeration"""

    JSON = "json"
    HTML = "html"
    CSV = "csv"
    XML = "xml"


class ConfigFormat(Enum):
    """Configuration file format enumeration"""

    YAML = "yaml"
    JSON = "json"
    TOML = "toml"


class ErrorSeverity(IntEnum):
    """Error severity level enumeration"""

    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class UIEvent(Enum):
    """UI event type enumeration"""

    DIRECTORY_SELECTED = auto()
    PROCESSING_STARTED = auto()
    PROCESSING_STOPPED = auto()
    PROCESSING_COMPLETED = auto()
    CONFIGURATION_CHANGED = auto()
    THEME_CHANGED = auto()
    LANGUAGE_CHANGED = auto()


class ProcessingEvent(Enum):
    """Processing event type enumeration"""

    FILE_STARTED = auto()
    FILE_COMPLETED = auto()
    STEP_STARTED = auto()
    STEP_COMPLETED = auto()
    PROGRESS_UPDATED = auto()
    ERROR_OCCURRED = auto()


# Convenience functions
def get_enum_values(enum_class):
    """Get all values of enumeration class"""
    return [item.value for item in enum_class]


def get_enum_names(enum_class):
    """Get all names of enumeration class"""
    return [item.name for item in enum_class]


def find_enum_by_value(enum_class, value):
    """Find enumeration item by value"""
    for item in enum_class:
        if item.value == value:
            return item
    return None


class UIStrings(Enum):
    """UI interface string constants"""

    # Window title
    WINDOW_TITLE = "PktMask"

    # Button text
    BUTTON_START = "Start"
    BUTTON_STOP = "Stop"
    BUTTON_CLOSE = "Close"

    # Menu items
    MENU_FILE = "File"
    MENU_HELP = "Help"
    MENU_EXIT = "Exit"
    MENU_ABOUT = "About"

    # Label text
    LABEL_INPUT = "Input:"
    LABEL_OUTPUT = "Output:"
    LABEL_FILES_PROCESSED = "Files Processed"
    LABEL_PACKETS_PROCESSED = "Packets Processed"
    LABEL_TIME_ELAPSED = "Time Elapsed"

    # Group box titles
    GROUP_DIRECTORIES = "Set Working Directories"
    GROUP_OPTIONS = "Set Actions"
    GROUP_PROCESSING = "Run Processing"
    GROUP_DASHBOARD = "Live Dashboard"
    GROUP_LOG = "Log"
    GROUP_SUMMARY = "Summary Report"

    # Checkbox text (using standard GUI naming)
    CHECKBOX_REMOVE_DUPES = "Remove Dupes"
    CHECKBOX_ANONYMIZE_IPS = "Anonymize IPs"
    CHECKBOX_MASK_PAYLOADS = "Mask Payloads"
    CHECKBOX_WEB_FOCUSED = "Web-Focused Traffic Only (feature removed)"

    # Path label default text
    PATH_INPUT_DEFAULT = "Click and pick your pcap directory"
    PATH_OUTPUT_DEFAULT = "Auto-create or click for custom"

    # Time format
    TIME_INITIAL = "00:00.00"

    # Processing step names (unified using GUI standard naming)
    STEP_REMOVE_DUPES = "Remove Dupes"
    STEP_ANONYMIZE_IPS = "Anonymize IPs"
    STEP_MASK_PAYLOADS = "Mask Payloads"

    # Message box titles
    MSG_WARNING = "Warning"
    MSG_ERROR = "Error"

    # Tooltip information (using standard GUI naming)
    TOOLTIP_REMOVE_DUPES = (
        "Remove duplicate packets based on content hash to reduce file size."
    )
    TOOLTIP_ANONYMIZE_IPS = "Replace IP addresses with anonymized versions while preserving network structure."
    TOOLTIP_MASK_PAYLOADS = (
        "Intelligently trims packet payloads while preserving TLS handshake data."
    )
    TOOLTIP_WEB_FOCUSED = (
        "HTTP protocol processing functionality has been removed from this version. Only supports TLS, IP anonymization and deduplication features."
    )
