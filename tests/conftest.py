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

# 添加源代码路径到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pktmask.config.settings import AppConfig


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
def mock_gui_environment(monkeypatch):
    """模拟GUI测试环境"""
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("DISPLAY", ":99")  # 虚拟显示
    

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
    # 为没有标记的测试添加默认标记
    for item in items:
        if not any(item.iter_markers()):
            if "unit" in str(item.fspath):
                item.add_marker(pytest.mark.unit)
            elif "integration" in str(item.fspath):
                item.add_marker(pytest.mark.integration)
            elif "e2e" in str(item.fspath):
                item.add_marker(pytest.mark.e2e)
            elif "performance" in str(item.fspath):
                item.add_marker(pytest.mark.performance)


def pytest_runtest_setup(item):
    """测试运行前的设置"""
    # 跳过性能测试（除非明确要求）
    if item.get_closest_marker("performance") and not item.config.getoption("-m"):
        pytest.skip("性能测试默认跳过，使用 -m performance 运行")


def pytest_html_report_title(report):
    """自定义HTML报告标题"""
    report.title = "PktMask 自动化测试报告" 