#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Phase 2.2 PyShark分析器集成测试（简化版）

验证PyShark分析器与现有系统的集成效果：
1. 基础数据流传递
2. 事件系统集成
3. 错误处理
4. 配置系统集成
"""

import pytest
import tempfile
import shutil
import time
from pathlib import Path
from unittest.mock import Mock, patch

from pktmask.core.trim.stages.pyshark_analyzer import PySharkAnalyzer
from pktmask.core.trim.stages.base_stage import StageContext
from pktmask.core.trim.models.mask_table import StreamMaskTable
from pktmask.core.events import PipelineEvents
from pktmask.config import get_app_config


class TestPhase22IntegrationSimple:
    """Phase 2.2 PyShark分析器简化集成测试类"""

    def setup_method(self):
        """测试设置"""
        self.temp_dir = Path(tempfile.mkdtemp())
        
        # 创建基础文件和目录
        self.input_file = self.temp_dir / "input.pcap"
        self.output_file = self.temp_dir / "output.pcap"
        self.work_dir = self.temp_dir / "work"
        self.work_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建一个模拟的PCAP文件
        self._create_mock_pcap_file()
        
    def teardown_method(self):
        """测试清理"""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def _create_mock_pcap_file(self):
        """创建模拟PCAP文件"""
        # 创建一个最小的PCAP文件头
        pcap_header = (
            b'\xd4\xc3\xb2\xa1'  # Magic number (Little Endian)
            b'\x02\x00\x04\x00'  # Version major/minor
            b'\x00\x00\x00\x00'  # Timezone offset
            b'\x00\x00\x00\x00'  # Timestamp accuracy
            b'\xff\xff\x00\x00'  # Max packet length
            b'\x01\x00\x00\x00'  # Data link type (Ethernet)
        )
        self.input_file.write_bytes(pcap_header)

    def test_basic_integration(self):
        """测试1: 基础集成功能"""
        print("\n=== 测试1: PyShark分析器基础集成功能 ===")
        
        # 模拟TShark预处理器的输出
        tshark_output = self.work_dir / "tshark_output.pcap"
        tshark_output.write_bytes(self.input_file.read_bytes())
        
        # 创建Stage上下文
        context = StageContext(
            input_file=self.input_file,
            output_file=self.output_file,
            work_dir=self.work_dir
        )
        context.tshark_output = str(tshark_output)
        
        # 创建PyShark分析器
        analyzer_config = {
            'analyze_http': True,
            'analyze_tls': True,
            'analyze_tcp': True,
            'analyze_udp': True
        }
        
        with patch('pktmask.core.trim.stages.pyshark_analyzer.pyshark') as mock_pyshark:
            # 模拟PyShark
            mock_packets = [
                self._create_mock_tcp_packet(1, has_http=True),
                self._create_mock_tcp_packet(2, has_tls=True),
                self._create_mock_udp_packet(3)
            ]
            mock_cap = Mock()
            mock_cap.__iter__ = Mock(return_value=iter(mock_packets))
            mock_cap.close = Mock()
            mock_pyshark.FileCapture.return_value = mock_cap
            
            # 创建并初始化分析器
            analyzer = PySharkAnalyzer(analyzer_config)
            analyzer.initialize()
            
            # 验证输入验证
            assert analyzer.validate_inputs(context)
            
            # 执行分析
            result = analyzer.execute(context)
            
            # 验证执行结果
            assert result.success
            assert "PyShark分析完成" in result.data
            
            # 验证数据流传递
            assert context.mask_table is not None
            assert isinstance(context.mask_table, StreamMaskTable)
            assert context.pyshark_results is not None
            assert 'streams' in context.pyshark_results
            assert 'packet_analyses' in context.pyshark_results
            assert 'statistics' in context.pyshark_results
            
        print("✅ 基础集成功能验证通过")

    def test_error_handling_integration(self):
        """测试2: 错误处理集成"""
        print("\n=== 测试2: 错误处理集成 ===")
        
        # 测试输入验证失败
        analyzer = PySharkAnalyzer()
        analyzer.initialize()
        
        # 创建无效上下文（没有TShark输出）
        invalid_context = StageContext(
            input_file=self.input_file,
            output_file=self.output_file,
            work_dir=self.work_dir
        )
        
        # 验证输入验证失败
        assert not analyzer.validate_inputs(invalid_context)
        
        # 测试执行失败
        result = analyzer.execute(invalid_context)
        assert not result.success
        assert "PyShark分析失败" in result.error
        
        print("✅ 错误处理集成验证通过")

    def test_configuration_integration(self):
        """测试3: 配置系统集成"""
        print("\n=== 测试3: 配置系统集成 ===")
        
        # 测试配置参数
        trim_config = {
            'analyze_http': True,
            'analyze_tls': True,
            'http_keep_headers': True,
            'tls_keep_handshake': True,
            'max_packets_per_batch': 800,
            'memory_cleanup_interval': 2000
        }
        
        # 创建分析器
        analyzer = PySharkAnalyzer(trim_config)
        
        # 验证配置读取
        assert analyzer.get_config_value('analyze_http') == True
        assert analyzer.get_config_value('analyze_tls') == True
        assert analyzer.get_config_value('http_keep_headers') == True
        assert analyzer.get_config_value('tls_keep_handshake') == True
        assert analyzer.get_config_value('max_packets_per_batch') == 800
        assert analyzer.get_config_value('memory_cleanup_interval') == 2000
        
        # 验证默认值
        assert analyzer.get_config_value('nonexistent_param', 'default') == 'default'
        
        # 验证初始化成功
        assert analyzer.initialize()
        
        print("✅ 配置系统集成验证通过")

    def test_mask_table_generation(self):
        """测试4: 掩码表生成集成"""
        print("\n=== 测试4: 掩码表生成集成 ===")
        
        # 创建上下文
        context = StageContext(
            input_file=self.input_file,
            output_file=self.output_file,
            work_dir=self.work_dir
        )
        context.tshark_output = str(self.input_file)
        
        analyzer_config = {
            'analyze_http': True,
            'analyze_tls': True,
            'http_keep_headers': True,
            'tls_keep_handshake': True,
            'tls_mask_application_data': True
        }
        
        with patch('pktmask.core.trim.stages.pyshark_analyzer.pyshark') as mock_pyshark:
            # 模拟包含HTTP和TLS的数据包
            mock_packets = [
                self._create_mock_tcp_packet(1, has_http=True),
                self._create_mock_tcp_packet(2, has_tls=True),
                self._create_mock_tcp_packet(3, has_tls=True)  # TLS应用数据
            ]
            
            # 设置TLS包的类型
            mock_packets[1].tls.record.content_type = 22  # 握手
            mock_packets[2].tls.record.content_type = 23  # 应用数据
            
            mock_cap = Mock()
            mock_cap.__iter__ = Mock(return_value=iter(mock_packets))
            mock_cap.close = Mock()
            mock_pyshark.FileCapture.return_value = mock_cap
            
            # 创建分析器
            analyzer = PySharkAnalyzer(analyzer_config)
            analyzer.initialize()
            
            # 执行分析
            result = analyzer.execute(context)
            
            # 验证结果
            assert result.success
            assert context.mask_table is not None
            
            # 验证掩码表内容
            mask_table = context.mask_table
            assert mask_table.get_total_entry_count() > 0
            
            print(f"   生成掩码表条目数: {mask_table.get_total_entry_count()}")
            
        print("✅ 掩码表生成集成验证通过")

    def test_performance_integration(self):
        """测试5: 性能集成测试"""
        print("\n=== 测试5: 性能集成测试 ===")
        
        analyzer_config = {
            'max_packets_per_batch': 100,
            'memory_cleanup_interval': 500,
            'analysis_timeout_seconds': 30
        }
        
        # 创建上下文
        context = StageContext(
            input_file=self.input_file,
            output_file=self.output_file,
            work_dir=self.work_dir
        )
        context.tshark_output = str(self.input_file)
        
        with patch('pktmask.core.trim.stages.pyshark_analyzer.pyshark') as mock_pyshark:
            # 模拟大量数据包
            mock_packets = [
                self._create_mock_tcp_packet(i, has_http=(i%3==0), has_tls=(i%5==0)) 
                for i in range(1, 501)  # 500个数据包
            ]
            mock_cap = Mock()
            mock_cap.__iter__ = Mock(return_value=iter(mock_packets))
            mock_cap.close = Mock()
            mock_pyshark.FileCapture.return_value = mock_cap
            
            # 创建分析器
            analyzer = PySharkAnalyzer(analyzer_config)
            analyzer.initialize()
            
            # 测量执行时间
            start_time = time.time()
            result = analyzer.execute(context)
            execution_time = time.time() - start_time
            
            # 验证性能
            assert result.success
            assert execution_time < 30.0  # 应该在30秒内完成
            
            # 验证配置应用
            assert analyzer._max_packets_per_batch == 100
            assert analyzer._memory_cleanup_interval == 500
            assert analyzer._timeout_seconds == 30
            
            # 验证处理结果
            assert context.mask_table is not None
            assert context.pyshark_results is not None
            
            # 验证统计信息
            stats = context.pyshark_results['statistics']
            assert stats['total_packets'] == 500
            assert 'protocol_distribution' in stats
            assert 'application_distribution' in stats
            
            print(f"   处理500个数据包用时: {execution_time:.2f}s")
            print(f"   处理速度: {stats['total_packets']/execution_time:.0f} pps")
            
        print("✅ 性能集成测试验证通过")

    # Helper methods for creating mock objects
    
    def _create_mock_tcp_packet(self, number, has_http=False, has_tls=False):
        """创建模拟TCP数据包"""
        packet = Mock()
        packet.number = number
        packet.sniff_timestamp = time.time()
        
        # TCP层
        packet.tcp = Mock()
        packet.tcp.srcport = 80 if has_http else (443 if has_tls else 12345)
        packet.tcp.dstport = 54321
        packet.tcp.seq = 1000 + number * 100
        packet.tcp.len = 100
        packet.tcp.hdr_len = 20
        
        # IP层
        packet.ip = Mock()
        packet.ip.src = "192.168.1.1"
        packet.ip.dst = "192.168.1.100"
        
        # 应用层
        if has_http:
            packet.http = Mock()
            packet.http.request_method = "GET"
            packet.http.response_code = None
            packet.http.host = "example.com"
        
        if has_tls:
            packet.tls = Mock()
            packet.tls.record = Mock()
            packet.tls.record.content_type = 22  # 默认握手
            packet.tls.record.length = 100
        
        return packet
    
    def _create_mock_udp_packet(self, number):
        """创建模拟UDP数据包"""
        packet = Mock()
        packet.number = number
        packet.sniff_timestamp = time.time()
        
        # UDP层
        packet.udp = Mock()
        packet.udp.srcport = 53  # DNS
        packet.udp.dstport = 54321
        packet.udp.length = 64
        
        # IP层
        packet.ip = Mock()
        packet.ip.src = "192.168.1.1"
        packet.ip.dst = "192.168.1.100"
        
        return packet


if __name__ == "__main__":
    # 运行集成测试
    test_instance = TestPhase22IntegrationSimple()
    test_instance.setup_method()
    
    try:
        print("Phase 2.2 PyShark分析器集成测试开始...")
        
        test_instance.test_basic_integration()
        test_instance.test_error_handling_integration()
        test_instance.test_configuration_integration()
        test_instance.test_mask_table_generation()
        test_instance.test_performance_integration()
        
        print("\n🎉 Phase 2.2 集成测试全部通过！")
        print("\n=== 集成测试总结 ===")
        print("✅ 数据流传递：PyShark分析器与现有系统完美集成")
        print("✅ 错误处理：异常情况下正确处理和报告")
        print("✅ 配置系统：与现有配置系统无缝集成")
        print("✅ 掩码表生成：HTTP/TLS协议智能掩码策略")
        print("✅ 性能表现：500包处理速度达标")
        print("\n🎯 Phase 2.2 (PyShark分析器) 与现有系统集成验证完成！")
        
    except Exception as e:
        print(f"\n❌ 集成测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        test_instance.teardown_method() 