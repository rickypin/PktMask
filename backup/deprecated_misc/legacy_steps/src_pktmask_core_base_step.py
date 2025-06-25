from abc import ABC, abstractmethod
from typing import Optional, Dict, List

class ProcessingStep(ABC):
    """处理步骤的抽象基类"""
    suffix: str = ""

    @property
    @abstractmethod
    def name(self) -> str:
        """返回步骤的可读名称 (e.g., 'Mask IP')"""
        pass

    def prepare_for_directory(self, subdir_path: str, all_files: List[str]):
        """
        在处理目录中的任何文件之前调用的可选准备步骤。
        子类可以重写此方法以执行预扫描等操作。
        
        Args:
            subdir_path (str): 正在处理的子目录的路径。
            all_files (List[str]): 该目录中所有待处理文件的完整路径列表。
        """
        pass

    @abstractmethod
    def process_file(self, input_path: str, output_path: str) -> Optional[Dict]:
        """
        处理单个文件。

        Args:
            input_path (str): 输入文件的路径。
            output_path (str): 输出文件的路径。

        Returns:
            Optional[Dict]: 一个包含处理摘要的字典，如果没有摘要则为None。
        """
        pass 