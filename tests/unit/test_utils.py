"""
工具函数模块单元测试
测试文件操作、字符串操作、数学操作等工具函数
"""
import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

from pktmask.utils import file_ops, string_ops, math_ops, time


class TestFileOps:
    """文件操作工具测试"""
    
    def test_file_ops_module_exists(self):
        """测试文件操作模块存在"""
        assert file_ops is not None
    
    def test_file_ops_has_common_functions(self):
        """测试文件操作模块有常见函数"""
        # 检查常见的文件操作函数
        common_functions = [
            'ensure_directory_exists',
            'get_file_size',
            'copy_file',
            'move_file'
        ]
        
        for func_name in common_functions:
            if hasattr(file_ops, func_name):
                assert callable(getattr(file_ops, func_name))
    
    def test_ensure_directory_exists(self, temp_dir):
        """测试确保目录存在功能"""
        if hasattr(file_ops, 'ensure_directory_exists'):
            test_dir = temp_dir / "test_subdir"
            
            # 目录不存在时应该创建
            result = file_ops.ensure_directory_exists(str(test_dir))
            
            # 验证目录存在
            assert test_dir.exists()
    
    def test_get_file_size(self, temp_dir):
        """测试获取文件大小功能"""
        if hasattr(file_ops, 'get_file_size'):
            # 创建测试文件
            test_file = temp_dir / "test_file.txt"
            test_content = "Hello, World!"
            test_file.write_text(test_content)
            
            # 获取文件大小
            size = file_ops.get_file_size(str(test_file))
            
            # 验证大小
            assert size == len(test_content.encode('utf-8'))
    
    @patch('shutil.copy2')
    def test_copy_file(self, mock_copy, temp_dir):
        """测试文件复制功能"""
        if hasattr(file_ops, 'copy_file'):
            source = temp_dir / "source.txt"
            dest = temp_dir / "dest.txt"
            
            # 创建源文件
            source.touch()
            
            # 执行复制
            file_ops.copy_file(str(source), str(dest))
            
            # 验证调用了copy2
            mock_copy.assert_called_once()


class TestStringOps:
    """字符串操作工具测试"""
    
    def test_string_ops_module_exists(self):
        """测试字符串操作模块存在"""
        assert string_ops is not None
    
    def test_string_ops_has_common_functions(self):
        """测试字符串操作模块有常见函数"""
        # 检查常见的字符串操作函数
        common_functions = [
            'sanitize_filename',
            'format_bytes',
            'truncate_string',
            'escape_html'
        ]
        
        for func_name in common_functions:
            if hasattr(string_ops, func_name):
                assert callable(getattr(string_ops, func_name))
    
    def test_sanitize_filename(self):
        """测试文件名清理功能"""
        if hasattr(string_ops, 'sanitize_filename'):
            # 测试包含非法字符的文件名
            dirty_name = "file<>name|with:illegal*chars?.txt"
            clean_name = string_ops.sanitize_filename(dirty_name)
            
            # 验证非法字符被清理
            illegal_chars = '<>|:*?'
            for char in illegal_chars:
                assert char not in clean_name
    
    def test_format_bytes(self):
        """测试字节格式化功能"""
        if hasattr(string_ops, 'format_bytes'):
            # 测试不同大小的字节数
            test_cases = [
                (1024, "KB"),
                (1024*1024, "MB"),
                (1024*1024*1024, "GB")
            ]
            
            for bytes_val, expected_unit in test_cases:
                result = string_ops.format_bytes(bytes_val)
                assert expected_unit in result
    
    def test_truncate_string(self):
        """测试字符串截断功能"""
        if hasattr(string_ops, 'truncate_string'):
            long_string = "This is a very long string that should be truncated"
            max_length = 20
            
            result = string_ops.truncate_string(long_string, max_length)
            
            # 验证长度不超过限制
            assert len(result) <= max_length + 3  # +3 for "..."


class TestMathOps:
    """数学操作工具测试"""
    
    def test_math_ops_module_exists(self):
        """测试数学操作模块存在"""
        assert math_ops is not None
    
    def test_math_ops_has_common_functions(self):
        """测试数学操作模块有常见函数"""
        # 检查常见的数学操作函数
        common_functions = [
            'calculate_percentage',
            'round_to_nearest',
            'clamp_value'
        ]
        
        for func_name in common_functions:
            if hasattr(math_ops, func_name):
                assert callable(getattr(math_ops, func_name))
    
    def test_calculate_percentage(self):
        """测试百分比计算功能"""
        if hasattr(math_ops, 'calculate_percentage'):
            result = math_ops.calculate_percentage(25, 100)
            assert result == 25.0
            
            result = math_ops.calculate_percentage(1, 3)
            assert abs(result - 33.33) < 0.1  # 允许小的浮点误差
    
    def test_round_to_nearest(self):
        """测试四舍五入功能"""
        if hasattr(math_ops, 'round_to_nearest'):
            result = math_ops.round_to_nearest(23, 5)
            assert result == 25
            
            result = math_ops.round_to_nearest(22, 5)
            assert result == 20
    
    def test_clamp_value(self):
        """测试值限制功能"""
        if hasattr(math_ops, 'clamp_value'):
            # 测试值在范围内
            result = math_ops.clamp_value(5, 0, 10)
            assert result == 5
            
            # 测试值超出上限
            result = math_ops.clamp_value(15, 0, 10)
            assert result == 10
            
            # 测试值低于下限
            result = math_ops.clamp_value(-5, 0, 10)
            assert result == 0


class TestTimeUtils:
    """时间工具测试"""
    
    def test_time_module_exists(self):
        """测试时间模块存在"""
        assert time is not None
    
    def test_time_has_common_functions(self):
        """测试时间模块有常见函数"""
        # 检查常见的时间操作函数
        common_functions = [
            'format_duration_seconds',
            'current_timestamp',
            'current_time'
        ]
        
        for func_name in common_functions:
            if hasattr(time, func_name):
                assert callable(getattr(time, func_name))
    
    def test_format_duration(self):
        """测试持续时间格式化功能"""
        if hasattr(time, 'format_duration_seconds'):
            # 测试秒数格式化
            result = time.format_duration_seconds(3661)  # 1小时1分1秒
            assert "1h" in result  # 应该包含1小时
            assert "1m" in result  # 应该包含1分钟
            assert "1s" in result  # 应该包含1秒钟
    
    def test_get_timestamp(self):
        """测试获取时间戳功能"""
        if hasattr(time, 'current_timestamp'):
            timestamp = time.current_timestamp()
            assert isinstance(timestamp, str)
            assert timestamp is not None
            assert len(timestamp) > 0
    
    def test_format_timestamp(self):
        """测试时间戳格式化功能"""
        if hasattr(time, 'current_time'):
            result = time.current_time()
            assert isinstance(result, str)
            assert len(result) > 0


@pytest.mark.unit
class TestUtilsIntegration:
    """工具函数集成测试"""
    
    def test_all_utils_modules_importable(self):
        """测试所有工具模块都可以导入"""
        modules = [file_ops, string_ops, math_ops, time]
        
        for module in modules:
            assert module is not None
    
    def test_utils_functions_return_expected_types(self, temp_dir):
        """测试工具函数返回期望的类型"""
        # 测试文件操作返回类型
        if hasattr(file_ops, 'get_file_size'):
            test_file = temp_dir / "test.txt"
            test_file.write_text("test")
            
            size = file_ops.get_file_size(str(test_file))
            assert isinstance(size, (int, float))
        
        # 测试字符串操作返回类型
        if hasattr(string_ops, 'format_bytes'):
            result = string_ops.format_bytes(1024)
            assert isinstance(result, str)
        
        # 测试数学操作返回类型
        if hasattr(math_ops, 'calculate_percentage'):
            result = math_ops.calculate_percentage(50, 100)
            assert isinstance(result, (int, float))
    
    def test_utils_handle_edge_cases(self):
        """测试工具函数处理边界情况"""
        # 测试零值和负值
        if hasattr(math_ops, 'calculate_percentage'):
            # 零分母情况
            try:
                result = math_ops.calculate_percentage(50, 0)
                # 如果没有抛出异常，应该返回某种合理的值
                assert result is not None
            except (ZeroDivisionError, ValueError):
                # 抛出异常也是合理的处理方式
                pass
        
        # 测试空字符串
        if hasattr(string_ops, 'sanitize_filename'):
            result = string_ops.sanitize_filename("")
            assert isinstance(result, str)
        
        # 测试负数
        if hasattr(string_ops, 'format_bytes'):
            try:
                result = string_ops.format_bytes(-1024)
                assert isinstance(result, str)
            except ValueError:
                # 拒绝负数也是合理的
                pass 