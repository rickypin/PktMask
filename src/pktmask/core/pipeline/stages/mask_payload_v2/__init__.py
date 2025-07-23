"""
MaskPayload 阶段 - 双模块架构实现

本模块实现了基于双模块分离设计的新一代掩码处理阶段：
- Marker模块: 基于 tshark 的协议分析器，生成 TCP 序列号保留规则
- Masker模块: 基于 scapy 的通用载荷处理器，应用保留规则

设计目标：
1. 职责分离：协议分析与掩码应用完全解耦
2. 协议无关：Masker模块支持任意协议的保留规则
3. 易于扩展：新增协议仅需扩展Marker模块
4. 独立测试：两个模块可独立验证和调试
5. 性能优化：针对不同场景选择最优处理策略

版本: v1.0.0
状态: 开发中
遵循标准: Context7 文档标准
风险等级: P0 (高风险架构重构)
"""

from .stage import NewMaskPayloadStage

__all__ = ["NewMaskPayloadStage"]
