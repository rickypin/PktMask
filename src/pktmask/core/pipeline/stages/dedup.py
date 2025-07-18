"""
Deduplication Stage - StageBase Architecture Implementation

This module provides a StageBase-compatible wrapper for the existing DeduplicationProcessor,
enabling unified architecture while maintaining full backward compatibility.
"""

from __future__ import annotations

import time
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Union

from pktmask.core.pipeline.base_stage import StageBase
from pktmask.core.pipeline.models import StageStats
from pktmask.core.processors.deduplicator import DeduplicationProcessor, ProcessorConfig, ProcessorResult


class DeduplicationStage(StageBase):
    """Deduplication Stage - StageBase Architecture Implementation

    This stage wraps the existing DeduplicationProcessor to provide a unified
    StageBase interface while maintaining full functional compatibility.

    Features:
    - Full backward compatibility with existing DeduplicationProcessor functionality
    - Unified StageBase interface for pipeline integration
    - Automatic configuration conversion from dict to ProcessorConfig
    - Complete preservation of deduplication logic and statistics
    """

    name: str = "DeduplicationStage"

    def __init__(self, config: Dict[str, Any]):
        """Initialize Deduplication Stage

        Args:
            config: Configuration dictionary with the following optional parameters:
                - enabled: Whether the stage is enabled (default: True)
                - name: Stage name (default: "deduplication")
                - priority: Processing priority (default: 0)
        """
        super().__init__()
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")

        # Store original configuration
        self.config = config.copy()

        # Extract configuration parameters with defaults
        self.enabled = config.get('enabled', True)
        self.stage_name = config.get('name', 'deduplication')
        self.priority = config.get('priority', 0)

        # Internal DeduplicationProcessor instance (lazy initialization)
        self._processor: Optional[DeduplicationProcessor] = None

        self.logger.info(f"DeduplicationStage created: enabled={self.enabled}, name={self.stage_name}")

    def initialize(self, config: Optional[Dict] = None) -> None:
        """Initialize the deduplication stage

        Args:
            config: Optional configuration parameters to update
        """
        if self._initialized:
            return

        try:
            self.logger.info("Starting DeduplicationStage initialization")

            # Update configuration if provided
            if config:
                self.config.update(config)
                self.enabled = self.config.get('enabled', self.enabled)
                self.stage_name = self.config.get('name', self.stage_name)
                self.priority = self.config.get('priority', self.priority)

            # Create ProcessorConfig for DeduplicationProcessor
            processor_config = ProcessorConfig(
                enabled=self.enabled,
                name=self.stage_name,
                priority=self.priority
            )

            # Create and initialize DeduplicationProcessor
            self._processor = DeduplicationProcessor(processor_config)
            if not self._processor.initialize():
                raise RuntimeError("DeduplicationProcessor initialization failed")

            self._initialized = True
            self.logger.info("DeduplicationStage initialization successful")

            # Call parent initialization
            super().initialize(config)

        except Exception as e:
            self.logger.error(f"DeduplicationStage initialization failed: {e}")
            raise

    def process_file(self, input_path: Union[str, Path],
                    output_path: Union[str, Path]) -> StageStats:
        """Process a single file for deduplication

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
                raise RuntimeError("DeduplicationStage not initialized")

        if not self._processor:
            raise RuntimeError("DeduplicationProcessor not initialized")

        # Validate input parameters
        input_path = Path(input_path)
        output_path = Path(output_path)

        if not input_path.exists():
            raise FileNotFoundError(f"Input file does not exist: {input_path}")
        if not input_path.is_file():
            raise ValueError(f"Input path is not a file: {input_path}")

        self.logger.info(f"Starting deduplication: {input_path} -> {output_path}")

        start_time = time.time()

        try:
            # Call DeduplicationProcessor to process the file
            result: ProcessorResult = self._processor.process_file(str(input_path), str(output_path))

            # Calculate processing duration
            duration_ms = (time.time() - start_time) * 1000

            # Convert ProcessorResult to StageStats
            stage_stats = self._convert_processor_result_to_stage_stats(result, duration_ms)

            self.logger.info(f"Deduplication completed successfully in {duration_ms:.2f}ms")
            return stage_stats

        except Exception as e:
            self.logger.error(f"Deduplication failed: {e}")
            raise

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
        self.logger.info("DeduplicationStage stop requested")
        # No special cleanup needed for deduplication

    def _convert_processor_result_to_stage_stats(self, result: ProcessorResult,
                                               duration_ms: float) -> StageStats:
        """Convert ProcessorResult to StageStats format

        Args:
            result: ProcessorResult from DeduplicationProcessor
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
                    'enabled': self.enabled,
                    'stage_name': self.stage_name
                }
            )

        # Extract statistics from successful result
        stats = result.stats or {}
        data = result.data or {}

        return StageStats(
            stage_name=self.name,
            packets_processed=stats.get('total_packets', 0),
            packets_modified=stats.get('removed_count', 0),
            duration_ms=duration_ms,
            extra_metrics={
                'success': True,
                'total_packets': stats.get('total_packets', 0),
                'unique_packets': stats.get('unique_packets', 0),
                'removed_count': stats.get('removed_count', 0),
                'deduplication_rate': stats.get('deduplication_rate', 0.0),
                'space_saved': stats.get('space_saved', {}),
                'processing_time': data.get('processing_time', 0.0),
                'enabled': self.enabled,
                'stage_name': self.stage_name,
                # Include all original stats for compatibility
                **stats
            }
        )

    def get_display_name(self) -> str:
        """Get user-friendly display name

        Returns:
            str: Display name for GUI/CLI
        """
        return "Remove Dupes"

    def get_description(self) -> str:
        """Get stage description

        Returns:
            str: Detailed description of the stage functionality
        """
        return "Remove completely duplicate packets to reduce file size and improve processing efficiency."


# 兼容性别名 - 保持向后兼容
class DedupStage(DeduplicationStage):
    """兼容性别名，请使用 DeduplicationStage 代替。

    .. deprecated:: 当前版本
       请使用 :class:`DeduplicationStage` 代替 :class:`DedupStage`
    """

    def __init__(self, config: Optional[Dict[str, Any]] | None = None):
        import warnings
        warnings.warn(
            "DedupStage is deprecated, please use DeduplicationStage instead",
            DeprecationWarning,
            stacklevel=2
        )
        super().__init__(config or {})
