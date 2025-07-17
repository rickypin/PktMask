#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
数据服务 - 统一的数据和文件管理

合并原有的 FileManager 和 ReportManager 功能，
提供简化的数据处理和文件管理接口。
"""

import os
from typing import Optional, Dict, Any, List
from datetime import datetime
from PyQt6.QtWidgets import QFileDialog

from pktmask.infrastructure.logging import get_logger
from pktmask.config import get_app_config
from pktmask.utils.time import current_timestamp
from pktmask.utils.file_ops import open_directory_in_system


class ProcessingStats:
    """简化的处理统计信息"""
    
    def __init__(self):
        self.files_processed = 0
        self.packets_processed = 0
        self.packets_modified = 0
        self.processing_time = 0.0
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.errors: List[str] = []
        self.file_results: Dict[str, Dict] = {}
        
    def start_processing(self):
        """开始处理计时"""
        self.start_time = datetime.now()
        
    def end_processing(self):
        """结束处理计时"""
        self.end_time = datetime.now()
        if self.start_time:
            self.processing_time = (self.end_time - self.start_time).total_seconds()
    
    def add_file_result(self, filename: str, result: Dict[str, Any]):
        """添加文件处理结果"""
        self.file_results[filename] = result
        self.files_processed += 1
        
        # 累计统计
        if 'packets_processed' in result:
            self.packets_processed += result['packets_processed']
        if 'packets_modified' in result:
            self.packets_modified += result['packets_modified']
    
    def add_error(self, error_message: str):
        """添加错误信息"""
        self.errors.append(error_message)
    
    def get_completion_rate(self) -> float:
        """获取完成率"""
        if self.packets_processed == 0:
            return 0.0
        return (self.packets_modified / self.packets_processed) * 100
    
    def get_processing_speed(self) -> float:
        """获取处理速度（包/秒）"""
        if self.processing_time == 0:
            return 0.0
        return self.packets_processed / self.processing_time


class DataService:
    """数据服务 - 统一的数据和文件管理
    
    职责：
    1. 文件操作（目录选择、路径生成）
    2. 数据处理（统计收集、结果管理）
    3. 报告生成（日志、摘要、详细报告）
    4. 配置管理（用户偏好、路径记录）
    """
    
    def __init__(self, main_window):
        self.main_window = main_window
        self.config = get_app_config()
        self._logger = get_logger(__name__)
        
        # 路径管理
        self.input_dir: Optional[str] = None
        self.output_dir: Optional[str] = None
        self.current_output_dir: Optional[str] = None
        self.last_opened_dir = self.config.ui.last_input_dir or os.path.join(os.path.expanduser("~"), "Desktop")
        
        # 统计管理
        self.stats = ProcessingStats()
        
        # 报告管理
        self.log_messages: List[str] = []
        
        self._logger.info("Data service initialization completed")
    
    def select_input_directory(self) -> bool:
        """Select input path (directory or file) with enhanced dual-mode selection"""
        try:
            from PyQt6.QtWidgets import QMessageBox

            # Show selection mode dialog
            reply = QMessageBox.question(
                self.main_window,
                "Select Input Mode",
                "Choose input selection mode:\n\n"
                "• Yes: Select individual pcap/pcapng file\n"
                "• No: Select directory for batch processing\n"
                "• Cancel: Cancel selection",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.No  # Default to directory selection
            )

            if reply == QMessageBox.StandardButton.Cancel:
                return False

            if reply == QMessageBox.StandardButton.Yes:
                # File selection mode
                return self._select_individual_file()
            else:
                # Directory selection mode
                return self._select_directory()

        except Exception as e:
            self._logger.error(f"Error in input selection: {e}")
            return False

    def _select_individual_file(self) -> bool:
        """Select individual pcap/pcapng file"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self.main_window,
                "Select PCAP/PCAPNG File",
                self.last_opened_dir,
                "PCAP Files (*.pcap *.pcapng);;All Files (*)"
            )

            if file_path:
                self.input_dir = file_path  # Store file path directly
                self.last_opened_dir = os.path.dirname(file_path)

                # Update UI display with file indicator
                if hasattr(self.main_window, 'dir_path_label'):
                    file_name = os.path.basename(file_path)
                    self.main_window.dir_path_label.setText(f"📄 {file_name}")

                # Auto-generate output path
                self._generate_default_output_path()

                # Update main window properties (compatibility)
                self.main_window.base_dir = file_path

                # Update button state
                if hasattr(self.main_window, 'ui_builder'):
                    self.main_window.ui_builder.update_start_button_state()

                self._logger.info(f"Selected input file: {file_path}")
                return True

            return False

        except Exception as e:
            self._logger.error(f"Error selecting file: {e}")
            return False

    def _select_directory(self) -> bool:
        """Select input directory for batch processing"""
        try:
            dir_path = QFileDialog.getExistingDirectory(
                self.main_window,
                "Select Input Directory",
                self.last_opened_dir
            )

            if dir_path:
                self.input_dir = dir_path
                self.last_opened_dir = dir_path

                # Update UI display with directory indicator
                if hasattr(self.main_window, 'dir_path_label'):
                    dir_name = os.path.basename(dir_path)
                    self.main_window.dir_path_label.setText(f"📁 {dir_name}")

                # Auto-generate output path
                self._generate_default_output_path()

                # Update main window properties (compatibility)
                self.main_window.base_dir = dir_path

                # Update button state
                if hasattr(self.main_window, 'ui_builder'):
                    self.main_window.ui_builder.update_start_button_state()

                self._logger.info(f"Selected input directory: {dir_path}")
                return True

            return False

        except Exception as e:
            self._logger.error(f"Error selecting directory: {e}")
            return False

        except Exception as e:
            self._logger.error(f"Failed to select input directory: {e}")
            return False
    
    def select_output_directory(self) -> bool:
        """Select custom output directory"""
        try:
            dir_path = QFileDialog.getExistingDirectory(
                self.main_window,
                "Select Output Folder",
                self.output_dir or self.last_opened_dir
            )

            if dir_path:
                self.output_dir = dir_path

                # Update UI display
                if hasattr(self.main_window, 'output_path_label'):
                    self.main_window.output_path_label.setText(f"Custom: {os.path.basename(dir_path)}")

                self._logger.info(f"Selected output directory: {dir_path}")
                return True

            return False

        except Exception as e:
            self._logger.error(f"Failed to select output directory: {e}")
            return False
    
    def _generate_default_output_path(self):
        """Generate default output path display"""
        if self.input_dir:
            input_name = os.path.basename(self.input_dir)
            display_text = f"Auto: {input_name}-Masked-[timestamp]"
            
            if hasattr(self.main_window, 'output_path_label'):
                self.main_window.output_path_label.setText(display_text)
    
    def generate_actual_output_path(self) -> str:
        """Generate actual output directory path"""
        timestamp = current_timestamp()

        # Generate output directory name
        if self.input_dir:
            input_dir_name = os.path.basename(self.input_dir)
            output_name = f"{input_dir_name}-Masked-{timestamp}"
        else:
            output_name = f"PktMask-{timestamp}"

        # Determine output path
        if self.output_dir:
            # Custom output directory
            actual_path = os.path.join(self.output_dir, output_name)
        else:
            # Default output directory
            if self.config.ui.default_output_dir:
                actual_path = os.path.join(self.config.ui.default_output_dir, output_name)
            else:
                # Use subdirectory of input directory
                actual_path = os.path.join(self.input_dir, output_name)
        
        self.current_output_dir = actual_path
        self._logger.info(f"Generated actual output path: {actual_path}")
        return actual_path
    
    def get_directory_info(self, directory: str) -> Dict[str, Any]:
        """获取目录信息"""
        info = {
            'exists': False,
            'is_directory': False,
            'pcap_files': [],
            'total_files': 0,
            'total_size': 0
        }
        
        if not directory or not os.path.exists(directory):
            return info
        
        info['exists'] = True
        info['is_directory'] = os.path.isdir(directory)
        
        if not info['is_directory']:
            return info
        
        try:
            pcap_extensions = ['.pcap', '.pcapng', '.cap']
            
            for file in os.listdir(directory):
                filepath = os.path.join(directory, file)
                if os.path.isfile(filepath):
                    info['total_files'] += 1
                    info['total_size'] += os.path.getsize(filepath)
                    
                    if any(file.lower().endswith(ext) for ext in pcap_extensions):
                        info['pcap_files'].append(file)
        
        except Exception as e:
            self._logger.error(f"Error occurred while getting directory information: {e}")
        
        return info
    
    def add_log_message(self, message: str):
        """添加日志消息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        self.log_messages.append(formatted_message)
        
        # 更新UI显示
        if hasattr(self.main_window, 'log_text'):
            self.main_window.log_text.append(formatted_message)
            
            # 自动滚动到底部
            cursor = self.main_window.log_text.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            self.main_window.log_text.setTextCursor(cursor)
    
    def generate_processing_report(self) -> str:
        """生成处理报告"""
        report_lines = []
        
        # 报告标题
        report_lines.append("=" * 60)
        report_lines.append("PROCESSING SUMMARY REPORT")
        report_lines.append("=" * 60)
        
        # 基本信息
        if self.input_dir:
            report_lines.append(f"Input Directory: {self.input_dir}")
        if self.current_output_dir:
            report_lines.append(f"Output Directory: {self.current_output_dir}")
        
        report_lines.append("")
        
        # 统计信息
        report_lines.append("PROCESSING STATISTICS:")
        report_lines.append(f"  Files Processed: {self.stats.files_processed}")
        report_lines.append(f"  Packets Processed: {self.stats.packets_processed:,}")
        report_lines.append(f"  Packets Modified: {self.stats.packets_modified:,}")
        report_lines.append(f"  Processing Time: {self.stats.processing_time:.2f} seconds")
        
        if self.stats.processing_time > 0:
            speed = self.stats.packets_processed / self.stats.processing_time
            report_lines.append(f"  Processing Speed: {speed:.1f} packets/second")
        
        completion_rate = self.stats.get_completion_rate()
        report_lines.append(f"  Completion Rate: {completion_rate:.1f}%")
        
        # 错误信息
        if self.stats.errors:
            report_lines.append("")
            report_lines.append("ERRORS:")
            for error in self.stats.errors:
                report_lines.append(f"  - {error}")
        
        # 文件详情
        if self.stats.file_results:
            report_lines.append("")
            report_lines.append("FILE PROCESSING DETAILS:")
            for filename, result in self.stats.file_results.items():
                report_lines.append(f"  {filename}:")
                if 'packets_processed' in result:
                    report_lines.append(f"    Packets: {result['packets_processed']}")
                if 'output_file' in result:
                    report_lines.append(f"    Output: {result['output_file']}")
        
        report_lines.append("=" * 60)
        
        return "\n".join(report_lines)
    
    def save_report_to_file(self, report_content: str, filename: str = "processing_report.txt"):
        """保存报告到文件"""
        try:
            if self.current_output_dir:
                report_path = os.path.join(self.current_output_dir, filename)
                with open(report_path, 'w', encoding='utf-8') as f:
                    f.write(report_content)
                
                self._logger.info(f"Report saved to: {report_path}")
                return report_path
            
        except Exception as e:
            self._logger.error(f"Failed to save report: {e}")
            return None
    
    def open_output_directory(self):
        """Open output directory"""
        if self.current_output_dir and os.path.exists(self.current_output_dir):
            open_directory_in_system(self.current_output_dir)
        else:
            self._logger.warning("Output directory does not exist or is not set")
    
    def reset_stats(self):
        """重置统计信息"""
        self.stats = ProcessingStats()
        self.log_messages.clear()
        
        # 清空UI显示
        if hasattr(self.main_window, 'log_text'):
            self.main_window.log_text.clear()
        if hasattr(self.main_window, 'summary_text'):
            self.main_window.summary_text.clear()
    
    def cleanup(self):
        """清理资源"""
        try:
            # 保存用户偏好
            if self.last_opened_dir:
                # 这里可以保存到配置文件
                pass
            
            self._logger.info("数据服务资源清理完成")
            
        except Exception as e:
            self._logger.error(f"Failed to cleanup resources: {e}")
