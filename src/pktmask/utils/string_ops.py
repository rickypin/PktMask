#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
字符串格式化工具模块
提供统一的字符串处理和格式化功能
"""

from typing import List, Dict, Any, Optional
from ..common.constants import FormatConstants


def create_separator(length: int = FormatConstants.SEPARATOR_LENGTH, 
                    char: str = FormatConstants.STEP_SEPARATOR) -> str:
    """
    创建分隔符字符串
    
    Args:
        length: 分隔符长度
        char: 分隔符字符
    
    Returns:
        分隔符字符串
    """
    return char * length


def format_ip_mapping(original_ip: str, masked_ip: str, 
                     ip_width: int = FormatConstants.IP_DISPLAY_WIDTH) -> str:
    """
    格式化IP映射显示
    
    Args:
        original_ip: 原始IP地址
        masked_ip: 匿名化IP地址
        ip_width: IP地址显示宽度
    
    Returns:
        格式化的IP映射字符串
    """
    formatted_original = f"{original_ip:<{ip_width}}"
    return f"{formatted_original}{FormatConstants.IP_MAPPING_SEPARATOR}{masked_ip}"


def format_step_summary(step_name: str, original_count: int, processed_count: int, 
                       rate: float, emoji: str = "🔧") -> str:
    """
    格式化处理步骤摘要
    
    Args:
        step_name: 步骤名称
        original_count: 原始数量
        processed_count: 处理数量
        rate: 处理率
        emoji: 步骤图标
    
    Returns:
        格式化的步骤摘要字符串
    """
    step_display = f"{step_name:<{FormatConstants.STEP_NAME_WIDTH}}"
    original_display = f"{original_count:{FormatConstants.RIGHT_ALIGN}{FormatConstants.NUMBER_DISPLAY_WIDTH_MEDIUM}}"
    processed_display = f"{processed_count:{FormatConstants.RIGHT_ALIGN}{FormatConstants.NUMBER_DISPLAY_WIDTH_MEDIUM}}"
    rate_display = f"{rate:5.{FormatConstants.RATE_DECIMAL_PLACES}f}%"
    
    return f"  {emoji} {step_display} | Original: {original_display} | Processed: {processed_display} | Rate: {rate_display}"


def format_deduplication_summary(step_name: str, unique_count: int, removed_count: int, 
                                rate: float) -> str:
    """
    格式化去重步骤摘要
    
    Args:
        step_name: 步骤名称
        unique_count: 唯一包数量
        removed_count: 移除包数量
        rate: 去重率
    
    Returns:
        格式化的去重摘要字符串
    """
    step_display = f"{step_name:<{FormatConstants.STEP_NAME_WIDTH}}"
    unique_display = f"{unique_count:{FormatConstants.RIGHT_ALIGN}{FormatConstants.NUMBER_DISPLAY_WIDTH_MEDIUM}}"
    removed_display = f"{removed_count:{FormatConstants.RIGHT_ALIGN}{FormatConstants.NUMBER_DISPLAY_WIDTH_MEDIUM}}"
    rate_display = f"{rate:5.{FormatConstants.RATE_DECIMAL_PLACES}f}%"
    
    return f"  🔄 {step_display} | Unique Pkts: {unique_display} | Removed Pkts: {removed_display} | Rate: {rate_display}"


def format_trimming_summary(step_name: str, full_packets: int, trimmed_packets: int, 
                          rate: float) -> str:
    """
    格式化裁切步骤摘要
    
    Args:
        step_name: 步骤名称
        full_packets: 完整包数量
        trimmed_packets: 裁切包数量
        rate: 裁切率
    
    Returns:
        格式化的裁切摘要字符串
    """
    step_display = f"{step_name:<{FormatConstants.STEP_NAME_WIDTH}}"
    full_display = f"{full_packets:{FormatConstants.RIGHT_ALIGN}{FormatConstants.NUMBER_DISPLAY_WIDTH_LARGE}}"
    trimmed_display = f"{trimmed_packets:{FormatConstants.RIGHT_ALIGN}{FormatConstants.NUMBER_DISPLAY_WIDTH_MEDIUM}}"
    rate_display = f"{rate:5.{FormatConstants.RATE_DECIMAL_PLACES}f}%"
    
    return f"  ✂️  {step_display} | Full Pkts: {full_display} | Trimmed Pkts: {trimmed_display} | Rate: {rate_display}"


def format_ip_mapping_list(ip_mappings: Dict[str, str], 
                          max_display: Optional[int] = None,
                          show_numbers: bool = True) -> str:
    """
    格式化IP映射列表
    
    Args:
        ip_mappings: IP映射字典
        max_display: 最大显示数量，None表示显示全部
        show_numbers: 是否显示序号
    
    Returns:
        格式化的IP映射列表字符串
    """
    if not ip_mappings:
        return ""
    
    lines = []
    items = list(ip_mappings.items())
    
    if max_display and len(items) > max_display:
        display_items = items[:max_display]
        show_more = True
    else:
        display_items = items
        show_more = False
    
    for i, (orig_ip, masked_ip) in enumerate(display_items, 1):
        if show_numbers:
            number_part = f"   {i:2d}. "
        else:
            number_part = "   "
        
        ip_mapping = format_ip_mapping(orig_ip, masked_ip)
        lines.append(f"{number_part}{ip_mapping}")
    
    if show_more:
        remaining = len(items) - max_display
        lines.append(f"      ... and {remaining} more")
    
    return "\n".join(lines)


def format_section_header(title: str, emoji: str = "📋", 
                         separator_length: int = FormatConstants.SEPARATOR_LENGTH) -> str:
    """
    格式化章节标题
    
    Args:
        title: 标题文本
        emoji: 标题图标
        separator_length: 分隔符长度
    
    Returns:
        格式化的章节标题字符串
    """
    separator = create_separator(separator_length)
    return f"\n{separator}\n{emoji} {title}\n{separator}\n"


def format_summary_section(title: str, items: List[str], 
                          emoji: str = "📈") -> str:
    """
    格式化摘要章节
    
    Args:
        title: 章节标题
        items: 摘要项目列表
        emoji: 章节图标
    
    Returns:
        格式化的摘要章节字符串
    """
    lines = [format_section_header(title, emoji)]
    
    for item in items:
        if item.strip():  # 只添加非空项目
            lines.append(f"   • {item}")
    
    lines.append("")  # 添加空行
    return "\n".join(lines)


def format_file_status(filename: str, status: str, details: Optional[List[str]] = None) -> str:
    """
    格式化文件状态显示
    
    Args:
        filename: 文件名
        status: 状态（如 "✅", "🔄", "❌"）
        details: 详细信息列表
    
    Returns:
        格式化的文件状态字符串
    """
    lines = [f"\n{status} {filename}"]
    
    if details:
        for detail in details:
            if detail.strip():
                lines.append(f"   {detail}")
    
    return "\n".join(lines)


def truncate_string(text: str, max_length: int, ellipsis: str = "...") -> str:
    """
    截断字符串并添加省略号
    
    Args:
        text: 原始字符串
        max_length: 最大长度
        ellipsis: 省略号字符串
    
    Returns:
        截断后的字符串
    """
    if len(text) <= max_length:
        return text
    
    if max_length <= len(ellipsis):
        return ellipsis[:max_length]
    
    return text[:max_length - len(ellipsis)] + ellipsis


def pad_string(text: str, width: int, align: str = FormatConstants.LEFT_ALIGN, 
              fill_char: str = " ") -> str:
    """
    填充字符串到指定宽度
    
    Args:
        text: 原始字符串
        width: 目标宽度
        align: 对齐方式（'<', '>', '^'）
        fill_char: 填充字符
    
    Returns:
        填充后的字符串
    """
    if align == FormatConstants.RIGHT_ALIGN:
        return text.rjust(width, fill_char)
    elif align == FormatConstants.CENTER_ALIGN:
        return text.center(width, fill_char)
    else:  # 默认左对齐
        return text.ljust(width, fill_char)


def join_with_separator(items: List[str], separator: str = ", ", 
                       empty_text: str = "None") -> str:
    """
    使用分隔符连接字符串列表
    
    Args:
        items: 字符串列表
        separator: 分隔符
        empty_text: 空列表时的显示文本
    
    Returns:
        连接后的字符串
    """
    if not items:
        return empty_text
    
    # 过滤空字符串
    filtered_items = [item for item in items if item.strip()]
    
    if not filtered_items:
        return empty_text
    
    return separator.join(filtered_items)


def format_key_value_pairs(data: Dict[str, Any], separator: str = ": ", 
                          line_prefix: str = "   ") -> str:
    """
    格式化键值对数据
    
    Args:
        data: 键值对字典
        separator: 键值分隔符
        line_prefix: 行前缀
    
    Returns:
        格式化的键值对字符串
    """
    if not data:
        return ""
    
    lines = []
    for key, value in data.items():
        formatted_line = f"{line_prefix}{key}{separator}{value}"
        lines.append(formatted_line)
    
    return "\n".join(lines)


def clean_filename(filename: str, replacement_char: str = "_") -> str:
    """
    清理文件名中的非法字符
    
    Args:
        filename: 原始文件名
        replacement_char: 替换字符
    
    Returns:
        清理后的文件名
    """
    # 定义非法字符
    illegal_chars = ['<', '>', ':', '"', '|', '?', '*', '/', '\\']
    
    cleaned = filename
    for char in illegal_chars:
        cleaned = cleaned.replace(char, replacement_char)
    
    # 移除多个连续的替换字符
    while replacement_char + replacement_char in cleaned:
        cleaned = cleaned.replace(replacement_char + replacement_char, replacement_char)
    
    # 移除开头和结尾的替换字符
    cleaned = cleaned.strip(replacement_char)
    
    return cleaned or "unnamed"


def format_progress_text(current: int, total: int, item_name: str = "items") -> str:
    """
    格式化进度文本
    
    Args:
        current: 当前进度
        total: 总数
        item_name: 项目名称
    
    Returns:
        格式化的进度文本
    """
    if total == 0:
        return f"0 {item_name}"
    
    percentage = (current / total) * 100
    return f"{current:,} / {total:,} {item_name} ({percentage:.1f}%)" 