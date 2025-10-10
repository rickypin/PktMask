#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
GUI Manager Module
Provides manager classes for various MainWindow responsibilities
"""

from .dialogs import DialogsManager
from .event_coordinator import EventCoordinator
from .pipeline_manager import PipelineManager

__all__ = [
    "PipelineManager",
    "DialogsManager",
    "EventCoordinator",
]
