"""
Enhanced Trim Payloads 数据模型

包含所有核心数据结构的定义：
- MaskSpec: 掩码规范及其子类
- StreamMaskTable: 流掩码表
- ExecutionResult: 执行结果封装
"""

from .mask_spec import MaskSpec, MaskAfter, MaskRange, KeepAll
from .mask_table import StreamMaskTable, StreamMaskEntry
from .execution_result import ExecutionResult

__all__ = [
    'MaskSpec', 'MaskAfter', 'MaskRange', 'KeepAll',
    'StreamMaskTable', 'StreamMaskEntry',
    'ExecutionResult'
] 