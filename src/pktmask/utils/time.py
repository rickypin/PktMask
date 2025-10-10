#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
时间处理工具模块
提供统一的时间格式化和计算功能
"""

import time
from datetime import datetime
from typing import Optional

from ..common.constants import SystemConstants


def current_time(format_string: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    获取当前时间字符串

    Args:
        format_string: 时间格式字符串，默认为 "%Y-%m-%d %H:%M:%S"

    Returns:
        格式化的时间字符串
    """
    return datetime.now().strftime(format_string)


def current_timestamp() -> str:
    """
    获取当前时间戳字符串（用于文件命名）

    Returns:
        格式为 "YYYYMMDD_HHMMSS" 的时间戳字符串
    """
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def format_duration(start_time: float, end_time: Optional[float] = None) -> str:
    """
    格式化时间持续时长

    Args:
        start_time: 开始时间（time.time()格式）
        end_time: 结束时间，如果为None则使用当前时间

    Returns:
        格式化的持续时长字符串，如 "1h 23m 45s"
    """
    if end_time is None:
        end_time = time.time()

    duration = end_time - start_time
    return format_duration_seconds(duration)


def format_duration_seconds(duration_seconds: float) -> str:
    """
    将秒数格式化为可读的时长字符串

    Args:
        duration_seconds: 持续时长（秒）

    Returns:
        格式化的时长字符串
    """
    hours = int(duration_seconds // (SystemConstants.MINUTES_PER_HOUR * SystemConstants.SECONDS_PER_MINUTE))
    minutes = int(
        (duration_seconds % (SystemConstants.MINUTES_PER_HOUR * SystemConstants.SECONDS_PER_MINUTE))
        // SystemConstants.SECONDS_PER_MINUTE
    )
    seconds = int(duration_seconds % SystemConstants.SECONDS_PER_MINUTE)

    if hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"


def format_milliseconds_to_time(milliseconds: int) -> str:
    """
    将毫秒转换为时间显示格式 (MM:SS.ms)

    Args:
        milliseconds: 毫秒数

    Returns:
        格式化的时间字符串，如 "01:23.45"
    """
    total_seconds = milliseconds // SystemConstants.MILLISECONDS_PER_SECOND
    msecs = (milliseconds % SystemConstants.MILLISECONDS_PER_SECOND) // SystemConstants.MILLISECONDS_DISPLAY_DIVISOR

    hours, remainder = divmod(
        total_seconds,
        SystemConstants.MINUTES_PER_HOUR * SystemConstants.SECONDS_PER_MINUTE,
    )
    minutes, seconds = divmod(remainder, SystemConstants.SECONDS_PER_MINUTE)

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{msecs:02d}"
    else:
        return f"{minutes:02d}:{seconds:02d}.{msecs:02d}"


def get_performance_metrics(start_time: float, end_time: Optional[float] = None, item_count: int = 0) -> dict:
    """
    计算性能指标

    Args:
        start_time: 开始时间
        end_time: 结束时间，如果为None则使用当前时间
        item_count: 处理的项目数量

    Returns:
        包含持续时间、速度等指标的字典
    """
    if end_time is None:
        end_time = time.time()

    duration = end_time - start_time

    metrics = {
        "duration_seconds": duration,
        "duration_formatted": format_duration_seconds(duration),
        "start_time": start_time,
        "end_time": end_time,
    }

    if item_count > 0 and duration > 0:
        metrics["items_per_second"] = item_count / duration
        metrics["items_processed"] = item_count

    return metrics
