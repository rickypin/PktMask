#!/usr/bin/env python3

"""
Phase 2: 配置系统简化 - 测试脚本

测试新的简化配置系统是否正常工作。
"""

import os
import sys
import tempfile
import yaml
import json
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root / "src"))

try:
    from pktmask.config import (
        AppConfig, UISettings, ProcessingSettings, LoggingSettings,
        get_app_config, reload_app_config, save_app_config,
        DEFAULT_UI_CONFIG, DEFAULT_PROCESSING_CONFIG, DEFAULT_LOGGING_CONFIG,
        get_default_config_dict, is_valid_theme, is_valid_log_level
    )
    print("✅ 成功导入简化配置模块")
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    sys.exit(1)


def test_config_classes():
    """测试配置数据类"""
    print("\n🔍 测试配置数据类...")
    
    try:
        # 测试默认创建
        ui_settings = UISettings()
        processing_settings = ProcessingSettings()
        logging_settings = LoggingSettings()
        
        print(f"  默认UI设置: {ui_settings.window_width}x{ui_settings.window_height}")
        print(f"  默认处理设置: chunk_size={processing_settings.chunk_size}")
        print(f"  默认日志设置: {logging_settings.log_level}")
        
        # 测试自定义参数
        custom_ui = UISettings(window_width=1600, default_mask_ip=False)
        assert custom_ui.window_width == 1600
        assert custom_ui.default_mask_ip == False
        
        print("  ✅ 配置数据类测试通过")
        return True
        
    except Exception as e:
        print(f"  ❌ 配置数据类测试失败: {e}")
        return False


def test_app_config():
    """测试主配置类"""
    print("\n🔍 测试主配置类...")
    
    try:
        # 测试默认配置
        config = AppConfig.default()
        assert config.config_version == "2.0"
        assert config.ui.window_width == 1200
        assert config.processing.chunk_size == 10
        
        # 测试配置验证
        is_valid, messages = config.validate()
        assert is_valid, f"默认配置验证失败: {messages}"
        
        # 测试配置字典获取
        ui_dict = config.get_ui_config()
        processing_dict = config.get_processing_config()
        
        assert 'default_mask_ip' in ui_dict
        assert 'chunk_size' in processing_dict
        
        print("  ✅ 主配置类测试通过")
        return True
        
    except Exception as e:
        print(f"  ❌ 主配置类测试失败: {e}")
        return False


def test_config_file_operations():
    """测试配置文件操作"""
    print("\n🔍 测试配置文件操作...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # 测试YAML保存和加载
            yaml_path = Path(temp_dir) / "test_config.yaml"
            
            config = AppConfig.default()
            config.ui.window_width = 1600
            config.processing.chunk_size = 20
            
            # 保存配置
            success = config.save(yaml_path)
            assert success, "配置保存失败"
            assert yaml_path.exists(), "配置文件未创建"
            
            # 加载配置
            loaded_config = AppConfig.load(yaml_path)
            assert loaded_config.ui.window_width == 1600
            assert loaded_config.processing.chunk_size == 20
            
            # 测试JSON保存和加载
            json_path = Path(temp_dir) / "test_config.json"
            success = config.save(json_path)
            assert success, "JSON配置保存失败"
            
            json_config = AppConfig.load(json_path)
            assert json_config.ui.window_width == 1600
            
            print("  ✅ 配置文件操作测试通过")
            return True
            
        except Exception as e:
            print(f"  ❌ 配置文件操作测试失败: {e}")
            return False


def test_config_validation():
    """测试配置验证"""
    print("\n🔍 测试配置验证...")
    
    try:
        # 测试有效配置
        config = AppConfig.default()
        is_valid, messages = config.validate()
        assert is_valid, f"默认配置应该是有效的: {messages}"
        
        # 测试无效配置
        config.ui.theme = "invalid_theme"
        config.processing.chunk_size = -1
        config.logging.log_level = "INVALID"
        
        is_valid, messages = config.validate()
        assert not is_valid, "无效配置应该被检测出来"
        assert len(messages) >= 3, f"应该有至少3个错误，实际: {len(messages)}"
        
        # 测试边界值
        config = AppConfig.default()
        config.ui.window_width = 500  # 过小
        config.ui.window_height = 400  # 过小
        
        is_valid, messages = config.validate()
        # 边界值会产生警告，不一定是错误
        
        print("  ✅ 配置验证测试通过")
        return True
        
    except Exception as e:
        print(f"  ❌ 配置验证测试失败: {e}")
        return False


def test_global_config():
    """测试全局配置管理"""
    print("\n🔍 测试全局配置管理...")
    
    try:
        # 测试获取全局配置
        config1 = get_app_config()
        config2 = get_app_config()
        
        # 应该是同一个实例
        assert config1 is config2, "全局配置应该是单例"
        
        # 测试目录更新
        config1.update_last_directories(
            input_dir="/test/input",
            output_dir="/test/output"
        )
        
        assert config1.ui.last_input_dir == "/test/input"
        assert config1.ui.last_output_dir == "/test/output"
        
        print("  ✅ 全局配置管理测试通过")
        return True
        
    except Exception as e:
        print(f"  ❌ 全局配置管理测试失败: {e}")
        return False


def test_defaults_and_validation():
    """测试默认值和验证函数"""
    print("\n🔍 测试默认值和验证函数...")
    
    try:
        # 测试默认值常量
        assert DEFAULT_UI_CONFIG['window_width'] == 1200
        assert DEFAULT_PROCESSING_CONFIG['chunk_size'] == 10
        assert DEFAULT_LOGGING_CONFIG['log_level'] == 'INFO'
        
        # 测试默认配置字典
        default_dict = get_default_config_dict()
        assert 'ui' in default_dict
        assert 'processing' in default_dict
        assert 'logging' in default_dict
        
        # 测试验证函数
        assert is_valid_theme('auto')
        assert is_valid_theme('light')
        assert is_valid_theme('dark')
        assert not is_valid_theme('invalid')
        
        assert is_valid_log_level('INFO')
        assert is_valid_log_level('DEBUG')
        assert not is_valid_log_level('INVALID')
        
        print("  ✅ 默认值和验证函数测试通过")
        return True
        
    except Exception as e:
        print(f"  ❌ 默认值和验证函数测试失败: {e}")
        return False


def test_config_migration():
    """测试配置迁移功能"""
    print("\n🔍 测试配置迁移功能...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # 创建模拟的旧配置文件
            old_config_path = Path(temp_dir) / "legacy_config.yaml"
            old_config_data = {
                'ui': {
                    'last_input_dir': '/old/input',
                    'last_output_dir': '/old/output',
                    'window_width': 1400
                },
                'processing': {
                    'chunk_size': 15
                }
            }
            
            with open(old_config_path, 'w') as f:
                yaml.dump(old_config_data, f)
            
            # 加载并验证旧配置可以正常读取
            migrated_config = AppConfig.load(old_config_path)
            assert migrated_config.ui.last_input_dir == '/old/input'
            assert migrated_config.ui.window_width == 1400
            assert migrated_config.processing.chunk_size == 15
            
            print("  ✅ 配置迁移功能测试通过")
            return True
            
        except Exception as e:
            print(f"  ❌ 配置迁移功能测试失败: {e}")
            return False


def main():
    """主测试函数"""
    print("🚀 Phase 2: 配置系统简化测试")
    print("=" * 50)
    
    tests = [
        test_config_classes,
        test_app_config,
        test_config_file_operations,
        test_config_validation,
        test_global_config,
        test_defaults_and_validation,
        test_config_migration
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print("\n" + "=" * 50)
    print(f"📊 测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 Phase 2 配置系统简化测试 - 全部通过！")
        return True
    else:
        print(f"❌ {total - passed} 个测试失败")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 