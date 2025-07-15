"""
Deduplication processor

Directly implements deduplication functionality without relying on Legacy Steps.
"""
import os
from typing import Optional, Set, Dict
import hashlib
import time

from .base_processor import BaseProcessor, ProcessorConfig, ProcessorResult
from ...infrastructure.logging import get_logger

try:
    from scapy.all import rdpcap, wrpcap, Packet
except ImportError:
    rdpcap = wrpcap = Packet = None


class DeduplicationProcessor(BaseProcessor):
    """Deduplication processor

    Directly implements packet deduplication functionality.
    """
    
    def __init__(self, config: ProcessorConfig):
        super().__init__(config)
        self._logger = get_logger('deduplicator')
        self._packet_hashes: Set[str] = set()
        
    def _initialize_impl(self):
        """Initialize deduplication components"""
        try:
            if rdpcap is None:
                raise ImportError("Scapy library not installed, cannot perform deduplication")

            self._packet_hashes.clear()
            self._logger.info("Deduplication processor initialized successfully")

        except Exception as e:
            self._logger.error(f"Deduplication processor initialization failed: {e}")
            raise
            
    def process_file(self, input_path: str, output_path: str) -> ProcessorResult:
        """Process deduplication for a single file"""
        if not self._is_initialized:
            if not self.initialize():
                return ProcessorResult(
                    success=False,
                    error="Processor not properly initialized"
                )
        
        try:
            # Validate inputs
            self.validate_inputs(input_path, output_path)

            # Reset statistics
            self.reset_stats()

            self._logger.info(f"Starting deduplication: {input_path} -> {output_path}")
            
            start_time = time.time()
            
            # Read packets
            packets = rdpcap(input_path)
            total_packets = len(packets)

            # Deduplication processing
            unique_packets = []
            removed_count = 0

            for packet in packets:
                # Generate packet hash
                packet_hash = self._generate_packet_hash(packet)
                
                if packet_hash not in self._packet_hashes:
                    self._packet_hashes.add(packet_hash)
                    unique_packets.append(packet)
                else:
                    removed_count += 1
            
            # Save deduplicated packets
            if unique_packets:
                wrpcap(output_path, unique_packets)
            else:
                # If no unique packets, create empty file
                open(output_path, 'a').close()
            
            processing_time = time.time() - start_time
            
            # Build result data
            result_data = {
                'total_packets': total_packets,
                'unique_packets': len(unique_packets),
                'removed_count': removed_count,
                'processing_time': processing_time
            }

            # Update statistics
            self.stats.update({
                'total_packets': result_data.get('total_packets', 0),
                'unique_packets': result_data.get('unique_packets', 0),
                'removed_count': result_data.get('removed_count', 0),
                'deduplication_rate': self._calculate_deduplication_rate(result_data),
                'space_saved': self._calculate_space_saved(input_path, output_path)
            })
            
            removed_count = result_data.get('removed_count', 0)
            self._logger.info(f"Deduplication completed: removed {removed_count} duplicate packets")
            
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
            error_msg = f"Deduplication processing failed: {e}"
            self._logger.error(error_msg)
            return ProcessorResult(success=False, error=error_msg)
    
    def get_display_name(self) -> str:
        """Get user-friendly display name"""
        return "Remove Dupes"

    def get_description(self) -> str:
        """Get processor description"""
        return "Remove completely duplicate packets to reduce file size"
        
    def _calculate_deduplication_rate(self, result_data: dict) -> float:
        """Calculate deduplication rate"""
        total_packets = result_data.get('total_packets', 0)
        removed_count = result_data.get('removed_count', 0)
        
        if total_packets == 0:
            return 0.0
        
        return (removed_count / total_packets) * 100.0
        
    def _calculate_space_saved(self, input_path: str, output_path: str) -> dict:
        """Calculate space saved"""
        try:
            if not os.path.exists(input_path) or not os.path.exists(output_path):
                return {'input_size': 0, 'output_size': 0, 'saved_bytes': 0, 'saved_percentage': 0.0}
            
            input_size = os.path.getsize(input_path)
            output_size = os.path.getsize(output_path)
            saved_bytes = input_size - output_size
            saved_percentage = (saved_bytes / input_size * 100.0) if input_size > 0 else 0.0
            
            return {
                'input_size': input_size,
                'output_size': output_size,
                'saved_bytes': saved_bytes,
                'saved_percentage': saved_percentage
            }
            
        except Exception as e:
            self._logger.warning(f"Failed to calculate space saved: {e}")
            return {'input_size': 0, 'output_size': 0, 'saved_bytes': 0, 'saved_percentage': 0.0}
            
    def get_duplication_stats(self) -> dict:
        """Get deduplication statistics"""
        return {
            'total_processed': self.stats.get('total_packets', 0),
            'unique_found': self.stats.get('unique_packets', 0),
            'duplicates_removed': self.stats.get('removed_count', 0),
            'deduplication_rate': self.stats.get('deduplication_rate', 0.0),
            'space_saved': self.stats.get('space_saved', {})
        }
    
    def _generate_packet_hash(self, packet: 'Packet') -> str:
        """Generate packet hash value"""
        try:
            # Generate hash using packet's raw bytes
            packet_bytes = bytes(packet)
            return hashlib.md5(packet_bytes).hexdigest()
        except Exception as e:
            self._logger.warning(f"Failed to generate packet hash: {e}")
            # Fallback: use string representation
            return hashlib.md5(str(packet).encode()).hexdigest()


# Compatibility alias - maintain backward compatibility
class Deduplicator(DeduplicationProcessor):
    """Compatibility alias, please use DeduplicationProcessor instead.

    .. deprecated:: Current version
       Please use :class:`DeduplicationProcessor` instead of :class:`Deduplicator`
    """

    def __init__(self, config: ProcessorConfig):
        import warnings
        warnings.warn(
            "Deduplicator is deprecated, please use DeduplicationProcessor instead",
            DeprecationWarning,
            stacklevel=2
        )
        super().__init__(config)
