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
from typing import Optional
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QProgressBar, QTextEdit, QFileDialog,
    QMessageBox, QScrollArea, QSplitter, QTableWidget, QTableWidgetItem,
    QTabWidget, QFrame, QDialog, QCheckBox, QGridLayout
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QIcon, QTextCursor, QFontMetrics, QColor

# Refactored imports
from pktmask.core.pipeline import Pipeline
from pktmask.core.events import PipelineEvents
from pktmask.core.factory import create_step
from pktmask.utils.path import resource_path

PROCESS_DISPLAY_NAMES = {
    "mask_ip": "Mask IP",
    "remove_dupes": "Remove Dupes",
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
        self.current_process_type = "mask_ip"
        self.init_ui()

    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle("PktMask - Protect Your Packet Data")
        self.setMinimumSize(1200, 800)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(14)
        main_layout.setContentsMargins(22, 18, 22, 18)

        # 顶部区域：Target Directory（左）+ User Guide（右），按钮区全部靠左
        control_area = QWidget()
        grid = QGridLayout(control_area)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(0)
        grid.setVerticalSpacing(8)
        # Target Directory（前缀+内容分开，左对齐）
        self.dir_prefix_label = QLabel("Input Folder: ")
        self.dir_prefix_label.setStyleSheet("font-size: 13pt; font-weight: bold; color: #174ea6; margin-bottom: 2px;")
        self.dir_prefix_label.setMinimumHeight(32)
        self.dir_prefix_label.setMaximumHeight(36)
        self.dir_prefix_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self.dir_content_label = QLabel("Choose a folder")
        self.dir_content_label.setStyleSheet("font-size: 13pt; font-weight: bold; color: #aaa; margin-bottom: 2px;")
        self.dir_content_label.setMinimumHeight(32)
        self.dir_content_label.setMaximumHeight(36)
        self.dir_content_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.dir_content_label.setWordWrap(False)
        self.dir_content_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        dir_hbox = QHBoxLayout()
        dir_hbox.setContentsMargins(0, 0, 0, 0)
        dir_hbox.setSpacing(0)
        dir_hbox.addWidget(self.dir_prefix_label)
        dir_hbox.addWidget(self.dir_content_label)
        dir_hbox.addStretch()
        dir_widget_wrap = QWidget()
        dir_widget_wrap.setLayout(dir_hbox)
        # User Guide 超链接，右对齐
        self.guide_link = QLabel('<a href="#" style="color:#1976d2;text-decoration:underline;">User Guide</a>')
        self.guide_link.setTextFormat(Qt.TextFormat.RichText)
        self.guide_link.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.guide_link.setOpenExternalLinks(False)
        self.guide_link.linkActivated.connect(self.show_guide_dialog)
        self.guide_link.setStyleSheet("font-size: 11pt; padding-right: 2px;")
        # 按钮区：全部靠左
        btns_hbox = QHBoxLayout()
        btns_hbox.setContentsMargins(0, 0, 0, 0)
        btns_hbox.setSpacing(14)
        self.select_dir_btn = QPushButton("Choose Folder")
        self.select_dir_btn.setMinimumHeight(32)
        self.select_dir_btn.clicked.connect(self.choose_folder)
        self.clear_dir_btn = QPushButton("Reset")
        self.clear_dir_btn.setMinimumHeight(32)
        self.clear_dir_btn.clicked.connect(self.reset_folder)
        self.clear_dir_btn.setEnabled(False)
        self.ip_replacement_btn = QPushButton("Mask IP")
        self.ip_replacement_btn.setMinimumHeight(32)
        self.ip_replacement_btn.clicked.connect(lambda: self.select_process("mask_ip"))
        self.ip_replacement_btn.setEnabled(False)
        self.deduplicate_btn = QPushButton("Remove Dupes")
        self.deduplicate_btn.setMinimumHeight(32)
        self.deduplicate_btn.clicked.connect(lambda: self.select_process("remove_dupes"))
        self.deduplicate_btn.setEnabled(False)
        self.slicing_btn = QPushButton("Trim Packet")
        self.slicing_btn.setMinimumHeight(32)
        self.slicing_btn.clicked.connect(lambda: self.select_process("trim_packet"))
        self.slicing_btn.setEnabled(False)
        btns_hbox.addWidget(self.select_dir_btn)
        btns_hbox.addWidget(self.clear_dir_btn)
        btns_hbox.addWidget(self.ip_replacement_btn)
        btns_hbox.addWidget(self.deduplicate_btn)
        btns_hbox.addWidget(self.slicing_btn)
        btns_hbox.addStretch()
        btns_widget = QWidget()
        btns_widget.setLayout(btns_hbox)
        # 布局到 grid
        grid.addWidget(dir_widget_wrap, 0, 0, alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        grid.addWidget(self.guide_link, 0, 1, alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        grid.addWidget(btns_widget, 1, 0, 1, 2, alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        main_layout.addWidget(control_area, 0)
        # Processing Area（下半部分）
        body_widget = QWidget()
        body_layout = QHBoxLayout(body_widget)
        body_layout.setSpacing(18)
        body_layout.setContentsMargins(0, 0, 0, 0)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        # 左侧：处理日志
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        log_layout.setSpacing(8)
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        log_label = QLabel("Log:")
        log_label.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        log_label.setStyleSheet("color: #222; margin-bottom: 4px;")
        log_layout.addWidget(log_label, alignment=Qt.AlignmentFlag.AlignTop)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        self.splitter.addWidget(log_widget)
        # 右侧：处理报告
        report_widget = QWidget()
        report_layout = QVBoxLayout(report_widget)
        report_layout.setSpacing(8)
        report_layout.setContentsMargins(0, 0, 0, 0)
        report_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        report_label = QLabel("Summary:")
        report_label.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        report_label.setStyleSheet("color: #222; margin-bottom: 4px;")
        report_layout.addWidget(report_label, alignment=Qt.AlignmentFlag.AlignTop)
        self.report_text = QTextEdit()
        self.report_text.setReadOnly(True)
        report_layout.addWidget(self.report_text)
        self.splitter.addWidget(report_widget)
        self.splitter.setSizes([200, 300])
        body_layout.addWidget(self.splitter)
        main_layout.addWidget(body_widget, 1)
        self.show_initial_guides()
        # Step 1 按钮样式（灰色主色，现代圆角，交互风格与Step2一致）
        btn_style_step1 = """
            QPushButton {
                background-color: #e0e0e0;
                color: #222;
                border-radius: 6px;
                font-size: 11pt;
                padding: 4px 18px;
                font-weight: normal;
                transition: background 0.2s, font-weight 0.2s;
            }
            QPushButton:enabled:hover {
                background-color: #d5d5d5;
                cursor: PointingHandCursor;
            }
            QPushButton:pressed {
                background-color: #cccccc;
            }
            QPushButton:disabled {
                background-color: #f5f5f5;
                color: #aaa;
            }
        """
        self.select_dir_btn.setStyleSheet(btn_style_step1)
        self.clear_dir_btn.setStyleSheet(btn_style_step1)
        # Step 2 按钮样式（蓝色主色，所有状态一致，无选中高亮）
        btn_style_step2 = """
            QPushButton {
                background-color: #1976d2;
                color: #fff;
                border-radius: 6px;
                font-size: 11pt;
                padding: 4px 18px;
                font-weight: normal;
                transition: background 0.2s, font-weight 0.2s;
            }
            QPushButton:enabled:hover {
                background-color: #1565c0;
                cursor: PointingHandCursor;
            }
            QPushButton:pressed {
                background-color: #0b2850;
            }
            QPushButton:disabled {
                background-color: #e3eaf3;
                color: #b0b0b0;
            }
        """
        self.ip_replacement_btn.setStyleSheet(btn_style_step2)
        self.deduplicate_btn.setStyleSheet(btn_style_step2)
        self.slicing_btn.setStyleSheet(btn_style_step2)
        # 鼠标手型
        from PyQt6.QtCore import Qt as QtCoreQt
        self.select_dir_btn.setCursor(QtCoreQt.CursorShape.PointingHandCursor)
        self.clear_dir_btn.setCursor(QtCoreQt.CursorShape.PointingHandCursor)
        self.ip_replacement_btn.setCursor(QtCoreQt.CursorShape.PointingHandCursor)
        self.deduplicate_btn.setCursor(QtCoreQt.CursorShape.PointingHandCursor)
        self.slicing_btn.setCursor(QtCoreQt.CursorShape.PointingHandCursor)

    def show_initial_guides(self):
        """启动时在log和report区域显示指引和User Guide"""
        self.dir_prefix_label.setText("Input Folder: ")
        self.dir_content_label.setText("Choose a folder")
        self.dir_content_label.setStyleSheet("font-size: 13pt; font-weight: bold; color: #aaa; margin-bottom: 2px;")
        self.log_text.setPlainText(
            "Welcome to PktMask!\n\nInstructions:\n1. Click 'Choose Folder' to choose a folder to process.\n2. Choose a processing method (Mask IP, Remove Dupes, Trim Packet).\n3. Processing results and logs will be shown below.\n\nFor detailed instructions, click the 'User Guide' link in the top right corner."
        )
        # 加载 User Guide 内容
        try:
            with open(resource_path('summary.md'), 'r', encoding='utf-8') as f:
                content = f.read()
            import markdown
            self.report_text.setHtml(markdown.markdown(content))
        except Exception as e:
            self.report_text.setPlainText(f"Error loading guide: {str(e)}")

    def choose_folder(self):
        """选择目录"""
        import glob
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        dir_path = QFileDialog.getExistingDirectory(self, "Choose folder to process", desktop_path)
        if dir_path:
            if not os.path.exists(dir_path):
                QMessageBox.warning(self, "Warning", "The selected directory does not exist.")
                return
            base_dir = os.path.abspath(self.allowed_root)
            user_dir = os.path.abspath(dir_path)
            if os.path.commonpath([base_dir]) != os.path.commonpath([base_dir, user_dir]):
                QMessageBox.warning(self, "Warning", "The selected directory is outside the allowed workspace!")
                return
            if not os.access(user_dir, os.R_OK):
                QMessageBox.warning(self, "Warning", "No read permission for the selected directory.")
                return
            if not os.access(user_dir, os.W_OK):
                QMessageBox.warning(self, "Warning", "No write permission for the selected directory.")
                return
            self.base_dir = dir_path
            # 只显示路径，深蓝色
            self.dir_prefix_label.setText("Input Folder: ")
            self.dir_content_label.setText(dir_path)
            self.dir_content_label.setStyleSheet("font-size: 13pt; font-weight: bold; color: #174ea6; margin-bottom: 2px;")
            self.clear_dir_btn.setEnabled(True)
            self.ip_replacement_btn.setEnabled(True)
            self.deduplicate_btn.setEnabled(True)
            self.slicing_btn.setEnabled(True)
        else:
            self.dir_prefix_label.setText("Input Folder: ")
            self.dir_content_label.setText("Choose a folder")
            self.dir_content_label.setStyleSheet("font-size: 13pt; font-weight: bold; color: #aaa; margin-bottom: 2px;")

    def reset_folder(self):
        """清除目录选择"""
        self.base_dir = None
        self.dir_prefix_label.setText("Input Folder: ")
        self.dir_content_label.setText("Choose a folder")
        self.dir_content_label.setStyleSheet("font-size: 13pt; font-weight: bold; color: #aaa; margin-bottom: 2px;")
        self.clear_dir_btn.setEnabled(False)
        self.ip_replacement_btn.setEnabled(False)
        self.deduplicate_btn.setEnabled(False)
        self.slicing_btn.setEnabled(False)
        self.show_initial_guides()

    def select_process(self, process_type: str):
        if not self.base_dir:
            QMessageBox.warning(self, "Warning", "Please choose a folder to process.")
            return

        self.current_process_type = process_type
        self.log_text.clear()
        self.report_text.clear()
        self.all_ip_reports.clear()

        # 使用工厂模式创建处理步骤
        try:
            if self.current_process_type == "trim_packet":
                self.log_text.append("Trim Packet feature is coming soon!")
                return
            
            step = create_step(self.current_process_type)
            pipeline = Pipeline(steps=[step])
            self.start_processing(pipeline)

        except ValueError as e:
            self.log_text.append(f"Error: {e}")
            return
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An unexpected error occurred while preparing the process: {e}")
            return

    def start_processing(self, pipeline: Pipeline):
        process_type_str = PROCESS_DISPLAY_NAMES.get(self.current_process_type, self.current_process_type.replace('_', ' ').title())
        self.log_text.append(f"--- Processing Type: {process_type_str} | Status: START ---\n")
        self.report_text.append(f"--- Processing Type: {process_type_str} | Status: START ---\n")

        self.pipeline_thread = PipelineThread(pipeline, self.base_dir)
        self.pipeline_thread.progress_signal.connect(self.handle_thread_progress)
        self.pipeline_thread.start()

        self.select_dir_btn.setEnabled(False)
        self.clear_dir_btn.setEnabled(False)
        self.ip_replacement_btn.setEnabled(False)
        self.deduplicate_btn.setEnabled(False)
        self.slicing_btn.setEnabled(False)

    def handle_thread_progress(self, event_type: PipelineEvents, data: dict):
        """主槽函数，根据事件类型分发UI更新任务"""
        if event_type == PipelineEvents.LOG:
            self.update_log(data['message'])
        elif event_type == PipelineEvents.STEP_SUMMARY and data['type'] == 'mask_ip':
            self.update_ip_report(data['report'])
        elif event_type == PipelineEvents.STEP_SUMMARY and data['type'] == 'remove_dupes':
            self.update_dedup_report(data)
        elif event_type == PipelineEvents.PIPELINE_END:
            self.processing_finished()
        elif event_type == PipelineEvents.ERROR:
            self.processing_error(data['message'])
        # Other events like 'subdir_start' can be used for finer-grained progress bars in the future

    def update_log(self, message: str):
        self.log_text.append(message)
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())

    def update_ip_report(self, report_data: dict):
        subdir = report_data.get('rel_subdir', 'Unknown Subdir')
        self.all_ip_reports[subdir] = report_data

        text = ""
        for subdir_name, data in self.all_ip_reports.items():
            stats = data.get("stats", {})
            file_mappings = data.get("file_mappings", {})
            total_mapping = data.get("total_mapping", {})
            
            text += f"Subdirectory: {subdir_name}\n"
            text += "=" * 40 + "\n"
            text += "[Basic Stats]\n"
            text += json.dumps(stats, indent=2) + "\n\n"
            
            text += "[File Mappings]\n"
            for fname, mapping in file_mappings.items():
                text += f"File: {fname}\n"
                for orig, new in mapping.items():
                    text += f"  {orig:<40} -> {new}\n"
                text += "\n"
            
            text += "[Total Mapping]\n"
            for orig, new in total_mapping.items():
                text += f"{orig:<40} -> {new}\n"
            text += "\n" + ("-"*40) + "\n\n"

        self.set_report_text(text)
    
    def update_dedup_report(self, summary_data: dict):
        text = f"Remove Dupes Summary:\n"
        text += "=" * 40 + "\n"
        text += f"Processed Files: {summary_data.get('processed_files', 0)}\n"
        text += f"Total Original Packets: {summary_data.get('total_packets', 0)}\n"
        text += f"Total Unique Packets: {summary_data.get('total_unique_packets', 0)}\n"
        self.set_report_text(text)

    def set_report_text(self, text: str):
        """Helper to set report text while preserving the header."""
        process_type_str = PROCESS_DISPLAY_NAMES.get(self.current_process_type, self.current_process_type.replace('_', ' ').title())
        head_str = f"--- Processing Type: {process_type_str} | Status: START ---\n\n"
        self.report_text.setPlainText(head_str + text)
        self.report_text.moveCursor(QTextCursor.MoveOperation.End)

    def processing_finished(self):
        process_type_str = PROCESS_DISPLAY_NAMES.get(self.current_process_type, self.current_process_type.replace('_', ' ').title())
        self.log_text.append(f"\n--- Processing Type: {process_type_str} | Status: END ---")
        self.report_text.append(f"\n--- Processing Type: {process_type_str} | Status: END ---")
        self.select_dir_btn.setEnabled(True)
        self.clear_dir_btn.setEnabled(True)
        self.ip_replacement_btn.setEnabled(True)
        self.deduplicate_btn.setEnabled(True)
        self.slicing_btn.setEnabled(True)

    def processing_error(self, error_message: str):
        QMessageBox.critical(self, "Error", f"An error occurred during processing:\n{error_message}")
        self.processing_finished()

    def show_guide_dialog(self):
        """弹窗显示用户指南"""
        display_name = PROCESS_DISPLAY_NAMES.get(self.current_process_type, self.current_process_type)
        if self.current_process_type == "mask_ip":
            try:
                with open(resource_path('summary.md'), 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception as e:
                content = f"Error loading guide: {str(e)}"
        else:
            content = f"# {display_name}\n\nComing Soon!"
        dialog = GuideDialog(display_name, content, self)
        dialog.exec()

def main():
    """主函数"""
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec()) 