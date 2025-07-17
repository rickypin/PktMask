#!/usr/bin/env python3
"""
Windows环境TShark依赖检查场景测试

此脚本专门测试Windows打包环境下可能出现的各种边界情况，
验证修复后的代码能够正确处理这些情况。
"""

import os
import sys
import subprocess
import unittest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.pktmask.infrastructure.dependency.checker import DependencyChecker


class TestWindowsTSharkScenarios(unittest.TestCase):
    """测试Windows环境下的TShark依赖检查场景"""
    
    def setUp(self):
        """测试前准备"""
        self.checker = DependencyChecker()
    
    @patch('os.name', 'nt')
    def test_windows_default_paths_search(self):
        """测试Windows默认路径搜索"""
        with patch('pathlib.Path.exists') as mock_exists, \
             patch.object(self.checker, '_is_executable') as mock_executable:
            
            # 模拟在第二个默认路径找到tshark
            def exists_side_effect(path):
                return str(path) == r"C:\Program Files (x86)\Wireshark\tshark.exe"

            mock_exists.side_effect = exists_side_effect
            mock_executable.return_value = True
            
            result = self.checker._find_tshark_executable()
            
            self.assertEqual(r"C:\Program Files (x86)\Wireshark\tshark.exe", result)
    
    @patch('os.name', 'nt')
    def test_windows_portable_installation(self):
        """测试Windows便携版安装检测"""
        with patch('pathlib.Path.exists') as mock_exists, \
             patch.object(self.checker, '_is_executable') as mock_executable, \
             patch('os.getcwd') as mock_getcwd, \
             patch('sys.executable', r'C:\MyApp\pktmask.exe'):
            
            mock_getcwd.return_value = r"C:\MyApp"
            
            # 模拟在应用目录下找到tshark
            def exists_side_effect(path):
                return str(path) == r"C:\MyApp\tshark.exe"

            mock_exists.side_effect = exists_side_effect
            mock_executable.return_value = True
            
            result = self.checker._find_tshark_executable()
            
            self.assertEqual(r"C:\MyApp\tshark.exe", result)
    
    def test_subprocess_permission_error_windows(self):
        """测试Windows下的权限错误处理"""
        with patch('subprocess.run') as mock_run:
            # 模拟权限错误
            mock_run.side_effect = PermissionError("Access is denied")
            
            result = self.checker._check_tshark_version(r"C:\Program Files\Wireshark\tshark.exe")
            
            self.assertFalse(result['success'])
            self.assertIn("Permission denied", result['error'])
    
    def test_subprocess_file_not_found_windows(self):
        """测试Windows下的文件未找到错误处理"""
        with patch('subprocess.run') as mock_run:
            # 模拟文件未找到错误
            mock_run.side_effect = FileNotFoundError("The system cannot find the file specified")
            
            result = self.checker._check_tshark_version(r"C:\NonExistent\tshark.exe")
            
            self.assertFalse(result['success'])
            self.assertIn("not found", result['error'])
    
    def test_windows_encoding_issues(self):
        """测试Windows编码问题导致的None输出"""
        with patch('subprocess.run') as mock_run:
            # 模拟编码问题导致的None输出
            mock_proc = Mock()
            mock_proc.returncode = 0
            mock_proc.stdout = None  # 编码问题可能导致None
            mock_proc.stderr = None
            mock_run.return_value = mock_proc
            
            result = self.checker._check_protocol_support(r"C:\Program Files\Wireshark\tshark.exe")
            
            self.assertFalse(result['success'])
            self.assertIn("stdout is None", result['error'])
    
    def test_windows_path_with_spaces(self):
        """测试包含空格的Windows路径"""
        path_with_spaces = r"C:\Program Files\Wireshark\tshark.exe"
        
        with patch('subprocess.run') as mock_run:
            mock_proc = Mock()
            mock_proc.returncode = 0
            mock_proc.stdout = "TShark (Wireshark) 4.2.0"
            mock_proc.stderr = ""
            mock_run.return_value = mock_proc
            
            result = self.checker._check_tshark_version(path_with_spaces)
            
            # 验证路径被正确传递给subprocess
            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            self.assertEqual(path_with_spaces, call_args[0])
            
            self.assertTrue(result['success'])
    
    def test_windows_antivirus_interference(self):
        """测试Windows防病毒软件干扰的情况"""
        with patch('subprocess.run') as mock_run:
            # 模拟防病毒软件阻止执行，导致超时
            mock_run.side_effect = subprocess.TimeoutExpired("tshark", 10)
            
            result = self.checker._check_protocol_support(r"C:\Program Files\Wireshark\tshark.exe")
            
            self.assertFalse(result['success'])
            self.assertIn("timeout", result['error'])
    
    def test_windows_uac_elevation_needed(self):
        """测试需要UAC提升权限的情况"""
        with patch('subprocess.run') as mock_run:
            # 模拟需要管理员权限的错误
            mock_proc = Mock()
            mock_proc.returncode = 1
            mock_proc.stdout = ""
            mock_proc.stderr = "Access denied. Administrator privileges required."
            mock_run.return_value = mock_proc
            
            result = self.checker._check_tshark_version(r"C:\Program Files\Wireshark\tshark.exe")
            
            self.assertFalse(result['success'])
            self.assertIn("Administrator privileges required", result['error'])
    
    @patch('os.name', 'nt')
    def test_windows_error_message_formatting(self):
        """测试Windows环境下的错误消息格式化"""
        from src.pktmask.infrastructure.dependency.checker import DependencyResult, DependencyStatus
        
        # 测试缺失依赖的Windows特定建议
        result = DependencyResult(
            name="tshark",
            status=DependencyStatus.MISSING,
            error_message="TShark executable not found"
        )
        
        formatted = self.checker._format_error_message(result)
        
        self.assertIn("Check if Wireshark is installed", formatted)
        self.assertIn("Try running as administrator", formatted)
        self.assertIn("Verify installation path", formatted)
    
    def test_packaged_app_environment_variables(self):
        """测试打包应用环境变量的影响"""
        with patch.dict(os.environ, {
            'PATH': r'C:\PackagedApp\bin;C:\Windows\System32',
            'PROGRAMFILES': r'C:\Program Files',
            'PROGRAMFILES(X86)': r'C:\Program Files (x86)'
        }):
            with patch('shutil.which') as mock_which, \
                 patch('pathlib.Path.exists') as mock_exists, \
                 patch.object(self.checker, '_is_executable') as mock_executable:
                
                # 模拟系统PATH中没有tshark，但默认路径存在
                mock_which.return_value = None
                mock_exists.return_value = True
                mock_executable.return_value = True
                
                result = self.checker._find_tshark_executable()
                
                # 应该在默认路径中找到
                self.assertIsNotNone(result)
                self.assertTrue(result.endswith('tshark.exe'))


class TestWindowsSpecificFixes(unittest.TestCase):
    """测试Windows特定修复的有效性"""
    
    def setUp(self):
        self.checker = DependencyChecker()
    
    def test_none_stdout_handling_in_protocol_check(self):
        """验证协议检查中None stdout的处理"""
        with patch('subprocess.run') as mock_run:
            mock_proc = Mock()
            mock_proc.returncode = 0
            mock_proc.stdout = None
            mock_proc.stderr = "Some error info"
            mock_run.return_value = mock_proc
            
            # 这应该不会抛出AttributeError
            result = self.checker._check_protocol_support("/fake/path")
            
            self.assertFalse(result['success'])
            self.assertIn("stdout is None", result['error'])
    
    def test_none_stderr_handling_in_json_check(self):
        """验证JSON检查中None stderr的处理"""
        with patch('subprocess.run') as mock_run:
            mock_proc = Mock()
            mock_proc.returncode = 0
            mock_proc.stdout = ""
            mock_proc.stderr = None
            mock_run.return_value = mock_proc
            
            # 这应该不会抛出AttributeError
            result = self.checker._check_json_output("/fake/path")
            
            self.assertTrue(result['success'])  # 没有错误信息表示支持JSON


if __name__ == '__main__':
    import subprocess
    unittest.main(verbosity=2)
