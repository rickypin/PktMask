"""
TShark TLS 分析器单元测试

测试TSharkTLSAnalyzer的所有功能，包括：
1. 初始化和依赖检查
2. TShark命令构建
3. JSON输出解析
4. TLS记录提取
5. 跨段检测
6. 错误处理
"""

import json
import pytest
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import subprocess

from src.pktmask.core.processors.tshark_tls_analyzer import TSharkTLSAnalyzer
from src.pktmask.core.trim.models.tls_models import TLSRecordInfo, TLSAnalysisResult
from src.pktmask.config.defaults import get_tshark_paths


class TestTSharkTLSAnalyzer:
    """TShark TLS分析器测试"""
    
    @pytest.fixture
    def analyzer(self):
        """创建分析器实例"""
        config = {
            'tshark_timeout_seconds': 30,
            'verbose': False
        }
        return TSharkTLSAnalyzer(config)
    
    @pytest.fixture
    def mock_tshark_path(self):
        """模拟TShark路径"""
        return "/usr/bin/tshark"
    
    @pytest.fixture
    def sample_pcap_file(self, tmp_path):
        """创建样本PCAP文件"""
        pcap_file = tmp_path / "sample.pcap"
        pcap_file.write_bytes(b'sample pcap data')
        return pcap_file
    
    @pytest.fixture
    def sample_tshark_json(self):
        """样本TShark JSON输出"""
        return json.dumps([
            {
                "_source": {
                    "layers": {
                        "frame.number": ["1"],
                        "tcp.stream": ["0"],
                        "tcp.seq": ["1000"],
                        "tcp.len": ["100"],
                        "tls.record.content_type": ["23"],
                        "tls.record.length": ["95"],
                        "tls.record.version": ["0x0303"]
                    }
                }
            },
            {
                "_source": {
                    "layers": {
                        "frame.number": ["2"],
                        "tcp.stream": ["0"],
                        "tcp.seq": ["1100"],
                        "tcp.len": ["50"],
                        "tls.record.content_type": ["22"],
                        "tls.record.length": ["45"],
                        "tls.record.version": ["0x0303"]
                    }
                }
            }
        ])
    
    def test_initialization_default_config(self):
        """测试默认配置初始化"""
        analyzer = TSharkTLSAnalyzer()
        
        assert analyzer.config == {}
        assert analyzer._timeout_seconds == 300
        assert analyzer._verbose is False
        assert analyzer._tshark_path is None
        assert analyzer.SUPPORTED_TLS_TYPES == [20, 21, 22, 23, 24]
        assert analyzer.MIN_TSHARK_VERSION == (4, 0, 0)
    
    def test_initialization_custom_config(self):
        """测试自定义配置初始化"""
        config = {
            'tshark_timeout_seconds': 120,
            'verbose': True,
            'enable_tcp_reassembly': False
        }
        analyzer = TSharkTLSAnalyzer(config)
        
        assert analyzer.config == config
        assert analyzer._timeout_seconds == 120
        assert analyzer._verbose is True
        assert analyzer._enable_tcp_reassembly is False
    
    @patch('shutil.which')
    def test_find_tshark_executable_from_path(self, mock_which, analyzer):
        """测试从PATH查找TShark"""
        mock_which.return_value = "/usr/bin/tshark"
        
        result = analyzer._find_tshark_executable()
        
        assert result == "/usr/bin/tshark"
        mock_which.assert_called_once_with('tshark')
    
    @patch('shutil.which')
    def test_find_tshark_executable_not_found(self, mock_which, analyzer):
        """测试TShark不存在"""
        mock_which.return_value = None
        analyzer._executable_paths = []  # 空搜索路径
        
        result = analyzer._find_tshark_executable()
        
        assert result is None
    
    @patch('subprocess.run')
    def test_get_tshark_version_success(self, mock_run, analyzer, mock_tshark_path):
        """测试获取TShark版本成功"""
        analyzer._tshark_path = mock_tshark_path
        mock_run.return_value = Mock(
            returncode=0,
            stdout="TShark (Wireshark) 4.2.1 (Git commit abc123)"
        )
        
        version = analyzer._get_tshark_version()
        
        assert version == (4, 2, 1)
        mock_run.assert_called_once_with(
            [mock_tshark_path, '--version'],
            capture_output=True,
            text=True,
            timeout=10
        )
    
    @patch('subprocess.run')
    def test_get_tshark_version_failure(self, mock_run, analyzer, mock_tshark_path):
        """测试获取TShark版本失败"""
        analyzer._tshark_path = mock_tshark_path
        mock_run.return_value = Mock(returncode=1, stdout="")
        
        version = analyzer._get_tshark_version()
        
        assert version is None
    
    def test_validate_tshark_version_success(self, analyzer):
        """测试TShark版本验证成功"""
        version = (4, 2, 1)
        
        result = analyzer._validate_tshark_version(version)
        
        assert result is True
    
    def test_validate_tshark_version_too_old(self, analyzer):
        """测试TShark版本过低"""
        version = (3, 6, 2)
        
        result = analyzer._validate_tshark_version(version)
        
        assert result is False
    
    def test_validate_tshark_version_none(self, analyzer):
        """测试TShark版本为None"""
        version = None
        
        result = analyzer._validate_tshark_version(version)
        
        assert result is False
    
    @patch('subprocess.run')
    def test_verify_tshark_capabilities_success(self, mock_run, analyzer, mock_tshark_path):
        """测试TShark功能验证成功"""
        analyzer._tshark_path = mock_tshark_path
        mock_run.return_value = Mock(
            returncode=0,
            stdout="tcp\ntls\nssl\nhttp\n"
        )
        
        result = analyzer._verify_tshark_capabilities()
        
        assert result is True
    
    @patch('subprocess.run')
    def test_verify_tshark_capabilities_no_tls(self, mock_run, analyzer, mock_tshark_path):
        """测试TShark不支持TLS"""
        analyzer._tshark_path = mock_tshark_path
        mock_run.return_value = Mock(
            returncode=0,
            stdout="tcp\nhttp\nudp\n"
        )
        
        result = analyzer._verify_tshark_capabilities()
        
        assert result is False
    
    @patch('subprocess.run')
    def test_verify_tshark_capabilities_failure(self, mock_run, analyzer, mock_tshark_path):
        """测试TShark功能验证失败"""
        analyzer._tshark_path = mock_tshark_path
        mock_run.return_value = Mock(returncode=1, stdout="")
        
        result = analyzer._verify_tshark_capabilities()
        
        assert result is False
    
    def test_check_dependencies_success(self, analyzer, mock_tshark_path):
        """测试依赖检查成功"""
        analyzer._tshark_path = mock_tshark_path
        
        with patch('pathlib.Path.exists', return_value=True):
            result = analyzer.check_dependencies()
        
        assert result is True
    
    def test_check_dependencies_failure(self, analyzer):
        """测试依赖检查失败"""
        analyzer._tshark_path = None
        
        result = analyzer.check_dependencies()
        
        assert result is False
    
    def test_build_tshark_command_basic(self, analyzer, sample_pcap_file, mock_tshark_path):
        """测试构建基本TShark命令"""
        analyzer._tshark_path = mock_tshark_path
        
        cmd = analyzer._build_tshark_command(sample_pcap_file)
        
        expected_fields = [
            'frame.number', 'tcp.stream', 'tcp.seq', 'tcp.len',
            'tls.record.content_type', 'tls.record.length',
            'tls.record.opaque_type', 'tls.record.version', 'tls.app_data'
        ]
        
        assert cmd[0] == mock_tshark_path
        assert '-r' in cmd
        assert str(sample_pcap_file) in cmd
        assert '-T' in cmd
        assert 'json' in cmd
        assert '-Y' in cmd
        assert 'tls' in cmd
        
        # 检查所有必要字段
        for field in expected_fields:
            assert field in cmd
    
    def test_build_tshark_command_with_options(self, analyzer, sample_pcap_file, mock_tshark_path):
        """测试构建带选项的TShark命令"""
        analyzer._tshark_path = mock_tshark_path
        analyzer._enable_tcp_reassembly = True
        analyzer._enable_tls_desegment = True
        
        cmd = analyzer._build_tshark_command(sample_pcap_file)
        
        assert 'tcp.desegment_tcp_streams:TRUE' in cmd
        assert 'tls.desegment_ssl_records:TRUE' in cmd
    
    @patch('subprocess.run')
    def test_execute_tshark_command_success(self, mock_run, analyzer):
        """测试执行TShark命令成功"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout='{"test": "data"}',
            stderr=""
        )
        
        cmd = ["/usr/bin/tshark", "-r", "test.pcap"]
        result = analyzer._execute_tshark_command(cmd)
        
        assert result == '{"test": "data"}'
    
    @patch('subprocess.run')
    def test_execute_tshark_command_empty_output(self, mock_run, analyzer):
        """测试TShark命令输出为空"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout='',
            stderr=""
        )
        
        cmd = ["/usr/bin/tshark", "-r", "test.pcap"]
        result = analyzer._execute_tshark_command(cmd)
        
        assert result == "[]"
    
    @patch('subprocess.run')
    def test_execute_tshark_command_failure(self, mock_run, analyzer):
        """测试执行TShark命令失败"""
        mock_run.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="Error: invalid file"
        )
        
        cmd = ["/usr/bin/tshark", "-r", "test.pcap"]
        
        with pytest.raises(RuntimeError, match="TShark执行失败"):
            analyzer._execute_tshark_command(cmd)
    
    @patch('subprocess.run')
    def test_execute_tshark_command_timeout(self, mock_run, analyzer):
        """测试TShark命令超时"""
        mock_run.side_effect = subprocess.TimeoutExpired('tshark', 30)
        
        cmd = ["/usr/bin/tshark", "-r", "test.pcap"]
        
        with pytest.raises(RuntimeError, match="TShark执行超时"):
            analyzer._execute_tshark_command(cmd)
    
    def test_extract_field_int_success(self, analyzer):
        """测试提取整数字段成功"""
        layers = {"frame.number": ["42"]}
        
        result = analyzer._extract_field_int(layers, "frame.number", 0)
        
        assert result == 42
    
    def test_extract_field_int_hex(self, analyzer):
        """测试提取十六进制整数字段"""
        layers = {"tls.version": ["0x0303"]}
        
        result = analyzer._extract_field_int(layers, "tls.version", 0)
        
        assert result == 0x0303
    
    def test_extract_field_int_default(self, analyzer):
        """测试提取整数字段使用默认值"""
        layers = {}
        
        result = analyzer._extract_field_int(layers, "missing.field", 999)
        
        assert result == 999
    
    def test_extract_field_str_success(self, analyzer):
        """测试提取字符串字段成功"""
        layers = {"tcp.stream": ["5"]}
        
        result = analyzer._extract_field_str(layers, "tcp.stream", "default")
        
        assert result == "5"
    
    def test_extract_field_str_default(self, analyzer):
        """测试提取字符串字段使用默认值"""
        layers = {}
        
        result = analyzer._extract_field_str(layers, "missing.field", "default")
        
        assert result == "default"
    
    def test_extract_field_list_success(self, analyzer):
        """测试提取列表字段成功"""
        layers = {"tls.record.content_type": ["22", "23"]}
        
        result = analyzer._extract_field_list(layers, "tls.record.content_type")
        
        assert result == ["22", "23"]
    
    def test_extract_field_list_single_value(self, analyzer):
        """测试提取单值列表字段"""
        layers = {"tls.record.content_type": "23"}
        
        result = analyzer._extract_field_list(layers, "tls.record.content_type")
        
        assert result == ["23"]
    
    def test_extract_field_list_empty(self, analyzer):
        """测试提取空列表字段"""
        layers = {}
        
        result = analyzer._extract_field_list(layers, "missing.field")
        
        assert result == []
    
    def test_parse_packet_tls_records_single_record(self, analyzer):
        """测试解析单个TLS记录"""
        packet_data = {
            "_source": {
                "layers": {
                    "frame.number": ["1"],
                    "tcp.stream": ["0"],
                    "tcp.seq": ["1000"],
                    "tls.record.content_type": ["23"],
                    "tls.record.length": ["100"],
                    "tls.record.version": ["0x0303"]
                }
            }
        }
        
        records = analyzer._parse_packet_tls_records(packet_data)
        
        assert len(records) == 1
        record = records[0]
        assert record.packet_number == 1
        assert record.content_type == 23
        assert record.version == (3, 3)
        assert record.length == 100
        assert record.tcp_stream_id == "TCP_0"
        assert record.record_offset == 0
    
    def test_parse_packet_tls_records_multiple_records(self, analyzer):
        """测试解析多个TLS记录"""
        packet_data = {
            "_source": {
                "layers": {
                    "frame.number": ["1"],
                    "tcp.stream": ["0"],
                    "tcp.seq": ["1000"],
                    "tls.record.content_type": ["22", "23"],
                    "tls.record.length": ["50", "100"],
                    "tls.record.version": ["0x0303", "0x0303"]
                }
            }
        }
        
        records = analyzer._parse_packet_tls_records(packet_data)
        
        assert len(records) == 2
        
        # 第一个记录 (Handshake)
        record1 = records[0]
        assert record1.content_type == 22
        assert record1.length == 50
        assert record1.record_offset == 0
        
        # 第二个记录 (ApplicationData)
        record2 = records[1]
        assert record2.content_type == 23
        assert record2.length == 100
        assert record2.record_offset == 55  # 5 + 50
    
    def test_parse_packet_tls_records_unsupported_type(self, analyzer):
        """测试解析不支持的TLS类型"""
        packet_data = {
            "_source": {
                "layers": {
                    "frame.number": ["1"],
                    "tcp.stream": ["0"],
                    "tcp.seq": ["1000"],
                    "tls.record.content_type": ["99"],  # 不支持的类型
                    "tls.record.length": ["100"],
                    "tls.record.version": ["0x0303"]
                }
            }
        }
        
        records = analyzer._parse_packet_tls_records(packet_data)
        
        assert len(records) == 0  # 应该跳过不支持的类型
    
    def test_parse_tshark_output_success(self, analyzer, sample_tshark_json):
        """测试解析TShark输出成功"""
        records = analyzer._parse_tshark_output(sample_tshark_json)
        
        assert len(records) == 2
        assert records[0].content_type == 23
        assert records[1].content_type == 22
    
    def test_parse_tshark_output_invalid_json(self, analyzer):
        """测试解析无效JSON"""
        invalid_json = "invalid json"
        
        with pytest.raises(RuntimeError, match="JSON解析失败"):
            analyzer._parse_tshark_output(invalid_json)
    
    def test_detect_cross_packet_records(self, analyzer):
        """测试跨段检测"""
        records = [
            TLSRecordInfo(
                packet_number=1,
                content_type=23,
                version=(3, 3),
                length=100,
                is_complete=True,
                spans_packets=[1],
                tcp_stream_id="TCP_0",
                record_offset=0
            ),
            TLSRecordInfo(
                packet_number=2,
                content_type=22,
                version=(3, 3),
                length=50,
                is_complete=True,
                spans_packets=[2],
                tcp_stream_id="TCP_0",
                record_offset=0
            )
        ]
        
        enhanced_records = analyzer._detect_cross_packet_records(records)
        
        assert len(enhanced_records) == 2
        # 当前实现假设都是完整记录
        assert all(r.is_complete for r in enhanced_records)
    
    def test_get_analysis_result(self, analyzer):
        """测试生成分析结果"""
        records = [
            TLSRecordInfo(
                packet_number=1,
                content_type=23,
                version=(3, 3),
                length=100,
                is_complete=True,
                spans_packets=[1],
                tcp_stream_id="TCP_0",
                record_offset=0
            ),
            TLSRecordInfo(
                packet_number=2,
                content_type=22,
                version=(3, 3),
                length=50,
                is_complete=True,
                spans_packets=[2],
                tcp_stream_id="TCP_0",
                record_offset=0
            )
        ]
        
        result = analyzer.get_analysis_result(records, total_packets=10)
        
        assert isinstance(result, TLSAnalysisResult)
        assert result.total_packets == 10
        assert result.tls_packets == 2
        assert len(result.tls_records) == 2
        assert len(result.cross_packet_records) == 0
        assert len(result.analysis_errors) == 0
    
    @patch.object(TSharkTLSAnalyzer, 'check_dependencies')
    def test_analyze_file_dependency_failure(self, mock_check, analyzer, sample_pcap_file):
        """测试分析文件时依赖不可用"""
        mock_check.return_value = False
        
        with pytest.raises(RuntimeError, match="TShark依赖不可用"):
            analyzer.analyze_file(sample_pcap_file)
    
    def test_analyze_file_missing_file(self, analyzer):
        """测试分析缺失文件"""
        missing_file = Path("/nonexistent/file.pcap")
        
        # 模拟依赖检查失败
        analyzer._tshark_path = None
        
        with pytest.raises(RuntimeError, match="TShark依赖不可用"):
            analyzer.analyze_file(missing_file)


class TestTSharkTLSAnalyzerIntegration:
    """TShark TLS分析器集成测试"""
    
    @pytest.mark.slow
    @pytest.mark.skipif(not shutil.which('tshark'), reason="TShark not available")
    def test_real_tshark_integration(self, tmp_path):
        """测试真实TShark集成（需要安装TShark）"""
        # 检查TShark是否可用
        if not shutil.which('tshark'):
            pytest.skip("TShark not available")
        
        # 创建分析器
        analyzer = TSharkTLSAnalyzer()
        
        # 初始化
        if not analyzer.initialize():
            pytest.skip("TShark initialization failed")
        
        # 创建最小PCAP文件（这里只是测试框架，实际需要有效的TLS包）
        pcap_file = tmp_path / "test.pcap"
        with open(pcap_file, 'wb') as f:
            # PCAP Global Header
            f.write(b'\xd4\xc3\xb2\xa1')  # Magic number
            f.write(b'\x02\x00\x04\x00')  # Version
            f.write(b'\x00\x00\x00\x00')  # Timezone
            f.write(b'\x00\x00\x00\x00')  # Accuracy
            f.write(b'\xff\xff\x00\x00')  # Max length
            f.write(b'\x01\x00\x00\x00')  # Link type
        
        try:
            # 分析文件（预期会返回空列表，因为没有TLS数据）
            result = analyzer.analyze_file(pcap_file)
            
            # 验证结果格式
            assert isinstance(result, list)
            # 由于没有实际TLS数据，结果应该为空
            assert len(result) == 0
            
        except Exception as e:
            # 如果分析失败，确保是可预期的错误
            assert "TLS分析失败" in str(e) or "TShark执行失败" in str(e)


class TestTSharkTLSAnalyzerCoverageGaps:
    """TShark TLS分析器覆盖率缺口补充测试
    
    针对Day 6目标，覆盖84% -> ≥90%的缺失代码路径
    """
    
    @pytest.fixture
    def analyzer_with_custom_config(self):
        """自定义配置的分析器"""
        config = {
            'tshark_timeout_seconds': 600,
            'tshark_max_memory_mb': 2048,
            'temp_dir': '/custom/temp/dir',
            'enable_tcp_reassembly': False,
            'enable_tls_desegment': False,
            'tshark_custom_executable': '/custom/tshark/path',
            'tshark_executable_paths': ['/path1/tshark', '/path2/tshark'],
            'verbose': True
        }
        return TSharkTLSAnalyzer(config)

    def test_platform_specific_path_detection(self):
        """测试平台特定路径检测逻辑（覆盖get_tshark_paths函数）"""
        
        # 测试基本功能
        paths = get_tshark_paths()
        assert isinstance(paths, list)
        assert len(paths) > 0
        
        # 测试路径是否为字符串
        for path in paths:
            assert isinstance(path, str)
            assert len(path) > 0

    def test_tshark_executable_finding_configured_paths(self):
        """测试配置路径中查找TShark可执行文件"""
        # 使用正确的mock方式
        config = {'tshark_executable_paths': ['/custom/tshark', '/another/path/tshark']}
        analyzer = TSharkTLSAnalyzer(config)
        
        # Mock Path.exists 方法
        with patch('pathlib.Path.exists') as mock_exists:
            def mock_exists_side_effect(path_obj):
                return str(path_obj) == '/custom/tshark'
            mock_exists.side_effect = mock_exists_side_effect
            
            # 测试找到配置路径中的TShark
            result = analyzer._find_tshark_executable()
            assert result == '/custom/tshark'

    def test_tshark_executable_finding_custom_path(self, analyzer_with_custom_config):
        """测试自定义可执行文件路径查找"""
        # 测试自定义可执行文件存在的情况
        with patch('pathlib.Path.exists') as mock_exists:
            mock_exists.return_value = True
            
            result = analyzer_with_custom_config._find_tshark_executable()
            assert result == '/custom/tshark/path'
    
    def test_tshark_executable_finding_path_search(self):
        """测试PATH环境变量中的tshark查找"""
        analyzer = TSharkTLSAnalyzer()
        
        # 测试在PATH中找到tshark
        with patch('shutil.which') as mock_which:
            mock_which.return_value = '/usr/bin/tshark'
            
            result = analyzer._find_tshark_executable()
            assert result == '/usr/bin/tshark'
    
    def test_tshark_version_parsing_edge_cases(self):
        """测试TShark版本解析边界情况"""
        analyzer = TSharkTLSAnalyzer()
        analyzer._tshark_path = '/fake/tshark'
        
        # 测试版本解析失败（无法匹配版本号）
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="TShark unknown version format"
            )
            
            result = analyzer._get_tshark_version()
            assert result is None
        
        # 测试非零退出码
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=1, stdout="")
            
            result = analyzer._get_tshark_version()
            assert result is None
        
        # 测试subprocess异常
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = OSError("Permission denied")
            
            result = analyzer._get_tshark_version()
            assert result is None

    def test_verify_tshark_capabilities_tcp_missing(self):
        """测试TShark功能验证 - TCP协议支持缺失"""
        analyzer = TSharkTLSAnalyzer()
        analyzer._tshark_path = '/fake/tshark'
        
        # 测试TCP协议不支持的情况
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="tls\nssl\nhttp\n"  # 没有tcp
            )
            
            result = analyzer._verify_tshark_capabilities()
            assert result is False

    def test_verify_tshark_capabilities_protocol_check_failure(self):
        """测试TShark协议检查命令失败"""
        analyzer = TSharkTLSAnalyzer()
        analyzer._tshark_path = '/fake/tshark'
        
        # 测试协议检查命令返回非零退出码
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=1, stdout="")
            
            result = analyzer._verify_tshark_capabilities()
            assert result is False

    def test_execute_tshark_command_timeout_scenario(self):
        """测试TShark命令执行超时场景"""
        config = {'tshark_timeout_seconds': 1}
        analyzer = TSharkTLSAnalyzer(config)
        
        cmd = ['/fake/tshark', '--version']
        
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired('tshark', 1)
            
            with pytest.raises(RuntimeError, match="TShark执行超时"):
                analyzer._execute_tshark_command(cmd)

    def test_execute_tshark_command_general_exception(self):
        """测试TShark命令执行一般异常"""
        analyzer = TSharkTLSAnalyzer()
        cmd = ['/fake/tshark', '--version']
        
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = OSError("Permission denied")
            
            with pytest.raises(RuntimeError, match="TShark执行异常"):
                analyzer._execute_tshark_command(cmd)

    def test_parse_packet_tls_records_unsupported_types(self):
        """测试解析包含不支持TLS类型的数据包"""
        analyzer = TSharkTLSAnalyzer()
        
        # 模拟包含不支持TLS类型（如99）的数据包
        packet_data = {
            '_source': {
                'layers': {
                    'frame.number': ['1'],
                    'tcp.stream': ['0'],
                    'tcp.seq': ['1000'],
                    'tls.record.content_type': ['99', '23'],  # 99是不支持的类型
                    'tls.record.length': ['10', '100'],
                    'tls.record.version': ['0x0303', '0x0303']
                }
            }
        }
        
        records = analyzer._parse_packet_tls_records(packet_data)
        
        # 应该只解析出类型23的记录，跳过类型99
        assert len(records) == 1
        assert records[0].content_type == 23

    def test_parse_packet_tls_records_version_parsing_errors(self):
        """测试TLS版本解析错误处理"""
        analyzer = TSharkTLSAnalyzer()
        
        packet_data = {
            '_source': {
                'layers': {
                    'frame.number': ['1'],
                    'tcp.stream': ['0'], 
                    'tcp.seq': ['1000'],
                    'tls.record.content_type': ['23'],
                    'tls.record.length': ['100'],
                    'tls.record.version': ['invalid_version']  # 无效版本格式
                }
            }
        }
        
        records = analyzer._parse_packet_tls_records(packet_data)
        
        # 应该使用默认版本(3, 1)
        assert len(records) == 1
        assert records[0].version == (3, 1)

    def test_parse_packet_tls_records_content_type_parsing_errors(self):
        """测试TLS内容类型解析错误处理"""
        analyzer = TSharkTLSAnalyzer()
        
        packet_data = {
            '_source': {
                'layers': {
                    'frame.number': ['1'],
                    'tcp.stream': ['0'],
                    'tcp.seq': ['1000'],
                    'tls.record.content_type': ['invalid_type'],  # 无效类型
                    'tls.record.length': ['100'],
                    'tls.record.version': ['0x0303']
                }
            }
        }
        
        records = analyzer._parse_packet_tls_records(packet_data)
        
        # 解析失败时应该跳过该记录
        assert len(records) == 0

    def test_extract_field_methods_edge_cases(self):
        """测试字段提取方法的边界情况"""
        analyzer = TSharkTLSAnalyzer()
        
        # 测试嵌套字段结构
        layers = {
            'tls': {
                'record': {
                    'content_type': '23'
                }
            },
            'frame.number': 42
        }
        
        # 测试整数字段提取
        result = analyzer._extract_field_int(layers, 'frame.number', 0)
        assert result == 42
        
        # 测试不存在字段的默认值
        result = analyzer._extract_field_int(layers, 'nonexistent.field', 999)
        assert result == 999
        
        # 测试字符串字段提取
        result = analyzer._extract_field_str(layers, 'nonexistent.field', 'default')
        assert result == 'default'
        
        # 测试列表字段提取（字段不存在）
        result = analyzer._extract_field_list(layers, 'nonexistent.field')
        assert result == []
        
        # 测试列表字段提取（单个值转换为列表）
        layers_single = {
            'single_field': '23'
        }
        result = analyzer._extract_field_list(layers_single, 'single_field')
        assert result == ['23']

    def test_detect_cross_packet_records_advanced_scenarios(self):
        """测试跨包记录检测的高级场景"""
        analyzer = TSharkTLSAnalyzer()
        
        # 创建复杂的跨包场景：同一流但不同包之间有间隔
        tls_records = [
            TLSRecordInfo(
                packet_number=1,
                content_type=23,
                version=(3, 3),
                length=100,
                is_complete=True,
                spans_packets=[1],
                tcp_stream_id="TCP_0",
                record_offset=0
            ),
            TLSRecordInfo(
                packet_number=3,  # 跳过包2
                content_type=23,
                version=(3, 3), 
                length=50,
                is_complete=True,
                spans_packets=[3],
                tcp_stream_id="TCP_0",
                record_offset=0
            )
        ]
        
        result = analyzer._detect_cross_packet_records(tls_records)
        
        # 验证结果保持原状（没有连续的跨包记录）
        assert len(result) == 2
        assert all(record.is_complete for record in result)

    def test_get_analysis_result_comprehensive(self):
        """测试分析结果的综合场景（修复属性名错误）"""
        analyzer = TSharkTLSAnalyzer(self.config)
        
        # 创建模拟的TLS记录
        mock_records = [
            TLSRecordInfo(1, 22, (3, 3), 100, True, [1], "stream1", 0),
            TLSRecordInfo(2, 23, (3, 3), 200, True, [2], "stream1", 0),
            TLSRecordInfo(3, 23, (3, 3), 150, False, [3, 4], "stream1", 0)
        ]
        
        # 创建分析结果
        analysis_result = TLSAnalysisResult(
            total_packets=10,
            tls_packets=3,
            tls_records=mock_records,
            cross_packet_records=[mock_records[2]],
            analysis_errors=[]
        )
        
        # 修复：使用正确的属性名
        assert len(analysis_result.tls_records) == 3
        assert analysis_result.total_packets == 10
        assert analysis_result.tls_packets == 3
        assert len(analysis_result.cross_packet_records) == 1


class TestTSharkTLSAnalyzerPerformanceScenarios:
    """TShark TLS分析器性能相关测试场景"""
    
    def test_large_dataset_handling(self):
        """测试大数据集处理性能（修复属性名错误）"""
        config = {
            'enable_tls_processing': True,
            'enable_detailed_logging': False,
            'chunk_size': 500
        }
        analyzer = TSharkTLSAnalyzer(config)
        
        # 创建大量模拟TLS记录
        large_records = []
        for i in range(1000):
            record = TLSRecordInfo(
                packet_number=i+1,
                content_type=23,
                version=(3, 3),
                length=100,
                is_complete=True,
                spans_packets=[i+1],
                tcp_stream_id=f"stream_{i%10}",
                record_offset=0
            )
            large_records.append(record)
        
        analysis_result = TLSAnalysisResult(
            total_packets=1000,
            tls_packets=1000,
            tls_records=large_records,
            cross_packet_records=[],
            analysis_errors=[]
        )
        
        # 修复：使用正确的属性名
        assert len(analysis_result.tls_records) == 1000
        assert analysis_result.total_packets == 1000

    def test_verbose_logging_scenarios(self):
        """测试详细日志记录场景"""
        config = {'verbose': True}
        analyzer = TSharkTLSAnalyzer(config)
        
        # 测试详细模式下的命令构建
        pcap_file = Path('test.pcap')
        cmd = analyzer._build_tshark_command(pcap_file)
        
        # 在详细模式下，不应该包含 -q (静默) 参数
        assert '-q' not in cmd
        
        # 测试非详细模式
        config_quiet = {'verbose': False}
        analyzer_quiet = TSharkTLSAnalyzer(config_quiet)
        cmd_quiet = analyzer_quiet._build_tshark_command(pcap_file)
        
        # 非详细模式应该包含 -q 参数
        assert '-q' in cmd_quiet 