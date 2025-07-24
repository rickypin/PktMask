"""
MaskPayload Stage - Dual-Module Architecture Implementation

This module implements next-generation masking processing stage based on dual-module separation design:
- Marker Module: tshark-based protocol analyzer that generates TCP sequence number keep rules
- Masker Module: scapy-based universal payload processor that applies keep rules

Design Goals:
1. Separation of Concerns: Protocol analysis and masking application are completely decoupled
2. Protocol Agnostic: Masker module supports keep rules for any protocol
3. Easy Extension: Adding new protocols only requires extending the Marker module
4. Independent Testing: Both modules can be independently verified and debugged
5. Performance Optimization: Optimal processing strategy selection for different scenarios

Version: v1.0.0
Status: In Development
Standards: Context7 Documentation Standards
Risk Level: P0 (High-Risk Architecture Refactoring)
"""

from .stage import MaskingStage

__all__ = ["MaskingStage"]
