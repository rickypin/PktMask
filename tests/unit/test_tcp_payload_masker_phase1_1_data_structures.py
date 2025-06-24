"""
TCP载荷掩码器Phase 1.1测试: 核心数据结构

测试PacketMaskInstruction、MaskingRecipe、PacketMaskingResult等核心数据结构的功能。
"""

import pytest
from typing import Dict, Tuple

from src.pktmask.core.tcp_payload_masker.api.types import (
    PacketMaskInstruction,
    MaskingRecipe,
    PacketMaskingResult,
    MaskingStatistics
)
from src.pktmask.core.trim.models.mask_spec import MaskAfter, MaskRange, KeepAll


class TestPacketMaskInstruction:
    """测试PacketMaskInstruction数据结构"""
    
    def test_valid_instruction_creation(self):
        """测试创建有效的包掩码指令"""
        mask_spec = MaskAfter(keep_bytes=10)
        instruction = PacketMaskInstruction(
            packet_index=5,
            packet_timestamp="1234567890.123456789",
            payload_offset=42,
            mask_spec=mask_spec,
            metadata={"test": "data"}
        )
        
        assert instruction.packet_index == 5
        assert instruction.packet_timestamp == "1234567890.123456789"
        assert instruction.payload_offset == 42
        assert instruction.mask_spec == mask_spec
        assert instruction.metadata == {"test": "data"}
    
    def test_instruction_validation_negative_index(self):
        """测试负数包索引验证"""
        with pytest.raises(ValueError, match="packet_index必须为非负数"):
            PacketMaskInstruction(
                packet_index=-1,
                packet_timestamp="123.456",
                payload_offset=0,
                mask_spec=KeepAll()
            )
    
    def test_instruction_validation_negative_offset(self):
        """测试负数偏移量验证"""
        with pytest.raises(ValueError, match="payload_offset必须为非负数"):
            PacketMaskInstruction(
                packet_index=0,
                packet_timestamp="123.456", 
                payload_offset=-1,
                mask_spec=KeepAll()
            )
    
    def test_instruction_validation_invalid_timestamp(self):
        """测试无效时间戳验证"""
        with pytest.raises(ValueError, match="packet_timestamp必须为字符串"):
            PacketMaskInstruction(
                packet_index=0,
                packet_timestamp=123.456,  # 应该是字符串
                payload_offset=0,
                mask_spec=KeepAll()
            )
    
    def test_instruction_default_metadata(self):
        """测试默认元数据"""
        instruction = PacketMaskInstruction(
            packet_index=0,
            packet_timestamp="123.456",
            payload_offset=0,
            mask_spec=KeepAll()
        )
        
        assert instruction.metadata == {}


class TestMaskingRecipe:
    """测试MaskingRecipe数据结构"""
    
    def test_valid_recipe_creation(self):
        """测试创建有效的掩码配方"""
        instruction1 = PacketMaskInstruction(
            packet_index=0, packet_timestamp="100.0", 
            payload_offset=40, mask_spec=MaskAfter(5)
        )
        instruction2 = PacketMaskInstruction(
            packet_index=1, packet_timestamp="101.0",
            payload_offset=42, mask_spec=KeepAll()
        )
        
        instructions = {
            (0, "100.0"): instruction1,
            (1, "101.0"): instruction2
        }
        
        recipe = MaskingRecipe(
            instructions=instructions,
            total_packets=2,
            metadata={"source": "test"}
        )
        
        assert recipe.total_packets == 2
        assert len(recipe.instructions) == 2
        assert recipe.metadata["source"] == "test"
    
    def test_recipe_validation_negative_total_packets(self):
        """测试负数总包数验证"""
        with pytest.raises(ValueError, match="total_packets必须为非负数"):
            MaskingRecipe(
                instructions={},
                total_packets=-1
            )
    
    def test_recipe_validation_invalid_instructions(self):
        """测试无效指令验证"""
        with pytest.raises(ValueError, match="instructions必须为字典类型"):
            MaskingRecipe(
                instructions="invalid",  # 应该是字典
                total_packets=0
            )
    
    def test_recipe_validation_index_out_of_range(self):
        """测试超出范围的包索引验证"""
        instruction = PacketMaskInstruction(
            packet_index=5, packet_timestamp="100.0",
            payload_offset=0, mask_spec=KeepAll()
        )
        
        with pytest.raises(ValueError, match="指令包索引5超出总包数2"):
            MaskingRecipe(
                instructions={(5, "100.0"): instruction},
                total_packets=2
            )
    
    def test_recipe_validation_inconsistent_index(self):
        """测试不一致的包索引验证"""
        instruction = PacketMaskInstruction(
            packet_index=1, packet_timestamp="100.0",
            payload_offset=0, mask_spec=KeepAll()
        )
        
        with pytest.raises(ValueError, match="指令键索引0与指令内索引1不一致"):
            MaskingRecipe(
                instructions={(0, "100.0"): instruction},  # 键索引是0，但指令内是1
                total_packets=2
            )
    
    def test_recipe_validation_inconsistent_timestamp(self):
        """测试不一致的时间戳验证"""
        instruction = PacketMaskInstruction(
            packet_index=0, packet_timestamp="101.0",
            payload_offset=0, mask_spec=KeepAll()
        )
        
        with pytest.raises(ValueError, match="指令键时间戳100.0与指令内时间戳101.0不一致"):
            MaskingRecipe(
                instructions={(0, "100.0"): instruction},  # 键时间戳是100.0，但指令内是101.0
                total_packets=2
            )
    
    def test_recipe_methods(self):
        """测试配方的方法"""
        instruction = PacketMaskInstruction(
            packet_index=0, packet_timestamp="100.0",
            payload_offset=0, mask_spec=KeepAll()
        )
        
        recipe = MaskingRecipe(
            instructions={(0, "100.0"): instruction},
            total_packets=1
        )
        
        # 测试get_instruction_count
        assert recipe.get_instruction_count() == 1
        
        # 测试get_instruction_for_packet
        found = recipe.get_instruction_for_packet(0, "100.0")
        assert found == instruction
        
        not_found = recipe.get_instruction_for_packet(1, "200.0")
        assert not_found is None
        
        # 测试has_instruction_for_packet
        assert recipe.has_instruction_for_packet(0, "100.0") is True
        assert recipe.has_instruction_for_packet(1, "200.0") is False


class TestMaskingStatistics:
    """测试MaskingStatistics数据结构"""
    
    def test_statistics_creation(self):
        """测试统计信息创建"""
        stats = MaskingStatistics()
        
        assert stats.processed_packets == 0
        assert stats.modified_packets == 0
        assert stats.skipped_packets == 0
        assert stats.error_packets == 0
        assert stats.total_bytes_processed == 0
        assert stats.total_bytes_masked == 0
        assert stats.processing_time_seconds == 0.0
    
    def test_statistics_to_dict(self):
        """测试统计信息转换为字典"""
        stats = MaskingStatistics()
        stats.processed_packets = 100
        stats.modified_packets = 50
        
        stats_dict = stats.to_dict()
        
        assert stats_dict["processed_packets"] == 100
        assert stats_dict["modified_packets"] == 50
        assert stats_dict["modification_rate"] == 50.0


class TestPacketMaskingResult:
    """测试PacketMaskingResult数据结构"""
    
    def test_valid_result_creation(self):
        """测试创建有效的处理结果"""
        result = PacketMaskingResult(
            success=True,
            processed_packets=100,
            modified_packets=50,
            output_file="/path/to/output.pcap",
            errors=[],
            statistics={"rate": 50.0},
            execution_time=1.5
        )
        
        assert result.success is True
        assert result.processed_packets == 100
        assert result.modified_packets == 50
        assert result.output_file == "/path/to/output.pcap"
        assert result.execution_time == 1.5
    
    def test_result_validation_negative_processed(self):
        """测试负数处理包数验证"""
        with pytest.raises(ValueError, match="processed_packets必须为非负数"):
            PacketMaskingResult(
                success=True,
                processed_packets=-1,
                modified_packets=0,
                output_file=""
            )
    
    def test_result_validation_negative_modified(self):
        """测试负数修改包数验证"""
        with pytest.raises(ValueError, match="modified_packets必须为非负数"):
            PacketMaskingResult(
                success=True,
                processed_packets=100,
                modified_packets=-1,
                output_file=""
            )
    
    def test_result_validation_modified_exceeds_processed(self):
        """测试修改包数超过处理包数验证"""
        with pytest.raises(ValueError, match="modified_packets.*不能大于.*processed_packets"):
            PacketMaskingResult(
                success=True,
                processed_packets=50,
                modified_packets=100,  # 修改包数不能大于处理包数
                output_file=""
            )
    
    def test_result_methods(self):
        """测试结果对象的方法"""
        result = PacketMaskingResult(
            success=True,
            processed_packets=100,
            modified_packets=25,
            output_file="test.pcap"
        )
        
        # 测试get_modification_rate
        assert result.get_modification_rate() == 25.0
        
        # 测试is_successful
        assert result.is_successful() is True
        
        # 测试add_error
        result.add_error("测试错误")
        assert len(result.errors) == 1
        assert result.success is False
        assert result.is_successful() is False
        
        # 测试get_summary
        summary = result.get_summary()
        assert "错误数: 1" in summary
    
    def test_result_zero_processed_packets(self):
        """测试零处理包数的情况"""
        result = PacketMaskingResult(
            success=True,
            processed_packets=0,
            modified_packets=0,
            output_file=""
        )
        
        assert result.get_modification_rate() == 0.0


class TestDataStructureIntegration:
    """测试数据结构的集成使用"""
    
    def test_complete_workflow_data_structures(self):
        """测试完整工作流程中的数据结构使用"""
        # 创建掩码指令
        instruction1 = PacketMaskInstruction(
            packet_index=0,
            packet_timestamp="1000.123",
            payload_offset=42,
            mask_spec=MaskAfter(keep_bytes=5),
            metadata={"tcp_stream": "192.168.1.1:80"}
        )
        
        instruction2 = PacketMaskInstruction(
            packet_index=2,
            packet_timestamp="1002.456",
            payload_offset=44,
            mask_spec=MaskRange(ranges=[(10, 20), (30, 40)]),
            metadata={"tcp_stream": "192.168.1.2:443"}
        )
        
        # 创建掩码配方
        recipe = MaskingRecipe(
            instructions={
                (0, "1000.123"): instruction1,
                (2, "1002.456"): instruction2
            },
            total_packets=5,
            metadata={
                "source": "pyshark_analyzer",
                "version": "1.0",
                "creation_time": "2024-01-01T00:00:00Z"
            }
        )
        
        # 验证配方
        assert recipe.get_instruction_count() == 2
        assert recipe.has_instruction_for_packet(0, "1000.123")
        assert recipe.has_instruction_for_packet(2, "1002.456")
        assert not recipe.has_instruction_for_packet(1, "1001.0")
        
        # 创建处理结果
        result = PacketMaskingResult(
            success=True,
            processed_packets=5,
            modified_packets=2,
            output_file="/tmp/masked_output.pcap",
            statistics={
                "processing_time": 0.5,
                "modification_rate": 40.0
            }
        )
        
        assert result.get_modification_rate() == 40.0
        assert result.is_successful()
        
        # 测试集成使用场景
        summary = result.get_summary()
        assert "成功处理5个包" in summary
        assert "修改2个包" in summary 