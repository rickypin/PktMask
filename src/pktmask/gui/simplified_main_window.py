#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
简化的主窗口实现

使用新的核心组件架构：
- AppController: 应用逻辑控制
- UIBuilder: 界面构建管理
- DataService: 数据文件服务

职责简化为：UI容器 + 基本事件分发
"""

import sys
import os
from typing import Optional
from PyQt6.QtWidgets import QMainWindow, QApplication
from PyQt6.QtCore import QEvent, pyqtSignal

from pktmask.infrastructure.logging import get_logger
from pktmask.infrastructure.config import get_app_config

# 导入新的核心组件
from .core.app_controller import AppController
from .core.ui_builder import UIBuilder
from .core.data_service import DataService


class SimplifiedMainWindow(QMainWindow):
    """Simplified main window - only responsible for UI container and basic event dispatching

    New architecture features:
    1. Single responsibility: Only serves as UI container and event dispatcher
    2. Clear components: 3 core components each with their own responsibilities
    3. Simplified dependencies: Reduced complex dependencies between components
    4. Maintenance friendly: Clear code structure, easy to understand and modify
    """
    
    # 基本信号定义
    error_occurred = pyqtSignal(str)  # 错误发生信号
    
    def __init__(self):
        super().__init__()
        self._logger = get_logger('simplified_main_window')
        
        # Basic configuration
        self.config = get_app_config()

        # Compatibility properties (maintain compatibility with original code)
        self.base_dir: Optional[str] = None
        self.output_dir: Optional[str] = None
        self.current_output_dir: Optional[str] = None
        self.time_elapsed = 0
        self.user_stopped = False

        # Initialize core components
        self._init_core_components()

        # Build interface
        self.ui_builder.setup_ui()

        # Connect signals
        self._connect_signals()

        self._logger.info("Simplified main window initialization completed")
    
    def _init_core_components(self):
        """初始化核心组件"""
        try:
            # 创建核心组件
            self.app_controller = AppController(self)
            self.ui_builder = UIBuilder(self)
            self.data_service = DataService(self)
            
            self._logger.info("核心组件初始化完成")
            
        except Exception as e:
            self._logger.error(f"核心组件初始化失败: {e}")
            raise
    
    def _connect_signals(self):
        """连接信号和槽"""
        try:
            # 应用控制器信号
            self.app_controller.progress_updated.connect(self._handle_progress_update)
            self.app_controller.status_changed.connect(self._handle_status_change)
            self.app_controller.error_occurred.connect(self._handle_error)
            self.app_controller.processing_finished.connect(self._handle_processing_finished)
            
            # UI控件信号
            if hasattr(self, 'dir_path_label'):
                self.dir_path_label.clicked.connect(self.data_service.select_input_directory)
            
            if hasattr(self, 'output_path_label'):
                self.output_path_label.clicked.connect(self.data_service.select_output_directory)
            
            if hasattr(self, 'start_proc_btn'):
                self.start_proc_btn.clicked.connect(self.app_controller.start_processing)
            
            # 选项变化信号
            if hasattr(self, 'anonymize_ips_cb'):
                self.anonymize_ips_cb.stateChanged.connect(self.ui_builder.update_start_button_state)
            if hasattr(self, 'remove_dupes_cb'):
                self.remove_dupes_cb.stateChanged.connect(self.ui_builder.update_start_button_state)
            if hasattr(self, 'mask_payloads_cb'):
                self.mask_payloads_cb.stateChanged.connect(self.ui_builder.update_start_button_state)
            
            self._logger.debug("信号连接完成")
            
        except Exception as e:
            self._logger.error(f"信号连接失败: {e}")
    
    def _handle_progress_update(self, event_type: str, data: dict):
        """处理进度更新"""
        try:
            # 更新进度条
            if hasattr(self, 'progress_bar') and 'progress' in data:
                progress = data['progress']
                if isinstance(progress, (int, float)):
                    self.progress_bar.setValue(int(progress))
                    if not self.progress_bar.isVisible():
                        self.progress_bar.setVisible(True)
            
            # 更新状态标签
            if hasattr(self, 'status_label') and 'message' in data:
                self.status_label.setText(data['message'])
            
            # 添加日志消息
            if 'message' in data:
                self.data_service.add_log_message(data['message'])
            
            # 更新统计信息
            if 'stats' in data:
                self._update_stats_display(data['stats'])
                
        except Exception as e:
            self._logger.error(f"处理进度更新失败: {e}")
    
    def _handle_status_change(self, status: str):
        """处理状态变化"""
        try:
            status_messages = {
                'processing_started': 'Processing started...',
                'processing_stopped': 'Processing stopped',
                'processing_finished': 'Processing completed'
            }
            
            message = status_messages.get(status, status)
            
            # 更新状态显示
            if hasattr(self, 'status_label'):
                self.status_label.setText(message)
            
            # 更新按钮状态
            if status == 'processing_started':
                if hasattr(self, 'start_proc_btn'):
                    self.start_proc_btn.setText("Stop Processing")
                    self.start_proc_btn.clicked.disconnect()
                    self.start_proc_btn.clicked.connect(self.app_controller.stop_processing)
            
            elif status in ['processing_stopped', 'processing_finished']:
                if hasattr(self, 'start_proc_btn'):
                    self.start_proc_btn.setText("Start Processing")
                    self.start_proc_btn.clicked.disconnect()
                    self.start_proc_btn.clicked.connect(self.app_controller.start_processing)
                    self.ui_builder.update_start_button_state()
                
                # 隐藏进度条
                if hasattr(self, 'progress_bar'):
                    self.progress_bar.setVisible(False)
            
            self._logger.debug(f"状态变化: {status}")
            
        except Exception as e:
            self._logger.error(f"处理状态变化失败: {e}")
    
    def _handle_error(self, error_message: str):
        """处理错误"""
        try:
            # 显示错误对话框
            self.ui_builder.show_error_dialog("Processing Error", error_message)
            
            # 添加错误日志
            self.data_service.add_log_message(f"ERROR: {error_message}")
            self.data_service.stats.add_error(error_message)
            
            # 发送错误信号（用于测试）
            self.error_occurred.emit(error_message)
            
            self._logger.error(f"处理错误: {error_message}")
            
        except Exception as e:
            self._logger.error(f"处理错误回调失败: {e}")
    
    def _handle_processing_finished(self, final_stats: dict):
        """处理完成回调"""
        try:
            # 生成最终报告
            report = self.data_service.generate_processing_report()
            
            # 显示报告
            if hasattr(self, 'summary_text'):
                self.summary_text.clear()
                self.summary_text.append(report)
            
            # 保存报告到文件
            self.data_service.save_report_to_file(report)
            
            # 添加完成日志
            self.data_service.add_log_message("Processing completed successfully!")
            
            # 显示完成对话框
            self.ui_builder.show_info_dialog(
                "Processing Complete",
                f"Processing completed in {final_stats.get('elapsed_time', 0)} seconds.\n"
                f"Report saved to output directory."
            )
            
            self._logger.info("处理完成")
            
        except Exception as e:
            self._logger.error(f"处理完成回调失败: {e}")
    
    def _update_stats_display(self, stats: dict):
        """更新统计显示"""
        try:
            # 更新数据服务中的统计
            if 'files_processed' in stats:
                self.data_service.stats.files_processed = stats['files_processed']
            if 'packets_processed' in stats:
                self.data_service.stats.packets_processed = stats['packets_processed']
            if 'packets_modified' in stats:
                self.data_service.stats.packets_modified = stats['packets_modified']
            
        except Exception as e:
            self._logger.error(f"更新统计显示失败: {e}")
    
    def update_time_elapsed(self):
        """更新经过时间显示（兼容性方法）"""
        try:
            if hasattr(self, 'time_label') and hasattr(self, 'time_elapsed'):
                hours = self.time_elapsed // 3600
                minutes = (self.time_elapsed % 3600) // 60
                seconds = self.time_elapsed % 60
                time_str = f"Time: {hours:02d}:{minutes:02d}:{seconds:02d}"
                self.time_label.setText(time_str)
                
        except Exception as e:
            self._logger.error(f"更新时间显示失败: {e}")
    
    def changeEvent(self, event: QEvent):
        """处理窗口事件（主题变化等）"""
        try:
            # 委托给UI构建器处理主题变化
            self.ui_builder.apply_theme_change(event)
            super().changeEvent(event)
            
        except Exception as e:
            self._logger.error(f"处理窗口事件失败: {e}")
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        try:
            # 停止处理
            if self.app_controller.state.is_running:
                self.app_controller.stop_processing()
            
            # 清理资源
            self.app_controller.cleanup()
            self.data_service.cleanup()
            
            # 保存窗口状态
            self._save_window_state()
            
            event.accept()
            self._logger.info("主窗口关闭")
            
        except Exception as e:
            self._logger.error(f"窗口关闭处理失败: {e}")
            event.accept()
    
    def _save_window_state(self):
        """保存窗口状态"""
        try:
            # 保存窗口几何信息
            geometry = self.saveGeometry()
            # 这里可以保存到配置文件
            
            # 保存用户偏好
            if self.data_service.last_opened_dir:
                # 保存最后打开的目录
                pass
            
        except Exception as e:
            self._logger.error(f"保存窗口状态失败: {e}")


def main():
    """主函数 - 使用简化的主窗口"""
    import os
    
    # 检查测试模式
    test_mode = os.getenv('PKTMASK_TEST_MODE', '').lower() in ('true', '1', 'yes')
    headless_mode = os.getenv('PKTMASK_HEADLESS', '').lower() in ('true', '1', 'yes')
    
    if test_mode or headless_mode:
        try:
            app = QApplication.instance()
            if app is None:
                app = QApplication(sys.argv)
            
            window = SimplifiedMainWindow()
            if hasattr(window, 'set_test_mode'):
                window.set_test_mode(True)
            
            return window if test_mode else 0
            
        except Exception as e:
            print(f"GUI initialization failed in test mode: {e}")
            return None
    else:
        # 正常模式
        app = QApplication(sys.argv)
        window = SimplifiedMainWindow()
        window.show()
        sys.exit(app.exec())


if __name__ == "__main__":
    main()
