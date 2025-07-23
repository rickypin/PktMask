"""
Pipeline service interface
Provides decoupled interface between GUI and core pipeline
"""

from typing import Any, Callable, Dict, Optional, Tuple

from pktmask.core.events import PipelineEvents
from pktmask.infrastructure.logging import get_logger


# Define service layer exceptions
class PipelineServiceError(Exception):
    """Base service layer exception"""


class ConfigurationError(PipelineServiceError):
    """Configuration error"""


logger = get_logger("PipelineService")

# Create pipeline executor
# Dummy implementation; replace ... with real logic


def create_pipeline_executor(config: Dict) -> object:
    """
    Create pipeline executor

    Args:
        config: Pipeline configuration dictionary containing stage enable status and parameters

    Returns:
        Executor object (opaque to GUI)
    """
    try:
        from pktmask.core.pipeline.executor import PipelineExecutor

        return PipelineExecutor(config)
    except Exception as e:
        logger.error(f"[Service] Failed to create executor: {e}")
        raise PipelineServiceError("Failed to create executor")


# Process all PCAP files in directory
# Dummy implementation; replace ... with real logic


def process_directory(
    executor: object,
    input_dir: str,
    output_dir: str,
    progress_callback: Callable[[PipelineEvents, Dict], None],
    is_running_check: Callable[[], bool],
) -> None:
    """
    Process all PCAP files in directory

    Args:
        executor: Executor object
        input_dir: Input directory path
        output_dir: Output directory path
        progress_callback: Progress callback function
        is_running_check: Function to check if should continue running
    """
    try:
        import os

        logger.info(f"[Service] Starting directory processing: {input_dir}")

        # Send pipeline start event
        progress_callback(PipelineEvents.PIPELINE_START, {"total_subdirs": 1})

        # Scan PCAP files in directory
        pcap_files = []
        for file in os.scandir(input_dir):
            if file.name.endswith((".pcap", ".pcapng")):
                pcap_files.append(file.path)

        if not pcap_files:
            progress_callback(
                PipelineEvents.LOG, {"message": "No PCAP files found in directory"}
            )
            progress_callback(PipelineEvents.PIPELINE_END, {})
            return

        # Send subdirectory start event
        rel_subdir = os.path.relpath(input_dir, input_dir)
        progress_callback(
            PipelineEvents.SUBDIR_START,
            {
                "name": rel_subdir,
                "current": 1,
                "total": 1,
                "file_count": len(pcap_files),
            },
        )

        # Process each file
        for input_path in pcap_files:
            if not is_running_check():
                break

            # Send file start event
            progress_callback(PipelineEvents.FILE_START, {"path": input_path})

            try:
                # Construct output filename
                base_name, ext = os.path.splitext(os.path.basename(input_path))
                output_path = os.path.join(output_dir, f"{base_name}_processed{ext}")

                # Use executor to process file
                result = executor.run(
                    input_path,
                    output_path,
                    progress_cb=lambda stage, stats: _handle_stage_progress(
                        stage, stats, progress_callback
                    ),
                )

                # Check if processing was successful
                if not result.success:
                    # Send error information to GUI for failed processing
                    for error in result.errors:
                        progress_callback(
                            PipelineEvents.ERROR,
                            {
                                "message": f"File {os.path.basename(input_path)}: {error}"
                            },
                        )

                    # Send user-friendly error messages from stage statistics
                    for stage_stats in result.stage_stats:
                        if "user_message" in stage_stats.extra_metrics:
                            progress_callback(
                                PipelineEvents.ERROR,
                                {
                                    "message": f"File {os.path.basename(input_path)}: {stage_stats.extra_metrics['user_message']}"
                                },
                            )

                # Send step summary events (for both successful and failed stages)
                for stage_stats in result.stage_stats:
                    progress_callback(
                        PipelineEvents.STEP_SUMMARY,
                        {
                            "step_name": stage_stats.stage_name,
                            "filename": os.path.basename(input_path),
                            "packets_processed": stage_stats.packets_processed,
                            "packets_modified": stage_stats.packets_modified,
                            "duration_ms": stage_stats.duration_ms,
                            **stage_stats.extra_metrics,
                        },
                    )

            except Exception as e:
                # Log the exception with full context
                logger.error(
                    f"[Service] Unexpected error processing file {input_path}: {e}",
                    exc_info=True,
                )

                # Send user-friendly error message to GUI
                progress_callback(
                    PipelineEvents.ERROR,
                    {
                        "message": f"Unexpected error processing file {os.path.basename(input_path)}: {str(e)}"
                    },
                )

            # Send file completion event
            progress_callback(PipelineEvents.FILE_END, {"path": input_path})

        # Send subdirectory end event
        progress_callback(PipelineEvents.SUBDIR_END, {"name": rel_subdir})

        # Send pipeline end event
        progress_callback(PipelineEvents.PIPELINE_END, {})

        logger.info(f"[Service] Completed directory processing: {input_dir}")

    except Exception as e:
        logger.error(f"[Service] Directory processing failed: {e}")
        raise PipelineServiceError(f"Directory processing failed: {str(e)}")


def _handle_stage_progress(stage, stats, progress_callback):
    """Handle stage progress callback"""
    # Get standardized display name for the stage
    stage_display_name = _get_stage_display_name(stage.name)

    # Emit log with stage-specific action wording and correct statistics
    if stage.name == "DeduplicationStage":
        msg = f"- {stage_display_name}: processed {stats.packets_processed} pkts, removed {stats.packets_modified} pkts"
    elif stage.name in ["AnonStage", "IPAnonymizationStage"]:
        # For IP anonymization, show IP statistics instead of packet statistics
        original_ips = getattr(stats, "original_ips", 0) or stats.extra_metrics.get(
            "original_ips", 0
        )
        anonymized_ips = getattr(stats, "anonymized_ips", 0) or stats.extra_metrics.get(
            "anonymized_ips", 0
        )
        if original_ips > 0:
            msg = f"- {stage_display_name}: found {original_ips} IPs, anonymized {anonymized_ips} IPs"
        else:
            # Fallback to packet count if IP statistics are not available
            msg = f"- {stage_display_name}: processed {stats.packets_processed} pkts, anonymized {stats.packets_modified} IPs"
    else:
        msg = f"- {stage_display_name}: processed {stats.packets_processed} pkts, masked {stats.packets_modified} pkts"
    progress_callback(PipelineEvents.LOG, {"message": msg})


def _get_stage_display_name(stage_name: str) -> str:
    """Get standardized display name for stage based on naming consistency guide"""
    stage_name_mapping = {
        "DeduplicationStage": "Deduplication Stage",
        "AnonStage": "IP Anonymization Stage",
        "IPAnonymizationStage": "IP Anonymization Stage",  # New StageBase implementation
        "NewMaskPayloadStage": "Payload Masking Stage",
        "MaskStage": "Payload Masking Stage",
        "MaskPayloadStage": "Payload Masking Stage",
        "Mask Payloads (v2)": "Payload Masking Stage",
    }
    return stage_name_mapping.get(stage_name, stage_name)


# Stop pipeline execution
# Dummy implementation; replace ... with real logic


def stop_pipeline(executor: object) -> None:
    """Stop pipeline execution"""
    try:
        # Try to call executor's stop method
        if hasattr(executor, "stop"):
            executor.stop()
            logger.info("[Service] Pipeline stopped")
        else:
            logger.warning("[Service] Executor does not support stop method")
    except Exception as e:
        logger.error(f"[Service] Failed to stop pipeline: {e}")
        raise PipelineServiceError(f"Failed to stop pipeline: {str(e)}")


# Return current executor statistics
# Dummy implementation; replace ... with real logic


def get_pipeline_status(executor: object) -> Dict[str, Any]:
    """Return current executor statistics, such as number of processed files"""
    return {}


# Validate configuration before actually creating executor
# Dummy implementation; replace ... with real logic


def validate_config(config: Dict) -> Tuple[bool, Optional[str]]:
    """Validate configuration validity"""
    if not config:
        return False, "Configuration is empty"
    return True, None


# Build pipeline configuration based on feature switches
# Dummy implementation; replace ... with real logic


def build_pipeline_config(
    enable_anon: bool, enable_dedup: bool, enable_mask: bool
) -> Dict:
    """Build pipeline configuration based on feature switches (using standard naming conventions)"""
    # Use unified configuration service
    from pktmask.services.config_service import get_config_service

    service = get_config_service()
    options = service.create_options_from_gui(
        dedup_checked=enable_dedup, anon_checked=enable_anon, mask_checked=enable_mask
    )

    return service.build_pipeline_config(options)


# ============================================================================
# CLI unified service interface
# ============================================================================


def process_single_file(
    executor: object,
    input_file: str,
    output_file: str,
    progress_callback: Optional[Callable[[PipelineEvents, Dict], None]] = None,
    verbose: bool = False,
) -> Dict[str, Any]:
    """
    Process single file (CLI-specific interface)

    Args:
        executor: Executor object
        input_file: Input file path
        output_file: Output file path
        progress_callback: Progress callback function
        verbose: Whether to enable verbose output

    Returns:
        Processing result dictionary containing statistics and status
    """
    try:
        logger.info(f"[Service] Processing single file: {input_file}")

        # Ensure output directory exists
        from pathlib import Path

        output_path = Path(output_file)
        output_dir = output_path.parent

        if not output_dir.exists():
            try:
                output_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"[Service] Created output directory: {output_dir}")
            except Exception as e:
                logger.error(
                    f"[Service] Failed to create output directory {output_dir}: {e}"
                )
                raise PipelineServiceError(
                    f"Failed to create output directory: {str(e)}"
                )

        # Send processing start event
        if progress_callback:
            progress_callback(PipelineEvents.PIPELINE_START, {"total_files": 1})
            progress_callback(PipelineEvents.FILE_START, {"path": input_file})

        # Create progress callback wrapper
        def stage_progress_wrapper(stage, stats):
            if progress_callback:
                _handle_stage_progress(stage, stats, progress_callback)

        # Execute processing
        result = executor.run(
            input_file,
            output_file,
            progress_cb=stage_progress_wrapper if verbose else None,
        )

        # Send processing completion event
        if progress_callback:
            progress_callback(
                PipelineEvents.FILE_END,
                {
                    "path": input_file,
                    "output_path": output_file,
                    "success": result.success,
                },
            )
            progress_callback(PipelineEvents.PIPELINE_END, {})

        # Return unified format result
        return {
            "success": result.success,
            "input_file": result.input_file,
            "output_file": result.output_file,
            "duration_ms": result.duration_ms,
            "stage_stats": [
                stats.model_dump() if hasattr(stats, "model_dump") else stats.__dict__
                for stats in result.stage_stats
            ],
            "errors": result.errors,
            "total_files": 1,
            "processed_files": 1 if result.success else 0,
        }

    except Exception as e:
        logger.error(f"[Service] Failed to process single file: {e}")
        if progress_callback:
            progress_callback(PipelineEvents.ERROR, {"message": str(e)})
            progress_callback(PipelineEvents.PIPELINE_END, {})
        raise PipelineServiceError(f"Failed to process file: {str(e)}")


def process_directory_cli(
    executor: object,
    input_dir: str,
    output_dir: str,
    progress_callback: Optional[Callable[[PipelineEvents, Dict], None]] = None,
    verbose: bool = False,
    file_pattern: str = "*.pcap,*.pcapng",
) -> Dict[str, Any]:
    """
    Process all files in directory (CLI-specific interface)

    Args:
        executor: Executor object
        input_dir: Input directory path
        output_dir: Output directory path
        progress_callback: Progress callback function
        verbose: Whether to enable verbose output
        file_pattern: File matching pattern

    Returns:
        Processing result dictionary containing statistics and status
    """
    try:
        import glob
        import os

        logger.info(f"[Service] Processing directory: {input_dir}")

        # Scan matching files
        pcap_files = []
        patterns = file_pattern.split(",")
        for pattern in patterns:
            pattern = pattern.strip()
            files = glob.glob(os.path.join(input_dir, pattern))
            pcap_files.extend(files)

        if not pcap_files:
            logger.warning(
                f"[Service] No matching files found in directory: {input_dir}"
            )
            return {
                "success": True,
                "input_dir": input_dir,
                "output_dir": output_dir,
                "duration_ms": 0.0,
                "total_files": 0,
                "processed_files": 0,
                "failed_files": 0,
                "errors": [],
            }

        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)

        # Send processing start event
        if progress_callback:
            progress_callback(
                PipelineEvents.PIPELINE_START, {"total_files": len(pcap_files)}
            )

        # Processing statistics
        processed_files = 0
        failed_files = 0
        all_errors = []
        total_duration = 0.0

        # Process each file
        for i, input_file in enumerate(pcap_files):
            try:
                # Construct output filename
                base_name = os.path.splitext(os.path.basename(input_file))[0]
                ext = os.path.splitext(input_file)[1]
                output_file = os.path.join(output_dir, f"{base_name}_processed{ext}")

                # Process single file
                result = process_single_file(
                    executor, input_file, output_file, progress_callback, verbose
                )

                if result["success"]:
                    processed_files += 1
                else:
                    failed_files += 1
                    all_errors.extend(result.get("errors", []))

                total_duration += result["duration_ms"]

            except Exception as e:
                failed_files += 1
                error_msg = f"Failed to process {input_file}: {str(e)}"
                all_errors.append(error_msg)
                logger.error(f"[Service] {error_msg}")

                if progress_callback:
                    progress_callback(PipelineEvents.ERROR, {"message": error_msg})

        # Send processing completion event
        if progress_callback:
            progress_callback(PipelineEvents.PIPELINE_END, {})

        # Return unified format result
        return {
            "success": failed_files == 0,
            "input_dir": input_dir,
            "output_dir": output_dir,
            "duration_ms": total_duration,
            "total_files": len(pcap_files),
            "processed_files": processed_files,
            "failed_files": failed_files,
            "errors": all_errors,
        }

    except Exception as e:
        logger.error(f"[Service] Failed to process directory: {e}")
        if progress_callback:
            progress_callback(PipelineEvents.ERROR, {"message": str(e)})
            progress_callback(PipelineEvents.PIPELINE_END, {})
        raise PipelineServiceError(f"Failed to process directory: {str(e)}")


def create_gui_compatible_report_data(result: Dict[str, Any]) -> Dict[str, Any]:
    """Create GUI-compatible report data format"""
    # Convert CLI results to format expected by GUI report manager
    gui_report_data = {
        "step_results": {},
        "total_files": result.get("total_files", 1),
        "processed_files": result.get("processed_files", 0),
        "failed_files": result.get("failed_files", 0),
        "duration_ms": result.get("duration_ms", 0.0),
        "output_directory": result.get("output_dir") or result.get("output_file"),
        "success": result.get("success", False),
    }

    # Convert stage statistics data
    stage_stats = result.get("stage_stats", [])
    for stage_stat in stage_stats:
        if isinstance(stage_stat, dict):
            stage_name = stage_stat.get("stage_name", "Unknown")

            # Map to format expected by GUI
            if "dedup" in stage_name.lower():
                gui_report_data["step_results"]["Deduplication"] = {
                    "packets_processed": stage_stat.get("packets_processed", 0),
                    "packets_modified": stage_stat.get("packets_modified", 0),
                    "duration_ms": stage_stat.get("duration_ms", 0.0),
                    "summary": f"Processed {stage_stat.get('packets_processed', 0)} packets, removed {stage_stat.get('packets_modified', 0)} duplicates",
                }
            elif "anon" in stage_name.lower() or "ip" in stage_name.lower():
                gui_report_data["step_results"]["IP Anonymization"] = {
                    "packets_processed": stage_stat.get("packets_processed", 0),
                    "packets_modified": stage_stat.get("packets_modified", 0),
                    "ips_anonymized": stage_stat.get("packets_modified", 0),
                    "duration_ms": stage_stat.get("duration_ms", 0.0),
                    "summary": f"Anonymized {stage_stat.get('packets_modified', 0)} IP addresses",
                }
            elif "mask" in stage_name.lower() or "payload" in stage_name.lower():
                gui_report_data["step_results"]["Payload Masking"] = {
                    "packets_processed": stage_stat.get("packets_processed", 0),
                    "packets_modified": stage_stat.get("packets_modified", 0),
                    "total_packets": stage_stat.get("packets_processed", 0),
                    "duration_ms": stage_stat.get("duration_ms", 0.0),
                    "summary": f"Masked {stage_stat.get('packets_modified', 0)} payload packets",
                    "data": {
                        "total_packets": stage_stat.get("packets_processed", 0),
                        "output_filename": result.get("output_file"),
                    },
                }

    return gui_report_data


def generate_gui_style_report(result: Dict[str, Any]) -> str:
    """Generate GUI-style report text"""
    gui_data = create_gui_compatible_report_data(result)

    # Use GUI report manager format
    report_lines = []

    # Title
    report_lines.append("=" * 70)
    report_lines.append("📋 PROCESSING SUMMARY")
    report_lines.append("=" * 70)
    report_lines.append("")

    # Basic information
    report_lines.append(
        f"📊 Files Processed: {gui_data['processed_files']}/{gui_data['total_files']}"
    )
    if gui_data["failed_files"] > 0:
        report_lines.append(f"❌ Failed Files: {gui_data['failed_files']}")
    report_lines.append(f"⏱️  Total Duration: {gui_data['duration_ms']:.1f} ms")
    report_lines.append("")

    # Stage results
    if gui_data["step_results"]:
        report_lines.append("📈 Step Statistics:")
        report_lines.append("")

        for step_name, step_data in gui_data["step_results"].items():
            report_lines.append(f"🔧 {step_name}:")
            report_lines.append(
                f"  • Packets Processed: {step_data.get('packets_processed', 0):,}"
            )
            report_lines.append(
                f"  • Packets Modified: {step_data.get('packets_modified', 0):,}"
            )
            report_lines.append(
                f"  • Duration: {step_data.get('duration_ms', 0.0):.1f} ms"
            )
            if "summary" in step_data:
                report_lines.append(f"  • Summary: {step_data['summary']}")
            report_lines.append("")

    # Output information
    if gui_data["output_directory"]:
        report_lines.append(f"📁 Output: {gui_data['output_directory']}")
        report_lines.append("")

    # Status
    status = "✅ Success" if gui_data["success"] else "❌ Failed"
    report_lines.append(f"Status: {status}")

    return "\n".join(report_lines)
