#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PktMask GUI架构改进 - PyQt6 View实现示例
展示如何实现GUI框架特定的View层
"""

import os
from typing import Dict, Any, Optional
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QCheckBox, QTextEdit, QProgressBar,
    QGroupBox, QFileDialog, QMessageBox, QApplication
)
from PyQt6.QtCore import QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QFont

# 导入接口定义
# from .gui_architecture_interfaces import IMainView, AppState, ProcessingProgress, ProcessingResult


# ============================================================================
# 1. PyQt6 View实现
# ============================================================================

class PyQt6MainView(QMainWindow):  # 实际应该继承 IMainView
    """PyQt6主View实现 - 展示如何实现接口"""
    
    def __init__(self):
        super().__init__()
        self._presenter = None
        self._setup_ui()
        self._connect_signals()
    
    def set_presenter(self, presenter):
        """设置Presenter"""
        self._presenter = presenter
    
    # ========================================================================
    # IView 接口实现
    # ========================================================================
    
    def show_main_window(self) -> None:
        """显示主窗口"""
        self.show()
        self.raise_()
        self.activateWindow()
    
    def close_application(self) -> None:
        """关闭应用程序"""
        self.close()
        QApplication.quit()
    
    def update_app_state(self, state) -> None:  # state: AppState
        """更新应用程序状态显示"""
        # 更新输入目录显示
        if state.input_directory:
            self.input_dir_label.setText(os.path.basename(state.input_directory))
        else:
            self.input_dir_label.setText("Click to select input directory")
        
        # 更新输出目录显示
        if state.output_directory:
            self.output_dir_label.setText(os.path.basename(state.output_directory))
        else:
            self.output_dir_label.setText("Click to select output directory")
        
        # 更新处理选项
        if state.processing_options:
            self.remove_dupes_cb.setChecked(state.processing_options.get("remove_dupes", False))
            self.anonymize_ips_cb.setChecked(state.processing_options.get("anonymize_ips", False))
            self.mask_payloads_cb.setChecked(state.processing_options.get("mask_payloads", False))
        
        # 更新处理状态
        self.update_processing_button_state(state.is_processing)
    
    def update_progress(self, progress) -> None:  # progress: ProcessingProgress
        """更新处理进度显示"""
        # 更新进度条
        self.progress_bar.setValue(int(progress.percentage))
        
        # 更新当前文件显示
        if progress.current_file:
            self.current_file_label.setText(f"Processing: {os.path.basename(progress.current_file)}")
        
        # 更新统计信息
        stats_text = f"Processed: {progress.processed_files}/{progress.total_files}"
        if progress.failed_files > 0:
            stats_text += f" (Failed: {progress.failed_files})"
        self.stats_label.setText(stats_text)
        
        # 更新日志
        log_message = f"[{progress.stage_name}] {os.path.basename(progress.current_file)}"
        self.update_log_display(log_message)
    
    def show_processing_result(self, result) -> None:  # result: ProcessingResult
        """显示处理结果"""
        if result.success:
            title = "Processing Completed"
            message = f"Successfully processed {result.processed_files} files"
            if result.failed_files > 0:
                message += f"\n{result.failed_files} files failed"
            self.show_info(title, message)
        else:
            title = "Processing Failed"
            message = f"Processing failed with {len(result.errors)} errors"
            self.show_error(title, message)
        
        # 重置进度显示
        self.progress_bar.setValue(0)
        self.current_file_label.setText("Ready")
    
    def show_error(self, title: str, message: str) -> None:
        """显示错误信息"""
        QMessageBox.critical(self, title, message)
        self.update_log_display(f"ERROR: {message}")
    
    def show_warning(self, title: str, message: str) -> None:
        """显示警告信息"""
        QMessageBox.warning(self, title, message)
        self.update_log_display(f"WARNING: {message}")
    
    def show_info(self, title: str, message: str) -> None:
        """显示信息提示"""
        QMessageBox.information(self, title, message)
        self.update_log_display(f"INFO: {message}")
    
    def prompt_directory_selection(self, title: str, initial_dir: str = "") -> Optional[str]:
        """提示用户选择目录"""
        directory = QFileDialog.getExistingDirectory(
            self, title, initial_dir
        )
        return directory if directory else None
    
    def confirm_action(self, title: str, message: str) -> bool:
        """确认用户操作"""
        reply = QMessageBox.question(
            self, title, message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        return reply == QMessageBox.StandardButton.Yes
    
    # ========================================================================
    # IFileView 接口实现
    # ========================================================================
    
    def update_input_directory_display(self, directory: str) -> None:
        """更新输入目录显示"""
        self.input_dir_label.setText(os.path.basename(directory))
        self.input_dir_label.setToolTip(directory)
    
    def update_output_directory_display(self, directory: str) -> None:
        """更新输出目录显示"""
        self.output_dir_label.setText(os.path.basename(directory))
        self.output_dir_label.setToolTip(directory)
    
    def update_file_count_display(self, count: int) -> None:
        """更新文件数量显示"""
        self.file_count_label.setText(f"Files found: {count}")
    
    # ========================================================================
    # IPipelineView 接口实现
    # ========================================================================
    
    def update_processing_button_state(self, is_processing: bool) -> None:
        """更新处理按钮状态"""
        if is_processing:
            self.start_button.setText("Stop Processing")
            self.start_button.setStyleSheet("background-color: #ff6b6b;")
        else:
            self.start_button.setText("Start Processing")
            self.start_button.setStyleSheet("background-color: #51cf66;")
    
    def update_options_display(self, options: Dict[str, bool]) -> None:
        """更新选项显示"""
        self.remove_dupes_cb.setChecked(options.get("remove_dupes", False))
        self.anonymize_ips_cb.setChecked(options.get("anonymize_ips", False))
        self.mask_payloads_cb.setChecked(options.get("mask_payloads", False))
    
    def enable_controls(self, enabled: bool) -> None:
        """启用/禁用控件"""
        self.input_dir_button.setEnabled(enabled)
        self.output_dir_button.setEnabled(enabled)
        self.remove_dupes_cb.setEnabled(enabled)
        self.anonymize_ips_cb.setEnabled(enabled)
        self.mask_payloads_cb.setEnabled(enabled)
    
    # ========================================================================
    # IReportView 接口实现
    # ========================================================================
    
    def update_log_display(self, message: str) -> None:
        """更新日志显示"""
        self.log_text.append(message)
        # 自动滚动到底部
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def update_statistics_display(self, stats: Dict[str, Any]) -> None:
        """更新统计信息显示"""
        stats_text = []
        for key, value in stats.items():
            stats_text.append(f"{key}: {value}")
        self.stats_text.setText("\n".join(stats_text))
    
    def show_detailed_report(self, report_data: Dict[str, Any]) -> None:
        """显示详细报告"""
        # 这里可以打开一个新的对话框显示详细报告
        report_text = str(report_data)  # 简化实现
        QMessageBox.information(self, "Detailed Report", report_text)
    
    # ========================================================================
    # UI设置方法
    # ========================================================================
    
    def _setup_ui(self) -> None:
        """设置UI界面"""
        self.setWindowTitle("PktMask - Packet Processing Tool")
        self.setMinimumSize(800, 600)
        
        # 创建中央widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建主布局
        main_layout = QVBoxLayout(central_widget)
        
        # 创建各个组件
        self._create_directory_section(main_layout)
        self._create_options_section(main_layout)
        self._create_progress_section(main_layout)
        self._create_log_section(main_layout)
        self._create_control_section(main_layout)
    
    def _create_directory_section(self, parent_layout) -> None:
        """创建目录选择区域"""
        group = QGroupBox("Directories")
        layout = QGridLayout(group)
        
        # 输入目录
        layout.addWidget(QLabel("Input:"), 0, 0)
        self.input_dir_button = QPushButton("Select Input Directory")
        self.input_dir_label = QLabel("No directory selected")
        layout.addWidget(self.input_dir_button, 0, 1)
        layout.addWidget(self.input_dir_label, 0, 2)
        
        # 输出目录
        layout.addWidget(QLabel("Output:"), 1, 0)
        self.output_dir_button = QPushButton("Select Output Directory")
        self.output_dir_label = QLabel("No directory selected")
        layout.addWidget(self.output_dir_button, 1, 1)
        layout.addWidget(self.output_dir_label, 1, 2)
        
        # 文件数量
        self.file_count_label = QLabel("Files found: 0")
        layout.addWidget(self.file_count_label, 2, 0, 1, 3)
        
        parent_layout.addWidget(group)
    
    def _create_options_section(self, parent_layout) -> None:
        """创建选项区域"""
        group = QGroupBox("Processing Options")
        layout = QHBoxLayout(group)
        
        self.remove_dupes_cb = QCheckBox("Remove Duplicates")
        self.anonymize_ips_cb = QCheckBox("Anonymize IPs")
        self.mask_payloads_cb = QCheckBox("Mask Payloads")
        
        layout.addWidget(self.remove_dupes_cb)
        layout.addWidget(self.anonymize_ips_cb)
        layout.addWidget(self.mask_payloads_cb)
        
        parent_layout.addWidget(group)
    
    def _create_progress_section(self, parent_layout) -> None:
        """创建进度区域"""
        group = QGroupBox("Progress")
        layout = QVBoxLayout(group)
        
        self.progress_bar = QProgressBar()
        self.current_file_label = QLabel("Ready")
        self.stats_label = QLabel("Processed: 0/0")
        
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.current_file_label)
        layout.addWidget(self.stats_label)
        
        parent_layout.addWidget(group)
    
    def _create_log_section(self, parent_layout) -> None:
        """创建日志区域"""
        group = QGroupBox("Log")
        layout = QVBoxLayout(group)
        
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(150)
        self.log_text.setFont(QFont("Consolas", 9))
        
        layout.addWidget(self.log_text)
        parent_layout.addWidget(group)
    
    def _create_control_section(self, parent_layout) -> None:
        """创建控制区域"""
        layout = QHBoxLayout()
        
        self.start_button = QPushButton("Start Processing")
        self.start_button.setMinimumHeight(40)
        self.start_button.setStyleSheet("background-color: #51cf66; font-weight: bold;")
        
        clear_log_button = QPushButton("Clear Log")
        
        layout.addStretch()
        layout.addWidget(clear_log_button)
        layout.addWidget(self.start_button)
        
        parent_layout.addLayout(layout)
    
    def _connect_signals(self) -> None:
        """连接信号"""
        # 目录选择
        self.input_dir_button.clicked.connect(self._on_input_dir_clicked)
        self.output_dir_button.clicked.connect(self._on_output_dir_clicked)
        
        # 处理选项
        self.remove_dupes_cb.toggled.connect(self._on_options_changed)
        self.anonymize_ips_cb.toggled.connect(self._on_options_changed)
        self.mask_payloads_cb.toggled.connect(self._on_options_changed)
        
        # 控制按钮
        self.start_button.clicked.connect(self._on_start_clicked)
    
    # ========================================================================
    # 信号处理方法
    # ========================================================================
    
    def _on_input_dir_clicked(self) -> None:
        """输入目录按钮点击"""
        if self._presenter:
            self._presenter.select_input_directory()
    
    def _on_output_dir_clicked(self) -> None:
        """输出目录按钮点击"""
        if self._presenter:
            self._presenter.select_output_directory()
    
    def _on_options_changed(self) -> None:
        """处理选项变更"""
        if self._presenter:
            options = {
                "remove_dupes": self.remove_dupes_cb.isChecked(),
                "anonymize_ips": self.anonymize_ips_cb.isChecked(),
                "mask_payloads": self.mask_payloads_cb.isChecked()
            }
            self._presenter.update_processing_options(options)
    
    def _on_start_clicked(self) -> None:
        """开始按钮点击"""
        if self._presenter:
            if self._presenter.is_processing():
                self._presenter.stop_processing()
            else:
                self._presenter.start_processing()


# ============================================================================
# 2. 应用程序入口
# ============================================================================

def create_pyqt6_application():
    """创建PyQt6应用程序"""
    app = QApplication([])
    
    # 创建组件
    view = PyQt6MainView()
    # event_bus = EventBus()
    # presenter = MainPresenter()
    
    # 连接组件
    # presenter.set_view(view)
    # presenter.set_event_bus(event_bus)
    # view.set_presenter(presenter)
    
    # 初始化
    # presenter.initialize()
    
    return app, view


if __name__ == "__main__":
    app, view = create_pyqt6_application()
    view.show()
    app.exec()
