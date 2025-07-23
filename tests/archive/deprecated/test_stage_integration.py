"""
NewMaskPayloadStage 集成测试

测试新一代掩码处理阶段的集成功能，包括：
- 配置格式转换和向后兼容性
- 双模块架构集成
- 各种处理模式
- 接口兼容性
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from pktmask.core.pipeline.stages.mask_payload_v2.stage import NewMaskPayloadStage
from pktmask.core.pipeline.models import StageStats


class TestNewMaskPayloadStageIntegration:
    """NewMaskPayloadStage 集成测试"""
    
    def test_new_format_config(self):
        """测试新格式配置"""
        config = {
            'protocol': 'tls',
            'mode': 'enhanced',
            'marker_config': {
                'tls': {
                    'preserve_handshake': True,
                    'preserve_application_data': False
                }
            },
            'masker_config': {
                'chunk_size': 1000,
                'verify_checksums': True
            }
        }
        
        stage = NewMaskPayloadStage(config)
        
        assert stage.protocol == 'tls'
        assert stage.mode == 'enhanced'
        assert not stage.use_legacy_mode
        assert stage.marker_config == config['marker_config']
        assert stage.masker_config == config['masker_config']
    
    def test_legacy_recipe_config(self):
        """测试旧版配方配置"""
        from pktmask.core.tcp_payload_masker.api.types import MaskingRecipe
        
        recipe = MaskingRecipe(total_packets=10)
        config = {
            'mode': 'enhanced',
            'recipe': recipe
        }
        
        stage = NewMaskPayloadStage(config)
        
        assert stage.use_legacy_mode
        assert stage.legacy_recipe == recipe
        assert stage.protocol == 'tls'  # 默认协议
    
    def test_legacy_recipe_dict_config(self):
        """测试旧版配方字典配置"""
        recipe_dict = {
            'total_packets': 5,
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
        
        stage = NewMaskPayloadStage(config)
        
        assert stage.use_legacy_mode
        assert stage.legacy_recipe_dict == recipe_dict
        assert stage.protocol == 'tls'  # 默认协议
    
    def test_processor_adapter_mode_conversion(self):
        """测试 processor_adapter 模式转换"""
        config = {
            'mode': 'processor_adapter'
        }
        
        stage = NewMaskPayloadStage(config)
        
        # processor_adapter 应该转换为 enhanced
        assert stage.mode == 'enhanced'
        assert stage.normalized_config['mode'] == 'enhanced'
    
    def test_basic_mode_config(self):
        """测试基础模式配置"""
        config = {
            'mode': 'basic'
        }
        
        stage = NewMaskPayloadStage(config)
        
        assert stage.mode == 'basic'
        assert not stage.use_legacy_mode
    
    @patch('pktmask.core.pipeline.stages.mask_payload_v2.stage.NewMaskPayloadStage._create_marker')
    @patch('pktmask.core.pipeline.stages.mask_payload_v2.stage.NewMaskPayloadStage._create_masker')
    def test_initialization_success(self, mock_create_masker, mock_create_marker):
        """测试成功初始化"""
        # 模拟 marker 和 masker
        mock_marker = Mock()
        mock_marker.initialize.return_value = True
        mock_create_marker.return_value = mock_marker
        
        mock_masker = Mock()
        mock_create_masker.return_value = mock_masker
        
        config = {'mode': 'enhanced'}
        stage = NewMaskPayloadStage(config)
        
        result = stage.initialize()
        
        assert result is True
        assert stage.is_initialized
        assert stage.marker == mock_marker
        assert stage.masker == mock_masker
        mock_marker.initialize.assert_called_once()
    
    @patch('pktmask.core.pipeline.stages.mask_payload_v2.stage.NewMaskPayloadStage._create_marker')
    def test_initialization_marker_failure(self, mock_create_marker):
        """测试 Marker 初始化失败"""
        mock_marker = Mock()
        mock_marker.initialize.return_value = False
        mock_create_marker.return_value = mock_marker
        
        config = {'mode': 'enhanced'}
        stage = NewMaskPayloadStage(config)
        
        result = stage.initialize()
        
        assert result is False
        assert not stage.is_initialized
    
    def test_basic_mode_processing(self):
        """测试基础模式处理"""
        config = {'mode': 'basic'}
        stage = NewMaskPayloadStage(config)
        
        with tempfile.NamedTemporaryFile(suffix='.pcap') as input_file:
            with tempfile.NamedTemporaryFile(suffix='.pcap') as output_file:
                # 写入一些测试数据
                input_file.write(b'test pcap data')
                input_file.flush()
                
                # 处理文件
                stats = stage.process_file(input_file.name, output_file.name)
                
                # 验证结果
                assert isinstance(stats, StageStats)
                assert stats.stage_name == "Mask Payloads (v2)"
                assert stats.extra_metrics['mode'] == 'basic'
                assert stats.extra_metrics['operation'] == 'passthrough_copy'
                assert stats.extra_metrics['success'] is True
                
                # 验证文件被复制
                output_file.seek(0)
                assert output_file.read() == b'test pcap data'
    
    def test_get_display_name(self):
        """测试显示名称"""
        stage = NewMaskPayloadStage({})
        assert stage.get_display_name() == "Mask Payloads (v2)"
    
    def test_get_description(self):
        """测试描述信息"""
        config = {'protocol': 'tls', 'mode': 'enhanced'}
        stage = NewMaskPayloadStage(config)
        
        description = stage.get_description()
        assert 'tls' in description.lower()
        assert 'enhanced' in description.lower()
        assert '双模块架构' in description
    
    def test_get_required_tools(self):
        """测试所需工具列表"""
        # TLS 协议需要 tshark
        config = {'protocol': 'tls'}
        stage = NewMaskPayloadStage(config)
        tools = stage.get_required_tools()
        
        assert 'scapy' in tools
        assert 'tshark' in tools
        
        # HTTP 协议不需要 tshark（如果支持的话）
        config = {'protocol': 'http'}
        stage = NewMaskPayloadStage(config)
        tools = stage.get_required_tools()
        
        assert 'scapy' in tools
    
    def test_cleanup(self):
        """测试资源清理"""
        mock_marker = Mock()
        mock_masker = Mock()
        
        stage = NewMaskPayloadStage({})
        stage.marker = mock_marker
        stage.masker = mock_masker
        stage._initialized = True
        
        stage.cleanup()
        
        mock_marker.cleanup.assert_called_once()
        assert not stage.is_initialized
    
    def test_config_validation_enabled(self):
        """测试配置验证启用"""
        config = {
            'mode': 'debug',  # debug 模式应该启用配置验证
            'protocol': 'tls'
        }
        
        stage = NewMaskPayloadStage(config)
        
        # debug 模式应该启用配置验证
        assert stage._should_validate_config()
    
    def test_config_validation_disabled(self):
        """测试配置验证禁用"""
        config = {
            'mode': 'enhanced',
            'protocol': 'tls'
        }
        
        stage = NewMaskPayloadStage(config)
        
        # 普通模式默认不启用配置验证
        assert not stage._should_validate_config()
    
    def test_empty_config_normalization(self):
        """测试空配置的标准化"""
        stage = NewMaskPayloadStage({})
        
        # 应该设置默认值
        assert stage.protocol == 'tls'
        assert stage.mode == 'enhanced'
        assert isinstance(stage.marker_config, dict)
        assert isinstance(stage.masker_config, dict)
