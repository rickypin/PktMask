#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
GUI Core Module - GUI Protection Layer

This module provides the GUI protection layer that ensures 100% compatibility
with existing GUI functionality while using the new ConsistentProcessor core.

Key Components:
- gui_consistent_processor.py: GUI-compatible wrapper for ConsistentProcessor
- feature_flags.py: Feature flags for safe rollout
"""

from .gui_consistent_processor import (
    GUIConsistentProcessor,
    GUIServicePipelineThread,
    GUIThreadingHelper
)

from .feature_flags import GUIFeatureFlags

__all__ = [
    "GUIConsistentProcessor",
    "GUIServicePipelineThread", 
    "GUIThreadingHelper",
    "GUIFeatureFlags"
]
