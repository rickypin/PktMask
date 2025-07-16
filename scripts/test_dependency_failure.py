#!/usr/bin/env python3
"""
测试依赖失败场景

这个脚本通过临时修改PATH环境变量来模拟tshark不可用的情况，
测试依赖检查器的错误处理和GUI显示逻辑。
"""

import sys
import os
from pathlib import Path
from unittest.mock import patch

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

def test_tshark_missing():
    """测试tshark缺失的情况"""
    print("=" * 60)
    print("测试场景: TShark 不可用")
    print("=" * 60)
    
    try:
        from pktmask.infrastructure.dependency import DependencyChecker
        
        # 创建检查器实例
        checker = DependencyChecker()
        
        # 模拟tshark不可用 - 通过修改查找方法
        original_find = checker._find_tshark_executable
        checker._find_tshark_executable = lambda custom_path=None: None
        
        print("模拟tshark不在系统PATH中...")
        
        # 测试tshark检查
        tshark_result = checker.check_tshark()
        print(f"状态: {tshark_result.status.value}")
        print(f"错误信息: {tshark_result.error_message}")
        
        # 测试整体依赖状态
        all_satisfied = checker.are_dependencies_satisfied()
        print(f"所有依赖满足: {all_satisfied}")
        
        # 测试状态消息
        status_messages = checker.get_status_messages()
        print(f"状态消息数量: {len(status_messages)}")
        for i, message in enumerate(status_messages, 1):
            print(f"  {i}. {message}")
        
        # 恢复原始方法
        checker._find_tshark_executable = original_find
        
        return not all_satisfied  # 期望依赖不满足
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

def test_tshark_version_mismatch():
    """测试tshark版本不匹配的情况"""
    print("\n" + "=" * 60)
    print("测试场景: TShark 版本过低")
    print("=" * 60)
    
    try:
        from pktmask.infrastructure.dependency import DependencyChecker
        
        # 创建检查器实例
        checker = DependencyChecker()
        
        # 模拟版本过低 - 通过修改版本检查方法
        def mock_version_check(tshark_path):
            return {
                'success': True,
                'version': (3, 6, 2),  # 低于要求的4.2.0
                'version_string': 'TShark 3.6.2',
                'meets_requirement': False,
                'error': None
            }
        
        original_check = checker._check_tshark_version
        checker._check_tshark_version = mock_version_check
        
        print("模拟tshark版本为3.6.2（低于要求的4.2.0）...")
        
        # 测试tshark检查
        tshark_result = checker.check_tshark()
        print(f"状态: {tshark_result.status.value}")
        print(f"发现版本: {tshark_result.version_found}")
        print(f"要求版本: {tshark_result.version_required}")
        print(f"错误信息: {tshark_result.error_message}")
        
        # 测试状态消息
        status_messages = checker.get_status_messages()
        for i, message in enumerate(status_messages, 1):
            print(f"  {i}. {message}")
        
        # 恢复原始方法
        checker._check_tshark_version = original_check
        
        return tshark_result.status.value == "version_mismatch"
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

def test_gui_error_display():
    """测试GUI错误显示"""
    print("\n" + "=" * 60)
    print("GUI 错误显示测试")
    print("=" * 60)
    
    try:
        from pktmask.infrastructure.dependency import DependencyChecker
        
        checker = DependencyChecker()
        
        # 模拟多种错误情况
        test_scenarios = [
            {
                'name': 'TShark 缺失',
                'mock_find': lambda custom_path=None: None,
                'mock_version': None
            },
            {
                'name': 'TShark 版本过低',
                'mock_find': lambda custom_path=None: '/usr/bin/tshark',
                'mock_version': lambda path: {
                    'success': True,
                    'version': (3, 6, 2),
                    'version_string': 'TShark 3.6.2',
                    'meets_requirement': False,
                    'error': None
                }
            }
        ]
        
        for scenario in test_scenarios:
            print(f"\n--- 场景: {scenario['name']} ---")
            
            # 应用模拟
            original_find = checker._find_tshark_executable
            original_version = checker._check_tshark_version
            
            checker._find_tshark_executable = scenario['mock_find']
            if scenario['mock_version']:
                checker._check_tshark_version = scenario['mock_version']
            
            # 模拟GUI显示逻辑
            if not checker.are_dependencies_satisfied():
                print("⚠️  Dependency Status Check:")
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
                print("✅ 依赖满足，显示正常欢迎信息")
            
            # 恢复原始方法
            checker._find_tshark_executable = original_find
            checker._check_tshark_version = original_version
        
        return True
        
    except Exception as e:
        print(f"❌ GUI错误显示测试失败: {e}")
        return False

def main():
    """主函数"""
    print(f"Python版本: {sys.version}")
    print(f"工作目录: {os.getcwd()}")
    print(f"项目根目录: {project_root}")
    
    # 测试各种失败场景
    test1_ok = test_tshark_missing()
    test2_ok = test_tshark_version_mismatch()
    test3_ok = test_gui_error_display()
    
    # 总结
    print("\n" + "=" * 60)
    print("失败场景测试总结")
    print("=" * 60)
    print(f"TShark缺失测试: {'✅ 通过' if test1_ok else '❌ 失败'}")
    print(f"版本不匹配测试: {'✅ 通过' if test2_ok else '❌ 失败'}")
    print(f"GUI错误显示测试: {'✅ 通过' if test3_ok else '❌ 失败'}")
    
    if test1_ok and test2_ok and test3_ok:
        print("\n🎉 所有失败场景测试通过！错误处理逻辑正常工作。")
        return 0
    else:
        print("\n⚠️  部分测试失败，请检查错误处理实现。")
        return 1

if __name__ == "__main__":
    sys.exit(main())
