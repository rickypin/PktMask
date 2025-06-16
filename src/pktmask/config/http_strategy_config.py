"""
HTTP策略配置系统

这个模块定义了双策略配置架构，支持Legacy HTTPTrimStrategy和新的HTTPScanningStrategy
并存，提供A/B测试、性能对比、渐进迁移等功能的配置管理。

作者: PktMask Team
创建时间: 2025-01-15 
版本: 1.0.0
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
import random
import time
from enum import Enum


class StrategyMode(Enum):
    """策略模式枚举"""
    LEGACY = "legacy"          # 使用原HTTPTrimStrategy
    SCANNING = "scanning"      # 使用新HTTPScanningStrategy  
    AUTO = "auto"              # 自动选择策略
    AB_TEST = "ab_test"        # A/B测试模式
    COMPARISON = "comparison"  # 性能对比模式


class MultiMessageMode(Enum):
    """多消息处理模式"""
    CONSERVATIVE = "conservative"  # 保守策略：保留所有头部+第一消息体样本
    AGGRESSIVE = "aggressive"      # 激进策略：尝试精确解析所有消息


@dataclass
class HttpStrategyConfig:
    """HTTP策略选择器配置"""
    
    # 主策略选择
    primary_strategy: StrategyMode = StrategyMode.LEGACY
    
    # A/B测试配置
    enable_ab_testing: bool = False
    ab_test_ratio: float = 0.1  # 新策略流量比例，默认10%
    ab_test_seed: int = 42      # 随机种子，确保结果可重复
    
    # 性能对比配置
    enable_performance_comparison: bool = False
    comparison_log_file: str = "http_strategy_comparison.json"
    
    # 故障回退配置
    auto_fallback_enabled: bool = True
    fallback_error_threshold: float = 0.05  # 5%错误率触发回退
    fallback_timeout_ms: int = 5000         # 5秒超时触发回退
    
    # 迁移配置
    migration_mode: bool = False
    migration_phase: int = 0  # 0-5 迁移阶段标识


@dataclass
class ScanningStrategyConfig:
    """扫描式HTTP策略配置"""
    
    # 扫描窗口配置
    max_scan_window: int = 8192  # 最大扫描窗口 8KB
    header_boundary_timeout_ms: int = 100  # 头部边界检测超时
    
    # Chunked处理配置
    chunked_sample_size: int = 1024      # chunked样本大小
    max_chunks_to_analyze: int = 10      # 最大分析chunk数量
    chunked_incomplete_ratio: float = 0.8 # 不完整chunked保留比例
    
    # 多消息处理配置
    multi_message_mode: MultiMessageMode = MultiMessageMode.CONSERVATIVE
    max_messages_per_payload: int = 5    # 单个载荷最大消息数
    multi_message_sample_size: int = 512 # 多消息样本大小
    
    # 大文件优化配置
    large_file_threshold: int = 1024 * 1024  # 1MB阈值
    large_file_header_limit: int = 8192      # 大文件头部限制
    
    # 保守策略配置
    fallback_on_error: bool = True
    conservative_preserve_ratio: float = 0.8  # 保守模式保留比例
    min_preserve_bytes: int = 64              # 最小保留字节数
    max_preserve_bytes: int = 8192            # 最大保留字节数
    
    # 性能配置
    enable_caching: bool = True
    cache_ttl_seconds: int = 300  # 5分钟缓存TTL
    
    # 调试和监控
    enable_scan_logging: bool = False
    performance_metrics_enabled: bool = True
    detailed_warnings: bool = True


@dataclass
class LegacyHttpTrimConfig:
    """Legacy HTTP策略配置（完全保留现有配置项）"""
    
    # 现有HTTPTrimStrategy的所有配置项完全保留
    # 这里只是占位符，实际配置项在现有系统中已定义
    preserve_existing_config: bool = True
    
    # 注：实际的Legacy配置项继续使用现有ProcessingSettings中的配置


@dataclass  
class ABTestConfig:
    """A/B测试配置"""
    
    # 测试参数
    test_name: str = ""
    test_description: str = ""
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    
    # 流量分配
    control_ratio: float = 0.9   # 控制组(Legacy)比例
    treatment_ratio: float = 0.1 # 实验组(Scanning)比例
    
    # 采样配置
    sampling_strategy: str = "hash_based"  # hash_based | random | time_based
    hash_seed: int = 42
    
    # 指标收集
    metrics_collection_enabled: bool = True
    metrics_collection_interval: int = 300  # 5分钟
    
    # 结果分析
    min_sample_size: int = 100
    confidence_level: float = 0.95
    statistical_power: float = 0.8


@dataclass
class PerformanceComparisonConfig:
    """性能对比配置"""
    
    # 对比模式
    run_both_strategies: bool = True  # 同时运行两种策略
    use_primary_result: bool = True   # 使用主策略结果
    
    # 数据收集
    collect_timing_data: bool = True
    collect_memory_data: bool = True  
    collect_accuracy_data: bool = True
    
    # 报告配置
    auto_generate_reports: bool = True
    report_interval_hours: int = 24
    max_report_history: int = 30
    
    # 性能阈值
    max_performance_degradation: float = 0.2  # 20%性能降低阈值
    max_memory_increase: float = 0.3         # 30%内存增长阈值


@dataclass
class MonitoringConfig:
    """监控配置"""
    
    # 健康检查
    health_check_enabled: bool = True
    health_check_interval_seconds: int = 300  # 5分钟
    
    # 指标跟踪
    track_error_rates: bool = True
    track_performance_metrics: bool = True
    track_strategy_selection: bool = True
    
    # 告警配置
    alert_enabled: bool = True
    alert_error_threshold: float = 0.05      # 5%错误率告警
    alert_performance_threshold: float = 0.3  # 30%性能降低告警
    
    # 数据保留
    metrics_retention_days: int = 30
    logs_retention_days: int = 7


@dataclass
class HttpStrategyConfiguration:
    """HTTP策略完整配置"""
    
    # 各配置模块
    strategy: HttpStrategyConfig = field(default_factory=HttpStrategyConfig)
    scanning: ScanningStrategyConfig = field(default_factory=ScanningStrategyConfig) 
    legacy: LegacyHttpTrimConfig = field(default_factory=LegacyHttpTrimConfig)
    ab_test: ABTestConfig = field(default_factory=ABTestConfig)
    performance: PerformanceComparisonConfig = field(default_factory=PerformanceComparisonConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    
    # 配置元数据
    config_version: str = "1.0.0"
    created_at: Optional[float] = None
    updated_at: Optional[float] = None
    
    def __post_init__(self):
        current_time = time.time()
        if self.created_at is None:
            self.created_at = current_time
        self.updated_at = current_time
    
    def should_use_scanning_strategy(self, file_path: str = None) -> bool:
        """判断是否应该使用扫描策略"""
        
        if self.strategy.primary_strategy == StrategyMode.LEGACY:
            return False
        elif self.strategy.primary_strategy == StrategyMode.SCANNING:
            return True
        elif self.strategy.primary_strategy == StrategyMode.AB_TEST:
            return self._ab_test_selection(file_path)
        elif self.strategy.primary_strategy == StrategyMode.AUTO:
            return self._auto_selection(file_path)
        else:
            return False  # 默认回退到Legacy
    
    def _ab_test_selection(self, file_path: str = None) -> bool:
        """A/B测试策略选择"""
        if not self.strategy.enable_ab_testing:
            return False
        
        # 基于文件路径或其他特征计算hash，确保同一文件始终使用相同策略
        hash_input = file_path or f"default_{time.time()}"
        file_hash = hash(hash_input)
        
        # 使用种子确保可重复性
        random.seed(file_hash + self.strategy.ab_test_seed)
        
        return random.random() < self.strategy.ab_test_ratio
    
    def _auto_selection(self, file_path: str = None) -> bool:
        """自动策略选择"""
        # 自动选择逻辑可以基于文件大小、历史性能等因素
        # 这里先简单返回False，表示默认使用Legacy策略
        return False
    
    def get_strategy_name(self, file_path: str = None) -> str:
        """获取当前应使用的策略名称"""
        if self.should_use_scanning_strategy(file_path):
            return "http_scanning"
        else:
            return "http_trim"
    
    def validate(self) -> tuple[bool, List[str]]:
        """验证配置有效性"""
        errors = []
        
        # 验证A/B测试配置
        if self.strategy.enable_ab_testing:
            if not (0.0 <= self.strategy.ab_test_ratio <= 1.0):
                errors.append("ab_test_ratio必须在0.0-1.0之间")
        
        # 验证扫描策略配置
        if self.scanning.max_scan_window <= 0:
            errors.append("max_scan_window必须大于0")
        
        if self.scanning.chunked_sample_size <= 0:
            errors.append("chunked_sample_size必须大于0")
        
        if not (0.0 <= self.scanning.conservative_preserve_ratio <= 1.0):
            errors.append("conservative_preserve_ratio必须在0.0-1.0之间")
        
        # 验证监控配置
        if self.monitoring.health_check_interval_seconds <= 0:
            errors.append("health_check_interval_seconds必须大于0")
        
        if not (0.0 <= self.monitoring.alert_error_threshold <= 1.0):
            errors.append("alert_error_threshold必须在0.0-1.0之间")
        
        return len(errors) == 0, errors


def get_default_http_strategy_config() -> HttpStrategyConfiguration:
    """获取默认HTTP策略配置"""
    return HttpStrategyConfiguration()


def create_production_config() -> HttpStrategyConfiguration:
    """创建生产环境配置"""
    config = HttpStrategyConfiguration()
    
    # 生产环境使用保守设置
    config.strategy.primary_strategy = StrategyMode.LEGACY
    config.strategy.auto_fallback_enabled = True
    config.strategy.fallback_error_threshold = 0.03  # 更严格的3%阈值
    
    # 扫描策略保守配置
    config.scanning.fallback_on_error = True
    config.scanning.enable_scan_logging = False  # 生产环境关闭详细日志
    config.scanning.performance_metrics_enabled = True
    
    # 监控配置
    config.monitoring.health_check_enabled = True
    config.monitoring.alert_enabled = True
    config.monitoring.metrics_retention_days = 90  # 更长的数据保留
    
    return config


def create_ab_test_config(test_ratio: float = 0.05) -> HttpStrategyConfiguration:
    """创建A/B测试配置"""
    config = HttpStrategyConfiguration()
    
    # A/B测试模式
    config.strategy.primary_strategy = StrategyMode.AB_TEST
    config.strategy.enable_ab_testing = True
    config.strategy.ab_test_ratio = test_ratio
    
    # 启用对比分析
    config.strategy.enable_performance_comparison = True
    config.performance.run_both_strategies = False  # A/B测试模式只运行选中策略
    
    # 详细监控
    config.monitoring.track_error_rates = True
    config.monitoring.track_performance_metrics = True
    config.monitoring.track_strategy_selection = True
    
    return config 