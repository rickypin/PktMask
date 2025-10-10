#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Dialogs Manager - Unified dialog and file selection management

This module combines dialog display and file/directory selection functionality,
providing a unified interface for all user interactions requiring dialogs.

Responsibilities:
- Complex dialogs (User Guide, About, Processing Error/Complete)
- Simple dialogs (Error, Warning, Info, Question)
- File/Directory selection dialogs
- Output directory management
- Path generation and validation
"""

import os
from typing import TYPE_CHECKING, Optional

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
from pktmask.utils.file_ops import open_directory_in_system
from pktmask.utils.path import resource_path
from pktmask.utils.time import current_timestamp


class DialogsManager:
    """Unified dialogs and file selection manager

    Combines functionality from DialogManager and FileManager to provide
    a single interface for all dialog-related operations.
    """

    def __init__(self, main_window: "MainWindow"):
        self.main_window = main_window
        self.config = main_window.config
        self._logger = get_logger(__name__)

    # ========================================================================
    # COMPLEX DIALOGS (from DialogManager)
    # ========================================================================

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
            QMessageBox.critical(self.main_window, "Error", f"Could not load User Guide: {str(e)}")

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
            QMessageBox.critical(self.main_window, "Error", f"Could not show About dialog: {str(e)}")

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
                or hasattr(self.main_window, "_test_mode")  # Test mode flag
            )

            if is_automated_test:
                # In automated test environment, only log error without showing blocking dialog
                self._logger.error(f"Processing error (automated test mode): {error_message}")
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
            self.main_window.update_log(f"Error: {error_message}")

    def _send_non_blocking_error_notification(self, error_message: str):
        """Send non-blocking error notification (for automated testing)"""
        try:
            # Can send status bar message, log update or other non-blocking notifications
            if hasattr(self.main_window, "statusBar"):
                self.main_window.statusBar().showMessage(f"Error: {error_message}", 5000)

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

    # ========================================================================
    # SIMPLE DIALOGS (from DialogManager - simplified)
    # ========================================================================

    def show_error(self, title: str, message: str):
        """Show error dialog (simplified wrapper)"""
        try:
            QMessageBox.critical(self.main_window, title, message)
            self._logger.error(f"Error dialog displayed: {title} - {message}")
        except Exception as e:
            self._logger.error(f"Failed to show error dialog: {e}")

    def show_warning(self, title: str, message: str):
        """Show warning dialog (simplified wrapper)"""
        try:
            QMessageBox.warning(self.main_window, title, message)
            self._logger.warning(f"Warning dialog displayed: {title} - {message}")
        except Exception as e:
            self._logger.error(f"Failed to show warning dialog: {e}")

    def show_info(self, title: str, message: str):
        """Show info dialog (simplified wrapper)"""
        try:
            QMessageBox.information(self.main_window, title, message)
            self._logger.info(f"Info dialog displayed: {title} - {message}")
        except Exception as e:
            self._logger.error(f"Failed to show info dialog: {e}")

    def ask_question(self, title: str, message: str) -> bool:
        """Show confirmation dialog (simplified wrapper)"""
        try:
            reply = QMessageBox.question(
                self.main_window,
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
            progress = QProgressDialog(message, "Cancel", 0, maximum, self.main_window)
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
        dir_path = QFileDialog.getExistingDirectory(
            self.main_window, "Select Input Folder", self.main_window.last_opened_dir
        )
        if dir_path:
            self.main_window.base_dir = dir_path
            self.main_window.last_opened_dir = dir_path  # Record currently selected directory
            self.main_window.dir_path_label.setText(os.path.basename(dir_path))

            # Auto-generate default output path
            self.generate_default_output_path()
            self.main_window._update_start_button_state()  # Intelligently update button state

            self._logger.info(f"Selected input directory: {dir_path}")

    def handle_output_click(self):
        """Handle output path button click - open directory if processing is complete, otherwise select custom output directory"""
        if self.main_window.current_output_dir and os.path.exists(self.main_window.current_output_dir):
            # If output directory exists, open it
            self.open_output_directory()
        else:
            # Otherwise let user select custom output directory
            self.choose_output_folder()

    def choose_output_folder(self):
        """Select custom output directory"""
        dir_path = QFileDialog.getExistingDirectory(
            self.main_window, "Select Output Folder", self.main_window.last_opened_dir
        )
        if dir_path:
            self.main_window.output_dir = dir_path
            self.main_window.output_path_label.setText(os.path.basename(dir_path))
            self._logger.info(f"Selected custom output directory: {dir_path}")

    def generate_default_output_path(self):
        """Generate default output path preview"""
        if not self.main_window.base_dir:
            return

        # Reset to default mode
        self.main_window.output_dir = None
        self.main_window.output_path_label.setText("Auto-create or click for custom")
        self._logger.debug("Reset to default output path mode")

    def generate_actual_output_path(self) -> str:
        """Generate actual output directory path"""
        timestamp = current_timestamp()

        # Get input directory name
        if self.main_window.base_dir:
            input_dir_name = os.path.basename(self.main_window.base_dir)
            # Generate new naming format: input_dir_name-Masked-timestamp
            output_name = f"{input_dir_name}-Masked-{timestamp}"
        else:
            # If no input directory, use default format
            output_name = f"PktMask-{timestamp}"

        if self.main_window.output_dir:
            # Custom output directory
            actual_path = os.path.join(self.main_window.output_dir, output_name)
        else:
            # Default output directory
            if self.config.ui.default_output_dir:
                actual_path = os.path.join(self.config.ui.default_output_dir, output_name)
            else:
                # Use subdirectory of input directory
                actual_path = os.path.join(self.main_window.base_dir, output_name)

        self._logger.info(f"Generated actual output path: {actual_path}")
        return actual_path

    def open_output_directory(self):
        """Open output directory"""
        if not self.main_window.current_output_dir or not os.path.exists(self.main_window.current_output_dir):
            QMessageBox.warning(self.main_window, "Warning", "Output directory not found.")
            return

        try:
            success = open_directory_in_system(self.main_window.current_output_dir)
            if success:
                self.main_window.update_log(
                    f"Opened output directory: {os.path.basename(self.main_window.current_output_dir)}"
                )
                self._logger.info(f"Opened output directory: {self.main_window.current_output_dir}")
            else:
                self._logger.error("Failed to open output directory")
                QMessageBox.critical(self.main_window, "Error", "Could not open output directory.")
        except Exception as e:
            self._logger.error(f"Error occurred while opening output directory: {e}")
            QMessageBox.critical(self.main_window, "Error", f"Error opening directory: {str(e)}")

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
        if not self.main_window.current_output_dir:
            self._logger.warning("Output directory path is empty, cannot save summary report")
            return False

        try:
            # Ensure output directory exists
            if not os.path.exists(self.main_window.current_output_dir):
                self._logger.info(f"Creating output directory: {self.main_window.current_output_dir}")
                os.makedirs(self.main_window.current_output_dir, exist_ok=True)

            filename = self.generate_summary_report_filename()
            filepath = os.path.join(self.main_window.current_output_dir, filename)

            # Get summary text
            summary_text = self.main_window.summary_text.toPlainText()

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(summary_text)

            self._logger.info(f"Summary report saved to: {filepath}")
            self.main_window.update_log(f"Summary report saved: {filename}")
            return True

        except Exception as e:
            self._logger.error(f"Failed to save summary report: {e}")
            self.main_window.update_log(f"Error saving summary report: {str(e)}")
            return False

    def generate_summary_report_filename(self) -> str:
        """Generate summary report filename"""
        timestamp = current_timestamp()

        # Generate processing options identifier
        enabled_steps = []
        if hasattr(self.main_window, "anonymize_ips_cb") and self.main_window.anonymize_ips_cb.isChecked():
            enabled_steps.append("MaskIP")
        if hasattr(self.main_window, "remove_dupes_cb") and self.main_window.remove_dupes_cb.isChecked():
            enabled_steps.append("Dedup")
        if hasattr(self.main_window, "mask_payloads_cb") and self.main_window.mask_payloads_cb.isChecked():
            enabled_steps.append("Trim")

        steps_suffix = "_".join(enabled_steps) if enabled_steps else "NoSteps"
        filename = f"summary_report_{steps_suffix}_{timestamp}.txt"

        return filename

    def find_existing_summary_reports(self) -> list[str]:
        """Find existing summary report files"""
        if not self.main_window.current_output_dir or not os.path.exists(self.main_window.current_output_dir):
            return []

        try:
            reports = []
            for file in os.listdir(self.main_window.current_output_dir):
                if file.startswith("summary_report_") and file.endswith(".txt"):
                    filepath = os.path.join(self.main_window.current_output_dir, file)
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
