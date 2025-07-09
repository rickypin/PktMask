import abc
import warnings
from pathlib import Path
from typing import Optional, Dict, List, Union

from .pipeline.base_stage import StageBase
from .pipeline.models import StageStats


class ProcessingStep(StageBase):
    """处理步骤的抽象基类 - 兼容性包装
    
    ！！！迁移提示！！！
    这个类是为了兼容旧的 ProcessingStep 接口而保留的。
    推荐新代码直接继承 StageBase。
    
    现有的 ProcessingStep 子类可以：
    1. 暂时继续使用这个兼容层
    2. 将 process_file 方法重命名为 process_file_legacy
    3. 最终迁移到直接继承 StageBase
    """
    
    # 保持旧的 suffix 属性以兼容
    suffix: str = ""
    
    def __init__(self):
        super().__init__()
        # 发出迁移提示（仅在第一次创建实例时）
        if not hasattr(self.__class__, '_migration_warning_shown'):
            warnings.warn(
                f"{self.__class__.__name__} 继承自 ProcessingStep（兼容层）。"
                "推荐迁移到直接继承 StageBase 以获得更好的功能。",
                FutureWarning,
                stacklevel=2
            )
            self.__class__._migration_warning_shown = True
    
    # 重写父类的方法以提供兼容性
    def prepare_for_directory(self, directory: str | Path, all_files: List[str]) -> None:
        """兼容旧的 prepare_for_directory 接口"""
        # 调用旧版本的方法签名（如果子类重写了的话）
        if hasattr(self, '_legacy_prepare_for_directory'):
            self._legacy_prepare_for_directory(str(directory), all_files)
        else:
            # 尝试调用旧的方法签名
            try:
                # 获取原始方法
                method = getattr(super(ProcessingStep, self), 'prepare_for_directory', None)
                if method and callable(method):
                    method(str(directory), all_files)
            except TypeError:
                # 如果方法签名不匹配，调用新的方法
                super().prepare_for_directory(directory, all_files)
    
    def process_file(self, input_path: str | Path, output_path: str | Path) -> StageStats | Dict | None:
        """统一的处理方法 - 兼容新旧接口"""
        
        # 尝试调用新的方法（如果子类已经迁移）
        if hasattr(self, 'process_file_legacy'):
            # 子类提供了 legacy 方法，使用它
            result = self.process_file_legacy(str(input_path), str(output_path))
            return self._convert_legacy_result_to_stage_stats(result)
        
        # 如果子类重写了 process_file，直接调用
        # 这里使用一个技巧来检测子类是否重写了 process_file
        child_method = getattr(type(self), 'process_file', None)
        if child_method and child_method is not ProcessingStep.process_file:
            # 子类重写了 process_file，但我们需要避免无限递归
            # 这种情况下，假设子类期望旧的接口
            result = self._call_legacy_process_file(str(input_path), str(output_path))
            return self._convert_legacy_result_to_stage_stats(result)
        
        # 如果都没有，抛出错误
        raise NotImplementedError(
            f"{self.__class__.__name__} 必须实现 process_file_legacy 方法，"
            "或者直接继承 StageBase 并实现新的 process_file 方法。"
        )
    
    def _call_legacy_process_file(self, input_path: str, output_path: str) -> Optional[Dict]:
        """调用子类的旧版 process_file 方法"""
        # 这里需要一个巧妙的方法来调用子类的原始 process_file
        # 我们直接查找子类的方法并调用
        for cls in type(self).__mro__[1:]:  # 跳过自己，从父类开始
            if hasattr(cls, 'process_file') and cls is not ProcessingStep:
                method = getattr(cls, 'process_file')
                if callable(method):
                    return method(self, input_path, output_path)
        return None
    
    def _convert_legacy_result_to_stage_stats(self, result: Optional[Dict]) -> StageStats | Dict | None:
        """将旧的 Dict 结果转换为 StageStats"""
        if result is None:
            return None
        
        if not isinstance(result, dict):
            return result
        
        # 尝试从旧结果中提取信息构建 StageStats
        return StageStats(
            stage_name=self.name,
            packets_processed=result.get('total_packets', 0),
            packets_modified=result.get('anonymized_packets', result.get('modified_packets', 0)),
            duration_ms=result.get('duration_ms', 0.0),
            extra_metrics=result
        )
    
    @property
    @abc.abstractmethod 
    def name(self) -> str:
        """返回步骤的可读名称 (e.g., 'Mask IP')"""
        pass
