#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Standard Messages - Unified messages for GUI and CLI consistency

This module provides the StandardMessages class that ensures consistent
error messages, progress formats, and user communications across both
GUI and CLI interfaces.

Key Features:
- Standardized error messages
- Consistent progress indicators
- Unified result formatting
- Professional English messaging
- Functional emoji support
"""

from typing import List, Optional
from .pipeline.models import ProcessResult


class StandardMessages:
    """Standardized messages for GUI and CLI consistency
    
    This class provides all user-facing messages in a consistent format
    to ensure identical user experience across GUI and CLI interfaces.
    """
    
    # =========================================================================
    # Error Messages
    # =========================================================================
    NO_INPUT_SELECTED = "Please select an input file or directory"
    NO_OPTIONS_SELECTED = "At least one processing option must be enabled"
    INVALID_FILE_TYPE = "Input file must be a PCAP or PCAPNG file"
    INPUT_NOT_FOUND = "Input path does not exist"
    OUTPUT_PATH_ERROR = "Unable to create output path"
    CONFIGURATION_ERROR = "Configuration validation failed"
    PROCESSING_ERROR = "Processing operation failed"
    PERMISSION_ERROR = "Insufficient permissions to access file"
    DISK_SPACE_ERROR = "Insufficient disk space for processing"
    
    # =========================================================================
    # Progress Messages
    # =========================================================================
    PROCESSING_START = "🚀 Processing started..."
    PROCESSING_COMPLETE = "✅ Processing completed successfully"
    PROCESSING_FAILED = "❌ Processing failed"
    PROCESSING_STOPPED = "⏹️ Processing stopped by user"
    PROCESSING_PAUSED = "⏸️ Processing paused"
    
    # Stage-specific messages
    STAGE_DEDUP_START = "⚙️ Starting Remove Dupes stage..."
    STAGE_ANON_START = "⚙️ Starting Anonymize IPs stage..."
    STAGE_MASK_START = "⚙️ Starting Mask Payloads stage..."
    
    STAGE_DEDUP_COMPLETE = "✅ Remove Dupes stage completed"
    STAGE_ANON_COMPLETE = "✅ Anonymize IPs stage completed"
    STAGE_MASK_COMPLETE = "✅ Mask Payloads stage completed"
    
    # =========================================================================
    # Status Indicators
    # =========================================================================
    SUCCESS_ICON = "✅"
    ERROR_ICON = "❌"
    WARNING_ICON = "⚠️"
    INFO_ICON = "ℹ️"
    PROCESSING_ICON = "⚙️"
    START_ICON = "🚀"
    STOP_ICON = "⏹️"
    PAUSE_ICON = "⏸️"
    
    # =========================================================================
    # Configuration Messages
    # =========================================================================
    CONFIG_DEDUP_ENABLED = "Remove Dupes: Enabled"
    CONFIG_ANON_ENABLED = "Anonymize IPs: Enabled"
    CONFIG_MASK_ENABLED = "Mask Payloads: Enabled"
    
    CONFIG_DEDUP_DISABLED = "Remove Dupes: Disabled"
    CONFIG_ANON_DISABLED = "Anonymize IPs: Disabled"
    CONFIG_MASK_DISABLED = "Mask Payloads: Disabled"
    
    # =========================================================================
    # File Operation Messages
    # =========================================================================
    FILE_PROCESSING_START = "📁 Processing file: {filename}"
    FILE_PROCESSING_COMPLETE = "✅ File processed: {filename}"
    FILE_PROCESSING_FAILED = "❌ File failed: {filename}"
    FILE_SKIPPED = "⏭️ File skipped: {filename}"
    
    DIRECTORY_PROCESSING_START = "📂 Processing directory: {dirname}"
    DIRECTORY_PROCESSING_COMPLETE = "✅ Directory processed: {dirname}"
    
    # =========================================================================
    # Statistics Messages
    # =========================================================================
    STATS_FILES_PROCESSED = "Files processed: {count}"
    STATS_FILES_FAILED = "Files failed: {count}"
    STATS_TOTAL_DURATION = "Total duration: {duration:.2f}s"
    STATS_PACKETS_PROCESSED = "Packets processed: {count:,}"
    STATS_PACKETS_MODIFIED = "Packets modified: {count:,}"
    STATS_SIZE_REDUCTION = "Size reduction: {percentage:.1f}%"
    
    @staticmethod
    def format_result_summary(result: ProcessResult) -> str:
        """Unified result summary format for both GUI and CLI
        
        Args:
            result: ProcessResult from pipeline execution
            
        Returns:
            Formatted summary string
        """
        if result.success:
            duration = result.duration_ms / 1000
            stages = len(result.stage_stats)
            return f"{StandardMessages.SUCCESS_ICON} Processed {stages} stages in {duration:.2f}s"
        else:
            errors = "; ".join(result.errors)
            return f"{StandardMessages.ERROR_ICON} Processing failed: {errors}"
    
    @staticmethod
    def format_stage_progress(stage_name: str, packets_processed: int, 
                            packets_modified: int) -> str:
        """Unified stage progress format
        
        Args:
            stage_name: Name of the processing stage
            packets_processed: Total packets processed
            packets_modified: Number of packets modified
            
        Returns:
            Formatted progress string
        """
        return f"{StandardMessages.PROCESSING_ICON} [{stage_name}] {packets_processed:,} packets, {packets_modified:,} modified"
    
    @staticmethod
    def format_file_progress(filename: str, current: int, total: int) -> str:
        """Format file processing progress
        
        Args:
            filename: Name of file being processed
            current: Current file number
            total: Total number of files
            
        Returns:
            Formatted progress string
        """
        return f"📁 [{current}/{total}] Processing: {filename}"
    
    @staticmethod
    def format_configuration_summary(dedup: bool, anon: bool, mask: bool) -> List[str]:
        """Format configuration summary
        
        Args:
            dedup: Remove Dupes enabled
            anon: Anonymize IPs enabled
            mask: Mask Payloads enabled
            
        Returns:
            List of configuration status messages
        """
        config_lines = []
        
        config_lines.append(
            StandardMessages.CONFIG_DEDUP_ENABLED if dedup 
            else StandardMessages.CONFIG_DEDUP_DISABLED
        )
        config_lines.append(
            StandardMessages.CONFIG_ANON_ENABLED if anon 
            else StandardMessages.CONFIG_ANON_DISABLED
        )
        config_lines.append(
            StandardMessages.CONFIG_MASK_ENABLED if mask 
            else StandardMessages.CONFIG_MASK_DISABLED
        )
        
        return config_lines
    
    @staticmethod
    def format_error_with_context(error_message: str, context: Optional[str] = None) -> str:
        """Format error message with optional context
        
        Args:
            error_message: The error message
            context: Optional context information
            
        Returns:
            Formatted error string
        """
        if context:
            return f"{StandardMessages.ERROR_ICON} {error_message} (Context: {context})"
        else:
            return f"{StandardMessages.ERROR_ICON} {error_message}"
    
    @staticmethod
    def format_warning_with_context(warning_message: str, context: Optional[str] = None) -> str:
        """Format warning message with optional context
        
        Args:
            warning_message: The warning message
            context: Optional context information
            
        Returns:
            Formatted warning string
        """
        if context:
            return f"{StandardMessages.WARNING_ICON} {warning_message} (Context: {context})"
        else:
            return f"{StandardMessages.WARNING_ICON} {warning_message}"
    
    @staticmethod
    def format_info_with_context(info_message: str, context: Optional[str] = None) -> str:
        """Format info message with optional context
        
        Args:
            info_message: The info message
            context: Optional context information
            
        Returns:
            Formatted info string
        """
        if context:
            return f"{StandardMessages.INFO_ICON} {info_message} (Context: {context})"
        else:
            return f"{StandardMessages.INFO_ICON} {info_message}"


class MessageFormatter:
    """Helper class for advanced message formatting"""
    
    @staticmethod
    def format_duration(duration_ms: float) -> str:
        """Format duration in human-readable format
        
        Args:
            duration_ms: Duration in milliseconds
            
        Returns:
            Formatted duration string
        """
        if duration_ms < 1000:
            return f"{duration_ms:.0f}ms"
        elif duration_ms < 60000:
            return f"{duration_ms/1000:.1f}s"
        else:
            minutes = int(duration_ms // 60000)
            seconds = (duration_ms % 60000) / 1000
            return f"{minutes}m {seconds:.1f}s"
    
    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        """Format file size in human-readable format
        
        Args:
            size_bytes: Size in bytes
            
        Returns:
            Formatted size string
        """
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"
    
    @staticmethod
    def format_percentage(value: float, total: float) -> str:
        """Format percentage with proper handling of edge cases
        
        Args:
            value: The value
            total: The total
            
        Returns:
            Formatted percentage string
        """
        if total == 0:
            return "0.0%"
        percentage = (value / total) * 100
        return f"{percentage:.1f}%"
