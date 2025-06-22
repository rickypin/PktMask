"""
Phase 3: 文件I/O和一致性保证测试

测试文件格式处理器和一致性验证器的功能。
"""

import unittest
import tempfile
import os
import logging
from typing import List, Tuple
from pathlib import Path

# 设置测试路径
import sys
test_dir = Path(__file__).parent.parent
src_dir = test_dir.parent / "src"
sys.path.insert(0, str(src_dir))

try:
    from scapy.all import Packet, Ether, IP, TCP, Raw, wrpcap, rdpcap
except ImportError:
    import pytest
    pytest.skip("Scapy not available", allow_module_level=True)

from pktmask.core.independent_pcap_masker.core import (
    PcapFileHandler,
    ConsistencyVerifier
)
from pktmask.core.independent_pcap_masker.exceptions import (
    FileConsistencyError,
    ValidationError
)


class TestPcapFileHandler(unittest.TestCase):
    """测试PCAP文件格式处理器"""
    
    def setUp(self):
        """设置测试环境"""
        self.logger = logging.getLogger(__name__)
        self.handler = PcapFileHandler(self.logger)
        
        # 创建临时目录
        self.temp_dir = tempfile.mkdtemp()
        
        # 创建测试数据包
        self.test_packets = self._create_test_packets()
        
        # 创建测试PCAP文件
        self.test_pcap_path = os.path.join(self.temp_dir, "test.pcap")
        wrpcap(self.test_pcap_path, self.test_packets)
    
    def tearDown(self):
        """清理测试环境"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def _create_test_packets(self) -> List[Packet]:
        """创建测试数据包"""
        packets = []
        
        # 创建简单的TCP数据包
        for i in range(5):
            packet = Ether(dst="00:11:22:33:44:55", src="aa:bb:cc:dd:ee:ff") / \
                    IP(src="192.168.1.100", dst="192.168.1.200") / \
                    TCP(sport=1234, dport=80, seq=1000 + i * 100) / \
                    Raw(load=f"Test data packet {i}".encode())
            packets.append(packet)
        
        return packets
    
    def test_validate_file_format_pcap(self):
        """测试PCAP格式验证"""
        # 测试有效的PCAP文件
        self.assertTrue(self.handler.validate_file_format(self.test_pcap_path))
        
        # 测试不存在的文件
        invalid_path = os.path.join(self.temp_dir, "nonexistent.pcap")
        self.assertFalse(self.handler.validate_file_format(invalid_path))
        
        # 测试不支持的格式
        text_file = os.path.join(self.temp_dir, "test.txt")
        with open(text_file, 'w') as f:
            f.write("This is not a PCAP file")
        self.assertFalse(self.handler.validate_file_format(text_file))
    
    def test_read_packets(self):
        """测试数据包读取"""
        # 读取数据包
        packets = self.handler.read_packets(self.test_pcap_path)
        
        # 验证数据包数量
        self.assertEqual(len(packets), len(self.test_packets))
        
        # 验证数据包类型
        for packet in packets:
            self.assertIsInstance(packet, Packet)
        
        # 验证读取不存在的文件时抛出异常
        invalid_path = os.path.join(self.temp_dir, "nonexistent.pcap")
        with self.assertRaises(ValidationError):
            self.handler.read_packets(invalid_path)
    
    def test_write_packets(self):
        """测试数据包写入"""
        output_path = os.path.join(self.temp_dir, "output.pcap")
        
        # 写入数据包
        self.handler.write_packets(self.test_packets, output_path)
        
        # 验证文件创建
        self.assertTrue(os.path.exists(output_path))
        
        # 验证文件格式
        self.assertTrue(self.handler.validate_file_format(output_path))
        
        # 读取写入的数据包并验证
        written_packets = self.handler.read_packets(output_path)
        self.assertEqual(len(written_packets), len(self.test_packets))
    
    def test_write_empty_packets(self):
        """测试写入空数据包列表"""
        output_path = os.path.join(self.temp_dir, "empty.pcap")
        
        with self.assertRaises(ValidationError):
            self.handler.write_packets([], output_path)
    
    def test_copy_packet_metadata(self):
        """测试数据包元数据复制"""
        source = self.test_packets[0]
        target = self.test_packets[1]
        
        # 设置源数据包的时间戳
        source.time = 1234567890.123456
        
        # 复制元数据
        result = self.handler.copy_packet_metadata(source, target)
        
        # 验证时间戳被复制
        self.assertEqual(result.time, source.time)
        self.assertIsInstance(result, Packet)
    
    def test_get_file_stats(self):
        """测试文件统计信息获取"""
        stats = self.handler.get_file_stats(self.test_pcap_path)
        
        # 验证统计信息包含必要字段
        required_fields = [
            'file_path', 'file_size', 'file_format', 
            'packet_count', 'readable', 'writable'
        ]
        
        for field in required_fields:
            self.assertIn(field, stats)
        
        # 验证数据包数量正确
        self.assertEqual(stats['packet_count'], len(self.test_packets))
        
        # 验证文件格式
        self.assertEqual(stats['file_format'], '.pcap')
    
    def test_create_backup(self):
        """测试备份文件创建"""
        backup_path = self.handler.create_backup(self.test_pcap_path)
        
        # 验证备份文件创建
        self.assertIsNotNone(backup_path)
        self.assertTrue(os.path.exists(backup_path))
        
        # 验证备份文件内容
        original_size = os.path.getsize(self.test_pcap_path)
        backup_size = os.path.getsize(backup_path)
        self.assertEqual(original_size, backup_size)


class TestConsistencyVerifier(unittest.TestCase):
    """测试一致性验证器"""
    
    def setUp(self):
        """设置测试环境"""
        self.logger = logging.getLogger(__name__)
        self.verifier = ConsistencyVerifier(self.logger)
        
        # 创建临时目录
        self.temp_dir = tempfile.mkdtemp()
        
        # 创建测试数据包
        self.test_packets = self._create_test_packets()
        
        # 创建原始文件
        self.original_path = os.path.join(self.temp_dir, "original.pcap")
        wrpcap(self.original_path, self.test_packets)
        
        # 创建相同内容的修改文件（模拟无修改的情况）
        self.modified_path = os.path.join(self.temp_dir, "modified.pcap")
        wrpcap(self.modified_path, self.test_packets)
    
    def tearDown(self):
        """清理测试环境"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def _create_test_packets(self) -> List[Packet]:
        """创建测试数据包"""
        packets = []
        
        for i in range(3):
            packet = Ether(dst="00:11:22:33:44:55", src="aa:bb:cc:dd:ee:ff") / \
                    IP(src="192.168.1.100", dst="192.168.1.200") / \
                    TCP(sport=1234, dport=80, seq=1000 + i * 100) / \
                    Raw(load=f"Test data {i}".encode())
            packet.time = 1234567890.0 + i * 0.1  # 设置时间戳
            packets.append(packet)
        
        return packets
    
    def test_verify_file_consistency_identical(self):
        """测试验证相同文件的一致性"""
        # 验证相同文件应该通过
        result = self.verifier.verify_file_consistency(
            self.original_path, 
            self.modified_path
        )
        
        self.assertTrue(result)
        
        # 检查统计信息
        stats = self.verifier.get_last_verification_stats()
        self.assertEqual(stats['original_packet_count'], len(self.test_packets))
        self.assertEqual(stats['modified_packet_count'], len(self.test_packets))
        self.assertTrue(stats['packet_count_consistent'])
    
    def test_verify_file_consistency_nonexistent(self):
        """测试验证不存在文件的情况"""
        invalid_path = os.path.join(self.temp_dir, "nonexistent.pcap")
        
        with self.assertRaises(FileConsistencyError):
            self.verifier.verify_file_consistency(
                self.original_path,
                invalid_path
            )
    
    def test_compare_packet_metadata(self):
        """测试数据包元数据比较"""
        original = self.test_packets[0]
        modified = self.test_packets[0]  # 相同的包
        
        # 比较相同的包应该通过
        result = self.verifier.compare_packet_metadata(original, modified, 0)
        self.assertTrue(result)
        
        # 创建不同大小的包
        different_packet = Ether() / IP() / TCP() / Raw(load=b"Different size payload")
        result = self.verifier.compare_packet_metadata(
            original, different_packet, 0
        )
        self.assertFalse(result)
    
    def test_calculate_file_hash(self):
        """测试文件哈希计算"""
        # 计算原始文件哈希
        hash1 = self.verifier.calculate_file_hash(self.original_path)
        hash2 = self.verifier.calculate_file_hash(self.modified_path)
        
        # 相同文件应该有相同的哈希
        self.assertEqual(hash1, hash2)
        self.assertIsInstance(hash1, str)
        self.assertEqual(len(hash1), 64)  # SHA256哈希长度
    
    def test_calculate_file_hash_with_exclusions(self):
        """测试带排除范围的文件哈希计算"""
        # 排除某些字节范围计算哈希
        exclude_ranges = [(100, 200), (300, 400)]
        
        hash_with_exclusions = self.verifier.calculate_file_hash(
            self.original_path, 
            exclude_ranges
        )
        
        # 应该返回有效的哈希
        self.assertIsInstance(hash_with_exclusions, str)
        self.assertEqual(len(hash_with_exclusions), 64)
    
    def test_verify_with_mask_ranges(self):
        """测试带掩码范围的验证"""
        # 模拟已应用掩码的范围
        mask_ranges = [
            (0, 100, 150),  # 包0，字节100-150
            (1, 200, 250),  # 包1，字节200-250
        ]
        
        # 验证时考虑掩码范围
        result = self.verifier.verify_file_consistency(
            self.original_path,
            self.modified_path,
            mask_ranges
        )
        
        self.assertTrue(result)
        
        # 检查统计信息包含掩码信息
        stats = self.verifier.get_last_verification_stats()
        self.assertEqual(stats['mask_ranges_count'], len(mask_ranges))
        self.assertEqual(stats['affected_packets'], 2)


class TestFileIOIntegration(unittest.TestCase):
    """测试文件I/O集成功能"""
    
    def setUp(self):
        """设置测试环境"""
        self.logger = logging.getLogger(__name__)
        self.handler = PcapFileHandler(self.logger)
        self.verifier = ConsistencyVerifier(self.logger)
        
        # 创建临时目录
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """清理测试环境"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_roundtrip_consistency(self):
        """测试读写往返一致性"""
        # 创建原始数据包
        original_packets = [
            Ether() / IP(src="1.1.1.1", dst="2.2.2.2") / TCP() / Raw(load=b"Test data 1"),
            Ether() / IP(src="3.3.3.3", dst="4.4.4.4") / TCP() / Raw(load=b"Test data 2"),
        ]
        
        # 写入原始文件
        original_path = os.path.join(self.temp_dir, "original.pcap")
        self.handler.write_packets(original_packets, original_path)
        
        # 读取数据包
        read_packets = self.handler.read_packets(original_path)
        
        # 写入到新文件
        roundtrip_path = os.path.join(self.temp_dir, "roundtrip.pcap")
        self.handler.write_packets(read_packets, roundtrip_path)
        
        # 验证一致性
        consistency_result = self.verifier.verify_file_consistency(
            original_path, 
            roundtrip_path
        )
        
        self.assertTrue(consistency_result)
    
    def test_multiple_format_support(self):
        """测试多种格式支持"""
        # 创建测试数据包
        test_packets = [
            Ether() / IP() / TCP() / Raw(load=b"Format test"),
        ]
        
        # 测试PCAP格式
        pcap_path = os.path.join(self.temp_dir, "test.pcap")
        self.handler.write_packets(test_packets, pcap_path)
        self.assertTrue(self.handler.validate_file_format(pcap_path))
        
        # 验证读取
        read_packets = self.handler.read_packets(pcap_path)
        self.assertEqual(len(read_packets), len(test_packets))


if __name__ == '__main__':
    # 配置日志
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 运行测试
    unittest.main(verbosity=2) 