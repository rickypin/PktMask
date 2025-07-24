"""
Anonymize IPs Stage - StageBase Architecture Implementation

This module provides a unified IP anonymization stage based on the StageBase architecture,
replacing the old BaseProcessor wrapper approach with direct implementation.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from pktmask.core.pipeline.stages.ip_anonymization_unified import (
    UnifiedIPAnonymizationStage,
)


class IPAnonymizationStage(UnifiedIPAnonymizationStage):
    """Anonymize IPs Stage - StageBase Architecture Implementation

    This stage provides a unified IP anonymization implementation based on the StageBase
    architecture, directly inheriting from UnifiedIPAnonymizationStage for better
    performance and simplified architecture.

    Features:
    - Direct StageBase implementation without wrapper layers
    - Full backward compatibility with existing functionality
    - Unified interface for pipeline integration
    - Complete preservation of IP mapping and anonymization logic
    """

    name: str = "IPAnonymizationStage"

    def __init__(self, config: Dict[str, Any]):
        """Initialize Anonymize IPs Stage

        Args:
            config: Configuration dictionary with the following optional parameters:
                - method: Anonymization method (default: "prefix_preserving")
                - ipv4_prefix: IPv4 prefix length (default: 24)
                - ipv6_prefix: IPv6 prefix length (default: 64)
                - enabled: Whether the stage is enabled (default: True)
                - name: Stage name (default: "ip_anonymization")
        """
        # Call parent constructor with unified configuration
        super().__init__(config)
        self.logger = logging.getLogger(
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )
        self.logger.info(
            f"IPAnonymizationStage created: method={self.method}, "
            f"ipv4_prefix={self.ipv4_prefix}, ipv6_prefix={self.ipv6_prefix}"
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
        self.logger.info("IPAnonymizationStage stop requested")
        # No special cleanup needed for IP anonymization

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
        return (
            "Anonymize IP addresses in packets while maintaining subnet structure consistency. "
            f"Uses {self.method} method with IPv4/{self.ipv4_prefix} and IPv6/{self.ipv6_prefix} prefixes."
        )
