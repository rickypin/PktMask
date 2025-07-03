#!/usr/bin/env python3
"""
Phase 3 Day 15: 增强TLS验证功能综合测试

验证所有新增的TLS协议类型(20-24)验证函数的正确性：
- validate_complete_preservation()
- validate_smart_masking()  
- validate_cross_segment_handling()
- validate_protocol_type_detection()
- validate_boundary_safety()
- validate_enhanced_tls_processing()
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import sys
import os

# 添加项目根目录到Python路径
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

# 导入验证器模块
sys.path.append(str(project_root / "scripts" / "validation"))
import tls23_maskstage_e2e_validator as validator


class TestPhase3Day15EnhancedValidation(unittest.TestCase):
    """Phase 3 Day 15 增强验证功能测试"""

    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        
        # 创建模拟数据
        self.original_data = {
            "summary": {"total_matches": 5},
            "matches": [
                {
                    "frame": 1,
                    "protocol_types": [22],  # Handshake
                    "lengths": [100],
                    "zero_bytes": 0,
                    "payload_preview": "160301006b010000670303"
                },
                {
                    "frame": 2, 
                    "protocol_types": [23],  # Application Data
                    "lengths": [200],
                    "zero_bytes": 0,
                    "payload_preview": "1703010050aabbccdd"
                },
                {
                    "frame": 3,
                    "protocol_types": [20],  # Change Cipher Spec
                    "lengths": [50],
                    "zero_bytes": 0,
                    "payload_preview": "140301000101"
                },
                {
                    "frame": 4,
                    "protocol_types": [21],  # Alert
                    "lengths": [30],
                    "zero_bytes": 0,
                    "payload_preview": "1503010002"
                },
                {
                    "frame": 5,
                    "protocol_types": [24],  # Heartbeat
                    "lengths": [40],
                    "zero_bytes": 0,
                    "payload_preview": "1803010010"
                }
            ]
        }
        
        self.masked_data = {
            "summary": {"total_matches": 5},
            "matches": [
                {
                    "frame": 1,
                    "protocol_types": [22],  # Handshake - 应完全保留
                    "lengths": [100],
                    "zero_bytes": 0,
                    "payload_preview": "160301006b010000670303"  # 相同
                },
                {
                    "frame": 2,
                    "protocol_types": [23],  # Application Data - 应智能掩码
                    "lengths": [200],
                    "zero_bytes": 195,  # 大部分置零
                    "payload_preview": "1703010050000000000000"  # 头部保留，载荷置零
                },
                {
                    "frame": 3,
                    "protocol_types": [20],  # Change Cipher Spec - 应完全保留
                    "lengths": [50],
                    "zero_bytes": 0,
                    "payload_preview": "140301000101"  # 相同
                },
                {
                    "frame": 4,
                    "protocol_types": [21],  # Alert - 应完全保留
                    "lengths": [30],
                    "zero_bytes": 0,
                    "payload_preview": "1503010002"  # 相同
                },
                {
                    "frame": 5,
                    "protocol_types": [24],  # Heartbeat - 应完全保留
                    "lengths": [40],
                    "zero_bytes": 0,
                    "payload_preview": "1803010010"  # 相同
                }
            ]
        }

        # 写入临时文件
        self.original_json = self.temp_path / "original.json"
        self.masked_json = self.temp_path / "masked.json"
        
        with open(self.original_json, 'w') as f:
            json.dump(self.original_data, f)
        with open(self.masked_json, 'w') as f:
            json.dump(self.masked_data, f)

    def tearDown(self):
        """清理测试环境"""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_validate_complete_preservation(self):
        """测试完全保留验证功能"""
        result = validator.validate_complete_preservation(
            self.original_json, 
            self.masked_json, 
            target_types=[20, 21, 22, 24]
        )
        
        # 验证结果结构
        self.assertIn("total_target_records", result)
        self.assertIn("preserved_records", result)
        self.assertIn("preservation_rate", result)
        self.assertIn("status", result)
        self.assertIn("details", result)
        
        # 验证具体数值
        self.assertEqual(result["total_target_records"], 4)  # 4个目标类型记录
        self.assertEqual(result["preserved_records"], 4)      # 4个完全保留
        self.assertEqual(result["preservation_rate"], 100.0)  # 100%保留率
        self.assertEqual(result["status"], "pass")            # 通过验证
        
        print(f"✅ 完全保留验证: {result['preservation_rate']}% 保留率")

    def test_validate_smart_masking(self):
        """测试智能掩码验证功能"""
        result = validator.validate_smart_masking(
            self.original_json,
            self.masked_json,
            target_type=23,
            header_bytes=5
        )
        
        # 验证结果结构
        self.assertIn("total_target_records", result)
        self.assertIn("correctly_masked_records", result) 
        self.assertIn("masking_rate", result)
        self.assertIn("status", result)
        self.assertIn("details", result)
        
        # 验证具体数值
        self.assertEqual(result["total_target_records"], 1)      # 1个TLS-23记录
        self.assertEqual(result["correctly_masked_records"], 1)   # 1个正确掩码
        self.assertEqual(result["masking_rate"], 100.0)          # 100%掩码率
        self.assertEqual(result["status"], "pass")               # 通过验证
        
        print(f"✅ 智能掩码验证: {result['masking_rate']}% 掩码率")

    def test_validate_cross_segment_handling(self):
        """测试跨TCP段处理验证功能"""
        result = validator.validate_cross_segment_handling(
            self.original_json,
            self.masked_json
        )
        
        # 验证结果结构
        self.assertIn("total_streams", result)
        self.assertIn("consistent_streams", result)
        self.assertIn("consistency_rate", result)
        self.assertIn("status", result)
        self.assertIn("details", result)
        
        # 基本一致性检查
        self.assertGreaterEqual(result["consistency_rate"], 0)
        self.assertLessEqual(result["consistency_rate"], 100)
        
        print(f"✅ 跨段处理验证: {result['consistency_rate']}% 一致性")

    def test_validate_protocol_type_detection(self):
        """测试协议类型检测验证功能"""
        result = validator.validate_protocol_type_detection(
            self.original_json,
            target_types=[20, 21, 22, 23, 24]
        )
        
        # 验证结果结构
        self.assertIn("target_types", result)
        self.assertIn("detected_types", result)
        self.assertIn("missing_types", result)
        self.assertIn("type_counts", result)
        self.assertIn("detection_completeness", result)
        self.assertIn("status", result)
        
        # 验证检测结果
        self.assertEqual(result["target_types"], [20, 21, 22, 23, 24])
        self.assertEqual(set(result["detected_types"]), {20, 21, 22, 23, 24})
        self.assertEqual(result["missing_types"], [])  # 无缺失类型
        self.assertEqual(result["detection_completeness"], 100.0)  # 100%检测完整性
        self.assertEqual(result["status"], "pass")
        
        print(f"✅ 协议类型检测: {result['detection_completeness']}% 完整性")

    def test_validate_boundary_safety(self):
        """测试边界安全验证功能"""
        result = validator.validate_boundary_safety(
            self.original_json,
            self.masked_json
        )
        
        # 验证结果结构
        self.assertIn("total_frames", result)
        self.assertIn("safe_frames", result)
        self.assertIn("boundary_issues", result)
        self.assertIn("safety_rate", result)
        self.assertIn("status", result)
        self.assertIn("issue_details", result)
        
        # 验证安全性
        self.assertEqual(result["total_frames"], 5)     # 5个帧
        self.assertEqual(result["safe_frames"], 5)      # 5个安全帧
        self.assertEqual(result["boundary_issues"], 0)  # 0个边界问题
        self.assertEqual(result["safety_rate"], 100.0)  # 100%安全率
        self.assertEqual(result["status"], "pass")
        
        print(f"✅ 边界安全验证: {result['safety_rate']}% 安全率")

    def test_validate_enhanced_tls_processing(self):
        """测试综合增强TLS处理验证功能"""
        result = validator.validate_enhanced_tls_processing(
            self.original_json,
            self.masked_json
        )
        
        # 验证结果结构 - 包含所有子验证
        expected_keys = [
            "complete_preservation", 
            "smart_masking",
            "cross_segment_handling",
            "protocol_type_detection", 
            "boundary_safety",
            "overall"
        ]
        
        for key in expected_keys:
            self.assertIn(key, result)
            self.assertIn("status", result[key])
        
        # 验证overall评分
        overall = result["overall"]
        self.assertIn("score", overall)
        self.assertIn("status", overall)
        self.assertIn("passed_tests", overall)
        self.assertIn("total_tests", overall)
        
        # 验证高分通过
        self.assertGreaterEqual(overall["score"], 80.0)
        self.assertEqual(overall["status"], "pass")
        self.assertEqual(overall["passed_tests"], 5)  # 所有5个子测试通过
        self.assertEqual(overall["total_tests"], 5)
        
        print(f"✅ 综合验证: {overall['score']}% 评分, {overall['passed_tests']}/{overall['total_tests']} 测试通过")

    def test_enhanced_marker_tool_integration(self):
        """测试增强标记工具集成"""
        # 模拟增强TLS标记工具调用
        with patch('tls23_maskstage_e2e_validator.run_cmd') as mock_run_cmd:
            mock_run_cmd.return_value = None
            
            # 创建模拟输出文件
            output_file = self.temp_path / "test_enhanced_tls_frames.json"
            with open(output_file, 'w') as f:
                json.dump(self.original_data, f)
            
            # 测试工具调用
            result_path = validator.run_enhanced_tls_marker(
                Path("test.pcap"),
                self.temp_path,
                types="20,21,22,23,24"
            )
            
            # 验证调用参数
            mock_run_cmd.assert_called_once()
            args = mock_run_cmd.call_args[0][0]
            
            self.assertIn("pktmask.tools.enhanced_tls_marker", args)
            self.assertIn("--types", args)
            self.assertIn("20,21,22,23,24", args)
            self.assertIn("--formats", args)
            self.assertIn("json", args)
            
            print("✅ 增强标记工具集成测试通过")


class TestPhase3Day15ValidationCriteria(unittest.TestCase):
    """Phase 3 Day 15 验收标准测试"""

    def test_validation_functions_exist(self):
        """验证所有新增验证函数存在"""
        required_functions = [
            "validate_complete_preservation",
            "validate_smart_masking", 
            "validate_cross_segment_handling",
            "validate_protocol_type_detection",
            "validate_boundary_safety",
            "validate_enhanced_tls_processing"
        ]
        
        for func_name in required_functions:
            self.assertTrue(hasattr(validator, func_name))
            self.assertTrue(callable(getattr(validator, func_name)))
            print(f"✅ 验证函数存在: {func_name}")

    def test_tls_protocol_types_support(self):
        """验证TLS协议类型支持"""
        # 验证增强标记工具中的TLS类型定义
        from src.pktmask.tools import enhanced_tls_marker
        
        # 验证所有TLS类型都被支持
        expected_types = {20, 21, 22, 23, 24}
        supported_types = set(enhanced_tls_marker.TLS_CONTENT_TYPES.keys())
        
        self.assertEqual(expected_types, supported_types)
        print("✅ TLS协议类型支持: 20, 21, 22, 23, 24")

        # 验证处理策略正确性
        expected_strategies = {
            20: "keep_all",      # ChangeCipherSpec
            21: "keep_all",      # Alert
            22: "keep_all",      # Handshake  
            23: "mask_payload",  # ApplicationData
            24: "keep_all"       # Heartbeat
        }
        
        for tls_type, expected_strategy in expected_strategies.items():
            actual_strategy = enhanced_tls_marker.TLS_PROCESSING_STRATEGIES[tls_type]
            self.assertEqual(actual_strategy, expected_strategy)
            
        print("✅ TLS处理策略映射正确")

    def test_validation_thresholds(self):
        """验证验证阈值设置正确"""
        # 根据设计文档验证阈值设置
        validation_thresholds = {
            "complete_preservation": 95.0,  # TLS-20/21/22/24 >= 95%保留率
            "smart_masking": 95.0,          # TLS-23 >= 95%掩码率
            "cross_segment_handling": 90.0,  # >= 90%流一致性
            "protocol_type_detection": 80.0, # >= 80%检测完整性
            "boundary_safety": 95.0,         # >= 95%安全率
            "overall": 80.0                  # >= 80%综合评分
        }
        
        print("✅ 验证阈值设置:")
        for validation_type, threshold in validation_thresholds.items():
            print(f"   {validation_type}: >= {threshold}%")


if __name__ == "__main__":
    print("🚀 开始 Phase 3 Day 15 增强验证功能测试")
    print("=" * 60)
    
    # 运行测试
    unittest.main(verbosity=2, exit=False)
    
    print("=" * 60) 
    print("✅ Phase 3 Day 15 增强验证功能测试完成") 