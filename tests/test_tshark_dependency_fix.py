#!/usr/bin/env python3
"""
测试脚本：验证TShark依赖检查的NoneType错误修复

此脚本测试修复后的代码在各种边界情况下的表现，
特别是模拟Windows环境下可能导致NoneType错误的场景。
"""

import os
import sys
import unittest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.pktmask.infrastructure.dependency.checker import DependencyChecker, DependencyStatus


class TestTSharkDependencyFix(unittest.TestCase):
    """测试TShark依赖检查的NoneType错误修复"""
    
    def setUp(self):
        """测试前准备"""
        self.checker = DependencyChecker()
    
    def test_protocol_support_none_stdout(self):
        """测试协议支持检查中stdout为None的情况"""
        with patch('subprocess.run') as mock_run:
            # 模拟subprocess返回stdout=None的情况
            mock_proc = Mock()
            mock_proc.returncode = 0
            mock_proc.stdout = None
            mock_proc.stderr = "some stderr"
            mock_run.return_value = mock_proc
            
            result = self.checker._check_protocol_support("/fake/tshark")
            
            self.assertFalse(result['success'])
            self.assertIn("stdout is None", result['error'])
            self.assertEqual([], result['supported_protocols'])
    
    def test_protocol_support_empty_stdout(self):
        """测试协议支持检查中stdout为空字符串的情况"""
        with patch('subprocess.run') as mock_run:
            # 模拟subprocess返回空stdout的情况
            mock_proc = Mock()
            mock_proc.returncode = 0
            mock_proc.stdout = ""
            mock_proc.stderr = ""
            mock_run.return_value = mock_proc
            
            result = self.checker._check_protocol_support("/fake/tshark")
            
            self.assertFalse(result['success'])
            self.assertIn("empty output", result['error'])
    
    def test_protocol_support_whitespace_stdout(self):
        """测试协议支持检查中stdout只有空白字符的情况"""
        with patch('subprocess.run') as mock_run:
            # 模拟subprocess返回只有空白字符的stdout
            mock_proc = Mock()
            mock_proc.returncode = 0
            mock_proc.stdout = "   \n\t  \n  "
            mock_proc.stderr = ""
            mock_run.return_value = mock_proc
            
            result = self.checker._check_protocol_support("/fake/tshark")
            
            self.assertFalse(result['success'])
            self.assertIn("empty output", result['error'])
    
    def test_version_check_none_outputs(self):
        """测试版本检查中stdout和stderr都为None的情况"""
        with patch('subprocess.run') as mock_run:
            # 模拟subprocess返回stdout和stderr都为None
            mock_proc = Mock()
            mock_proc.returncode = 0
            mock_proc.stdout = None
            mock_proc.stderr = None
            mock_run.return_value = mock_proc
            
            result = self.checker._check_tshark_version("/fake/tshark")
            
            self.assertFalse(result['success'])
            self.assertIn("no output", result['error'])
    
    def test_version_check_mixed_none_outputs(self):
        """测试版本检查中stdout为None但stderr有内容的情况"""
        with patch('subprocess.run') as mock_run:
            # 模拟subprocess返回stdout=None但stderr有内容
            mock_proc = Mock()
            mock_proc.returncode = 0
            mock_proc.stdout = None
            mock_proc.stderr = "TShark (Wireshark) 4.2.0"
            mock_run.return_value = mock_proc
            
            result = self.checker._check_tshark_version("/fake/tshark")
            
            # 应该能够从stderr解析版本
            self.assertTrue(result['success'])
            self.assertEqual((4, 2, 0), result['version'])
    
    def test_json_output_none_stderr(self):
        """测试JSON输出检查中stderr为None的情况"""
        with patch('subprocess.run') as mock_run:
            # 模拟subprocess返回stderr=None
            mock_proc = Mock()
            mock_proc.returncode = 0
            mock_proc.stdout = ""
            mock_proc.stderr = None
            mock_run.return_value = mock_proc
            
            result = self.checker._check_json_output("/fake/tshark")
            
            # 应该成功，因为没有错误信息
            self.assertTrue(result['success'])
    
    @patch('os.name', 'nt')  # 模拟Windows环境
    def test_windows_executable_detection(self):
        """测试Windows环境下的可执行文件检测"""
        with patch('pathlib.Path.exists') as mock_exists:
            mock_exists.return_value = True
            
            # 测试.exe文件应该被识别为可执行
            self.assertTrue(self.checker._is_executable("C:\\test\\tshark.exe"))
            
            # 测试非.exe文件应该不被识别为可执行
            self.assertFalse(self.checker._is_executable("C:\\test\\tshark"))
    
    @patch('os.name', 'posix')  # 模拟Unix环境
    def test_unix_executable_detection(self):
        """测试Unix环境下的可执行文件检测"""
        with patch('pathlib.Path.exists') as mock_exists, \
             patch('os.access') as mock_access:
            mock_exists.return_value = True
            mock_access.return_value = True
            
            # 测试有执行权限的文件应该被识别为可执行
            self.assertTrue(self.checker._is_executable("/usr/bin/tshark"))
            
            mock_access.return_value = False
            # 测试没有执行权限的文件应该不被识别为可执行
            self.assertFalse(self.checker._is_executable("/usr/bin/tshark"))
    
    def test_error_message_formatting_execution_error(self):
        """测试执行错误的错误消息格式化"""
        from src.pktmask.infrastructure.dependency.checker import DependencyResult
        
        # 测试NoneType错误的特殊处理
        result = DependencyResult(
            name="tshark",
            status=DependencyStatus.EXECUTION_ERROR,
            path="/fake/path",
            version_found="4.2.0",
            error_message="Protocol support check failed: 'NoneType' object has no attribute 'lower'"
        )
        
        formatted = self.checker._format_error_message(result)
        
        self.assertIn("Windows compatibility", formatted)
        self.assertIn("known issue", formatted)
        self.assertIn("packaged Windows applications", formatted)
    
    def test_comprehensive_dependency_check_with_mocked_failure(self):
        """测试完整的依赖检查流程，模拟各种失败情况"""
        with patch.object(self.checker, '_find_tshark_executable') as mock_find, \
             patch.object(self.checker, '_check_tshark_version') as mock_version, \
             patch.object(self.checker, '_check_protocol_support') as mock_protocol:
            
            # 模拟找到tshark但协议检查失败（NoneType错误）
            mock_find.return_value = "/fake/tshark"
            mock_version.return_value = {
                'success': True,
                'version': (4, 2, 0),
                'meets_requirement': True
            }
            mock_protocol.return_value = {
                'success': False,
                'error': "Protocol support check failed: 'NoneType' object has no attribute 'lower'"
            }
            
            result = self.checker.check_tshark()
            
            self.assertFalse(result.is_satisfied)
            self.assertEqual(DependencyStatus.EXECUTION_ERROR, result.status)
            self.assertIn("Protocol support check failed", result.error_message)


if __name__ == '__main__':
    # 设置详细的测试输出
    unittest.main(verbosity=2)
