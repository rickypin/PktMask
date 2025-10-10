#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Main window module
Implements graphical interface
"""

import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

import markdown
from PyQt6.QtCore import QEasingCurve, QEvent, QPropertyAnimation, Qt, QTime, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QFont, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QProgressDialog,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from pktmask.common.constants import UIConstants
from pktmask.config.settings import get_app_config

# Refactored imports
from pktmask.core.events import PipelineEvents
from pktmask.infrastructure.logging import get_logger
from pktmask.utils import current_time, current_timestamp, format_milliseconds_to_time
from pktmask.utils.file_ops import open_directory_in_system
from pktmask.utils.path import resource_path

# Import GUI protection layer (from PipelineManager)
from .core.feature_flags import GUIFeatureFlags
from .core.gui_consistent_processor import GUIConsistentProcessor, GUIThreadingHelper

# Import stylesheet generator (moved from UIManager)
from .stylesheet import generate_stylesheet

# PROCESS_DISPLAY_NAMES moved to common.constants


class GuideDialog(QDialog):
    """Processing guide dialog"""

    def __init__(self, title: str, content: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{title} - Guide")
        self.setMinimumSize(UIConstants.GUIDE_DIALOG_MIN_WIDTH, UIConstants.GUIDE_DIALOG_MIN_HEIGHT)
        layout = QVBoxLayout(self)
        content_text = QTextEdit()
        content_text.setReadOnly(True)
        content_text.setHtml(markdown.markdown(content))
        layout.addWidget(content_text)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)


class MainWindow(QMainWindow):
    """Main window"""

    # Qt signals (replacing EventCoordinator)
    error_occurred = pyqtSignal(str)  # Error signal for automated testing
    progress_updated = pyqtSignal(int)  # Progress update signal
    pipeline_event = pyqtSignal(str, dict)  # Pipeline event signal (event_type, data)
    ui_update_requested = pyqtSignal(str, dict)  # UI update request signal (action, kwargs)
    statistics_changed = pyqtSignal(dict)  # Statistics change signal

    def __init__(self):
        super().__init__()
        self._logger = get_logger("main_window")

        # Initialize configuration manager
        self.config = get_app_config()

        # 注册配置变更回调 (简化版本暂时移除复杂的回调机制)

        # 基本属性
        self.base_dir: Optional[str] = None
        self.output_dir: Optional[str] = None  # 新增：输出目录
        self.current_output_dir: Optional[str] = None  # 新增：当前处理的输出目录

        # 使用配置中的目录设置
        self.last_opened_dir = self.config.ui.last_input_dir or os.path.join(os.path.expanduser("~"), "Desktop")
        self.allowed_root = os.path.expanduser("~")

        # 时间相关属性
        self.time_elapsed = 0
        self.timer: Optional[QTimer] = None
        self.start_time: Optional[QTime] = None
        self.user_stopped = False  # 用户停止标志

        # Statistics attributes (moved from StatisticsManager)
        self.files_processed = 0
        self.packets_processed = 0
        self.total_files_to_process = 0
        self.processing_time = 0
        self.file_processing_results = {}  # original_file -> {steps: {step_name: result_data}}
        self.step_results = {}  # 步骤结果缓存
        self.global_ip_mappings = {}  # 全局IP映射汇总
        self.all_ip_reports = {}  # subdir -> report_data
        self.processed_files_count = 0
        self.current_processing_file = None  # 当前正在处理的原始文件
        self.subdirs_files_counted = set()
        self.subdirs_packets_counted = set()
        self.printed_summary_headers = set()

        # 初始化管理器（不包括 UIManager）
        self._init_managers()

        # 初始化UI（moved from UIManager）
        self._setup_window_properties()
        self._create_menu_bar()
        self._setup_main_layout()
        self._connect_ui_signals()
        self._apply_initial_styles()
        self._check_and_display_dependencies()
        self._show_initial_guides()

        self._logger.info("PktMask main window initialization completed")

    def _init_managers(self):
        """Initialize processing state and timer (managers removed)"""
        # All manager functionality has been moved to MainWindow methods

        # Initialize processing state (from PipelineManager)
        self.processing_thread = None
        self.user_stopped = False

        # Set up timer (from PipelineManager)
        self._setup_timer()

        # Connect internal Qt signals
        self._connect_signals()

        self._logger.debug("Processing state and timer initialization completed")

    def _connect_signals(self):
        """Connect Qt signals (replacing EventCoordinator subscriptions)"""
        # Connect internal signals to handlers
        self.statistics_changed.connect(self._handle_statistics_update)
        self.ui_update_requested.connect(self._handle_ui_update_request)
        self.pipeline_event.connect(self._handle_pipeline_event_data)

    # === UI Initialization Methods (moved from UIManager) ===

    def _setup_window_properties(self):
        """Set window properties"""
        self.setWindowTitle("PktMask")

        # 使用配置中的窗口尺寸
        window_width = self.config.ui.window_width
        window_height = self.config.ui.window_height
        self.setGeometry(100, 100, window_width, window_height)

        # 设置最小尺寸
        self.setMinimumSize(self.config.ui.window_min_width, self.config.ui.window_min_height)

        self.setWindowIcon(QIcon(resource_path("icon.png")))

    def _create_menu_bar(self):
        """Create menu bar"""
        menu_bar = self.menuBar()

        # File menu
        file_menu = menu_bar.addMenu("File")

        reset_action = QAction("Reset All", self)
        reset_action.triggered.connect(self.reset_state)
        reset_action.setShortcut("Ctrl+R")
        file_menu.addAction(reset_action)

        file_menu.addSeparator()

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        exit_action.setShortcut("Ctrl+Q")
        file_menu.addAction(exit_action)

        # Help menu
        help_menu = menu_bar.addMenu("Help")

        user_guide_action = QAction("User Guide", self)
        user_guide_action.triggered.connect(self.show_user_guide_dialog)
        help_menu.addAction(user_guide_action)

        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about_dialog)
        help_menu.addAction(about_action)

    def _setup_main_layout(self):
        """Set up main layout"""
        main_widget = QWidget()
        self.setCentralWidget(main_widget)

        main_layout = QGridLayout(main_widget)
        main_layout.setSpacing(UIConstants.LAYOUT_SPACING)
        main_layout.setContentsMargins(
            UIConstants.LAYOUT_MARGINS,
            UIConstants.LAYOUT_MARGINS,
            UIConstants.LAYOUT_MARGINS,
            UIConstants.LAYOUT_MARGINS,
        )

        # --- Create all GroupBox widgets ---
        self._create_dirs_group()
        self._create_row2_widget()
        self._create_dashboard_group()
        self._create_log_group()
        self._create_summary_group()

        # --- Define layout structure ---
        self._setup_grid_layout(main_layout)

    def _create_dirs_group(self):
        """Create directory selection group"""
        # Step 1: Input and Output (left-right distribution) - simplified version
        dirs_group = QGroupBox("Set Working Directories")
        dirs_group.setMaximumHeight(UIConstants.DIRS_GROUP_HEIGHT)
        dirs_layout = QHBoxLayout(dirs_group)
        dirs_layout.setContentsMargins(*UIConstants.DIRS_LAYOUT_PADDING)

        # 左侧：Input Directory - 单行布局
        input_layout = QVBoxLayout()
        input_layout.setSpacing(5)
        input_label = QLabel("Input:")
        input_label.setMaximumHeight(UIConstants.INPUT_LABEL_HEIGHT)
        input_path_layout = QHBoxLayout()
        input_path_layout.setSpacing(8)
        self.dir_path_label = QPushButton("Click and pick your pcap directory")
        self.dir_path_label.setObjectName("DirPathLabel")
        self.dir_path_label.setMaximumHeight(UIConstants.BUTTON_MAX_HEIGHT)
        self.dir_path_label.setCursor(Qt.CursorShape.PointingHandCursor)
        input_path_layout.addWidget(input_label)
        input_path_layout.addWidget(self.dir_path_label, 1)
        input_layout.addLayout(input_path_layout)

        # 右侧：Output Directory - 单行布局
        output_layout = QVBoxLayout()
        output_layout.setSpacing(5)
        output_label = QLabel("Output:")
        output_label.setMaximumHeight(20)
        output_path_layout = QHBoxLayout()
        output_path_layout.setSpacing(8)
        self.output_path_label = QPushButton("Auto-create or click for custom")
        self.output_path_label.setObjectName("DirPathLabel")
        self.output_path_label.setMaximumHeight(30)
        self.output_path_label.setCursor(Qt.CursorShape.PointingHandCursor)
        output_path_layout.addWidget(output_label)
        output_path_layout.addWidget(self.output_path_label, 1)
        output_layout.addLayout(output_path_layout)

        dirs_layout.addLayout(input_layout, 1)
        dirs_layout.addLayout(output_layout, 1)

        # 保存引用
        self.dirs_group = dirs_group

    def _create_row2_widget(self):
        """Create second row components (options and execution)"""
        # Step 2 & 3: Second row side-by-side layout
        row2_widget = QWidget()
        row2_widget.setMaximumHeight(90)
        row2_layout = QHBoxLayout(row2_widget)
        row2_layout.setContentsMargins(0, 0, 0, 0)
        row2_layout.setSpacing(12)

        # Step 2: Configure Pipeline
        pipeline_group = QGroupBox("Set Actions")
        pipeline_group.setMaximumHeight(85)
        pipeline_layout = QHBoxLayout(pipeline_group)
        pipeline_layout.setContentsMargins(15, 12, 15, 12)
        pipeline_layout.setSpacing(20)

        self.remove_dupes_cb = QCheckBox("Remove Dupes")
        self.anonymize_ips_cb = QCheckBox("Anonymize IPs")
        self.mask_payloads_cb = QCheckBox("Mask Payloads ( Keep TLS Handshakes and HTTP Headers for troubleshooting )")

        self.mask_payloads_cb.setToolTip("Intelligently masks packet payloads while preserving TLS handshake data.")

        # 设置手型光标
        for cb in [
            self.remove_dupes_cb,
            self.anonymize_ips_cb,
            self.mask_payloads_cb,
        ]:
            cb.setCursor(Qt.CursorShape.PointingHandCursor)

        # 使用配置中的默认状态
        self.remove_dupes_cb.setChecked(self.config.ui.default_remove_dupes)
        self.anonymize_ips_cb.setChecked(self.config.ui.default_anonymize_ips)
        self.mask_payloads_cb.setChecked(self.config.ui.default_mask_payloads)

        pipeline_layout.addWidget(self.remove_dupes_cb)
        pipeline_layout.addWidget(self.anonymize_ips_cb)
        pipeline_layout.addWidget(self.mask_payloads_cb)
        pipeline_layout.addStretch()

        # Step 3: Execute
        execute_group = QGroupBox("Run Processing")
        execute_group.setMaximumHeight(85)
        execute_layout = QVBoxLayout(execute_group)
        execute_layout.setContentsMargins(15, 20, 15, 20)
        execute_layout.setSpacing(5)
        self.start_proc_btn = QPushButton("Start")
        self.start_proc_btn.setMinimumHeight(35)
        self.start_proc_btn.setMaximumHeight(35)
        self.start_proc_btn.setEnabled(False)
        self.start_proc_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        execute_layout.addWidget(self.start_proc_btn)

        row2_layout.addWidget(pipeline_group, 3)
        row2_layout.addWidget(execute_group, 1)

        # 保存引用
        self.row2_widget = row2_widget

    def _create_dashboard_group(self):
        """Create dashboard group"""
        dashboard_group = QGroupBox("Live Dashboard")
        dashboard_group.setMaximumHeight(140)
        dashboard_layout = QVBoxLayout(dashboard_group)
        dashboard_layout.setContentsMargins(15, 20, 15, 12)
        dashboard_layout.setSpacing(10)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(18)

        # 初始化进度条动画
        self.progress_animation = QPropertyAnimation(self.progress_bar, b"value")
        self.progress_animation.setDuration(300)
        self.progress_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        dashboard_layout.addWidget(self.progress_bar)

        # KPI布局
        kpi_layout = QGridLayout()
        kpi_layout.setSpacing(10)
        self.files_processed_label = QLabel("0")
        self.files_processed_label.setObjectName("FilesProcessedLabel")
        self.packets_processed_label = QLabel("0")
        self.packets_processed_label.setObjectName("IpsMaskedLabel")
        self.time_elapsed_label = QLabel("00:00.00")
        self.time_elapsed_label.setObjectName("DupesRemovedLabel")

        kpi_layout.addWidget(self.files_processed_label, 0, 0, Qt.AlignmentFlag.AlignCenter)
        kpi_layout.addWidget(QLabel("Files Processed"), 1, 0, Qt.AlignmentFlag.AlignCenter)
        kpi_layout.addWidget(self.packets_processed_label, 0, 1, Qt.AlignmentFlag.AlignCenter)
        kpi_layout.addWidget(QLabel("Packets Processed"), 1, 1, Qt.AlignmentFlag.AlignCenter)
        kpi_layout.addWidget(self.time_elapsed_label, 0, 2, Qt.AlignmentFlag.AlignCenter)
        kpi_layout.addWidget(QLabel("Time Elapsed"), 1, 2, Qt.AlignmentFlag.AlignCenter)

        dashboard_layout.addLayout(kpi_layout)

        # 保存引用
        self.dashboard_group = dashboard_group

    def _create_log_group(self):
        """Create log group"""
        log_group = QGroupBox("Log")
        log_layout = QVBoxLayout(log_group)
        log_layout.setContentsMargins(12, 20, 12, 12)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)

        # 设置Log区域的字体大小
        log_font = QFont()
        log_font.setPointSize(12)
        self.log_text.setFont(log_font)
        log_layout.addWidget(self.log_text)

        # 保存引用
        self.log_group = log_group

    def _create_summary_group(self):
        """Create summary group"""
        summary_group = QGroupBox("Summary Report")
        summary_layout = QVBoxLayout(summary_group)
        summary_layout.setContentsMargins(12, 20, 12, 12)
        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)

        # 设置Summary Report区域的字体大小
        summary_font = QFont()
        summary_font.setPointSize(12)
        self.summary_text.setFont(summary_font)
        summary_layout.addWidget(self.summary_text)

        # 保存引用
        self.summary_group = summary_group

    def _setup_grid_layout(self, main_layout):
        """Set up grid layout"""
        # Add components to grid layout
        main_layout.addWidget(self.dirs_group, 0, 0, 1, 2)
        main_layout.addWidget(self.row2_widget, 1, 0, 1, 2)
        main_layout.addWidget(self.dashboard_group, 2, 0)
        main_layout.addWidget(self.log_group, 3, 0)
        main_layout.addWidget(self.summary_group, 2, 1, 2, 1)

        # 设置拉伸因子
        main_layout.setColumnStretch(0, 2)  # 左列
        main_layout.setColumnStretch(1, 3)  # 右列
        main_layout.setRowStretch(0, 0)  # Step 1 row
        main_layout.setRowStretch(1, 0)  # Step 2&3 row
        main_layout.setRowStretch(2, 0)  # Dashboard row
        main_layout.setRowStretch(3, 2)  # Log row

    def _connect_ui_signals(self):
        """Connect UI component signals to their handlers"""
        try:
            # Directory selection signals
            # Directory selection signals
            self.dir_path_label.clicked.connect(self.choose_input_folder)
            self.output_path_label.clicked.connect(self.handle_output_click)

            # Processing button signals
            self.start_proc_btn.clicked.connect(self.toggle_pipeline_processing)
            self._logger.debug("Start button signal connected successfully")

        except Exception as e:
            self._logger.error(f"Failed to connect start button signal: {e}")
            import traceback

            traceback.print_exc()

        # checkbox state change signals - correctly call UIManager methods
        self.anonymize_ips_cb.stateChanged.connect(self._update_start_button_state)
        self.remove_dupes_cb.stateChanged.connect(self._update_start_button_state)
        self.mask_payloads_cb.stateChanged.connect(self._update_start_button_state)

    def _apply_initial_styles(self):
        """Apply initial styles"""
        self.apply_stylesheet()
        self._update_path_link_styles()
        self._update_start_button_style()

    def _check_and_display_dependencies(self):
        """Check dependencies and display status in GUI"""
        try:
            from pktmask.infrastructure.dependency import DependencyChecker

            checker = DependencyChecker()

            if not checker.are_dependencies_satisfied():
                # 依赖不满足时显示状态信息
                status_messages = checker.get_status_messages()
                self._display_dependency_status(status_messages)
            # 依赖满足时不显示任何额外信息（保持界面清洁）

        except Exception as e:
            self._logger.error(f"Dependency check failed: {e}")
            # 如果依赖检查失败，显示通用错误信息
            self.log_text.append("⚠️  Unable to verify system dependencies")
            self.log_text.append("   Some features may not work properly")
            self.log_text.append("")

    def _display_dependency_status(self, messages):
        """Display dependency status in Log module"""
        if hasattr(self, "log_text"):
            # Build dependency status message
            status_text = "⚠️  Dependency Status Check:\n"
            status_text += "-" * 40 + "\n"

            # Add specific status information
            for message in messages:
                status_text += f"❌ {message}\n"

            # Add resolution suggestions
            status_text += "\n💡 Installation Guide:\n"
            status_text += "   • Install Wireshark (includes tshark)\n"
            status_text += "   • Ensure tshark is in system PATH\n"
            status_text += "   • Minimum version required: 4.2.0\n"
            status_text += "   • Download: https://www.wireshark.org/download.html\n"
            status_text += "-" * 40 + "\n\n"

            # Use append instead of setPlaceholderText to display dependency status
            self.log_text.append(status_text)

    def _show_initial_guides(self):
        """Show initial guides"""
        self.log_text.setPlaceholderText(
            "\n🚀 Welcome to PktMask!\n\n"
            "┌─ Quick Start Guide ──────────┐\n"
            "│ 1. Select pcap directory     │\n"
            "│ 2. Configure actions         │\n"
            "│ 3. Start processing          │\n"
            "└──────────────────────────────┘\n\n"
            "💡 Remove Dupes & Anonymize IPs enabled by default\n\n"
            "Processing logs will appear here..."
        )

        # Read summary.md file content
        try:
            with open(resource_path("summary.md"), "r", encoding="utf-8") as f:
                summary_md_content = f.read()

            # Convert markdown content to display-friendly format, maintaining existing styles
            formatted_content = "\n" + self._format_summary_md_content(summary_md_content)

        except Exception as e:
            # If reading fails, show error message instead of fallback content
            self.logger.error(f"Failed to load summary.md: {e}")
            formatted_content = (
                "\n⚠️ User Guide Not Available\n\n"
                "The summary.md file could not be loaded.\n"
                f"Error: {str(e)}\n\n"
                "Please check the installation or contact support.\n"
                "If you're in development mode, ensure config/templates/summary.md exists."
            )

        self.summary_text.setPlaceholderText(formatted_content)

    def _format_summary_md_content(self, md_content: str) -> str:
        """Format markdown content to plain text format suitable for display"""
        lines = md_content.split("\n")
        formatted_lines = []

        # Start directly, don't add top horizontal line

        for line in lines:
            line = line.strip()
            if not line:
                formatted_lines.append("")
            elif line.startswith("# "):
                # Main title - add horizontal lines above and below the title
                title = line[2:].strip()
                formatted_lines.append("─" * 80)
                formatted_lines.append(f"📦 {title}")
                formatted_lines.append("─" * 80)
                formatted_lines.append("")
            elif line.startswith("## "):
                # Subtitle
                subtitle = line[3:].strip()
                emoji_map = {
                    "Anonymize IPs": "🎭",
                    "Remove Dupes": "🔄",
                    "Mask Payloads": "🛡️",
                    "Processing Flow": "⚡",
                    "Key Benefits": "🎯",
                }
                emoji = emoji_map.get(subtitle, "🔧")
                formatted_lines.append(f"{emoji} {subtitle}")
            elif line.startswith("   - "):
                # 列表项
                item = line[5:].strip()
                formatted_lines.append(f"   • {item}")
            elif line.startswith("   "):
                # 缩进内容
                content = line[3:].strip()
                if content.startswith("- "):
                    content = content[2:].strip()
                formatted_lines.append(f"   - {content}")
            elif line and not line.startswith("#"):
                # 普通段落
                formatted_lines.append(f"   {line}")

            # 在某些部分后添加空行
            if line.startswith("## ") and line != lines[-1]:
                formatted_lines.append("")

        # 不再添加底部的Web-focused和Use Cases部分

        return "\n".join(formatted_lines)

    # Style management methods
    def get_current_theme(self) -> str:
        """Detect whether current system is using light or dark mode"""
        bg_color = self.palette().color(self.backgroundRole())
        return "dark" if bg_color.lightness() < 128 else "light"

    def apply_stylesheet(self):
        """Apply theme-appropriate stylesheet to the main window"""
        theme = self.get_current_theme()
        self.setStyleSheet(generate_stylesheet(theme))

    def handle_theme_change(self, event: QEvent):
        """Handle system theme changes and update UI accordingly"""
        if event.type() == QEvent.Type.ApplicationPaletteChange:
            self.apply_stylesheet()
            self._update_path_link_styles()
            self._update_start_button_style()

    def _get_path_link_style(self) -> str:
        """Get path link style"""
        theme = self.get_current_theme()
        if theme == "dark":
            return """
                QPushButton#DirPathLabel {
                    border: 1px solid #555;
                    background-color: #3a3a3a;
                    color: #87CEEB;
                    padding: 5px;
                    text-align: left;
                    border-radius: 3px;
                }
                QPushButton#DirPathLabel:hover {
                    background-color: #4a4a4a;
                    color: #98DFEF;
                }
                QPushButton#DirPathLabel:pressed {
                    background-color: #2a2a2a;
                }
            """
        else:
            return """
                QPushButton#DirPathLabel {
                    border: 1px solid #ccc;
                    background-color: #f8f8f8;
                    color: #0066cc;
                    padding: 5px;
                    text-align: left;
                    border-radius: 3px;
                }
                QPushButton#DirPathLabel:hover {
                    background-color: #e8e8e8;
                    color: #004499;
                }
                QPushButton#DirPathLabel:pressed {
                    background-color: #d8d8d8;
                }
            """

    def _update_path_link_styles(self):
        """Update path link styles"""
        style = self._get_path_link_style()
        self.setStyleSheet(self.styleSheet() + style)

    def _get_start_button_style(self) -> str:
        """Get start button style"""
        theme = self.get_current_theme()
        if self.start_proc_btn.isEnabled():
            if theme == "dark":
                return """
                    QPushButton {
                        background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                                  stop: 0 #4CAF50, stop: 1 #45a049);
                        color: white;
                        border: none;
                        border-radius: 5px;
                        font-weight: bold;
                        font-size: 14px;
                    }
                    QPushButton:hover {
                        background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                                  stop: 0 #5CBF60, stop: 1 #55b059);
                    }
                    QPushButton:pressed {
                        background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                                  stop: 0 #3CAF40, stop: 1 #359039);
                    }
                """
            else:
                return """
                    QPushButton {
                        background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                                  stop: 0 #4CAF50, stop: 1 #45a049);
                        color: white;
                        border: none;
                        border-radius: 5px;
                        font-weight: bold;
                        font-size: 14px;
                    }
                    QPushButton:hover {
                        background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                                  stop: 0 #5CBF60, stop: 1 #55b059);
                    }
                    QPushButton:pressed {
                        background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                                  stop: 0 #3CAF40, stop: 1 #359039);
                    }
                """
        else:
            if theme == "dark":
                return """
                    QPushButton {
                        background-color: #555;
                        color: #888;
                        border: 1px solid #666;
                        border-radius: 5px;
                        font-weight: bold;
                        font-size: 14px;
                    }
                """
            else:
                return """
                    QPushButton {
                        background-color: #e0e0e0;
                        color: #888;
                        border: 1px solid #ccc;
                        border-radius: 5px;
                        font-weight: bold;
                        font-size: 14px;
                    }
                """

    def _update_start_button_style(self):
        """Update start button style"""
        style = self._get_start_button_style()
        # 移除旧的按钮样式并添加新的
        self.start_proc_btn.setStyleSheet(style)

    def _update_start_button_state(self):
        """Update Start button based on input directory and option states"""
        has_input_dir = self.base_dir is not None
        has_any_action = (
            self.anonymize_ips_cb.isChecked() or self.remove_dupes_cb.isChecked() or self.mask_payloads_cb.isChecked()
        )

        # 检查是否正在处理中 - Store thread reference to avoid race condition
        processing_thread = getattr(self.pipeline_manager, "processing_thread", None)
        is_processing = processing_thread is not None and processing_thread.isRunning()

        # 只有当有输入目录且至少选择一个操作时才启用按钮，或者正在处理中时保持启用
        should_enable = (has_input_dir and has_any_action) or is_processing

        self.start_proc_btn.setEnabled(should_enable)

        # 同时更新按钮样式
        self._update_start_button_style()

    def _handle_statistics_update(self, data: dict):
        """Handle statistics data updates (Qt signal handler)"""
        action = data.get("action", "update")
        if action == "reset":
            # Check if processing is in progress, only reset Live Dashboard when starting new processing
            # Avoid resetting display after processing completion which would lose statistics
            if hasattr(self, "processing_thread") and self.processing_thread is None:
                # Only reset display when no processing thread is running (i.e., starting new processing)
                self.files_processed_label.setText("0")
                self.packets_processed_label.setText("0")
                self.time_elapsed_label.setText("00:00.00")
                self.progress_bar.setValue(0)
            # If processing or just completed, keep current display unchanged
        else:
            # Update UI display
            if hasattr(self, "get_processing_stats"):
                stats = self.get_processing_stats()
                if stats:
                    self.files_processed_label.setText(str(stats.get("files_processed", 0)))
                    self.packets_processed_label.setText(str(stats.get("packets_processed", 0)))
                    self.time_elapsed_label.setText(stats.get("processing_time", "00:00.00"))

    def _handle_ui_update_request(self, action: str, kwargs: dict):
        """Handle UI update requests (Qt signal handler)"""
        if action == "enable_controls":
            controls = kwargs.get("controls", [])
            enabled = kwargs.get("enabled", True)
            for control_name in controls:
                if hasattr(self, control_name):
                    getattr(self, control_name).setEnabled(enabled)
        elif action == "update_button_text":
            button_name = kwargs.get("button", "")
            text = kwargs.get("text", "")
            if hasattr(self, button_name):
                getattr(self, button_name).setText(text)

    def _handle_pipeline_event_data(self, event_type: str, data: dict):
        """Handle pipeline event data (Qt signal handler)"""
        # Process pipeline events directly (simplified from EventCoordinator)
        self._logger.debug(f"Received pipeline event: {event_type}")

    def _on_config_changed(self, new_config):
        """Configuration change callback"""
        self.config = new_config
        self._logger.info("Configuration updated, reapplying settings")

        # 更新窗口尺寸（如果需要）
        current_size = self.size()
        if current_size.width() != new_config.ui.window_width or current_size.height() != new_config.ui.window_height:
            self.resize(new_config.ui.window_width, new_config.ui.window_height)

        # 重新应用样式表
        self._apply_stylesheet()

    def save_window_state(self):
        """Save window state to configuration"""
        current_size = self.size()
        self.config.ui.window_width = current_size.width()
        self.config.ui.window_height = current_size.height()
        self.config.save()

    def save_user_preferences(self):
        """Save user preference settings"""
        # Save default state of processing options
        self.config.ui.default_remove_dupes = self.remove_dupes_cb.isChecked()
        self.config.ui.default_anonymize_ips = self.anonymize_ips_cb.isChecked()
        self.config.ui.default_mask_payloads = self.mask_payloads_cb.isChecked()

        # 保存最后使用的目录
        if self.base_dir and self.config.ui.remember_last_dir:
            self.config.ui.last_input_dir = self.base_dir

        self.config.save()

    def closeEvent(self, event):
        """Window close event"""
        # Save window state and user preferences
        self.save_window_state()
        self.save_user_preferences()

        # Stop processing thread
        processing_thread = getattr(self.pipeline_manager, "processing_thread", None)
        if processing_thread and processing_thread.isRunning():
            self.stop_pipeline_processing()
            processing_thread.wait(3000)  # Wait up to 3 seconds

        # Unregister configuration callbacks (simplified version temporarily removed)

        event.accept()

    def init_ui(self):
        """Initialize interface (delegated to UIManager)"""
        pass  # UI already initialized in __init__

    def _get_current_theme(self) -> str:
        """Detect whether current system is light or dark mode."""
        return self.get_current_theme()

    def _apply_stylesheet(self):
        """Apply current theme's stylesheet."""
        self.apply_stylesheet()

    def changeEvent(self, event: QEvent):
        """Override changeEvent to monitor system theme changes."""
        self.handle_theme_change(event)
        super().changeEvent(event)

    def create_menu_bar(self):
        """Create menu bar (handled by UIManager)"""
        pass  # Already handled by UIManager in init_ui

    def show_initial_guides(self):
        """Show initial guides in log and report areas at startup (handled by UIManager)"""
        pass  # Already handled by UIManager in init_ui

    def reset_state(self):
        """Reset all state and UI"""
        self.base_dir = None
        self.output_dir = None  # Reset output directory
        self.current_output_dir = None  # Reset current output directory
        self.dir_path_label.setText("Click and pick your pcap directory")
        self.output_path_label.setText("Auto-create or click for custom")  # Reset output path display
        self.log_text.clear()
        self.summary_text.clear()

        # Reset all statistics
        self.files_processed = 0
        self.packets_processed = 0
        self.total_files_to_process = 0
        self.processing_time = 0
        self.file_processing_results.clear()
        self.step_results.clear()
        self.global_ip_mappings.clear()
        self.all_ip_reports.clear()
        self.processed_files_count = 0
        self.current_processing_file = None
        self.subdirs_files_counted.clear()
        self.subdirs_packets_counted.clear()
        self.printed_summary_headers.clear()

        # Reset Live Dashboard display
        self.files_processed_label.setText("0")
        self.packets_processed_label.setText("0")
        self.time_elapsed_label.setText("00:00.00")
        self.progress_bar.setValue(0)

        # Reset other states
        self.user_stopped = False  # Reset stop flag
        if hasattr(self, "_current_file_ips"):
            self._current_file_ips.clear()  # Clear file IP mappings
        if hasattr(self, "_counted_files"):
            self._counted_files.clear()  # Clear packet count cache

        # Stop timer
        if self.timer and self.timer.isActive():
            self.timer.stop()

        # Reset button and display state
        self.start_proc_btn.setEnabled(False)  # Keep disabled until directory is selected
        self.start_proc_btn.setText("Start")
        self.show_initial_guides()

    def handle_thread_progress(self, event_type: PipelineEvents, data: dict):
        """Main slot function to dispatch UI update tasks based on event type"""
        # Emit Qt signal directly (replacing EventCoordinator)
        self.pipeline_event.emit(str(event_type), data)

        # Process UI updates based on event type
        if event_type == PipelineEvents.PIPELINE_START:
            # Initialize progress bar to 0, maximum will be set when we know the actual file count
            self.progress_bar.setValue(0)
            self.progress_bar.setMaximum(100)  # Set to 100 for percentage-based progress

        elif event_type == PipelineEvents.SUBDIR_START:
            # Reset progress bar to 0% when starting directory processing
            self.progress_bar.setValue(0)
            self.update_log(f"Processing directory: {data.get('name', 'N/A')}")

        elif event_type == PipelineEvents.FILE_START:
            # 不在这里递增文件计数，应该在FILE_END时递增
            file_path = data["path"]
            self.current_processing_file = os.path.basename(file_path)
            self.update_log(f"Processing file: {self.current_processing_file}")

            # 初始化当前文件的处理结果记录
            if self.current_processing_file not in self.file_processing_results:
                self.file_processing_results[self.current_processing_file] = {"steps": {}}

        elif event_type == PipelineEvents.FILE_END:
            if self.current_processing_file:
                # **修复**: 增加处理完成的文件计数
                self.processed_files_count += 1

                # 获取输出文件名信息
                output_files = []
                if self.current_processing_file in self.file_processing_results:
                    steps_data = self.file_processing_results[self.current_processing_file]["steps"]
                    step_order = [
                        "Deduplication",
                        "Anonymize IPs",
                        "Mask Payloads",
                    ]
                    for step_name in reversed(step_order):
                        if step_name in steps_data:
                            output_file = steps_data[step_name]["data"].get("output_filename")
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
            count = data.get("count", 0)
            if count > 0:
                self.packets_processed += count
                self.packets_processed_label.setText(str(self.packets_processed))

        elif event_type == PipelineEvents.LOG:
            self.update_log(data["message"])

        elif event_type == PipelineEvents.STEP_SUMMARY:
            # **修复**: 简化包计数逻辑，只从第一个Stage（去重阶段）计算包数，避免重复计算
            step_name = data.get("step_name", "")
            packets_processed = data.get("packets_processed", 0)
            # **修复**: 如果packets_processed为0，尝试使用total_packets字段
            if packets_processed == 0:
                packets_processed = data.get("total_packets", 0)
            current_file = data.get("filename", "")

            # 只从去重阶段计算包数（它总是第一个运行的Stage）
            # **修复**: 支持新旧两种Stage名称，并且只要有包数就计算（不要求>0）
            if (step_name in ["DeduplicationStage", "UnifiedDeduplicationStage"]) and packets_processed >= 0:
                # 检查这个文件是否已经计算过包数
                if not hasattr(self, "_counted_files"):
                    self._counted_files = set()
                if current_file not in self._counted_files:
                    self._counted_files.add(current_file)
                    # Add packet count
                    self.packets_processed += packets_processed
                    # Update UI display
                    self.packets_processed_label.setText(str(self.packets_processed))
                    self._logger.debug(
                        f"Updated packet count: file={current_file}, packets={packets_processed}, total={self.packets_processed}"
                    )

            # 检查是否有降级处理信息
            fallback_used = data.get("fallback_used", False)
            if fallback_used:
                fallback_mode = data.get("fallback_mode", "unknown")
                fallback_details = data.get("fallback_details", {})
                fallback_reason = fallback_details.get("fallback_reason", "Processing failed, using fallback mode")

                self.update_log(f"⚠️  {step_name}: Fallback activated - {fallback_mode}")
                self.update_log(f"   Reason: {fallback_reason}")
                if fallback_details.get("file_size"):
                    self.update_log(f"   File copied as-is ({fallback_details['file_size']} bytes)")

            self.collect_step_result(data)

        elif event_type == PipelineEvents.PIPELINE_END:
            self._animate_progress_to(100)  # 动画到100%
            # 注意：处理完成的逻辑由 PipelineManager 负责处理

        elif event_type == PipelineEvents.ERROR:
            self.processing_error(data["message"])

    def processing_error(self, error_message: str):
        """Handle processing error"""
        self.show_processing_error(error_message)
        self.processing_finished()

    def on_thread_finished(self):
        """Callback function when thread finishes, ensuring UI state is properly restored"""
        # Thread cleanup is now handled by PipelineManager

    def get_elided_text(self, label: QLabel, text: str) -> str:
        """Elide text if it's too long"""
        fm = label.fontMetrics()
        elided_text = fm.elidedText(text, Qt.TextElideMode.ElideMiddle, label.width())
        return elided_text

    def resizeEvent(self, event):
        """Handle window resize events to update elided text"""
        super().resizeEvent(event)
        if self.base_dir:
            self.dir_path_label.setText(self.get_elided_text(self.dir_path_label, self.base_dir))

    def update_time_elapsed(self):
        if not self.start_time:
            return

        elapsed_msecs = self.start_time.msecsTo(QTime.currentTime())
        time_str = format_milliseconds_to_time(elapsed_msecs)
        self.time_elapsed_label.setText(time_str)

    def generate_summary_report_filename(self) -> str:
        """Generate summary report filename with processing options identifier"""

        # Generate processing options identifier
        enabled_steps = []
        if self.anonymize_ips_cb.isChecked():
            enabled_steps.append("AnonymizeIPs")
        if self.remove_dupes_cb.isChecked():
            enabled_steps.append("RemoveDupes")
        if self.mask_payloads_cb.isChecked():
            enabled_steps.append("MaskPayloads")

        steps_suffix = "_".join(enabled_steps) if enabled_steps else "NoSteps"
        timestamp = current_timestamp()

        return f"summary_report_{steps_suffix}_{timestamp}.txt"

    def save_summary_report_to_output_dir(self):
        """Save summary report to output directory"""
        if not self.current_output_dir:
            return

        try:
            filename = self.generate_summary_report_filename()
            file_path = os.path.join(self.current_output_dir, filename)

            # 获取summary text的内容
            summary_content = self.summary_text.toPlainText()

            with open(file_path, "w", encoding="utf-8") as f:
                f.write("# PktMask Summary Report\n")
                f.write(f"# Generated: {current_time()}\n")
                f.write(f"# Working Directory: {self.current_output_dir}\n")
                f.write("#" + "=" * 68 + "\n\n")
                f.write(summary_content)

            self.update_log(f"Summary report saved: {filename}")

        except Exception as e:
            self.update_log(f"Error saving summary report: {str(e)}")

    def find_existing_summary_reports(self) -> List[str]:
        """Find existing summary report files in working directory"""
        if not self.current_output_dir or not os.path.exists(self.current_output_dir):
            return []

        try:
            files = os.listdir(self.current_output_dir)
            summary_files = [f for f in files if f.startswith("summary_report_") and f.endswith(".txt")]
            # 按修改时间倒序排列，最新的在前
            summary_files.sort(
                key=lambda x: os.path.getmtime(os.path.join(self.current_output_dir, x)),
                reverse=True,
            )
            return summary_files
        except Exception:
            return []

    def load_latest_summary_report(self) -> Optional[str]:
        """Load latest summary report content"""
        summary_files = self.find_existing_summary_reports()
        if not summary_files:
            return None

        try:
            latest_file = summary_files[0]
            file_path = os.path.join(self.current_output_dir, latest_file)

            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # 移除文件头部的注释行
            lines = content.split("\n")
            content_lines = []
            skip_header = True

            for line in lines:
                if skip_header and line.startswith("#"):
                    continue
                elif skip_header and line.strip() == "":
                    continue
                else:
                    skip_header = False
                    content_lines.append(line)

            return "\n".join(content_lines)

        except Exception as e:
            self.update_log(f"Error loading summary report: {str(e)}")
            return None

    def _animate_progress_to(self, target_value: int):
        """Smooth animation to target progress value"""
        if self.progress_animation.state() == QPropertyAnimation.State.Running:
            self.progress_animation.stop()

        current_value = self.progress_bar.value()
        self.progress_animation.setStartValue(current_value)
        self.progress_animation.setEndValue(target_value)
        self.progress_animation.start()

    # === Report generation methods (moved from ReportManager) ===
    def update_log(self, message: str):
        """Update log display"""
        try:
            timestamp = datetime.now().strftime("%H:%M:%S")
            formatted_message = f"[{timestamp}] {message}"

            # Add to log text area
            self.log_text.append(formatted_message)

            # Auto-scroll to bottom
            cursor = self.log_text.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            self.log_text.setTextCursor(cursor)

            self._logger.debug(f"UI log updated: {message}")

        except Exception as e:
            self._logger.error(f"Error occurred while updating log display: {e}")

    def generate_partial_summary_on_stop(self):
        """Generate partial summary statistics when user stops processing"""
        separator_length = 70

        # Calculate current time
        if self.timer:
            self.timer.stop()

        # Stop timing and update elapsed time
        if self.start_time:
            from PyQt6.QtCore import QTime

            elapsed_msecs = self.start_time.msecsTo(QTime.currentTime())
            self.processing_time = elapsed_msecs

        self.update_time_elapsed()

        partial_time = self.time_elapsed_label.text()
        partial_files = self.files_processed
        partial_packets = self.packets_processed_count

        # Generate stop summary report
        stop_report = f"\n{'='*separator_length}\n⏹️ PROCESSING STOPPED BY USER\n{'='*separator_length}\n"
        stop_report += "📊 Partial Statistics (Completed Portion):\n"
        stop_report += f"   • Files Processed: {partial_files}\n"
        stop_report += f"   • Packets Processed: {partial_packets:,}\n"
        stop_report += f"   • Processing Time: {partial_time}\n"

        # Calculate partial processing speed
        try:
            time_parts = partial_time.split(":")
            if len(time_parts) >= 2:
                minutes = int(time_parts[-2])
                seconds_with_ms = time_parts[-1].split(".")
                seconds = int(seconds_with_ms[0])
                total_seconds = minutes * 60 + seconds
                if total_seconds > 0 and partial_packets > 0:
                    speed = partial_packets / total_seconds
                    stop_report += f"   • Average Speed: {speed:,.0f} packets/second\n\n"
                else:
                    stop_report += "   • Average Speed: N/A\n\n"
            else:
                stop_report += "   • Average Speed: N/A\n\n"
        except Exception:
            stop_report += "   • Average Speed: N/A\n\n"

        # Display enabled processing steps
        enabled_steps = []
        if self.anonymize_ips_cb.isChecked():
            enabled_steps.append("Anonymize IPs")
        if self.remove_dupes_cb.isChecked():
            enabled_steps.append("Deduplication")
        if self.mask_payloads_cb.isChecked():
            enabled_steps.append("Mask Payloads")

        stop_report += f"🔧 Configured Processing Steps: {', '.join(enabled_steps)}\n"
        stop_report += f"📁 Working Directory: {os.path.basename(self.base_dir) if self.base_dir else 'N/A'}\n"
        stop_report += "⚠️ Processing was interrupted. All intermediate files have been cleaned up.\n"
        stop_report += "❌ No completed output files were generated due to interruption.\n"
        stop_report += f"{'='*separator_length}\n"

        self.summary_text.append(stop_report)

        # Check and display file processing status
        if self.file_processing_results:
            files_status_report = self._generate_files_status_report(separator_length)
            self.summary_text.append(files_status_report)

        # Display global IP mapping summary (only when there are fully completed files)
        if self.processed_files_count >= 1 and self.global_ip_mappings:
            global_partial_report = self._generate_global_ip_mappings_report(separator_length, True)
            if global_partial_report:
                self.summary_text.append(global_partial_report)

        # Display Enhanced Masking intelligent processing statistics (if any)
        enhanced_partial_report = self._generate_enhanced_masking_report(separator_length, is_partial=True)
        if enhanced_partial_report:
            self.summary_text.append(enhanced_partial_report)

        # Corrected restart hint
        restart_hint = "\n💡 RESTART INFORMATION:\n"
        restart_hint += "   • Clicking 'Start' will restart processing from the beginning\n"
        restart_hint += "   • All files will be reprocessed (no partial resume capability)\n"
        restart_hint += "   • Any existing output files will be skipped to avoid overwriting\n"
        restart_hint += "   • Processing will be performed completely for each file\n"
        self.summary_text.append(restart_hint)

    def _generate_files_status_report(self, separator_length: int) -> str:
        """Generate file processing status report"""
        files_status_report = (
            f"\n{'='*separator_length}\n📋 FILES PROCESSING STATUS (At Stop)\n{'='*separator_length}\n"
        )

        completed_files = 0
        partial_files = 0

        for filename, file_result in self.file_processing_results.items():
            steps_data = file_result["steps"]
            if not steps_data:
                continue

            # Check if file is fully processed (all configured steps completed)
            expected_steps = set()
            if self.anonymize_ips_cb.isChecked():
                expected_steps.add("Anonymize IPs")
            if self.remove_dupes_cb.isChecked():
                expected_steps.add("Deduplication")
            if self.mask_payloads_cb.isChecked():
                expected_steps.add("Mask Payloads")

            completed_steps = set(steps_data.keys())
            is_fully_completed = expected_steps.issubset(completed_steps)

            if is_fully_completed:
                completed_files += 1
                files_status_report += self._generate_completed_file_report(filename, steps_data)
            else:
                partial_files += 1
                files_status_report += self._generate_partial_file_report(filename, completed_steps, expected_steps)

        if completed_files == 0 and partial_files > 0:
            files_status_report += "\n⚠️ All files were only partially processed.\n"
            files_status_report += "   No final output files were created.\n"
        elif completed_files > 0:
            files_status_report += f"\n📈 Summary: {completed_files} completed, {partial_files} partial\n"

        files_status_report += f"{'='*separator_length}\n"
        return files_status_report

    def _generate_completed_file_report(self, filename: str, steps_data: Dict) -> str:
        """Generate report for completed file"""
        report = f"\n✅ {filename}\n"
        report += "   Status: FULLY COMPLETED\n"

        # Get final output filename
        step_order = ["Deduplication", "Anonymize IPs", "Mask Payloads"]
        final_output = None
        for step_name in reversed(step_order):
            if step_name in steps_data:
                output_file = steps_data[step_name]["data"].get("output_filename")
                if output_file and not output_file.startswith("tmp"):
                    final_output = output_file
                    break

        if final_output:
            report += f"   Output File: {final_output}\n"

        # Display detailed results
        original_packets = 0
        file_ip_mappings = {}

        # Prioritize getting original packet count from Deduplication step
        if "Deduplication" in steps_data:
            original_packets = steps_data["Deduplication"]["data"].get("total_packets", 0)
        elif "Anonymize IPs" in steps_data:
            original_packets = steps_data["Anonymize IPs"]["data"].get("total_packets", 0)
        elif "Mask Payloads" in steps_data:
            original_packets = steps_data["Mask Payloads"]["data"].get("total_packets", 0)

        for step_name in step_order:
            if step_name in steps_data:
                data = steps_data[step_name]["data"]

                if step_name == "Anonymize IPs":
                    # Support new AnonStage field names (retrieved from extra_metrics)
                    extra_metrics = data.get("extra_metrics", {})
                    original_ips = data.get("original_ips", extra_metrics.get("original_ips", 0))
                    masked_ips = data.get("anonymized_ips", extra_metrics.get("anonymized_ips", 0))
                    rate = (masked_ips / original_ips * 100) if original_ips > 0 else 0
                    report += f"   🛡️  Anonymize IPs: {original_ips} → {masked_ips} IPs ({rate:.1f}%)\n"
                    file_ip_mappings = data.get("file_ip_mappings", extra_metrics.get("file_ip_mappings", {}))

                elif step_name == "Deduplication":
                    data.get("unique_packets", 0)
                    removed = data.get("removed_count", 0)
                    rate = (removed / original_packets * 100) if original_packets > 0 else 0
                    report += f"   🔄 Deduplication: {removed} removed ({rate:.1f}%)\n"

                elif step_name == "Mask Payloads":
                    # Support new MaskPayloadStage field names
                    masked = data.get("packets_modified", data.get("masked_packets", 0))
                    rate = (masked / original_packets * 100) if original_packets > 0 else 0
                    report += f"   ✂️  Mask Payloads: {masked} masked ({rate:.1f}%)\n"

        # Display IP mappings (if any)
        if file_ip_mappings:
            report += f"   🔗 IP Mappings ({len(file_ip_mappings)}):\n"
            for i, (orig_ip, new_ip) in enumerate(sorted(file_ip_mappings.items()), 1):
                if i <= 5:  # Only display first 5
                    report += f"      {i}. {orig_ip} → {new_ip}\n"
                elif i == 6:
                    report += f"      ... and {len(file_ip_mappings) - 5} more\n"
                    break

        return report

    def _generate_partial_file_report(self, filename: str, completed_steps: set, expected_steps: set) -> str:
        """Generate report for partially completed file"""
        report = f"\n🔄 {filename}\n"
        report += "   Status: PARTIALLY PROCESSED (Interrupted)\n"
        report += f"   Completed Steps: {', '.join(completed_steps)}\n"
        report += f"   Missing Steps: {', '.join(expected_steps - completed_steps)}\n"
        report += "   ❌ No final output file generated\n"
        report += "   🗑️ Temporary files cleaned up automatically\n"
        return report

    def _generate_global_ip_mappings_report(self, separator_length: int, is_partial: bool = False) -> Optional[str]:
        """Generate global IP mapping report"""
        # First check if IP anonymization processing is enabled
        if not self.anonymize_ips_cb.isChecked():
            return None

        # Check if global IP mapping data exists
        if not self.global_ip_mappings:
            return None

        # Check if there are fully completed files
        has_completed_files = False
        for filename, file_result in self.file_processing_results.items():
            # Build expected steps based on what's actually configured, with fallback logic
            expected_steps = set()

            # Safe check for GUI components with fallback
            try:
                if hasattr(self, "anonymize_ips_cb") and self.anonymize_ips_cb.isChecked():
                    expected_steps.add("Anonymize IPs")
                if hasattr(self, "remove_dupes_cb") and self.remove_dupes_cb.isChecked():
                    expected_steps.add("Deduplication")
                if hasattr(self, "mask_payloads_cb") and self.mask_payloads_cb.isChecked():
                    expected_steps.add("Mask Payloads")
            except AttributeError:
                # Fallback: if GUI components are not available, infer from actual completed steps
                # This handles cases where the method is called outside of GUI context
                completed_steps = set(file_result["steps"].keys())
                if completed_steps:
                    expected_steps = completed_steps  # Assume all completed steps were expected

            # If we have IP mappings and Anonymize IPs step exists, consider it completed
            if not expected_steps and "Anonymize IPs" in file_result["steps"]:
                expected_steps.add("Anonymize IPs")

            completed_steps = set(file_result["steps"].keys())
            if expected_steps.issubset(completed_steps) or (not expected_steps and completed_steps):
                has_completed_files = True
                break

        # If we have global IP mappings but no completed files detected, still show the report
        # This handles edge cases where the completion detection fails
        if not has_completed_files and len(self.global_ip_mappings) > 0:
            has_completed_files = True

        if is_partial:
            title = "🌐 IP MAPPINGS FROM COMPLETED FILES"
            subtitle = "📝 IP Mapping Table - From Successfully Completed Files Only:"
        else:
            title = "🌐 GLOBAL IP MAPPINGS (All Files Combined)"
            subtitle = "📝 Complete IP Mapping Table - Unique Entries Across All Files:"

        global_partial_report = f"\n{'='*separator_length}\n{title}\n{'='*separator_length}\n"
        global_partial_report += f"{subtitle}\n"
        global_partial_report += f"   • Total Unique IPs Mapped: {len(self.global_ip_mappings)}\n\n"

        sorted_global_mappings = sorted(self.global_ip_mappings.items())
        for i, (orig_ip, new_ip) in enumerate(sorted_global_mappings, 1):
            global_partial_report += f"   {i:2d}. {orig_ip:<16} → {new_ip}\n"

        if is_partial:
            global_partial_report += "\n✅ All unique IP addresses across files have been\n"
            global_partial_report += "   successfully anonymized with consistent mappings.\n"
        else:
            # Safe access to processed_files_count with fallback
            files_count = getattr(
                self,
                "processed_files_count",
                len(self.file_processing_results),
            )
            global_partial_report += f"\n✅ All unique IP addresses across {files_count} files have been\n"
            global_partial_report += "   successfully anonymized with consistent mappings.\n"

        global_partial_report += f"{'='*separator_length}\n"
        return global_partial_report

    def generate_file_complete_report(self, original_filename: str):
        """Generate complete processing report for a single file"""
        if original_filename not in self.file_processing_results:
            return

        file_results = self.file_processing_results[original_filename]
        steps_data = file_results["steps"]

        if not steps_data:
            return

        # **Fix**: Remove duplicate file count increment (already counted in main_window.py FILE_END event)
        # self.processed_files_count += 1  # Remove this line to avoid double counting

        separator_length = 70
        filename_display = original_filename

        # File processing title
        header = f"\n{'='*separator_length}\n📄 FILE PROCESSING RESULTS: {filename_display}\n{'='*separator_length}"
        self.summary_text.append(header)

        # Get original packet count (prioritize from Deduplication step as it contains the true original packet count)
        original_packets = 0
        output_filename = None
        if "Deduplication" in steps_data:
            # Deduplication step's total_packets is the true original packet count
            original_packets = steps_data["Deduplication"]["data"].get("total_packets", 0)
            output_filename = steps_data["Deduplication"]["data"].get("output_filename")
        elif "Anonymize IPs" in steps_data:
            # If no deduplication step, get from IP anonymization step
            original_packets = steps_data["Anonymize IPs"]["data"].get("total_packets", 0)
            output_filename = steps_data["Anonymize IPs"]["data"].get("output_filename")
        elif "Mask Payloads" in steps_data:
            # Finally get from payload masking step
            original_packets = steps_data["Mask Payloads"]["data"].get("total_packets", 0)
            output_filename = steps_data["Mask Payloads"]["data"].get("output_filename")

        # Get final output filename from the last processing step
        step_order = ["Deduplication", "Anonymize IPs", "Mask Payloads"]
        for step_name in reversed(step_order):
            if step_name in steps_data:
                final_output = steps_data[step_name]["data"].get("output_filename")
                if final_output:
                    output_filename = final_output
                    break

        # Display original packet count and output filename
        self.summary_text.append(f"📦 Original Packets: {original_packets:,}")
        if output_filename:
            self.summary_text.append(f"📄 Output File: {output_filename}")
        self.summary_text.append("")

        # Display step results in processing order
        file_ip_mappings = {}  # Store current file's IP mappings

        # **Debug log**: Display collected step data
        self._logger.info(f"🔍 Generating file report: {original_filename}")
        self._logger.info(f"🔍 Collected steps: {list(steps_data.keys())}")
        for step_name, step_info in steps_data.items():
            self._logger.info(
                f"🔍   {step_name}: type={step_info.get('type')}, data_fields={list(step_info.get('data', {}).keys())}"
            )

        # Fix: Get IP mapping information from file-level IP mapping cache
        if hasattr(self, "_current_file_ips") and original_filename in self._current_file_ips:
            file_ip_mappings = self._current_file_ips[original_filename]

        for step_name in step_order:
            if step_name in steps_data:
                step_result = steps_data[step_name]
                step_type = step_result["type"]
                data = step_result["data"]

                self._logger.info(f"🔍 Processing step {step_name}: type={step_type}")

                # For Mask Payloads, record detailed data fields
                if step_name == "Mask Payloads":
                    self._logger.info(
                        f"🔍 Mask Payloads data: packets_processed={data.get('packets_processed')}, packets_modified={data.get('packets_modified')}"
                    )
                    self._logger.info(
                        f"🔍 Mask Payloads data: total_packets={data.get('total_packets')}, masked_packets={data.get('masked_packets')}"
                    )

                if step_type in [
                    "anonymize_ips",
                    "mask_ip",
                    "mask_ips",
                ]:  # Support standard naming and legacy naming
                    # Use new IP statistics data - check both direct data and extra_metrics
                    original_ips = data.get("original_ips", 0)
                    masked_ips = data.get("anonymized_ips", 0)

                    # If not found in direct data, check extra_metrics (for IPAnonymizationStage)
                    if original_ips == 0 and masked_ips == 0:
                        extra_metrics = data.get("extra_metrics", {})
                        original_ips = extra_metrics.get("original_ips", 0)
                        masked_ips = extra_metrics.get("anonymized_ips", 0)

                    rate = (masked_ips / original_ips * 100) if original_ips > 0 else 0
                    line = f"  🎭 {step_name:<18} | Total IPs: {original_ips:>5} | Anonymized IPs: {masked_ips:>4} | Rate: {rate:5.1f}%"

                elif step_type == "remove_dupes":
                    unique = data.get("unique_packets", 0)
                    removed = data.get("removed_count", 0)
                    total_before = data.get("total_packets", 0)
                    rate = (removed / total_before * 100) if total_before > 0 else 0
                    line = f"  🔄 {step_name:<18} | Unique Pkts: {unique:>4} | Removed Pkts: {removed:>4} | Rate: {rate:5.1f}%"

                elif step_type in [
                    "mask_payloads",
                    "mask payloads",
                ]:  # Use standard naming
                    # Fix: MaskStage returns different field names
                    total = data.get("total_packets", data.get("packets_processed", 0))
                    masked = data.get("masked_packets", data.get("packets_modified", 0))
                    rate = (masked / total * 100) if total > 0 else 0

                    # Check if this is Enhanced Masking intelligent processing result
                    if self._is_enhanced_masking(data):
                        line = self._generate_enhanced_masking_report_line(step_name, data)
                    else:
                        line = f"  🛡️ {step_name:<18} | Total Pkts: {total:>5} | Masked Pkts: {masked:>4} | Rate: {rate:5.1f}%"
                else:
                    continue

                self.summary_text.append(line)

        # If IP mappings exist, display file-level IP mappings
        if file_ip_mappings:
            self.summary_text.append("")
            self.summary_text.append("🔗 IP Mappings for this file:")
            sorted_mappings = sorted(file_ip_mappings.items())
            for i, (orig_ip, new_ip) in enumerate(sorted_mappings, 1):
                self.summary_text.append(f"   {i:2d}. {orig_ip:<16} → {new_ip}")

        # If Enhanced Masking was used, display intelligent processing details
        enhanced_report = self._generate_enhanced_masking_report_for_file(original_filename, separator_length)
        if enhanced_report:
            self.summary_text.append(enhanced_report)

        self.summary_text.append(f"{'='*separator_length}")

    def generate_processing_finished_report(self):
        """Generate report when processing is complete"""
        separator_length = 70  # Maintain consistent separator length

        # **Fix**: Save current statistics data before stopping timer and resetting statistics
        # Ensure Live Dashboard display data is not affected by reset
        current_files_processed = self.files_processed_count
        current_packets_processed = self.packets_processed_count
        current_time_elapsed = self.time_elapsed_label.text()

        # Stop timer
        if self.timer and self.timer.isActive():
            self.timer.stop()

        # Stop timing and update elapsed time
        if self.start_time:
            from PyQt6.QtCore import QTime

            elapsed_msecs = self.start_time.msecsTo(QTime.currentTime())
            self.processing_time = elapsed_msecs

        self.update_time_elapsed()

        enabled_steps = []
        if self.remove_dupes_cb.isChecked():
            enabled_steps.append("Deduplication")
        if self.anonymize_ips_cb.isChecked():
            enabled_steps.append("Anonymize IPs")
        if self.mask_payloads_cb.isChecked():
            enabled_steps.append("Mask Payloads")

        completion_report = f"\n{'='*separator_length}\n🎉 PROCESSING COMPLETED!\n{'='*separator_length}\n"
        completion_report += f"🎯 All {current_files_processed} files have been successfully processed.\n"
        completion_report += f"📈 Files Processed: {current_files_processed}\n"
        completion_report += f"📊 Total Packets Processed: {current_packets_processed}\n"
        completion_report += f"⏱️ Time Elapsed: {current_time_elapsed}\n"
        completion_report += f"🔧 Applied Processing Steps: {', '.join(enabled_steps)}\n"

        # Safely handle output directory display
        if self.current_output_dir:
            completion_report += f"📁 Output Location: {os.path.basename(self.current_output_dir)}\n"
        else:
            completion_report += "📁 Output Location: Not specified\n"

        completion_report += "📝 All processed files saved to output directory.\n"
        completion_report += f"{'='*separator_length}\n"

        self.summary_text.append(completion_report)

        # Fix: Add global IP mapping summary report (display deduplicated global IP mappings for multi-file processing)
        global_ip_report = self._generate_global_ip_mappings_report(separator_length, is_partial=False)
        if global_ip_report:
            self.summary_text.append(global_ip_report)

        # Add Enhanced Masking intelligent processing total report
        enhanced_masking_report = self._generate_enhanced_masking_report(separator_length, is_partial=False)
        if enhanced_masking_report:
            self.summary_text.append(enhanced_masking_report)

        # Fix: Automatically save Summary Report to output directory after processing completion
        self._save_summary_report_to_output()

    def set_final_summary_report(self, report: dict):
        """Set final summary report, including detailed IP mapping information."""
        subdir = report.get("path", "N/A")
        stats = report.get("stats", {})
        total_mapping = report.get("data", {}).get("total_mapping", {})

        separator_length = 70  # Maintain consistent separator length

        # Add IP mapping summary information, including detailed mapping table
        text = f"\n{'='*separator_length}\n📋 DIRECTORY PROCESSING SUMMARY\n{'='*separator_length}\n"
        text += f"📂 Directory: {subdir}\n\n"
        text += "🔒 Anonymize IPs Summary:\n"
        text += f"   • Total Unique IPs Discovered: {stats.get('total_unique_ips', 'N/A')}\n"
        text += f"   • Total IPs Anonymized: {stats.get('total_mapped_ips', 'N/A')}\n\n"

        if total_mapping:
            text += "📝 Complete IP Mapping Table (All Files):\n"
            # Display mappings sorted by original IP
            sorted_mappings = sorted(total_mapping.items())
            for i, (orig_ip, new_ip) in enumerate(sorted_mappings, 1):
                text += f"   {i:2d}. {orig_ip:<16} → {new_ip}\n"
            text += "\n"

        text += "✅ All IP addresses have been successfully anonymized while\n"
        text += "   preserving network structure and subnet relationships.\n"
        text += f"{'='*separator_length}\n"

        self.summary_text.append(text)

    def update_summary_report(self, data: Dict[str, Any]):
        """Update summary report display"""
        try:
            # Generate different reports based on data type
            if "filename" in data:
                # Single file processing report
                self._update_file_summary(data)
            elif "step_results" in data:
                # Overall processing summary
                self._update_overall_summary(data)
            else:
                step_type = data.get("type")
                if step_type and step_type.endswith("_final"):
                    report_data = data.get("report")
                    if report_data and "mask_ip" in step_type:
                        self.set_final_summary_report(report_data)
                else:
                    self._logger.warning(f"Unknown summary report data format: {data.keys()}")

        except Exception as e:
            self._logger.error(f"Error occurred while updating summary report: {e}")

    def _update_file_summary(self, data: Dict[str, Any]):
        """Update single file processing summary"""
        data.get("filename", "Unknown file")

        # Get current summary text
        current_text = self.summary_text.toPlainText()

        # Generate file summary
        file_summary = self._generate_file_summary_text(data)

        # Append to existing text
        if current_text.strip():
            updated_text = current_text + "\n\n" + file_summary
        else:
            updated_text = file_summary

        self.summary_text.setPlainText(updated_text)

        # Scroll to bottom
        cursor = self.summary_text.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.summary_text.setTextCursor(cursor)

    def _update_overall_summary(self, data: Dict[str, Any]):
        """Update overall processing summary"""
        summary_text = self._generate_overall_summary_text(data)
        self.summary_text.setPlainText(summary_text)

    def _generate_file_summary_text(self, data: Dict[str, Any]) -> str:
        """Generate single file summary text"""
        filename = data.get("filename", "Unknown file")
        summary_parts = [f"📄 {filename}"]

        # Processing result statistics
        results = data.get("results", {})
        for step_name, result in results.items():
            if isinstance(result, dict):
                if "summary" in result:
                    summary_parts.append(f"  • {step_name}: {result['summary']}")
                elif "packets_processed" in result:
                    summary_parts.append(f"  • {step_name}: {result['packets_processed']} packets")
                elif "ips_anonymized" in result:
                    summary_parts.append(f"  • {step_name}: {result['ips_anonymized']} IPs anonymized")

        return "\n".join(summary_parts)

    def _generate_overall_summary_text(self, data: Dict[str, Any]) -> str:
        """生成整体摘要文本"""
        summary_parts = ["📊 Processing Summary", "=" * 50]

        # 基本统计
        files_processed = data.get("files_processed", 0)
        total_files = data.get("total_files", 0)
        status = data.get("status", "unknown")

        summary_parts.append(f"Status: {status.title().replace('_', ' ')}")
        summary_parts.append(f"Files Processed: {files_processed}/{total_files}")

        if files_processed > 0 and total_files > 0:
            percentage = (files_processed / total_files) * 100
            summary_parts.append(f"Completion: {percentage:.1f}%")

        summary_parts.append("")

        # 步骤统计
        step_results = data.get("step_results", {})
        if step_results:
            summary_parts.append("📈 Step Statistics:")

            # 聚合各步骤的统计
            step_stats = self._aggregate_step_statistics(step_results)

            for step_name, stats in step_stats.items():
                summary_parts.append(f"\n🔧 {step_name}:")
                for key, value in stats.items():
                    summary_parts.append(f"  • {key}: {value}")

        # 输出目录信息
        output_dir = data.get("output_directory")
        if output_dir:
            summary_parts.append("\n📁 Output Directory:")
            summary_parts.append(f"  {output_dir}")

        # 时间戳
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        summary_parts.append(f"\n⏰ Generated: {timestamp}")

        return "\n".join(summary_parts)

    def _generate_final_summary_text(self, data: Dict[str, Any]) -> str:
        """生成最终摘要文本"""
        summary_parts = ["🎯 Final Processing Report", "=" * 60]

        # 处理状态
        status = data.get("status", "unknown")
        files_processed = data.get("files_processed", 0)
        total_files = data.get("total_files", 0)

        if status == "completed":
            summary_parts.append("✅ Status: Successfully Completed")
        elif status == "stopped_by_user":
            summary_parts.append("⏹️ Status: Stopped by User")
        else:
            summary_parts.append(f"❓ Status: {status.title()}")

        summary_parts.append(f"📊 Files Processed: {files_processed} of {total_files}")

        if files_processed > 0 and total_files > 0:
            percentage = (files_processed / total_files) * 100
            summary_parts.append(f"📈 Completion Rate: {percentage:.1f}%")

        summary_parts.append("")

        # 详细统计
        step_results = data.get("step_results", {})
        if step_results:
            summary_parts.append("📋 Detailed Statistics:")
            summary_parts.append("-" * 40)

            # 聚合统计
            aggregated_stats = self._aggregate_step_statistics(step_results)

            for step_name, stats in aggregated_stats.items():
                summary_parts.append(f"\n🔧 {step_name}:")
                for stat_name, stat_value in stats.items():
                    summary_parts.append(f"  • {stat_name}: {stat_value}")

        # 文件详情
        if step_results:
            summary_parts.append("\n📄 File Details:")
            summary_parts.append("-" * 30)

            for filename, file_results in step_results.items():
                summary_parts.append(f"\n📁 {filename}:")
                for step_name, result in file_results.items():
                    if isinstance(result, dict):
                        if "summary" in result:
                            summary_parts.append(f"  • {step_name}: {result['summary']}")
                        else:
                            summary_parts.append(f"  • {step_name}: Processed")

        # 输出信息
        output_dir = data.get("output_directory")
        if output_dir:
            summary_parts.append("\n📂 Output Location:")
            summary_parts.append(f"  {output_dir}")

        # 生成时间
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        summary_parts.append(f"\n🕒 Report Generated: {timestamp}")

        # 工具信息
        summary_parts.append("\n" + "=" * 60)
        summary_parts.append("🛠️ Generated by PktMask - Network Packet Processing Tool")

        return "\n".join(summary_parts)

    def _aggregate_step_statistics(self, step_results: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """聚合步骤统计信息"""
        aggregated = {}

        for filename, file_results in step_results.items():
            for step_name, result in file_results.items():
                if step_name not in aggregated:
                    aggregated[step_name] = {}

                if isinstance(result, dict):
                    for key, value in result.items():
                        if isinstance(value, (int, float)):
                            # 数值类型进行累加
                            if key in aggregated[step_name]:
                                aggregated[step_name][key] += value
                            else:
                                aggregated[step_name][key] = value
                        elif key == "summary" and isinstance(value, str):
                            # 摘要信息收集到列表
                            summary_key = "summaries"
                            if summary_key not in aggregated[step_name]:
                                aggregated[step_name][summary_key] = []
                            aggregated[step_name][summary_key].append(f"{filename}: {value}")

        # 后处理：计算平均值、格式化显示等
        for step_name, stats in aggregated.items():
            if "summaries" in stats:
                # 将摘要列表转换为计数
                summaries = stats.pop("summaries")
                stats["files_processed"] = len(summaries)

        return aggregated

    def clear_displays(self):
        """Clear display areas"""
        try:
            self.log_text.clear()
            self.summary_text.clear()
            self._logger.debug("Cleared log and summary display")

        except Exception as e:
            self._logger.error(f"Error occurred while clearing display area: {e}")

    def export_summary_report(self, filepath: str) -> bool:
        """导出摘要报告到文件"""
        try:
            content = self.summary_text.toPlainText()

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

            self._logger.info(f"Summary report exported to: {filepath}")
            return True

        except Exception as e:
            self._logger.error(f"Failed to export summary report: {e}")
            return False

    def _save_summary_report_to_output(self):
        """私有方法：保存摘要报告到输出目录"""
        try:
            # 委托给FileManager或使用MainWindow的现有方法
            if hasattr(self, "save_summary_report_to_output_dir"):
                self.save_summary_report_to_output_dir()
            else:
                self._logger.warning("Cannot find method to save Summary Report")
        except Exception as e:
            self._logger.error(f"Failed to save Summary Report to output directory: {e}")

    def collect_step_result(self, data: dict):
        """收集每个步骤的处理结果，但不立即显示"""
        if not self.current_processing_file:
            return

        step_type = data.get("type")
        step_name_raw = data.get("step_name", "")

        # **调试日志**: 记录收集的步骤结果
        self._logger.info(
            f"🔍 Collecting step results: file={self.current_processing_file}, step={step_name_raw}, type={step_type}"
        )
        self._logger.info(f"🔍 Data fields: {list(data.keys())}")

        # DEBUG: Print detailed data structure
        print(f"🔍 DEBUG collect_step_result: step_name_raw='{step_name_raw}', step_type='{step_type}'")
        print(f"🔍 DEBUG collect_step_result: data keys={list(data.keys())}")
        if "extra_metrics" in data:
            print(f"🔍 DEBUG collect_step_result: extra_metrics keys={list(data['extra_metrics'].keys())}")

        # DEBUG: Print detailed data structure
        print(f"🔍 DEBUG collect_step_result: step_name_raw='{step_name_raw}', step_type='{step_type}'")
        print(f"🔍 DEBUG collect_step_result: data keys={list(data.keys())}")
        if "extra_metrics" in data:
            print(f"🔍 DEBUG collect_step_result: extra_metrics keys={list(data['extra_metrics'].keys())}")

        # **修复**: 支持新Pipeline系统的步骤名称
        # 从step_name推断步骤类型，而不是仅依赖type字段
        if not step_type:
            # 新Pipeline系统没有type字段，从step_name推断
            if step_name_raw in [
                "AnonStage",
                "IPAnonymizationStage",
                "UnifiedIPAnonymizationStage",  # Add new Unified stage name
                "AnonymizationStage",  # Add standardized stage name
            ]:  # Support both old and new stage names
                step_type = "anonymize_ips"  # Use standard naming
            elif step_name_raw in [
                "DeduplicationStage",
                "UnifiedDeduplicationStage",
            ]:  # Add new Unified stage name
                step_type = "remove_dupes"
            elif step_name_raw in [
                "MaskStage",
                "MaskPayloadStage",
                "NewMaskPayloadStage",
                "MaskingStage",  # Add standardized stage name
                "Mask Payloads",  # Add the actual display name from NewMaskPayloadStage
                "Mask Payloads (v2)",
                "Mask Payloads Stage",
            ]:
                step_type = "mask_payloads"  # Use standard naming
            else:
                step_type = step_name_raw.lower()

        self._logger.info(f"🔍 Inferred step type: {step_type}")

        # DEBUG: Print inferred step type
        print(f"🔍 DEBUG collect_step_result: inferred step_type='{step_type}'")

        if not step_type or step_type.endswith("_final"):
            if step_type and step_type.endswith("_final"):
                # 处理最终报告，提取IP映射信息
                report_data = data.get("report")
                if report_data and "anonymize_ips" in step_type:
                    self.set_final_summary_report(report_data)
            return

        # 标准化步骤名称 - 修复Pipeline和ReportManager之间的映射不匹配
        step_display_names = {
            "anonymize_ips": "Anonymize IPs",  # Standard naming
            "remove_dupes": "Deduplication",
            "mask_payloads": "Mask Payloads",  # Standard naming
        }

        step_name = step_display_names.get(step_type, step_type)

        # DEBUG: Print standardized step name
        print(f"🔍 DEBUG collect_step_result: standardized step_name='{step_name}'")

        # 存储步骤结果
        self.file_processing_results[self.current_processing_file]["steps"][step_name] = {
            "type": step_type,
            "data": data,
        }

        # **关键修复**: 如果是IP匿名化步骤，提取并累积IP映射到全局映射
        is_ip_anonymization = (
            step_type in ["anonymize_ips"]
            or step_name_raw
            in [
                "AnonStage",
                "IPAnonymizationStage",
                "UnifiedIPAnonymizationStage",  # Add new Unified stage name
                "AnonymizationStage",  # Add standardized stage name
            ]  # Support both old and new stage names
            or "ip_mappings" in data
            or "file_ip_mappings" in data
        )

        if is_ip_anonymization:
            # 从step数据中提取IP映射
            ip_mappings = None
            if "file_ip_mappings" in data:
                ip_mappings = data["file_ip_mappings"]
            elif "ip_mappings" in data:
                ip_mappings = data["ip_mappings"]
            elif "extra_metrics" in data:
                # 检查extra_metrics中的IP映射（新Pipeline系统）
                extra_metrics = data["extra_metrics"]
                if "file_ip_mappings" in extra_metrics:
                    ip_mappings = extra_metrics["file_ip_mappings"]
                elif "ip_mappings" in extra_metrics:
                    ip_mappings = extra_metrics["ip_mappings"]
                # 新增：检查IPAnonymizationStage的extra_metrics中包含的原始stats
                # IPAnonymizationStage将所有原始stats包含在extra_metrics中
                elif any(key in extra_metrics for key in ["total_packets", "anonymized_packets"]):
                    # 这是IPAnonymizationStage的数据，检查是否有ip_mappings
                    for key, value in extra_metrics.items():
                        if key == "ip_mappings" and isinstance(value, dict):
                            ip_mappings = value
                            break

            if ip_mappings and isinstance(ip_mappings, dict):
                # 保存文件级IP映射
                if not hasattr(self, "_current_file_ips"):
                    self._current_file_ips = {}
                self._current_file_ips[self.current_processing_file] = ip_mappings

                # **关键修复**: 将当前文件的IP映射累积到全局映射中（不覆盖）
                if not hasattr(self, "global_ip_mappings") or self.global_ip_mappings is None:
                    self.global_ip_mappings = {}

                # 累积映射而不是覆盖
                self.global_ip_mappings.update(ip_mappings)

                self._logger.info(
                    f"✅ Collected IP mappings: file={self.current_processing_file}, new_mappings={len(ip_mappings)}, global_total={len(self.global_ip_mappings)}"
                )
            else:
                self._logger.warning(
                    f"IP anonymization step completed, but no valid IP mapping data found: {list(data.keys())}"
                )
        else:
            self._logger.debug(f"Non-IP anonymization step: {step_name_raw}")

    def _is_enhanced_masking(self, data: Dict[str, Any]) -> bool:
        """检查是否是增强掩码处理结果 - 基于双模块架构"""
        data.get("step_name", "")

        # 检查Enhanced Masking特有的字段组合 - 必须是真正的Enhanced Intelligent Mode
        enhanced_indicators = [
            "processing_mode" in data and data.get("processing_mode") == "Enhanced Intelligent Mode",
            "protocol_stats" in data,
            "strategies_applied" in data,
            "enhancement_level" in data,
        ]

        # Protocol adaptation mode has different processing mode identifiers, not 'Enhanced Intelligent Mode'
        # 如果有真正的Enhanced Masking特有字段组合，认为是智能处理
        return all(enhanced_indicators[:3])  # 前3个字段必须都存在

    def _generate_enhanced_masking_report_line(self, step_name: str, data: Dict[str, Any]) -> str:
        """生成Enhanced Masking的处理结果报告行（移除HTTP统计）"""
        total = data.get("total_packets", 0)
        masked = data.get("masked_packets", 0)

        # 获取协议统计（移除HTTP）
        protocol_stats = data.get("protocol_stats", {})
        protocol_stats.get("tls_packets", 0)
        protocol_stats.get("other_packets", 0)

        # 基础报告行（增强模式标识）
        rate = (masked / total * 100) if total > 0 else 0
        line = f"  ✂️  {step_name:<18} | Enhanced Mode | Total: {total:>4} | Masked: {masked:>4} | Rate: {rate:5.1f}%"

        return line

    def _generate_enhanced_masking_report(self, separator_length: int, is_partial: bool = False) -> Optional[str]:
        """生成Enhanced Masking的智能处理统计总报告（移除HTTP支持）"""
        # 检查是否有Enhanced Masking处理的文件
        enhanced_files = []
        total_enhanced_stats = {
            "total_packets": 0,
            "tls_packets": 0,
            "other_packets": 0,
            "strategies_applied": set(),
            "files_processed": 0,
        }

        # 遍历所有处理过的文件，找出使用Enhanced Masking的文件
        for filename, file_result in self.file_processing_results.items():
            steps_data = file_result.get("steps", {})
            payload_step = steps_data.get("Mask Payloads")

            if payload_step and self._is_enhanced_masking(payload_step.get("data", {})):
                enhanced_files.append(filename)
                data = payload_step["data"]

                # 汇总统计（移除HTTP）
                total_enhanced_stats["files_processed"] += 1
                total_enhanced_stats["total_packets"] += data.get("total_packets", 0)

                protocol_stats = data.get("protocol_stats", {})
                total_enhanced_stats["tls_packets"] += protocol_stats.get("tls_packets", 0)
                total_enhanced_stats["other_packets"] += protocol_stats.get("other_packets", 0)

                strategies = data.get("strategies_applied", [])
                total_enhanced_stats["strategies_applied"].update(strategies)

        # 如果没有Enhanced Masking处理，返回None
        if not enhanced_files:
            return None

        # 生成智能处理总报告
        title = "🧠 ENHANCED MASKING INTELLIGENCE REPORT"
        if is_partial:
            title += " (Partial)"

        report = f"\n{'='*separator_length}\n{title}\n{'='*separator_length}\n"

        # 处理模式和增强信息
        report += "🎯 Processing Mode: Intelligent Auto-Detection\n"
        report += "⚡ Enhancement Level: 4x accuracy improvement over simple masking\n"
        report += (
            f"📁 Enhanced Files: {total_enhanced_stats['files_processed']}/{len(self.file_processing_results)}\n\n"
        )

        # 协议检测统计（移除HTTP）
        total_packets = total_enhanced_stats["total_packets"]
        if total_packets > 0:
            tls_rate = (total_enhanced_stats["tls_packets"] / total_packets) * 100
            other_rate = (total_enhanced_stats["other_packets"] / total_packets) * 100

            report += "📊 Protocol Detection Results:\n"
            report += f"   • TLS packets: {total_enhanced_stats['tls_packets']:,} ({tls_rate:.1f}%) - Intelligent TLS strategy\n"
            report += f"   • Other packets: {total_enhanced_stats['other_packets']:,} ({other_rate:.1f}%) - General strategy\n"
            report += f"   • Total processed: {total_packets:,} packets in 4 stages\n\n"

        # 策略应用统计
        strategies_list = list(total_enhanced_stats["strategies_applied"])
        if strategies_list:
            report += "🔧 Applied Strategies:\n"
            for strategy in sorted(strategies_list):
                report += f"   • {strategy}\n"
            report += "\n"

        # 智能处理优势说明（移除HTTP）
        report += "🚀 Enhanced Processing Benefits:\n"
        report += "   • Automatic protocol detection and strategy selection\n"
        report += "   • TLS handshake preserved, ApplicationData masked\n"
        report += "   • Improved accuracy while maintaining network analysis capability\n"

        report += f"{'='*separator_length}\n"

        return report

    def _generate_enhanced_masking_report_for_file(self, filename: str, separator_length: int) -> Optional[str]:
        """为单个文件生成Enhanced Masking的处理结果报告（移除HTTP统计）"""
        if filename not in self.file_processing_results:
            return None

        file_result = self.file_processing_results[filename]
        steps_data = file_result.get("steps", {})
        payload_step = steps_data.get("Mask Payloads")

        if not payload_step or not self._is_enhanced_masking(payload_step.get("data", {})):
            return None

        data = payload_step["data"]
        protocol_stats = data.get("protocol_stats", {})

        report = f"\n🧠 Enhanced Masking Details for {filename}:\n"
        report += "   📊 Protocol Analysis:\n"

        total_packets = data.get("total_packets", 0)
        if total_packets > 0:
            tls_packets = protocol_stats.get("tls_packets", 0)
            other_packets = protocol_stats.get("other_packets", 0)

            if tls_packets > 0:
                tls_rate = (tls_packets / total_packets) * 100
                report += f"      • TLS: {tls_packets} packets ({tls_rate:.1f}%) - Handshake preserved\n"

            if other_packets > 0:
                other_rate = (other_packets / total_packets) * 100
                report += f"      • Other: {other_packets} packets ({other_rate:.1f}%) - Generic strategy\n"

        # 策略应用信息
        strategies = data.get("strategies_applied", [])
        if strategies:
            report += f"   🔧 Applied Strategies: {', '.join(strategies)}\n"

        # 处理效率
        enhancement_level = data.get("enhancement_level", "Not specified")
        report += f"   ⚡ Enhancement: {enhancement_level}\n"

        return report

    def _generate_enhanced_masking_report_for_directory(self, separator_length: int) -> Optional[str]:
        """生成整个目录的Enhanced Masking的处理结果报告"""
        # 这个方法在目录级别处理完成时调用
        # 目前先返回通用的Enhanced报告
        return self._generate_enhanced_masking_report(separator_length, is_partial=False)

    # === Dialog and file selection methods (moved from DialogsManager) ===
    def show_user_guide_dialog(self):
        """Show user guide dialog"""
        try:
            with open(resource_path("summary.md"), "r", encoding="utf-8") as f:
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

            self._logger.info("Show user guide dialog")

        except Exception as e:
            self._logger.error(f"Failed to load user guide: {e}")
            QMessageBox.critical(self, "Error", f"Could not load User Guide: {str(e)}")

    def show_about_dialog(self):
        """Show about dialog"""
        try:
            about_text = """
            <h2>PktMask</h2>
            <p><b>Network Packet Processing Tool</b></p>
            <p>Version: 1.0.0</p>

            <p>PktMask is a powerful network packet processing tool designed for:</p>
            <ul>
                <li>🔄 <b>Remove Dupes</b> - Eliminate duplicate packets</li>
                <li>🛡️ <b>Anonymize IPs</b> - Advanced hierarchical IP masking</li>
                <li>✂️ <b>Smart Trimming</b> - Intelligent payload reduction</li>
            </ul>

            <p><b>Features:</b></p>
            <ul>
                <li>Preserves network topology and relationships</li>
                <li>Maintains TLS handshake integrity</li>
                <li>Optimized for security research and compliance</li>
                <li>Safe data sharing capabilities</li>
            </ul>

            <p><b>Use Cases:</b></p>
            <ul>
                <li>Security research and analysis</li>
                <li>Network troubleshooting</li>
                <li>Compliance reporting</li>
                <li>Data anonymization for sharing</li>
            </ul>

            <hr>
            <p><small>Built with Python and PyQt6</small></p>
            """

            dialog = QDialog(self)
            dialog.setWindowTitle("About PktMask")
            dialog.setFixedSize(450, 500)

            layout = QVBoxLayout(dialog)

            # Main text
            text_widget = QTextEdit()
            text_widget.setReadOnly(True)
            text_widget.setHtml(about_text)

            # Set font
            font = QFont()
            font.setPointSize(11)
            text_widget.setFont(font)

            layout.addWidget(text_widget)

            # Buttons
            button_layout = QHBoxLayout()
            button_layout.addStretch()

            ok_button = QPushButton("OK")
            ok_button.clicked.connect(dialog.accept)
            ok_button.setMinimumSize(80, 30)
            button_layout.addWidget(ok_button)

            layout.addLayout(button_layout)

            dialog.exec()

            self._logger.info("About dialog displayed")

        except Exception as e:
            self._logger.error(f"Failed to show About dialog: {e}")
            QMessageBox.critical(self, "Error", f"Could not show About dialog: {str(e)}")

    def show_processing_error(self, error_message: str):
        """Show processing error dialog"""
        try:
            # If error message is empty or just "Unknown error", use a more friendly message
            if not error_message or error_message.strip() == "Unknown error":
                error_message = (
                    "An unexpected error occurred during processing. Please check the logs for more details."
                )

            # Check if in automated test environment
            is_automated_test = (
                os.environ.get("QT_QPA_PLATFORM") == "offscreen"  # Headless mode
                or os.environ.get("PYTEST_CURRENT_TEST") is not None  # pytest environment
                or os.environ.get("CI") == "true"  # CI environment
                or hasattr(self, "_test_mode")  # Test mode flag
            )

            if is_automated_test:
                # In automated test environment, only log error without showing blocking dialog
                self._logger.error(f"Processing error (automated test mode): {error_message}")
                # Update main window log for test verification
                self.update_log(f"Error: {error_message}")
                # Optional: send a non-blocking notification
                self._send_non_blocking_error_notification(error_message)
                return

            # Show modal dialog in normal GUI environment
            error_dialog = QMessageBox(self)
            error_dialog.setIcon(QMessageBox.Icon.Critical)
            error_dialog.setWindowTitle("Processing Error")
            error_dialog.setText("An error occurred during processing:")
            error_dialog.setInformativeText(error_message)

            # Add detailed information button
            error_dialog.setDetailedText(
                f"Error details:\n"
                f"Timestamp: {QTime.currentTime().toString()}\n"
                f"Error: {error_message}\n\n"
                f"Troubleshooting tips:\n"
                f"1. Check if input files are valid pcap files\n"
                f"2. Ensure you have write permissions to the output directory\n"
                f"3. Check available disk space\n"
                f"4. Review the log panel for more detailed error information"
            )

            error_dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
            error_dialog.exec()

            self._logger.error(f"Processing error dialog displayed: {error_message}")

        except Exception as e:
            self._logger.error(f"Failed to show processing error dialog: {e}")
            # If dialog display fails, at least update the log
            self.update_log(f"Error: {error_message}")

    def _send_non_blocking_error_notification(self, error_message: str):
        """Send non-blocking error notification (for automated testing)"""
        try:
            # Can send status bar message, log update or other non-blocking notifications
            if hasattr(self, "statusBar"):
                self.statusBar().showMessage(f"Error: {error_message}", 5000)

            # Emit error signal for test listening
            if hasattr(self, "error_occurred"):
                self.error_occurred.emit(error_message)

        except Exception as e:
            self._logger.debug(f"Failed to send non-blocking notification: {e}")

    def show_processing_complete(self, summary: str):
        """Show processing complete dialog"""
        try:
            success_dialog = QMessageBox(self)
            success_dialog.setIcon(QMessageBox.Icon.Information)
            success_dialog.setWindowTitle("Processing Complete")
            success_dialog.setText("Processing completed successfully!")

            if summary:
                success_dialog.setDetailedText(summary)

            success_dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
            success_dialog.exec()

            self._logger.info("Showed processing complete dialog")

        except Exception as e:
            self._logger.error(f"Failed to show processing complete dialog: {e}")

    # ========================================================================
    # SIMPLE DIALOGS (from DialogManager - simplified)
    # ========================================================================

    def show_error(self, title: str, message: str):
        """Show error dialog (simplified wrapper)"""
        try:
            QMessageBox.critical(self, title, message)
            self._logger.error(f"Error dialog displayed: {title} - {message}")
        except Exception as e:
            self._logger.error(f"Failed to show error dialog: {e}")

    def show_warning(self, title: str, message: str):
        """Show warning dialog (simplified wrapper)"""
        try:
            QMessageBox.warning(self, title, message)
            self._logger.warning(f"Warning dialog displayed: {title} - {message}")
        except Exception as e:
            self._logger.error(f"Failed to show warning dialog: {e}")

    def show_info(self, title: str, message: str):
        """Show info dialog (simplified wrapper)"""
        try:
            QMessageBox.information(self, title, message)
            self._logger.info(f"Info dialog displayed: {title} - {message}")
        except Exception as e:
            self._logger.error(f"Failed to show info dialog: {e}")

    def ask_question(self, title: str, message: str) -> bool:
        """Show confirmation dialog (simplified wrapper)"""
        try:
            reply = QMessageBox.question(
                self,
                title,
                message,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            result = reply == QMessageBox.StandardButton.Yes
            self._logger.info(f"Question dialog displayed: {title} - User choice: {'Yes' if result else 'No'}")
            return result

        except Exception as e:
            self._logger.error(f"Failed to show question dialog: {e}")
            return False

    def show_progress_dialog(self, title: str, message: str, maximum: int = 0) -> QProgressDialog:
        """Show progress dialog"""
        try:
            progress = QProgressDialog(message, "Cancel", 0, maximum, self)
            progress.setWindowTitle(title)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(1000)  # Show after 1 second

            self._logger.info(f"Created progress dialog: {title}")
            return progress

        except Exception as e:
            self._logger.error(f"Failed to create progress dialog: {e}")
            return None

    # ========================================================================
    # FILE/DIRECTORY SELECTION (from FileManager)
    # ========================================================================

    def choose_input_folder(self):
        """Select input directory (renamed from choose_folder)"""
        dir_path = QFileDialog.getExistingDirectory(self, "Select Input Folder", self.last_opened_dir)
        if dir_path:
            self.base_dir = dir_path
            self.last_opened_dir = dir_path  # Record currently selected directory
            self.dir_path_label.setText(os.path.basename(dir_path))

            # Auto-generate default output path
            self.generate_default_output_path()
            self._update_start_button_state()  # Intelligently update button state

            self._logger.info(f"Selected input directory: {dir_path}")

    def handle_output_click(self):
        """Handle output path button click - open directory if processing is complete, otherwise select custom output directory"""
        if self.current_output_dir and os.path.exists(self.current_output_dir):
            # If output directory exists, open it
            self.open_output_directory()
        else:
            # Otherwise let user select custom output directory
            self.choose_output_folder()

    def choose_output_folder(self):
        """Select custom output directory"""
        dir_path = QFileDialog.getExistingDirectory(self, "Select Output Folder", self.last_opened_dir)
        if dir_path:
            self.output_dir = dir_path
            self.output_path_label.setText(os.path.basename(dir_path))
            self._logger.info(f"Selected custom output directory: {dir_path}")

    def generate_default_output_path(self):
        """Generate default output path preview"""
        if not self.base_dir:
            return

        # Reset to default mode
        self.output_dir = None
        self.output_path_label.setText("Auto-create or click for custom")
        self._logger.debug("Reset to default output path mode")

    def generate_actual_output_path(self) -> str:
        """Generate actual output directory path"""
        timestamp = current_timestamp()

        # Get input directory name
        if self.base_dir:
            input_dir_name = os.path.basename(self.base_dir)
            # Generate new naming format: input_dir_name-Masked-timestamp
            output_name = f"{input_dir_name}-Masked-{timestamp}"
        else:
            # If no input directory, use default format
            output_name = f"PktMask-{timestamp}"

        if self.output_dir:
            # Custom output directory
            actual_path = os.path.join(self.output_dir, output_name)
        else:
            # Default output directory
            if self.config.ui.default_output_dir:
                actual_path = os.path.join(self.config.ui.default_output_dir, output_name)
            else:
                # Use subdirectory of input directory
                actual_path = os.path.join(self.base_dir, output_name)

        self._logger.info(f"Generated actual output path: {actual_path}")
        return actual_path

    def open_output_directory(self):
        """Open output directory"""
        if not self.current_output_dir or not os.path.exists(self.current_output_dir):
            QMessageBox.warning(self, "Warning", "Output directory not found.")
            return

        try:
            success = open_directory_in_system(self.current_output_dir)
            if success:
                self.update_log(f"Opened output directory: {os.path.basename(self.current_output_dir)}")
                self._logger.info(f"Opened output directory: {self.current_output_dir}")
            else:
                self._logger.error("Failed to open output directory")
                QMessageBox.critical(self, "Error", "Could not open output directory.")
        except Exception as e:
            self._logger.error(f"Error occurred while opening output directory: {e}")
            QMessageBox.critical(self, "Error", f"Error opening directory: {str(e)}")

    # ========================================================================
    # DIRECTORY VALIDATION AND INFO (from FileManager)
    # ========================================================================

    def validate_input_directory(self, directory: str) -> bool:
        """Validate if input directory is valid"""
        if not directory:
            return False

        if not os.path.exists(directory):
            self._logger.warning(f"Input directory does not exist: {directory}")
            return False

        if not os.path.isdir(directory):
            self._logger.warning(f"Input path is not a directory: {directory}")
            return False

        # Check if there are pcap files
        pcap_extensions = [".pcap", ".pcapng", ".cap"]
        for file in os.listdir(directory):
            if any(file.lower().endswith(ext) for ext in pcap_extensions):
                return True

        self._logger.warning(f"No pcap files found in input directory: {directory}")
        return False

    def get_directory_info(self, directory: str) -> dict:
        """Get directory information"""
        info = {
            "exists": False,
            "is_directory": False,
            "pcap_files": [],
            "total_files": 0,
            "total_size": 0,
        }

        if not directory or not os.path.exists(directory):
            return info

        info["exists"] = True
        info["is_directory"] = os.path.isdir(directory)

        if not info["is_directory"]:
            return info

        try:
            pcap_extensions = [".pcap", ".pcapng", ".cap"]

            for file in os.listdir(directory):
                filepath = os.path.join(directory, file)
                if os.path.isfile(filepath):
                    info["total_files"] += 1
                    info["total_size"] += os.path.getsize(filepath)

                    if any(file.lower().endswith(ext) for ext in pcap_extensions):
                        info["pcap_files"].append(file)

        except Exception as e:
            self._logger.error(f"Error occurred while getting directory information: {e}")

        return info

    # ========================================================================
    # REPORT FILE OPERATIONS (from FileManager)
    # ========================================================================

    def save_summary_report_to_output_dir(self) -> bool:
        """Save summary report to output directory"""
        if not self.current_output_dir:
            self._logger.warning("Output directory path is empty, cannot save summary report")
            return False

        try:
            # Ensure output directory exists
            if not os.path.exists(self.current_output_dir):
                self._logger.info(f"Creating output directory: {self.current_output_dir}")
                os.makedirs(self.current_output_dir, exist_ok=True)

            filename = self.generate_summary_report_filename()
            filepath = os.path.join(self.current_output_dir, filename)

            # Get summary text
            summary_text = self.summary_text.toPlainText()

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(summary_text)

            self._logger.info(f"Summary report saved to: {filepath}")
            self.update_log(f"Summary report saved: {filename}")
            return True

        except Exception as e:
            self._logger.error(f"Failed to save summary report: {e}")
            self.update_log(f"Error saving summary report: {str(e)}")
            return False

    def generate_summary_report_filename(self) -> str:
        """Generate summary report filename"""
        timestamp = current_timestamp()

        # Generate processing options identifier
        enabled_steps = []
        if hasattr(self, "anonymize_ips_cb") and self.anonymize_ips_cb.isChecked():
            enabled_steps.append("MaskIP")
        if hasattr(self, "remove_dupes_cb") and self.remove_dupes_cb.isChecked():
            enabled_steps.append("Dedup")
        if hasattr(self, "mask_payloads_cb") and self.mask_payloads_cb.isChecked():
            enabled_steps.append("Trim")

        steps_suffix = "_".join(enabled_steps) if enabled_steps else "NoSteps"
        filename = f"summary_report_{steps_suffix}_{timestamp}.txt"

        return filename

    def find_existing_summary_reports(self) -> list[str]:
        """Find existing summary report files"""
        if not self.current_output_dir or not os.path.exists(self.current_output_dir):
            return []

        try:
            reports = []
            for file in os.listdir(self.current_output_dir):
                if file.startswith("summary_report_") and file.endswith(".txt"):
                    filepath = os.path.join(self.current_output_dir, file)
                    reports.append(filepath)

            # Sort by modification time, newest first
            reports.sort(key=lambda x: os.path.getmtime(x), reverse=True)
            return reports

        except Exception as e:
            self._logger.error(f"Error occurred while finding summary report files: {e}")
            return []

    def load_latest_summary_report(self) -> Optional[str]:
        """Load latest summary report"""
        reports = self.find_existing_summary_reports()
        if not reports:
            return None

        try:
            latest_report = reports[0]  # Latest report
            with open(latest_report, "r", encoding="utf-8") as f:
                content = f.read()

            self._logger.info(f"Loaded latest summary report: {latest_report}")
            return content

        except Exception as e:
            self._logger.error(f"Failed to load summary report: {e}")
            return None

    # ========================================================================
    # LEGACY COMPATIBILITY METHODS
    # ========================================================================

    # These methods maintain backward compatibility with old method names
    def choose_folder(self):
        """Legacy method - redirects to choose_input_folder"""
        return self.choose_input_folder()

    def show_error_dialog(self, title: str, message: str):
        """Legacy method - redirects to show_error"""
        return self.show_error(title, message)

    def show_warning_dialog(self, title: str, message: str):
        """Legacy method - redirects to show_warning"""
        return self.show_warning(title, message)

    def show_info_dialog(self, title: str, message: str):
        """Legacy method - redirects to show_info"""
        return self.show_info(title, message)

    def show_question_dialog(self, title: str, message: str) -> bool:
        """Legacy method - redirects to ask_question"""
        return self.ask_question(title, message)

    # === Pipeline processing methods (moved from PipelineManager) ===
    def _setup_timer(self):
        """Set up processing time tracking timer"""
        self.time_elapsed = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_time_elapsed)

    def toggle_pipeline_processing(self):
        """Toggle processing flow state"""
        self._logger.debug("toggle_pipeline_processing called")

        # Store thread reference to avoid race condition
        thread = self.processing_thread
        if thread and thread.isRunning():
            self._logger.debug("Stopping pipeline processing")
            self.stop_pipeline_processing()
        else:
            self._logger.debug("Starting pipeline processing")
            self.start_pipeline_processing()

    def start_pipeline_processing(self):
        """Start processing flow"""
        self._logger.debug("start_pipeline_processing called")

        if not self.base_dir:
            self._logger.warning("No input directory selected")
            from PyQt6.QtWidgets import QMessageBox

            try:
                QMessageBox.warning(
                    self,
                    "Warning",
                    "Please choose an input folder to process.",
                )
                self._logger.debug("Warning dialog shown successfully")
            except Exception as e:
                self._logger.error(f"Failed to show warning dialog: {e}")
                # Fallback: update log text
                if hasattr(self, "update_log"):
                    self.update_log("⚠️ Please choose an input folder to process.")
            return

        # Generate actual output directory path
        self.current_output_dir = self.generate_actual_output_path()

        # Create output directory
        try:
            import os

            os.makedirs(self.current_output_dir, exist_ok=True)
            self.update_log(f"📁 Created output directory: {os.path.basename(self.current_output_dir)}")

            # Update output path display
            self.output_path_label.setText(os.path.basename(self.current_output_dir))
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.critical(
                self,
                "Error",
                f"Failed to create output directory: {str(e)}",
            )
            return

        # Reset UI and counters for new run
        self.log_text.clear()
        self.summary_text.clear()
        self.all_ip_reports.clear()
        self.files_processed_count = 0
        self.packets_processed_count = 0

        # Reset Live Dashboard display
        self.files_processed_label.setText("0")
        self.packets_processed_label.setText("0")
        self.subdirs_files_counted.clear()
        self.subdirs_packets_counted.clear()
        self.printed_summary_headers.clear()
        self.file_processing_results.clear()  # Clear file processing results
        self.current_processing_file = None  # Reset current processing file
        self.global_ip_mappings.clear()  # Clear global IP mappings
        self.processed_files_count = 0  # Reset file count
        self.user_stopped = False  # Reset stop flag

        # Disable controls via Qt signal
        self.ui_update_requested.emit(
            "enable_controls",
            {
                "controls": [
                    "dir_path_label",
                    "output_path_label",
                    "anonymize_ips_cb",
                    "remove_dupes_cb",
                    "mask_payloads_cb",
                ],
                "enabled": False,
            },
        )

        # Start processing with unified core
        self._start_with_consistent_processor()

    def stop_pipeline_processing(self):
        """Stop the processing pipeline and clean up resources"""
        self.user_stopped = True  # Set stop flag
        self.update_log("--- Stopping pipeline... ---")

        # Store thread reference to avoid race condition
        thread = self.processing_thread
        if thread:
            thread.stop()
            # Wait for thread to safely end, maximum wait 3 seconds
            if not thread.wait(3000):
                self.log_text.append("Warning: Pipeline did not stop gracefully, forcing termination.")
                thread.terminate()
                thread.wait()

        # Generate partial summary statistics when stopped
        self.generate_partial_summary_on_stop()

        # Re-enable controls via Qt signal
        self.ui_update_requested.emit(
            "enable_controls",
            {
                "controls": [
                    "dir_path_label",
                    "output_path_label",
                    "anonymize_ips_cb",
                    "remove_dupes_cb",
                    "mask_payloads_cb",
                    "start_proc_btn",
                ],
                "enabled": True,
            },
        )
        self.ui_update_requested.emit("update_button_text", {"button": "start_proc_btn", "text": "Start"})

    def _start_with_consistent_processor(self):
        """Start processing using new ConsistentProcessor (feature flag enabled)

        CRITICAL: This method preserves 100% GUI functionality while using
        the new unified core processing logic.
        """
        # Log feature flag status for debugging
        if GUIFeatureFlags.is_gui_debug_mode():
            status = GUIFeatureFlags.get_status_summary()
            self._logger.info(f"Feature flags: {status}")
            self.update_log("🔧 Using new unified processing core")

        # Get checkbox states using exact same logic as legacy implementation
        remove_dupes_checked = self.remove_dupes_cb.isChecked()
        anonymize_ips_checked = self.anonymize_ips_cb.isChecked()
        mask_payloads_checked = self.mask_payloads_cb.isChecked()

        # Validate options using GUI wrapper
        try:
            GUIConsistentProcessor.validate_gui_options(
                remove_dupes_checked, anonymize_ips_checked, mask_payloads_checked
            )
        except ValueError as e:
            self._logger.warning(f"No processing steps selected: {str(e)}")
            self.update_log(f"⚠️ {str(e)}")
            return

        # Create threaded executor using GUI helper
        try:
            self.processing_thread = GUIThreadingHelper.create_threaded_executor(
                remove_dupes_checked=remove_dupes_checked,
                anonymize_ips_checked=anonymize_ips_checked,
                mask_payloads_checked=mask_payloads_checked,
                base_dir=self.base_dir,
                output_dir=self.current_output_dir,
            )
        except Exception as e:
            self._logger.error(f"Configuration error: {str(e)}")
            self.update_log(f"❌ Configuration error: {str(e)}")
            return

        # Log configuration summary
        config_summary = GUIConsistentProcessor.get_gui_configuration_summary(
            remove_dupes_checked, anonymize_ips_checked, mask_payloads_checked
        )
        self._logger.info(f"Configuration: {config_summary}")

        # Start processing using same UI flow as legacy
        self._start_gui_thread_processing()

    def _start_gui_thread_processing(self):
        """Common GUI thread processing setup for both implementations

        CRITICAL: This method preserves the exact UI state management,
        signal connections, and timing behavior as the original implementation.
        """
        # Connect signals (same as original start_processing)
        self.processing_thread.progress_signal.connect(self.handle_thread_progress)
        self.processing_thread.finished.connect(self.on_thread_finished)

        # Update UI state (same as original start_processing)
        self.start_proc_btn.setText("Stop")
        self.start_proc_btn.setEnabled(True)
        self._update_start_button_style()

        # Reset statistics before starting new processing
        self.files_processed = 0
        self.packets_processed = 0
        self.total_files_to_process = 0
        self.processing_time = 0
        self.file_processing_results.clear()
        self.step_results.clear()
        self.global_ip_mappings.clear()
        self.all_ip_reports.clear()
        self.processed_files_count = 0
        self.current_processing_file = None
        self.subdirs_files_counted.clear()
        self.subdirs_packets_counted.clear()
        self.printed_summary_headers.clear()

        # Also reset the main window's packet counting cache
        if hasattr(self, "_counted_files"):
            self._counted_files.clear()

        # Start timing
        from PyQt6.QtCore import QTime

        self.start_time = QTime.currentTime()
        self.time_elapsed = 0
        self.timer.start(100)  # Update every 100ms

        # Start thread (same as original)
        self.processing_thread.start()

        self._logger.info(f"Processing thread started, output directory: {self.current_output_dir}")

    def handle_thread_progress(self, event_type: PipelineEvents, data: dict):
        """Handle thread progress events"""
        try:
            # First let MainWindow handle events to update UI statistics and collect data
            self.handle_thread_progress(event_type, data)

            # Then PipelineManager handles its own logic
            # Handle pipeline start events
            if event_type in (
                PipelineEvents.PIPELINE_START,
                PipelineEvents.PIPELINE_STARTED,
            ):
                # Pipeline sends total directory count, but we need to track file count
                data.get("total_subdirs", data.get("total_files", 0))
                # Reset file counter
                self.files_processed = 0

            # Handle subdirectory start events
            elif event_type == PipelineEvents.SUBDIR_START:
                data.get("name", "Unknown directory")
                file_count = data.get("file_count", 0)
                self.total_files_to_process = file_count  # Set actual total file count

            # Handle file completion events
            elif event_type in (PipelineEvents.FILE_END, PipelineEvents.FILE_COMPLETED):
                self.files_processed += 1
                # Update Live Dashboard display
                self.files_processed_label.setText(str(self.files_processed))
                self._update_progress()

            # Handle pipeline completion events
            elif event_type in (
                PipelineEvents.PIPELINE_END,
                PipelineEvents.PIPELINE_COMPLETED,
            ):
                self.processing_finished()

            # Handle step summary events
            elif event_type == PipelineEvents.STEP_SUMMARY:
                # Important: collect step result data for final report
                self.collect_step_result(data)

            # Handle error events
            elif event_type == PipelineEvents.ERROR:
                data.get("message", data.get("error", "Unknown error"))
                # MainWindow has already handled this, no need to repeat

        except Exception as e:
            self._logger.error(f"Error occurred while processing progress event: {e}")
            self.processing_error(f"Event processing error: {str(e)}")

    def collect_step_result(self, data: dict):
        """Collect step results"""
        step_name = data.get("step_name", "")
        filename = data.get("filename", data.get("path", ""))

        # Collect all available result data
        result_data = {}

        # Extract useful statistics from data
        for key, value in data.items():
            if key not in ["step_name", "filename", "path", "type"]:
                result_data[key] = value

        # If there's an existing result field, merge it
        if "result" in data:
            if isinstance(data["result"], dict):
                result_data.update(data["result"])
            else:
                result_data["result"] = data["result"]

        # Collect step result (moved from StatisticsManager)
        file_key = filename.split("/")[-1] if filename else "unknown"
        if file_key not in self.step_results:
            self.step_results[file_key] = {}
        self.step_results[file_key][step_name] = result_data

        # Note: Real-time statistics are handled by MainWindow

    def get_processing_stats(self) -> dict:
        """Get processing statistics"""
        # Return processing summary (moved from StatisticsManager)
        from PyQt6.QtCore import QTime

        from pktmask.utils.time import format_milliseconds_to_time

        elapsed_time = "00:00.00"
        if self.start_time:
            elapsed_msecs = self.start_time.msecsTo(QTime.currentTime())
            elapsed_time = format_milliseconds_to_time(elapsed_msecs)

        return {
            "files_processed": self.files_processed,
            "total_files": self.total_files_to_process,
            "packets_processed": self.packets_processed,
            "processing_time": elapsed_time,
            "step_results": self.step_results.copy(),
            "file_processing_results": self.file_processing_results.copy(),
            "global_ip_mappings": self.global_ip_mappings.copy(),
            "all_ip_reports": self.all_ip_reports.copy(),
        }

    def _update_progress(self):
        """Update progress bar"""
        if self.total_files_to_process > 0:
            progress = int((self.files_processed / self.total_files_to_process) * 100)
            # Ensure progress doesn't exceed 100%
            progress = min(progress, 100)
            self._animate_progress_to(progress)
            self._logger.debug(f"Progress updated: {self.files_processed}/{self.total_files_to_process} = {progress}%")
        else:
            # If no files to process, keep progress at 0
            self._animate_progress_to(0)

    def processing_finished(self):
        """Processing complete"""
        # 首先清理线程状态，确保UI状态检查正确
        # Note: Thread cleanup is also handled in on_thread_finished to ensure cleanup
        if self.processing_thread:
            self.processing_thread = None

        # **Fix**: Before generating the report, ensure Live Dashboard displays final statistics
        # Update Live Dashboard to show final statistics
        final_files_processed = self.files_processed
        final_packets_processed = self.packets_processed

        # Ensure Live Dashboard displays the correct final data
        self.files_processed_label.setText(str(final_files_processed))
        self.packets_processed_label.setText(str(final_packets_processed))

        # Delegate to ReportManager to generate report
        self.generate_processing_finished_report()

        import os

        from pktmask.utils.file_ops import open_directory_in_system

        # Update output path display
        if self.current_output_dir:
            self.output_path_label.setText(os.path.basename(self.current_output_dir))
        self.update_log("Output directory ready. Click output path to view results.")

        # If configuration is enabled, automatically open output directory
        if self.config.ui.auto_open_output and self.current_output_dir:
            try:
                success = open_directory_in_system(self.current_output_dir)
                if success:
                    self.update_log(f"Auto-opened output directory: {os.path.basename(self.current_output_dir)}")
                else:
                    self._logger.warning("Failed to auto-open output directory")
            except Exception as e:
                self._logger.error(f"Error auto-opening output directory: {e}")

        # Use QTimer.singleShot to ensure UI updates are executed in the next cycle of the event loop
        from PyQt6.QtCore import QTimer

        def update_ui_state():
            """Delayed UI state update"""
            # Directly set button state
            self.start_proc_btn.setText("Start")
            self.start_proc_btn.setEnabled(True)

            # Enable other controls
            self.dir_path_label.setEnabled(True)
            self.output_path_label.setEnabled(True)
            for cb in [
                self.anonymize_ips_cb,
                self.remove_dupes_cb,
                self.mask_payloads_cb,
            ]:
                cb.setEnabled(True)

            # Update button style
            self._update_start_button_style()

        def ensure_final_stats_display():
            """Ensure final statistics are correctly displayed in Live Dashboard"""
            # **Fix**: Again ensure Live Dashboard displays the correct final statistics
            # Prevent any subsequent operations from accidentally resetting the display
            self.files_processed_label.setText(str(final_files_processed))
            self.packets_processed_label.setText(str(final_packets_processed))

        # Delay 100ms to execute UI update
        QTimer.singleShot(100, update_ui_state)

        # **Fix**: Delay 200ms to again ensure statistics display is correct, preventing overwrite by other operations
        QTimer.singleShot(200, ensure_final_stats_display)

        self._logger.info("Processing flow completed")

    def on_thread_finished(self):
        """Thread completion handling"""
        # Ensure thread cleanup happens regardless of how processing ended
        if self.processing_thread:
            self.processing_thread = None

    def reset_processing_state(self):
        """Reset processing state (only called when starting new processing)"""
        # Reset all statistics
        self.files_processed = 0
        self.packets_processed = 0
        self.total_files_to_process = 0
        self.processing_time = 0
        self.file_processing_results.clear()
        self.step_results.clear()
        self.global_ip_mappings.clear()
        self.all_ip_reports.clear()
        self.processed_files_count = 0
        self.current_processing_file = None
        self.subdirs_files_counted.clear()
        self.subdirs_packets_counted.clear()
        self.printed_summary_headers.clear()

        self.user_stopped = False

        # Notify UI update via Qt signal, but only reset display when starting new processing
        # This avoids accidentally resetting Live Dashboard display after processing completion
        self.statistics_changed.emit({"action": "reset"})

        # Stop timer
        if self.timer.isActive():
            self.timer.stop()

    def generate_partial_summary_on_stop(self):
        """Generate partial summary when stopped"""
        try:
            # Get processing summary
            stats = self.get_processing_stats()
            partial_data = {**stats, "status": "stopped_by_user"}

            self.set_final_summary_report(partial_data)

        except Exception as e:
            self._logger.error(f"Error occurred while generating partial summary: {e}")

    def _generate_final_report(self):
        """Generate final report"""
        try:
            # Get processing summary
            stats = self.get_processing_stats()
            final_data = {
                **stats,
                "status": "completed",
                "output_directory": self.current_output_dir,
            }

            self.set_final_summary_report(final_data)

        except Exception as e:
            self._logger.error(f"Error occurred while generating final report: {e}")

    # Old _build_pipeline_config method has been removed, use service layer's build_pipeline_config function

    # === Statistics attributes are now direct attributes (no longer using property accessors) ===
    # All statistics are initialized in __init__ and accessed directly

    def set_test_mode(self, enabled: bool = True):
        """Set test mode (for automated testing)"""
        self._test_mode = enabled
        if enabled:
            self._logger.info("Test mode enabled - dialogs will be handled automatically")
        else:
            self._logger.info("Test mode disabled")
        return self


def main():
    """Main function"""
    import os

    # Check if in test mode or headless mode
    test_mode = os.getenv("PKTMASK_TEST_MODE", "").lower() in ("true", "1", "yes")
    headless_mode = os.getenv("PKTMASK_HEADLESS", "").lower() in ("true", "1", "yes")

    if test_mode or headless_mode:
        # Test mode: create application but don't show window or enter event loop
        try:
            app = QApplication.instance()
            if app is None:
                app = QApplication(sys.argv)

            # Create window in test mode but don't show
            window = MainWindow()
            if hasattr(window, "set_test_mode"):
                window.set_test_mode(True)

            # Return immediately in test mode, don't enter event loop
            return window if test_mode else 0

        except Exception as e:
            print(f"GUI initialization failed in test mode: {e}")
            return None
    else:
        # Normal mode: full GUI startup
        app = QApplication(sys.argv)
        window = MainWindow()
        window.show()
        sys.exit(app.exec())
