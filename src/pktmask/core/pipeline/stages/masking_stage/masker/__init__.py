"""
Masker Module - Universal Payload Masking Processor

This module receives KeepRuleSet and original pcap files, applies preservation rules
for precise masking, handles sequence number matching and wraparound, and generates
masked pcap files.

Core Components:
- PayloadMasker: Main payload masking processor class
- ErrorRecoveryHandler: Error recovery handler
- PerformanceMonitor: Performance monitoring system
- MaskingStats: Masking statistics information

Technical Features:
- Universal payload processing based on scapy
- TCP sequence number wraparound handling support
- Based on TCP_MARKER_REFERENCE algorithm
- Protocol-agnostic masking application
"""

from .data_validator import DataValidator
from .error_handler import ErrorCategory, ErrorRecoveryHandler, ErrorSeverity
from .fallback_handler import FallbackHandler, FallbackMode
from .payload_masker import PayloadMasker
from .stats import MaskingStats

__all__ = [
    "PayloadMasker",
    "MaskingStats",
    "ErrorRecoveryHandler",
    "ErrorSeverity",
    "ErrorCategory",
    "DataValidator",
    "FallbackHandler",
    "FallbackMode",
]
