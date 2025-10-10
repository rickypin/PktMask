"""
Unified Deduplication Stage - Pure StageBase Implementation

Completely removes BaseProcessor dependency, directly integrates SHA256 hash deduplication algorithm.
Eliminates adapter layer, unified StageStats format return.
"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Any, Dict, Optional, Set

from pktmask.common.exceptions import PktMaskError, ProcessingError
from pktmask.core.pipeline.base_stage import StageBase
from pktmask.core.pipeline.models import StageStats
from pktmask.infrastructure.logging import get_logger


class DeduplicationStage(StageBase):
    """Unified deduplication stage - eliminates BaseProcessor dependency

    Directly integrates SHA256 hash deduplication algorithm, no adapter layer, unified interface.
    Maintains all existing functionality: byte-level deduplication, statistics collection, space savings calculation.
    """

    name: str = "DeduplicationStage"

    def __init__(self, config: Dict[str, Any]):
        """Initialize unified deduplication stage.

        Args:
            config: Configuration dictionary with the following parameters:
                - algorithm: Deduplication algorithm (default: "md5")
                - enabled: Whether stage is enabled (default: True)
                - name: Stage name
                - priority: Processing priority
        """
        super().__init__(config)

        # Parse configuration
        self.algorithm = config.get("algorithm", "md5")
        self.enabled = config.get("enabled", True)
        self.stage_name = config.get("name", "deduplication")
        self.priority = config.get("priority", 0)

        # Logger
        self.logger = get_logger("dedup_stage")

        # Deduplication state
        self._packet_hashes: Set[str] = set()

        # Statistics
        self._stats = {}

        self.logger.info(f"DeduplicationStage created: algorithm={self.algorithm}")

    def initialize(self, config: Optional[Dict] = None) -> bool:
        """Initialize deduplication components.

        Args:
            config: Optional configuration parameters

        Returns:
            bool: True if initialization successful, False otherwise
        """
        if self._initialized:
            return True

        try:
            # Check Scapy availability
            pass

            # Clear hash set
            self._packet_hashes.clear()

            # Update configuration if provided
            if config:
                self.config.update(config)

            self._initialized = True
            self.logger.info("Unified deduplication stage initialization successful")
            return True

        except ImportError as e:
            error_msg = f"Scapy library not available: {e}"
            self.logger.error(error_msg)
            return False
        except Exception as e:
            self.logger.error(f"Unified deduplication stage initialization failed: {e}")
            return False

    def process_file(self, input_path: Path, output_path: Path) -> StageStats:
        """Process file - direct deduplication logic implementation without adapter layer.

        Args:
            input_path: Input file path
            output_path: Output file path

        Returns:
            StageStats: Standard statistics format

        Raises:
            FileNotFoundError: If input file does not exist
            ValueError: If input path is not a file
            RuntimeError: If stage is not initialized
        """
        if not self._initialized:
            if not self.initialize():
                raise RuntimeError("DeduplicationStage initialization failed")

        # Validate input with enhanced error handling
        self.validate_file_access(input_path, "deduplication")

        self.logger.info(f"Starting deduplication: {input_path} -> {output_path}")

        start_time = time.time()

        try:
            # 重置统计信息和去重状态
            self._stats.clear()
            self._packet_hashes.clear()  # 清空哈希集合，确保每个文件独立处理

            # Import Scapy with error handling
            try:
                from scapy.all import PcapReader, PcapWriter
            except ImportError as e:
                raise ProcessingError("Scapy library not available for deduplication") from e

            # 开始流式去重处理
            self.logger.info("Starting streaming deduplication")
            total_packets = 0
            unique_packets = 0
            removed_count = 0

            # 使用流式处理：逐包读取、去重、写入
            def process_streaming_dedup():
                nonlocal total_packets, unique_packets, removed_count

                with PcapReader(str(input_path)) as reader:
                    with PcapWriter(str(output_path), sync=True) as writer:
                        for packet in reader:
                            total_packets += 1

                            try:
                                # 监控内存压力
                                if total_packets % 1000 == 0 and self.resource_manager.get_memory_pressure() > 0.9:
                                    self.logger.warning(
                                        f"High memory pressure during deduplication at packet {total_packets}"
                                    )

                                # 生成数据包哈希
                                packet_hash = self._generate_packet_hash(packet)

                                if packet_hash not in self._packet_hashes:
                                    # 首次出现，保留
                                    self._packet_hashes.add(packet_hash)
                                    writer.write(packet)
                                    unique_packets += 1
                                else:
                                    # 重复，跳过
                                    removed_count += 1

                            except Exception as e:
                                self.logger.warning(
                                    f"Failed to process packet {total_packets} during deduplication: {e}. "
                                    f"Treating as unique packet."
                                )
                                # 保留包以维护文件完整性
                                writer.write(packet)
                                unique_packets += 1

                            # 定期报告进度
                            if total_packets % 10000 == 0:
                                self.logger.debug(
                                    f"Processed {total_packets} packets, "
                                    f"{unique_packets} unique, {removed_count} duplicates"
                                )

                # 如果没有处理任何包，创建空文件
                if total_packets == 0:
                    output_path.touch()
                    self.logger.warning("No packets processed, created empty output file")

            self.retry_operation(process_streaming_dedup, f"streaming deduplication from {input_path} to {output_path}")

            processing_time = time.time() - start_time
            duration_ms = processing_time * 1000

            # 计算去重率
            deduplication_rate = (removed_count / total_packets * 100.0) if total_packets > 0 else 0.0

            # 计算空间节省
            space_saved = self._calculate_space_saved(input_path, output_path)

            # 更新内部统计
            self._stats.update(
                {
                    "total_packets": total_packets,
                    "unique_packets": unique_packets,
                    "removed_count": removed_count,
                    "deduplication_rate": deduplication_rate,
                    "space_saved": space_saved,
                    "processing_time": processing_time,
                }
            )

            self.logger.info(
                f"Deduplication completed: removed {removed_count}/{total_packets} duplicate packets "
                f"({deduplication_rate:.1f}% deduplication rate)"
            )

            # 返回标准StageStats格式
            return StageStats(
                stage_name=self.name,
                packets_processed=total_packets,
                packets_modified=removed_count,
                duration_ms=duration_ms,
                extra_metrics={
                    "algorithm": self.algorithm,
                    "total_packets": total_packets,
                    "unique_packets": unique_packets,
                    "removed_count": removed_count,
                    "deduplication_rate": deduplication_rate,
                    "space_saved": space_saved,
                    "processing_time": processing_time,
                    "enabled": self.enabled,
                    "stage_name": self.stage_name,
                    "success": True,
                },
            )

        except FileNotFoundError as e:
            self.handle_file_operation_error(e, input_path, "deduplication")

        except ImportError as e:
            raise ProcessingError(f"Required dependency not available for deduplication: {e}") from e

        except MemoryError as e:
            # Clear hash set to free memory
            self._packet_hashes.clear()
            raise PktMaskError(
                f"Insufficient memory for deduplication of {input_path}",
                error_code="RESOURCE_ERROR",
            ) from e

        except Exception as e:
            error_msg = f"Deduplication processing failed: {e}"
            self.logger.error(error_msg, exc_info=True)
            # Clear hash set on error to prevent state corruption
            self._packet_hashes.clear()
            raise ProcessingError(error_msg) from e

    def get_display_name(self) -> str:
        """Get display name for this stage"""
        return "Remove Dupes"

    def _cleanup_stage_specific(self) -> None:
        """Stage-specific resource cleanup"""
        # Clear deduplication state
        self._packet_hashes.clear()

        # Clear statistics
        self._stats.clear()

        self.logger.debug("DeduplicationStage specific cleanup completed")

    def get_description(self) -> str:
        """Get stage description for UI and documentation"""
        return "Remove completely duplicate packets to reduce file size"

    def _generate_packet_hash(self, packet) -> str:
        """生成数据包哈希值"""
        try:
            # 使用数据包的原始字节生成哈希
            packet_bytes = bytes(packet)
            if self.algorithm == "sha256":
                return hashlib.sha256(packet_bytes).hexdigest()
            else:
                # 默认使用MD5（与原实现保持一致）
                return hashlib.md5(packet_bytes).hexdigest()
        except Exception as e:
            self.logger.warning(f"Failed to generate packet hash: {e}")
            # 回退：使用字符串表示
            packet_str = str(packet).encode()
            if self.algorithm == "sha256":
                return hashlib.sha256(packet_str).hexdigest()
            else:
                return hashlib.md5(packet_str).hexdigest()

    def _calculate_space_saved(self, input_path: Path, output_path: Path) -> dict:
        """计算空间节省"""
        try:
            if not input_path.exists() or not output_path.exists():
                return {
                    "input_size": 0,
                    "output_size": 0,
                    "saved_bytes": 0,
                    "saved_percentage": 0.0,
                }

            input_size = input_path.stat().st_size
            output_size = output_path.stat().st_size
            saved_bytes = input_size - output_size
            saved_percentage = (saved_bytes / input_size * 100.0) if input_size > 0 else 0.0

            return {
                "input_size": input_size,
                "output_size": output_size,
                "saved_bytes": saved_bytes,
                "saved_percentage": saved_percentage,
            }

        except Exception as e:
            self.logger.warning(f"Failed to calculate space saved: {e}")
            return {
                "input_size": 0,
                "output_size": 0,
                "saved_bytes": 0,
                "saved_percentage": 0.0,
            }

    def get_duplication_stats(self) -> dict:
        """获取去重统计信息"""
        return {
            "total_processed": self._stats.get("total_packets", 0),
            "unique_found": self._stats.get("unique_packets", 0),
            "duplicates_removed": self._stats.get("removed_count", 0),
            "deduplication_rate": self._stats.get("deduplication_rate", 0.0),
            "space_saved": self._stats.get("space_saved", {}),
        }

    def get_stats(self) -> Dict[str, Any]:
        """获取处理统计信息"""
        return self._stats.copy()

    def reset_stats(self):
        """重置统计信息"""
        self._stats.clear()
        self._packet_hashes.clear()
