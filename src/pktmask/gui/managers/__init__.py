#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
GUI Manager Module
Provides manager classes for various MainWindow responsibilities
"""

from .dialog_manager import DialogManager
from .dialogs import DialogsManager
from .display_manager import DisplayManager
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
    "DialogsManager",  # New unified dialogs manager
    "DisplayManager",  # New display manager
    "EventCoordinator",
]
