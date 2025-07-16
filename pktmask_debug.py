#!/usr/bin/env python3
"""
PktMask Windows Debug Launcher
专门用于Windows环境的调试启动脚本
"""

import sys
import os
import traceback
import logging
from pathlib import Path

# 设置详细日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pktmask_debug.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def setup_environment():
    """设置环境"""
    logger.info("=== 设置环境 ===")
    
    # 添加src目录到Python路径
    current_dir = Path(__file__).parent
    src_dir = current_dir / 'src'
    
    if src_dir.exists():
        sys.path.insert(0, str(src_dir))
        logger.info(f"✅ 添加src目录到路径: {src_dir}")
    else:
        logger.warning(f"⚠️ src目录不存在: {src_dir}")
    
    # 设置环境变量
    os.environ['PKTMASK_DEBUG'] = '1'
    os.environ['QT_DEBUG_PLUGINS'] = '1'
    
    logger.info(f"Python版本: {sys.version}")
    logger.info(f"工作目录: {os.getcwd()}")
    logger.info(f"Python路径: {sys.path[:5]}")

def test_qt_availability():
    """测试Qt可用性"""
    logger.info("=== 测试Qt可用性 ===")
    
    try:
        import PyQt6
        logger.info(f"✅ PyQt6版本: {PyQt6.__version__}")
        
        from PyQt6.QtCore import QT_VERSION_STR, PYQT_VERSION_STR
        logger.info(f"✅ Qt版本: {QT_VERSION_STR}")
        logger.info(f"✅ PyQt版本: {PYQT_VERSION_STR}")
        
        from PyQt6.QtWidgets import QApplication
        logger.info("✅ QApplication导入成功")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Qt测试失败: {e}")
        traceback.print_exc()
        return False

def test_pktmask_imports():
    """测试PktMask模块导入"""
    logger.info("=== 测试PktMask模块导入 ===")
    
    modules_to_test = [
        'pktmask',
        'pktmask.__main__',
        'pktmask.config',
        'pktmask.config.app_config',
        'pktmask.gui',
        'pktmask.gui.main_window',
        'pktmask.gui.managers',
        'pktmask.gui.managers.pipeline_manager',
        'pktmask.services',
        'pktmask.services.pipeline_service'
    ]
    
    failed_imports = []
    
    for module in modules_to_test:
        try:
            __import__(module)
            logger.info(f"✅ {module}")
        except Exception as e:
            logger.error(f"❌ {module}: {e}")
            failed_imports.append(module)
    
    if failed_imports:
        logger.error(f"导入失败的模块: {failed_imports}")
        return False
    
    return True

def create_test_gui():
    """创建测试GUI"""
    logger.info("=== 创建测试GUI ===")
    
    try:
        from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QTextEdit
        from PyQt6.QtCore import pyqtSlot
        
        class TestWindow(QMainWindow):
            def __init__(self):
                super().__init__()
                self.setWindowTitle("PktMask Debug Test")
                self.setGeometry(100, 100, 600, 400)
                
                # 创建中央widget
                central_widget = QWidget()
                self.setCentralWidget(central_widget)
                
                # 创建布局
                layout = QVBoxLayout(central_widget)
                
                # 创建测试按钮
                self.test_button = QPushButton("Test Start Button")
                self.test_button.clicked.connect(self.on_test_button_clicked)
                layout.addWidget(self.test_button)
                
                # 创建日志显示
                self.log_display = QTextEdit()
                self.log_display.setReadOnly(True)
                layout.addWidget(self.log_display)
                
                self.log("测试窗口创建成功")
            
            def log(self, message):
                self.log_display.append(f"[{self.__class__.__name__}] {message}")
                logger.info(message)
            
            @pyqtSlot()
            def on_test_button_clicked(self):
                self.log("测试按钮被点击！")
                try:
                    # 尝试导入并创建真实的MainWindow
                    from pktmask.gui.main_window import MainWindow
                    self.log("MainWindow导入成功")
                    
                    # 创建MainWindow实例
                    main_window = MainWindow()
                    self.log("MainWindow创建成功")
                    
                    # 检查start button
                    if hasattr(main_window, 'start_proc_btn'):
                        self.log(f"找到start_proc_btn: {main_window.start_proc_btn.text()}")
                        self.log(f"按钮启用状态: {main_window.start_proc_btn.isEnabled()}")
                        
                        # 检查pipeline_manager
                        if hasattr(main_window, 'pipeline_manager'):
                            self.log("找到pipeline_manager")
                            
                            # 尝试调用toggle_pipeline_processing
                            try:
                                main_window.pipeline_manager.toggle_pipeline_processing()
                                self.log("✅ toggle_pipeline_processing调用成功")
                            except Exception as e:
                                self.log(f"❌ toggle_pipeline_processing调用失败: {e}")
                        else:
                            self.log("❌ 未找到pipeline_manager")
                    else:
                        self.log("❌ 未找到start_proc_btn")
                        
                except Exception as e:
                    self.log(f"❌ 测试失败: {e}")
                    traceback.print_exc()
        
        # 创建应用
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # 创建测试窗口
        window = TestWindow()
        window.show()
        
        logger.info("✅ 测试GUI创建成功")
        return app, window
        
    except Exception as e:
        logger.error(f"❌ 测试GUI创建失败: {e}")
        traceback.print_exc()
        return None, None

def main():
    """主函数"""
    logger.info("开始PktMask Windows调试...")
    
    # 设置环境
    setup_environment()
    
    # 测试Qt
    if not test_qt_availability():
        logger.error("Qt不可用，退出")
        return 1
    
    # 测试PktMask导入
    if not test_pktmask_imports():
        logger.error("PktMask模块导入失败，退出")
        return 1
    
    # 创建测试GUI
    app, window = create_test_gui()
    if not app or not window:
        logger.error("测试GUI创建失败，退出")
        return 1
    
    logger.info("启动GUI事件循环...")
    try:
        return app.exec()
    except KeyboardInterrupt:
        logger.info("用户中断")
        return 0
    except Exception as e:
        logger.error(f"GUI运行时错误: {e}")
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
