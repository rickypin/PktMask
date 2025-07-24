"""
PktMask 多层封装处理模块

此模块提供对各种网络封装协议的自动检测、解析和处理能力。
支持的封装类型包括：VLAN、双层VLAN、MPLS、VXLAN、GRE等。

核心功能：
- 自动封装类型检测
- 多层协议栈解析
- 智能处理适配
"""

from .detector import EncapsulationDetector
from .parser import ProtocolStackParser
from .types import (
    EncapsulationResult,
    EncapsulationType,
    IPLayerInfo,
    LayerInfo,
    PayloadInfo,
)

# ProcessingAdapter has been eliminated - use direct scapy operations instead

__all__ = [
    # 数据类型
    "EncapsulationType",
    "LayerInfo",
    "IPLayerInfo",
    "PayloadInfo",
    "EncapsulationResult",
    # 核心组件
    "EncapsulationDetector",
    "ProtocolStackParser",
]

__version__ = "1.0.0"
