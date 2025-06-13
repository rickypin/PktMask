#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TShark预处理器测试

测试TShark预处理器的各种功能和场景，包括：
- TCP流重组验证
- IP碎片重组验证
- 大文件处理测试
- 错误场景处理
"""

import pytest
import tempfile
import shutil
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.pktmask.core.trim.stages.tshark_preprocessor import TSharkPreprocessor
from src.pktmask.core.trim.stages.base_stage import StageContext
from src.pktmask.core.processors.base_processor import ProcessorResult


class TestTSharkPreprocessor:
    """TShark预处理器测试类"""
    
    @pytest.fixture
    def temp_dir(self):
        """临时目录fixture"""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def sample_pcap(self, temp_dir):
        """示例PCAP文件fixture"""
        pcap_file = temp_dir / "sample.pcap"
        # 创建一个最小的PCAP文件头
        with open(pcap_file, 'wb') as f:
            # PCAP Global Header
            f.write(b'\xd4\xc3\xb2\xa1')  # Magic number
            f.write(b'\x02\x00\x04\x00')  # Version major/minor
            f.write(b'\x00\x00\x00\x00')  # Timezone offset
            f.write(b'\x00\x00\x00\x00')  # Timestamp accuracy
            f.write(b'\xff\xff\x00\x00')  # Max packet length
            f.write(b'\x01\x00\x00\x00')  # Data link type (Ethernet)
        
        return pcap_file
    
    @pytest.fixture
    def stage_context(self, temp_dir, sample_pcap):
        """Stage上下文fixture"""
        return StageContext(
            input_file=sample_pcap,
            output_file=temp_dir / "output.pcap",
            work_dir=temp_dir / "work"
        )
    
    @pytest.fixture
    def mock_tshark_config(self):
        """Mock TShark配置"""
        return {
            'tshark_executable_paths': ['/usr/bin/tshark', '/usr/local/bin/tshark'],
            'tshark_custom_executable': '/usr/bin/tshark',
            'tshark_enable_reassembly': True,
            'tshark_enable_defragmentation': True,
            'tshark_timeout_seconds': 60,
            'tshark_max_memory_mb': 512,
            'temp_dir': None
        }
    
    def test_init_default_config(self):
        """测试默认配置初始化"""
        preprocessor = TSharkPreprocessor()
        
        assert preprocessor.name == "TShark预处理器"
        assert preprocessor._enable_reassembly is True
        assert preprocessor._enable_defragmentation is True
        assert preprocessor._timeout_seconds == 300
        assert preprocessor._max_memory_mb == 1024
    
    def test_init_custom_config(self, mock_tshark_config):
        """测试自定义配置初始化"""
        preprocessor = TSharkPreprocessor(mock_tshark_config)
        
        assert preprocessor._enable_reassembly is True
        assert preprocessor._enable_defragmentation is True
        assert preprocessor._timeout_seconds == 60
        assert preprocessor._max_memory_mb == 512
    
    def test_init_with_custom_paths_config(self):
        """测试使用自定义路径配置初始化"""
        config = {
            'tshark_executable_paths': ['/custom/path1', '/custom/path2'],
            'tshark_custom_executable': '/custom/tshark',
            'tshark_max_memory_mb': 2048
        }
        preprocessor = TSharkPreprocessor(config)
        
        assert preprocessor._executable_paths == ['/custom/path1', '/custom/path2']
        assert preprocessor._custom_executable == '/custom/tshark'
        assert preprocessor._max_memory_mb == 2048
    
    def test_init_with_default_paths(self):
        """测试使用默认路径配置初始化"""
        preprocessor = TSharkPreprocessor()
        
        # 应该使用默认路径
        assert len(preprocessor._executable_paths) > 0
        assert '/usr/bin/tshark' in preprocessor._executable_paths
        assert 'C:\\Program Files\\Wireshark\\tshark.exe' in preprocessor._executable_paths
        assert preprocessor._custom_executable is None
    
    @patch('shutil.which')
    @patch('os.path.exists')
    def test_find_tshark_executable_in_path(self, mock_exists, mock_which):
        """测试在PATH中查找TShark"""
        mock_which.return_value = '/usr/bin/tshark'
        mock_exists.return_value = True
        
        preprocessor = TSharkPreprocessor()
        result = preprocessor._find_tshark_executable()
        
        assert result == '/usr/bin/tshark'
        mock_which.assert_called_once_with('tshark')
    
    @patch('shutil.which')
    @patch('os.path.exists')
    def test_find_tshark_executable_custom_path(self, mock_exists, mock_which):
        """测试使用自定义路径查找TShark"""
        mock_which.return_value = None
        mock_exists.return_value = True
        
        config = {'tshark_custom_executable': '/custom/path/tshark'}
        preprocessor = TSharkPreprocessor(config)
        result = preprocessor._find_tshark_executable()
        
        assert result == '/custom/path/tshark'
        mock_exists.assert_called_with('/custom/path/tshark')
    
    @patch('shutil.which')
    @patch('os.path.exists')
    def test_find_tshark_executable_in_config_paths(self, mock_exists, mock_which):
        """测试在配置路径中查找TShark"""
        mock_which.return_value = None
        
        def mock_exists_side_effect(path):
            return path == '/usr/local/bin/tshark'
        
        mock_exists.side_effect = mock_exists_side_effect
        
        config = {'tshark_executable_paths': ['/opt/bin/tshark', '/usr/local/bin/tshark']}
        preprocessor = TSharkPreprocessor(config)
        result = preprocessor._find_tshark_executable()
        
        assert result == '/usr/local/bin/tshark'
    
    @patch('shutil.which')
    @patch('os.path.exists')
    def test_find_tshark_executable_not_found(self, mock_exists, mock_which):
        """测试TShark未找到的情况"""
        mock_which.return_value = None
        mock_exists.return_value = False
        
        preprocessor = TSharkPreprocessor()
        result = preprocessor._find_tshark_executable()
        
        assert result is None
    
    @patch('subprocess.run')
    def test_get_tshark_version_success(self, mock_run):
        """测试成功获取TShark版本"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="TShark (Wireshark) 3.4.5 (Git v3.4.5)\n"
        )
        
        preprocessor = TSharkPreprocessor()
        preprocessor._tshark_path = '/usr/bin/tshark'
        
        version = preprocessor._get_tshark_version()
        
        assert version == "TShark (Wireshark) 3.4.5 (Git v3.4.5)"
        mock_run.assert_called_once()
    
    @patch('subprocess.run')
    def test_get_tshark_version_failure(self, mock_run):
        """测试获取TShark版本失败"""
        mock_run.return_value = Mock(returncode=1, stdout="")
        
        preprocessor = TSharkPreprocessor()
        preprocessor._tshark_path = '/usr/bin/tshark'
        
        version = preprocessor._get_tshark_version()
        
        assert version == "未知版本"
    
    @patch('subprocess.run')
    def test_verify_tshark_capabilities_success(self, mock_run):
        """测试TShark功能验证成功"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="tcp.desegment_tcp_streams: TRUE\nip.defragment: TRUE\n"
        )
        
        preprocessor = TSharkPreprocessor()
        preprocessor._tshark_path = '/usr/bin/tshark'
        
        # 应该不抛出异常
        preprocessor._verify_tshark_capabilities()
    
    @patch('subprocess.run')
    def test_verify_tshark_capabilities_failure(self, mock_run):
        """测试TShark功能验证失败"""
        mock_run.return_value = Mock(returncode=1, stdout="")
        
        preprocessor = TSharkPreprocessor()
        preprocessor._tshark_path = '/usr/bin/tshark'
        
        with pytest.raises(RuntimeError, match="TShark功能验证失败"):
            preprocessor._verify_tshark_capabilities()
    
    @patch('subprocess.run')
    def test_initialization_success(self, mock_run):
        """测试初始化成功"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="TShark 3.4.5\ntcp.desegment_tcp_streams: TRUE\nip.defragment: TRUE\n"
        )
        
        with patch.object(TSharkPreprocessor, '_find_tshark_executable', 
                         return_value='/usr/bin/tshark'):
            preprocessor = TSharkPreprocessor()
            success = preprocessor.initialize()
            
            assert success is True
            assert preprocessor.is_initialized is True
            assert preprocessor._tshark_path == '/usr/bin/tshark'
    
    def test_initialization_no_tshark(self):
        """测试初始化时没有找到TShark"""
        with patch.object(TSharkPreprocessor, '_find_tshark_executable', 
                         return_value=None):
            preprocessor = TSharkPreprocessor()
            success = preprocessor.initialize()
            
            assert success is False
            assert preprocessor.is_initialized is False
    
    def test_validate_inputs_success(self, stage_context):
        """测试输入验证成功"""
        preprocessor = TSharkPreprocessor()
        preprocessor._is_initialized = True
        preprocessor._tshark_path = '/usr/bin/tshark'
        
        result = preprocessor.validate_inputs(stage_context)
        
        assert result is True
        assert stage_context.output_file.parent.exists()
        assert stage_context.work_dir.exists()
    
    def test_validate_inputs_no_input_file(self, temp_dir):
        """测试输入文件不存在"""
        context = StageContext(
            input_file=temp_dir / "nonexistent.pcap",
            output_file=temp_dir / "output.pcap",
            work_dir=temp_dir / "work"
        )
        
        preprocessor = TSharkPreprocessor()
        preprocessor._is_initialized = True
        preprocessor._tshark_path = '/usr/bin/tshark'
        
        result = preprocessor.validate_inputs(context)
        
        assert result is False
    
    def test_validate_inputs_empty_input_file(self, temp_dir):
        """测试空输入文件"""
        empty_file = temp_dir / "empty.pcap"
        empty_file.touch()  # 创建空文件
        
        context = StageContext(
            input_file=empty_file,
            output_file=temp_dir / "output.pcap",
            work_dir=temp_dir / "work"
        )
        
        preprocessor = TSharkPreprocessor()
        preprocessor._is_initialized = True
        preprocessor._tshark_path = '/usr/bin/tshark'
        
        result = preprocessor.validate_inputs(context)
        
        assert result is False
    
    def test_validate_inputs_not_initialized(self, stage_context):
        """测试未初始化状态的验证"""
        preprocessor = TSharkPreprocessor()
        # 不调用initialize()
        
        result = preprocessor.validate_inputs(stage_context)
        
        assert result is False
    
    def test_build_tshark_command_basic(self, temp_dir):
        """测试基本TShark命令构建"""
        preprocessor = TSharkPreprocessor()
        preprocessor._tshark_path = '/usr/bin/tshark'
        
        input_file = temp_dir / "input.pcap"
        output_file = temp_dir / "output.pcap"
        
        cmd = preprocessor._build_tshark_command(input_file, output_file)
        
        expected_cmd = [
            '/usr/bin/tshark',
            '-r', str(input_file),
            '-w', str(output_file),
            '-o', 'tcp.desegment_tcp_streams:TRUE',
            '-o', 'tcp.reassemble_out_of_order:TRUE',
            '-o', 'ip.defragment:TRUE',
            '-o', 'ipv6.defragment:TRUE',
            '-C', '1024',
            '-q'
        ]
        
        assert cmd == expected_cmd
    
    def test_build_tshark_command_disabled_features(self, temp_dir):
        """测试禁用功能的命令构建"""
        config = {
            'tshark_enable_reassembly': False,
            'tshark_enable_defragmentation': False,
            'tshark_max_memory_mb': 0
        }
        
        preprocessor = TSharkPreprocessor(config)
        preprocessor._tshark_path = '/usr/bin/tshark'
        
        input_file = temp_dir / "input.pcap"
        output_file = temp_dir / "output.pcap"
        
        cmd = preprocessor._build_tshark_command(input_file, output_file)
        
        expected_cmd = [
            '/usr/bin/tshark',
            '-r', str(input_file),
            '-w', str(output_file),
            '-q'
        ]
        
        assert cmd == expected_cmd
    
    def test_create_temp_file(self, stage_context):
        """测试临时文件创建"""
        preprocessor = TSharkPreprocessor()
        
        temp_file = preprocessor._create_temp_file(stage_context, "test", ".pcap")
        
        assert temp_file.exists()
        assert temp_file.suffix == ".pcap"
        assert temp_file.name.startswith("test_")
        assert temp_file in stage_context.temp_files
    
    def test_parse_tshark_output_basic(self):
        """测试TShark输出解析"""
        preprocessor = TSharkPreprocessor()
        
        stdout = "1000 packets processed\n"
        stderr = "Warning: some warning\nError: some error\n"
        
        stats = preprocessor._parse_tshark_output(stdout, stderr)
        
        assert stats['packets_processed'] == 1000
        assert stats['warnings'] == 1
        assert stats['errors'] == 1
    
    def test_verify_output_success(self, temp_dir):
        """测试输出文件验证成功"""
        output_file = temp_dir / "output.pcap"
        
        # 创建有效的PCAP文件
        with open(output_file, 'wb') as f:
            f.write(b'\xd4\xc3\xb2\xa1')  # PCAP magic number
            f.write(b'\x00' * 20)  # 其他头部数据
        
        preprocessor = TSharkPreprocessor()
        
        # 应该不抛出异常
        preprocessor._verify_output(output_file)
    
    def test_verify_output_no_file(self, temp_dir):
        """测试输出文件不存在"""
        output_file = temp_dir / "nonexistent.pcap"
        
        preprocessor = TSharkPreprocessor()
        
        with pytest.raises(RuntimeError, match="TShark未生成输出文件"):
            preprocessor._verify_output(output_file)
    
    def test_verify_output_empty_file(self, temp_dir):
        """测试空输出文件"""
        output_file = temp_dir / "empty.pcap"
        output_file.touch()  # 创建空文件
        
        preprocessor = TSharkPreprocessor()
        
        with pytest.raises(RuntimeError, match="TShark生成了空的输出文件"):
            preprocessor._verify_output(output_file)
    
    @patch('subprocess.Popen')
    def test_execute_tshark_success(self, mock_popen):
        """测试TShark执行成功"""
        # Mock process
        mock_process = Mock()
        mock_process.communicate.return_value = ("1000 packets processed", "")
        mock_process.returncode = 0
        mock_popen.return_value = mock_process
        
        preprocessor = TSharkPreprocessor()
        
        cmd = ['/usr/bin/tshark', '-r', 'input.pcap', '-w', 'output.pcap', '-q']
        progress_callback = Mock()
        
        stats = preprocessor._execute_tshark(cmd, progress_callback)
        
        assert stats['packets_processed'] == 1000
        assert stats['return_code'] == 0
        assert 'execution_time' in stats
        progress_callback.assert_called_with(0.8)
    
    @patch('subprocess.Popen')
    def test_execute_tshark_failure(self, mock_popen):
        """测试TShark执行失败"""
        # Mock process
        mock_process = Mock()
        mock_process.communicate.return_value = ("", "Error: invalid file")
        mock_process.returncode = 1
        mock_popen.return_value = mock_process
        
        preprocessor = TSharkPreprocessor()
        
        cmd = ['/usr/bin/tshark', '-r', 'input.pcap', '-w', 'output.pcap', '-q']
        progress_callback = Mock()
        
        with pytest.raises(RuntimeError, match="TShark执行失败"):
            preprocessor._execute_tshark(cmd, progress_callback)
    
    @patch('subprocess.Popen')
    def test_execute_tshark_timeout(self, mock_popen):
        """测试TShark执行超时"""
        # Mock process
        mock_process = Mock()
        mock_process.communicate.side_effect = subprocess.TimeoutExpired('tshark', 60)
        mock_process.kill.return_value = None
        mock_process.wait.return_value = None
        mock_popen.return_value = mock_process
        
        preprocessor = TSharkPreprocessor({'tshark_timeout_seconds': 60})
        
        cmd = ['/usr/bin/tshark', '-r', 'input.pcap', '-w', 'output.pcap', '-q']
        progress_callback = Mock()
        
        with pytest.raises(RuntimeError, match="TShark执行超时"):
            preprocessor._execute_tshark(cmd, progress_callback)
    
    def test_get_estimated_duration(self, stage_context):
        """测试处理时间估算"""
        preprocessor = TSharkPreprocessor()
        
        duration = preprocessor.get_estimated_duration(stage_context)
        
        # 应该返回合理的时间估算
        assert duration >= 0.5
        assert isinstance(duration, float)
    
    def test_get_estimated_duration_with_reassembly(self, stage_context):
        """测试启用重组时的时间估算"""
        config = {
            'tshark_enable_reassembly': True,
            'tshark_enable_defragmentation': True
        }
        
        preprocessor = TSharkPreprocessor(config)
        
        duration = preprocessor.get_estimated_duration(stage_context)
        
        # 启用重组应该增加处理时间
        assert duration >= 0.5
    
    def test_get_estimated_duration_nonexistent_file(self, temp_dir):
        """测试不存在文件的时间估算"""
        context = StageContext(
            input_file=temp_dir / "nonexistent.pcap",
            output_file=temp_dir / "output.pcap",
            work_dir=temp_dir / "work"
        )
        
        preprocessor = TSharkPreprocessor()
        
        duration = preprocessor.get_estimated_duration(context)
        
        assert duration == 1.0
    
    def test_get_required_tools(self):
        """测试获取所需工具列表"""
        preprocessor = TSharkPreprocessor()
        
        tools = preprocessor.get_required_tools()
        
        assert tools == ['tshark']
    
    def test_check_tool_availability_available(self):
        """测试工具可用性检查 - 可用"""
        preprocessor = TSharkPreprocessor()
        preprocessor._tshark_path = '/usr/bin/tshark'
        
        with patch('os.path.exists', return_value=True):
            availability = preprocessor.check_tool_availability()
            
            assert availability['tshark'] is True
    
    def test_check_tool_availability_unavailable(self):
        """测试工具可用性检查 - 不可用"""
        preprocessor = TSharkPreprocessor()
        preprocessor._tshark_path = None
        
        availability = preprocessor.check_tool_availability()
        
        assert availability['tshark'] is False
    
    def test_get_description(self):
        """测试获取处理器描述"""
        preprocessor = TSharkPreprocessor()
        
        description = preprocessor.get_description()
        
        assert "TShark预处理器" in description
        assert "TCP流重组" in description
        assert "IP碎片重组" in description
    
    @patch('subprocess.Popen')
    def test_execute_full_pipeline_success(self, mock_popen, stage_context):
        """测试完整执行流程成功"""
        # Setup mocks
        mock_process = Mock()
        mock_process.communicate.return_value = ("1000 packets processed", "")
        mock_process.returncode = 0
        mock_popen.return_value = mock_process
        
        # Mock preprocessor
        preprocessor = TSharkPreprocessor()
        preprocessor._is_initialized = True
        preprocessor._tshark_path = '/usr/bin/tshark'
        
        # Mock temp file operations
        with patch.object(preprocessor, '_create_temp_file') as mock_create_temp:
            temp_file = stage_context.work_dir / "temp_output.pcap"
            stage_context.work_dir.mkdir(parents=True, exist_ok=True)  # 确保目录存在
            temp_file.touch()  # 创建临时文件
            
            # 写入PCAP头
            with open(temp_file, 'wb') as f:
                f.write(b'\xd4\xc3\xb2\xa1')  # PCAP magic
                f.write(b'\x00' * 20)  # 其他数据
            
            mock_create_temp.return_value = temp_file
            
            # Execute
            result = preprocessor.execute(stage_context)
            
            # Verify results
            assert result.success is True
            assert "TShark预处理完成" in result.data['message']
            assert 'output_file' in result.data
            assert result.stats['return_code'] == 0
            assert result.stats['packets_processed'] == 1000
    
    def test_execute_validation_failure(self, stage_context):
        """测试执行时验证失败"""
        preprocessor = TSharkPreprocessor()
        # 不初始化，导致验证失败
        
        result = preprocessor.execute(stage_context)
        
        assert result.success is False
        assert "输入验证失败" in result.error
    
    @patch('subprocess.Popen')
    def test_execute_tshark_failure(self, mock_popen, stage_context):
        """测试执行时TShark失败"""
        # Setup mock for failure
        mock_process = Mock()
        mock_process.communicate.return_value = ("", "Error: cannot read file")
        mock_process.returncode = 1
        mock_popen.return_value = mock_process
        
        preprocessor = TSharkPreprocessor()
        preprocessor._is_initialized = True
        preprocessor._tshark_path = '/usr/bin/tshark'
        
        with patch.object(preprocessor, '_create_temp_file') as mock_create_temp:
            temp_file = stage_context.work_dir / "temp_output.pcap"
            mock_create_temp.return_value = temp_file
            
            result = preprocessor.execute(stage_context)
            
            assert result.success is False
            assert "TShark预处理失败" in result.error
    
    def test_update_stats(self, stage_context):
        """测试统计信息更新"""
        preprocessor = TSharkPreprocessor()
        
        execution_stats = {
            'packets_processed': 1000,
            'execution_time': 2.5,
            'return_code': 0
        }
        
        preprocessor._update_stats(stage_context, execution_stats)
        
        # 检查preprocessor统计
        assert preprocessor.stats['packets_processed'] == 1000
        assert preprocessor.stats['execution_time'] == 2.5
        
        # 检查context统计
        assert 'tshark_preprocessing' in stage_context.stats
        assert stage_context.stats['tshark_preprocessing']['packets_processed'] == 1000


class TestTSharkPreprocessorIntegration:
    """TShark预处理器集成测试"""
    
    @pytest.mark.slow
    @pytest.mark.skipif(not shutil.which('tshark'), reason="TShark not available")
    def test_real_tshark_execution(self, tmp_path):
        """测试真实TShark执行（需要安装TShark）"""
        # 创建一个简单的PCAP文件用于测试
        input_file = tmp_path / "test_input.pcap"
        
        # 创建最小PCAP文件
        with open(input_file, 'wb') as f:
            # PCAP Global Header
            f.write(b'\xd4\xc3\xb2\xa1')  # Magic number
            f.write(b'\x02\x00\x04\x00')  # Version
            f.write(b'\x00\x00\x00\x00')  # Timezone
            f.write(b'\x00\x00\x00\x00')  # Accuracy
            f.write(b'\xff\xff\x00\x00')  # Max length
            f.write(b'\x01\x00\x00\x00')  # Link type
        
        # 创建context
        context = StageContext(
            input_file=input_file,
            output_file=tmp_path / "output.pcap",
            work_dir=tmp_path / "work"
        )
        
        # 创建并初始化preprocessor
        preprocessor = TSharkPreprocessor()
        
        # 如果TShark可用，测试完整流程
        if preprocessor.initialize():
            result = preprocessor.execute(context)
            
            # 由于输入文件没有实际数据包，可能会失败，但不应该崩溃
            assert isinstance(result, ProcessorResult)
            
            # 清理
            context.cleanup_temp_files()
    
    def test_large_file_handling(self, tmp_path):
        """测试大文件处理能力"""
        # 创建一个相对大的文件（模拟）
        large_file = tmp_path / "large_test.pcap"
        
        with open(large_file, 'wb') as f:
            # 写入PCAP头
            f.write(b'\xd4\xc3\xb2\xa1')
            f.write(b'\x02\x00\x04\x00')
            f.write(b'\x00\x00\x00\x00')
            f.write(b'\x00\x00\x00\x00')
            f.write(b'\xff\xff\x00\x00')
            f.write(b'\x01\x00\x00\x00')
            
            # 写入一些数据模拟大文件
            f.write(b'\x00' * (1024 * 1024))  # 1MB数据
        
        context = StageContext(
            input_file=large_file,
            output_file=tmp_path / "output.pcap",
            work_dir=tmp_path / "work"
        )
        
        preprocessor = TSharkPreprocessor()
        
        # 测试时间估算应该合理
        estimated_time = preprocessor.get_estimated_duration(context)
        assert estimated_time >= 0.5  # 至少0.5秒
        assert estimated_time < 60    # 不应该超过1分钟
    
    def test_memory_limit_configuration(self):
        """测试内存限制配置"""
        config = {'tshark_max_memory_mb': 256}
        
        preprocessor = TSharkPreprocessor(config)
        
        assert preprocessor._max_memory_mb == 256
        
        # 测试命令构建包含内存限制
        cmd = preprocessor._build_tshark_command(Path("input.pcap"), Path("output.pcap"))
        
        assert '-C' in cmd
        memory_limit_index = cmd.index('-C')
        assert cmd[memory_limit_index + 1] == '256' 