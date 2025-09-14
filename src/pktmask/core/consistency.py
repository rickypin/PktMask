#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Core Consistency Layer - Unified processor ensuring GUI-CLI consistency

This module provides the ConsistentProcessor class that serves as the unified
interface for both GUI and CLI processing, eliminating service layer dependencies
and ensuring identical processing results across interfaces.

Key Features:
- Standardized parameter naming (dedup, anon, mask)
- Unified configuration creation and validation
- Consistent error handling and messaging
- Direct PipelineExecutor integration
"""

from typing import Optional
from pathlib import Path
from .pipeline.executor import PipelineExecutor
from .pipeline.models import ProcessResult


class ConsistentProcessor:
    """Unified processor ensuring GUI-CLI consistency
    
    This class provides the core interface that both GUI and CLI use to ensure
    identical processing logic and results. It eliminates the service layer
    abstraction and provides direct access to PipelineExecutor functionality.
    """

    @staticmethod
    def create_executor(
        dedup: bool,
        anon: bool,
        mask: bool,
        mask_protocol: str = "auto",
    ) -> PipelineExecutor:
        """Create executor with standardized configuration
        
        Args:
            dedup: Enable Remove Dupes processing
            anon: Enable Anonymize IPs processing  
            mask: Enable Mask Payloads processing
            
        Returns:
            PipelineExecutor configured with specified options
            
        Raises:
            ValueError: If no processing options are enabled
        """
        # Import here to avoid circular imports
        from .messages import StandardMessages
        
        # Validate that at least one option is enabled
        if not any([dedup, anon, mask]):
            raise ValueError(StandardMessages.NO_OPTIONS_SELECTED)
        
        # Build configuration using PipelineExecutor expected keys
        config = {}

        if dedup:
            config["remove_dupes"] = {"enabled": True}

        if anon:
            config["anonymize_ips"] = {"enabled": True}

        if mask:
            config["mask_payloads"] = {
                "enabled": True,
                "protocol": mask_protocol or "auto",
                "mode": "enhanced",  # Always use enhanced mode
                "marker_config": {
                    "preserve": {
                        "application_data": False,
                        "handshake": True,
                        "alert": True,
                        "change_cipher_spec": True,
                        "heartbeat": True,
                    }
                },
                "masker_config": {"chunk_size": 1000, "verify_checksums": True},
            }
        
        return PipelineExecutor(config)

    @staticmethod
    def validate_options(dedup: bool, anon: bool, mask: bool) -> None:
        """Unified validation for both GUI and CLI
        
        Args:
            dedup: Enable Remove Dupes processing
            anon: Enable Anonymize IPs processing
            mask: Enable Mask Payloads processing
            
        Raises:
            ValueError: If validation fails
        """
        from .messages import StandardMessages
        
        if not any([dedup, anon, mask]):
            raise ValueError(StandardMessages.NO_OPTIONS_SELECTED)

    @staticmethod
    def process_file(
        input_path: Path,
        output_path: Path,
        dedup: bool,
        anon: bool,
        mask: bool,
        mask_protocol: str = "auto",
    ) -> ProcessResult:
        """Unified file processing for both interfaces
        
        Args:
            input_path: Input PCAP/PCAPNG file path
            output_path: Output file path
            dedup: Enable Remove Dupes processing
            anon: Enable Anonymize IPs processing
            mask: Enable Mask Payloads processing
            
        Returns:
            ProcessResult with processing outcome and statistics
            
        Raises:
            ValueError: If validation fails
            FileNotFoundError: If input file doesn't exist
        """
        from .messages import StandardMessages
        
        # Validate input exists
        if not input_path.exists():
            raise FileNotFoundError(StandardMessages.INPUT_NOT_FOUND)
            
        # Validate file type
        if not input_path.suffix.lower() in ['.pcap', '.pcapng']:
            raise ValueError(StandardMessages.INVALID_FILE_TYPE)
        
        # Validate options
        ConsistentProcessor.validate_options(dedup, anon, mask)
        
        # Create executor and process
        executor = ConsistentProcessor.create_executor(dedup, anon, mask, mask_protocol)
        return executor.run(input_path, output_path)

    @staticmethod
    def get_configuration_summary(
        dedup: bool, anon: bool, mask: bool, mask_protocol: str = "auto"
    ) -> str:
        """Get human-readable configuration summary
        
        Args:
            dedup: Enable Remove Dupes processing
            anon: Enable Anonymize IPs processing
            mask: Enable Mask Payloads processing
            
        Returns:
            String describing enabled processing options
        """
        enabled_options = []
        
        if dedup:
            enabled_options.append("Remove Dupes")
        if anon:
            enabled_options.append("Anonymize IPs")
        if mask:
            enabled_options.append(
                "Mask Payloads" + (f" (protocol: {mask_protocol})" if mask_protocol else "")
            )
            
        if not enabled_options:
            return "No processing options enabled"
            
        return f"Enabled: {', '.join(enabled_options)}"

    @staticmethod
    def validate_input_path(input_path: Path) -> None:
        """Validate input path for processing
        
        Args:
            input_path: Path to validate
            
        Raises:
            FileNotFoundError: If path doesn't exist
            ValueError: If path is not a valid PCAP/PCAPNG file
        """
        from .messages import StandardMessages
        
        if not input_path.exists():
            raise FileNotFoundError(StandardMessages.INPUT_NOT_FOUND)
            
        if input_path.is_file():
            if not input_path.suffix.lower() in ['.pcap', '.pcapng']:
                raise ValueError(StandardMessages.INVALID_FILE_TYPE)
        elif not input_path.is_dir():
            raise ValueError("Input path must be a file or directory")

    @staticmethod
    def generate_output_path(input_path: Path, suffix: str = "_processed") -> Path:
        """Generate smart output path based on input

        Args:
            input_path: Input file or directory path
            suffix: Suffix to add to output name

        Returns:
            Generated output path
        """
        # Check if path has a file extension (indicating it's a file)
        if input_path.suffix:
            return input_path.parent / f"{input_path.stem}{suffix}{input_path.suffix}"
        else:
            return input_path.parent / f"{input_path.name}{suffix}"


class ConfigurationError(Exception):
    """Exception raised for configuration-related errors"""
    pass


class ProcessingError(Exception):
    """Exception raised for processing-related errors"""
    pass
