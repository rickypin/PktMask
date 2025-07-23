#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Numerical calculation utility module
Provides unified mathematical calculation and statistical functionality
"""

from typing import Any, Dict, Optional, Union

from ..common.constants import FormatConstants, ProcessingConstants


def calculate_percentage(
    part: Union[int, float],
    total: Union[int, float],
    decimal_places: int = FormatConstants.PERCENTAGE_DECIMAL_PLACES,
) -> float:
    """
    Calculate percentage

    Args:
        part: Partial value
        total: Total value
        decimal_places: Decimal places

    Returns:
        Percentage value
    """
    if total == 0:
        return 0.0

    percentage = (part / total) * ProcessingConstants.PERCENTAGE_MULTIPLIER
    return round(percentage, decimal_places)


def calculate_rate(
    processed: Union[int, float],
    total: Union[int, float],
    decimal_places: int = FormatConstants.RATE_DECIMAL_PLACES,
) -> float:
    """
    Calculate processing rate (semantic alias for percentage)

    Args:
        processed: Processed count
        total: Total count
        decimal_places: Decimal places

    Returns:
        Processing rate
    """
    return calculate_percentage(processed, total, decimal_places)


def calculate_speed(
    items: Union[int, float], duration_seconds: float, decimal_places: int = 1
) -> float:
    """
    Calculate processing speed (items/second)

    Args:
        items: Number of processed items
        duration_seconds: Duration (seconds)
        decimal_places: Decimal places

    Returns:
        Processing speed (items/second)
    """
    if duration_seconds <= 0:
        return 0.0

    speed = items / duration_seconds
    return round(speed, decimal_places)


def safe_divide(
    numerator: Union[int, float],
    denominator: Union[int, float],
    default: Union[int, float] = 0,
) -> float:
    """
    Safe division to avoid division by zero errors

    Args:
        numerator: Numerator
        denominator: Denominator
        default: Default value when dividing by zero

    Returns:
        Division result
    """
    if denominator == 0:
        return float(default)
    return numerator / denominator


def format_number(
    number: Union[int, float], decimal_places: int = 0, thousands_separator: bool = True
) -> str:
    """
    Format number display

    Args:
        number: Number to format
        decimal_places: Decimal places
        thousands_separator: Whether to use thousands separator

    Returns:
        Formatted number string
    """
    if decimal_places == 0:
        number = int(number)
        return f"{number:,}" if thousands_separator else str(number)
    else:
        format_str = f"{{:.{decimal_places}f}}"
        formatted = format_str.format(number)
        if thousands_separator:
            # Handle thousands separator with decimal points
            parts = formatted.split(".")
            parts[0] = f"{int(parts[0]):,}"
            return ".".join(parts)
        return formatted


def format_size_bytes(size_bytes: int, decimal_places: int = 2) -> str:
    """
    Format byte size to readable format

    Args:
        size_bytes: Byte size
        decimal_places: Decimal places

    Returns:
        Formatted size string, e.g., "1.23 MB"
    """
    if size_bytes == 0:
        return "0 B"

    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    unit_index = 0
    size = float(size_bytes)

    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1

    if unit_index == 0:  # Bytes
        return f"{int(size)} {units[unit_index]}"
    else:
        return f"{size:.{decimal_places}f} {units[unit_index]}"


def calculate_statistics(values: list) -> Dict[str, Any]:
    """
    Calculate basic statistical information

    Args:
        values: List of values

    Returns:
        Dictionary containing statistical information
    """
    if not values:
        return {"count": 0, "sum": 0, "mean": 0, "min": 0, "max": 0, "median": 0}

    values = [v for v in values if v is not None]  # Filter None values

    if not values:
        return {"count": 0, "sum": 0, "mean": 0, "min": 0, "max": 0, "median": 0}

    count = len(values)
    total = sum(values)
    mean = total / count
    sorted_values = sorted(values)

    # Calculate median
    if count % 2 == 0:
        median = (sorted_values[count // 2 - 1] + sorted_values[count // 2]) / 2
    else:
        median = sorted_values[count // 2]

    return {
        "count": count,
        "sum": total,
        "mean": mean,
        "min": min(values),
        "max": max(values),
        "median": median,
    }


def format_processing_summary(
    original_count: int, processed_count: int, step_name: str, unit_name: str = "items"
) -> str:
    """
    Format processing summary information

    Args:
        original_count: Original count
        processed_count: Processed count
        step_name: Processing step name
        unit_name: Unit name

    Returns:
        Formatted summary string
    """
    rate = calculate_percentage(processed_count, original_count)
    return (
        f"{step_name}: {format_number(processed_count)} / "
        f"{format_number(original_count)} {unit_name} ({rate:.1f}%)"
    )


def clamp(
    value: Union[int, float], min_value: Union[int, float], max_value: Union[int, float]
) -> Union[int, float]:
    """
    Clamp value within specified range

    Args:
        value: Value to clamp
        min_value: Minimum value
        max_value: Maximum value

    Returns:
        Clamped value
    """
    return max(min_value, min(value, max_value))


def normalize_value(
    value: Union[int, float], min_value: Union[int, float], max_value: Union[int, float]
) -> float:
    """
    Normalize value to 0-1 range

    Args:
        value: Value to normalize
        min_value: Minimum value
        max_value: Maximum value

    Returns:
        Normalized value (0-1)
    """
    if max_value == min_value:
        return 0.0

    return (value - min_value) / (max_value - min_value)


def moving_average(values: list, window_size: int) -> list:
    """
    Calculate moving average

    Args:
        values: List of values
        window_size: Window size

    Returns:
        List of moving averages
    """
    if window_size <= 0 or window_size > len(values):
        return values.copy()

    averages = []
    for i in range(len(values) - window_size + 1):
        window_values = values[i : i + window_size]
        avg = sum(window_values) / window_size
        averages.append(avg)

    return averages


def calculate_growth_rate(
    old_value: Union[int, float], new_value: Union[int, float], decimal_places: int = 2
) -> float:
    """
    Calculate growth rate

    Args:
        old_value: Old value
        new_value: New value
        decimal_places: Decimal places

    Returns:
        Growth rate (percentage)
    """
    if old_value == 0:
        return float("inf") if new_value > 0 else 0.0

    growth_rate = ((new_value - old_value) / old_value) * 100
    return round(growth_rate, decimal_places)
