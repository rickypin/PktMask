"""
工具函数模块全面功能测试
测试Utils模块的实际功能实现，提升测试覆盖率
"""
import pytest
import tempfile
import os
import shutil
from pathlib import Path
from unittest.mock import patch

from pktmask.utils import file_ops, string_ops, math_ops, time as time_ops
from pktmask.common.exceptions import FileError, ValidationError


class TestFileOpsComprehensive:
    """文件操作工具全面测试"""
    
    def test_ensure_directory_creates_new_directory(self, temp_dir):
        """测试创建新目录"""
        test_dir = temp_dir / "new_test_dir"
        assert not test_dir.exists()
        
        result = file_ops.ensure_directory(str(test_dir))
        
        assert result is True
        assert test_dir.exists()
        assert test_dir.is_dir()
    
    def test_ensure_directory_existing_directory(self, temp_dir):
        """测试已存在的目录"""
        result = file_ops.ensure_directory(str(temp_dir))
        assert result is True
    
    def test_ensure_directory_nested_path(self, temp_dir):
        """测试创建嵌套目录"""
        nested_dir = temp_dir / "level1" / "level2" / "level3"
        
        result = file_ops.ensure_directory(str(nested_dir))
        
        assert result is True
        assert nested_dir.exists()
        assert nested_dir.is_dir()
    
    def test_ensure_directory_file_exists_raises_error(self, temp_dir):
        """测试路径为文件时抛出错误"""
        test_file = temp_dir / "test_file.txt"
        test_file.write_text("test content")
        
        with pytest.raises(FileError):
            file_ops.ensure_directory(str(test_file))
    
    def test_ensure_directory_no_create(self, temp_dir):
        """测试不创建不存在的目录"""
        test_dir = temp_dir / "non_existent"
        
        result = file_ops.ensure_directory(str(test_dir), create_if_missing=False)
        
        assert result is False
        assert not test_dir.exists()
    
    def test_safe_join(self):
        """测试安全路径拼接"""
        result = file_ops.safe_join("path1", "path2", "file.txt")
        expected = str(Path("path1") / "path2" / "file.txt")
        assert result == expected
    
    def test_safe_join_with_empty_components(self):
        """测试包含空组件的路径拼接"""
        result = file_ops.safe_join("path1", "", "path2", None, "file.txt")
        expected = str(Path("path1") / "path2" / "file.txt")
        assert result == expected
    
    def test_get_file_extension(self):
        """测试获取文件扩展名"""
        assert file_ops.get_file_extension("test.txt") == ".txt"
        assert file_ops.get_file_extension("test.TXT") == ".txt"
        assert file_ops.get_file_extension("test.tar.gz") == ".gz"
        assert file_ops.get_file_extension("test") == ""
        assert file_ops.get_file_extension("/path/to/test.pcap") == ".pcap"
    
    def test_get_file_base_name(self):
        """测试获取文件基础名称"""
        assert file_ops.get_file_base_name("test.txt") == "test"
        assert file_ops.get_file_base_name("test.tar.gz") == "test.tar"
        assert file_ops.get_file_base_name("/path/to/test.pcap") == "test"
        assert file_ops.get_file_base_name("test") == "test"
    
    def test_get_file_size(self, temp_dir):
        """测试获取文件大小"""
        test_file = temp_dir / "test_file.txt"
        content = "Hello, World! This is test content."
        test_file.write_text(content)
        
        size = file_ops.get_file_size(str(test_file))
        assert size == len(content.encode('utf-8'))
    
    def test_get_file_size_non_existent_file(self):
        """测试获取不存在文件的大小"""
        with pytest.raises(FileError):
            file_ops.get_file_size("/non/existent/file.txt")
    
    def test_is_supported_file(self):
        """测试文件格式支持检查"""
        assert file_ops.is_supported_file("test.pcap") is True
        assert file_ops.is_supported_file("test.pcapng") is True
        # Note: .cap may not be in the supported list, only .pcap and .pcapng
        assert file_ops.is_supported_file("test.txt") is False
        assert file_ops.is_supported_file("test.pdf") is False
    
    def test_find_files_by_extension(self):
        """测试按扩展名查找文件"""
        # 使用独立的临时目录
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            # 创建测试文件
            (temp_path / "test1.txt").write_text("content1")
            (temp_path / "test2.txt").write_text("content2")
            (temp_path / "test.log").write_text("log content")
            (temp_path / "test.pcap").write_text("pcap content")
            
            # 查找txt文件
            txt_files = file_ops.find_files_by_extension(temp_path, [".txt"])
            assert len(txt_files) == 2
            assert all(f.endswith(".txt") for f in txt_files)
            
            # 查找多种格式
            files = file_ops.find_files_by_extension(temp_path, [".txt", ".log"])
            assert len(files) == 3
    
    def test_find_files_by_extension_recursive(self, temp_dir):
        """测试递归查找文件"""
        # 使用全新的临时目录避免其他测试文件干扰
        clean_dir = temp_dir / "clean_test"
        clean_dir.mkdir()
        
        subdir = clean_dir / "subdir"
        subdir.mkdir()
        (clean_dir / "file1.txt").write_text("content1")
        (subdir / "file2.txt").write_text("content2")
        
        # 非递归查找
        files = file_ops.find_files_by_extension(clean_dir, [".txt"], recursive=False)
        assert len(files) == 1
        
        # 递归查找
        files = file_ops.find_files_by_extension(clean_dir, [".txt"], recursive=True)
        assert len(files) == 2
    
    def test_find_pcap_files(self, temp_dir):
        """测试查找PCAP文件"""
        # 使用全新的临时目录避免其他测试文件干扰
        clean_dir = temp_dir / "pcap_test"
        clean_dir.mkdir()
        
        # 创建不同格式的文件
        (clean_dir / "test1.pcap").write_text("pcap1")
        (clean_dir / "test2.pcapng").write_text("pcap2")
        (clean_dir / "test.txt").write_text("text")
        
        pcap_files = file_ops.find_pcap_files(clean_dir)
        assert len(pcap_files) == 2
        assert all(any(f.endswith(ext) for ext in [".pcap", ".pcapng"]) for f in pcap_files)
    
    def test_copy_file_safely(self, temp_dir):
        """测试安全文件复制"""
        source = temp_dir / "source.txt"
        dest = temp_dir / "dest.txt"
        content = "Test content for copying"
        
        source.write_text(content)
        
        result = file_ops.copy_file_safely(str(source), str(dest))
        
        assert result is True
        assert dest.exists()
        assert dest.read_text() == content
    
    def test_copy_file_safely_no_overwrite(self, temp_dir):
        """测试不覆盖已存在文件"""
        source = temp_dir / "source.txt"
        dest = temp_dir / "dest.txt"
        
        source.write_text("source content")
        dest.write_text("existing content")
        
        # 期待抛出FileError异常
        with pytest.raises(FileError):
            file_ops.copy_file_safely(str(source), str(dest), overwrite=False)
    
    def test_copy_file_safely_with_overwrite(self, temp_dir):
        """测试覆盖已存在文件"""
        source = temp_dir / "source.txt"
        dest = temp_dir / "dest.txt"
        
        source.write_text("new content")
        dest.write_text("old content")
        
        result = file_ops.copy_file_safely(str(source), str(dest), overwrite=True)
        
        assert result is True
        assert dest.read_text() == "new content"
    
    def test_delete_file_safely(self, temp_dir):
        """测试安全删除文件"""
        test_file = temp_dir / "to_delete.txt"
        test_file.write_text("content to delete")
        
        assert test_file.exists()
        
        result = file_ops.delete_file_safely(str(test_file))
        
        assert result is True
        assert not test_file.exists()
    
    def test_delete_file_safely_non_existent(self):
        """测试删除不存在的文件"""
        result = file_ops.delete_file_safely("/non/existent/file.txt")
        assert result is True  # 函数返回True，表示"删除操作成功"（即文件不存在）
    
    def test_generate_output_filename(self):
        """测试生成输出文件名"""
        result = file_ops.generate_output_filename("input.pcap", "_processed")
        assert result == "input_processed.pcap"
        
        result = file_ops.generate_output_filename("input.pcap", "_processed", "/output/dir")
        expected = str(Path("/output/dir") / "input_processed.pcap")
        assert result == expected
    
    def test_get_directory_size(self, temp_dir):
        """测试获取目录大小"""
        # 使用全新的临时目录避免其他测试文件干扰
        clean_dir = temp_dir / "size_test"
        clean_dir.mkdir()
        
        # 创建一些文件
        (clean_dir / "file1.txt").write_text("content1")
        (clean_dir / "file2.txt").write_text("longer content for file2")
        
        size = file_ops.get_directory_size(clean_dir)
        assert size > 0
        
        # 计算预期大小
        expected_size = len("content1".encode()) + len("longer content for file2".encode())
        assert size == expected_size


class TestStringOpsComprehensive:
    """字符串操作工具全面测试"""
    
    def test_create_separator(self):
        """测试创建分隔符"""
        sep = string_ops.create_separator(10, "-")
        assert sep == "----------"
        assert len(sep) == 10
        
        sep = string_ops.create_separator(5, "=")
        assert sep == "====="
    
    def test_format_ip_mapping(self):
        """测试IP映射格式化"""
        result = string_ops.format_ip_mapping("192.168.1.1", "10.0.0.1", 15)
        assert "192.168.1.1" in result
        assert "10.0.0.1" in result
        assert " → " in result or " -> " in result or "→" in result
    
    def test_format_step_summary(self):
        """测试步骤摘要格式化"""
        result = string_ops.format_step_summary("Deduplication", 1000, 800, 80.0, "🔄")
        
        assert "Deduplication" in result
        assert "1000" in result
        assert "800" in result
        assert "80.0%" in result
        assert "🔄" in result
    
    def test_format_deduplication_summary(self):
        """测试去重摘要格式化"""
        result = string_ops.format_deduplication_summary("Deduplication", 800, 200, 20.0)
        
        assert "Deduplication" in result
        assert "800" in result
        assert "200" in result
        assert "20.0%" in result
        assert "🔄" in result
    
    def test_format_trimming_summary(self):
        """测试裁切摘要格式化"""
        result = string_ops.format_trimming_summary("Payload Trimming", 1000, 500, 50.0)
        
        assert "Payload Trimming" in result
        assert "1000" in result
        assert "500" in result
        assert "50.0%" in result
        assert "✂️" in result
    
    def test_format_ip_mapping_list(self):
        """测试IP映射列表格式化"""
        ip_mappings = {
            "192.168.1.1": "10.0.0.1",
            "192.168.1.2": "10.0.0.2",
            "192.168.1.3": "10.0.0.3"
        }
        
        result = string_ops.format_ip_mapping_list(ip_mappings)
        
        assert "192.168.1.1" in result
        assert "10.0.0.1" in result
        assert "1." in result  # 序号
        assert "2." in result
        assert "3." in result
    
    def test_format_ip_mapping_list_with_limit(self):
        """测试限制显示数量的IP映射列表"""
        ip_mappings = {f"192.168.1.{i}": f"10.0.0.{i}" for i in range(1, 11)}
        
        result = string_ops.format_ip_mapping_list(ip_mappings, max_display=5)
        
        assert "192.168.1.1" in result
        assert "192.168.1.5" in result
        assert "... and 5 more" in result
    
    def test_format_ip_mapping_list_no_numbers(self):
        """测试不显示序号的IP映射列表"""
        ip_mappings = {"192.168.2.1": "10.0.0.1"}  # 避免IP地址本身包含"1."
        
        result = string_ops.format_ip_mapping_list(ip_mappings, show_numbers=False)
        
        assert "192.168.2.1" in result
        assert "10.0.0.1" in result
        assert "1." not in result
    
    def test_format_section_header(self):
        """测试章节标题格式化"""
        result = string_ops.format_section_header("Test Section", "📋", 20)
        
        assert "Test Section" in result
        assert "📋" in result
        assert len([line for line in result.split('\n') if '=' in line]) >= 1
    
    def test_format_summary_section(self):
        """测试摘要章节格式化"""
        items = ["Item 1", "Item 2", "Item 3"]
        result = string_ops.format_summary_section("Summary", items, "📈")
        
        assert "Summary" in result
        assert "📈" in result
        assert "• Item 1" in result
        assert "• Item 2" in result
        assert "• Item 3" in result
    
    def test_format_file_status(self):
        """测试文件状态格式化"""
        result = string_ops.format_file_status("test.pcap", "Processed", ["Detail 1", "Detail 2"])
        
        assert "test.pcap" in result
        assert "Processed" in result
    
    def test_truncate_string(self):
        """测试字符串截断"""
        long_text = "This is a very long string that should be truncated"
        
        result = string_ops.truncate_string(long_text, 20)
        
        assert len(result) <= 23  # 20 + 3 for "..."
        assert result.endswith("...")
        
        # 测试短字符串不被截断
        short_text = "Short"
        result = string_ops.truncate_string(short_text, 20)
        assert result == "Short"
    
    def test_pad_string(self):
        """测试字符串填充"""
        if hasattr(string_ops, 'pad_string'):
            # 右对齐：文本靠右，填充在左边，所以字符串开头应该是填充字符，结尾是原文本
            result = string_ops.pad_string("test", 10, ">")
            assert len(result) == 10
            assert result.endswith("test")
            assert result.startswith(" ")
            
            # 左对齐：文本靠左，填充在右边，所以字符串开头是原文本，结尾是填充字符
            result = string_ops.pad_string("test", 10, "<")
            assert len(result) == 10
            assert result.startswith("test")
            assert result.endswith(" ")
            
            # 居中对齐：文本在中间
            result = string_ops.pad_string("test", 10, "^")
            assert len(result) == 10
            assert "test" in result
    
    def test_join_with_separator(self):
        """测试带分隔符的字符串连接"""
        items = ["item1", "item2", "item3"]
        result = string_ops.join_with_separator(items, " | ")
        assert result == "item1 | item2 | item3"
        
        result = string_ops.join_with_separator([], empty_text="Nothing")
        assert result == "Nothing"
    
    def test_format_key_value_pairs(self):
        """测试键值对格式化"""
        data = {"key1": "value1", "key2": "value2", "key3": 123}
        result = string_ops.format_key_value_pairs(data)
        
        assert "key1: value1" in result
        assert "key2: value2" in result
        assert "key3: 123" in result
    
    def test_clean_filename(self):
        """测试文件名清理"""
        dirty_name = "file<>name|with:illegal*chars?.txt"
        clean_name = string_ops.clean_filename(dirty_name)
        
        illegal_chars = '<>|:*?'
        for char in illegal_chars:
            assert char not in clean_name
        
        assert clean_name.endswith(".txt")
        assert "file" in clean_name
        assert "name" in clean_name
    
    def test_format_progress_text(self):
        """测试进度文本格式化"""
        result = string_ops.format_progress_text(25, 100, "files")
        
        assert "25" in result
        assert "100" in result
        assert "files" in result
        assert "%" in result or "of" in result


class TestMathOpsComprehensive:
    """数学操作工具全面测试"""
    
    def test_calculate_percentage(self):
        """测试百分比计算"""
        assert math_ops.calculate_percentage(25, 100) == 25.0
        assert math_ops.calculate_percentage(1, 3, 2) == 33.33
        assert math_ops.calculate_percentage(0, 100) == 0.0
        assert math_ops.calculate_percentage(100, 100) == 100.0
        
        # 测试除零情况
        assert math_ops.calculate_percentage(25, 0) == 0.0
    
    def test_calculate_rate(self):
        """测试处理率计算"""
        assert math_ops.calculate_rate(80, 100) == 80.0
        assert math_ops.calculate_rate(33, 100, 1) == 33.0
        assert math_ops.calculate_rate(0, 100) == 0.0
    
    def test_calculate_speed(self):
        """测试速度计算"""
        assert math_ops.calculate_speed(100, 10.0) == 10.0
        assert math_ops.calculate_speed(150, 5.0, 1) == 30.0
        
        # 测试除零情况
        assert math_ops.calculate_speed(100, 0) == 0.0
        assert math_ops.calculate_speed(100, -1) == 0.0
    
    def test_safe_divide(self):
        """测试安全除法"""
        assert math_ops.safe_divide(10, 2) == 5.0
        assert math_ops.safe_divide(10, 0) == 0.0
        assert math_ops.safe_divide(10, 0, -1) == -1.0
        assert math_ops.safe_divide(7, 3) == pytest.approx(2.333, abs=0.001)
    
    def test_format_number(self):
        """测试数字格式化"""
        assert math_ops.format_number(1234) == "1,234"
        assert math_ops.format_number(1234, thousands_separator=False) == "1234"
        assert math_ops.format_number(1234.567, 2) == "1,234.57"
        assert math_ops.format_number(1234.567, 2, False) == "1234.57"
    
    def test_format_size_bytes(self):
        """测试字节大小格式化"""
        assert math_ops.format_size_bytes(0) == "0 B"
        assert math_ops.format_size_bytes(512) == "512 B"
        assert math_ops.format_size_bytes(1024) == "1.00 KB"
        assert math_ops.format_size_bytes(1024*1024) == "1.00 MB"
        assert math_ops.format_size_bytes(1024*1024*1024) == "1.00 GB"
        assert math_ops.format_size_bytes(1536, 1) == "1.5 KB"
    
    def test_calculate_statistics(self):
        """测试统计信息计算"""
        values = [1, 2, 3, 4, 5]
        stats = math_ops.calculate_statistics(values)
        
        assert stats['count'] == 5
        assert stats['sum'] == 15
        assert stats['mean'] == 3.0
        assert stats['min'] == 1
        assert stats['max'] == 5
        assert stats['median'] == 3
        
        # 测试偶数个值的中位数
        values = [1, 2, 3, 4]
        stats = math_ops.calculate_statistics(values)
        assert stats['median'] == 2.5
        
        # 测试空列表
        stats = math_ops.calculate_statistics([])
        assert stats['count'] == 0
        assert stats['sum'] == 0
        
        # 测试包含None的列表
        values = [1, 2, None, 4, 5]
        stats = math_ops.calculate_statistics(values)
        assert stats['count'] == 4
        assert stats['sum'] == 12
    
    def test_format_processing_summary(self):
        """测试处理摘要格式化"""
        result = math_ops.format_processing_summary(1000, 800, "Deduplication", "packets")
        
        assert "1,000" in result  # 适配千位分隔符格式
        assert "800" in result
        assert "Deduplication" in result
        assert "packets" in result
        assert "80.0%" in result
    
    def test_clamp(self):
        """测试值限制"""
        assert math_ops.clamp(5, 0, 10) == 5
        assert math_ops.clamp(15, 0, 10) == 10
        assert math_ops.clamp(-5, 0, 10) == 0
        assert math_ops.clamp(7.5, 5.0, 10.0) == 7.5
    
    def test_normalize_value(self):
        """测试值归一化"""
        assert math_ops.normalize_value(5, 0, 10) == 0.5
        assert math_ops.normalize_value(0, 0, 10) == 0.0
        assert math_ops.normalize_value(10, 0, 10) == 1.0
        assert math_ops.normalize_value(15, 0, 10) == 1.5
    
    def test_moving_average(self):
        """测试移动平均"""
        values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        result = math_ops.moving_average(values, 3)
        
        assert len(result) == len(values) - 2  # 窗口大小为3，减少2个值
        assert result[0] == 2.0  # (1+2+3)/3
        assert result[1] == 3.0  # (2+3+4)/3
        
        # 测试窗口大小大于列表长度 - 根据实际实现应返回原列表副本
        result = math_ops.moving_average([1, 2], 5)
        assert result == [1, 2]
    
    def test_calculate_growth_rate(self):
        """测试增长率计算"""
        assert math_ops.calculate_growth_rate(100, 120) == 20.0
        assert math_ops.calculate_growth_rate(100, 80) == -20.0
        assert math_ops.calculate_growth_rate(100, 100) == 0.0
        
        # 测试从0开始的增长
        assert math_ops.calculate_growth_rate(0, 100) == float('inf')


class TestTimeOpsComprehensive:
    """时间工具全面测试"""
    
    def test_format_duration(self):
        """测试持续时间格式化"""
        if hasattr(time_ops, 'format_duration_seconds'):
            result = time_ops.format_duration_seconds(65)  # 1分5秒
            assert "1" in result and ("m" in result)  # 1m
            assert "5" in result and ("s" in result)  # 5s
            
            result = time_ops.format_duration_seconds(3661)  # 1小时1分1秒
            assert "1" in result and ("h" in result)  # 1h
        
        # 同时测试format_duration函数（基于时间戳的）
        if hasattr(time_ops, 'format_duration'):
            import time
            start = time.time()
            # 模拟一个很短的间隔测试
            result = time_ops.format_duration(start - 65, start)  # 65秒前到现在
            assert "1" in result and "m" in result  # 应该包含分钟
            assert "5" in result and "s" in result  # 应该包含秒
    
    def test_get_timestamp(self):
        """测试获取时间戳"""
        if hasattr(time_ops, 'get_timestamp'):
            timestamp = time_ops.get_timestamp()
            assert isinstance(timestamp, (int, float))
            assert timestamp > 0
    
    def test_format_timestamp(self):
        """测试时间戳格式化"""
        if hasattr(time_ops, 'format_timestamp'):
            import time
            current_time = time.time()
            result = time_ops.format_timestamp(current_time)
            assert isinstance(result, str)
            assert len(result) > 0
            # 检查是否包含日期时间的基本格式
            assert any(char.isdigit() for char in result)
    
    def test_sleep_with_callback(self):
        """测试带回调的睡眠功能"""
        if hasattr(time_ops, 'sleep_with_callback'):
            callback_count = 0
            
            def test_callback():
                nonlocal callback_count
                callback_count += 1
            
            # 使用很短的时间进行测试
            time_ops.sleep_with_callback(0.01, test_callback, 0.005)
            assert callback_count >= 1


@pytest.mark.integration
class TestUtilsIntegrationComprehensive:
    """Utils模块综合集成测试"""
    
    def test_file_and_string_ops_integration(self, temp_dir):
        """测试文件操作和字符串操作的集成"""
        # 创建一个文件名需要清理的文件
        dirty_filename = "test<file>name.txt"
        clean_filename = string_ops.clean_filename(dirty_filename)
        
        # 使用清理后的文件名创建文件
        file_path = temp_dir / clean_filename
        content = "Test content for integration"
        file_path.write_text(content)
        
        # 获取文件大小并格式化
        size = file_ops.get_file_size(str(file_path))
        formatted_size = math_ops.format_size_bytes(size)
        
        assert size > 0
        assert "B" in formatted_size
        assert clean_filename != dirty_filename
        assert "<" not in clean_filename
        assert ">" not in clean_filename
    
    def test_math_and_string_ops_integration(self):
        """测试数学操作和字符串操作的集成"""
        # 模拟处理统计
        original_count = 1000
        processed_count = 850
        rate = math_ops.calculate_percentage(processed_count, original_count)
        
        # 格式化摘要
        summary = string_ops.format_step_summary("Test Step", original_count, processed_count, rate)
        
        assert "1000" in summary
        assert "850" in summary
        assert "85.0%" in summary
        assert "Test Step" in summary
    
    def test_all_utils_modules_work_together(self, temp_dir):
        """测试所有工具模块协同工作"""
        # 1. 创建测试文件
        test_files = []
        for i in range(5):
            filename = f"test_file_{i}.pcap"
            file_path = temp_dir / filename
            content = f"Test content for file {i}" * (i + 1)  # 不同大小的文件
            file_path.write_text(content)
            test_files.append(str(file_path))
        
        # 2. 查找PCAP文件
        found_files = file_ops.find_pcap_files(temp_dir)
        # 过滤只保留我们创建的测试文件
        our_test_files = [f for f in found_files if any(f"test_file_{i}" in f for i in range(5))]
        
        # 验证我们创建的文件都被找到
        assert len(our_test_files) >= 5
        
        # 验证我们创建的文件都在其中
        expected_basenames = [f"test_file_{i}" for i in range(5)]
        found_basenames = [file_ops.get_file_base_name(f) for f in our_test_files]
        for expected_basename in expected_basenames:
            assert expected_basename in found_basenames
        
        # 3. 计算统计信息（只基于我们的文件）
        our_file_sizes = [file_ops.get_file_size(f) for f in our_test_files]
        stats = math_ops.calculate_statistics(our_file_sizes)
        
        # 4. 格式化结果
        summary_items = []
        for f in our_test_files:
            size = file_ops.get_file_size(f)
            formatted_size = math_ops.format_size_bytes(size)
            base_name = file_ops.get_file_base_name(f)
            summary_items.append(f"{base_name}: {formatted_size}")
        
        summary = string_ops.format_summary_section("File Summary", summary_items)
        
        # 5. 验证结果
        assert stats['count'] == len(our_test_files)
        assert stats['sum'] > 0
        assert "File Summary" in summary
        assert any("test_file_" in item for item in summary_items)
        
        # 6. 验证所有我们创建的文件大小都被正确计算
        assert all(size > 0 for size in our_file_sizes)
        assert len(summary_items) == len(our_test_files)
        
        # 7. 验证文件内容长度符合预期
        for i, test_file in enumerate(test_files):
            expected_content_length = len(f"Test content for file {i}") * (i + 1)
            actual_size = file_ops.get_file_size(test_file)
            assert actual_size == expected_content_length 