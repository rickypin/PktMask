import pytest
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt
from pktmask.gui.main_window import MainWindow
from unittest.mock import patch, MagicMock
import os

@pytest.fixture
def app(qtbot):
    """创建 QApplication 实例"""
    return QApplication.instance() or QApplication([])

@pytest.fixture
def main_window(app, qtbot):
    """创建主窗口实例"""
    window = MainWindow()
    window.set_test_mode(True)  # 启用测试模式
    qtbot.addWidget(window)
    window.show()
    return window

def test_main_window_title(main_window):
    """测试主窗口标题"""
    assert main_window.windowTitle() == "PktMask"

def test_select_dir_btn_visible_and_enabled(main_window):
    """测试选择目录按钮可见且可用"""
    # 实际上是 dir_path_label 作为按钮使用
    assert hasattr(main_window, "dir_path_label")
    assert main_window.dir_path_label.isVisible()
    assert main_window.dir_path_label.isEnabled()

def test_process_btn_visible(main_window):
    """测试处理按钮可见"""
    assert hasattr(main_window, "start_proc_btn")
    assert main_window.start_proc_btn.isVisible()

def test_log_text_visible(main_window):
    """测试日志区可见"""
    assert hasattr(main_window, "log_text")
    assert main_window.log_text.isVisible()

def test_select_dir_btn_click(main_window, qtbot, tmp_path, monkeypatch):
    # Ensure allowed_root matches tmp_path for path check
    main_window.allowed_root = str(tmp_path)
    monkeypatch.setattr("PyQt6.QtWidgets.QFileDialog.getExistingDirectory", lambda *a, **k: str(tmp_path))
    qtbot.mouseClick(main_window.dir_path_label, Qt.MouseButton.LeftButton)
    assert main_window.start_proc_btn.isEnabled()
    assert f"Selected directory: {tmp_path}" in main_window.log_text.toPlainText()

def test_process_btn_no_dir(main_window, qtbot, monkeypatch):
    # 未选择目录时点击处理按钮，弹出警告
    main_window.start_proc_btn.setEnabled(True)  # 确保按钮可用
    with patch.object(QMessageBox, "warning") as mock_warn:
        qtbot.mouseClick(main_window.start_proc_btn, Qt.MouseButton.LeftButton)
        mock_warn.assert_called_once()

def test_process_btn_and_stop_btn_state(main_window, qtbot, tmp_path, monkeypatch):
    # Ensure allowed_root matches tmp_path for path check
    main_window.allowed_root = str(tmp_path)
    monkeypatch.setattr("PyQt6.QtWidgets.QFileDialog.getExistingDirectory", lambda *a, **k: str(tmp_path))
    qtbot.mouseClick(main_window.dir_path_label, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(main_window.start_proc_btn, Qt.MouseButton.LeftButton)
    assert not main_window.start_proc_btn.isEnabled()
    # Stop and check state recovery
    if main_window.pipeline_thread:
        main_window.pipeline_thread.is_running = False
    qtbot.mouseClick(main_window.start_proc_btn, Qt.MouseButton.LeftButton)  # 在处理中这个按钮应该是Stop功能
    assert main_window.start_proc_btn.isEnabled()

def test_log_text_update(main_window):
    msg = "Test log message"
    main_window.update_log(msg)  # 使用正确的方法名
    assert msg in main_window.log_text.toPlainText()

def test_display_ip_mapping_file_not_found(main_window, tmp_path):
    main_window.base_dir = str(tmp_path)
    # 目录下无 replacement.log
    main_window.display_ip_mapping("subdir", {})
    assert "File not found" in main_window.log_text.toPlainText()

def test_processing_error_shows_messagebox(main_window, qtbot):
    """测试处理错误在测试模式下的行为"""
    # 在测试模式下，错误应该被记录而不是显示阻塞性对话框
    error_messages = []
    
    def capture_error(message):
        error_messages.append(message)
    
    # 连接错误信号
    main_window.error_occurred.connect(capture_error)
    
    # 触发错误
    main_window.processing_error("test error")
    
    # 验证错误被正确处理
    assert "test error" in main_window.log_text.toPlainText()
    
    # 验证UI状态正确恢复
    assert main_window.start_proc_btn.isEnabled()
    # 注意：这里使用正确的属性名 start_proc_btn 而不是 process_btn

def test_processing_finished_state(main_window):
    main_window.start_proc_btn.setEnabled(False)
    main_window.processing_finished()
    assert main_window.start_proc_btn.isEnabled()

def test_select_directory_path_traversal(main_window, monkeypatch, tmp_path):
    main_window.allowed_root = str(tmp_path)
    parent_dir = tmp_path.parent
    monkeypatch.setattr("PyQt6.QtWidgets.QFileDialog.getExistingDirectory", lambda *a, **k: str(parent_dir))
    called = {}
    def fake_warning(*args, **kwargs):
        called['warned'] = True
    monkeypatch.setattr("pktmask.gui.main_window.QMessageBox.warning", fake_warning)
    main_window.choose_folder()  # 使用正确的方法名
    assert called.get('warned'), "Should warn for path traversal"

def test_select_directory_permission_checks(main_window, monkeypatch, tmp_path):
    main_window.allowed_root = str(tmp_path)
    monkeypatch.setattr("PyQt6.QtWidgets.QFileDialog.getExistingDirectory", lambda *a, **k: str(tmp_path))
    monkeypatch.setattr(os, "access", lambda path, mode: mode == os.R_OK)
    called = {}
    def fake_warning(*args, **kwargs):
        called['warned'] = True
    monkeypatch.setattr("pktmask.gui.main_window.QMessageBox.warning", fake_warning)
    main_window.choose_folder()  # 使用正确的方法名
    assert called.get('warned'), "Should warn for no write permission"

def test_select_directory_nonexistent(main_window, monkeypatch, tmp_path):
    main_window.allowed_root = str(tmp_path)
    fake_dir = tmp_path / "not_exist"
    monkeypatch.setattr("PyQt6.QtWidgets.QFileDialog.getExistingDirectory", lambda *a, **k: str(fake_dir))
    monkeypatch.setattr(os.path, "exists", lambda path: False)
    called = {}
    def fake_warning(*args, **kwargs):
        called['warned'] = True
    monkeypatch.setattr("pktmask.gui.main_window.QMessageBox.warning", fake_warning)
    main_window.choose_folder()  # 使用正确的方法名
    assert called.get('warned'), "Should warn for non-existent directory" 