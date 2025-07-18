"""
IP Anonymization Stage - StageBase Architecture Implementation

This module provides a StageBase-compatible wrapper for the existing IPAnonymizer
processor, enabling unified architecture while maintaining full backward compatibility.
"""

from __future__ import annotations

import time
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Union

from pktmask.core.pipeline.base_stage import StageBase
from pktmask.core.pipeline.models import StageStats
from pktmask.core.processors.ip_anonymizer import IPAnonymizer
from pktmask.core.processors.base_processor import ProcessorConfig, ProcessorResult


class IPAnonymizationStage(StageBase):
    """IP Anonymization Stage - StageBase Architecture Implementation
    
    This stage wraps the existing IPAnonymizer processor to provide a unified
    StageBase interface while maintaining full functional compatibility.
    
    Features:
    - Full backward compatibility with existing IPAnonymizer functionality
    - Unified StageBase interface for pipeline integration
    - Automatic configuration conversion from dict to ProcessorConfig
    - Complete preservation of IP mapping and anonymization logic
    """
    
    name: str = "IPAnonymizationStage"
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize IP Anonymization Stage
        
        Args:
            config: Configuration dictionary with the following optional parameters:
                - method: Anonymization method (default: "prefix_preserving")
                - ipv4_prefix: IPv4 prefix length (default: 24)
                - ipv6_prefix: IPv6 prefix length (default: 64)
                - enabled: Whether the stage is enabled (default: True)
                - name: Stage name (default: "ip_anonymization")
        """
        super().__init__()
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        
        # Store original configuration
        self.config = config.copy()
        
        # Extract configuration parameters with defaults
        self.method = config.get('method', 'prefix_preserving')
        self.ipv4_prefix = config.get('ipv4_prefix', 24)
        self.ipv6_prefix = config.get('ipv6_prefix', 64)
        self.enabled = config.get('enabled', True)
        self.stage_name = config.get('name', 'ip_anonymization')
        
        # Internal IPAnonymizer instance (lazy initialization)
        self._anonymizer: Optional[IPAnonymizer] = None
        
        self.logger.info(f"IPAnonymizationStage created: method={self.method}, "
                        f"ipv4_prefix={self.ipv4_prefix}, ipv6_prefix={self.ipv6_prefix}")
    
    def initialize(self, config: Optional[Dict] = None) -> None:
        """Initialize the IP anonymization stage
        
        Args:
            config: Optional configuration parameters to update
        """
        if self._initialized:
            return
        
        try:
            self.logger.info("Starting IPAnonymizationStage initialization")
            
            # Update configuration if provided
            if config:
                self.config.update(config)
                self.method = self.config.get('method', self.method)
                self.ipv4_prefix = self.config.get('ipv4_prefix', self.ipv4_prefix)
                self.ipv6_prefix = self.config.get('ipv6_prefix', self.ipv6_prefix)
            
            # Create ProcessorConfig for IPAnonymizer
            processor_config = ProcessorConfig(
                enabled=self.enabled,
                name=self.stage_name,
                priority=0
            )
            
            # Create and initialize IPAnonymizer
            self._anonymizer = IPAnonymizer(processor_config)
            if not self._anonymizer.initialize():
                raise RuntimeError("IPAnonymizer initialization failed")
            
            self._initialized = True
            self.logger.info("IPAnonymizationStage initialization successful")
            
            # Call parent initialization
            super().initialize(config)
            
        except Exception as e:
            self.logger.error(f"IPAnonymizationStage initialization failed: {e}")
            raise
    
    def prepare_for_directory(self, directory: str | Path, all_files: list[str]) -> None:
        """Prepare for directory-level processing
        
        This method is called before processing files in a directory to build
        the IP mapping table for consistent anonymization across all files.
        
        Args:
            directory: Directory path containing the files
            all_files: List of all files to be processed in the directory
        """
        if not self._initialized:
            self.initialize()
        
        if not self._anonymizer:
            raise RuntimeError("IPAnonymizer not initialized")
        
        self.logger.info(f"Preparing IP mapping for directory: {directory}")
        self.logger.info(f"Files to process: {len(all_files)}")
        
        # Use IPAnonymizer's directory preparation method
        self._anonymizer.prepare_for_directory(str(directory), all_files)
        
        # Log IP mapping statistics
        ip_mappings = self._anonymizer.get_ip_mappings()
        self.logger.info(f"IP mapping prepared: {len(ip_mappings)} unique IP addresses")
    
    def process_file(self, input_path: Union[str, Path], 
                    output_path: Union[str, Path]) -> StageStats:
        """Process a single file for IP anonymization
        
        Args:
            input_path: Input file path
            output_path: Output file path
            
        Returns:
            StageStats: Processing statistics
            
        Raises:
            FileNotFoundError: If input file doesn't exist
            ValueError: If input path is not a file
            RuntimeError: If stage is not initialized
        """
        if not self._initialized:
            self.initialize()
            if not self._initialized:
                raise RuntimeError("IPAnonymizationStage not initialized")
        
        if not self._anonymizer:
            raise RuntimeError("IPAnonymizer not initialized")
        
        # Validate input parameters
        input_path = Path(input_path)
        output_path = Path(output_path)
        
        if not input_path.exists():
            raise FileNotFoundError(f"Input file does not exist: {input_path}")
        if not input_path.is_file():
            raise ValueError(f"Input path is not a file: {input_path}")
        
        self.logger.info(f"Starting IP anonymization: {input_path} -> {output_path}")
        
        start_time = time.time()
        
        try:
            # Call IPAnonymizer to process the file
            result: ProcessorResult = self._anonymizer.process_file(str(input_path), str(output_path))
            
            # Calculate processing duration
            duration_ms = (time.time() - start_time) * 1000
            
            # Convert ProcessorResult to StageStats
            stage_stats = self._convert_processor_result_to_stage_stats(result, duration_ms)
            
            self.logger.info(f"IP anonymization completed successfully in {duration_ms:.2f}ms")
            return stage_stats
            
        except Exception as e:
            self.logger.error(f"IP anonymization failed: {e}")
            raise
    
    def finalize_directory_processing(self) -> Optional[Dict]:
        """Finalize directory processing and return summary information
        
        Returns:
            Optional[Dict]: Summary information about the directory processing
        """
        if not self._anonymizer:
            return None
        
        # Get final IP mapping statistics
        ip_mappings = self._anonymizer.get_ip_mappings()
        
        summary = {
            'total_unique_ips': len(ip_mappings),
            'ip_mappings': ip_mappings,
            'anonymization_method': self.method,
            'ipv4_prefix': self.ipv4_prefix,
            'ipv6_prefix': self.ipv6_prefix
        }
        
        self.logger.info(f"Directory processing completed: {len(ip_mappings)} unique IPs anonymized")
        return summary
    
    def get_required_tools(self) -> list[str]:
        """Get list of required external tools
        
        Returns:
            list[str]: Empty list (no external tools required)
        """
        return []
    
    def stop(self) -> None:
        """Stop the stage processing
        
        This method can be called to gracefully stop the processing.
        """
        self.logger.info("IPAnonymizationStage stop requested")
        # No special cleanup needed for IP anonymization
    
    def _convert_processor_result_to_stage_stats(self, result: ProcessorResult, 
                                               duration_ms: float) -> StageStats:
        """Convert ProcessorResult to StageStats format
        
        Args:
            result: ProcessorResult from IPAnonymizer
            duration_ms: Processing duration in milliseconds
            
        Returns:
            StageStats: Converted statistics
        """
        if not result.success:
            # Handle failure case
            return StageStats(
                stage_name=self.name,
                packets_processed=0,
                packets_modified=0,
                duration_ms=duration_ms,
                extra_metrics={
                    'success': False,
                    'error': result.error,
                    'method': self.method,
                    'ipv4_prefix': self.ipv4_prefix,
                    'ipv6_prefix': self.ipv6_prefix
                }
            )
        
        # Extract statistics from successful result
        stats = result.stats or {}
        data = result.data or {}
        
        return StageStats(
            stage_name=self.name,
            packets_processed=stats.get('total_packets', 0),
            packets_modified=stats.get('anonymized_packets', 0),
            duration_ms=duration_ms,
            extra_metrics={
                'success': True,
                'original_ips': stats.get('original_ips', 0),
                'anonymized_ips': stats.get('anonymized_ips', 0),
                'anonymization_rate': stats.get('anonymization_rate', 0.0),
                'method': self.method,
                'ipv4_prefix': self.ipv4_prefix,
                'ipv6_prefix': self.ipv6_prefix,
                'processing_time': data.get('processing_time', 0.0),
                'ip_mappings_count': len(stats.get('ip_mappings', {})),
                # Include all original stats for compatibility
                **stats
            }
        )
    
    def get_display_name(self) -> str:
        """Get user-friendly display name
        
        Returns:
            str: Display name for GUI/CLI
        """
        return "Anonymize IPs"
    
    def get_description(self) -> str:
        """Get stage description
        
        Returns:
            str: Detailed description of the stage functionality
        """
        return ("Anonymize IP addresses in packets while maintaining subnet structure consistency. "
                f"Uses {self.method} method with IPv4/{self.ipv4_prefix} and IPv6/{self.ipv6_prefix} prefixes.")
