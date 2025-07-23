"""
Deduplication Stage - StageBase Architecture Implementation

This module provides a unified deduplication stage based on the StageBase architecture,
replacing the old BaseProcessor wrapper approach with direct implementation.
"""

from __future__ import annotations

import logging
from typing import Dict, Any, Optional

from pktmask.core.pipeline.stages.deduplication_unified import UnifiedDeduplicationStage


class DeduplicationStage(UnifiedDeduplicationStage):
    """Deduplication Stage - StageBase Architecture Implementation

    This stage provides a unified deduplication implementation based on the StageBase
    architecture, directly inheriting from UnifiedDeduplicationStage for better
    performance and simplified architecture.

    Features:
    - Direct StageBase implementation without wrapper layers
    - Full backward compatibility with existing functionality
    - Unified interface for pipeline integration
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
                - algorithm: Deduplication algorithm (default: "md5")
        """
        # Call parent constructor with unified configuration
        super().__init__(config)
        self.logger = logging.getLogger(
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )
        self.logger.info(
            f"DeduplicationStage created: enabled={self.enabled}, name={self.stage_name}"
        )

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
