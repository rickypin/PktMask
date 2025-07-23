import ipaddress
import os
import random
from abc import ABC, abstractmethod
from typing import Dict, List, Set, Tuple

from scapy.all import IP, IPv6, PcapNgReader, PcapReader

from ..common.constants import ProcessingConstants
from ..infrastructure.logging import get_logger


class AnonymizationStrategy(ABC):
    """Abstract base class for IP anonymization strategies."""

    @abstractmethod
    def create_mapping(
        self, files_to_process: List[str], subdir_path: str, error_log: List
    ) -> Dict[str, str]:
        """
        Create mapping from original IPs to anonymous IPs based on a set of files.

        Args:
            files_to_process: List of files to be processed.
            subdir_path: Subdirectory where files are located.
            error_log: List for recording errors.

        Returns:
            A dictionary mapping each original IP to its new anonymous IP.
        """

    @abstractmethod
    def reset(self):
        """Reset the strategy's internal state for processing new directories."""

    @abstractmethod
    def build_mapping_from_directory(self, all_pcap_files: List[str]):
        """Build IP mapping based on all files in the directory."""

    @abstractmethod
    def anonymize_packet(self, pkt) -> Tuple[object, bool]:
        """Anonymize a single packet."""

    @abstractmethod
    def get_ip_map(self) -> Dict[str, str]:
        """Get the currently built IP mapping."""


def ip_sort_key(ip_str: str) -> tuple:
    """Generate sorting key based on IP string"""
    # This is a utility function, can be kept here or moved to a utils file.
    # For now, it's closely tied to the hierarchical strategy's need for sorted IPs.
    try:
        if "." in ip_str:
            parts = ip_str.split(".")
            return (ProcessingConstants.IPV4_SORT_WEIGHT,) + tuple(
                int(x) for x in parts
            )
        else:
            try:
                ip_obj = ipaddress.IPv6Address(ip_str)
                ip_str = ip_obj.exploded
            except Exception:
                pass
            parts = ip_str.split(":")
            return (ProcessingConstants.IPV6_SORT_WEIGHT,) + tuple(
                int(x, ProcessingConstants.HEX_BASE) for x in parts
            )
    except Exception:
        return (ProcessingConstants.UNKNOWN_IP_SORT_WEIGHT,)


def _safe_hash(input_str: str) -> int:
    """
    Safe hash function ensuring determinism and uniform distribution
    """
    import hashlib

    # Use SHA256 to ensure better distribution and determinism
    hash_obj = hashlib.sha256(input_str.encode("utf-8"))
    return int(
        hash_obj.hexdigest()[: ProcessingConstants.HASH_DIGEST_LENGTH],
        ProcessingConstants.HEX_BASE,
    )


def _generate_unique_segment(
    original_seg: str,
    seed_base: str,
    used_values: Set[str],
    min_val: int = ProcessingConstants.IPV4_MIN_SEGMENT,
    max_val: int = ProcessingConstants.IPV4_MAX_SEGMENT,
    max_attempts: int = 100,
) -> str:
    """
    Generate unique IP segment value, avoiding conflicts

    Args:
        original_seg: Original segment value
        seed_base: Seed base string
        used_values: Set of already used values
        min_val: Minimum value
        max_val: Maximum value
        max_attempts: Maximum number of attempts
    """
    if not original_seg.isdigit():
        raise ValueError(f"Invalid segment: {original_seg}")

    orig_int = int(original_seg)
    if orig_int < min_val or orig_int > max_val:
        raise ValueError(f"Segment out of range: {original_seg}")

    # Generate deterministic random number generator based on seed
    seed_value = _safe_hash(f"{seed_base}_{original_seg}")
    local_random = random.Random(seed_value)

    # Calculate candidate range
    n = len(original_seg)
    if n == 1:
        delta = 3
    elif n == 2:
        delta = 5
    else:
        delta = 20

    # First try adjacent value range
    cand_lower = max(min_val, orig_int - delta)
    cand_upper = min(max_val, orig_int + delta)

    # Generate candidate values, avoiding original value and used values
    candidates = []
    for val in range(cand_lower, cand_upper + 1):
        if val != orig_int and str(val) not in used_values:
            candidates.append(val)

    # If no available values in adjacent range, expand to full range
    if not candidates:
        for val in range(min_val, max_val + 1):
            if val != orig_int and str(val) not in used_values:
                candidates.append(val)

    if not candidates:
        # If no available values, use simple offset
        for offset in range(1, max_val - min_val + 1):
            val = (orig_int + offset) % (max_val - min_val + 1) + min_val
            if str(val) not in used_values:
                candidates.append(val)
                break

    if candidates:
        # Use deterministic random selection
        choice_idx = local_random.randint(0, len(candidates) - 1)
        result = str(candidates[choice_idx])
        used_values.add(result)
        return result
    else:
        # Last resort: force generate non-conflicting value
        for val in range(min_val, max_val + 1):
            if str(val) not in used_values:
                used_values.add(str(val))
                return str(val)

        # If really no available values, return original value (should not happen)
        return original_seg


def _generate_new_ipv4_address_hierarchical(
    original_ip: str, freq1, freq2, freq3, maps, used_segments
) -> str:
    """
    Frequency-based hierarchical IPv4 address generation, ensuring consistency for high-frequency subnets
    """
    ipv4_first_map, ipv4_second_map, ipv4_third_map = maps
    used_a, used_ab, used_abc = used_segments

    if not isinstance(original_ip, str):
        return original_ip
    parts = original_ip.split(".")
    if len(parts) != 4:
        return original_ip
    A, B, C, D = parts

    # A segment processing - maintain consistent mapping for high-frequency A segments
    if freq1.get(A, 0) >= 2:
        if A not in ipv4_first_map:
            ipv4_first_map[A] = _generate_unique_segment(
                A, f"first_{A}", used_a, 1, 255
            )
        newA = ipv4_first_map[A]
    else:
        newA = _generate_unique_segment(A, f"first_single_{A}", used_a, 1, 255)

    # A.B segment processing - key fix: maintain consistent mapping for high-frequency A.B segments
    key2 = ".".join(parts[:2])  # Original A.B segment, e.g. "140.216"

    if freq2.get(key2, 0) >= 2:
        # High-frequency A.B segment: must maintain consistent mapping
        if key2 not in ipv4_second_map:
            # Assign a new B segment value for this high-frequency A.B segment
            ipv4_second_map[key2] = _generate_unique_segment(
                B, f"second_freq_{key2}", used_ab, 0, 255
            )
        newB = ipv4_second_map[key2]

        # Build new A.B segment combination and record
        new_ab = f"{newA}.{newB}"
        used_ab.add(new_ab)
    else:
        # Low-frequency A.B segment: generate unique mapping for each independent A.B segment
        if key2 not in ipv4_second_map:
            ipv4_second_map[key2] = _generate_unique_segment(
                B, f"second_single_{key2}", used_ab, 0, 255
            )
        newB = ipv4_second_map[key2]

        # Build new A.B segment combination and record
        new_ab = f"{newA}.{newB}"
        used_ab.add(new_ab)

    # A.B.C segment processing - maintain consistent mapping for high-frequency A.B.C segments
    key3 = ".".join(parts[:3])  # Original A.B.C segment, e.g. "140.216.190"

    if freq3.get(key3, 0) >= 2:
        # High-frequency A.B.C segment: must maintain consistent mapping
        if key3 not in ipv4_third_map:
            ipv4_third_map[key3] = _generate_unique_segment(
                C, f"third_freq_{key3}", used_abc, 0, 255
            )
        newC = ipv4_third_map[key3]

        # Build new A.B.C segment combination and record
        new_abc = f"{newA}.{newB}.{newC}"
        used_abc.add(new_abc)
    else:
        # Low-frequency A.B.C segment: generate unique mapping for each independent A.B.C segment
        if key3 not in ipv4_third_map:
            ipv4_third_map[key3] = _generate_unique_segment(
                C, f"third_single_{key3}", used_abc, 0, 255
            )
        newC = ipv4_third_map[key3]

        # Build new A.B.C segment combination and record
        new_abc = f"{newA}.{newB}.{newC}"
        used_abc.add(new_abc)

    return f"{newA}.{newB}.{newC}.{D}"


def _generate_new_ipv6_address_hierarchical(original_ip: str, freqs, maps) -> str:
    """
    Frequency-based hierarchical IPv6 address generation
    """
    try:
        ip_obj = ipaddress.IPv6Address(original_ip)
        parts = ip_obj.exploded.split(":")
    except Exception:
        return original_ip
    if len(parts) != 8:
        return original_ip

    new_parts = []
    for i in range(7):
        key = ":".join(parts[: i + 1])
        if freqs[i].get(key, 0) >= 2:
            if key not in maps[i]:
                maps[i][key] = _generate_unique_ipv6_segment(
                    parts[i], f"ipv6_{i}_{key}"
                )
            new_seg = maps[i][key]
        else:
            new_seg = _generate_unique_ipv6_segment(parts[i], f"ipv6_single_{i}_{key}")
        new_parts.append(new_seg)

    new_parts.append(parts[7])
    return ":".join(new_parts)


def _generate_unique_ipv6_segment(original_seg: str, seed_base: str) -> str:
    """生成IPv6段的确定性随机化值"""
    n = len(original_seg)
    orig_int = int(original_seg, 16)

    # 使用确定性种子
    seed_value = _safe_hash(f"{seed_base}_{original_seg}")
    local_random = random.Random(seed_value)

    lower = 16 ** (n - 1) if n > 1 else 0
    upper = 16**n - 1
    if n == 1:
        delta = 3
    elif n == 2:
        delta = 8
    elif n == 3:
        delta = 32
    elif n == 4:
        delta = 128
    else:
        delta = 256

    cand_lower = max(lower, orig_int - delta)
    cand_upper = min(upper, orig_int + delta)

    # 生成候选值，避免原值
    candidates = []
    for val in range(cand_lower, cand_upper + 1):
        if val != orig_int:
            candidates.append(val)

    if not candidates:
        # 如果邻近范围没有可用值，扩展到全范围
        for val in range(lower, upper + 1):
            if val != orig_int:
                candidates.append(val)

    if candidates:
        choice_idx = local_random.randint(0, len(candidates) - 1)
        result = candidates[choice_idx]
    else:
        # 最后手段
        result = (orig_int + 1) % (upper - lower + 1) + lower

    return format(result, "x").zfill(n)


class HierarchicalAnonymizationStrategy(AnonymizationStrategy):
    """
    Hierarchical IP anonymization strategy based on network segment frequency.
    This strategy pre-scans files to preserve subnet structure.
    """

    def __init__(self):
        self._ip_map: Dict[str, str] = {}
        # New: Encapsulation processing adapter (lazy initialization to avoid circular imports)
        self._encap_adapter = None
        self._encap_stats = {
            "total_packets_scanned": 0,
            "encapsulated_packets": 0,
            "multi_layer_ip_packets": 0,
            "plain_packets": 0,
        }

    def _get_encap_adapter(self):
        """Lazy initialize encapsulation adapter to avoid circular imports"""
        if self._encap_adapter is None:
            from pktmask.adapters.encapsulation_adapter import ProcessingAdapter

            self._encap_adapter = ProcessingAdapter()
        return self._encap_adapter

    def reset(self):
        self._ip_map = {}
        # Reset encapsulation statistics
        if self._encap_adapter is not None:
            self._encap_adapter.reset_stats()
        self._encap_stats = {
            "total_packets_scanned": 0,
            "encapsulated_packets": 0,
            "multi_layer_ip_packets": 0,
            "plain_packets": 0,
        }

    def get_ip_map(self) -> Dict[str, str]:
        return self._ip_map

    def _prescan_addresses(
        self, files_to_process: List[str], subdir_path: str, error_log: List[str]
    ) -> Tuple:
        """
        Corrected version: Correctly count frequency of all IP addresses (source and destination)
        """
        import time

        from pktmask.infrastructure.logging import log_performance

        start_time = time.time()

        freq_ipv4_1, freq_ipv4_2, freq_ipv4_3 = {}, {}, {}
        (
            freq_ipv6_1,
            freq_ipv6_2,
            freq_ipv6_3,
            freq_ipv6_4,
            freq_ipv6_5,
            freq_ipv6_6,
            freq_ipv6_7,
        ) = ({}, {}, {}, {}, {}, {}, {})
        unique_ips = set()

        def process_ipv4_address(ip_str: str):
            """处理单个IPv4地址的频率统计"""
            unique_ips.add(ip_str)
            try:
                ipaddress.IPv4Address(ip_str)
            except Exception:
                return
            parts = ip_str.split(".")
            if len(parts) != 4:
                return
            # 统计各级频率
            freq_ipv4_1[parts[0]] = freq_ipv4_1.get(parts[0], 0) + 1
            freq_ipv4_2[".".join(parts[:2])] = (
                freq_ipv4_2.get(".".join(parts[:2]), 0) + 1
            )
            freq_ipv4_3[".".join(parts[:3])] = (
                freq_ipv4_3.get(".".join(parts[:3]), 0) + 1
            )

        def process_ipv6_address(ip_str: str):
            """处理单个IPv6地址的频率统计"""
            unique_ips.add(ip_str)
            try:
                ip_obj = ipaddress.IPv6Address(ip_str)
            except Exception:
                return
            parts = ip_obj.exploded.split(":")
            if len(parts) != 8:
                return
            # 统计各级前缀频率
            freq_ipv6_1[parts[0]] = freq_ipv6_1.get(parts[0], 0) + 1
            freq_ipv6_2[":".join(parts[:2])] = (
                freq_ipv6_2.get(":".join(parts[:2]), 0) + 1
            )
            freq_ipv6_3[":".join(parts[:3])] = (
                freq_ipv6_3.get(":".join(parts[:3]), 0) + 1
            )
            freq_ipv6_4[":".join(parts[:4])] = (
                freq_ipv6_4.get(":".join(parts[:4]), 0) + 1
            )
            freq_ipv6_5[":".join(parts[:5])] = (
                freq_ipv6_5.get(":".join(parts[:5]), 0) + 1
            )
            freq_ipv6_6[":".join(parts[:6])] = (
                freq_ipv6_6.get(":".join(parts[:6]), 0) + 1
            )
            freq_ipv6_7[":".join(parts[:7])] = (
                freq_ipv6_7.get(":".join(parts[:7]), 0) + 1
            )

        # 【Enhanced】Get encapsulation adapter once for the entire process
        encap_adapter = self._get_encap_adapter()

        for f in files_to_process:
            file_path = os.path.join(subdir_path, f)
            ext = os.path.splitext(f)[1].lower()
            try:
                reader_class = PcapNgReader if ext == ".pcapng" else PcapReader
                with reader_class(file_path) as reader:
                    for packet in reader:
                        self._encap_stats["total_packets_scanned"] += 1

                        # 【Enhanced】Use encapsulation adapter to analyze packets and extract IPs from all layers
                        ip_analysis = encap_adapter.analyze_packet_for_ip_processing(
                            packet
                        )

                        # Update encapsulation statistics
                        if ip_analysis["has_encapsulation"]:
                            self._encap_stats["encapsulated_packets"] += 1
                            if ip_analysis["has_multiple_ips"]:
                                self._encap_stats["multi_layer_ip_packets"] += 1
                        else:
                            self._encap_stats["plain_packets"] += 1

                        # 【Enhanced】Process IP addresses from all layers
                        ip_pairs = encap_adapter.extract_ips_for_anonymization(
                            ip_analysis
                        )
                        for src_ip, dst_ip, context in ip_pairs:
                            # 处理IPv4地址
                            if "." in src_ip:
                                process_ipv4_address(src_ip)
                            elif ":" in src_ip:
                                process_ipv6_address(src_ip)

                            if "." in dst_ip:
                                process_ipv4_address(dst_ip)
                            elif ":" in dst_ip:
                                process_ipv6_address(dst_ip)

                        # 【Compatibility】Keep original simple IP extraction as fallback
                        if not ip_pairs:
                            # Fall back to original logic
                            if packet.haslayer(IP):
                                process_ipv4_address(packet.getlayer(IP).src)
                                process_ipv4_address(packet.getlayer(IP).dst)

                            if packet.haslayer(IPv6):
                                process_ipv6_address(packet.getlayer(IPv6).src)
                                process_ipv6_address(packet.getlayer(IPv6).dst)

            except Exception as e:
                error_log.append(f"Error scanning file {file_path}: {str(e)}")

        # Record frequency statistics and performance metrics
        end_time = time.time()
        duration = end_time - start_time

        # 【Enhanced】Get encapsulation processing statistics
        encap_proc_stats = encap_adapter.get_processing_stats()

        log_performance(
            "ip_prescan_addresses",
            duration,
            "ip_anonymization.performance",
            files_processed=len(files_to_process),
            unique_ips=len(unique_ips),
            encapsulated_packets=self._encap_stats["encapsulated_packets"],
            multi_layer_ip_packets=self._encap_stats["multi_layer_ip_packets"],
        )

        logger = get_logger("anonymization.strategy")
        logger.info(
            f"Frequency statistics completed: unique IPs={len(unique_ips)}, duration={duration:.2f}s"
        )

        # 【Enhanced】Encapsulation processing statistics report
        logger.info(
            f"Encapsulation processing statistics: total packets={self._encap_stats['total_packets_scanned']}, "
            f"encapsulated={self._encap_stats['encapsulated_packets']}, "
            f"multi-layer IP={self._encap_stats['multi_layer_ip_packets']}, "
            f"normal={self._encap_stats['plain_packets']}"
        )
        if self._encap_stats["total_packets_scanned"] > 0:
            encap_ratio = (
                self._encap_stats["encapsulated_packets"]
                / self._encap_stats["total_packets_scanned"]
            )
            multi_ip_ratio = (
                self._encap_stats["multi_layer_ip_packets"]
                / self._encap_stats["total_packets_scanned"]
            )
            logger.info(
                f"Encapsulation ratio: {encap_ratio:.1%}, multi-layer IP ratio: {multi_ip_ratio:.1%}"
            )

        if encap_proc_stats["encapsulation_distribution"]:
            logger.debug(
                f"Encapsulation type distribution: {encap_proc_stats['encapsulation_distribution']}"
            )

        if freq_ipv4_1:
            top_ipv4_a = dict(
                sorted(freq_ipv4_1.items(), key=lambda x: x[1], reverse=True)[:5]
            )
            logger.debug(f"IPv4 A-segment frequency statistics (top 5): {top_ipv4_a}")
        if freq_ipv4_2:
            top_ipv4_ab = dict(
                sorted(freq_ipv4_2.items(), key=lambda x: x[1], reverse=True)[:5]
            )
            logger.debug(
                f"IPv4 A.B-segment frequency statistics (top 5): {top_ipv4_ab}"
            )

        return (
            (freq_ipv4_1, freq_ipv4_2, freq_ipv4_3),
            (
                freq_ipv6_1,
                freq_ipv6_2,
                freq_ipv6_3,
                freq_ipv6_4,
                freq_ipv6_5,
                freq_ipv6_6,
                freq_ipv6_7,
            ),
            unique_ips,
        )

    def create_mapping(
        self, files_to_process: List[str], subdir_path: str, error_log: List[str]
    ) -> Dict[str, str]:
        """
        Create IP mapping, ensuring no conflicts
        """
        import time

        from pktmask.infrastructure.logging import log_performance

        start_time = time.time()

        freqs_ipv4, freqs_ipv6, all_ips = self._prescan_addresses(
            files_to_process, subdir_path, error_log
        )

        mapping = {}
        maps_ipv4 = ({}, {}, {})
        maps_ipv6 = ({}, {}, {}, {}, {}, {}, {})

        # Track used segment values to ensure uniqueness
        used_segments = (set(), set(), set())  # (A-segment, A.B-segment, A.B.C-segment)

        sorted_ips = sorted(all_ips, key=ip_sort_key)

        # Record mapping generation start information
        logger = get_logger("anonymization.strategy")
        ipv4_count = sum(1 for ip in sorted_ips if "." in ip)
        logger.info(
            f"Starting mapping generation - IPv4 addresses: {ipv4_count}, total IPs: {len(sorted_ips)}"
        )

        for ip in sorted_ips:
            try:
                ip_obj = ipaddress.ip_address(ip)
                if ip_obj.version == 4:
                    mapping[ip] = _generate_new_ipv4_address_hierarchical(
                        ip,
                        freqs_ipv4[0],
                        freqs_ipv4[1],
                        freqs_ipv4[2],
                        maps_ipv4,
                        used_segments,
                    )
                else:
                    mapping[ip] = _generate_new_ipv6_address_hierarchical(
                        ip, freqs_ipv6, maps_ipv6
                    )
            except Exception as e:
                error_log.append(f"Pre-calculate mapping error for IP {ip}: {str(e)}")

        # Record hierarchical mapping statistics
        logger.info(
            f"Hierarchical mapping generation completed: A-segment mappings={len(maps_ipv4[0])}, A.B-segment mappings={len(maps_ipv4[1])}, A.B.C-segment mappings={len(maps_ipv4[2])}"
        )
        logger.debug(
            f"Unique segment count statistics: A-segment={len(used_segments[0])}, A.B-segment={len(used_segments[1])}, A.B.C-segment={len(used_segments[2])}"
        )

        # 验证高频网段的一致性映射
        consistency_errors = []
        ab_mapping_check = {}  # original_ab -> mapped_ab
        abc_mapping_check = {}  # original_abc -> mapped_abc

        for orig_ip, mapped_ip in mapping.items():
            if "." in orig_ip:  # IPv4
                orig_parts = orig_ip.split(".")
                mapped_parts = mapped_ip.split(".")

                if len(orig_parts) == 4 and len(mapped_parts) == 4:
                    # 检查A.B段一致性
                    orig_ab = ".".join(orig_parts[:2])
                    mapped_ab = ".".join(mapped_parts[:2])

                    if orig_ab in ab_mapping_check:
                        if ab_mapping_check[orig_ab] != mapped_ab:
                            consistency_errors.append(
                                f"A.B-segment mapping inconsistent: {orig_ab} → {ab_mapping_check[orig_ab]} and {mapped_ab}"
                            )
                    else:
                        ab_mapping_check[orig_ab] = mapped_ab

                    # 检查A.B.C段一致性（仅对高频段）
                    orig_abc = ".".join(orig_parts[:3])
                    mapped_abc = ".".join(mapped_parts[:3])

                    if freqs_ipv4[2].get(orig_abc, 0) >= 2:  # 只检查高频A.B.C段
                        if orig_abc in abc_mapping_check:
                            if abc_mapping_check[orig_abc] != mapped_abc:
                                consistency_errors.append(
                                    f"A.B.C-segment mapping inconsistent: {orig_abc} → {abc_mapping_check[orig_abc]} and {mapped_abc}"
                                )
                        else:
                            abc_mapping_check[orig_abc] = mapped_abc

        # Report consistency validation results
        if consistency_errors:
            logger.warning(f"Found {len(consistency_errors)} consistency errors")
            for error in consistency_errors[:5]:  # Only log first 5
                logger.warning(f"Consistency error: {error}")
        else:
            logger.info(
                "All high-frequency network segment mapping consistency validation passed"
            )

        # 验证高频段映射的正确性
        high_freq_ab_segments = {k: v for k, v in freqs_ipv4[1].items() if v >= 2}
        if high_freq_ab_segments:
            logger.debug("High-frequency A.B-segment consistency validation:")
            for orig_ab, freq in sorted(
                high_freq_ab_segments.items(), key=lambda x: x[1], reverse=True
            )[:3]:
                if orig_ab in ab_mapping_check:
                    mapped_ab = ab_mapping_check[orig_ab]
                    logger.debug(
                        f"High-frequency segment mapping: {orig_ab} (frequency:{freq}) → {mapped_ab}"
                    )

        if maps_ipv4[0]:
            sample_mappings = dict(list(maps_ipv4[0].items())[:3])
            logger.debug(f"A-segment mapping examples: {sample_mappings}")

        # Record performance metrics
        end_time = time.time()
        duration = end_time - start_time
        log_performance(
            "ip_create_mapping",
            duration,
            "ip_anonymization.performance",
            total_ips=len(mapping),
            files_processed=len(files_to_process),
        )

        logger.info(
            f"IP mapping creation completed: {len(mapping)} mappings, duration={duration:.2f}s"
        )

        self._ip_map = mapping
        return mapping

    def build_mapping_from_directory(self, all_pcap_files: List[str]):
        """Scan all files and build complete IP mapping."""
        if not all_pcap_files:
            return

        subdir_path = os.path.dirname(all_pcap_files[0])
        filenames = [os.path.basename(p) for p in all_pcap_files]
        error_log = []

        logger = get_logger("anonymization.strategy")
        logger.info(
            f"Starting directory-level mapping construction - file count: {len(filenames)}"
        )
        self.create_mapping(filenames, subdir_path, error_log)

    def anonymize_packet(self, pkt) -> Tuple[object, bool]:
        """Anonymize single packet based on built mapping. 【Enhanced】Support multi-layer encapsulated IP anonymization."""
        is_anonymized = False

        # 【Enhanced】Use encapsulation adapter to analyze packet
        encap_adapter = self._get_encap_adapter()
        ip_analysis = encap_adapter.analyze_packet_for_ip_processing(pkt)

        if ip_analysis["has_encapsulation"] and ip_analysis["ip_layers"]:
            # 【Enhanced】Multi-layer encapsulation processing - anonymize IPs at all layers
            for ip_layer_info in ip_analysis["ip_layers"]:
                ip_layer = ip_layer_info.layer_object

                # Anonymize source IP
                if ip_layer_info.src_ip in self._ip_map:
                    ip_layer.src = self._ip_map[ip_layer_info.src_ip]
                    is_anonymized = True

                # Anonymize destination IP
                if ip_layer_info.dst_ip in self._ip_map:
                    ip_layer.dst = self._ip_map[ip_layer_info.dst_ip]
                    is_anonymized = True
        else:
            # 【Compatibility】Fall back to original logic for simple packets
            # Process IPv4
            if pkt.haslayer(IP):
                layer = pkt.getlayer(IP)
                if layer.src in self._ip_map:
                    layer.src = self._ip_map[layer.src]
                    is_anonymized = True
                if layer.dst in self._ip_map:
                    layer.dst = self._ip_map[layer.dst]
                    is_anonymized = True

            # Process IPv6
            if pkt.haslayer(IPv6):
                layer = pkt.getlayer(IPv6)
                if layer.src in self._ip_map:
                    layer.src = self._ip_map[layer.src]
                    is_anonymized = True
                if layer.dst in self._ip_map:
                    layer.dst = self._ip_map[layer.dst]
                    is_anonymized = True

        # Delete checksums to force recalculation (applies to all modified IP layers)
        if is_anonymized:
            # Clear all potentially affected checksums
            current_layer = pkt
            while current_layer:
                if hasattr(current_layer, "chksum"):
                    del current_layer.chksum
                elif (
                    hasattr(current_layer, "len")
                    and current_layer.__class__.__name__ == "IPv6"
                ):
                    del current_layer.len

                if hasattr(current_layer, "payload"):
                    current_layer = current_layer.payload
                else:
                    break

        return pkt, is_anonymized
