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
from typing import Optional, List, Tuple
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
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # --- Create all GroupBox widgets first ---

        # Step 1: Input
        input_group = QGroupBox("Step 1: Select Working Directory")
        input_layout = QHBoxLayout(input_group)
        self.dir_path_label = QLabel("No directory selected.")
        self.dir_path_label.setObjectName("DirPathLabel")
        self.select_dir_btn = QPushButton("Browse...")
        self.reset_btn = QPushButton("Clear")
        self.reset_btn.setObjectName("ResetButton")
        input_layout.addWidget(self.dir_path_label, 1)
        input_layout.addWidget(self.select_dir_btn)
        input_layout.addWidget(self.reset_btn)

        # Step 2: Configure Pipeline
        pipeline_group = QGroupBox("Step 2: Set Options")
        pipeline_layout = QVBoxLayout(pipeline_group)
        self.mask_ip_cb = QCheckBox("Mask IPs")
        self.dedup_packet_cb = QCheckBox("Remove Dupes")
        self.trim_packet_cb = QCheckBox("Trim Payloads (Preserve TLS Handshake)")
        self.trim_packet_cb.setToolTip("Intelligently trims packet payloads while preserving TLS handshake data.")
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
        self.progress_bar.setTextVisible(False)
        dashboard_layout.addWidget(self.progress_bar)
        kpi_layout = QGridLayout()
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
        self.start_proc_btn.clicked.connect(self.toggle_pipeline_processing)
        
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
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "Select Folder",
            self.last_opened_dir
        )
        if dir_path:
            self.base_dir = dir_path
            self.last_opened_dir = dir_path # 记录当前选择的目录
            self.dir_path_label.setText(self.get_elided_text(self.dir_path_label, dir_path))
            self.start_proc_btn.setEnabled(True)

    def reset_state(self):
        """重置所有状态和UI"""
        self.base_dir = None
        self.dir_path_label.setText("No directory selected.")
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
        self.start_proc_btn.setEnabled(False)
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
        self.select_dir_btn.setEnabled(True)
        self.reset_btn.setEnabled(True)
        for cb in [self.mask_ip_cb, self.dedup_packet_cb, self.trim_packet_cb]:
            cb.setEnabled(True)
        self.start_proc_btn.setEnabled(True)
        self.start_proc_btn.setText("Start")

    def start_pipeline_processing(self):
        if not self.base_dir:
            QMessageBox.warning(self, "Warning", "Please choose a folder to process.")
            return

        # 检查是否所有文件都已经被处理过
        all_processed, original_files, processed_files = self.check_already_processed_files()
        
        if all_processed and original_files:
            # 如果所有文件都已处理，显示已处理摘要并加载历史日志
            self.log_text.clear()
            self.summary_text.clear()
            self.update_log("--- Checking Working Directory ---")
            self.update_log(f"Found {len(original_files)} original files, all already processed.")
            self.show_already_processed_summary(original_files, processed_files)
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
        start_report += f"📂 Source Directory: {os.path.basename(self.base_dir)}\n"
        start_report += f"🔧 Processing Steps: {', '.join(enabled_steps)}\n"
        start_report += f"⏰ Started at: {QTime.currentTime().toString('hh:mm:ss')}\n"
        start_report += f"{'='*separator_length}\n"
        
        self.summary_text.append(start_report)

        self.pipeline_thread = PipelineThread(pipeline, self.base_dir)
        self.pipeline_thread.progress_signal.connect(self.handle_thread_progress)
        self.pipeline_thread.finished.connect(self.on_thread_finished)
        self.pipeline_thread.start()

        # Disable all controls during processing
        self.select_dir_btn.setEnabled(False)
        self.reset_btn.setEnabled(False)
        for cb in [self.mask_ip_cb, self.dedup_packet_cb, self.trim_packet_cb]:
            cb.setEnabled(False)
        self.start_proc_btn.setText("Stop")

    def handle_thread_progress(self, event_type: PipelineEvents, data: dict):
        """主槽函数，根据事件类型分发UI更新任务"""
        if event_type == PipelineEvents.PIPELINE_START:
            self.progress_bar.setMaximum(data.get('total_subdirs', 100))
        
        elif event_type == PipelineEvents.SUBDIR_START:
            self.progress_bar.setValue(data.get('current', 0))
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
            self.progress_bar.setValue(self.progress_bar.maximum()) # Ensure it reaches 100%
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
        completion_report += f"📁 Output Location: Same directory as input files\n"
        completion_report += f"📝 All processed files have suffixes to distinguish from originals.\n"
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

        # 保存summary report到文件
        self.save_summary_report_to_file()

        # Re-enable controls
        self.select_dir_btn.setEnabled(True)
        self.reset_btn.setEnabled(True)
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
        from datetime import datetime
        
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

    def save_summary_report_to_file(self):
        """将summary report保存到工作目录"""
        if not self.base_dir:
            return
        
        try:
            filename = self.generate_summary_report_filename()
            file_path = os.path.join(self.base_dir, filename)
            
            # 获取summary text的内容
            summary_content = self.summary_text.toPlainText()
            
            with open(file_path, 'w', encoding='utf-8') as f:
                from datetime import datetime
                f.write("# PktMask Summary Report\n")
                f.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# Working Directory: {self.base_dir}\n")
                f.write("#" + "="*68 + "\n\n")
                f.write(summary_content)
            
            self.update_log(f"Summary report saved: {filename}")
            
        except Exception as e:
            self.update_log(f"Error saving summary report: {str(e)}")

    def find_existing_summary_reports(self) -> List[str]:
        """查找工作目录中的现有summary report文件"""
        if not self.base_dir or not os.path.exists(self.base_dir):
            return []
        
        try:
            files = os.listdir(self.base_dir)
            summary_files = [f for f in files if f.startswith('summary_report_') and f.endswith('.txt')]
            # 按修改时间倒序排列，最新的在前
            summary_files.sort(key=lambda x: os.path.getmtime(os.path.join(self.base_dir, x)), reverse=True)
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
            file_path = os.path.join(self.base_dir, latest_file)
            
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

    def check_already_processed_files(self) -> Tuple[bool, List[str], List[str]]:
        """检查目录中的文件是否已经被处理过
        返回: (是否所有文件都已处理, 原始文件列表, 已处理文件列表)
        """
        if not self.base_dir or not os.path.exists(self.base_dir):
            return False, [], []
        
        try:
            # 获取当前启用的处理步骤
            enabled_steps = []
            if self.mask_ip_cb.isChecked():
                enabled_steps.append("-Masked")
            if self.dedup_packet_cb.isChecked():
                enabled_steps.append("-Deduped")
            if self.trim_packet_cb.isChecked():
                enabled_steps.append("-Trimmed")
            
            expected_suffix = "".join(enabled_steps)
            
            # 扫描目录中的pcap文件
            all_files = [f for f in os.listdir(self.base_dir) if f.endswith(('.pcap', '.pcapng'))]
            
            # 分离原始文件和已处理文件
            original_files = []
            processed_files = []
            
            for file in all_files:
                if any(suffix in file for suffix in ["-Masked", "-Deduped", "-Trimmed"]):
                    processed_files.append(file)
                else:
                    original_files.append(file)
            
            # 检查是否所有原始文件都有对应的已处理版本
            all_processed = True
            for orig_file in original_files:
                base_name, ext = os.path.splitext(orig_file)
                expected_processed = f"{base_name}{expected_suffix}{ext}"
                if expected_processed not in all_files:
                    all_processed = False
                    break
            
            return all_processed, original_files, processed_files
            
        except Exception as e:
            self.update_log(f"Error checking processed files: {str(e)}")
            return False, [], []

    def show_already_processed_summary(self, original_files: List[str], processed_files: List[str]):
        """显示已处理文件的摘要并尝试加载历史日志"""
        separator_length = 70
        
        # 显示已处理的提示
        already_processed_msg = f"{'='*separator_length}\n📋 FILES ALREADY PROCESSED\n{'='*separator_length}\n"
        already_processed_msg += f"📂 Working Directory: {os.path.basename(self.base_dir)}\n"
        already_processed_msg += f"✅ All {len(original_files)} original files have been processed.\n\n"
        
        already_processed_msg += f"📄 Original Files ({len(original_files)}):\n"
        for i, file in enumerate(sorted(original_files), 1):
            already_processed_msg += f"   {i:2d}. {file}\n"
        
        already_processed_msg += f"\n📦 Processed Files ({len(processed_files)}):\n"
        for i, file in enumerate(sorted(processed_files), 1):
            already_processed_msg += f"   {i:2d}. {file}\n"
        
        already_processed_msg += f"\n💡 No new processing required. Loading previous summary report...\n"
        already_processed_msg += f"{'='*separator_length}\n"
        
        self.summary_text.append(already_processed_msg)
        
        # 尝试加载历史summary report
        historical_content = self.load_latest_summary_report()
        if historical_content:
            self.summary_text.append("\n📖 Previous Processing Summary:")
            self.summary_text.append(historical_content)
            self.update_log("Loaded previous summary report from working directory.")
        else:
            self.summary_text.append("\n⚠️ No previous summary report found in the working directory.")
            self.update_log("No previous summary report found.")

def main():
    """主函数"""
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec()) 