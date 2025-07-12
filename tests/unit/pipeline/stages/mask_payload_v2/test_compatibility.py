"""
NewMaskPayloadStage 兼容性测试

验证新一代掩码处理阶段与现有 MaskPayloadStage 的接口兼容性。
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from pktmask.core.pipeline.stages.mask_payload_v2.stage import NewMaskPayloadStage
from pktmask.core.pipeline.stages.mask_payload.stage import MaskPayloadStage
from pktmask.core.pipeline.models import StageStats


class TestMaskPayloadStageCompatibility:
    """NewMaskPayloadStage 与 MaskPayloadStage 兼容性测试"""
    
    def test_interface_compatibility(self):
        """测试接口兼容性"""
        # 相同的配置应该在两个实现中都能工作
        config = {'mode': 'basic'}

        old_stage = MaskPayloadStage(config)
        new_stage = NewMaskPayloadStage(config)

        # 检查基本属性
        assert hasattr(old_stage, 'initialize')
        assert hasattr(new_stage, 'initialize')

        assert hasattr(old_stage, 'process_file')
        assert hasattr(new_stage, 'process_file')

        assert hasattr(old_stage, 'get_display_name')
        assert hasattr(new_stage, 'get_display_name')

        assert hasattr(old_stage, 'get_description')
        assert hasattr(new_stage, 'get_description')

        assert hasattr(old_stage, 'get_required_tools')
        assert hasattr(new_stage, 'get_required_tools')

        # 注意：旧版 MaskPayloadStage 没有 cleanup 方法，但新版有
        # 这是一个增强功能，不影响向后兼容性
        assert hasattr(new_stage, 'cleanup')
    
    def test_basic_mode_compatibility(self):
        """测试基础模式兼容性"""
        config = {'mode': 'basic'}

        new_stage = NewMaskPayloadStage(config)

        with tempfile.NamedTemporaryFile(suffix='.pcap') as input_file:
            with tempfile.NamedTemporaryFile(suffix='.pcap') as output_file_new:
                # 写入测试数据
                test_data = b'test pcap data for compatibility'
                input_file.write(test_data)
                input_file.flush()

                # 新版处理文件
                new_stats = new_stage.process_file(input_file.name, output_file_new.name)

                # 验证返回类型
                assert isinstance(new_stats, StageStats)

                # 验证文件被正确复制
                output_file_new.seek(0)
                new_content = output_file_new.read()

                assert new_content == test_data

                # 验证基础模式的特征
                assert new_stats.extra_metrics['mode'] == 'basic'
                assert new_stats.extra_metrics['operation'] == 'passthrough_copy'
    
    def test_enhanced_mode_config_compatibility(self):
        """测试增强模式配置兼容性"""
        # 旧版配置格式
        config = {'mode': 'enhanced'}
        
        old_stage = MaskPayloadStage(config)
        new_stage = NewMaskPayloadStage(config)
        
        # 两个实现都应该能够处理相同的配置
        assert old_stage.config == new_stage.config
        
        # 新实现应该正确转换配置
        assert new_stage.mode == 'enhanced'
        assert new_stage.protocol == 'tls'  # 默认协议
    
    def test_processor_adapter_mode_compatibility(self):
        """测试 processor_adapter 模式兼容性"""
        config = {'mode': 'processor_adapter'}
        
        old_stage = MaskPayloadStage(config)
        new_stage = NewMaskPayloadStage(config)
        
        # 新实现应该将 processor_adapter 转换为 enhanced
        assert new_stage.mode == 'enhanced'
        assert new_stage.normalized_config['mode'] == 'enhanced'
    
    def test_recipe_config_compatibility(self):
        """测试配方配置兼容性"""
        from pktmask.core.tcp_payload_masker.api.types import MaskingRecipe
        
        recipe = MaskingRecipe(total_packets=5)
        config = {
            'mode': 'enhanced',
            'recipe': recipe
        }
        
        old_stage = MaskPayloadStage(config)
        new_stage = NewMaskPayloadStage(config)
        
        # 两个实现都应该能够处理配方配置
        assert old_stage.config == new_stage.config
        
        # 新实现应该识别为旧版模式
        assert new_stage.use_legacy_mode
        assert new_stage.legacy_recipe == recipe
    
    def test_recipe_dict_config_compatibility(self):
        """测试配方字典配置兼容性"""
        recipe_dict = {
            'total_packets': 3,
            'instructions': [
                {
                    'packet_index': 0,
                    'mask_spec_type': 'KeepAll',
                    'mask_spec_params': {}
                }
            ]
        }
        config = {
            'mode': 'enhanced',
            'recipe_dict': recipe_dict
        }
        
        old_stage = MaskPayloadStage(config)
        new_stage = NewMaskPayloadStage(config)
        
        # 两个实现都应该能够处理配方字典配置
        assert old_stage.config == new_stage.config
        
        # 新实现应该识别为旧版模式
        assert new_stage.use_legacy_mode
        assert new_stage.legacy_recipe_dict == recipe_dict
    
    def test_display_name_compatibility(self):
        """测试显示名称兼容性"""
        old_stage = MaskPayloadStage({})
        new_stage = NewMaskPayloadStage({})
        
        old_name = old_stage.get_display_name()
        new_name = new_stage.get_display_name()
        
        # 显示名称应该相似但可以有版本区别
        assert 'Mask' in old_name
        assert 'Mask' in new_name
        assert 'Payload' in old_name or 'Payload' in new_name
    
    def test_required_tools_compatibility(self):
        """测试所需工具兼容性"""
        config = {'protocol': 'tls'}
        
        old_stage = MaskPayloadStage(config)
        new_stage = NewMaskPayloadStage(config)
        
        old_tools = old_stage.get_required_tools()
        new_tools = new_stage.get_required_tools()
        
        # 新实现应该包含旧实现的所有必需工具
        # 注意：这里我们只检查基本的工具需求
        assert isinstance(old_tools, list)
        assert isinstance(new_tools, list)
        
        # scapy 是两个实现都需要的
        assert 'scapy' in new_tools
    
    def test_initialization_compatibility(self):
        """测试初始化兼容性"""
        config = {'mode': 'basic'}
        
        old_stage = MaskPayloadStage(config)
        new_stage = NewMaskPayloadStage(config)
        
        # 两个实现都应该能够成功初始化
        old_result = old_stage.initialize()
        new_result = new_stage.initialize()
        
        assert old_result is True
        assert new_result is True
        
        assert old_stage.is_initialized
        assert new_stage.is_initialized
    
    def test_cleanup_compatibility(self):
        """测试清理兼容性"""
        new_stage = NewMaskPayloadStage({})

        # 新版实现应该能够安全清理
        new_stage.cleanup()

        # 清理后应该重置初始化状态
        assert not new_stage.is_initialized

        # 注意：旧版 MaskPayloadStage 没有 cleanup 方法
        # 这是新版的增强功能，不影响向后兼容性
    
    def test_error_handling_compatibility(self):
        """测试错误处理兼容性"""
        config = {'mode': 'enhanced'}
        
        old_stage = MaskPayloadStage(config)
        new_stage = NewMaskPayloadStage(config)
        
        # 测试无效输入的错误处理
        with pytest.raises((FileNotFoundError, RuntimeError, ValueError)):
            old_stage.process_file('/nonexistent/input.pcap', '/tmp/output.pcap')
        
        with pytest.raises((FileNotFoundError, RuntimeError, ValueError)):
            new_stage.process_file('/nonexistent/input.pcap', '/tmp/output.pcap')
    
    def test_stage_stats_compatibility(self):
        """测试统计信息兼容性"""
        config = {'mode': 'basic'}
        
        new_stage = NewMaskPayloadStage(config)
        
        with tempfile.NamedTemporaryFile(suffix='.pcap') as input_file:
            with tempfile.NamedTemporaryFile(suffix='.pcap') as output_file:
                # 写入测试数据
                input_file.write(b'test data')
                input_file.flush()
                
                # 处理文件
                stats = new_stage.process_file(input_file.name, output_file.name)
                
                # 验证 StageStats 结构
                assert hasattr(stats, 'stage_name')
                assert hasattr(stats, 'packets_processed')
                assert hasattr(stats, 'packets_modified')
                assert hasattr(stats, 'duration_ms')
                assert hasattr(stats, 'extra_metrics')
                
                # 验证基本字段类型
                assert isinstance(stats.stage_name, str)
                assert isinstance(stats.packets_processed, int)
                assert isinstance(stats.packets_modified, int)
                assert isinstance(stats.duration_ms, (int, float))
                assert isinstance(stats.extra_metrics, dict)
