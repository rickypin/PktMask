#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
UI管理器 - 负责界面初始化和样式管理
"""

from typing import TYPE_CHECKING

from PyQt6.QtCore import *
from PyQt6.QtGui import *
from PyQt6.QtWidgets import *

if TYPE_CHECKING:
    from ..main_window import MainWindow

from pktmask.common.constants import UIConstants
from pktmask.infrastructure.logging import get_logger
from pktmask.utils.path import resource_path

from ..stylesheet import generate_stylesheet


class UIManager:
    """UI Manager - responsible for interface initialization and style management"""

    def __init__(self, main_window: "MainWindow"):
        self.main_window = main_window
        self.config = main_window.config
        self._logger = get_logger(__name__)

    def init_ui(self):
        """Initialize interface"""
        self._setup_window_properties()
        self._create_menu_bar()
        self._setup_main_layout()
        self._connect_signals()
        self._apply_initial_styles()
        self._check_and_display_dependencies()
        self._show_initial_guides()

    def _setup_window_properties(self):
        """Set window properties"""
        self.main_window.setWindowTitle("PktMask")

        # 使用配置中的窗口尺寸
        window_width = self.config.ui.window_width
        window_height = self.config.ui.window_height
        self.main_window.setGeometry(100, 100, window_width, window_height)

        # 设置最小尺寸
        self.main_window.setMinimumSize(
            self.config.ui.window_min_width, self.config.ui.window_min_height
        )

        self.main_window.setWindowIcon(QIcon(resource_path("icon.png")))

    def _create_menu_bar(self):
        """Create menu bar"""
        menu_bar = self.main_window.menuBar()

        # File menu
        file_menu = menu_bar.addMenu("File")

        reset_action = QAction("Reset All", self.main_window)
        reset_action.triggered.connect(self.main_window.reset_state)
        reset_action.setShortcut("Ctrl+R")
        file_menu.addAction(reset_action)

        file_menu.addSeparator()

        exit_action = QAction("Exit", self.main_window)
        exit_action.triggered.connect(self.main_window.close)
        exit_action.setShortcut("Ctrl+Q")
        file_menu.addAction(exit_action)

        # Help menu
        help_menu = menu_bar.addMenu("Help")

        user_guide_action = QAction("User Guide", self.main_window)
        user_guide_action.triggered.connect(self.main_window.show_user_guide_dialog)
        help_menu.addAction(user_guide_action)

        about_action = QAction("About", self.main_window)
        about_action.triggered.connect(self.main_window.show_about_dialog)
        help_menu.addAction(about_action)

    def _setup_main_layout(self):
        """Set up main layout"""
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
        self.main_window.dir_path_label = QPushButton(
            "Click and pick your pcap directory"
        )
        self.main_window.dir_path_label.setObjectName("DirPathLabel")
        self.main_window.dir_path_label.setMaximumHeight(UIConstants.BUTTON_MAX_HEIGHT)
        self.main_window.dir_path_label.setCursor(Qt.CursorShape.PointingHandCursor)
        input_path_layout.addWidget(input_label)
        input_path_layout.addWidget(self.main_window.dir_path_label, 1)
        input_layout.addLayout(input_path_layout)

        # 右侧：Output Directory - 单行布局
        output_layout = QVBoxLayout()
        output_layout.setSpacing(5)
        output_label = QLabel("Output:")
        output_label.setMaximumHeight(20)
        output_path_layout = QHBoxLayout()
        output_path_layout.setSpacing(8)
        self.main_window.output_path_label = QPushButton(
            "Auto-create or click for custom"
        )
        self.main_window.output_path_label.setObjectName("DirPathLabel")
        self.main_window.output_path_label.setMaximumHeight(30)
        self.main_window.output_path_label.setCursor(Qt.CursorShape.PointingHandCursor)
        output_path_layout.addWidget(output_label)
        output_path_layout.addWidget(self.main_window.output_path_label, 1)
        output_layout.addLayout(output_path_layout)

        dirs_layout.addLayout(input_layout, 1)
        dirs_layout.addLayout(output_layout, 1)

        # 保存引用
        self.main_window.dirs_group = dirs_group

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

        self.main_window.remove_dupes_cb = QCheckBox("Remove Dupes")
        self.main_window.anonymize_ips_cb = QCheckBox("Anonymize IPs")
        self.main_window.mask_payloads_cb = QCheckBox(
            "Mask Payloads ( Keep TLS Handshakes )"
        )

        self.main_window.mask_payloads_cb.setToolTip(
            "Intelligently masks packet payloads while preserving TLS handshake data."
        )

        # 设置手型光标
        for cb in [
            self.main_window.remove_dupes_cb,
            self.main_window.anonymize_ips_cb,
            self.main_window.mask_payloads_cb,
        ]:
            cb.setCursor(Qt.CursorShape.PointingHandCursor)

        # 使用配置中的默认状态
        self.main_window.remove_dupes_cb.setChecked(self.config.ui.default_remove_dupes)
        self.main_window.anonymize_ips_cb.setChecked(
            self.config.ui.default_anonymize_ips
        )
        self.main_window.mask_payloads_cb.setChecked(
            self.config.ui.default_mask_payloads
        )

        pipeline_layout.addWidget(self.main_window.remove_dupes_cb)
        pipeline_layout.addWidget(self.main_window.anonymize_ips_cb)
        pipeline_layout.addWidget(self.main_window.mask_payloads_cb)
        pipeline_layout.addStretch()

        # Step 3: Execute
        execute_group = QGroupBox("Run Processing")
        execute_group.setMaximumHeight(85)
        execute_layout = QVBoxLayout(execute_group)
        execute_layout.setContentsMargins(15, 20, 15, 20)
        execute_layout.setSpacing(5)
        self.main_window.start_proc_btn = QPushButton("Start")
        self.main_window.start_proc_btn.setMinimumHeight(35)
        self.main_window.start_proc_btn.setMaximumHeight(35)
        self.main_window.start_proc_btn.setEnabled(False)
        self.main_window.start_proc_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        execute_layout.addWidget(self.main_window.start_proc_btn)

        row2_layout.addWidget(pipeline_group, 3)
        row2_layout.addWidget(execute_group, 1)

        # 保存引用
        self.main_window.row2_widget = row2_widget

    def _create_dashboard_group(self):
        """Create dashboard group"""
        dashboard_group = QGroupBox("Live Dashboard")
        dashboard_group.setMaximumHeight(140)
        dashboard_layout = QVBoxLayout(dashboard_group)
        dashboard_layout.setContentsMargins(15, 20, 15, 12)
        dashboard_layout.setSpacing(10)

        # 进度条
        self.main_window.progress_bar = QProgressBar()
        self.main_window.progress_bar.setTextVisible(False)
        self.main_window.progress_bar.setFixedHeight(18)

        # 初始化进度条动画
        self.main_window.progress_animation = QPropertyAnimation(
            self.main_window.progress_bar, b"value"
        )
        self.main_window.progress_animation.setDuration(300)
        self.main_window.progress_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        dashboard_layout.addWidget(self.main_window.progress_bar)

        # KPI布局
        kpi_layout = QGridLayout()
        kpi_layout.setSpacing(10)
        self.main_window.files_processed_label = QLabel("0")
        self.main_window.files_processed_label.setObjectName("FilesProcessedLabel")
        self.main_window.packets_processed_label = QLabel("0")
        self.main_window.packets_processed_label.setObjectName("IpsMaskedLabel")
        self.main_window.time_elapsed_label = QLabel("00:00.00")
        self.main_window.time_elapsed_label.setObjectName("DupesRemovedLabel")

        kpi_layout.addWidget(
            self.main_window.files_processed_label, 0, 0, Qt.AlignmentFlag.AlignCenter
        )
        kpi_layout.addWidget(
            QLabel("Files Processed"), 1, 0, Qt.AlignmentFlag.AlignCenter
        )
        kpi_layout.addWidget(
            self.main_window.packets_processed_label, 0, 1, Qt.AlignmentFlag.AlignCenter
        )
        kpi_layout.addWidget(
            QLabel("Packets Processed"), 1, 1, Qt.AlignmentFlag.AlignCenter
        )
        kpi_layout.addWidget(
            self.main_window.time_elapsed_label, 0, 2, Qt.AlignmentFlag.AlignCenter
        )
        kpi_layout.addWidget(QLabel("Time Elapsed"), 1, 2, Qt.AlignmentFlag.AlignCenter)

        dashboard_layout.addLayout(kpi_layout)

        # 保存引用
        self.main_window.dashboard_group = dashboard_group

    def _create_log_group(self):
        """Create log group"""
        log_group = QGroupBox("Log")
        log_layout = QVBoxLayout(log_group)
        log_layout.setContentsMargins(12, 20, 12, 12)
        self.main_window.log_text = QTextEdit()
        self.main_window.log_text.setReadOnly(True)

        # 设置Log区域的字体大小
        log_font = QFont()
        log_font.setPointSize(12)
        self.main_window.log_text.setFont(log_font)
        log_layout.addWidget(self.main_window.log_text)

        # 保存引用
        self.main_window.log_group = log_group

    def _create_summary_group(self):
        """Create summary group"""
        summary_group = QGroupBox("Summary Report")
        summary_layout = QVBoxLayout(summary_group)
        summary_layout.setContentsMargins(12, 20, 12, 12)
        self.main_window.summary_text = QTextEdit()
        self.main_window.summary_text.setReadOnly(True)

        # 设置Summary Report区域的字体大小
        summary_font = QFont()
        summary_font.setPointSize(12)
        self.main_window.summary_text.setFont(summary_font)
        summary_layout.addWidget(self.main_window.summary_text)

        # 保存引用
        self.main_window.summary_group = summary_group

    def _setup_grid_layout(self, main_layout):
        """Set up grid layout"""
        # Add components to grid layout
        main_layout.addWidget(self.main_window.dirs_group, 0, 0, 1, 2)
        main_layout.addWidget(self.main_window.row2_widget, 1, 0, 1, 2)
        main_layout.addWidget(self.main_window.dashboard_group, 2, 0)
        main_layout.addWidget(self.main_window.log_group, 3, 0)
        main_layout.addWidget(self.main_window.summary_group, 2, 1, 2, 1)

        # 设置拉伸因子
        main_layout.setColumnStretch(0, 2)  # 左列
        main_layout.setColumnStretch(1, 3)  # 右列
        main_layout.setRowStretch(0, 0)  # Step 1 row
        main_layout.setRowStretch(1, 0)  # Step 2&3 row
        main_layout.setRowStretch(2, 0)  # Dashboard row
        main_layout.setRowStretch(3, 2)  # Log row

    def _connect_signals(self):
        """Connect signals"""
        try:
            # 目录选择信号
            self.main_window.dir_path_label.clicked.connect(
                self.main_window.file_manager.choose_folder
            )
            self.main_window.output_path_label.clicked.connect(
                self.main_window.file_manager.handle_output_click
            )

            # 处理按钮信号
            self.main_window.start_proc_btn.clicked.connect(
                self.main_window.pipeline_manager.toggle_pipeline_processing
            )
            self._logger.debug("Start button signal connected successfully")

        except Exception as e:
            self._logger.error(f"Failed to connect start button signal: {e}")
            import traceback

            traceback.print_exc()

        # checkbox state change signals - correctly call UIManager methods
        self.main_window.anonymize_ips_cb.stateChanged.connect(
            self._update_start_button_state
        )
        self.main_window.remove_dupes_cb.stateChanged.connect(
            self._update_start_button_state
        )
        self.main_window.mask_payloads_cb.stateChanged.connect(
            self._update_start_button_state
        )

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
            self.main_window.log_text.append("⚠️  Unable to verify system dependencies")
            self.main_window.log_text.append("   Some features may not work properly")
            self.main_window.log_text.append("")

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
            self.main_window.log_text.append(status_text)

    def _show_initial_guides(self):
        """Show initial guides"""
        self.main_window.log_text.setPlaceholderText(
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
            formatted_content = "\n" + self._format_summary_md_content(
                summary_md_content
            )

        except Exception:
            # If reading fails, use fallback content
            formatted_content = (
                "\n📊 Processing results and statistics will be displayed here.\n\n"
                "═══════════════════════════════════════════════════════════════════\n\n"
                "📦 PktMask — Network Packet Processing Tool\n\n"
                "🔄 Remove Dupes\n"
                "   • Eliminates duplicate packets to reduce file size\n"
                "   • Reduces noise in network analysis and forensics\n"
                "   • Optimizes storage and speeds up analysis\n\n"
                "🛡️ Anonymize IPs - Advanced Anonymization\n"
                "   • Preserves network topology and subnet relationships\n"
                "   • Uses hierarchical anonymization for consistent mapping\n"
                "   • Perfect for data sharing, compliance, and research\n\n"
                "✂️ Mask Payloads - Intelligent Data Reduction\n"
                "   • Removes sensitive payload data while preserving headers\n"
                "   • Keeps TLS handshakes intact for protocol analysis\n"
                "   • Reduces file size without losing network behavior insights\n\n"
                "🌐 Web-Focused Traffic Only (Coming Soon)\n"
                "   • HTTP protocol processing functionality will be provided in future versions\n"
                "   • Only supports TLS, IP anonymization, and de-duplication functionality\n"
                "   • It's recommended to use a generic processing mode\n\n"
                "🎯 Use Cases: Security research, network troubleshooting,\n"
                "   compliance reporting, and safe data sharing."
            )

        self.main_window.summary_text.setPlaceholderText(formatted_content)

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
        """Detect whether current system is light or dark mode"""
        bg_color = self.main_window.palette().color(self.main_window.backgroundRole())
        return "dark" if bg_color.lightness() < 128 else "light"

    def apply_stylesheet(self):
        """Apply stylesheet"""
        theme = self.get_current_theme()
        self.main_window.setStyleSheet(generate_stylesheet(theme))

    def handle_theme_change(self, event: QEvent):
        """Handle theme changes"""
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
        self.main_window.setStyleSheet(self.main_window.styleSheet() + style)

    def _get_start_button_style(self) -> str:
        """Get start button style"""
        theme = self.get_current_theme()
        if self.main_window.start_proc_btn.isEnabled():
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
        self.main_window.start_proc_btn.setStyleSheet(style)

    def _update_start_button_state(self):
        """Update Start button based on input directory and option states"""
        has_input_dir = self.main_window.base_dir is not None
        has_any_action = (
            self.main_window.anonymize_ips_cb.isChecked()
            or self.main_window.remove_dupes_cb.isChecked()
            or self.main_window.mask_payloads_cb.isChecked()
        )

        # 检查是否正在处理中 - Store thread reference to avoid race condition
        processing_thread = getattr(
            self.main_window.pipeline_manager, "processing_thread", None
        )
        is_processing = processing_thread is not None and processing_thread.isRunning()

        # 只有当有输入目录且至少选择一个操作时才启用按钮，或者正在处理中时保持启用
        should_enable = (has_input_dir and has_any_action) or is_processing

        self.main_window.start_proc_btn.setEnabled(should_enable)

        # 同时更新按钮样式
        self._update_start_button_style()
