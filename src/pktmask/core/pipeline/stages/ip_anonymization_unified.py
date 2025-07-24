"""
统一IP匿名化阶段 - 纯StageBase实现

完全移除BaseProcessor依赖，直接集成HierarchicalAnonymizationStrategy逻辑。
消除适配器层，统一返回StageStats格式。
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from pktmask.common.exceptions import ProcessingError, ResourceError
from pktmask.core.pipeline.base_stage import StageBase
from pktmask.core.pipeline.models import StageStats
from pktmask.core.strategy import HierarchicalAnonymizationStrategy
from pktmask.infrastructure.logging import get_logger
from pktmask.utils.reporting import FileReporter


class AnonymizationStage(StageBase):
    """Unified IP anonymization stage - eliminates BaseProcessor dependency

    Directly integrates IP anonymization logic without adapter layer, unified interface.
    Maintains all existing features: hierarchical anonymization, subnet structure preservation, statistics collection.
    """

    name: str = "AnonymizationStage"

    def __init__(self, config: Dict[str, Any]):
        """Initialize unified IP anonymization stage.

        Args:
            config: Configuration dictionary with the following parameters:
                - method: Anonymization method (default: "prefix_preserving")
                - ipv4_prefix: IPv4 prefix length (default: 24)
                - ipv6_prefix: IPv6 prefix length (default: 64)
                - enabled: Whether stage is enabled (default: True)
                - name: Stage name
                - priority: Processing priority
        """
        super().__init__(config)

        # Parse configuration
        self.method = config.get("method", "prefix_preserving")
        self.ipv4_prefix = config.get("ipv4_prefix", 24)
        self.ipv6_prefix = config.get("ipv6_prefix", 64)
        self.enabled = config.get("enabled", True)
        self.stage_name = config.get("name", "ip_anonymization")
        self.priority = config.get("priority", 0)

        # Logger
        self.logger = get_logger("anonymize_stage")

        # Core components - direct initialization, no lazy loading
        self._strategy: Optional[HierarchicalAnonymizationStrategy] = None
        self._reporter: Optional[FileReporter] = None

        # Use full HierarchicalAnonymizationStrategy for IP anonymization
        self._use_simple_strategy = False

        # Statistics
        self._stats = {}

        self.logger.info(f"AnonymizationStage created: method={self.method}")

    def initialize(self, config: Optional[Dict] = None) -> bool:
        """Initialize IP anonymization components.

        Args:
            config: Optional configuration parameters

        Returns:
            bool: True if initialization successful, False otherwise
        """
        if self._initialized:
            return True

        try:
            # Update configuration if provided
            if config:
                self.config.update(config)

            if self._use_simple_strategy:
                # Use simplified strategy to avoid encapsulation adapter issues
                from pktmask.core.strategy import SimpleIPAnonymizationStrategy

                self._strategy = SimpleIPAnonymizationStrategy()
            else:
                # Use full HierarchicalAnonymizationStrategy
                self._strategy = HierarchicalAnonymizationStrategy()

            self._reporter = FileReporter()

            self._initialized = True
            self.logger.info("Unified IP anonymization stage initialization successful")
            return True

        except Exception as e:
            self.logger.error(
                f"Unified IP anonymization stage initialization failed: {e}"
            )
            return False

    def process_file(self, input_path: Path, output_path: Path) -> StageStats:
        """Process file - direct IP anonymization implementation without adapter layer.

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
                raise RuntimeError("AnonymizationStage initialization failed")

        # Validate input with enhanced error handling
        self.validate_file_access(input_path, "IP anonymization")

        self.logger.info(f"Starting IP anonymization: {input_path} -> {output_path}")

        start_time = time.time()

        try:
            # 重置统计信息
            self._stats.clear()

            # Import Scapy with error handling
            try:
                from scapy.all import rdpcap, wrpcap
            except ImportError as e:
                raise ProcessingError(
                    "Scapy library not available for IP anonymization"
                ) from e

            # 读取数据包 with retry mechanism
            def load_packets():
                return rdpcap(str(input_path))

            packets = self.retry_operation(
                load_packets, f"loading packets from {input_path}"
            )
            total_packets = len(packets)

            self.logger.info(f"Loaded {total_packets} packets from {input_path}")

            # 关键修复：先构建IP映射表 with error handling
            with self.safe_operation("IP mapping construction"):
                self.logger.info("Analyzing IP addresses and building mapping table...")
                self._strategy.build_mapping_from_directory([str(input_path)])
                ip_mappings = self._strategy.get_ip_map()
                self.logger.info(
                    f"IP mapping construction completed: {len(ip_mappings)} IP addresses"
                )

            # 开始匿名化数据包 with error handling
            self.logger.info("Starting packet anonymization")
            anonymized_packets = 0
            anonymized_pkts = []

            # 处理每个数据包 with individual packet error handling
            for i, packet in enumerate(packets):
                try:
                    modified_packet, was_modified = self._strategy.anonymize_packet(
                        packet
                    )
                    anonymized_pkts.append(modified_packet)
                    if was_modified:
                        anonymized_packets += 1
                except Exception as e:
                    self.logger.warning(
                        f"Failed to anonymize packet {i+1}/{total_packets}: {e}. Using original packet."
                    )
                    anonymized_pkts.append(
                        packet
                    )  # Keep original packet to maintain file integrity

            # 保存匿名化后的数据包 with error handling
            def save_packets():
                if anonymized_pkts:
                    wrpcap(str(output_path), anonymized_pkts)
                    self.logger.info(
                        f"Saved {len(anonymized_pkts)} anonymized packets to {output_path}"
                    )
                else:
                    # 如果没有数据包，创建空文件
                    output_path.touch()
                    self.logger.warning("No packets to save, created empty output file")

            self.retry_operation(
                save_packets, f"saving anonymized packets to {output_path}"
            )

            processing_time = time.time() - start_time
            duration_ms = processing_time * 1000

            # 构建统计信息
            ip_mappings = self._strategy.get_ip_map()
            original_ips = len([ip for ip in ip_mappings.keys()])
            anonymized_ips = len([ip for ip in ip_mappings.values()])

            # 计算匿名化率
            anonymization_rate = (
                (anonymized_ips / original_ips * 100.0) if original_ips > 0 else 0.0
            )

            # 更新内部统计
            self._stats.update(
                {
                    "original_ips": original_ips,
                    "anonymized_ips": anonymized_ips,
                    "total_packets": total_packets,
                    "anonymized_packets": anonymized_packets,
                    "ip_mappings": ip_mappings,
                    "anonymization_rate": anonymization_rate,
                    "processing_time": processing_time,
                }
            )

            self.logger.info(
                f"IP anonymization completed: {anonymized_ips} IPs anonymized, "
                f"{anonymized_packets}/{total_packets} packets modified"
            )

            # 返回标准StageStats格式
            return StageStats(
                stage_name=self.name,
                packets_processed=total_packets,
                packets_modified=anonymized_packets,
                duration_ms=duration_ms,
                extra_metrics={
                    "method": self.method,
                    "ipv4_prefix": self.ipv4_prefix,
                    "ipv6_prefix": self.ipv6_prefix,
                    "original_ips": original_ips,
                    "anonymized_ips": anonymized_ips,
                    "anonymization_rate": anonymization_rate,
                    "ip_mappings_count": len(ip_mappings),
                    "ip_mappings": ip_mappings,  # 添加实际的IP映射数据
                    "file_ip_mappings": ip_mappings,  # 为兼容性添加file_ip_mappings字段
                    "enabled": self.enabled,
                    "stage_name": self.stage_name,
                    "success": True,
                },
            )

        except FileNotFoundError as e:
            self.handle_file_operation_error(e, input_path, "IP anonymization")

        except ImportError as e:
            raise ProcessingError(
                f"Required dependency not available for IP anonymization: {e}"
            ) from e

        except MemoryError as e:
            raise ResourceError(
                f"Insufficient memory for IP anonymization of {input_path}",
                resource_type="memory",
            ) from e

        except Exception as e:
            error_msg = f"IP anonymization processing failed: {e}"
            self.logger.error(error_msg, exc_info=True)
            raise ProcessingError(error_msg) from e

    def get_display_name(self) -> str:
        """获取显示名称"""
        return "Anonymize IPs"

    def get_description(self) -> str:
        """获取描述"""
        return "Anonymize IP addresses in packets while maintaining subnet structure consistency"

    def get_ip_mappings(self) -> dict:
        """获取IP映射表"""
        if self._strategy:
            return self._strategy.get_ip_map()
        return {}

    def prepare_for_directory(
        self, directory: str | Path, all_files: List[str]
    ) -> None:
        """目录级预处理 - 构建全局IP映射"""
        if not self._initialized:
            self.initialize()

        self.logger.info(f"Preparing IP mapping for directory: {directory}")

        # 使用策略的build_mapping_from_directory方法构建IP映射
        self._strategy.build_mapping_from_directory(all_files)

        ip_count = len(self._strategy.get_ip_map())
        self.logger.info(
            f"Directory IP mapping prepared: {ip_count} unique IP addresses"
        )

    def get_stats(self) -> Dict[str, Any]:
        """获取处理统计信息"""
        return self._stats.copy()

    def reset_stats(self):
        """重置统计信息"""
        self._stats.clear()

    def _cleanup_stage_specific(self) -> None:
        """Stage-specific resource cleanup"""
        # Clear IP mapping and statistics
        if self._strategy:
            # Reset strategy state
            if hasattr(self._strategy, "reset"):
                self._strategy.reset()

        # Clear statistics
        self._stats.clear()

        self.logger.debug("AnonymizationStage specific cleanup completed")


class SimpleIPAnonymizationStrategy:
    """Simplified IP anonymization strategy - avoids complex dependencies"""

    def __init__(self):
        self._ip_map = {}

    def build_mapping_from_directory(self, all_pcap_files: List[str]):
        """Build IP mapping - simplified version"""
        # Simplified implementation: create empty mapping for testing purposes
        self._ip_map = {}

    def get_ip_map(self):
        """Get IP mapping"""
        return self._ip_map

    def anonymize_packet(self, pkt):
        """Anonymize packet - simplified version"""
        # Simplified implementation: return original packet, marked as unmodified
        return pkt, False
