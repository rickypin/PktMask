"""
TCP载荷掩码器 Phase 1.3 API封装测试

验证主API函数的功能和错误处理机制。
"""

import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from typing import Dict, List

from src.pktmask.core.tcp_payload_masker.api.types import (
    PacketMaskInstruction,
    MaskingRecipe,
    PacketMaskingResult,
    MaskingStatistics
)
from src.pktmask.core.tcp_payload_masker.api.masker import (
    mask_pcap_with_instructions,
    create_masking_recipe_from_dict,
    get_api_version,
    get_supported_formats,
    estimate_processing_time
)
from src.pktmask.core.tcp_payload_masker.api.validator import validate_masking_recipe
from src.pktmask.core.tcp_payload_masker.core.consistency import verify_file_consistency
from src.pktmask.core.trim.models.mask_spec import MaskAfter, MaskRange, KeepAll


class TestMaskPcapWithInstructions(unittest.TestCase):
    """测试主API函数 mask_pcap_with_instructions"""
    
    def setUp(self):
        """测试设置"""
        self.temp_dir = tempfile.mkdtemp()
        self.input_file = os.path.join(self.temp_dir, "test_input.pcap")
        self.output_file = os.path.join(self.temp_dir, "test_output.pcap")
        
        # 创建简单的测试配方
        self.test_recipe = MaskingRecipe(
            instructions={
                (0, "123456789.123"): PacketMaskInstruction(
                    packet_index=0,
                    packet_timestamp="123456789.123",
                    payload_offset=54,
                    mask_spec=MaskAfter(keep_bytes=5)
                )
            },
            total_packets=1,
            metadata={"test": "data"}
        )
    
    @patch('src.pktmask.core.tcp_payload_masker.api.validator.validate_masking_recipe')
    @patch('src.pktmask.core.tcp_payload_masker.api.masker.PacketProcessor')
    def test_successful_processing(self, mock_processor_class, mock_validate):
        """测试成功的处理流程"""
        # 模拟验证通过
        mock_validate.return_value = []
        
        # 模拟处理器成功处理
        mock_processor = MagicMock()
        mock_processor_class.return_value = mock_processor
        
        mock_result = PacketMaskingResult(
            success=True,
            processed_packets=1,
            modified_packets=1,
            output_file=self.output_file,
            errors=[],
            statistics={"processed": 1}
        )
        mock_processor.process_pcap_file.return_value = mock_result
        
        # 执行测试（禁用一致性验证以简化测试）
        result = mask_pcap_with_instructions(
            self.input_file,
            self.output_file,
            self.test_recipe,
            verify_consistency=False  # 禁用一致性验证
        )
        
        # 验证结果
        self.assertTrue(result.success)
        self.assertEqual(result.processed_packets, 1)
        self.assertEqual(result.modified_packets, 1)
        
        # 验证调用
        mock_validate.assert_called_once_with(self.test_recipe, self.input_file)
        mock_processor.process_pcap_file.assert_called_once()
    
    @patch('src.pktmask.core.tcp_payload_masker.api.validator.validate_masking_recipe')
    def test_validation_failure(self, mock_validate):
        """测试验证失败的情况"""
        # 模拟验证失败
        mock_validate.return_value = ["验证错误1", "验证错误2"]
        
        # 执行测试
        result = mask_pcap_with_instructions(
            self.input_file,
            self.output_file,
            self.test_recipe
        )
        
        # 验证结果
        self.assertFalse(result.success)
        self.assertEqual(len(result.errors), 2)
        self.assertIn("验证错误1", result.errors)
        self.assertEqual(result.processed_packets, 0)
    
    @patch('src.pktmask.core.tcp_payload_masker.api.validator.validate_masking_recipe')
    @patch('src.pktmask.core.tcp_payload_masker.core.consistency.verify_file_consistency')
    @patch('src.pktmask.core.tcp_payload_masker.api.masker.PacketProcessor')
    def test_consistency_verification(self, mock_processor_class, mock_verify, mock_validate):
        """测试一致性验证功能"""
        # 模拟验证通过
        mock_validate.return_value = []
        
        # 模拟处理器成功处理
        mock_processor = MagicMock()
        mock_processor_class.return_value = mock_processor
        
        mock_result = PacketMaskingResult(
            success=True,
            processed_packets=1,
            modified_packets=1,
            output_file=self.output_file
        )
        mock_processor.process_pcap_file.return_value = mock_result
        
        # 模拟一致性验证失败
        mock_verify.return_value = ["一致性错误"]
        
        # 执行测试
        result = mask_pcap_with_instructions(
            self.input_file,
            self.output_file,
            self.test_recipe,
            verify_consistency=True
        )
        
        # 验证结果
        self.assertFalse(result.success)
        self.assertIn("一致性错误", result.errors)
        
        # 验证一致性检查被调用
        mock_verify.assert_called_once_with(
            self.input_file, self.output_file, self.test_recipe
        )


class TestValidateMaskingRecipe(unittest.TestCase):
    """测试配方验证函数"""
    
    def setUp(self):
        """测试设置"""
        self.valid_recipe = MaskingRecipe(
            instructions={
                (0, "123456789.123"): PacketMaskInstruction(
                    packet_index=0,
                    packet_timestamp="123456789.123",
                    payload_offset=54,
                    mask_spec=MaskAfter(keep_bytes=5)
                )
            },
            total_packets=1
        )
    
    def test_valid_recipe_without_file(self):
        """测试有效配方（不检查文件）"""
        errors = validate_masking_recipe(self.valid_recipe)
        self.assertEqual(len(errors), 0)
    
    def test_empty_instructions(self):
        """测试空指令配方"""
        empty_recipe = MaskingRecipe(
            instructions={},
            total_packets=0
        )
        
        errors = validate_masking_recipe(empty_recipe)
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("没有任何掩码指令" in err for err in errors))
    
    def test_invalid_total_packets(self):
        """测试无效的总包数"""
        # 应该在创建配方时就抛出异常
        with self.assertRaises(ValueError) as context:
            MaskingRecipe(
                instructions={
                    (0, "123456789.123"): PacketMaskInstruction(
                        packet_index=0,
                        packet_timestamp="123456789.123",
                        payload_offset=54,
                        mask_spec=MaskAfter(keep_bytes=5)
                    )
                },
                total_packets=-1  # 无效的总包数
            )
        
        # 验证异常消息包含预期内容
        self.assertIn("total_packets必须为非负数", str(context.exception))
    
    def test_nonexistent_file(self):
        """测试不存在的文件"""
        errors = validate_masking_recipe(self.valid_recipe, "/nonexistent/file.pcap")
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("输入文件不存在" in err for err in errors))


class TestCreateMaskingRecipeFromDict(unittest.TestCase):
    """测试从字典创建配方的功能"""
    
    def test_valid_dict_creation(self):
        """测试从有效字典创建配方"""
        instructions_dict = {
            "0_123456789.123": {
                "packet_index": 0,
                "packet_timestamp": "123456789.123",
                "payload_offset": 54,
                "mask_spec": {
                    "type": "MaskAfter",
                    "keep_bytes": 5
                },
                "metadata": {"test": "data"}
            }
        }
        
        recipe = create_masking_recipe_from_dict(instructions_dict, 1)
        
        # 验证配方
        self.assertEqual(recipe.total_packets, 1)
        self.assertEqual(len(recipe.instructions), 1)
        
        # 获取指令
        instruction = recipe.get_instruction_for_packet(0, "123456789.123")
        self.assertIsNotNone(instruction)
        self.assertEqual(instruction.payload_offset, 54)
        self.assertIsInstance(instruction.mask_spec, MaskAfter)
        self.assertEqual(instruction.mask_spec.keep_bytes, 5)
    
    def test_invalid_key_format(self):
        """测试无效的键格式"""
        instructions_dict = {
            "invalid_key_format": {
                "packet_index": 0,
                "packet_timestamp": "123456789.123",
                "payload_offset": 54,
                "mask_spec": {"type": "MaskAfter", "keep_bytes": 5}
            }
        }
        
        with self.assertRaises(ValueError):
            create_masking_recipe_from_dict(instructions_dict, 1)
    
    def test_mask_range_creation(self):
        """测试MaskRange类型的创建"""
        instructions_dict = {
            "0_123456789.123": {
                "packet_index": 0,
                "packet_timestamp": "123456789.123",
                "payload_offset": 54,
                "mask_spec": {
                    "type": "MaskRange",
                    "ranges": [
                        {"start": 0, "end": 10},
                        {"start": 20, "end": 30}
                    ]
                }
            }
        }
        
        recipe = create_masking_recipe_from_dict(instructions_dict, 1)
        instruction = recipe.get_instruction_for_packet(0, "123456789.123")
        
        self.assertIsInstance(instruction.mask_spec, MaskRange)
        self.assertEqual(len(instruction.mask_spec.ranges), 2)


class TestPrivateHelperFunctions(unittest.TestCase):
    """测试私有辅助函数"""
    
    def test_validate_instructions(self):
        """测试指令验证"""
        # 创建有问题的配方
        recipe = MaskingRecipe(
            instructions={
                (0, "123456789.123"): PacketMaskInstruction(
                    packet_index=0,
                    packet_timestamp="123456789.123",
                    payload_offset=5,  # 过小的偏移量
                    mask_spec=MaskAfter(keep_bytes=5)
                ),
                (1, "123456789.124"): PacketMaskInstruction(
                    packet_index=1,
                    packet_timestamp="123456789.124",
                    payload_offset=2000,  # 过大的偏移量
                    mask_spec=MaskAfter(keep_bytes=5)
                )
            },
            total_packets=2
        )
        
        errors = _validate_instructions(recipe)
        self.assertEqual(len(errors), 2)
        self.assertTrue(any("过小" in err for err in errors))
        self.assertTrue(any("过大" in err for err in errors))
    
    def test_rebuild_mask_spec(self):
        """测试MaskSpec重建"""
        # 测试MaskAfter
        mask_after_data = {"type": "MaskAfter", "keep_bytes": 10}
        mask_spec = _rebuild_mask_spec(mask_after_data)
        self.assertIsInstance(mask_spec, MaskAfter)
        self.assertEqual(mask_spec.keep_bytes, 10)
        
        # 测试KeepAll
        keep_all_data = {"type": "KeepAll"}
        mask_spec = _rebuild_mask_spec(keep_all_data)
        self.assertIsInstance(mask_spec, KeepAll)
        
        # 测试未知类型
        with self.assertRaises(ValueError):
            _rebuild_mask_spec({"type": "UnknownType"})


class TestIntegrationScenarios(unittest.TestCase):
    """集成场景测试"""
    
    def test_complete_workflow_mock(self):
        """测试完整工作流程（模拟）"""
        # 创建测试配方
        recipe = MaskingRecipe(
            instructions={
                (0, "123456789.123"): PacketMaskInstruction(
                    packet_index=0,
                    packet_timestamp="123456789.123",
                    payload_offset=54,
                    mask_spec=MaskAfter(keep_bytes=5)
                )
            },
            total_packets=1,
            metadata={"source": "test"}
        )
        
        # 验证配方有效性
        errors = validate_masking_recipe(recipe)
        self.assertEqual(len(errors), 0)
        
        # 测试字典往返转换
        instructions_dict = {
            "0_123456789.123": {
                "packet_index": 0,
                "packet_timestamp": "123456789.123",
                "payload_offset": 54,
                "mask_spec": {"type": "MaskAfter", "keep_bytes": 5}
            }
        }
        
        recreated_recipe = create_masking_recipe_from_dict(instructions_dict, 1)
        
        # 验证重建的配方
        self.assertEqual(recreated_recipe.total_packets, recipe.total_packets)
        self.assertEqual(len(recreated_recipe.instructions), len(recipe.instructions))
        
        # 获取指令并比较
        original_instruction = recipe.get_instruction_for_packet(0, "123456789.123")
        recreated_instruction = recreated_recipe.get_instruction_for_packet(0, "123456789.123")
        
        self.assertEqual(original_instruction.payload_offset, recreated_instruction.payload_offset)
        self.assertEqual(type(original_instruction.mask_spec), type(recreated_instruction.mask_spec))


if __name__ == '__main__':
    # 配置日志以便调试
    import logging
    logging.basicConfig(level=logging.DEBUG)
    
    # 运行测试
    unittest.main(verbosity=2) 