#!/usr/bin/env python3
"""
Windows Start Button Debug Script
诊断Windows构建版本中start button点击无反应的问题
"""

import sys
import os
import traceback
import logging
from pathlib import Path

# 设置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('debug_start_button.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def test_imports():
    """测试关键模块导入"""
    logger.info("=== 测试模块导入 ===")
    
    try:
        import PyQt6
        logger.info(f"✅ PyQt6 导入成功: {PyQt6.__version__}")
    except Exception as e:
        logger.error(f"❌ PyQt6 导入失败: {e}")
        return False
    
    try:
        from PyQt6.QtWidgets import QApplication
        logger.info("✅ QApplication 导入成功")
    except Exception as e:
        logger.error(f"❌ QApplication 导入失败: {e}")
        return False
    
    try:
        # 添加src目录到路径
        src_path = Path(__file__).parent / 'src'
        if src_path.exists():
            sys.path.insert(0, str(src_path))
            logger.info(f"✅ 添加src路径: {src_path}")
        
        from pktmask.gui.main_window import MainWindow
        logger.info("✅ MainWindow 导入成功")
    except Exception as e:
        logger.error(f"❌ MainWindow 导入失败: {e}")
        traceback.print_exc()
        return False
    
    return True

def test_gui_creation():
    """测试GUI创建"""
    logger.info("=== 测试GUI创建 ===")
    
    try:
        from PyQt6.QtWidgets import QApplication
        from pktmask.gui.main_window import MainWindow
        
        # 创建应用
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        logger.info("✅ QApplication 创建成功")
        
        # 创建主窗口
        window = MainWindow()
        logger.info("✅ MainWindow 创建成功")
        
        # 检查start button
        if hasattr(window, 'start_proc_btn'):
            logger.info("✅ start_proc_btn 存在")
            logger.info(f"   按钮文本: {window.start_proc_btn.text()}")
            logger.info(f"   按钮启用: {window.start_proc_btn.isEnabled()}")
            
            # 检查信号连接
            if hasattr(window, 'pipeline_manager'):
                logger.info("✅ pipeline_manager 存在")
            else:
                logger.error("❌ pipeline_manager 不存在")
                
        else:
            logger.error("❌ start_proc_btn 不存在")
            
        return window, app
        
    except Exception as e:
        logger.error(f"❌ GUI创建失败: {e}")
        traceback.print_exc()
        return None, None

def test_button_click():
    """测试按钮点击"""
    logger.info("=== 测试按钮点击 ===")
    
    window, app = test_gui_creation()
    if not window:
        return False
    
    try:
        # 模拟按钮点击
        if hasattr(window, 'start_proc_btn'):
            logger.info("准备模拟按钮点击...")
            
            # 检查点击处理函数
            if hasattr(window, 'pipeline_manager') and hasattr(window.pipeline_manager, 'toggle_pipeline_processing'):
                logger.info("✅ toggle_pipeline_processing 方法存在")
                
                # 直接调用处理函数
                try:
                    window.pipeline_manager.toggle_pipeline_processing()
                    logger.info("✅ toggle_pipeline_processing 调用成功")
                except Exception as e:
                    logger.error(f"❌ toggle_pipeline_processing 调用失败: {e}")
                    traceback.print_exc()
                    
            else:
                logger.error("❌ toggle_pipeline_processing 方法不存在")
                
            # 模拟点击信号
            try:
                window.start_proc_btn.clicked.emit()
                logger.info("✅ 按钮点击信号发送成功")
            except Exception as e:
                logger.error(f"❌ 按钮点击信号发送失败: {e}")
                traceback.print_exc()
                
        return True
        
    except Exception as e:
        logger.error(f"❌ 按钮点击测试失败: {e}")
        traceback.print_exc()
        return False

def test_pipeline_manager():
    """测试PipelineManager"""
    logger.info("=== 测试PipelineManager ===")
    
    try:
        from pktmask.gui.managers.pipeline_manager import PipelineManager
        logger.info("✅ PipelineManager 导入成功")
        
        # 创建模拟主窗口
        class MockMainWindow:
            def __init__(self):
                from pktmask.config.app_config import get_app_config
                self.config = get_app_config()
                self.base_dir = None
                self.current_output_dir = None
                
        mock_window = MockMainWindow()
        pipeline_manager = PipelineManager(mock_window)
        logger.info("✅ PipelineManager 创建成功")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ PipelineManager 测试失败: {e}")
        traceback.print_exc()
        return False

def check_dependencies():
    """检查依赖"""
    logger.info("=== 检查依赖 ===")
    
    dependencies = [
        'scapy', 'pydantic', 'yaml', 'typer', 
        'markdown', 'jinja2', 'psutil'
    ]
    
    for dep in dependencies:
        try:
            __import__(dep)
            logger.info(f"✅ {dep} 可用")
        except ImportError as e:
            logger.error(f"❌ {dep} 不可用: {e}")

def main():
    """主函数"""
    logger.info("开始Windows Start Button调试...")
    logger.info(f"Python版本: {sys.version}")
    logger.info(f"工作目录: {os.getcwd()}")
    logger.info(f"Python路径: {sys.path[:3]}...")  # 只显示前3个路径
    
    # 检查依赖
    check_dependencies()
    
    # 测试导入
    if not test_imports():
        logger.error("模块导入失败，停止测试")
        return
    
    # 测试PipelineManager
    test_pipeline_manager()
    
    # 测试GUI创建
    window, app = test_gui_creation()
    if not window:
        logger.error("GUI创建失败，停止测试")
        return
    
    # 测试按钮点击
    test_button_click()
    
    logger.info("调试完成，请查看debug_start_button.log文件")

if __name__ == '__main__':
    main()
