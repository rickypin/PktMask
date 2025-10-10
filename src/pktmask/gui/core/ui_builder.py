#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
UI Builder - Focused on interface construction and management

Merges original UIManager and DialogManager functionality,
providing simplified interface construction and dialog management interface.
"""

from typing import List

from PyQt6.QtCore import QEvent
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from pktmask.config import get_app_config
from pktmask.infrastructure.logging import get_logger

from ..constants import UIConstants
from ..styles.stylesheet import generate_stylesheet


class UIBuilder:
    """UI Builder - Focused on interface construction and management

    Responsibilities:
    1. Interface construction (layout, widget creation)
    2. Style management (themes, stylesheets)
    3. Dialog management (various popups)
    4. Menu management (menu bar, context menus)
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
            self._check_and_display_dependencies()
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
            UIConstants.LAYOUT_MARGINS,
            UIConstants.LAYOUT_MARGINS,
            UIConstants.LAYOUT_MARGINS,
            UIConstants.LAYOUT_MARGINS,
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
        """Create options group"""
        self.main_window.options_group = QGroupBox("Processing Options")
        layout = QVBoxLayout(self.main_window.options_group)

        # Processing options (using standard GUI naming)
        self.main_window.anonymize_ips_cb = QCheckBox("Anonymize IPs")
        self.main_window.anonymize_ips_cb.setChecked(True)

        self.main_window.remove_dupes_cb = QCheckBox("Remove Dupes")
        self.main_window.remove_dupes_cb.setChecked(True)

        self.main_window.mask_payloads_cb = QCheckBox(
            "Mask Payloads ( Keep TLS Handshakes and HTTP Headers for troubleshooting )"
        )
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
        """Apply initial styles"""
        theme = self._get_current_theme()
        self.main_window.setStyleSheet(generate_stylesheet(theme))

    def _check_and_display_dependencies(self):
        """Check dependencies and display status in GUI"""
        try:
            from pktmask.infrastructure.dependency import DependencyChecker

            checker = DependencyChecker()

            if not checker.are_dependencies_satisfied():
                # Display status information when dependencies are not satisfied
                status_messages = checker.get_status_messages()
                self._display_dependency_status(status_messages)
            # Don't display any additional information when dependencies are satisfied (keep interface clean)

        except Exception as e:
            self._logger.error(f"Dependency check failed: {e}")
            # If dependency check fails, display generic error information
            self.main_window.log_text.append("⚠️  Unable to verify system dependencies")
            self.main_window.log_text.append("   Some features may not work properly")
            self.main_window.log_text.append("")

    def _display_dependency_status(self, messages: List[str]):
        """Display dependency status in Log module"""
        if hasattr(self.main_window, "log_text"):
            # Add dependency status title
            self.main_window.log_text.append("⚠️  Dependency Status Check:")
            self.main_window.log_text.append("-" * 40)

            # Add specific status information
            for message in messages:
                self.main_window.log_text.append(f"❌ {message}")

            # Add resolution suggestions
            self.main_window.log_text.append("")
            self.main_window.log_text.append("💡 Installation Guide:")
            self.main_window.log_text.append("   • Install Wireshark (includes tshark)")
            self.main_window.log_text.append("   • Ensure tshark is in system PATH")
            self.main_window.log_text.append("   • Minimum version required: 4.2.0")
            self.main_window.log_text.append("   • Download: https://www.wireshark.org/download.html")
            self.main_window.log_text.append("-" * 40)
            self.main_window.log_text.append("")

    def _show_initial_guides(self):
        """Show initial guides"""
        self.main_window.log_text.append("🚀 Welcome to PktMask!")
        self.main_window.log_text.append("")
        self.main_window.log_text.append("┌─ Quick Start Guide ──────────┐")
        self.main_window.log_text.append("│ 1. Select pcap directory     │")
        self.main_window.log_text.append("│ 2. Configure actions         │")
        self.main_window.log_text.append("│ 3. Start processing          │")
        self.main_window.log_text.append("└──────────────────────────────┘")
        self.main_window.log_text.append("")
        self.main_window.log_text.append("💡 Remove Dupes & Anonymize IPs enabled by default")
        self.main_window.log_text.append("")
        self.main_window.log_text.append("Processing logs will appear here...")

        self.main_window.summary_text.append("Processing summary will appear here...")

    # Dialog management methods
    def show_error_dialog(self, title: str, message: str):
        """Show error dialog"""
        QMessageBox.critical(self.main_window, title, message)
        self._logger.error(f"Error dialog: {title} - {message}")

    def show_info_dialog(self, title: str, message: str):
        """Show information dialog"""
        QMessageBox.information(self.main_window, title, message)
        self._logger.info(f"Info dialog: {title} - {message}")

    def show_question_dialog(self, title: str, message: str) -> bool:
        """Show confirmation dialog"""
        reply = QMessageBox.question(
            self.main_window,
            title,
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
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
           - Anonymize IPs: Replace IP addresses with anonymized versions
           - Remove Dupes: Remove duplicate packets
           - Mask Payloads: Mask sensitive payload data

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
        - Anonymize IPs
        - Remove Dupes
        - Mask Payloads
        - Batch Processing

        © 2024 PktMask Team
        """
        QMessageBox.about(self.main_window, "About PktMask", about_text)

    # Style management methods
    def _get_current_theme(self) -> str:
        """Get current theme"""
        bg_color = self.main_window.palette().color(self.main_window.backgroundRole())
        return "dark" if bg_color.lightness() < 128 else "light"

    def apply_theme_change(self, event: QEvent):
        """Handle theme changes"""
        if event.type() == QEvent.Type.ApplicationPaletteChange:
            theme = self._get_current_theme()
            self.main_window.setStyleSheet(generate_stylesheet(theme))

    def update_start_button_state(self):
        """Update start button state"""
        # Check if directory is selected
        has_input = hasattr(self.main_window, "base_dir") and self.main_window.base_dir

        # Check if processing options are selected
        has_options = (
            self.main_window.anonymize_ips_cb.isChecked()
            or self.main_window.remove_dupes_cb.isChecked()
            or self.main_window.mask_payloads_cb.isChecked()
        )

        # Update button state
        self.main_window.start_proc_btn.setEnabled(has_input and has_options)

    # Event handling methods
    def _handle_select_input(self):
        """Handle input directory selection"""
        if hasattr(self.main_window, "data_service"):
            self.main_window.data_service.select_input_directory()

    def _handle_select_output(self):
        """Handle output directory selection"""
        if hasattr(self.main_window, "data_service"):
            self.main_window.data_service.select_output_directory()
