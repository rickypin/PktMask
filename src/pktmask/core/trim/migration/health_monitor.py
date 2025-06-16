"""
健康监控系统

提供双策略迁移过程中的实时健康监控、告警和自动回退功能。
"""

import logging
import time
import psutil
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from .migration_models import (
    MigrationMetrics, MigrationState, HealthStatus, 
    MigrationPhase, PhaseConfig
)


@dataclass
class HealthAlert:
    """健康告警"""
    severity: str  # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    metrics: Dict[str, Any] = field(default_factory=dict)
    recommended_actions: List[str] = field(default_factory=list)
    acknowledged: bool = False
    
    def acknowledge(self, operator: str, notes: str = ""):
        """确认告警"""
        self.acknowledged = True
        self.metrics['acknowledged_by'] = operator
        self.metrics['acknowledged_at'] = datetime.now().isoformat()
        if notes:
            self.metrics['acknowledgment_notes'] = notes


@dataclass
class HealthReport:
    """健康报告"""
    timestamp: datetime = field(default_factory=datetime.now)
    overall_health_score: float = 0.0
    health_status: HealthStatus = HealthStatus.UNKNOWN
    
    # 分维度健康指标
    strategy_selection_health: float = 0.0
    performance_health: float = 0.0
    error_rate_health: float = 0.0
    resource_usage_health: float = 0.0
    business_metrics_health: float = 0.0
    
    # 详细指标
    metrics: MigrationMetrics = field(default_factory=MigrationMetrics)
    
    # 告警信息
    alerts: List[HealthAlert] = field(default_factory=list)
    
    # 趋势信息
    trend_data: Dict[str, List[float]] = field(default_factory=dict)
    
    def get_health_summary(self) -> Dict[str, Any]:
        """获取健康状态摘要"""
        return {
            'overall_score': self.overall_health_score,
            'status': self.health_status.value,
            'timestamp': self.timestamp.isoformat(),
            'dimensions': {
                'strategy_selection': self.strategy_selection_health,
                'performance': self.performance_health,
                'error_rate': self.error_rate_health,
                'resource_usage': self.resource_usage_health,
                'business_metrics': self.business_metrics_health
            },
            'active_alerts': len([a for a in self.alerts if not a.acknowledged]),
            'recommendations': [
                alert.recommended_actions for alert in self.alerts 
                if not alert.acknowledged and alert.recommended_actions
            ]
        }


class HealthMonitor:
    """健康监控器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # 监控配置
        self.health_check_interval = config.get('health_check_interval_seconds', 300)
        self.metrics_retention_days = config.get('metrics_retention_days', 30)
        
        # 告警阈值
        self.alert_thresholds = config.get('alert_thresholds', {
            'health_score_warning': 0.8,
            'health_score_critical': 0.6,
            'error_rate_warning': 0.02,
            'error_rate_critical': 0.05,
            'response_time_warning': 100.0,  # ms
            'response_time_critical': 200.0,  # ms
            'memory_usage_warning': 1000.0,  # MB
            'memory_usage_critical': 2000.0,  # MB
        })
        
        # 历史数据存储
        self.metrics_history: List[MigrationMetrics] = []
        self.health_history: List[HealthReport] = []
        self.alert_history: List[HealthAlert] = []
        
        # 回调函数
        self.alert_callbacks: List[Callable[[HealthAlert], None]] = []
        
        # 最后检查时间
        self.last_health_check: Optional[datetime] = None
        
    def register_alert_callback(self, callback: Callable[[HealthAlert], None]):
        """注册告警回调函数"""
        self.alert_callbacks.append(callback)
    
    def collect_current_metrics(self, migration_state: MigrationState) -> MigrationMetrics:
        """收集当前指标"""
        # 这里需要从实际运行的策略工厂获取指标
        # 为了示例，我们提供一个基础实现
        metrics = MigrationMetrics(
            timestamp=time.time(),
            phase=migration_state.current_phase
        )
        
        # 获取系统资源使用情况
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            metrics.memory_usage_mb = memory_info.rss / 1024 / 1024
            metrics.cpu_usage_percent = process.cpu_percent()
        except Exception as e:
            self.logger.warning(f"获取系统资源信息失败: {e}")
        
        # TODO: 集成实际的策略使用统计
        # 这需要与StrategyFactory的ComparisonWrapper集成
        
        return metrics
    
    def analyze_strategy_selection_health(self, metrics: MigrationMetrics) -> float:
        """分析策略选择健康度"""
        if metrics.total_requests == 0:
            return 1.0  # 没有请求时认为健康
        
        # 检查回退比例
        fallback_ratio = metrics.get_fallback_ratio()
        if fallback_ratio > 0.1:  # 回退比例超过10%
            return 0.3
        elif fallback_ratio > 0.05:  # 回退比例超过5%
            return 0.7
        
        return 1.0
    
    def analyze_performance_health(self, metrics: MigrationMetrics) -> float:
        """分析性能健康度"""
        if metrics.avg_processing_time_ms == 0:
            return 1.0
        
        # 检查响应时间
        warning_threshold = self.alert_thresholds['response_time_warning']
        critical_threshold = self.alert_thresholds['response_time_critical']
        
        if metrics.avg_processing_time_ms > critical_threshold:
            return 0.2
        elif metrics.avg_processing_time_ms > warning_threshold:
            return 0.6
        
        return 1.0
    
    def analyze_error_rate_health(self, metrics: MigrationMetrics) -> float:
        """分析错误率健康度"""
        error_rate = metrics.overall_error_rate
        
        warning_threshold = self.alert_thresholds['error_rate_warning']
        critical_threshold = self.alert_thresholds['error_rate_critical']
        
        if error_rate > critical_threshold:
            return 0.1
        elif error_rate > warning_threshold:
            return 0.5
        
        return 1.0
    
    def analyze_resource_usage_health(self, metrics: MigrationMetrics) -> float:
        """分析资源使用健康度"""
        memory_warning = self.alert_thresholds['memory_usage_warning']
        memory_critical = self.alert_thresholds['memory_usage_critical']
        
        memory_score = 1.0
        if metrics.memory_usage_mb > memory_critical:
            memory_score = 0.2
        elif metrics.memory_usage_mb > memory_warning:
            memory_score = 0.6
        
        cpu_score = 1.0
        if metrics.cpu_usage_percent > 90:
            cpu_score = 0.2
        elif metrics.cpu_usage_percent > 70:
            cpu_score = 0.6
        
        return min(memory_score, cpu_score)
    
    def analyze_business_metrics_health(self, metrics: MigrationMetrics) -> float:
        """分析业务指标健康度"""
        # 基于吞吐量变化进行评估
        if metrics.throughput_pps < 10:  # 吞吐量过低
            return 0.5
        
        return 1.0
    
    def generate_health_alerts(self, report: HealthReport) -> List[HealthAlert]:
        """生成健康告警"""
        alerts = []
        
        # 整体健康分数告警
        if report.overall_health_score < self.alert_thresholds['health_score_critical']:
            alerts.append(HealthAlert(
                severity="CRITICAL",
                message=f"系统健康分数严重过低: {report.overall_health_score:.2f}",
                metrics={'health_score': report.overall_health_score},
                recommended_actions=[
                    "立即检查错误日志",
                    "考虑回退到Legacy策略",
                    "联系技术支持团队"
                ]
            ))
        elif report.overall_health_score < self.alert_thresholds['health_score_warning']:
            alerts.append(HealthAlert(
                severity="HIGH",
                message=f"系统健康分数过低: {report.overall_health_score:.2f}",
                metrics={'health_score': report.overall_health_score},
                recommended_actions=[
                    "检查系统负载",
                    "审查最近的配置变更",
                    "准备回退计划"
                ]
            ))
        
        # 错误率告警
        if report.metrics.overall_error_rate > self.alert_thresholds['error_rate_critical']:
            alerts.append(HealthAlert(
                severity="CRITICAL",
                message=f"错误率过高: {report.metrics.overall_error_rate:.1%}",
                metrics={'error_rate': report.metrics.overall_error_rate},
                recommended_actions=[
                    "立即回退到Legacy策略",
                    "分析错误日志",
                    "暂停A/B测试"
                ]
            ))
        
        # 性能告警
        if report.metrics.avg_processing_time_ms > self.alert_thresholds['response_time_critical']:
            alerts.append(HealthAlert(
                severity="HIGH",
                message=f"响应时间过长: {report.metrics.avg_processing_time_ms:.1f}ms",
                metrics={'response_time_ms': report.metrics.avg_processing_time_ms},
                recommended_actions=[
                    "检查系统资源使用",
                    "优化策略配置",
                    "考虑降低A/B测试比例"
                ]
            ))
        
        # 资源使用告警
        if report.metrics.memory_usage_mb > self.alert_thresholds['memory_usage_critical']:
            alerts.append(HealthAlert(
                severity="HIGH",
                message=f"内存使用过高: {report.metrics.memory_usage_mb:.1f}MB",
                metrics={'memory_usage_mb': report.metrics.memory_usage_mb},
                recommended_actions=[
                    "重启应用程序",
                    "检查内存泄漏",
                    "优化策略实现"
                ]
            ))
        
        return alerts
    
    def monitor_dual_strategy_health(self, migration_state: MigrationState) -> HealthReport:
        """监控双策略健康状态"""
        self.logger.info("开始健康检查...")
        
        # 收集当前指标
        current_metrics = self.collect_current_metrics(migration_state)
        self.metrics_history.append(current_metrics)
        
        # 分析各维度健康度
        strategy_health = self.analyze_strategy_selection_health(current_metrics)
        performance_health = self.analyze_performance_health(current_metrics)
        error_health = self.analyze_error_rate_health(current_metrics)
        resource_health = self.analyze_resource_usage_health(current_metrics)
        business_health = self.analyze_business_metrics_health(current_metrics)
        
        # 计算整体健康分数（加权平均）
        weights = {
            'strategy': 0.25,
            'performance': 0.25,
            'error': 0.30,
            'resource': 0.15,
            'business': 0.05
        }
        
        overall_score = (
            strategy_health * weights['strategy'] +
            performance_health * weights['performance'] +
            error_health * weights['error'] +
            resource_health * weights['resource'] +
            business_health * weights['business']
        )
        
        # 确定健康状态
        if overall_score >= 0.8:
            health_status = HealthStatus.HEALTHY
        elif overall_score >= 0.6:
            health_status = HealthStatus.WARNING
        else:
            health_status = HealthStatus.CRITICAL
        
        # 生成健康报告
        health_report = HealthReport(
            overall_health_score=overall_score,
            health_status=health_status,
            strategy_selection_health=strategy_health,
            performance_health=performance_health,
            error_rate_health=error_health,
            resource_usage_health=resource_health,
            business_metrics_health=business_health,
            metrics=current_metrics
        )
        
        # 生成告警
        alerts = self.generate_health_alerts(health_report)
        health_report.alerts = alerts
        
        # 触发告警回调
        for alert in alerts:
            if not alert.acknowledged:
                for callback in self.alert_callbacks:
                    try:
                        callback(alert)
                    except Exception as e:
                        self.logger.error(f"告警回调执行失败: {e}")
        
        # 保存报告
        self.health_history.append(health_report)
        self.alert_history.extend(alerts)
        self.last_health_check = datetime.now()
        
        # 清理历史数据
        self._cleanup_old_data()
        
        self.logger.info(f"健康检查完成，整体得分: {overall_score:.2f}, 状态: {health_status.value}")
        
        return health_report
    
    def _cleanup_old_data(self):
        """清理过期的历史数据"""
        cutoff_time = datetime.now() - timedelta(days=self.metrics_retention_days)
        
        # 清理指标历史
        self.metrics_history = [
            m for m in self.metrics_history 
            if datetime.fromtimestamp(m.timestamp) > cutoff_time
        ]
        
        # 清理健康报告历史
        self.health_history = [
            h for h in self.health_history 
            if h.timestamp > cutoff_time
        ]
        
        # 清理告警历史
        self.alert_history = [
            a for a in self.alert_history 
            if a.timestamp > cutoff_time
        ]
    
    def get_health_trends(self, hours: int = 24) -> Dict[str, List[float]]:
        """获取健康趋势数据"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        recent_reports = [
            r for r in self.health_history 
            if r.timestamp > cutoff_time
        ]
        
        if not recent_reports:
            return {}
        
        return {
            'overall_health': [r.overall_health_score for r in recent_reports],
            'error_rates': [r.metrics.overall_error_rate for r in recent_reports],
            'response_times': [r.metrics.avg_processing_time_ms for r in recent_reports],
            'memory_usage': [r.metrics.memory_usage_mb for r in recent_reports],
            'timestamps': [r.timestamp.timestamp() for r in recent_reports]
        }
    
    def should_trigger_rollback(self, health_report: HealthReport) -> bool:
        """判断是否应该触发自动回退"""
        # 严重健康问题
        if health_report.overall_health_score < 0.3:
            return True
        
        # 严重错误率
        if health_report.metrics.overall_error_rate > 0.1:
            return True
        
        # 连续的健康问题
        if len(self.health_history) >= 3:
            recent_scores = [h.overall_health_score for h in self.health_history[-3:]]
            if all(score < 0.6 for score in recent_scores):
                return True
        
        return False 