from __future__ import annotations

import json
import logging
import shutil
import time
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from scapy.all import rdpcap, wrpcap, Packet  # type: ignore

from pktmask.core.pipeline.processor_stage import ProcessorStage
from pktmask.core.pipeline.models import StageStats
from pktmask.core.tcp_payload_masker.api.types import MaskingRecipe  # 核心数据结构
from pktmask.core.tcp_payload_masker.utils.helpers import (
    create_masking_recipe_from_dict,
)


class MaskPayloadStage(ProcessorStage):
    """Desktop-optimized payload masking stage with direct integration

    This stage provides two processing modes optimized for desktop applications:
    - Enhanced Mode: Direct TSharkEnhancedMaskProcessor integration
    - Basic Mode: Fast passthrough copy mode

    Desktop application optimizations:
    - No adapter layer overhead
    - Lazy initialization for faster startup
    - Direct processor integration
    - Simplified error handling

    Configuration keys:
    1. ``recipe``: Direct :class:`MaskingRecipe` instance
    2. ``recipe_dict``: Dictionary compatible with ``create_masking_recipe_from_dict``
    3. ``mode``: Processing mode (enhanced or basic)
    4. ``mode``: Processing mode - "enhanced" (default) or "basic"
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config or {})

        # Create logger
        self._logger = logging.getLogger(self.name)

        # Processing mode selection
        mode = self.config.get("mode", "enhanced")
        self._use_enhanced_mode = mode == "enhanced"

        # Enhanced mode components (lazy initialization)
        self._tshark_processor: Optional[Any] = None

        # Recipe configuration
        self._recipe: Optional[MaskingRecipe] = None

    def initialize(self) -> bool:
        """Initialize the mask payload stage with desktop application optimizations"""
        if self._initialized:
            return True

        try:
            # Parse masking recipe if provided
            self._parse_recipe()

            if self._use_enhanced_mode:
                return self._initialize_enhanced_mode()
            else:
                # Basic mode requires no initialization
                self._logger.info("MaskPayloadStage basic mode - passthrough copy")
                self._initialized = True
                return True

        except Exception as e:
            self._logger.error(f"MaskPayloadStage initialization failed: {e}")
            # Fallback to basic mode
            self._use_enhanced_mode = False
            self._initialized = True
            return True



    def _initialize_enhanced_mode(self) -> bool:
        """Initialize enhanced mode with direct TShark processor integration"""
        try:
            # Lazy import for faster startup
            from pktmask.core.processors.tshark_enhanced_mask_processor import TSharkEnhancedMaskProcessor
            from pktmask.core.processors.base_processor import ProcessorConfig

            # Create processor configuration
            processor_config = ProcessorConfig(
                enabled=True,
                name="tshark_enhanced_mask",
                priority=1
            )

            # Create TSharkEnhancedMaskProcessor instance directly
            self._tshark_processor = TSharkEnhancedMaskProcessor(processor_config)

            # Initialize the processor
            if self._tshark_processor.initialize():
                self._initialized = True
                self._logger.info("MaskPayloadStage enhanced mode initialized successfully")
                return True
            else:
                self._logger.error("TSharkEnhancedMaskProcessor initialization failed")
                return False

        except Exception as e:
            self._logger.error(f"Enhanced mode initialization failed: {e}")
            return False

    def _parse_recipe(self):
        """Parse masking recipe from configuration"""
        if "recipe" in self.config:
            self._recipe = self.config["recipe"]
        elif "recipe_dict" in self.config:
            self._recipe = create_masking_recipe_from_dict(self.config["recipe_dict"])
        # recipe_path support removed - use intelligent protocol analysis
        # If no recipe provided, TShark processor will use intelligent protocol analysis

    def process_file(self, input_path: Union[str, Path], output_path: Union[str, Path]) -> StageStats:
        """Process file with payload masking - desktop application optimized

        Args:
            input_path: Input PCAP/PCAPNG file path
            output_path: Output processed file path

        Returns:
            StageStats: Processing statistics
        """
        if not self._initialized and not self.initialize():
            raise RuntimeError("MaskPayloadStage not initialized")

        self.validate_inputs(input_path, output_path)

        input_path = Path(input_path)
        output_path = Path(output_path)

        if self._use_enhanced_mode and self._tshark_processor:
            return self._process_with_enhanced_mode(input_path, output_path)
        else:
            return self._process_with_basic_mode(input_path, output_path)

    def _process_with_enhanced_mode(self, input_path: Path, output_path: Path) -> StageStats:
        """Process with direct TSharkEnhancedMaskProcessor integration"""
        start_time = time.time()

        try:
            # Direct call to TSharkEnhancedMaskProcessor (no adapter overhead)
            result = self._tshark_processor.process_file(str(input_path), str(output_path))

            if not result.success:
                raise RuntimeError(f"TShark processing failed: {result.error}")

            # Convert ProcessorResult to StageStats
            return self._create_stage_stats(
                packets_processed=result.stats.get('packets_processed', 0),
                packets_modified=result.stats.get('packets_modified', 0),
                duration_ms=result.stats.get('duration_ms', 0.0),
                extra_metrics=result.stats
            )

        except Exception as e:
            # Enhanced mode failed, fallback to basic mode
            self._logger.error(f"Enhanced mode failed, falling back to basic mode: {e}")
            duration_ms = (time.time() - start_time) * 1000
            return self._process_with_basic_mode_fallback(input_path, output_path, duration_ms, str(e))



    def _process_with_basic_mode(self, input_path: Path, output_path: Path) -> StageStats:
        """Process with basic passthrough mode (fast copy)"""
        start_time = time.time()

        # Basic mode: fast passthrough copy
        self._logger.info("MaskPayloadStage basic mode: passthrough copy")

        shutil.copyfile(str(input_path), str(output_path))

        duration_ms = (time.time() - start_time) * 1000

        # Statistics: read packet count but don't modify packets
        packets: List[Packet] = rdpcap(str(input_path))

        return self._create_stage_stats(
            packets_processed=len(packets),
            packets_modified=0,
            duration_ms=duration_ms,
            extra_metrics={
                "enhanced_mode": False,
                "mode": "basic_passthrough",
                "reason": "basic_mode_selected"
            }
        )

    def _process_with_basic_mode_fallback(self, input_path: Path, output_path: Path,
                                        duration_ms: float, error: Optional[str] = None) -> StageStats:
        """Fallback processing when enhanced mode fails"""
        # Simple file copy as fallback
        packets: List[Packet] = rdpcap(str(input_path))
        wrpcap(str(output_path), packets)

        return self._create_stage_stats(
            packets_processed=len(packets),
            packets_modified=0,
            duration_ms=duration_ms,
            extra_metrics={
                "enhanced_mode": False,
                "mode": "fallback",
                "original_mode": "enhanced",
                "fallback_reason": error or "enhanced_mode_execution_failed",
                "graceful_degradation": True
            }
        )

    def get_required_tools(self) -> List[str]:
        """Get required tools for enhanced mode"""
        if self._use_enhanced_mode:
            return ['tshark', 'scapy']
        return []

    def get_display_name(self) -> str:
        """Get user-friendly display name"""
        return "Mask Payloads"

    def get_description(self) -> str:
        """Get processor description"""
        return (
            "Desktop-optimized payload masking processor with direct TShark integration. "
            "Supports intelligent protocol recognition and precise masking for TLS/HTTP protocols."
        )


# Backward compatibility alias
MaskStage = MaskPayloadStage
