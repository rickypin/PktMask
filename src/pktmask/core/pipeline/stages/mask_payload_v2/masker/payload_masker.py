"""
通用载荷掩码处理器

基于 TCP_MARKER_REFERENCE 算法的通用载荷掩码处理器。
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

try:
    from scapy.all import IP, TCP, PcapReader, PcapWriter, Raw

    SCAPY_AVAILABLE = True
except ImportError:
    # 在测试环境中可能没有 scapy
    PcapReader = PcapWriter = IP = TCP = Raw = None
    SCAPY_AVAILABLE = False

# 尝试导入隧道协议支持（可选）
try:
    from scapy.contrib import geneve, vxlan
except ImportError:
    vxlan = geneve = None

from ....resource_manager import ResourceManager
from ..marker.types import KeepRuleSet
from .data_validator import DataValidator
from .error_handler import ErrorCategory, ErrorRecoveryHandler, ErrorSeverity
from .fallback_handler import FallbackHandler
from .memory_optimizer import MemoryOptimizer
from .stats import MaskingStats


class PayloadMasker:
    """载荷掩码处理器

    基于 TCP_MARKER_REFERENCE.md 算法实现的通用载荷掩码处理器。
    支持多层封装、序列号回绕处理和精确的保留规则应用。
    """

    def __init__(self, config: Dict[str, Any]):
        """初始化载荷掩码处理器

        Args:
            config: 配置字典
        """
        self.config = config
        self.logger = logging.getLogger(
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )

        # 注释：移除序列号状态管理，直接使用绝对序列号
        # self.seq_state = defaultdict(lambda: {"last": None, "epoch": 0})

        # 流方向识别状态管理（与Marker模块保持一致）
        self.flow_directions = {}  # 存储每个流的方向信息
        self.stream_id_cache = {}  # 缓存数据包的stream_id
        self.flow_id_counter = 0  # 流ID计数器，模拟tshark的tcp.stream
        self.tuple_to_stream_id = {}  # 五元组到stream_id的映射

        # 配置参数
        self.chunk_size = config.get("chunk_size", 1000)
        self.verify_checksums = config.get("verify_checksums", True)
        self.mask_byte_value = config.get("mask_byte_value", 0x00)

        # 性能优化配置
        self.enable_performance_monitoring = config.get(
            "enable_performance_monitoring", True
        )
        self.max_memory_usage = config.get(
            "max_memory_usage", 2 * 1024 * 1024 * 1024
        )  # 2GB

        # 初始化统一资源管理器
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

        # 保持向后兼容性的内存优化器（逐步废弃）
        memory_config = config.get("memory_optimizer", {})
        memory_config.setdefault(
            "max_memory_mb", self.max_memory_usage // (1024 * 1024)
        )
        self.memory_optimizer = MemoryOptimizer(memory_config)

        # 初始化错误处理器
        error_config = config.get("error_handler", {})
        error_config.setdefault("max_retry_attempts", 3)
        error_config.setdefault("enable_auto_recovery", True)
        self.error_handler = ErrorRecoveryHandler(error_config)

        # 初始化数据验证器
        validator_config = config.get("data_validator", {})
        validator_config.setdefault("enable_checksum_validation", self.verify_checksums)
        self.data_validator = DataValidator(validator_config)

        # 初始化降级处理器
        fallback_config = config.get("fallback_handler", {})
        fallback_config.setdefault("enable_fallback", True)
        self.fallback_handler = FallbackHandler(fallback_config)

        # 注册内存压力回调（新的统一方式）
        self.resource_manager.memory_monitor.register_pressure_callback(
            self._handle_memory_pressure_unified
        )

        # 保持向后兼容性
        self.memory_optimizer.register_memory_callback(self._handle_memory_pressure)

        # 注册自定义错误恢复处理器
        self._register_custom_recovery_handlers()

        self.logger.info(
            f"PayloadMasker initialized: chunk_size={self.chunk_size}, "
            f"verify_checksums={self.verify_checksums}, "
            f"memory_limit={memory_config['max_memory_mb']}MB"
        )

        # 检查 scapy 可用性
        if not SCAPY_AVAILABLE:
            self.logger.warning("Scapy unavailable, some features may be limited")

    def _reset_processing_state(self) -> None:
        """重置处理状态以避免多文件处理时的状态污染

        在每次apply_masking调用开始时重置所有可能导致状态污染的变量。
        这确保了每个文件的处理都是独立的，不会受到之前文件处理的影响。
        """
        self.logger.debug("Resetting PayloadMasker processing state")

        # 重置流方向识别状态
        self.flow_directions.clear()
        self.stream_id_cache.clear()
        self.tuple_to_stream_id.clear()

        # 重置流ID计数器
        self.flow_id_counter = 0

        # 清除当前统计信息引用
        self._current_stats = None

        # 重置内存优化器状态
        if hasattr(self.memory_optimizer, "reset"):
            self.memory_optimizer.reset()

        # 重置错误处理器状态
        if hasattr(self.error_handler, "reset"):
            self.error_handler.reset()

        # 重置数据验证器状态
        if hasattr(self.data_validator, "reset"):
            self.data_validator.reset()

        # 重置降级处理器状态
        if hasattr(self.fallback_handler, "reset"):
            self.fallback_handler.reset()

    def apply_masking(
        self, input_path: str, output_path: str, keep_rules: KeepRuleSet
    ) -> MaskingStats:
        """应用掩码规则

        基于 TCP_MARKER_REFERENCE.md 算法实现的完整掩码处理流程：
        1. 预处理保留规则，构建高效查找结构
        2. 逐包处理载荷，支持多层封装剥离
        3. 应用序列号匹配，处理32位回绕
        4. 执行精确掩码操作，保持载荷长度不变

        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径
            keep_rules: 保留规则集合

        Returns:
            MaskingStats: 掩码处理统计信息
        """
        self.logger.info(f"Starting mask application: {input_path} -> {output_path}")
        start_time = time.time()

        # 重置状态以避免多文件处理时的状态污染
        self._reset_processing_state()

        # 创建统计信息
        stats = MaskingStats(
            success=True, input_file=input_path, output_file=output_path
        )

        # 设置当前统计信息，以便在掩码处理过程中更新
        self._current_stats = stats

        try:
            # 1. 验证输入文件
            self.logger.info("Validating input file...")
            input_validation = self.data_validator.validate_input_file(input_path)
            if not input_validation.is_valid:
                error_msg = (
                    f"Input file validation failed: {input_validation.error_message}"
                )
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

            # 检查 scapy 可用性
            if not SCAPY_AVAILABLE:
                error_msg = "Scapy unavailable, cannot process pcap files"
                self.error_handler.handle_error(
                    error_msg,
                    ErrorSeverity.CRITICAL,
                    ErrorCategory.SYSTEM_ERROR,
                    {"input_file": input_path, "output_file": output_path},
                )
                raise RuntimeError(error_msg)

            # 1. 预处理保留规则
            self.logger.info("Preprocessing keep rules...")
            rule_lookup = self.error_handler.retry_operation(
                lambda: self._preprocess_keep_rules(keep_rules),
                error_category=ErrorCategory.PROCESSING_ERROR,
            )
            self.logger.info(
                f"Preprocessing completed, {len(rule_lookup)} flow directions total"
            )

            # 2. 逐包处理载荷 - 优化的流式处理
            self.logger.info("Starting packet-by-packet processing...")

            # 性能监控
            if self.enable_performance_monitoring:
                import psutil

                process = psutil.Process()
                process.memory_info().rss

            # 使用统一的缓冲区管理
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
                            # 处理单个数据包
                            modified_packet, packet_modified = self._process_packet(
                                packet, rule_lookup
                            )

                            if packet_modified:
                                stats.modified_packets += 1

                            # 添加到缓冲区
                            packet_buffer.append(modified_packet)

                        except Exception as e:
                            # 处理单个数据包的错误
                            self.error_handler.handle_error(
                                e,
                                ErrorSeverity.MEDIUM,
                                ErrorCategory.PROCESSING_ERROR,
                                {"packet_number": stats.processed_packets},
                            )
                            # 对于单个数据包错误，添加原始数据包以保持完整性
                            packet_buffer.append(packet)

                        # 统一的缓冲区管理：检查是否需要刷新缓冲区
                        if self.resource_manager.should_flush_buffer("packet_buffer"):
                            # 刷新缓冲区并写入
                            buffered_packets = self.resource_manager.flush_buffer(
                                "packet_buffer"
                            )
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
                                self.logger.debug(
                                    f"Processed {stats.processed_packets} packets"
                                )

                    # 写入剩余的缓冲区数据包
                    remaining_packets = self.resource_manager.flush_buffer(
                        "packet_buffer"
                    )
                    if remaining_packets:
                        self._write_packets_to_file(remaining_packets, writer)

            # 执行文件处理，带重试机制
            self.error_handler.retry_operation(
                process_file, error_category=ErrorCategory.INPUT_ERROR
            )

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

            # 记录处理状态警告
            for warning in processing_validation.warnings:
                self.logger.warning(f"Processing state warning: {warning}")

            # 4. 验证输出文件
            self.logger.info("Validating output file...")
            output_validation = self.data_validator.validate_output_file(
                output_path, expected_packet_count=stats.processed_packets
            )

            if not output_validation.is_valid:
                error_msg = (
                    f"Output file validation failed: {output_validation.error_message}"
                )
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
                memory_report = self.memory_optimizer.get_optimization_report()
                self.logger.info(
                    f"Mask application completed: processed_packets={stats.processed_packets}, "
                    f"modified_packets={stats.modified_packets}, "
                    f"execution_time={stats.execution_time:.2f}s, "
                    f"peak_memory={memory_report['peak_memory_mb']:.1f}MB, "
                    f"gc_count={memory_report['gc_collections']}"
                )
            else:
                self.logger.info(
                    f"Mask application completed: processed_packets={stats.processed_packets}, "
                    f"modified_packets={stats.modified_packets}, "
                    f"execution_time={stats.execution_time:.2f}s"
                )

        except Exception as e:
            # 处理顶级异常
            error_info = self.error_handler.handle_error(
                e,
                ErrorSeverity.HIGH,
                ErrorCategory.PROCESSING_ERROR,
                {"input_file": input_path, "output_file": output_path},
            )

            self.logger.error(f"Mask application failed: {e}")

            # 尝试降级处理
            fallback_mode = self.fallback_handler.get_recommended_fallback_mode(
                {
                    "error_category": ErrorCategory.PROCESSING_ERROR.value,
                    "error_severity": ErrorSeverity.HIGH.value,
                    "error_message": str(e),
                }
            )

            self.logger.warning(
                f"Attempting fallback processing: {fallback_mode.value}"
            )

            fallback_result = self.fallback_handler.execute_fallback(
                input_path, output_path, fallback_mode, {"original_error": str(e)}
            )

            if fallback_result.success:
                self.logger.info(
                    f"Fallback processing succeeded: {fallback_result.message}"
                )
                stats.success = True  # 降级处理成功
                stats.add_error(
                    f"Original processing failed, fallback processing succeeded: {fallback_result.message}"
                )
                stats.fallback_used = True
                stats.fallback_mode = fallback_mode.value
                stats.fallback_details = fallback_result.details
            else:
                self.logger.error(
                    f"Fallback processing also failed: {fallback_result.message}"
                )
                stats.success = False
                stats.add_error(str(e))
                stats.add_error(
                    f"Fallback processing failed: {fallback_result.message}"
                )

            # 添加错误摘要到统计信息
            error_summary = self.error_handler.get_error_summary()
            stats.error_details = error_summary

        finally:
            # 清理当前统计信息引用
            self._current_stats = None

        return stats

    def _preprocess_keep_rules(
        self, keep_rules: KeepRuleSet
    ) -> Dict[str, Dict[str, Dict]]:
        """预处理保留规则，构建高效查找结构

        基于 TCP_MARKER_REFERENCE.md 的区间预编算法，为每个流方向构建优化的查找结构。

        Args:
            keep_rules: 保留规则集合

        Returns:
            Dict[流标识, Dict[方向, 查找结构]]
        """
        rule_lookup = defaultdict(
            lambda: defaultdict(lambda: {"header_only": [], "full_preserve": []})
        )

        # 按流、方向和保留策略分组规则
        for rule in keep_rules.rules:
            preserve_strategy = rule.metadata.get("preserve_strategy", "full_preserve")

            # Map strategy names: map 'full_message' to 'full_preserve'
            if preserve_strategy == "full_message":
                preserve_strategy = "full_preserve"
            elif preserve_strategy not in ["header_only", "full_preserve"]:
                # 对于未知策略，默认使用 full_preserve
                self.logger.warning(
                    f"Unknown preserve strategy '{preserve_strategy}', using 'full_preserve' instead"
                )
                preserve_strategy = "full_preserve"

            rule_lookup[rule.stream_id][rule.direction][preserve_strategy].append(
                (rule.seq_start, rule.seq_end)
            )

        # 为每个流方向构建优化的查找结构
        processed_lookup = {}
        for stream_id, directions in rule_lookup.items():
            processed_lookup[stream_id] = {}

            for direction, strategy_groups in directions.items():
                # 分别处理不同保留策略的规则
                header_only_ranges = strategy_groups["header_only"]
                full_preserve_ranges = strategy_groups["full_preserve"]

                # 处理full_preserve规则（可以合并）
                if full_preserve_ranges:
                    merged_full_ranges = self._merge_overlapping_ranges(
                        full_preserve_ranges
                    )
                else:
                    merged_full_ranges = []

                # 构建分离的查找结构
                all_ranges = header_only_ranges + merged_full_ranges
                sorted_ranges = sorted(all_ranges)

                # 构建边界点集合（保持向后兼容）
                bounds = sorted(
                    set(point for start, end in all_ranges for point in [start, end])
                )

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

                total_original_ranges = len(header_only_ranges) + len(
                    full_preserve_ranges
                )
                self.logger.debug(
                    f"Flow {stream_id}:{direction} - "
                    f"original ranges: {total_original_ranges}, after merge: {len(all_ranges)}, "
                    f"header_only: {len(header_only_ranges)}, full_preserve: {len(merged_full_ranges)}, "
                    f"boundary points: {len(bounds)}"
                )

        return processed_lookup

    def _merge_overlapping_ranges(
        self, ranges: List[Tuple[int, int]]
    ) -> List[Tuple[int, int]]:
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
        """处理单个数据包

        Args:
            packet: 原始数据包
            rule_lookup: 预处理的规则查找结构

        Returns:
            Tuple[处理后的数据包, 是否被修改]
        """
        try:
            # 查找最内层的 TCP/IP
            tcp_layer, ip_layer = self._find_innermost_tcp(packet)

            if tcp_layer is None or ip_layer is None:
                # 非 TCP 包，原样返回
                return packet, False

            # 构建流标识
            stream_id = self._build_stream_id(ip_layer, tcp_layer)

            # 确定流方向
            direction = self._determine_flow_direction(ip_layer, tcp_layer, stream_id)

            # 添加调试日志
            src_info = f"{ip_layer.src}:{tcp_layer.sport}"
            dst_info = f"{ip_layer.dst}:{tcp_layer.dport}"
            self.logger.debug(
                f"Processing packet: {src_info}->{dst_info}, stream_id={stream_id}, direction={direction}"
            )

            # 获取 TCP 载荷
            payload = bytes(tcp_layer.payload) if tcp_layer.payload else b""
            if not payload:
                # 无载荷，原样返回
                return packet, False

            # 直接使用绝对序列号，不进行64位转换
            seq_start = tcp_layer.seq
            seq_end = tcp_layer.seq + len(payload)

            # 获取匹配的规则数据，如果没有匹配规则则使用空规则数据
            if stream_id in rule_lookup and direction in rule_lookup[stream_id]:
                rule_data = rule_lookup[stream_id][direction]
                self.logger.debug(
                    f"Found matching rule: stream_id={stream_id}, direction={direction}"
                )
            else:
                # 没有匹配的规则，使用空规则数据（将导致全掩码处理）
                rule_data = {"header_only_ranges": [], "full_preserve_ranges": []}
                available_streams = list(rule_lookup.keys())
                available_directions = {}
                for sid in available_streams:
                    available_directions[sid] = list(rule_lookup[sid].keys())

                self.logger.debug(
                    f"No matching rule, performing full masking: stream_id={stream_id}, direction={direction}"
                )
                self.logger.debug(f"Available streams: {available_streams}")
                self.logger.debug(f"Available directions: {available_directions}")

            # 应用保留规则（对于无规则的情况，将执行全掩码）
            new_payload = self._apply_keep_rules(payload, seq_start, seq_end, rule_data)

            # 检查载荷是否发生变化
            if new_payload is None or new_payload == payload:
                # 如果_apply_keep_rules返回None或未修改，但我们需要确保全掩码处理
                if (
                    rule_data["header_only_ranges"] == []
                    and rule_data["full_preserve_ranges"] == []
                ):
                    # 无任何保留规则，执行全掩码
                    new_payload = b"\x00" * len(payload)
                    self.logger.debug(f"Performing full masking: {len(payload)} bytes")
                else:
                    # 有规则但未修改，原样返回
                    return packet, False

            # 修改数据包载荷
            modified_packet = self._modify_packet_payload(
                packet, tcp_layer, new_payload
            )
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

        # 递归遍历所有层，支持多种隧道协议
        while current and depth < max_depth:
            depth += 1

            # 检查是否找到 IP 层
            if hasattr(current, "haslayer") and IP and current.haslayer(IP):
                ip_layer = current[IP]

            # 检查是否找到 TCP 层
            if hasattr(current, "haslayer") and TCP and current.haslayer(TCP):
                tcp_layer = current[TCP]
                break

            # 处理特殊的隧道协议
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
            self.logger.warning(
                f"Reached maximum recursion depth {max_depth}, possible circular reference"
            )

        return (tcp_layer, ip_layer) if tcp_layer and ip_layer else (None, None)

    def _build_stream_id(self, ip_layer, tcp_layer) -> str:
        """构建 TCP 流标识（与Marker模块保持一致）

        Args:
            ip_layer: IP 层
            tcp_layer: TCP 层

        Returns:
            流标识字符串（数字形式，如"0", "1"等）
        """
        # Marker模块使用tshark的tcp.stream字段，返回数字形式的stream_id
        # 我们需要模拟相同的逻辑：为每个唯一的TCP流分配一个递增的数字ID

        src_ip = str(ip_layer.src)
        dst_ip = str(ip_layer.dst)
        src_port = tcp_layer.sport
        dst_port = tcp_layer.dport

        # 构建标准化的五元组（较小的IP:端口在前）
        if (src_ip, src_port) < (dst_ip, dst_port):
            tuple_key = f"{src_ip}:{src_port}-{dst_ip}:{dst_port}"
        else:
            tuple_key = f"{dst_ip}:{dst_port}-{src_ip}:{src_port}"

        # 检查是否已为此流分配了stream_id
        if tuple_key in self.tuple_to_stream_id:
            return self.tuple_to_stream_id[tuple_key]

        # 为新流分配数字ID
        stream_id = str(self.flow_id_counter)
        self.tuple_to_stream_id[tuple_key] = stream_id
        self.flow_id_counter += 1

        self.logger.debug(f"Assigned new flow ID: {tuple_key} -> {stream_id}")

        return stream_id

    def _determine_flow_direction(self, ip_layer, tcp_layer, stream_id: str) -> str:
        """确定流方向（与Marker模块保持一致）

        Args:
            ip_layer: IP 层
            tcp_layer: TCP 层
            stream_id: 流标识

        Returns:
            'forward' 或 'reverse'
        """
        src_ip = str(ip_layer.src)
        dst_ip = str(ip_layer.dst)
        src_port = tcp_layer.sport
        dst_port = tcp_layer.dport

        # 检查是否已经建立了此流的方向信息
        if stream_id not in self.flow_directions:
            # 第一次遇到此流，建立方向信息（模拟Marker模块的逻辑）
            self.flow_directions[stream_id] = {
                "forward": {
                    "src_ip": src_ip,
                    "dst_ip": dst_ip,
                    "src_port": src_port,
                    "dst_port": dst_port,
                },
                "reverse": {
                    "src_ip": dst_ip,
                    "dst_ip": src_ip,
                    "src_port": dst_port,
                    "dst_port": src_port,
                },
            }

            self.logger.debug(
                f"Established flow direction info {stream_id}: forward={src_ip}:{src_port}->{dst_ip}:{dst_port}"
            )
            return "forward"  # First packet defines forward direction

        # 根据已建立的方向信息判断当前包的方向
        forward_info = self.flow_directions[stream_id]["forward"]

        if (
            src_ip == forward_info["src_ip"]
            and src_port == forward_info["src_port"]
            and dst_ip == forward_info["dst_ip"]
            and dst_port == forward_info["dst_port"]
        ):
            return "forward"
        else:
            return "reverse"

    def _apply_keep_rules(
        self, payload: bytes, seg_start: int, seg_end: int, rule_data: Dict
    ) -> bytes:
        """应用保留规则到载荷

        基于 TCP_MARKER_REFERENCE.md 的核心算法实现，使用优化的二分查找。

        修改说明：现在总是返回处理后的载荷，实现默认全掩码策略。
        - 如果有保留规则，则根据规则选择性保留
        - 如果无保留规则，则返回全零载荷
        - 不再返回None，确保所有TCP载荷都被处理

        Args:
            payload: 原始载荷
            seg_start: 段起始序列号
            seg_end: 段结束序列号
            rule_data: 规则数据

        Returns:
            处理后的载荷（总是返回，不再返回None）
        """
        if not payload:
            return b""

        # 使用优化的查找算法
        if "sorted_ranges" in rule_data and rule_data["range_count"] > 10:
            # 对于大量规则，使用二分查找优化
            return self._apply_keep_rules_optimized(
                payload, seg_start, seg_end, rule_data
            )
        else:
            # 对于少量规则，使用简单遍历
            return self._apply_keep_rules_simple(payload, seg_start, seg_end, rule_data)

    def _apply_keep_rules_simple(
        self, payload: bytes, seg_start: int, seg_end: int, rule_data: Dict
    ) -> bytes:
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

    def _apply_keep_rules_optimized(
        self, payload: bytes, seg_start: int, seg_end: int, rule_data: Dict
    ) -> bytes:
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
        header_overlapping = self._find_overlapping_ranges(
            header_only_ranges, seg_start, seg_end
        )

        # 使用二分查找找到可能重叠的full_preserve区间
        full_overlapping = self._find_overlapping_ranges(
            full_preserve_ranges, seg_start, seg_end
        )

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
            raise ValueError(
                f"Payload length cannot change: {original_length} -> {len(new_payload)}"
            )

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

    def _handle_memory_pressure(self, memory_stats):
        """处理内存压力回调

        Args:
            memory_stats: 内存统计信息
        """
        self.logger.warning(
            f"Memory pressure warning: usage={memory_stats.memory_pressure*100:.1f}%, "
            f"current_memory={memory_stats.current_usage/1024/1024:.1f}MB"
        )

        # 可以在这里实现额外的内存压力处理逻辑
        # 例如：减少缓冲区大小、强制垃圾回收等
        if memory_stats.memory_pressure > 0.9:  # 90%以上内存使用率
            self.logger.error(
                "Memory usage too high, recommend reducing chunk_size or increasing memory limit"
            )

            # 触发内存错误处理
            self.error_handler.handle_error(
                "Memory usage too high",
                ErrorSeverity.HIGH,
                ErrorCategory.MEMORY_ERROR,
                {"memory_pressure": memory_stats.memory_pressure},
            )

    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计信息

        Returns:
            性能统计字典
        """
        if hasattr(self, "memory_optimizer"):
            return self.memory_optimizer.get_optimization_report()
        else:
            return {
                "memory_optimizer_available": False,
                "seq_state_flows": len(self.seq_state),
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
        """清理PayloadMasker资源"""
        self.logger.debug("Starting PayloadMasker cleanup")

        try:
            # 清理统一资源管理器
            if hasattr(self, "resource_manager"):
                self.resource_manager.cleanup()

            # 清理其他组件
            if hasattr(self, "error_handler") and hasattr(
                self.error_handler, "cleanup"
            ):
                self.error_handler.cleanup()

            if hasattr(self, "data_validator") and hasattr(
                self.data_validator, "cleanup"
            ):
                self.data_validator.cleanup()

            if hasattr(self, "fallback_handler") and hasattr(
                self.fallback_handler, "cleanup"
            ):
                self.fallback_handler.cleanup()

            # 重置状态
            self._reset_processing_state()

            self.logger.debug("PayloadMasker cleanup completed")

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
                            self.logger.error(
                                f"PCAP file header incomplete: {input_file}"
                            )
                            return False

                return True
            except Exception as e:
                self.logger.warning(f"PCAP file recovery check failed: {e}")
                return False

        def processing_error_recovery(error_info) -> bool:
            """处理错误恢复"""
            try:
                # 清理序列号状态，重新开始
                if hasattr(self, "seq_state"):
                    self.seq_state.clear()
                    self.logger.info(
                        "Cleared sequence number state to recover processing"
                    )
                    return True
                return False
            except Exception:
                return False

        # 注册自定义处理器
        self.error_handler.register_recovery_handler(
            ErrorCategory.INPUT_ERROR, pcap_file_recovery
        )
        self.error_handler.register_recovery_handler(
            ErrorCategory.PROCESSING_ERROR, processing_error_recovery
        )

    def get_error_summary(self) -> Dict[str, Any]:
        """获取错误摘要

        Returns:
            错误摘要字典
        """
        if hasattr(self, "error_handler"):
            return self.error_handler.get_error_summary()
        else:
            return {"error_handler_available": False}
