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
    QMessageBox, QScrollArea, QSplitter, QTableWidget, QTableWidgetItem
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QIcon

from ..core.ip_processor import (
    prescan_addresses, generate_new_ipv4_address_hierarchical,
    generate_new_ipv6_address_hierarchical, process_file
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
        total_subdirs = len(subdirs)

        for i, subdir in enumerate(subdirs, 1):
            if not self.is_running:
                break

            subdir_path = os.path.join(base_dir, subdir)
            self.progress.emit(f"正在处理子目录 {i}/{total_subdirs}: {subdir}")

            # 获取需要处理的文件
            files_to_process = []
            for f in os.listdir(subdir_path):
                if f.lower().endswith(('.pcap', '.pcapng')):
                    files_to_process.append(f)

            if not files_to_process:
                self.progress.emit(f"子目录 {subdir} 中没有需要处理的文件，跳过")
                continue

            # 预扫描
            error_log = []
            freq_data = prescan_addresses(files_to_process, subdir_path, error_log)
            if error_log:
                self.progress.emit("\n".join(error_log))

            # 生成 IP 映射
            ip_mapping = {}
            for ip in freq_data[-1]:  # unique_ips
                if '.' in ip:  # IPv4
                    new_ip = generate_new_ipv4_address_hierarchical(
                        ip, *freq_data[:3], {}, {}, {}
                    )
                else:  # IPv6
                    new_ip = generate_new_ipv6_address_hierarchical(
                        ip, *freq_data[3:-1], {}, {}, {}, {}, {}, {}, {}
                    )
                ip_mapping[ip] = new_ip

            # 处理文件
            all_file_mapping = {}
            for f in files_to_process:
                if not self.is_running:
                    break

                file_path = os.path.join(subdir_path, f)
                self.progress.emit(f"正在处理文件: {f}")
                ok, file_mapping = process_file(file_path, ip_mapping, error_log)
                if ok:
                    self.progress.emit(f"文件 {f} 处理完成")
                else:
                    self.progress.emit(f"文件 {f} 处理失败")
                all_file_mapping.update(file_mapping)

            # 写入 replacement.log
            try:
                import json
                log_path = os.path.join(subdir_path, "replacement.log")
                with open(log_path, "w", encoding="utf-8") as f:
                    json.dump(all_file_mapping, f, indent=2, ensure_ascii=False)
                self.progress.emit(f"IP 替换映射已写入 {log_path}")
                self.ip_mapping_signal.emit(subdir, all_file_mapping)
            except Exception as e:
                self.progress.emit(f"写入 replacement.log 出错：{str(e)}")

            if error_log:
                self.progress.emit("\n".join(error_log))

    def stop(self):
        """停止处理"""
        self.is_running = False

class MainWindow(QMainWindow):
    """主窗口"""
    def __init__(self):
        super().__init__()
        self.process_thread: Optional[ProcessThread] = None
        self.ip_mapping_tables = {}  # 子目录名 -> QTableWidget
        self.init_ui()

    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle("PktMask - IP 地址替换工具")
        self.setMinimumSize(1000, 700)

        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 创建主布局
        main_layout = QVBoxLayout(central_widget)

        # 创建说明文本区域
        summary_label = QLabel("IP 地址替换说明：")
        summary_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        main_layout.addWidget(summary_label)

        summary_text = QTextEdit()
        summary_text.setReadOnly(True)
        summary_text.setMaximumHeight(120)
        main_layout.addWidget(summary_text)

        # 加载说明文档，兼容 PyInstaller
        def resource_path(relative_path):
            if hasattr(sys, '_MEIPASS'):
                return os.path.join(sys._MEIPASS, relative_path)
            return os.path.join(os.path.dirname(__file__), '..', 'resources', relative_path)

        try:
            summary_path = resource_path('pktmask/resources/summary.md')
            with open(summary_path, "r", encoding="utf-8") as f:
                summary_content = f.read()
            summary_html = markdown.markdown(summary_content)
            summary_text.setHtml(summary_html)
        except Exception as e:
            summary_text.setText(f"无法加载说明文档：{str(e)}")

        # 创建按钮区域
        button_layout = QHBoxLayout()
        self.select_dir_btn = QPushButton("选择目录")
        self.select_dir_btn.clicked.connect(self.select_directory)
        button_layout.addWidget(self.select_dir_btn)

        self.process_btn = QPushButton("开始处理")
        self.process_btn.clicked.connect(self.start_processing)
        self.process_btn.setEnabled(False)
        button_layout.addWidget(self.process_btn)

        self.stop_btn = QPushButton("停止处理")
        self.stop_btn.clicked.connect(self.stop_processing)
        self.stop_btn.setEnabled(False)
        button_layout.addWidget(self.stop_btn)

        main_layout.addLayout(button_layout)

        # 分割区（日志区和IP映射区）
        splitter = QSplitter(Qt.Orientation.Vertical)
        # 日志区
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        log_label = QLabel("处理日志：")
        log_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        log_layout.addWidget(log_label)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        splitter.addWidget(log_widget)
        # IP映射区
        ip_map_widget = QWidget()
        ip_map_layout = QVBoxLayout(ip_map_widget)
        ip_map_label = QLabel("IP 替换映射（每个子目录）：")
        ip_map_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        ip_map_layout.addWidget(ip_map_label)
        self.ip_map_area = QScrollArea()
        self.ip_map_area.setWidgetResizable(True)
        self.ip_map_content = QWidget()
        self.ip_map_content_layout = QVBoxLayout(self.ip_map_content)
        self.ip_map_area.setWidget(self.ip_map_content)
        ip_map_layout.addWidget(self.ip_map_area)
        ip_map_widget.setLayout(ip_map_layout)
        splitter.addWidget(ip_map_widget)
        splitter.setSizes([300, 400])
        main_layout.addWidget(splitter)

    def select_directory(self):
        """选择目录"""
        dir_path = QFileDialog.getExistingDirectory(self, "选择要处理的目录")
        if dir_path:
            self.base_dir = dir_path
            self.process_btn.setEnabled(True)
            self.log_text.append(f"已选择目录：{dir_path}")

    def start_processing(self):
        """开始处理"""
        if not hasattr(self, 'base_dir'):
            QMessageBox.warning(self, "警告", "请先选择要处理的目录")
            return

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
            self.log_text.append("处理已停止")
            self.process_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.select_dir_btn.setEnabled(True)

    def update_progress(self, message: str):
        """更新进度"""
        self.log_text.append(message)
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )

    def display_ip_mapping(self, subdir: str, ip_mapping: dict):
        # 创建表格展示
        table = QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["原始 IP", "替换后 IP"])
        table.setRowCount(len(ip_mapping))
        for row, (orig, new) in enumerate(sorted(ip_mapping.items(), key=lambda kv: kv[0])):
            table.setItem(row, 0, QTableWidgetItem(orig))
            table.setItem(row, 1, QTableWidgetItem(new))
        table.resizeColumnsToContents()
        table.setMinimumHeight(120)
        label = QLabel(f"子目录：{subdir}")
        label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        self.ip_map_content_layout.addWidget(label)
        self.ip_map_content_layout.addWidget(table)
        self.ip_mapping_tables[subdir] = table

    def processing_finished(self):
        """处理完成"""
        self.log_text.append("处理完成")
        self.process_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.select_dir_btn.setEnabled(True)

    def processing_error(self, error_message: str):
        """处理出错"""
        QMessageBox.critical(self, "错误", f"处理过程中出现错误：{error_message}")
        self.process_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.select_dir_btn.setEnabled(True)

def main():
    """主函数"""
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec()) 