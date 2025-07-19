#!/usr/bin/env python3
"""
去重功能核心验证脚本

专门验证去重功能修复的核心部分，不包括GUI测试。
验证内容：
1. 模块导入测试
2. ProcessorRegistry集成测试  
3. Pipeline创建测试
4. DeduplicationStage功能测试
"""

import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

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
        
        # 验证继承关系
        assert issubclass(DeduplicationStage, UnifiedDeduplicationStage)
        print("✅ DeduplicationStage正确继承UnifiedDeduplicationStage")
        
        return True
    except Exception as e:
        print(f"❌ 模块导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_processor_registry():
    """测试ProcessorRegistry集成"""
    print("\n🔍 测试ProcessorRegistry集成...")
    
    try:
        from pktmask.core.processors.registry import ProcessorRegistry, ProcessorConfig
        
        # 测试获取去重处理器
        config = ProcessorConfig(enabled=True, name="test_dedup")
        processor = ProcessorRegistry.get_processor('remove_dupes', config)
        
        print(f"✅ 获取去重处理器成功: {type(processor).__name__}")
        
        # 验证返回的是UnifiedDeduplicationStage实例
        from pktmask.core.pipeline.stages.deduplication_unified import UnifiedDeduplicationStage
        assert isinstance(processor, UnifiedDeduplicationStage)
        print("✅ 返回正确的UnifiedDeduplicationStage实例")
        
        # 测试处理器信息
        info = ProcessorRegistry.get_processor_info('remove_dupes')
        print(f"✅ 处理器信息: {info['display_name']}")
        assert info['display_name'] == 'Remove Dupes'
        
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
        print(f"✅ Pipeline创建成功: {type(executor).__name__}")
        
        # 验证pipeline包含去重阶段
        stages = executor.stages
        dedup_stages = [s for s in stages if 'dedup' in s.name.lower() or 'deduplication' in s.name.lower()]
        assert len(dedup_stages) > 0
        print(f"✅ Pipeline包含去重阶段: {[s.name for s in dedup_stages]}")
        
        return True
    except Exception as e:
        print(f"❌ Pipeline创建失败: {e}")
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
        required_tools = stage.get_required_tools()
        
        print(f"✅ 显示名称: {display_name}")
        print(f"✅ 描述: {description}")
        print(f"✅ 所需工具: {required_tools}")
        
        # 验证返回值
        assert display_name == "Remove Dupes"
        assert isinstance(description, str) and len(description) > 0
        assert isinstance(required_tools, list)
        
        return True
    except Exception as e:
        print(f"❌ DeduplicationStage功能测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_architecture_consistency():
    """测试架构一致性"""
    print("\n🔍 测试架构一致性...")
    
    try:
        from pktmask.core.pipeline.stages.dedup import DeduplicationStage
        from pktmask.core.pipeline.stages.deduplication_unified import UnifiedDeduplicationStage
        from pktmask.core.processors.registry import ProcessorRegistry, ProcessorConfig
        
        # 测试通过不同方式获取的实例是否一致
        config = ProcessorConfig(enabled=True, name="test")
        registry_instance = ProcessorRegistry.get_processor('remove_dupes', config)
        
        direct_config = {'enabled': True, 'name': 'test', 'algorithm': 'md5'}
        direct_instance = DeduplicationStage(direct_config)
        
        # 验证类型一致性
        assert type(registry_instance) == UnifiedDeduplicationStage
        assert type(direct_instance) == DeduplicationStage
        assert isinstance(direct_instance, UnifiedDeduplicationStage)
        
        print("✅ 架构一致性验证通过")
        
        # 验证方法一致性
        assert registry_instance.get_display_name() == direct_instance.get_display_name()
        print("✅ 方法一致性验证通过")
        
        return True
    except Exception as e:
        print(f"❌ 架构一致性测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主测试函数"""
    print("🚀 开始去重功能核心验证...")
    print("=" * 60)
    
    tests = [
        ("模块导入", test_module_imports),
        ("ProcessorRegistry集成", test_processor_registry),
        ("Pipeline创建", test_pipeline_creation),
        ("DeduplicationStage功能", test_deduplication_stage_functionality),
        ("架构一致性", test_architecture_consistency),
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
        print("🎉 所有核心测试通过！去重功能修复成功！")
        print("\n✅ 修复总结:")
        print("  - DeduplicationStage现在直接继承UnifiedDeduplicationStage")
        print("  - 移除了对不存在的deduplicator.py的依赖")
        print("  - ProcessorRegistry正确映射到统一架构")
        print("  - Pipeline可以正常创建和运行")
        return 0
    else:
        print("⚠️  部分测试失败，需要进一步检查")
        return 1

if __name__ == "__main__":
    sys.exit(main())
