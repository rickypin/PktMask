from __future__ import annotations

import abc
from pathlib import Path
from typing import Dict, List, Optional

from .models import StageStats


class StageBase(metaclass=abc.ABCMeta):
    """Pipeline 中每个处理阶段的抽象基类。

    该接口只定义必要的生命周期方法，避免过度约束。所有实现类必须保持
    向后兼容，禁止修改已有方法的入参/返回值签名。新增方法需保证带默认
    实现，并通过类型提示避免破坏。"""

    #: 实现类应覆盖，用于 GUI/CLI 显示
    name: str = "UnnamedStage"

    #: Stage 是否已执行初始化
    _initialized: bool = False

    def initialize(self, config: Optional[Dict] | None = None) -> None:
        """可选初始化逻辑。默认实现仅设置 `_initialized = True`。"""

        self._initialized = True

    # ---------------------------------------------------------------------
    # 目录级生命周期
    # ---------------------------------------------------------------------
    def prepare_for_directory(self, directory: str | Path, all_files: List[str]) -> None:
        """在处理同一目录中的文件之前调用，用于执行预扫描或资源初始化。
        默认实现什么也不做。"""

    def finalize_directory_processing(self) -> Optional[Dict]:
        """目录中所有文件处理完毕后调用，用于生成汇总信息或清理资源。"""
        return None

    # ---------------------------------------------------------------------
    # 核心处理方法
    # ---------------------------------------------------------------------
    @abc.abstractmethod
    def process_file(self, input_path: str | Path, output_path: str | Path) -> StageStats | Dict | None:
        """处理单个文件。必须返回 `StageStats` 或兼容字典以供序列化。"""

    # ---------------------------------------------------------------------
    # 可选停止钩子
    # ---------------------------------------------------------------------
    def stop(self) -> None:
        """在 Pipeline 停止或用户取消时调用，用于提前终止外部进程等。"""

    # ---------------------------------------------------------------------
    # 工具链检测
    # ---------------------------------------------------------------------
    def get_required_tools(self) -> List[str]:
        """若 Stage 依赖外部可执行文件，返回其名称列表 (如 `tshark`)。
        默认返回空列表。"""
        return [] 