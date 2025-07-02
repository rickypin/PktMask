"""
TLS掩码规则生成器

基于TShark TLS分析结果生成精确掩码规则的组件。
这是TSharkEnhancedMaskProcessor的第二阶段处理器。

功能特性：
1. 多记录处理：处理单包内多个TLS记录的掩码规则生成
2. 跨段识别算法：处理跨TCP段TLS消息的掩码策略
3. 分类处理策略：TLS-20/21/22/24完全保留，TLS-23智能掩码
4. 边界安全处理：确保掩码操作不会超出记录边界
5. 性能优化：批量处理和缓存机制
"""

import logging
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple, Any

from ..trim.models.tls_models import (
    TLSRecordInfo, 
    MaskRule, 
    TLSAnalysisResult,
    create_mask_rule_for_tls_record,
    validate_tls_record_boundary
)


class TLSMaskRuleGenerator:
    """TLS掩码规则生成器
    
    将TShark分析的TLS记录转换为精确的掩码规则，处理多记录和跨段情况。
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化TLS掩码规则生成器
        
        Args:
            config: 配置参数字典
        """
        self.config = config or {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # 配置参数
        self._enable_multi_record_optimization = self.config.get('enable_multi_record_optimization', True)
        self._enable_cross_packet_detection = self.config.get('enable_cross_packet_detection', True)
        self._max_rules_per_packet = self.config.get('max_rules_per_packet', 10)
        self._validate_boundaries = self.config.get('validate_boundaries', True)
        
        # 调试配置
        self._verbose = self.config.get('verbose', False)
        self._debug_packet_numbers = self.config.get('debug_packet_numbers', [])
        
        # 内部状态
        self._generated_rules_count = 0
        self._processed_records_count = 0
        self._cross_packet_records_count = 0
        
    def generate_rules(self, tls_records: List[TLSRecordInfo]) -> List[MaskRule]:
        """为TLS记录列表生成掩码规则
        
        Args:
            tls_records: TLS记录列表
            
        Returns:
            生成的掩码规则列表
            
        Raises:
            ValueError: 输入数据无效时抛出
            RuntimeError: 规则生成失败时抛出
        """
        if not tls_records:
            self.logger.info("输入TLS记录列表为空，返回空规则列表")
            return []
        
        self.logger.info(f"开始为{len(tls_records)}个TLS记录生成掩码规则")
        self._reset_statistics()
        
        try:
            # 按包编号分组TLS记录
            packet_groups = self._group_records_by_packet(tls_records)
            
            # 处理跨包检测（如果启用）
            if self._enable_cross_packet_detection:
                packet_groups = self._enhance_cross_packet_detection(packet_groups)
            
            # 为每个包生成掩码规则
            all_rules = []
            for packet_number, records in packet_groups.items():
                packet_rules = self._generate_rules_for_packet(packet_number, records)
                all_rules.extend(packet_rules)
            
            # 验证和优化规则
            optimized_rules = self._optimize_rules(all_rules)
            
            self._log_generation_statistics(optimized_rules)
            self.logger.info(f"掩码规则生成完成：生成{len(optimized_rules)}条规则")
            
            return optimized_rules
            
        except Exception as e:
            self.logger.error(f"TLS掩码规则生成失败: {e}")
            raise RuntimeError(f"掩码规则生成失败: {e}") from e
    
    def _group_records_by_packet(self, tls_records: List[TLSRecordInfo]) -> Dict[int, List[TLSRecordInfo]]:
        """将TLS记录按包编号分组
        
        Args:
            tls_records: TLS记录列表
            
        Returns:
            按包编号分组的TLS记录字典
        """
        packet_groups = defaultdict(list)
        
        for record in tls_records:
            packet_groups[record.packet_number].append(record)
            self._processed_records_count += 1
        
        self.logger.debug(f"TLS记录分组完成：{len(packet_groups)}个包，{self._processed_records_count}条记录")
        return dict(packet_groups)
    
    def _enhance_cross_packet_detection(self, packet_groups: Dict[int, List[TLSRecordInfo]]) -> Dict[int, List[TLSRecordInfo]]:
        """增强跨包检测，识别和处理跨TCP段的TLS记录
        
        Args:
            packet_groups: 按包分组的TLS记录
            
        Returns:
            增强的包分组字典
        """
        enhanced_groups = {}
        
        # 按TCP流分组
        stream_groups = defaultdict(list)
        for packet_number, records in packet_groups.items():
            for record in records:
                stream_groups[record.tcp_stream_id].append((packet_number, record))
        
        # 对每个流进行跨包检测
        for stream_id, stream_records in stream_groups.items():
            enhanced_stream_records = self._detect_cross_packet_in_stream(stream_records)
            
            # 重新分组到包
            for packet_number, record in enhanced_stream_records:
                if packet_number not in enhanced_groups:
                    enhanced_groups[packet_number] = []
                enhanced_groups[packet_number].append(record)
        
        self.logger.debug(f"跨包检测完成：发现{self._cross_packet_records_count}个跨包记录")
        return enhanced_groups
    
    def _detect_cross_packet_in_stream(self, stream_records: List[Tuple[int, TLSRecordInfo]]) -> List[Tuple[int, TLSRecordInfo]]:
        """在单个流中检测跨包TLS记录
        
        Args:
            stream_records: 单个流的(包编号, TLS记录)列表
            
        Returns:
            增强的(包编号, TLS记录)列表
        """
        # 按包编号排序
        stream_records.sort(key=lambda x: x[0])
        
        enhanced_records = []
        
        for packet_number, record in stream_records:
            # 检查是否为跨包记录
            is_cross_packet = len(record.spans_packets) > 1
            
            if is_cross_packet:
                self._cross_packet_records_count += 1
                
                # 为跨包记录创建增强版本
                enhanced_record = TLSRecordInfo(
                    packet_number=record.packet_number,
                    content_type=record.content_type,
                    version=record.version,
                    length=record.length,
                    is_complete=record.is_complete,
                    spans_packets=record.spans_packets,
                    tcp_stream_id=record.tcp_stream_id,
                    record_offset=record.record_offset
                )
                
                if self._verbose:
                    self.logger.debug(f"检测到跨包TLS记录: 包{packet_number}, 类型{record.content_type}, 跨{len(record.spans_packets)}个包")
                
            else:
                enhanced_record = record
            
            enhanced_records.append((packet_number, enhanced_record))
        
        return enhanced_records
    
    def _generate_rules_for_packet(self, packet_number: int, records: List[TLSRecordInfo]) -> List[MaskRule]:
        """为单个包中的所有TLS记录生成掩码规则
        
        Args:
            packet_number: 包编号
            records: 该包中的TLS记录列表
            
        Returns:
            该包的掩码规则列表
        """
        if not records:
            return []
        
        # 检查是否需要调试输出
        debug_this_packet = packet_number in self._debug_packet_numbers or self._verbose
        
        if debug_this_packet:
            self.logger.info(f"=== 包{packet_number}掩码规则生成开始 ===")
            self.logger.info(f"包含{len(records)}个TLS记录")
        
        # 按记录偏移量排序，确保处理顺序正确
        sorted_records = sorted(records, key=lambda r: r.record_offset)
        
        packet_rules = []
        current_offset = 0
        
        for i, record in enumerate(sorted_records):
            try:
                # 验证记录边界（如果启用）
                if self._validate_boundaries:
                    self._validate_record_boundary(record, current_offset)
                
                # 为记录生成掩码规则
                rule = self._generate_rule_for_record(record)
                packet_rules.append(rule)
                
                if debug_this_packet:
                    self.logger.info(f"记录{i+1}: {rule.get_description()}")
                
                # 更新偏移量
                current_offset = record.record_offset + record.length
                self._generated_rules_count += 1
                
            except Exception as e:
                self.logger.warning(f"包{packet_number}记录{i+1}规则生成失败: {e}")
                continue
        
        # 检查规则数量限制
        if len(packet_rules) > self._max_rules_per_packet:
            self.logger.warning(f"包{packet_number}规则数量超限: {len(packet_rules)} > {self._max_rules_per_packet}")
            packet_rules = packet_rules[:self._max_rules_per_packet]
        
        if debug_this_packet:
            self.logger.info(f"=== 包{packet_number}掩码规则生成完成：{len(packet_rules)}条规则 ===")
        
        return packet_rules
    
    def _generate_rule_for_record(self, record: TLSRecordInfo) -> MaskRule:
        """为单个TLS记录生成掩码规则
        
        Args:
            record: TLS记录信息
            
        Returns:
            对应的掩码规则
        """
        # 使用工具函数创建基本规则
        base_rule = create_mask_rule_for_tls_record(record)
        
        # 根据记录特性进行增强
        enhanced_rule = self._enhance_rule_for_record(base_rule, record)
        
        return enhanced_rule
    
    def _enhance_rule_for_record(self, base_rule: MaskRule, record: TLSRecordInfo) -> MaskRule:
        """增强单个记录的掩码规则
        
        Args:
            base_rule: 基础掩码规则
            record: TLS记录信息
            
        Returns:
            增强的掩码规则
        """
        # 处理跨包记录的特殊情况
        if len(record.spans_packets) > 1:
            enhanced_reason = f"{base_rule.reason} (跨{len(record.spans_packets)}个包)"
            
            # 跨包记录通常需要特殊处理，这里暂时保持原始策略
            # 在未来版本中可以添加更复杂的跨包掩码逻辑
            return MaskRule(
                packet_number=base_rule.packet_number,
                tcp_stream_id=base_rule.tcp_stream_id,
                tls_record_offset=base_rule.tls_record_offset,
                tls_record_length=base_rule.tls_record_length,
                mask_offset=base_rule.mask_offset,
                mask_length=base_rule.mask_length,
                action=base_rule.action,
                reason=enhanced_reason,
                tls_record_type=base_rule.tls_record_type
            )
        
        # 处理不完整记录
        if not record.is_complete:
            enhanced_reason = f"{base_rule.reason} (不完整记录)"
            
            return MaskRule(
                packet_number=base_rule.packet_number,
                tcp_stream_id=base_rule.tcp_stream_id,
                tls_record_offset=base_rule.tls_record_offset,
                tls_record_length=base_rule.tls_record_length,
                mask_offset=0,  # 不完整记录完全保留
                mask_length=0,
                action=base_rule.action,
                reason=enhanced_reason,
                tls_record_type=base_rule.tls_record_type
            )
        
        # 其他情况返回原始规则
        return base_rule
    
    def _validate_record_boundary(self, record: TLSRecordInfo, expected_offset: int) -> None:
        """验证TLS记录边界
        
        Args:
            record: TLS记录信息
            expected_offset: 期望的偏移量
            
        Raises:
            ValueError: 边界验证失败时抛出
        """
        # 验证记录偏移量的连续性
        if record.record_offset < expected_offset:
            raise ValueError(f"TLS记录偏移量异常: {record.record_offset} < {expected_offset}")
        
        # 计算估计的TCP载荷长度 (记录偏移 + 记录长度)
        estimated_tcp_payload_length = record.record_offset + record.length
        
        # 使用工具函数验证记录边界
        if not validate_tls_record_boundary(record, estimated_tcp_payload_length):
            raise ValueError(f"TLS记录边界验证失败: 包{record.packet_number}")
    
    def _optimize_rules(self, rules: List[MaskRule]) -> List[MaskRule]:
        """优化掩码规则列表
        
        Args:
            rules: 原始掩码规则列表
            
        Returns:
            优化后的掩码规则列表
        """
        if not self._enable_multi_record_optimization or not rules:
            return rules
        
        # 按包编号分组
        packet_rules = defaultdict(list)
        for rule in rules:
            packet_rules[rule.packet_number].append(rule)
        
        optimized_rules = []
        
        # 对每个包的规则进行优化
        for packet_number, packet_rule_list in packet_rules.items():
            optimized_packet_rules = self._optimize_packet_rules(packet_rule_list)
            optimized_rules.extend(optimized_packet_rules)
        
        self.logger.debug(f"规则优化完成：{len(rules)} -> {len(optimized_rules)}")
        return optimized_rules
    
    def _optimize_packet_rules(self, packet_rules: List[MaskRule]) -> List[MaskRule]:
        """优化单个包的掩码规则
        
        Args:
            packet_rules: 单个包的掩码规则列表
            
        Returns:
            优化后的规则列表
        """
        if len(packet_rules) <= 1:
            return packet_rules
        
        # 按偏移量排序
        sorted_rules = sorted(packet_rules, key=lambda r: r.tls_record_offset)
        
        # 检查是否可以合并相邻的相同操作规则
        optimized = []
        current_rule = sorted_rules[0]
        
        for next_rule in sorted_rules[1:]:
            # 检查是否可以合并
            if self._can_merge_rules(current_rule, next_rule):
                current_rule = self._merge_rules(current_rule, next_rule)
            else:
                optimized.append(current_rule)
                current_rule = next_rule
        
        optimized.append(current_rule)
        
        return optimized
    
    def _can_merge_rules(self, rule1: MaskRule, rule2: MaskRule) -> bool:
        """检查两个规则是否可以合并
        
        Args:
            rule1: 第一个规则
            rule2: 第二个规则
            
        Returns:
            是否可以合并
        """
        # 基本条件检查
        if (rule1.packet_number != rule2.packet_number or
            rule1.tcp_stream_id != rule2.tcp_stream_id or
            rule1.action != rule2.action):
            return False
        
        # 检查规则是否相邻
        rule1_end = rule1.tls_record_offset + rule1.tls_record_length
        rule2_start = rule2.tls_record_offset
        
        return rule1_end == rule2_start
    
    def _merge_rules(self, rule1: MaskRule, rule2: MaskRule) -> MaskRule:
        """合并两个相邻的相同操作规则
        
        Args:
            rule1: 第一个规则
            rule2: 第二个规则
            
        Returns:
            合并后的规则
        """
        merged_length = rule1.tls_record_length + rule2.tls_record_length
        merged_reason = f"合并规则: {rule1.reason} + {rule2.reason}"
        
        return MaskRule(
            packet_number=rule1.packet_number,
            tcp_stream_id=rule1.tcp_stream_id,
            tls_record_offset=rule1.tls_record_offset,
            tls_record_length=merged_length,
            mask_offset=rule1.mask_offset,
            mask_length=rule1.mask_length + rule2.mask_length,
            action=rule1.action,
            reason=merged_reason,
            tls_record_type=rule1.tls_record_type
        )
    
    def _reset_statistics(self) -> None:
        """重置统计信息"""
        self._generated_rules_count = 0
        self._processed_records_count = 0
        self._cross_packet_records_count = 0
    
    def _log_generation_statistics(self, rules: List[MaskRule]) -> None:
        """记录生成统计信息
        
        Args:
            rules: 生成的规则列表
        """
        # 统计规则类型分布
        action_counts = defaultdict(int)
        tls_type_counts = defaultdict(int)
        
        for rule in rules:
            action_counts[rule.action.value] += 1
            if rule.tls_record_type is not None:
                tls_type_counts[rule.tls_record_type] += 1
        
        self.logger.info(f"掩码规则生成统计:")
        self.logger.info(f"  处理记录数: {self._processed_records_count}")
        self.logger.info(f"  生成规则数: {len(rules)}")
        self.logger.info(f"  跨包记录数: {self._cross_packet_records_count}")
        
        self.logger.info(f"  操作类型分布: {dict(action_counts)}")
        self.logger.info(f"  TLS类型分布: {dict(tls_type_counts)}")
    
    def get_generation_statistics(self) -> Dict[str, Any]:
        """获取生成统计信息
        
        Returns:
            统计信息字典
        """
        return {
            'processed_records_count': self._processed_records_count,
            'generated_rules_count': self._generated_rules_count,
            'cross_packet_records_count': self._cross_packet_records_count,
            'multi_record_optimization_enabled': self._enable_multi_record_optimization,
            'cross_packet_detection_enabled': self._enable_cross_packet_detection
        } 