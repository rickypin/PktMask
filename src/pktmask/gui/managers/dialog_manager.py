#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
对话框管理器 - 负责各种对话框的显示
"""

import os
from typing import TYPE_CHECKING

import markdown
from PyQt6.QtCore import Qt, QTime
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

if TYPE_CHECKING:
    from ..main_window import MainWindow

from pktmask.infrastructure.logging import get_logger
from pktmask.utils.path import resource_path


class DialogManager:
    """对话框管理器 - 负责各种对话框的显示"""

    def __init__(self, main_window: "MainWindow"):
        self.main_window = main_window
        self.config = main_window.config
        self._logger = get_logger(__name__)

    def show_user_guide_dialog(self):
        """Show user guide dialog"""
        try:
            with open(resource_path("summary.md"), "r", encoding="utf-8") as f:
                content = f.read()

            dialog = QDialog(self.main_window)
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
            QMessageBox.critical(
                self.main_window, "Error", f"Could not load User Guide: {str(e)}"
            )

    def show_about_dialog(self):
        """Show about dialog"""
        try:
            about_text = """
            <h2>PktMask</h2>
            <p><b>Network Packet Processing Tool</b></p>
            <p>Version: 1.0.0</p>
            
            <p>PktMask is a powerful network packet processing tool designed for:</p>
            <ul>
                <li>🔄 <b>Remove Duplicates</b> - Eliminate duplicate packets</li>
                <li>🛡️ <b>IP Anonymization</b> - Advanced hierarchical IP masking</li>
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

            dialog = QDialog(self.main_window)
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
            QMessageBox.critical(
                self.main_window, "Error", f"Could not show About dialog: {str(e)}"
            )

    def show_error_dialog(self, title: str, message: str):
        """Show error dialog"""
        try:
            QMessageBox.critical(self.main_window, title, message)
            self._logger.error(f"Error dialog displayed: {title} - {message}")
        except Exception as e:
            self._logger.error(f"Failed to show error dialog: {e}")

    def show_warning_dialog(self, title: str, message: str):
        """Show warning dialog"""
        try:
            QMessageBox.warning(self.main_window, title, message)
            self._logger.warning(f"Warning dialog displayed: {title} - {message}")
        except Exception as e:
            self._logger.error(f"Failed to show warning dialog: {e}")

    def show_info_dialog(self, title: str, message: str):
        """Show info dialog"""
        try:
            QMessageBox.information(self.main_window, title, message)
            self._logger.info(f"Info dialog displayed: {title} - {message}")
        except Exception as e:
            self._logger.error(f"Failed to show info dialog: {e}")

    def show_question_dialog(self, title: str, message: str) -> bool:
        """Show confirmation dialog"""
        try:
            reply = QMessageBox.question(
                self.main_window,
                title,
                message,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            result = reply == QMessageBox.StandardButton.Yes
            self._logger.info(
                f"Question dialog displayed: {title} - User choice: {'Yes' if result else 'No'}"
            )
            return result

        except Exception as e:
            self._logger.error(f"Failed to show question dialog: {e}")
            return False

    def show_progress_dialog(
        self, title: str, message: str, maximum: int = 0
    ) -> QProgressDialog:
        """Show progress dialog"""
        try:
            progress = QProgressDialog(message, "Cancel", 0, maximum, self.main_window)
            progress.setWindowTitle(title)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(1000)  # Show after 1 second

            self._logger.info(f"Created progress dialog: {title}")
            return progress

        except Exception as e:
            self._logger.error(f"Failed to create progress dialog: {e}")
            return None

    def show_file_save_dialog(
        self, title: str, default_name: str = "", file_filter: str = "All Files (*)"
    ) -> str:
        """Show file save dialog"""
        try:
            filepath, _ = QFileDialog.getSaveFileName(
                self.main_window, title, default_name, file_filter
            )

            if filepath:
                self._logger.info(f"User selected save file: {filepath}")
            else:
                self._logger.debug("User cancelled file save")

            return filepath

        except Exception as e:
            self._logger.error(f"Failed to show file save dialog: {e}")
            return ""

    def show_file_open_dialog(
        self, title: str, file_filter: str = "All Files (*)"
    ) -> str:
        """Show file open dialog"""
        try:
            filepath, _ = QFileDialog.getOpenFileName(
                self.main_window, title, "", file_filter
            )

            if filepath:
                self._logger.info(f"User selected open file: {filepath}")
            else:
                self._logger.debug("User cancelled file open")

            return filepath

        except Exception as e:
            self._logger.error(f"Failed to show file open dialog: {e}")
            return ""

    def show_directory_dialog(self, title: str, default_path: str = "") -> str:
        """Show directory selection dialog"""
        try:
            directory = QFileDialog.getExistingDirectory(
                self.main_window, title, default_path
            )

            if directory:
                self._logger.info(f"User selected directory: {directory}")
            else:
                self._logger.debug("User cancelled directory selection")

            return directory

        except Exception as e:
            self._logger.error(f"Failed to show directory selection dialog: {e}")
            return ""

    def show_input_dialog(
        self, title: str, label: str, default_text: str = ""
    ) -> tuple[str, bool]:
        """Show input dialog"""
        try:
            text, ok = QInputDialog.getText(
                self.main_window, title, label, text=default_text
            )

            if ok:
                self._logger.info(f"User input: {title} - {text}")
            else:
                self._logger.debug("User cancelled input")

            return text, ok

        except Exception as e:
            self._logger.error(f"Failed to show input dialog: {e}")
            return "", False

    def show_custom_dialog(
        self, title: str, content: str, width: int = 400, height: int = 300
    ) -> QDialog:
        """Show custom content dialog"""
        try:
            dialog = QDialog(self.main_window)
            dialog.setWindowTitle(title)
            dialog.setFixedSize(width, height)

            layout = QVBoxLayout(dialog)

            # Content area
            text_widget = QTextEdit()
            text_widget.setReadOnly(True)
            text_widget.setPlainText(content)
            layout.addWidget(text_widget)

            # Button area
            button_layout = QHBoxLayout()
            button_layout.addStretch()

            ok_button = QPushButton("OK")
            ok_button.clicked.connect(dialog.accept)
            button_layout.addWidget(ok_button)

            layout.addLayout(button_layout)

            self._logger.info(f"Created custom dialog: {title}")
            return dialog

        except Exception as e:
            self._logger.error(f"Failed to create custom dialog: {e}")
            return None

    def show_processing_error(self, error_message: str):
        """Show processing error dialog"""
        try:
            # If error message is empty or just "Unknown error", use a more friendly message
            if not error_message or error_message.strip() == "Unknown error":
                error_message = "An unexpected error occurred during processing. Please check the logs for more details."

            # Check if in automated test environment
            is_automated_test = (
                os.environ.get("QT_QPA_PLATFORM") == "offscreen"  # Headless mode
                or os.environ.get("PYTEST_CURRENT_TEST")
                is not None  # pytest environment
                or os.environ.get("CI") == "true"  # CI environment
                or hasattr(self.main_window, "_test_mode")  # Test mode flag
            )

            if is_automated_test:
                # In automated test environment, only log error without showing blocking dialog
                self._logger.error(
                    f"Processing error (automated test mode): {error_message}"
                )
                # Update main window log for test verification
                self.main_window.update_log(f"Error: {error_message}")
                # Optional: send a non-blocking notification
                self._send_non_blocking_error_notification(error_message)
                return

            # Show modal dialog in normal GUI environment
            error_dialog = QMessageBox(self.main_window)
            error_dialog.setIcon(QMessageBox.Icon.Critical)
            error_dialog.setWindowTitle("Processing Error")
            error_dialog.setText("An error occurred during processing:")
            error_dialog.setInformativeText(error_message)

            # 添加详细信息按钮
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
            self.main_window.update_log(f"Error: {error_message}")

    def _send_non_blocking_error_notification(self, error_message: str):
        """Send non-blocking error notification (for automated testing)"""
        try:
            # Can send status bar message, log update or other non-blocking notifications
            if hasattr(self.main_window, "statusBar"):
                self.main_window.statusBar().showMessage(
                    f"Error: {error_message}", 5000
                )

            # Emit error signal for test listening
            if hasattr(self.main_window, "error_occurred"):
                self.main_window.error_occurred.emit(error_message)

        except Exception as e:
            self._logger.debug(f"Failed to send non-blocking notification: {e}")

    def show_processing_complete(self, summary: str):
        """Show processing complete dialog"""
        try:
            success_dialog = QMessageBox(self.main_window)
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
