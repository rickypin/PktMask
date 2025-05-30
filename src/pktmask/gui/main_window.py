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
            self.progress.emit(f"正在处理子目录 {i}/{self.total_subdirs}: {subdir}")

            # 获取需要处理的文件
            files_to_process = []
            for f in os.listdir(subdir_path):
                if f.lower().endswith(('.pcap', '.pcapng')):
                    files_to_process.append(f)

            if not files_to_process:
                self.progress.emit(f"子目录 {subdir} 中没有需要处理的文件，跳过")
                self.skipped_subdirs += 1
                continue

            # 子目录统计信息
            subdir_stats = {
                'total_files': len(files_to_process),
                'processed_files': 0,
                'skipped_files': 0,
                'failed_files': 0,
                'unique_ips': 0
            }

            # 预扫描所有文件，收集所有唯一IP和频率
            error_log = []
            freq_data = prescan_addresses(files_to_process, subdir_path, error_log)
            if error_log:
                self.progress.emit("\n".join(error_log))

            # 生成全局唯一IP映射表
            ip_mapping = {}
            ipv4_first_map, ipv4_second_map, ipv4_third_map = {}, {}, {}
            ipv6_first_map, ipv6_second_map, ipv6_third_map = {}, {}, {}
            ipv6_fourth_map, ipv6_fifth_map, ipv6_sixth_map, ipv6_seventh_map = {}, {}, {}, {}
            unique_ips = freq_data[-1]
            for ip in sorted(unique_ips):
                if '.' in ip:  # IPv4
                    new_ip = generate_new_ipv4_address_hierarchical(
                        ip, *freq_data[:3], ipv4_first_map, ipv4_second_map, ipv4_third_map
                    )
                else:  # IPv6
                    new_ip = generate_new_ipv6_address_hierarchical(
                        ip, *freq_data[3:-1],
                        ipv6_first_map, ipv6_second_map, ipv6_third_map,
                        ipv6_fourth_map, ipv6_fifth_map, ipv6_sixth_map, ipv6_seventh_map
                    )
                ip_mapping[ip] = new_ip

            subdir_stats['unique_ips'] = len(ip_mapping)
            self.total_unique_ips += len(ip_mapping)

            # 处理文件，所有文件都用同一个ip_mapping
            all_file_mapping = {}
            for f in files_to_process:
                if not self.is_running:
                    break

                file_path = os.path.join(subdir_path, f)
                self.progress.emit(f"正在处理文件: {f}")
                ok, file_mapping = process_file(file_path, ip_mapping, error_log)
                if ok:
                    if f.endswith('-Replaced.pcap') or f.endswith('-Replaced.pcapng'):
                        self.progress.emit(f"文件 {f} 跳过")
                        subdir_stats['skipped_files'] += 1
                        self.skipped_files += 1
                    else:
                        self.progress.emit(f"文件 {f} 处理完成")
                        subdir_stats['processed_files'] += 1
                        self.processed_files += 1
                else:
                    self.progress.emit(f"文件 {f} 处理失败")
                    subdir_stats['failed_files'] += 1
                    self.failed_files += 1
                all_file_mapping.update(file_mapping)

            # 显示子目录处理摘要
            self.progress.emit(f"\n子目录 {subdir} 处理摘要：")
            self.progress.emit(f"  总文件数：{subdir_stats['total_files']}")
            self.progress.emit(f"  处理完成：{subdir_stats['processed_files']}")
            self.progress.emit(f"  跳过文件：{subdir_stats['skipped_files']}")
            self.progress.emit(f"  处理失败：{subdir_stats['failed_files']}")
            self.progress.emit(f"  唯一IP数：{subdir_stats['unique_ips']}\n")

            # 写入 replacement.log（全局映射）
            try:
                import json
                log_path = os.path.join(subdir_path, "replacement.log")
                with open(log_path, "w", encoding="utf-8") as f:
                    json.dump(ip_mapping, f, indent=2, ensure_ascii=False)
                self.progress.emit(f"IP 替换映射已写入 {log_path}")
                self.ip_mapping_signal.emit(subdir, ip_mapping)
            except Exception as e:
                self.progress.emit(f"写入 replacement.log 出错：{str(e)}")

            if error_log:
                self.progress.emit("\n".join(error_log))

            self.processed_subdirs += 1

        # 显示总体处理摘要
        self.progress.emit("\n处理完成，总体统计：")
        self.progress.emit(f"总子目录数：{self.total_subdirs}")
        self.progress.emit(f"处理子目录：{self.processed_subdirs}")
        self.progress.emit(f"跳过子目录：{self.skipped_subdirs}")
        self.progress.emit(f"总文件数：{self.processed_files + self.skipped_files + self.failed_files}")
        self.progress.emit(f"处理完成：{self.processed_files}")
        self.progress.emit(f"跳过文件：{self.skipped_files}")
        self.progress.emit(f"处理失败：{self.failed_files}")
        self.progress.emit(f"总唯一IP数：{self.total_unique_ips}\n")

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

        button_title = QLabel("操作控制：")
        button_title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        op_layout.addWidget(button_title)

        self.select_dir_btn = QPushButton("选择目录")
        self.select_dir_btn.setMinimumHeight(40)
        self.select_dir_btn.clicked.connect(self.select_directory)
        op_layout.addWidget(self.select_dir_btn)

        self.process_btn = QPushButton("开始处理")
        self.process_btn.setMinimumHeight(40)
        self.process_btn.clicked.connect(self.start_processing)
        self.process_btn.setEnabled(False)
        op_layout.addWidget(self.process_btn)

        self.stop_btn = QPushButton("停止处理")
        self.stop_btn.setMinimumHeight(40)
        self.stop_btn.clicked.connect(self.stop_processing)
        self.stop_btn.setEnabled(False)
        op_layout.addWidget(self.stop_btn)

        op_layout.addStretch()
        left_layout.addWidget(op_widget, 0)

        # 日志区
        log_label = QLabel("处理日志：")
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
        self.mapping_tab.addTab(self.mapping_scroll, "IP 映射关系")

        # 说明Tab
        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setMinimumHeight(150)
        def resource_path(relative_path):
            if hasattr(sys, '_MEIPASS'):
                base_path = sys._MEIPASS
            else:
                base_path = os.path.abspath(".")
            return os.path.join(base_path, relative_path)
        try:
            summary_path = resource_path('resources/summary.md')
            with open(summary_path, "r", encoding="utf-8") as f:
                summary_content = f.read()
            summary_html = markdown.markdown(summary_content)
            self.summary_text.setHtml(summary_html)
        except Exception as e:
            self.summary_text.setText(f"无法加载说明文档：{str(e)}")
        self.mapping_tab.addTab(self.summary_text, "IP 地址替换说明")
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
        try:
            # 改为文本输出
            if not hasattr(self, 'ip_mapping_text'):  # 只创建一次
                from PyQt6.QtWidgets import QTextEdit
                self.ip_mapping_text = QTextEdit()
                self.ip_mapping_text.setReadOnly(True)
                self.ip_mapping_text.setFont(QFont("Consolas", 12))
                self.ip_mapping_text.setStyleSheet("background-color: #232323; color: #fff; border: none;")
                self.mapping_vlayout.addWidget(self.ip_mapping_text)
            # 组装文本内容
            text = self.ip_mapping_text.toPlainText()
            if text:
                text += "\n\n"
            text += f"子目录：{subdir}\n"
            text += "-" * 40 + "\n"
            for orig, new in sorted(ip_mapping.items(), key=lambda kv: kv[0]):
                text += f"{orig:<20} -> {new}\n"
            self.ip_mapping_text.setPlainText(text)
            self.ip_mapping_text.moveCursor(QTextCursor.MoveOperation.End)
            self.mapping_tab.setCurrentIndex(0)
        except Exception as e:
            import traceback
            err_msg = f"[IP映射关系显示异常] {e}\n{traceback.format_exc()}"
            if hasattr(self, 'log_text'):
                self.log_text.append(err_msg)
            else:
                print(err_msg)

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