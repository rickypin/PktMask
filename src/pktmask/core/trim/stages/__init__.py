#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Enhanced Trim 处理阶段模块

包含TShark预处理、PyShark分析、Scapy回写的三阶段处理器。
"""

from .base_stage import BaseStage, StageContext
from .stage_result import (
    StageResult, StageStatus, StageMetrics, StageResultCollection
)
from .tshark_preprocessor import TSharkPreprocessor
from .enhanced_pyshark_analyzer import EnhancedPySharkAnalyzer, EnhancedPySharkAnalyzer as PySharkAnalyzer
from .tcp_payload_masker_adapter import TcpPayloadMaskerAdapter

__all__ = [
    'BaseStage', 'StageContext',
    'StageResult', 'StageStatus', 'StageMetrics', 'StageResultCollection',
    'TSharkPreprocessor',
    'EnhancedPySharkAnalyzer',
    'PySharkAnalyzer',
    'TcpPayloadMaskerAdapter'
] 