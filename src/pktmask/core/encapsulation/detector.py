"""
封装检测引擎

自动检测数据包的封装类型，支持各种网络封装协议的识别。
使用Scapy的层检测能力和自定义匹配模式实现智能检测。
"""

import logging
from typing import List, Dict, Callable, Optional, Set
from scapy.packet import Packet
from scapy.layers.inet import IP
from scapy.layers.inet6 import IPv6
from scapy.layers.l2 import Ether, Dot1Q
try:
    from scapy.layers.l2 import Dot1AD  # 双层VLAN支持
except ImportError:
    Dot1AD = None
from scapy.contrib.mpls import MPLS
try:
    from scapy.contrib.vxlan import VXLAN
except ImportError:
    VXLAN = None
from scapy.layers.inet import GRE

from .types import (
    EncapsulationType, 
    EncapsulationError,
    UnsupportedEncapsulationError
)


class EncapsulationDetector:
    """
    封装检测引擎
    
    负责自动检测数据包的封装类型，支持：
    - 无封装 (Plain IP)
    - VLAN封装 (802.1Q)
    - 双层VLAN封装 (QinQ/802.1ad)
    - MPLS封装
    - VXLAN封装
    - GRE隧道
    - 复合封装
    """
    
    def __init__(self):
        """初始化检测引擎"""
        self.logger = logging.getLogger(__name__)
        
        # 检测模式映射表 - 按优先级排序
        self._detection_patterns: Dict[EncapsulationType, Callable] = {
            EncapsulationType.DOUBLE_VLAN: self._detect_double_vlan,
            EncapsulationType.VLAN: self._detect_vlan,
            EncapsulationType.VXLAN: self._detect_vxlan,
            EncapsulationType.GRE: self._detect_gre,
            EncapsulationType.MPLS: self._detect_mpls,
            EncapsulationType.PLAIN: self._detect_plain,
        }
        
        # 缓存最近检测结果，提高性能
        self._detection_cache: Dict[str, EncapsulationType] = {}
        self._cache_max_size = 1000
    
    def detect_encapsulation_type(self, packet: Packet) -> EncapsulationType:
        """
        自动检测封装类型
        
        Args:
            packet: 要检测的数据包
            
        Returns:
            检测到的封装类型
            
        Raises:
            EncapsulationError: 检测过程中出现错误
        """
        try:
            # 生成包的特征键用于缓存
            cache_key = self._generate_cache_key(packet)
            if cache_key in self._detection_cache:
                return self._detection_cache[cache_key]
            
            # 检测复合封装
            detected_types = set()
            for encap_type, detector in self._detection_patterns.items():
                if detector(packet):
                    detected_types.add(encap_type)
                    self.logger.debug(f"检测到封装类型: {encap_type.value}")
            
            # 确定最终封装类型
            final_type = self._resolve_encapsulation_type(detected_types)
            
            # 缓存结果
            self._cache_result(cache_key, final_type)
            
            self.logger.info(f"数据包封装类型检测完成: {final_type.value}")
            return final_type
            
        except Exception as e:
            error_msg = f"封装类型检测失败: {str(e)}"
            self.logger.error(error_msg)
            raise EncapsulationError(error_msg) from e
    
    def is_encapsulated(self, packet: Packet) -> bool:
        """
        检查数据包是否包含封装
        
        Args:
            packet: 要检查的数据包
            
        Returns:
            True如果包含封装，False如果是无封装的IP包
        """
        try:
            encap_type = self.detect_encapsulation_type(packet)
            return encap_type != EncapsulationType.PLAIN
        except Exception:
            return False
    
    def get_encapsulation_depth(self, packet: Packet) -> int:
        """
        获取封装深度
        
        Args:
            packet: 要分析的数据包
            
        Returns:
            封装层数(0表示无封装)
        """
        try:
            depth = 0
            current = packet
            
            # 递归计算层深度
            while current:
                if hasattr(current, 'payload') and current.payload:
                    if self._is_encapsulation_layer(current):
                        depth += 1
                    current = current.payload
                else:
                    break
            
            return depth
            
        except Exception as e:
            self.logger.warning(f"计算封装深度失败: {str(e)}")
            return 0
    
    def get_supported_encapsulations(self) -> List[EncapsulationType]:
        """
        获取支持的封装类型列表
        
        Returns:
            支持的封装类型列表
        """
        return list(self._detection_patterns.keys())
    
    # === 具体检测方法 ===
    
    def _detect_vlan(self, packet: Packet) -> bool:
        """检测VLAN封装 (802.1Q)"""
        try:
            return packet.haslayer(Dot1Q) and not self._detect_double_vlan(packet)
        except Exception:
            return False
    
    def _detect_double_vlan(self, packet: Packet) -> bool:
        """检测双层VLAN封装 (QinQ/802.1ad)"""
        try:
            # 方法1: 检测是否存在Dot1AD层
            if Dot1AD and packet.haslayer(Dot1AD):
                return True
            
            # 方法2: 检测连续的两个Dot1Q层
            if packet.haslayer(Dot1Q):
                dot1q_layer = packet[Dot1Q]
                if hasattr(dot1q_layer, 'payload') and dot1q_layer.payload.haslayer(Dot1Q):
                    return True
            
            # 方法3: 检测EtherType模式 (0x88a8 + 0x8100)
            if packet.haslayer(Ether):
                ether_layer = packet[Ether]
                if hasattr(ether_layer, 'type') and ether_layer.type == 0x88a8:
                    return True
            
            return False
            
        except Exception:
            return False
    
    def _detect_mpls(self, packet: Packet) -> bool:
        """检测MPLS封装"""
        try:
            return packet.haslayer(MPLS)
        except Exception:
            return False
    
    def _detect_vxlan(self, packet: Packet) -> bool:
        """检测VXLAN封装"""
        try:
            if VXLAN is None:
                return False
            return packet.haslayer(VXLAN)
        except Exception:
            return False
    
    def _detect_gre(self, packet: Packet) -> bool:
        """检测GRE封装"""
        try:
            return packet.haslayer(GRE)
        except Exception:
            return False
    
    def _detect_plain(self, packet: Packet) -> bool:
        """检测无封装 (直接IP)"""
        try:
            # 有IP层但没有其他封装层
            has_ip = packet.haslayer(IP) or packet.haslayer(IPv6)
            has_encap = (packet.haslayer(Dot1Q) or 
                        packet.haslayer(MPLS) or
                        packet.haslayer(GRE) or
                        (VXLAN and packet.haslayer(VXLAN)))
            
            return has_ip and not has_encap
            
        except Exception:
            return False
    
    # === 辅助方法 ===
    
    def _resolve_encapsulation_type(self, detected_types: Set[EncapsulationType]) -> EncapsulationType:
        """
        解析最终的封装类型
        
        当检测到多种封装类型时，确定优先级最高的类型
        """
        if not detected_types:
            return EncapsulationType.UNKNOWN
        
        if len(detected_types) == 1:
            return detected_types.pop()
        
        # 多种封装类型的优先级处理
        priority_order = [
            EncapsulationType.DOUBLE_VLAN,  # 双层VLAN优先级最高
            EncapsulationType.VLAN,
            EncapsulationType.VXLAN,
            EncapsulationType.GRE,
            EncapsulationType.MPLS,
            EncapsulationType.PLAIN,
        ]
        
        for encap_type in priority_order:
            if encap_type in detected_types:
                if len(detected_types) > 1:
                    self.logger.info(f"检测到复合封装，选择优先级最高的类型: {encap_type.value}")
                return encap_type
        
        return EncapsulationType.COMPOSITE
    
    def _is_encapsulation_layer(self, layer: Packet) -> bool:
        """判断是否为封装层"""
        encap_layer_types = [Dot1Q, MPLS, GRE]
        if VXLAN:
            encap_layer_types.append(VXLAN)
        if Dot1AD:
            encap_layer_types.append(Dot1AD)
        
        return any(isinstance(layer, layer_type) for layer_type in encap_layer_types)
    
    def _generate_cache_key(self, packet: Packet) -> str:
        """生成数据包的缓存键"""
        try:
            # 使用层结构生成简单的特征键
            layers = []
            current = packet
            depth = 0
            
            while current and depth < 10:  # 限制深度避免无限循环
                layer_name = current.__class__.__name__
                layers.append(layer_name)
                if hasattr(current, 'payload'):
                    current = current.payload
                    depth += 1
                else:
                    break
            
            return "|".join(layers)
            
        except Exception:
            # 如果生成缓存键失败，返回空字符串(不使用缓存)
            return ""
    
    def _cache_result(self, cache_key: str, result: EncapsulationType):
        """缓存检测结果"""
        if not cache_key:
            return
        
        # 如果缓存已满，清除旧条目
        if len(self._detection_cache) >= self._cache_max_size:
            # 清除一半的缓存
            keys_to_remove = list(self._detection_cache.keys())[:self._cache_max_size // 2]
            for key in keys_to_remove:
                del self._detection_cache[key]
        
        self._detection_cache[cache_key] = result
    
    def clear_cache(self):
        """清除检测缓存"""
        self._detection_cache.clear()
        self.logger.debug("封装检测缓存已清除")
    
    def get_cache_stats(self) -> Dict[str, int]:
        """获取缓存统计信息"""
        return {
            "cache_size": len(self._detection_cache),
            "cache_max_size": self._cache_max_size
        } 