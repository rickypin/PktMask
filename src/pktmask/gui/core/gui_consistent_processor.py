#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
GUI Consistent Processor - GUI-compatible wrapper for ConsistentProcessor

This module provides GUI-compatible wrappers that preserve Qt threading,
signal behavior, and user interaction patterns while using the new
ConsistentProcessor core.

CRITICAL: This module ensures 100% GUI functionality preservation by:
- Maintaining identical Qt signal emission patterns
- Preserving threading model and responsiveness
- Keeping all user interaction capabilities
- Providing exact same progress event timing
"""

import os
from pathlib import Path
from typing import Callable, Optional, Union

from PyQt6.QtCore import QThread, pyqtSignal

from ...core.consistency import ConsistentProcessor
from ...core.events import PipelineEvents
from ...core.messages import StandardMessages
from ...utils.file_ops import generate_output_filename
from .feature_flags import GUIFeatureFlags


class GUIConsistentProcessor:
    """GUI-compatible wrapper for ConsistentProcessor

    This class provides the interface between GUI components and the
    ConsistentProcessor while preserving all existing GUI behavior patterns.
    """

    @staticmethod
    def create_executor_from_gui(
        remove_dupes_checked: bool,
        anonymize_ips_checked: bool,
        mask_payloads_checked: bool,
    ):
        """Create executor from GUI checkbox states

        Args:
            remove_dupes_checked: Remove Dupes checkbox state
            anonymize_ips_checked: Anonymize IPs checkbox state
            mask_payloads_checked: Mask Payloads checkbox state

        Returns:
            PipelineExecutor configured for GUI use

        Raises:
            ValueError: If no processing options are enabled
        """
        # Convert GUI checkbox names to standardized names
        return ConsistentProcessor.create_executor(
            dedup=remove_dupes_checked,
            anon=anonymize_ips_checked,
            mask=mask_payloads_checked,
        )

    @staticmethod
    def validate_gui_options(
        remove_dupes_checked: bool,
        anonymize_ips_checked: bool,
        mask_payloads_checked: bool,
    ) -> None:
        """Validate GUI options using ConsistentProcessor validation

        Args:
            remove_dupes_checked: Remove Dupes checkbox state
            anonymize_ips_checked: Anonymize IPs checkbox state
            mask_payloads_checked: Mask Payloads checkbox state

        Raises:
            ValueError: If validation fails
        """
        ConsistentProcessor.validate_options(
            dedup=remove_dupes_checked,
            anon=anonymize_ips_checked,
            mask=mask_payloads_checked,
        )

    @staticmethod
    def get_gui_configuration_summary(
        remove_dupes_checked: bool,
        anonymize_ips_checked: bool,
        mask_payloads_checked: bool,
    ) -> str:
        """Get configuration summary for GUI display

        Args:
            remove_dupes_checked: Remove Dupes checkbox state
            anonymize_ips_checked: Anonymize IPs checkbox state
            mask_payloads_checked: Mask Payloads checkbox state

        Returns:
            Human-readable configuration summary
        """
        return ConsistentProcessor.get_configuration_summary(
            dedup=remove_dupes_checked,
            anon=anonymize_ips_checked,
            mask=mask_payloads_checked,
        )


class GUIServicePipelineThread(QThread):
    """Enhanced ServicePipelineThread that uses ConsistentProcessor internally

    CRITICAL: This class preserves ALL current GUI behavior:
    - Identical Qt signal emission patterns
    - Same progress event timing and data format
    - Preserved user interruption capability
    - Maintained threading model for GUI responsiveness
    """

    # CRITICAL: Preserve all Qt signals exactly as current implementation
    progress_signal = pyqtSignal(PipelineEvents, dict)

    def __init__(
        self, executor, base_dir: Union[str, Path], output_dir: Union[str, Path]
    ):
        super().__init__()
        self._executor = executor
        self._base_dir = Path(base_dir)
        self._output_dir = Path(output_dir)
        self.is_running = True  # CRITICAL: Preserve user interruption capability

        # Debug mode support
        self._debug_mode = GUIFeatureFlags.is_gui_debug_mode()
        if self._debug_mode:
            self._log_debug(
                "GUIServicePipelineThread initialized with ConsistentProcessor"
            )

    def run(self):
        """CRITICAL: Preserve exact current behavior while using consistent core

        This method maintains identical signal emission patterns and timing
        while using the ConsistentProcessor internally instead of service layer.
        """
        try:
            if self._debug_mode:
                self._log_debug(
                    f"Starting processing: {self._base_dir} -> {self._output_dir}"
                )

            # Direct processing using ConsistentProcessor approach
            # This eliminates dependency on pipeline_service.process_directory
            if self._base_dir.is_file():
                self._process_single_file()
            else:
                self._process_directory_with_progress()

        except Exception as e:
            # CRITICAL: Preserve exact error handling and signal emission
            if self._debug_mode:
                self._log_debug(f"Processing error: {str(e)}")

            # Emit error using same pattern as original implementation
            self.progress_signal.emit(PipelineEvents.ERROR, {"message": str(e)})

    def _process_single_file(self):
        """Process single file while maintaining GUI signal patterns"""
        try:
            output_file = self._build_output_file_path(self._base_dir)

            # Emit start signal
            self.progress_signal.emit(
                PipelineEvents.PIPELINE_START,
                {"total_files": 1, "input_path": str(self._base_dir)},
            )

            # Emit file start signal
            self.progress_signal.emit(
                PipelineEvents.FILE_START, {"path": str(self._base_dir), "index": 0}
            )

            # Process using executor directly (same as CLI) with progress callback
            result = self._executor.run(
                self._base_dir, output_file, progress_cb=self._handle_stage_progress
            )

            # Emit stage summaries BEFORE file end (GUI expects this order)
            for stage_stat in result.stage_stats:
                payload = {
                    "step_name": stage_stat.stage_name,
                    "filename": os.path.basename(str(self._base_dir)),
                    "path": str(self._base_dir),
                    "packets_processed": stage_stat.packets_processed,
                    "packets_modified": stage_stat.packets_modified,
                    "duration_ms": stage_stat.duration_ms,
                    "total_packets": stage_stat.packets_processed,
                    "output_filename": str(output_file),
                }
                # Attach extra metrics if present
                if hasattr(stage_stat, "extra_metrics") and stage_stat.extra_metrics:
                    payload["extra_metrics"] = stage_stat.extra_metrics
                self.progress_signal.emit(PipelineEvents.STEP_SUMMARY, payload)

            # Emit file end signal with result (after summaries)
            self.progress_signal.emit(
                PipelineEvents.FILE_END, {"path": str(self._base_dir), "result": result}
            )

            # Emit pipeline end signal
            self.progress_signal.emit(
                PipelineEvents.PIPELINE_END,
                {"processed": 1, "total_duration": result.duration_ms},
            )

        except Exception as e:
            self.progress_signal.emit(PipelineEvents.ERROR, {"message": str(e)})

    def _process_directory_with_progress(self):
        """Process directory while maintaining GUI progress events

        CRITICAL: This method preserves the exact progress event emission
        pattern that the GUI expects for proper display updates.
        """
        # Find all PCAP/PCAPNG files in current directory only (not recursive)
        pcap_files = []
        for file in os.scandir(self._base_dir):
            if file.name.lower().endswith((".pcap", ".pcapng")):
                pcap_files.append(Path(file.path))

        if not pcap_files:
            self.progress_signal.emit(
                PipelineEvents.ERROR,
                {"message": "No PCAP/PCAPNG files found in directory"},
            )
            return

        # Emit pipeline start signal
        self.progress_signal.emit(
            PipelineEvents.PIPELINE_START, {"total_files": len(pcap_files)}
        )

        # CRITICAL FIX: Emit SUBDIR_START event to set total file count for progress bar
        # This matches the behavior expected by PipelineManager for proper progress calculation
        self.progress_signal.emit(
            PipelineEvents.SUBDIR_START,
            {
                "name": str(
                    self._base_dir.name
                    if self._base_dir.is_dir()
                    else self._base_dir.parent.name
                ),
                "current": 1,
                "total": 1,
                "file_count": len(pcap_files),
            },
        )

        processed_files = 0
        total_duration = 0.0

        for i, pcap_file in enumerate(pcap_files):
            # Check if user stopped processing
            if not self.is_running:
                self.progress_signal.emit(
                    PipelineEvents.LOG, {"message": "--- Pipeline Stopped by User ---"}
                )
                break

            # Emit file start signal
            self.progress_signal.emit(
                PipelineEvents.FILE_START, {"path": str(pcap_file), "index": i}
            )

            try:
                # Generate output file path with unified suffix logic
                output_file = self._build_output_file_path(pcap_file)

                # Process file using executor directly with progress callback
                result = self._executor.run(
                    pcap_file, output_file, progress_cb=self._handle_stage_progress
                )

                if result.success:
                    processed_files += 1
                    total_duration += result.duration_ms

                # Emit stage summaries BEFORE file end so summary manager sees them
                for stage_stat in result.stage_stats:
                    payload = {
                        "step_name": stage_stat.stage_name,
                        "filename": os.path.basename(str(pcap_file)),
                        "path": str(pcap_file),
                        "packets_processed": stage_stat.packets_processed,
                        "packets_modified": stage_stat.packets_modified,
                        "duration_ms": stage_stat.duration_ms,
                        "total_packets": stage_stat.packets_processed,
                        "output_filename": str(output_file),
                    }
                    if (
                        hasattr(stage_stat, "extra_metrics")
                        and stage_stat.extra_metrics
                    ):
                        payload["extra_metrics"] = stage_stat.extra_metrics
                    self.progress_signal.emit(PipelineEvents.STEP_SUMMARY, payload)

                # Emit file end signal with result (after summaries)
                self.progress_signal.emit(
                    PipelineEvents.FILE_END, {"path": str(pcap_file), "result": result}
                )

            except Exception as e:
                # Emit error for this specific file
                self.progress_signal.emit(
                    PipelineEvents.ERROR,
                    {"message": f"File {pcap_file.name}: {str(e)}"},
                )

        # Emit pipeline end signal
        self.progress_signal.emit(
            PipelineEvents.PIPELINE_END,
            {
                "processed": processed_files,
                "total_files": len(pcap_files),
                "total_duration": total_duration,
            },
        )

    def stop(self):
        """CRITICAL: Preserve exact stop behavior

        This method maintains the same stop functionality as the original
        implementation, ensuring user interruption works identically.
        """
        self.is_running = False

        if self._debug_mode:
            self._log_debug("Pipeline stop requested by user")

        # Emit stop message using same format as original
        self.progress_signal.emit(
            PipelineEvents.LOG, {"message": "--- Pipeline Stopped by User ---"}
        )

        # Note: We don't call stop_pipeline() from service layer since we're
        # using the executor directly. The executor handles its own cleanup.

        # Emit pipeline end to ensure GUI state is properly updated
        self.progress_signal.emit(PipelineEvents.PIPELINE_END, {})

    def _log_debug(self, message: str):
        """Log debug message if debug mode is enabled"""
        if self._debug_mode:
            self.progress_signal.emit(
                PipelineEvents.LOG, {"message": f"[DEBUG] {message}"}
            )

    def _handle_stage_progress(self, stage, stats):
        """Handle stage progress callback to emit detailed stage statistics

        This replicates the functionality of pipeline_service._handle_stage_progress
        to provide detailed stage-by-stage processing information in the GUI log.
        """
        # Get standardized display name for the stage
        stage_display_name = self._get_stage_display_name(stage.name)

        # Emit log with stage-specific action wording and correct statistics
        if stage.name in ["DeduplicationStage", "UnifiedDeduplicationStage"]:
            msg = f"- {stage_display_name}: processed {stats.packets_processed} pkts, removed {stats.packets_modified} pkts"
        elif stage.name in [
            "AnonStage",
            "IPAnonymizationStage",
            "UnifiedIPAnonymizationStage",
            "AnonymizationStage",
        ]:
            # For IP anonymization, show IP statistics instead of packet statistics
            original_ips = getattr(stats, "original_ips", 0) or stats.extra_metrics.get(
                "original_ips", 0
            )
            anonymized_ips = getattr(
                stats, "anonymized_ips", 0
            ) or stats.extra_metrics.get("anonymized_ips", 0)
            if original_ips > 0:
                msg = f"- {stage_display_name}: processed {original_ips} IPs, anonymized {anonymized_ips} IPs"
            else:
                # Fallback to packet count if IP statistics are not available
                msg = f"- {stage_display_name}: processed {stats.packets_processed} pkts, anonymized {stats.packets_modified} IPs"
        else:
            msg = f"- {stage_display_name}: processed {stats.packets_processed} pkts, masked {stats.packets_modified} pkts"

        self.progress_signal.emit(PipelineEvents.LOG, {"message": msg})

    def _get_stage_display_name(self, stage_name: str) -> str:
        """Get standardized display name for stage based on naming consistency guide"""
        stage_name_mapping = {
            "DeduplicationStage": "Deduplication Stage",
            "UnifiedDeduplicationStage": "Deduplication Stage",  # New Unified implementation
            "AnonStage": "Anonymize IPs Stage",
            "IPAnonymizationStage": "Anonymize IPs Stage",  # Old StageBase implementation
            "UnifiedIPAnonymizationStage": "Anonymize IPs Stage",  # New Unified implementation
            "AnonymizationStage": "Anonymize IPs Stage",  # Standardized naming
            "NewMaskPayloadStage": "Mask Payloads Stage",
            "MaskStage": "Mask Payloads Stage",
            "MaskPayloadStage": "Mask Payloads Stage",
            "MaskingStage": "Mask Payloads Stage",  # Standardized naming
            "Mask Payloads (v2)": "Mask Payloads Stage",
        }
        return stage_name_mapping.get(stage_name, stage_name)

    def _build_output_file_path(self, input_file: Path) -> Path:
        """Generate processed output file path with unified suffix"""
        return Path(
            generate_output_filename(
                str(input_file),
                "_processed",
                self._output_dir,
            )
        )


class GUIThreadingHelper:
    """Helper for GUI threading integration with ConsistentProcessor

    CRITICAL: This helper ensures proper integration between the GUI threading
    model and the ConsistentProcessor while preserving all current behavior.
    """

    @staticmethod
    def create_threaded_executor(
        remove_dupes_checked: bool,
        anonymize_ips_checked: bool,
        mask_payloads_checked: bool,
        base_dir: Union[str, Path],
        output_dir: Union[str, Path],
    ) -> GUIServicePipelineThread:
        """Create GUI thread with ConsistentProcessor executor

        Args:
            remove_dupes_checked: Remove Dupes checkbox state
            anonymize_ips_checked: Anonymize IPs checkbox state
            mask_payloads_checked: Mask Payloads checkbox state
            base_dir: Input directory or file path
            output_dir: Output directory path

        Returns:
            GUIServicePipelineThread ready for execution

        Raises:
            ValueError: If configuration validation fails
        """
        # Validate options first
        GUIConsistentProcessor.validate_gui_options(
            remove_dupes_checked, anonymize_ips_checked, mask_payloads_checked
        )

        # Create executor using GUI wrapper
        executor = GUIConsistentProcessor.create_executor_from_gui(
            remove_dupes_checked, anonymize_ips_checked, mask_payloads_checked
        )

        # Create and return GUI thread
        return GUIServicePipelineThread(executor, base_dir, output_dir)

    @staticmethod
    def validate_gui_threading_compatibility() -> bool:
        """Validate that GUI threading is compatible with ConsistentProcessor

        Returns:
            True if threading is compatible, False otherwise
        """
        try:
            # Test basic executor creation
            test_executor = ConsistentProcessor.create_executor(True, False, False)

            # Test that executor can be used in threading context
            # (This is a basic compatibility check)
            return test_executor is not None

        except Exception:
            return False
