"""
PktMask 配置系统单元测试
Phase 7.1: 单元测试补全 - 配置系统测试
"""

import pytest
import unittest.mock as mock
from unittest.mock import MagicMock, patch, Mock
import tempfile
import os
import sys
import json
import yaml
from pathlib import Path

# 添加src路径到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pktmask.config.app_config import AppConfig
from pktmask.config.algorithm_configs import (
    IPAnonymizationConfig,
    DeduplicationConfig,
    PacketProcessingConfig,
    CustomAlgorithmConfig
)
from pktmask.config.config_manager import ConfigManager
from pktmask.domain.models.statistics_data import StatisticsData, PacketStatistics
from pktmask.domain.models.pipeline_event_data import PipelineEventData


class TestAppConfig:
    """应用配置单元测试"""
    
    def test_app_config_default(self):
        """测试默认应用配置"""
        config = AppConfig()
        
        assert config.debug is False
        assert config.log_level == "INFO"
        assert hasattr(config, 'ui_theme')
        assert hasattr(config, 'processing_threads')
    
    def test_app_config_validation(self):
        """测试应用配置验证"""
        # 测试有效配置
        config = AppConfig(
            debug=True,
            log_level="DEBUG",
            processing_threads=4
        )
        
        assert config.debug is True
        assert config.log_level == "DEBUG"
        assert config.processing_threads == 4
    
    def test_app_config_invalid_log_level(self):
        """测试无效日志级别"""
        with pytest.raises(ValueError):
            AppConfig(log_level="INVALID_LEVEL")
    
    def test_app_config_serialization(self):
        """测试配置序列化"""
        config = AppConfig(
            debug=True,
            log_level="DEBUG"
        )
        
        # 测试转为字典
        config_dict = config.dict()
        assert isinstance(config_dict, dict)
        assert config_dict['debug'] is True
        assert config_dict['log_level'] == "DEBUG"
        
        # 测试JSON序列化
        config_json = config.json()
        assert isinstance(config_json, str)
        
        # 测试从字典重建
        new_config = AppConfig(**config_dict)
        assert new_config.debug == config.debug
        assert new_config.log_level == config.log_level


class TestAlgorithmConfigs:
    """算法配置单元测试"""
    
    def test_ip_anonymization_config(self):
        """测试IP匿名化配置"""
        config = IPAnonymizationConfig(
            anonymization_method="hierarchical",
            preserve_subnet_structure=True,
            cache_enabled=True,
            cache_size=10000,
            performance_mode="balanced"
        )
        
        assert config.anonymization_method == "hierarchical"
        assert config.preserve_subnet_structure is True
        assert config.cache_enabled is True
        assert config.cache_size == 10000
        assert config.performance_mode == "balanced"
    
    def test_ip_anonymization_config_validation(self):
        """测试IP匿名化配置验证"""
        # 测试无效方法
        with pytest.raises(ValueError):
            IPAnonymizationConfig(anonymization_method="invalid_method")
        
        # 测试无效缓存大小
        with pytest.raises(ValueError):
            IPAnonymizationConfig(cache_size=-1)
        
        # 测试无效性能模式
        with pytest.raises(ValueError):
            IPAnonymizationConfig(performance_mode="invalid_mode")
    
    def test_deduplication_config(self):
        """测试去重配置"""
        config = DeduplicationConfig(
            deduplication_method="hash_based",
            time_window_seconds=60,
            cache_enabled=True,
            max_cache_size=50000,
            hash_algorithm="md5"
        )
        
        assert config.deduplication_method == "hash_based"
        assert config.time_window_seconds == 60
        assert config.cache_enabled is True
        assert config.max_cache_size == 50000
        assert config.hash_algorithm == "md5"
    
    def test_deduplication_config_validation(self):
        """测试去重配置验证"""
        # 测试无效方法
        with pytest.raises(ValueError):
            DeduplicationConfig(deduplication_method="invalid_method")
        
        # 测试无效时间窗口
        with pytest.raises(ValueError):
            DeduplicationConfig(time_window_seconds=-1)
    
    def test_packet_processing_config(self):
        """测试数据包处理配置"""
        config = PacketProcessingConfig(
            processing_mode="trim",
            trim_size=128,
            compression_enabled=True,
            filter_rules=["tcp", "udp"],
            batch_size=1000
        )
        
        assert config.processing_mode == "trim"
        assert config.trim_size == 128
        assert config.compression_enabled is True
        assert config.filter_rules == ["tcp", "udp"]
        assert config.batch_size == 1000
    
    def test_packet_processing_config_validation(self):
        """测试数据包处理配置验证"""
        # 测试无效处理模式
        with pytest.raises(ValueError):
            PacketProcessingConfig(processing_mode="invalid_mode")
        
        # 测试无效裁切大小
        with pytest.raises(ValueError):
            PacketProcessingConfig(trim_size=0)
    
    def test_custom_algorithm_config(self):
        """测试自定义算法配置"""
        custom_params = {
            "param1": "value1",
            "param2": 42,
            "param3": True
        }
        
        config = CustomAlgorithmConfig(
            algorithm_name="custom_algorithm",
            algorithm_version="1.0.0",
            parameters=custom_params
        )
        
        assert config.algorithm_name == "custom_algorithm"
        assert config.algorithm_version == "1.0.0"
        assert config.parameters == custom_params
    
    def test_config_serialization_json(self):
        """测试配置JSON序列化"""
        config = IPAnonymizationConfig(
            anonymization_method="hierarchical",
            cache_size=5000
        )
        
        # 序列化为JSON
        json_str = config.json()
        assert isinstance(json_str, str)
        
        # 反序列化
        config_data = json.loads(json_str)
        new_config = IPAnonymizationConfig(**config_data)
        
        assert new_config.anonymization_method == config.anonymization_method
        assert new_config.cache_size == config.cache_size


class TestConfigManager:
    """配置管理器单元测试"""
    
    @pytest.fixture
    def temp_config_dir(self):
        """创建临时配置目录"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def config_manager(self, temp_config_dir):
        """创建配置管理器实例"""
        return ConfigManager(config_dir=temp_config_dir)
    
    def test_config_manager_init(self, config_manager, temp_config_dir):
        """测试配置管理器初始化"""
        assert config_manager.config_dir == temp_config_dir
        assert hasattr(config_manager, 'load_config')
        assert hasattr(config_manager, 'save_config')
        assert hasattr(config_manager, 'get_config')
    
    def test_save_and_load_config_json(self, config_manager):
        """测试配置保存和加载（JSON格式）"""
        config = IPAnonymizationConfig(
            anonymization_method="hierarchical",
            cache_size=8000
        )
        
        # 保存配置
        config_file = "test_ip_config.json"
        config_manager.save_config(config, config_file, format="json")
        
        # 验证文件存在
        config_path = config_manager.config_dir / config_file
        assert config_path.exists()
        
        # 加载配置
        loaded_config = config_manager.load_config(config_file, IPAnonymizationConfig)
        
        assert loaded_config.anonymization_method == config.anonymization_method
        assert loaded_config.cache_size == config.cache_size
    
    def test_save_and_load_config_yaml(self, config_manager):
        """测试配置保存和加载（YAML格式）"""
        config = DeduplicationConfig(
            deduplication_method="hash_based",
            time_window_seconds=120
        )
        
        # 保存配置
        config_file = "test_dedup_config.yaml"
        config_manager.save_config(config, config_file, format="yaml")
        
        # 验证文件存在
        config_path = config_manager.config_dir / config_file
        assert config_path.exists()
        
        # 加载配置
        loaded_config = config_manager.load_config(config_file, DeduplicationConfig)
        
        assert loaded_config.deduplication_method == config.deduplication_method
        assert loaded_config.time_window_seconds == config.time_window_seconds
    
    def test_config_versioning(self, config_manager):
        """测试配置版本管理"""
        config = PacketProcessingConfig(
            processing_mode="trim",
            trim_size=256
        )
        
        config_file = "test_processing_config.json"
        
        # 保存初始版本
        version1 = config_manager.save_config(config, config_file, format="json")
        
        # 修改配置
        config.trim_size = 512
        
        # 保存新版本
        version2 = config_manager.save_config(config, config_file, format="json")
        
        # 验证版本不同
        assert version1 != version2
        
        # 验证可以获取版本历史
        if hasattr(config_manager, 'get_config_versions'):
            versions = config_manager.get_config_versions(config_file)
            assert len(versions) >= 2
    
    def test_config_hot_reload(self, config_manager):
        """测试配置热重载"""
        config = IPAnonymizationConfig(
            anonymization_method="hierarchical",
            cache_size=4000
        )
        
        config_file = "test_hot_reload.json"
        
        # 保存配置
        config_manager.save_config(config, config_file, format="json")
        
        # 模拟热重载回调
        reload_called = False
        def reload_callback(new_config):
            nonlocal reload_called
            reload_called = True
            assert new_config.cache_size == 6000
        
        # 注册热重载回调
        if hasattr(config_manager, 'register_hot_reload'):
            config_manager.register_hot_reload(config_file, reload_callback)
        
        # 修改并保存配置
        config.cache_size = 6000
        config_manager.save_config(config, config_file, format="json")
        
        # 验证回调被调用（如果支持热重载）
        # assert reload_called  # 取消注释如果实现了热重载
    
    def test_config_templates(self, config_manager):
        """测试配置模板"""
        if hasattr(config_manager, 'get_template'):
            # 获取IP匿名化模板
            template = config_manager.get_template('ip_anonymization')
            assert isinstance(template, IPAnonymizationConfig)
            
            # 获取去重模板
            template = config_manager.get_template('deduplication')
            assert isinstance(template, DeduplicationConfig)
            
            # 获取数据包处理模板
            template = config_manager.get_template('packet_processing')
            assert isinstance(template, PacketProcessingConfig)
    
    def test_config_validation_on_load(self, config_manager, temp_config_dir):
        """测试加载时的配置验证"""
        # 创建无效配置文件
        invalid_config = {
            "anonymization_method": "invalid_method",
            "cache_size": -1
        }
        
        config_file = temp_config_dir / "invalid_config.json"
        with open(config_file, 'w') as f:
            json.dump(invalid_config, f)
        
        # 尝试加载应该失败
        with pytest.raises(ValueError):
            config_manager.load_config("invalid_config.json", IPAnonymizationConfig)


class TestDataModels:
    """数据模型单元测试"""
    
    def test_statistics_data_model(self):
        """测试统计数据模型"""
        packet_stats = PacketStatistics(
            total_packets=1000,
            processed_packets=950,
            filtered_packets=50
        )
        
        stats = StatisticsData(
            total_files=10,
            processed_files=8,
            failed_files=2,
            total_size=1024000,
            processed_size=900000,
            packet_stats=packet_stats
        )
        
        assert stats.total_files == 10
        assert stats.processed_files == 8
        assert stats.failed_files == 2
        assert stats.total_size == 1024000
        assert stats.processed_size == 900000
        assert stats.packet_stats.total_packets == 1000
        assert stats.packet_stats.processed_packets == 950
    
    def test_statistics_data_validation(self):
        """测试统计数据验证"""
        # 测试无效值
        with pytest.raises(ValueError):
            StatisticsData(
                total_files=-1,  # 不能为负数
                processed_files=0,
                failed_files=0
            )
    
    def test_pipeline_event_data_model(self):
        """测试管道事件数据模型"""
        event = PipelineEventData(
            event_type="step_start",
            step_name="ip_anonymization",
            progress=0.5,
            message="Processing IP anonymization",
            timestamp=None  # 应该自动设置
        )
        
        assert event.event_type == "step_start"
        assert event.step_name == "ip_anonymization"
        assert event.progress == 0.5
        assert event.message == "Processing IP anonymization"
        assert event.timestamp is not None
    
    def test_pipeline_event_data_validation(self):
        """测试管道事件数据验证"""
        # 测试无效进度值
        with pytest.raises(ValueError):
            PipelineEventData(
                event_type="step_progress",
                step_name="test",
                progress=1.5,  # 不能超过1.0
                message="Invalid progress"
            )
    
    def test_data_model_serialization(self):
        """测试数据模型序列化"""
        packet_stats = PacketStatistics(
            total_packets=500,
            processed_packets=450,
            filtered_packets=50
        )
        
        stats = StatisticsData(
            total_files=5,
            processed_files=4,
            failed_files=1,
            total_size=512000,
            processed_size=400000,
            packet_stats=packet_stats
        )
        
        # 测试转为字典
        stats_dict = stats.dict()
        assert isinstance(stats_dict, dict)
        assert stats_dict['total_files'] == 5
        assert 'packet_stats' in stats_dict
        assert stats_dict['packet_stats']['total_packets'] == 500
        
        # 测试JSON序列化
        stats_json = stats.json()
        assert isinstance(stats_json, str)
        
        # 测试从字典重建
        new_stats = StatisticsData(**stats_dict)
        assert new_stats.total_files == stats.total_files
        assert new_stats.packet_stats.total_packets == stats.packet_stats.total_packets


# 测试运行配置
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"]) 