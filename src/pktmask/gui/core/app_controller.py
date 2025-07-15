#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
应用控制器 - 统一的业务逻辑管理

合并原有的 PipelineManager 和 EventCoordinator 功能，
提供简化的应用逻辑控制接口。
"""

import os
from typing import Optional, Dict, Any
from PyQt6.QtCore import QObject, QTimer, QTime, pyqtSignal
from PyQt6.QtWidgets import QApplication

from pktmask.infrastructure.logging import get_logger
from pktmask.infrastructure.config import get_app_config


class ProcessingState:
    """处理状态管理"""
    
    def __init__(self):
        self.is_running = False
        self.user_stopped = False
        self.start_time: Optional[QTime] = None
        self.elapsed_time = 0
        self.current_file: Optional[str] = None
        
    def start(self):
        """开始处理"""
        self.is_running = True
        self.user_stopped = False
        self.start_time = QTime.currentTime()
        self.elapsed_time = 0
        
    def stop(self):
        """停止处理"""
        self.is_running = False
        self.current_file = None
        
    def user_stop(self):
        """用户主动停止"""
        self.user_stopped = True
        self.stop()


class AppController(QObject):
    """应用控制器 - 统一的业务逻辑管理
    
    职责：
    1. 处理流程控制（启动、停止、暂停）
    2. 状态管理（处理状态、进度跟踪）
    3. 事件协调（组件间通信）
    4. 配置管理（处理参数配置）
    """
    
    # 信号定义
    progress_updated = pyqtSignal(str, dict)  # 进度更新
    status_changed = pyqtSignal(str)          # 状态变化
    error_occurred = pyqtSignal(str)          # 错误发生
    processing_finished = pyqtSignal(dict)    # 处理完成
    
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.config = get_app_config()
        self._logger = get_logger(__name__)
        
        # 状态管理
        self.state = ProcessingState()
        
        # 计时器
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_elapsed_time)
        
        # 处理线程
        self.processing_thread: Optional[object] = None
        
        self._logger.info("Application controller initialization completed")
    
    def start_processing(self):
        """启动处理流程"""
        try:
            # 验证输入
            if not self._validate_inputs():
                return False
                
            # 准备处理
            if not self._prepare_processing():
                return False
                
            # 启动处理
            self._start_processing_thread()
            
            # 更新状态
            self.state.start()
            self.timer.start(1000)  # 每秒更新一次
            
            # 发送状态变化信号
            self.status_changed.emit("processing_started")
            self._logger.info("处理流程启动成功")
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to start processing flow: {e}")
            self.error_occurred.emit(f"启动失败: {str(e)}")
            return False
    
    def stop_processing(self):
        """停止处理流程"""
        try:
            # 设置停止标志
            self.state.user_stop()

            # 停止处理线程 - Store thread reference to avoid race condition
            thread = self.processing_thread
            if thread:
                thread.stop()
                if not thread.wait(3000):
                    thread.terminate()
                    thread.wait()

            # 停止计时器
            self.timer.stop()

            # 发送状态变化信号
            self.status_changed.emit("processing_stopped")
            self._logger.info("处理流程已停止")

        except Exception as e:
            self._logger.error(f"Failed to stop processing flow: {e}")
            self.error_occurred.emit(f"Stop failed: {str(e)}")
    
    def get_processing_config(self) -> Dict[str, Any]:
        """获取处理配置（使用标准命名规范）"""
        # 从主窗口获取用户选择的配置
        config = {
            'anonymize_ips': getattr(self.main_window, 'anonymize_ips_cb', None) and self.main_window.anonymize_ips_cb.isChecked(),
            'remove_dupes': getattr(self.main_window, 'remove_dupes_cb', None) and self.main_window.remove_dupes_cb.isChecked(),
            'mask_payloads': getattr(self.main_window, 'mask_payloads_cb', None) and self.main_window.mask_payloads_cb.isChecked(),
        }
        return config
    
    def _validate_inputs(self) -> bool:
        """验证输入参数"""
        # 检查输入目录
        if not hasattr(self.main_window, 'base_dir') or not self.main_window.base_dir:
            self.error_occurred.emit("Please select input directory")
            return False

        if not os.path.exists(self.main_window.base_dir):
            self.error_occurred.emit("Input directory does not exist")
            return False

        # Check processing options
        config = self.get_processing_config()
        if not any(config.values()):
            self.error_occurred.emit("Please select at least one processing option")
            return False
            
        return True
    
    def _prepare_processing(self) -> bool:
        """准备处理环境"""
        try:
            # 生成输出目录
            if hasattr(self.main_window, 'file_manager'):
                output_dir = self.main_window.file_manager.generate_actual_output_path()
                self.main_window.current_output_dir = output_dir
            
            # 创建输出目录
            if hasattr(self.main_window, 'current_output_dir'):
                os.makedirs(self.main_window.current_output_dir, exist_ok=True)
            
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to prepare processing environment: {e}")
            self.error_occurred.emit(f"Preparation failed: {str(e)}")
            return False
    
    def _start_processing_thread(self):
        """启动处理线程"""
        try:
            # 导入处理线程类
            from ..main_window import ServicePipelineThread
            
            # 创建处理线程
            self.processing_thread = ServicePipelineThread(
                self.get_processing_config(),
                self.main_window.base_dir,
                self.main_window.current_output_dir
            )
            
            # 连接信号
            self.processing_thread.progress_signal.connect(self._handle_progress_update)
            self.processing_thread.finished.connect(self._handle_processing_finished)
            
            # 启动线程
            self.processing_thread.start()
            
        except Exception as e:
            self._logger.error(f"Failed to start processing thread: {e}")
            raise
    
    def _update_elapsed_time(self):
        """更新经过时间"""
        if self.state.start_time:
            self.state.elapsed_time = self.state.start_time.secsTo(QTime.currentTime())
            
            # 更新主窗口显示
            if hasattr(self.main_window, 'time_elapsed'):
                self.main_window.time_elapsed = self.state.elapsed_time
            if hasattr(self.main_window, 'update_time_elapsed'):
                self.main_window.update_time_elapsed()
    
    def _handle_progress_update(self, event_type: str, data: dict):
        """处理进度更新"""
        self.progress_updated.emit(event_type, data)
        
        # 更新当前处理文件
        if 'filename' in data:
            self.state.current_file = data['filename']
    
    def _handle_processing_finished(self):
        """处理完成回调"""
        try:
            # 停止计时器
            self.timer.stop()
            
            # 更新状态
            self.state.stop()
            
            # 收集最终统计
            final_stats = {
                'elapsed_time': self.state.elapsed_time,
                'user_stopped': self.state.user_stopped,
                'completion_time': QTime.currentTime().toString()
            }
            
            # 发送完成信号
            self.processing_finished.emit(final_stats)
            self.status_changed.emit("processing_finished")
            
            self._logger.info("Processing flow completed")

        except Exception as e:
            self._logger.error(f"Failed to handle processing completion: {e}")
            self.error_occurred.emit(f"Completion handling failed: {str(e)}")
    
    def cleanup(self):
        """清理资源"""
        try:
            # 停止计时器
            if self.timer.isActive():
                self.timer.stop()
            
            # 清理处理线程
            if self.processing_thread and self.processing_thread.isRunning():
                self.processing_thread.stop()
                self.processing_thread.wait(1000)
            
            self._logger.info("Application controller resource cleanup completed")

        except Exception as e:
            self._logger.error(f"Failed to cleanup resources: {e}")
