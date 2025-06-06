import os
from abc import ABC, abstractmethod
from typing import Callable, Optional, List

from .events import PipelineEvents

class ProcessingStep(ABC):
    """处理步骤的抽象基类"""

    @property
    @abstractmethod
    def suffix(self) -> str:
        """返回此步骤添加到文件名中的后缀"""
        pass

    @abstractmethod
    def process_directory(self, subdir_path: str, base_path: str, progress_callback: Optional[Callable] = None, all_suffixes: Optional[List[str]] = None):
        """
        处理整个目录的接口方法
        
        Args:
            subdir_path (str): 待处理的子目录路径.
            base_path (str): 项目的根目录路径.
            progress_callback (Optional[Callable]): 用于报告进度的回调函数.
            all_suffixes (Optional[List[str]]): 流水线中所有步骤的后缀列表.
        """
        pass


class Pipeline:
    """定义和执行处理步骤的流水线"""

    def __init__(self, steps: list[ProcessingStep]):
        self._steps = steps

    def run(self, root_path: str, progress_callback: Optional[Callable] = None):
        """在指定路径上运行所有处理步骤"""
        subdirs = [os.path.join(root_path, d) for d in os.listdir(root_path) if os.path.isdir(os.path.join(root_path, d))]
        total_subdirs = len(subdirs)
        all_suffixes = [step.suffix for step in self._steps]

        if progress_callback:
            progress_callback(PipelineEvents.PIPELINE_START, {'total_subdirs': total_subdirs})

        for i, subdir in enumerate(subdirs):
            rel_subdir = os.path.relpath(subdir, root_path)
            if progress_callback:
                progress_callback(PipelineEvents.SUBDIR_START, {'name': rel_subdir, 'current': i + 1, 'total': total_subdirs})
            
            for step in self._steps:
                if progress_callback:
                    progress_callback(PipelineEvents.STEP_START, {'name': step.__class__.__name__})
                
                step.process_directory(subdir, base_path=root_path, progress_callback=progress_callback, all_suffixes=all_suffixes)
                
                if progress_callback:
                    progress_callback(PipelineEvents.STEP_END, {'name': step.__class__.__name__})
            
            if progress_callback:
                progress_callback(PipelineEvents.SUBDIR_END, {'name': rel_subdir})

        if progress_callback:
            progress_callback(PipelineEvents.PIPELINE_END, {}) 