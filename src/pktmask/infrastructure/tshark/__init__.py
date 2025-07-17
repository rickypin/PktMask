#!/usr/bin/env python3
"""
TShark Infrastructure Module

Cross-platform TShark management and integration for PktMask.
"""

from .manager import TSharkManager, TSharkInfo, TSharkStatus
from .tls_validator import TLSMarkerValidator, TLSValidationResult, validate_tls_marker_functionality

__all__ = [
    'TSharkManager',
    'TSharkInfo',
    'TSharkStatus',
    'TLSMarkerValidator',
    'TLSValidationResult',
    'validate_tls_marker_functionality'
]
