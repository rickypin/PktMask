"""
PktMask 测试配置和共享fixture
"""
import os
import sys
import tempfile
import shutil
from pathlib import Path
from typing import Generator, Dict, Any
import pytest
from scapy.all import Ether, IP, TCP, Dot1Q, Raw, wrpcap
from unittest.mock import Mock, MagicMock, patch

# 设置测试环境
os.environ['PKTMASK_TEST_MODE'] = 'true'
os.environ['PKTMASK_HEADLESS'] = 'true'
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

# 添加src到Python路径
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# 导入本地模块
try:
    from pktmask.config.settings import AppConfig
    from pktmask.core.encapsulation.types import EncapsulationType, LayerInfo
    from pktmask.infrastructure.logging.logger import get_logger
except ImportError:
    # 如果直接导入失败，尝试从pktmask导入
    try:
        from pktmask.config.settings import AppConfig
        from pktmask.core.encapsulation.types import EncapsulationType, LayerInfo
        from pktmask.infrastructure.logging.logger import get_logger
    except ImportError as e:
        # 重新抛出异常，以便显示根本原因
        raise e


@pytest.fixture(scope="session")
def temp_dir() -> Generator[Path, None, None]:
    """创建临时测试目录"""
    temp_path = Path(tempfile.mkdtemp(prefix="pktmask_test_"))
    try:
        yield temp_path
    finally:
        shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def test_data_dir() -> Path:
    """返回测试数据目录路径"""
    return Path(__file__).parent / "data"


@pytest.fixture
def sample_pcap_files(test_data_dir: Path) -> Dict[str, Path]:
    """提供样本PCAP文件路径"""
    samples_dir = test_data_dir / "samples"
    return {
        "small": samples_dir / "small_sample.pcap",
        "medium": samples_dir / "medium_sample.pcap", 
        "large": samples_dir / "large_sample.pcap"
    }


@pytest.fixture
def default_config() -> AppConfig:
    """提供默认配置对象"""
    return AppConfig.default()


@pytest.fixture
def test_config(temp_dir: Path) -> AppConfig:
    """提供测试专用配置"""
    config = AppConfig.default()
    config.ui.last_output_dir = str(temp_dir / "output")
    return config


@pytest.fixture  
def processor_config():
    """提供处理器配置"""
    from pktmask.core.processors.base_processor import ProcessorConfig
    return ProcessorConfig(enabled=True, name="test_processor", priority=1)


@pytest.fixture
def qapp_args():
    """为pytest-qt提供QApplication参数"""
    return ['-platform', 'offscreen']


@pytest.fixture
def qtbot_no_show(qtbot):
    """修改qtbot不自动显示窗口"""
    # 覆盖addWidget方法，不调用show()
    original_add_widget = qtbot.addWidget
    
    def add_widget_no_show(widget, **kwargs):
        # 调用原始方法但设置show=False
        return original_add_widget(widget, show=False, **kwargs)
    
    qtbot.addWidget = add_widget_no_show
    return qtbot


@pytest.fixture
def mock_gui_environment(monkeypatch):
    """模拟GUI测试环境"""
    # 设置无头模式环境变量
    monkeypatch.setenv('PKTMASK_TEST_MODE', 'true')
    monkeypatch.setenv('PKTMASK_HEADLESS', 'true')
    monkeypatch.setenv('QT_QPA_PLATFORM', 'offscreen')
    
    # Mock QApplication以避免真正创建GUI
    mock_app = Mock()
    mock_app.instance.return_value = None
    mock_app.exec.return_value = 0
    
    with patch('PyQt6.QtWidgets.QApplication', return_value=mock_app):
        yield mock_app


class TestDataGenerator:
    """测试数据生成器"""
    
    @staticmethod
    def create_test_pcap(file_path: Path, packet_count: int = 10) -> Path:
        """创建测试用的PCAP文件（模拟）"""
        # 这里可以实现真实的PCAP文件生成
        # 暂时创建空文件作为占位符
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.touch()
        return file_path
    
    @staticmethod
    def create_config_file(file_path: Path, config_data: Dict[str, Any]) -> Path:
        """创建测试配置文件"""
        import json
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2)
        return file_path


@pytest.fixture
def test_data_generator() -> TestDataGenerator:
    """提供测试数据生成器"""
    return TestDataGenerator()


def pytest_configure(config):
    """pytest配置钩子"""
    # 确保报告目录存在
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    (reports_dir / "coverage").mkdir(exist_ok=True)
    (reports_dir / "junit").mkdir(exist_ok=True)


def pytest_collection_modifyitems(config, items):
    """修改测试收集行为"""
    import re
    legacy_patterns = [
        r"test_phase[0-9]+_",  # 以阶段编号命名的旧测试
        r"test_tcp_payload_masker_",  # 早期tcp_payload_masker实现
        r"test_pyshark_analyzer",  # 旧PyShark分析器接口
        r"test_tshark_preprocessor",  # 旧TShark预处理器接口
        r"test_tls_reassembly_fix",  # 针对旧TLS重组逻辑
        r"test_tcp_sequence_masking_validation",  # 旧序列号掩码验证框架
        r"test_enhanced_trim_core_models",  # 依赖旧的bisect key签名
        r"test_process.*deduplicator",  # 去重处理器旧接口
        r"test_processors",  # 处理器全集测试，部分依赖旧接口
        r"test_real_data_validation",
        r"test_pipeline",
        r"test_tl[\w]*bidirectional_fix",
        r"test_tcp_bidirectional_fix",
    ]
    compiled_patterns = [re.compile(p) for p in legacy_patterns]

    for item in items:
        path_str = str(item.fspath)
        # 为没有标记的测试添加默认标记
        if not any(item.iter_markers()):
            if "unit" in path_str:
                item.add_marker(pytest.mark.unit)
            elif "integration" in path_str:
                item.add_marker(pytest.mark.integration)
            elif "e2e" in path_str:
                item.add_marker(pytest.mark.e2e)
            elif "performance" in path_str:
                item.add_marker(pytest.mark.performance)

        # 自动检测 legacy 测试
        for pat in compiled_patterns:
            if pat.search(path_str):
                item.add_marker(pytest.mark.legacy)
                break


def pytest_runtest_setup(item):
    """测试运行前的设置"""
    # 跳过性能测试（除非明确要求）
    if item.get_closest_marker("performance") and not item.config.getoption("-m"):
        pytest.skip("性能测试默认跳过，使用 -m performance 运行")


# def pytest_html_report_title(report):
#     """自定义HTML报告标题"""
#     report.title = "PktMask 测试报告"


class BasePcapProcessingTest:
    """PCAP数据处理测试基类
    
    提供通用的PCAP数据处理测试工具和验证方法，
    用于整合重叠的PCAP处理测试功能。
    """
    
    @staticmethod
    def create_test_packets(packet_type="mixed"):
        """创建标准测试数据包
        
        Args:
            packet_type: 数据包类型 ("plain", "vlan", "mixed", "tcp_with_payload")
            
        Returns:
            list: 测试数据包列表
        """
        if packet_type == "plain":
            return [
                Ether() / IP(src="192.168.1.1", dst="192.168.1.2") / TCP(sport=80, dport=8080, flags="S"),
                Ether() / IP(src="192.168.1.1", dst="192.168.1.2") / TCP(sport=80, dport=8080, seq=1000) / Raw(b"plain_data"),
            ]
        elif packet_type == "vlan":
            return [
                Ether() / Dot1Q(vlan=100) / IP(src="10.1.1.1", dst="10.1.1.2") / TCP(sport=443, dport=9443, seq=1000) / Raw(b"vlan_data"),
                Ether() / Dot1Q(vlan=200) / IP(src="10.2.2.1", dst="10.2.2.2") / TCP(sport=22, dport=2222, seq=2000) / Raw(b"vlan_data2"),
            ]
        elif packet_type == "mixed":
            return [
                Ether() / IP(src="192.168.1.1", dst="192.168.1.2") / TCP(sport=80, dport=8080, seq=1000) / Raw(b"plain_tcp"),
                Ether() / Dot1Q(vlan=100) / IP(src="10.1.1.1", dst="10.1.1.2") / TCP(sport=443, dport=9443, seq=2000) / Raw(b"vlan_tcp"),
            ]
        elif packet_type == "tcp_with_payload":
            return [
                Ether() / IP(src="1.1.1.1", dst="2.2.2.2") / TCP(sport=80, dport=8080, flags="S"),  # SYN包不应被裁切
                Ether() / IP(src="1.1.1.1", dst="2.2.2.2") / TCP(sport=80, dport=8080, seq=1000) / b"data",  # 数据包
            ]
        else:
            raise ValueError(f"不支持的数据包类型: {packet_type}")
    
    @staticmethod
    def verify_pcap_processing_result(result, expected_total, result_format="tuple"):
        """通用的PCAP处理结果验证
        
        Args:
            result: 处理结果 (可以是tuple或dict)
            expected_total: 期望的总数据包数
            result_format: 结果格式 ("tuple", "dict", "enhanced_tuple")
        """
        if result_format == "tuple":
            # 基础版本: (processed_packets, total, trimmed, error_log)
            processed_packets, total, trimmed, error_log = result
            assert total == expected_total, f"期望总数 {expected_total}，实际 {total}"
            assert len(processed_packets) <= total, f"处理包数不应超过总数"
            assert trimmed >= 0, f"裁切数应为非负数，实际 {trimmed}"
            assert isinstance(error_log, list), f"错误日志应为列表"
        elif result_format == "enhanced_tuple":
            # 增强版本: (result_packets, total, trimmed, errors)
            result_packets, total, trimmed, errors = result
            assert total == expected_total, f"期望总数 {expected_total}，实际 {total}"
            assert len(result_packets) <= total, f"结果包数不应超过总数"
            assert trimmed >= 0, f"裁切数应为非负数，实际 {trimmed}"
            assert isinstance(errors, list), f"错误列表应为列表"
        elif result_format == "dict":
            # 字典格式处理结果验证
            assert "total_packets" in result, "结果应包含总包数"
            assert result["total_packets"] == expected_total, f"期望总数 {expected_total}，实际 {result['total_packets']}"
            if "trimmed_packets" in result:
                assert result["trimmed_packets"] >= 0, "裁切包数应为非负数"
        else:
            raise ValueError(f"不支持的结果格式: {result_format}")
    
    @staticmethod
    def verify_encapsulation_stats(stats, expected_total, expected_encap_count=None):
        """验证封装统计信息
        
        Args:
            stats: 统计信息字典
            expected_total: 期望的总包数
            expected_encap_count: 期望的封装包数（可选）
        """
        assert "total_packets" in stats, "统计信息应包含总包数"
        assert stats["total_packets"] == expected_total, f"期望总包数 {expected_total}，实际 {stats['total_packets']}"
        
        if "encapsulated_packets" in stats:
            assert stats["encapsulated_packets"] >= 0, "封装包数应为非负数"
            if expected_encap_count is not None:
                assert stats["encapsulated_packets"] == expected_encap_count, \
                    f"期望封装包数 {expected_encap_count}，实际 {stats['encapsulated_packets']}"
        
        if "encapsulation_ratio" in stats:
            assert 0 <= stats["encapsulation_ratio"] <= 1, "封装比例应在0-1之间"
    
    @staticmethod
    def create_temp_pcap_file(packets, suffix=".pcap"):
        """创建临时PCAP文件
        
        Args:
            packets: 数据包列表
            suffix: 文件后缀
            
        Returns:
            str: 临时文件路径
        """
        temp_file = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        temp_file.close()
        wrpcap(temp_file.name, packets)
        return temp_file.name
    
    @staticmethod
    def cleanup_temp_file(file_path):
        """清理临时文件"""
        if os.path.exists(file_path):
            os.unlink(file_path)


class ErrorHandlingTestMixin:
    """错误处理测试混入类
    
    提供通用的错误处理测试工具，用于整合重叠的错误处理测试。
    """
    
    @staticmethod
    def assert_graceful_error_handling(func, *args, expected_result_type=None, **kwargs):
        """验证优雅的错误处理
        
        Args:
            func: 要测试的函数
            *args: 函数参数
            expected_result_type: 期望的结果类型（用于验证回退机制）
            **kwargs: 函数关键字参数
            
        Returns:
            函数执行结果
        """
        try:
            result = func(*args, **kwargs)
            assert result is not None, "函数应返回有效结果或优雅处理错误"
            
            if expected_result_type is not None:
                assert isinstance(result, expected_result_type), \
                    f"结果类型应为 {expected_result_type}，实际为 {type(result)}"
            
            return result
        except Exception as e:
            # 记录意外异常，但不立即失败
            # 某些情况下，函数可能会抛出受控异常
            import logging
            logging.warning(f"函数 {func.__name__} 抛出异常: {e}")
            raise
    
    @staticmethod
    def verify_error_recovery(error_result, success_result):
        """验证错误恢复机制
        
        Args:
            error_result: 错误情况下的结果
            success_result: 正常情况下的结果
        """
        # 验证错误情况下仍能返回合理结果
        if isinstance(error_result, (tuple, list)) and isinstance(success_result, (tuple, list)):
            assert len(error_result) == len(success_result), "错误恢复应保持结果结构一致"
        elif isinstance(error_result, dict) and isinstance(success_result, dict):
            # 验证关键字段仍然存在
            for key in success_result.keys():
                if key in error_result:
                    assert type(error_result[key]) == type(success_result[key]), \
                        f"字段 {key} 的类型应保持一致"
    
    @staticmethod
    def create_error_inducing_data():
        """创建可能导致错误的测试数据"""
        return {
            "invalid_packet": Ether() / Raw(b"invalid packet structure"),
            "malformed_tcp": Ether() / Raw(b"malformed tcp without IP layer"),
            "empty_payload": b"",
            "corrupted_data": b"\x00\x01\x02\x03\xff\xfe\xfd",
        }


class PerformanceTestSuite:
    """性能测试套件
    
    提供统一的性能测试工具和基准，用于整合分散的性能测试。
    """
    
    # 性能基准阈值
    PERFORMANCE_THRESHOLDS = {
        "detection_time": 0.001,      # 检测时间 < 1ms
        "parsing_time": 0.005,        # 解析时间 < 5ms  
        "processing_time": 0.010,     # 处理时间 < 10ms
        "small_file_processing": 1.0, # 小文件处理 < 1s
        "large_file_processing": 10.0 # 大文件处理 < 10s
    }
    
    @staticmethod
    def measure_processing_performance(func, data, iterations=1):
        """标准化性能测量
        
        Args:
            func: 要测试的函数
            data: 测试数据
            iterations: 迭代次数
            
        Returns:
            dict: 性能测量结果
        """
        import time
        
        times = []
        results = []
        
        for _ in range(iterations):
            start_time = time.time()
            result = func(data)
            end_time = time.time()
            
            times.append(end_time - start_time)
            results.append(result)
        
        return {
            "avg_time": sum(times) / len(times),
            "min_time": min(times),
            "max_time": max(times),
            "total_time": sum(times),
            "iterations": iterations,
            "results": results
        }
    
    @staticmethod
    def assert_performance_threshold(actual_time, operation_type, custom_threshold=None):
        """性能阈值断言
        
        Args:
            actual_time: 实际执行时间
            operation_type: 操作类型
            custom_threshold: 自定义阈值（覆盖默认值）
        """
        threshold = custom_threshold or PerformanceTestSuite.PERFORMANCE_THRESHOLDS.get(operation_type)
        
        if threshold is None:
            raise ValueError(f"未知的操作类型: {operation_type}")
        
        assert actual_time <= threshold, \
            f"{operation_type} 性能超出阈值: {actual_time:.3f}s > {threshold:.3f}s"
    
    @staticmethod
    def verify_performance_report(report):
        """验证性能报告格式
        
        Args:
            report: 性能报告字典
        """
        required_fields = ["avg_time", "total_time", "iterations"]
        for field in required_fields:
            assert field in report, f"性能报告缺少必需字段: {field}"
            assert isinstance(report[field], (int, float)), f"字段 {field} 应为数值类型"
        
        assert report["iterations"] > 0, "迭代次数应大于0"
        assert report["avg_time"] >= 0, "平均时间应为非负数"
        assert report["total_time"] >= 0, "总时间应为非负数"
    
    @staticmethod
    def compare_performance(baseline, current, tolerance=0.1):
        """比较性能结果
        
        Args:
            baseline: 基线性能
            current: 当前性能
            tolerance: 容忍度（10%）
            
        Returns:
            dict: 比较结果
        """
        if isinstance(baseline, dict) and isinstance(current, dict):
            baseline_time = baseline.get("avg_time", baseline.get("time", 0))
            current_time = current.get("avg_time", current.get("time", 0))
        else:
            baseline_time = float(baseline)
            current_time = float(current)
        
        improvement = (baseline_time - current_time) / baseline_time if baseline_time > 0 else 0
        regression = improvement < -tolerance
        
        return {
            "baseline_time": baseline_time,
            "current_time": current_time,
            "improvement": improvement,
            "regression": regression,
            "performance_ratio": current_time / baseline_time if baseline_time > 0 else float('inf')
        }


# 统一测试工具类
class TestUtils:
    """统一测试工具类，整合各种通用测试功能"""
    
    @staticmethod
    def get_test_data_path(filename):
        """获取测试数据文件路径"""
        return os.path.join(os.path.dirname(__file__), "data", filename)
    
    @staticmethod
    def assert_file_exists_and_readable(file_path):
        """验证文件存在且可读"""
        assert os.path.exists(file_path), f"文件不存在: {file_path}"
        assert os.path.isfile(file_path), f"路径不是文件: {file_path}"
        assert os.access(file_path, os.R_OK), f"文件不可读: {file_path}"
    
    @staticmethod
    def create_test_directory_structure(base_dir, structure):
        """创建测试目录结构
        
        Args:
            base_dir: 基础目录
            structure: 目录结构描述 (list of dict)
        """
        for item in structure:
            if item["type"] == "dir":
                os.makedirs(os.path.join(base_dir, item["path"]), exist_ok=True)
            elif item["type"] == "file":
                file_path = os.path.join(base_dir, item["path"])
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                with open(file_path, "w") as f:
                    f.write(item.get("content", "")) 