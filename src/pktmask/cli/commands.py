#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Simplified CLI Commands - Direct ConsistentProcessor usage

This module provides simplified CLI commands that use the ConsistentProcessor
directly, eliminating service layer dependencies and ensuring consistency
with the GUI interface.

Key Features:
- Direct ConsistentProcessor usage
- Standardized parameter naming (dedup, anon, mask)
- Unified error handling and messaging
- Smart output path generation
- Directory processing support
"""

import os
from pathlib import Path
from typing import Optional
import typer

from ..core.consistency import ConsistentProcessor
from ..core.messages import StandardMessages
from .formatters import format_result, format_directory_summary


def process_command(
    input_path: Path = typer.Argument(..., help="Input PCAP/PCAPNG file or directory"),
    output_path: Optional[Path] = typer.Option(None, "-o", "--output", 
                                              help="Output path (auto-generated if not specified)"),
    dedup: bool = typer.Option(False, "--dedup", help="Enable Remove Dupes processing"),
    anon: bool = typer.Option(False, "--anon", help="Enable Anonymize IPs processing"),
    mask: bool = typer.Option(False, "--mask", help="Enable Mask Payloads processing"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output")
):
    """Process PCAP/PCAPNG files with unified core processing
    
    This command uses the same ConsistentProcessor that the GUI uses,
    ensuring identical processing results across interfaces.
    """
    
    # Input validation
    try:
        ConsistentProcessor.validate_input_path(input_path)
    except (FileNotFoundError, ValueError) as e:
        typer.echo(f"{StandardMessages.ERROR_ICON} {str(e)}", err=True)
        raise typer.Exit(1)
    
    # Options validation
    try:
        ConsistentProcessor.validate_options(dedup, anon, mask)
    except ValueError as e:
        typer.echo(f"{StandardMessages.ERROR_ICON} {str(e)}", err=True)
        raise typer.Exit(1)
    
    # Generate output path if needed
    if output_path is None:
        output_path = ConsistentProcessor.generate_output_path(input_path)
        if verbose:
            typer.echo(f"📁 Auto-generated output: {output_path}")
    
    # Display configuration if verbose
    if verbose:
        config_summary = ConsistentProcessor.get_configuration_summary(dedup, anon, mask)
        typer.echo(f"⚙️ Configuration: {config_summary}")
    
    # Process using unified core
    try:
        if input_path.is_file():
            _process_single_file(input_path, output_path, dedup, anon, mask, verbose)
        else:
            _process_directory(input_path, output_path, dedup, anon, mask, verbose)
    except Exception as e:
        typer.echo(f"{StandardMessages.ERROR_ICON} {str(e)}", err=True)
        raise typer.Exit(1)


def _process_single_file(input_path: Path, output_path: Path, 
                        dedup: bool, anon: bool, mask: bool, verbose: bool):
    """Process a single file using ConsistentProcessor"""
    
    typer.echo(f"{StandardMessages.START_ICON} {StandardMessages.PROCESSING_START}")
    
    if verbose:
        typer.echo(f"📁 Input: {input_path}")
        typer.echo(f"📁 Output: {output_path}")
    
    try:
        result = ConsistentProcessor.process_file(input_path, output_path, dedup, anon, mask)
        format_result(result, verbose)
        
        if result.success:
            typer.echo(f"{StandardMessages.SUCCESS_ICON} {StandardMessages.PROCESSING_COMPLETE}")
        else:
            typer.echo(f"{StandardMessages.ERROR_ICON} {StandardMessages.PROCESSING_FAILED}")
            raise typer.Exit(1)
            
    except Exception as e:
        typer.echo(f"{StandardMessages.ERROR_ICON} Processing failed: {str(e)}", err=True)
        raise typer.Exit(1)


def _process_directory(input_path: Path, output_path: Path,
                      dedup: bool, anon: bool, mask: bool, verbose: bool):
    """Process a directory of files using ConsistentProcessor"""
    
    # Find all PCAP/PCAPNG files
    pcap_files = []
    for root, dirs, files in os.walk(input_path):
        for file in files:
            if file.lower().endswith(('.pcap', '.pcapng')):
                pcap_files.append(Path(root) / file)
    
    if not pcap_files:
        typer.echo(f"{StandardMessages.WARNING_ICON} No PCAP/PCAPNG files found in directory")
        return
    
    typer.echo(f"{StandardMessages.START_ICON} {StandardMessages.PROCESSING_START}")
    typer.echo(f"📂 Found {len(pcap_files)} files to process")
    
    # Ensure output directory exists
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Process each file
    processed_files = 0
    failed_files = 0
    total_duration = 0.0
    
    for i, pcap_file in enumerate(pcap_files, 1):
        if verbose:
            typer.echo(f"📁 [{i}/{len(pcap_files)}] Processing: {pcap_file.name}")
        
        # Generate output file path
        output_file = output_path / pcap_file.name
        
        try:
            result = ConsistentProcessor.process_file(pcap_file, output_file, dedup, anon, mask)
            
            if result.success:
                processed_files += 1
                total_duration += result.duration_ms
                if verbose:
                    format_result(result, verbose=False)  # Brief format for directory processing
            else:
                failed_files += 1
                typer.echo(f"{StandardMessages.ERROR_ICON} Failed: {pcap_file.name}")
                if verbose:
                    for error in result.errors:
                        typer.echo(f"  - {error}")
                        
        except Exception as e:
            failed_files += 1
            typer.echo(f"{StandardMessages.ERROR_ICON} Failed: {pcap_file.name} - {str(e)}")
    
    # Display summary
    format_directory_summary(processed_files, failed_files, total_duration, verbose)
    
    if failed_files > 0:
        typer.echo(f"{StandardMessages.WARNING_ICON} {failed_files} files failed processing")
        raise typer.Exit(1)
    else:
        typer.echo(f"{StandardMessages.SUCCESS_ICON} {StandardMessages.PROCESSING_COMPLETE}")


def validate_command(
    input_path: Path = typer.Argument(..., help="Input PCAP/PCAPNG file or directory to validate"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output")
):
    """Validate PCAP/PCAPNG files without processing
    
    This command validates input files and reports any issues without
    performing any processing operations.
    """
    
    typer.echo(f"{StandardMessages.INFO_ICON} Validating input: {input_path}")
    
    try:
        ConsistentProcessor.validate_input_path(input_path)
        
        if input_path.is_file():
            typer.echo(f"{StandardMessages.SUCCESS_ICON} Valid PCAP/PCAPNG file")
            if verbose:
                file_size = input_path.stat().st_size
                from ..core.messages import MessageFormatter
                typer.echo(f"📊 File size: {MessageFormatter.format_file_size(file_size)}")
        else:
            # Count files in directory
            pcap_files = []
            for root, dirs, files in os.walk(input_path):
                for file in files:
                    if file.lower().endswith(('.pcap', '.pcapng')):
                        pcap_files.append(Path(root) / file)
            
            typer.echo(f"{StandardMessages.SUCCESS_ICON} Valid directory with {len(pcap_files)} PCAP/PCAPNG files")
            
            if verbose and pcap_files:
                typer.echo("📁 Files found:")
                for pcap_file in pcap_files[:10]:  # Show first 10 files
                    file_size = pcap_file.stat().st_size
                    from ..core.messages import MessageFormatter
                    typer.echo(f"  - {pcap_file.name} ({MessageFormatter.format_file_size(file_size)})")
                if len(pcap_files) > 10:
                    typer.echo(f"  ... and {len(pcap_files) - 10} more files")
                    
    except (FileNotFoundError, ValueError) as e:
        typer.echo(f"{StandardMessages.ERROR_ICON} Validation failed: {str(e)}", err=True)
        raise typer.Exit(1)


def config_command(
    dedup: bool = typer.Option(False, "--dedup", help="Enable Remove Dupes processing"),
    anon: bool = typer.Option(False, "--anon", help="Enable Anonymize IPs processing"),
    mask: bool = typer.Option(False, "--mask", help="Enable Mask Payloads processing")
):
    """Display configuration summary for given options
    
    This command shows what processing stages would be enabled
    for the given options without performing any processing.
    """
    
    try:
        ConsistentProcessor.validate_options(dedup, anon, mask)
        
        typer.echo(f"{StandardMessages.INFO_ICON} Configuration Summary:")
        config_lines = StandardMessages.format_configuration_summary(dedup, anon, mask)
        for line in config_lines:
            typer.echo(f"  {line}")
            
        summary = ConsistentProcessor.get_configuration_summary(dedup, anon, mask)
        typer.echo(f"\n⚙️ {summary}")
        
    except ValueError as e:
        typer.echo(f"{StandardMessages.ERROR_ICON} {str(e)}", err=True)
        raise typer.Exit(1)


# Helper function for smart output path generation
def generate_output_path(input_path: Path) -> Path:
    """Generate smart output path (wrapper for ConsistentProcessor method)"""
    return ConsistentProcessor.generate_output_path(input_path)
