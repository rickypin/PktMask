#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
主窗口模块
实现图形界面
"""

import os
import sys
import markdown
from typing import Optional
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QProgressBar, QTextEdit, QFileDialog,
    QMessageBox, QScrollArea, QSplitter, QTableWidget, QTableWidgetItem,
    QTabWidget, QFrame, QDialog, QCheckBox, QGridLayout
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QIcon, QTextCursor, QFontMetrics, QColor

from ..core.ip_processor import (
    prescan_addresses, generate_new_ipv4_address_hierarchical,
    generate_new_ipv6_address_hierarchical, process_file, stream_subdirectory_process
)
from pktmask.utils.path import resource_path
from pktmask.utils.pcap_dedup import process_file_dedup, select_files_for_processing
from scapy.all import wrpcap

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

class ProcessThread(QThread):
    """处理线程"""
    progress = pyqtSignal(str)
    finished = pyqtSignal()
    error = pyqtSignal(str)
    ip_mapping_signal = pyqtSignal(str, dict)  # 子目录名, IP映射

    def __init__(self, base_dir: str, process_type: str):
        super().__init__()
        self.base_dir = base_dir
        self.process_type = process_type
        self.is_running = True
        # 添加统计信息
        self.total_subdirs = 0
        self.processed_subdirs = 0
        self.skipped_subdirs = 0
        self.total_files = 0
        self.processed_files = 0
        self.skipped_files = 0
        self.failed_files = 0
        self.total_unique_ips = 0

    def run(self):
        try:
            if self.process_type == "ip_replacement":
                self.process_directory(self.base_dir)
            else:
                # 其他处理类型暂时显示 Coming Soon
                self.progress.emit(f"\n{self.process_type.replace('_', ' ').title()} - Coming Soon!")
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))

    def process_directory(self, base_dir: str):
        """处理目录"""
        if not self.is_running:
            return

        # 获取所有子目录
        subdirs = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]
        self.total_subdirs = len(subdirs)

        for i, subdir in enumerate(subdirs, 1):
            if not self.is_running:
                break

            subdir_path = os.path.join(base_dir, subdir)
            self.progress.emit(f"Processing subdirectory {i}/{self.total_subdirs}: {subdir}")

            # 使用stream_subdirectory_process处理子目录
            for message in stream_subdirectory_process(subdir_path, base_dir):
                if not self.is_running:
                    break
                
                if message.startswith("[SUBDIR_RESULT]"):
                    result = message.split(" ")[1]
                    if result == "SKIPPED":
                        self.skipped_subdirs += 1
                    elif result == "ERROR":
                        self.failed_files += 1
                    else:  # SUCCESS
                        self.processed_subdirs += 1
                else:
                    self.progress.emit(message)
                    
                    # 尝试从日志中提取统计信息
                    if "Processing completed" in message and "Successfully processed" in message:
                        try:
                            parts = message.split(", ")
                            for part in parts:
                                if "Successfully processed" in part:
                                    self.processed_files += int(part.split(" ")[2])
                                elif "Total time" in part:
                                    self.total_unique_ips += int(part.split(" ")[1])
                        except:
                            pass

            # 读取生成的replacement.log
            try:
                import json
                log_path = os.path.join(subdir_path, "replacement.log")
                if os.path.exists(log_path):
                    with open(log_path, "r", encoding="utf-8") as f:
                        log_data = json.load(f)
                        if "total_mapping" in log_data:
                            self.ip_mapping_signal.emit(subdir, log_data["total_mapping"])
                        # 自动累加总体统计
                        stats = log_data.get("stats", {})
                        self.processed_files += stats.get("processed_file_count", 0)
                        self.total_unique_ips += stats.get("total_unique_ips", 0)
            except Exception as e:
                self.progress.emit(f"Error reading replacement.log: {str(e)}")

        # 显示总体处理摘要
        self.progress.emit("\nProcessing completed. Summary:")
        self.progress.emit(f"Total subdirectories: {self.total_subdirs}")
        self.progress.emit(f"Processed subdirectories: {self.processed_subdirs}")
        self.progress.emit(f"Skipped subdirectories: {self.skipped_subdirs}")
        self.progress.emit(f"Total files: {self.processed_files + self.skipped_files + self.failed_files}")
        self.progress.emit(f"Processed files: {self.processed_files}")
        self.progress.emit(f"Skipped files: {self.skipped_files}")
        self.progress.emit(f"Failed files: {self.failed_files}")
        self.progress.emit(f"Total unique IPs: {self.total_unique_ips}\n")

    def stop(self):
        """停止处理"""
        self.is_running = False

class DeduplicateThread(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal()
    error = pyqtSignal(str)
    report_signal = pyqtSignal(str)

    def __init__(self, base_dir):
        super().__init__()
        self.base_dir = base_dir
        self.is_running = True
        self.total_files = 0
        self.deduped_files = 0
        self.failed_files = 0
        self.total_packets = 0
        self.total_unique_packets = 0
        self.report_lines = []

    def run(self):
        try:
            all_known_suffixes = ['-Deduped', '-Replaced', '-Deduped-Replaced']
            current_suffix = '-Deduped'
            subdirs = [d for d in os.listdir(self.base_dir) if os.path.isdir(os.path.join(self.base_dir, d))]
            self.progress.emit(f"Found {len(subdirs)} subdirectories.")
            for idx, subdir in enumerate(subdirs, 1):
                if not self.is_running:
                    break
                subdir_path = os.path.join(self.base_dir, subdir)
                self.progress.emit(f"Processing subdirectory {idx}/{len(subdirs)}: {subdir}")
                self.report_lines.append(f"Subdirectory: {subdir}")
                files_to_process, info = select_files_for_processing(subdir_path, all_known_suffixes, current_suffix)
                self.progress.emit(f"  {info}")
                self.report_lines.append(f"  {info}\n")
                if not files_to_process:
                    continue
                for fname in files_to_process:
                    fpath = os.path.join(subdir_path, fname)
                    error_log = []
                    packets, total, deduped = process_file_dedup(fpath, error_log)
                    self.total_files += 1
                    self.total_packets += total
                    self.total_unique_packets += deduped
                    if packets is None:
                        self.failed_files += 1
                        self.progress.emit(f"  [FAILED] {fname} ({'; '.join(error_log)})")
                        self.report_lines.append(f"  [FAILED] {fname} ({'; '.join(error_log)})\n")
                        continue
                    out_name = fname.rsplit('.', 1)
                    out_file = out_name[0] + '-Deduped.' + out_name[1]
                    out_path = os.path.join(subdir_path, out_file)
                    try:
                        wrpcap(out_path, packets)
                        self.deduped_files += 1
                        self.progress.emit(f"  [OK] {fname} -> {out_file} (original: {total}, deduped: {deduped})")
                        self.report_lines.append(f"  {fname} -> {out_file} (original: {total}, deduped: {deduped})")
                    except Exception as e:
                        self.failed_files += 1
                        self.progress.emit(f"  [FAILED] {fname} (write error: {str(e)})")
                        self.report_lines.append(f"  [FAILED] {fname} (write error: {str(e)})\n")
                self.report_lines.append("")
            # 汇总
            self.progress.emit(f"\nDeduplication completed. Total files: {self.total_files}, Deduped: {self.deduped_files}, Failed: {self.failed_files}")
            self.progress.emit(f"Total packets: {self.total_packets}, Unique packets: {self.total_unique_packets}")
            self.report_lines.append(f"\nTotal files processed: {self.total_files}")
            self.report_lines.append(f"Total packets: {self.total_packets}")
            self.report_lines.append(f"Total unique packets: {self.total_unique_packets}")
            self.report_signal.emit('\n'.join(self.report_lines))
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))

class MainWindow(QMainWindow):
    """主窗口"""
    def __init__(self):
        super().__init__()
        self.process_thread: Optional[ProcessThread] = None
        self.ip_mapping_tables = {}  # 子目录名 -> QTableWidget
        self.all_ip_mappings = {}    # 子目录名 -> replacement.log内容
        # Set allowed_root to user's home directory by default
        self.allowed_root = os.path.expanduser("~")
        self.current_process_type = "ip_replacement"  # 当前选择的处理类型
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
        self.dir_prefix_label = QLabel("Target Directory: ")
        self.dir_prefix_label.setStyleSheet("font-size: 13pt; font-weight: bold; color: #174ea6; margin-bottom: 2px;")
        self.dir_prefix_label.setMinimumHeight(32)
        self.dir_prefix_label.setMaximumHeight(36)
        self.dir_prefix_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self.dir_content_label = QLabel("Select a directory")
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
        self.select_dir_btn = QPushButton("Select Directory")
        self.select_dir_btn.setMinimumHeight(32)
        self.select_dir_btn.clicked.connect(self.select_directory)
        self.clear_dir_btn = QPushButton("Clear")
        self.clear_dir_btn.setMinimumHeight(32)
        self.clear_dir_btn.clicked.connect(self.clear_directory)
        self.clear_dir_btn.setEnabled(False)
        self.ip_replacement_btn = QPushButton("IP Replacement")
        self.ip_replacement_btn.setMinimumHeight(32)
        self.ip_replacement_btn.clicked.connect(lambda: self.select_process("ip_replacement"))
        self.ip_replacement_btn.setEnabled(False)
        self.deduplicate_btn = QPushButton("Deduplicate")
        self.deduplicate_btn.setMinimumHeight(32)
        self.deduplicate_btn.clicked.connect(lambda: self.select_process("deduplicate"))
        self.deduplicate_btn.setEnabled(False)
        self.slicing_btn = QPushButton("Slicing")
        self.slicing_btn.setMinimumHeight(32)
        self.slicing_btn.clicked.connect(lambda: self.select_process("slicing"))
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
        log_label = QLabel("Processing Log:")
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
        report_label = QLabel("Processing Report:")
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
        self.dir_prefix_label.setText("Target Directory: ")
        self.dir_content_label.setText("Select a directory")
        self.dir_content_label.setStyleSheet("font-size: 13pt; font-weight: bold; color: #aaa; margin-bottom: 2px;")
        self.log_text.setPlainText(
            "Welcome to PktMask!\n\nInstructions:\n1. Click 'Select Directory' to choose a folder to process.\n2. Choose a processing method (IP Replacement, Deduplicate, Slicing).\n3. Processing results and logs will be shown below.\n\nFor detailed instructions, click the 'User Guide' link in the top right corner."
        )
        # 加载 User Guide 内容
        try:
            with open(resource_path('summary.md'), 'r', encoding='utf-8') as f:
                content = f.read()
            import markdown
            self.report_text.setHtml(markdown.markdown(content))
        except Exception as e:
            self.report_text.setPlainText(f"Error loading guide: {str(e)}")

    def select_directory(self):
        """选择目录"""
        import glob
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        dir_path = QFileDialog.getExistingDirectory(self, "Select directory to process", desktop_path)
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
            self.dir_prefix_label.setText("Target Directory: ")
            self.dir_content_label.setText(dir_path)
            self.dir_content_label.setStyleSheet("font-size: 13pt; font-weight: bold; color: #174ea6; margin-bottom: 2px;")
            self.clear_dir_btn.setEnabled(True)
            self.ip_replacement_btn.setEnabled(True)
            self.deduplicate_btn.setEnabled(True)
            self.slicing_btn.setEnabled(True)
        else:
            self.dir_prefix_label.setText("Target Directory: ")
            self.dir_content_label.setText("Select a directory")
            self.dir_content_label.setStyleSheet("font-size: 13pt; font-weight: bold; color: #aaa; margin-bottom: 2px;")

    def clear_directory(self):
        """清除目录选择"""
        self.base_dir = None
        self.dir_prefix_label.setText("Target Directory: ")
        self.dir_content_label.setText("Select a directory")
        self.dir_content_label.setStyleSheet("font-size: 13pt; font-weight: bold; color: #aaa; margin-bottom: 2px;")
        self.clear_dir_btn.setEnabled(False)
        self.ip_replacement_btn.setEnabled(False)
        self.deduplicate_btn.setEnabled(False)
        self.slicing_btn.setEnabled(False)
        self.show_initial_guides()

    def select_process(self, process_type: str):
        self.current_process_type = process_type
        self.log_text.clear()
        self.report_text.clear()
        if process_type == "deduplicate":
            self.start_deduplicate()
        else:
            self.start_processing()

    def start_processing(self):
        """开始处理"""
        if not hasattr(self, 'base_dir'):
            QMessageBox.warning(self, "Warning", "Please select a directory to process.")
            return

        self.all_ip_mappings = {}  # 新处理前清空
        # 在 log 和 report 区域插入 Processing 类型和开始提示
        process_type_str = self.current_process_type.replace('_', ' ').title()
        self.log_text.append(f"--- Processing Type: {process_type_str} | Status: START ---\n")
        self.report_text.clear()  # 确保每次都清空再插入
        self.report_text.append(f"--- Processing Type: {process_type_str} | Status: START ---\n")

        self.process_thread = ProcessThread(self.base_dir, self.current_process_type)
        self.process_thread.progress.connect(self.update_progress)
        self.process_thread.finished.connect(self.processing_finished)
        self.process_thread.error.connect(self.processing_error)
        self.process_thread.ip_mapping_signal.connect(self.display_ip_mapping)

        self.process_thread.start()
        self.select_dir_btn.setEnabled(False)
        self.clear_dir_btn.setEnabled(False)
        self.ip_replacement_btn.setEnabled(False)
        self.deduplicate_btn.setEnabled(False)
        self.slicing_btn.setEnabled(False)

    def update_progress(self, message: str):
        """更新进度"""
        self.log_text.append(message)
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )

    def display_ip_mapping(self, subdir: str, _):
        """显示 IP 映射"""
        import json
        import os
        from PyQt6.QtGui import QTextCursor
        # 只用 replacement.log 作为数据源
        log_path = os.path.join(self.base_dir, subdir, "replacement.log")
        if not os.path.exists(log_path):
            self.log_text.append(f"File not found: {log_path}")
            return
        with open(log_path, "r", encoding="utf-8") as f:
            log_data = json.load(f)
        # 缓存到全局映射
        self.all_ip_mappings[subdir] = log_data

        # 更新报告显示，保留头部 Processing Type/START 信息
        text = ""
        for subdir_name, log_data in self.all_ip_mappings.items():
            stats = log_data.get("stats", {})
            file_mappings = log_data.get("file_mappings", {})
            total_mapping = log_data.get("total_mapping", {})
            text += f"Subdirectory: {subdir_name}\n"
            text += "=" * 40 + "\n"
            text += "[Basic Stats]\n"
            for k, v in stats.items():
                text += f"{k}: {v}\n"
            text += "\n"
            for fname, mapping in file_mappings.items():
                text += f"File: {fname}\n"
                for orig, new in mapping.items():
                    text += f"  {orig:<20} -> {new}\n"
                text += "\n"
            text += "[Total Mapping]\n"
            for orig, new in total_mapping.items():
                text += f"{orig:<20} -> {new}\n"
            text += "\n" + ("-"*40) + "\n\n"
        # 保留头部 Processing Type/START 信息
        current_head = self.report_text.toPlainText()
        head_str = ''
        if 'Processing Type' in current_head and 'Status: START' in current_head:
            head_lines = current_head.split('\n')
            head = []
            for line in head_lines:
                if 'Processing Type' in line and 'Status: START' in line:
                    head.append(line)
            if head:
                head_str = '\n'.join(head) + '\n\n'
        self.report_text.setPlainText(head_str + text)
        self.report_text.moveCursor(QTextCursor.MoveOperation.End)

    def processing_finished(self):
        """处理完成"""
        process_type_str = self.current_process_type.replace('_', ' ').title()
        self.log_text.append(f"\n--- Processing Type: {process_type_str} | Status: END ---")
        self.report_text.append(f"\n--- Processing Type: {process_type_str} | Status: END ---")
        self.select_dir_btn.setEnabled(True)
        self.clear_dir_btn.setEnabled(True)
        self.ip_replacement_btn.setEnabled(True)
        self.deduplicate_btn.setEnabled(True)
        self.slicing_btn.setEnabled(True)

    def processing_error(self, error_message: str):
        """处理出错"""
        QMessageBox.critical(self, "Error", f"An error occurred during processing: {error_message}")
        self.select_dir_btn.setEnabled(True)
        self.clear_dir_btn.setEnabled(True)
        self.ip_replacement_btn.setEnabled(True)
        self.deduplicate_btn.setEnabled(True)
        self.slicing_btn.setEnabled(True)

    def show_guide_dialog(self):
        """弹窗显示用户指南"""
        if self.current_process_type == "ip_replacement":
            try:
                with open(resource_path('summary.md'), 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception as e:
                content = f"Error loading guide: {str(e)}"
        else:
            content = f"# {self.current_process_type.replace('_', ' ').title()}\n\nComing Soon!"
        dialog = GuideDialog(self.current_process_type.replace('_', ' ').title(), content, self)
        dialog.exec()

    def start_deduplicate(self):
        process_type_str = "Deduplicate"
        self.log_text.append(f"--- Processing Type: {process_type_str} | Status: START ---\n")
        self.report_text.clear()
        self.report_text.append(f"--- Processing Type: {process_type_str} | Status: START ---\n")
        self.dedup_thread = DeduplicateThread(self.base_dir)
        self.dedup_thread.progress.connect(self.update_progress)
        self.dedup_thread.finished.connect(self.dedup_finished)
        self.dedup_thread.error.connect(self.processing_error)
        self.dedup_thread.report_signal.connect(self.update_report)
        self.dedup_thread.start()
        self.select_dir_btn.setEnabled(False)
        self.clear_dir_btn.setEnabled(False)
        self.ip_replacement_btn.setEnabled(False)
        self.deduplicate_btn.setEnabled(False)
        self.slicing_btn.setEnabled(False)

    def dedup_finished(self):
        process_type_str = "Deduplicate"
        self.log_text.append(f"\n--- Processing Type: {process_type_str} | Status: END ---")
        self.report_text.append(f"\n--- Processing Type: {process_type_str} | Status: END ---")
        self.select_dir_btn.setEnabled(True)
        self.clear_dir_btn.setEnabled(True)
        self.ip_replacement_btn.setEnabled(True)
        self.deduplicate_btn.setEnabled(True)
        self.slicing_btn.setEnabled(True)

    def update_report(self, report):
        # 保留头部 Processing Type/START 信息
        current_head = self.report_text.toPlainText()
        head_str = ''
        if 'Processing Type' in current_head and 'Status: START' in current_head:
            head_lines = current_head.split('\n')
            head = []
            for line in head_lines:
                if 'Processing Type' in line and 'Status: START' in line:
                    head.append(line)
            if head:
                head_str = '\n'.join(head) + '\n\n'
        self.report_text.setPlainText(head_str + report)
        self.report_text.moveCursor(QTextCursor.MoveOperation.End)

def main():
    """主函数"""
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec()) 