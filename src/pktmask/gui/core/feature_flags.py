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
    ENV_USE_CONSISTENT = "PKTMASK_USE_CONSISTENT_PROCESSOR"
    ENV_FORCE_LEGACY = "PKTMASK_FORCE_LEGACY_MODE"

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
    def should_use_consistent_processor() -> bool:
        """Whether GUI should use the unified ConsistentProcessor path.

        Follows precedence: force legacy overrides any explicit enable.
        """
        if GUIFeatureFlags._get_bool_env(GUIFeatureFlags.ENV_FORCE_LEGACY, False):
            return False
        return GUIFeatureFlags._get_bool_env(GUIFeatureFlags.ENV_USE_CONSISTENT, False)

    @staticmethod
    def enable_consistent_processor() -> None:
        """Enable ConsistentProcessor for the current session (GUI path)."""
        os.environ[GUIFeatureFlags.ENV_USE_CONSISTENT] = "true"
        # Do not automatically unset force legacy; precedence will handle it

    @staticmethod
    def force_legacy_mode() -> None:
        """Force legacy behavior for current session (overrides consistent)."""
        os.environ[GUIFeatureFlags.ENV_FORCE_LEGACY] = "true"

    @staticmethod
    def is_legacy_mode_forced() -> bool:
        """Return True if legacy mode is explicitly forced."""
        return GUIFeatureFlags._get_bool_env(GUIFeatureFlags.ENV_FORCE_LEGACY, False)

    @staticmethod
    def get_feature_config() -> Dict[str, Any]:
        """Get complete feature configuration

        Returns:
            Dictionary with all feature flag values
        """
        return {
            "gui_debug_mode": GUIFeatureFlags.is_gui_debug_mode(),
            "use_consistent_processor": GUIFeatureFlags.should_use_consistent_processor(),
            "legacy_mode_forced": GUIFeatureFlags.is_legacy_mode_forced(),
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
