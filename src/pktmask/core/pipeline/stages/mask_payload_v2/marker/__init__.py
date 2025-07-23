"""
Marker模块 - 协议分析和保留规则生成

本模块负责分析 pcap/pcapng 文件中的协议流量，识别需要保留的数据区段，
并生成结构化的 KeepRule 清单。

核心组件：
- ProtocolMarker: 协议标记器基类
- TLSProtocolMarker: TLS协议标记器实现
- KeepRule/KeepRuleSet: 保留规则数据结构

技术特点：
- 基于 tshark 的深度协议分析
- 支持 TCP 序列号回绕处理
- 复用 tls_flow_analyzer 的核心算法
- 支持多协议扩展
"""

from .base import ProtocolMarker
from .tls_marker import TLSProtocolMarker
from .types import FlowInfo, KeepRule, KeepRuleSet

__all__ = ["ProtocolMarker", "TLSProtocolMarker", "KeepRule", "KeepRuleSet", "FlowInfo"]
