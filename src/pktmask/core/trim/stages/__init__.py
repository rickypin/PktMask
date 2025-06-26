#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Enhanced Trim 处理阶段模块

包含TShark预处理、PyShark分析以及 TcpPayloadMaskerAdapter 回写的多阶段处理器。
"""

from .base_stage import BaseStage, StageContext
from .stage_result import (
    StageResult, StageStatus, StageMetrics, StageResultCollection
)
from .tshark_preprocessor import TSharkPreprocessor
from .enhanced_pyshark_analyzer import EnhancedPySharkAnalyzer, EnhancedPySharkAnalyzer as PySharkAnalyzer
from .tcp_payload_masker_adapter import TcpPayloadMaskerAdapter
from importlib import import_module as _import_module
import sys as _sys

__all__ = [
    'BaseStage', 'StageContext',
    'StageResult', 'StageStatus', 'StageMetrics', 'StageResultCollection',
    'TSharkPreprocessor',
    'EnhancedPySharkAnalyzer',
    'PySharkAnalyzer',
    'TcpPayloadMaskerAdapter'
]

# ------------------------------------------------------------------
# 兼容性别名（临时保留）
# ------------------------------------------------------------------
# 为了避免旧测试或脚本仍然出现 "pktmask.core.trim.stages.scapy_rewriter"
# 的导入路径报错，这里将其映射到新的 TcpPayloadMaskerAdapter 模块。
# ✅ 生产代码请直接使用 TcpPayloadMaskerAdapter，并尽快删除对旧路径的引用。

_scapy_alias = _import_module('.tcp_payload_masker_adapter', package=__name__)
_sys.modules[f'{__name__}.scapy_rewriter'] = _scapy_alias
_sys.modules['src.pktmask.core.trim.stages.scapy_rewriter'] = _scapy_alias 