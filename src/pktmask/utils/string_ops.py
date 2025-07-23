#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
String formatting utility module
Provides unified string processing and formatting functionality
"""

from typing import Any, Dict, List, Optional

from ..common.constants import FormatConstants


def create_separator(
    length: int = FormatConstants.SEPARATOR_LENGTH,
    char: str = FormatConstants.STEP_SEPARATOR,
) -> str:
    """
    Create a separator string

    Args:
        length: Separator length
        char: Separator character

    Returns:
        Separator string
    """
    return char * length


def format_ip_mapping(
    original_ip: str, masked_ip: str, ip_width: int = FormatConstants.IP_DISPLAY_WIDTH
) -> str:
    """
    Format IP mapping display

    Args:
        original_ip: Original IP address
        masked_ip: Anonymized IP address
        ip_width: IP address display width

    Returns:
        Formatted IP mapping string
    """
    formatted_original = f"{original_ip:<{ip_width}}"
    return f"{formatted_original}{FormatConstants.IP_MAPPING_SEPARATOR}{masked_ip}"


def format_step_summary(
    step_name: str,
    original_count: int,
    processed_count: int,
    rate: float,
    emoji: str = "🔧",
) -> str:
    """
    Format processing step summary

    Args:
        step_name: Step name
        original_count: Original count
        processed_count: Processed count
        rate: Processing rate
        emoji: Step icon

    Returns:
        Formatted step summary string
    """
    step_display = f"{step_name:<{FormatConstants.STEP_NAME_WIDTH}}"
    original_display = f"{original_count:{FormatConstants.RIGHT_ALIGN}{FormatConstants.NUMBER_DISPLAY_WIDTH_MEDIUM}}"
    processed_display = f"{processed_count:{FormatConstants.RIGHT_ALIGN}{FormatConstants.NUMBER_DISPLAY_WIDTH_MEDIUM}}"
    rate_display = f"{rate:5.{FormatConstants.RATE_DECIMAL_PLACES}f}%"

    return f"  {emoji} {step_display} | Original: {original_display} | Processed: {processed_display} | Rate: {rate_display}"


def format_deduplication_summary(
    step_name: str, unique_count: int, removed_count: int, rate: float
) -> str:
    """
    Format deduplication step summary

    Args:
        step_name: Step name
        unique_count: Unique packet count
        removed_count: Removed packet count
        rate: Deduplication rate

    Returns:
        Formatted deduplication summary string
    """
    step_display = f"{step_name:<{FormatConstants.STEP_NAME_WIDTH}}"
    unique_display = f"{unique_count:{FormatConstants.RIGHT_ALIGN}{FormatConstants.NUMBER_DISPLAY_WIDTH_MEDIUM}}"
    removed_display = f"{removed_count:{FormatConstants.RIGHT_ALIGN}{FormatConstants.NUMBER_DISPLAY_WIDTH_MEDIUM}}"
    rate_display = f"{rate:5.{FormatConstants.RATE_DECIMAL_PLACES}f}%"

    return f"  🔄 {step_display} | Unique Pkts: {unique_display} | Removed Pkts: {removed_display} | Rate: {rate_display}"


def format_trimming_summary(
    step_name: str, full_packets: int, trimmed_packets: int, rate: float
) -> str:
    """
    Format trimming step summary

    Args:
        step_name: Step name
        full_packets: Full packet count
        trimmed_packets: Trimmed packet count
        rate: Trimming rate

    Returns:
        Formatted trimming summary string
    """
    step_display = f"{step_name:<{FormatConstants.STEP_NAME_WIDTH}}"
    full_display = f"{full_packets:{FormatConstants.RIGHT_ALIGN}{FormatConstants.NUMBER_DISPLAY_WIDTH_LARGE}}"
    trimmed_display = f"{trimmed_packets:{FormatConstants.RIGHT_ALIGN}{FormatConstants.NUMBER_DISPLAY_WIDTH_MEDIUM}}"
    rate_display = f"{rate:5.{FormatConstants.RATE_DECIMAL_PLACES}f}%"

    return f"  ✂️  {step_display} | Full Pkts: {full_display} | Trimmed Pkts: {trimmed_display} | Rate: {rate_display}"


def format_ip_mapping_list(
    ip_mappings: Dict[str, str],
    max_display: Optional[int] = None,
    show_numbers: bool = True,
) -> str:
    """
    Format IP mapping list

    Args:
        ip_mappings: IP mapping dictionary
        max_display: Maximum display count, None means show all
        show_numbers: Whether to show sequence numbers

    Returns:
        Formatted IP mapping list string
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


def format_section_header(
    title: str,
    emoji: str = "📋",
    separator_length: int = FormatConstants.SEPARATOR_LENGTH,
) -> str:
    """
    Format section header

    Args:
        title: Title text
        emoji: Title icon
        separator_length: Separator length

    Returns:
        Formatted section header string
    """
    separator = create_separator(separator_length)
    return f"\n{separator}\n{emoji} {title}\n{separator}\n"


def format_summary_section(title: str, items: List[str], emoji: str = "📈") -> str:
    """
    Format summary section

    Args:
        title: Section title
        items: Summary item list
        emoji: Section icon

    Returns:
        Formatted summary section string
    """
    lines = [format_section_header(title, emoji)]

    for item in items:
        if item.strip():  # Only add non-empty items
            lines.append(f"   • {item}")

    lines.append("")  # Add empty line
    return "\n".join(lines)


def format_file_status(
    filename: str, status: str, details: Optional[List[str]] = None
) -> str:
    """
    Format file status display

    Args:
        filename: File name
        status: Status (e.g., "✅", "🔄", "❌")
        details: Detailed information list

    Returns:
        Formatted file status string
    """
    lines = [f"\n{status} {filename}"]

    if details:
        for detail in details:
            if detail.strip():
                lines.append(f"   {detail}")

    return "\n".join(lines)


def truncate_string(text: str, max_length: int, ellipsis: str = "...") -> str:
    """
    Truncate string and add ellipsis

    Args:
        text: Original string
        max_length: Maximum length
        ellipsis: Ellipsis string

    Returns:
        Truncated string
    """
    if len(text) <= max_length:
        return text

    if max_length <= len(ellipsis):
        return ellipsis[:max_length]

    return text[: max_length - len(ellipsis)] + ellipsis


def pad_string(
    text: str, width: int, align: str = FormatConstants.LEFT_ALIGN, fill_char: str = " "
) -> str:
    """
    Pad string to specified width

    Args:
        text: Original string
        width: Target width
        align: Alignment method ('<', '>', '^')
        fill_char: Fill character

    Returns:
        Padded string
    """
    if align == FormatConstants.RIGHT_ALIGN:
        return text.rjust(width, fill_char)
    elif align == FormatConstants.CENTER_ALIGN:
        return text.center(width, fill_char)
    else:  # Default left alignment
        return text.ljust(width, fill_char)


def join_with_separator(
    items: List[str], separator: str = ", ", empty_text: str = "None"
) -> str:
    """
    Join string list with separator

    Args:
        items: String list
        separator: Separator
        empty_text: Display text for empty list

    Returns:
        Joined string
    """
    if not items:
        return empty_text

    # Filter empty strings
    filtered_items = [item for item in items if item.strip()]

    if not filtered_items:
        return empty_text

    return separator.join(filtered_items)


def format_key_value_pairs(
    data: Dict[str, Any], separator: str = ": ", line_prefix: str = "   "
) -> str:
    """
    Format key-value pair data

    Args:
        data: Key-value pair dictionary
        separator: Key-value separator
        line_prefix: Line prefix

    Returns:
        Formatted key-value pair string
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
    Clean illegal characters from filename

    Args:
        filename: Original filename
        replacement_char: Replacement character

    Returns:
        Cleaned filename
    """
    # Define illegal characters
    illegal_chars = ["<", ">", ":", '"', "|", "?", "*", "/", "\\"]

    cleaned = filename
    for char in illegal_chars:
        cleaned = cleaned.replace(char, replacement_char)

    # Remove multiple consecutive replacement characters
    while replacement_char + replacement_char in cleaned:
        cleaned = cleaned.replace(replacement_char + replacement_char, replacement_char)

    # Remove replacement characters from beginning and end
    cleaned = cleaned.strip(replacement_char)

    return cleaned or "unnamed"


def format_progress_text(current: int, total: int, item_name: str = "items") -> str:
    """
    Format progress text

    Args:
        current: Current progress
        total: Total count
        item_name: Item name

    Returns:
        Formatted progress text
    """
    if total == 0:
        return f"0 {item_name}"

    percentage = (current / total) * 100
    return f"{current:,} / {total:,} {item_name} ({percentage:.1f}%)"
