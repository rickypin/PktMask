#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Phase 2.2 PyShark分析器集成测试

验证PyShark分析器与现有系统的集成效果：
1. 与TShark预处理器的数据流传递
2. 多阶段执行器的协调工作  
3. 事件系统集成验证
4. 错误处理和资源管理
5. 性能和内存使用
"""

import pytest
import tempfile
import shutil
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from pktmask.core.trim.multi_stage_executor import MultiStageExecutor
from pktmask.core.trim.stages.tshark_preprocessor import TSharkPreprocessor
from pktmask.core.trim.stages.pyshark_analyzer import PySharkAnalyzer
from pktmask.core.trim.stages.base_stage import StageContext
from pktmask.core.trim.models.mask_table import StreamMaskTable
from pktmask.core.events import PipelineEvents
from pktmask.config import AppConfig


class TestPhase22Integration:
    """Phase 2.2 PyShark分析器集成测试类"""

    def setup_method(self):
        """测试设置"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.test_samples_dir = Path(__file__).parent.parent / "samples"
        
        # 创建基础文件和目录
        self.input_file = self.temp_dir / "input.pcap"
        self.output_file = self.temp_dir / "output.pcap"
        self.work_dir = self.temp_dir / "work"
        self.work_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建一个模拟的PCAP文件
        self._create_mock_pcap_file()
        
        # 事件记录器
        self.events_received = []
        
    def teardown_method(self):
        """测试清理"""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def _create_mock_pcap_file(self):
        """创建模拟PCAP文件"""
        # 创建一个最小的PCAP文件头
        pcap_header = (
            b'\xd4\xc3\xb2\xa1'  # Magic number (Little Endian)
            b'\x02\x00\x04\x00'  # Version major/minor
            b'\x00\x00\x00\x00'  # Timezone offset
            b'\x00\x00\x00\x00'  # Timestamp accuracy
            b'\xff\xff\x00\x00'  # Max packet length
            b'\x01\x00\x00\x00'  # Data link type (Ethernet)
        )
        self.input_file.write_bytes(pcap_header)

    def _event_callback(self, event_type, data):
        """事件回调记录器"""
        self.events_received.append({
            'type': event_type,
            'data': data,
            'timestamp': time.time()
        })

    def test_phase2_1_to_phase2_2_data_flow(self):
        """测试1: Phase 2.1 到 Phase 2.2 的数据流传递"""
        print("\n=== 测试1: TShark预处理器到PyShark分析器的数据流传递 ===")
        
        # 模拟TShark预处理器的输出
        tshark_output = self.work_dir / "tshark_output.pcap"
        tshark_output.write_bytes(self.input_file.read_bytes())
        
        # 创建Stage上下文
        context = StageContext(
            input_file=self.input_file,
            output_file=self.output_file,
            work_dir=self.work_dir
        )
        
        # 设置TShark预处理器的输出作为PyShark分析器的输入
        context.tshark_output = str(tshark_output)
        
        # 创建PyShark分析器
        analyzer_config = {
            'analyze_http': True,
            'analyze_tls': True,
            'analyze_tcp': True,
            'analyze_udp': True
        }
        
        with patch('pktmask.core.trim.stages.pyshark_analyzer.pyshark') as mock_pyshark:
            # 模拟PyShark
            mock_packets = [
                self._create_mock_tcp_packet(1, has_http=True),
                self._create_mock_tcp_packet(2, has_tls=True),
                self._create_mock_udp_packet(3)
            ]
            mock_cap = Mock()
            mock_cap.__iter__ = Mock(return_value=iter(mock_packets))
            mock_cap.close = Mock()
            mock_pyshark.FileCapture.return_value = mock_cap
            
            # 创建并初始化分析器
            analyzer = PySharkAnalyzer(analyzer_config)
            analyzer.initialize()
            
            # 验证输入验证
            assert analyzer.validate_inputs(context)
            
            # 执行分析
            result = analyzer.execute(context)
            
            # 验证执行结果
            assert result.success
            assert "PyShark分析完成" in result.data
            
            # 验证数据流传递
            assert context.mask_table is not None
            assert isinstance(context.mask_table, StreamMaskTable)
            assert context.pyshark_results is not None
            assert 'streams' in context.pyshark_results
            assert 'packet_analyses' in context.pyshark_results
            assert 'statistics' in context.pyshark_results
            
            # 验证PyShark被正确调用
            mock_pyshark.FileCapture.assert_called_once_with(
                str(tshark_output),
                keep_packets=False,
                use_json=True,
                include_raw=False
            )
        
        print("✅ 数据流传递验证通过")

    def test_multi_stage_executor_coordination(self):
        """测试2: 多阶段执行器协调工作"""
        print("\n=== 测试2: 多阶段执行器协调工作 ===")
        
        # 创建多阶段执行器
        executor = MultiStageExecutor(
            work_dir=self.work_dir,
            event_callback=self._event_callback
        )
        
        # 配置TShark预处理器（模拟）
        tshark_config = {
            'tshark_executable': '/usr/bin/tshark',  # 模拟路径
            'tshark_enable_reassembly': True,
            'temp_dir': str(self.temp_dir)
        }
        
        # 配置PyShark分析器
        analyzer_config = {
            'analyze_http': True,
            'analyze_tls': True,
            'max_packets_per_batch': 500
        }
        
        with patch('shutil.which', return_value='/usr/bin/tshark'), \
             patch('subprocess.run') as mock_subprocess, \
             patch('subprocess.Popen') as mock_popen, \
             patch('pktmask.core.trim.stages.pyshark_analyzer.pyshark') as mock_pyshark:
            
            # 模拟TShark命令执行
            def mock_subprocess_run(cmd, *args, **kwargs):
                if '--version' in cmd or 'TShark' in str(cmd):
                    return Mock(returncode=0, stdout="TShark 3.0.0\n")
                elif any('-o' in arg for arg in cmd):
                    return Mock(returncode=0, stdout="tcp.desegment\nip.defragment")
                else:
                    # 实际执行时，模拟成功并创建输出文件
                    output_file = None
                    for i, arg in enumerate(cmd):
                        if arg == '-w' and i + 1 < len(cmd):
                            output_file = cmd[i + 1]
                            break
                    if output_file:
                         # 确保输出文件有足够的内容（复制输入文件+额外数据）
                         input_data = self.input_file.read_bytes()
                         if len(input_data) < 100:  # 如果输入文件太小，增加一些数据
                             extra_data = b'\x00' * (100 - len(input_data))
                             Path(output_file).write_bytes(input_data + extra_data)
                         else:
                             Path(output_file).write_bytes(input_data)
                    return Mock(returncode=0, stdout="", stderr="")
            
            mock_subprocess.side_effect = mock_subprocess_run
            
            # 模拟Popen（TShark预处理器可能使用）
            def mock_popen_init(*args, **kwargs):
                mock_process = Mock()
                mock_process.communicate.return_value = ("", "")
                mock_process.returncode = 0
                mock_process.wait.return_value = 0
                return mock_process
            
            mock_popen.side_effect = mock_popen_init
            
            # 模拟PyShark
            mock_packets = [self._create_mock_tcp_packet(i, has_http=(i%2==0)) for i in range(1, 6)]
            mock_cap = Mock()
            mock_cap.__iter__ = Mock(return_value=iter(mock_packets))
            mock_cap.close = Mock()
            mock_pyshark.FileCapture.return_value = mock_cap
            
            # 创建Stage
            preprocessor = TSharkPreprocessor(tshark_config)
            analyzer = PySharkAnalyzer(analyzer_config)
            
            # 注册Stage到执行器
            executor.register_stage(preprocessor)
            executor.register_stage(analyzer)
            
            # 初始化Stage
            assert preprocessor.initialize()
            assert analyzer.initialize()
            
            # 验证Stage注册
            assert len(executor.stages) == 2
            assert executor.stages[0].name == "TShark预处理器"
            assert executor.stages[1].name == "PyShark分析器"
            
            # 执行管道
            result = executor.execute_pipeline(self.input_file, self.output_file)
            
            # 验证执行结果
            assert result.success
            assert result.total_stages == 2
            assert len(result.stage_results) == 2
            
            # 验证Stage执行顺序
            assert result.stage_results[0]['name'] == "TShark预处理器"
            assert result.stage_results[1]['name'] == "PyShark分析器"
            assert all(stage['success'] for stage in result.stage_results)
            
        print("✅ 多阶段执行器协调工作验证通过")

    def test_event_system_integration(self):
        """测试3: 事件系统集成验证"""
        print("\n=== 测试3: 事件系统集成验证 ===")
        
        # 创建带事件回调的执行器
        executor = MultiStageExecutor(
            work_dir=self.work_dir,
            event_callback=self._event_callback
        )
        
        with patch('pktmask.core.trim.stages.pyshark_analyzer.pyshark') as mock_pyshark:
            # 模拟PyShark
            mock_packets = [self._create_mock_tcp_packet(i) for i in range(1, 4)]
            mock_cap = Mock()
            mock_cap.__iter__ = Mock(return_value=iter(mock_packets))
            mock_cap.close = Mock()
            mock_pyshark.FileCapture.return_value = mock_cap
            
            # 创建并注册PyShark分析器
            analyzer = PySharkAnalyzer({'analyze_tcp': True})
            analyzer.initialize()
            executor.register_stage(analyzer)
            
            # 手动创建上下文并设置TShark输出
            context = StageContext(
                input_file=self.input_file,
                output_file=self.output_file,
                work_dir=self.work_dir
            )
            context.tshark_output = str(self.input_file)
            
            # 执行单个Stage
            stage_result = executor._execute_stage(analyzer, context, 0)
            
            # 验证事件发送
            assert len(self.events_received) >= 2
            
            # 检查事件类型
            event_types = [event['type'] for event in self.events_received]
            assert PipelineEvents.STEP_START in event_types
            assert PipelineEvents.STEP_END in event_types
            
            # 验证Stage开始事件
            start_events = [e for e in self.events_received if e['type'] == PipelineEvents.STEP_START]
            assert len(start_events) >= 1
            assert start_events[0]['data']['stage_name'] == 'PyShark分析器'
            
            # 验证Stage结束事件
            end_events = [e for e in self.events_received if e['type'] == PipelineEvents.STEP_END]
            assert len(end_events) >= 1
            assert end_events[0]['data']['stage_name'] == 'PyShark分析器'
            assert end_events[0]['data']['success'] is True
            
        print("✅ 事件系统集成验证通过")

    def test_error_handling_and_resource_management(self):
        """测试4: 错误处理和资源管理"""
        print("\n=== 测试4: 错误处理和资源管理 ===")
        
        # 测试输入验证失败
        analyzer = PySharkAnalyzer()
        analyzer.initialize()
        
        # 创建无效上下文（没有TShark输出）
        invalid_context = StageContext(
            input_file=self.input_file,
            output_file=self.output_file,
            work_dir=self.work_dir
        )
        
        # 验证输入验证失败
        assert not analyzer.validate_inputs(invalid_context)
        
        # 测试执行失败
        result = analyzer.execute(invalid_context)
        assert not result.success
        assert "PyShark分析失败" in result.error
        
        # 测试PyShark打开文件失败
        valid_context = StageContext(
            input_file=self.input_file,
            output_file=self.output_file,
            work_dir=self.work_dir
        )
        valid_context.tshark_output = str(self.input_file)
        
        with patch('pktmask.core.trim.stages.pyshark_analyzer.pyshark') as mock_pyshark:
            mock_pyshark.FileCapture.side_effect = Exception("文件打开失败")
            
            result = analyzer.execute(valid_context)
            assert not result.success
            assert "PyShark分析失败" in result.error
        
        # 测试资源清理
        context = StageContext(
            input_file=self.input_file,
            output_file=self.output_file,
            work_dir=self.work_dir
        )
        
        # 创建临时文件
        temp_file = context.create_temp_file("test", ".tmp")
        assert temp_file.exists()
        assert len(context.temp_files) == 1
        
        # 清理资源
        analyzer.cleanup(context)
        context.cleanup()
        
        # 验证临时文件被清理
        assert not temp_file.exists()
        assert len(context.temp_files) == 0
        
        print("✅ 错误处理和资源管理验证通过")

    def test_performance_and_memory_usage(self):
        """测试5: 性能和内存使用"""
        print("\n=== 测试5: 性能和内存使用 ===")
        
        analyzer_config = {
            'max_packets_per_batch': 100,
            'memory_cleanup_interval': 500,
            'analysis_timeout_seconds': 30
        }
        
        with patch('pktmask.core.trim.stages.pyshark_analyzer.pyshark') as mock_pyshark:
            # 模拟大量数据包
            mock_packets = [
                self._create_mock_tcp_packet(i, has_http=(i%3==0), has_tls=(i%5==0)) 
                for i in range(1, 1001)  # 1000个数据包
            ]
            mock_cap = Mock()
            mock_cap.__iter__ = Mock(return_value=iter(mock_packets))
            mock_cap.close = Mock()
            mock_pyshark.FileCapture.return_value = mock_cap
            
            # 创建分析器
            analyzer = PySharkAnalyzer(analyzer_config)
            analyzer.initialize()
            
            # 创建上下文
            context = StageContext(
                input_file=self.input_file,
                output_file=self.output_file,
                work_dir=self.work_dir
            )
            context.tshark_output = str(self.input_file)
            
            # 测量执行时间
            start_time = time.time()
            result = analyzer.execute(context)
            execution_time = time.time() - start_time
            
            # 验证性能
            assert result.success
            assert execution_time < 60.0  # 应该在60秒内完成
            
            # 验证配置应用
            assert analyzer._max_packets_per_batch == 100
            assert analyzer._memory_cleanup_interval == 500
            assert analyzer._timeout_seconds == 30
            
            # 验证处理结果
            assert context.mask_table is not None
            assert context.pyshark_results is not None
            
            # 验证统计信息
            stats = context.pyshark_results['statistics']
            assert stats['total_packets'] == 1000
            assert 'protocol_distribution' in stats
            assert 'application_distribution' in stats
            
        print(f"✅ 性能和内存使用验证通过 - 执行时间: {execution_time:.2f}s")

    def test_configuration_system_integration(self):
        """测试6: 配置系统集成"""
        print("\n=== 测试6: 配置系统集成 ===")
        
        # 测试与AppConfig的集成
        from pktmask.config import get_app_config
        app_config = get_app_config()
        
        # 模拟配置参数
        trim_config = {
            'analyze_http': True,
            'analyze_tls': True,
            'http_keep_headers': True,
            'tls_keep_handshake': True,
            'max_packets_per_batch': 800,
            'memory_cleanup_interval': 2000
        }
        
        # 创建分析器
        analyzer = PySharkAnalyzer(trim_config)
        
        # 验证配置读取
        assert analyzer.get_config_value('analyze_http') == True
        assert analyzer.get_config_value('analyze_tls') == True
        assert analyzer.get_config_value('http_keep_headers') == True
        assert analyzer.get_config_value('tls_keep_handshake') == True
        assert analyzer.get_config_value('max_packets_per_batch') == 800
        assert analyzer.get_config_value('memory_cleanup_interval') == 2000
        
        # 验证默认值
        assert analyzer.get_config_value('nonexistent_param', 'default') == 'default'
        
        # 验证初始化成功
        assert analyzer.initialize()
        
        print("✅ 配置系统集成验证通过")

    # Helper methods for creating mock objects
    
    def _create_mock_tcp_packet(self, number, has_http=False, has_tls=False):
        """创建模拟TCP数据包"""
        packet = Mock()
        packet.number = number
        packet.sniff_timestamp = time.time()
        
        # TCP层
        packet.tcp = Mock()
        packet.tcp.srcport = 80 if has_http else (443 if has_tls else 12345)
        packet.tcp.dstport = 54321
        packet.tcp.seq = 1000 + number * 100
        packet.tcp.len = 100
        packet.tcp.hdr_len = 20
        
        # IP层
        packet.ip = Mock()
        packet.ip.src = "192.168.1.1"
        packet.ip.dst = "192.168.1.100"
        
        # 应用层
        if has_http:
            packet.http = Mock()
            packet.http.request_method = "GET"
            packet.http.response_code = None
            packet.http.host = "example.com"
        
        if has_tls:
            packet.tls = Mock()
            packet.tls.record = Mock()
            packet.tls.record.content_type = 22  # Handshake
            packet.tls.record.length = 100
        
        return packet
    
    def _create_mock_udp_packet(self, number):
        """创建模拟UDP数据包"""
        packet = Mock()
        packet.number = number
        packet.sniff_timestamp = time.time()
        
        # UDP层
        packet.udp = Mock()
        packet.udp.srcport = 53  # DNS
        packet.udp.dstport = 54321
        packet.udp.length = 64
        
        # IP层
        packet.ip = Mock()
        packet.ip.src = "192.168.1.1"
        packet.ip.dst = "192.168.1.100"
        
        return packet


if __name__ == "__main__":
    # 运行集成测试
    test_instance = TestPhase22Integration()
    test_instance.setup_method()
    
    try:
        print("Phase 2.2 PyShark分析器集成测试开始...")
        
        test_instance.test_phase2_1_to_phase2_2_data_flow()
        test_instance.test_multi_stage_executor_coordination()
        test_instance.test_event_system_integration()
        test_instance.test_error_handling_and_resource_management()
        test_instance.test_performance_and_memory_usage()
        test_instance.test_configuration_system_integration()
        
        print("\n🎉 Phase 2.2 集成测试全部通过！")
        
    except Exception as e:
        print(f"\n❌ 集成测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        test_instance.teardown_method() 