"""
Phase 3 Day 18: TLS协议类型测试

验证所有5种TLS协议类型(20/21/22/23/24)的处理策略正确性。

测试覆盖：
1. 所有TLS协议类型策略正确性验证
2. 处理策略一致性验证  
3. 边界情况策略验证
4. 组合情况策略验证
5. 端到端策略应用验证

验收标准：5种TLS类型(20/21/22/23/24)策略100%正确
"""

import unittest
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Any
from unittest.mock import Mock, patch

from src.pktmask.core.processors.tls_mask_rule_generator import TLSMaskRuleGenerator
from src.pktmask.core.trim.models.tls_models import (
    TLSRecordInfo, MaskRule, MaskAction, TLSProcessingStrategy,
    get_tls_processing_strategy
)


class TestPhase3Day18TLSProtocolTypes(unittest.TestCase):
    """Phase 3 Day 18: TLS协议类型测试"""
    
    def setUp(self):
        """测试设置"""
        self.temp_dir = Path(tempfile.mkdtemp())
        
        # 基础配置
        self.mock_config = {
            'enable_tls_processing': True,
            'enable_protocol_detection': True,
            'verbose': True,
            'validate_boundaries': True
        }
        
        # TLS协议类型映射定义
        self.tls_protocol_types = {
            20: {
                'name': 'ChangeCipherSpec',
                'strategy': TLSProcessingStrategy.KEEP_ALL,
                'description': '密码规范变更'
            },
            21: {
                'name': 'Alert',
                'strategy': TLSProcessingStrategy.KEEP_ALL,
                'description': '警告消息'
            },
            22: {
                'name': 'Handshake',
                'strategy': TLSProcessingStrategy.KEEP_ALL,
                'description': '握手消息'
            },
            23: {
                'name': 'ApplicationData',
                'strategy': TLSProcessingStrategy.MASK_PAYLOAD,
                'description': '应用数据'
            },
            24: {
                'name': 'Heartbeat',
                'strategy': TLSProcessingStrategy.KEEP_ALL,
                'description': '心跳消息'
            }
        }
        
    def tearDown(self):
        """清理测试环境"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_individual_protocol_type_strategies(self):
        """测试1: 个别协议类型策略验证"""
        print("\n=== 测试1: 个别TLS协议类型策略验证 ===")
        
        generator = TLSMaskRuleGenerator(self.mock_config)
        
        # 分别测试每种TLS协议类型
        for tls_type, type_info in self.tls_protocol_types.items():
            with self.subTest(tls_type=tls_type, name=type_info['name']):
                # 创建单个TLS记录
                record = TLSRecordInfo(
                    packet_number=1,
                    content_type=tls_type,
                    version=(3, 3),
                    length=100,
                    is_complete=True,
                    spans_packets=[1],
                    tcp_stream_id="test_stream",
                    record_offset=0
                )
                
                # 生成掩码规则
                rules = generator.generate_rules([record])
                self.assertEqual(len(rules), 1, f"TLS-{tls_type}应该生成1个规则")
                
                rule = rules[0]
                
                # 验证策略正确性
                if type_info['strategy'] == TLSProcessingStrategy.KEEP_ALL:
                    self.assertEqual(rule.action, MaskAction.KEEP_ALL, 
                                   f"TLS-{tls_type}({type_info['name']})应该完全保留")
                    self.assertEqual(rule.mask_length, 0, 
                                   f"TLS-{tls_type}({type_info['name']})不应该掩码")
                    
                elif type_info['strategy'] == TLSProcessingStrategy.MASK_PAYLOAD:
                    self.assertEqual(rule.action, MaskAction.MASK_PAYLOAD, 
                                   f"TLS-{tls_type}({type_info['name']})应该智能掩码")
                    self.assertEqual(rule.mask_offset, 5, 
                                   f"TLS-{tls_type}({type_info['name']})应该保留5字节头部")
                    self.assertEqual(rule.mask_length, 95, 
                                   f"TLS-{tls_type}({type_info['name']})应该掩码95字节载荷")
                
                print(f"   TLS-{tls_type} ({type_info['name']}): {rule.action} ✓")
        
        print("✅ 个别协议类型策略验证通过")
    
    def test_all_protocol_types_together(self):
        """测试2: 所有协议类型组合策略验证"""
        print("\n=== 测试2: 所有TLS协议类型组合策略验证 ===")
        
        generator = TLSMaskRuleGenerator(self.mock_config)
        
        # 创建包含所有TLS类型的记录集合
        all_type_records = []
        for packet_num, (tls_type, type_info) in enumerate(self.tls_protocol_types.items(), 1):
            record = TLSRecordInfo(
                packet_number=packet_num,
                content_type=tls_type,
                version=(3, 3),
                length=100,
                is_complete=True,
                spans_packets=[packet_num],
                tcp_stream_id=f"stream_{packet_num}",
                record_offset=0
            )
            all_type_records.append(record)
        
        # 生成所有规则
        all_rules = generator.generate_rules(all_type_records)
        self.assertEqual(len(all_rules), 5, "应该生成5个掩码规则")
        
        # 按TLS类型组织规则进行验证
        type_rule_map = {rule.tls_record_type: rule for rule in all_rules}
        
        # 验证完全保留类型：20, 21, 22, 24
        keep_all_types = [20, 21, 22, 24]
        for tls_type in keep_all_types:
            rule = type_rule_map[tls_type]
            type_name = self.tls_protocol_types[tls_type]['name']
            
            self.assertEqual(rule.action, MaskAction.KEEP_ALL,
                           f"TLS-{tls_type}({type_name})应该完全保留")
            self.assertEqual(rule.mask_length, 0,
                           f"TLS-{tls_type}({type_name})不应该掩码")
            print(f"   TLS-{tls_type} ({type_name}): 完全保留 ✓")
        
        # 验证智能掩码类型：23
        tls_23_rule = type_rule_map[23]
        self.assertEqual(tls_23_rule.action, MaskAction.MASK_PAYLOAD,
                        "TLS-23(ApplicationData)应该智能掩码")
        self.assertEqual(tls_23_rule.mask_offset, 5,
                        "TLS-23应该保留5字节头部")
        self.assertEqual(tls_23_rule.mask_length, 95,
                        "TLS-23应该掩码95字节载荷")
        print(f"   TLS-23 (ApplicationData): 智能掩码(5字节头部+95字节载荷) ✓")
        
        print("✅ 所有协议类型组合策略验证通过")
    
    def test_protocol_type_strategy_consistency(self):
        """测试3: 协议类型策略一致性验证"""
        print("\n=== 测试3: TLS协议类型策略一致性验证 ===")
        
        # 验证get_tls_processing_strategy函数的一致性
        for tls_type, type_info in self.tls_protocol_types.items():
            strategy_from_function = get_tls_processing_strategy(tls_type)
            expected_strategy = type_info['strategy']
            
            self.assertEqual(strategy_from_function, expected_strategy,
                           f"TLS-{tls_type}的策略不一致")
            print(f"   TLS-{tls_type}: {strategy_from_function.value} ✓")
        
        # 验证TLSRecordInfo的processing_strategy属性一致性
        for tls_type, type_info in self.tls_protocol_types.items():
            record = TLSRecordInfo(
                packet_number=1,
                content_type=tls_type,
                version=(3, 3),
                length=100,
                is_complete=True,
                spans_packets=[1],
                tcp_stream_id="test_stream",
                record_offset=0
            )
            
            self.assertEqual(record.processing_strategy, type_info['strategy'],
                           f"TLSRecordInfo.processing_strategy与预期不符: TLS-{tls_type}")
        
        print("✅ 协议类型策略一致性验证通过")
    
    def test_boundary_cases_protocol_strategies(self):
        """测试4: 边界情况协议策略验证"""
        print("\n=== 测试4: 边界情况TLS协议策略验证 ===")
        
        generator = TLSMaskRuleGenerator(self.mock_config)
        
        # 测试边界情况
        boundary_test_cases = [
            # 最小长度记录
            {
                'name': '最小长度记录',
                'length': 5,  # 等于TLS头部长度
                'expected_23_action': MaskAction.KEEP_ALL,  # 无载荷可掩码
                'expected_23_mask_length': 0
            },
            # 小于头部长度记录
            {
                'name': '小于头部长度记录',
                'length': 3,  # 小于TLS头部长度
                'expected_23_action': MaskAction.KEEP_ALL,  # 异常情况完全保留
                'expected_23_mask_length': 0
            },
            # 标准长度记录
            {
                'name': '标准长度记录',
                'length': 100,
                'expected_23_action': MaskAction.MASK_PAYLOAD,
                'expected_23_mask_length': 95  # 100 - 5
            }
        ]
        
        for test_case in boundary_test_cases:
            with self.subTest(case=test_case['name']):
                print(f"\n   测试边界情况: {test_case['name']} (长度: {test_case['length']})")
                
                # 为每种TLS类型创建边界测试记录
                boundary_records = []
                for packet_num, tls_type in enumerate(self.tls_protocol_types.keys(), 1):
                    record = TLSRecordInfo(
                        packet_number=packet_num,
                        content_type=tls_type,
                        version=(3, 3),
                        length=test_case['length'],
                        is_complete=True,
                        spans_packets=[packet_num],
                        tcp_stream_id=f"stream_{packet_num}",
                        record_offset=0
                    )
                    boundary_records.append(record)
                
                # 生成规则
                boundary_rules = generator.generate_rules(boundary_records)
                type_rule_map = {rule.tls_record_type: rule for rule in boundary_rules}
                
                # 验证非ApplicationData类型始终完全保留
                for tls_type in [20, 21, 22, 24]:
                    if tls_type in type_rule_map:
                        rule = type_rule_map[tls_type]
                        self.assertEqual(rule.action, MaskAction.KEEP_ALL,
                                       f"TLS-{tls_type}在边界情况下应该完全保留")
                        self.assertEqual(rule.mask_length, 0,
                                       f"TLS-{tls_type}在边界情况下不应该掩码")
                
                # 验证ApplicationData类型的边界行为
                if 23 in type_rule_map:
                    tls_23_rule = type_rule_map[23]
                    self.assertEqual(tls_23_rule.action, test_case['expected_23_action'],
                                   f"TLS-23在{test_case['name']}下的处理策略不正确")
                    self.assertEqual(tls_23_rule.mask_length, test_case['expected_23_mask_length'],
                                   f"TLS-23在{test_case['name']}下的掩码长度不正确")
                    
                    print(f"     TLS-23: {tls_23_rule.action}, 掩码长度: {tls_23_rule.mask_length} ✓")
        
        print("✅ 边界情况协议策略验证通过")
    
    def test_unsupported_protocol_type_handling(self):
        """测试5: 不支持协议类型处理"""
        print("\n=== 测试5: 不支持TLS协议类型处理验证 ===")
        
        # 测试不支持的协议类型
        unsupported_types = [0, 1, 25, 99, 255]
        
        for unsupported_type in unsupported_types:
            with self.subTest(unsupported_type=unsupported_type):
                # 测试get_tls_processing_strategy函数
                with self.assertRaises(ValueError) as context:
                    get_tls_processing_strategy(unsupported_type)
                
                self.assertIn("不支持的TLS内容类型", str(context.exception))
                print(f"   不支持类型{unsupported_type}: 正确抛出异常 ✓")
                
                # 测试TLSRecordInfo构造函数
                with self.assertRaises(ValueError) as context:
                    TLSRecordInfo(
                        packet_number=1,
                        content_type=unsupported_type,
                        version=(3, 3),
                        length=100,
                        is_complete=True,
                        spans_packets=[1],
                        tcp_stream_id="test_stream",
                        record_offset=0
                    )
                
                self.assertIn("不支持的TLS内容类型", str(context.exception))
        
        print("✅ 不支持协议类型处理验证通过")


class TestPhase3Day18AcceptanceCriteria(unittest.TestCase):
    """Phase 3 Day 18 验收标准测试"""
    
    def test_acceptance_criteria_verification(self):
        """验收标准验证"""
        print("\n=== Phase 3 Day 18 验收标准验证 ===")
        
        # 验收标准：5种TLS类型(20/21/22/23/24)策略100%正确
        
        expected_strategies = {
            20: TLSProcessingStrategy.KEEP_ALL,      # ChangeCipherSpec
            21: TLSProcessingStrategy.KEEP_ALL,      # Alert
            22: TLSProcessingStrategy.KEEP_ALL,      # Handshake
            23: TLSProcessingStrategy.MASK_PAYLOAD,  # ApplicationData
            24: TLSProcessingStrategy.KEEP_ALL       # Heartbeat
        }
        
        success_count = 0
        total_count = len(expected_strategies)
        
        for tls_type, expected_strategy in expected_strategies.items():
            try:
                actual_strategy = get_tls_processing_strategy(tls_type)
                self.assertEqual(actual_strategy, expected_strategy,
                               f"TLS-{tls_type}策略不正确")
                success_count += 1
                print(f"   TLS-{tls_type}: {actual_strategy.value} ✓")
            except Exception as e:
                print(f"   TLS-{tls_type}: 失败 - {e}")
        
        # 计算成功率
        success_rate = (success_count / total_count) * 100
        self.assertEqual(success_rate, 100.0, f"策略正确率应该为100%，实际为{success_rate}%")
        
        print(f"\n✅ 验收标准达成: TLS协议类型策略正确率 {success_rate}% (5/5)")
        print("✅ Phase 3 Day 18 所有验收标准通过")


def run_phase3_day18_tests():
    """运行Phase 3 Day 18测试"""
    print("=" * 80)
    print("Phase 3 Day 18: TLS协议类型测试执行")
    print("=" * 80)
    
    # 创建测试套件
    test_suite = unittest.TestSuite()
    
    # 添加主要测试
    test_suite.addTest(unittest.makeSuite(TestPhase3Day18TLSProtocolTypes))
    test_suite.addTest(unittest.makeSuite(TestPhase3Day18AcceptanceCriteria))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # 输出总结
    print("\n" + "=" * 80)
    print("Phase 3 Day 18 测试总结")
    print("=" * 80)
    print(f"运行测试数: {result.testsRun}")
    print(f"失败数: {len(result.failures)}")
    print(f"错误数: {len(result.errors)}")
    print(f"成功率: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    
    if result.failures:
        print("\n失败的测试:")
        for test, traceback in result.failures:
            print(f"  - {test}: {traceback}")
    
    if result.errors:
        print("\n错误的测试:")
        for test, traceback in result.errors:
            print(f"  - {test}: {traceback}")
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_phase3_day18_tests()
    exit(0 if success else 1) 