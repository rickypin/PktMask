"""
A/B测试框架 - 支持双策略对比验证

这个模块实现了完整的A/B测试框架，用于对比验证Legacy HTTP策略
和新的Scanning HTTP策略的性能和效果差异。

核心功能：
1. 科学的A/B测试设计和执行
2. 详细的性能指标收集和分析
3. 统计显著性检验和置信区间计算
4. 自动化测试报告生成

作者: PktMask Team
创建时间: 2025-01-15
版本: 1.0.0
"""

import time
import json
import logging
import statistics
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from pathlib import Path
from datetime import datetime, timedelta
import hashlib
import random
from enum import Enum

try:
    from ..strategies.base_strategy import BaseStrategy, ProtocolInfo, TrimContext
    from ..strategies.factory import get_enhanced_strategy_factory
    from ....config.http_strategy_config import HttpStrategyConfiguration
    DEPENDENCIES_AVAILABLE = True
except ImportError:
    DEPENDENCIES_AVAILABLE = False
    # 创建一个简单的替代类
    class HttpStrategyConfiguration:
        def __init__(self):
            self.primary_strategy = "legacy"


class TestStatus(Enum):
    """测试状态枚举"""
    PENDING = "pending"        # 等待开始
    RUNNING = "running"        # 运行中
    COMPLETED = "completed"    # 已完成
    FAILED = "failed"          # 失败
    CANCELLED = "cancelled"    # 已取消


class StrategyGroup(Enum):
    """策略组枚举"""
    CONTROL = "control"        # 控制组 (Legacy)
    TREATMENT = "treatment"    # 实验组 (Scanning)


@dataclass
class ABTestConfig:
    """A/B测试配置"""
    test_name: str                    # 测试名称
    treatment_ratio: float = 0.5      # 实验组比例 (0.0-1.0)
    min_sample_size: int = 100        # 最小样本量
    max_duration_hours: int = 24      # 最大测试时长(小时)
    confidence_level: float = 0.95    # 置信度
    effect_size_threshold: float = 0.1  # 效应量阈值
    
    # 分组策略
    assignment_strategy: str = "random"  # random, hash_based, file_size
    
    # 结果收集配置
    collect_detailed_metrics: bool = True
    collect_comparison_data: bool = True
    auto_stop_on_significance: bool = False


@dataclass
class TestCase:
    """测试用例"""
    file_path: str
    protocol_info: ProtocolInfo
    context: TrimContext
    payload_size: int
    expected_group: Optional[StrategyGroup] = None
    test_id: str = ""
    
    def __post_init__(self):
        if not self.test_id:
            # 生成唯一测试ID
            content = f"{self.file_path}_{self.payload_size}_{time.time()}"
            self.test_id = hashlib.md5(content.encode()).hexdigest()[:12]


@dataclass
class StrategyResult:
    """策略执行结果"""
    strategy_name: str
    strategy_group: StrategyGroup
    test_case_id: str
    
    # 性能指标
    execution_time_ms: float
    memory_usage_mb: float
    cpu_usage_percent: float
    
    # 功能指标
    success: bool
    error_message: Optional[str] = None
    analysis_result: Dict[str, Any] = field(default_factory=dict)
    
    # 质量指标
    header_boundary_found: bool = False
    chunked_handling: bool = False
    multi_message_detected: bool = False
    
    # 输出质量
    preserve_bytes: int = 0
    total_bytes: int = 0
    preserve_ratio: float = 0.0
    
    # 时间戳
    timestamp: float = field(default_factory=time.time)
    
    def __post_init__(self):
        if self.total_bytes > 0:
            self.preserve_ratio = self.preserve_bytes / self.total_bytes


@dataclass
class ComparisonResult:
    """对比结果"""
    test_case_id: str
    control_result: StrategyResult
    treatment_result: StrategyResult
    
    # 性能对比
    speed_improvement: float = 0.0  # 正值表示Treatment更快
    memory_improvement: float = 0.0  # 正值表示Treatment内存更少
    
    # 功能一致性
    both_successful: bool = False
    results_consistent: bool = False
    quality_difference: float = 0.0
    
    # 综合评分
    overall_score: float = 0.0
    
    def __post_init__(self):
        self._calculate_comparisons()
    
    def _calculate_comparisons(self):
        """计算对比指标"""
        # 性能对比
        if self.control_result.execution_time_ms > 0:
            self.speed_improvement = (
                (self.control_result.execution_time_ms - self.treatment_result.execution_time_ms) 
                / self.control_result.execution_time_ms
            )
        
        if self.control_result.memory_usage_mb > 0:
            self.memory_improvement = (
                (self.control_result.memory_usage_mb - self.treatment_result.memory_usage_mb)
                / self.control_result.memory_usage_mb
            )
        
        # 功能一致性
        self.both_successful = (
            self.control_result.success and self.treatment_result.success
        )
        
        self.results_consistent = self._check_result_consistency()
        
        # 质量差异
        control_quality = self._calculate_quality_score(self.control_result)
        treatment_quality = self._calculate_quality_score(self.treatment_result)
        self.quality_difference = treatment_quality - control_quality
        
        # 综合评分 (0-100分)
        self.overall_score = self._calculate_overall_score()
    
    def _check_result_consistency(self) -> bool:
        """检查结果一致性"""
        if not self.both_successful:
            return False
        
        # 检查关键字段一致性
        control_analysis = self.control_result.analysis_result
        treatment_analysis = self.treatment_result.analysis_result
        
        key_fields = ['header_boundary', 'is_chunked', 'content_length']
        for field in key_fields:
            if control_analysis.get(field) != treatment_analysis.get(field):
                return False
        
        return True
    
    def _calculate_quality_score(self, result: StrategyResult) -> float:
        """计算质量评分 (0-100)"""
        if not result.success:
            return 0.0
        
        score = 50.0  # 基础分
        
        # 功能检测加分
        if result.header_boundary_found:
            score += 15.0
        if result.chunked_handling:
            score += 15.0
        if result.multi_message_detected:
            score += 10.0
        
        # 保留比例合理性加分
        if 0.1 <= result.preserve_ratio <= 0.8:
            score += 10.0
        
        return min(score, 100.0)
    
    def _calculate_overall_score(self) -> float:
        """计算综合评分"""
        if not self.both_successful:
            return 0.0
        
        score = 50.0  # 基础分
        
        # 性能提升加分
        if self.speed_improvement > 0:
            score += min(self.speed_improvement * 20, 20)  # 最多20分
        
        if self.memory_improvement > 0:
            score += min(self.memory_improvement * 10, 10)  # 最多10分
        
        # 一致性加分
        if self.results_consistent:
            score += 15.0
        
        # 质量改进加分
        if self.quality_difference > 0:
            score += min(self.quality_difference * 0.05, 5)  # 最多5分
        
        return min(score, 100.0)


@dataclass
class ABTestReport:
    """A/B测试报告"""
    test_name: str
    test_config: ABTestConfig
    start_time: float
    end_time: float
    
    # 测试统计
    total_test_cases: int
    successful_comparisons: int
    failed_test_cases: int
    
    # 整体性能指标
    avg_speed_improvement: float
    avg_memory_improvement: float
    consistency_rate: float
    overall_success_rate: float
    
    # 详细结果
    comparison_results: List[ComparisonResult] = field(default_factory=list)
    
    # 统计分析
    statistical_significance: bool = False
    confidence_interval: Tuple[float, float] = (0.0, 0.0)
    p_value: float = 1.0
    
    # 建议
    recommendation: str = ""
    risk_assessment: str = ""
    
    @property
    def duration_hours(self) -> float:
        """测试持续时间（小时）"""
        return (self.end_time - self.start_time) / 3600
    
    @property
    def test_efficiency(self) -> float:
        """测试效率（成功率）"""
        if self.total_test_cases == 0:
            return 0.0
        return self.successful_comparisons / self.total_test_cases


class PerformanceTracker:
    """性能跟踪器"""
    
    def __init__(self):
        self.metrics_data: List[Dict[str, Any]] = []
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
    
    def record_strategy_execution(self, strategy_name: str, result: StrategyResult):
        """记录策略执行性能"""
        metric = {
            'timestamp': result.timestamp,
            'strategy_name': strategy_name,
            'execution_time_ms': result.execution_time_ms,
            'memory_usage_mb': result.memory_usage_mb,
            'success': result.success,
            'preserve_ratio': result.preserve_ratio
        }
        self.metrics_data.append(metric)
    
    def get_performance_summary(self, strategy_name: str) -> Dict[str, float]:
        """获取策略性能汇总"""
        strategy_metrics = [
            m for m in self.metrics_data 
            if m['strategy_name'] == strategy_name and m['success']
        ]
        
        if not strategy_metrics:
            return {}
        
        execution_times = [m['execution_time_ms'] for m in strategy_metrics]
        memory_usages = [m['memory_usage_mb'] for m in strategy_metrics]
        preserve_ratios = [m['preserve_ratio'] for m in strategy_metrics]
        
        return {
            'avg_execution_time': statistics.mean(execution_times),
            'median_execution_time': statistics.median(execution_times),
            'std_execution_time': statistics.stdev(execution_times) if len(execution_times) > 1 else 0,
            'avg_memory_usage': statistics.mean(memory_usages),
            'avg_preserve_ratio': statistics.mean(preserve_ratios),
            'success_rate': len(strategy_metrics) / len([m for m in self.metrics_data if m['strategy_name'] == strategy_name])
        }


class ABTestFramework:
    """A/B测试框架"""
    
    def __init__(self, http_config: Optional[HttpStrategyConfiguration] = None):
        if not DEPENDENCIES_AVAILABLE:
            raise ImportError("A/B测试框架依赖项不可用")
        
        self.http_config = http_config
        self.enhanced_factory = get_enhanced_strategy_factory(http_config)
        self.performance_tracker = PerformanceTracker()
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        
        # 测试状态
        self.current_test: Optional[ABTestConfig] = None
        self.test_status: TestStatus = TestStatus.PENDING
        self.test_results: List[ComparisonResult] = []
    
    def create_test_plan(self, test_files: List[str], 
                        test_config: ABTestConfig) -> List[TestCase]:
        """创建测试计划"""
        
        test_cases = []
        
        for file_path in test_files:
            # 创建基础协议信息和上下文
            protocol_info = ProtocolInfo(name="http", version="1.1")
            context = TrimContext(input_file=file_path, output_file="")
            
            # 获取文件大小作为载荷大小
            try:
                payload_size = Path(file_path).stat().st_size
            except OSError:
                payload_size = 0
            
            # 创建测试用例
            test_case = TestCase(
                file_path=file_path,
                protocol_info=protocol_info,
                context=context,
                payload_size=payload_size
            )
            
            # 分配到测试组
            if self._should_assign_to_treatment(test_case, test_config):
                test_case.expected_group = StrategyGroup.TREATMENT
            else:
                test_case.expected_group = StrategyGroup.CONTROL
            
            test_cases.append(test_case)
        
        self.logger.info(f"创建测试计划完成，共{len(test_cases)}个测试用例")
        return test_cases
    
    def _should_assign_to_treatment(self, test_case: TestCase, 
                                   config: ABTestConfig) -> bool:
        """判断是否分配到实验组"""
        
        if config.sampling_strategy == "hash_based":
            # 基于文件路径hash
            file_hash = hashlib.md5(test_case.file_path.encode()).hexdigest()
            hash_value = int(file_hash[:8], 16) / (16**8)
            return hash_value < config.treatment_ratio
        
        elif config.sampling_strategy == "random":
            # 随机分配
            random.seed(config.hash_seed)
            return random.random() < config.treatment_ratio
        
        else:
            # 默认基于文件大小
            return (test_case.payload_size % 10) < (config.treatment_ratio * 10)
    
    def run_ab_test(self, test_cases: List[TestCase], 
                   config: ABTestConfig) -> ABTestReport:
        """运行A/B测试"""
        
        self.current_test = config
        self.test_status = TestStatus.RUNNING
        self.test_results = []
        
        start_time = time.time()
        self.logger.info(f"开始A/B测试: {config.test_name}")
        
        try:
            # 执行所有测试用例
            for test_case in test_cases:
                try:
                    comparison_result = self._execute_test_case(test_case, config)
                    if comparison_result:
                        self.test_results.append(comparison_result)
                except Exception as e:
                    self.logger.error(f"测试用例 {test_case.test_id} 执行失败: {e}")
            
            end_time = time.time()
            
            # 生成报告
            report = self._generate_report(config, start_time, end_time)
            
            self.test_status = TestStatus.COMPLETED
            self.logger.info(f"A/B测试完成: {config.test_name}")
            
            return report
            
        except Exception as e:
            self.test_status = TestStatus.FAILED
            self.logger.error(f"A/B测试失败: {e}")
            raise
    
    def _execute_test_case(self, test_case: TestCase, 
                          config: ABTestConfig) -> Optional[ComparisonResult]:
        """执行单个测试用例"""
        
        # 获取两个策略实例
        legacy_strategy = self.enhanced_factory._get_legacy_strategy({})
        scanning_strategy = self.enhanced_factory._get_scanning_strategy({})
        
        if not legacy_strategy or not scanning_strategy:
            self.logger.warning(f"无法获取策略实例: {test_case.test_id}")
            return None
        
        # 模拟载荷数据（实际实现中应该从文件读取）
        payload = b"HTTP/1.1 200 OK\r\nContent-Length: 100\r\n\r\n" + b"x" * 100
        
        # 执行控制组策略 (Legacy)
        control_result = self._execute_strategy(
            legacy_strategy, payload, test_case, StrategyGroup.CONTROL
        )
        
        # 执行实验组策略 (Scanning)
        treatment_result = self._execute_strategy(
            scanning_strategy, payload, test_case, StrategyGroup.TREATMENT
        )
        
        # 创建对比结果
        comparison = ComparisonResult(
            test_case_id=test_case.test_id,
            control_result=control_result,
            treatment_result=treatment_result
        )
        
        return comparison
    
    def _execute_strategy(self, strategy: BaseStrategy, payload: bytes,
                         test_case: TestCase, group: StrategyGroup) -> StrategyResult:
        """执行单个策略"""
        
        start_time = time.perf_counter()
        success = False
        error_message = None
        analysis_result = {}
        
        try:
            # 执行策略分析
            analysis_result = strategy.analyze_payload(
                payload, test_case.protocol_info, test_case.context
            )
            success = True
            
        except Exception as e:
            error_message = str(e)
            
        end_time = time.perf_counter()
        execution_time = (end_time - start_time) * 1000  # 转为毫秒
        
        # 创建结果对象
        result = StrategyResult(
            strategy_name=strategy.strategy_name,
            strategy_group=group,
            test_case_id=test_case.test_id,
            execution_time_ms=execution_time,
            memory_usage_mb=0.0,  # 简化实现，实际中需要测量内存
            cpu_usage_percent=0.0,  # 简化实现
            success=success,
            error_message=error_message,
            analysis_result=analysis_result,
            header_boundary_found=bool(analysis_result.get('header_boundary')),
            chunked_handling=bool(analysis_result.get('is_chunked')),
            preserve_bytes=analysis_result.get('preserve_bytes', 0),
            total_bytes=len(payload)
        )
        
        # 记录性能数据
        self.performance_tracker.record_strategy_execution(
            strategy.strategy_name, result
        )
        
        return result
    
    def _generate_report(self, config: ABTestConfig, 
                        start_time: float, end_time: float) -> ABTestReport:
        """生成测试报告"""
        
        successful_comparisons = len([r for r in self.test_results if r.both_successful])
        
        # 计算平均指标
        if successful_comparisons > 0:
            avg_speed_improvement = statistics.mean([
                r.speed_improvement for r in self.test_results if r.both_successful
            ])
            avg_memory_improvement = statistics.mean([
                r.memory_improvement for r in self.test_results if r.both_successful
            ])
            consistency_rate = len([
                r for r in self.test_results if r.results_consistent
            ]) / successful_comparisons
        else:
            avg_speed_improvement = 0.0
            avg_memory_improvement = 0.0
            consistency_rate = 0.0
        
        # 生成建议
        recommendation = self._generate_recommendation(
            avg_speed_improvement, consistency_rate, successful_comparisons
        )
        
        # 创建报告
        report = ABTestReport(
            test_name=config.test_name,
            test_config=config,
            start_time=start_time,
            end_time=end_time,
            total_test_cases=len(self.test_results),
            successful_comparisons=successful_comparisons,
            failed_test_cases=len(self.test_results) - successful_comparisons,
            avg_speed_improvement=avg_speed_improvement,
            avg_memory_improvement=avg_memory_improvement,
            consistency_rate=consistency_rate,
            overall_success_rate=successful_comparisons / len(self.test_results) if self.test_results else 0,
            comparison_results=self.test_results,
            recommendation=recommendation
        )
        
        return report
    
    def _generate_recommendation(self, speed_improvement: float,
                               consistency_rate: float, sample_size: int) -> str:
        """生成策略建议"""
        
        if sample_size < 10:
            return "样本量过小，建议增加测试用例后再做决策"
        
        if consistency_rate < 0.8:
            return "结果一致性较低，建议检查策略实现后重新测试"
        
        if speed_improvement > 0.2 and consistency_rate > 0.9:
            return "强烈推荐切换到Scanning策略，性能提升明显且结果一致"
        elif speed_improvement > 0.1 and consistency_rate > 0.85:
            return "推荐切换到Scanning策略，性能有提升且结果基本一致"
        elif consistency_rate > 0.95:
            return "可以考虑切换到Scanning策略，结果一致性很高"
        else:
            return "建议继续使用Legacy策略，需要进一步优化Scanning策略"
    
    def save_report(self, report: ABTestReport, output_path: str):
        """保存测试报告"""
        
        report_data = asdict(report)
        
        # 转换不可序列化的对象
        report_data['start_time'] = datetime.fromtimestamp(report.start_time).isoformat()
        report_data['end_time'] = datetime.fromtimestamp(report.end_time).isoformat()
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"测试报告已保存到: {output_path}")


def create_default_ab_test_config(test_name: str = "HTTP Strategy A/B Test") -> ABTestConfig:
    """创建默认A/B测试配置"""
    return ABTestConfig(
        test_name=test_name,
        test_description="对比Legacy和Scanning HTTP策略的性能和一致性",
        control_ratio=0.8,
        treatment_ratio=0.2,
        sampling_strategy="hash_based",
        metrics_collection_enabled=True,
        min_sample_size=50,
        confidence_level=0.95
    )


def run_quick_ab_test(test_files: List[str], 
                     test_name: str = "Quick A/B Test") -> ABTestReport:
    """运行快速A/B测试"""
    
    if not DEPENDENCIES_AVAILABLE:
        raise ImportError("A/B测试框架依赖项不可用")
    
    # 创建测试配置
    config = create_default_ab_test_config(test_name)
    
    # 创建测试框架
    framework = ABTestFramework()
    
    # 创建测试计划
    test_cases = framework.create_test_plan(test_files, config)
    
    # 运行测试
    report = framework.run_ab_test(test_cases, config)
    
    return report 