#!/usr/bin/env python3
"""
阶段一：简化兼容层实现方案
目标：移除复杂的智能检测逻辑，提供清晰的迁移路径
"""

import abc
import warnings
from pathlib import Path
from typing import Optional, Dict, List, Union

from .pipeline.base_stage import StageBase
from .pipeline.models import StageStats


class ProcessingStep(StageBase):
    """处理步骤的抽象基类 - 简化兼容层
    
    这是一个临时的兼容层，用于支持旧的 ProcessingStep 接口。
    新代码应该直接继承 StageBase。
    
    迁移路径：
    1. 现有代码：继续使用，会收到废弃警告
    2. 迁移代码：直接继承 StageBase
    3. 未来版本：移除此兼容层
    """
    
    # 保持旧的 suffix 属性以兼容现有代码
    suffix: str = ""
    
    def __init__(self):
        super().__init__()
        # 简化的废弃警告
        warnings.warn(
            f"{self.__class__.__name__} 继承自已废弃的 ProcessingStep。"
            f"请迁移到直接继承 StageBase。",
            DeprecationWarning,
            stacklevel=2
        )
    
    # 简化的兼容性实现
    def process_file(self, input_path: str | Path, output_path: str | Path) -> StageStats | Dict | None:
        """统一的处理方法 - 简化兼容实现"""
        
        # 调用子类的 legacy 方法
        result = self.process_file_legacy(str(input_path), str(output_path))
        
        # 简单的结果转换
        if result is None:
            return None
        
        if isinstance(result, dict):
            return self._convert_dict_to_stage_stats(result)
        
        return result
    
    @abc.abstractmethod
    def process_file_legacy(self, input_path: str, output_path: str) -> Optional[Dict]:
        """子类必须实现的旧版处理方法
        
        这是一个明确的接口，子类知道需要实现什么。
        返回值应该是包含处理统计信息的字典。
        """
        pass
    
    def _convert_dict_to_stage_stats(self, result: Dict) -> StageStats:
        """将旧的字典结果转换为 StageStats"""
        return StageStats(
            stage_name=self.name,
            packets_processed=result.get('total_packets', 0),
            packets_modified=result.get('modified_packets', 
                                      result.get('anonymized_packets', 
                                               result.get('removed_count', 0))),
            duration_ms=result.get('duration_ms', 0.0),
            extra_metrics=result
        )
    
    @property
    @abc.abstractmethod 
    def name(self) -> str:
        """返回步骤的可读名称"""
        pass


# 为现有实现提供迁移示例
class ExampleMigratedStage(StageBase):
    """迁移示例：如何从复杂兼容层迁移到简化版本"""
    
    @property
    def name(self) -> str:
        return "Example Stage"
    
    def process_file_legacy(self, input_path: str, output_path: str) -> Optional[Dict]:
        """实现旧版接口 - 清晰明确"""
        # 处理逻辑...
        return {
            'total_packets': 100,
            'modified_packets': 50,
            'duration_ms': 1000.0,
            'custom_metric': 'some_value'
        }


# 现代化实现示例
class ExampleModernStage(StageBase):
    """现代化实现：直接继承 StageBase"""
    
    name: str = "Modern Stage"
    
    def process_file(self, input_path: str | Path, output_path: str | Path) -> StageStats:
        """直接实现现代接口"""
        # 处理逻辑...
        return StageStats(
            stage_name=self.name,
            packets_processed=100,
            packets_modified=50,
            duration_ms=1000.0,
            extra_metrics={'custom_metric': 'some_value'}
        )
