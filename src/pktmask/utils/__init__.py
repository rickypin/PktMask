#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
工具函数模块
统一导出所有工具函数，提供便捷的导入接口
"""

# 文件操作工具
from .file_ops import (
    cleanup_temp_files,
    copy_file_safely,
    delete_file_safely,
    ensure_directory,
    find_files_by_extension,
    find_pcap_files,
    generate_output_filename,
    get_directory_size,
    get_file_base_name,
    get_file_extension,
    get_file_size,
    is_supported_file,
    open_directory_in_system,
    safe_join,
    validate_file_size,
)

# 文件选择工具
from .file_selector import select_files

# 数值计算工具
from .math_ops import (
    calculate_growth_rate,
    calculate_percentage,
    calculate_rate,
    calculate_speed,
    calculate_statistics,
    clamp,
    format_number,
    format_processing_summary,
    format_size_bytes,
    moving_average,
    normalize_value,
    safe_divide,
)

# 路径处理工具
from .path import resource_path

# 报告生成工具
from .reporting import FileReporter, Reporter

# 字符串格式化工具
from .string_ops import (
    clean_filename,
    create_separator,
    format_deduplication_summary,
    format_file_status,
    format_ip_mapping,
    format_ip_mapping_list,
    format_key_value_pairs,
    format_progress_text,
    format_section_header,
    format_step_summary,
    format_summary_section,
    format_trimming_summary,
    join_with_separator,
    pad_string,
    truncate_string,
)

# 时间处理工具
from .time import (
    current_time,
    current_timestamp,
    format_duration,
    format_duration_seconds,
    format_milliseconds_to_time,
    get_performance_metrics,
)

__all__ = [
    # 时间处理
    "current_time",
    "current_timestamp",
    "format_duration",
    "format_duration_seconds",
    "format_milliseconds_to_time",
    "get_performance_metrics",
    # 文件操作
    "ensure_directory",
    "safe_join",
    "get_file_extension",
    "get_file_base_name",
    "get_file_size",
    "validate_file_size",
    "is_supported_file",
    "find_files_by_extension",
    "find_pcap_files",
    "copy_file_safely",
    "delete_file_safely",
    "open_directory_in_system",
    "generate_output_filename",
    "get_directory_size",
    "cleanup_temp_files",
    # 数值计算
    "calculate_percentage",
    "calculate_rate",
    "calculate_speed",
    "safe_divide",
    "format_number",
    "format_size_bytes",
    "calculate_statistics",
    "format_processing_summary",
    "clamp",
    "normalize_value",
    "moving_average",
    "calculate_growth_rate",
    # 字符串格式化
    "create_separator",
    "format_ip_mapping",
    "format_step_summary",
    "format_deduplication_summary",
    "format_trimming_summary",
    "format_ip_mapping_list",
    "format_section_header",
    "format_summary_section",
    "format_file_status",
    "truncate_string",
    "pad_string",
    "join_with_separator",
    "format_key_value_pairs",
    "clean_filename",
    "format_progress_text",
    # 其他工具
    "resource_path",
    "select_files",
    "Reporter",
    "FileReporter",
]
