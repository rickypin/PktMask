"""
Universal Payload Masking Processor

Universal payload masking processor based on TCP_MARKER_REFERENCE algorithm.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from scapy.all import IP, TCP, PcapReader, PcapWriter, Raw

    SCAPY_AVAILABLE = True
except ImportError:
    # Scapy may not be available in test environment
    PcapReader = PcapWriter = IP = TCP = Raw = None
    SCAPY_AVAILABLE = False

# Try to import tunnel protocol support (optional)
try:
    from scapy.contrib import geneve, vxlan
except ImportError:
    vxlan = geneve = None

from ....resource_manager import ResourceManager
from ..marker.types import KeepRuleSet
from .data_validator import DataValidator
from .error_handler import ErrorCategory, ErrorRecoveryHandler, ErrorSeverity
from .fallback_handler import FallbackHandler
from .stats import MaskingStats


class PayloadMasker:
    """Payload masking processor

    Universal payload masking processor based on TCP_MARKER_REFERENCE.md algorithm.
    Supports multi-layer encapsulation, sequence number wraparound handling and precise keep rule application.
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize payload masking processor

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")

        # Note: Remove sequence number state management, use absolute sequence numbers directly
        # self.seq_state = defaultdict(lambda: {"last": None, "epoch": 0})

        # Flow direction identification state management (consistent with Marker module)
        self.flow_directions = {}  # Store direction information for each flow
        self.stream_id_cache = {}  # Cache stream_id for packets
        self.flow_id_counter = 0  # Flow ID counter, simulating tshark's tcp.stream
        self.tuple_to_stream_id = {}  # Mapping from five-tuple to stream_id

        # Configuration parameters
        self.chunk_size = config.get("chunk_size", 1000)
        self.verify_checksums = config.get("verify_checksums", True)
        self.mask_byte_value = config.get("mask_byte_value", 0x00)

        # 性能优化配置
        self.enable_performance_monitoring = config.get("enable_performance_monitoring", True)
        self.max_memory_usage = config.get("max_memory_usage", 2 * 1024 * 1024 * 1024)  # 2GB

        # Initialize unified resource manager
        resource_config = config.get("resource_manager", {})
        resource_config.setdefault(
            "memory_monitor",
            {
                "max_memory_mb": self.max_memory_usage // (1024 * 1024),
                "pressure_threshold": 0.8,
                "monitoring_interval": 100,
            },
        )
        resource_config.setdefault(
            "buffer_manager",
            {"default_buffer_size": min(self.chunk_size, 100), "auto_resize": True},
        )
        self.resource_manager = ResourceManager(resource_config)

        # Initialize error handler
        error_config = config.get("error_handler", {})
        error_config.setdefault("max_retry_attempts", 3)
        error_config.setdefault("enable_auto_recovery", True)
        self.error_handler = ErrorRecoveryHandler(error_config)

        # Initialize data validator
        validator_config = config.get("data_validator", {})
        validator_config.setdefault("enable_checksum_validation", self.verify_checksums)
        self.data_validator = DataValidator(validator_config)

        # Initialize fallback handler
        fallback_config = config.get("fallback_handler", {})
        fallback_config.setdefault("enable_fallback", True)
        self.fallback_handler = FallbackHandler(fallback_config)

        # 注册内存压力回调（统一方式）
        self.resource_manager.memory_monitor.register_pressure_callback(self._handle_memory_pressure_unified)

        # Register custom error recovery handlers
        self._register_custom_recovery_handlers()

        memory_limit_mb = resource_config.get("memory_monitor", {}).get("max_memory_mb", 2048)
        self.logger.info(
            f"PayloadMasker initialized: chunk_size={self.chunk_size}, "
            f"verify_checksums={self.verify_checksums}, "
            f"memory_limit={memory_limit_mb}MB"
        )

        # Check scapy availability
        if not SCAPY_AVAILABLE:
            self.logger.warning("Scapy unavailable, some features may be limited")

    def _reset_processing_state(self) -> None:
        """Reset processing state to avoid state pollution during multi-file processing

        Reset all variables that may cause state pollution at the beginning of each apply_masking call.
        This ensures that each file processing is independent and not affected by previous file processing.
        """
        self.logger.debug("Resetting PayloadMasker processing state")

        # Reset flow direction identification state
        self.flow_directions.clear()
        self.stream_id_cache.clear()
        self.tuple_to_stream_id.clear()

        # Reset flow ID counter
        self.flow_id_counter = 0

        # Clear current statistics reference
        self._current_stats = None

        # 重置错误处理器状态
        if hasattr(self.error_handler, "reset"):
            self.error_handler.reset()

        # 重置数据验证器状态
        if hasattr(self.data_validator, "reset"):
            self.data_validator.reset()

        # Reset fallback handler state
        if hasattr(self.fallback_handler, "reset"):
            self.fallback_handler.reset()

    def apply_masking(self, input_path: str, output_path: str, keep_rules: KeepRuleSet) -> MaskingStats:
        """Apply masking rules

        Complete masking processing flow based on TCP_MARKER_REFERENCE.md algorithm:
        1. Preprocess keep rules, build efficient lookup structure
        2. Process packets payload by payload, support multi-layer encapsulation stripping
        3. Apply sequence number matching, handle 32-bit wraparound
        4. Execute precise masking operations, maintain payload length unchanged

        Args:
            input_path: Input file path
            output_path: Output file path
            keep_rules: Keep rules set

        Returns:
            MaskingStats: Masking processing statistics
        """
        self.logger.info(f"Starting mask application: {input_path} -> {output_path}")
        start_time = time.time()

        # Reset state to avoid state pollution during multi-file processing
        self._reset_processing_state()

        # 创建统计信息
        stats = MaskingStats(success=True, input_file=input_path, output_file=output_path)

        # Set current statistics for updates during masking process
        self._current_stats = stats

        try:
            # 1. 验证输入文件
            self.logger.info("Validating input file...")
            input_validation = self.data_validator.validate_input_file(input_path)
            if not input_validation.is_valid:
                error_msg = f"Input file validation failed: {input_validation.error_message}"
                self.error_handler.handle_error(
                    error_msg,
                    ErrorSeverity.HIGH,
                    ErrorCategory.INPUT_ERROR,
                    {
                        "input_file": input_path,
                        "validation_details": input_validation.details,
                    },
                )
                raise ValueError(error_msg)

            # 记录验证警告
            for warning in input_validation.warnings:
                self.logger.warning(f"Input file warning: {warning}")

            # Check scapy availability
            if not SCAPY_AVAILABLE:
                error_msg = "Scapy unavailable, cannot process pcap files"
                self.error_handler.handle_error(
                    error_msg,
                    ErrorSeverity.CRITICAL,
                    ErrorCategory.SYSTEM_ERROR,
                    {"input_file": input_path, "output_file": output_path},
                )
                raise RuntimeError(error_msg)

            # 1. Preprocess keep rules
            self.logger.info("Preprocessing keep rules...")
            rule_lookup = self.error_handler.retry_operation(
                lambda: self._preprocess_keep_rules(keep_rules),
                error_category=ErrorCategory.PROCESSING_ERROR,
            )
            self.logger.info(f"Preprocessing completed, {len(rule_lookup)} flow directions total")

            # 2. Process payload packet by packet - optimized streaming processing
            self.logger.info("Starting packet-by-packet processing...")

            # 性能监控
            if self.enable_performance_monitoring:
                import psutil

                process = psutil.Process()
                process.memory_info().rss

            # Use unified buffer management
            packet_buffer = self.resource_manager.create_buffer("packet_buffer")

            # 使用错误处理包装文件操作
            def process_file():
                with (
                    PcapReader(input_path) as reader,
                    PcapWriter(output_path, sync=True) as writer,
                ):
                    for packet in reader:
                        stats.processed_packets += 1

                        try:
                            # Process single packet
                            modified_packet, packet_modified = self._process_packet(packet, rule_lookup)

                            if packet_modified:
                                stats.modified_packets += 1

                            # 添加到缓冲区
                            packet_buffer.append(modified_packet)

                        except Exception as e:
                            # Handle single packet error
                            self.error_handler.handle_error(
                                e,
                                ErrorSeverity.MEDIUM,
                                ErrorCategory.PROCESSING_ERROR,
                                {"packet_number": stats.processed_packets},
                            )
                            # For single packet errors, add original packet to maintain integrity
                            packet_buffer.append(packet)

                        # Unified buffer management: Check if buffer needs to be flushed
                        if self.resource_manager.should_flush_buffer("packet_buffer"):
                            # Flush buffer and write
                            buffered_packets = self.resource_manager.flush_buffer("packet_buffer")
                            self._write_packets_to_file(buffered_packets, writer)

                        # 定期报告进度
                        if stats.processed_packets % self.chunk_size == 0:
                            if self.enable_performance_monitoring:
                                current_memory = process.memory_info().rss
                                memory_usage_mb = current_memory / 1024 / 1024
                                self.logger.info(
                                    f"Processed {stats.processed_packets} packets, "
                                    f"memory usage: {memory_usage_mb:.1f}MB"
                                )
                            else:
                                self.logger.debug(f"Processed {stats.processed_packets} packets")

                    # 写入剩余的缓冲区数据包
                    remaining_packets = self.resource_manager.flush_buffer("packet_buffer")
                    if remaining_packets:
                        self._write_packets_to_file(remaining_packets, writer)

            # Execute file processing with retry mechanism
            self.error_handler.retry_operation(process_file, error_category=ErrorCategory.INPUT_ERROR)

            # 3. 验证处理状态
            self.logger.info("Validating processing state...")
            processing_validation = self.data_validator.validate_processing_state(
                stats.processed_packets, stats.modified_packets, len(stats.errors)
            )

            if not processing_validation.is_valid:
                error_msg = f"Processing state validation failed: {processing_validation.error_message}"
                self.error_handler.handle_error(
                    error_msg,
                    ErrorSeverity.HIGH,
                    ErrorCategory.VALIDATION_ERROR,
                    processing_validation.details,
                )
                stats.add_error(error_msg)

            # Log processing state warnings
            for warning in processing_validation.warnings:
                self.logger.warning(f"Processing state warning: {warning}")

            # 4. 验证输出文件
            self.logger.info("Validating output file...")
            output_validation = self.data_validator.validate_output_file(
                output_path, expected_packet_count=stats.processed_packets
            )

            if not output_validation.is_valid:
                error_msg = f"Output file validation failed: {output_validation.error_message}"
                self.error_handler.handle_error(
                    error_msg,
                    ErrorSeverity.HIGH,
                    ErrorCategory.OUTPUT_ERROR,
                    {
                        "output_file": output_path,
                        "validation_details": output_validation.details,
                    },
                )
                stats.add_error(error_msg)

            # 记录输出验证警告
            for warning in output_validation.warnings:
                self.logger.warning(f"Output file warning: {warning}")

            # 5. 计算执行时间和统计信息
            stats.execution_time = time.time() - start_time

            # 添加验证结果到统计信息
            stats.validation_results = {
                "input_validation": input_validation.details,
                "processing_validation": processing_validation.details,
                "output_validation": output_validation.details,
            }

            # 生成性能报告
            if self.enable_performance_monitoring:
                resource_stats = self.resource_manager.get_resource_stats()
                self.logger.info(
                    f"Mask application completed: processed_packets={stats.processed_packets}, "
                    f"modified_packets={stats.modified_packets}, "
                    f"execution_time={stats.execution_time:.2f}s, "
                    f"peak_memory={resource_stats.peak_memory_mb:.1f}MB, "
                    f"current_memory={resource_stats.memory_usage_mb:.1f}MB"
                )
            else:
                self.logger.info(
                    f"Mask application completed: processed_packets={stats.processed_packets}, "
                    f"modified_packets={stats.modified_packets}, "
                    f"execution_time={stats.execution_time:.2f}s"
                )

        except Exception as e:
            # Handle top-level exception
            self.error_handler.handle_error(
                e,
                ErrorSeverity.HIGH,
                ErrorCategory.PROCESSING_ERROR,
                {"input_file": input_path, "output_file": output_path},
            )

            self.logger.error(f"Mask application failed: {e}")

            # Attempt fallback processing
            fallback_mode = self.fallback_handler.get_recommended_fallback_mode(
                {
                    "error_category": ErrorCategory.PROCESSING_ERROR.value,
                    "error_severity": ErrorSeverity.HIGH.value,
                    "error_message": str(e),
                }
            )

            self.logger.warning(f"Attempting fallback processing: {fallback_mode.value}")

            fallback_result = self.fallback_handler.execute_fallback(
                input_path, output_path, fallback_mode, {"original_error": str(e)}
            )

            if fallback_result.success:
                self.logger.info(f"Fallback processing succeeded: {fallback_result.message}")
                stats.success = True  # Fallback processing succeeded
                stats.add_error(f"Original processing failed, fallback processing succeeded: {fallback_result.message}")
                stats.fallback_used = True
                stats.fallback_mode = fallback_mode.value
                stats.fallback_details = fallback_result.details
            else:
                self.logger.error(f"Fallback processing also failed: {fallback_result.message}")
                stats.success = False
                stats.add_error(str(e))
                stats.add_error(f"Fallback processing failed: {fallback_result.message}")

            # 添加错误摘要到统计信息
            error_summary = self.error_handler.get_error_summary()
            stats.error_details = error_summary

        finally:
            # Clear current statistics reference
            self._current_stats = None

        return stats

    def _preprocess_keep_rules(self, keep_rules: KeepRuleSet) -> Dict[str, Dict[str, Dict]]:
        """Preprocess keep rules to build efficient lookup structure

        Based on TCP_MARKER_REFERENCE.md interval pre-computation algorithm, build optimized lookup structure for each flow direction.

        Args:
            keep_rules: Keep rule set

        Returns:
            Dict[flow_id, Dict[direction, lookup_structure]]
        """
        rule_lookup = defaultdict(lambda: defaultdict(lambda: {"header_only": [], "full_preserve": []}))

        # Group rules by flow, direction and preservation strategy
        for rule in keep_rules.rules:
            preserve_strategy = rule.metadata.get("preserve_strategy", "full_preserve")

            # Map strategy names: map 'full_message' to 'full_preserve'
            if preserve_strategy == "full_message":
                preserve_strategy = "full_preserve"
            elif preserve_strategy not in ["header_only", "full_preserve"]:
                # For unknown strategies, default to full_preserve
                self.logger.warning(f"Unknown preserve strategy '{preserve_strategy}', using 'full_preserve' instead")
                preserve_strategy = "full_preserve"

            # Insert by stream_id
            rule_lookup[rule.stream_id][rule.direction][preserve_strategy].append((rule.seq_start, rule.seq_end))
            # Also insert by tuple_key (if provided) to tolerate stream_id numbering drift
            tuple_key = None
            meta = getattr(rule, "metadata", {}) or {}
            tuple_key = meta.get("tuple_key")
            if tuple_key:
                rule_lookup[tuple_key][rule.direction][preserve_strategy].append((rule.seq_start, rule.seq_end))

        # 为每个流方向构建优化的查找结构
        processed_lookup = {}
        for stream_id, directions in rule_lookup.items():
            processed_lookup[stream_id] = {}

            for direction, strategy_groups in directions.items():
                # Process rules for different preservation strategies separately
                header_only_ranges = strategy_groups["header_only"]
                full_preserve_ranges = strategy_groups["full_preserve"]

                # 处理full_preserve规则（可以合并）
                if full_preserve_ranges:
                    merged_full_ranges = self._merge_overlapping_ranges(full_preserve_ranges)
                else:
                    merged_full_ranges = []

                # 构建分离的查找结构
                all_ranges = header_only_ranges + merged_full_ranges
                sorted_ranges = sorted(all_ranges)

                # 构建边界点集合（保持向后兼容）
                bounds = sorted(set(point for start, end in all_ranges for point in [start, end]))

                # 构建保留区间集合（保持向后兼容）
                keep_set = set(all_ranges)

                processed_lookup[stream_id][direction] = {
                    "bounds": bounds,
                    "keep_set": keep_set,
                    "sorted_ranges": sorted_ranges,
                    "range_count": len(all_ranges),
                    # 新增：分离的策略组
                    "header_only_ranges": header_only_ranges,
                    "full_preserve_ranges": merged_full_ranges,
                }

                total_original_ranges = len(header_only_ranges) + len(full_preserve_ranges)
                self.logger.debug(
                    f"Flow {stream_id}:{direction} - "
                    f"original ranges: {total_original_ranges}, after merge: {len(all_ranges)}, "
                    f"header_only: {len(header_only_ranges)}, full_preserve: {len(merged_full_ranges)}, "
                    f"boundary points: {len(bounds)}"
                )

        return processed_lookup

    def _debug_log_rule_miss(self, stream_id: str, tuple_key: str, direction: str, rule_lookup: Dict) -> None:
        try:
            available_streams = list(rule_lookup.keys())
            self.logger.warning(
                f"No rule for stream_id={stream_id}, tuple_key={tuple_key}, dir={direction}. "
                f"Available keys={available_streams[:10]}{'...' if len(available_streams)>10 else ''}"
            )
        except Exception:
            pass

    def _merge_overlapping_ranges(self, ranges: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        """合并重叠的区间以优化查找性能

        Args:
            ranges: 原始区间列表

        Returns:
            合并后的区间列表
        """
        if not ranges:
            return []

        # 按起始位置排序
        sorted_ranges = sorted(ranges)
        merged = [sorted_ranges[0]]

        for current_start, current_end in sorted_ranges[1:]:
            last_start, last_end = merged[-1]

            # 如果当前区间与上一个区间重叠或相邻
            if current_start <= last_end:
                # 合并区间
                merged[-1] = (last_start, max(last_end, current_end))
            else:
                # 添加新区间
                merged.append((current_start, current_end))

        return merged

    def _process_packet(self, packet, rule_lookup: Dict) -> Tuple[Any, bool]:
        """Process single packet

        Args:
            packet: Original packet
            rule_lookup: Preprocessed rule lookup structure

        Returns:
            Tuple[processed packet, whether modified]
        """
        try:
            # Find innermost TCP/IP layers
            tcp_layer, ip_layer = self._find_innermost_tcp(packet)

            if tcp_layer is None or ip_layer is None:
                # Non-TCP packet, return as-is
                return packet, False

            # Build stream identifier and tuple key (order-invariant)
            stream_id = self._build_stream_id(ip_layer, tcp_layer)
            tuple_key = self._build_tuple_key(ip_layer, tcp_layer)

            # Determine flow direction
            direction = self._determine_flow_direction(ip_layer, tcp_layer, stream_id)

            # Add debug logging
            src_info = f"{ip_layer.src}:{tcp_layer.sport}"
            dst_info = f"{ip_layer.dst}:{tcp_layer.dport}"
            self.logger.debug(
                f"Processing packet: {src_info}->{dst_info}, stream_id={stream_id}, direction={direction}"
            )

            # Get TCP payload
            payload = bytes(tcp_layer.payload) if tcp_layer.payload else b""
            if not payload:
                # No payload, return as-is
                return packet, False

            # Use absolute sequence numbers directly, no 64-bit conversion
            seq_start = tcp_layer.seq
            seq_end = tcp_layer.seq + len(payload)

            # Get matching rule data, with tuple-key fallback if stream_id mapping differs
            rule_data = None
            if tuple_key in rule_lookup and direction in rule_lookup[tuple_key]:
                rule_data = rule_lookup[tuple_key][direction]
                self.logger.debug(f"Found matching rule by tuple_key: {tuple_key}, direction={direction}")
            elif stream_id in rule_lookup and direction in rule_lookup[stream_id]:
                rule_data = rule_lookup[stream_id][direction]
                self.logger.debug(f"Found matching rule by stream_id: {stream_id}, direction={direction}")
            if rule_data is None and tuple_key in rule_lookup:
                # Combine all directions under tuple_key as a direction-agnostic fallback
                combined_header = []
                combined_full = []
                try:
                    for dkey, groups in rule_lookup[tuple_key].items():
                        combined_header.extend(groups.get("header_only", []))
                        combined_full.extend(groups.get("full_preserve", []))
                except Exception:
                    pass
                if combined_header or combined_full:
                    rule_data = {
                        "header_only_ranges": combined_header,
                        "full_preserve_ranges": combined_full,
                    }
                    self.logger.debug(f"Using direction-agnostic fallback rule set for tuple_key={tuple_key}")

            if rule_data is None:
                # No matching rules, use empty rule data (will result in full masking)
                rule_data = {"header_only_ranges": [], "full_preserve_ranges": []}
                self._debug_log_rule_miss(stream_id, tuple_key, direction, rule_lookup)

            # Apply keep rules (for cases with no rules, full masking will be executed)
            new_payload = self._apply_keep_rules(payload, seq_start, seq_end, rule_data)

            # Check if payload has changed
            if new_payload is None or new_payload == payload:
                # If _apply_keep_rules returns None or unmodified, but we need to ensure full masking
                if rule_data["header_only_ranges"] == [] and rule_data["full_preserve_ranges"] == []:
                    # No keep rules, execute full masking
                    new_payload = b"\x00" * len(payload)
                    self.logger.debug(f"Performing full masking: {len(payload)} bytes")
                else:
                    # Has rules but unmodified, return as-is
                    return packet, False

            # Modify packet payload
            modified_packet = self._modify_packet_payload(packet, tcp_layer, new_payload)
            return modified_packet, True

        except Exception as e:
            self.logger.warning(f"Packet processing failed: {e}")
            return packet, False

    def _find_innermost_tcp(self, packet) -> Tuple[Optional[Any], Optional[Any]]:
        """递归查找最内层的 TCP/IP 层

        支持多层封装剥离：VLAN/QinQ、MPLS、GRE、ERSPAN、NVGRE、VXLAN、GENEVE 等

        Args:
            packet: 数据包

        Returns:
            Tuple[TCP层, IP层] 或 (None, None)
        """
        if not packet:
            return (None, None)

        current = packet
        ip_layer = None
        tcp_layer = None
        max_depth = 10  # 防止无限递归
        depth = 0

        # Recursively traverse all layers, supporting multiple tunnel protocols
        while current and depth < max_depth:
            depth += 1

            # 检查是否找到 IP 层
            if hasattr(current, "haslayer") and IP and current.haslayer(IP):
                ip_layer = current[IP]

            # 检查是否找到 TCP 层
            if hasattr(current, "haslayer") and TCP and current.haslayer(TCP):
                tcp_layer = current[TCP]
                break

            # Handle special tunnel protocols
            if hasattr(current, "name"):
                layer_name = current.name

                # VXLAN 隧道
                if layer_name == "VXLAN" and hasattr(current, "payload"):
                    current = current.payload
                    continue

                # GENEVE 隧道
                elif layer_name == "GENEVE" and hasattr(current, "payload"):
                    current = current.payload
                    continue

                # GRE 隧道
                elif layer_name == "GRE" and hasattr(current, "payload"):
                    current = current.payload
                    continue

                # MPLS 标签
                elif layer_name == "MPLS" and hasattr(current, "payload"):
                    current = current.payload
                    continue

                # VLAN 标签
                elif layer_name in ("Dot1Q", "Dot1AD") and hasattr(current, "payload"):
                    current = current.payload
                    continue

            # 继续到下一层
            if hasattr(current, "payload") and current.payload:
                current = current.payload
            else:
                break

        if depth >= max_depth:
            self.logger.warning(f"Reached maximum recursion depth {max_depth}, possible circular reference")

        return (tcp_layer, ip_layer) if tcp_layer and ip_layer else (None, None)

    def _build_tuple_key(self, ip_layer, tcp_layer) -> str:
        """Construct a stable 4-tuple key independent of encounter order.

        Returns:
            A string key like "ip:port-ip:port" with lexical ordering applied.
        """
        src_ip = str(ip_layer.src)
        dst_ip = str(ip_layer.dst)
        src_port = int(tcp_layer.sport)
        dst_port = int(tcp_layer.dport)
        if (src_ip, src_port) < (dst_ip, dst_port):
            return f"{src_ip}:{src_port}-{dst_ip}:{dst_port}"
        else:
            return f"{dst_ip}:{dst_port}-{src_ip}:{src_port}"

    def _build_stream_id(self, ip_layer, tcp_layer) -> str:
        """构建 TCP 流标识（与Marker模块保持一致）

        Args:
            ip_layer: IP 层
            tcp_layer: TCP 层

        Returns:
            流标识字符串（数字形式，如"0", "1"等）
        """
        # Marker module uses tshark's tcp.stream field, returns numeric stream_id
        # We need to simulate the same logic: assign an incremental numeric ID for each unique TCP flow

        src_ip = str(ip_layer.src)
        dst_ip = str(ip_layer.dst)
        src_port = tcp_layer.sport
        dst_port = tcp_layer.dport

        # 构建标准化的五元组（较小的IP:端口在前）
        if (src_ip, src_port) < (dst_ip, dst_port):
            tuple_key = f"{src_ip}:{src_port}-{dst_ip}:{dst_port}"
        else:
            tuple_key = f"{dst_ip}:{dst_port}-{src_ip}:{src_port}"

        # Check if stream_id has been assigned for this flow
        if tuple_key in self.tuple_to_stream_id:
            return self.tuple_to_stream_id[tuple_key]

        # Assign numeric ID for new flow
        stream_id = str(self.flow_id_counter)
        self.tuple_to_stream_id[tuple_key] = stream_id
        self.flow_id_counter += 1

        self.logger.debug(f"Assigned new flow ID: {tuple_key} -> {stream_id}")

        return stream_id

    def _determine_flow_direction(self, ip_layer, tcp_layer, stream_id: str) -> str:
        """确定流方向，与TLS Marker保持一致的逻辑

        使用字典序确定canonical方向，确保与TLS Marker的一致性。

        Args:
            ip_layer: IP 层
            tcp_layer: TCP 层
            stream_id: 流标识

        Returns:
            'forward' 或 'reverse'
        """
        src_ip = str(ip_layer.src)
        dst_ip = str(ip_layer.dst)
        src_port = int(tcp_layer.sport)
        dst_port = int(tcp_layer.dport)

        # 使用字典序逻辑确定canonical forward方向：字典序较小的端点作为源
        if (src_ip, src_port) < (dst_ip, dst_port):
            # 当前连接的字典序：src < dst，所以forward是src->dst
            canonical_forward = {
                "src_ip": src_ip,
                "dst_ip": dst_ip,
                "src_port": src_port,
                "dst_port": dst_port,
            }
        else:
            # 当前连接的字典序：src > dst，所以forward是dst->src
            canonical_forward = {
                "src_ip": dst_ip,
                "dst_ip": src_ip,
                "src_port": dst_port,
                "dst_port": src_port,
            }

        # 存储canonical方向信息（如果还没有存储）
        if stream_id not in self.flow_directions:
            self.flow_directions[stream_id] = {
                "forward": canonical_forward,
                "reverse": {
                    "src_ip": canonical_forward["dst_ip"],
                    "dst_ip": canonical_forward["src_ip"],
                    "src_port": canonical_forward["dst_port"],
                    "dst_port": canonical_forward["src_port"],
                },
            }

            self.logger.debug(
                f"Established canonical flow direction info {stream_id}: forward={canonical_forward['src_ip']}:{canonical_forward['src_port']}->{canonical_forward['dst_ip']}:{canonical_forward['dst_port']}"
            )

        # 判断当前包的方向
        fwd = self.flow_directions[stream_id]["forward"]
        if (
            src_ip == fwd["src_ip"]
            and src_port == fwd["src_port"]
            and dst_ip == fwd["dst_ip"]
            and dst_port == fwd["dst_port"]
        ):
            return "forward"
        return "reverse"

    def _apply_keep_rules(self, payload: bytes, seg_start: int, seg_end: int, rule_data: Dict) -> bytes:
        """Apply keep rules to payload

        Core algorithm implementation based on TCP_MARKER_REFERENCE.md, using optimized binary search.

        Modification note: Now always returns processed payload, implementing default full masking strategy.
        - If there are keep rules, selectively preserve according to rules
        - If no keep rules, return all-zero payload
        - No longer returns None, ensures all TCP payloads are processed

        Args:
            payload: Original payload
            seg_start: Segment start sequence number
            seg_end: Segment end sequence number
            rule_data: Rule data

        Returns:
            Processed payload (always returns, no longer returns None)
        """
        if not payload:
            return b""

        # 使用优化的查找算法
        if "sorted_ranges" in rule_data and rule_data["range_count"] > 10:
            # 对于大量规则，使用二分查找优化
            return self._apply_keep_rules_optimized(payload, seg_start, seg_end, rule_data)
        else:
            # 对于少量规则，使用简单遍历
            return self._apply_keep_rules_simple(payload, seg_start, seg_end, rule_data)

    def _apply_keep_rules_simple(self, payload: bytes, seg_start: int, seg_end: int, rule_data: Dict) -> bytes:
        """简单的保留规则应用（适用于少量规则）

        使用规则类型优先级策略处理重叠规则：
        1. TLS头部保留规则 (header_only) 具有最高优先级
        2. 完全保留规则 (full_preserve) 不能覆盖头部保留规则
        3. 避免跨包TLS消息规则覆盖精确的TLS-23头部规则

        修改说明：现在总是返回处理后的载荷，实现默认全掩码策略。
        """
        # 使用预处理的分离策略组
        header_only_ranges = rule_data.get("header_only_ranges", [])
        full_preserve_ranges = rule_data.get("full_preserve_ranges", [])

        # 创建全零缓冲区
        buf = bytearray(len(payload))

        # 处理header_only规则
        header_range_infos = []
        for keep_start, keep_end in header_only_ranges:
            # 计算与当前段的重叠部分
            overlap_start = max(keep_start, seg_start)
            overlap_end = min(keep_end, seg_end)

            if overlap_start < overlap_end:
                # 计算在载荷中的偏移
                offset_left = max(0, overlap_start - seg_start)
                offset_right = min(len(payload), overlap_end - seg_start)

                if offset_left < offset_right:
                    header_range_infos.append(
                        {
                            "offset_left": offset_left,
                            "offset_right": offset_right,
                            "rule_range": (keep_start, keep_end),
                        }
                    )

        # 处理full_preserve规则
        full_range_infos = []
        for keep_start, keep_end in full_preserve_ranges:
            # 计算与当前段的重叠部分
            overlap_start = max(keep_start, seg_start)
            overlap_end = min(keep_end, seg_end)

            if overlap_start < overlap_end:
                # 计算在载荷中的偏移
                offset_left = max(0, overlap_start - seg_start)
                offset_right = min(len(payload), overlap_end - seg_start)

                if offset_left < offset_right:
                    full_range_infos.append(
                        {
                            "offset_left": offset_left,
                            "offset_right": offset_right,
                            "rule_range": (keep_start, keep_end),
                        }
                    )

        # 创建保留映射，记录每个字节是否已被保留
        preserved_map = [False] * len(payload)
        preserved_bytes = 0

        # 第一阶段：优先应用头部保留规则（最高优先级）
        for range_info in header_range_infos:
            offset_left = range_info["offset_left"]
            offset_right = range_info["offset_right"]

            # 头部保留规则无条件应用
            buf[offset_left:offset_right] = payload[offset_left:offset_right]
            for i in range(offset_left, offset_right):
                preserved_map[i] = True
            preserved_bytes += offset_right - offset_left

        # 第二阶段：应用完全保留规则，但不能覆盖已保留的头部区域
        for range_info in full_range_infos:
            offset_left = range_info["offset_left"]
            offset_right = range_info["offset_right"]

            # 只保留未被头部规则占用的部分
            for i in range(offset_left, offset_right):
                if not preserved_map[i]:
                    buf[i] = payload[i]
                    preserved_map[i] = True
                    preserved_bytes += 1

        # 计算掩码字节数
        masked_bytes = len(payload) - preserved_bytes

        # 更新统计信息（如果有的话）
        if hasattr(self, "_current_stats") and self._current_stats:
            self._current_stats.preserved_bytes += preserved_bytes
            self._current_stats.masked_bytes += masked_bytes

        # 总是返回处理后的载荷（全零缓冲区 + 保留区间的原始数据）
        return bytes(buf)

    def _apply_keep_rules_optimized(self, payload: bytes, seg_start: int, seg_end: int, rule_data: Dict) -> bytes:
        """优化的保留规则应用（使用二分查找，适用于大量规则）

        使用规则类型优先级策略处理重叠规则：
        1. TLS头部保留规则 (header_only) 具有最高优先级
        2. 完全保留规则 (full_preserve) 不能覆盖头部保留规则
        3. 避免跨包TLS消息规则覆盖精确的TLS-23头部规则

        修改说明：现在总是返回处理后的载荷，实现默认全掩码策略。
        """
        # 使用预处理的分离策略组
        header_only_ranges = rule_data.get("header_only_ranges", [])
        full_preserve_ranges = rule_data.get("full_preserve_ranges", [])

        # 创建全零缓冲区
        buf = bytearray(len(payload))

        # 使用二分查找找到可能重叠的header_only区间
        header_overlapping = self._find_overlapping_ranges(header_only_ranges, seg_start, seg_end)

        # 使用二分查找找到可能重叠的full_preserve区间
        full_overlapping = self._find_overlapping_ranges(full_preserve_ranges, seg_start, seg_end)

        # 处理header_only规则
        header_range_infos = []
        for keep_start, keep_end in header_overlapping:
            # 计算与当前段的重叠部分
            overlap_start = max(keep_start, seg_start)
            overlap_end = min(keep_end, seg_end)

            if overlap_start < overlap_end:
                # 计算在载荷中的偏移
                offset_left = max(0, overlap_start - seg_start)
                offset_right = min(len(payload), overlap_end - seg_start)

                if offset_left < offset_right:
                    header_range_infos.append(
                        {
                            "offset_left": offset_left,
                            "offset_right": offset_right,
                            "rule_range": (keep_start, keep_end),
                        }
                    )

        # 处理full_preserve规则
        full_range_infos = []
        for keep_start, keep_end in full_overlapping:
            # 计算与当前段的重叠部分
            overlap_start = max(keep_start, seg_start)
            overlap_end = min(keep_end, seg_end)

            if overlap_start < overlap_end:
                # 计算在载荷中的偏移
                offset_left = max(0, overlap_start - seg_start)
                offset_right = min(len(payload), overlap_end - seg_start)

                if offset_left < offset_right:
                    full_range_infos.append(
                        {
                            "offset_left": offset_left,
                            "offset_right": offset_right,
                            "rule_range": (keep_start, keep_end),
                        }
                    )

        # 创建保留映射，记录每个字节是否已被保留
        preserved_map = [False] * len(payload)
        preserved_bytes = 0

        # 第一阶段：优先应用头部保留规则（最高优先级）
        for range_info in header_range_infos:
            offset_left = range_info["offset_left"]
            offset_right = range_info["offset_right"]

            # 头部保留规则无条件应用
            buf[offset_left:offset_right] = payload[offset_left:offset_right]
            for i in range(offset_left, offset_right):
                preserved_map[i] = True
            preserved_bytes += offset_right - offset_left

        # 第二阶段：应用完全保留规则，但不能覆盖已保留的头部区域
        for range_info in full_range_infos:
            offset_left = range_info["offset_left"]
            offset_right = range_info["offset_right"]

            # 只保留未被头部规则占用的部分
            for i in range(offset_left, offset_right):
                if not preserved_map[i]:
                    buf[i] = payload[i]
                    preserved_map[i] = True
                    preserved_bytes += 1

        # 计算掩码字节数
        masked_bytes = len(payload) - preserved_bytes

        # 更新统计信息（如果有的话）
        if hasattr(self, "_current_stats") and self._current_stats:
            self._current_stats.preserved_bytes += preserved_bytes
            self._current_stats.masked_bytes += masked_bytes

        # 总是返回处理后的载荷（全零缓冲区 + 保留区间的原始数据）
        return bytes(buf)

    def _find_overlapping_ranges(
        self, sorted_ranges: List[Tuple[int, int]], seg_start: int, seg_end: int
    ) -> List[Tuple[int, int]]:
        """使用二分查找找到与给定段重叠的所有区间

        所有区间都使用左闭右开格式 [start, end)：
        - seg_start, seg_end: 当前TCP段的序列号范围 [seg_start, seg_end)
        - range_start, range_end: 保留规则的序列号范围 [range_start, range_end)
        - 重叠条件: range_end > seg_start and range_start < seg_end
        """
        if not sorted_ranges:
            return []

        overlapping = []

        # 找到第一个可能重叠的区间
        left = 0
        right = len(sorted_ranges)

        # 二分查找第一个结束位置 > seg_start 的区间（左闭右开区间）
        while left < right:
            mid = (left + right) // 2
            if sorted_ranges[mid][1] > seg_start:
                right = mid
            else:
                left = mid + 1

        # 从找到的位置开始，收集所有重叠的区间
        for i in range(left, len(sorted_ranges)):
            range_start, range_end = sorted_ranges[i]

            # 如果区间开始位置已经超过段结束位置，则后续区间都不会重叠
            if range_start >= seg_end:
                break

            # 左闭右开区间重叠检测: range_end > seg_start and range_start < seg_end
            if range_end > seg_start and range_start < seg_end:
                overlapping.append((range_start, range_end))

        return overlapping

    def _modify_packet_payload(self, packet, tcp_layer, new_payload: bytes):
        """修改数据包的 TCP 载荷

        Args:
            packet: 原始数据包
            tcp_layer: TCP 层
            new_payload: 新的载荷数据

        Returns:
            修改后的数据包
        """
        # 确保载荷长度不变
        original_length = len(bytes(tcp_layer.payload)) if tcp_layer.payload else 0
        if len(new_payload) != original_length:
            raise ValueError(f"Payload length cannot change: {original_length} -> {len(new_payload)}")

        # 创建数据包副本
        import copy

        modified_packet = copy.deepcopy(packet)

        # 找到修改后数据包中的 TCP 层
        modified_tcp, _ = self._find_innermost_tcp(modified_packet)
        if modified_tcp is None:
            raise ValueError("Cannot find TCP layer in modified packet")

        # 更新载荷
        modified_tcp.payload = Raw(load=new_payload)

        # 删除 TCP 校验和，让 Scapy 自动重新计算
        if hasattr(modified_tcp, "chksum"):
            del modified_tcp.chksum

        return modified_packet

    # 注释：移除32位序列号回绕处理，直接使用绝对序列号
    # def logical_seq(self, seq32: int, flow_key: str) -> int:
    #     """处理32位序列号回绕，返回64位逻辑序号
    #
    #     基于 TCP_MARKER_REFERENCE.md 的序列号回绕处理算法。
    #
    #     Args:
    #         seq32: 32位序列号
    #         flow_key: 流标识
    #
    #     Returns:
    #         64位逻辑序号
    #     """
    #     state = self.seq_state[flow_key]
    #     if state["last"] is not None and (state["last"] - seq32) > 0x7FFFFFFF:
    #         state["epoch"] += 1
    #     state["last"] = seq32
    #     return (state["epoch"] << 32) | seq32

    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计信息

        Returns:
            性能统计字典
        """
        if hasattr(self, "resource_manager"):
            resource_stats = self.resource_manager.get_resource_stats()
            memory_pressure = self.resource_manager.get_memory_pressure()
            return {
                "memory_monitor_available": True,
                "current_memory_mb": resource_stats.memory_usage_mb,
                "peak_memory_mb": resource_stats.peak_memory_mb,
                "memory_pressure": memory_pressure,
                "buffer_count": resource_stats.buffer_count,
                "gc_collections": resource_stats.gc_collections,
                "flow_directions_count": len(self.flow_directions),
            }
        else:
            return {
                "memory_monitor_available": False,
                "flow_directions_count": (len(self.flow_directions) if hasattr(self, "flow_directions") else 0),
            }

    def _flush_packet_buffer(self, packet_buffer: list, writer):
        """刷新数据包缓冲区（保持向后兼容性）

        Args:
            packet_buffer: 数据包缓冲区
            writer: PcapWriter实例
        """
        try:
            for buffered_packet in packet_buffer:
                writer.write(buffered_packet)
            packet_buffer.clear()
        except Exception as e:
            self.error_handler.handle_error(
                e,
                ErrorSeverity.HIGH,
                ErrorCategory.OUTPUT_ERROR,
                {"buffer_size": len(packet_buffer)},
            )
            raise

    def _write_packets_to_file(self, packets: list, writer):
        """统一的数据包写入方法

        Args:
            packets: 数据包列表
            writer: PcapWriter实例
        """
        try:
            for packet in packets:
                writer.write(packet)
            self.logger.debug(f"Written {len(packets)} packets to file")
        except Exception as e:
            self.error_handler.handle_error(
                e,
                ErrorSeverity.HIGH,
                ErrorCategory.OUTPUT_ERROR,
                {"packet_count": len(packets)},
            )
            raise

    def _handle_memory_pressure_unified(self, pressure: float) -> None:
        """统一的内存压力处理回调

        Args:
            pressure: 内存压力值 (0.0 to 1.0)
        """
        self.logger.warning(f"Memory pressure detected: {pressure*100:.1f}%")

        # 在高内存压力下刷新所有缓冲区
        if pressure > 0.9:
            self.logger.warning("High memory pressure, flushing all buffers")
            # 这里可以添加更多的内存压力处理逻辑

    def cleanup(self) -> None:
        """Clean up PayloadMasker resources"""
        self.logger.debug("Starting PayloadMasker cleanup")

        try:
            # Use simple component list to avoid hasattr checks
            cleanup_components = [
                getattr(self, "resource_manager", None),
                getattr(self, "error_handler", None),
                getattr(self, "data_validator", None),
                getattr(self, "fallback_handler", None),
            ]

            cleanup_errors = []
            for component in cleanup_components:
                if component and hasattr(component, "cleanup"):
                    try:
                        component.cleanup()
                    except Exception as e:
                        cleanup_errors.append(f"{component.__class__.__name__}: {e}")

            # Reset processing state
            self._reset_processing_state()

            if cleanup_errors:
                self.logger.warning(f"PayloadMasker cleanup completed with errors: {'; '.join(cleanup_errors)}")
            else:
                self.logger.debug("PayloadMasker cleanup completed successfully")

        except Exception as e:
            self.logger.error(f"Error during PayloadMasker cleanup: {e}")
            raise

    def _register_custom_recovery_handlers(self):
        """注册自定义错误恢复处理器"""

        def pcap_file_recovery(error_info) -> bool:
            """PCAP文件错误恢复"""
            try:
                if "input_file" in error_info.context:
                    input_file = Path(error_info.context["input_file"])
                    if not input_file.exists():
                        self.logger.error(f"Input file does not exist: {input_file}")
                        return False

                    # 检查文件大小
                    if input_file.stat().st_size == 0:
                        self.logger.error(f"Input file is empty: {input_file}")
                        return False

                    # 尝试简单的文件读取测试
                    with open(input_file, "rb") as f:
                        header = f.read(24)  # PCAP文件头
                        if len(header) < 24:
                            self.logger.error(f"PCAP file header incomplete: {input_file}")
                            return False

                return True
            except Exception as e:
                self.logger.warning(f"PCAP file recovery check failed: {e}")
                return False

        def processing_error_recovery(error_info) -> bool:
            """处理错误恢复"""
            try:
                # 清理流方向状态，重新开始
                if hasattr(self, "flow_directions"):
                    self.flow_directions.clear()
                    self.stream_id_cache.clear()
                    self.logger.info("Cleared flow direction state to recover processing")
                    return True
                return False
            except Exception:
                return False

        # 注册自定义处理器
        self.error_handler.register_recovery_handler(ErrorCategory.INPUT_ERROR, pcap_file_recovery)
        self.error_handler.register_recovery_handler(ErrorCategory.PROCESSING_ERROR, processing_error_recovery)

    def get_error_summary(self) -> Dict[str, Any]:
        """获取错误摘要

        Returns:
            错误摘要字典
        """
        if hasattr(self, "error_handler"):
            return self.error_handler.get_error_summary()
        else:
            return {"error_handler_available": False}
