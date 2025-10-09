"""
Next-Generation MaskPayload Stage Main Class

Implements next-generation masking processing stage based on dual-module architecture,
integrating Marker and Masker modules. Supports fully backward-compatible configuration format conversion.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, Optional

from pktmask.core.pipeline.base_stage import StageBase
from pktmask.core.pipeline.models import StageStats
from pktmask.core.temp_file_manager import get_temp_file_manager
from pktmask.infrastructure.logging import get_logger


class MaskingStage(StageBase):
    """Dual-module architecture masking processing stage

    Based on dual-module separation design:
    - Marker module: Protocol analysis and rule generation
    - Masker module: Universal payload masking application
    """

    name: str = "MaskingStage"

    def __init__(self, config: Dict[str, Any]):
        """Initialize new generation mask payload stage.

        Args:
            config: Configuration dictionary with the following parameters:
                - protocol: Protocol type ("tls", "http", "auto")
                - marker_config: Marker module configuration
                - masker_config: Masker module configuration
        """
        super().__init__(config)
        self.logger = get_logger("mask_stage")

        # Parse configuration
        self.protocol = config.get("protocol", "tls")
        self.marker_config = config.get("marker_config", {})
        self.masker_config = config.get("masker_config", {})

        # Module instances (lazy initialization)
        self.marker = None
        self.masker = None

        # Optional configuration validator
        self.config_validator = None

        self.logger.info(f"MaskingStage created: protocol={self.protocol}")

    def initialize(self, config: Optional[Dict] = None) -> bool:
        """Initialize the stage.

        Args:
            config: Optional configuration parameters

        Returns:
            bool: True if initialization successful, False otherwise
        """
        if self._initialized:
            return True

        try:
            self.logger.info("Starting MaskingStage initialization")

            # Update configuration if provided
            if config:
                self.config.update(config)

            # Create Marker module (tls|http|auto)
            self.marker = self._create_marker()
            if not self.marker.initialize():
                self.logger.error("Marker module initialization failed")
                return False

            # Create Masker module
            self.masker = self._create_masker()

            self._initialized = True
            self.logger.info("MaskingStage initialization successful")
            return True

        except Exception as e:
            self.logger.error(f"MaskingStage initialization failed: {e}")
            return False

    def process_file(self, input_path: Path, output_path: Path) -> StageStats:
        """Process a single file.

        Args:
            input_path: Input file path
            output_path: Output file path

        Returns:
            StageStats: Processing statistics and results

        Raises:
            FileNotFoundError: If input file does not exist
            ValueError: If input path is not a file
            RuntimeError: If stage is not initialized
        """
        if not self._initialized:
            if not self.initialize():
                raise RuntimeError("MaskingStage initialization failed")

        # Validate input parameters
        if not input_path.exists():
            raise FileNotFoundError(f"Input file does not exist: {input_path}")
        if not input_path.is_file():
            raise ValueError(f"Input path is not a file: {input_path}")

        self.logger.info(f"Starting file processing: {input_path} -> {output_path}")

        start_time = time.time()

        try:
            # Use dual-module processing mode (enhanced mode)
            return self._process_with_dual_module_mode(input_path, output_path, start_time)

        except Exception as e:
            self.logger.error(f"File processing failed: {e}")
            raise

    def _process_with_dual_module_mode(self, input_path: Path, output_path: Path, start_time: float) -> StageStats:
        """Process file using dual-module architecture"""
        self.logger.debug("Using dual-module architecture processing mode")

        # Optimization: Check if temporary file copy is needed to avoid duplicate reads
        working_input_path = self._prepare_input_file(input_path)

        try:
            # Phase 1: Call Marker module to generate KeepRuleSet
            self.logger.debug("Phase 1: Generate keep rules")
            keep_rules = self.marker.analyze_file(str(working_input_path), self.config)

            # Phase 2: Call Masker module to apply rules
            self.logger.debug("Phase 2: Apply masking rules")
            masking_stats = self.masker.apply_masking(str(working_input_path), str(output_path), keep_rules)

            # Phase 3: Convert statistics information
            stage_stats = self._convert_to_stage_stats(masking_stats)
        finally:
            # Clean up temporary files (if created)
            self._cleanup_input_file(working_input_path, input_path)

        self.logger.info(
            f"Dual-module processing completed: processed_packets={stage_stats.packets_processed}, "
            f"modified_packets={stage_stats.packets_modified}"
        )

        return stage_stats

    def _prepare_input_file(self, input_path: Path) -> Path:
        """Prepare input file with simple file read optimization

        Strategy:
        1. Small files (<50MB): Use original file directly, performance impact negligible
        2. Medium files (50-200MB): Log performance hint but no optimization (avoid over-engineering)
        3. Large files (>200MB): Create temporary hard link to reduce disk I/O

        Args:
            input_path: Original input file path

        Returns:
            Working file path (may be original path or temporary file path)
        """
        try:
            file_size = input_path.stat().st_size
            file_size_mb = file_size / (1024 * 1024)

            # Small file: Use directly, performance impact negligible
            if file_size_mb < 50:
                self.logger.debug(f"Small file ({file_size_mb:.1f}MB), using direct access")
                return input_path

            # Medium file: Log hint but no optimization
            elif file_size_mb < 200:
                self.logger.info(
                    f"Medium file ({file_size_mb:.1f}MB), dual-module processing may cause some I/O overhead"
                )
                return input_path

            # Large file: Create temporary hard link optimization
            else:
                return self._create_temp_hardlink(input_path, file_size_mb)

        except Exception as e:
            self.logger.warning(f"Failed to check file size: {e}, using direct access")
            return input_path

    def _create_temp_hardlink(self, input_path: Path, file_size_mb: float) -> Path:
        """Create temporary hard link for large files to avoid duplicate I/O

        Args:
            input_path: Original file path
            file_size_mb: File size (MB)

        Returns:
            Temporary hard link path
        """
        import os

        try:
            # Use global TempFileManager for reliable cleanup
            temp_manager = get_temp_file_manager()
            temp_dir = temp_manager.create_temp_dir(prefix="pktmask_stage_")
            temp_file = temp_dir / f"input_{input_path.name}"

            # Create hard link (no additional disk space) with enhanced error handling
            try:
                os.link(str(input_path), str(temp_file))
            except OSError as e:
                # Handle cross-device link errors or permission issues
                self.logger.warning(
                    f"Cannot create hardlink (cross-device or permission issue): {e}. "
                    f"Falling back to direct access."
                )
                # Clean up temp directory immediately since hardlink failed
                try:
                    temp_dir.rmdir()
                except OSError as cleanup_error:
                    self.logger.debug(f"Failed to cleanup temp directory after hardlink failure: {cleanup_error}")
                return input_path

            # Register temp file using unified temp file management
            self.register_temp_file(temp_file)
            # Also register a cleanup callback for the directory
            self.resource_manager.register_cleanup_callback(lambda: self._cleanup_temp_directory(temp_dir))

            self.logger.info(f"Created temporary hardlink for large file ({file_size_mb:.1f}MB): {temp_file}")
            return temp_file

        except Exception as e:
            self.logger.warning(f"Failed to create hardlink for optimization: {e}, using direct access")
            return input_path

    def _cleanup_temp_directory(self, temp_dir: Path) -> None:
        """Clean up temporary directory safely

        Args:
            temp_dir: Temporary directory to clean up
        """
        if temp_dir and temp_dir.exists() and temp_dir.name.startswith("pktmask_stage_"):
            try:
                # Try to remove directory (will only succeed if empty)
                temp_dir.rmdir()
                self.logger.debug(f"Cleaned up temporary directory: {temp_dir}")
            except OSError as e:
                # Directory not empty or other error - this is expected if files remain
                self.logger.debug(
                    f"Could not remove temporary directory {temp_dir}: {e} "
                    f"(directory may not be empty or already cleaned)"
                )

    def _cleanup_input_file(self, working_path: Path, original_path: Path) -> None:
        """Clean up working files and temporary directories

        Args:
            working_path: Working file path
            original_path: Original file path
        """
        # If working path differs from original path, temporary file was created and needs cleanup
        if working_path != original_path:
            with self.safe_operation("temporary file cleanup"):
                if working_path.exists():
                    try:
                        # Delete temporary file
                        working_path.unlink()
                        self.logger.debug(f"Cleaned up temporary file: {working_path}")
                    except OSError as e:
                        self.logger.warning(f"Failed to delete temporary file {working_path}: {e}")
                        # Continue with directory cleanup even if file deletion fails

                    # 删除临时目录（如果为空）
                    temp_dir = working_path.parent
                    if temp_dir.name.startswith("pktmask_stage_"):
                        try:
                            temp_dir.rmdir()  # 只删除空目录
                            self.logger.debug(f"Cleaned up temporary directory: {temp_dir}")
                        except OSError as e:
                            # Directory not empty or other error, log but don't raise exception
                            self.logger.debug(
                                f"Could not remove temporary directory {temp_dir}: {e} " f"(directory may not be empty)"
                            )
                else:
                    self.logger.debug(f"Temporary file already cleaned up: {working_path}")

    def _create_marker(self):
        """Create Marker module instance supporting tls|http|auto"""
        if self.protocol == "tls":
            from .marker.tls_marker import TLSProtocolMarker

            return TLSProtocolMarker(self.marker_config)
        elif self.protocol == "http":
            from .marker.http_marker import HTTPProtocolMarker

            return HTTPProtocolMarker(self.marker_config)
        elif self.protocol == "auto":
            from .marker.auto_marker import AutoProtocolMarker

            return AutoProtocolMarker(self.marker_config)
        else:
            raise ValueError(f"Unsupported protocol: {self.protocol}")

    def _create_masker(self):
        """Create Masker module instance

        Returns:
            PayloadMasker instance
        """
        from .masker.payload_masker import PayloadMasker

        return PayloadMasker(self.masker_config)

    def _convert_to_stage_stats(self, masking_stats) -> StageStats:
        """Convert masking statistics to stage statistics

        Args:
            masking_stats: MaskingStats instance

        Returns:
            StageStats instance
        """
        return StageStats(
            stage_name=self.get_display_name(),
            packets_processed=masking_stats.processed_packets,
            packets_modified=masking_stats.modified_packets,
            duration_ms=masking_stats.execution_time * 1000,
            extra_metrics={
                "masked_bytes": masking_stats.masked_bytes,
                "preserved_bytes": masking_stats.preserved_bytes,
                "masking_ratio": masking_stats.masking_ratio,
                "preservation_ratio": masking_stats.preservation_ratio,
                "processing_speed_mbps": masking_stats.processing_speed_mbps,
                "protocol": self.protocol,
                "mode": "enhanced",  # Always enhanced mode
                "success": masking_stats.success,
                "errors": masking_stats.errors,
                "warnings": masking_stats.warnings,
                # 降级处理信息
                "fallback_used": masking_stats.fallback_used,
                "fallback_mode": masking_stats.fallback_mode,
                "fallback_details": masking_stats.fallback_details,
            },
        )

    def get_display_name(self) -> str:
        """获取显示名称"""
        return "Mask Payloads"

    def get_description(self) -> str:
        """Get description information"""
        return (
            f"Next-generation payload masking processor (Protocol: {self.protocol}, Mode: enhanced). "
            "Based on dual-module architecture, supports separation of protocol analysis and mask application."
        )

    def get_required_tools(self) -> list[str]:
        """Get required tools list"""
        tools = ["scapy"]
        if self.protocol in ("tls", "auto"):
            tools.append("tshark")
        return tools

    def _cleanup_stage_specific(self) -> None:
        """Stage-specific resource cleanup"""
        if self.marker:
            self.marker.cleanup()
        if self.masker:
            # Use new cleanup method
            self.masker.cleanup()
        self.logger.debug("MaskingStage specific cleanup completed")
