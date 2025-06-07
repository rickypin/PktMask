from abc import ABC, abstractmethod
from typing import Dict, Set, List, Tuple
import ipaddress
import random
import os

from scapy.all import PcapReader, PcapNgReader, IP, IPv6, TCP, UDP

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
            return (4,) + tuple(int(x) for x in parts)
        else:
            try:
                ip_obj = ipaddress.IPv6Address(ip_str)
                ip_str = ip_obj.exploded
            except Exception:
                pass
            parts = ip_str.split(':')
            return (6,) + tuple(int(x, 16) for x in parts)
    except Exception:
        return (99,)

def _randomize_ipv4_segment(original_seg: str) -> str:
    # (implementation moved from ip_processor)
    if not original_seg.isdigit():
        raise ValueError(f"Invalid IPv4 segment: {original_seg}")
    orig_int = int(original_seg)
    if orig_int < 0 or orig_int > 255:
        raise ValueError(f"IPv4 segment out of range: {original_seg}")
    n = len(original_seg)
    if n == 1:
        lower, upper, delta = 0, 9, 2
    elif n == 2:
        lower, upper, delta = 10, 99, 3
    elif n == 3:
        lower, upper, delta = 100, 255, 20
    else:
        lower = 10 ** (n - 1)
        upper = min(10 ** n - 1, 255)
        delta = 20
    cand_lower = max(lower, orig_int - delta)
    cand_upper = min(upper, orig_int + delta)
    count = (cand_upper - cand_lower + 1) - 1
    if count <= 0:
        cand_lower, cand_upper = lower, upper
        count = (upper - lower + 1) - 1
    r = random.randint(0, count - 1)
    candidate = cand_lower + r
    if candidate >= orig_int:
        candidate += 1
    return str(candidate)

def _randomize_ipv6_segment(original_seg: str) -> str:
    # (implementation moved from ip_processor)
    n = len(original_seg)
    orig_int = int(original_seg, 16)
    lower = 16 ** (n - 1) if n > 1 else 0
    upper = 16 ** n - 1
    if n == 1: delta = 2
    elif n == 2: delta = 5
    elif n == 3: delta = 20
    elif n == 4: delta = 50
    else: delta = 50
    cand_lower = max(lower, orig_int - delta)
    cand_upper = min(upper, orig_int + delta)
    count = (cand_upper - cand_lower + 1) - 1
    if count <= 0:
        cand_lower, cand_upper = lower, upper
        count = (upper - lower + 1) - 1
    r = random.randint(0, count - 1)
    candidate = cand_lower + r
    if candidate >= orig_int:
        candidate += 1
    return format(candidate, 'x').zfill(n)

def _generate_new_ipv4_address_hierarchical(original_ip: str, freq1, freq2, freq3, maps) -> str:
    # (implementation moved from ip_processor)
    ipv4_first_map, ipv4_second_map, ipv4_third_map = maps
    if not isinstance(original_ip, str): return original_ip
    parts = original_ip.split('.')
    if len(parts) != 4: return original_ip
    A, B, C, D = parts
    
    if freq1.get(A, 0) >= 2:
        if A not in ipv4_first_map: ipv4_first_map[A] = _randomize_ipv4_segment(A)
        newA = ipv4_first_map[A]
    else: newA = _randomize_ipv4_segment(A)
    
    key2 = ".".join(parts[:2])
    if freq2.get(key2, 0) >= 2:
        if key2 not in ipv4_second_map: ipv4_second_map[key2] = _randomize_ipv4_segment(B)
        newB = ipv4_second_map[key2]
    else: newB = _randomize_ipv4_segment(B)
    
    key3 = ".".join(parts[:3])
    if freq3.get(key3, 0) >= 2:
        if key3 not in ipv4_third_map: ipv4_third_map[key3] = _randomize_ipv4_segment(C)
        newC = ipv4_third_map[key3]
    else: newC = _randomize_ipv4_segment(C)
    
    return f"{newA}.{newB}.{newC}.{D}"

def _generate_new_ipv6_address_hierarchical(original_ip: str, freqs, maps) -> str:
    # (implementation moved from ip_processor)
    try:
        ip_obj = ipaddress.IPv6Address(original_ip)
        parts = ip_obj.exploded.split(':')
    except Exception: return original_ip
    if len(parts) != 8: return original_ip
    
    new_parts = []
    for i in range(7):
        key = ":".join(parts[:i+1])
        if freqs[i].get(key, 0) >= 2:
            if key not in maps[i]: maps[i][key] = _randomize_ipv6_segment(parts[i])
            new_seg = maps[i][key]
        else: new_seg = _randomize_ipv6_segment(parts[i])
        new_parts.append(new_seg)
    
    new_parts.append(parts[7])
    return ":".join(new_parts)

class HierarchicalAnonymizationStrategy(AnonymizationStrategy):
    """
    基于网段频率的分层IP匿名化策略。
    该策略会预扫描文件以保留子网结构。
    """
    def __init__(self):
        self._ip_map: Dict[str, str] = {}

    def reset(self):
        self._ip_map = {}

    def get_ip_map(self) -> Dict[str, str]:
        return self._ip_map

    def _prescan_addresses(self, files_to_process: List[str], subdir_path: str, error_log: List[str]) -> Tuple:
        freq_ipv4_1, freq_ipv4_2, freq_ipv4_3 = {}, {}, {}
        freq_ipv6_1, freq_ipv6_2, freq_ipv6_3, freq_ipv6_4, freq_ipv6_5, freq_ipv6_6, freq_ipv6_7 = {}, {}, {}, {}, {}, {}, {}
        unique_ips = set()
        
        for f in files_to_process:
            file_path = os.path.join(subdir_path, f)
            ext = os.path.splitext(f)[1].lower()
            try:
                reader_class = PcapNgReader if ext == ".pcapng" else PcapReader
                with reader_class(file_path) as reader:
                    for packet in reader:
                        if packet.haslayer(IP):
                            ip_str = packet.getlayer(IP).src
                            unique_ips.add(ip_str)
                            unique_ips.add(packet.getlayer(IP).dst)
                            try: ipaddress.IPv4Address(ip_str)
                            except Exception: continue
                            parts = ip_str.split('.')
                            if len(parts) != 4: continue
                            freq_ipv4_1[parts[0]] = freq_ipv4_1.get(parts[0], 0) + 1
                            freq_ipv4_2[".".join(parts[:2])] = freq_ipv4_2.get(".".join(parts[:2]), 0) + 1
                            freq_ipv4_3[".".join(parts[:3])] = freq_ipv4_3.get(".".join(parts[:3]), 0) + 1
                        if packet.haslayer(IPv6):
                            ip_str = packet.getlayer(IPv6).src
                            unique_ips.add(ip_str)
                            unique_ips.add(packet.getlayer(IPv6).dst)
                            try: ip_obj = ipaddress.IPv6Address(ip_str)
                            except Exception: continue
                            parts = ip_obj.exploded.split(':')
                            if len(parts) != 8: continue
                            freq_ipv6_1[parts[0]] = freq_ipv6_1.get(parts[0], 0) + 1
                            freq_ipv6_2[":".join(parts[:2])] = freq_ipv6_2.get(":".join(parts[:2]), 0) + 1
                            freq_ipv6_3[":".join(parts[:3])] = freq_ipv6_3.get(":".join(parts[:3]), 0) + 1
                            freq_ipv6_4[":".join(parts[:4])] = freq_ipv6_4.get(":".join(parts[:4]), 0) + 1
                            freq_ipv6_5[":".join(parts[:5])] = freq_ipv6_5.get(":".join(parts[:5]), 0) + 1
                            freq_ipv6_6[":".join(parts[:6])] = freq_ipv6_6.get(":".join(parts[:6]), 0) + 1
                            freq_ipv6_7[":".join(parts[:7])] = freq_ipv6_7.get(":".join(parts[:7]), 0) + 1
            except Exception as e:
                error_log.append(f"Error scanning file {file_path}: {str(e)}")
        
        return (freq_ipv4_1, freq_ipv4_2, freq_ipv4_3), \
               (freq_ipv6_1, freq_ipv6_2, freq_ipv6_3, freq_ipv6_4, freq_ipv6_5, freq_ipv6_6, freq_ipv6_7), \
               unique_ips
    
    def create_mapping(self, files_to_process: List[str], subdir_path: str, error_log: List[str]) -> Dict[str, str]:
        freqs_ipv4, freqs_ipv6, all_ips = self._prescan_addresses(files_to_process, subdir_path, error_log)
        
        mapping = {}
        maps_ipv4 = ({}, {}, {})
        maps_ipv6 = ({}, {}, {}, {}, {}, {}, {})
        
        sorted_ips = sorted(all_ips, key=ip_sort_key)
        
        for ip in sorted_ips:
            try:
                ip_obj = ipaddress.ip_address(ip)
                if ip_obj.version == 4:
                    mapping[ip] = _generate_new_ipv4_address_hierarchical(
                        ip, freqs_ipv4[0], freqs_ipv4[1], freqs_ipv4[2], maps_ipv4
                    )
                else:
                    mapping[ip] = _generate_new_ipv6_address_hierarchical(
                        ip, freqs_ipv6, maps_ipv6
                    )
            except Exception as e:
                error_log.append(f"Pre-calculate mapping error for IP {ip}: {str(e)}")
        
        self._ip_map = mapping
        return mapping

    def build_mapping_from_directory(self, all_pcap_files: List[str]):
        """扫描所有文件并构建完整的IP映射。"""
        if not all_pcap_files:
            return
        
        subdir_path = os.path.dirname(all_pcap_files[0])
        filenames = [os.path.basename(p) for p in all_pcap_files]
        error_log = []

        self.create_mapping(filenames, subdir_path, error_log)

    def anonymize_packet(self, pkt) -> Tuple[object, bool]:
        """根据已构建的映射匿名化单个数据包。"""
        is_anonymized = False
        
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
                
        # 删除校验和以强制重新计算
        if is_anonymized:
            if pkt.haslayer(IP): del pkt.getlayer(IP).chksum
            if pkt.haslayer(IPv6): del pkt.getlayer(IPv6).len
            if pkt.haslayer(TCP): del pkt.getlayer(TCP).chksum
            if pkt.haslayer(UDP): del pkt.getlayer(UDP).chksum
            
        return pkt, is_anonymized 