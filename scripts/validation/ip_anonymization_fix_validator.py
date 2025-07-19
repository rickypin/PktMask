#!/usr/bin/env python3
"""
IP匿名化功能修复验证脚本

验证IPAnonymizationStage修复后是否正常工作，包括：
1. 模块导入测试
2. ProcessorRegistry集成测试
3. Pipeline创建测试
4. IPAnonymizationStage功能测试
5. 架构一致性测试
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
        from pktmask.core.pipeline.stages.ip_anonymization import IPAnonymizationStage
        print("✅ IPAnonymizationStage导入成功")
        
        from pktmask.core.pipeline.stages.ip_anonymization_unified import UnifiedIPAnonymizationStage
        print("✅ UnifiedIPAnonymizationStage导入成功")
        
        from pktmask.core.processors.registry import ProcessorRegistry
        print("✅ ProcessorRegistry导入成功")
        
        # 验证继承关系
        assert issubclass(IPAnonymizationStage, UnifiedIPAnonymizationStage)
        print("✅ IPAnonymizationStage正确继承UnifiedIPAnonymizationStage")
        
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
        
        # 测试获取IP匿名化处理器
        config = ProcessorConfig(enabled=True, name="test_ip_anon")
        processor = ProcessorRegistry.get_processor('anonymize_ips', config)
        
        print(f"✅ 获取IP匿名化处理器成功: {type(processor).__name__}")
        
        # 验证返回的是UnifiedIPAnonymizationStage实例
        from pktmask.core.pipeline.stages.ip_anonymization_unified import UnifiedIPAnonymizationStage
        assert isinstance(processor, UnifiedIPAnonymizationStage)
        print("✅ 返回正确的UnifiedIPAnonymizationStage实例")
        
        # 测试处理器信息
        info = ProcessorRegistry.get_processor_info('anonymize_ips')
        print(f"✅ 处理器信息: {info['display_name']}")
        assert info['display_name'] == 'Anonymize IPs'
        
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
            'remove_dupes': {'enabled': False},
            'anonymize_ips': {'enabled': True}, 
            'mask_payloads': {'enabled': False}
        }
        
        executor = create_pipeline_executor(config)
        print(f"✅ Pipeline创建成功: {type(executor).__name__}")
        
        # 验证pipeline包含IP匿名化阶段
        stages = executor.stages
        ip_stages = [s for s in stages if 'ip' in s.name.lower() or 'anon' in s.name.lower()]
        assert len(ip_stages) > 0
        print(f"✅ Pipeline包含IP匿名化阶段: {[s.name for s in ip_stages]}")
        
        return True
    except Exception as e:
        print(f"❌ Pipeline创建失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_ip_anonymization_stage_functionality():
    """测试IPAnonymizationStage功能"""
    print("\n🔍 测试IPAnonymizationStage功能...")
    
    try:
        from pktmask.core.pipeline.stages.ip_anonymization import IPAnonymizationStage
        
        # 创建配置
        config = {
            'enabled': True,
            'name': 'test_ip_anon',
            'method': 'prefix_preserving',
            'ipv4_prefix': 24,
            'ipv6_prefix': 64
        }
        
        # 创建实例
        stage = IPAnonymizationStage(config)
        print(f"✅ IPAnonymizationStage创建成功: {stage.name}")
        
        # 测试初始化
        stage.initialize()
        print("✅ IPAnonymizationStage初始化成功")
        
        # 测试方法
        display_name = stage.get_display_name()
        description = stage.get_description()
        required_tools = stage.get_required_tools()
        
        print(f"✅ 显示名称: {display_name}")
        print(f"✅ 描述: {description}")
        print(f"✅ 所需工具: {required_tools}")
        
        # 验证返回值
        assert display_name == "Anonymize IPs"
        assert isinstance(description, str) and len(description) > 0
        assert isinstance(required_tools, list)
        
        return True
    except Exception as e:
        print(f"❌ IPAnonymizationStage功能测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_architecture_consistency():
    """测试架构一致性"""
    print("\n🔍 测试架构一致性...")
    
    try:
        from pktmask.core.pipeline.stages.ip_anonymization import IPAnonymizationStage
        from pktmask.core.pipeline.stages.ip_anonymization_unified import UnifiedIPAnonymizationStage
        from pktmask.core.processors.registry import ProcessorRegistry, ProcessorConfig
        
        # 测试通过不同方式获取的实例是否一致
        config = ProcessorConfig(enabled=True, name="test")
        registry_instance = ProcessorRegistry.get_processor('anonymize_ips', config)
        
        direct_config = {'enabled': True, 'name': 'test', 'method': 'prefix_preserving'}
        direct_instance = IPAnonymizationStage(direct_config)
        
        # 验证类型一致性
        assert type(registry_instance) == UnifiedIPAnonymizationStage
        assert type(direct_instance) == IPAnonymizationStage
        assert isinstance(direct_instance, UnifiedIPAnonymizationStage)
        
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

def test_combined_pipeline():
    """测试组合Pipeline（去重+IP匿名化）"""
    print("\n🔍 测试组合Pipeline...")
    
    try:
        from pktmask.services.pipeline_service import create_pipeline_executor
        
        config = {
            'remove_dupes': {'enabled': True},
            'anonymize_ips': {'enabled': True}, 
            'mask_payloads': {'enabled': False}
        }
        
        executor = create_pipeline_executor(config)
        print(f"✅ 组合Pipeline创建成功: {type(executor).__name__}")
        
        # 验证pipeline包含两个阶段
        stages = executor.stages
        stage_names = [s.name for s in stages]
        print(f"✅ Pipeline包含阶段: {stage_names}")
        
        # 验证包含去重和IP匿名化阶段
        has_dedup = any('dedup' in name.lower() for name in stage_names)
        has_ip_anon = any('ip' in name.lower() or 'anon' in name.lower() for name in stage_names)
        
        assert has_dedup, "Pipeline应该包含去重阶段"
        assert has_ip_anon, "Pipeline应该包含IP匿名化阶段"
        
        print("✅ 组合Pipeline验证通过")
        
        return True
    except Exception as e:
        print(f"❌ 组合Pipeline测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主测试函数"""
    print("🚀 开始IP匿名化功能修复验证...")
    print("=" * 60)
    
    tests = [
        ("模块导入", test_module_imports),
        ("ProcessorRegistry集成", test_processor_registry),
        ("Pipeline创建", test_pipeline_creation),
        ("IPAnonymizationStage功能", test_ip_anonymization_stage_functionality),
        ("架构一致性", test_architecture_consistency),
        ("组合Pipeline", test_combined_pipeline),
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
        print("🎉 所有测试通过！IP匿名化功能修复成功！")
        print("\n✅ 修复总结:")
        print("  - IPAnonymizationStage现在直接继承UnifiedIPAnonymizationStage")
        print("  - 移除了对不存在的ip_anonymizer.py的依赖")
        print("  - ProcessorRegistry正确映射到统一架构")
        print("  - Pipeline可以正常创建和运行")
        print("  - 支持去重+IP匿名化的组合处理")
        return 0
    else:
        print("⚠️  部分测试失败，需要进一步检查")
        return 1

if __name__ == "__main__":
    sys.exit(main())
