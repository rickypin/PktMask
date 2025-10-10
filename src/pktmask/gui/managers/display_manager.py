#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Display Manager - Responsible for log and dashboard display updates

This module handles all UI display updates including:
- Log text area updates
- Dashboard statistics display
- Progress bar updates
- Summary text area updates
- Display clearing operations

Extracted from ReportManager to separate display concerns from report generation logic.
"""

from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..main_window import MainWindow

from pktmask.infrastructure.logging import get_logger


class DisplayManager:
    """Display Manager - Handles log and dashboard display updates"""

    def __init__(self, main_window: "MainWindow"):
        self.main_window = main_window
        self._logger = get_logger(__name__)

    # ========================================================================
    # LOG DISPLAY
    # ========================================================================

    def update_log(self, message: str):
        """Update log display"""
        try:
            timestamp = datetime.now().strftime("%H:%M:%S")
            formatted_message = f"[{timestamp}] {message}"

            # Add to log text area
            self.main_window.log_text.append(formatted_message)

            # Auto-scroll to bottom
            self._scroll_to_bottom(self.main_window.log_text)

            self._logger.debug(f"UI log updated: {message}")

        except Exception as e:
            self._logger.error(f"Error occurred while updating log display: {e}")

    def clear_log(self):
        """Clear log display"""
        try:
            self.main_window.log_text.clear()
            self._logger.debug("Log display cleared")
        except Exception as e:
            self._logger.error(f"Error occurred while clearing log display: {e}")

    # ========================================================================
    # SUMMARY DISPLAY
    # ========================================================================

    def append_summary(self, text: str):
        """Append text to summary display"""
        try:
            self.main_window.summary_text.append(text)
            self._scroll_to_bottom(self.main_window.summary_text)
            self._logger.debug("Summary text appended")
        except Exception as e:
            self._logger.error(f"Error occurred while appending summary text: {e}")

    def clear_summary(self):
        """Clear summary display"""
        try:
            self.main_window.summary_text.clear()
            self._logger.debug("Summary display cleared")
        except Exception as e:
            self._logger.error(f"Error occurred while clearing summary display: {e}")

    def set_summary_text(self, text: str):
        """Set summary display text (replaces existing content)"""
        try:
            self.main_window.summary_text.setPlainText(text)
            self._scroll_to_bottom(self.main_window.summary_text)
            self._logger.debug("Summary text set")
        except Exception as e:
            self._logger.error(f"Error occurred while setting summary text: {e}")

    # ========================================================================
    # DASHBOARD DISPLAY
    # ========================================================================

    def update_dashboard(self, stats: dict):
        """Update dashboard display with statistics

        Args:
            stats: Dictionary containing:
                - files_processed: int
                - packets_processed: int
                - elapsed_time: str (formatted as HH:MM:SS.ms)
        """
        try:
            if "files_processed" in stats:
                self.main_window.files_processed_label.setText(str(stats["files_processed"]))

            if "packets_processed" in stats:
                self.main_window.packets_processed_label.setText(f"{stats['packets_processed']:,}")

            if "elapsed_time" in stats:
                self.main_window.time_elapsed_label.setText(stats["elapsed_time"])

            self._logger.debug(f"Dashboard updated: {stats}")

        except Exception as e:
            self._logger.error(f"Error occurred while updating dashboard: {e}")

    def update_progress(self, value: int):
        """Update progress bar

        Args:
            value: Progress value (0-100)
        """
        try:
            self.main_window.progress_bar.setValue(value)
            self._logger.debug(f"Progress bar updated: {value}%")
        except Exception as e:
            self._logger.error(f"Error occurred while updating progress bar: {e}")

    def reset_progress(self):
        """Reset progress bar to 0"""
        try:
            self.main_window.progress_bar.setValue(0)
            self._logger.debug("Progress bar reset")
        except Exception as e:
            self._logger.error(f"Error occurred while resetting progress bar: {e}")

    # ========================================================================
    # CLEAR ALL DISPLAYS
    # ========================================================================

    def clear_displays(self):
        """Clear all display areas (log and summary)"""
        try:
            self.clear_log()
            self.clear_summary()
            self._logger.info("All displays cleared")
        except Exception as e:
            self._logger.error(f"Error occurred while clearing displays: {e}")

    def clear_all(self):
        """Clear all displays including progress bar"""
        try:
            self.clear_displays()
            self.reset_progress()
            self._logger.info("All displays and progress cleared")
        except Exception as e:
            self._logger.error(f"Error occurred while clearing all: {e}")

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def _scroll_to_bottom(self, text_widget):
        """Scroll text widget to bottom"""
        try:
            cursor = text_widget.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            text_widget.setTextCursor(cursor)
        except Exception as e:
            self._logger.error(f"Error occurred while scrolling to bottom: {e}")

    # ========================================================================
    # LEGACY COMPATIBILITY
    # ========================================================================

    # These methods maintain backward compatibility with ReportManager interface
    def update_log_display(self, message: str):
        """Legacy method - redirects to update_log"""
        return self.update_log(message)

    def append_summary_text(self, text: str):
        """Legacy method - redirects to append_summary"""
        return self.append_summary(text)
