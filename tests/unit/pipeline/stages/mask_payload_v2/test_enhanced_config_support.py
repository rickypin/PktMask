"""
NewMaskPayloadStage 增强配置格式支持测试

测试新一代掩码处理阶段对各种配置格式的支持，包括：
- TLS 特定配置格式（YAML）
- GUI 配置格式
- 复杂配置结构
- 废弃参数处理
"""

import pytest
from unittest.mock import Mock, patch

from pktmask.core.pipeline.stages.mask_payload_v2.stage import NewMaskPayloadStage


class TestEnhancedConfigSupport:
    """增强配置格式支持测试"""
    
    def test_tls_yaml_config_conversion(self):
        """测试 TLS YAML 配置格式转换"""
        config = {
            'tls_20_strategy': 'keep_all',
            'tls_21_strategy': 'keep_all',
            'tls_22_strategy': 'keep_all',
            'tls_23_strategy': 'mask_payload',
            'tls_23_header_preserve_bytes': 5,
            'tls_24_strategy': 'keep_all',
            'non_tls_tcp_strategy': 'mask_all_payload',
            'enable_non_tls_tcp_masking': True,
            'chunk_size': 2000,
            'verify_checksums': False,
            'enable_performance_monitoring': True,
            'keep_intermediate_files': True,
            'temp_dir': '/tmp/pktmask'
        }
        
        stage = NewMaskPayloadStage(config)
        
        # 验证协议设置
        assert stage.protocol == 'tls'
        
        # 验证 marker 配置转换
        marker_config = stage.normalized_config['marker_config']
        assert 'tls' in marker_config
        
        tls_config = marker_config['tls']
        assert tls_config['preserve_change_cipher_spec'] is True  # tls_20_strategy: keep_all
        assert tls_config['preserve_alert'] is True  # tls_21_strategy: keep_all
        assert tls_config['preserve_handshake'] is True  # tls_22_strategy: keep_all
        assert tls_config['preserve_application_data'] is False  # tls_23_strategy: mask_payload
        assert tls_config['application_data_header_bytes'] == 5
        assert tls_config['preserve_heartbeat'] is True  # tls_24_strategy: keep_all
        
        # 验证 TCP 配置
        assert 'tcp' in marker_config
        assert marker_config['tcp']['mask_non_tls_payload'] is True
        
        # 验证 masker 配置转换
        masker_config = stage.normalized_config['masker_config']
        assert masker_config['chunk_size'] == 2000
        assert masker_config['verify_checksums'] is False
        assert masker_config['enable_performance_monitoring'] is True
        assert masker_config['keep_intermediate_files'] is True
        assert masker_config['temp_dir'] == '/tmp/pktmask'
    
    def test_gui_config_conversion_enabled(self):
        """测试 GUI 配置格式转换（启用掩码）"""
        config = {
            'enable_anon': True,
            'enable_dedup': True,
            'enable_mask': True
        }
        
        stage = NewMaskPayloadStage(config)
        
        # 启用掩码时应该使用 enhanced 模式
        assert stage.mode == 'enhanced'
        assert stage.protocol == 'tls'
        
        # 应该有默认的 marker 配置
        marker_config = stage.normalized_config['marker_config']
        assert 'tls' in marker_config
        assert marker_config['tls']['preserve_handshake'] is True
        assert marker_config['tls']['preserve_application_data'] is False
    
    def test_gui_config_conversion_disabled(self):
        """测试 GUI 配置格式转换（禁用掩码）"""
        config = {
            'enable_anon': True,
            'enable_dedup': True,
            'enable_mask': False
        }
        
        stage = NewMaskPayloadStage(config)
        
        # 禁用掩码时应该使用 basic 模式
        assert stage.mode == 'basic'
        assert stage.protocol == 'tls'
    
    def test_recipe_path_deprecation_handling(self):
        """测试废弃的 recipe_path 参数处理"""
        config = {
            'recipe_path': '/path/to/old/recipe.json',
            'mode': 'enhanced'
        }
        
        stage = NewMaskPayloadStage(config)
        
        # recipe_path 应该被移除
        assert 'recipe_path' not in stage.normalized_config
        
        # 应该使用默认配置
        assert stage.protocol == 'tls'
        assert stage.mode == 'enhanced'
    
    def test_unknown_mode_handling(self):
        """测试未知模式处理"""
        config = {
            'mode': 'unknown_mode'
        }
        
        stage = NewMaskPayloadStage(config)
        
        # 未知模式应该降级到 enhanced
        assert stage.mode == 'enhanced'
        assert stage.normalized_config['mode'] == 'enhanced'
    
    def test_legacy_parameter_mapping(self):
        """测试旧版参数映射"""
        config = {
            'min_preserve_bytes': 200,
            'enable_tls_processing': False,
            'fallback_config': {
                'enable_fallback': True,
                'max_retries': 3
            }
        }

        stage = NewMaskPayloadStage(config)

        # 验证参数映射
        masker_config = stage.normalized_config['masker_config']
        assert masker_config['min_preserve_bytes'] == 200
        assert masker_config['fallback_config']['enable_fallback'] is True
        assert masker_config['fallback_config']['max_retries'] == 3

        marker_config = stage.normalized_config['marker_config']
        assert marker_config['enable_tls_processing'] is False
    
    def test_mixed_config_format(self):
        """测试混合配置格式"""
        config = {
            # 新格式
            'protocol': 'tls',
            'marker_config': {
                'tls': {
                    'preserve_handshake': False
                }
            },
            # TLS 配置
            'tls_23_header_preserve_bytes': 10
        }

        stage = NewMaskPayloadStage(config)

        # 新格式应该优先
        assert stage.protocol == 'tls'

        # TLS 配置应该被合并
        marker_config = stage.normalized_config['marker_config']
        assert marker_config['tls']['preserve_handshake'] is False  # 来自新格式
        assert marker_config['tls']['application_data_header_bytes'] == 10  # 来自 TLS 配置
    
    def test_empty_config_defaults(self):
        """测试空配置的默认值设置"""
        stage = NewMaskPayloadStage({})
        
        # 应该设置合理的默认值
        assert stage.protocol == 'tls'
        assert stage.mode == 'enhanced'
        
        marker_config = stage.normalized_config['marker_config']
        assert 'tls' in marker_config
        assert marker_config['tls']['preserve_handshake'] is True
        
        masker_config = stage.normalized_config['masker_config']
        assert masker_config['chunk_size'] == 1000
        assert masker_config['verify_checksums'] is True
    
    def test_complex_tls_config_edge_cases(self):
        """测试复杂 TLS 配置的边界情况"""
        config = {
            'tls_20_strategy': 'mask_all',  # 非标准策略
            'tls_21_strategy': 'keep_all',
            'tls_22_strategy': 'partial_keep',  # 非标准策略
            'tls_23_strategy': 'keep_all',  # 与通常不同
            'tls_24_strategy': 'mask_all',  # 非标准策略
            'tls_23_header_preserve_bytes': 0,  # 边界值
            'chunk_size': -1,  # 无效值
            'verify_checksums': 'invalid'  # 无效类型
        }
        
        stage = NewMaskPayloadStage(config)
        
        # 验证非标准策略的处理
        marker_config = stage.normalized_config['marker_config']
        tls_config = marker_config['tls']
        
        assert tls_config['preserve_change_cipher_spec'] is False  # mask_all -> False
        assert tls_config['preserve_alert'] is True  # keep_all -> True
        assert tls_config['preserve_handshake'] is False  # partial_keep -> False (非 keep_all)
        assert tls_config['preserve_application_data'] is True  # keep_all -> True
        assert tls_config['preserve_heartbeat'] is False  # mask_all -> False
        
        # 验证边界值处理
        assert tls_config['application_data_header_bytes'] == 0
        
        # 验证无效值的处理（应该使用默认值或保持原值）
        masker_config = stage.normalized_config['masker_config']
        assert masker_config['chunk_size'] == -1  # 保持原值，由验证器处理
        assert masker_config['verify_checksums'] == 'invalid'  # 保持原值，由验证器处理
    
    def test_config_conversion_logging(self):
        """测试配置转换过程的日志记录"""
        import logging

        # 使用 caplog 来捕获日志
        with patch('pktmask.core.pipeline.stages.mask_payload_v2.stage.logging.getLogger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            # 测试旧版配置转换日志
            config = {'recipe_dict': {'total_packets': 5}}
            stage = NewMaskPayloadStage(config)

            # 验证日志调用
            mock_logger.info.assert_any_call("Detected legacy configuration format, converting to new format")

            # 重置 mock
            mock_logger.reset_mock()

            # 测试废弃参数警告日志
            config = {'recipe_path': '/old/path'}
            stage = NewMaskPayloadStage(config)

            mock_logger.warning.assert_any_call("Detected deprecated recipe_path configuration, will ignore and use intelligent protocol analysis")
    
    def test_config_format_detection_priority(self):
        """测试配置格式检测优先级"""
        # 当多种格式同时存在时，应该按优先级处理
        config = {
            # 新格式（最高优先级）
            'protocol': 'tls',
            'marker_config': {'tls': {'preserve_handshake': False}},
            # 旧版配置
            'recipe_dict': {'total_packets': 10},
            # TLS 配置
            'tls_22_strategy': 'keep_all',
            # GUI 配置
            'enable_mask': True
        }
        
        stage = NewMaskPayloadStage(config)
        
        # 新格式应该优先，不应该触发旧版配置转换
        assert not stage.use_legacy_mode
        assert stage.protocol == 'tls'
        
        # 新格式的配置应该保持
        marker_config = stage.normalized_config['marker_config']
        assert marker_config['tls']['preserve_handshake'] is False
