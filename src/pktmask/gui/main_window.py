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
    QTabWidget, QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QIcon, QTextCursor

from ..core.ip_processor import (
    prescan_addresses, generate_new_ipv4_address_hierarchical,
    generate_new_ipv6_address_hierarchical, process_file, stream_subdirectory_process
)

class ProcessThread(QThread):
    """处理线程"""
    progress = pyqtSignal(str)
    finished = pyqtSignal()
    error = pyqtSignal(str)
    ip_mapping_signal = pyqtSignal(str, dict)  # 新增：子目录名, IP映射

    def __init__(self, base_dir: str):
        super().__init__()
        self.base_dir = base_dir
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
            self.process_directory(self.base_dir)
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
                        # 如有需要可累加其他统计项
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

class MainWindow(QMainWindow):
    """主窗口"""
    def __init__(self):
        super().__init__()
        self.process_thread: Optional[ProcessThread] = None
        self.ip_mapping_tables = {}  # 子目录名 -> QTableWidget
        self.all_ip_mappings = {}    # 子目录名 -> replacement.log内容
        self.init_ui()

    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle("PktMask - IP Address Replacement Tool")
        self.setMinimumSize(1200, 800)

        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 主水平布局
        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # 左侧：操作按钮+日志
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setSpacing(15)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # 操作按钮区
        op_widget = QWidget()
        op_layout = QVBoxLayout(op_widget)
        op_layout.setSpacing(10)
        op_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        button_title = QLabel("Operations:")
        button_title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        op_layout.addWidget(button_title)

        self.select_dir_btn = QPushButton("Select Directory")
        self.select_dir_btn.setMinimumHeight(40)
        self.select_dir_btn.clicked.connect(self.select_directory)
        op_layout.addWidget(self.select_dir_btn)

        self.process_btn = QPushButton("Start Processing")
        self.process_btn.setMinimumHeight(40)
        self.process_btn.clicked.connect(self.start_processing)
        self.process_btn.setEnabled(False)
        op_layout.addWidget(self.process_btn)

        self.stop_btn = QPushButton("Stop Processing")
        self.stop_btn.setMinimumHeight(40)
        self.stop_btn.clicked.connect(self.stop_processing)
        self.stop_btn.setEnabled(False)
        op_layout.addWidget(self.stop_btn)

        op_layout.addStretch()
        left_layout.addWidget(op_widget, 0)

        # 日志区
        log_label = QLabel("Processing Log:")
        log_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        left_layout.addWidget(log_label)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        left_layout.addWidget(self.log_text, 1)

        main_layout.addWidget(left_widget, 2)

        # 右侧：Tab（IP映射关系/说明）
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setSpacing(10)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.mapping_tab = QTabWidget()
        self.mapping_tab.setTabPosition(QTabWidget.TabPosition.North)
        self.mapping_tab.setMovable(False)
        self.mapping_tab.setTabsClosable(False)

        # IP映射关系Tab内容：QScrollArea + 垂直布局
        self.mapping_scroll = QScrollArea()
        self.mapping_scroll.setWidgetResizable(True)
        self.mapping_scroll.setStyleSheet("background-color: #232323;")
        self.mapping_container = QWidget()
        self.mapping_container.setStyleSheet("background-color: #232323; color: #fff;")
        self.mapping_vlayout = QVBoxLayout(self.mapping_container)
        self.mapping_vlayout.setSpacing(20)
        self.mapping_vlayout.setContentsMargins(10, 10, 10, 10)
        self.mapping_scroll.setWidget(self.mapping_container)
        self.mapping_tab.addTab(self.mapping_scroll, "IP Mapping")

        # 说明Tab
        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setMinimumHeight(150)
        # 统一资源路径查找
        def resource_path(relative_path):
            import sys, os
            if hasattr(sys, '_MEIPASS'):
                base_path = sys._MEIPASS
                app_resource_path = os.path.join(sys._MEIPASS, 'pktmask', 'resources', os.path.basename(relative_path))
                if os.path.exists(app_resource_path):
                    return app_resource_path
                alt_path = os.path.join(os.path.dirname(sys.executable), 'Resources', 'pktmask', 'resources', os.path.basename(relative_path))
                if os.path.exists(alt_path):
                    return alt_path
            else:
                base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            return os.path.join(base_path, relative_path)
        try:
            summary_path = resource_path('resources/summary.md')
            with open(summary_path, "r", encoding="utf-8") as f:
                summary_content = f.read()
            import markdown
            summary_html = markdown.markdown(summary_content)
            self.summary_text.setHtml(summary_html)
        except Exception as e:
            self.summary_text.setText(f"无法加载说明文档：{str(e)}")
        self.mapping_tab.addTab(self.summary_text, "IP Address Replacement Instructions")
        self.mapping_tab.setCurrentIndex(0)
        right_layout.addWidget(self.mapping_tab)
        right_widget.setLayout(right_layout)
        main_layout.addWidget(right_widget, 3)

    def select_directory(self):
        """选择目录"""
        # 获取用户桌面路径
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        dir_path = QFileDialog.getExistingDirectory(self, "选择要处理的目录", desktop_path)
        if dir_path:
            self.base_dir = dir_path
            self.process_btn.setEnabled(True)
            self.log_text.append(f"Selected directory: {dir_path}")

    def start_processing(self):
        """开始处理"""
        if not hasattr(self, 'base_dir'):
            QMessageBox.warning(self, "Warning", "Please select a directory to process.")
            return

        self.all_ip_mappings = {}  # 新处理前清空
        self.process_thread = ProcessThread(self.base_dir)
        self.process_thread.progress.connect(self.update_progress)
        self.process_thread.finished.connect(self.processing_finished)
        self.process_thread.error.connect(self.processing_error)
        self.process_thread.ip_mapping_signal.connect(self.display_ip_mapping)

        self.process_thread.start()
        self.process_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.select_dir_btn.setEnabled(False)

    def stop_processing(self):
        """停止处理"""
        if self.process_thread and self.process_thread.isRunning():
            self.process_thread.stop()
            self.process_thread.wait()
            self.log_text.append("Processing stopped.")
            self.process_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.select_dir_btn.setEnabled(True)

    def update_progress(self, message: str):
        """更新进度"""
        self.log_text.append(message)
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )

    def display_ip_mapping(self, subdir: str, _):
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

        # 清空并重建右侧Tab内容
        if not hasattr(self, 'ip_mapping_text'):
            from PyQt6.QtWidgets import QTextEdit
            self.ip_mapping_text = QTextEdit()
            self.ip_mapping_text.setReadOnly(True)
            self.ip_mapping_text.setFont(QFont("Consolas", 12))
            self.ip_mapping_text.setStyleSheet("background-color: #232323; color: #fff; border: none;")
            self.mapping_vlayout.addWidget(self.ip_mapping_text)
        self.ip_mapping_text.clear()
        text = ""
        # 遍历所有子目录，依次输出
        for subdir_name, log_data in self.all_ip_mappings.items():
            stats = log_data.get("stats", {})
            file_mappings = log_data.get("file_mappings", {})
            total_mapping = log_data.get("total_mapping", {})
            text += f"Subdirectory: {subdir_name}\n"
            text += "=" * 40 + "\n"
            # 1. Basic Stats
            text += "[Basic Stats]\n"
            for k, v in stats.items():
                text += f"{k}: {v}\n"
            text += "\n"
            # 2. File Mappings
            for fname, mapping in file_mappings.items():
                text += f"File: {fname}\n"
                for orig, new in mapping.items():
                    text += f"  {orig:<20} -> {new}\n"
                text += "\n"
            # 3. Total Mapping
            text += "[Total Mapping]\n"
            for orig, new in total_mapping.items():
                text += f"{orig:<20} -> {new}\n"
            text += "\n" + ("-"*40) + "\n\n"
        self.ip_mapping_text.setPlainText(text)
        self.ip_mapping_text.moveCursor(QTextCursor.MoveOperation.End)
        self.mapping_tab.setCurrentIndex(0)

    def processing_finished(self):
        """处理完成"""
        self.log_text.append("Processing completed.")
        self.process_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.select_dir_btn.setEnabled(True)

    def processing_error(self, error_message: str):
        """处理出错"""
        QMessageBox.critical(self, "Error", f"An error occurred during processing: {error_message}")
        self.process_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.select_dir_btn.setEnabled(True)

def main():
    """主函数"""
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec()) 