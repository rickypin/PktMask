#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
GUI Feature Flags - Safe rollout mechanism for GUI-CLI consistency

This module provides feature flags for safely rolling out the new
ConsistentProcessor integration while maintaining the ability to
instantly rollback to the original implementation.

Key Features:
- Environment variable based configuration
- Instant rollback capability
- Development vs production modes
- Granular feature control
"""

import os
from pathlib import Path
from typing import Any, Dict


class GUIFeatureFlags:
    """Feature flags for safe GUI-CLI consistency rollout

    This class provides a centralized way to control the rollout of new
    GUI functionality while maintaining backward compatibility.
    """

    # Environment variable names
    ENV_USE_CONSISTENT_PROCESSOR = "PKTMASK_USE_CONSISTENT_PROCESSOR"
    ENV_GUI_DEBUG_MODE = "PKTMASK_GUI_DEBUG_MODE"
    ENV_FORCE_LEGACY_MODE = "PKTMASK_FORCE_LEGACY_MODE"
    ENV_FEATURE_CONFIG_FILE = "PKTMASK_FEATURE_CONFIG"

    # Default values
    DEFAULT_USE_CONSISTENT_PROCESSOR = True
    DEFAULT_GUI_DEBUG_MODE = False
    DEFAULT_FORCE_LEGACY_MODE = False

    @staticmethod
    def should_use_consistent_processor() -> bool:
        """Check if new consistent processor should be used

        Returns:
            True if GUI should use ConsistentProcessor, False for legacy service layer
        """
        # Check for force legacy mode first (highest priority)
        if GUIFeatureFlags._get_bool_env(GUIFeatureFlags.ENV_FORCE_LEGACY_MODE):
            return False

        # Check main feature flag
        return GUIFeatureFlags._get_bool_env(
            GUIFeatureFlags.ENV_USE_CONSISTENT_PROCESSOR,
            GUIFeatureFlags.DEFAULT_USE_CONSISTENT_PROCESSOR,
        )

    @staticmethod
    def is_gui_debug_mode() -> bool:
        """Check if GUI debug mode is enabled

        Returns:
            True if debug mode is enabled (shows additional logging and validation)
        """
        return GUIFeatureFlags._get_bool_env(
            GUIFeatureFlags.ENV_GUI_DEBUG_MODE, GUIFeatureFlags.DEFAULT_GUI_DEBUG_MODE
        )

    @staticmethod
    def is_legacy_mode_forced() -> bool:
        """Check if legacy mode is forced

        Returns:
            True if legacy service layer mode is forced (overrides all other flags)
        """
        return GUIFeatureFlags._get_bool_env(
            GUIFeatureFlags.ENV_FORCE_LEGACY_MODE,
            GUIFeatureFlags.DEFAULT_FORCE_LEGACY_MODE,
        )

    @staticmethod
    def get_feature_config() -> Dict[str, Any]:
        """Get complete feature configuration

        Returns:
            Dictionary with all feature flag values
        """
        config = {
            "use_consistent_processor": GUIFeatureFlags.should_use_consistent_processor(),
            "gui_debug_mode": GUIFeatureFlags.is_gui_debug_mode(),
            "legacy_mode_forced": GUIFeatureFlags.is_legacy_mode_forced(),
            "config_source": "environment_variables",
        }

        # Check for config file override
        config_file = os.environ.get(GUIFeatureFlags.ENV_FEATURE_CONFIG_FILE)
        if config_file and Path(config_file).exists():
            try:
                file_config = GUIFeatureFlags._load_config_file(config_file)
                config.update(file_config)
                config["config_source"] = f"file:{config_file}"
            except Exception as e:
                # Fall back to environment variables if file loading fails
                config["config_file_error"] = str(e)

        return config

    @staticmethod
    def enable_consistent_processor():
        """Enable consistent processor for current session

        This is a convenience method for programmatic control.
        """
        os.environ[GUIFeatureFlags.ENV_USE_CONSISTENT_PROCESSOR] = "true"

    @staticmethod
    def disable_consistent_processor():
        """Disable consistent processor for current session

        This is a convenience method for programmatic control.
        """
        os.environ[GUIFeatureFlags.ENV_USE_CONSISTENT_PROCESSOR] = "false"

    @staticmethod
    def force_legacy_mode():
        """Force legacy mode for current session

        This overrides all other settings and forces use of legacy service layer.
        """
        os.environ[GUIFeatureFlags.ENV_FORCE_LEGACY_MODE] = "true"

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
        config = GUIFeatureFlags.get_feature_config()

        if config["legacy_mode_forced"]:
            return "🔒 Legacy Mode (Forced) - Using original service layer"
        elif config["use_consistent_processor"]:
            debug_status = " (Debug Mode)" if config["gui_debug_mode"] else ""
            return (
                f"✅ Consistent Processor Mode{debug_status} - Using new unified core"
            )
        else:
            return "🔄 Legacy Mode - Using original service layer"

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

    @staticmethod
    def _load_config_file(config_file: str) -> Dict[str, Any]:
        """Load configuration from file

        Args:
            config_file: Path to configuration file

        Returns:
            Configuration dictionary
        """
        import json

        with open(config_file, "r") as f:
            config = json.load(f)

        # Validate and normalize config
        normalized = {}
        if "use_consistent_processor" in config:
            normalized["use_consistent_processor"] = bool(
                config["use_consistent_processor"]
            )
        if "gui_debug_mode" in config:
            normalized["gui_debug_mode"] = bool(config["gui_debug_mode"])
        if "legacy_mode_forced" in config:
            normalized["legacy_mode_forced"] = bool(config["legacy_mode_forced"])

        return normalized


class GUIFeatureFlagValidator:
    """Validator for feature flag configurations"""

    @staticmethod
    def validate_environment() -> Dict[str, Any]:
        """Validate current environment configuration

        Returns:
            Validation results with any issues found
        """
        results = {
            "valid": True,
            "warnings": [],
            "errors": [],
            "config": GUIFeatureFlags.get_feature_config(),
        }

        # Check for conflicting settings by examining raw environment variables
        # This is needed because should_use_consistent_processor() returns False when legacy is forced
        raw_processor_enabled = GUIFeatureFlags._get_bool_env(
            GUIFeatureFlags.ENV_USE_CONSISTENT_PROCESSOR
        )
        if results["config"]["legacy_mode_forced"] and raw_processor_enabled:
            results["warnings"].append(
                "Legacy mode is forced but consistent processor is also enabled. "
                "Legacy mode takes precedence."
            )

        # Check for debug mode without consistent processor
        if (
            results["config"]["gui_debug_mode"]
            and not results["config"]["use_consistent_processor"]
        ):
            results["warnings"].append(
                "Debug mode is enabled but consistent processor is disabled. "
                "Debug mode has no effect in legacy mode."
            )

        # Check for config file issues
        if "config_file_error" in results["config"]:
            results["errors"].append(
                f"Config file error: {results['config']['config_file_error']}"
            )
            results["valid"] = False

        return results

    @staticmethod
    def get_validation_summary() -> str:
        """Get human-readable validation summary

        Returns:
            String describing validation results
        """
        validation = GUIFeatureFlagValidator.validate_environment()

        summary_parts = [GUIFeatureFlags.get_status_summary()]

        if validation["warnings"]:
            summary_parts.append(f"⚠️  {len(validation['warnings'])} warning(s)")

        if validation["errors"]:
            summary_parts.append(f"❌ {len(validation['errors'])} error(s)")

        return " | ".join(summary_parts)
