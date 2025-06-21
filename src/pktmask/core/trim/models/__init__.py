"""
Trim模块数据模型

包含掩码规范、掩码表、TCP流管理等核心数据结构。
"""

from .mask_spec import MaskSpec, MaskAfter, MaskRange, KeepAll
from .mask_table import StreamMaskTable, StreamMaskEntry
from .execution_result import ExecutionResult, StageResult
from .simple_execution_result import SimpleExecutionResult

# Phase 1 重构：新增的序列号掩码机制
from .tcp_stream import (
    ConnectionDirection, 
    TCPConnection, 
    DirectionalTCPStream, 
    TCPStreamManager,
    detect_packet_direction
)
from .sequence_mask_table import (
    MaskEntry,
    SequenceMatchResult, 
    SequenceMaskTable
)

__all__ = [
    # 原有掩码规范
    'MaskSpec', 'MaskAfter', 'MaskRange', 'KeepAll',
    
    # 原有掩码表
    'StreamMaskTable', 'StreamMaskEntry',
    
    # 执行结果
    'ExecutionResult', 'StageResult', 'SimpleExecutionResult',
    
    # 新增：TCP流管理
    'ConnectionDirection', 'TCPConnection', 'DirectionalTCPStream', 'TCPStreamManager',
    'detect_packet_direction',
    
    # 新增：序列号掩码表
    'MaskEntry', 'SequenceMatchResult', 'SequenceMaskTable'
] 