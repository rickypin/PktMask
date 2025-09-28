#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CLI Module - Simplified command line interface

This module provides the simplified CLI interface that uses the ConsistentProcessor
directly, eliminating service layer dependencies and ensuring consistency with GUI.

Key Components:
- commands.py: Main CLI commands using ConsistentProcessor
- formatters.py: Result formatting utilities
"""

from .commands import (
    config_command,
    generate_output_path,
    process_command,
    validate_command,
)
from .formatters import (
    format_configuration_display,
    format_directory_summary,
    format_result,
    format_validation_result,
)

__all__ = [
    # Commands
    "process_command",
    "validate_command",
    "config_command",
    "generate_output_path",
    # Formatters
    "format_result",
    "format_directory_summary",
    "format_configuration_display",
    "format_validation_result",
]
