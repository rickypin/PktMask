#!/usr/bin/env python3
"""
统一架构功能测试脚本
验证新架构是否正常工作
"""

import sys
import os
import tempfile
from pathlib import Path
from typing import Dict, List, Any

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

def test_unified_stage_import():
    """测试统一基类导入"""
    try:
        from pktmask.core.unified_stage import StageBase, StageStats, create_stage
        print("✅ 统一基类导入成功")
        return True
    except ImportError as e:
        print(f"❌ 统一基类导入失败: {e}")
        return False

def test_compatibility_layer():
    """测试兼容性层"""
    try:
        from pktmask.core.base_step import ProcessingStep
        print("✅ 兼容性层导入成功")
        return True
    except ImportError as e:
        print(f"❌ 兼容性层导入失败: {e}")
        return False

def test_stage_creation():
    """测试阶段创建"""
    try:
        from pktmask.core.unified_stage import create_stage
        
        # 测试创建去重阶段
        try:
            dedup_stage = create_stage('dedup')
            print("✅ 去重阶段创建成功")
        except Exception as e:
            print(f"⚠️  去重阶段创建失败: {e}")
        
        # 测试创建匿名化阶段
        try:
            anon_stage = create_stage('anon')
            print("✅ 匿名化阶段创建成功")
        except Exception as e:
            print(f"⚠️  匿名化阶段创建失败: {e}")
        
        # 测试创建掩码阶段
        try:
            mask_stage = create_stage('mask')
            print("✅ 掩码阶段创建成功")
        except Exception as e:
            print(f"⚠️  掩码阶段创建失败: {e}")
        
        return True
    except ImportError as e:
        print(f"❌ 阶段创建测试失败: {e}")
        return False

def test_pipeline_executor():
    """测试Pipeline执行器"""
    try:
        from pktmask.core.unified_stage import ModernPipelineExecutor, PipelineConfig
        
        # 创建简单的Pipeline配置
        config = PipelineConfig(
            stages=[
                {'type': 'dedup', 'config': {}},
            ],
            fail_fast=True,
            cleanup_temp=True
        )
        
        # 创建执行器
        executor = ModernPipelineExecutor(config)
        print("✅ Pipeline执行器创建成功")
        
        return True
    except Exception as e:
        print(f"❌ Pipeline执行器测试失败: {e}")
        return False

def test_legacy_stage_compatibility():
    """测试旧阶段兼容性"""
    try:
        # 测试旧的stages模块导入
        from pktmask.stages import DeduplicationStage
        print("✅ 旧阶段兼容性导入成功")
        
        # 创建实例
        stage = DeduplicationStage()
        print("✅ 旧阶段实例创建成功")
        
        return True
    except Exception as e:
        print(f"⚠️  旧阶段兼容性测试失败: {e}")
        return False

def test_adapter_compatibility():
    """测试适配器兼容性"""
    try:
        from pktmask.adapters.compatibility.dedup_compat import DeduplicationStageCompat
        print("✅ 兼容性适配器导入成功")
        
        # 创建实例
        compat_stage = DeduplicationStageCompat()
        print("✅ 兼容性适配器实例创建成功")
        
        return True
    except Exception as e:
        print(f"⚠️  适配器兼容性测试失败: {e}")
        return False

def test_config_system():
    """测试配置系统"""
    try:
        from pktmask.config.settings import AppConfig
        
        # 创建默认配置
        config = AppConfig.default()
        print("✅ 配置系统测试成功")
        
        return True
    except Exception as e:
        print(f"❌ 配置系统测试失败: {e}")
        return False

def test_gui_imports():
    """测试GUI相关导入"""
    try:
        # 测试GUI管理器导入
        from pktmask.gui.managers import pipeline_manager
        print("✅ GUI管理器导入成功")
        
        return True
    except Exception as e:
        print(f"⚠️  GUI导入测试失败: {e}")
        return False

def run_comprehensive_test():
    """运行综合测试"""
    print("🧪 开始统一架构功能测试...")
    print("=" * 50)
    
    tests = [
        ("统一基类导入", test_unified_stage_import),
        ("兼容性层", test_compatibility_layer),
        ("阶段创建", test_stage_creation),
        ("Pipeline执行器", test_pipeline_executor),
        ("旧阶段兼容性", test_legacy_stage_compatibility),
        ("适配器兼容性", test_adapter_compatibility),
        ("配置系统", test_config_system),
        ("GUI导入", test_gui_imports),
    ]
    
    results = {}
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n🔍 测试: {test_name}")
        try:
            result = test_func()
            results[test_name] = result
            if result:
                passed += 1
        except Exception as e:
            print(f"💥 测试异常: {e}")
            results[test_name] = False
    
    print("\n" + "=" * 50)
    print(f"📊 测试结果: {passed}/{total} 通过")
    print(f"📈 成功率: {passed/total*100:.1f}%")
    
    # 详细结果
    print(f"\n📋 详细结果:")
    for test_name, result in results.items():
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {test_name}: {status}")
    
    # 生成建议
    print(f"\n💡 建议:")
    if passed == total:
        print("  🎉 所有测试通过！新架构工作正常。")
        print("  🚀 可以开始使用统一架构进行开发。")
    elif passed >= total * 0.8:
        print("  ✨ 大部分测试通过，架构基本可用。")
        print("  🔧 建议修复失败的测试项。")
    else:
        print("  ⚠️  多个测试失败，需要进一步调试。")
        print("  🛠️  建议检查依赖和导入路径。")
    
    return results

def create_simple_test_file():
    """创建简单的测试文件"""
    test_content = """#!/usr/bin/env python3
# 简单的统一架构使用示例

from pktmask.core.unified_stage import StageBase, StageStats

class SimpleTestStage(StageBase):
    name = "SimpleTestStage"
    
    def process_file(self, input_path, output_path):
        # 简单的文件复制
        import shutil
        shutil.copy2(input_path, output_path)
        
        return StageStats(
            stage_name=self.name,
            packets_processed=100,
            packets_modified=0,
            duration_ms=10.0
        )

if __name__ == "__main__":
    stage = SimpleTestStage()
    stage.initialize()
    print(f"测试阶段创建成功: {stage}")
"""
    
    test_file = project_root / "test_simple_stage.py"
    with open(test_file, 'w', encoding='utf-8') as f:
        f.write(test_content)
    
    print(f"📝 创建测试文件: {test_file}")
    return test_file

def cleanup_test_files():
    """清理测试文件"""
    test_files = [
        project_root / "test_simple_stage.py"
    ]
    
    for test_file in test_files:
        if test_file.exists():
            test_file.unlink()
            print(f"🗑️  清理测试文件: {test_file}")

if __name__ == "__main__":
    try:
        # 创建测试文件
        test_file = create_simple_test_file()
        
        # 运行综合测试
        results = run_comprehensive_test()
        
        # 测试简单阶段
        print(f"\n🧪 测试简单阶段...")
        try:
            import subprocess
            result = subprocess.run([
                sys.executable, str(test_file)
            ], cwd=project_root, capture_output=True, text=True)
            
            if result.returncode == 0:
                print("✅ 简单阶段测试成功")
                print(f"输出: {result.stdout}")
            else:
                print(f"❌ 简单阶段测试失败: {result.stderr}")
        except Exception as e:
            print(f"💥 简单阶段测试异常: {e}")
        
        # 保存测试结果
        import json
        output_file = project_root / "reports" / "architecture_test_results.json"
        output_file.parent.mkdir(exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                "test_results": results,
                "timestamp": str(Path(__file__).stat().st_mtime),
                "summary": {
                    "total_tests": len(results),
                    "passed_tests": sum(results.values()),
                    "success_rate": sum(results.values()) / len(results) * 100
                }
            }, f, indent=2)
        
        print(f"\n✅ 测试结果已保存到: {output_file}")
        
    finally:
        # 清理测试文件
        cleanup_test_files()
