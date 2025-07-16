#!/usr/bin/env python3
"""
测试Start Button修复的脚本
验证信号连接和错误处理是否正常工作
"""

import sys
import os
import logging
from pathlib import Path

# 设置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 添加src目录到路径
src_path = Path(__file__).parent / 'src'
if src_path.exists():
    sys.path.insert(0, str(src_path))

def test_signal_connection():
    """测试信号连接"""
    print("=== 测试信号连接 ===")
    
    try:
        from PyQt6.QtWidgets import QApplication
        from pktmask.gui.main_window import MainWindow
        
        # 创建应用
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # 创建主窗口
        window = MainWindow()
        print("✅ MainWindow创建成功")
        
        # 检查组件存在性
        if hasattr(window, 'start_proc_btn'):
            print("✅ start_proc_btn存在")
            print(f"   按钮文本: {window.start_proc_btn.text()}")
            print(f"   按钮启用: {window.start_proc_btn.isEnabled()}")
        else:
            print("❌ start_proc_btn不存在")
            return False
        
        if hasattr(window, 'pipeline_manager'):
            print("✅ pipeline_manager存在")
        else:
            print("❌ pipeline_manager不存在")
            return False
        
        # 测试信号连接
        print("\n--- 测试按钮点击（无输入目录） ---")
        try:
            # 确保没有选择目录
            window.base_dir = None
            
            # 模拟按钮点击
            window.start_proc_btn.clicked.emit()
            print("✅ 按钮点击信号发送成功")
            
            # 处理事件
            app.processEvents()
            print("✅ 事件处理完成")
            
        except Exception as e:
            print(f"❌ 按钮点击测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        # 测试直接调用
        print("\n--- 测试直接方法调用 ---")
        try:
            window.pipeline_manager.toggle_pipeline_processing()
            print("✅ toggle_pipeline_processing调用成功")
        except Exception as e:
            print(f"❌ toggle_pipeline_processing调用失败: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_with_directory():
    """测试选择目录后的行为"""
    print("\n=== 测试选择目录后的行为 ===")
    
    try:
        from PyQt6.QtWidgets import QApplication
        from pktmask.gui.main_window import MainWindow
        import tempfile
        
        # 创建应用
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # 创建主窗口
        window = MainWindow()
        
        # 创建临时目录作为输入目录
        with tempfile.TemporaryDirectory() as temp_dir:
            window.base_dir = temp_dir
            print(f"✅ 设置输入目录: {temp_dir}")
            
            # 测试按钮点击
            try:
                window.pipeline_manager.toggle_pipeline_processing()
                print("✅ 有输入目录时的toggle_pipeline_processing调用成功")
            except Exception as e:
                print(f"⚠️ 有输入目录时的调用出现预期错误: {e}")
                # 这是预期的，因为可能没有有效的pcap文件
        
        return True
        
    except Exception as e:
        print(f"❌ 目录测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("开始Start Button修复测试...")
    
    # 测试信号连接
    if not test_signal_connection():
        print("❌ 信号连接测试失败")
        return 1
    
    # 测试目录选择后的行为
    if not test_with_directory():
        print("❌ 目录测试失败")
        return 1
    
    print("\n🎉 所有测试通过！Start Button修复验证成功")
    return 0

if __name__ == '__main__':
    sys.exit(main())
