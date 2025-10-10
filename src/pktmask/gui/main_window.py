#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Main window module
Implements graphical interface
"""

import os
import sys
from typing import List, Optional

import markdown
from PyQt6.QtCore import QEasingCurve, QEvent, QPropertyAnimation, Qt, QTime, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QFont, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QProgressBar,
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
from pktmask.utils.path import resource_path

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
        """Initialize all managers"""
        # Import manager classes
        from .managers import DialogsManager, PipelineManager, ReportManager

        # 创建管理器实例
        self.dialogs = DialogsManager(self)  # Unified dialogs and file manager
        self.pipeline_manager = PipelineManager(self)
        self.report_manager = ReportManager(self)

        # Backward compatibility: create aliases for old manager names
        self.file_manager = self.dialogs  # FileManager functionality now in DialogsManager
        self.dialog_manager = self.dialogs  # DialogManager functionality now in DialogsManager

        # Connect internal Qt signals (must be done after managers are created)
        self._connect_signals()

        self._logger.debug("All managers initialization completed")

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
            # Note: file_manager is now an alias to dialogs manager for backward compatibility
            self.dir_path_label.clicked.connect(self.dialogs.choose_input_folder)
            self.output_path_label.clicked.connect(self.dialogs.handle_output_click)

            # Processing button signals
            self.start_proc_btn.clicked.connect(self.pipeline_manager.toggle_pipeline_processing)
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
        if hasattr(self.main_window, "log_text"):
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
            if hasattr(self, "pipeline_manager") and self.pipeline_manager.processing_thread is None:
                # Only reset display when no processing thread is running (i.e., starting new processing)
                self.files_processed_label.setText("0")
                self.packets_processed_label.setText("0")
                self.time_elapsed_label.setText("00:00.00")
                self.progress_bar.setValue(0)
            # If processing or just completed, keep current display unchanged
        else:
            # Update UI display
            if hasattr(self, "pipeline_manager"):
                stats = self.pipeline_manager.get_processing_stats()
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

    def show_user_guide_dialog(self):
        """Show user guide dialog"""
        self.dialog_manager.show_user_guide_dialog()

    def show_initial_guides(self):
        """Show initial guides in log and report areas at startup (handled by UIManager)"""
        pass  # Already handled by UIManager in init_ui

    def choose_folder(self):
        """Choose directory"""
        self.file_manager.choose_folder()

    def handle_output_click(self):
        """Handle output path button click"""
        self.file_manager.handle_output_click()

    def choose_output_folder(self):
        """Choose custom output directory"""
        self.file_manager.choose_output_folder()

    def generate_default_output_path(self):
        """Generate default output path preview"""
        self.file_manager.generate_default_output_path()

    def generate_actual_output_path(self) -> str:
        """Generate actual output directory path"""
        return self.file_manager.generate_actual_output_path()

    def open_output_directory(self):
        """Open output directory"""
        self.file_manager.open_output_directory()

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

    def toggle_pipeline_processing(self):
        """Toggle processing start/stop based on current state"""
        self.pipeline_manager.toggle_pipeline_processing()

    def generate_partial_summary_on_stop(self):
        """Generate partial summary statistics when user stops (delegated to ReportManager)"""
        self.report_manager.generate_partial_summary_on_stop()

    def stop_pipeline_processing(self):
        """Stop pipeline processing (delegated to PipelineManager)"""
        self.pipeline_manager.stop_pipeline_processing()

    def start_pipeline_processing(self):
        """Start pipeline processing (delegated to PipelineManager)"""
        self.pipeline_manager.start_pipeline_processing()

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

    def collect_step_result(self, data: dict):
        """Collect processing results for each step (delegated to ReportManager)"""
        self.report_manager.collect_step_result(data)

    def generate_file_complete_report(self, original_filename: str):
        """Generate complete processing report for a single file (delegated to ReportManager)"""
        self.report_manager.generate_file_complete_report(original_filename)

    def update_summary_report(self, data: dict):
        """Update summary report (delegated to ReportManager)"""
        self.report_manager.update_summary_report(data)

    def set_final_summary_report(self, report: dict):
        """Set final summary report (delegated to ReportManager)"""
        self.report_manager.set_final_summary_report(report)

    def update_log(self, message: str):
        """Update log display"""
        self.report_manager.update_log(message)

    def processing_finished(self):
        """Processing finished (delegated to PipelineManager)"""
        self.pipeline_manager.processing_finished()

    def processing_error(self, error_message: str):
        """Handle processing error"""
        self.dialog_manager.show_processing_error(error_message)
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

    def show_about_dialog(self):
        """Show about dialog"""
        self.dialog_manager.show_about_dialog()

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
