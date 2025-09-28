#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CLI Result Formatters - Unified result display formatting

This module provides result formatting utilities for the CLI interface
that use the StandardMessages system to ensure consistency with the GUI.

Key Features:
- Unified result formatting using StandardMessages
- Verbose and brief output modes
- Progress and statistics display
- Error and warning formatting
"""

from typing import List, Optional

import typer

from ..core.messages import MessageFormatter, StandardMessages
from ..core.pipeline.models import ProcessResult, StageStats


def format_result(result: ProcessResult, verbose: bool = False):
    """Format and display processing result

    Args:
        result: ProcessResult from pipeline execution
        verbose: Whether to show detailed information
    """

    # Display result summary
    summary = StandardMessages.format_result_summary(result)
    typer.echo(summary)

    if verbose and result.success:
        # Display detailed statistics
        _format_detailed_stats(result)

    if result.errors:
        # Display errors
        typer.echo(f"\n{StandardMessages.ERROR_ICON} Errors:")
        for error in result.errors:
            typer.echo(f"  - {error}")


def _format_detailed_stats(result: ProcessResult):
    """Format detailed processing statistics

    Args:
        result: ProcessResult with statistics to display
    """

    if not result.stage_stats:
        return

    typer.echo("\n📊 Processing Statistics:")

    # Overall timing
    duration_str = MessageFormatter.format_duration(result.duration_ms)
    typer.echo(f"  ⏱️  Total duration: {duration_str}")
    typer.echo(f"  🔧 Stages executed: {len(result.stage_stats)}")

    # Stage-by-stage breakdown
    typer.echo("\n📋 Stage Details:")
    for i, stage_stat in enumerate(result.stage_stats, 1):
        _format_stage_stats(stage_stat, i)


def _format_stage_stats(stage_stat: StageStats, stage_number: int):
    """Format individual stage statistics

    Args:
        stage_stat: StageStats for a single stage
        stage_number: Stage number for display
    """

    stage_duration = MessageFormatter.format_duration(stage_stat.duration_ms)

    typer.echo(f"  {stage_number}. {stage_stat.stage_name}")
    typer.echo(f"     ⏱️  Duration: {stage_duration}")
    typer.echo(f"     📦 Packets processed: {stage_stat.packets_processed:,}")
    typer.echo(f"     ✏️  Packets modified: {stage_stat.packets_modified:,}")

    # Calculate modification percentage
    if stage_stat.packets_processed > 0:
        mod_percentage = MessageFormatter.format_percentage(stage_stat.packets_modified, stage_stat.packets_processed)
        typer.echo(f"     📊 Modification rate: {mod_percentage}")

    # Display extra metrics if available
    if hasattr(stage_stat, "extra_metrics") and stage_stat.extra_metrics:
        _format_extra_metrics(stage_stat.extra_metrics)


def _format_extra_metrics(extra_metrics: dict):
    """Format extra metrics from stage statistics

    Args:
        extra_metrics: Dictionary of additional metrics
    """

    # Common metrics formatting
    if "bytes_saved" in extra_metrics:
        bytes_saved = extra_metrics["bytes_saved"]
        size_str = MessageFormatter.format_file_size(bytes_saved)
        typer.echo(f"     💾 Bytes saved: {size_str}")

    if "compression_ratio" in extra_metrics:
        ratio = extra_metrics["compression_ratio"]
        typer.echo(f"     🗜️  Compression ratio: {ratio:.2f}x")

    if "duplicates_removed" in extra_metrics:
        dups = extra_metrics["duplicates_removed"]
        typer.echo(f"     🔄 Duplicates removed: {dups:,}")

    if "ips_anonymized" in extra_metrics:
        ips = extra_metrics["ips_anonymized"]
        typer.echo(f"     🎭 IPs anonymized: {ips:,}")

    if "payloads_masked" in extra_metrics:
        payloads = extra_metrics["payloads_masked"]
        typer.echo(f"     🎭 Payloads masked: {payloads:,}")


def format_directory_summary(
    processed_files: int,
    failed_files: int,
    total_duration: float,
    verbose: bool = False,
):
    """Format directory processing summary

    Args:
        processed_files: Number of successfully processed files
        failed_files: Number of failed files
        total_duration: Total processing duration in milliseconds
        verbose: Whether to show detailed information
    """

    total_files = processed_files + failed_files
    duration_str = MessageFormatter.format_duration(total_duration)

    typer.echo("\n📊 Directory Processing Summary:")
    typer.echo(f"  📁 Total files: {total_files}")
    typer.echo(f"  {StandardMessages.SUCCESS_ICON} Processed: {processed_files}")

    if failed_files > 0:
        typer.echo(f"  {StandardMessages.ERROR_ICON} Failed: {failed_files}")

    typer.echo(f"  ⏱️  Total duration: {duration_str}")

    if verbose and total_files > 0:
        success_rate = MessageFormatter.format_percentage(processed_files, total_files)
        typer.echo(f"  📊 Success rate: {success_rate}")

        if total_duration > 0:
            avg_duration = total_duration / total_files
            avg_duration_str = MessageFormatter.format_duration(avg_duration)
            typer.echo(f"  ⚡ Average per file: {avg_duration_str}")


def format_progress_update(current: int, total: int, filename: str):
    """Format progress update for directory processing

    Args:
        current: Current file number
        total: Total number of files
        filename: Name of current file being processed
    """

    progress_msg = StandardMessages.format_file_progress(filename, current, total)
    typer.echo(progress_msg)


def format_error_list(errors: List[str], title: str = "Errors"):
    """Format a list of errors for display

    Args:
        errors: List of error messages
        title: Title for the error section
    """

    if not errors:
        return

    typer.echo(f"\n{StandardMessages.ERROR_ICON} {title}:")
    for error in errors:
        typer.echo(f"  - {error}")


def format_warning_list(warnings: List[str], title: str = "Warnings"):
    """Format a list of warnings for display

    Args:
        warnings: List of warning messages
        title: Title for the warning section
    """

    if not warnings:
        return

    typer.echo(f"\n{StandardMessages.WARNING_ICON} {title}:")
    for warning in warnings:
        typer.echo(f"  - {warning}")


def format_configuration_display(dedup: bool, anon: bool, mask: bool):
    """Format configuration for display

    Args:
        dedup: Remove Dupes enabled
        anon: Anonymize IPs enabled
        mask: Mask Payloads enabled
    """

    typer.echo(f"{StandardMessages.INFO_ICON} Processing Configuration:")
    config_lines = StandardMessages.format_configuration_summary(dedup, anon, mask)
    for line in config_lines:
        typer.echo(f"  {line}")


def format_validation_result(is_valid: bool, errors: Optional[List[str]] = None):
    """Format validation result for display

    Args:
        is_valid: Whether validation passed
        errors: List of validation errors (if any)
    """

    if is_valid:
        typer.echo(f"{StandardMessages.SUCCESS_ICON} Validation passed")
    else:
        typer.echo(f"{StandardMessages.ERROR_ICON} Validation failed")
        if errors:
            format_error_list(errors, "Validation Errors")


def format_file_info(file_path, show_size: bool = True, show_type: bool = True):
    """Format file information for display

    Args:
        file_path: Path to the file
        show_size: Whether to show file size
        show_type: Whether to show file type
    """

    info_parts = [f"📁 {file_path.name}"]

    if show_size:
        try:
            file_size = file_path.stat().st_size
            size_str = MessageFormatter.format_file_size(file_size)
            info_parts.append(f"({size_str})")
        except OSError:
            pass

    if show_type:
        file_type = "PCAP" if file_path.suffix.lower() == ".pcap" else "PCAPNG"
        info_parts.append(f"[{file_type}]")

    typer.echo(" ".join(info_parts))


def format_processing_start(input_path, output_path, config_summary: str):
    """Format processing start message

    Args:
        input_path: Input file/directory path
        output_path: Output file/directory path
        config_summary: Configuration summary string
    """

    typer.echo(f"{StandardMessages.START_ICON} {StandardMessages.PROCESSING_START}")
    typer.echo(f"📁 Input: {input_path}")
    typer.echo(f"📁 Output: {output_path}")
    typer.echo(f"⚙️ {config_summary}")


def format_processing_complete():
    """Format processing complete message"""
    typer.echo(f"{StandardMessages.SUCCESS_ICON} {StandardMessages.PROCESSING_COMPLETE}")


def format_processing_failed(error_message: str):
    """Format processing failed message

    Args:
        error_message: Error message to display
    """
    typer.echo(f"{StandardMessages.ERROR_ICON} {StandardMessages.PROCESSING_FAILED}")
    typer.echo(f"Error: {error_message}")


def format_help_text(command_name: str, description: str):
    """Format help text for commands

    Args:
        command_name: Name of the command
        description: Command description
    """
    typer.echo(f"{StandardMessages.INFO_ICON} {command_name}")
    typer.echo(f"  {description}")
