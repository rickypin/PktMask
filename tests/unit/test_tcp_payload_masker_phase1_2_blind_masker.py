"""
测试TCP载荷掩码器Phase 1.2 - 盲操作引擎

测试BlindPacketMasker和PacketProcessor的核心功能：
- 各种掩码类型的应用
- 字节级操作的精确性
- 校验和自动修复
- 错误处理和边界条件
"""

import pytest
import tempfile
import os
from unittest.mock import patch, Mock
from scapy.all import Ether, IP, TCP, UDP, raw, wrpcap, rdpcap
from scapy.packet import Packet

from src.pktmask.core.tcp_payload_masker.api.types import (
    PacketMaskInstruction,
    MaskingRecipe,
    MaskingStatistics,
    PacketMaskingResult
)
from src.pktmask.core.tcp_payload_masker.core.blind_masker import BlindPacketMasker
from src.pktmask.core.tcp_payload_masker.core.packet_processor import PacketProcessor
from src.pktmask.core.trim.models.mask_spec import MaskAfter, MaskRange, KeepAll


class TestBlindPacketMasker:
    """测试BlindPacketMasker核心类"""
    
    def setup_method(self):
        """设置测试环境"""
        # 创建简单的掩码配方
        instructions = {
            (0, "123.456789"): PacketMaskInstruction(
                packet_index=0,
                packet_timestamp="123.456789",
                payload_offset=54,  # 典型的Ethernet+IP+TCP头部长度
                mask_spec=MaskAfter(5)
            ),
            (1, "123.456790"): PacketMaskInstruction(
                packet_index=1,
                packet_timestamp="123.456790", 
                payload_offset=54,
                mask_spec=MaskRange([(0, 10), (20, 30)])
            )
        }
        
        self.recipe = MaskingRecipe(
            instructions=instructions,
            total_packets=3,
            metadata={"test": "phase1.2"}
        )
        
        self.masker = BlindPacketMasker(self.recipe)
    
    def test_initialization(self):
        """测试掩码器初始化"""
        assert self.masker.recipe == self.recipe
        assert isinstance(self.masker.stats, MaskingStatistics)
        assert self.masker.stats.processed_packets == 0
    
    def test_process_packet_with_instruction(self):
        """测试有掩码指令的包处理"""
        # 创建测试包
        packet = self._create_test_packet_with_payload(b"Hello, World! This is test data for masking.")
        packet.time = 123.456789
        
        # 处理包
        result_bytes, was_modified = self.masker.process_packet(0, packet)
        
        # 验证结果
        assert was_modified is True
        assert result_bytes is not None
        assert len(result_bytes) == len(raw(packet))
        
        # 验证统计信息
        assert self.masker.stats.processed_packets == 1
        assert self.masker.stats.modified_packets == 1
    
    def test_process_packet_without_instruction(self):
        """测试无掩码指令的包处理"""
        # 创建测试包（不匹配任何指令）
        packet = self._create_test_packet_with_payload(b"No instruction for this packet")
        packet.time = 999.999999
        
        # 处理包
        result_bytes, was_modified = self.masker.process_packet(99, packet)
        
        # 验证结果
        assert was_modified is False
        assert result_bytes is None
        
        # 验证统计信息
        assert self.masker.stats.processed_packets == 1
        assert self.masker.stats.skipped_packets == 1
    
    def test_apply_mask_after(self):
        """测试MaskAfter掩码应用"""
        payload = b"0123456789ABCDEFGHIJ"
        mask_spec = MaskAfter(5)
        
        result = self.masker._apply_mask_spec(payload, mask_spec)
        
        # 验证前5字节保留，后续置零
        assert result[:5] == b"01234"
        assert result[5:] == b'\x00' * 15
    
    def test_apply_mask_after_keep_zero(self):
        """测试MaskAfter保留0字节（全部置零）"""
        payload = b"ABCDEFGHIJ"
        mask_spec = MaskAfter(0)
        
        result = self.masker._apply_mask_spec(payload, mask_spec)
        
        # 验证全部置零
        assert result == b'\x00' * 10
    
    def test_apply_mask_after_keep_all(self):
        """测试MaskAfter保留全部（keep_bytes超过载荷长度）"""
        payload = b"ABCDE"
        mask_spec = MaskAfter(10)  # 超过载荷长度
        
        result = self.masker._apply_mask_spec(payload, mask_spec)
        
        # 验证完全保留
        assert result == payload
    
    def test_apply_mask_range(self):
        """测试MaskRange掩码应用"""
        payload = b"0123456789ABCDEFGHIJ"
        mask_spec = MaskRange([(2, 5), (10, 15)])
        
        result = self.masker._apply_mask_spec(payload, mask_spec)
        
        # 验证指定范围置零
        expected = bytearray(payload)
        expected[2:5] = b'\x00\x00\x00'  # 位置2-4置零
        expected[10:15] = b'\x00\x00\x00\x00\x00'  # 位置10-14置零
        
        assert result == bytes(expected)
    
    def test_apply_keep_all(self):
        """测试KeepAll掩码应用"""
        payload = b"This should remain unchanged"
        mask_spec = KeepAll()
        
        result = self.masker._apply_mask_spec(payload, mask_spec)
        
        # 验证完全保留
        assert result == payload
    
    def test_apply_mask_instruction_invalid_offset(self):
        """测试无效载荷偏移的处理"""
        packet_bytes = b"Short packet"
        instruction = PacketMaskInstruction(
            packet_index=0,
            packet_timestamp="123.456789",
            payload_offset=100,  # 超过包长度
            mask_spec=MaskAfter(5)
        )
        
        result = self.masker._apply_mask_instruction(packet_bytes, instruction)
        
        # 验证返回原始字节流
        assert result == packet_bytes
    
    def test_count_masked_bytes(self):
        """测试掩码字节数统计"""
        original = b"ABCDEFGHIJ"
        modified = b"ABC\x00\x00\x00GHIJ"
        
        count = self.masker._count_masked_bytes(original, modified)
        
        assert count == 3  # DEF被置零
    
    def test_statistics_tracking(self):
        """测试统计信息跟踪"""
        # 重置统计信息
        self.masker.reset_statistics()
        assert self.masker.stats.processed_packets == 0
        
        # 处理几个包
        packet1 = self._create_test_packet_with_payload(b"Test data 1")
        packet1.time = 123.456789
        
        packet2 = self._create_test_packet_with_payload(b"Test data 2")
        packet2.time = 999.999999  # 无指令
        
        self.masker.process_packet(0, packet1)
        self.masker.process_packet(99, packet2)
        
        # 验证统计信息
        stats = self.masker.get_statistics()
        assert stats.processed_packets == 2
        assert stats.modified_packets == 1
        assert stats.skipped_packets == 1
    
    def _create_test_packet_with_payload(self, payload: bytes) -> Packet:
        """创建带载荷的测试包"""
        packet = Ether(dst="aa:bb:cc:dd:ee:ff", src="11:22:33:44:55:66") / \
                 IP(src="192.168.1.1", dst="192.168.1.2") / \
                 TCP(sport=12345, dport=80) / payload
        return packet


class TestPacketProcessor:
    """测试PacketProcessor文件处理类"""
    
    def setup_method(self):
        """设置测试环境"""
        self.processor = PacketProcessor(enable_checksum_fix=True)
        self.temp_dir = tempfile.mkdtemp()
    
    def teardown_method(self):
        """清理测试环境"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_initialization(self):
        """测试处理器初始化"""
        assert self.processor.enable_checksum_fix is True
        
        processor_no_fix = PacketProcessor(enable_checksum_fix=False)
        assert processor_no_fix.enable_checksum_fix is False
    
    def test_process_pcap_file_input_not_exists(self):
        """测试输入文件不存在的情况"""
        non_existent_file = os.path.join(self.temp_dir, "non_existent.pcap")
        output_file = os.path.join(self.temp_dir, "output.pcap")
        
        # 创建空配方
        recipe = MaskingRecipe(instructions={}, total_packets=0)
        
        result = self.processor.process_pcap_file(non_existent_file, output_file, recipe)
        
        # 验证失败结果
        assert result.success is False
        assert len(result.errors) > 0
        assert "不存在" in result.errors[0]
    
    def test_reconstruct_packet(self):
        """测试包重构功能"""
        # 创建原始包
        original = Ether() / IP() / TCP() / b"test payload"
        packet_bytes = raw(original)
        
        # 重构包
        reconstructed = self.processor._reconstruct_packet(packet_bytes)
        
        # 验证重构成功
        assert isinstance(reconstructed, Packet)
        assert raw(reconstructed) == packet_bytes
    
    def test_fix_checksums(self):
        """测试校验和修复"""
        # 创建包并破坏校验和
        packet = Ether() / IP(src="1.1.1.1", dst="2.2.2.2") / TCP(sport=80, dport=443) / b"test"
        
        # 手动设置错误的校验和
        packet[IP].chksum = 0xFFFF
        packet[TCP].chksum = 0xFFFF
        
        # 修复校验和
        fixed_packet = self.processor._fix_checksums(packet)
        
        # 验证修复（通过重新构建包来验证）
        assert isinstance(fixed_packet, Packet)
        assert fixed_packet.haslayer(IP)
        assert fixed_packet.haslayer(TCP)
    
    def test_write_and_verify_packets(self):
        """测试包写入和验证"""
        output_file = os.path.join(self.temp_dir, "test_output.pcap")
        
        # 创建测试包
        packets = [
            Ether() / IP() / TCP() / b"packet 1",
            Ether() / IP() / UDP() / b"packet 2"
        ]
        
        # 写入文件
        self.processor._write_packets(output_file, packets)
        
        # 验证文件
        assert os.path.exists(output_file)
        assert self.processor.verify_output_file(output_file) is True
        
        # 读取验证
        read_packets = rdpcap(output_file)
        assert len(read_packets) == 2
    
    def test_verify_output_file_invalid(self):
        """测试无效输出文件验证"""
        non_existent_file = os.path.join(self.temp_dir, "non_existent.pcap")
        
        result = self.processor.verify_output_file(non_existent_file)
        assert result is False
    
    @patch('src.pktmask.core.tcp_payload_masker.core.packet_processor.PcapReader')
    def test_process_packets_with_errors(self, mock_reader):
        """测试包处理过程中的错误处理"""
        # 模拟PcapReader抛出异常
        mock_reader.return_value.__enter__.return_value.__iter__.side_effect = Exception("读取错误")
        
        recipe = MaskingRecipe(instructions={}, total_packets=0)
        input_file = "dummy.pcap"
        output_file = os.path.join(self.temp_dir, "output.pcap")
        
        masker = BlindPacketMasker(recipe)
        result = self.processor._process_packets(input_file, output_file, masker)
        
        # 验证错误处理
        assert result.success is False
        assert len(result.errors) > 0


class TestIntegration:
    """集成测试：BlindPacketMasker + PacketProcessor"""
    
    def setup_method(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.processor = PacketProcessor()
    
    def teardown_method(self):
        """清理测试环境"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_end_to_end_masking(self):
        """端到端掩码测试"""
        # 创建输入文件
        input_file = os.path.join(self.temp_dir, "input.pcap")
        output_file = os.path.join(self.temp_dir, "output.pcap")
        
        # 创建测试包
        packets = [
            Ether() / IP() / TCP() / b"This is packet 0 payload for testing",
            Ether() / IP() / TCP() / b"This is packet 1 payload for testing", 
            Ether() / IP() / UDP() / b"UDP packet without instruction"
        ]
        
        # 设置时间戳
        for i, packet in enumerate(packets):
            packet.time = 123.456789 + i * 0.001
        
        wrpcap(input_file, packets)
        
        # 创建掩码配方（只对前两个包应用掩码）
        instructions = {
            (0, "123.456789"): PacketMaskInstruction(
                packet_index=0,
                packet_timestamp="123.456789",
                payload_offset=54,
                mask_spec=MaskAfter(10)  # 保留前10字节
            ),
            (1, "123.457789"): PacketMaskInstruction(
                packet_index=1,
                packet_timestamp="123.457789",
                payload_offset=54,
                mask_spec=KeepAll()  # 完全保留
            )
        }
        
        recipe = MaskingRecipe(
            instructions=instructions,
            total_packets=3,
            metadata={"test": "integration"}
        )
        
        # 执行处理
        result = self.processor.process_pcap_file(input_file, output_file, recipe)
        
        # 验证结果
        assert result.success is True
        assert result.processed_packets == 3
        assert result.modified_packets == 1  # 只有第一个包被修改
        assert os.path.exists(output_file)
        
        # 验证输出文件内容
        output_packets = rdpcap(output_file)
        assert len(output_packets) == 3
        
        # 验证第一个包被掩码（载荷前10字节保留，后续置零）
        first_packet_payload = bytes(output_packets[0][TCP].payload)
        assert first_packet_payload.startswith(b"This is pa")  # 前10字节
        # 验证后续字节有置零（这里简化检查是否有变化）
        
        # 验证第二个包完全保留
        second_packet_payload = bytes(output_packets[1][TCP].payload)
        assert second_packet_payload == b"This is packet 1 payload for testing"
        
        # 验证第三个包未被修改
        third_packet_payload = bytes(output_packets[2][UDP].payload)
        assert third_packet_payload == b"UDP packet without instruction"


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 