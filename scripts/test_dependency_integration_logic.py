#!/usr/bin/env python3
"""
测试依赖集成逻辑

这个脚本测试依赖检查逻辑是否正确集成，不依赖GUI组件，
专注于验证核心的依赖检查和消息生成逻辑。
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

def test_dependency_checker_import():
    """测试依赖检查器导入"""
    print("=" * 60)
    print("测试依赖检查器导入")
    print("=" * 60)
    
    try:
        from pktmask.infrastructure.dependency import DependencyChecker, DependencyResult, DependencyStatus
        print("✅ 成功导入 DependencyChecker")
        print("✅ 成功导入 DependencyResult")
        print("✅ 成功导入 DependencyStatus")
        
        # 测试枚举值
        print(f"DependencyStatus.SATISFIED: {DependencyStatus.SATISFIED.value}")
        print(f"DependencyStatus.MISSING: {DependencyStatus.MISSING.value}")
        print(f"DependencyStatus.VERSION_MISMATCH: {DependencyStatus.VERSION_MISMATCH.value}")
        
        return True
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        return False

def test_gui_integration_methods():
    """测试GUI集成方法的存在性"""
    print("\n" + "=" * 60)
    print("测试GUI集成方法")
    print("=" * 60)
    
    try:
        # 测试UIBuilder中的方法
        from pktmask.gui.core.ui_builder import UIBuilder
        
        # 检查方法是否存在
        methods_to_check = [
            '_check_and_display_dependencies',
            '_display_dependency_status',
            '_show_initial_guides'
        ]
        
        for method_name in methods_to_check:
            if hasattr(UIBuilder, method_name):
                print(f"✅ UIBuilder.{method_name} 存在")
            else:
                print(f"❌ UIBuilder.{method_name} 不存在")
                return False
        
        return True
    except ImportError as e:
        print(f"❌ UIBuilder导入失败: {e}")
        return False

def test_dependency_status_message_generation():
    """测试依赖状态消息生成"""
    print("\n" + "=" * 60)
    print("测试依赖状态消息生成")
    print("=" * 60)
    
    try:
        from pktmask.infrastructure.dependency import DependencyChecker, DependencyResult, DependencyStatus
        
        # 创建不同状态的依赖结果
        test_results = [
            DependencyResult(
                name="tshark",
                status=DependencyStatus.MISSING,
                version_required="4.2.0",
                error_message="TShark executable not found"
            ),
            DependencyResult(
                name="tshark",
                status=DependencyStatus.VERSION_MISMATCH,
                version_found="3.6.2",
                version_required="4.2.0",
                path="/usr/bin/tshark",
                error_message="Version too old"
            ),
            DependencyResult(
                name="tshark",
                status=DependencyStatus.EXECUTION_ERROR,
                version_required="4.2.0",
                error_message="Permission denied"
            )
        ]
        
        checker = DependencyChecker()
        
        for i, result in enumerate(test_results, 1):
            print(f"\n--- 测试场景 {i}: {result.status.value} ---")
            message = checker._format_error_message(result)
            print(f"生成的消息: {message}")
            
            # 验证消息格式
            if result.name.upper() in message:
                print("✅ 消息包含依赖名称")
            else:
                print("❌ 消息缺少依赖名称")
                return False
        
        return True
    except Exception as e:
        print(f"❌ 消息生成测试失败: {e}")
        return False

def test_conditional_display_logic():
    """测试条件显示逻辑"""
    print("\n" + "=" * 60)
    print("测试条件显示逻辑")
    print("=" * 60)
    
    try:
        from pktmask.infrastructure.dependency import DependencyChecker
        
        checker = DependencyChecker()
        
        # 测试正常情况（依赖满足）
        print("--- 场景1: 依赖满足 ---")
        if checker.are_dependencies_satisfied():
            status_messages = checker.get_status_messages()
            print(f"状态消息数量: {len(status_messages)}")
            if len(status_messages) == 0:
                print("✅ 依赖满足时无状态消息（符合预期）")
            else:
                print("❌ 依赖满足时仍有状态消息")
                return False
        else:
            print("⚠️  当前系统依赖不满足，跳过此测试")
        
        # 测试模拟失败情况
        print("\n--- 场景2: 模拟依赖失败 ---")
        original_check = checker.check_tshark
        
        # 模拟tshark缺失
        def mock_tshark_missing():
            from pktmask.infrastructure.dependency import DependencyResult, DependencyStatus
            return DependencyResult(
                name="tshark",
                status=DependencyStatus.MISSING,
                version_required="4.2.0",
                error_message="TShark not found"
            )
        
        checker.check_tshark = mock_tshark_missing
        
        # 清除缓存以使用新的模拟结果
        checker.clear_cache()
        
        satisfied = checker.are_dependencies_satisfied()
        status_messages = checker.get_status_messages()
        
        print(f"依赖满足: {satisfied}")
        print(f"状态消息数量: {len(status_messages)}")
        
        if not satisfied and len(status_messages) > 0:
            print("✅ 依赖失败时正确生成状态消息")
            for i, message in enumerate(status_messages, 1):
                print(f"  {i}. {message}")
        else:
            print("❌ 依赖失败时状态消息生成异常")
            return False
        
        # 恢复原始方法
        checker.check_tshark = original_check
        checker.clear_cache()
        
        return True
    except Exception as e:
        print(f"❌ 条件显示逻辑测试失败: {e}")
        return False

def test_gui_message_formatting():
    """测试GUI消息格式化"""
    print("\n" + "=" * 60)
    print("测试GUI消息格式化")
    print("=" * 60)
    
    try:
        # 模拟GUI显示逻辑
        sample_messages = [
            "TSHARK not found in system PATH",
            "TSHARK version too old: 3.6.2, required: ≥4.2.0"
        ]
        
        # 构建GUI显示文本
        gui_text = "⚠️  Dependency Status Check:\n"
        gui_text += "-" * 40 + "\n"
        
        for message in sample_messages:
            gui_text += f"❌ {message}\n"
        
        gui_text += "\n💡 Installation Guide:\n"
        gui_text += "   • Install Wireshark (includes tshark)\n"
        gui_text += "   • Ensure tshark is in system PATH\n"
        gui_text += "   • Minimum version required: 4.2.0\n"
        gui_text += "   • Download: https://www.wireshark.org/download.html\n"
        gui_text += "-" * 40 + "\n\n"
        
        print("生成的GUI文本:")
        print(gui_text)
        
        # 验证格式
        required_elements = [
            "Dependency Status Check",
            "Installation Guide",
            "Install Wireshark",
            "system PATH",
            "4.2.0"
        ]
        
        for element in required_elements:
            if element in gui_text:
                print(f"✅ 包含必需元素: {element}")
            else:
                print(f"❌ 缺少必需元素: {element}")
                return False
        
        return True
    except Exception as e:
        print(f"❌ GUI消息格式化测试失败: {e}")
        return False

def main():
    """主函数"""
    print(f"Python版本: {sys.version}")
    print(f"工作目录: {os.getcwd()}")
    print(f"项目根目录: {project_root}")
    
    # 运行所有测试
    tests = [
        ("依赖检查器导入", test_dependency_checker_import),
        ("GUI集成方法", test_gui_integration_methods),
        ("状态消息生成", test_dependency_status_message_generation),
        ("条件显示逻辑", test_conditional_display_logic),
        ("GUI消息格式化", test_gui_message_formatting)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name}测试异常: {e}")
            results.append((test_name, False))
    
    # 总结
    print("\n" + "=" * 60)
    print("依赖集成逻辑测试总结")
    print("=" * 60)
    
    passed = 0
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n通过率: {passed}/{len(results)} ({passed/len(results)*100:.1f}%)")
    
    if passed == len(results):
        print("\n🎉 所有依赖集成逻辑测试通过！核心功能正常工作。")
        return 0
    else:
        print("\n⚠️  部分测试失败，请检查实现。")
        return 1

if __name__ == "__main__":
    sys.exit(main())
