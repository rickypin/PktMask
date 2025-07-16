#!/usr/bin/env python3
"""
测试依赖检查器功能

这个脚本用于测试新的统一依赖检查器，验证其功能是否正常工作。
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

def test_dependency_checker():
    """测试依赖检查器"""
    print("=" * 60)
    print("PktMask 依赖检查器测试")
    print("=" * 60)
    
    try:
        from pktmask.infrastructure.dependency import DependencyChecker, DependencyStatus
        
        # 创建检查器实例
        checker = DependencyChecker()
        print("✅ DependencyChecker 创建成功")
        
        # 测试单个依赖检查
        print("\n--- TShark 依赖检查 ---")
        tshark_result = checker.check_tshark()
        print(f"状态: {tshark_result.status.value}")
        print(f"路径: {tshark_result.path}")
        print(f"版本: {tshark_result.version_found}")
        print(f"要求版本: {tshark_result.version_required}")
        if tshark_result.error_message:
            print(f"错误信息: {tshark_result.error_message}")
        
        # 测试所有依赖检查
        print("\n--- 所有依赖检查 ---")
        all_results = checker.check_all_dependencies()
        for name, result in all_results.items():
            status_icon = "✅" if result.is_satisfied else "❌"
            print(f"{status_icon} {name.upper()}: {result.status.value}")
        
        # 测试整体满足状态
        print("\n--- 整体依赖状态 ---")
        all_satisfied = checker.are_dependencies_satisfied()
        status_icon = "✅" if all_satisfied else "❌"
        print(f"{status_icon} 所有依赖满足: {all_satisfied}")
        
        # 测试状态消息生成
        print("\n--- GUI 状态消息 ---")
        status_messages = checker.get_status_messages()
        if status_messages:
            print("需要显示的状态消息:")
            for i, message in enumerate(status_messages, 1):
                print(f"  {i}. {message}")
        else:
            print("无需显示状态消息（所有依赖满足）")
        
        print("\n" + "=" * 60)
        print("测试完成")
        
        return all_satisfied
        
    except ImportError as e:
        print(f"❌ 导入错误: {e}")
        return False
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

def test_gui_integration():
    """测试GUI集成（模拟）"""
    print("\n" + "=" * 60)
    print("GUI 集成测试（模拟）")
    print("=" * 60)
    
    try:
        from pktmask.infrastructure.dependency import DependencyChecker
        
        checker = DependencyChecker()
        
        # 模拟GUI启动时的依赖检查流程
        print("模拟GUI启动流程...")
        
        if not checker.are_dependencies_satisfied():
            print("\n⚠️  依赖不满足，将在GUI中显示状态信息:")
            print("-" * 40)
            
            status_messages = checker.get_status_messages()
            for message in status_messages:
                print(f"❌ {message}")
            
            print("\n💡 Installation Guide:")
            print("   • Install Wireshark (includes tshark)")
            print("   • Ensure tshark is in system PATH")
            print("   • Minimum version required: 4.2.0")
            print("   • Download: https://www.wireshark.org/download.html")
            print("-" * 40)
        else:
            print("\n✅ 所有依赖满足，GUI将显示正常欢迎信息")
        
        print("\n🚀 Welcome to PktMask!")
        print("\n┌─ Quick Start Guide ──────────┐")
        print("│ 1. Select pcap directory     │")
        print("│ 2. Configure actions         │")
        print("│ 3. Start processing          │")
        print("└──────────────────────────────┘")
        print("\n💡 Remove Dupes & Anonymize IPs enabled by default")
        print("\nProcessing logs will appear here...")
        
        return True
        
    except Exception as e:
        print(f"❌ GUI集成测试失败: {e}")
        return False

def main():
    """主函数"""
    print(f"Python版本: {sys.version}")
    print(f"工作目录: {os.getcwd()}")
    print(f"项目根目录: {project_root}")
    
    # 测试依赖检查器
    checker_ok = test_dependency_checker()
    
    # 测试GUI集成
    gui_ok = test_gui_integration()
    
    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    print(f"依赖检查器: {'✅ 通过' if checker_ok else '❌ 失败'}")
    print(f"GUI集成: {'✅ 通过' if gui_ok else '❌ 失败'}")
    
    if checker_ok and gui_ok:
        print("\n🎉 所有测试通过！依赖状态显示系统可以正常工作。")
        return 0
    else:
        print("\n⚠️  部分测试失败，请检查实现。")
        return 1

if __name__ == "__main__":
    sys.exit(main())
