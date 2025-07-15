#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
File manager - handles directory selection and file operations
"""

import os
from typing import TYPE_CHECKING, Optional
from PyQt6.QtWidgets import QFileDialog, QMessageBox

if TYPE_CHECKING:
    from ..main_window import MainWindow

from pktmask.utils.time import current_timestamp
from pktmask.utils.file_ops import open_directory_in_system
from pktmask.infrastructure.logging import get_logger

class FileManager:
    """File manager - handles directory selection and file operations"""
    
    def __init__(self, main_window: 'MainWindow'):
        self.main_window = main_window
        self.config = main_window.config
        self._logger = get_logger(__name__)
    
    def choose_folder(self):
        """Select input directory"""
        dir_path = QFileDialog.getExistingDirectory(
            self.main_window,
            "Select Input Folder",
            self.main_window.last_opened_dir
        )
        if dir_path:
            self.main_window.base_dir = dir_path
            self.main_window.last_opened_dir = dir_path  # Record currently selected directory
            self.main_window.dir_path_label.setText(os.path.basename(dir_path))

            # Auto-generate default output path
            self.generate_default_output_path()
            self.main_window.ui_manager._update_start_button_state()  # Intelligently update button state

            self._logger.info(f"Selected input directory: {dir_path}")

    def handle_output_click(self):
        """处理输出路径按钮点击 - 在处理完成后打开目录，否则选择自定义输出目录"""
        if self.main_window.current_output_dir and os.path.exists(self.main_window.current_output_dir):
            # 如果已有输出目录且存在，则打开它
            self.open_output_directory()
        else:
            # 否则让用户选择自定义输出目录
            self.choose_output_folder()

    def choose_output_folder(self):
        """选择自定义输出目录"""
        dir_path = QFileDialog.getExistingDirectory(
            self.main_window,
            "Select Output Folder",
            self.main_window.last_opened_dir
        )
        if dir_path:
            self.main_window.output_dir = dir_path
            self.main_window.output_path_label.setText(os.path.basename(dir_path))
            self._logger.info(f"选择自定义输出目录: {dir_path}")

    def generate_default_output_path(self):
        """生成默认输出路径预览"""
        if not self.main_window.base_dir:
            return
        
        # 重置为默认模式
        self.main_window.output_dir = None
        self.main_window.output_path_label.setText("Auto-create or click for custom")
        self._logger.debug("重置为默认输出路径模式")

    def generate_actual_output_path(self) -> str:
        """生成实际的输出目录路径"""
        timestamp = current_timestamp()
        
        # 获取输入目录名称
        if self.main_window.base_dir:
            input_dir_name = os.path.basename(self.main_window.base_dir)
            # 生成新的命名格式：输入目录名-Masked-时间戳
            output_name = f"{input_dir_name}-Masked-{timestamp}"
        else:
            # 如果没有输入目录，使用默认格式
            output_name = f"PktMask-{timestamp}"
        
        if self.main_window.output_dir:
            # 自定义输出目录
            actual_path = os.path.join(self.main_window.output_dir, output_name)
        else:
            # 默认输出目录
            if self.config.ui.default_output_dir:
                actual_path = os.path.join(self.config.ui.default_output_dir, output_name)
            else:
                # 使用输入目录的子目录
                actual_path = os.path.join(self.main_window.base_dir, output_name)
        
        self._logger.info(f"生成实际输出路径: {actual_path}")
        return actual_path

    def open_output_directory(self):
        """打开输出目录"""
        if not self.main_window.current_output_dir or not os.path.exists(self.main_window.current_output_dir):
            QMessageBox.warning(self.main_window, "Warning", "Output directory not found.")
            return
        
        try:
            success = open_directory_in_system(self.main_window.current_output_dir)
            if success:
                self.main_window.update_log(f"Opened output directory: {os.path.basename(self.main_window.current_output_dir)}")
                self._logger.info(f"打开输出目录: {self.main_window.current_output_dir}")
            else:
                self._logger.error("无法打开输出目录")
                QMessageBox.critical(self.main_window, "Error", "Could not open output directory.")
        except Exception as e:
            self._logger.error(f"打开输出目录时发生错误: {e}")
            QMessageBox.critical(self.main_window, "Error", f"Error opening directory: {str(e)}")

    def save_summary_report_to_output_dir(self) -> bool:
        """保存摘要报告到输出目录"""
        if not self.main_window.current_output_dir:
            self._logger.warning("输出目录路径为空，无法保存摘要报告")
            return False
        
        try:
            # 确保输出目录存在
            if not os.path.exists(self.main_window.current_output_dir):
                self._logger.info(f"创建输出目录: {self.main_window.current_output_dir}")
                os.makedirs(self.main_window.current_output_dir, exist_ok=True)
            
            filename = self.generate_summary_report_filename()
            filepath = os.path.join(self.main_window.current_output_dir, filename)
            
            # 获取摘要文本
            summary_text = self.main_window.summary_text.toPlainText()
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(summary_text)
            
            self._logger.info(f"摘要报告保存到: {filepath}")
            self.main_window.update_log(f"Summary report saved: {filename}")
            return True
            
        except Exception as e:
            self._logger.error(f"保存摘要报告失败: {e}")
            self.main_window.update_log(f"Error saving summary report: {str(e)}")
            return False

    def generate_summary_report_filename(self) -> str:
        """生成摘要报告文件名"""
        timestamp = current_timestamp()
        
        # 生成处理选项标识
        enabled_steps = []
        if hasattr(self.main_window, 'anonymize_ips_cb') and self.main_window.anonymize_ips_cb.isChecked():
            enabled_steps.append("MaskIP")
        if hasattr(self.main_window, 'remove_dupes_cb') and self.main_window.remove_dupes_cb.isChecked():
            enabled_steps.append("Dedup")
        if hasattr(self.main_window, 'mask_payloads_cb') and self.main_window.mask_payloads_cb.isChecked():
            enabled_steps.append("Trim")
        
        steps_suffix = "_".join(enabled_steps) if enabled_steps else "NoSteps"
        filename = f"summary_report_{steps_suffix}_{timestamp}.txt"
        
        return filename

    def find_existing_summary_reports(self) -> list[str]:
        """查找现有的摘要报告文件"""
        if not self.main_window.current_output_dir or not os.path.exists(self.main_window.current_output_dir):
            return []
        
        try:
            reports = []
            for file in os.listdir(self.main_window.current_output_dir):
                if file.startswith('summary_report_') and file.endswith('.txt'):
                    filepath = os.path.join(self.main_window.current_output_dir, file)
                    reports.append(filepath)
            
            # 按修改时间排序，最新的在前
            reports.sort(key=lambda x: os.path.getmtime(x), reverse=True)
            return reports
            
        except Exception as e:
            self._logger.error(f"查找摘要报告文件时发生错误: {e}")
            return []

    def load_latest_summary_report(self) -> Optional[str]:
        """加载最新的摘要报告"""
        reports = self.find_existing_summary_reports()
        if not reports:
            return None
        
        try:
            latest_report = reports[0]  # 最新的报告
            with open(latest_report, 'r', encoding='utf-8') as f:
                content = f.read()
            
            self._logger.info(f"加载最新摘要报告: {latest_report}")
            return content
            
        except Exception as e:
            self._logger.error(f"加载摘要报告失败: {e}")
            return None

    def validate_input_directory(self, directory: str) -> bool:
        """验证输入目录是否有效"""
        if not directory:
            return False
        
        if not os.path.exists(directory):
            self._logger.warning(f"输入目录不存在: {directory}")
            return False
        
        if not os.path.isdir(directory):
            self._logger.warning(f"输入路径不是目录: {directory}")
            return False
        
        # 检查是否有pcap文件
        pcap_extensions = ['.pcap', '.pcapng', '.cap']
        for file in os.listdir(directory):
            if any(file.lower().endswith(ext) for ext in pcap_extensions):
                return True
        
        self._logger.warning(f"输入目录中未找到pcap文件: {directory}")
        return False

    def get_directory_info(self, directory: str) -> dict:
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
            self._logger.error(f"获取目录信息时发生错误: {e}")
        
        return info 