#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Phase 2.3 Scapy回写器集成测试

测试Scapy回写器与整个系统的集成，包括：
- 与TShark预处理器的数据流对接
- 与PyShark分析器的掩码表集成
- 实际PCAP文件的处理
- 掩码应用的正确性验证
"""

import unittest
import tempfile
import shutil
from pathlib import Path
import struct
import time

# 导入被测试的模块
from src.pktmask.core.trim.stages.tcp_payload_masker_adapter import TcpPayloadMaskerAdapter
from src.pktmask.core.trim.stages.base_stage import StageContext
from src.pktmask.core.trim.models.mask_table import StreamMaskTable
from src.pktmask.core.trim.models.mask_spec import MaskAfter, MaskRange, KeepAll


class TestPhase2_3Integration(unittest.TestCase):
    """Phase 2.3 Scapy回写器集成测试"""
    
    def setUp(self):
        """测试前置设置"""
        self.temp_dir = Path(tempfile.mkdtemp())
        
        # 创建测试文件
        self.input_file = self.temp_dir / "input.pcap"
        self.output_file = self.temp_dir / "output.pcap"
        
        # 创建一个最小的PCAP文件结构
        self._create_minimal_pcap_file()
        
        # 创建测试上下文
        self.context = StageContext(
            input_file=self.input_file,
            output_file=self.output_file,
            work_dir=self.temp_dir
        )
        self.context.tshark_output = str(self.input_file)
        
        # 创建Scapy回写器
        self.config = {
            'preserve_timestamps': True,
            'recalculate_checksums': True,
            'mask_byte_value': 0x00
        }
        self.rewriter = TcpPayloadMaskerAdapter(self.config)
    
    def tearDown(self):
        """测试后置清理"""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def _create_minimal_pcap_file(self):
        """创建一个最小的PCAP文件用于测试"""
        # 创建简单的PCAP全局头
        pcap_header = struct.pack('<LHHLLLL', 
            0xa1b2c3d4,  # magic number
            2,           # version major
            4,           # version minor  
            0,           # thiszone
            0,           # sigfigs
            65535,       # snaplen
            1            # network (Ethernet)
        )
        
        # 创建一个简单的数据包记录 (最小以太网帧)
        timestamp = int(time.time())
        packet_data = b'\x00' * 60  # 最小以太网帧
        
        packet_header = struct.pack('<LLLL',
            timestamp,        # ts_sec
            0,               # ts_usec
            len(packet_data), # incl_len
            len(packet_data)  # orig_len
        )
        
        # 写入PCAP文件
        with open(self.input_file, 'wb') as f:
            f.write(pcap_header)
            f.write(packet_header)
            f.write(packet_data)
    
    def test_scapy_availability(self):
        """测试Scapy是否可用"""
        try:
            from scapy.all import rdpcap, wrpcap
            self.assertTrue(True, "Scapy可用")
        except ImportError:
            self.skipTest("Scapy未安装")
    
    def test_initialization(self):
        """测试ScapyRewriter初始化"""
        self.assertEqual(self.rewriter.name, "TcpPayloadMaskerAdapter")
        self.assertFalse(self.rewriter.is_initialized)
        
        # 初始化
        success = self.rewriter.initialize()
        if success:
            self.assertTrue(self.rewriter.is_initialized)
        else:
            self.skipTest("Scapy不可用，跳过测试")
    
    def test_input_validation(self):
        """测试输入验证"""
        # 初始化回写器
        if not self.rewriter.initialize():
            self.skipTest("Scapy不可用，跳过测试")
        
        # 测试缺少掩码表的情况
        self.context.mask_table = None
        self.assertFalse(self.rewriter.validate_inputs(self.context))
        
        # 测试有效输入
        mask_table = StreamMaskTable()
        mask_table.finalize()
        self.context.mask_table = mask_table
        self.assertTrue(self.rewriter.validate_inputs(self.context))
    
    def test_empty_mask_table_processing(self):
        """测试空掩码表的处理"""
        if not self.rewriter.initialize():
            self.skipTest("Scapy不可用，跳过测试")
        
        # 创建空掩码表
        mask_table = StreamMaskTable()
        mask_table.finalize()
        self.context.mask_table = mask_table
        
        # 执行处理
        result = self.rewriter.execute(self.context)
        
        # 验证结果
        self.assertTrue(result.success)
        self.assertEqual(result.data['packets_modified'], 0)
        self.assertTrue(self.output_file.exists())
    
    def test_mask_table_integration(self):
        """测试掩码表集成"""
        if not self.rewriter.initialize():
            self.skipTest("Scapy不可用，跳过测试")
        
        # 创建包含掩码的掩码表
        mask_table = StreamMaskTable()
        
        # 添加一些测试掩码
        mask_table.add_mask_range("192.168.1.1:80-192.168.1.2:8080/TCP", 
                                  1000, 1050, MaskAfter(20))
        mask_table.add_mask_range("192.168.1.1:53-192.168.1.2:5353/UDP",
                                  0, 100, MaskRange([(10, 50)]))
        mask_table.finalize()
        
        self.context.mask_table = mask_table
        
        # 执行处理
        result = self.rewriter.execute(self.context)
        
        # 验证结果
        self.assertTrue(result.success)
        self.assertGreaterEqual(result.data['total_packets'], 0)
        self.assertTrue(self.output_file.exists())
        
        # 验证统计信息
        self.assertIn('processing_time', result.data)
        self.assertIn('processing_rate', result.data)
    
    def test_tool_availability_check(self):
        """测试工具可用性检查"""
        availability = self.rewriter.check_tool_availability()
        self.assertIn('scapy', availability)
        
        # 如果Scapy可用，测试其他方法
        if availability['scapy']:
            self.assertEqual(self.rewriter.get_required_tools(), ['scapy'])
            self.assertIn("Scapy", self.rewriter.get_description())
    
    def test_configuration_options(self):
        """测试配置选项"""
        # 测试不同配置
        configs = [
            {'preserve_timestamps': False, 'mask_byte_value': 0xFF},
            {'recalculate_checksums': False, 'batch_size': 50},
            {}  # 默认配置
        ]
        
        for config in configs:
            rewriter = TcpPayloadMaskerAdapter(config)
            self.assertEqual(rewriter.name, "TcpPayloadMaskerAdapter")
            
            # 验证配置应用
            for key, value in config.items():
                self.assertEqual(rewriter.get_config_value(key, None), value)
    
    def test_processing_statistics(self):
        """测试处理统计信息"""
        if not self.rewriter.initialize():
            self.skipTest("Scapy不可用，跳过测试")
        
        # 创建掩码表
        mask_table = StreamMaskTable()
        mask_table.finalize()
        self.context.mask_table = mask_table
        
        # 执行处理
        result = self.rewriter.execute(self.context)
        
        if result.success:
            # 验证统计信息结构
            required_stats = [
                'total_packets', 'packets_modified', 'bytes_masked',
                'checksums_updated', 'processing_time', 'processing_rate'
            ]
            
            for stat in required_stats:
                self.assertIn(stat, result.data)
                self.assertIsInstance(result.data[stat], (int, float))
    
    def test_error_handling(self):
        """测试错误处理"""
        if not self.rewriter.initialize():
            self.skipTest("Scapy不可用，跳过测试")
        
        # 测试无效输入文件
        self.context.tshark_output = str(self.temp_dir / "nonexistent.pcap")
        self.assertFalse(self.rewriter.validate_inputs(self.context))
        
        # 测试无效掩码表
        self.context.tshark_output = str(self.input_file)
        self.context.mask_table = None
        result = self.rewriter.execute(self.context)
        self.assertFalse(result.success)
        self.assertIn("失败", result.error)
    
    def test_cleanup_functionality(self):
        """测试清理功能"""
        if not self.rewriter.initialize():
            self.skipTest("Scapy不可用，跳过测试")
        
        # 执行清理
        self.rewriter.cleanup(self.context)
        
        # 验证内部状态被清理
        self.assertIsNone(self.rewriter._mask_table)
        self.assertEqual(len(self.rewriter._rewrite_info), 0)
        self.assertEqual(len(self.rewriter._stream_stats), 0)
    
    def test_duration_estimation(self):
        """测试时间估算"""
        # 测试不同大小的文件
        duration = self.rewriter.get_estimated_duration(self.context)
        self.assertGreater(duration, 0)
        self.assertIsInstance(duration, float)
        
        # 测试大文件估算
        large_file = self.temp_dir / "large.pcap"
        large_file.write_bytes(b'x' * (5 * 1024 * 1024))  # 5MB
        self.context.tshark_output = str(large_file)
        
        large_duration = self.rewriter.get_estimated_duration(self.context)
        self.assertGreater(large_duration, duration)


if __name__ == '__main__':
    unittest.main() 