"""
TLS掩码规则生成器单元测试

测试TLSMaskRuleGenerator的所有功能组件，包括：
1. 基本规则生成
2. 多记录处理
3. 跨包检测算法
4. 规则优化
5. 边界条件处理
"""

import pytest
from typing import List
from unittest.mock import Mock, patch

from src.pktmask.core.processors.tls_mask_rule_generator import TLSMaskRuleGenerator
from src.pktmask.core.trim.models.tls_models import (
    TLSRecordInfo,
    MaskRule,
    MaskAction,
    TLSProcessingStrategy
)


class TestTLSMaskRuleGenerator:
    """TLS掩码规则生成器基础测试"""
    
    def test_init_default_config(self):
        """测试默认配置初始化"""
        generator = TLSMaskRuleGenerator()
        
        assert generator.config == {}
        assert generator._enable_multi_record_optimization is True
        assert generator._enable_cross_packet_detection is True
        assert generator._max_rules_per_packet == 10
        assert generator._validate_boundaries is True
        assert generator._verbose is False
        assert generator._debug_packet_numbers == []
        
    def test_init_custom_config(self):
        """测试自定义配置初始化"""
        config = {
            'enable_multi_record_optimization': False,
            'enable_cross_packet_detection': False,
            'max_rules_per_packet': 5,
            'validate_boundaries': False,
            'verbose': True,
            'debug_packet_numbers': [1, 2, 3]
        }
        
        generator = TLSMaskRuleGenerator(config)
        
        assert generator.config == config
        assert generator._enable_multi_record_optimization is False
        assert generator._enable_cross_packet_detection is False
        assert generator._max_rules_per_packet == 5
        assert generator._validate_boundaries is False
        assert generator._verbose is True
        assert generator._debug_packet_numbers == [1, 2, 3]
    
    def test_generate_rules_empty_input(self):
        """测试空输入的规则生成"""
        generator = TLSMaskRuleGenerator()
        
        result = generator.generate_rules([])
        
        assert result == []
        assert generator._processed_records_count == 0
        assert generator._generated_rules_count == 0
    
    def test_generate_rules_single_record(self):
        """测试单个记录的规则生成"""
        generator = TLSMaskRuleGenerator()
        
        # 创建单个TLS记录
        record = TLSRecordInfo(
            packet_number=1,
            content_type=23,  # ApplicationData
            version=(3, 3),
            length=100,
            is_complete=True,
            spans_packets=[1],
            tcp_stream_id="TCP_1",
            record_offset=0
        )
        
        rules = generator.generate_rules([record])
        
        assert len(rules) == 1
        rule = rules[0]
        
        assert rule.packet_number == 1
        assert rule.tcp_stream_id == "TCP_1"
        assert rule.tls_record_type == 23
        assert rule.action == MaskAction.MASK_PAYLOAD
        assert rule.mask_offset == 5  # 保留TLS头部
        assert rule.mask_length == 95  # 100 - 5
        
    def test_generate_rules_multiple_records_same_packet(self):
        """测试同一包内多个记录的规则生成"""
        generator = TLSMaskRuleGenerator()
        
        records = [
            TLSRecordInfo(
                packet_number=1,
                content_type=22,  # Handshake
                version=(3, 3),
                length=50,
                is_complete=True,
                spans_packets=[1],
                tcp_stream_id="TCP_1",
                record_offset=0
            ),
            TLSRecordInfo(
                packet_number=1,
                content_type=23,  # ApplicationData
                version=(3, 3),
                length=100,
                is_complete=True,
                spans_packets=[1],
                tcp_stream_id="TCP_1",
                record_offset=55  # 50 + 5字节头部
            )
        ]
        
        rules = generator.generate_rules(records)
        
        assert len(rules) == 2
        
        # 验证Handshake规则
        handshake_rule = rules[0]
        assert handshake_rule.tls_record_type == 22
        assert handshake_rule.action == MaskAction.KEEP_ALL
        assert handshake_rule.mask_length == 0
        
        # 验证ApplicationData规则
        app_data_rule = rules[1]
        assert app_data_rule.tls_record_type == 23
        assert app_data_rule.action == MaskAction.MASK_PAYLOAD
        assert app_data_rule.mask_offset == 5
        assert app_data_rule.mask_length == 95
    
    def test_generate_rules_different_tls_types(self):
        """测试不同TLS类型的规则生成"""
        generator = TLSMaskRuleGenerator()
        
        test_cases = [
            (20, MaskAction.KEEP_ALL, 0, 0),  # ChangeCipherSpec
            (21, MaskAction.KEEP_ALL, 0, 0),  # Alert
            (22, MaskAction.KEEP_ALL, 0, 0),  # Handshake
            (23, MaskAction.MASK_PAYLOAD, 5, 95),  # ApplicationData
            (24, MaskAction.KEEP_ALL, 0, 0),  # Heartbeat
        ]
        
        for i, (content_type, expected_action, expected_mask_offset, expected_mask_length) in enumerate(test_cases):
            record = TLSRecordInfo(
                packet_number=i + 1,
                content_type=content_type,
                version=(3, 3),
                length=100,
                is_complete=True,
                spans_packets=[i + 1],
                tcp_stream_id=f"TCP_{i + 1}",
                record_offset=0
            )
            
            rules = generator.generate_rules([record])
            assert len(rules) == 1
            
            rule = rules[0]
            assert rule.tls_record_type == content_type
            assert rule.action == expected_action
            assert rule.mask_offset == expected_mask_offset
            assert rule.mask_length == expected_mask_length


class TestTLSMaskRuleGeneratorGrouping:
    """测试记录分组功能"""
    
    def test_group_records_by_packet(self):
        """测试按包编号分组记录"""
        generator = TLSMaskRuleGenerator()
        
        records = [
            TLSRecordInfo(1, 22, (3, 3), 50, True, [1], "TCP_1", 0),
            TLSRecordInfo(2, 23, (3, 3), 100, True, [2], "TCP_1", 0),
            TLSRecordInfo(1, 23, (3, 3), 80, True, [1], "TCP_1", 55),
            TLSRecordInfo(3, 21, (3, 3), 20, True, [3], "TCP_2", 0),
        ]
        
        groups = generator._group_records_by_packet(records)
        
        assert len(groups) == 3
        assert len(groups[1]) == 2  # 包1有2个记录
        assert len(groups[2]) == 1  # 包2有1个记录
        assert len(groups[3]) == 1  # 包3有1个记录
        
        # 验证分组内容
        assert groups[1][0].content_type == 22
        assert groups[1][1].content_type == 23
        assert groups[2][0].content_type == 23
        assert groups[3][0].content_type == 21


class TestTLSMaskRuleGeneratorCrossPacket:
    """测试跨包检测功能"""
    
    def test_cross_packet_detection_enabled(self):
        """测试启用跨包检测"""
        config = {'enable_cross_packet_detection': True}
        generator = TLSMaskRuleGenerator(config)
        
        # 创建跨包记录
        record = TLSRecordInfo(
            packet_number=1,
            content_type=23,
            version=(3, 3),
            length=1000,
            is_complete=False,
            spans_packets=[1, 2],  # 跨两个包
            tcp_stream_id="TCP_1",
            record_offset=0
        )
        
        rules = generator.generate_rules([record])
        
        assert len(rules) == 1
        rule = rules[0]
        
        # 跨包记录应该完全保留
        assert rule.action == MaskAction.KEEP_ALL
        assert rule.mask_length == 0
        assert "跨2个包" in rule.reason
        
    def test_cross_packet_detection_disabled(self):
        """测试禁用跨包检测"""
        config = {'enable_cross_packet_detection': False}
        generator = TLSMaskRuleGenerator(config)
        
        record = TLSRecordInfo(
            packet_number=1,
            content_type=23,
            version=(3, 3),
            length=100,
            is_complete=True,
            spans_packets=[1, 2],  # 跨包标记会被忽略
            tcp_stream_id="TCP_1",
            record_offset=0
        )
        
        rules = generator.generate_rules([record])
        
        assert len(rules) == 1
        rule = rules[0]
        
        # 正常的ApplicationData处理
        assert rule.action == MaskAction.MASK_PAYLOAD
        assert rule.mask_offset == 5
        assert rule.mask_length == 95
    
    def test_detect_cross_packet_in_stream(self):
        """测试流内跨包检测"""
        generator = TLSMaskRuleGenerator()
        
        stream_records = [
            (1, TLSRecordInfo(1, 23, (3, 3), 100, True, [1], "TCP_1", 0)),
            (2, TLSRecordInfo(2, 23, (3, 3), 500, False, [2, 3], "TCP_1", 0)),  # 跨包
            (3, TLSRecordInfo(3, 22, (3, 3), 50, True, [3], "TCP_1", 0)),
        ]
        
        enhanced = generator._detect_cross_packet_in_stream(stream_records)
        
        assert len(enhanced) == 3
        
        # 验证跨包记录被正确标识
        _, record2 = enhanced[1]
        assert len(record2.spans_packets) == 2
        assert not record2.is_complete


class TestTLSMaskRuleGeneratorRuleOptimization:
    """测试规则优化功能"""
    
    def test_optimization_enabled(self):
        """测试启用规则优化"""
        config = {'enable_multi_record_optimization': True}
        generator = TLSMaskRuleGenerator(config)
        
        # 创建两个相邻的相同操作规则
        rules = [
            MaskRule(1, "TCP_1", 0, 50, 0, 0, MaskAction.KEEP_ALL, "测试1", 22),
            MaskRule(1, "TCP_1", 50, 60, 0, 0, MaskAction.KEEP_ALL, "测试2", 22),
        ]
        
        optimized = generator._optimize_rules(rules)
        
        # 应该合并为一个规则
        assert len(optimized) == 1
        merged_rule = optimized[0]
        
        assert merged_rule.tls_record_offset == 0
        assert merged_rule.tls_record_length == 110  # 50 + 60
        assert "合并规则" in merged_rule.reason
    
    def test_optimization_disabled(self):
        """测试禁用规则优化"""
        config = {'enable_multi_record_optimization': False}
        generator = TLSMaskRuleGenerator(config)
        
        rules = [
            MaskRule(1, "TCP_1", 0, 50, 0, 0, MaskAction.KEEP_ALL, "测试1", 22),
            MaskRule(1, "TCP_1", 50, 60, 0, 0, MaskAction.KEEP_ALL, "测试2", 22),
        ]
        
        optimized = generator._optimize_rules(rules)
        
        # 应该保持原样
        assert len(optimized) == 2
        assert optimized[0] == rules[0]
        assert optimized[1] == rules[1]
    
    def test_can_merge_rules_different_actions(self):
        """测试不同操作的规则不能合并"""
        generator = TLSMaskRuleGenerator()
        
        rule1 = MaskRule(1, "TCP_1", 0, 50, 0, 0, MaskAction.KEEP_ALL, "测试1", 22)
        rule2 = MaskRule(1, "TCP_1", 50, 60, 5, 55, MaskAction.MASK_PAYLOAD, "测试2", 23)
        
        can_merge = generator._can_merge_rules(rule1, rule2)
        
        assert not can_merge
    
    def test_can_merge_rules_different_packets(self):
        """测试不同包的规则不能合并"""
        generator = TLSMaskRuleGenerator()
        
        rule1 = MaskRule(1, "TCP_1", 0, 50, 0, 0, MaskAction.KEEP_ALL, "测试1", 22)
        rule2 = MaskRule(2, "TCP_1", 50, 60, 0, 0, MaskAction.KEEP_ALL, "测试2", 22)
        
        can_merge = generator._can_merge_rules(rule1, rule2)
        
        assert not can_merge
    
    def test_can_merge_rules_non_adjacent(self):
        """测试非相邻规则不能合并"""
        generator = TLSMaskRuleGenerator()
        
        rule1 = MaskRule(1, "TCP_1", 0, 50, 0, 0, MaskAction.KEEP_ALL, "测试1", 22)
        rule2 = MaskRule(1, "TCP_1", 60, 60, 0, 0, MaskAction.KEEP_ALL, "测试2", 22)  # 间隔10字节
        
        can_merge = generator._can_merge_rules(rule1, rule2)
        
        assert not can_merge
    
    def test_merge_rules_calculation(self):
        """测试规则合并计算"""
        generator = TLSMaskRuleGenerator()
        
        rule1 = MaskRule(1, "TCP_1", 0, 50, 5, 45, MaskAction.MASK_PAYLOAD, "测试1", 23)
        rule2 = MaskRule(1, "TCP_1", 50, 60, 5, 55, MaskAction.MASK_PAYLOAD, "测试2", 23)
        
        merged = generator._merge_rules(rule1, rule2)
        
        assert merged.packet_number == 1
        assert merged.tcp_stream_id == "TCP_1"
        assert merged.tls_record_offset == 0
        assert merged.tls_record_length == 110  # 50 + 60
        assert merged.mask_offset == 5
        assert merged.mask_length == 100  # 45 + 55
        assert merged.action == MaskAction.MASK_PAYLOAD
        assert "合并规则" in merged.reason


class TestTLSMaskRuleGeneratorBoundaryHandling:
    """测试边界处理功能"""
    
    def test_boundary_validation_enabled(self):
        """测试启用边界验证"""
        config = {'validate_boundaries': True}
        generator = TLSMaskRuleGenerator(config)
        
        # 创建边界异常的记录
        record = TLSRecordInfo(
            packet_number=1,
            content_type=23,
            version=(3, 3),
            length=100,
            is_complete=True,
            spans_packets=[1],
            tcp_stream_id="TCP_1",
            record_offset=10
        )
        
        # 模拟边界验证失败 - 正确的patch路径
        with patch.object(generator, '_validate_record_boundary', side_effect=ValueError("边界验证失败")):
            rules = generator.generate_rules([record])
        
        # 验证失败的记录会被跳过（由于try/catch处理），但不会抛出异常
        assert len(rules) == 0
        
    def test_boundary_validation_disabled(self):
        """测试禁用边界验证"""
        config = {'validate_boundaries': False}
        generator = TLSMaskRuleGenerator(config)
        
        record = TLSRecordInfo(
            packet_number=1,
            content_type=23,
            version=(3, 3),
            length=100,
            is_complete=True,
            spans_packets=[1],
            tcp_stream_id="TCP_1",
            record_offset=10
        )
        
        rules = generator.generate_rules([record])
        
        # 禁用验证时应该正常生成规则
        assert len(rules) == 1
    
    def test_incomplete_record_handling(self):
        """测试不完整记录处理"""
        generator = TLSMaskRuleGenerator()
        
        record = TLSRecordInfo(
            packet_number=1,
            content_type=23,  # ApplicationData
            version=(3, 3),
            length=100,
            is_complete=False,  # 不完整记录
            spans_packets=[1, 2],
            tcp_stream_id="TCP_1",
            record_offset=0
        )
        
        rules = generator.generate_rules([record])
        
        assert len(rules) == 1
        rule = rules[0]
        
        # 不完整记录应该完全保留
        assert rule.action == MaskAction.KEEP_ALL
        assert rule.mask_offset == 0
        assert rule.mask_length == 0
        assert "不完整记录" in rule.reason
    
    def test_max_rules_per_packet_limit(self):
        """测试包规则数量限制"""
        config = {'max_rules_per_packet': 2}
        generator = TLSMaskRuleGenerator(config)
        
        # 创建3个记录，超过限制
        records = [
            TLSRecordInfo(1, 22, (3, 3), 50, True, [1], "TCP_1", 0),
            TLSRecordInfo(1, 23, (3, 3), 100, True, [1], "TCP_1", 55),
            TLSRecordInfo(1, 21, (3, 3), 20, True, [1], "TCP_1", 160),
        ]
        
        rules = generator.generate_rules(records)
        
        # 应该只保留前2个规则
        assert len(rules) == 2


class TestTLSMaskRuleGeneratorStatistics:
    """测试统计信息功能"""
    
    def test_statistics_collection(self):
        """测试统计信息收集"""
        generator = TLSMaskRuleGenerator()
        
        records = [
            TLSRecordInfo(1, 22, (3, 3), 50, True, [1], "TCP_1", 0),
            TLSRecordInfo(2, 23, (3, 3), 100, True, [2], "TCP_1", 0),
            TLSRecordInfo(3, 23, (3, 3), 200, False, [3, 4], "TCP_1", 0),  # 跨包
        ]
        
        rules = generator.generate_rules(records)
        
        stats = generator.get_generation_statistics()
        
        assert stats['processed_records_count'] == 3
        assert stats['generated_rules_count'] == 3
        assert stats['cross_packet_records_count'] == 1
        assert stats['multi_record_optimization_enabled'] is True
        assert stats['cross_packet_detection_enabled'] is True
    
    def test_statistics_reset(self):
        """测试统计信息重置"""
        generator = TLSMaskRuleGenerator()
        
        # 第一次生成
        records1 = [TLSRecordInfo(1, 22, (3, 3), 50, True, [1], "TCP_1", 0)]
        generator.generate_rules(records1)
        
        # 第二次生成
        records2 = [TLSRecordInfo(2, 23, (3, 3), 100, True, [2], "TCP_1", 0)]
        generator.generate_rules(records2)
        
        stats = generator.get_generation_statistics()
        
        # 统计应该只包含第二次生成的结果
        assert stats['processed_records_count'] == 1
        assert stats['generated_rules_count'] == 1


class TestTLSMaskRuleGeneratorErrorHandling:
    """测试错误处理功能"""
    
    def test_generate_rules_exception_handling(self):
        """测试规则生成异常的优雅处理"""
        generator = TLSMaskRuleGenerator()
        
        # 创建会导致异常的记录（通过模拟）
        record = TLSRecordInfo(1, 23, (3, 3), 100, True, [1], "TCP_1", 0)
        
        with patch.object(generator, '_generate_rule_for_record', side_effect=Exception("测试异常")):
            # 应该优雅处理异常，而不是抛出RuntimeError
            rules = generator.generate_rules([record])
            
            # 验证异常被捕获，返回空规则列表
            assert len(rules) == 0
            
            # 验证统计信息正确记录了处理的记录数
            stats = generator.get_generation_statistics()
            assert stats['processed_records_count'] == 1
            assert stats['generated_rules_count'] == 0
    
    def test_individual_record_error_handling(self):
        """测试单个记录错误处理"""
        generator = TLSMaskRuleGenerator()
        
        records = [
            TLSRecordInfo(1, 22, (3, 3), 50, True, [1], "TCP_1", 0),  # 正常记录
            TLSRecordInfo(1, 23, (3, 3), 100, True, [1], "TCP_1", 55),  # 会出错的记录
        ]
        
        # 模拟第二个记录处理出错
        original_method = generator._generate_rule_for_record
        def mock_generate_rule(record):
            if record.content_type == 23:
                raise ValueError("测试错误")
            return original_method(record)
        
        with patch.object(generator, '_generate_rule_for_record', side_effect=mock_generate_rule):
            rules = generator.generate_rules(records)
        
        # 应该只生成一个规则（错误的记录被跳过）
        assert len(rules) == 1
        assert rules[0].tls_record_type == 22


class TestTLSMaskRuleGeneratorIntegration:
    """集成测试"""
    
    def test_complete_workflow(self):
        """测试完整工作流程"""
        config = {
            'enable_multi_record_optimization': True,
            'enable_cross_packet_detection': True,
            'validate_boundaries': True,
            'verbose': False
        }
        generator = TLSMaskRuleGenerator(config)
        
        # 创建复杂的TLS记录场景
        records = [
            # 包1: 握手记录
            TLSRecordInfo(1, 22, (3, 3), 200, True, [1], "TCP_1", 0),
            
            # 包2: 多个记录
            TLSRecordInfo(2, 20, (3, 3), 6, True, [2], "TCP_1", 0),     # ChangeCipherSpec
            TLSRecordInfo(2, 22, (3, 3), 100, True, [2], "TCP_1", 11),  # Handshake
            
            # 包3: 应用数据
            TLSRecordInfo(3, 23, (3, 3), 1000, True, [3], "TCP_1", 0),
            
            # 包4: 跨包记录
            TLSRecordInfo(4, 23, (3, 3), 1500, False, [4, 5], "TCP_1", 0),
            
            # 包5: 心跳
            TLSRecordInfo(5, 24, (3, 3), 50, True, [5], "TCP_2", 0),
        ]
        
        rules = generator.generate_rules(records)
        
        # 验证生成的规则数量和类型
        assert len(rules) == 6
        
        # 验证不同类型的处理策略
        tls_types = [rule.tls_record_type for rule in rules]
        assert 22 in tls_types  # Handshake
        assert 20 in tls_types  # ChangeCipherSpec
        assert 23 in tls_types  # ApplicationData
        assert 24 in tls_types  # Heartbeat
        
        # 验证操作类型分布
        keep_all_rules = [r for r in rules if r.action == MaskAction.KEEP_ALL]
        mask_payload_rules = [r for r in rules if r.action == MaskAction.MASK_PAYLOAD]
        
        assert len(keep_all_rules) >= 3  # 至少握手、CCS、心跳应该完全保留
        assert len(mask_payload_rules) >= 1  # 至少有一个应用数据应该掩码
        
        # 验证统计信息
        stats = generator.get_generation_statistics()
        assert stats['processed_records_count'] == 6
        assert stats['generated_rules_count'] == 6
        assert stats['cross_packet_records_count'] == 1
    
    def test_performance_with_large_dataset(self):
        """测试大数据集性能"""
        generator = TLSMaskRuleGenerator()
        
        # 创建大量记录
        records = []
        for i in range(100):
            record = TLSRecordInfo(
                packet_number=i + 1,
                content_type=23,  # ApplicationData
                version=(3, 3),
                length=1000,
                is_complete=True,
                spans_packets=[i + 1],
                tcp_stream_id=f"TCP_{i % 10}",  # 10个不同的流
                record_offset=0
            )
            records.append(record)
        
        # 测试处理时间（应该在合理范围内）
        import time
        start_time = time.time()
        
        rules = generator.generate_rules(records)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # 验证结果
        assert len(rules) == 100
        assert processing_time < 1.0  # 应该在1秒内完成
        
        # 验证统计信息
        stats = generator.get_generation_statistics()
        assert stats['processed_records_count'] == 100
        assert stats['generated_rules_count'] == 100 