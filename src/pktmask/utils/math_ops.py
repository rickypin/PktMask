#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
数值计算工具模块
提供统一的数学计算和统计功能
"""

from typing import Union, Optional, Dict, Any
from ..common.constants import ProcessingConstants, FormatConstants


def calculate_percentage(part: Union[int, float], total: Union[int, float], 
                        decimal_places: int = FormatConstants.PERCENTAGE_DECIMAL_PLACES) -> float:
    """
    计算百分比
    
    Args:
        part: 部分数值
        total: 总数值
        decimal_places: 小数位数
    
    Returns:
        百分比值
    """
    if total == 0:
        return 0.0
    
    percentage = (part / total) * ProcessingConstants.PERCENTAGE_MULTIPLIER
    return round(percentage, decimal_places)


def calculate_rate(processed: Union[int, float], total: Union[int, float],
                  decimal_places: int = FormatConstants.RATE_DECIMAL_PLACES) -> float:
    """
    计算处理率（百分比的别名，更语义化）
    
    Args:
        processed: 已处理数量
        total: 总数量
        decimal_places: 小数位数
    
    Returns:
        处理率
    """
    return calculate_percentage(processed, total, decimal_places)


def calculate_speed(items: Union[int, float], duration_seconds: float,
                   decimal_places: int = 1) -> float:
    """
    计算处理速度（items/second）
    
    Args:
        items: 处理项目数量
        duration_seconds: 持续时间（秒）
        decimal_places: 小数位数
    
    Returns:
        处理速度（items/second）
    """
    if duration_seconds <= 0:
        return 0.0
    
    speed = items / duration_seconds
    return round(speed, decimal_places)


def safe_divide(numerator: Union[int, float], denominator: Union[int, float],
               default: Union[int, float] = 0) -> float:
    """
    安全除法，避免除零错误
    
    Args:
        numerator: 分子
        denominator: 分母
        default: 除零时的默认值
    
    Returns:
        除法结果
    """
    if denominator == 0:
        return float(default)
    return numerator / denominator


def format_number(number: Union[int, float], decimal_places: int = 0, 
                 thousands_separator: bool = True) -> str:
    """
    格式化数字显示
    
    Args:
        number: 要格式化的数字
        decimal_places: 小数位数
        thousands_separator: 是否使用千位分隔符
    
    Returns:
        格式化的数字字符串
    """
    if decimal_places == 0:
        number = int(number)
        return f"{number:,}" if thousands_separator else str(number)
    else:
        format_str = f"{{:.{decimal_places}f}}"
        formatted = format_str.format(number)
        if thousands_separator:
            # 处理带小数点的千位分隔符
            parts = formatted.split('.')
            parts[0] = f"{int(parts[0]):,}"
            return '.'.join(parts)
        return formatted


def format_size_bytes(size_bytes: int, decimal_places: int = 2) -> str:
    """
    格式化字节大小为可读格式
    
    Args:
        size_bytes: 字节大小
        decimal_places: 小数位数
    
    Returns:
        格式化的大小字符串，如 "1.23 MB"
    """
    if size_bytes == 0:
        return "0 B"
    
    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
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
    计算基本统计信息
    
    Args:
        values: 数值列表
    
    Returns:
        包含统计信息的字典
    """
    if not values:
        return {
            'count': 0,
            'sum': 0,
            'mean': 0,
            'min': 0,
            'max': 0,
            'median': 0
        }
    
    values = [v for v in values if v is not None]  # 过滤None值
    
    if not values:
        return {
            'count': 0,
            'sum': 0,
            'mean': 0,
            'min': 0,
            'max': 0,
            'median': 0
        }
    
    count = len(values)
    total = sum(values)
    mean = total / count
    sorted_values = sorted(values)
    
    # 计算中位数
    if count % 2 == 0:
        median = (sorted_values[count // 2 - 1] + sorted_values[count // 2]) / 2
    else:
        median = sorted_values[count // 2]
    
    return {
        'count': count,
        'sum': total,
        'mean': mean,
        'min': min(values),
        'max': max(values),
        'median': median
    }


def format_processing_summary(original_count: int, processed_count: int, 
                            step_name: str, unit_name: str = "items") -> str:
    """
    格式化处理摘要信息
    
    Args:
        original_count: 原始数量
        processed_count: 处理数量
        step_name: 处理步骤名称
        unit_name: 单位名称
    
    Returns:
        格式化的摘要字符串
    """
    rate = calculate_percentage(processed_count, original_count)
    return (f"{step_name}: {format_number(processed_count)} / "
            f"{format_number(original_count)} {unit_name} ({rate:.1f}%)")


def clamp(value: Union[int, float], min_value: Union[int, float], 
         max_value: Union[int, float]) -> Union[int, float]:
    """
    将数值限制在指定范围内
    
    Args:
        value: 要限制的值
        min_value: 最小值
        max_value: 最大值
    
    Returns:
        限制后的值
    """
    return max(min_value, min(value, max_value))


def normalize_value(value: Union[int, float], min_value: Union[int, float], 
                   max_value: Union[int, float]) -> float:
    """
    将数值标准化到0-1范围
    
    Args:
        value: 要标准化的值
        min_value: 最小值
        max_value: 最大值
    
    Returns:
        标准化后的值（0-1）
    """
    if max_value == min_value:
        return 0.0
    
    return (value - min_value) / (max_value - min_value)


def moving_average(values: list, window_size: int) -> list:
    """
    计算移动平均值
    
    Args:
        values: 数值列表
        window_size: 窗口大小
    
    Returns:
        移动平均值列表
    """
    if window_size <= 0 or window_size > len(values):
        return values.copy()
    
    averages = []
    for i in range(len(values) - window_size + 1):
        window_values = values[i:i + window_size]
        avg = sum(window_values) / window_size
        averages.append(avg)
    
    return averages


def calculate_growth_rate(old_value: Union[int, float], new_value: Union[int, float],
                         decimal_places: int = 2) -> float:
    """
    计算增长率
    
    Args:
        old_value: 旧值
        new_value: 新值
        decimal_places: 小数位数
    
    Returns:
        增长率（百分比）
    """
    if old_value == 0:
        return float('inf') if new_value > 0 else 0.0
    
    growth_rate = ((new_value - old_value) / old_value) * 100
    return round(growth_rate, decimal_places) 