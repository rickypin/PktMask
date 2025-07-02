"""
Phase 2 Day 10: 配置系统集成测试

验证TShark增强掩码处理器配置系统的无缝集成：
1. 配置文件加载测试
2. TShark增强配置读取测试  
3. 处理器配置集成测试
4. 降级机制配置测试
5. 配置系统兼容性测试

作者: PktMask Team
创建时间: 2025-01-22 (Phase 2 Day 10)
"""

import pytest
import tempfile
import yaml
import os
from pathlib import Path
from unittest.mock import patch

import sys
from pathlib import Path

# 添加src目录到Python路径
src_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

from pktmask.config.settings import (
    AppConfig, TSharkEnhancedSettings, FallbackConfig
)
from pktmask.core.processors.tshark_enhanced_mask_processor import (
    TSharkEnhancedMaskProcessor, FallbackMode
)
from pktmask.core.processors.base_processor import ProcessorConfig


class TestPhase2Day10ConfigIntegration:
    """Phase 2 Day 10: 配置系统集成测试套件"""
    
    def setup_method(self):
        """测试设置"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.config_file = self.temp_dir / "test_config.yaml"
        
    def teardown_method(self):
        """测试清理"""
        import shutil
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def test_tshark_enhanced_config_loading(self):
        """测试1: TShark增强配置加载"""
        # 创建测试配置
        config_data = {
            'tools': {
                'tshark_enhanced': {
                    'enable_tls_processing': False,
                    'enable_cross_segment_detection': False,
                    'tls_23_strategy': 'keep_all',
                    'tls_23_header_preserve_bytes': 10,
                    'chunk_size': 2000,
                    'enable_detailed_logging': True,
                    'fallback_config': {
                        'enable_fallback': False,
                        'max_retries': 5,
                        'retry_delay_seconds': 2.5,
                        'preferred_fallback_order': ['mask_stage']
                    }
                }
            }
        }
        
        # 保存配置文件
        with open(self.config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        # 加载配置
        app_config = AppConfig.load(self.config_file)
        
        # 验证TShark增强配置
        enhanced = app_config.tools.tshark_enhanced
        assert enhanced.enable_tls_processing == False
        assert enhanced.enable_cross_segment_detection == False
        assert enhanced.tls_23_strategy == 'keep_all'
        assert enhanced.tls_23_header_preserve_bytes == 10
        assert enhanced.chunk_size == 2000
        assert enhanced.enable_detailed_logging == True
        
        # 验证降级配置
        fallback = enhanced.fallback_config
        assert fallback.enable_fallback == False
        assert fallback.max_retries == 5
        assert fallback.retry_delay_seconds == 2.5
        assert fallback.preferred_fallback_order == ['mask_stage']
        
        print("✅ TShark增强配置加载测试通过")
    
    def test_processor_config_integration(self):
        """测试2: 处理器配置集成"""
        # 创建测试配置
        config_data = {
            'tools': {
                'tshark_enhanced': {
                    'enable_tls_processing': True,
                    'tls_23_strategy': 'mask_payload',
                    'tls_23_header_preserve_bytes': 5,
                    'fallback_config': {
                        'enable_fallback': True,
                        'preferred_fallback_order': ['enhanced_trimmer', 'mask_stage']
                    }
                }
            }
        }
        
        # 保存配置文件
        with open(self.config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        # Mock get_app_config以返回测试配置
        test_app_config = AppConfig.load(self.config_file)
        
        with patch('pktmask.config.settings.get_app_config', return_value=test_app_config):
            # 创建处理器配置
            processor_config = ProcessorConfig(
                enabled=True,
                name="test_tshark_enhanced",
                priority=1
            )
            
            # 创建处理器实例
            processor = TSharkEnhancedMaskProcessor(processor_config)
            
            # 验证配置加载
            enhanced_config = processor.enhanced_config
            assert enhanced_config.enable_tls_processing == True
            assert enhanced_config.tls_23_strategy == 'mask_payload'
            assert enhanced_config.tls_23_header_preserve_bytes == 5
            assert enhanced_config.fallback_config.enable_fallback == True
            
        print("✅ 处理器配置集成测试通过")
    
    def test_config_dictionary_access(self):
        """测试3: 配置字典访问方法"""
        config_data = {
            'tools': {
                'tshark_enhanced': {
                    'enable_tls_processing': False,
                    'tls_23_strategy': 'keep_all',
                    'chunk_size': 800,
                    'fallback_config': {
                        'enable_fallback': False,
                        'max_retries': 1
                    }
                }
            }
        }
        
        with open(self.config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        app_config = AppConfig.load(self.config_file)
        
        # 测试新的配置访问方法
        enhanced_config_dict = app_config.get_tshark_enhanced_config()
        
        assert enhanced_config_dict['enable_tls_processing'] == False
        assert enhanced_config_dict['tls_23_strategy'] == 'keep_all'
        assert enhanced_config_dict['chunk_size'] == 800
        assert enhanced_config_dict['fallback_enable_fallback'] == False
        assert enhanced_config_dict['fallback_max_retries'] == 1
        
        # 验证所有必需的键都存在
        expected_keys = [
            'enable_tls_processing', 'enable_cross_segment_detection', 'enable_boundary_safety',
            'tls_20_strategy', 'tls_21_strategy', 'tls_22_strategy', 'tls_23_strategy', 'tls_24_strategy',
            'tls_23_header_preserve_bytes', 'temp_dir', 'cleanup_temp_files',
            'fallback_enable_fallback', 'fallback_max_retries'
        ]
        
        for key in expected_keys:
            assert key in enhanced_config_dict, f"缺少配置键: {key}"
        
        print("✅ 配置字典访问方法测试通过")
    
    def test_default_config_fallback(self):
        """测试4: 默认配置回退机制"""
        # 测试不存在的配置文件
        non_existent_config = self.temp_dir / "non_existent.yaml"
        app_config = AppConfig.load(non_existent_config)
        
        # 验证使用默认配置
        enhanced = app_config.tools.tshark_enhanced
        assert enhanced.enable_tls_processing == True  # 默认值
        assert enhanced.tls_23_strategy == 'mask_payload'  # 默认值
        assert enhanced.fallback_config.enable_fallback == True  # 默认值
        
        print("✅ 默认配置回退机制测试通过")
    
    def test_config_validation(self):
        """测试5: 配置验证"""
        # 创建复杂配置
        config_data = {
            'ui': {
                'theme': 'dark',
                'window_width': 1400
            },
            'processing': {
                'chunk_size': 20,
                'timeout_seconds': 600
            },
            'tools': {
                'tshark_enhanced': {
                    'enable_tls_processing': True,
                    'chunk_size': 1500,
                    'fallback_config': {
                        'max_retries': 3,
                        'tshark_check_timeout': 10.0
                    }
                }
            }
        }
        
        with open(self.config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        # 加载和验证配置
        app_config = AppConfig.load(self.config_file)
        is_valid, errors = app_config.validate()
        
        assert is_valid, f"配置验证失败: {errors}"
        
        # 验证各部分配置
        assert app_config.ui.theme == 'dark'
        assert app_config.processing.chunk_size == 20
        assert app_config.tools.tshark_enhanced.chunk_size == 1500
        assert app_config.tools.tshark_enhanced.fallback_config.max_retries == 3
        
        print("✅ 配置验证测试通过")


def run_phase2_day10_tests():
    """运行Phase 2 Day 10配置集成测试"""
    print("🚀 开始Phase 2 Day 10配置系统集成测试...")
    print("=" * 60)
    
    test_suite = TestPhase2Day10ConfigIntegration()
    
    try:
        # 运行所有测试
        test_suite.setup_method()
        test_suite.test_tshark_enhanced_config_loading()
        test_suite.teardown_method()
        
        test_suite.setup_method()
        test_suite.test_processor_config_integration()
        test_suite.teardown_method()
        
        test_suite.setup_method()
        test_suite.test_config_dictionary_access()
        test_suite.teardown_method()
        
        test_suite.setup_method()
        test_suite.test_default_config_fallback()
        test_suite.teardown_method()
        
        test_suite.setup_method()
        test_suite.test_config_validation()
        test_suite.teardown_method()
        
        print("=" * 60)
        print("🎉 Phase 2 Day 10配置系统集成测试全部通过！")
        print("✅ 验收标准：新配置项无缝集成 - 100%达成")
        print("📊 测试结果：5/5测试通过 (100%通过率)")
        print("🔧 配置系统：TShark增强配置完全集成")
        print("🎯 集成状态：现有配置系统零破坏性变更")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    run_phase2_day10_tests() 