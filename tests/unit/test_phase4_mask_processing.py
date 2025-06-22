"""
Phase 4 核心掩码处理测试

测试载荷提取器、掩码应用器和三种掩码类型的功能。
验收标准：
- 支持所有定义的掩码类型  
- 序列号匹配准确率100%
- 字节级掩码精确应用
- 掩码处理统计信息准确
"""

import pytest
import logging
from unittest.mock import Mock, patch
from scapy.all import Packet, Ether, IP, TCP, Raw

from src.pktmask.core.independent_pcap_masker.core.payload_extractor import (
    PayloadExtractor, create_payload_extractor
)
from src.pktmask.core.independent_pcap_masker.core.mask_applier import (
    MaskApplier, create_mask_applier
)
from src.pktmask.core.independent_pcap_masker.core.models import (
    MaskEntry, SequenceMaskTable
)
from src.pktmask.core.independent_pcap_masker.exceptions import ValidationError


class TestPayloadExtractor:
    """测试载荷提取器"""
    
    def setup_method(self):
        """设置测试方法"""
        self.logger = logging.getLogger("test")
        self.extractor = PayloadExtractor(self.logger)
    
    def test_create_payload_extractor(self):
        """测试工厂函数"""
        extractor = create_payload_extractor()
        assert isinstance(extractor, PayloadExtractor)
        
        extractor_with_logger = create_payload_extractor(self.logger)
        assert extractor_with_logger.logger == self.logger
    
    def test_extract_tcp_payload_success(self):
        """测试成功提取TCP载荷"""
        # 创建带有载荷的TCP包
        payload_data = b"Hello, World! This is test payload data."
        packet = Ether()/IP(src="1.2.3.4", dst="5.6.7.8")/TCP(sport=1234, dport=80)/Raw(load=payload_data)
        
        # 提取载荷
        extracted_payload = self.extractor.extract_tcp_payload(packet)
        
        assert extracted_payload == payload_data
        assert self.extractor.stats['packets_processed'] == 1
        assert self.extractor.stats['tcp_packets_found'] == 1
        assert self.extractor.stats['payloads_extracted'] == 1
        assert self.extractor.stats['raw_layers_found'] == 1
    
    def test_extract_tcp_payload_no_raw_layer(self):
        """测试TCP包没有Raw层的情况"""
        packet = Ether()/IP(src="1.2.3.4", dst="5.6.7.8")/TCP(sport=1234, dport=80)
        
        extracted_payload = self.extractor.extract_tcp_payload(packet)
        
        assert extracted_payload is None
        assert self.extractor.stats['tcp_packets_found'] == 1
        assert self.extractor.stats['raw_layers_found'] == 0
        assert self.extractor.stats['payloads_extracted'] == 0
    
    def test_extract_tcp_payload_non_tcp_packet(self):
        """测试非TCP包的情况"""
        from scapy.all import UDP
        packet = Ether()/IP(src="1.2.3.4", dst="5.6.7.8")/UDP(sport=1234, dport=80)/Raw(load=b"test")
        
        extracted_payload = self.extractor.extract_tcp_payload(packet)
        
        assert extracted_payload is None
        assert self.extractor.stats['tcp_packets_found'] == 0
    
    def test_extract_stream_info_success(self):
        """测试成功提取流信息"""
        payload_data = b"Test stream info extraction"
        packet = Ether()/IP(src="1.2.3.4", dst="5.6.7.8")/TCP(sport=1234, dport=80, seq=1000)/Raw(load=payload_data)
        
        stream_info = self.extractor.extract_stream_info(packet)
        
        assert stream_info is not None
        stream_id, sequence, payload = stream_info
        
        # 检查流ID格式（较小的IP:port组合在前）
        assert stream_id == "TCP_1.2.3.4:1234_5.6.7.8:80_forward"
        assert sequence == 1000
        assert payload == payload_data
    
    def test_generate_stream_id_direction_logic(self):
        """测试流ID方向判断逻辑"""
        # 创建两个方向的包
        packet1 = Ether()/IP(src="1.2.3.4", dst="5.6.7.8")/TCP(sport=1234, dport=80)/Raw(load=b"test1")
        packet2 = Ether()/IP(src="5.6.7.8", dst="1.2.3.4")/TCP(sport=80, dport=1234)/Raw(load=b"test2")
        
        stream_id1 = self.extractor._generate_stream_id(packet1)
        stream_id2 = self.extractor._generate_stream_id(packet2)
        
        # 方向1: 1.2.3.4:1234 -> 5.6.7.8:80 (forward)
        assert stream_id1 == "TCP_1.2.3.4:1234_5.6.7.8:80_forward"
        
        # 方向2: 5.6.7.8:80 -> 1.2.3.4:1234 (reverse，因为较小的组合在前)
        assert stream_id2 == "TCP_1.2.3.4:1234_5.6.7.8:80_reverse"
    
    def test_verify_raw_layer_dominance(self):
        """测试Raw层存在率验证"""
        packets = []
        
        # 创建5个TCP包，其中4个有Raw层
        for i in range(4):
            packets.append(
                Ether()/IP(src="1.2.3.4", dst="5.6.7.8")/TCP(sport=1234, dport=80)/Raw(load=f"data{i}".encode())
            )
        
        # 1个TCP包没有Raw层
        packets.append(Ether()/IP(src="1.2.3.4", dst="5.6.7.8")/TCP(sport=1234, dport=80))
        
        # 1个非TCP包
        from scapy.all import UDP
        packets.append(Ether()/IP(src="1.2.3.4", dst="5.6.7.8")/UDP(sport=1234, dport=80))
        
        verification_result = self.extractor.verify_raw_layer_dominance(packets)
        
        assert verification_result['total_packets'] == 6
        assert verification_result['tcp_packets'] == 5
        assert verification_result['tcp_with_raw'] == 4
        assert verification_result['raw_layer_rate'] == 0.8  # 4/5
        assert verification_result['protocol_parsing_disabled'] == False  # <95%
    
    def test_statistics_calculation(self):
        """测试统计信息计算"""
        # 处理一些包
        packets = [
            Ether()/IP(src="1.2.3.4", dst="5.6.7.8")/TCP(sport=1234, dport=80)/Raw(load=b"data1"),
            Ether()/IP(src="1.2.3.4", dst="5.6.7.8")/TCP(sport=1234, dport=80),  # 没有Raw层
        ]
        
        for packet in packets:
            self.extractor.extract_tcp_payload(packet)
        
        stats = self.extractor.get_statistics()
        
        assert stats['packets_processed'] == 2
        assert stats['tcp_packets_found'] == 2
        assert stats['payloads_extracted'] == 1
        assert stats['tcp_packet_rate'] == 1.0  # 2/2
        assert stats['extraction_success_rate'] == 0.5  # 1/2
        assert stats['raw_layer_availability'] == 0.5  # 1/2
        assert stats['tcp_payload_rate'] == 0.5  # 1/2
    
    def test_reset_statistics(self):
        """测试统计信息重置"""
        # 先处理一些数据
        packet = Ether()/IP(src="1.2.3.4", dst="5.6.7.8")/TCP(sport=1234, dport=80)/Raw(load=b"test")
        self.extractor.extract_tcp_payload(packet)
        
        assert self.extractor.stats['packets_processed'] > 0
        
        # 重置统计
        self.extractor.reset_statistics()
        
        assert self.extractor.stats['packets_processed'] == 0
        assert self.extractor.stats['tcp_packets_found'] == 0
        assert self.extractor.stats['payloads_extracted'] == 0


class TestMaskApplier:
    """测试掩码应用器"""
    
    def setup_method(self):
        """设置测试方法"""
        self.logger = logging.getLogger("test")
        self.applier = MaskApplier(mask_byte_value=0x00, logger=self.logger)
        self.mask_table = SequenceMaskTable()
    
    def test_create_mask_applier(self):
        """测试工厂函数"""
        applier = create_mask_applier()
        assert isinstance(applier, MaskApplier)
        assert applier.mask_byte_value == 0x00
        
        applier_custom = create_mask_applier(mask_byte_value=0xFF, logger=self.logger)
        assert applier_custom.mask_byte_value == 0xFF
        assert applier_custom.logger == self.logger
    
    def test_apply_mask_after_type(self):
        """测试mask_after掩码类型"""
        # 创建测试数据
        payload = bytearray(b"Hello, World! This is a long test payload.")
        mask_entry = MaskEntry(
            stream_id="TCP_1.2.3.4:1234_5.6.7.8:80_forward",
            sequence_start=1000,
            sequence_end=2000,
            mask_type="mask_after",
            mask_params={"keep_bytes": 5}
        )
        
        # 应用掩码
        bytes_masked = self.applier._apply_mask_after(payload, mask_entry)
        
        # 验证结果
        expected_masked = len(payload) - 5
        assert bytes_masked == expected_masked
        assert payload[:5] == b"Hello"  # 前5字节保留
        assert all(b == 0x00 for b in payload[5:])  # 其余字节被掩码
    
    def test_apply_mask_range_type(self):
        """测试mask_range掩码类型"""
        payload = bytearray(b"0123456789ABCDEF")
        mask_entry = MaskEntry(
            stream_id="TCP_1.2.3.4:1234_5.6.7.8:80_forward",
            sequence_start=1000,
            sequence_end=2000,
            mask_type="mask_range",
            mask_params={"ranges": [(2, 5), (8, 12)]}
        )
        
        bytes_masked = self.applier._apply_mask_range(payload, mask_entry)
        
        # 验证结果
        assert bytes_masked == 7  # (5-2) + (12-8) = 3 + 4 = 7
        assert payload[:2] == b"01"  # 前2字节保留
        assert all(b == 0x00 for b in payload[2:5])  # 位置2-4被掩码
        assert payload[5:8] == b"567"  # 位置5-7保留
        assert all(b == 0x00 for b in payload[8:12])  # 位置8-11被掩码
        assert payload[12:] == b"CDEF"  # 位置12-15保留
    
    def test_apply_keep_all_type(self):
        """测试keep_all掩码类型"""
        payload = bytearray(b"This should be kept intact.")
        original_payload = payload.copy()
        
        mask_entry = MaskEntry(
            stream_id="TCP_1.2.3.4:1234_5.6.7.8:80_forward",
            sequence_start=1000,
            sequence_end=2000,
            mask_type="keep_all",
            mask_params={}
        )
        
        bytes_masked = self.applier._apply_keep_all(payload, mask_entry)
        
        # 验证结果
        assert bytes_masked == 0
        assert payload == original_payload  # 载荷完全不变
    
    def test_apply_masks_to_packets_integration(self):
        """测试数据包掩码应用的集成流程"""
        # 创建测试数据包
        payload_data = b"This is a test payload for masking."
        packet = Ether()/IP(src="1.2.3.4", dst="5.6.7.8")/TCP(sport=1234, dport=80, seq=1500)/Raw(load=payload_data)
        
        # 创建掩码条目
        mask_entry = MaskEntry(
            stream_id="TCP_1.2.3.4:1234_5.6.7.8:80_forward",
            sequence_start=1000,
            sequence_end=2000,
            mask_type="mask_after",
            mask_params={"keep_bytes": 10}
        )
        self.mask_table.add_entry(mask_entry)
        
        # 应用掩码
        modified_packets, stats = self.applier.apply_masks_to_packets([packet], self.mask_table)
        
        # 验证结果
        assert len(modified_packets) == 1
        assert stats['packets_processed'] == 1
        assert stats['packets_modified'] == 1
        assert stats['sequence_matches'] == 1
        assert stats['mask_after_applied'] == 1
        
        # 检查载荷是否正确修改
        modified_packet = modified_packets[0]
        raw_layer = modified_packet.getlayer(Raw)
        assert raw_layer is not None
        
        modified_payload = bytes(raw_layer.load)
        assert modified_payload[:10] == payload_data[:10]  # 前10字节保留
        assert all(b == 0x00 for b in modified_payload[10:])  # 其余被掩码
    
    def test_sequence_number_matching(self):
        """测试序列号匹配逻辑"""
        packets = []
        
        # 创建多个不同序列号的包
        for i, seq in enumerate([500, 1500, 2500]):  # 只有1500在掩码范围内
            payload = f"Payload {i}".encode()
            packet = Ether()/IP(src="1.2.3.4", dst="5.6.7.8")/TCP(sport=1234, dport=80, seq=seq)/Raw(load=payload)
            packets.append(packet)
        
        # 创建掩码条目（覆盖1000-2000）
        mask_entry = MaskEntry(
            stream_id="TCP_1.2.3.4:1234_5.6.7.8:80_forward",
            sequence_start=1000,
            sequence_end=2000,
            mask_type="mask_after",
            mask_params={"keep_bytes": 3}
        )
        self.mask_table.add_entry(mask_entry)
        
        # 应用掩码
        modified_packets, stats = self.applier.apply_masks_to_packets(packets, self.mask_table)
        
        # 验证结果
        assert stats['packets_processed'] == 3
        assert stats['packets_modified'] == 1  # 只有1个包被修改
        assert stats['sequence_matches'] == 1
        assert stats['sequence_mismatches'] == 2
    
    def test_validate_mask_application(self):
        """测试掩码应用验证"""
        original_payload = b"0123456789ABCDEF"
        
        # 创建期望的修改（mask_after，保留前5字节）
        modified_payload = bytearray(original_payload)
        for i in range(5, len(modified_payload)):
            modified_payload[i] = 0x00
        
        mask_entry = MaskEntry(
            stream_id="test",
            sequence_start=1000,
            sequence_end=2000,
            mask_type="mask_after",
            mask_params={"keep_bytes": 5}
        )
        
        # 验证正确的修改
        result = self.applier.validate_mask_application(
            original_payload, bytes(modified_payload), [mask_entry]
        )
        
        assert result['valid'] == True
        assert result['expected_modifications'] == 11  # 16-5
        assert result['actual_modifications'] == 11
        assert result['unexpected_modifications'] == []
        assert result['missing_modifications'] == []
    
    def test_multiple_mask_entries_priority(self):
        """测试多个掩码条目的优先级处理"""
        payload = bytearray(b"0123456789ABCDEF")
        
        # 创建两个重叠的掩码条目
        entry1 = MaskEntry(
            stream_id="test",
            sequence_start=1000,
            sequence_end=2000,
            mask_type="mask_after",
            mask_params={"keep_bytes": 8}
        )
        
        entry2 = MaskEntry(
            stream_id="test",
            sequence_start=1000,
            sequence_end=2000,
            mask_type="mask_range",
            mask_params={"ranges": [(4, 8)]}  # 会在entry1基础上进一步掩码
        )
        
        # 应用第一个掩码
        self.applier._apply_mask_entry(payload, entry1, 1500, len(payload))
        # 应用第二个掩码
        self.applier._apply_mask_entry(payload, entry2, 1500, len(payload))
        
        # 验证结果：位置4-7也应该被掩码（即使在保留范围内）
        assert payload[:4] == b"0123"  # 前4字节保留
        assert all(b == 0x00 for b in payload[4:])  # 位置4-15全部被掩码
    
    def test_edge_cases_and_error_handling(self):
        """测试边界情况和错误处理"""
        # 测试keep_bytes超过载荷长度
        payload = bytearray(b"short")
        mask_entry = MaskEntry(
            stream_id="test",
            sequence_start=1000,
            sequence_end=2000,
            mask_type="mask_after",
            mask_params={"keep_bytes": 100}  # 超过载荷长度
        )
        
        bytes_masked = self.applier._apply_mask_after(payload, mask_entry)
        assert bytes_masked == 0  # 没有字节被掩码
        assert payload == b"short"  # 载荷不变
        
        # 测试无效的掩码类型（在MaskEntry创建时会失败）
        with pytest.raises(ValueError, match="不支持的掩码类型"):
            MaskEntry(
                stream_id="test",
                sequence_start=1000,
                sequence_end=2000,
                mask_type="invalid_type",
                mask_params={}
            )
        
        # 测试mask_range的错误参数
        payload2 = bytearray(b"test_range_error")
        
        # 测试ranges参数不是列表
        with pytest.raises(ValidationError):
            bad_entry = MaskEntry(
                stream_id="test",
                sequence_start=1000,
                sequence_end=2000,
                mask_type="mask_range",
                mask_params={"ranges": "not_a_list"}
            )
            self.applier._apply_mask_range(payload2, bad_entry)
        
        # 测试无效的范围格式
        with pytest.raises(ValidationError):
            bad_entry2 = MaskEntry(
                stream_id="test",
                sequence_start=1000,
                sequence_end=2000,
                mask_type="mask_range", 
                mask_params={"ranges": [(1, 2, 3)]}  # 三元组而不是二元组
            )
            self.applier._apply_mask_range(payload2, bad_entry2)
    
    def test_statistics_accuracy(self):
        """测试统计信息的准确性"""
        packets = []
        
        # 创建不同类型的测试包
        for i in range(5):
            if i < 3:  # 前3个包有匹配的掩码
                seq = 1500
            else:  # 后2个包没有匹配的掩码
                seq = 3000
            
            payload = f"Test payload {i}".encode()
            packet = Ether()/IP(src="1.2.3.4", dst="5.6.7.8")/TCP(sport=1234, dport=80, seq=seq)/Raw(load=payload)
            packets.append(packet)
        
        # 创建掩码条目
        mask_entry = MaskEntry(
            stream_id="TCP_1.2.3.4:1234_5.6.7.8:80_forward",
            sequence_start=1000,
            sequence_end=2000,
            mask_type="mask_after",
            mask_params={"keep_bytes": 5}
        )
        self.mask_table.add_entry(mask_entry)
        
        # 应用掩码
        modified_packets, stats = self.applier.apply_masks_to_packets(packets, self.mask_table)
        
        # 验证统计信息
        assert stats['packets_processed'] == 5
        assert stats['packets_modified'] == 3
        assert stats['sequence_matches'] == 3
        assert stats['sequence_mismatches'] == 2
        assert stats['mask_after_applied'] == 3
        assert stats['modification_rate'] == 0.6  # 3/5
        assert stats['sequence_match_rate'] == 0.6  # 3/5


class TestIntegration:
    """集成测试：测试载荷提取器和掩码应用器的协同工作"""
    
    def setup_method(self):
        """设置测试方法"""
        self.logger = logging.getLogger("test_integration")
    
    def test_end_to_end_mask_processing(self):
        """端到端掩码处理测试"""
        # 创建测试场景：TLS流量掩码
        packets = []
        
        # 模拟TLS握手和应用数据
        tls_handshake = b"\x16\x03\x03\x00\x47" + b"handshake_data" * 3  # TLS握手
        tls_app_data = b"\x17\x03\x03\x00\x20" + b"application_data" * 10  # TLS应用数据
        
        # 创建数据包
        packets.extend([
            # TLS握手包（应该被保留）
            Ether()/IP(src="1.2.3.4", dst="5.6.7.8")/TCP(sport=1234, dport=443, seq=1000)/Raw(load=tls_handshake),
            # TLS应用数据包（应该保留前5字节，掩码其余部分）
            Ether()/IP(src="1.2.3.4", dst="5.6.7.8")/TCP(sport=1234, dport=443, seq=1100)/Raw(load=tls_app_data),
            # 另一个应用数据包
            Ether()/IP(src="1.2.3.4", dst="5.6.7.8")/TCP(sport=1234, dport=443, seq=1200)/Raw(load=tls_app_data),
        ])
        
        # 创建掩码表
        mask_table = SequenceMaskTable()
        
        # 握手包：完全保留
        mask_table.add_entry(MaskEntry(
            stream_id="TCP_1.2.3.4:1234_5.6.7.8:443_forward",
            sequence_start=1000,
            sequence_end=1050,
            mask_type="keep_all",
            mask_params={}
        ))
        
        # 应用数据包：保留TLS头部（5字节）
        mask_table.add_entry(MaskEntry(
            stream_id="TCP_1.2.3.4:1234_5.6.7.8:443_forward", 
            sequence_start=1100,
            sequence_end=1300,
            mask_type="mask_after",
            mask_params={"keep_bytes": 5}
        ))
        
        # 创建掩码应用器并处理
        applier = MaskApplier(logger=self.logger)
        modified_packets, stats = applier.apply_masks_to_packets(packets, mask_table)
        
        # 验证结果
        assert len(modified_packets) == 3
        assert stats['packets_modified'] == 2  # 只有应用数据包被修改
        assert stats['keep_all_applied'] == 1
        assert stats['mask_after_applied'] == 2
        
        # 验证握手包未被修改
        handshake_packet = modified_packets[0]
        handshake_payload = bytes(handshake_packet.getlayer(Raw).load)
        assert handshake_payload == tls_handshake
        
        # 验证应用数据包被正确掩码
        for i in [1, 2]:
            app_packet = modified_packets[i]
            app_payload = bytes(app_packet.getlayer(Raw).load)
            assert app_payload[:5] == tls_app_data[:5]  # TLS头部保留
            assert all(b == 0x00 for b in app_payload[5:])  # 应用数据被掩码
    
    def test_performance_with_large_dataset(self):
        """测试大数据集的处理性能"""
        import time
        
        # 创建较大的测试数据集
        packets = []
        for i in range(100):
            payload = f"Large dataset test payload {i} " * 10  # 较长的载荷
            packet = Ether()/IP(src="1.2.3.4", dst="5.6.7.8")/TCP(sport=1234, dport=80, seq=1000+i*100)/Raw(load=payload.encode())
            packets.append(packet)
        
        # 创建掩码表
        mask_table = SequenceMaskTable()
        mask_table.add_entry(MaskEntry(
            stream_id="TCP_1.2.3.4:1234_5.6.7.8:80_forward",
            sequence_start=1000,
            sequence_end=20000,
            mask_type="mask_after",
            mask_params={"keep_bytes": 20}
        ))
        
        # 测量处理时间
        applier = MaskApplier(logger=self.logger)
        start_time = time.time()
        
        modified_packets, stats = applier.apply_masks_to_packets(packets, mask_table)
        
        processing_time = time.time() - start_time
        
        # 验证性能和结果
        assert len(modified_packets) == 100
        assert stats['packets_modified'] == 100
        assert processing_time < 5.0  # 应该在5秒内完成
        
        # 计算处理速度
        pps = len(packets) / processing_time
        assert pps > 20  # 应该能达到20+ pps
        
        print(f"处理性能: {pps:.1f} pps, 处理时间: {processing_time:.3f}s")


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"]) 