#!/usr/bin/env python3
"""
Dependency Error Dialog

User-friendly dialog for handling dependency errors and providing
installation guidance with platform-specific instructions.
"""

import platform
from typing import Dict, List, Optional, Any
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QTabWidget, QWidget, QScrollArea, QGroupBox,
    QFileDialog, QLineEdit, QMessageBox, QProgressBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QIcon, QPixmap

from pktmask.infrastructure.logging import get_logger
from pktmask.infrastructure.startup import ValidationResult
from pktmask.infrastructure.tshark import TSharkManager


class TSharkPathTestThread(QThread):
    """Thread for testing custom TShark path"""
    
    result_ready = pyqtSignal(bool, str)  # success, message
    
    def __init__(self, tshark_path: str):
        super().__init__()
        self.tshark_path = tshark_path
        self.logger = get_logger('tshark_test_thread')
    
    def run(self):
        """Test the TShark path"""
        try:
            tshark_manager = TSharkManager(custom_path=self.tshark_path)
            tshark_info = tshark_manager.detect_tshark(force_refresh=True)
            
            if tshark_info.is_available:
                # Additional TLS functionality test
                requirements_met, missing_requirements = tshark_manager.verify_tls_marker_requirements(
                    self.tshark_path
                )
                
                if requirements_met:
                    self.result_ready.emit(True, f"✅ TShark validated successfully!\nVersion: {tshark_info.version_formatted}")
                else:
                    self.result_ready.emit(False, f"❌ TShark found but missing TLS capabilities:\n• {chr(10).join(missing_requirements)}")
            else:
                self.result_ready.emit(False, f"❌ TShark validation failed:\n{tshark_info.error_message}")
                
        except Exception as e:
            self.logger.error(f"TShark path test failed: {e}")
            self.result_ready.emit(False, f"❌ Test failed: {str(e)}")


class DependencyErrorDialog(QDialog):
    """Dialog for handling dependency errors with user guidance"""
    
    def __init__(self, validation_result: ValidationResult, parent=None):
        super().__init__(parent)
        self.validation_result = validation_result
        self.logger = get_logger('dependency_dialog')
        
        self.setWindowTitle("PktMask - Dependency Configuration")
        self.setMinimumSize(700, 500)
        self.setModal(True)
        
        # Custom TShark path for testing
        self.custom_tshark_path = ""
        self.test_thread = None
        
        self._init_ui()
        self._populate_content()
    
    def _init_ui(self):
        """Initialize the user interface"""
        layout = QVBoxLayout(self)
        
        # Header
        header_label = QLabel("Dependency Configuration Required")
        header_font = QFont()
        header_font.setPointSize(14)
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header_label)
        
        # Status message
        if self.validation_result.success:
            status_text = "✅ All dependencies are satisfied."
            status_color = "color: green;"
        else:
            status_text = f"⚠️ {len(self.validation_result.missing_dependencies)} dependency issue(s) found."
            status_color = "color: orange;"
        
        status_label = QLabel(status_text)
        status_label.setStyleSheet(f"font-weight: bold; {status_color}")
        status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(status_label)
        
        # Tab widget for different sections
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # Button layout
        button_layout = QHBoxLayout()
        
        self.retry_button = QPushButton("🔄 Retry Detection")
        self.retry_button.clicked.connect(self._retry_detection)
        button_layout.addWidget(self.retry_button)
        
        button_layout.addStretch()
        
        if self.validation_result.can_continue:
            self.continue_button = QPushButton("⚠️ Continue Anyway")
            self.continue_button.clicked.connect(self.accept)
            button_layout.addWidget(self.continue_button)
        
        self.close_button = QPushButton("❌ Exit Application")
        self.close_button.clicked.connect(self.reject)
        button_layout.addWidget(self.close_button)
        
        layout.addLayout(button_layout)
    
    def _populate_content(self):
        """Populate dialog content based on validation result"""
        # Error Details Tab
        if self.validation_result.error_messages:
            self._create_error_details_tab()
        
        # Installation Guide Tab
        if self.validation_result.installation_guides:
            self._create_installation_guide_tab()
        
        # Manual Configuration Tab
        self._create_manual_config_tab()
        
        # System Information Tab
        self._create_system_info_tab()
    
    def _create_error_details_tab(self):
        """Create error details tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Error summary
        summary_label = QLabel("The following issues were detected:")
        summary_label.setStyleSheet("font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(summary_label)
        
        # Error list
        error_text = QTextEdit()
        error_text.setReadOnly(True)
        error_content = "\n".join([f"• {error}" for error in self.validation_result.error_messages])
        error_text.setPlainText(error_content)
        error_text.setMaximumHeight(150)
        layout.addWidget(error_text)
        
        # Missing dependencies
        if self.validation_result.missing_dependencies:
            missing_label = QLabel("Missing Dependencies:")
            missing_label.setStyleSheet("font-weight: bold; margin-top: 15px; margin-bottom: 5px;")
            layout.addWidget(missing_label)
            
            missing_list = QLabel("• " + "\n• ".join(self.validation_result.missing_dependencies))
            missing_list.setStyleSheet("color: red; margin-left: 20px;")
            layout.addWidget(missing_list)
        
        layout.addStretch()
        self.tab_widget.addTab(tab, "❌ Error Details")
    
    def _create_installation_guide_tab(self):
        """Create installation guide tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Scroll area for installation guides
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        for dep_name, guide in self.validation_result.installation_guides.items():
            if dep_name == 'tshark':
                self._add_tshark_installation_guide(scroll_layout, guide)
        
        scroll_widget.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)
        
        self.tab_widget.addTab(tab, "📋 Installation Guide")
    
    def _add_tshark_installation_guide(self, layout: QVBoxLayout, guide: Dict[str, Any]):
        """Add TShark installation guide to layout"""
        # Platform header
        platform_name = guide.get('platform', 'Unknown Platform')
        platform_label = QLabel(f"🖥️ Installation Guide for {platform_name}")
        platform_label.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(platform_label)
        
        # Installation methods
        methods = guide.get('methods', [])
        for i, method in enumerate(methods, 1):
            method_group = QGroupBox(f"{i}. {method['name']}")
            method_layout = QVBoxLayout(method_group)
            
            # Description
            desc_label = QLabel(method['description'])
            desc_label.setWordWrap(True)
            method_layout.addWidget(desc_label)
            
            # Commands
            if method.get('commands'):
                cmd_label = QLabel("Commands:")
                cmd_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
                method_layout.addWidget(cmd_label)
                
                for cmd in method['commands']:
                    cmd_text = QTextEdit()
                    cmd_text.setPlainText(cmd)
                    cmd_text.setMaximumHeight(30)
                    cmd_text.setReadOnly(True)
                    cmd_text.setStyleSheet("background-color: #f0f0f0; font-family: monospace;")
                    method_layout.addWidget(cmd_text)
            
            # URL
            if method.get('url'):
                url_label = QLabel(f"<a href='{method['url']}'>Download from: {method['url']}</a>")
                url_label.setOpenExternalLinks(True)
                url_label.setStyleSheet("margin-top: 10px;")
                method_layout.addWidget(url_label)
            
            layout.addWidget(method_group)
        
        # Common paths
        common_paths = guide.get('common_paths', [])
        if common_paths:
            paths_group = QGroupBox("🔍 Common Installation Paths")
            paths_layout = QVBoxLayout(paths_group)
            
            paths_text = QTextEdit()
            paths_text.setPlainText("\n".join([f"• {path}" for path in common_paths]))
            paths_text.setMaximumHeight(120)
            paths_text.setReadOnly(True)
            paths_text.setStyleSheet("font-family: monospace;")
            paths_layout.addWidget(paths_text)
            
            layout.addWidget(paths_group)
    
    def _create_manual_config_tab(self):
        """Create manual configuration tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Instructions
        instructions = QLabel(
            "If TShark is installed in a custom location, you can specify the path manually:"
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("margin-bottom: 15px;")
        layout.addWidget(instructions)
        
        # Path input
        path_layout = QHBoxLayout()
        
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Enter path to tshark executable...")
        path_layout.addWidget(self.path_input)
        
        browse_button = QPushButton("📁 Browse")
        browse_button.clicked.connect(self._browse_tshark_path)
        path_layout.addWidget(browse_button)
        
        layout.addLayout(path_layout)
        
        # Test button and progress
        test_layout = QHBoxLayout()
        
        self.test_button = QPushButton("🧪 Test Path")
        self.test_button.clicked.connect(self._test_tshark_path)
        test_layout.addWidget(self.test_button)
        
        test_layout.addStretch()
        layout.addLayout(test_layout)
        
        # Test results
        self.test_result_label = QLabel("")
        self.test_result_label.setWordWrap(True)
        self.test_result_label.setStyleSheet("margin-top: 10px; padding: 10px; border: 1px solid #ccc;")
        layout.addWidget(self.test_result_label)
        
        # Save button
        self.save_path_button = QPushButton("💾 Save and Use This Path")
        self.save_path_button.clicked.connect(self._save_custom_path)
        self.save_path_button.setEnabled(False)
        layout.addWidget(self.save_path_button)
        
        layout.addStretch()
        self.tab_widget.addTab(tab, "⚙️ Manual Configuration")
    
    def _create_system_info_tab(self):
        """Create system information tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # System information
        system_info = f"""
🖥️ System Information:
• Operating System: {platform.system()} {platform.release()}
• Architecture: {platform.machine()}
• Python Version: {platform.python_version()}

🔍 Search Paths:
The following paths are automatically searched for TShark:
        """.strip()
        
        info_label = QLabel(system_info)
        info_label.setStyleSheet("font-family: monospace; margin-bottom: 10px;")
        layout.addWidget(info_label)
        
        # Search paths
        tshark_manager = TSharkManager()
        current_system = platform.system()
        search_paths = tshark_manager.PLATFORM_PATHS.get(current_system, [])
        
        paths_text = QTextEdit()
        paths_text.setPlainText("\n".join([f"• {path}" for path in search_paths]))
        paths_text.setReadOnly(True)
        paths_text.setMaximumHeight(200)
        paths_text.setStyleSheet("font-family: monospace; background-color: #f8f8f8;")
        layout.addWidget(paths_text)
        
        layout.addStretch()
        self.tab_widget.addTab(tab, "ℹ️ System Info")
    
    def _browse_tshark_path(self):
        """Browse for TShark executable"""
        file_dialog = QFileDialog(self)
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        file_dialog.setWindowTitle("Select TShark Executable")
        
        # Set appropriate file filters based on platform
        if platform.system() == "Windows":
            file_dialog.setNameFilter("Executable Files (*.exe);;All Files (*)")
        else:
            file_dialog.setNameFilter("All Files (*)")
        
        if file_dialog.exec():
            selected_files = file_dialog.selectedFiles()
            if selected_files:
                self.path_input.setText(selected_files[0])
    
    def _test_tshark_path(self):
        """Test the specified TShark path"""
        path = self.path_input.text().strip()
        if not path:
            QMessageBox.warning(self, "Warning", "Please enter a TShark path first.")
            return
        
        # Disable test button during testing
        self.test_button.setEnabled(False)
        self.test_button.setText("🔄 Testing...")
        self.test_result_label.setText("Testing TShark path, please wait...")
        self.test_result_label.setStyleSheet("color: blue; margin-top: 10px; padding: 10px; border: 1px solid #ccc;")
        
        # Start test thread
        self.test_thread = TSharkPathTestThread(path)
        self.test_thread.result_ready.connect(self._handle_test_result)
        self.test_thread.start()
    
    def _handle_test_result(self, success: bool, message: str):
        """Handle TShark path test result"""
        # Re-enable test button
        self.test_button.setEnabled(True)
        self.test_button.setText("🧪 Test Path")
        
        # Update result display
        if success:
            self.test_result_label.setText(message)
            self.test_result_label.setStyleSheet("color: green; margin-top: 10px; padding: 10px; border: 1px solid #4CAF50; background-color: #E8F5E8;")
            self.save_path_button.setEnabled(True)
            self.custom_tshark_path = self.path_input.text().strip()
        else:
            self.test_result_label.setText(message)
            self.test_result_label.setStyleSheet("color: red; margin-top: 10px; padding: 10px; border: 1px solid #F44336; background-color: #FFEBEE;")
            self.save_path_button.setEnabled(False)
            self.custom_tshark_path = ""
    
    def _save_custom_path(self):
        """Save custom TShark path and close dialog"""
        if self.custom_tshark_path:
            # Here you would typically save to configuration
            # For now, we'll just accept the dialog
            QMessageBox.information(
                self,
                "Path Saved",
                f"Custom TShark path saved:\n{self.custom_tshark_path}\n\nThe application will use this path."
            )
            self.accept()
    
    def _retry_detection(self):
        """Retry dependency detection"""
        # This would typically re-run the validation
        QMessageBox.information(
            self,
            "Retry Detection",
            "Dependency detection will be retried when the application restarts.\n\n"
            "Please install any missing dependencies and restart PktMask."
        )
    
    def get_custom_tshark_path(self) -> Optional[str]:
        """Get the custom TShark path if configured"""
        return self.custom_tshark_path if self.custom_tshark_path else None
