"""
IP Anonymization Processor

Directly implements IP anonymization functionality, not dependent on Legacy Steps.
"""
import os
from typing import Optional
from pathlib import Path

from .base_processor import BaseProcessor, ProcessorConfig, ProcessorResult
from ...core.strategy import HierarchicalAnonymizationStrategy
from ...utils.reporting import FileReporter
from ...infrastructure.logging import get_logger


class IPAnonymizer(BaseProcessor):
    """IP anonymization processor

    Directly uses HierarchicalAnonymizationStrategy to implement IP anonymization functionality.
    """
    
    def __init__(self, config: ProcessorConfig):
        super().__init__(config)
        self._logger = get_logger('ip_anonymizer')
        self._strategy: Optional[HierarchicalAnonymizationStrategy] = None
        self._reporter: Optional[FileReporter] = None
        
    def _initialize_impl(self):
        """Initialize IP anonymization components"""
        try:
            # Create strategy and reporter
            self._strategy = HierarchicalAnonymizationStrategy()
            self._reporter = FileReporter()
            
            self._logger.info("IP anonymization processor initialization successful")
            
        except Exception as e:
            self._logger.error(f"IP anonymization processor initialization failed: {e}")
            raise
            
    def process_file(self, input_path: str, output_path: str) -> ProcessorResult:
        """处理单个文件的IP匿名化"""
        if not self._is_initialized:
            if not self.initialize():
                return ProcessorResult(
                    success=False, 
                    error="处理器未正确初始化"
                )
        
        try:
            # Validate inputs
            self.validate_inputs(input_path, output_path)

            # Reset statistics
            self.reset_stats()

            self._logger.info(f"Starting IP anonymization: {input_path} -> {output_path}")

            # Use Scapy to process PCAP file
            from scapy.all import rdpcap, wrpcap
            import time

            start_time = time.time()

            # Read packets
            packets = rdpcap(input_path)
            total_packets = len(packets)

            # **Key fix**: Build IP mapping table first
            self._logger.info("Analyzing IP addresses in file and building mapping table...")
            self._strategy.build_mapping_from_directory([input_path])
            ip_mappings = self._strategy.get_ip_map()
            self._logger.info(f"IP mapping construction completed: {len(ip_mappings)} IP addresses")

            # Start anonymizing packets
            self._logger.info("Starting packet anonymization")
            anonymized_packets = 0
            
            # Process each packet
            anonymized_pkts = []
            for packet in packets:
                modified_packet, was_modified = self._strategy.anonymize_packet(packet)
                anonymized_pkts.append(modified_packet)
                if was_modified:
                    anonymized_packets += 1

            # Save anonymized packets
            if anonymized_pkts:
                wrpcap(output_path, anonymized_pkts)
            else:
                # If no packets, create empty file
                open(output_path, 'a').close()

            processing_time = time.time() - start_time

            # Build result data
            ip_mappings = self._strategy.get_ip_map()
            result_data = {
                'total_packets': total_packets,
                'anonymized_packets': anonymized_packets,
                'original_ips': len([ip for ip in ip_mappings.keys()]),
                'anonymized_ips': len([ip for ip in ip_mappings.values()]),
                'file_ip_mappings': ip_mappings,
                'processing_time': processing_time
            }

            if result_data is None:
                return ProcessorResult(
                    success=False,
                    error="IP anonymization processing failed, no result returned"
                )

            # Update statistics
            self.stats.update({
                'original_ips': result_data.get('original_ips', 0),
                'anonymized_ips': result_data.get('anonymized_ips', 0),
                'total_packets': result_data.get('total_packets', 0),
                'anonymized_packets': result_data.get('anonymized_packets', 0),
                'ip_mappings': result_data.get('file_ip_mappings', {}),
                'anonymization_rate': self._calculate_anonymization_rate(result_data)
            })

            self._logger.info(
                f"IP anonymization completed: {result_data.get('anonymized_ips', 0)} IPs anonymized"
            )
            
            return ProcessorResult(
                success=True,
                data=result_data,
                stats=self.stats
            )
            
        except FileNotFoundError as e:
            error_msg = f"File not found: {e}"
            self._logger.error(error_msg)
            return ProcessorResult(success=False, error=error_msg)

        except Exception as e:
            error_msg = f"IP anonymization processing failed: {e}"
            self._logger.error(error_msg)
            return ProcessorResult(success=False, error=error_msg)
    
    def get_display_name(self) -> str:
        """Get processor display name"""
        return "Anonymize IPs"

    def get_description(self) -> str:
        """Get processor description"""
        return "Anonymize IP addresses in packets while maintaining subnet structure consistency"

    def _calculate_anonymization_rate(self, result_data: dict) -> float:
        """Calculate anonymization rate"""
        original_ips = result_data.get('original_ips', 0)
        anonymized_ips = result_data.get('anonymized_ips', 0)

        if original_ips == 0:
            return 0.0

        return (anonymized_ips / original_ips) * 100.0

    def get_ip_mappings(self) -> dict:
        """Get IP mapping table"""
        if self._strategy:
            return self._strategy.get_ip_map()
        return {}

    def prepare_for_directory(self, directory_path: str, pcap_files: list):
        """Prepare IP mapping for directory processing"""
        if not self._is_initialized:
            if not self.initialize():
                raise RuntimeError("Processor initialization failed")

        self._logger.info(f"Preparing IP mapping for directory: {directory_path}")
        # Use strategy's build_mapping_from_directory method to build IP mapping
        self._strategy.build_mapping_from_directory(pcap_files)
        
    def finalize_directory_processing(self) -> Optional[dict]:
        """Complete directory processing"""
        if self._strategy:
            return {
                'total_ip_mappings': len(self._strategy.get_ip_map()),
                'ip_mappings': self._strategy.get_ip_map()
            }
        return None 