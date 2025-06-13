#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
简化执行结果模型

专门为多阶段执行器设计的简单执行结果类。
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum, auto


class SimpleStageState(Enum):
    """简化的阶段状态枚举"""
    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()


@dataclass
class SimpleExecutionResult:
    """简化的执行结果
    
    专门为多阶段执行器设计，提供基本的执行结果信息。
    """
    
    success: bool
    state: SimpleStageState
    duration: float = 0.0
    total_stages: int = 0
    stats: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    stage_results: Optional[List[Dict[str, Any]]] = None
    
    def __post_init__(self):
        if self.stats is None:
            self.stats = {}
        if self.stage_results is None:
            self.stage_results = []
    
    def is_successful(self) -> bool:
        """检查是否成功"""
        return self.success and self.state == SimpleStageState.COMPLETED
    
    def get_summary(self) -> Dict[str, Any]:
        """获取摘要信息"""
        return {
            'success': self.success,
            'state': self.state.name,
            'duration': self.duration,
            'total_stages': self.total_stages,
            'error': self.error,
            'stage_count': len(self.stage_results) if self.stage_results else 0
        } 