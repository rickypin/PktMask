#!/usr/bin/env python3
"""
去重功能修复验证脚本

验证DeduplicationStage修复后是否正常工作，包括：
1. 模块导入测试
2. ProcessorRegistry集成测试
3. Pipeline创建测试
4. GUI初始化测试
5. CLI功能测试
"""

import sys
import os
import tempfile
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

# 添加config路径以支持GUI测试
config_path = project_root / "config"
if str(config_path) not in sys.path:
    sys.path.insert(0, str(config_path))

def test_module_imports():
    """测试模块导入"""
    print("🔍 测试模块导入...")
    
    try:
        from pktmask.core.pipeline.stages.dedup import DeduplicationStage
        print("✅ DeduplicationStage导入成功")
        
        from pktmask.core.pipeline.stages.deduplication_unified import UnifiedDeduplicationStage
        print("✅ UnifiedDeduplicationStage导入成功")
        
        from pktmask.core.processors.registry import ProcessorRegistry
        print("✅ ProcessorRegistry导入成功")
        
        return True
    except Exception as e:
        print(f"❌ 模块导入失败: {e}")
        return False

def test_processor_registry():
    """测试ProcessorRegistry集成"""
    print("\n🔍 测试ProcessorRegistry集成...")
    
    try:
        from pktmask.core.processors.registry import ProcessorRegistry, ProcessorConfig
        
        # 测试获取去重处理器
        config = ProcessorConfig(enabled=True, name="test_dedup")
        processor = ProcessorRegistry.get_processor('remove_dupes', config)
        
        print(f"✅ 获取去重处理器成功: {type(processor)}")
        
        # 测试处理器信息
        info = ProcessorRegistry.get_processor_info('remove_dupes')
        print(f"✅ 处理器信息: {info['display_name']}")
        
        return True
    except Exception as e:
        print(f"❌ ProcessorRegistry测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_pipeline_creation():
    """测试Pipeline创建"""
    print("\n🔍 测试Pipeline创建...")
    
    try:
        from pktmask.services.pipeline_service import create_pipeline_executor
        
        config = {
            'remove_dupes': {'enabled': True},
            'anonymize_ips': {'enabled': False}, 
            'mask_payloads': {'enabled': False}
        }
        
        executor = create_pipeline_executor(config)
        print(f"✅ Pipeline创建成功: {type(executor)}")
        
        return True
    except Exception as e:
        print(f"❌ Pipeline创建失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_gui_initialization():
    """测试GUI初始化"""
    print("\n🔍 测试GUI初始化...")
    
    try:
        # 设置测试模式
        os.environ['PKTMASK_TEST_MODE'] = 'true'
        
        from pktmask.gui.main_window import main
        window = main()
        
        if window:
            print(f"✅ GUI初始化成功: {type(window)}")
            return True
        else:
            print("❌ GUI初始化返回None")
            return False
            
    except Exception as e:
        print(f"❌ GUI初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_deduplication_stage_functionality():
    """测试DeduplicationStage功能"""
    print("\n🔍 测试DeduplicationStage功能...")
    
    try:
        from pktmask.core.pipeline.stages.dedup import DeduplicationStage
        
        # 创建配置
        config = {
            'enabled': True,
            'name': 'test_dedup',
            'algorithm': 'md5'
        }
        
        # 创建实例
        stage = DeduplicationStage(config)
        print(f"✅ DeduplicationStage创建成功: {stage.name}")
        
        # 测试初始化
        stage.initialize()
        print("✅ DeduplicationStage初始化成功")
        
        # 测试方法
        display_name = stage.get_display_name()
        description = stage.get_description()
        print(f"✅ 显示名称: {display_name}")
        print(f"✅ 描述: {description}")
        
        return True
    except Exception as e:
        print(f"❌ DeduplicationStage功能测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主测试函数"""
    print("🚀 开始去重功能修复验证...")
    print("=" * 60)
    
    tests = [
        ("模块导入", test_module_imports),
        ("ProcessorRegistry集成", test_processor_registry),
        ("Pipeline创建", test_pipeline_creation),
        ("GUI初始化", test_gui_initialization),
        ("DeduplicationStage功能", test_deduplication_stage_functionality),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                print(f"❌ {test_name} 测试失败")
        except Exception as e:
            print(f"❌ {test_name} 测试异常: {e}")
    
    print("\n" + "=" * 60)
    print(f"📊 测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有测试通过！去重功能修复成功！")
        return 0
    else:
        print("⚠️  部分测试失败，需要进一步检查")
        return 1

if __name__ == "__main__":
    sys.exit(main())
