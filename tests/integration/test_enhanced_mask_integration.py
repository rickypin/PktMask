"""
增强掩码规则集成测试

验证TLS和非TLS TCP载荷掩码的完整集成功能
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os
from pathlib import Path

from src.pktmask.core.processors.tshark_enhanced_mask_processor import (
    TSharkEnhancedMaskProcessor, 
    TSharkEnhancedConfig
)
from src.pktmask.core.trim.models.tls_models import (
    TLSRecordInfo, 
    MaskRule, 
    MaskAction
)


class TestEnhancedMaskIntegration(unittest.TestCase):
    """测试增强掩码规则的集成功能"""
    
    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.input_file = os.path.join(self.temp_dir, "test_input.pcap")
        self.output_file = os.path.join(self.temp_dir, "test_output.pcap")
        
        # 创建测试用的空PCAP文件
        with open(self.input_file, 'wb') as f:
            f.write(b'\x00' * 100)  # 简单的测试数据
        
        # 配置增强掩码处理器
        self.config = TSharkEnhancedConfig(
            enable_non_tls_tcp_masking=True,
            non_tls_tcp_strategy="mask_all_payload",
            enable_detailed_logging=True
        )
    
    def tearDown(self):
        """清理测试环境"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('src.pktmask.core.processors.tshark_enhanced_mask_processor.TSharkEnhancedMaskProcessor._collect_tcp_packets_info')
    @patch('src.pktmask.core.processors.tshark_tls_analyzer.TSharkTLSAnalyzer')
    @patch('src.pktmask.core.processors.scapy_mask_applier.ScapyMaskApplier')
    def test_enhanced_mask_processing_with_mixed_traffic(self, mock_applier_class, mock_analyzer_class, mock_collect_tcp):
        """测试混合流量的增强掩码处理"""
        
        # 模拟TShark分析器
        mock_analyzer = Mock()
        mock_analyzer_class.return_value = mock_analyzer
        mock_analyzer.initialize.return_value = True
        
        # 模拟TLS记录（只有包1有TLS记录）
        tls_records = [
            TLSRecordInfo(
                packet_number=1,
                content_type=23,  # ApplicationData
                version=(3, 3),
                length=100,
                is_complete=True,
                spans_packets=[1],
                tcp_stream_id="tls_stream",
                record_offset=0
            )
        ]
        mock_analyzer.analyze_file.return_value = tls_records
        
        # 模拟TCP包信息（包1有TLS，包2-4是非TLS）
        tcp_packets_info = {
            1: {'tcp_stream_id': 'tls_stream', 'has_payload': True, 'payload_length': 105},
            2: {'tcp_stream_id': 'http_stream', 'has_payload': True, 'payload_length': 200},
            3: {'tcp_stream_id': 'ssh_stream', 'has_payload': True, 'payload_length': 150},
            4: {'tcp_stream_id': 'ftp_stream', 'has_payload': True, 'payload_length': 80},
        }
        mock_collect_tcp.return_value = tcp_packets_info
        
        # 模拟Scapy掩码应用器
        mock_applier = Mock()
        mock_applier_class.return_value = mock_applier
        mock_applier.apply_masks.return_value = {
            'packets_processed': 4,
            'packets_modified': 4,
            'success': True
        }
        
        # 创建处理器并处理文件
        processor = TSharkEnhancedMaskProcessor(self.config)
        
        # 手动初始化核心组件（绕过实际的TShark检查）
        from src.pktmask.core.processors.tls_mask_rule_generator import TLSMaskRuleGenerator
        processor._tshark_analyzer = mock_analyzer
        processor._rule_generator = TLSMaskRuleGenerator(processor._create_generator_config())
        processor._scapy_applier = mock_applier
        
        # 处理文件
        result = processor.process_file(self.input_file, self.output_file)
        
        # 验证结果
        self.assertTrue(result.success)
        self.assertEqual(result.stats['tls_records_found'], 1)
        self.assertEqual(result.stats['mask_rules_generated'], 4)  # 1个TLS + 3个非TLS
        self.assertEqual(result.stats['non_tls_rules_generated'], 3)
        
        # 验证调用了正确的方法
        mock_analyzer.analyze_file.assert_called_once()
        mock_collect_tcp.assert_called_once()
        mock_applier.apply_masks.assert_called_once()
        
        # 验证传递给Scapy应用器的掩码规则
        call_args = mock_applier.apply_masks.call_args
        mask_rules = call_args[0][2]  # 第三个参数是掩码规则列表
        
        # 应该有4条规则：1条TLS + 3条非TLS
        self.assertEqual(len(mask_rules), 4)
        
        # 验证TLS规则
        tls_rules = [r for r in mask_rules if r.tls_record_type == 23]
        self.assertEqual(len(tls_rules), 1)
        self.assertEqual(tls_rules[0].action, MaskAction.MASK_PAYLOAD)
        self.assertEqual(tls_rules[0].packet_number, 1)
        
        # 验证非TLS规则
        non_tls_rules = [r for r in mask_rules if r.tls_record_type is None]
        self.assertEqual(len(non_tls_rules), 3)
        
        for rule in non_tls_rules:
            self.assertEqual(rule.action, MaskAction.MASK_ALL_PAYLOAD)
            self.assertEqual(rule.mask_length, -1)  # 掩码到载荷结束
            self.assertEqual(rule.mask_offset, 0)   # 从载荷开始
            self.assertIn("非TLS TCP载荷全掩码策略", rule.reason)
    
    @patch('src.pktmask.core.processors.tshark_enhanced_mask_processor.TSharkEnhancedMaskProcessor._collect_tcp_packets_info')
    @patch('src.pktmask.core.processors.tshark_tls_analyzer.TSharkTLSAnalyzer')
    @patch('src.pktmask.core.processors.scapy_mask_applier.ScapyMaskApplier')
    def test_disabled_non_tls_masking(self, mock_applier_class, mock_analyzer_class, mock_collect_tcp):
        """测试禁用非TLS TCP载荷掩码时的行为"""
        
        # 配置禁用非TLS掩码
        disabled_config = TSharkEnhancedConfig(
            enable_non_tls_tcp_masking=False,
            non_tls_tcp_strategy="mask_all_payload"
        )
        
        # 模拟组件
        mock_analyzer = Mock()
        mock_analyzer_class.return_value = mock_analyzer
        mock_analyzer.initialize.return_value = True
        mock_analyzer.analyze_file.return_value = []  # 无TLS记录
        
        mock_applier = Mock()
        mock_applier_class.return_value = mock_applier
        mock_applier.apply_masks.return_value = {
            'packets_processed': 0,
            'packets_modified': 0,
            'success': True
        }
        
        # 创建处理器
        processor = TSharkEnhancedMaskProcessor(disabled_config)
        from src.pktmask.core.processors.tls_mask_rule_generator import TLSMaskRuleGenerator
        processor._tshark_analyzer = mock_analyzer
        processor._rule_generator = TLSMaskRuleGenerator(processor._create_generator_config())
        processor._scapy_applier = mock_applier
        
        # 处理文件
        result = processor.process_file(self.input_file, self.output_file)
        
        # 验证结果
        self.assertTrue(result.success)
        self.assertEqual(result.stats['mask_rules_generated'], 0)
        
        # 验证调用了TCP包信息收集，但没有生成非TLS规则
        mock_collect_tcp.assert_called_once()
        
        # 验证传递给Scapy应用器的掩码规则为空
        call_args = mock_applier.apply_masks.call_args
        mask_rules = call_args[0][2]
        self.assertEqual(len(mask_rules), 0)
    
    def test_enhanced_config_parameters(self):
        """测试增强配置参数"""
        config = TSharkEnhancedConfig(
            enable_non_tls_tcp_masking=True,
            non_tls_tcp_strategy="mask_all_payload"
        )
        
        self.assertTrue(config.enable_non_tls_tcp_masking)
        self.assertEqual(config.non_tls_tcp_strategy, "mask_all_payload")
        
        # 测试默认值
        default_config = TSharkEnhancedConfig()
        self.assertTrue(default_config.enable_non_tls_tcp_masking)
        self.assertEqual(default_config.non_tls_tcp_strategy, "mask_all_payload")


if __name__ == '__main__':
    unittest.main()
