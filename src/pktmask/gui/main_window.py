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
from typing import Optional, List
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QProgressBar, QTextEdit, QFileDialog,
    QMessageBox, QScrollArea, QSplitter, QTableWidget, QTableWidgetItem,
    QTabWidget, QFrame, QDialog, QCheckBox, QGridLayout, QGroupBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject, QEvent, QTimer, QTime
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

    def __init__(self, pipeline: Pipeline, base_dir: str):
        super().__init__()
        self._pipeline = pipeline
        self._base_dir = base_dir
        self.is_running = True

    def run(self):
        try:
            self._pipeline.run(self._base_dir, progress_callback=self.handle_progress)
        except Exception as e:
            self.progress_signal.emit(PipelineEvents.ERROR, {'message': str(e)})

    def handle_progress(self, event_type: PipelineEvents, data: dict):
        if not self.is_running:
            # Should ideally stop the pipeline gracefully
            return
        self.progress_signal.emit(event_type, data)

    def stop(self):
        self.is_running = False

class MainWindow(QMainWindow):
    """主窗口"""
    def __init__(self):
        super().__init__()
        self.pipeline_thread: Optional[PipelineThread] = None
        self.all_ip_reports = {}  # subdir -> report_data
        self.base_dir: Optional[str] = None
        self.allowed_root = os.path.expanduser("~")
        
        # KPI counters
        self.files_processed_count = 0
        self.packets_processed_count = 0
        self.timer: Optional[QTimer] = None
        self.start_time: Optional[QTime] = None
        self.subdirs_files_counted = set()
        self.subdirs_packets_counted = set()

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
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # --- Create all GroupBox widgets first ---

        # Step 1: Input
        input_group = QGroupBox("Step 1: Select Target")
        input_layout = QHBoxLayout(input_group)
        self.dir_prefix_label = QLabel("Input Folder:")
        self.dir_path_label = QLabel("No folder selected.")
        self.dir_path_label.setObjectName("DirPathLabel")
        self.select_dir_btn = QPushButton("Choose Folder")
        self.reset_btn = QPushButton("Reset")
        self.reset_btn.setObjectName("ResetButton")
        input_layout.addWidget(self.dir_prefix_label)
        input_layout.addWidget(self.dir_path_label, 1)
        input_layout.addWidget(self.select_dir_btn)
        input_layout.addWidget(self.reset_btn)

        # Step 2: Configure Pipeline
        pipeline_group = QGroupBox("Step 2: Set Options")
        pipeline_layout = QVBoxLayout(pipeline_group)
        self.mask_ip_cb = QCheckBox("Mask IPs")
        self.dedup_packet_cb = QCheckBox("Remove Dupes")
        self.trim_packet_cb = QCheckBox("Cut Payloads")
        self.trim_packet_cb.setToolTip("Cuts payload of packets to reduce size.")
        self.mask_ip_cb.setChecked(True)
        self.dedup_packet_cb.setChecked(True)
        self.trim_packet_cb.setChecked(True)
        pipeline_layout.addWidget(self.mask_ip_cb)
        pipeline_layout.addWidget(self.dedup_packet_cb)
        pipeline_layout.addWidget(self.trim_packet_cb)
        pipeline_layout.addStretch()

        # Step 3: Execute
        execute_group = QGroupBox("Step 3: Run Processing")
        execute_layout = QVBoxLayout(execute_group)
        self.start_proc_btn = QPushButton("Start")
        self.start_proc_btn.setMinimumHeight(40)
        execute_layout.addStretch()
        execute_layout.addWidget(self.start_proc_btn)
        execute_layout.addStretch()
        
        # Live Dashboard
        dashboard_group = QGroupBox("Live Dashboard")
        dashboard_layout = QVBoxLayout(dashboard_group)
        self.progress_bar = QProgressBar()
        dashboard_layout.addWidget(self.progress_bar)
        kpi_layout = QGridLayout()
        self.files_processed_label = QLabel("0")
        self.files_processed_label.setObjectName("FilesProcessedLabel")
        self.packets_processed_label = QLabel("0")
        self.packets_processed_label.setObjectName("IpsMaskedLabel") # Re-use for same style
        self.time_elapsed_label = QLabel("00:00")
        self.time_elapsed_label.setObjectName("DupesRemovedLabel") # Re-use for same style

        kpi_layout.addWidget(self.files_processed_label, 0, 0, Qt.AlignmentFlag.AlignCenter)
        kpi_layout.addWidget(QLabel("Files Processed"), 1, 0, Qt.AlignmentFlag.AlignCenter)
        kpi_layout.addWidget(self.packets_processed_label, 0, 1, Qt.AlignmentFlag.AlignCenter)
        kpi_layout.addWidget(QLabel("Packets Processed"), 1, 1, Qt.AlignmentFlag.AlignCenter)
        kpi_layout.addWidget(self.time_elapsed_label, 0, 2, Qt.AlignmentFlag.AlignCenter)
        kpi_layout.addWidget(QLabel("Time Elapsed"), 1, 2, Qt.AlignmentFlag.AlignCenter)
        
        dashboard_layout.addLayout(kpi_layout)
        
        # Log
        log_group = QGroupBox("Log")
        log_layout = QVBoxLayout(log_group)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)

        # Summary Report
        summary_group = QGroupBox("Summary Report")
        summary_layout = QVBoxLayout(summary_group)
        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        summary_layout.addWidget(self.summary_text)

        # --- Add widgets to the grid layout ---
        
        # Row 0: Top controls
        main_layout.addWidget(input_group, 0, 0)
        main_layout.addWidget(pipeline_group, 0, 1)
        main_layout.addWidget(execute_group, 0, 2)
        
        # Left column contents
        main_layout.addWidget(dashboard_group, 1, 0)
        main_layout.addWidget(log_group, 2, 0)
        
        # Right column contents
        main_layout.addWidget(summary_group, 1, 1, 2, 2) # row, col, rowspan, colspan

        # --- Define stretch factors for the grid ---
        main_layout.setColumnStretch(0, 2)
        main_layout.setColumnStretch(1, 1)
        main_layout.setColumnStretch(2, 1)
        
        main_layout.setRowStretch(0, 0)  # Top controls row - no stretch
        main_layout.setRowStretch(1, 0)  # Dashboard row - no stretch
        main_layout.setRowStretch(2, 1)  # Log row - takes available space

        # Connect signals
        self.select_dir_btn.clicked.connect(self.choose_folder)
        self.reset_btn.clicked.connect(self.reset_state)
        self.start_proc_btn.clicked.connect(self.start_pipeline_processing)
        
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
        super().changeEvent(event)

    def create_menu_bar(self):
        menu_bar = self.menuBar()
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
        # 默认路径设置为桌面
        default_path = os.path.join(os.path.expanduser("~"), "Desktop")
        
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "Select Folder",
            default_path
        )
        if dir_path:
            self.base_dir = dir_path
            self.dir_path_label.setText(self.get_elided_text(self.dir_path_label, dir_path))
            self.start_proc_btn.setEnabled(True)

    def reset_state(self):
        """重置所有状态和UI"""
        self.base_dir = None
        self.dir_path_label.setText("No folder selected.")
        self.log_text.clear()
        self.summary_text.clear()
        self.all_ip_reports.clear()
        self.files_processed_count = 0
        self.packets_processed_count = 0
        self.subdirs_files_counted.clear()
        self.subdirs_packets_counted.clear()
        self.files_processed_label.setText("0")
        self.packets_processed_label.setText("0")
        self.time_elapsed_label.setText("00:00")
        if self.timer and self.timer.isActive():
            self.timer.stop()
        self.progress_bar.setValue(0)
        self.start_proc_btn.setEnabled(False)
        self.show_initial_guides()

    def start_pipeline_processing(self):
        if not self.base_dir:
            QMessageBox.warning(self, "Warning", "Please choose a folder to process.")
            return

        # Reset UI and counters for new run
        self.log_text.clear()
        self.summary_text.clear()
        self.all_ip_reports.clear()
        self.files_processed_count = 0
        self.packets_processed_count = 0
        self.subdirs_files_counted.clear()
        self.subdirs_packets_counted.clear()
        self.files_processed_label.setText("0")
        self.packets_processed_label.setText("0")
        self.time_elapsed_label.setText("00:00")
        self.progress_bar.setValue(0)

        # Start timer
        self.start_time = QTime.currentTime()
        if not self.timer:
            self.timer = QTimer(self)
            self.timer.timeout.connect(self.update_time_elapsed)
        self.timer.start(1000) # update every second

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
        self.summary_text.append(f"--- Pipeline Started ---\n")

        self.pipeline_thread = PipelineThread(pipeline, self.base_dir)
        self.pipeline_thread.progress_signal.connect(self.handle_thread_progress)
        self.pipeline_thread.start()

        # Disable all controls during processing
        self.select_dir_btn.setEnabled(False)
        self.reset_btn.setEnabled(False)
        for cb in [self.mask_ip_cb, self.dedup_packet_cb, self.trim_packet_cb]:
            if cb.text() != "Trim Packet (Coming Soon)":
                cb.setEnabled(False)
        self.start_proc_btn.setEnabled(False)

    def handle_thread_progress(self, event_type: PipelineEvents, data: dict):
        """主槽函数，根据事件类型分发UI更新任务"""
        if event_type == PipelineEvents.PIPELINE_START:
            self.progress_bar.setMaximum(data.get('total_subdirs', 100))
        
        elif event_type == PipelineEvents.SUBDIR_START:
            self.progress_bar.setValue(data.get('current', 0))

        elif event_type == PipelineEvents.LOG:
            self.update_log(data['message'])

        elif event_type == PipelineEvents.STEP_SUMMARY:
            subdir_path = None
            if data['type'] == 'mask_ip':
                subdir_path = data.get('report', {}).get('path')
            elif data['type'] == 'dedup_packet':
                subdir_path = data.get('subdir')
            elif data['type'] == 'intelligent_trim':
                subdir_path = data.get('report', {}).get('subdir')

            if data['type'] == 'mask_ip':
                report = data['report']
                if subdir_path and subdir_path not in self.subdirs_files_counted:
                    self.files_processed_count += report.get('stats', {}).get('processed_file_count', 0)
                    self.subdirs_files_counted.add(subdir_path)
                self.update_ip_report(report)
            
            elif data['type'] == 'dedup_packet':
                report = data
                if subdir_path and subdir_path not in self.subdirs_files_counted:
                    self.files_processed_count += report.get('processed_files', 0)
                    self.subdirs_files_counted.add(subdir_path)
                if subdir_path and subdir_path not in self.subdirs_packets_counted:
                    self.packets_processed_count += report.get('total_packets', 0)
                    self.subdirs_packets_counted.add(subdir_path)
                self.update_dedup_report(data)

            elif data['type'] == 'intelligent_trim':
                report = data.get('report', {})
                if subdir_path and subdir_path not in self.subdirs_files_counted:
                    self.files_processed_count += report.get('processed_files', 0)
                    self.subdirs_files_counted.add(subdir_path)
                if subdir_path and subdir_path not in self.subdirs_packets_counted:
                    self.packets_processed_count += report.get('total_packets', 0)
                    self.subdirs_packets_counted.add(subdir_path)
                self.update_trim_report(data)
            
            # Update KPI labels
            self.files_processed_label.setText(f"{self.files_processed_count}")
            self.packets_processed_label.setText(f"{self.packets_processed_count}")

        elif event_type == PipelineEvents.PIPELINE_END:
            self.progress_bar.setValue(self.progress_bar.maximum()) # Ensure it reaches 100%
            self.processing_finished()
            
        elif event_type == PipelineEvents.ERROR:
            self.processing_error(data['message'])

    def update_log(self, message: str):
        self.log_text.append(message)
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())

    def update_ip_report(self, report: dict):
        """更新IP脱敏报告的文本视图"""
        subdir = report.get('path', 'N/A')
        stats = report.get('stats', {})
        total_mapping = report.get('data', {}).get('total_mapping', {})

        text = f"--- IP Masking Summary for: {subdir} ---\n"
        text += f"Processed Files: {stats.get('processed_file_count', 'N/A')}\n"
        text += f"Total Unique IPs Found: {stats.get('total_unique_ips', 'N/A')}\n"
        text += f"Total Mapped IPs: {stats.get('total_mapped_ips', 'N/A')}\n"
        text += "[Mapping Details]\n"
        for orig, new in total_mapping.items():
            text += f"  {orig:<40} -> {new}\n"
        text += "\n"
        
        self.set_report_text(text)
    
    def update_dedup_report(self, summary_data: dict):
        subdir = summary_data.get('subdir', 'N/A')
        text = f"--- Remove Dupes Summary for: {subdir} ---\n"
        text += f"Processed Files: {summary_data.get('processed_files', 0)}\n"
        text += f"Total Original Packets: {summary_data.get('total_packets', 0)}\n"
        text += f"Total Unique Packets: {summary_data.get('total_unique_packets', 0)}\n\n"
        self.set_report_text(text)

    def update_trim_report(self, summary_data: dict):
        """更新智能裁切报告的文本视图"""
        report = summary_data.get('report', {})
        subdir = report.get('subdir', 'N/A')
        total = report.get('total_packets', 0)
        trimmed = report.get('trimmed_packets', 0)
        
        text = f"--- Intelligent Trim Summary for: {subdir} ---\n"
        text += f"Total Packets Scanned: {total}\n"
        text += f"Packets Trimmed: {trimmed}\n\n"
        
        self.set_report_text(text)

    def set_report_text(self, text: str):
        self.summary_text.append(text)
        self.summary_text.moveCursor(QTextCursor.MoveOperation.End)

    def processing_finished(self):
        self.log_text.append(f"\n--- Pipeline Finished ---")
        self.summary_text.append(f"\n--- Pipeline Finished ---")
        
        if self.timer:
            self.timer.stop()
        self.update_time_elapsed()

        # Re-enable controls
        self.select_dir_btn.setEnabled(True)
        self.reset_btn.setEnabled(True)
        for cb in [self.mask_ip_cb, self.dedup_packet_cb, self.trim_packet_cb]:
            cb.setEnabled(True)
        self.start_proc_btn.setEnabled(True)

    def processing_error(self, error_message: str):
        QMessageBox.critical(self, "Error", f"An error occurred during processing:\n{error_message}")
        self.processing_finished()

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
        elapsed_seconds = self.start_time.secsTo(QTime.currentTime())
        hours, remainder = divmod(elapsed_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours > 0:
            self.time_elapsed_label.setText(f"{hours}:{minutes:02d}:{seconds:02d}")
        else:
            self.time_elapsed_label.setText(f"{minutes:02d}:{seconds:02d}")

def main():
    """主函数"""
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec()) 