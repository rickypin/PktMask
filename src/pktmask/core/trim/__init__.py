#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Enhanced Trim Payloads 核心模块

提供多阶段载荷裁切功能，包括TShark预处理、PyShark分析、Scapy回写。

核心组件:
- 数据结构模型 (models/)
- 多阶段执行器 (multi_stage_executor.py)
- 处理阶段 (stages/)
"""

# 导入数据结构模型
from .models.mask_spec import (
    MaskSpec, MaskAfter, MaskRange, KeepAll
)
from .models.mask_table import (
    StreamMaskTable, StreamMaskEntry
)
from .models.execution_result import (
    ExecutionResult, ExecutionStatus, StageStatus, TrimmerConfig
)
from .models.simple_execution_result import (
    SimpleExecutionResult, SimpleStageState
)

# 导入多阶段执行器框架
from .multi_stage_executor import (
    MultiStageExecutor, StageContext, BaseStage, StageResult
)

# 导入阶段相关类
from .stages.base_stage import BaseStage as StageBase
from .stages.stage_result import (
    StageResult as DetailedStageResult,
    StageStatus, StageMetrics, StageResultCollection
)

__all__ = [
    # 数据结构模型
    'MaskSpec', 'MaskAfter', 'MaskRange', 'KeepAll',
    'StreamMaskTable', 'StreamMaskEntry',
    'ExecutionResult', 'ExecutionStatus', 'StageStatus', 'TrimmerConfig',
    'SimpleExecutionResult', 'SimpleStageState',
    
    # 多阶段执行器框架
    'MultiStageExecutor', 'StageContext', 'BaseStage', 'StageResult',
    
    # 阶段相关
    'StageBase', 'DetailedStageResult', 
    'StageStatus', 'StageMetrics', 'StageResultCollection'
]

# 版本信息
__version__ = '1.0.0'
__author__ = 'PktMask Enhanced Trim Team'
__description__ = 'Multi-stage payload trimming framework for PCAP files' 