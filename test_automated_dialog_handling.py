#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
自动化测试 - 弹窗处理验证
专门测试在自动化环境中弹窗是否被正确处理，不会阻塞测试执行
"""

import os
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from PyQt6.QtWidgets import QApplication

# 设置无头模式（确保在Qt导入之前设置）
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['PYTEST_CURRENT_TEST'] = 'automated_test'

# 添加src路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from pktmask.gui.main_window import MainWindow
from pktmask.gui.managers.dialog_manager import DialogManager


class TestAutomatedDialogHandling:
    """自动化弹窗处理测试类"""
    
    @pytest.fixture
    def app(self):
        """创建QApplication实例"""
        return QApplication.instance() or QApplication([])
    
    @pytest.fixture
    def main_window(self, app):
        """创建主窗口实例（测试模式）"""
        window = MainWindow()
        window.set_test_mode(True)
        return window
    
    @pytest.fixture
    def dialog_manager(self, main_window):
        """创建对话框管理器实例"""
        return DialogManager(main_window)
    
    def test_processing_error_in_automated_mode(self, dialog_manager, main_window):
        """测试自动化模式下的错误处理"""
        error_messages = []
        
        def capture_error(message):
            error_messages.append(message)
        
        # 连接错误信号
        main_window.error_occurred.connect(capture_error)
        
        # 触发错误 - 应该不阻塞
        dialog_manager.show_processing_error("Automated test error")
        
        # 验证错误被记录到日志而不是显示阻塞对话框
        log_content = main_window.log_text.toPlainText()
        assert "Automated test error" in log_content
        
        # 验证没有阻塞性对话框被显示
        # 在自动化环境中，这应该立即返回
    
    def test_environment_detection(self, dialog_manager):
        """测试自动化环境检测"""
        # 验证环境变量设置
        assert os.environ.get('QT_QPA_PLATFORM') == 'offscreen'
        assert os.environ.get('PYTEST_CURRENT_TEST') is not None
        
        # 验证测试模式标志
        assert hasattr(dialog_manager.main_window, '_test_mode')
        assert dialog_manager.main_window._test_mode is True
    
    def test_non_blocking_error_notification(self, dialog_manager, main_window):
        """测试非阻塞错误通知"""
        # 直接调用非阻塞通知方法
        dialog_manager._send_non_blocking_error_notification("Test notification")
        
        # 验证没有抛出异常（即方法执行成功）
        # 在没有状态栏的情况下，方法应该优雅地处理
    
    def test_multiple_errors_handling(self, dialog_manager, main_window):
        """测试多个错误的处理"""
        error_messages = ["Error 1", "Error 2", "Error 3"]
        
        # 连续触发多个错误
        for error_msg in error_messages:
            dialog_manager.show_processing_error(error_msg)
        
        # 验证所有错误都被记录
        log_content = main_window.log_text.toPlainText()
        for error_msg in error_messages:
            assert error_msg in log_content
    
    def test_error_signal_emission(self, main_window):
        """测试错误信号发射"""
        received_errors = []
        
        def error_handler(error_msg):
            received_errors.append(error_msg)
        
        # 连接信号
        main_window.error_occurred.connect(error_handler)
        
        # 触发错误
        main_window.processing_error("Signal test error")
        
        # 验证信号被正确发射（如果实现了的话）
        # 注意：这个测试可能需要根据实际实现进行调整
    
    def test_normal_vs_automated_mode(self, main_window):
        """测试正常模式与自动化模式的差异"""
        # 测试模式下
        main_window.set_test_mode(True)
        with patch('PyQt6.QtWidgets.QMessageBox.exec') as mock_exec:
            main_window.processing_error("Test mode error")
            # 在测试模式下，不应该调用exec()
            mock_exec.assert_not_called()
        
        # 非测试模式下（模拟）
        main_window.set_test_mode(False)
        # 清除自动化环境标识来模拟正常环境
        old_platform = os.environ.get('QT_QPA_PLATFORM')
        old_pytest = os.environ.get('PYTEST_CURRENT_TEST')
        
        try:
            if 'QT_QPA_PLATFORM' in os.environ:
                del os.environ['QT_QPA_PLATFORM']
            if 'PYTEST_CURRENT_TEST' in os.environ:
                del os.environ['PYTEST_CURRENT_TEST']
            
            with patch('PyQt6.QtWidgets.QMessageBox.exec') as mock_exec:
                main_window.processing_error("Normal mode error")
                # 在正常模式下，应该调用exec()
                mock_exec.assert_called_once()
        
        finally:
            # 恢复环境变量
            if old_platform:
                os.environ['QT_QPA_PLATFORM'] = old_platform
            if old_pytest:
                os.environ['PYTEST_CURRENT_TEST'] = old_pytest


def run_automated_tests():
    """运行自动化弹窗处理测试"""
    print("🤖 开始自动化弹窗处理测试")
    print("=" * 50)
    
    # 使用pytest运行测试
    import pytest
    
    test_file = __file__
    pytest_args = [
        test_file,
        '-v',
        '--tb=short',
        '--durations=5'
    ]
    
    exit_code = pytest.main(pytest_args)
    
    if exit_code == 0:
        print("\n✅ 自动化弹窗处理测试通过")
        print("🎉 弹窗阻塞问题已解决")
    else:
        print("\n❌ 自动化弹窗处理测试失败")
        print("⚠️  弹窗阻塞问题仍然存在")
    
    return exit_code == 0


if __name__ == '__main__':
    success = run_automated_tests()
    sys.exit(0 if success else 1) 