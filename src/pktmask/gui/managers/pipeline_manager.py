#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Pipeline Manager - Responsible for processing flow control
"""

from typing import TYPE_CHECKING

from PyQt6.QtCore import QTimer

if TYPE_CHECKING:
    from ..main_window import MainWindow, ServicePipelineThread

from pktmask.core.events import PipelineEvents
from pktmask.infrastructure.logging import get_logger
from pktmask.services import (
    ConfigurationError,
    build_pipeline_config,
    create_pipeline_executor,
)

from .statistics_manager import StatisticsManager


class PipelineManager:
    """Pipeline Manager - Responsible for processing flow control"""

    def __init__(self, main_window: "MainWindow"):
        self.main_window = main_window
        self.config = main_window.config
        self._logger = get_logger(__name__)

        # Integrate statistics manager
        self.statistics = StatisticsManager()

        # Processing state
        self.processing_thread: "ServicePipelineThread" = None
        self.user_stopped = False

        # Retain timer setup
        self._setup_timer()

    # === Use statistics attribute directly, no additional accessors needed ===

    def _setup_timer(self):
        """Set up processing time tracking timer"""
        self.main_window.time_elapsed = 0
        self.main_window.timer = QTimer()
        self.main_window.timer.timeout.connect(self.main_window.update_time_elapsed)

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

        if not self.main_window.base_dir:
            self._logger.warning("No input directory selected")
            from PyQt6.QtWidgets import QMessageBox

            try:
                QMessageBox.warning(
                    self.main_window,
                    "Warning",
                    "Please choose an input folder to process.",
                )
                self._logger.debug("Warning dialog shown successfully")
            except Exception as e:
                self._logger.error(f"Failed to show warning dialog: {e}")
                # Fallback: update log text
                if hasattr(self.main_window, "update_log"):
                    self.main_window.update_log(
                        "⚠️ Please choose an input folder to process."
                    )
            return

        # Generate actual output directory path
        self.main_window.current_output_dir = (
            self.main_window.file_manager.generate_actual_output_path()
        )

        # Create output directory
        try:
            import os

            os.makedirs(self.main_window.current_output_dir, exist_ok=True)
            self.main_window.update_log(
                f"📁 Created output directory: {os.path.basename(self.main_window.current_output_dir)}"
            )

            # Update output path display
            self.main_window.output_path_label.setText(
                os.path.basename(self.main_window.current_output_dir)
            )
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.critical(
                self.main_window,
                "Error",
                f"Failed to create output directory: {str(e)}",
            )
            return

        # Reset UI and counters for new run
        self.main_window.log_text.clear()
        self.main_window.summary_text.clear()
        self.main_window.all_ip_reports.clear()
        self.main_window.files_processed_count = 0
        self.main_window.packets_processed_count = 0

        # Reset Live Dashboard display
        self.main_window.files_processed_label.setText("0")
        self.main_window.packets_processed_label.setText("0")
        self.main_window.subdirs_files_counted.clear()
        self.main_window.subdirs_packets_counted.clear()
        self.main_window.printed_summary_headers.clear()
        self.main_window.file_processing_results.clear()  # Clear file processing results
        self.main_window.current_processing_file = None  # Reset current processing file
        self.main_window.global_ip_mappings.clear()  # Clear global IP mappings
        self.main_window.processed_files_count = 0  # Reset file count
        self.main_window.user_stopped = False  # Reset stop flag

        # Disable controls through event coordinator
        if hasattr(self.main_window, "event_coordinator"):
            self.main_window.event_coordinator.request_ui_update(
                "enable_controls",
                controls=[
                    "dir_path_label",
                    "output_path_label",
                    "anonymize_ips_cb",
                    "remove_dupes_cb",
                    "mask_payloads_cb",
                ],
                enabled=False,
            )
        else:
            # Fallback: direct operation
            self.main_window.dir_path_label.setEnabled(False)
            self.main_window.output_path_label.setEnabled(False)
            for cb in [
                self.main_window.anonymize_ips_cb,
                self.main_window.remove_dupes_cb,
                self.main_window.mask_payloads_cb,
            ]:
                cb.setEnabled(False)

        # Create and configure new PipelineExecutor
        config = build_pipeline_config(
            anonymize_ips=self.main_window.anonymize_ips_cb.isChecked(),
            remove_dupes=self.main_window.remove_dupes_cb.isChecked(),
            mask_payloads=self.main_window.mask_payloads_cb.isChecked(),
        )
        if not config:
            self._logger.warning("No processing steps selected")
            return

        try:
            executor = create_pipeline_executor(config)
        except ConfigurationError as e:
            self._logger.error(f"Configuration error: {str(e)}")
            self.main_window.update_log(f"Configuration error: {str(e)}")
            return
        self._logger.info(f"Built PipelineExecutor containing {len(config)} Stages")

        # Start processing
        self.start_processing(executor)

    def stop_pipeline_processing(self):
        """Stop the processing pipeline and clean up resources"""
        self.main_window.user_stopped = True  # Set stop flag
        self.main_window.update_log("--- Stopping pipeline... ---")

        # Store thread reference to avoid race condition
        thread = self.processing_thread
        if thread:
            thread.stop()
            # Wait for thread to safely end, maximum wait 3 seconds
            if not thread.wait(3000):
                self.main_window.log_text.append(
                    "Warning: Pipeline did not stop gracefully, forcing termination."
                )
                thread.terminate()
                thread.wait()

        # Generate partial summary statistics when stopped
        self.main_window.report_manager.generate_partial_summary_on_stop()

        # Re-enable controls through event coordinator
        if hasattr(self.main_window, "event_coordinator"):
            self.main_window.event_coordinator.request_ui_update(
                "enable_controls",
                controls=[
                    "dir_path_label",
                    "output_path_label",
                    "anonymize_ips_cb",
                    "remove_dupes_cb",
                    "mask_payloads_cb",
                    "start_proc_btn",
                ],
                enabled=True,
            )
            self.main_window.event_coordinator.request_ui_update(
                "update_button_text", button="start_proc_btn", text="Start"
            )
        else:
            # Fallback: direct operation
            self.main_window.dir_path_label.setEnabled(True)
            self.main_window.output_path_label.setEnabled(True)
            for cb in [
                self.main_window.anonymize_ips_cb,
                self.main_window.remove_dupes_cb,
                self.main_window.mask_payloads_cb,
            ]:
                cb.setEnabled(True)
            self.main_window.start_proc_btn.setEnabled(True)
            self.main_window.start_proc_btn.setText("Start")

    def start_processing(self, executor):
        """Start processing thread with the given executor"""
        # Import ServicePipelineThread (avoid circular import)
        from ..main_window import ServicePipelineThread

        # Create processing thread
        self.processing_thread = ServicePipelineThread(
            executor, self.main_window.base_dir, self.main_window.current_output_dir
        )

        # Connect signals
        self.processing_thread.progress_signal.connect(self.handle_thread_progress)
        self.processing_thread.finished.connect(self.on_thread_finished)

        # Update UI state
        self.main_window.start_proc_btn.setText("Stop")
        self.main_window.start_proc_btn.setEnabled(True)
        self.main_window.ui_manager._update_start_button_style()

        # Reset statistics before starting new processing
        self.statistics.reset_all_statistics()

        # Also reset the main window's packet counting cache
        if hasattr(self.main_window, "_counted_files"):
            self.main_window._counted_files.clear()

        # Start timing (unified use of StatisticsManager)
        self.statistics.start_timing()
        self.main_window.time_elapsed = 0
        self.main_window.start_time = (
            self.statistics.start_time
        )  # Maintain compatibility
        self.main_window.timer.start(100)  # Update every 100ms

        # Start thread
        self.processing_thread.start()

        self._logger.info(
            f"Processing thread started, output directory: {self.main_window.current_output_dir}"
        )
        self.main_window.update_log("🚀 Processing started...")

    def handle_thread_progress(self, event_type: PipelineEvents, data: dict):
        """Handle thread progress events"""
        try:
            # First let MainWindow handle events to update UI statistics and collect data
            self.main_window.handle_thread_progress(event_type, data)

            # Then PipelineManager handles its own logic
            # Handle pipeline start events
            if event_type in (
                PipelineEvents.PIPELINE_START,
                PipelineEvents.PIPELINE_STARTED,
            ):
                # Pipeline sends total directory count, but we need to track file count
                data.get("total_subdirs", data.get("total_files", 0))
                # Reset file counter (through StatisticsManager)
                self.statistics.update_file_count(0)

            # Handle subdirectory start events
            elif event_type == PipelineEvents.SUBDIR_START:
                data.get("name", "Unknown directory")
                file_count = data.get("file_count", 0)
                self.statistics.set_total_files(
                    file_count
                )  # Set actual total file count

            # Handle file completion events
            elif event_type in (PipelineEvents.FILE_END, PipelineEvents.FILE_COMPLETED):
                self.statistics.increment_file_count()
                # Update Live Dashboard display
                self.main_window.files_processed_label.setText(
                    str(self.statistics.files_processed)
                )
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
            self.main_window.processing_error(f"Event processing error: {str(e)}")

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

        # Delegate to StatisticsManager
        self.statistics.collect_step_result(step_name, filename, result_data)

        # Note: Real-time statistics are handled by MainWindow

    def get_processing_stats(self) -> dict:
        """Get processing statistics"""
        return self.statistics.get_processing_summary()

    def _update_progress(self):
        """Update progress bar"""
        if self.statistics.total_files_to_process > 0:
            progress = int(
                (
                    self.statistics.files_processed
                    / self.statistics.total_files_to_process
                )
                * 100
            )
            # Ensure progress doesn't exceed 100%
            progress = min(progress, 100)
            self.main_window._animate_progress_to(progress)
            self._logger.debug(
                f"Progress updated: {self.statistics.files_processed}/{self.statistics.total_files_to_process} = {progress}%"
            )
        else:
            # If no files to process, keep progress at 0
            self.main_window._animate_progress_to(0)

    def processing_finished(self):
        """Processing complete"""
        # 首先清理线程状态，确保UI状态检查正确
        # Note: Thread cleanup is also handled in on_thread_finished to ensure cleanup
        if self.processing_thread:
            self.processing_thread = None

        # **Fix**: Before generating the report, ensure Live Dashboard displays final statistics
        # Update Live Dashboard to show final statistics
        final_files_processed = self.statistics.files_processed
        final_packets_processed = self.statistics.packets_processed

        # Ensure Live Dashboard displays the correct final data
        self.main_window.files_processed_label.setText(str(final_files_processed))
        self.main_window.packets_processed_label.setText(str(final_packets_processed))

        # Delegate to ReportManager to generate report
        self.main_window.report_manager.generate_processing_finished_report()

        import os

        from pktmask.utils.file_ops import open_directory_in_system

        # Update output path display
        if self.main_window.current_output_dir:
            self.main_window.output_path_label.setText(
                os.path.basename(self.main_window.current_output_dir)
            )
        self.main_window.update_log(
            "Output directory ready. Click output path to view results."
        )

        # If configuration is enabled, automatically open output directory
        if (
            self.main_window.config.ui.auto_open_output
            and self.main_window.current_output_dir
        ):
            try:
                success = open_directory_in_system(self.main_window.current_output_dir)
                if success:
                    self.main_window.update_log(
                        f"Auto-opened output directory: {os.path.basename(self.main_window.current_output_dir)}"
                    )
                else:
                    self._logger.warning("Failed to auto-open output directory")
            except Exception as e:
                self._logger.error(f"Error auto-opening output directory: {e}")

        # Use QTimer.singleShot to ensure UI updates are executed in the next cycle of the event loop
        from PyQt6.QtCore import QTimer

        def update_ui_state():
            """Delayed UI state update"""
            # Directly set button state
            self.main_window.start_proc_btn.setText("Start")
            self.main_window.start_proc_btn.setEnabled(True)

            # Enable other controls
            self.main_window.dir_path_label.setEnabled(True)
            self.main_window.output_path_label.setEnabled(True)
            for cb in [
                self.main_window.anonymize_ips_cb,
                self.main_window.remove_dupes_cb,
                self.main_window.mask_payloads_cb,
            ]:
                cb.setEnabled(True)

            # Update button style
            self.main_window.ui_manager._update_start_button_style()

        def ensure_final_stats_display():
            """Ensure final statistics are correctly displayed in Live Dashboard"""
            # **Fix**: Again ensure Live Dashboard displays the correct final statistics
            # Prevent any subsequent operations from accidentally resetting the display
            self.main_window.files_processed_label.setText(str(final_files_processed))
            self.main_window.packets_processed_label.setText(
                str(final_packets_processed)
            )

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
        # Use statistics manager to reset data
        self.statistics.reset_all_statistics()
        self.user_stopped = False

        # **Fix**: Notify UI update through event coordinator, but only reset display when starting new processing
        # This avoids accidentally resetting Live Dashboard display after processing completion
        if hasattr(self.main_window, "event_coordinator"):
            self.main_window.event_coordinator.notify_statistics_change(action="reset")

        # Stop timer
        if self.main_window.timer.isActive():
            self.main_window.timer.stop()

    def generate_partial_summary_on_stop(self):
        """Generate partial summary when stopped"""
        try:
            # Get data from StatisticsManager
            stats = self.statistics.get_processing_summary()
            partial_data = {**stats, "status": "stopped_by_user"}

            self.main_window.report_manager.set_final_summary_report(partial_data)

        except Exception as e:
            self._logger.error(f"Error occurred while generating partial summary: {e}")

    def _generate_final_report(self):
        """Generate final report"""
        try:
            # Get data from StatisticsManager
            stats = self.statistics.get_processing_summary()
            final_data = {
                **stats,
                "status": "completed",
                "output_directory": self.main_window.current_output_dir,
            }

            self.main_window.report_manager.set_final_summary_report(final_data)

        except Exception as e:
            self._logger.error(f"Error occurred while generating final report: {e}")

    # Old _build_pipeline_config method has been removed, use service layer's build_pipeline_config function
