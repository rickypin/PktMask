"""
Marker Module - Protocol Analysis and Keep Rule Generation

This module analyzes protocol traffic in pcap/pcapng files, identifies data segments
that need to be preserved, and generates structured KeepRule lists.

Core Components:
- ProtocolMarker: Protocol marker base class
- TLSProtocolMarker: TLS protocol marker implementation
- KeepRule/KeepRuleSet: Keep rule data structures

Technical Features:
- Deep protocol analysis based on tshark
- TCP sequence number wraparound handling support
- Reuses core algorithms from tls_flow_analyzer
- Multi-protocol extension support
"""

from .base import ProtocolMarker
from .tls_marker import TLSProtocolMarker
from .types import FlowInfo, KeepRule, KeepRuleSet

__all__ = ["ProtocolMarker", "TLSProtocolMarker", "KeepRule", "KeepRuleSet", "FlowInfo"]
