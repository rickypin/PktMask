#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PktMask GUI架构改进 - 核心接口定义
定义GUI无关的接口，实现真正的架构分层
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

# ============================================================================
# 1. 数据模型定义 (GUI无关)
# ============================================================================


@dataclass
class AppState:
    """应用程序状态模型"""

    input_directory: Optional[str] = None
    output_directory: Optional[str] = None
    processing_options: Dict[str, bool] = None
    is_processing: bool = False
    current_file: Optional[str] = None
    progress_percentage: float = 0.0

    def __post_init__(self):
        if self.processing_options is None:
            self.processing_options = {
                "remove_dupes": False,
                "anonymize_ips": False,
                "mask_payloads": False,
            }


@dataclass
class ProcessingProgress:
    """处理进度模型"""

    current_file: str
    total_files: int
    processed_files: int
    failed_files: int
    percentage: float
    stage_name: str
    stage_stats: Dict[str, Any]


@dataclass
class ProcessingResult:
    """处理结果模型"""

    success: bool
    total_files: int
    processed_files: int
    failed_files: int
    duration_ms: float
    errors: List[str]
    summary_stats: Dict[str, Any]


class AppEvent(Enum):
    """应用程序事件类型"""

    # 文件选择事件
    INPUT_DIRECTORY_SELECTED = "input_directory_selected"
    OUTPUT_DIRECTORY_SELECTED = "output_directory_selected"

    # 处理控制事件
    PROCESSING_STARTED = "processing_started"
    PROCESSING_STOPPED = "processing_stopped"
    PROCESSING_COMPLETED = "processing_completed"

    # 进度事件
    PROGRESS_UPDATED = "progress_updated"
    FILE_PROCESSING_STARTED = "file_processing_started"
    FILE_PROCESSING_COMPLETED = "file_processing_completed"

    # 错误事件
    ERROR_OCCURRED = "error_occurred"
    WARNING_OCCURRED = "warning_occurred"

    # 配置事件
    OPTIONS_CHANGED = "options_changed"
    THEME_CHANGED = "theme_changed"


# ============================================================================
# 2. View接口定义 (GUI框架无关)
# ============================================================================


class IView(ABC):
    """View接口 - 定义GUI必须实现的方法"""

    @abstractmethod
    def show_main_window(self) -> None:
        """显示主窗口"""
        pass

    @abstractmethod
    def close_application(self) -> None:
        """关闭应用程序"""
        pass

    @abstractmethod
    def update_app_state(self, state: AppState) -> None:
        """更新应用程序状态显示"""
        pass

    @abstractmethod
    def update_progress(self, progress: ProcessingProgress) -> None:
        """更新处理进度显示"""
        pass

    @abstractmethod
    def show_processing_result(self, result: ProcessingResult) -> None:
        """显示处理结果"""
        pass

    @abstractmethod
    def show_error(self, title: str, message: str) -> None:
        """显示错误信息"""
        pass

    @abstractmethod
    def show_warning(self, title: str, message: str) -> None:
        """显示警告信息"""
        pass

    @abstractmethod
    def show_info(self, title: str, message: str) -> None:
        """显示信息提示"""
        pass

    @abstractmethod
    def prompt_directory_selection(self, title: str, initial_dir: str = "") -> Optional[str]:
        """提示用户选择目录"""
        pass

    @abstractmethod
    def confirm_action(self, title: str, message: str) -> bool:
        """确认用户操作"""
        pass


class IFileView(ABC):
    """文件操作View接口"""

    @abstractmethod
    def update_input_directory_display(self, directory: str) -> None:
        """更新输入目录显示"""
        pass

    @abstractmethod
    def update_output_directory_display(self, directory: str) -> None:
        """更新输出目录显示"""
        pass

    @abstractmethod
    def update_file_count_display(self, count: int) -> None:
        """更新文件数量显示"""
        pass


class IPipelineView(ABC):
    """处理流程View接口"""

    @abstractmethod
    def update_processing_button_state(self, is_processing: bool) -> None:
        """更新处理按钮状态"""
        pass

    @abstractmethod
    def update_options_display(self, options: Dict[str, bool]) -> None:
        """更新选项显示"""
        pass

    @abstractmethod
    def enable_controls(self, enabled: bool) -> None:
        """启用/禁用控件"""
        pass


class IReportView(ABC):
    """报告View接口"""

    @abstractmethod
    def update_log_display(self, message: str) -> None:
        """更新日志显示"""
        pass

    @abstractmethod
    def update_statistics_display(self, stats: Dict[str, Any]) -> None:
        """更新统计信息显示"""
        pass

    @abstractmethod
    def show_detailed_report(self, report_data: Dict[str, Any]) -> None:
        """显示详细报告"""
        pass


# ============================================================================
# 3. Presenter接口定义 (业务逻辑层)
# ============================================================================


class IEventBus(ABC):
    """事件总线接口"""

    @abstractmethod
    def subscribe(self, event_type: AppEvent, handler: Callable[[Any], None]) -> None:
        """订阅事件"""
        pass

    @abstractmethod
    def unsubscribe(self, event_type: AppEvent, handler: Callable[[Any], None]) -> None:
        """取消订阅事件"""
        pass

    @abstractmethod
    def emit(self, event_type: AppEvent, data: Any = None) -> None:
        """发送事件"""
        pass


class IAppPresenter(ABC):
    """应用程序Presenter接口"""

    @abstractmethod
    def initialize(self) -> None:
        """初始化应用程序"""
        pass

    @abstractmethod
    def shutdown(self) -> None:
        """关闭应用程序"""
        pass

    @abstractmethod
    def get_current_state(self) -> AppState:
        """获取当前应用程序状态"""
        pass


class IFilePresenter(ABC):
    """文件操作Presenter接口"""

    @abstractmethod
    def select_input_directory(self) -> None:
        """选择输入目录"""
        pass

    @abstractmethod
    def select_output_directory(self) -> None:
        """选择输出目录"""
        pass

    @abstractmethod
    def validate_directories(self) -> bool:
        """验证目录有效性"""
        pass

    @abstractmethod
    def get_file_count(self, directory: str) -> int:
        """获取目录中的文件数量"""
        pass


class IPipelinePresenter(ABC):
    """处理流程Presenter接口"""

    @abstractmethod
    def start_processing(self) -> None:
        """开始处理"""
        pass

    @abstractmethod
    def stop_processing(self) -> None:
        """停止处理"""
        pass

    @abstractmethod
    def update_processing_options(self, options: Dict[str, bool]) -> None:
        """更新处理选项"""
        pass

    @abstractmethod
    def is_processing(self) -> bool:
        """检查是否正在处理"""
        pass


class IReportPresenter(ABC):
    """报告Presenter接口"""

    @abstractmethod
    def generate_summary_report(self) -> Dict[str, Any]:
        """生成摘要报告"""
        pass

    @abstractmethod
    def export_detailed_report(self, file_path: str) -> bool:
        """导出详细报告"""
        pass

    @abstractmethod
    def clear_logs(self) -> None:
        """清空日志"""
        pass


# ============================================================================
# 4. 组合接口 (完整的View和Presenter接口)
# ============================================================================


class IMainView(IView, IFileView, IPipelineView, IReportView):
    """主View接口 - 组合所有View接口"""

    pass


class IMainPresenter(IAppPresenter, IFilePresenter, IPipelinePresenter, IReportPresenter):
    """主Presenter接口 - 组合所有Presenter接口"""

    @abstractmethod
    def set_view(self, view: IMainView) -> None:
        """设置View实例"""
        pass

    @abstractmethod
    def set_event_bus(self, event_bus: IEventBus) -> None:
        """设置事件总线"""
        pass
