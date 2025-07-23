#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
GUI管理器模块
提供MainWindow各个职责的管理器类
"""

from .dialog_manager import DialogManager
from .event_coordinator import EventCoordinator
from .file_manager import FileManager
from .pipeline_manager import PipelineManager
from .report_manager import ReportManager
from .ui_manager import UIManager

__all__ = [
    "UIManager",
    "FileManager",
    "PipelineManager",
    "ReportManager",
    "DialogManager",
    "EventCoordinator",
]
