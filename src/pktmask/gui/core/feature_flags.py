#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
GUI Feature Flags - Simplified feature flag system

This module provides feature flags for GUI debugging and development.
"""

import os
from typing import Any, Dict


class GUIFeatureFlags:
    """Simplified feature flags for GUI debugging

    This class provides centralized control for GUI debugging features.
    """

    # Environment variable names
    ENV_GUI_DEBUG_MODE = "PKTMASK_GUI_DEBUG_MODE"

    # Default values
    DEFAULT_GUI_DEBUG_MODE = False

    @staticmethod
    def is_gui_debug_mode() -> bool:
        """Check if GUI debug mode is enabled

        Returns:
            True if debug mode is enabled (shows additional logging and validation)
        """
        return GUIFeatureFlags._get_bool_env(GUIFeatureFlags.ENV_GUI_DEBUG_MODE, GUIFeatureFlags.DEFAULT_GUI_DEBUG_MODE)

    @staticmethod
    def get_feature_config() -> Dict[str, Any]:
        """Get complete feature configuration

        Returns:
            Dictionary with all feature flag values
        """
        return {
            "gui_debug_mode": GUIFeatureFlags.is_gui_debug_mode(),
            "config_source": "environment_variables",
        }

    @staticmethod
    def enable_debug_mode():
        """Enable GUI debug mode for current session"""
        os.environ[GUIFeatureFlags.ENV_GUI_DEBUG_MODE] = "true"

    @staticmethod
    def get_status_summary() -> str:
        """Get human-readable status summary

        Returns:
            String describing current feature flag status
        """
        if GUIFeatureFlags.is_gui_debug_mode():
            return "🔧 Debug Mode Enabled"
        return "✅ Normal Mode"

    @staticmethod
    def _get_bool_env(env_var: str, default: bool = False) -> bool:
        """Get boolean value from environment variable

        Args:
            env_var: Environment variable name
            default: Default value if not set

        Returns:
            Boolean value
        """
        value = os.environ.get(env_var, "").lower()
        if value in ("true", "1", "yes", "on", "enabled"):
            return True
        elif value in ("false", "0", "no", "off", "disabled"):
            return False
        else:
            return default
