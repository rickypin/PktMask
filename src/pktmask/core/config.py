#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Unified Configuration - Standardized configuration model and validation

This module provides unified configuration handling with standardized parameter
names and consistent validation logic across GUI and CLI interfaces.

Key Features:
- Standardized parameter naming (dedup, anon, mask)
- Unified validation logic
- Configuration conversion utilities
- Backward compatibility adapters
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from pathlib import Path


@dataclass
class UnifiedConfig:
    """Unified configuration model with standardized parameter names
    
    This class uses the standardized naming conventions:
    - dedup: Remove Dupes processing
    - anon: Anonymize IPs processing  
    - mask: Mask Payloads processing
    """
    
    # Core processing options
    dedup: bool = False
    anon: bool = False
    mask: bool = False
    
    # Mask-specific options
    mask_protocol: str = "tls"
    preserve_handshake: bool = True
    preserve_alert: bool = True
    preserve_change_cipher_spec: bool = True
    preserve_heartbeat: bool = True
    preserve_application_data: bool = False
    
    # Input/Output paths
    input_path: Optional[Path] = None
    output_path: Optional[Path] = None
    
    # Advanced options
    tshark_path: Optional[str] = None
    verbose: bool = False
    
    def to_pipeline_config(self) -> Dict[str, Any]:
        """Convert to PipelineExecutor configuration format

        Returns:
            Dictionary configuration for PipelineExecutor
        """
        config = {}

        if self.dedup:
            config["remove_dupes"] = {"enabled": True}

        if self.anon:
            config["anonymize_ips"] = {"enabled": True}

        if self.mask:
            config["mask_payloads"] = {
                "enabled": True,
                "protocol": self.mask_protocol,
                "mode": "enhanced",  # Always use enhanced mode
                "marker_config": {
                    "preserve": {
                        "application_data": self.preserve_application_data,
                        "handshake": self.preserve_handshake,
                        "alert": self.preserve_alert,
                        "change_cipher_spec": self.preserve_change_cipher_spec,
                        "heartbeat": self.preserve_heartbeat,
                    }
                },
                "masker_config": {"chunk_size": 1000, "verify_checksums": True},
            }

        return config
    
    def has_any_processing_enabled(self) -> bool:
        """Check if any processing option is enabled
        
        Returns:
            True if at least one processing option is enabled
        """
        return any([self.dedup, self.anon, self.mask])
    
    def get_enabled_options(self) -> List[str]:
        """Get list of enabled processing options
        
        Returns:
            List of enabled option names
        """
        enabled = []
        if self.dedup:
            enabled.append("dedup")
        if self.anon:
            enabled.append("anon")
        if self.mask:
            enabled.append("mask")
        return enabled
    
    def get_summary(self) -> str:
        """Get human-readable configuration summary
        
        Returns:
            Configuration summary string
        """
        enabled = self.get_enabled_options()
        if not enabled:
            return "No processing options enabled"
        return f"Enabled: {', '.join(enabled)}"


class ConfigValidator:
    """Unified configuration validation logic"""
    
    @staticmethod
    def validate_config(config: UnifiedConfig) -> List[str]:
        """Validate unified configuration
        
        Args:
            config: Configuration to validate
            
        Returns:
            List of validation error messages (empty if valid)
        """
        from .messages import StandardMessages
        
        errors = []
        
        # Check that at least one processing option is enabled
        if not config.has_any_processing_enabled():
            errors.append(StandardMessages.NO_OPTIONS_SELECTED)
        
        # Validate input path if provided
        if config.input_path:
            if not config.input_path.exists():
                errors.append(StandardMessages.INPUT_NOT_FOUND)
            elif config.input_path.is_file():
                if not config.input_path.suffix.lower() in ['.pcap', '.pcapng']:
                    errors.append(StandardMessages.INVALID_FILE_TYPE)
        
        # Validate mask protocol
        if config.mask and config.mask_protocol not in ["tls", "tcp", "all"]:
            errors.append("Invalid mask protocol. Must be 'tls', 'tcp', or 'all'")
        
        # Validate tshark path if provided
        if config.tshark_path:
            tshark_path = Path(config.tshark_path)
            if not tshark_path.exists():
                errors.append(f"TShark path not found: {config.tshark_path}")
        
        return errors
    
    @staticmethod
    def validate_processing_options(dedup: bool, anon: bool, mask: bool) -> None:
        """Quick validation for processing options
        
        Args:
            dedup: Remove Dupes enabled
            anon: Anonymize IPs enabled
            mask: Mask Payloads enabled
            
        Raises:
            ValueError: If validation fails
        """
        from .messages import StandardMessages
        
        if not any([dedup, anon, mask]):
            raise ValueError(StandardMessages.NO_OPTIONS_SELECTED)


class ConfigConverter:
    """Utilities for converting between configuration formats"""
    
    @staticmethod
    def from_gui_checkboxes(remove_dupes_checked: bool, 
                           anonymize_ips_checked: bool,
                           mask_payloads_checked: bool) -> UnifiedConfig:
        """Convert from GUI checkbox states to unified config
        
        Args:
            remove_dupes_checked: Remove Dupes checkbox state
            anonymize_ips_checked: Anonymize IPs checkbox state
            mask_payloads_checked: Mask Payloads checkbox state
            
        Returns:
            UnifiedConfig instance
        """
        return UnifiedConfig(
            dedup=remove_dupes_checked,
            anon=anonymize_ips_checked,
            mask=mask_payloads_checked
        )
    
    @staticmethod
    def from_cli_args(dedup: bool, anon: bool, mask: bool, 
                     input_path: Optional[Path] = None,
                     output_path: Optional[Path] = None,
                     verbose: bool = False) -> UnifiedConfig:
        """Convert from CLI arguments to unified config
        
        Args:
            dedup: Remove Dupes enabled
            anon: Anonymize IPs enabled
            mask: Mask Payloads enabled
            input_path: Input file/directory path
            output_path: Output path
            verbose: Verbose output enabled
            
        Returns:
            UnifiedConfig instance
        """
        return UnifiedConfig(
            dedup=dedup,
            anon=anon,
            mask=mask,
            input_path=input_path,
            output_path=output_path,
            verbose=verbose
        )
    
    @staticmethod
    def to_legacy_gui_format(config: UnifiedConfig) -> Dict[str, bool]:
        """Convert to legacy GUI format for backward compatibility
        
        Args:
            config: UnifiedConfig instance
            
        Returns:
            Dictionary with legacy GUI parameter names
        """
        return {
            'remove_dupes_checked': config.dedup,
            'anonymize_ips_checked': config.anon,
            'mask_payloads_checked': config.mask
        }
    
    @staticmethod
    def to_legacy_cli_format(config: UnifiedConfig) -> Dict[str, Any]:
        """Convert to legacy CLI format for backward compatibility
        
        Args:
            config: UnifiedConfig instance
            
        Returns:
            Dictionary with legacy CLI parameter names
        """
        return {
            'remove_dupes': config.dedup,
            'anonymize_ips': config.anon,
            'mask_payloads': config.mask,
            'input_path': config.input_path,
            'output_path': config.output_path,
            'verbose': config.verbose
        }


class BackwardCompatibilityAdapter:
    """Temporary adapter for migration period"""
    
    @staticmethod
    def adapt_legacy_gui_config(legacy_config: Dict[str, Any]) -> UnifiedConfig:
        """Convert legacy GUI configuration to unified format
        
        Args:
            legacy_config: Legacy configuration dictionary
            
        Returns:
            UnifiedConfig instance
        """
        mapping = {
            'remove_dupes_checked': 'dedup',
            'anonymize_ips_checked': 'anon', 
            'mask_payloads_checked': 'mask'
        }
        
        unified_params = {}
        for legacy_key, unified_key in mapping.items():
            if legacy_key in legacy_config:
                unified_params[unified_key] = legacy_config[legacy_key]
        
        return UnifiedConfig(**unified_params)
    
    @staticmethod
    def adapt_legacy_cli_args(legacy_args: Dict[str, Any]) -> UnifiedConfig:
        """Convert legacy CLI arguments to unified format
        
        Args:
            legacy_args: Legacy arguments dictionary
            
        Returns:
            UnifiedConfig instance
        """
        mapping = {
            'remove_dupes': 'dedup',
            'anonymize_ips': 'anon',
            'mask_payloads': 'mask'
        }
        
        unified_params = {}
        for legacy_key, unified_key in mapping.items():
            if legacy_key in legacy_args:
                unified_params[unified_key] = legacy_args[legacy_key]
        
        # Copy other parameters directly
        for key in ['input_path', 'output_path', 'verbose']:
            if key in legacy_args:
                unified_params[key] = legacy_args[key]
        
        return UnifiedConfig(**unified_params)
