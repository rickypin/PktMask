#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PktMask GUI架构改进 - Presenter层实现
实现GUI无关的业务逻辑层
"""

import os
import threading
from typing import Any, Dict, List, Optional

# 注意：这里的导入在实际实现时需要调整
# from .gui_architecture_interfaces import *

# 导入现有的服务层 (已经存在且GUI无关)
# from pktmask.services.config_service import get_config_service
# from pktmask.services.pipeline_service import (
#     create_pipeline_executor,
#     process_directory,
#     PipelineEvents
# )


# ============================================================================
# 1. 事件总线实现
# ============================================================================


class EventBus(IEventBus):
    """简单的事件总线实现"""

    def __init__(self):
        self._subscribers: Dict[AppEvent, List[Callable]] = {}
        self._lock = threading.Lock()

    def subscribe(self, event_type: AppEvent, handler: Callable[[Any], None]) -> None:
        """订阅事件"""
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: AppEvent, handler: Callable[[Any], None]) -> None:
        """取消订阅事件"""
        with self._lock:
            if event_type in self._subscribers:
                try:
                    self._subscribers[event_type].remove(handler)
                except ValueError:
                    pass  # Handler not found

    def emit(self, event_type: AppEvent, data: Any = None) -> None:
        """发送事件"""
        with self._lock:
            handlers = self._subscribers.get(event_type, []).copy()

        # 在锁外执行处理器，避免死锁
        for handler in handlers:
            try:
                handler(data)
            except Exception as e:
                print(f"Error in event handler: {e}")


# ============================================================================
# 2. 主Presenter实现
# ============================================================================


class MainPresenter(IMainPresenter):
    """主Presenter - 协调所有业务逻辑"""

    def __init__(self):
        self._view: Optional[IMainView] = None
        self._event_bus: Optional[IEventBus] = None
        self._app_state = AppState()
        self._config_service = get_config_service()
        self._processing_thread: Optional[threading.Thread] = None
        self._stop_processing_flag = threading.Event()

    def set_view(self, view: IMainView) -> None:
        """设置View实例"""
        self._view = view

    def set_event_bus(self, event_bus: IEventBus) -> None:
        """设置事件总线"""
        self._event_bus = event_bus
        self._subscribe_to_events()

    def _subscribe_to_events(self) -> None:
        """订阅相关事件"""
        if not self._event_bus:
            return

        # 订阅内部事件
        self._event_bus.subscribe(
            AppEvent.INPUT_DIRECTORY_SELECTED, self._on_input_directory_selected
        )
        self._event_bus.subscribe(
            AppEvent.OUTPUT_DIRECTORY_SELECTED, self._on_output_directory_selected
        )
        self._event_bus.subscribe(AppEvent.OPTIONS_CHANGED, self._on_options_changed)

    # ========================================================================
    # IAppPresenter 实现
    # ========================================================================

    def initialize(self) -> None:
        """初始化应用程序"""
        if self._view:
            self._view.show_main_window()
            self._view.update_app_state(self._app_state)

    def shutdown(self) -> None:
        """关闭应用程序"""
        if self.is_processing():
            self.stop_processing()

        if self._view:
            self._view.close_application()

    def get_current_state(self) -> AppState:
        """获取当前应用程序状态"""
        return self._app_state

    # ========================================================================
    # IFilePresenter 实现
    # ========================================================================

    def select_input_directory(self) -> None:
        """选择输入目录"""
        if not self._view:
            return

        directory = self._view.prompt_directory_selection(
            "Select Input Directory", self._app_state.input_directory or ""
        )

        if directory:
            self._app_state.input_directory = directory
            self._view.update_input_directory_display(directory)

            # 自动生成输出目录
            if not self._app_state.output_directory:
                default_output = os.path.join(directory, "processed")
                self._app_state.output_directory = default_output
                self._view.update_output_directory_display(default_output)

            # 更新文件数量
            file_count = self.get_file_count(directory)
            self._view.update_file_count_display(file_count)

            # 发送事件
            if self._event_bus:
                self._event_bus.emit(AppEvent.INPUT_DIRECTORY_SELECTED, directory)

    def select_output_directory(self) -> None:
        """选择输出目录"""
        if not self._view:
            return

        directory = self._view.prompt_directory_selection(
            "Select Output Directory", self._app_state.output_directory or ""
        )

        if directory:
            self._app_state.output_directory = directory
            self._view.update_output_directory_display(directory)

            # 发送事件
            if self._event_bus:
                self._event_bus.emit(AppEvent.OUTPUT_DIRECTORY_SELECTED, directory)

    def validate_directories(self) -> bool:
        """验证目录有效性"""
        if not self._app_state.input_directory:
            if self._view:
                self._view.show_error("Error", "Please select an input directory")
            return False

        if not os.path.exists(self._app_state.input_directory):
            if self._view:
                self._view.show_error("Error", "Input directory does not exist")
            return False

        if not self._app_state.output_directory:
            if self._view:
                self._view.show_error("Error", "Please select an output directory")
            return False

        return True

    def get_file_count(self, directory: str) -> int:
        """获取目录中的PCAP文件数量"""
        if not os.path.exists(directory):
            return 0

        count = 0
        try:
            for file in os.listdir(directory):
                if file.lower().endswith((".pcap", ".pcapng")):
                    count += 1
        except OSError:
            pass

        return count

    # ========================================================================
    # IPipelinePresenter 实现
    # ========================================================================

    def start_processing(self) -> None:
        """开始处理"""
        if self.is_processing():
            return

        if not self.validate_directories():
            return

        # 检查是否选择了处理选项
        if not any(self._app_state.processing_options.values()):
            if self._view:
                self._view.show_warning(
                    "Warning", "Please select at least one processing option"
                )
            return

        # 更新状态
        self._app_state.is_processing = True
        if self._view:
            self._view.update_processing_button_state(True)
            self._view.enable_controls(False)

        # 发送事件
        if self._event_bus:
            self._event_bus.emit(AppEvent.PROCESSING_STARTED)

        # 启动处理线程
        self._stop_processing_flag.clear()
        self._processing_thread = threading.Thread(target=self._run_processing)
        self._processing_thread.start()

    def stop_processing(self) -> None:
        """停止处理"""
        if not self.is_processing():
            return

        self._stop_processing_flag.set()

        if self._processing_thread and self._processing_thread.is_alive():
            self._processing_thread.join(timeout=5.0)

        # 更新状态
        self._app_state.is_processing = False
        if self._view:
            self._view.update_processing_button_state(False)
            self._view.enable_controls(True)

        # 发送事件
        if self._event_bus:
            self._event_bus.emit(AppEvent.PROCESSING_STOPPED)

    def update_processing_options(self, options: Dict[str, bool]) -> None:
        """更新处理选项"""
        self._app_state.processing_options.update(options)

        if self._view:
            self._view.update_options_display(self._app_state.processing_options)

        # 发送事件
        if self._event_bus:
            self._event_bus.emit(AppEvent.OPTIONS_CHANGED, options)

    def is_processing(self) -> bool:
        """检查是否正在处理"""
        return self._app_state.is_processing

    # ========================================================================
    # IReportPresenter 实现
    # ========================================================================

    def generate_summary_report(self) -> Dict[str, Any]:
        """生成摘要报告"""
        return {
            "input_directory": self._app_state.input_directory,
            "output_directory": self._app_state.output_directory,
            "processing_options": self._app_state.processing_options,
            "current_state": "Processing" if self._app_state.is_processing else "Idle",
        }

    def export_detailed_report(self, file_path: str) -> bool:
        """导出详细报告"""
        try:
            report = self.generate_summary_report()
            # 这里可以实现具体的报告导出逻辑
            return True
        except Exception:
            return False

    def clear_logs(self) -> None:
        """清空日志"""
        if self._view:
            self._view.update_log_display("")

    # ========================================================================
    # 私有方法
    # ========================================================================

    def _run_processing(self) -> None:
        """运行处理逻辑 (在后台线程中)"""
        try:
            # 构建配置
            config = self._config_service.build_pipeline_config(
                self._app_state.processing_options
            )

            # 创建执行器
            executor = create_pipeline_executor(config)

            # 定义进度回调
            def progress_callback(event_type: PipelineEvents, data: Dict[str, Any]):
                if self._stop_processing_flag.is_set():
                    return

                # 转换为我们的进度模型
                if event_type == PipelineEvents.FILE_START:
                    progress = ProcessingProgress(
                        current_file=data.get("path", ""),
                        total_files=0,  # 这里需要从其他地方获取
                        processed_files=0,
                        failed_files=0,
                        percentage=0.0,
                        stage_name="Processing",
                        stage_stats={},
                    )

                    if self._view:
                        self._view.update_progress(progress)

                    if self._event_bus:
                        self._event_bus.emit(AppEvent.PROGRESS_UPDATED, progress)

            # 运行处理
            process_directory(
                executor=executor,
                input_dir=self._app_state.input_directory,
                output_dir=self._app_state.output_directory,
                progress_callback=progress_callback,
                is_running_check=lambda: not self._stop_processing_flag.is_set(),
            )

            # 处理完成
            result = ProcessingResult(
                success=True,
                total_files=0,  # 需要从实际结果获取
                processed_files=0,
                failed_files=0,
                duration_ms=0.0,
                errors=[],
                summary_stats={},
            )

            if self._view:
                self._view.show_processing_result(result)

            if self._event_bus:
                self._event_bus.emit(AppEvent.PROCESSING_COMPLETED, result)

        except Exception as e:
            if self._view:
                self._view.show_error("Processing Error", str(e))

            if self._event_bus:
                self._event_bus.emit(AppEvent.ERROR_OCCURRED, str(e))

        finally:
            # 确保状态正确更新
            self._app_state.is_processing = False
            if self._view:
                self._view.update_processing_button_state(False)
                self._view.enable_controls(True)

    def _on_input_directory_selected(self, directory: str) -> None:
        """处理输入目录选择事件"""
        pass  # 可以添加额外的逻辑

    def _on_output_directory_selected(self, directory: str) -> None:
        """处理输出目录选择事件"""
        pass  # 可以添加额外的逻辑

    def _on_options_changed(self, options: Dict[str, bool]) -> None:
        """处理选项变更事件"""
        pass  # 可以添加额外的逻辑
