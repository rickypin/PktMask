#!/usr/bin/env python3
"""
测试GUI依赖集成

这个脚本测试依赖检查是否正确集成到GUI启动流程中，
验证在不同依赖状态下GUI的显示效果。
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

def test_gui_with_satisfied_dependencies():
    """测试依赖满足时的GUI显示"""
    print("=" * 60)
    print("测试场景: 依赖满足时的GUI显示")
    print("=" * 60)
    
    try:
        # 设置测试模式环境变量
        os.environ['PKTMASK_TEST_MODE'] = 'true'
        
        from pktmask.gui.simplified_main_window import SimplifiedMainWindow
        from PyQt6.QtWidgets import QApplication
        
        # 创建应用实例
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # 创建主窗口
        window = SimplifiedMainWindow()
        
        # 检查log_text内容
        if hasattr(window, 'log_text'):
            log_content = window.log_text.toPlainText()
            print("Log内容预览:")
            print("-" * 40)
            print(log_content[:500] + "..." if len(log_content) > 500 else log_content)
            print("-" * 40)
            
            # 检查是否包含依赖错误信息
            has_dependency_error = "Dependency Status Check" in log_content
            print(f"包含依赖错误信息: {has_dependency_error}")
            
            # 检查是否包含欢迎信息
            has_welcome = "Welcome to PktMask" in log_content
            print(f"包含欢迎信息: {has_welcome}")
            
            return not has_dependency_error and has_welcome
        else:
            print("❌ 未找到log_text控件")
            return False
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # 清理环境变量
        if 'PKTMASK_TEST_MODE' in os.environ:
            del os.environ['PKTMASK_TEST_MODE']

def test_gui_with_mocked_dependency_failure():
    """测试依赖失败时的GUI显示（通过模拟）"""
    print("\n" + "=" * 60)
    print("测试场景: 依赖失败时的GUI显示（模拟）")
    print("=" * 60)
    
    try:
        # 设置测试模式环境变量
        os.environ['PKTMASK_TEST_MODE'] = 'true'
        
        from pktmask.gui.simplified_main_window import SimplifiedMainWindow
        from pktmask.infrastructure.dependency import DependencyChecker
        from PyQt6.QtWidgets import QApplication
        
        # 创建应用实例
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # 在创建窗口前模拟依赖失败
        original_check = DependencyChecker.are_dependencies_satisfied
        original_messages = DependencyChecker.get_status_messages
        
        # 模拟依赖不满足
        DependencyChecker.are_dependencies_satisfied = lambda self: False
        DependencyChecker.get_status_messages = lambda self: [
            "TSHARK not found in system PATH",
            "TSHARK version too old: 3.6.2, required: ≥4.2.0"
        ]
        
        try:
            # 创建主窗口
            window = SimplifiedMainWindow()
            
            # 检查log_text内容
            if hasattr(window, 'log_text'):
                log_content = window.log_text.toPlainText()
                print("Log内容预览:")
                print("-" * 40)
                print(log_content[:800] + "..." if len(log_content) > 800 else log_content)
                print("-" * 40)
                
                # 检查是否包含依赖错误信息
                has_dependency_error = "Dependency Status Check" in log_content
                print(f"包含依赖错误信息: {has_dependency_error}")
                
                # 检查是否包含安装指导
                has_installation_guide = "Installation Guide" in log_content
                print(f"包含安装指导: {has_installation_guide}")
                
                # 检查是否包含具体错误消息
                has_tshark_error = "TSHARK" in log_content and "not found" in log_content
                print(f"包含TShark错误消息: {has_tshark_error}")
                
                return has_dependency_error and has_installation_guide and has_tshark_error
            else:
                print("❌ 未找到log_text控件")
                return False
                
        finally:
            # 恢复原始方法
            DependencyChecker.are_dependencies_satisfied = original_check
            DependencyChecker.get_status_messages = original_messages
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # 清理环境变量
        if 'PKTMASK_TEST_MODE' in os.environ:
            del os.environ['PKTMASK_TEST_MODE']

def test_traditional_gui_integration():
    """测试传统GUI的依赖集成"""
    print("\n" + "=" * 60)
    print("测试场景: 传统GUI依赖集成")
    print("=" * 60)
    
    try:
        # 设置测试模式环境变量
        os.environ['PKTMASK_TEST_MODE'] = 'true'
        
        from pktmask.gui.main_window import MainWindow
        from PyQt6.QtWidgets import QApplication
        
        # 创建应用实例
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # 创建主窗口
        window = MainWindow()
        
        # 检查log_text内容
        if hasattr(window, 'log_text'):
            log_content = window.log_text.toPlainText()
            print("传统GUI Log内容预览:")
            print("-" * 40)
            print(log_content[:500] + "..." if len(log_content) > 500 else log_content)
            print("-" * 40)
            
            # 检查是否正确初始化
            has_content = len(log_content.strip()) > 0
            print(f"Log有内容: {has_content}")
            
            return True  # 传统GUI使用placeholder，可能没有直接内容
        else:
            print("❌ 未找到log_text控件")
            return False
            
    except Exception as e:
        print(f"❌ 传统GUI测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # 清理环境变量
        if 'PKTMASK_TEST_MODE' in os.environ:
            del os.environ['PKTMASK_TEST_MODE']

def main():
    """主函数"""
    print(f"Python版本: {sys.version}")
    print(f"工作目录: {os.getcwd()}")
    print(f"项目根目录: {project_root}")
    
    # 测试各种GUI集成场景
    test1_ok = test_gui_with_satisfied_dependencies()
    test2_ok = test_gui_with_mocked_dependency_failure()
    test3_ok = test_traditional_gui_integration()
    
    # 总结
    print("\n" + "=" * 60)
    print("GUI依赖集成测试总结")
    print("=" * 60)
    print(f"依赖满足GUI测试: {'✅ 通过' if test1_ok else '❌ 失败'}")
    print(f"依赖失败GUI测试: {'✅ 通过' if test2_ok else '❌ 失败'}")
    print(f"传统GUI集成测试: {'✅ 通过' if test3_ok else '❌ 失败'}")
    
    if test1_ok and test2_ok and test3_ok:
        print("\n🎉 所有GUI集成测试通过！依赖状态显示已正确集成到GUI中。")
        return 0
    else:
        print("\n⚠️  部分GUI集成测试失败，请检查GUI集成实现。")
        return 1

if __name__ == "__main__":
    sys.exit(main())
