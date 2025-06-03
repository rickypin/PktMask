import pytest
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt
from pktmask.gui.main_window import MainWindow
from unittest.mock import patch, MagicMock

@pytest.fixture
def app(qtbot):
    """创建 QApplication 实例"""
    return QApplication.instance() or QApplication([])

@pytest.fixture
def main_window(app, qtbot):
    """创建主窗口实例"""
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    return window

def test_main_window_title(main_window):
    """测试主窗口标题"""
    assert main_window.windowTitle() == "PktMask - IP Address Replacement Tool"

def test_select_dir_btn_visible_and_enabled(main_window):
    """测试选择目录按钮可见且可用"""
    assert hasattr(main_window, "select_dir_btn")
    assert main_window.select_dir_btn.isVisible()
    assert main_window.select_dir_btn.isEnabled()

def test_process_btn_visible(main_window):
    """测试处理按钮可见"""
    assert hasattr(main_window, "process_btn")
    assert main_window.process_btn.isVisible()

def test_stop_btn_visible(main_window):
    """测试停止按钮可见"""
    assert hasattr(main_window, "stop_btn")
    assert main_window.stop_btn.isVisible()

def test_log_text_visible(main_window):
    """测试日志区可见"""
    assert hasattr(main_window, "log_text")
    assert main_window.log_text.isVisible()

def test_select_dir_btn_click(main_window, qtbot, tmp_path, monkeypatch):
    # 模拟文件选择对话框返回路径
    monkeypatch.setattr("PyQt6.QtWidgets.QFileDialog.getExistingDirectory", lambda *a, **k: str(tmp_path))
    qtbot.mouseClick(main_window.select_dir_btn, Qt.MouseButton.LeftButton)
    assert main_window.process_btn.isEnabled()
    assert f"Selected directory: {tmp_path}" in main_window.log_text.toPlainText()

def test_process_btn_no_dir(main_window, qtbot, monkeypatch):
    # 未选择目录时点击处理按钮，弹出警告
    main_window.process_btn.setEnabled(True)  # 确保按钮可用
    with patch.object(QMessageBox, "warning") as mock_warn:
        qtbot.mouseClick(main_window.process_btn, Qt.MouseButton.LeftButton)
        mock_warn.assert_called_once()

def test_process_btn_and_stop_btn_state(main_window, qtbot, tmp_path, monkeypatch):
    # 选择目录后，处理按钮可用，点击后状态切换
    monkeypatch.setattr("PyQt6.QtWidgets.QFileDialog.getExistingDirectory", lambda *a, **k: str(tmp_path))
    qtbot.mouseClick(main_window.select_dir_btn, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(main_window.process_btn, Qt.MouseButton.LeftButton)
    assert not main_window.process_btn.isEnabled()
    assert main_window.stop_btn.isEnabled()
    assert not main_window.select_dir_btn.isEnabled()
    # 停止后状态恢复
    if main_window.process_thread:
        main_window.process_thread.is_running = False
    qtbot.mouseClick(main_window.stop_btn, Qt.MouseButton.LeftButton)
    assert main_window.process_btn.isEnabled()
    assert not main_window.stop_btn.isEnabled()
    assert main_window.select_dir_btn.isEnabled()

def test_log_text_update(main_window):
    msg = "Test log message"
    main_window.update_progress(msg)
    assert msg in main_window.log_text.toPlainText()

def test_display_ip_mapping_file_not_found(main_window, tmp_path):
    main_window.base_dir = str(tmp_path)
    # 目录下无 replacement.log
    main_window.display_ip_mapping("subdir", {})
    assert "File not found" in main_window.log_text.toPlainText()

def test_processing_error_shows_messagebox(main_window, qtbot):
    with patch.object(QMessageBox, "critical") as mock_critical:
        main_window.processing_error("test error")
        mock_critical.assert_called_once()
        assert main_window.process_btn.isEnabled()
        assert not main_window.stop_btn.isEnabled()
        assert main_window.select_dir_btn.isEnabled()

def test_processing_finished_state(main_window):
    main_window.process_btn.setEnabled(False)
    main_window.stop_btn.setEnabled(True)
    main_window.select_dir_btn.setEnabled(False)
    main_window.processing_finished()
    assert main_window.process_btn.isEnabled()
    assert not main_window.stop_btn.isEnabled()
    assert main_window.select_dir_btn.isEnabled() 