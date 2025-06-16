"""
A/B测试自动化报告系统

生成详细的双策略A/B测试分析报告，包括统计分析、可视化数据和决策建议。

作者: PktMask Team
创建时间: 2025-06-16
版本: 1.0.0
"""

import json
import time
import statistics
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
import logging
from datetime import datetime, timedelta
from collections import defaultdict


@dataclass
class ABTestMetrics:
    """A/B测试指标"""
    
    # 基础指标
    total_samples: int
    control_samples: int
    treatment_samples: int
    
    # 性能指标
    control_avg_time: float
    treatment_avg_time: float
    control_success_rate: float
    treatment_success_rate: float
    
    # 质量指标
    control_avg_accuracy: float
    treatment_avg_accuracy: float
    control_error_rate: float
    treatment_error_rate: float
    
    # 统计分析
    time_improvement: float
    time_improvement_pvalue: float
    success_rate_delta: float
    accuracy_delta: float
    
    # 置信区间
    time_improvement_ci_lower: float
    time_improvement_ci_upper: float
    success_rate_ci_lower: float
    success_rate_ci_upper: float


@dataclass
class ABTestConclusion:
    """A/B测试结论"""
    
    # 结论状态
    is_significant: bool
    confidence_level: float
    recommendation: str  # "adopt", "reject", "continue_testing"
    
    # 风险评估
    risk_level: str  # "low", "medium", "high"
    risk_factors: List[str]
    
    # 部署建议
    deployment_strategy: str
    rollout_percentage: float
    monitoring_requirements: List[str]
    
    # 额外考虑
    business_impact: str
    technical_considerations: List[str]
    next_steps: List[str]


@dataclass
class ABTestReport:
    """完整A/B测试报告"""
    
    # 报告元信息
    report_id: str
    generated_at: float
    test_duration_days: float
    
    # 测试配置
    test_name: str
    test_description: str
    control_strategy: str
    treatment_strategy: str
    
    # 指标分析
    metrics: ABTestMetrics
    
    # 趋势分析
    daily_metrics: List[Dict[str, Any]]
    performance_trends: Dict[str, float]
    
    # 结论和建议
    conclusion: ABTestConclusion
    
    # 详细数据
    raw_data_summary: Dict[str, Any]
    quality_checks: Dict[str, bool]


class ABTestAnalyzer:
    """A/B测试分析器"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化分析器
        
        Args:
            config: 配置参数
        """
        self.config = config or {}
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        
        # 统计配置
        self.confidence_level = self.config.get('confidence_level', 0.95)
        self.min_sample_size = self.config.get('min_sample_size', 100)
        self.significance_threshold = self.config.get('significance_threshold', 0.05)
        
        self.logger.info("A/B测试分析器初始化完成")
    
    def analyze_ab_test_data(self, comparison_data: List[Dict[str, Any]], 
                           test_config: Dict[str, Any]) -> ABTestReport:
        """
        分析A/B测试数据
        
        Args:
            comparison_data: 对比数据列表
            test_config: 测试配置
            
        Returns:
            A/B测试报告
        """
        self.logger.info(f"开始分析A/B测试数据: {len(comparison_data)}个样本")
        
        # 数据预处理和分组
        control_data, treatment_data = self._group_data_by_strategy(comparison_data)
        
        if len(control_data) < self.min_sample_size or len(treatment_data) < self.min_sample_size:
            self.logger.warning(f"样本量不足: Control={len(control_data)}, Treatment={len(treatment_data)}")
        
        # 计算基础指标
        metrics = self._calculate_metrics(control_data, treatment_data)
        
        # 趋势分析
        daily_metrics = self._analyze_daily_trends(comparison_data)
        performance_trends = self._calculate_performance_trends(daily_metrics)
        
        # 生成结论
        conclusion = self._generate_conclusion(metrics, test_config)
        
        # 质量检查
        quality_checks = self._perform_quality_checks(control_data, treatment_data)
        
        # 生成报告
        report = ABTestReport(
            report_id=f"ab_test_{int(time.time())}",
            generated_at=time.time(),
            test_duration_days=self._calculate_test_duration(comparison_data),
            test_name=test_config.get('test_name', 'HTTP策略A/B测试'),
            test_description=test_config.get('test_description', '双策略性能对比测试'),
            control_strategy=test_config.get('control_strategy', 'Legacy HTTPTrimStrategy'),
            treatment_strategy=test_config.get('treatment_strategy', 'HTTPScanningStrategy'),
            metrics=metrics,
            daily_metrics=daily_metrics,
            performance_trends=performance_trends,
            conclusion=conclusion,
            raw_data_summary=self._generate_data_summary(comparison_data),
            quality_checks=quality_checks
        )
        
        self.logger.info(f"A/B测试分析完成: {conclusion.recommendation}")
        return report
    
    def _group_data_by_strategy(self, comparison_data: List[Dict[str, Any]]) -> Tuple[List[Dict], List[Dict]]:
        """按策略分组数据"""
        
        control_data = []
        treatment_data = []
        
        for data in comparison_data:
            # 根据选中的策略或结果特征分组
            selected_strategy = data.get('selected_strategy', 'legacy')
            
            if selected_strategy == 'legacy':
                control_data.append(data.get('legacy_result', {}))
            elif selected_strategy == 'scanning':
                treatment_data.append(data.get('scanning_result', {}))
            else:
                # 如果有同时运行的数据，分别加入两组
                if 'legacy_result' in data:
                    control_data.append(data['legacy_result'])
                if 'scanning_result' in data:
                    treatment_data.append(data['scanning_result'])
        
        return control_data, treatment_data
    
    def _calculate_metrics(self, control_data: List[Dict], treatment_data: List[Dict]) -> ABTestMetrics:
        """计算A/B测试指标"""
        
        # 基础样本数
        control_samples = len(control_data)
        treatment_samples = len(treatment_data)
        total_samples = control_samples + treatment_samples
        
        # 提取性能数据
        control_times = [d.get('duration_ms', 0) for d in control_data if d.get('success', False)]
        treatment_times = [d.get('duration_ms', 0) for d in treatment_data if d.get('success', False)]
        
        # 成功率
        control_success_rate = sum(1 for d in control_data if d.get('success', False)) / max(control_samples, 1)
        treatment_success_rate = sum(1 for d in treatment_data if d.get('success', False)) / max(treatment_samples, 1)
        
        # 平均处理时间
        control_avg_time = statistics.mean(control_times) if control_times else 0
        treatment_avg_time = statistics.mean(treatment_times) if treatment_times else 0
        
        # 准确性（基于保留字节数的一致性）
        control_accuracy = self._calculate_accuracy(control_data)
        treatment_accuracy = self._calculate_accuracy(treatment_data)
        
        # 错误率
        control_error_rate = 1 - control_success_rate
        treatment_error_rate = 1 - treatment_success_rate
        
        # 性能改进
        time_improvement = ((control_avg_time - treatment_avg_time) / control_avg_time 
                          if control_avg_time > 0 else 0)
        
        # 统计显著性检验
        time_improvement_pvalue = self._calculate_pvalue(control_times, treatment_times)
        
        # 差异计算
        success_rate_delta = treatment_success_rate - control_success_rate
        accuracy_delta = treatment_accuracy - control_accuracy
        
        # 置信区间
        time_ci_lower, time_ci_upper = self._calculate_confidence_interval(
            control_times, treatment_times, 'time_improvement'
        )
        success_ci_lower, success_ci_upper = self._calculate_confidence_interval(
            [1 if d.get('success', False) else 0 for d in control_data],
            [1 if d.get('success', False) else 0 for d in treatment_data],
            'success_rate'
        )
        
        return ABTestMetrics(
            total_samples=total_samples,
            control_samples=control_samples,
            treatment_samples=treatment_samples,
            control_avg_time=control_avg_time,
            treatment_avg_time=treatment_avg_time,
            control_success_rate=control_success_rate,
            treatment_success_rate=treatment_success_rate,
            control_avg_accuracy=control_accuracy,
            treatment_avg_accuracy=treatment_accuracy,
            control_error_rate=control_error_rate,
            treatment_error_rate=treatment_error_rate,
            time_improvement=time_improvement,
            time_improvement_pvalue=time_improvement_pvalue,
            success_rate_delta=success_rate_delta,
            accuracy_delta=accuracy_delta,
            time_improvement_ci_lower=time_ci_lower,
            time_improvement_ci_upper=time_ci_upper,
            success_rate_ci_lower=success_ci_lower,
            success_rate_ci_upper=success_ci_upper
        )
    
    def _calculate_accuracy(self, data: List[Dict]) -> float:
        """计算策略准确性"""
        if not data:
            return 0.0
        
        # 简化的准确性计算：基于成功的分析结果
        accurate_results = 0
        total_results = 0
        
        for d in data:
            if d.get('success', False):
                analysis = d.get('analysis', {})
                # 如果有合理的头部边界，认为是准确的
                if analysis.get('header_boundary', 0) > 0:
                    accurate_results += 1
                total_results += 1
        
        return accurate_results / max(total_results, 1)
    
    def _calculate_pvalue(self, control_data: List[float], treatment_data: List[float]) -> float:
        """计算统计显著性p值（简化版t检验）"""
        
        if len(control_data) < 2 or len(treatment_data) < 2:
            return 1.0  # 无足够数据
        
        try:
            # 简化的t检验
            control_mean = statistics.mean(control_data)
            treatment_mean = statistics.mean(treatment_data)
            
            control_var = statistics.variance(control_data)
            treatment_var = statistics.variance(treatment_data)
            
            # 合并方差
            pooled_var = ((len(control_data) - 1) * control_var + 
                         (len(treatment_data) - 1) * treatment_var) / (
                         len(control_data) + len(treatment_data) - 2)
            
            # 标准误差
            se = (pooled_var * (1/len(control_data) + 1/len(treatment_data))) ** 0.5
            
            if se == 0:
                return 1.0
            
            # t统计量
            t_stat = abs(control_mean - treatment_mean) / se
            
            # 简化的p值估算
            if t_stat > 2.576:  # 99%置信水平
                return 0.01
            elif t_stat > 1.96:  # 95%置信水平
                return 0.05
            elif t_stat > 1.645:  # 90%置信水平
                return 0.10
            else:
                return 0.5
                
        except Exception as e:
            self.logger.warning(f"p值计算失败: {e}")
            return 1.0
    
    def _calculate_confidence_interval(self, control_data: List[float], 
                                     treatment_data: List[float], 
                                     metric_type: str) -> Tuple[float, float]:
        """计算置信区间"""
        
        if len(control_data) < 2 or len(treatment_data) < 2:
            return 0.0, 0.0
        
        try:
            if metric_type == 'time_improvement':
                control_mean = statistics.mean(control_data)
                treatment_mean = statistics.mean(treatment_data)
                improvement = (control_mean - treatment_mean) / control_mean if control_mean > 0 else 0
                
                # 简化的标准误差估算
                control_se = statistics.stdev(control_data) / (len(control_data) ** 0.5)
                treatment_se = statistics.stdev(treatment_data) / (len(treatment_data) ** 0.5)
                
                improvement_se = ((control_se/control_mean)**2 + (treatment_se/treatment_mean)**2)**0.5 if control_mean > 0 and treatment_mean > 0 else 0.1
                
                margin = 1.96 * improvement_se  # 95%置信水平
                return improvement - margin, improvement + margin
                
            elif metric_type == 'success_rate':
                control_rate = statistics.mean(control_data)
                treatment_rate = statistics.mean(treatment_data)
                rate_diff = treatment_rate - control_rate
                
                # 成功率差异的标准误差
                control_se = (control_rate * (1 - control_rate) / len(control_data)) ** 0.5
                treatment_se = (treatment_rate * (1 - treatment_rate) / len(treatment_data)) ** 0.5
                diff_se = (control_se**2 + treatment_se**2) ** 0.5
                
                margin = 1.96 * diff_se
                return rate_diff - margin, rate_diff + margin
                
        except Exception as e:
            self.logger.warning(f"置信区间计算失败: {e}")
        
        return 0.0, 0.0
    
    def _analyze_daily_trends(self, comparison_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """分析每日趋势"""
        
        # 按日期分组数据
        daily_data = defaultdict(list)
        
        for data in comparison_data:
            timestamp = data.get('comparison_metadata', {}).get('timestamp', time.time())
            date_key = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')
            daily_data[date_key].append(data)
        
        # 计算每日指标
        daily_metrics = []
        
        for date, day_data in sorted(daily_data.items()):
            control_data, treatment_data = self._group_data_by_strategy(day_data)
            
            # 计算当日指标
            control_avg_time = statistics.mean([d.get('duration_ms', 0) for d in control_data if d.get('success', False)]) if control_data else 0
            treatment_avg_time = statistics.mean([d.get('duration_ms', 0) for d in treatment_data if d.get('success', False)]) if treatment_data else 0
            
            control_success_rate = sum(1 for d in control_data if d.get('success', False)) / max(len(control_data), 1)
            treatment_success_rate = sum(1 for d in treatment_data if d.get('success', False)) / max(len(treatment_data), 1)
            
            daily_metrics.append({
                'date': date,
                'control_samples': len(control_data),
                'treatment_samples': len(treatment_data),
                'control_avg_time': control_avg_time,
                'treatment_avg_time': treatment_avg_time,
                'control_success_rate': control_success_rate,
                'treatment_success_rate': treatment_success_rate,
                'time_improvement': ((control_avg_time - treatment_avg_time) / control_avg_time 
                                   if control_avg_time > 0 else 0)
            })
        
        return daily_metrics
    
    def _calculate_performance_trends(self, daily_metrics: List[Dict[str, Any]]) -> Dict[str, float]:
        """计算性能趋势"""
        
        if len(daily_metrics) < 2:
            return {}
        
        # 提取时间序列数据
        time_improvements = [d['time_improvement'] for d in daily_metrics]
        control_success_rates = [d['control_success_rate'] for d in daily_metrics]
        treatment_success_rates = [d['treatment_success_rate'] for d in daily_metrics]
        
        # 计算趋势（简单线性趋势）
        n = len(daily_metrics)
        mid_point = n // 2
        
        first_half_time = statistics.mean(time_improvements[:mid_point])
        second_half_time = statistics.mean(time_improvements[mid_point:])
        
        first_half_control_success = statistics.mean(control_success_rates[:mid_point])
        second_half_control_success = statistics.mean(control_success_rates[mid_point:])
        
        first_half_treatment_success = statistics.mean(treatment_success_rates[:mid_point])
        second_half_treatment_success = statistics.mean(treatment_success_rates[mid_point:])
        
        return {
            'time_improvement_trend': second_half_time - first_half_time,
            'control_success_trend': second_half_control_success - first_half_control_success,
            'treatment_success_trend': second_half_treatment_success - first_half_treatment_success,
            'stability_score': 1.0 - statistics.stdev(time_improvements) if len(time_improvements) > 1 else 1.0
        }
    
    def _generate_conclusion(self, metrics: ABTestMetrics, test_config: Dict[str, Any]) -> ABTestConclusion:
        """生成测试结论"""
        
        # 统计显著性判断
        is_significant = (metrics.time_improvement_pvalue < self.significance_threshold and
                         metrics.total_samples >= self.min_sample_size)
        
        # 实际改进判断
        meaningful_improvement = (metrics.time_improvement > 0.1 and  # 10%改进
                                metrics.success_rate_delta > -0.05)  # 成功率不大幅下降
        
        # 风险评估
        risk_factors = []
        if metrics.treatment_success_rate < 0.9:
            risk_factors.append("Treatment策略成功率较低")
        if metrics.accuracy_delta < -0.1:
            risk_factors.append("准确性显著下降")
        if abs(metrics.success_rate_delta) > 0.1:
            risk_factors.append("成功率变化较大")
        
        risk_level = "high" if len(risk_factors) > 2 else "medium" if len(risk_factors) > 0 else "low"
        
        # 生成建议
        if is_significant and meaningful_improvement and risk_level == "low":
            recommendation = "adopt"
            deployment_strategy = "gradual_rollout"
            rollout_percentage = 0.25  # 25%开始
        elif is_significant and meaningful_improvement and risk_level == "medium":
            recommendation = "adopt"
            deployment_strategy = "cautious_rollout"
            rollout_percentage = 0.1   # 10%开始
        elif not is_significant or not meaningful_improvement:
            recommendation = "continue_testing"
            deployment_strategy = "extended_testing"
            rollout_percentage = 0.05  # 5%继续测试
        else:
            recommendation = "reject"
            deployment_strategy = "maintain_current"
            rollout_percentage = 0.0
        
        # 监控要求
        monitoring_requirements = [
            "实时性能监控",
            "错误率监控",
            "用户反馈收集"
        ]
        
        if risk_level != "low":
            monitoring_requirements.extend([
                "详细日志记录",
                "A/B测试结果跟踪",
                "回滚准备"
            ])
        
        # 业务影响评估
        if metrics.time_improvement > 0.2:
            business_impact = "显著的性能提升，预期用户体验改善"
        elif metrics.time_improvement > 0.1:
            business_impact = "适度的性能提升，系统效率改善"
        elif metrics.time_improvement > 0:
            business_impact = "轻微的性能提升，维护性改善"
        else:
            business_impact = "无明显性能改善，需要进一步优化"
        
        # 技术考虑
        technical_considerations = [
            "代码复杂度降低",
            "维护成本优化",
            "系统稳定性验证"
        ]
        
        # 下一步行动
        if recommendation == "adopt":
            next_steps = [
                f"开始{rollout_percentage:.0%}流量的渐进部署",
                "建立详细监控系统",
                "制定回滚计划",
                "培训运维团队"
            ]
        elif recommendation == "continue_testing":
            next_steps = [
                "延长A/B测试周期",
                "增加样本量",
                "优化Treatment策略",
                "分析失败案例"
            ]
        else:
            next_steps = [
                "分析失败原因",
                "优化算法实现",
                "重新设计测试",
                "保持现有策略"
            ]
        
        return ABTestConclusion(
            is_significant=is_significant,
            confidence_level=self.confidence_level,
            recommendation=recommendation,
            risk_level=risk_level,
            risk_factors=risk_factors,
            deployment_strategy=deployment_strategy,
            rollout_percentage=rollout_percentage,
            monitoring_requirements=monitoring_requirements,
            business_impact=business_impact,
            technical_considerations=technical_considerations,
            next_steps=next_steps
        )
    
    def _perform_quality_checks(self, control_data: List[Dict], treatment_data: List[Dict]) -> Dict[str, bool]:
        """执行数据质量检查"""
        
        checks = {}
        
        # 样本量检查
        checks['adequate_sample_size'] = (len(control_data) >= self.min_sample_size and 
                                        len(treatment_data) >= self.min_sample_size)
        
        # 样本平衡检查
        sample_ratio = min(len(control_data), len(treatment_data)) / max(len(control_data), len(treatment_data))
        checks['balanced_samples'] = sample_ratio >= 0.8
        
        # 数据完整性检查
        control_complete = sum(1 for d in control_data if d.get('success') is not None)
        treatment_complete = sum(1 for d in treatment_data if d.get('success') is not None)
        
        checks['data_completeness'] = (control_complete / max(len(control_data), 1) >= 0.95 and
                                     treatment_complete / max(len(treatment_data), 1) >= 0.95)
        
        # 异常值检查
        control_times = [d.get('duration_ms', 0) for d in control_data if d.get('success', False)]
        treatment_times = [d.get('duration_ms', 0) for d in treatment_data if d.get('success', False)]
        
        checks['no_extreme_outliers'] = (
            (not control_times or max(control_times) < statistics.mean(control_times) * 10) and
            (not treatment_times or max(treatment_times) < statistics.mean(treatment_times) * 10)
        )
        
        return checks
    
    def _calculate_test_duration(self, comparison_data: List[Dict[str, Any]]) -> float:
        """计算测试持续时间（天）"""
        
        if not comparison_data:
            return 0.0
        
        timestamps = []
        for data in comparison_data:
            timestamp = data.get('comparison_metadata', {}).get('timestamp')
            if timestamp:
                timestamps.append(timestamp)
        
        if len(timestamps) < 2:
            return 0.0
        
        duration_seconds = max(timestamps) - min(timestamps)
        return duration_seconds / (24 * 3600)  # 转换为天
    
    def _generate_data_summary(self, comparison_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """生成原始数据摘要"""
        
        return {
            'total_records': len(comparison_data),
            'time_range': {
                'start': min(d.get('comparison_metadata', {}).get('timestamp', 0) for d in comparison_data) if comparison_data else 0,
                'end': max(d.get('comparison_metadata', {}).get('timestamp', 0) for d in comparison_data) if comparison_data else 0
            },
            'payload_size_distribution': self._analyze_payload_sizes(comparison_data),
            'file_types_processed': self._analyze_file_types(comparison_data)
        }
    
    def _analyze_payload_sizes(self, comparison_data: List[Dict[str, Any]]) -> Dict[str, int]:
        """分析载荷大小分布"""
        
        size_buckets = {'small': 0, 'medium': 0, 'large': 0, 'xlarge': 0}
        
        for data in comparison_data:
            size = data.get('comparison_metadata', {}).get('payload_size', 0)
            
            if size < 1024:
                size_buckets['small'] += 1
            elif size < 10240:
                size_buckets['medium'] += 1
            elif size < 102400:
                size_buckets['large'] += 1
            else:
                size_buckets['xlarge'] += 1
        
        return size_buckets
    
    def _analyze_file_types(self, comparison_data: List[Dict[str, Any]]) -> Dict[str, int]:
        """分析文件类型分布"""
        
        file_types = defaultdict(int)
        
        for data in comparison_data:
            file_path = data.get('comparison_metadata', {}).get('file_path', '')
            if file_path:
                # 简单的文件类型识别
                if 'http' in file_path.lower():
                    file_types['HTTP'] += 1
                elif 'tls' in file_path.lower():
                    file_types['TLS'] += 1
                elif 'chunked' in file_path.lower():
                    file_types['Chunked'] += 1
                else:
                    file_types['Other'] += 1
        
        return dict(file_types)


class ABTestReportGenerator:
    """A/B测试报告生成器"""
    
    def __init__(self, output_dir: Path = None):
        """
        初始化报告生成器
        
        Args:
            output_dir: 输出目录
        """
        self.output_dir = output_dir or Path('reports/ab_tests')
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        self.analyzer = ABTestAnalyzer()
    
    def generate_report(self, comparison_data: List[Dict[str, Any]], 
                       test_config: Dict[str, Any]) -> Path:
        """
        生成完整的A/B测试报告
        
        Args:
            comparison_data: 对比数据
            test_config: 测试配置
            
        Returns:
            报告文件路径
        """
        self.logger.info("开始生成A/B测试报告")
        
        # 分析数据
        report = self.analyzer.analyze_ab_test_data(comparison_data, test_config)
        
        # 生成JSON报告
        json_report = self._generate_json_report(report)
        
        # 保存报告
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_filename = f"ab_test_report_{timestamp}.json"
        report_path = self.output_dir / report_filename
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(json_report, f, indent=2, ensure_ascii=False)
        
        # 生成文本摘要
        summary_path = self._generate_text_summary(report, report_path.with_suffix('.txt'))
        
        self.logger.info(f"A/B测试报告已生成: {report_path}")
        self.logger.info(f"报告摘要: {summary_path}")
        
        return report_path
    
    def _generate_json_report(self, report: ABTestReport) -> Dict[str, Any]:
        """生成JSON格式报告"""
        
        return {
            'metadata': {
                'report_id': report.report_id,
                'generated_at': report.generated_at,
                'generated_at_human': datetime.fromtimestamp(report.generated_at).strftime("%Y-%m-%d %H:%M:%S"),
                'test_duration_days': report.test_duration_days,
                'report_version': '1.0.0'
            },
            'test_configuration': {
                'test_name': report.test_name,
                'test_description': report.test_description,
                'control_strategy': report.control_strategy,
                'treatment_strategy': report.treatment_strategy
            },
            'metrics': asdict(report.metrics),
            'trends': {
                'daily_metrics': report.daily_metrics,
                'performance_trends': report.performance_trends
            },
            'conclusion': asdict(report.conclusion),
            'data_quality': {
                'raw_data_summary': report.raw_data_summary,
                'quality_checks': report.quality_checks
            }
        }
    
    def _generate_text_summary(self, report: ABTestReport, output_path: Path) -> Path:
        """生成文本摘要报告"""
        
        summary_lines = [
            f"A/B测试报告摘要",
            f"=" * 50,
            f"",
            f"测试名称: {report.test_name}",
            f"测试描述: {report.test_description}",
            f"测试时长: {report.test_duration_days:.1f} 天",
            f"生成时间: {datetime.fromtimestamp(report.generated_at).strftime('%Y-%m-%d %H:%M:%S')}",
            f"",
            f"样本统计",
            f"-" * 20,
            f"总样本数: {report.metrics.total_samples}",
            f"控制组样本: {report.metrics.control_samples}",
            f"实验组样本: {report.metrics.treatment_samples}",
            f"",
            f"关键指标",
            f"-" * 20,
            f"平均处理时间改善: {report.metrics.time_improvement:.1%}",
            f"成功率变化: {report.metrics.success_rate_delta:.1%}",
            f"准确性变化: {report.metrics.accuracy_delta:.1%}",
            f"统计显著性: {'是' if report.conclusion.is_significant else '否'} (p={report.metrics.time_improvement_pvalue:.3f})",
            f"",
            f"结论和建议",
            f"-" * 20,
            f"建议: {report.conclusion.recommendation}",
            f"风险等级: {report.conclusion.risk_level}",
            f"部署策略: {report.conclusion.deployment_strategy}",
            f"建议流量比例: {report.conclusion.rollout_percentage:.0%}",
            f"",
            f"业务影响: {report.conclusion.business_impact}",
            f"",
            f"风险因素:",
        ]
        
        for factor in report.conclusion.risk_factors:
            summary_lines.append(f"  - {factor}")
        
        summary_lines.extend([
            f"",
            f"下一步行动:",
        ])
        
        for step in report.conclusion.next_steps:
            summary_lines.append(f"  - {step}")
        
        summary_lines.extend([
            f"",
            f"监控要求:",
        ])
        
        for requirement in report.conclusion.monitoring_requirements:
            summary_lines.append(f"  - {requirement}")
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(summary_lines))
        
        return output_path 