from abc import ABC, abstractmethod
from typing import Dict, Set, List, Tuple
import ipaddress
import random
import os

from scapy.all import PcapReader, PcapNgReader, IP, IPv6, TCP, UDP
from ..infrastructure.logging import get_logger, log_performance
from ..common.exceptions import ProcessingError, NetworkError
from ..common.constants import ProcessingConstants

class AnonymizationStrategy(ABC):
    """IP 匿名化策略的抽象基类。"""

    @abstractmethod
    def create_mapping(self, files_to_process: List[str], subdir_path: str, error_log: List) -> Dict[str, str]:
        """
        根据一组文件创建从原始IP到匿名IP的映射。

        Args:
            files_to_process: 待处理的文件列表。
            subdir_path: 文件所在的子目录。
            error_log: 用于记录错误的列表。

        Returns:
            一个字典，将每个原始IP映射到其新的匿名IP。
        """
        pass

    @abstractmethod
    def reset(self):
        """重置策略的内部状态，以便处理新的目录。"""
        pass

    @abstractmethod
    def build_mapping_from_directory(self, all_pcap_files: List[str]):
        """根据目录中的所有文件构建IP映射。"""
        pass

    @abstractmethod
    def anonymize_packet(self, pkt) -> Tuple[object, bool]:
        """匿名化单个数据包。"""
        pass

    @abstractmethod
    def get_ip_map(self) -> Dict[str, str]:
        """获取当前构建的IP映射。"""
        pass


def ip_sort_key(ip_str: str) -> tuple:
    """根据 IP 字符串生成排序键"""
    # This is a utility function, can be kept here or moved to a utils file.
    # For now, it's closely tied to the hierarchical strategy's need for sorted IPs.
    try:
        if '.' in ip_str:
            parts = ip_str.split('.')
            return (ProcessingConstants.IPV4_SORT_WEIGHT,) + tuple(int(x) for x in parts)
        else:
            try:
                ip_obj = ipaddress.IPv6Address(ip_str)
                ip_str = ip_obj.exploded
            except Exception:
                pass
            parts = ip_str.split(':')
            return (ProcessingConstants.IPV6_SORT_WEIGHT,) + tuple(int(x, ProcessingConstants.HEX_BASE) for x in parts)
    except Exception:
        return (ProcessingConstants.UNKNOWN_IP_SORT_WEIGHT,)

def _safe_hash(input_str: str) -> int:
    """
    安全的哈希函数，确保确定性和分布均匀性
    """
    import hashlib
    # 使用SHA256确保更好的分布和确定性
    hash_obj = hashlib.sha256(input_str.encode('utf-8'))
    return int(hash_obj.hexdigest()[:ProcessingConstants.HASH_DIGEST_LENGTH], ProcessingConstants.HEX_BASE)

def _generate_unique_segment(original_seg: str, seed_base: str, used_values: Set[str], 
                           min_val: int = ProcessingConstants.IPV4_MIN_SEGMENT, max_val: int = ProcessingConstants.IPV4_MAX_SEGMENT, max_attempts: int = 100) -> str:
    """
    生成唯一的IP段值，避免冲突
    
    Args:
        original_seg: 原始段值
        seed_base: 种子基础字符串
        used_values: 已使用的值集合
        min_val: 最小值
        max_val: 最大值
        max_attempts: 最大尝试次数
    """
    if not original_seg.isdigit():
        raise ValueError(f"Invalid segment: {original_seg}")
    
    orig_int = int(original_seg)
    if orig_int < min_val or orig_int > max_val:
        raise ValueError(f"Segment out of range: {original_seg}")
    
    # 基于种子生成确定性随机数生成器
    seed_value = _safe_hash(f"{seed_base}_{original_seg}")
    local_random = random.Random(seed_value)
    
    # 计算候选范围
    n = len(original_seg)
    if n == 1:
        delta = 3
    elif n == 2:
        delta = 5
    else:
        delta = 20
    
    # 首先尝试邻近值范围
    cand_lower = max(min_val, orig_int - delta)
    cand_upper = min(max_val, orig_int + delta)
    
    # 生成候选值，避免原值和已使用值
    candidates = []
    for val in range(cand_lower, cand_upper + 1):
        if val != orig_int and str(val) not in used_values:
            candidates.append(val)
    
    # 如果邻近范围没有可用值，扩展到全范围
    if not candidates:
        for val in range(min_val, max_val + 1):
            if val != orig_int and str(val) not in used_values:
                candidates.append(val)
    
    if not candidates:
        # 如果没有可用值，使用简单的偏移
        for offset in range(1, max_val - min_val + 1):
            val = (orig_int + offset) % (max_val - min_val + 1) + min_val
            if str(val) not in used_values:
                candidates.append(val)
                break
    
    if candidates:
        # 使用确定性随机选择
        choice_idx = local_random.randint(0, len(candidates) - 1)
        result = str(candidates[choice_idx])
        used_values.add(result)
        return result
    else:
        # 最后手段：强制生成不冲突的值
        for val in range(min_val, max_val + 1):
            if str(val) not in used_values:
                used_values.add(str(val))
                return str(val)
        
        # 如果真的没有可用值，返回原值（不应该发生）
        return original_seg

def _generate_new_ipv4_address_hierarchical(original_ip: str, freq1, freq2, freq3, maps, used_segments) -> str:
    """
    基于频率的分层IPv4地址生成，确保高频网段一致性
    """
    ipv4_first_map, ipv4_second_map, ipv4_third_map = maps
    used_a, used_ab, used_abc = used_segments
    
    if not isinstance(original_ip, str): 
        return original_ip
    parts = original_ip.split('.')
    if len(parts) != 4: 
        return original_ip
    A, B, C, D = parts
    
    # A段处理 - 高频A段保持一致映射
    if freq1.get(A, 0) >= 2:
        if A not in ipv4_first_map:
            ipv4_first_map[A] = _generate_unique_segment(
                A, f"first_{A}", used_a, 1, 255
            )
        newA = ipv4_first_map[A]
    else: 
        newA = _generate_unique_segment(
            A, f"first_single_{A}", used_a, 1, 255
        )
    
    # A.B段处理 - 关键修正：高频A.B段保持一致映射
    key2 = ".".join(parts[:2])  # 原始A.B段，如"140.216"
    
    if freq2.get(key2, 0) >= 2:
        # 高频A.B段：必须保持一致映射
        if key2 not in ipv4_second_map:
            # 为这个高频A.B段分配一个新的B段值
            ipv4_second_map[key2] = _generate_unique_segment(
                B, f"second_freq_{key2}", used_ab, 0, 255
            )
        newB = ipv4_second_map[key2]
        
        # 构建新的A.B段组合并记录
        new_ab = f"{newA}.{newB}"
        used_ab.add(new_ab)
    else:
        # 低频A.B段：为每个独立的A.B段生成唯一映射
        if key2 not in ipv4_second_map:
            ipv4_second_map[key2] = _generate_unique_segment(
                B, f"second_single_{key2}", used_ab, 0, 255
            )
        newB = ipv4_second_map[key2]
        
        # 构建新的A.B段组合并记录
        new_ab = f"{newA}.{newB}"
        used_ab.add(new_ab)
    
    # A.B.C段处理 - 高频A.B.C段保持一致映射
    key3 = ".".join(parts[:3])  # 原始A.B.C段，如"140.216.190"
    
    if freq3.get(key3, 0) >= 2:
        # 高频A.B.C段：必须保持一致映射
        if key3 not in ipv4_third_map:
            ipv4_third_map[key3] = _generate_unique_segment(
                C, f"third_freq_{key3}", used_abc, 0, 255
            )
        newC = ipv4_third_map[key3]
        
        # 构建新的A.B.C段组合并记录
        new_abc = f"{newA}.{newB}.{newC}"
        used_abc.add(new_abc)
    else:
        # 低频A.B.C段：为每个独立的A.B.C段生成唯一映射
        if key3 not in ipv4_third_map:
            ipv4_third_map[key3] = _generate_unique_segment(
                C, f"third_single_{key3}", used_abc, 0, 255
            )
        newC = ipv4_third_map[key3]
        
        # 构建新的A.B.C段组合并记录
        new_abc = f"{newA}.{newB}.{newC}"
        used_abc.add(new_abc)
    
    return f"{newA}.{newB}.{newC}.{D}"

def _generate_new_ipv6_address_hierarchical(original_ip: str, freqs, maps) -> str:
    """
    基于频率的分层IPv6地址生成
    """
    try:
        ip_obj = ipaddress.IPv6Address(original_ip)
        parts = ip_obj.exploded.split(':')
    except Exception: 
        return original_ip
    if len(parts) != 8: 
        return original_ip
    
    new_parts = []
    for i in range(7):
        key = ":".join(parts[:i+1])
        if freqs[i].get(key, 0) >= 2:
            if key not in maps[i]: 
                maps[i][key] = _generate_unique_ipv6_segment(parts[i], f"ipv6_{i}_{key}")
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
    upper = 16 ** n - 1
    if n == 1: delta = 3
    elif n == 2: delta = 8
    elif n == 3: delta = 32
    elif n == 4: delta = 128
    else: delta = 256
    
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
    
    return format(result, 'x').zfill(n)

class HierarchicalAnonymizationStrategy(AnonymizationStrategy):
    """
    基于网段频率的分层IP匿名化策略。
    该策略会预扫描文件以保留子网结构。
    """
    def __init__(self):
        self._ip_map: Dict[str, str] = {}
        # 新增：封装处理适配器（延迟初始化以避免循环导入）
        self._encap_adapter = None
        self._encap_stats = {
            'total_packets_scanned': 0,
            'encapsulated_packets': 0,
            'multi_layer_ip_packets': 0,
            'plain_packets': 0
        }

    def _get_encap_adapter(self):
        """延迟初始化封装适配器以避免循环导入"""
        if self._encap_adapter is None:
            from pktmask.adapters.encapsulation_adapter import ProcessingAdapter
            self._encap_adapter = ProcessingAdapter()
        return self._encap_adapter

    def reset(self):
        self._ip_map = {}
        # 重置封装统计
        if self._encap_adapter is not None:
            self._encap_adapter.reset_stats()
        self._encap_stats = {
            'total_packets_scanned': 0,
            'encapsulated_packets': 0,
            'multi_layer_ip_packets': 0,
            'plain_packets': 0
        }

    def get_ip_map(self) -> Dict[str, str]:
        return self._ip_map

    def _prescan_addresses(self, files_to_process: List[str], subdir_path: str, error_log: List[str]) -> Tuple:
        """
        修正版本：正确统计所有IP地址（源和目标）的频率
        """
        import time
        from pktmask.infrastructure.logging import log_performance
        
        start_time = time.time()
        
        freq_ipv4_1, freq_ipv4_2, freq_ipv4_3 = {}, {}, {}
        freq_ipv6_1, freq_ipv6_2, freq_ipv6_3, freq_ipv6_4, freq_ipv6_5, freq_ipv6_6, freq_ipv6_7 = {}, {}, {}, {}, {}, {}, {}
        unique_ips = set()
        
        def process_ipv4_address(ip_str: str):
            """处理单个IPv4地址的频率统计"""
            unique_ips.add(ip_str)
            try: 
                ipaddress.IPv4Address(ip_str)
            except Exception: 
                return
            parts = ip_str.split('.')
            if len(parts) != 4: 
                return
            # 统计各级频率
            freq_ipv4_1[parts[0]] = freq_ipv4_1.get(parts[0], 0) + 1
            freq_ipv4_2[".".join(parts[:2])] = freq_ipv4_2.get(".".join(parts[:2]), 0) + 1
            freq_ipv4_3[".".join(parts[:3])] = freq_ipv4_3.get(".".join(parts[:3]), 0) + 1

        def process_ipv6_address(ip_str: str):
            """处理单个IPv6地址的频率统计"""
            unique_ips.add(ip_str)
            try: 
                ip_obj = ipaddress.IPv6Address(ip_str)
            except Exception: 
                return
            parts = ip_obj.exploded.split(':')
            if len(parts) != 8: 
                return
            # 统计各级前缀频率
            freq_ipv6_1[parts[0]] = freq_ipv6_1.get(parts[0], 0) + 1
            freq_ipv6_2[":".join(parts[:2])] = freq_ipv6_2.get(":".join(parts[:2]), 0) + 1
            freq_ipv6_3[":".join(parts[:3])] = freq_ipv6_3.get(":".join(parts[:3]), 0) + 1
            freq_ipv6_4[":".join(parts[:4])] = freq_ipv6_4.get(":".join(parts[:4]), 0) + 1
            freq_ipv6_5[":".join(parts[:5])] = freq_ipv6_5.get(":".join(parts[:5]), 0) + 1
            freq_ipv6_6[":".join(parts[:6])] = freq_ipv6_6.get(":".join(parts[:6]), 0) + 1
            freq_ipv6_7[":".join(parts[:7])] = freq_ipv6_7.get(":".join(parts[:7]), 0) + 1
        
        for f in files_to_process:
            file_path = os.path.join(subdir_path, f)
            ext = os.path.splitext(f)[1].lower()
            try:
                reader_class = PcapNgReader if ext == ".pcapng" else PcapReader
                with reader_class(file_path) as reader:
                    for packet in reader:
                        self._encap_stats['total_packets_scanned'] += 1
                        
                        # 【增强】使用封装适配器分析数据包，提取所有层级的IP
                        encap_adapter = self._get_encap_adapter()
                        ip_analysis = encap_adapter.analyze_packet_for_ip_processing(packet)
                        
                        # 更新封装统计
                        if ip_analysis['has_encapsulation']:
                            self._encap_stats['encapsulated_packets'] += 1
                            if ip_analysis['has_multiple_ips']:
                                self._encap_stats['multi_layer_ip_packets'] += 1
                        else:
                            self._encap_stats['plain_packets'] += 1
                        
                        # 【增强】处理所有层级的IP地址
                        ip_pairs = encap_adapter.extract_ips_for_anonymization(ip_analysis)
                        for src_ip, dst_ip, context in ip_pairs:
                            # 处理IPv4地址
                            if '.' in src_ip:
                                process_ipv4_address(src_ip)
                            elif ':' in src_ip:
                                process_ipv6_address(src_ip)
                            
                            if '.' in dst_ip:
                                process_ipv4_address(dst_ip)
                            elif ':' in dst_ip:
                                process_ipv6_address(dst_ip)
                        
                        # 【兼容性】保持原有的简单IP提取作为备选
                        if not ip_pairs:
                            # 回退到原有逻辑
                            if packet.haslayer(IP):
                                process_ipv4_address(packet.getlayer(IP).src)
                                process_ipv4_address(packet.getlayer(IP).dst)
                            
                            if packet.haslayer(IPv6):
                                process_ipv6_address(packet.getlayer(IPv6).src)
                                process_ipv6_address(packet.getlayer(IPv6).dst)
                            
            except Exception as e:
                error_log.append(f"Error scanning file {file_path}: {str(e)}")
        
        # 记录频率统计信息和性能指标
        end_time = time.time()
        duration = end_time - start_time
        
        # 【增强】获取封装处理统计
        encap_proc_stats = encap_adapter.get_processing_stats()
        
        log_performance('ip_prescan_addresses', duration, 'ip_anonymization.performance', 
                       files_processed=len(files_to_process), unique_ips=len(unique_ips),
                       encapsulated_packets=self._encap_stats['encapsulated_packets'],
                       multi_layer_ip_packets=self._encap_stats['multi_layer_ip_packets'])
        
        logger = get_logger('anonymization.strategy')
        logger.info(f"频率统计完成: 唯一IP总数={len(unique_ips)}, 耗时={duration:.2f}秒")
        
        # 【增强】封装处理统计报告
        logger.info(f"封装处理统计: 总包数={self._encap_stats['total_packets_scanned']}, "
                   f"封装包数={self._encap_stats['encapsulated_packets']}, "
                   f"多层IP包数={self._encap_stats['multi_layer_ip_packets']}, "
                   f"普通包数={self._encap_stats['plain_packets']}")
        if self._encap_stats['total_packets_scanned'] > 0:
            encap_ratio = self._encap_stats['encapsulated_packets'] / self._encap_stats['total_packets_scanned']
            multi_ip_ratio = self._encap_stats['multi_layer_ip_packets'] / self._encap_stats['total_packets_scanned']
            logger.info(f"封装比例: {encap_ratio:.1%}, 多层IP比例: {multi_ip_ratio:.1%}")
        
        if encap_proc_stats['encapsulation_distribution']:
            logger.debug(f"封装类型分布: {encap_proc_stats['encapsulation_distribution']}")
        
        if freq_ipv4_1:
            top_ipv4_a = dict(sorted(freq_ipv4_1.items(), key=lambda x: x[1], reverse=True)[:5])
            logger.debug(f"IPv4 A段频率统计(前5): {top_ipv4_a}")
        if freq_ipv4_2:
            top_ipv4_ab = dict(sorted(freq_ipv4_2.items(), key=lambda x: x[1], reverse=True)[:5])
            logger.debug(f"IPv4 A.B段频率统计(前5): {top_ipv4_ab}")
        
        return (freq_ipv4_1, freq_ipv4_2, freq_ipv4_3), \
               (freq_ipv6_1, freq_ipv6_2, freq_ipv6_3, freq_ipv6_4, freq_ipv6_5, freq_ipv6_6, freq_ipv6_7), \
               unique_ips
    
    def create_mapping(self, files_to_process: List[str], subdir_path: str, error_log: List[str]) -> Dict[str, str]:
        """
        创建IP映射，确保无冲突
        """
        import time
        from pktmask.infrastructure.logging import log_performance
        
        start_time = time.time()
        
        freqs_ipv4, freqs_ipv6, all_ips = self._prescan_addresses(files_to_process, subdir_path, error_log)
        
        mapping = {}
        maps_ipv4 = ({}, {}, {})
        maps_ipv6 = ({}, {}, {}, {}, {}, {}, {})
        
        # 用于跟踪已使用的段值，确保唯一性
        used_segments = (set(), set(), set())  # (A段, A.B段, A.B.C段)
        
        sorted_ips = sorted(all_ips, key=ip_sort_key)
        
        # 记录映射生成开始信息
        logger = get_logger('anonymization.strategy')
        ipv4_count = sum(1 for ip in sorted_ips if '.' in ip)
        logger.info(f"开始生成映射 - IPv4地址数: {ipv4_count}, 总IP数: {len(sorted_ips)}")
        
        for ip in sorted_ips:
            try:
                ip_obj = ipaddress.ip_address(ip)
                if ip_obj.version == 4:
                    mapping[ip] = _generate_new_ipv4_address_hierarchical(
                        ip, freqs_ipv4[0], freqs_ipv4[1], freqs_ipv4[2], maps_ipv4, used_segments
                    )
                else:
                    mapping[ip] = _generate_new_ipv6_address_hierarchical(
                        ip, freqs_ipv6, maps_ipv6
                    )
            except Exception as e:
                error_log.append(f"Pre-calculate mapping error for IP {ip}: {str(e)}")
        
        # 记录分层映射统计信息
        logger.info(f"分层映射生成完成: A段映射数={len(maps_ipv4[0])}, A.B段映射数={len(maps_ipv4[1])}, A.B.C段映射数={len(maps_ipv4[2])}")
        logger.debug(f"唯一段数统计: A段={len(used_segments[0])}, A.B段={len(used_segments[1])}, A.B.C段={len(used_segments[2])}")
        
        # 验证高频网段的一致性映射
        consistency_errors = []
        ab_mapping_check = {}  # original_ab -> mapped_ab
        abc_mapping_check = {}  # original_abc -> mapped_abc
        
        for orig_ip, mapped_ip in mapping.items():
            if '.' in orig_ip:  # IPv4
                orig_parts = orig_ip.split('.')
                mapped_parts = mapped_ip.split('.')
                
                if len(orig_parts) == 4 and len(mapped_parts) == 4:
                    # 检查A.B段一致性
                    orig_ab = '.'.join(orig_parts[:2])
                    mapped_ab = '.'.join(mapped_parts[:2])
                    
                    if orig_ab in ab_mapping_check:
                        if ab_mapping_check[orig_ab] != mapped_ab:
                            consistency_errors.append(
                                f"A.B段映射不一致: {orig_ab} → {ab_mapping_check[orig_ab]} 和 {mapped_ab}"
                            )
                    else:
                        ab_mapping_check[orig_ab] = mapped_ab
                    
                    # 检查A.B.C段一致性（仅对高频段）
                    orig_abc = '.'.join(orig_parts[:3])
                    mapped_abc = '.'.join(mapped_parts[:3])
                    
                    if freqs_ipv4[2].get(orig_abc, 0) >= 2:  # 只检查高频A.B.C段
                        if orig_abc in abc_mapping_check:
                            if abc_mapping_check[orig_abc] != mapped_abc:
                                consistency_errors.append(
                                    f"A.B.C段映射不一致: {orig_abc} → {abc_mapping_check[orig_abc]} 和 {mapped_abc}"
                                )
                        else:
                            abc_mapping_check[orig_abc] = mapped_abc
        
        # 报告一致性验证结果
        if consistency_errors:
            logger.warning(f"发现 {len(consistency_errors)} 个一致性错误")
            for error in consistency_errors[:5]:  # 只记录前5个
                logger.warning(f"一致性错误: {error}")
        else:
            logger.info("所有高频网段映射一致性验证通过")
        
        # 验证高频段映射的正确性
        high_freq_ab_segments = {k: v for k, v in freqs_ipv4[1].items() if v >= 2}
        if high_freq_ab_segments:
            logger.debug("高频A.B段一致性验证:")
            for orig_ab, freq in sorted(high_freq_ab_segments.items(), key=lambda x: x[1], reverse=True)[:3]:
                if orig_ab in ab_mapping_check:
                    mapped_ab = ab_mapping_check[orig_ab]
                    logger.debug(f"高频段映射: {orig_ab} (频率:{freq}) → {mapped_ab}")
        
        if maps_ipv4[0]:
            sample_mappings = dict(list(maps_ipv4[0].items())[:3])
            logger.debug(f"A段映射示例: {sample_mappings}")
        
        # 记录性能指标
        end_time = time.time()
        duration = end_time - start_time
        log_performance('ip_create_mapping', duration, 'ip_anonymization.performance',
                       total_ips=len(mapping), files_processed=len(files_to_process))
        
        logger.info(f"IP映射创建完成: {len(mapping)}个映射, 耗时={duration:.2f}秒")
        
        self._ip_map = mapping
        return mapping

    def build_mapping_from_directory(self, all_pcap_files: List[str]):
        """扫描所有文件并构建完整的IP映射。"""
        if not all_pcap_files:
            return
        
        subdir_path = os.path.dirname(all_pcap_files[0])
        filenames = [os.path.basename(p) for p in all_pcap_files]
        error_log = []

        logger = get_logger('anonymization.strategy')
        logger.info(f"开始构建目录级映射 - 文件数: {len(filenames)}")
        self.create_mapping(filenames, subdir_path, error_log)

    def anonymize_packet(self, pkt) -> Tuple[object, bool]:
        """根据已构建的映射匿名化单个数据包。【增强】支持多层封装IP匿名化。"""
        is_anonymized = False
        
        # 【增强】使用封装适配器分析数据包
        encap_adapter = self._get_encap_adapter()
        ip_analysis = encap_adapter.analyze_packet_for_ip_processing(pkt)
        
        if ip_analysis['has_encapsulation'] and ip_analysis['ip_layers']:
            # 【增强】多层封装处理 - 匿名化所有层级的IP
            for ip_layer_info in ip_analysis['ip_layers']:
                ip_layer = ip_layer_info.layer_object
                
                # 匿名化源IP
                if ip_layer_info.src_ip in self._ip_map:
                    ip_layer.src = self._ip_map[ip_layer_info.src_ip]
                    is_anonymized = True
                
                # 匿名化目标IP
                if ip_layer_info.dst_ip in self._ip_map:
                    ip_layer.dst = self._ip_map[ip_layer_info.dst_ip]
                    is_anonymized = True
        else:
            # 【兼容性】回退到原有逻辑处理简单数据包
            # 处理IPv4
            if pkt.haslayer(IP):
                layer = pkt.getlayer(IP)
                if layer.src in self._ip_map:
                    layer.src = self._ip_map[layer.src]
                    is_anonymized = True
                if layer.dst in self._ip_map:
                    layer.dst = self._ip_map[layer.dst]
                    is_anonymized = True
            
            # 处理IPv6
            if pkt.haslayer(IPv6):
                layer = pkt.getlayer(IPv6)
                if layer.src in self._ip_map:
                    layer.src = self._ip_map[layer.src]
                    is_anonymized = True
                if layer.dst in self._ip_map:
                    layer.dst = self._ip_map[layer.dst]
                    is_anonymized = True
                
        # 删除校验和以强制重新计算（适用于所有被修改的IP层）
        if is_anonymized:
            # 清除所有可能受影响的校验和
            current_layer = pkt
            while current_layer:
                if hasattr(current_layer, 'chksum'):
                    del current_layer.chksum
                elif hasattr(current_layer, 'len') and current_layer.__class__.__name__ == 'IPv6':
                    del current_layer.len
                
                if hasattr(current_layer, 'payload'):
                    current_layer = current_layer.payload
                else:
                    break
            
        return pkt, is_anonymized 