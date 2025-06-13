"""
Enhanced Trim Payloads 核心数据结构单元测试

测试Phase 1.1实现的核心数据结构：
- MaskSpec及其子类
- StreamMaskTable和StreamMaskEntry
- ExecutionResult和TrimmerConfig
"""

import unittest
from typing import List

from src.pktmask.core.trim.models.mask_spec import (
    MaskSpec, MaskAfter, MaskRange, KeepAll,
    create_http_header_mask, create_tls_record_mask,
    create_full_payload_mask, create_preserve_all_mask
)
from src.pktmask.core.trim.models.mask_table import (
    StreamMaskTable, StreamMaskEntry
)
from src.pktmask.core.trim.models.execution_result import (
    ExecutionResult, TrimmerConfig, StageResult,
    ExecutionStatus, StageStatus
)
from src.pktmask.core.trim.exceptions import (
    MaskSpecError, StreamMaskTableError, ConfigValidationError
)


class TestMaskSpec(unittest.TestCase):
    """测试掩码规范及其子类"""
    
    def test_mask_after_basic(self):
        """测试MaskAfter基本功能"""
        # 测试保留前5字节
        mask = MaskAfter(5)
        payload = b"Hello, World!"
        result = mask.apply_to_payload(payload)
        expected = b"Hello\x00\x00\x00\x00\x00\x00\x00\x00"
        self.assertEqual(result, expected)
        self.assertEqual(mask.get_description(), "保留前5字节，其余置零")
    
    def test_mask_after_full_zero(self):
        """测试MaskAfter全部置零"""
        mask = MaskAfter(0)
        payload = b"Hello, World!"
        result = mask.apply_to_payload(payload)
        expected = b"\x00" * len(payload)
        self.assertEqual(result, expected)
        self.assertEqual(mask.get_description(), "全部载荷置零")
    
    def test_mask_after_full_keep(self):
        """测试MaskAfter完全保留"""
        mask = MaskAfter(100)  # 超过载荷长度
        payload = b"Hello!"
        result = mask.apply_to_payload(payload)
        self.assertEqual(result, payload)
    
    def test_mask_after_empty_payload(self):
        """测试MaskAfter处理空载荷"""
        mask = MaskAfter(5)
        result = mask.apply_to_payload(b"")
        self.assertEqual(result, b"")
    
    def test_mask_after_invalid_params(self):
        """测试MaskAfter无效参数"""
        with self.assertRaises(MaskSpecError):
            MaskAfter(-1)
    
    def test_mask_range_basic(self):
        """测试MaskRange基本功能"""
        mask = MaskRange([(2, 5), (8, 10)])
        payload = b"0123456789"
        result = mask.apply_to_payload(payload)
        expected = b"01\x00\x00\x00567\x00\x00"
        self.assertEqual(result, expected)
    
    def test_mask_range_boundary(self):
        """测试MaskRange边界处理"""
        mask = MaskRange([(5, 100)])  # 超出边界
        payload = b"Hello"
        result = mask.apply_to_payload(payload)
        self.assertEqual(result, payload)  # 超出边界不影响
    
    def test_mask_range_invalid_params(self):
        """测试MaskRange无效参数"""
        with self.assertRaises(MaskSpecError):
            MaskRange([])  # 空区间
        
        with self.assertRaises(MaskSpecError):
            MaskRange([(-1, 5)])  # 负数
        
        with self.assertRaises(MaskSpecError):
            MaskRange([(5, 3)])  # start >= end
        
        with self.assertRaises(MaskSpecError):
            MaskRange([(0, 5), (3, 8)])  # 重叠区间
    
    def test_keep_all(self):
        """测试KeepAll"""
        mask = KeepAll()
        payload = b"Hello, World!"
        result = mask.apply_to_payload(payload)
        self.assertEqual(result, payload)
        self.assertEqual(mask.get_description(), "完全保留载荷")
    
    def test_mask_spec_factory_functions(self):
        """测试掩码规范工厂函数"""
        # HTTP头掩码
        http_mask = create_http_header_mask(50)
        self.assertIsInstance(http_mask, MaskAfter)
        self.assertEqual(http_mask.keep_bytes, 50)
        
        # TLS记录头掩码
        tls_mask = create_tls_record_mask()
        self.assertIsInstance(tls_mask, MaskAfter)
        self.assertEqual(tls_mask.keep_bytes, 5)
        
        # 全载荷置零掩码
        full_mask = create_full_payload_mask()
        self.assertIsInstance(full_mask, MaskAfter)
        self.assertEqual(full_mask.keep_bytes, 0)
        
        # 完全保留掩码
        preserve_mask = create_preserve_all_mask()
        self.assertIsInstance(preserve_mask, KeepAll)


class TestStreamMaskTable(unittest.TestCase):
    """测试流掩码表"""
    
    def setUp(self):
        """设置测试环境"""
        self.table = StreamMaskTable()
        self.stream_id = "tcp/80->8080/stream1"
    
    def test_add_entry_basic(self):
        """测试添加基本条目"""
        mask_spec = MaskAfter(10)
        entry = StreamMaskEntry(self.stream_id, 100, 200, mask_spec)
        
        self.table.add_entry(entry)
        self.assertEqual(self.table.get_stream_entry_count(self.stream_id), 1)
        self.assertEqual(self.table.get_total_entry_count(), 1)
    
    def test_add_mask_range_convenience(self):
        """测试便捷添加方法"""
        mask_spec = MaskAfter(5)
        self.table.add_mask_range(self.stream_id, 0, 100, mask_spec)
        
        self.assertEqual(self.table.get_stream_entry_count(self.stream_id), 1)
        coverage = self.table.get_stream_coverage(self.stream_id)
        self.assertEqual(coverage, (0, 100))
    
    def test_lookup_basic(self):
        """测试基本查询"""
        mask_spec = MaskAfter(10)
        self.table.add_mask_range(self.stream_id, 100, 200, mask_spec)
        self.table.finalize()
        
        # 查询匹配的范围
        result = self.table.lookup(self.stream_id, 150, 20)
        self.assertEqual(result, mask_spec)
        
        # 查询不匹配的范围
        result = self.table.lookup(self.stream_id, 300, 20)
        self.assertIsNone(result)
    
    def test_lookup_multiple(self):
        """测试多重查询"""
        mask1 = MaskAfter(5)
        mask2 = MaskAfter(10)
        
        self.table.add_mask_range(self.stream_id, 0, 50, mask1)
        self.table.add_mask_range(self.stream_id, 75, 125, mask2)
        self.table.finalize()
        
        # 查询跨越两个区间的范围
        matches = self.table.lookup_multiple(self.stream_id, 40, 50)
        self.assertEqual(len(matches), 2)
        
        # 验证相对偏移计算
        first_match = matches[0]
        self.assertEqual(first_match[0], 0)  # 相对起始位置
        self.assertEqual(first_match[1], 10)  # 相对结束位置
        self.assertEqual(first_match[2], mask1)
    
    def test_finalize_and_merge(self):
        """测试完成和合并操作"""
        mask_spec = MaskAfter(10)
        
        # 添加相邻的相同掩码条目
        self.table.add_mask_range(self.stream_id, 0, 50, mask_spec)
        self.table.add_mask_range(self.stream_id, 50, 100, mask_spec)
        self.table.add_mask_range(self.stream_id, 100, 150, mask_spec)
        
        self.assertEqual(self.table.get_total_entry_count(), 3)
        
        # 完成后应该合并为一个条目
        self.table.finalize()
        self.assertEqual(self.table.get_total_entry_count(), 1)
        
        # 验证合并后的覆盖范围
        coverage = self.table.get_stream_coverage(self.stream_id)
        self.assertEqual(coverage, (0, 150))
    
    def test_statistics(self):
        """测试统计信息"""
        mask_spec = MaskAfter(10)
        self.table.add_mask_range(self.stream_id, 0, 100, mask_spec)
        self.table.add_mask_range("tcp/443->8443/stream2", 0, 50, mask_spec)
        
        stats = self.table.get_statistics()
        self.assertEqual(stats['total_streams'], 2)
        self.assertEqual(stats['total_entries'], 2)
        self.assertFalse(stats['is_finalized'])
        
        self.table.finalize()
        
        stats = self.table.get_statistics()
        self.assertTrue(stats['is_finalized'])
    
    def test_export_to_dict(self):
        """测试导出为字典"""
        mask_spec = MaskAfter(10)
        self.table.add_mask_range(self.stream_id, 0, 100, mask_spec)
        self.table.finalize()
        
        exported = self.table.export_to_dict()
        self.assertTrue(exported['is_finalized'])
        self.assertIn(self.stream_id, exported['streams'])
        
        stream_data = exported['streams'][self.stream_id]
        self.assertEqual(len(stream_data), 1)
        self.assertEqual(stream_data[0]['seq_start'], 0)
        self.assertEqual(stream_data[0]['seq_end'], 100)
        self.assertEqual(stream_data[0]['mask_type'], 'MaskAfter')
    
    def test_invalid_entry(self):
        """测试无效条目"""
        with self.assertRaises(StreamMaskTableError):
            StreamMaskEntry(self.stream_id, -1, 100, MaskAfter(10))
        
        with self.assertRaises(StreamMaskTableError):
            StreamMaskEntry(self.stream_id, 100, 50, MaskAfter(10))
        
        # 测试表已完成后不能添加条目
        self.table.finalize()
        with self.assertRaises(StreamMaskTableError):
            self.table.add_mask_range(self.stream_id, 0, 100, MaskAfter(10))


class TestTrimmerConfig(unittest.TestCase):
    """测试裁切配置"""
    
    def test_default_config(self):
        """测试默认配置"""
        config = TrimmerConfig()
        
        # 验证默认值
        self.assertTrue(config.http_keep_headers)
        self.assertTrue(config.tls_keep_signaling)
        self.assertEqual(config.processing_mode, "preserve_length")
        self.assertTrue(config.validation_enabled)
        self.assertEqual(config.chunk_size, 1000)
    
    def test_config_validation(self):
        """测试配置验证"""
        config = TrimmerConfig(
            # 设置一个兼容的默认配置，避免交叉验证警告
            tls_keep_signaling=True,
            tls_keep_handshake=True,
            default_trim_strategy="keep_all",  # 与http_keep_headers兼容
            pyshark_keep_packets=True  # 避免TShark配置建议
        )
        
        # 兼容配置应该有效
        errors = config.validate()
        self.assertEqual(len(errors), 0)
        
        # 测试无效配置
        config.http_header_max_length = -1
        config.default_keep_bytes = -5
        config.processing_mode = "invalid_mode"
        
        errors = config.validate()
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("HTTP头最大长度" in error for error in errors))
        self.assertTrue(any("默认保留字节数" in error for error in errors))
        self.assertTrue(any("处理模式必须是" in error for error in errors))
    
    def test_config_to_dict(self):
        """测试配置转换为字典"""
        config = TrimmerConfig(
            http_keep_headers=False,
            tls_keep_signaling=False,
            chunk_size=2000
        )
        
        config_dict = config.to_dict()
        self.assertFalse(config_dict['http_keep_headers'])
        self.assertFalse(config_dict['tls_keep_signaling'])
        self.assertEqual(config_dict['chunk_size'], 2000)


class TestExecutionResult(unittest.TestCase):
    """测试执行结果"""
    
    def setUp(self):
        """设置测试环境"""
        self.config = TrimmerConfig()
        self.result = ExecutionResult(
            input_file="test_input.pcap",
            output_file="test_output.pcap",
            config=self.config
        )
    
    def test_basic_lifecycle(self):
        """测试基本生命周期"""
        # 初始状态
        self.assertEqual(self.result.status, ExecutionStatus.PENDING)
        self.assertFalse(self.result.is_successful())
        
        # 开始执行
        self.result.mark_started()
        self.assertEqual(self.result.status, ExecutionStatus.RUNNING)
        self.assertIsNotNone(self.result.start_time)
        
        # 完成执行
        self.result.mark_completed()
        self.assertEqual(self.result.status, ExecutionStatus.SUCCESS)
        self.assertIsNotNone(self.result.end_time)
        self.assertGreater(self.result.total_duration_seconds, 0)
    
    def test_stage_management(self):
        """测试阶段管理"""
        # 添加阶段
        stage1 = self.result.add_stage("tshark_preprocess")
        self.assertIsInstance(stage1, StageResult)
        self.assertEqual(stage1.stage_name, "tshark_preprocess")
        
        stage2 = self.result.add_stage("pyshark_analyze")
        self.assertEqual(len(self.result.stages), 2)
        
        # 获取阶段
        retrieved_stage = self.result.get_stage("tshark_preprocess")
        self.assertEqual(retrieved_stage, stage1)
        
        # 不存在的阶段
        self.assertIsNone(self.result.get_stage("nonexistent"))
    
    def test_stage_lifecycle(self):
        """测试阶段生命周期"""
        stage = self.result.add_stage("test_stage")
        
        # 开始阶段
        stage.mark_started()
        self.assertEqual(stage.status, StageStatus.RUNNING)
        self.assertIsNotNone(stage.start_time)
        
        # 完成阶段
        stage.mark_completed(processed_packets=100, output_size=5000)
        self.assertEqual(stage.status, StageStatus.COMPLETED)
        self.assertTrue(stage.is_successful())
        self.assertEqual(stage.stage_data['processed_packets'], 100)
        
        # 失败阶段
        failed_stage = self.result.add_stage("failed_stage")
        failed_stage.mark_failed("测试错误")
        self.assertEqual(failed_stage.status, StageStatus.FAILED)
        self.assertFalse(failed_stage.is_successful())
        self.assertEqual(len(failed_stage.errors), 1)
    
    def test_error_and_warning_handling(self):
        """测试错误和警告处理"""
        stage = self.result.add_stage("test_stage")
        
        # 添加阶段错误和警告
        stage.add_error("阶段错误1")
        stage.add_warning("阶段警告1")
        
        # 添加全局错误和警告
        self.result.add_global_error("全局错误1")
        self.result.add_global_warning("全局警告1")
        
        # 验证计数
        self.assertEqual(self.result.get_total_error_count(), 2)
        self.assertEqual(self.result.get_total_warning_count(), 2)
    
    def test_summary_and_report(self):
        """测试摘要和报告生成"""
        # 添加一些测试数据
        self.result.total_packets_input = 1000
        self.result.total_packets_output = 950
        self.result.total_bytes_input = 100000
        self.result.total_bytes_output = 80000
        
        stage = self.result.add_stage("test_stage")
        stage.mark_completed(processed_packets=1000)
        
        self.result.mark_completed()
        
        # 测试摘要
        summary = self.result.get_summary()
        self.assertTrue(summary['success'])
        self.assertEqual(summary['total_packets_input'], 1000)
        self.assertEqual(summary['stages_completed'], 1)
        self.assertEqual(summary['stages_total'], 1)
        
        # 测试详细报告
        report = self.result.get_detailed_report()
        self.assertIn('summary', report)
        self.assertIn('config', report)
        self.assertIn('stages', report)
        self.assertIn('timestamps', report)
    
    def test_failed_execution(self):
        """测试失败执行"""
        stage1 = self.result.add_stage("stage1")
        stage1.mark_completed()
        
        stage2 = self.result.add_stage("stage2") 
        stage2.mark_failed("阶段2失败")
        
        # 整体执行失败，因为有失败的阶段
        self.result.mark_completed()
        self.assertFalse(self.result.is_successful())
        
        failed_stages = self.result.get_failed_stages()
        self.assertEqual(len(failed_stages), 1)
        self.assertEqual(failed_stages[0], "stage2")


if __name__ == '__main__':
    unittest.main() 