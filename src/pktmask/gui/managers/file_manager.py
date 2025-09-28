#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
File manager - handles directory selection and file operations
"""

import os
from typing import TYPE_CHECKING, Optional

from PyQt6.QtWidgets import QFileDialog, QMessageBox

if TYPE_CHECKING:
    from ..main_window import MainWindow

from pktmask.infrastructure.logging import get_logger
from pktmask.utils.file_ops import open_directory_in_system
from pktmask.utils.time import current_timestamp


class FileManager:
    """File manager - handles directory selection and file operations"""

    def __init__(self, main_window: "MainWindow"):
        self.main_window = main_window
        self.config = main_window.config
        self._logger = get_logger(__name__)

    def choose_folder(self):
        """Select input directory"""
        dir_path = QFileDialog.getExistingDirectory(
            self.main_window, "Select Input Folder", self.main_window.last_opened_dir
        )
        if dir_path:
            self.main_window.base_dir = dir_path
            self.main_window.last_opened_dir = dir_path  # Record currently selected directory
            self.main_window.dir_path_label.setText(os.path.basename(dir_path))

            # Auto-generate default output path
            self.generate_default_output_path()
            self.main_window.ui_manager._update_start_button_state()  # Intelligently update button state

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
