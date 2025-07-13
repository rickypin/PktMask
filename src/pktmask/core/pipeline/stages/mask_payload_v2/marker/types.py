"""
Marker模块数据结构定义

定义了保留规则和相关数据结构，用于在协议分析和掩码应用之间传递信息。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class FlowInfo:
    """TCP流信息"""
    stream_id: str              # TCP流标识
    src_ip: str                 # 源IP地址
    dst_ip: str                 # 目标IP地址
    src_port: int               # 源端口
    dst_port: int               # 目标端口
    protocol: str               # 协议类型 (tcp)
    direction: str              # 流方向 (forward/reverse)
    packet_count: int = 0       # 数据包数量
    byte_count: int = 0         # 字节数量
    first_seen: float = 0.0     # 首次出现时间
    last_seen: float = 0.0      # 最后出现时间
    metadata: Dict[str, Any] = field(default_factory=dict)  # 附加信息


@dataclass
class KeepRule:
    """单个保留规则
    
    定义了需要在掩码处理中保留的TCP载荷区段。
    使用64位逻辑序列号来处理32位序列号回绕问题。
    """
    stream_id: str              # TCP流标识
    direction: str              # 流方向 (forward/reverse)
    seq_start: int              # 起始序列号 (64-bit逻辑序号)
    seq_end: int                # 结束序列号 (64-bit逻辑序号)
    rule_type: str              # 规则类型 (tls_header/tls_payload/etc)
    metadata: Dict[str, Any] = field(default_factory=dict)  # 附加信息
    
    def __post_init__(self):
        """验证规则有效性"""
        if self.seq_start < 0 or self.seq_end < 0:
            raise ValueError("序列号不能为负数")
        if self.seq_start >= self.seq_end:
            raise ValueError("起始序列号必须小于结束序列号")
        if not self.stream_id:
            raise ValueError("流标识不能为空")
        if self.direction not in ('forward', 'reverse'):
            raise ValueError("流方向必须是 'forward' 或 'reverse'")
    
    @property
    def length(self) -> int:
        """获取规则覆盖的字节长度"""
        return self.seq_end - self.seq_start
    
    def overlaps_with(self, other: KeepRule) -> bool:
        """检查是否与另一个规则重叠或相邻"""
        if self.stream_id != other.stream_id or self.direction != other.direction:
            return False
        # 检查重叠或相邻（相邻规则也可以合并）
        return not (self.seq_end < other.seq_start or other.seq_end < self.seq_start)
    
    def merge_with(self, other: KeepRule) -> Optional[KeepRule]:
        """尝试与另一个规则合并

        注意：不合并具有不同保留策略的规则，特别是TLS-23头部保留规则
        应该保持独立，以确保精确的掩码控制。
        """
        if not self.overlaps_with(other):
            return None

        # 检查保留策略是否兼容
        self_strategy = self.metadata.get('preserve_strategy')
        other_strategy = other.metadata.get('preserve_strategy')

        # 如果任一规则是TLS-23头部保留规则，不进行合并
        if (self_strategy == 'header_only' or other_strategy == 'header_only'):
            return None

        # 如果保留策略不同，不进行合并
        if (self_strategy is not None and other_strategy is not None and
            self_strategy != other_strategy):
            return None

        # 合并重叠或相邻的规则
        new_start = min(self.seq_start, other.seq_start)
        new_end = max(self.seq_end, other.seq_end)

        # 合并元数据
        merged_metadata = {**self.metadata, **other.metadata}
        merged_metadata['merged_from'] = [
            self.metadata.get('rule_id', 'unknown'),
            other.metadata.get('rule_id', 'unknown')
        ]

        return KeepRule(
            stream_id=self.stream_id,
            direction=self.direction,
            seq_start=new_start,
            seq_end=new_end,
            rule_type=f"{self.rule_type}+{other.rule_type}",
            metadata=merged_metadata
        )


@dataclass
class KeepRuleSet:
    """保留规则集合
    
    包含了对整个PCAP文件进行掩码处理所需的所有保留规则和相关信息。
    """
    rules: List[KeepRule] = field(default_factory=list)
    tcp_flows: Dict[str, FlowInfo] = field(default_factory=dict)
    statistics: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_rule(self, rule: KeepRule) -> None:
        """添加保留规则"""
        self.rules.append(rule)
    
    def get_rules_for_stream(self, stream_id: str, direction: str) -> List[KeepRule]:
        """获取指定流和方向的所有规则"""
        return [
            rule for rule in self.rules 
            if rule.stream_id == stream_id and rule.direction == direction
        ]
    
    def optimize_rules(self) -> None:
        """优化规则集合，合并重叠和相邻的规则"""
        if not self.rules:
            return
        
        # 按流和方向分组
        grouped_rules: Dict[Tuple[str, str], List[KeepRule]] = {}
        for rule in self.rules:
            key = (rule.stream_id, rule.direction)
            if key not in grouped_rules:
                grouped_rules[key] = []
            grouped_rules[key].append(rule)
        
        # 对每组规则进行优化
        optimized_rules = []
        for rules_group in grouped_rules.values():
            optimized_rules.extend(self._optimize_rule_group(rules_group))
        
        self.rules = optimized_rules
        
        # 更新统计信息
        self.statistics['rules_before_optimization'] = len(self.rules)
        self.statistics['rules_after_optimization'] = len(optimized_rules)
    
    def _optimize_rule_group(self, rules: List[KeepRule]) -> List[KeepRule]:
        """优化单个规则组"""
        if not rules:
            return []
        
        # 按序列号排序
        sorted_rules = sorted(rules, key=lambda r: r.seq_start)
        
        # 合并重叠和相邻的规则
        merged_rules = [sorted_rules[0]]
        
        for current_rule in sorted_rules[1:]:
            last_rule = merged_rules[-1]
            
            # 检查是否可以合并
            if (current_rule.seq_start <= last_rule.seq_end or 
                current_rule.seq_start == last_rule.seq_end):
                # 合并规则
                merged_rule = last_rule.merge_with(current_rule)
                if merged_rule:
                    merged_rules[-1] = merged_rule
                else:
                    merged_rules.append(current_rule)
            else:
                merged_rules.append(current_rule)
        
        return merged_rules
    
    def get_total_preserved_bytes(self) -> int:
        """获取总的保留字节数"""
        return sum(rule.length for rule in self.rules)
    
    def get_stream_count(self) -> int:
        """获取TCP流数量"""
        return len(self.tcp_flows)
    
    def validate(self) -> List[str]:
        """验证规则集合的有效性，返回错误列表"""
        errors = []
        
        # 验证每个规则
        for i, rule in enumerate(self.rules):
            try:
                # 重新触发 __post_init__ 验证
                rule.__post_init__()
            except ValueError as e:
                errors.append(f"规则 {i}: {e}")
        
        # 验证流信息一致性
        rule_streams = {rule.stream_id for rule in self.rules}
        flow_streams = set(self.tcp_flows.keys())
        
        missing_flows = rule_streams - flow_streams
        if missing_flows:
            errors.append(f"缺少流信息: {missing_flows}")
        
        return errors
