#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
对话框管理器 - 负责各种对话框的显示
"""

import markdown
from typing import TYPE_CHECKING
from PyQt6.QtWidgets import *
from PyQt6.QtCore import Qt, QTime
from PyQt6.QtGui import QFont
import os

if TYPE_CHECKING:
    from ..main_window import MainWindow

from pktmask.utils.path import resource_path
from pktmask.infrastructure.logging import get_logger

class DialogManager:
    """对话框管理器 - 负责各种对话框的显示"""
    
    def __init__(self, main_window: 'MainWindow'):
        self.main_window = main_window
        self.config = main_window.config
        self._logger = get_logger(__name__)
    
    def show_user_guide_dialog(self):
        """显示用户指南对话框"""
        try:
            with open(resource_path('summary.md'), 'r', encoding='utf-8') as f:
                content = f.read()
            
            dialog = QDialog(self.main_window)
            dialog.setWindowTitle("User Guide")
            dialog.setGeometry(200, 200, 700, 500)
            
            layout = QVBoxLayout(dialog)
            text_edit = QTextEdit()
            text_edit.setReadOnly(True)
            text_edit.setHtml(markdown.markdown(content))
            
            layout.addWidget(text_edit)
            dialog.exec()
            
            self._logger.info("显示用户指南对话框")

        except Exception as e:
            self._logger.error(f"加载用户指南失败: {e}")
            QMessageBox.critical(self.main_window, "Error", f"Could not load User Guide: {str(e)}")

    def show_about_dialog(self):
        """显示关于对话框"""
        try:
            about_text = """
            <h2>PktMask</h2>
            <p><b>Network Packet Processing Tool</b></p>
            <p>Version: 1.0.0</p>
            
            <p>PktMask is a powerful network packet processing tool designed for:</p>
            <ul>
                <li>🔄 <b>Remove Duplicates</b> - Eliminate duplicate packets</li>
                <li>🛡️ <b>IP Anonymization</b> - Advanced hierarchical IP masking</li>
                <li>✂️ <b>Smart Trimming</b> - Intelligent payload reduction</li>
            </ul>
            
            <p><b>Features:</b></p>
            <ul>
                <li>Preserves network topology and relationships</li>
                <li>Maintains TLS handshake integrity</li>
                <li>Optimized for security research and compliance</li>
                <li>Safe data sharing capabilities</li>
            </ul>
            
            <p><b>Use Cases:</b></p>
            <ul>
                <li>Security research and analysis</li>
                <li>Network troubleshooting</li>
                <li>Compliance reporting</li>
                <li>Data anonymization for sharing</li>
            </ul>
            
            <hr>
            <p><small>Built with Python and PyQt6</small></p>
            """
            
            dialog = QDialog(self.main_window)
            dialog.setWindowTitle("About PktMask")
            dialog.setFixedSize(450, 500)
            
            layout = QVBoxLayout(dialog)
            
            # 主文本
            text_widget = QTextEdit()
            text_widget.setReadOnly(True)
            text_widget.setHtml(about_text)
            
            # 设置字体
            font = QFont()
            font.setPointSize(11)
            text_widget.setFont(font)
            
            layout.addWidget(text_widget)
            
            # 按钮
            button_layout = QHBoxLayout()
            button_layout.addStretch()
            
            ok_button = QPushButton("OK")
            ok_button.clicked.connect(dialog.accept)
            ok_button.setMinimumSize(80, 30)
            button_layout.addWidget(ok_button)
            
            layout.addLayout(button_layout)
            
            dialog.exec()
            
            self._logger.info("显示关于对话框")
            
        except Exception as e:
            self._logger.error(f"显示关于对话框失败: {e}")
            QMessageBox.critical(self.main_window, "Error", f"Could not show About dialog: {str(e)}")

    def show_error_dialog(self, title: str, message: str):
        """显示错误对话框"""
        try:
            QMessageBox.critical(self.main_window, title, message)
            self._logger.error(f"显示错误对话框: {title} - {message}")
        except Exception as e:
            self._logger.error(f"显示错误对话框失败: {e}")

    def show_warning_dialog(self, title: str, message: str):
        """显示警告对话框"""
        try:
            QMessageBox.warning(self.main_window, title, message)
            self._logger.warning(f"显示警告对话框: {title} - {message}")
        except Exception as e:
            self._logger.error(f"显示警告对话框失败: {e}")

    def show_info_dialog(self, title: str, message: str):
        """显示信息对话框"""
        try:
            QMessageBox.information(self.main_window, title, message)
            self._logger.info(f"显示信息对话框: {title} - {message}")
        except Exception as e:
            self._logger.error(f"显示信息对话框失败: {e}")

    def show_question_dialog(self, title: str, message: str) -> bool:
        """显示确认对话框"""
        try:
            reply = QMessageBox.question(
                self.main_window, 
                title, 
                message,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            result = reply == QMessageBox.StandardButton.Yes
            self._logger.info(f"显示确认对话框: {title} - 用户选择: {'是' if result else '否'}")
            return result
            
        except Exception as e:
            self._logger.error(f"显示确认对话框失败: {e}")
            return False

    def show_progress_dialog(self, title: str, message: str, maximum: int = 0) -> QProgressDialog:
        """显示进度对话框"""
        try:
            progress = QProgressDialog(message, "Cancel", 0, maximum, self.main_window)
            progress.setWindowTitle(title)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(1000)  # 1秒后显示
            
            self._logger.info(f"创建进度对话框: {title}")
            return progress
            
        except Exception as e:
            self._logger.error(f"创建进度对话框失败: {e}")
            return None

    def show_file_save_dialog(self, title: str, default_name: str = "", file_filter: str = "All Files (*)") -> str:
        """显示文件保存对话框"""
        try:
            filepath, _ = QFileDialog.getSaveFileName(
                self.main_window,
                title,
                default_name,
                file_filter
            )
            
            if filepath:
                self._logger.info(f"用户选择保存文件: {filepath}")
            else:
                self._logger.debug("用户取消文件保存")
            
            return filepath
            
        except Exception as e:
            self._logger.error(f"显示文件保存对话框失败: {e}")
            return ""

    def show_file_open_dialog(self, title: str, file_filter: str = "All Files (*)") -> str:
        """显示文件打开对话框"""
        try:
            filepath, _ = QFileDialog.getOpenFileName(
                self.main_window,
                title,
                "",
                file_filter
            )
            
            if filepath:
                self._logger.info(f"用户选择打开文件: {filepath}")
            else:
                self._logger.debug("用户取消文件打开")
            
            return filepath
            
        except Exception as e:
            self._logger.error(f"显示文件打开对话框失败: {e}")
            return ""

    def show_directory_dialog(self, title: str, default_path: str = "") -> str:
        """显示目录选择对话框"""
        try:
            directory = QFileDialog.getExistingDirectory(
                self.main_window,
                title,
                default_path
            )
            
            if directory:
                self._logger.info(f"用户选择目录: {directory}")
            else:
                self._logger.debug("用户取消目录选择")
            
            return directory
            
        except Exception as e:
            self._logger.error(f"显示目录选择对话框失败: {e}")
            return ""

    def show_input_dialog(self, title: str, label: str, default_text: str = "") -> tuple[str, bool]:
        """显示输入对话框"""
        try:
            text, ok = QInputDialog.getText(
                self.main_window,
                title,
                label,
                text=default_text
            )
            
            if ok:
                self._logger.info(f"用户输入: {title} - {text}")
            else:
                self._logger.debug("用户取消输入")
            
            return text, ok
            
        except Exception as e:
            self._logger.error(f"显示输入对话框失败: {e}")
            return "", False

    def show_custom_dialog(self, title: str, content: str, width: int = 400, height: int = 300) -> QDialog:
        """显示自定义内容对话框"""
        try:
            dialog = QDialog(self.main_window)
            dialog.setWindowTitle(title)
            dialog.setFixedSize(width, height)
            
            layout = QVBoxLayout(dialog)
            
            # 内容区域
            text_widget = QTextEdit()
            text_widget.setReadOnly(True)
            text_widget.setPlainText(content)
            layout.addWidget(text_widget)
            
            # 按钮区域
            button_layout = QHBoxLayout()
            button_layout.addStretch()
            
            ok_button = QPushButton("OK")
            ok_button.clicked.connect(dialog.accept)
            button_layout.addWidget(ok_button)
            
            layout.addLayout(button_layout)
            
            self._logger.info(f"创建自定义对话框: {title}")
            return dialog
            
        except Exception as e:
            self._logger.error(f"创建自定义对话框失败: {e}")
            return None

    def show_processing_error(self, error_message: str):
        """显示处理错误对话框"""
        try:
            # 如果错误消息为空或只是"Unknown error"，使用更友好的消息
            if not error_message or error_message.strip() == "Unknown error":
                error_message = "An unexpected error occurred during processing. Please check the logs for more details."
            
            # 检查是否在自动化测试环境中
            is_automated_test = (
                os.environ.get('QT_QPA_PLATFORM') == 'offscreen' or  # 无头模式
                os.environ.get('PYTEST_CURRENT_TEST') is not None or  # pytest环境
                os.environ.get('CI') == 'true' or  # CI环境
                hasattr(self.main_window, '_test_mode')  # 测试模式标志
            )
            
            if is_automated_test:
                # 在自动化测试环境中，只记录错误而不显示阻塞性对话框
                self._logger.error(f"处理错误（自动化测试模式）: {error_message}")
                # 更新主窗口日志以便测试验证
                self.main_window.update_log(f"Error: {error_message}")
                # 可选：发送一个非阻塞的通知
                self._send_non_blocking_error_notification(error_message)
                return
            
            # 在正常GUI环境中显示模态对话框
            error_dialog = QMessageBox(self.main_window)
            error_dialog.setIcon(QMessageBox.Icon.Critical)
            error_dialog.setWindowTitle("Processing Error")
            error_dialog.setText("An error occurred during processing:")
            error_dialog.setInformativeText(error_message)
            
            # 添加详细信息按钮
            error_dialog.setDetailedText(
                f"Error details:\n"
                f"Timestamp: {QTime.currentTime().toString()}\n"
                f"Error: {error_message}\n\n"
                f"Troubleshooting tips:\n"
                f"1. Check if input files are valid pcap files\n"
                f"2. Ensure you have write permissions to the output directory\n"
                f"3. Check available disk space\n"
                f"4. Review the log panel for more detailed error information"
            )
            
            error_dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
            error_dialog.exec()
            
            self._logger.error(f"显示处理错误对话框: {error_message}")
            
        except Exception as e:
            self._logger.error(f"显示处理错误对话框失败: {e}")
            # 如果对话框显示失败，至少更新日志
            self.main_window.update_log(f"Error: {error_message}")
    
    def _send_non_blocking_error_notification(self, error_message: str):
        """发送非阻塞的错误通知（用于自动化测试）"""
        try:
            # 这里可以发送状态栏消息、日志更新或其他非阻塞通知
            if hasattr(self.main_window, 'statusBar'):
                self.main_window.statusBar().showMessage(f"Error: {error_message}", 5000)
            
            # 发出错误信号供测试监听
            if hasattr(self.main_window, 'error_occurred'):
                self.main_window.error_occurred.emit(error_message)
                
        except Exception as e:
            self._logger.debug(f"发送非阻塞通知失败: {e}")

    def show_processing_complete(self, summary: str):
        """显示处理完成对话框"""
        try:
            success_dialog = QMessageBox(self.main_window)
            success_dialog.setIcon(QMessageBox.Icon.Information)
            success_dialog.setWindowTitle("Processing Complete")
            success_dialog.setText("Processing completed successfully!")
            
            if summary:
                success_dialog.setDetailedText(summary)
            
            success_dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
            success_dialog.exec()
            
            self._logger.info("显示处理完成对话框")
            
        except Exception as e:
            self._logger.error(f"显示处理完成对话框失败: {e}") 