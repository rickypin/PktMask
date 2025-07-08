#!/usr/bin/env python3
"""
适配器迁移验证脚本

验证适配器迁移后的基本功能。
"""

import sys
import importlib
import traceback
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / 'src'))

def test_import_adapters():
    """测试所有适配器是否能正常导入"""
    print("=== 测试适配器导入 ===")
    
    adapters_to_test = [
        # 新位置导入
        ("pktmask.adapters", ["PipelineProcessorAdapter", "ProcessingAdapter", 
                              "EventDataAdapter", "StatisticsDataAdapter"]),
        ("pktmask.adapters.compatibility", ["IpAnonymizationStageCompat", 
                                           "DeduplicationStageCompat"]),
        ("pktmask.adapters.adapter_exceptions", ["AdapterError", "ConfigurationError",
                                                "DataFormatError", "CompatibilityError"]),
    ]
    
    all_passed = True
    
    for module_name, classes in adapters_to_test:
        try:
            module = importlib.import_module(module_name)
            print(f"\n✅ 成功导入模块: {module_name}")
            
            for class_name in classes:
                if hasattr(module, class_name):
                    print(f"  ✅ 找到类: {class_name}")
                else:
                    print(f"  ❌ 未找到类: {class_name}")
                    all_passed = False
                    
        except Exception as e:
            print(f"\n❌ 导入失败: {module_name}")
            print(f"  错误: {e}")
            traceback.print_exc()
            all_passed = False
    
    return all_passed


def test_legacy_imports():
    """测试旧位置的代理文件是否正常工作"""
    print("\n\n=== 测试向后兼容性（代理文件）===")
    
    legacy_imports = [
        "pktmask.core.adapters.processor_adapter",
        "pktmask.domain.adapters.event_adapter",
        "pktmask.domain.adapters.statistics_adapter",
        "pktmask.stages.adapters.anon_compat",
        "pktmask.stages.adapters.dedup_compat",
    ]
    
    all_passed = True
    
    for module_name in legacy_imports:
        try:
            # 捕获废弃警告
            import warnings
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                module = importlib.import_module(module_name)
                
                # 检查是否有废弃警告
                deprecation_warnings = [warning for warning in w 
                                      if issubclass(warning.category, DeprecationWarning)]
                
                if deprecation_warnings:
                    print(f"\n✅ 代理文件工作正常: {module_name}")
                    print(f"  ⚠️  废弃警告: {deprecation_warnings[0].message}")
                else:
                    print(f"\n⚠️  代理文件未产生预期的废弃警告: {module_name}")
                    
        except Exception as e:
            print(f"\n❌ 代理文件导入失败: {module_name}")
            print(f"  错误: {e}")
            all_passed = False
    
    return all_passed


def test_adapter_creation():
    """测试创建适配器实例"""
    print("\n\n=== 测试适配器实例化 ===")
    
    try:
        # 测试异常类
        from pktmask.adapters.adapter_exceptions import AdapterError, MissingConfigError
        
        error = AdapterError("Test error")
        print(f"✅ 创建AdapterError实例: {error}")
        
        config_error = MissingConfigError("api_key", "TestAdapter")
        print(f"✅ 创建MissingConfigError实例: {config_error}")
        
        # 测试适配器类（需要避免复杂的依赖）
        print("\n注意：由于依赖关系，跳过复杂适配器的实例化测试")
        
        return True
        
    except Exception as e:
        print(f"❌ 适配器实例化失败: {e}")
        traceback.print_exc()
        return False


def check_file_structure():
    """检查文件结构是否正确"""
    print("\n\n=== 检查文件结构 ===")
    
    expected_files = [
        "src/pktmask/adapters/__init__.py",
        "src/pktmask/adapters/processor_adapter.py",
        "src/pktmask/adapters/encapsulation_adapter.py",
        "src/pktmask/adapters/event_adapter.py",
        "src/pktmask/adapters/statistics_adapter.py",
        "src/pktmask/adapters/adapter_exceptions.py",
        "src/pktmask/adapters/compatibility/__init__.py",
        "src/pktmask/adapters/compatibility/anon_compat.py",
        "src/pktmask/adapters/compatibility/dedup_compat.py",
    ]
    
    proxy_files = [
        "src/pktmask/core/adapters/processor_adapter.py",
        "src/pktmask/core/encapsulation/adapter.py",
        "src/pktmask/domain/adapters/event_adapter.py",
        "src/pktmask/domain/adapters/statistics_adapter.py",
        "src/pktmask/stages/adapters/anon_compat.py",
        "src/pktmask/stages/adapters/dedup_compat.py",
    ]
    
    all_passed = True
    
    print("\n检查新文件:")
    for file_path in expected_files:
        full_path = project_root / file_path
        if full_path.exists():
            print(f"  ✅ {file_path}")
        else:
            print(f"  ❌ {file_path} - 文件不存在")
            all_passed = False
    
    print("\n检查代理文件:")
    for file_path in proxy_files:
        full_path = project_root / file_path
        if full_path.exists():
            # 检查是否包含废弃警告
            content = full_path.read_text()
            if "DeprecationWarning" in content:
                print(f"  ✅ {file_path} - 代理文件存在")
            else:
                print(f"  ⚠️  {file_path} - 存在但可能不是代理文件")
        else:
            print(f"  ❌ {file_path} - 代理文件不存在")
            all_passed = False
    
    return all_passed


def main():
    """主函数"""
    print("适配器迁移验证脚本")
    print("=" * 60)
    
    results = []
    
    # 运行各项测试
    results.append(("文件结构检查", check_file_structure()))
    results.append(("新位置导入测试", test_import_adapters()))
    results.append(("向后兼容性测试", test_legacy_imports()))
    results.append(("适配器实例化测试", test_adapter_creation()))
    
    # 总结
    print("\n\n=== 测试总结 ===")
    print("=" * 60)
    
    total_tests = len(results)
    passed_tests = sum(1 for _, passed in results if passed)
    
    for test_name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{test_name}: {status}")
    
    print(f"\n总计: {passed_tests}/{total_tests} 测试通过")
    
    if passed_tests == total_tests:
        print("\n🎉 所有测试通过！适配器迁移验证成功。")
        return 0
    else:
        print("\n⚠️  部分测试失败，请检查上述错误信息。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
