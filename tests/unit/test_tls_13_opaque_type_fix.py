"""
测试TLS 1.3 opaque_type字段兼容性修复

验证TSharkTLSAnalyzer能够正确处理TLS 1.3的opaque_type字段和其他版本的content_type字段。
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import json
from pathlib import Path

from src.pktmask.core.processors.tshark_tls_analyzer import TSharkTLSAnalyzer
from src.pktmask.core.trim.models.tls_models import TLSRecordInfo


class TestTLS13OpaqueTypeFix(unittest.TestCase):
    """测试TLS 1.3 opaque_type字段兼容性修复"""
    
    def setUp(self):
        """测试初始化"""
        self.analyzer = TSharkTLSAnalyzer({'verbose': True})
        
    def test_tls_13_opaque_type_parsing(self):
        """测试TLS 1.3 opaque_type字段解析"""
        # 模拟TLS 1.3包的TShark JSON输出 - 使用opaque_type字段
        mock_packet_tls13 = {
            "_source": {
                "layers": {
                    "frame.number": ["100"],
                    "tcp.stream": ["5"],
                    "tcp.seq": ["1000"],
                    "tls.record.opaque_type": ["23"],  # TLS 1.3使用opaque_type
                    "tls.record.length": ["256"],
                    "tls.record.version": ["0x0304"]  # TLS 1.3版本
                }
            }
        }
        
        # 测试解析
        records = self.analyzer._parse_packet_tls_records(mock_packet_tls13)
        
        # 验证结果
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record.content_type, 23)
        self.assertEqual(record.packet_number, 100)
        self.assertEqual(record.length, 256)
        self.assertEqual(record.version, (3, 4))  # TLS 1.3
        
    def test_tls_12_content_type_parsing(self):
        """测试TLS 1.2 content_type字段解析"""
        # 模拟TLS 1.2包的TShark JSON输出 - 使用content_type字段
        mock_packet_tls12 = {
            "_source": {
                "layers": {
                    "frame.number": ["101"],
                    "tcp.stream": ["6"],
                    "tcp.seq": ["2000"],
                    "tls.record.content_type": ["23"],  # TLS 1.2使用content_type
                    "tls.record.length": ["512"],
                    "tls.record.version": ["0x0303"]  # TLS 1.2版本
                }
            }
        }
        
        # 测试解析
        records = self.analyzer._parse_packet_tls_records(mock_packet_tls12)
        
        # 验证结果
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record.content_type, 23)
        self.assertEqual(record.packet_number, 101)
        self.assertEqual(record.length, 512)
        self.assertEqual(record.version, (3, 3))  # TLS 1.2
        
    def test_tls_13_priority_over_content_type(self):
        """测试TLS 1.3中opaque_type优先于content_type"""
        # 模拟同时包含两个字段的包 - opaque_type应该优先
        mock_packet_both = {
            "_source": {
                "layers": {
                    "frame.number": ["102"],
                    "tcp.stream": ["7"],
                    "tcp.seq": ["3000"],
                    "tls.record.content_type": ["22"],  # Handshake
                    "tls.record.opaque_type": ["23"],   # ApplicationData (应该优先)
                    "tls.record.length": ["128"],
                    "tls.record.version": ["0x0304"]  # TLS 1.3
                }
            }
        }
        
        # 测试解析
        records = self.analyzer._parse_packet_tls_records(mock_packet_both)
        
        # 验证opaque_type优先被使用
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record.content_type, 23)  # 应该是opaque_type的值23，而不是content_type的值22
        
    def test_mixed_tls_versions_in_stream(self):
        """测试混合TLS版本在同一流中的处理"""
        # 模拟包含TLS 1.2和TLS 1.3记录的包
        mock_packet_mixed = {
            "_source": {
                "layers": {
                    "frame.number": ["103"],
                    "tcp.stream": ["8"],
                    "tcp.seq": ["4000"],
                    "tls.record.content_type": ["22", ""],  # 第一个记录用content_type
                    "tls.record.opaque_type": ["", "23"],   # 第二个记录用opaque_type
                    "tls.record.length": ["64", "256"],
                    "tls.record.version": ["0x0303", "0x0304"]  # TLS 1.2 和 TLS 1.3
                }
            }
        }
        
        # 测试解析
        records = self.analyzer._parse_packet_tls_records(mock_packet_mixed)
        
        # 验证两个记录都被正确解析
        self.assertEqual(len(records), 2)
        
        # 第一个记录：使用content_type
        record1 = records[0]
        self.assertEqual(record1.content_type, 22)
        self.assertEqual(record1.length, 64)
        self.assertEqual(record1.version, (3, 3))  # TLS 1.2
        
        # 第二个记录：使用opaque_type
        record2 = records[1]
        self.assertEqual(record2.content_type, 23)
        self.assertEqual(record2.length, 256)
        self.assertEqual(record2.version, (3, 4))  # TLS 1.3
        
    def test_empty_or_missing_fields(self):
        """测试空字段或缺失字段的处理"""
        # 模拟缺少类型字段的包
        mock_packet_no_type = {
            "_source": {
                "layers": {
                    "frame.number": ["104"],
                    "tcp.stream": ["9"],
                    "tcp.seq": ["5000"],
                    "tls.record.length": ["128"],
                    "tls.record.version": ["0x0303"]
                    # 没有content_type或opaque_type字段
                }
            }
        }
        
        # 测试解析
        records = self.analyzer._parse_packet_tls_records(mock_packet_no_type)
        
        # 验证没有记录被创建
        self.assertEqual(len(records), 0)
        
    @patch('subprocess.run')
    def test_tshark_command_includes_both_fields(self, mock_run):
        """测试TShark命令包含两个字段"""
        # 模拟TShark可用
        self.analyzer._tshark_path = '/usr/bin/tshark'
        
        # 模拟文件存在
        mock_file = Mock()
        mock_file.exists.return_value = True
        
        # 构建命令
        cmd = self.analyzer._build_tshark_command(mock_file)
        
        # 验证命令包含两个字段
        cmd_str = ' '.join(cmd)
        self.assertIn('-e tls.record.content_type', cmd_str)
        self.assertIn('-e tls.record.opaque_type', cmd_str)
        
    def test_logging_field_source_info(self):
        """测试日志记录字段来源信息"""
        with patch.object(self.analyzer.logger, 'debug') as mock_debug:
            # 测试TLS 1.3包
            mock_packet_tls13 = {
                "_source": {
                    "layers": {
                        "frame.number": ["105"],
                        "tcp.stream": ["10"],
                        "tcp.seq": ["6000"],
                        "tls.record.opaque_type": ["23"],
                        "tls.record.length": ["256"],
                        "tls.record.version": ["0x0304"]
                    }
                }
            }
            
            records = self.analyzer._parse_packet_tls_records(mock_packet_tls13)
            
            # 验证日志记录了字段来源
            mock_debug.assert_any_call("TLS记录0使用opaque_type (TLS 1.3): 23")


if __name__ == '__main__':
    unittest.main() 