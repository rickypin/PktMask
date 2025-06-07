#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
主窗口模块
实现图形界面
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
from pktmask.core.pipeline import Pipeline
from pktmask.core.events import PipelineEvents
from pktmask.core.factory import get_step_instance
from pktmask.utils.path import resource_path
from .stylesheet import generate_stylesheet

PROCESS_DISPLAY_NAMES = {
    "mask_ip": "Mask IP",
    "dedup_packet": "Remove Dupes",
    "trim_packet": "Trim Packet"
}

class GuideDialog(QDialog):
    """处理指南对话框"""
    def __init__(self, title: str, content: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{title} - Guide")
        self.setMinimumSize(700, 500)
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
    一个统一的线程来运行处理流水线。
    它通过信号将结构化的进度数据发送到主线程。
    """
    progress_signal = pyqtSignal(PipelineEvents, dict)

    def __init__(self, pipeline: Pipeline, base_dir: str, output_dir: str):
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
        # 发送停止日志和结束事件来触发 UI 恢复
        self.progress_signal.emit(PipelineEvents.LOG, {'message': '--- Pipeline Stopped by User ---'})
        self.progress_signal.emit(PipelineEvents.PIPELINE_END, {})

class MainWindow(QMainWindow):
    """主窗口"""
    def __init__(self):
        super().__init__()
        self.pipeline_thread: Optional[PipelineThread] = None
        self.all_ip_reports = {}  # subdir -> report_data
        self.base_dir: Optional[str] = None
        self.output_dir: Optional[str] = None  # 新增：输出目录
        self.current_output_dir: Optional[str] = None  # 新增：当前处理的输出目录
        self.last_opened_dir = os.path.join(os.path.expanduser("~"), "Desktop")
        self.allowed_root = os.path.expanduser("~")
        
        # KPI counters
        self.files_processed_count = 0
        self.packets_processed_count = 0
        self.timer: Optional[QTimer] = None
        self.start_time: Optional[QTime] = None
        self.subdirs_files_counted = set()
        self.subdirs_packets_counted = set()
        self.printed_summary_headers = set()
        
        # 文件处理追踪 - 按原始文件分组报告
        self.file_processing_results = {}  # original_file -> {steps: {step_name: result_data}}
        self.current_processing_file = None  # 当前正在处理的原始文件
        self.global_ip_mappings = {}  # 全局IP映射汇总
        self.processed_files_count = 0  # 已处理文件计数
        self.user_stopped = False  # 用户停止标志

        self.init_ui()
        self._apply_stylesheet() # 应用初始样式

    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle("PktMask")
        self.setGeometry(100, 100, 1200, 800)
        self.setWindowIcon(QIcon(resource_path('icon.png')))

        # Create Menu Bar
        self.create_menu_bar()

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        main_layout = QGridLayout(main_widget)
        main_layout.setSpacing(18)  # 增加整体间距，让各区域有足够的空白
        main_layout.setContentsMargins(15, 15, 15, 15)  # 增加外边距

        # --- Create all GroupBox widgets first ---

        # Step 1: Input and Output (左右分布) - 简化版
        dirs_group = QGroupBox("Set Working Directories")
        dirs_group.setMaximumHeight(100)  # 减少高度，因为去掉了额外的标题行
        dirs_layout = QHBoxLayout(dirs_group)
        dirs_layout.setContentsMargins(15, 12, 15, 12)  # 增加内边距
        
        # 左侧：Input Directory - 单行布局
        input_layout = QVBoxLayout()
        input_layout.setSpacing(5)  # 增加间距
        input_label = QLabel("Input:")
        input_label.setMaximumHeight(20)
        input_path_layout = QHBoxLayout()
        input_path_layout.setSpacing(8)
        self.dir_path_label = QPushButton("No directory selected.")  # 改为可点击的按钮
        self.dir_path_label.setObjectName("DirPathLabel")
        self.dir_path_label.setMaximumHeight(30)
        self.dir_path_label.setCursor(Qt.CursorShape.PointingHandCursor)  # 设置手型光标
        input_path_layout.addWidget(input_label)
        input_path_layout.addWidget(self.dir_path_label, 1)
        input_layout.addLayout(input_path_layout)
        
        # 右侧：Output Directory - 单行布局
        output_layout = QVBoxLayout()
        output_layout.setSpacing(5)  # 增加间距，与input保持一致
        output_label = QLabel("Output:")
        output_label.setMaximumHeight(20)
        output_path_layout = QHBoxLayout()
        output_path_layout.setSpacing(8)
        self.output_path_label = QPushButton("Output will be generated")  # 改为可点击的按钮
        self.output_path_label.setObjectName("DirPathLabel")
        self.output_path_label.setMaximumHeight(30)
        self.output_path_label.setCursor(Qt.CursorShape.PointingHandCursor)  # 设置手型光标
        output_path_layout.addWidget(output_label)
        output_path_layout.addWidget(self.output_path_label, 1)
        output_layout.addLayout(output_path_layout)
        
        dirs_layout.addLayout(input_layout, 1)
        dirs_layout.addLayout(output_layout, 1)

        # Step 2 & 3: 第二行并排布局 - 适度压缩
        row2_widget = QWidget()
        row2_widget.setMaximumHeight(90)  # 适度增加高度
        row2_layout = QHBoxLayout(row2_widget)
        row2_layout.setContentsMargins(0, 0, 0, 0)  # 保持无外边距
        row2_layout.setSpacing(12)  # 增加Step 2和Step 3之间的间距
        
        # Step 2: Configure Pipeline (3/4 宽度，横向布局)
        pipeline_group = QGroupBox("Set Options")
        pipeline_group.setMaximumHeight(85)  # 适度增加高度
        pipeline_layout = QHBoxLayout(pipeline_group)  # 改为水平布局
        pipeline_layout.setContentsMargins(15, 12, 15, 12)  # 增加内边距
        pipeline_layout.setSpacing(20)  # 增加选项之间的间距
        self.mask_ip_cb = QCheckBox("Mask IPs")
        self.dedup_packet_cb = QCheckBox("Remove Dupes")
        self.trim_packet_cb = QCheckBox("Trim Payloads (Preserve TLS Handshake)")
        self.trim_packet_cb.setToolTip("Intelligently trims packet payloads while preserving TLS handshake data.")
        # 为所有checkbox设置手型光标
        self.mask_ip_cb.setCursor(Qt.CursorShape.PointingHandCursor)
        self.dedup_packet_cb.setCursor(Qt.CursorShape.PointingHandCursor)
        self.trim_packet_cb.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mask_ip_cb.setChecked(True)
        self.dedup_packet_cb.setChecked(True)
        self.trim_packet_cb.setChecked(True)
        pipeline_layout.addWidget(self.mask_ip_cb)
        pipeline_layout.addWidget(self.dedup_packet_cb)
        pipeline_layout.addWidget(self.trim_packet_cb)
        pipeline_layout.addStretch()

        # Step 3: Execute (1/4 宽度) - 简化版
        execute_group = QGroupBox("Run Processing")
        execute_group.setMaximumHeight(85)
        execute_layout = QVBoxLayout(execute_group)
        execute_layout.setContentsMargins(15, 20, 15, 20)  # 增加内边距，上下更多空间
        execute_layout.setSpacing(5)
        self.start_proc_btn = QPushButton("Start")
        self.start_proc_btn.setMinimumHeight(35)  # 稍微增加按钮高度，因为只有一个按钮
        self.start_proc_btn.setMaximumHeight(35)
        self.start_proc_btn.setEnabled(False)  # 初始状态为禁用
        self.start_proc_btn.setCursor(Qt.CursorShape.PointingHandCursor)  # 设置手型光标
        # 应用动态按钮样式
        self._update_start_button_style()
        execute_layout.addWidget(self.start_proc_btn)
        
        row2_layout.addWidget(pipeline_group, 3)  # 3/4 宽度
        row2_layout.addWidget(execute_group, 1)   # 1/4 宽度

        # Live Dashboard - 适度压缩但保持可读性
        dashboard_group = QGroupBox("Live Dashboard")
        dashboard_group.setMaximumHeight(140)  # 适度增加高度
        dashboard_layout = QVBoxLayout(dashboard_group)
        dashboard_layout.setContentsMargins(15, 20, 15, 12)  # 增加标题下方空间
        dashboard_layout.setSpacing(10)  # 增加间距
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(18)  # 与样式表保持一致
        
        # 初始化进度条动画
        self.progress_animation = QPropertyAnimation(self.progress_bar, b"value")
        self.progress_animation.setDuration(300)  # 300ms动画时长
        self.progress_animation.setEasingCurve(QEasingCurve.Type.OutCubic)  # 平滑动画曲线
        
        dashboard_layout.addWidget(self.progress_bar)
        kpi_layout = QGridLayout()
        kpi_layout.setSpacing(10)  # 增加间距
        self.files_processed_label = QLabel("0")
        self.files_processed_label.setObjectName("FilesProcessedLabel")
        self.packets_processed_label = QLabel("0")
        self.packets_processed_label.setObjectName("IpsMaskedLabel") # Re-use for same style
        self.time_elapsed_label = QLabel("00:00.00")
        self.time_elapsed_label.setObjectName("DupesRemovedLabel") # Re-use for same style

        kpi_layout.addWidget(self.files_processed_label, 0, 0, Qt.AlignmentFlag.AlignCenter)
        kpi_layout.addWidget(QLabel("Files Processed"), 1, 0, Qt.AlignmentFlag.AlignCenter)
        kpi_layout.addWidget(self.packets_processed_label, 0, 1, Qt.AlignmentFlag.AlignCenter)
        kpi_layout.addWidget(QLabel("Packets Processed"), 1, 1, Qt.AlignmentFlag.AlignCenter)
        kpi_layout.addWidget(self.time_elapsed_label, 0, 2, Qt.AlignmentFlag.AlignCenter)
        kpi_layout.addWidget(QLabel("Time Elapsed"), 1, 2, Qt.AlignmentFlag.AlignCenter)
        
        dashboard_layout.addLayout(kpi_layout)
        
        # Log - 移除高度限制，让它能有效利用空间
        log_group = QGroupBox("Log")
        # 移除 setMaximumHeight 限制
        log_layout = QVBoxLayout(log_group)
        log_layout.setContentsMargins(12, 20, 12, 12)  # 增加标题下方空间
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)

        # Summary Report
        summary_group = QGroupBox("Summary Report")
        summary_layout = QVBoxLayout(summary_group)
        summary_layout.setContentsMargins(12, 20, 12, 12)  # 增加标题下方空间
        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        summary_layout.addWidget(self.summary_text)

        # --- Add widgets to the grid layout ---
        
        # Row 0: Top controls
        main_layout.addWidget(dirs_group, 0, 0, 1, 2)  # 第一行跨两列
        main_layout.addWidget(row2_widget, 1, 0, 1, 2)  # 第二行跨两列
        
        # Left column contents
        main_layout.addWidget(dashboard_group, 2, 0)
        main_layout.addWidget(log_group, 3, 0)
        
        # Right column contents
        main_layout.addWidget(summary_group, 2, 1, 2, 1) # row, col, rowspan, colspan

        # --- Define stretch factors for the grid ---
        main_layout.setColumnStretch(0, 2)  # 左列：Dashboard + Log
        main_layout.setColumnStretch(1, 3)  # 右列：Summary Report，60%的空间
        
        main_layout.setRowStretch(0, 0)  # Step 1 row - no stretch
        main_layout.setRowStretch(1, 0)  # Step 2&3 row - no stretch  
        main_layout.setRowStretch(2, 0)  # Dashboard row - no stretch
        main_layout.setRowStretch(3, 2)  # Log row - takes more available space

        # Connect signals
        self.dir_path_label.clicked.connect(self.choose_folder)  # 路径按钮直接选择输入目录
        self.output_path_label.clicked.connect(self.handle_output_click)  # 路径按钮处理输出目录操作
        self.start_proc_btn.clicked.connect(self.toggle_pipeline_processing)
        
        # 连接checkbox状态变化信号
        self.mask_ip_cb.stateChanged.connect(self._update_start_button_state)
        self.dedup_packet_cb.stateChanged.connect(self._update_start_button_state)
        self.trim_packet_cb.stateChanged.connect(self._update_start_button_state)
        
        # 应用路径链接样式和按钮样式
        self._update_path_link_styles()
        self._update_start_button_style()
        
        self.show_initial_guides()

    def _get_current_theme(self) -> str:
        """检测当前系统是浅色还是深色模式。"""
        # 一个简单的启发式方法：检查窗口背景色的亮度
        bg_color = self.palette().color(self.backgroundRole())
        # QColor.lightness() 返回 0 (暗) 到 255 (亮)
        return 'dark' if bg_color.lightness() < 128 else 'light'

    def _apply_stylesheet(self):
        """应用当前主题的样式表。"""
        theme = self._get_current_theme()
        self.setStyleSheet(generate_stylesheet(theme))

    def changeEvent(self, event: QEvent):
        """重写changeEvent来监听系统主题变化。"""
        if event.type() == QEvent.Type.ApplicationPaletteChange:
            self._apply_stylesheet()
            self._update_path_link_styles()  # 同时更新路径链接样式
            self._update_start_button_style()  # 同时更新按钮样式
        super().changeEvent(event)

    def create_menu_bar(self):
        menu_bar = self.menuBar()
        
        # File menu
        file_menu = menu_bar.addMenu("File")
        
        reset_action = QAction("Reset All", self)
        reset_action.triggered.connect(self.reset_state)
        reset_action.setShortcut("Ctrl+R")
        file_menu.addAction(reset_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        exit_action.setShortcut("Ctrl+Q")
        file_menu.addAction(exit_action)
        
        # Help menu
        help_menu = menu_bar.addMenu("Help")
        
        user_guide_action = QAction("User Guide", self)
        user_guide_action.triggered.connect(self.show_user_guide_dialog)
        help_menu.addAction(user_guide_action)

        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about_dialog)
        help_menu.addAction(about_action)

    def show_user_guide_dialog(self):
        try:
            with open(resource_path('summary.md'), 'r', encoding='utf-8') as f:
                content = f.read()
            
            dialog = QDialog(self)
            dialog.setWindowTitle("User Guide")
            dialog.setGeometry(200, 200, 700, 500)
            
            layout = QVBoxLayout(dialog)
            text_edit = QTextEdit()
            text_edit.setReadOnly(True)
            text_edit.setHtml(markdown.markdown(content))
            
            layout.addWidget(text_edit)
            dialog.exec()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not load User Guide: {str(e)}")

    def show_initial_guides(self):
        """启动时在log和report区域显示指引"""
        self.log_text.setPlaceholderText(
            "Welcome to PktMask!\n\n"
            "1. Click 'Choose Folder' to select the root directory containing pcap/pcapng files.\n"
            "2. Select the processing steps you want to apply.\n"
            "3. Click 'Start Processing' to run the pipeline.\n\n"
            "Logs will appear here once processing starts."
        )
        self.summary_text.setPlaceholderText(
             "A summary of the processing results will be displayed here."
        )

    def choose_folder(self):
        """选择目录"""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "Select Input Folder",
            self.last_opened_dir
        )
        if dir_path:
            self.base_dir = dir_path
            self.last_opened_dir = dir_path # 记录当前选择的目录
            self.dir_path_label.setText(os.path.basename(dir_path))
            
            # 自动生成默认输出路径
            self.generate_default_output_path()
            self._update_start_button_state()  # 智能更新按钮状态

    def handle_output_click(self):
        """处理输出路径按钮点击 - 在处理完成后打开目录，否则选择自定义输出目录"""
        if self.current_output_dir and os.path.exists(self.current_output_dir):
            # 如果已有输出目录且存在，则打开它
            self.open_output_directory()
        else:
            # 否则让用户选择自定义输出目录
            self.choose_output_folder()

    def choose_output_folder(self):
        """选择自定义输出目录"""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "Select Output Folder",
            self.last_opened_dir
        )
        if dir_path:
            self.output_dir = dir_path
            self.output_path_label.setText(os.path.basename(dir_path))

    def generate_default_output_path(self):
        """生成默认输出路径预览"""
        if not self.base_dir:
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_output = os.path.join(self.base_dir, f"pktmask_output_{timestamp}")
        
        # 重置为默认模式
        self.output_dir = None
        self.output_path_label.setText("Output will be generated")

    def generate_actual_output_path(self) -> str:
        """生成实际的输出目录路径"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if self.output_dir:
            # 自定义输出目录
            return os.path.join(self.output_dir, f"pktmask_output_{timestamp}")
        else:
            # 默认输出目录（输入目录的子目录）
            return os.path.join(self.base_dir, f"pktmask_output_{timestamp}")

    def open_output_directory(self):
        """打开输出目录"""
        if not self.current_output_dir or not os.path.exists(self.current_output_dir):
            QMessageBox.warning(self, "Warning", "Output directory not found.")
            return
        
        import subprocess
        import platform
        
        try:
            system = platform.system()
            if system == "Darwin":  # macOS
                subprocess.run(["open", self.current_output_dir])
            elif system == "Windows":
                subprocess.run(["explorer", self.current_output_dir])
            else:  # Linux
                subprocess.run(["xdg-open", self.current_output_dir])
            
            self.update_log(f"Opened output directory: {os.path.basename(self.current_output_dir)}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to open directory: {str(e)}")

    def reset_state(self):
        """重置所有状态和UI"""
        self.base_dir = None
        self.output_dir = None  # 重置输出目录
        self.current_output_dir = None  # 重置当前输出目录
        self.dir_path_label.setText("No directory selected.")
        self.output_path_label.setText("Output will be generated")  # 重置输出路径显示
        self.log_text.clear()
        self.summary_text.clear()
        self.all_ip_reports.clear()
        self.files_processed_count = 0
        self.packets_processed_count = 0
        self.subdirs_files_counted.clear()
        self.subdirs_packets_counted.clear()
        self.printed_summary_headers.clear()
        self.file_processing_results.clear()  # 清空文件处理结果
        self.current_processing_file = None   # 重置当前处理文件
        self.global_ip_mappings.clear()      # 清空全局IP映射
        self.processed_files_count = 0       # 重置文件计数
        self.user_stopped = False            # 重置停止标志
        if hasattr(self, '_current_file_ips'):
            self._current_file_ips.clear()    # 清空文件IP映射
        self.files_processed_label.setText("0")
        self.packets_processed_label.setText("0")
        self.time_elapsed_label.setText("00:00.00")
        if self.timer and self.timer.isActive():
            self.timer.stop()
        self.progress_bar.setValue(0)
        self.start_proc_btn.setEnabled(False)  # 保持禁用状态，直到选择目录
        self.start_proc_btn.setText("Start")
        self.show_initial_guides()

    def toggle_pipeline_processing(self):
        """根据当前状态切换处理开始/停止"""
        if self.pipeline_thread and self.pipeline_thread.isRunning():
            self.stop_pipeline_processing()
        else:
            self.start_pipeline_processing()

    def generate_partial_summary_on_stop(self):
        """生成用户停止时的部分汇总统计"""
        separator_length = 70
        
        # 计算当前的时间
        if self.timer:
            self.timer.stop()
        self.update_time_elapsed()
        
        partial_time = self.time_elapsed_label.text()
        partial_files = self.files_processed_count
        partial_packets = self.packets_processed_count
        
        # 生成停止汇总报告
        stop_report = f"\n{'='*separator_length}\n⏹️ PROCESSING STOPPED BY USER\n{'='*separator_length}\n"
        stop_report += f"📊 Partial Statistics (Completed Portion):\n"
        stop_report += f"   • Files Processed: {partial_files}\n"
        stop_report += f"   • Packets Processed: {partial_packets:,}\n"
        stop_report += f"   • Processing Time: {partial_time}\n"
        
        # 计算部分处理速度
        try:
            time_parts = partial_time.split(':')
            if len(time_parts) >= 2:
                minutes = int(time_parts[-2])
                seconds_with_ms = time_parts[-1].split('.')
                seconds = int(seconds_with_ms[0])
                total_seconds = minutes * 60 + seconds
                if total_seconds > 0 and partial_packets > 0:
                    speed = partial_packets / total_seconds
                    stop_report += f"   • Average Speed: {speed:,.0f} packets/second\n\n"
                else:
                    stop_report += f"   • Average Speed: N/A\n\n"
            else:
                stop_report += f"   • Average Speed: N/A\n\n"
        except:
            stop_report += f"   • Average Speed: N/A\n\n"
        
        # 显示已启用的处理步骤
        enabled_steps = []
        if self.mask_ip_cb.isChecked():
            enabled_steps.append("IP Masking")
        if self.dedup_packet_cb.isChecked():
            enabled_steps.append("Deduplication")
        if self.trim_packet_cb.isChecked():
            enabled_steps.append("Payload Trimming")
        
        stop_report += f"🔧 Configured Processing Steps: {', '.join(enabled_steps)}\n"
        stop_report += f"📁 Working Directory: {os.path.basename(self.base_dir) if self.base_dir else 'N/A'}\n"
        stop_report += f"⚠️ Processing was interrupted. All intermediate files have been cleaned up.\n"
        stop_report += f"❌ No completed output files were generated due to interruption.\n"
        stop_report += f"{'='*separator_length}\n"
        
        self.summary_text.append(stop_report)
        
        # 检查并显示文件处理状态
        if self.file_processing_results:
            files_status_report = f"\n{'='*separator_length}\n📋 FILES PROCESSING STATUS (At Stop)\n{'='*separator_length}\n"
            
            completed_files = 0
            partial_files = 0
            
            for filename, file_result in self.file_processing_results.items():
                steps_data = file_result['steps']
                if not steps_data:
                    continue
                
                # 检查文件是否完整处理完成（所有配置的步骤都完成）
                expected_steps = set()
                if self.mask_ip_cb.isChecked():
                    expected_steps.add("IP Masking")
                if self.dedup_packet_cb.isChecked():
                    expected_steps.add("Deduplication")
                if self.trim_packet_cb.isChecked():
                    expected_steps.add("Payload Trimming")
                
                completed_steps = set(steps_data.keys())
                is_fully_completed = expected_steps.issubset(completed_steps)
                
                if is_fully_completed:
                    completed_files += 1
                    files_status_report += f"\n✅ {filename}\n"
                    files_status_report += f"   Status: FULLY COMPLETED\n"
                    
                    # 获取最终输出文件名
                    step_order = ['IP Masking', 'Deduplication', 'Payload Trimming']
                    final_output = None
                    for step_name in reversed(step_order):
                        if step_name in steps_data:
                            output_file = steps_data[step_name]['data'].get('output_filename')
                            if output_file and not output_file.startswith('tmp'):
                                final_output = output_file
                                break
                    
                    if final_output:
                        files_status_report += f"   Output File: {final_output}\n"
                    
                    # 显示详细结果
                    original_packets = 0
                    file_ip_mappings = {}
                    
                    for step_name in step_order:
                        if step_name in steps_data:
                            data = steps_data[step_name]['data']
                            if data.get('total_packets'):
                                original_packets = data.get('total_packets', 0)
                            
                            if step_name == 'IP Masking':
                                original_ips = data.get('original_ips', 0)
                                masked_ips = data.get('anonymized_ips', 0)
                                rate = (masked_ips / original_ips * 100) if original_ips > 0 else 0
                                files_status_report += f"   🛡️  IP Masking: {original_ips} → {masked_ips} IPs ({rate:.1f}%)\n"
                                file_ip_mappings = data.get('file_ip_mappings', {})
                                
                            elif step_name == 'Deduplication':
                                unique = data.get('unique_packets', 0)
                                removed = data.get('removed_count', 0)
                                rate = (removed / original_packets * 100) if original_packets > 0 else 0
                                files_status_report += f"   🔄 Deduplication: {removed} removed ({rate:.1f}%)\n"
                            
                            elif step_name == 'Payload Trimming':
                                trimmed = data.get('trimmed_packets', 0)
                                rate = (trimmed / original_packets * 100) if original_packets > 0 else 0
                                files_status_report += f"   ✂️  Payload Trimming: {trimmed} trimmed ({rate:.1f}%)\n"
                    
                    # 显示IP映射（如果有）
                    if file_ip_mappings:
                        files_status_report += f"   🔗 IP Mappings ({len(file_ip_mappings)}):\n"
                        for i, (orig_ip, new_ip) in enumerate(sorted(file_ip_mappings.items()), 1):
                            if i <= 5:  # 只显示前5个
                                files_status_report += f"      {i}. {orig_ip} → {new_ip}\n"
                            elif i == 6:
                                files_status_report += f"      ... and {len(file_ip_mappings) - 5} more\n"
                                break
                else:
                    partial_files += 1
                    files_status_report += f"\n🔄 {filename}\n"
                    files_status_report += f"   Status: PARTIALLY PROCESSED (Interrupted)\n"
                    files_status_report += f"   Completed Steps: {', '.join(completed_steps)}\n"
                    files_status_report += f"   Missing Steps: {', '.join(expected_steps - completed_steps)}\n"
                    files_status_report += f"   ❌ No final output file generated\n"
                    files_status_report += f"   🗑️ Temporary files cleaned up automatically\n"
            
            if completed_files == 0 and partial_files > 0:
                files_status_report += f"\n⚠️ All files were only partially processed.\n"
                files_status_report += f"   No final output files were created.\n"
            elif completed_files > 0:
                files_status_report += f"\n📈 Summary: {completed_files} completed, {partial_files} partial\n"
            
            files_status_report += f"{'='*separator_length}\n"
            self.summary_text.append(files_status_report)
        
        # 显示全局IP映射汇总（仅当有完全完成的文件时）
        if self.processed_files_count >= 1 and self.global_ip_mappings:
            # 检查是否有完全完成的文件
            has_completed_files = False
            for filename, file_result in self.file_processing_results.items():
                expected_steps = set()
                if self.mask_ip_cb.isChecked():
                    expected_steps.add("IP Masking")
                if self.dedup_packet_cb.isChecked():
                    expected_steps.add("Deduplication")
                if self.trim_packet_cb.isChecked():
                    expected_steps.add("Payload Trimming")
                
                completed_steps = set(file_result['steps'].keys())
                if expected_steps.issubset(completed_steps):
                    has_completed_files = True
                    break
            
            if has_completed_files:
                global_partial_report = f"\n{'='*separator_length}\n🌐 IP MAPPINGS FROM COMPLETED FILES\n{'='*separator_length}\n"
                global_partial_report += f"📝 IP Mapping Table - From Successfully Completed Files Only:\n"
                global_partial_report += f"   • Total Unique IPs Mapped: {len(self.global_ip_mappings)}\n\n"
                
                sorted_global_mappings = sorted(self.global_ip_mappings.items())
                for i, (orig_ip, new_ip) in enumerate(sorted_global_mappings, 1):
                    global_partial_report += f"   {i:2d}. {orig_ip:<16} → {new_ip}\n"
                
                global_partial_report += f"{'='*separator_length}\n"
                self.summary_text.append(global_partial_report)
        
        # 修正的重启提示
        restart_hint = f"\n💡 RESTART INFORMATION:\n"
        restart_hint += f"   • Clicking 'Start' will restart processing from the beginning\n"
        restart_hint += f"   • All files will be reprocessed (no partial resume capability)\n"
        restart_hint += f"   • Any existing output files will be skipped to avoid overwriting\n"
        restart_hint += f"   • Processing will be performed completely for each file\n"
        self.summary_text.append(restart_hint)

    def stop_pipeline_processing(self):
        self.user_stopped = True  # 设置停止标志
        self.log_text.append("\n--- Stopping pipeline... ---")
        if self.pipeline_thread:
            self.pipeline_thread.stop()
            # 等待线程安全结束，最多等待 3 秒
            if not self.pipeline_thread.wait(3000):
                self.log_text.append("Warning: Pipeline did not stop gracefully, forcing termination.")
                self.pipeline_thread.terminate()
                self.pipeline_thread.wait()
        
        # 生成停止时的部分汇总统计
        self.generate_partial_summary_on_stop()
        
        # 重新启用控件
        self.dir_path_label.setEnabled(True)
        self.output_path_label.setEnabled(True)
        for cb in [self.mask_ip_cb, self.dedup_packet_cb, self.trim_packet_cb]:
            cb.setEnabled(True)
        self.start_proc_btn.setEnabled(True)
        self.start_proc_btn.setText("Start")

    def start_pipeline_processing(self):
        if not self.base_dir:
            QMessageBox.warning(self, "Warning", "Please choose an input folder to process.")
            return

        # 生成实际输出目录路径
        self.current_output_dir = self.generate_actual_output_path()
        
        # 创建输出目录
        try:
            os.makedirs(self.current_output_dir, exist_ok=True)
            self.update_log(f"📁 Created output directory: {os.path.basename(self.current_output_dir)}")
            
            # 更新输出路径显示
            self.output_path_label.setText(os.path.basename(self.current_output_dir))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create output directory: {str(e)}")
            return

        # Reset UI and counters for new run
        self.log_text.clear()
        self.summary_text.clear()
        self.all_ip_reports.clear()
        self.files_processed_count = 0
        self.packets_processed_count = 0
        self.subdirs_files_counted.clear()
        self.subdirs_packets_counted.clear()
        self.printed_summary_headers.clear()
        self.file_processing_results.clear()  # 清空文件处理结果
        self.current_processing_file = None   # 重置当前处理文件
        self.global_ip_mappings.clear()      # 清空全局IP映射
        self.processed_files_count = 0       # 重置文件计数
        self.user_stopped = False            # 重置停止标志
        if hasattr(self, '_current_file_ips'):
            self._current_file_ips.clear()    # 清空文件IP映射
        self.files_processed_label.setText("0")
        self.packets_processed_label.setText("0")
        self.time_elapsed_label.setText("00:00.00")
        self.progress_bar.setValue(0)

        # Start timer
        self.start_time = QTime.currentTime()
        if not self.timer:
            self.timer = QTimer(self)
            self.timer.timeout.connect(self.update_time_elapsed)
        self.timer.start(50) # update every 50ms for smooth ms display

        # Build pipeline from checkboxes
        steps_to_run: List[str] = []
        # 推荐的处理顺序：Mask IP -> Remove Dupes -> Trim Packet
        if self.mask_ip_cb.isChecked():
            steps_to_run.append("mask_ip")
        if self.dedup_packet_cb.isChecked():
            steps_to_run.append("dedup_packet")
        if self.trim_packet_cb.isChecked():
            steps_to_run.append("trim_packet")

        if not steps_to_run:
            QMessageBox.warning(self, "Warning", "Please select at least one processing step.")
            return

        try:
            pipeline_steps = [get_step_instance(name) for name in steps_to_run]
            pipeline = Pipeline(steps=pipeline_steps)
            self.start_processing(pipeline)
        except ValueError as e:
            self.log_text.append(f"Error creating pipeline: {e}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An unexpected error occurred: {e}")

    def start_processing(self, pipeline: Pipeline):
        self.log_text.append(f"--- Pipeline Started ---\n")
        
        # 添加处理开始的信息
        enabled_steps = []
        if self.mask_ip_cb.isChecked():
            enabled_steps.append("🛡️ IP Masking")
        if self.dedup_packet_cb.isChecked():
            enabled_steps.append("🔄 Deduplication")
        if self.trim_packet_cb.isChecked():
            enabled_steps.append("✂️ Payload Trimming")
            
        separator_length = 70
        start_report = f"{'='*separator_length}\n🚀 STARTING PACKET PROCESSING PIPELINE\n{'='*separator_length}\n"
        start_report += f"📂 Input Directory: {os.path.basename(self.base_dir)}\n"
        start_report += f"📁 Output Directory: {os.path.basename(self.current_output_dir)}\n"
        start_report += f"🔧 Processing Steps: {', '.join(enabled_steps)}\n"
        start_report += f"⏰ Started at: {QTime.currentTime().toString('hh:mm:ss')}\n"
        start_report += f"{'='*separator_length}\n"
        
        self.summary_text.append(start_report)

        self.pipeline_thread = PipelineThread(pipeline, self.base_dir, self.current_output_dir)
        self.pipeline_thread.progress_signal.connect(self.handle_thread_progress)
        self.pipeline_thread.finished.connect(self.on_thread_finished)
        self.pipeline_thread.start()

        # Disable all controls during processing
        self.dir_path_label.setEnabled(False)
        self.output_path_label.setEnabled(False)
        for cb in [self.mask_ip_cb, self.dedup_packet_cb, self.trim_packet_cb]:
            cb.setEnabled(False)
        self.start_proc_btn.setText("Stop")

    def handle_thread_progress(self, event_type: PipelineEvents, data: dict):
        """主槽函数，根据事件类型分发UI更新任务"""
        if event_type == PipelineEvents.PIPELINE_START:
            self.progress_bar.setMaximum(data.get('total_subdirs', 100))
        
        elif event_type == PipelineEvents.SUBDIR_START:
            self._animate_progress_to(data.get('current', 0))  # 使用动画
            self.update_log(f"Processing directory: {data.get('name', 'N/A')}")
        
        elif event_type == PipelineEvents.FILE_START:
            self.files_processed_count += 1
            self.files_processed_label.setText(str(self.files_processed_count))
            file_path = data['path']
            self.current_processing_file = os.path.basename(file_path)
            self.update_log(f"\nProcessing file: {self.current_processing_file}")
            
            # 初始化当前文件的处理结果记录
            if self.current_processing_file not in self.file_processing_results:
                self.file_processing_results[self.current_processing_file] = {'steps': {}}

        elif event_type == PipelineEvents.FILE_END:
            if self.current_processing_file:
                # 获取输出文件名信息
                output_files = []
                if self.current_processing_file in self.file_processing_results:
                    steps_data = self.file_processing_results[self.current_processing_file]['steps']
                    step_order = ['IP Masking', 'Deduplication', 'Payload Trimming']
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
            self.packets_processed_count += data.get('count', 0)
            self.packets_processed_label.setText(str(self.packets_processed_count))

        elif event_type == PipelineEvents.LOG:
            self.update_log(data['message'])

        elif event_type == PipelineEvents.STEP_SUMMARY:
            self.collect_step_result(data)

        elif event_type == PipelineEvents.PIPELINE_END:
            self._animate_progress_to(self.progress_bar.maximum())  # 动画到100%
            self.processing_finished()
            
        elif event_type == PipelineEvents.ERROR:
            self.processing_error(data['message'])

    def collect_step_result(self, data: dict):
        """收集每个步骤的处理结果，但不立即显示"""
        if not self.current_processing_file:
            return
            
        step_type = data.get('type')
        if not step_type or step_type.endswith('_final'):
            if step_type and step_type.endswith('_final'):
                # 处理最终报告，提取IP映射信息
                report_data = data.get('report')
                if report_data and 'mask_ip' in step_type:
                    self.set_final_summary_report(report_data)
            return
        
        # 标准化步骤名称
        step_display_names = {
            'mask_ip': 'IP Masking',
            'remove_dupes': 'Deduplication', 
            'intelligent_trim': 'Payload Trimming'
        }
        
        step_name = step_display_names.get(step_type, step_type)
        
        # 存储步骤结果
        self.file_processing_results[self.current_processing_file]['steps'][step_name] = {
            'type': step_type,
            'data': data
        }
        
        # 如果是IP匿名化步骤，提取文件级别的IP映射
        if step_type == 'mask_ip' and 'file_ip_mappings' in data:
            if not hasattr(self, '_current_file_ips'):
                self._current_file_ips = {}
            self._current_file_ips[self.current_processing_file] = data['file_ip_mappings']
            # 将IP映射添加到全局映射中
            self.global_ip_mappings.update(data['file_ip_mappings'])

    def generate_file_complete_report(self, original_filename: str):
        """为单个文件生成完整的处理报告"""
        if original_filename not in self.file_processing_results:
            return
            
        file_results = self.file_processing_results[original_filename]
        steps_data = file_results['steps']
        
        if not steps_data:
            return
        
        # 增加已处理文件计数
        self.processed_files_count += 1
        
        separator_length = 70
        filename_display = original_filename
        
        # 文件处理标题
        header = f"\n{'='*separator_length}\n📄 FILE PROCESSING RESULTS: {filename_display}\n{'='*separator_length}"
        self.summary_text.append(header)
        
        # 获取原始包数（从第一个处理步骤获取）
        original_packets = 0
        output_filename = None
        if 'IP Masking' in steps_data:
            original_packets = steps_data['IP Masking']['data'].get('total_packets', 0)
            output_filename = steps_data['IP Masking']['data'].get('output_filename')
        elif 'Deduplication' in steps_data:
            original_packets = steps_data['Deduplication']['data'].get('total_packets', 0)
            output_filename = steps_data['Deduplication']['data'].get('output_filename')
        elif 'Payload Trimming' in steps_data:
            original_packets = steps_data['Payload Trimming']['data'].get('total_packets', 0)
            output_filename = steps_data['Payload Trimming']['data'].get('output_filename')
        
        # 从最后一个处理步骤获取最终输出文件名
        step_order = ['IP Masking', 'Deduplication', 'Payload Trimming']
        for step_name in reversed(step_order):
            if step_name in steps_data:
                final_output = steps_data[step_name]['data'].get('output_filename')
                if final_output:
                    output_filename = final_output
                    break
        
        # 显示原始包数和输出文件名
        self.summary_text.append(f"📦 Original Packets: {original_packets:,}")
        if output_filename:
            self.summary_text.append(f"📄 Output File: {output_filename}")
        self.summary_text.append("")
        
        # 按处理顺序显示各步骤结果
        file_ip_mappings = {}  # 存储当前文件的IP映射
        
        for step_name in step_order:
            if step_name in steps_data:
                step_result = steps_data[step_name]
                step_type = step_result['type']
                data = step_result['data']
                
                if step_type == 'mask_ip':
                    # 使用新的IP统计数据
                    original_ips = data.get('original_ips', 0)
                    masked_ips = data.get('anonymized_ips', 0)
                    rate = (masked_ips / original_ips * 100) if original_ips > 0 else 0
                    line = f"  🛡️  {step_name:<18} | Original IPs: {original_ips:>3} | Masked IPs: {masked_ips:>3} | Rate: {rate:5.1f}%"
                    
                    # 获取文件级别的IP映射
                    file_ip_mappings = data.get('file_ip_mappings', {})
                    
                elif step_type == 'remove_dupes':
                    unique = data.get('unique_packets', 0)
                    removed = data.get('removed_count', 0)
                    total_before = data.get('total_packets', 0)
                    rate = (removed / total_before * 100) if total_before > 0 else 0
                    line = f"  🔄 {step_name:<18} | Unique Pkts: {unique:>4} | Removed Pkts: {removed:>4} | Rate: {rate:5.1f}%"
                
                elif step_type == 'intelligent_trim':
                    total = data.get('total_packets', 0)
                    trimmed = data.get('trimmed_packets', 0)
                    full_pkts = total - trimmed
                    rate = (trimmed / total * 100) if total > 0 else 0
                    line = f"  ✂️  {step_name:<18} | Full Pkts: {full_pkts:>5} | Trimmed Pkts: {trimmed:>4} | Rate: {rate:5.1f}%"
                else:
                    continue
                    
                self.summary_text.append(line)
        
        # 如果有IP映射，显示文件级别的IP映射
        if file_ip_mappings:
            self.summary_text.append("")
            self.summary_text.append("🔗 IP Mappings for this file:")
            sorted_mappings = sorted(file_ip_mappings.items())
            for i, (orig_ip, new_ip) in enumerate(sorted_mappings, 1):
                self.summary_text.append(f"   {i:2d}. {orig_ip:<16} → {new_ip}")
        
        self.summary_text.append(f"{'='*separator_length}")

    def update_summary_report(self, data: dict):
        """这个方法现在主要用于处理最终报告，文件级报告由 generate_file_complete_report 处理"""
        step_type = data.get('type')
        if step_type and step_type.endswith('_final'):
            report_data = data.get('report')
            if report_data and 'mask_ip' in step_type:
                self.set_final_summary_report(report_data)

    def set_final_summary_report(self, report: dict):
        """设置最终的汇总报告，包括详细的IP映射信息。"""
        subdir = report.get('path', 'N/A')
        stats = report.get('stats', {})
        total_mapping = report.get('data', {}).get('total_mapping', {})
        
        separator_length = 70  # 保持一致的分隔线长度
        
        # 添加IP映射的汇总信息，包括详细映射表
        text = f"\n{'='*separator_length}\n📋 DIRECTORY PROCESSING SUMMARY\n{'='*separator_length}\n"
        text += f"📂 Directory: {subdir}\n\n"
        text += f"🔒 IP Anonymization Summary:\n"
        text += f"   • Total Unique IPs Discovered: {stats.get('total_unique_ips', 'N/A')}\n"
        text += f"   • Total IPs Anonymized: {stats.get('total_mapped_ips', 'N/A')}\n\n"
        
        if total_mapping:
            text += f"📝 Complete IP Mapping Table (All Files):\n"
            # 按原始IP排序显示映射
            sorted_mappings = sorted(total_mapping.items())
            for i, (orig_ip, new_ip) in enumerate(sorted_mappings, 1):
                text += f"   {i:2d}. {orig_ip:<16} → {new_ip}\n"
            text += "\n"
        
        text += f"✅ All IP addresses have been successfully anonymized while\n"
        text += f"   preserving network structure and subnet relationships.\n"
        text += f"{'='*separator_length}\n"
        
        self.summary_text.append(text)

    def update_log(self, message: str):
        self.log_text.append(message)
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())

    def processing_finished(self):
        # 如果用户已经停止，不再显示完成信息
        if self.user_stopped:
            return
            
        self.log_text.append(f"\n--- Pipeline Finished ---")
        
        # 添加处理完成的汇总信息
        if self.timer:
            self.timer.stop()
        self.update_time_elapsed()
        
        final_time = self.time_elapsed_label.text()
        total_files = self.files_processed_count
        total_packets = self.packets_processed_count
        
        separator_length = 70
        completion_report = f"\n{'='*separator_length}\n✅ PROCESSING COMPLETED SUCCESSFULLY\n{'='*separator_length}\n"
        completion_report += f"📊 Overall Statistics:\n"
        completion_report += f"   • Total Files Processed: {total_files}\n"
        completion_report += f"   • Total Packets Processed: {total_packets:,}\n"
        completion_report += f"   • Processing Time: {final_time}\n"
        
        # 计算处理速度 (更安全的方式)
        try:
            time_parts = final_time.split(':')
            if len(time_parts) >= 2:
                minutes = int(time_parts[-2])
                seconds_with_ms = time_parts[-1].split('.')
                seconds = int(seconds_with_ms[0])
                total_seconds = minutes * 60 + seconds
                if total_seconds > 0:
                    speed = total_packets / total_seconds
                    completion_report += f"   • Average Speed: {speed:,.0f} packets/second\n\n"
                else:
                    completion_report += f"   • Average Speed: N/A (processing too fast)\n\n"
            else:
                completion_report += f"   • Average Speed: N/A\n\n"
        except:
            completion_report += f"   • Average Speed: N/A\n\n"
        
        enabled_steps = []
        if self.mask_ip_cb.isChecked():
            enabled_steps.append("IP Masking")
        if self.dedup_packet_cb.isChecked():
            enabled_steps.append("Deduplication")
        if self.trim_packet_cb.isChecked():
            enabled_steps.append("Payload Trimming")
            
        completion_report += f"🔧 Applied Processing Steps: {', '.join(enabled_steps)}\n"
        completion_report += f"📁 Output Location: {os.path.basename(self.current_output_dir)}\n"
        completion_report += f"📝 All processed files saved to output directory.\n"
        completion_report += f"{'='*separator_length}\n"
        
        self.summary_text.append(completion_report)

        # 如果处理了≥2个文件且有IP映射，显示全局IP映射
        if self.processed_files_count >= 2 and self.global_ip_mappings:
            global_mapping_report = f"\n{'='*separator_length}\n🌐 GLOBAL IP MAPPINGS (All Files Combined)\n{'='*separator_length}\n"
            global_mapping_report += f"📝 Complete IP Mapping Table - Unique Entries Across All Files:\n"
            global_mapping_report += f"   • Total Unique IPs Mapped: {len(self.global_ip_mappings)}\n\n"
            
            # 按原始IP排序显示映射
            sorted_global_mappings = sorted(self.global_ip_mappings.items())
            for i, (orig_ip, new_ip) in enumerate(sorted_global_mappings, 1):
                global_mapping_report += f"   {i:2d}. {orig_ip:<16} → {new_ip}\n"
            
            global_mapping_report += f"\n✅ All unique IP addresses across {self.processed_files_count} files have been\n"
            global_mapping_report += f"   successfully anonymized with consistent mappings.\n"
            global_mapping_report += f"{'='*separator_length}\n"
            
            self.summary_text.append(global_mapping_report)

        # 保存summary report到输出目录
        self.save_summary_report_to_output_dir()

        # 更新输出路径显示
        if self.current_output_dir:
            self.output_path_label.setText(os.path.basename(self.current_output_dir))
        self.update_log(f"Output directory ready. Click output path to view results.")

        # Re-enable controls
        self.dir_path_label.setEnabled(True)
        self.output_path_label.setEnabled(True)
        for cb in [self.mask_ip_cb, self.dedup_packet_cb, self.trim_packet_cb]:
            cb.setEnabled(True)
        self.start_proc_btn.setEnabled(True)
        self.start_proc_btn.setText("Start")

    def processing_error(self, error_message: str):
        QMessageBox.critical(self, "Error", f"An error occurred during processing:\n{error_message}")
        self.processing_finished()

    def on_thread_finished(self):
        """线程完成时的回调函数，确保UI状态正确恢复"""
        self.pipeline_thread = None

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
        QMessageBox.about(self, "About PktMask",
            "<h3>PktMask</h3>"
            "<p>Version: 1.0</p>"
            "<p>A tool for masking sensitive data in packet captures.</p>"
            "<p>For more information, visit our <a href='https://github.com/your-repo'>GitHub page</a>.</p>")

    def update_time_elapsed(self):
        if not self.start_time:
            return
        
        elapsed_msecs = self.start_time.msecsTo(QTime.currentTime())
        
        seconds = elapsed_msecs // 1000
        msecs = (elapsed_msecs % 1000) // 10
        
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if hours > 0:
            self.time_elapsed_label.setText(f"{hours}:{minutes:02d}:{seconds:02d}.{msecs:02d}")
        else:
            self.time_elapsed_label.setText(f"{minutes:02d}:{seconds:02d}.{msecs:02d}")

    def generate_summary_report_filename(self) -> str:
        """生成带有处理选项标识的summary report文件名"""
        
        # 生成处理选项标识
        enabled_steps = []
        if self.mask_ip_cb.isChecked():
            enabled_steps.append("MaskIP")
        if self.dedup_packet_cb.isChecked():
            enabled_steps.append("Dedup")
        if self.trim_packet_cb.isChecked():
            enabled_steps.append("Trim")
        
        steps_suffix = "_".join(enabled_steps) if enabled_steps else "NoSteps"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
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
                from datetime import datetime
                f.write("# PktMask Summary Report\n")
                f.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# Working Directory: {self.current_output_dir}\n")
                f.write("#" + "="*68 + "\n\n")
                f.write(summary_content)
            
            self.update_log(f"Summary report saved: {filename}")
            
        except Exception as e:
            self.update_log(f"Error saving summary report: {str(e)}")

    def find_existing_summary_reports(self) -> List[str]:
        """查找工作目录中的现有summary report文件"""
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
        """根据当前主题生成路径链接样式"""
        theme = self._get_current_theme()
        
        if theme == 'dark':
            # Dark模式：更柔和的蓝色系
            return """
                QPushButton {
                    background: none;
                    border: none;
                    padding: 8px 4px;
                    text-align: left;
                    color: #5AC8FA;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
                    font-size: 13px;
                    text-decoration: none;
                }
                QPushButton:hover {
                    color: #64D2FF;
                    text-decoration: underline;
                }
                QPushButton:pressed {
                    color: #32ADF0;
                }
            """
        else:
            # Light模式：经典蓝色系
            return """
                QPushButton {
                    background: none;
                    border: none;
                    padding: 8px 4px;
                    text-align: left;
                    color: #007AFF;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
                    font-size: 13px;
                    text-decoration: none;
                }
                QPushButton:hover {
                    color: #0051D5;
                    text-decoration: underline;
                }
                QPushButton:pressed {
                    color: #003D9F;
                }
            """

    def _update_path_link_styles(self):
        """更新路径链接的样式"""
        style = self._get_path_link_style()
        self.dir_path_label.setStyleSheet(style)
        self.output_path_label.setStyleSheet(style)

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
        has_input_dir = self.base_dir is not None
        has_any_option = (self.mask_ip_cb.isChecked() or 
                         self.dedup_packet_cb.isChecked() or 
                         self.trim_packet_cb.isChecked())
        
        # 检查是否正在处理中
        is_processing = (self.pipeline_thread is not None and 
                        self.pipeline_thread.isRunning())
        
        # 只有当有输入目录且至少选择一个选项时才启用按钮，或者正在处理中时保持启用
        should_enable = (has_input_dir and has_any_option) or is_processing
        self.start_proc_btn.setEnabled(should_enable)

    def _get_start_button_style(self) -> str:
        """根据当前主题生成Start按钮样式"""
        theme = self._get_current_theme()
        
        if theme == 'dark':
            return """
                QPushButton {
                    font-size: 14px;
                    font-weight: 600;
                    padding: 8px 20px;
                    border-radius: 6px;
                    border: none;
                }
                QPushButton:enabled:pressed {
                    background-color: #0069D9;
                }
                QPushButton:disabled {
                    background-color: #3A3A3C;
                    color: #8D8D92;
                    border: 1px solid #48484A;
                }
            """
        else:
            return """
                QPushButton {
                    font-size: 14px;
                    font-weight: 600;
                    padding: 8px 20px;
                    border-radius: 6px;
                    border: none;
                }
                QPushButton:enabled:pressed {
                    background-color: #0051D5;
                }
                QPushButton:disabled {
                    background-color: #E5E5E7;
                    color: #8E8E93;
                    border: 1px solid #D1D1D6;
                }
            """

    def _update_start_button_style(self):
        """更新Start按钮样式"""
        self.start_proc_btn.setStyleSheet(self._get_start_button_style())

def main():
    """主函数"""
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec()) 