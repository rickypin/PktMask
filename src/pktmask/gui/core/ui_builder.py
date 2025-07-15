#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
UI构建器 - 专注于界面构建和管理

合并原有的 UIManager 和 DialogManager 功能，
提供简化的界面构建和对话框管理接口。
"""

import os
from typing import Optional, Dict, Any
from PyQt6.QtWidgets import (
    QWidget, QGridLayout, QGroupBox, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QCheckBox, QTextEdit, QProgressBar,
    QMenuBar, QMenu, QMessageBox, QProgressDialog, QFileDialog,
    QDialog, QDialogButtonBox
)
from PyQt6.QtCore import Qt, QEvent
from PyQt6.QtGui import QAction, QFont

from pktmask.infrastructure.logging import get_logger
from pktmask.config import get_app_config
from ..styles.stylesheet import generate_stylesheet
from ..constants import UIConstants


class UIBuilder:
    """UI构建器 - 专注于界面构建和管理
    
    职责：
    1. 界面构建（布局、控件创建）
    2. 样式管理（主题、样式表）
    3. 对话框管理（各种弹窗）
    4. 菜单管理（菜单栏、上下文菜单）
    """
    
    def __init__(self, main_window):
        self.main_window = main_window
        self.config = get_app_config()
        self._logger = get_logger(__name__)
        
        self._logger.info("UI builder initialization completed")
    
    def setup_ui(self):
        """构建完整的用户界面"""
        try:
            self._setup_window_properties()
            self._create_menu_bar()
            self._create_main_layout()
            self._apply_initial_styles()
            self._show_initial_guides()
            
            self._logger.info("UI interface construction completed")

        except Exception as e:
            self._logger.error(f"UI interface construction failed: {e}")
            raise
    
    def _setup_window_properties(self):
        """设置窗口属性"""
        self.main_window.setWindowTitle("PktMask - Packet Processing Tool")
        self.main_window.setMinimumSize(UIConstants.MIN_WINDOW_WIDTH, UIConstants.MIN_WINDOW_HEIGHT)
        self.main_window.resize(UIConstants.DEFAULT_WINDOW_WIDTH, UIConstants.DEFAULT_WINDOW_HEIGHT)
    
    def _create_menu_bar(self):
        """创建菜单栏"""
        menubar = self.main_window.menuBar()
        
        # 文件菜单
        file_menu = menubar.addMenu("File")
        
        # 选择输入目录
        select_input_action = QAction("Select Input Directory", self.main_window)
        select_input_action.triggered.connect(self._handle_select_input)
        file_menu.addAction(select_input_action)
        
        # 选择输出目录
        select_output_action = QAction("Select Output Directory", self.main_window)
        select_output_action.triggered.connect(self._handle_select_output)
        file_menu.addAction(select_output_action)
        
        file_menu.addSeparator()
        
        # 退出
        exit_action = QAction("Exit", self.main_window)
        exit_action.triggered.connect(self.main_window.close)
        file_menu.addAction(exit_action)
        
        # 帮助菜单
        help_menu = menubar.addMenu("Help")
        
        # 用户指南
        guide_action = QAction("User Guide", self.main_window)
        guide_action.triggered.connect(self.show_user_guide_dialog)
        help_menu.addAction(guide_action)
        
        # 关于
        about_action = QAction("About", self.main_window)
        about_action.triggered.connect(self.show_about_dialog)
        help_menu.addAction(about_action)
    
    def _create_main_layout(self):
        """创建主布局"""
        main_widget = QWidget()
        self.main_window.setCentralWidget(main_widget)
        
        main_layout = QGridLayout(main_widget)
        main_layout.setSpacing(UIConstants.LAYOUT_SPACING)
        main_layout.setContentsMargins(
            UIConstants.LAYOUT_MARGINS, UIConstants.LAYOUT_MARGINS,
            UIConstants.LAYOUT_MARGINS, UIConstants.LAYOUT_MARGINS
        )
        
        # 创建各个组件
        self._create_directory_group()
        self._create_options_group()
        self._create_progress_group()
        self._create_log_group()
        self._create_summary_group()
        
        # 布局安排
        main_layout.addWidget(self.main_window.dirs_group, 0, 0, 1, 2)
        main_layout.addWidget(self.main_window.options_group, 1, 0)
        main_layout.addWidget(self.main_window.progress_group, 1, 1)
        main_layout.addWidget(self.main_window.log_group, 2, 0)
        main_layout.addWidget(self.main_window.summary_group, 2, 1)
        
        # 设置行列拉伸
        main_layout.setRowStretch(2, 1)  # 日志和摘要区域可拉伸
        main_layout.setColumnStretch(0, 1)
        main_layout.setColumnStretch(1, 1)
    
    def _create_directory_group(self):
        """创建目录选择组"""
        self.main_window.dirs_group = QGroupBox("Directory Selection")
        layout = QHBoxLayout(self.main_window.dirs_group)
        
        # 输入目录
        input_label = QLabel("Input:")
        self.main_window.dir_path_label = QPushButton("Click to select input directory")
        self.main_window.dir_path_label.setStyleSheet("text-align: left; padding: 5px;")
        
        # 输出目录
        output_label = QLabel("Output:")
        self.main_window.output_path_label = QPushButton("Auto-generated based on input")
        self.main_window.output_path_label.setStyleSheet("text-align: left; padding: 5px;")
        
        layout.addWidget(input_label)
        layout.addWidget(self.main_window.dir_path_label, 1)
        layout.addWidget(output_label)
        layout.addWidget(self.main_window.output_path_label, 1)
    
    def _create_options_group(self):
        """创建选项组"""
        self.main_window.options_group = QGroupBox("Processing Options")
        layout = QVBoxLayout(self.main_window.options_group)
        
        # 处理选项（使用标准GUI命名）
        self.main_window.anonymize_ips_cb = QCheckBox("Anonymize IPs")
        self.main_window.anonymize_ips_cb.setChecked(True)

        self.main_window.remove_dupes_cb = QCheckBox("Remove Dupes")
        self.main_window.remove_dupes_cb.setChecked(True)

        self.main_window.mask_payloads_cb = QCheckBox("Mask Payloads ( Keep TLS Handshakes )")
        self.main_window.mask_payloads_cb.setChecked(True)

        layout.addWidget(self.main_window.anonymize_ips_cb)
        layout.addWidget(self.main_window.remove_dupes_cb)
        layout.addWidget(self.main_window.mask_payloads_cb)
        
        # 开始按钮
        self.main_window.start_proc_btn = QPushButton("Start Processing")
        self.main_window.start_proc_btn.setEnabled(False)
        layout.addWidget(self.main_window.start_proc_btn)
    
    def _create_progress_group(self):
        """创建进度组"""
        self.main_window.progress_group = QGroupBox("Progress")
        layout = QVBoxLayout(self.main_window.progress_group)
        
        # 进度条
        self.main_window.progress_bar = QProgressBar()
        self.main_window.progress_bar.setVisible(False)
        
        # 状态标签
        self.main_window.status_label = QLabel("Ready")
        self.main_window.time_label = QLabel("Time: 00:00:00")
        
        layout.addWidget(self.main_window.progress_bar)
        layout.addWidget(self.main_window.status_label)
        layout.addWidget(self.main_window.time_label)
    
    def _create_log_group(self):
        """创建日志组"""
        self.main_window.log_group = QGroupBox("Processing Log")
        layout = QVBoxLayout(self.main_window.log_group)
        
        self.main_window.log_text = QTextEdit()
        self.main_window.log_text.setReadOnly(True)
        self.main_window.log_text.setMaximumHeight(200)
        
        layout.addWidget(self.main_window.log_text)
    
    def _create_summary_group(self):
        """创建摘要组"""
        self.main_window.summary_group = QGroupBox("Processing Summary")
        layout = QVBoxLayout(self.main_window.summary_group)
        
        self.main_window.summary_text = QTextEdit()
        self.main_window.summary_text.setReadOnly(True)
        self.main_window.summary_text.setMaximumHeight(200)
        
        layout.addWidget(self.main_window.summary_text)
    
    def _apply_initial_styles(self):
        """应用初始样式"""
        theme = self._get_current_theme()
        self.main_window.setStyleSheet(generate_stylesheet(theme))
    
    def _show_initial_guides(self):
        """显示初始指引"""
        self.main_window.log_text.append("Welcome to PktMask!")
        self.main_window.log_text.append("1. Select an input directory containing pcap/pcapng files")
        self.main_window.log_text.append("2. Choose processing options")
        self.main_window.log_text.append("3. Click 'Start Processing' to begin")
        
        self.main_window.summary_text.append("Processing summary will appear here...")
    
    # 对话框管理方法
    def show_error_dialog(self, title: str, message: str):
        """显示错误对话框"""
        QMessageBox.critical(self.main_window, title, message)
        self._logger.error(f"Error dialog: {title} - {message}")
    
    def show_info_dialog(self, title: str, message: str):
        """显示信息对话框"""
        QMessageBox.information(self.main_window, title, message)
        self._logger.info(f"Info dialog: {title} - {message}")
    
    def show_question_dialog(self, title: str, message: str) -> bool:
        """显示确认对话框"""
        reply = QMessageBox.question(
            self.main_window, title, message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        return reply == QMessageBox.StandardButton.Yes
    
    def show_user_guide_dialog(self):
        """Show user guide dialog"""
        guide_text = """
        PktMask User Guide
        ==================
        
        1. Directory Selection:
           - Click on input directory button to select folder containing pcap files
           - Output directory will be auto-generated or you can customize it
        
        2. Processing Options:
           - IP Anonymization: Replace IP addresses with anonymized versions
           - Packet Deduplication: Remove duplicate packets
           - Payload Masking: Mask sensitive payload data
        
        3. Processing:
           - Click 'Start Processing' to begin
           - Monitor progress in the log and summary areas
           - Results will be saved to the output directory
        """
        
        dialog = QDialog(self.main_window)
        dialog.setWindowTitle("User Guide")
        dialog.setFixedSize(500, 400)
        
        layout = QVBoxLayout(dialog)
        text_widget = QTextEdit()
        text_widget.setReadOnly(True)
        text_widget.setPlainText(guide_text)
        layout.addWidget(text_widget)
        
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(dialog.accept)
        layout.addWidget(button_box)
        
        dialog.exec()
    
    def show_about_dialog(self):
        """Show about dialog"""
        about_text = """
        PktMask v1.0
        
        A desktop application for batch processing pcap/pcapng files.
        
        Features:
        - IP Address Anonymization
        - Packet Deduplication  
        - Payload Masking
        - Batch Processing
        
        © 2024 PktMask Team
        """
        QMessageBox.about(self.main_window, "About PktMask", about_text)
    
    # 样式管理方法
    def _get_current_theme(self) -> str:
        """获取当前主题"""
        bg_color = self.main_window.palette().color(self.main_window.backgroundRole())
        return 'dark' if bg_color.lightness() < 128 else 'light'
    
    def apply_theme_change(self, event: QEvent):
        """处理主题变化"""
        if event.type() == QEvent.Type.ApplicationPaletteChange:
            theme = self._get_current_theme()
            self.main_window.setStyleSheet(generate_stylesheet(theme))
    
    def update_start_button_state(self):
        """更新开始按钮状态"""
        # 检查是否选择了目录
        has_input = hasattr(self.main_window, 'base_dir') and self.main_window.base_dir
        
        # 检查是否选择了处理选项
        has_options = (
            self.main_window.anonymize_ips_cb.isChecked() or
            self.main_window.remove_dupes_cb.isChecked() or
            self.main_window.mask_payloads_cb.isChecked()
        )
        
        # 更新按钮状态
        self.main_window.start_proc_btn.setEnabled(has_input and has_options)
    
    # 事件处理方法
    def _handle_select_input(self):
        """处理选择输入目录"""
        if hasattr(self.main_window, 'data_service'):
            self.main_window.data_service.select_input_directory()
    
    def _handle_select_output(self):
        """处理选择输出目录"""
        if hasattr(self.main_window, 'data_service'):
            self.main_window.data_service.select_output_directory()
