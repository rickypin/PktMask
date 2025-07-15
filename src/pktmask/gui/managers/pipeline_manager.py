#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Pipeline管理器 - 负责处理流程控制
"""

from typing import TYPE_CHECKING
from PyQt6.QtCore import QTimer

if TYPE_CHECKING:
    from ..main_window import MainWindow, PipelineThread

from pktmask.services import (
    PipelineServiceError,
    ConfigurationError,
    create_pipeline_executor,
    build_pipeline_config
)
from pktmask.core.events import PipelineEvents
from pktmask.infrastructure.logging import get_logger
from .statistics_manager import StatisticsManager

class PipelineManager:
    """Pipeline管理器 - 负责处理流程控制"""
    
    def __init__(self, main_window: 'MainWindow'):
        self.main_window = main_window
        self.config = main_window.config
        self._logger = get_logger(__name__)
        
        # 集成统计管理器
        self.statistics = StatisticsManager()
        
        # 处理状态
        self.processing_thread: 'PipelineThread' = None
        self.user_stopped = False
        
        # 保留计时器设置
        self._setup_timer()
    
    # === 直接使用statistics属性，无需额外访问器 ===
    
    def _setup_timer(self):
        """设置计时器"""
        self.main_window.time_elapsed = 0
        self.main_window.timer = QTimer()
        self.main_window.timer.timeout.connect(self.main_window.update_time_elapsed)
    
    def toggle_pipeline_processing(self):
        """切换处理流程状态"""
        if self.processing_thread and self.processing_thread.isRunning():
            self.stop_pipeline_processing()
        else:
            self.start_pipeline_processing()
    
    def start_pipeline_processing(self):
        """开始处理流程"""
        if not self.main_window.base_dir:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self.main_window, "Warning", "Please choose an input folder to process.")
            return

        # 生成实际输出目录路径
        self.main_window.current_output_dir = self.main_window.file_manager.generate_actual_output_path()
        
        # 创建输出目录
        try:
            import os
            os.makedirs(self.main_window.current_output_dir, exist_ok=True)
            self.main_window.update_log(f"📁 Created output directory: {os.path.basename(self.main_window.current_output_dir)}")
            
            # 更新输出路径显示
            self.main_window.output_path_label.setText(os.path.basename(self.main_window.current_output_dir))
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self.main_window, "Error", f"Failed to create output directory: {str(e)}")
            return

        # Reset UI and counters for new run
        self.main_window.log_text.clear()
        self.main_window.summary_text.clear()
        self.main_window.all_ip_reports.clear()
        self.main_window.files_processed_count = 0
        self.main_window.packets_processed_count = 0
        
        # 重置Live Dashboard显示
        self.main_window.files_processed_label.setText("0")
        self.main_window.packets_processed_label.setText("0")
        self.main_window.subdirs_files_counted.clear()
        self.main_window.subdirs_packets_counted.clear()
        self.main_window.printed_summary_headers.clear()
        self.main_window.file_processing_results.clear()  # 清空文件处理结果
        self.main_window.current_processing_file = None   # 重置当前处理文件
        self.main_window.global_ip_mappings.clear()      # 清空全局IP映射
        self.main_window.processed_files_count = 0       # 重置文件计数
        self.main_window.user_stopped = False            # 重置停止标志

        # 通过事件协调器禁用控件
        if hasattr(self.main_window, 'event_coordinator'):
            self.main_window.event_coordinator.request_ui_update('enable_controls',
                controls=['dir_path_label', 'output_path_label', 'anonymize_ips_cb', 'remove_dupes_cb', 'mask_payloads_cb'],
                enabled=False)
        else:
            # 备用方案：直接操作
            self.main_window.dir_path_label.setEnabled(False)
            self.main_window.output_path_label.setEnabled(False)
            for cb in [self.main_window.anonymize_ips_cb, self.main_window.remove_dupes_cb, self.main_window.mask_payloads_cb]:
                cb.setEnabled(False)

        # 创建并配置新的 PipelineExecutor
        config = build_pipeline_config(
            enable_anon=self.main_window.anonymize_ips_cb.isChecked(),
            enable_dedup=self.main_window.remove_dupes_cb.isChecked(),
            enable_mask=self.main_window.mask_payloads_cb.isChecked()
        )
        if not config:
            self._logger.warning("未选择任何处理步骤")
            return

        try:
            executor = create_pipeline_executor(config)
        except ConfigurationError as e:
            self._logger.error(f"配置错误: {str(e)}")
            self.main_window.update_log(f"配置错误: {str(e)}")
            return
        self._logger.info(f"构建了包含 {len(config)} 个Stage的 PipelineExecutor")

        # 开始处理
        self.start_processing(executor)
    
    def stop_pipeline_processing(self):
        """停止处理流程"""
        self.main_window.user_stopped = True  # 设置停止标志
        self.main_window.update_log("--- Stopping pipeline... ---")
        if self.processing_thread:
            self.processing_thread.stop()
            # 等待线程安全结束，最多等待 3 秒
            if not self.processing_thread.wait(3000):
                self.main_window.log_text.append("Warning: Pipeline did not stop gracefully, forcing termination.")
                self.processing_thread.terminate()
                self.processing_thread.wait()
        
        # 生成停止时的部分汇总统计
        self.main_window.report_manager.generate_partial_summary_on_stop()
        
        # 通过事件协调器重新启用控件
        if hasattr(self.main_window, 'event_coordinator'):
            self.main_window.event_coordinator.request_ui_update('enable_controls',
                controls=['dir_path_label', 'output_path_label', 'anonymize_ips_cb', 'remove_dupes_cb', 'mask_payloads_cb', 'start_proc_btn'],
                enabled=True)
            self.main_window.event_coordinator.request_ui_update('update_button_text',
                button='start_proc_btn', text='Start')
        else:
            # 备用方案：直接操作
            self.main_window.dir_path_label.setEnabled(True)
            self.main_window.output_path_label.setEnabled(True)
            for cb in [self.main_window.anonymize_ips_cb, self.main_window.remove_dupes_cb, self.main_window.mask_payloads_cb]:
                cb.setEnabled(True)
            # web_focused_cb 保持禁用状态，因为功能未完成
            self.main_window.start_proc_btn.setEnabled(True)
            self.main_window.start_proc_btn.setText("Start")
    
    def start_processing(self, executor):
        """启动处理线程"""
        # 导入新的PipelineThread（避免循环导入）
        from ..main_window import ServicePipelineThread
        
        # 创建处理线程
        self.processing_thread = ServicePipelineThread(
            executor, 
            self.main_window.base_dir, 
            self.main_window.current_output_dir
        )
        
        # 连接信号
        self.processing_thread.progress_signal.connect(self.handle_thread_progress)
        self.processing_thread.finished.connect(self.on_thread_finished)
        
        # 更新UI状态
        self.main_window.start_proc_btn.setText("Stop")
        self.main_window.start_proc_btn.setEnabled(True)
        self.main_window.ui_manager._update_start_button_style()
        
        # 开始计时（统一使用StatisticsManager）
        self.statistics.start_timing()
        self.main_window.time_elapsed = 0
        self.main_window.start_time = self.statistics.start_time  # 保持兼容性
        self.main_window.timer.start(100)  # 每100ms更新一次
        
        # 启动线程
        self.processing_thread.start()
        
        self._logger.info(f"处理线程已启动，输出目录: {self.main_window.current_output_dir}")
        self.main_window.update_log("🚀 Processing started...")
    
    def handle_thread_progress(self, event_type: PipelineEvents, data: dict):
        """处理线程进度事件"""
        try:
            # 首先让MainWindow处理事件以更新UI统计和收集数据
            self.main_window.handle_thread_progress(event_type, data)
            
            # 然后PipelineManager处理自己的逻辑
            # 处理管道启动事件
            if event_type in (PipelineEvents.PIPELINE_START, PipelineEvents.PIPELINE_STARTED):
                # Pipeline发送的是总目录数，但我们需要追踪文件数
                total_dirs = data.get('total_subdirs', data.get('total_files', 0))
                # 重置文件计数器（通过StatisticsManager）
                self.statistics.update_file_count(0)
                
            # 处理子目录开始事件
            elif event_type == PipelineEvents.SUBDIR_START:
                dir_name = data.get('name', 'Unknown directory')
                file_count = data.get('file_count', 0)
                self.statistics.set_total_files(file_count)  # 设置真正的文件总数
                
            # 处理文件完成事件
            elif event_type in (PipelineEvents.FILE_END, PipelineEvents.FILE_COMPLETED):
                self.statistics.increment_file_count()
                # 更新Live Dashboard显示
                self.main_window.files_processed_label.setText(str(self.statistics.files_processed))
                self._update_progress()
                
            # 处理管道完成事件
            elif event_type in (PipelineEvents.PIPELINE_END, PipelineEvents.PIPELINE_COMPLETED):
                self.processing_finished()
                
            # 处理步骤摘要事件
            elif event_type == PipelineEvents.STEP_SUMMARY:
                # 重要：收集步骤结果数据用于最终报告
                self.collect_step_result(data)
                
            # 处理错误事件
            elif event_type == PipelineEvents.ERROR:
                error_msg = data.get('message', data.get('error', 'Unknown error'))
                # MainWindow已经处理了，这里不需要重复
                
        except Exception as e:
            self._logger.error(f"处理进度事件时发生错误: {e}")
            self.main_window.processing_error(f"事件处理错误: {str(e)}")
    
    def collect_step_result(self, data: dict):
        """收集步骤结果"""
        step_name = data.get('step_name', '')
        filename = data.get('filename', data.get('path', ''))
        
        # 收集所有可用的结果数据
        result_data = {}
        
        # 从data中提取有用的统计信息
        for key, value in data.items():
            if key not in ['step_name', 'filename', 'path', 'type']:
                result_data[key] = value
        
        # 如果有现有的result字段，合并它
        if 'result' in data:
            if isinstance(data['result'], dict):
                result_data.update(data['result'])
            else:
                result_data['result'] = data['result']
        
        # 委托给StatisticsManager
        self.statistics.collect_step_result(step_name, filename, result_data)
        
        # 注意：实时统计由MainWindow处理
    
    def get_processing_stats(self) -> dict:
        """获取处理统计数据"""
        return self.statistics.get_processing_summary()
    
    def _update_progress(self):
        """更新进度条"""
        if self.statistics.total_files_to_process > 0:
            progress = int((self.statistics.files_processed / self.statistics.total_files_to_process) * 100)
            self.main_window._animate_progress_to(progress)
    
    def processing_finished(self):
        """处理完成"""
        # 首先清理线程状态，确保UI状态检查正确
        self.processing_thread = None

        # **修复**: 在生成报告之前，确保Live Dashboard显示最终的统计数据
        # 更新Live Dashboard显示为最终统计数据
        final_files_processed = self.statistics.files_processed
        final_packets_processed = self.statistics.packets_processed

        # 确保Live Dashboard显示最终的正确数据
        self.main_window.files_processed_label.setText(str(final_files_processed))
        self.main_window.packets_processed_label.setText(str(final_packets_processed))

        # 委托给ReportManager生成报告
        self.main_window.report_manager.generate_processing_finished_report()
        
        import os
        from pktmask.utils.file_ops import open_directory_in_system
        
        # 更新输出路径显示
        if self.main_window.current_output_dir:
            self.main_window.output_path_label.setText(os.path.basename(self.main_window.current_output_dir))
        self.main_window.update_log(f"Output directory ready. Click output path to view results.")
        
        # 如果配置启用，自动打开输出目录
        if self.main_window.config.ui.auto_open_output and self.main_window.current_output_dir:
            try:
                success = open_directory_in_system(self.main_window.current_output_dir)
                if success:
                    self.main_window.update_log(f"Auto-opened output directory: {os.path.basename(self.main_window.current_output_dir)}")
                else:
                    self._logger.warning("Failed to auto-open output directory")
            except Exception as e:
                self._logger.error(f"Error auto-opening output directory: {e}")
        
        # 使用QTimer.singleShot确保UI更新在事件循环的下一个周期执行
        from PyQt6.QtCore import QTimer

        def update_ui_state():
            """延迟更新UI状态"""
            # 直接设置按钮状态
            self.main_window.start_proc_btn.setText("Start")
            self.main_window.start_proc_btn.setEnabled(True)

            # 启用其他控件
            self.main_window.dir_path_label.setEnabled(True)
            self.main_window.output_path_label.setEnabled(True)
            for cb in [self.main_window.anonymize_ips_cb, self.main_window.remove_dupes_cb, self.main_window.mask_payloads_cb]:
                cb.setEnabled(True)

            # 更新按钮样式
            self.main_window.ui_manager._update_start_button_style()

        def ensure_final_stats_display():
            """确保最终统计数据正确显示在Live Dashboard中"""
            # **修复**: 再次确保Live Dashboard显示最终的正确统计数据
            # 防止任何后续操作意外重置显示
            self.main_window.files_processed_label.setText(str(final_files_processed))
            self.main_window.packets_processed_label.setText(str(final_packets_processed))

        # 延迟100ms执行UI更新
        QTimer.singleShot(100, update_ui_state)

        # **修复**: 延迟200ms再次确保统计数据显示正确，防止被其他操作覆盖
        QTimer.singleShot(200, ensure_final_stats_display)

        self._logger.info("处理流程完成")
    
    def on_thread_finished(self):
        """线程结束处理"""
        # 线程清理已在processing_finished中处理，这里不需要重复
        self.processing_thread = None
    
    def reset_processing_state(self):
        """重置处理状态（仅在开始新处理时调用）"""
        # 使用statistics管理器重置数据
        self.statistics.reset_all_statistics()
        self.user_stopped = False

        # **修复**: 通过事件协调器通知UI更新，但只在开始新处理时重置显示
        # 这样可以避免处理完成后意外重置Live Dashboard显示
        if hasattr(self.main_window, 'event_coordinator'):
            self.main_window.event_coordinator.notify_statistics_change(action='reset')

        # 停止计时器
        if self.main_window.timer.isActive():
            self.main_window.timer.stop()
    
    def generate_partial_summary_on_stop(self):
        """生成停止时的部分摘要"""
        try:
            # 从StatisticsManager获取数据
            stats = self.statistics.get_processing_summary()
            partial_data = {
                **stats,
                'status': 'stopped_by_user'
            }
            
            self.main_window.report_manager.set_final_summary_report(partial_data)
            
        except Exception as e:
            self._logger.error(f"生成部分摘要时发生错误: {e}")
    
    def _generate_final_report(self):
        """生成最终报告"""
        try:
            # 从StatisticsManager获取数据
            stats = self.statistics.get_processing_summary()
            final_data = {
                **stats,
                'status': 'completed',
                'output_directory': self.main_window.current_output_dir
            }
            
            self.main_window.report_manager.set_final_summary_report(final_data)
            
        except Exception as e:
            self._logger.error(f"生成最终报告时发生错误: {e}")
    
    # 旧的_build_pipeline_config方法已移除，使用服务层的build_pipeline_config函数
    pass
