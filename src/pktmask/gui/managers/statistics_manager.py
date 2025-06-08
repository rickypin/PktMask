#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
统计数据管理器 - 集中管理所有处理统计数据
"""

from typing import Dict, Any, Optional
from PyQt6.QtCore import QTime

from ...infrastructure.logging import get_logger
from ...utils.time import format_milliseconds_to_time

class StatisticsManager:
    """统计数据管理器 - 集中管理所有处理统计数据"""
    
    def __init__(self):
        self._logger = get_logger(__name__)
        
        # 处理统计
        self.files_processed = 0
        self.packets_processed = 0
        self.total_files_to_process = 0
        
        # 时间统计
        self.start_time: Optional[QTime] = None
        self.processing_time = 0
        
        # 文件处理结果
        self.file_processing_results = {}  # original_file -> {steps: {step_name: result_data}}
        self.step_results = {}  # 步骤结果缓存
        
        # IP映射相关
        self.global_ip_mappings = {}  # 全局IP映射汇总
        self.all_ip_reports = {}  # subdir -> report_data
        
        # 处理状态
        self.processed_files_count = 0
        self.current_processing_file = None  # 当前正在处理的原始文件
        
        # 计数追踪（用于去重计算）
        self.subdirs_files_counted = set()
        self.subdirs_packets_counted = set()
        self.printed_summary_headers = set()
        
        self._logger.debug("StatisticsManager initialized")
    
    def reset_all_statistics(self):
        """重置所有统计数据"""
        self.files_processed = 0
        self.packets_processed = 0
        self.total_files_to_process = 0
        
        self.start_time = None
        self.processing_time = 0
        
        self.file_processing_results.clear()
        self.step_results.clear()
        
        self.global_ip_mappings.clear()
        self.all_ip_reports.clear()
        
        self.processed_files_count = 0
        self.current_processing_file = None
        
        self.subdirs_files_counted.clear()
        self.subdirs_packets_counted.clear()
        self.printed_summary_headers.clear()
        
        self._logger.debug("All statistics reset")
    
    def start_timing(self):
        """开始计时"""
        self.start_time = QTime.currentTime()
        self._logger.debug("Started timing")
    
    def stop_timing(self):
        """停止计时并计算总耗时"""
        if self.start_time:
            elapsed_msecs = self.start_time.msecsTo(QTime.currentTime())
            self.processing_time = elapsed_msecs
            self._logger.debug(f"Stopped timing, total elapsed: {self.get_elapsed_time_string()}")
    
    def get_elapsed_time_string(self) -> str:
        """获取耗时字符串"""
        if not self.start_time:
            return "00:00.00"
        
        elapsed_msecs = self.start_time.msecsTo(QTime.currentTime())
        return format_milliseconds_to_time(elapsed_msecs)
    
    def update_file_count(self, count: int):
        """更新文件处理计数"""
        self.files_processed = count
        self._logger.debug(f"Updated file count: {count}")
    
    def increment_file_count(self):
        """递增文件计数"""
        self.files_processed += 1
        self._logger.debug(f"Incremented file count to: {self.files_processed}")
    
    def update_packet_count(self, count: int):
        """更新包处理计数"""
        self.packets_processed = count
        self._logger.debug(f"Updated packet count: {count}")
    
    def add_packet_count(self, additional: int):
        """增加包处理计数"""
        self.packets_processed += additional
        self._logger.debug(f"Added {additional} packets, total: {self.packets_processed}")
    
    def set_total_files(self, total: int):
        """设置总文件数"""
        self.total_files_to_process = total
        self._logger.debug(f"Set total files to process: {total}")
    
    def get_dashboard_stats(self) -> Dict[str, Any]:
        """获取仪表盘统计数据"""
        return {
            'files_processed': self.files_processed,
            'total_files': self.total_files_to_process,
            'packets_processed': self.packets_processed,
            'elapsed_time': self.get_elapsed_time_string(),
            'processing_time_ms': self.processing_time
        }
    
    def get_processing_summary(self) -> Dict[str, Any]:
        """获取处理摘要统计"""
        return {
            'files_processed': self.files_processed,
            'total_files': self.total_files_to_process,
            'packets_processed': self.packets_processed,
            'processing_time': self.get_elapsed_time_string(),
            'step_results': self.step_results.copy(),
            'file_processing_results': self.file_processing_results.copy(),
            'global_ip_mappings': self.global_ip_mappings.copy(),
            'all_ip_reports': self.all_ip_reports.copy()
        }
    
    def collect_step_result(self, step_name: str, filename: str, result_data: Dict[str, Any]):
        """收集步骤处理结果"""
        # 使用文件名作为键而不是完整路径
        file_key = filename.split('/')[-1] if filename else 'unknown'
        
        if file_key not in self.step_results:
            self.step_results[file_key] = {}
        
        self.step_results[file_key][step_name] = result_data
        self._logger.debug(f"Collected step result: {step_name} for {file_key}")
    
    def add_file_processing_result(self, filename: str, step_name: str, result_data: Dict[str, Any]):
        """添加文件处理结果"""
        if filename not in self.file_processing_results:
            self.file_processing_results[filename] = {'steps': {}}
        
        self.file_processing_results[filename]['steps'][step_name] = {
            'data': result_data,
            'timestamp': QTime.currentTime().toString()
        }
        
        self._logger.debug(f"Added processing result: {step_name} for {filename}")
    
    def update_global_ip_mappings(self, new_mappings: Dict[str, str]):
        """更新全局IP映射"""
        self.global_ip_mappings.update(new_mappings)
        self._logger.debug(f"Updated global IP mappings, total: {len(self.global_ip_mappings)}")
    
    def add_ip_report(self, subdir: str, report_data: Dict[str, Any]):
        """添加IP报告数据"""
        self.all_ip_reports[subdir] = report_data
        self._logger.debug(f"Added IP report for subdir: {subdir}")
    
    def set_current_processing_file(self, filename: Optional[str]):
        """设置当前正在处理的文件"""
        self.current_processing_file = filename
        if filename:
            self._logger.debug(f"Set current processing file: {filename}")
    
    def get_file_completion_rate(self) -> float:
        """获取文件完成率"""
        if self.total_files_to_process == 0:
            return 0.0
        return (self.files_processed / self.total_files_to_process) * 100
    
    def get_processing_speed(self) -> float:
        """获取处理速度（包/秒）"""
        if not self.start_time or self.packets_processed == 0:
            return 0.0
        
        elapsed_seconds = self.start_time.msecsTo(QTime.currentTime()) / 1000.0
        if elapsed_seconds <= 0:
            return 0.0
        
        return self.packets_processed / elapsed_seconds
    
    def is_processing_complete(self) -> bool:
        """检查处理是否完成"""
        return (self.total_files_to_process > 0 and 
                self.files_processed >= self.total_files_to_process)
    
    def get_debug_info(self) -> Dict[str, Any]:
        """获取调试信息"""
        return {
            'files_processed': self.files_processed,
            'total_files': self.total_files_to_process,
            'packets_processed': self.packets_processed,
            'step_results_count': len(self.step_results),
            'file_results_count': len(self.file_processing_results),
            'global_mappings_count': len(self.global_ip_mappings),
            'ip_reports_count': len(self.all_ip_reports),
            'current_file': self.current_processing_file,
            'completion_rate': f"{self.get_file_completion_rate():.1f}%",
            'processing_speed': f"{self.get_processing_speed():.1f} packets/sec"
        } 