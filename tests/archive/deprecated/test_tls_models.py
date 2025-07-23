"""
TLS协议模型单元测试

测试TLS协议处理模型的所有组件和功能。
"""

import pytest
from typing import List, Tuple

from src.pktmask.core.trim.models.tls_models import (
    TLSProcessingStrategy,
    MaskAction,
    TLSRecordInfo,
    MaskRule,
    TLSAnalysisResult,
    create_mask_rule_for_tls_record,
    validate_tls_record_boundary,
    get_tls_processing_strategy
)


class TestTLSProcessingStrategy:
    """测试TLS处理策略枚举"""
    
    def test_strategy_values(self):
        """测试策略值"""
        assert TLSProcessingStrategy.KEEP_ALL.value == "keep_all"
        assert TLSProcessingStrategy.MASK_PAYLOAD.value == "mask_payload"
    
    def test_strategy_count(self):
        """测试策略数量"""
        assert len(TLSProcessingStrategy) == 3  # 新增了MASK_ALL_PAYLOAD


class TestMaskAction:
    """测试掩码操作枚举"""
    
    def test_action_values(self):
        """测试操作值"""
        assert MaskAction.KEEP_ALL.value == "keep_all"
        assert MaskAction.MASK_PAYLOAD.value == "mask_payload"
    
    def test_action_count(self):
        """测试操作数量"""
        assert len(MaskAction) == 3  # 新增了MASK_ALL_PAYLOAD


class TestTLSRecordInfo:
    """测试TLS记录信息模型"""
    
    def test_valid_tls_record_creation(self):
        """测试有效TLS记录创建"""
        record = TLSRecordInfo(
            packet_number=1,
            content_type=23,
            version=(3, 3),
            length=100,
            is_complete=True,
            spans_packets=[1],
            tcp_stream_id="TCP_192.168.1.1:443_10.0.0.1:56789_forward",
            record_offset=5
        )
        
        assert record.packet_number == 1
        assert record.content_type == 23
        assert record.version == (3, 3)
        assert record.length == 100
        assert record.is_complete is True
        assert record.spans_packets == [1]
        assert record.record_offset == 5
    
    def test_invalid_content_type(self):
        """测试无效的内容类型"""
        with pytest.raises(ValueError, match="不支持的TLS内容类型"):
            TLSRecordInfo(
                packet_number=1,
                content_type=99,  # 无效类型
                version=(3, 3),
                length=100,
                is_complete=True,
                spans_packets=[1],
                tcp_stream_id="test_stream",
                record_offset=0
            )
    
    def test_negative_length(self):
        """测试负数长度"""
        with pytest.raises(ValueError, match="TLS记录长度不能为负数"):
            TLSRecordInfo(
                packet_number=1,
                content_type=23,
                version=(3, 3),
                length=-10,  # 负数长度
                is_complete=True,
                spans_packets=[1],
                tcp_stream_id="test_stream",
                record_offset=0
            )
    
    def test_negative_offset(self):
        """测试负数偏移"""
        with pytest.raises(ValueError, match="记录偏移量不能为负数"):
            TLSRecordInfo(
                packet_number=1,
                content_type=23,
                version=(3, 3),
                length=100,
                is_complete=True,
                spans_packets=[1],
                tcp_stream_id="test_stream",
                record_offset=-5  # 负数偏移
            )
    
    def test_packet_not_in_spans(self):
        """测试包编号不在跨包列表中"""
        with pytest.raises(ValueError, match="包编号.*必须在跨包列表中"):
            TLSRecordInfo(
                packet_number=5,
                content_type=23,
                version=(3, 3),
                length=100,
                is_complete=True,
                spans_packets=[1, 2, 3],  # 不包含包编号5
                tcp_stream_id="test_stream",
                record_offset=0
            )
    
    def test_content_type_names(self):
        """测试内容类型名称"""
        test_cases = [
            (20, "ChangeCipherSpec"),
            (21, "Alert"),
            (22, "Handshake"),
            (23, "ApplicationData"),
            (24, "Heartbeat")
        ]
        
        for content_type, expected_name in test_cases:
            record = TLSRecordInfo(
                packet_number=1,
                content_type=content_type,
                version=(3, 3),
                length=100,
                is_complete=True,
                spans_packets=[1],
                tcp_stream_id="test_stream",
                record_offset=0
            )
            assert record.content_type_name == expected_name
    
    def test_processing_strategies(self):
        """测试处理策略"""
        # ApplicationData使用MASK_PAYLOAD策略
        app_data_record = TLSRecordInfo(
            packet_number=1,
            content_type=23,
            version=(3, 3),
            length=100,
            is_complete=True,
            spans_packets=[1],
            tcp_stream_id="test_stream",
            record_offset=0
        )
        assert app_data_record.processing_strategy == TLSProcessingStrategy.MASK_PAYLOAD
        
        # 其他类型使用KEEP_ALL策略
        for content_type in [20, 21, 22, 24]:
            record = TLSRecordInfo(
                packet_number=1,
                content_type=content_type,
                version=(3, 3),
                length=100,
                is_complete=True,
                spans_packets=[1],
                tcp_stream_id="test_stream",
                record_offset=0
            )
            assert record.processing_strategy == TLSProcessingStrategy.KEEP_ALL
    
    def test_cross_packet_detection(self):
        """测试跨包检测"""
        # 单包记录
        single_packet = TLSRecordInfo(
            packet_number=1,
            content_type=23,
            version=(3, 3),
            length=100,
            is_complete=True,
            spans_packets=[1],
            tcp_stream_id="test_stream",
            record_offset=0
        )
        assert not single_packet.is_cross_packet
        
        # 跨包记录
        cross_packet = TLSRecordInfo(
            packet_number=1,
            content_type=23,
            version=(3, 3),
            length=2000,
            is_complete=True,
            spans_packets=[1, 2, 3],
            tcp_stream_id="test_stream",
            record_offset=0
        )
        assert cross_packet.is_cross_packet
    
    def test_version_strings(self):
        """测试版本字符串"""
        test_cases = [
            ((3, 0), "SSL 3.0"),
            ((3, 1), "TLS 1.0"),
            ((3, 2), "TLS 1.1"),
            ((3, 3), "TLS 1.2"),
            ((3, 4), "TLS 1.3"),
            ((4, 0), "TLS 4.0")
        ]
        
        for version, expected_string in test_cases:
            record = TLSRecordInfo(
                packet_number=1,
                content_type=23,
                version=version,
                length=100,
                is_complete=True,
                spans_packets=[1],
                tcp_stream_id="test_stream",
                record_offset=0
            )
            assert record.get_version_string() == expected_string


class TestMaskRule:
    """测试掩码规则模型"""
    
    def test_valid_mask_rule_creation(self):
        """测试有效掩码规则创建"""
        rule = MaskRule(
            packet_number=1,
            tcp_stream_id="test_stream",
            tls_record_offset=10,
            tls_record_length=100,
            mask_offset=5,
            mask_length=90,
            action=MaskAction.MASK_PAYLOAD,
            reason="测试掩码",
            tls_record_type=23
        )
        
        assert rule.packet_number == 1
        assert rule.tcp_stream_id == "test_stream"
        assert rule.tls_record_offset == 10
        assert rule.tls_record_length == 100
        assert rule.mask_offset == 5
        assert rule.mask_length == 90
        assert rule.action == MaskAction.MASK_PAYLOAD
        assert rule.reason == "测试掩码"
        assert rule.tls_record_type == 23
    
    def test_negative_values_validation(self):
        """测试负数值验证"""
        base_params = {
            "packet_number": 1,
            "tcp_stream_id": "test_stream",
            "tls_record_offset": 10,
            "tls_record_length": 100,
            "mask_offset": 5,
            "mask_length": 90,
            "action": MaskAction.MASK_PAYLOAD,
            "reason": "测试",
            "tls_record_type": 23
        }
        
        # 测试负数TLS记录偏移
        with pytest.raises(ValueError, match="TLS记录偏移量不能为负数"):
            MaskRule(**{**base_params, "tls_record_offset": -1})
        
        # 测试零或负数TLS记录长度
        with pytest.raises(ValueError, match="TLS记录长度必须为正数"):
            MaskRule(**{**base_params, "tls_record_length": 0})
        
        # 测试负数掩码偏移
        with pytest.raises(ValueError, match="掩码偏移量不能为负数"):
            MaskRule(**{**base_params, "mask_offset": -1})
        
        # 测试负数掩码长度（-1是特殊值，允许；-2及以下不允许）
        with pytest.raises(ValueError, match="掩码长度不能小于-1"):
            MaskRule(**{**base_params, "mask_length": -2})
    
    def test_boundary_validation(self):
        """测试边界验证"""
        # 掩码范围超出TLS记录边界
        with pytest.raises(ValueError, match="掩码范围超出TLS记录边界"):
            MaskRule(
                packet_number=1,
                tcp_stream_id="test_stream",
                tls_record_offset=10,
                tls_record_length=100,
                mask_offset=50,
                mask_length=60,  # 50 + 60 = 110 > 100
                action=MaskAction.MASK_PAYLOAD,
                reason="测试",
                tls_record_type=23
            )
    
    def test_invalid_tls_record_type(self):
        """测试无效TLS记录类型"""
        with pytest.raises(ValueError, match="不支持的TLS记录类型"):
            MaskRule(
                packet_number=1,
                tcp_stream_id="test_stream",
                tls_record_offset=10,
                tls_record_length=100,
                mask_offset=5,
                mask_length=90,
                action=MaskAction.MASK_PAYLOAD,
                reason="测试",
                tls_record_type=99  # 无效类型
            )
    
    def test_absolute_positions(self):
        """测试绝对位置计算"""
        rule = MaskRule(
            packet_number=1,
            tcp_stream_id="test_stream",
            tls_record_offset=10,
            tls_record_length=100,
            mask_offset=5,
            mask_length=90,
            action=MaskAction.MASK_PAYLOAD,
            reason="测试",
            tls_record_type=23
        )
        
        assert rule.absolute_mask_start == 15  # 10 + 5
        assert rule.absolute_mask_end == 105   # 15 + 90
    
    def test_is_mask_operation(self):
        """测试是否为掩码操作"""
        # 实际掩码操作
        mask_rule = MaskRule(
            packet_number=1,
            tcp_stream_id="test_stream",
            tls_record_offset=10,
            tls_record_length=100,
            mask_offset=5,
            mask_length=90,
            action=MaskAction.MASK_PAYLOAD,
            reason="测试",
            tls_record_type=23
        )
        assert mask_rule.is_mask_operation
        
        # 保留操作
        keep_rule = MaskRule(
            packet_number=1,
            tcp_stream_id="test_stream",
            tls_record_offset=10,
            tls_record_length=100,
            mask_offset=0,
            mask_length=0,
            action=MaskAction.KEEP_ALL,
            reason="测试",
            tls_record_type=22
        )
        assert not keep_rule.is_mask_operation
    
    def test_description_generation(self):
        """测试描述生成"""
        # 掩码操作描述
        mask_rule = MaskRule(
            packet_number=1,
            tcp_stream_id="test_stream",
            tls_record_offset=10,
            tls_record_length=100,
            mask_offset=5,
            mask_length=90,
            action=MaskAction.MASK_PAYLOAD,
            reason="测试掩码",
            tls_record_type=23
        )
        assert "TLS-23 掩码[5:95]: 测试掩码" == mask_rule.get_description()
        
        # 保留操作描述
        keep_rule = MaskRule(
            packet_number=1,
            tcp_stream_id="test_stream",
            tls_record_offset=10,
            tls_record_length=100,
            mask_offset=0,
            mask_length=0,
            action=MaskAction.KEEP_ALL,
            reason="测试保留",
            tls_record_type=22
        )
        assert "TLS-22 完全保留: 测试保留" == keep_rule.get_description()


class TestTLSAnalysisResult:
    """测试TLS分析结果模型"""
    
    def test_analysis_result_creation(self):
        """测试分析结果创建"""
        records = [
            TLSRecordInfo(1, 22, (3, 3), 100, True, [1], "stream1", 0),
            TLSRecordInfo(2, 23, (3, 3), 200, True, [2], "stream1", 100),
            TLSRecordInfo(3, 23, (3, 3), 300, True, [3, 4], "stream1", 300)
        ]
        
        cross_packet_records = [records[2]]  # 跨包记录
        
        result = TLSAnalysisResult(
            total_packets=100,
            tls_packets=50,
            tls_records=records,
            cross_packet_records=cross_packet_records,
            analysis_errors=["测试错误"]
        )
        
        assert result.total_packets == 100
        assert result.tls_packets == 50
        assert len(result.tls_records) == 3
        assert len(result.cross_packet_records) == 1
        assert result.analysis_errors == ["测试错误"]
    
    def test_tls_record_types_statistics(self):
        """测试TLS记录类型统计"""
        records = [
            TLSRecordInfo(1, 22, (3, 3), 100, True, [1], "stream1", 0),  # Handshake
            TLSRecordInfo(2, 23, (3, 3), 200, True, [2], "stream1", 100),  # ApplicationData
            TLSRecordInfo(3, 23, (3, 3), 300, True, [3], "stream1", 300),  # ApplicationData
            TLSRecordInfo(4, 21, (3, 3), 50, True, [4], "stream1", 600)   # Alert
        ]
        
        result = TLSAnalysisResult(
            total_packets=10,
            tls_packets=5,
            tls_records=records,
            cross_packet_records=[],
            analysis_errors=[]
        )
        
        type_stats = result.tls_record_types
        assert type_stats["Handshake"] == 1
        assert type_stats["ApplicationData"] == 2
        assert type_stats["Alert"] == 1
    
    def test_cross_packet_ratio(self):
        """测试跨包记录比例计算"""
        records = [
            TLSRecordInfo(1, 23, (3, 3), 100, True, [1], "stream1", 0),
            TLSRecordInfo(2, 22, (3, 3), 200, True, [2], "stream1", 100), 
            TLSRecordInfo(3, 23, (3, 3), 300, True, [3, 4], "stream1", 300),  # 跨包记录
            TLSRecordInfo(4, 21, (3, 3), 50, True, [4, 5, 6], "stream1", 600),  # 跨包记录
        ]
        
        cross_packet_records = [r for r in records if r.is_cross_packet]
        
        result = TLSAnalysisResult(
            total_packets=10,
            tls_packets=4,
            tls_records=records,
            cross_packet_records=cross_packet_records,
            analysis_errors=[]
        )
        
        assert result.cross_packet_ratio == 0.5  # 2/4 = 0.5
    
    def test_empty_records_ratio(self):
        """测试空记录的跨包比例"""
        result = TLSAnalysisResult(
            total_packets=10,
            tls_packets=0,
            tls_records=[],
            cross_packet_records=[],
            analysis_errors=[]
        )
        
        assert result.cross_packet_ratio == 0.0
    
    def test_summary_generation(self):
        """测试摘要生成"""
        records = [
            TLSRecordInfo(1, 22, (3, 3), 100, True, [1], "stream1", 0),
            TLSRecordInfo(2, 23, (3, 3), 200, True, [2, 3], "stream1", 100)
        ]
        
        result = TLSAnalysisResult(
            total_packets=100,
            tls_packets=50,
            tls_records=records,
            cross_packet_records=[records[1]],
            analysis_errors=[]
        )
        
        summary = result.get_summary()
        assert "总包数=100" in summary
        assert "TLS包数=50" in summary
        assert "TLS记录数=2" in summary
        assert "跨包记录数=1" in summary


class TestUtilityFunctions:
    """测试工具函数"""
    
    def test_create_mask_rule_for_keep_all_record(self):
        """测试为完全保留记录创建掩码规则"""
        # 测试Handshake记录（应该完全保留）
        handshake_record = TLSRecordInfo(
            packet_number=1,
            content_type=22,
            version=(3, 3),
            length=100,
            is_complete=True,
            spans_packets=[1],
            tcp_stream_id="test_stream",
            record_offset=0
        )
        
        rule = create_mask_rule_for_tls_record(handshake_record)
        
        assert rule.action == MaskAction.KEEP_ALL
        assert rule.mask_offset == 0
        assert rule.mask_length == 0
        assert rule.tls_record_type == 22
        assert "TLS-22 协议完全保留策略" == rule.reason
    
    def test_create_mask_rule_for_application_data_complete(self):
        """测试为完整ApplicationData记录创建掩码规则"""
        app_data_record = TLSRecordInfo(
            packet_number=1,
            content_type=23,
            version=(3, 3),
            length=100,  # 长度大于5，应该掩码
            is_complete=True,
            spans_packets=[1],
            tcp_stream_id="test_stream",
            record_offset=0
        )
        
        rule = create_mask_rule_for_tls_record(app_data_record)
        
        assert rule.action == MaskAction.MASK_PAYLOAD
        assert rule.mask_offset == 5  # 保留5字节头部
        assert rule.mask_length == 100  # 掩码整个消息体
        assert rule.tls_record_type == 23
        assert "TLS-23 智能掩码：保留头部，掩码载荷" == rule.reason
    
    def test_create_mask_rule_for_application_data_incomplete(self):
        """测试为不完整ApplicationData记录创建掩码规则"""
        incomplete_record = TLSRecordInfo(
            packet_number=1,
            content_type=23,
            version=(3, 3),
            length=100,
            is_complete=False,  # 不完整记录
            spans_packets=[1, 2],
            tcp_stream_id="test_stream",
            record_offset=0
        )
        
        rule = create_mask_rule_for_tls_record(incomplete_record)
        
        assert rule.action == MaskAction.KEEP_ALL
        assert rule.mask_offset == 0
        assert rule.mask_length == 0
        assert rule.tls_record_type == 23
        assert "TLS-23 不完整记录或无消息体：完全保留" == rule.reason
    
    def test_create_mask_rule_for_application_data_header_only(self):
        """测试为纯头部ApplicationData记录创建掩码规则"""
        header_only_record = TLSRecordInfo(
            packet_number=1,
            content_type=23,
            version=(3, 3),
            length=5,  # 仅头部长度
            is_complete=True,
            spans_packets=[1],
            tcp_stream_id="test_stream",
            record_offset=0
        )
        
        rule = create_mask_rule_for_tls_record(header_only_record)
        
        assert rule.action == MaskAction.MASK_PAYLOAD
        assert rule.mask_offset == 5  # 保留头部
        assert rule.mask_length == 5  # 掩码消息体
        assert rule.tls_record_type == 23
        assert "TLS-23 智能掩码：保留头部，掩码载荷" == rule.reason
    
    def test_validate_tls_record_boundary_valid(self):
        """测试有效TLS记录边界"""
        record = TLSRecordInfo(
            packet_number=1,
            content_type=23,
            version=(3, 3),
            length=100,
            is_complete=True,
            spans_packets=[1],
            tcp_stream_id="test_stream",
            record_offset=10
        )
        
        # 记录边界在TCP载荷范围内
        assert validate_tls_record_boundary(record, 200)  # 10 + 100 = 110 <= 200
        assert validate_tls_record_boundary(record, 110)  # 边界情况
    
    def test_validate_tls_record_boundary_invalid(self):
        """测试无效TLS记录边界"""
        record = TLSRecordInfo(
            packet_number=1,
            content_type=23,
            version=(3, 3),
            length=100,
            is_complete=True,
            spans_packets=[1],
            tcp_stream_id="test_stream",
            record_offset=10
        )
        
        # 记录边界超出TCP载荷范围
        assert not validate_tls_record_boundary(record, 50)   # 10 + 100 = 110 > 50
        assert not validate_tls_record_boundary(record, 109)  # 边界情况
    
    def test_get_tls_processing_strategy(self):
        """测试获取TLS处理策略"""
        # ApplicationData使用MASK_PAYLOAD策略
        assert get_tls_processing_strategy(23) == TLSProcessingStrategy.MASK_PAYLOAD
        
        # 其他类型使用KEEP_ALL策略
        for content_type in [20, 21, 22, 24]:
            assert get_tls_processing_strategy(content_type) == TLSProcessingStrategy.KEEP_ALL
        
        # 无效类型抛出异常
        with pytest.raises(ValueError, match="不支持的TLS内容类型"):
            get_tls_processing_strategy(99) 