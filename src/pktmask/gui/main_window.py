#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Main window module
Implements graphical interface
"""

import os
import sys
import json
import markdown
from datetime import datetime
from typing import Optional, List, Tuple
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QProgressBar, QTextEdit, QFileDialog,
    QMessageBox, QScrollArea, QSplitter, QTableWidget, QTableWidgetItem,
    QTabWidget, QFrame, QDialog, QCheckBox, QGridLayout, QGroupBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject, QEvent, QTimer, QTime, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont, QIcon, QTextCursor, QFontMetrics, QColor, QAction

# Refactored imports
from pktmask.core.events import PipelineEvents
from pktmask.utils.path import resource_path
from pktmask.common.constants import UIConstants, FormatConstants, SystemConstants, PROCESS_DISPLAY_NAMES
from pktmask.utils import current_timestamp, format_milliseconds_to_time, open_directory_in_system, current_time
from pktmask.infrastructure.logging import get_logger
from pktmask.config import get_app_config
from .stylesheet import generate_stylesheet

# PROCESS_DISPLAY_NAMES moved to common.constants

class GuideDialog(QDialog):
    """处理指南对话框"""
    def __init__(self, title: str, content: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{title} - Guide")
        self.setMinimumSize(UIConstants.GUIDE_DIALOG_MIN_WIDTH, UIConstants.GUIDE_DIALOG_MIN_HEIGHT)
        layout = QVBoxLayout(self)
        content_text = QTextEdit()
        content_text.setReadOnly(True)
        content_text.setHtml(markdown.markdown(content))
        layout.addWidget(content_text)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

class PipelineThread(QThread):
    """
    A unified thread to run processing pipeline.
    It sends structured progress data to main thread through signals.

    @deprecated: This class is deprecated, please use ServicePipelineThread instead
    """
    progress_signal = pyqtSignal(PipelineEvents, dict)

    def __init__(self, pipeline, base_dir: str, output_dir: str):
        import warnings
        warnings.warn(
            "PipelineThread is deprecated. Use ServicePipelineThread instead.",
            DeprecationWarning,
            stacklevel=2
        )
        super().__init__()
        self._pipeline = pipeline
        self._base_dir = base_dir
        self._output_dir = output_dir
        self.is_running = True

    def run(self):
        try:
            self._pipeline.run(self._base_dir, self._output_dir, progress_callback=self.handle_progress)
        except Exception as e:
            self.progress_signal.emit(PipelineEvents.ERROR, {'message': str(e)})

    def handle_progress(self, event_type: PipelineEvents, data: dict):
        if not self.is_running:
            # Should ideally stop the pipeline gracefully
            return
        self.progress_signal.emit(event_type, data)

    def stop(self):
        self.is_running = False
        if self._pipeline:
            self._pipeline.stop()
        # Send stop log and end event to trigger UI recovery
        self.progress_signal.emit(PipelineEvents.LOG, {'message': '--- Pipeline Stopped by User ---'})
        self.progress_signal.emit(PipelineEvents.PIPELINE_END, {})

class ServicePipelineThread(QThread):
    """
    Processing thread using service interface.
    """
    progress_signal = pyqtSignal(PipelineEvents, dict)

    def __init__(self, executor: object, base_dir: str, output_dir: str):
        super().__init__()
        self._executor = executor
        self._base_dir = base_dir
        self._output_dir = output_dir
        self.is_running = True

    def run(self):
        try:
            from pktmask.services.pipeline_service import process_directory
            process_directory(
                self._executor,
                self._base_dir,
                self._output_dir,
                progress_callback=self.progress_signal.emit,
                is_running_check=lambda: self.is_running
            )
        except Exception as e:
            from pktmask.services.pipeline_service import PipelineServiceError
            if isinstance(e, PipelineServiceError):
                self.progress_signal.emit(PipelineEvents.ERROR, {'message': str(e)})
            else:
                self.progress_signal.emit(PipelineEvents.ERROR, {'message': f'Unexpected error: {str(e)}'})

    def stop(self):
        self.is_running = False
        self.progress_signal.emit(PipelineEvents.LOG, {'message': '--- Pipeline Stopped by User ---'})
        from pktmask.services.pipeline_service import stop_pipeline
        stop_pipeline(self._executor)
        self.progress_signal.emit(PipelineEvents.PIPELINE_END, {})

class MainWindow(QMainWindow):
    """Main window"""
    
    # 定义信号
    error_occurred = pyqtSignal(str)  # 错误发生信号，用于自动化测试
    
    def __init__(self):
        super().__init__()
        self._logger = get_logger('main_window')
        
        # Initialize configuration manager
        self.config = get_app_config()
        
        # 注册配置变更回调 (简化版本暂时移除复杂的回调机制)
        
        # 基本属性
        self.base_dir: Optional[str] = None
        self.output_dir: Optional[str] = None  # 新增：输出目录
        self.current_output_dir: Optional[str] = None  # 新增：当前处理的输出目录
        
        # 使用配置中的目录设置
        self.last_opened_dir = self.config.ui.last_input_dir or os.path.join(os.path.expanduser("~"), "Desktop")
        self.allowed_root = os.path.expanduser("~")
        
        # 时间相关属性（由PipelineManager管理，但需要在这里声明以保持兼容性）
        self.time_elapsed = 0
        self.timer: Optional[QTimer] = None
        
        # 基本属性（不依赖管理器）
        self.start_time: Optional[QTime] = None
        self.user_stopped = False  # 用户停止标志

        
        # 先初始化管理器
        self._init_managers()
        
        # 初始化遗留属性（现在可以安全使用属性访问器）
        self._init_legacy_attributes()
        
        # 初始化UI
        self.ui_manager.init_ui()
        
        self._logger.info("PktMask main window initialization completed")
    
    def _init_managers(self):
        """初始化所有管理器"""
        # 导入管理器类
        from .managers import UIManager, FileManager, PipelineManager, ReportManager, DialogManager, EventCoordinator
        
        # 首先创建事件协调器
        self.event_coordinator = EventCoordinator(self)
        
        # 创建管理器实例
        self.ui_manager = UIManager(self)
        self.file_manager = FileManager(self)
        self.pipeline_manager = PipelineManager(self)
        self.report_manager = ReportManager(self)
        self.dialog_manager = DialogManager(self)
        
        # Setup inter-manager event subscriptions
        self._setup_manager_subscriptions()
        
        self._logger.debug("All managers initialization completed")
    def _setup_manager_subscriptions(self):
        """设置管理器间的订阅关系"""
        # 订阅统计更新
        self.event_coordinator.subscribe('statistics_changed', self._handle_statistics_update)
        
        # 订阅UI更新请求
        self.event_coordinator.subscribe('ui_state_changed', self._handle_ui_update_request)
        
        # 新增：订阅结构化数据事件
        self.event_coordinator.subscribe('pipeline_event', self._handle_pipeline_event_data)
        self.event_coordinator.subscribe('statistics_data', self._handle_statistics_data)
        
        # 连接Qt信号
        self.event_coordinator.statistics_updated.connect(self._handle_statistics_update)
        self.event_coordinator.ui_update_requested.connect(lambda action, data: self._handle_ui_update_request(action, data))
        
        # 新增：连接结构化数据信号（如果可用）
        if hasattr(self.event_coordinator, 'pipeline_event_data'):
            self.event_coordinator.pipeline_event_data.connect(self._handle_pipeline_event_data)
        if hasattr(self.event_coordinator, 'statistics_data_updated'):
            self.event_coordinator.statistics_data_updated.connect(self._handle_statistics_data)

#    def _setup_manager_subscriptions(self):
#        """设置管理器间的事件订阅关系"""
        # UI管理器订阅统计变化
#        self.event_coordinator.subscribe('statistics_changed', self._handle_statistics_update)
        
#        # 连接Qt信号
#        self.event_coordinator.ui_update_requested.connect(self._handle_ui_update_request)
#        self._logger.debug("Manager event subscription setup completed")
    
    def _handle_statistics_update(self, data: dict):
        """处理统计数据更新"""
        action = data.get('action', 'update')
        if action == 'reset':
            # **修复**: 检查是否正在处理中，只有在开始新处理时才重置Live Dashboard显示
            # 避免在处理完成后重置显示导致统计数据丢失
            if hasattr(self, 'pipeline_manager') and self.pipeline_manager.processing_thread is None:
                # 只有在没有处理线程运行时才重置显示（即开始新处理时）
                self.files_processed_label.setText("0")
                self.packets_processed_label.setText("0")
                self.time_elapsed_label.setText("00:00.00")
                self.progress_bar.setValue(0)
            # 如果正在处理或刚完成处理，保持当前显示不变
        else:
            # 更新UI显示
            stats = self.event_coordinator.get_statistics_data()
            if stats:
                self.files_processed_label.setText(str(stats.get('files_processed', 0)))
                self.packets_processed_label.setText(str(stats.get('packets_processed', 0)))
                self.time_elapsed_label.setText(stats.get('elapsed_time', '00:00.00'))
    
    def _handle_ui_update_request(self, action: str, data: dict = None):
        """处理UI更新请求"""
        if data is None:
            data = {}

        if action == 'enable_controls':
            controls = data.get('controls', [])
            enabled = data.get('enabled', True)
            for control_name in controls:
                if hasattr(self, control_name):
                    getattr(self, control_name).setEnabled(enabled)
        elif action == 'update_button_text':
            button_name = data.get('button', '')
            text = data.get('text', '')
            if hasattr(self, button_name):
                getattr(self, button_name).setText(text)
    
    def _handle_pipeline_event_data(self, event_data):
        """处理结构化管道事件数据"""
        try:
            from pktmask.domain.models.pipeline_event_data import PipelineEventData
            from pktmask.core.events import PipelineEvents
        except ImportError:
            self._logger.warning("Unable to import structured data model, skipping structured processing")
            return
        
        if isinstance(event_data, PipelineEventData):
            self._logger.debug(f"Received structured event: {event_data.event_type} - {type(event_data.data).__name__}")
            
            # 可以在这里添加基于新数据模型的增强处理逻辑
            # 例如：更详细的日志、更精确的UI更新、数据验证等
            
            if hasattr(event_data.data, 'message') and event_data.data.message:
                self._logger.info(f"Event message: {event_data.data.message}")
            
            # 可以根据事件类型执行特定的增强处理
            if event_data.event_type == PipelineEvents.FILE_START:
                if hasattr(event_data.data, 'size_bytes') and event_data.data.size_bytes:
                    self._logger.info(f"Started processing file, size: {event_data.data.size_bytes} bytes")
            
            elif event_data.event_type == PipelineEvents.STEP_SUMMARY:
                if hasattr(event_data.data, 'result'):
                    self._logger.debug(f"Step result: {event_data.data.result}")
        else:
            self._logger.warning(f"Received unstructured event data: {type(event_data)}")
    
    def _handle_statistics_data(self, stats_data):
        """处理结构化统计数据"""
        try:
            from pktmask.domain.models.statistics_data import StatisticsData
        except ImportError:
            self._logger.warning("Unable to import statistics data model, skipping structured processing")
            return
        
        if isinstance(stats_data, StatisticsData):
            self._logger.debug(f"Received structured statistics data: {stats_data.metrics.files_processed} files, {stats_data.metrics.packets_processed} packets")
            
            # 基于新数据模型的增强统计处理
            # 可以实现更精确的性能监控、数据验证等
            
            # 获取性能指标
            completion_rate = stats_data.metrics.get_completion_rate()
            processing_speed = stats_data.timing.get_processing_speed(stats_data.metrics.packets_processed)
            
            if completion_rate > 0:
                self._logger.info(f"Processing progress: {completion_rate:.1f}%")
            
            if processing_speed > 0:
                self._logger.info(f"Processing speed: {processing_speed:.1f} packets/sec")
            
            # 可以在这里添加实时性能监控、异常检测等功能
            
        else:
            self._logger.warning(f"Received unstructured statistics data: {type(stats_data)}")
    
    def _on_config_changed(self, new_config):
        """配置变更回调"""
        self.config = new_config
        self._logger.info("Configuration updated, reapplying settings")
        
        # 更新窗口尺寸（如果需要）
        current_size = self.size()
        if (current_size.width() != new_config.ui.window_width or 
            current_size.height() != new_config.ui.window_height):
            self.resize(new_config.ui.window_width, new_config.ui.window_height)
        
        # 重新应用样式表
        self._apply_stylesheet()
    
    def save_window_state(self):
        """保存窗口状态到配置"""
        current_size = self.size()
        self.config.ui.window_width = current_size.width()
        self.config.ui.window_height = current_size.height()
        self.config.save()
    
    def save_user_preferences(self):
        """保存用户偏好设置"""
        # 保存处理选项的默认状态
        self.config.ui.default_remove_dupes = self.remove_dupes_cb.isChecked()
        self.config.ui.default_anonymize_ips = self.anonymize_ips_cb.isChecked()
        self.config.ui.default_mask_payloads = self.mask_payloads_cb.isChecked()
        
        # 保存最后使用的目录
        if self.base_dir and self.config.ui.remember_last_dir:
            self.config.ui.last_input_dir = self.base_dir
            
        self.config.save()
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        # 保存窗口状态和用户偏好
        self.save_window_state()
        self.save_user_preferences()
        
        # 停止处理线程
        processing_thread = getattr(self.pipeline_manager, 'processing_thread', None)
        if processing_thread and processing_thread.isRunning():
            self.stop_pipeline_processing()
            processing_thread.wait(3000)  # 等待最多3秒
        
        # 关闭事件协调器
        if hasattr(self, 'event_coordinator'):
            self.event_coordinator.shutdown()
        
        # 取消注册配置回调 (简化版本暂时移除)
        
        event.accept()

    def init_ui(self):
        """初始化界面（委托给UIManager处理）"""
        self.ui_manager.init_ui()

    def _get_current_theme(self) -> str:
        """检测当前系统是浅色还是深色模式。"""
        return self.ui_manager.get_current_theme()

    def _apply_stylesheet(self):
        """应用当前主题的样式表。"""
        self.ui_manager.apply_stylesheet()

    def changeEvent(self, event: QEvent):
        """重写changeEvent来监听系统主题变化。"""
        self.ui_manager.handle_theme_change(event)
        super().changeEvent(event)

    def create_menu_bar(self):
        """创建菜单栏（由UIManager处理）"""
        pass  # 已由UIManager在init_ui中处理

    def show_user_guide_dialog(self):
        """显示用户指南对话框"""
        self.dialog_manager.show_user_guide_dialog()

    def show_initial_guides(self):
        """启动时在log和report区域显示指引（由UIManager处理）"""
        pass  # 已由UIManager在init_ui中处理

    def choose_folder(self):
        """选择目录"""
        self.file_manager.choose_folder()

    def handle_output_click(self):
        """处理输出路径按钮点击"""
        self.file_manager.handle_output_click()

    def choose_output_folder(self):
        """选择自定义输出目录"""
        self.file_manager.choose_output_folder()

    def generate_default_output_path(self):
        """生成默认输出路径预览"""
        self.file_manager.generate_default_output_path()

    def generate_actual_output_path(self) -> str:
        """生成实际的输出目录路径"""
        return self.file_manager.generate_actual_output_path()

    def open_output_directory(self):
        """打开输出目录"""
        self.file_manager.open_output_directory()

    def reset_state(self):
        """重置所有状态和UI"""
        self.base_dir = None
        self.output_dir = None  # 重置输出目录
        self.current_output_dir = None  # 重置当前输出目录
        self.dir_path_label.setText("Click and pick your pcap directory")
        self.output_path_label.setText("Auto-create or click for custom")  # 重置输出路径显示
        self.log_text.clear()
        self.summary_text.clear()
        
        # 使用事件协调器统一重置所有数据
        self.event_coordinator.reset_all_data()
        
        # 使用StatisticsManager统一重置所有统计数据
        self.pipeline_manager.statistics.reset_all_statistics()
        
        # 重置Live Dashboard显示
        self.files_processed_label.setText("0")
        self.packets_processed_label.setText("0")
        self.time_elapsed_label.setText("00:00.00")
        self.progress_bar.setValue(0)
        
        # 重置其他状态
        self.user_stopped = False            # 重置停止标志
        if hasattr(self, '_current_file_ips'):
            self._current_file_ips.clear()    # 清空文件IP映射
        if hasattr(self, '_counted_files'):
            self._counted_files.clear()      # 清空包计数缓存
        
        # 停止计时器
        if self.timer and self.timer.isActive():
            self.timer.stop()
        
        # 重置按钮和显示状态
        self.start_proc_btn.setEnabled(False)  # 保持禁用状态，直到选择目录
        self.start_proc_btn.setText("Start")
        self.show_initial_guides()

    def toggle_pipeline_processing(self):
        """根据当前状态切换处理开始/停止"""
        self.pipeline_manager.toggle_pipeline_processing()

    def generate_partial_summary_on_stop(self):
        """生成用户停止时的部分汇总统计（委托给ReportManager）"""
        self.report_manager.generate_partial_summary_on_stop()

    def stop_pipeline_processing(self):
        """停止管道处理（委托给PipelineManager）"""
        self.pipeline_manager.stop_pipeline_processing()

    def start_pipeline_processing(self):
        """开始管道处理（委托给PipelineManager）"""
        self.pipeline_manager.start_pipeline_processing()



    def handle_thread_progress(self, event_type: PipelineEvents, data: dict):
        """主槽函数，根据事件类型分发UI更新任务"""
        # 使用EventCoordinator发布结构化事件数据
        if hasattr(self, 'event_coordinator'):
            self.event_coordinator.emit_pipeline_event(event_type, data)
        
        # 保持原有的UI更新逻辑
        if event_type == PipelineEvents.PIPELINE_START:
            # Initialize progress bar to 0, maximum will be set when we know the actual file count
            self.progress_bar.setValue(0)
            self.progress_bar.setMaximum(100)  # Set to 100 for percentage-based progress
        
        elif event_type == PipelineEvents.SUBDIR_START:
            # Reset progress bar to 0% when starting directory processing
            self.progress_bar.setValue(0)
            self.update_log(f"Processing directory: {data.get('name', 'N/A')}")
        
        elif event_type == PipelineEvents.FILE_START:
            # 不在这里递增文件计数，应该在FILE_END时递增
            file_path = data['path']
            self.current_processing_file = os.path.basename(file_path)
            self.update_log(f"Processing file: {self.current_processing_file}")
            
            # 初始化当前文件的处理结果记录
            if self.current_processing_file not in self.file_processing_results:
                self.file_processing_results[self.current_processing_file] = {'steps': {}}

        elif event_type == PipelineEvents.FILE_END:
            if self.current_processing_file:
                # **修复**: 增加处理完成的文件计数
                self.processed_files_count += 1
                
                # 获取输出文件名信息
                output_files = []
                if self.current_processing_file in self.file_processing_results:
                    steps_data = self.file_processing_results[self.current_processing_file]['steps']
                    step_order = ['Deduplication', 'IP Anonymization', 'Payload Masking']
                    for step_name in reversed(step_order):
                        if step_name in steps_data:
                            output_file = steps_data[step_name]['data'].get('output_filename')
                            if output_file:
                                output_files.append(output_file)
                                break
                
                finish_msg = f"Finished file: {self.current_processing_file}"
                if output_files:
                    finish_msg += f" → Output: {output_files[0]}"
                self.update_log(finish_msg)
                
                # 生成当前文件的完整报告
                self.generate_file_complete_report(self.current_processing_file)
                self.current_processing_file = None

        elif event_type == PipelineEvents.PACKETS_SCANNED:
            count = data.get('count', 0)
            if count > 0:
                self.pipeline_manager.statistics.add_packet_count(count)
                self.packets_processed_label.setText(str(self.pipeline_manager.statistics.packets_processed))

        elif event_type == PipelineEvents.LOG:
            self.update_log(data['message'])

        elif event_type == PipelineEvents.STEP_SUMMARY:
            # **修复**: 简化包计数逻辑，只从第一个Stage（去重阶段）计算包数，避免重复计算
            step_name = data.get('step_name', '')
            packets_processed = data.get('packets_processed', 0)
            # **修复**: 如果packets_processed为0，尝试使用total_packets字段
            if packets_processed == 0:
                packets_processed = data.get('total_packets', 0)
            current_file = data.get('filename', '')

            # 只从去重阶段计算包数（它总是第一个运行的Stage）
            # **修复**: 支持新旧两种Stage名称，并且只要有包数就计算（不要求>0）
            if (step_name in ['DedupStage', 'DeduplicationStage']) and packets_processed >= 0:
                # 检查这个文件是否已经计算过包数
                if not hasattr(self, '_counted_files'):
                    self._counted_files = set()
                if current_file not in self._counted_files:
                    self._counted_files.add(current_file)
                    # Use StatisticsManager's add_packet_count method to properly accumulate
                    self.pipeline_manager.statistics.add_packet_count(packets_processed)
                    # Update UI display
                    self.packets_processed_label.setText(str(self.pipeline_manager.statistics.packets_processed))
                    self._logger.debug(f"Updated packet count: file={current_file}, packets={packets_processed}, total={self.pipeline_manager.statistics.packets_processed}")
            
            self.collect_step_result(data)

        elif event_type == PipelineEvents.PIPELINE_END:
            self._animate_progress_to(100)  # 动画到100%
            # 注意：处理完成的逻辑由 PipelineManager 负责处理
            
        elif event_type == PipelineEvents.ERROR:
            self.processing_error(data['message'])

    def collect_step_result(self, data: dict):
        """收集每个步骤的处理结果（委托给ReportManager）"""
        self.report_manager.collect_step_result(data)

    def generate_file_complete_report(self, original_filename: str):
        """为单个文件生成完整的处理报告（委托给ReportManager）"""
        self.report_manager.generate_file_complete_report(original_filename)

    def update_summary_report(self, data: dict):
        """更新摘要报告（委托给ReportManager）"""
        self.report_manager.update_summary_report(data)

    def set_final_summary_report(self, report: dict):
        """设置最终汇总报告（委托给ReportManager）"""
        self.report_manager.set_final_summary_report(report)

    def update_log(self, message: str):
        """更新日志显示"""
        self.report_manager.update_log(message)

    def processing_finished(self):
        """处理完成（委托给PipelineManager）"""
        self.pipeline_manager.processing_finished()

    def processing_error(self, error_message: str):
        """处理错误"""
        self.dialog_manager.show_processing_error(error_message)
        self.processing_finished()

    def on_thread_finished(self):
        """线程完成时的回调函数，确保UI状态正确恢复"""
        # 线程清理现在由PipelineManager处理
        pass

    def get_elided_text(self, label: QLabel, text: str) -> str:
        """如果文本太长，则省略文本"""
        fm = label.fontMetrics()
        elided_text = fm.elidedText(text, Qt.TextElideMode.ElideMiddle, label.width())
        return elided_text

    def resizeEvent(self, event):
        """处理窗口大小调整事件以更新省略的文本"""
        super().resizeEvent(event)
        if self.base_dir:
            self.dir_path_label.setText(self.get_elided_text(self.dir_path_label, self.base_dir))

    def show_about_dialog(self):
        """显示关于对话框"""
        self.dialog_manager.show_about_dialog()

    def update_time_elapsed(self):
        if not self.start_time:
            return
        
        elapsed_msecs = self.start_time.msecsTo(QTime.currentTime())
        time_str = format_milliseconds_to_time(elapsed_msecs)
        self.time_elapsed_label.setText(time_str)

    def generate_summary_report_filename(self) -> str:
        """生成带有处理选项标识的summary report文件名"""
        
        # 生成处理选项标识
        enabled_steps = []
        if self.anonymize_ips_cb.isChecked():
            enabled_steps.append("AnonymizeIPs")
        if self.remove_dupes_cb.isChecked():
            enabled_steps.append("RemoveDupes")
        if self.mask_payloads_cb.isChecked():
            enabled_steps.append("MaskPayloads")
        
        steps_suffix = "_".join(enabled_steps) if enabled_steps else "NoSteps"
        timestamp = current_timestamp()
        
        return f"summary_report_{steps_suffix}_{timestamp}.txt"

    def save_summary_report_to_output_dir(self):
        """将summary report保存到输出目录"""
        if not self.current_output_dir:
            return
        
        try:
            filename = self.generate_summary_report_filename()
            file_path = os.path.join(self.current_output_dir, filename)
            
            # 获取summary text的内容
            summary_content = self.summary_text.toPlainText()
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write("# PktMask Summary Report\n")
                f.write(f"# Generated: {current_time()}\n")
                f.write(f"# Working Directory: {self.current_output_dir}\n")
                f.write("#" + "="*68 + "\n\n")
                f.write(summary_content)
            
            self.update_log(f"Summary report saved: {filename}")
            
        except Exception as e:
            self.update_log(f"Error saving summary report: {str(e)}")

    def find_existing_summary_reports(self) -> List[str]:
        """Find existing summary report files in working directory"""
        if not self.current_output_dir or not os.path.exists(self.current_output_dir):
            return []
        
        try:
            files = os.listdir(self.current_output_dir)
            summary_files = [f for f in files if f.startswith('summary_report_') and f.endswith('.txt')]
            # 按修改时间倒序排列，最新的在前
            summary_files.sort(key=lambda x: os.path.getmtime(os.path.join(self.current_output_dir, x)), reverse=True)
            return summary_files
        except Exception:
            return []

    def load_latest_summary_report(self) -> Optional[str]:
        """加载最新的summary report内容"""
        summary_files = self.find_existing_summary_reports()
        if not summary_files:
            return None
        
        try:
            latest_file = summary_files[0]
            file_path = os.path.join(self.current_output_dir, latest_file)
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 移除文件头部的注释行
            lines = content.split('\n')
            content_lines = []
            skip_header = True
            
            for line in lines:
                if skip_header and line.startswith('#'):
                    continue
                elif skip_header and line.strip() == '':
                    continue
                else:
                    skip_header = False
                    content_lines.append(line)
            
            return '\n'.join(content_lines)
            
        except Exception as e:
            self.update_log(f"Error loading summary report: {str(e)}")
            return None

    def _get_path_link_style(self) -> str:
        """根据当前主题生成路径链接样式（由UIManager处理）"""
        return self.ui_manager._get_path_link_style()

    def _update_path_link_styles(self):
        """更新路径链接的样式"""
        self.ui_manager._update_path_link_styles()

    def _animate_progress_to(self, target_value: int):
        """平滑动画到目标进度值"""
        if self.progress_animation.state() == QPropertyAnimation.State.Running:
            self.progress_animation.stop()
        
        current_value = self.progress_bar.value()
        self.progress_animation.setStartValue(current_value)
        self.progress_animation.setEndValue(target_value)
        self.progress_animation.start()

    def _update_start_button_state(self):
        """根据输入目录和选项状态更新Start按钮"""
        self.ui_manager._update_start_button_state()

    def _get_start_button_style(self) -> str:
        """根据当前主题生成Start按钮样式（由UIManager处理）"""
        return self.ui_manager._get_start_button_style()

    def _update_start_button_style(self):
        """更新Start按钮样式"""
        self.ui_manager._update_start_button_style()



    # === 统计数据兼容性属性访问器 ===
    @property
    def files_processed_count(self):
        """已处理文件数（兼容性访问器）"""
        return self.pipeline_manager.statistics.files_processed
    
    @files_processed_count.setter
    def files_processed_count(self, value):
        """已处理文件数设置器（兼容性访问器）"""
        self.pipeline_manager.statistics.update_file_count(value)
    
    @property
    def packets_processed_count(self):
        """已处理包数（兼容性访问器）"""
        return self.pipeline_manager.statistics.packets_processed
    
    @packets_processed_count.setter
    def packets_processed_count(self, value):
        """已处理包数设置器（兼容性访问器）"""
        self.pipeline_manager.statistics.update_packet_count(value)
    
    @property
    def file_processing_results(self):
        """文件处理结果（兼容性访问器）"""
        return self.pipeline_manager.statistics.file_processing_results
    
    @file_processing_results.setter
    def file_processing_results(self, value):
        """文件处理结果设置器（兼容性访问器）"""
        self.pipeline_manager.statistics.file_processing_results = value
    
    @property
    def global_ip_mappings(self):
        """全局IP映射（兼容性访问器）"""
        return self.pipeline_manager.statistics.global_ip_mappings
    
    @global_ip_mappings.setter
    def global_ip_mappings(self, value):
        """全局IP映射设置器（兼容性访问器）"""
        self.pipeline_manager.statistics.global_ip_mappings = value
    
    @property
    def all_ip_reports(self):
        """所有IP报告（兼容性访问器）"""
        return self.pipeline_manager.statistics.all_ip_reports
    
    @all_ip_reports.setter
    def all_ip_reports(self, value):
        """所有IP报告设置器（兼容性访问器）"""
        self.pipeline_manager.statistics.all_ip_reports = value
    
    @property
    def processed_files_count(self):
        """已处理文件计数（兼容性访问器）"""
        return self.pipeline_manager.statistics.processed_files_count
    
    @processed_files_count.setter
    def processed_files_count(self, value):
        """已处理文件计数设置器（兼容性访问器）"""
        self.pipeline_manager.statistics.processed_files_count = value
    
    @property
    def current_processing_file(self):
        """当前处理文件（兼容性访问器）"""
        return self.pipeline_manager.statistics.current_processing_file
    
    @current_processing_file.setter
    def current_processing_file(self, value):
        """当前处理文件设置器（兼容性访问器）"""
        self.pipeline_manager.statistics.set_current_processing_file(value)
    
    @property
    def subdirs_files_counted(self):
        """子目录文件计数（兼容性访问器）"""
        return self.pipeline_manager.statistics.subdirs_files_counted
    
    @subdirs_files_counted.setter
    def subdirs_files_counted(self, value):
        """子目录文件计数设置器（兼容性访问器）"""
        self.pipeline_manager.statistics.subdirs_files_counted = value
    
    @property
    def subdirs_packets_counted(self):
        """子目录包计数（兼容性访问器）"""
        return self.pipeline_manager.statistics.subdirs_packets_counted
    
    @subdirs_packets_counted.setter
    def subdirs_packets_counted(self, value):
        """子目录包计数设置器（兼容性访问器）"""
        self.pipeline_manager.statistics.subdirs_packets_counted = value
    
    @property
    def printed_summary_headers(self):
        """已打印摘要头（兼容性访问器）"""
        return self.pipeline_manager.statistics.printed_summary_headers
    
    @printed_summary_headers.setter
    def printed_summary_headers(self, value):
        """已打印摘要头设置器（兼容性访问器）"""
        self.pipeline_manager.statistics.printed_summary_headers = value

    def _init_legacy_attributes(self):
        """初始化遗留属性（使用StatisticsManager）"""
        # 通过属性访问器初始化，确保数据存储在StatisticsManager中
        self.all_ip_reports = {}
        self.files_processed_count = 0
        self.packets_processed_count = 0
        self.subdirs_files_counted = set()
        self.subdirs_packets_counted = set()
        self.printed_summary_headers = set()
        self.file_processing_results = {}
        self.current_processing_file = None
        self.global_ip_mappings = {}
        self.processed_files_count = 0

    def set_test_mode(self, enabled: bool = True):
        """设置测试模式（用于自动化测试）"""
        self._test_mode = enabled
        if enabled:
            self._logger.info("Test mode enabled - dialogs will be handled automatically")
        else:
            self._logger.info("Test mode disabled")
        return self

def main():
    """主函数"""
    import os
    
    # 检查是否在测试模式或无头模式
    test_mode = os.getenv('PKTMASK_TEST_MODE', '').lower() in ('true', '1', 'yes')
    headless_mode = os.getenv('PKTMASK_HEADLESS', '').lower() in ('true', '1', 'yes')
    
    if test_mode or headless_mode:
        # 测试模式：创建应用但不显示窗口和进入事件循环
        try:
            app = QApplication.instance()
            if app is None:
                app = QApplication(sys.argv)
            
            # 在测试模式下创建窗口但不显示
            window = MainWindow()
            if hasattr(window, 'set_test_mode'):
                window.set_test_mode(True)
            
            # 测试模式下立即返回，不进入事件循环
            return window if test_mode else 0
            
        except Exception as e:
            print(f"GUI initialization failed in test mode: {e}")
            return None
    else:
        # 正常模式：完整的GUI启动
        app = QApplication(sys.argv)
        window = MainWindow()
        window.show()
        sys.exit(app.exec()) 