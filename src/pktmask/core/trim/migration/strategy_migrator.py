"""
策略迁移管理器

提供5阶段平滑迁移策略：基线验证→小规模A/B测试→渐进推广→完全迁移→Legacy清理
支持自动化迁移管理、健康监控、故障回退等功能。
"""

import logging
import time
import asyncio
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from .migration_models import (
    MigrationState, MigrationPhase, MigrationStatus, 
    HealthStatus, PhaseConfig, MigrationMetrics
)
from .health_monitor import HealthMonitor, HealthReport


@dataclass
class PhaseResult:
    """阶段执行结果"""
    phase: MigrationPhase
    success: bool
    start_time: datetime
    end_time: Optional[datetime] = None
    error: Optional[str] = None
    metrics: Optional[MigrationMetrics] = None
    health_reports: List[HealthReport] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    @classmethod
    def success(cls, phase: MigrationPhase, message: str = "") -> 'PhaseResult':
        """创建成功结果"""
        return cls(
            phase=phase,
            success=True,
            start_time=datetime.now(),
            end_time=datetime.now(),
            warnings=[message] if message else []
        )
    
    @classmethod
    def failure(cls, phase: MigrationPhase, error: str) -> 'PhaseResult':
        """创建失败结果"""
        return cls(
            phase=phase,
            success=False,
            start_time=datetime.now(),
            end_time=datetime.now(),
            error=error
        )
    
    def get_duration(self) -> Optional[float]:
        """获取阶段持续时间（秒）"""
        if not self.end_time:
            return None
        return (self.end_time - self.start_time).total_seconds()


@dataclass
class MigrationResult:
    """迁移执行结果"""
    success: bool
    migration_state: MigrationState
    phase_results: List[PhaseResult] = field(default_factory=list)
    final_health_report: Optional[HealthReport] = None
    rollback_performed: bool = False
    error_message: Optional[str] = None
    
    @classmethod
    def success(cls, state: MigrationState) -> 'MigrationResult':
        """创建成功结果"""
        return cls(success=True, migration_state=state)
    
    @classmethod
    def failure(cls, state: MigrationState, error: str) -> 'MigrationResult':
        """创建失败结果"""
        return cls(
            success=False, 
            migration_state=state,
            error_message=error
        )
    
    def get_total_duration(self) -> Optional[float]:
        """获取总迁移时间（秒）"""
        return self.migration_state.get_migration_duration()


@dataclass
class MigrationPlan:
    """迁移计划"""
    name: str
    description: str
    phase_configs: Dict[MigrationPhase, PhaseConfig] = field(
        default_factory=PhaseConfig.get_default_configs
    )
    
    # 全局配置
    enable_auto_rollback: bool = True
    max_total_duration_hours: float = 168.0  # 7天
    health_check_interval_seconds: int = 300  # 5分钟
    
    # 通知配置
    notification_callbacks: List[Callable[[str], None]] = field(default_factory=list)
    
    def add_notification_callback(self, callback: Callable[[str], None]):
        """添加通知回调"""
        self.notification_callbacks.append(callback)
    
    def get_phase_order(self) -> List[MigrationPhase]:
        """获取阶段执行顺序"""
        return [
            MigrationPhase.PHASE_1_BASELINE,
            MigrationPhase.PHASE_2_SMALL_AB,
            MigrationPhase.PHASE_3_GRADUAL,
            MigrationPhase.PHASE_4_FULL,
            MigrationPhase.PHASE_5_CLEANUP
        ]


class StrategyMigrator:
    """策略迁移管理器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # 迁移状态
        self.migration_state = MigrationState()
        
        # 健康监控器
        self.health_monitor = HealthMonitor(config.get('monitoring', {}))
        
        # 注册健康告警回调
        self.health_monitor.register_alert_callback(self._on_health_alert)
        
        # 迁移历史记录
        self.migration_history: List[MigrationResult] = []
        
        # 是否正在迁移
        self._migration_in_progress = False
        
        # 停止标志
        self._stop_requested = False
        
    def _on_health_alert(self, alert):
        """健康告警回调"""
        self.logger.warning(f"健康告警: {alert.severity} - {alert.message}")
        
        # 如果是严重告警，考虑自动回退
        if alert.severity == "CRITICAL" and self.migration_state.rollback_enabled:
            self.logger.error("检测到严重健康问题，准备自动回退...")
            # 这里可以触发自动回退逻辑
    
    async def execute_migration_plan(self, plan: MigrationPlan) -> MigrationResult:
        """执行迁移计划"""
        if self._migration_in_progress:
            return MigrationResult.failure(
                self.migration_state,
                "迁移已在进行中，不能重复执行"
            )
        
        self._migration_in_progress = True
        self._stop_requested = False
        
        try:
            self.logger.info(f"开始执行迁移计划: {plan.name}")
            
            # 初始化迁移状态
            self.migration_state.start_migration()
            
            # 执行各个阶段
            phase_results = []
            for phase in plan.get_phase_order():
                if self._stop_requested:
                    break
                
                phase_config = plan.phase_configs[phase]
                phase_result = await self._execute_migration_phase(phase, phase_config)
                phase_results.append(phase_result)
                
                if not phase_result.success:
                    # 阶段失败，检查是否需要回退
                    if phase_config.rollback_on_failure and plan.enable_auto_rollback:
                        self.logger.error(f"阶段{phase.value}失败，开始回退...")
                        rollback_result = await self._rollback_migration(
                            f"阶段{phase.value}失败: {phase_result.error}"
                        )
                        return rollback_result
                    else:
                        return MigrationResult.failure(
                            self.migration_state,
                            f"阶段{phase.value}失败: {phase_result.error}"
                        )
                
                # 标记阶段完成
                self.migration_state.complete_phase(phase)
                
                # 发送进度通知
                for callback in plan.notification_callbacks:
                    try:
                        callback(f"阶段{phase.value}完成")
                    except Exception as e:
                        self.logger.error(f"通知回调失败: {e}")
            
            # 完成迁移
            self.migration_state.complete_migration()
            
            # 最终健康检查
            final_health = self.health_monitor.monitor_dual_strategy_health(
                self.migration_state
            )
            
            result = MigrationResult.success(self.migration_state)
            result.phase_results = phase_results
            result.final_health_report = final_health
            
            self.migration_history.append(result)
            
            self.logger.info("迁移计划执行完成")
            return result
            
        except Exception as e:
            self.logger.error(f"迁移执行异常: {e}")
            return MigrationResult.failure(self.migration_state, str(e))
        
        finally:
            self._migration_in_progress = False
    
    async def _execute_migration_phase(self, phase: MigrationPhase, 
                                     config: PhaseConfig) -> PhaseResult:
        """执行单个迁移阶段"""
        self.logger.info(f"开始执行阶段: {phase.value}")
        
        self.migration_state.current_phase = phase
        self.migration_state.current_phase_start = datetime.now()
        
        start_time = datetime.now()
        
        try:
            # 根据阶段类型执行不同逻辑
            if phase == MigrationPhase.PHASE_1_BASELINE:
                return await self._phase_1_baseline_validation(config)
            elif phase == MigrationPhase.PHASE_2_SMALL_AB:
                return await self._phase_2_small_scale_ab_test(config)
            elif phase == MigrationPhase.PHASE_3_GRADUAL:
                return await self._phase_3_gradual_rollout(config)
            elif phase == MigrationPhase.PHASE_4_FULL:
                return await self._phase_4_full_migration(config)
            elif phase == MigrationPhase.PHASE_5_CLEANUP:
                return await self._phase_5_legacy_cleanup(config)
            else:
                return PhaseResult.failure(phase, f"未知阶段: {phase}")
                
        except Exception as e:
            self.logger.error(f"阶段{phase.value}执行异常: {e}")
            return PhaseResult.failure(phase, str(e))
    
    async def _phase_1_baseline_validation(self, config: PhaseConfig) -> PhaseResult:
        """阶段1: 基线验证 - 确保Legacy策略稳定运行"""
        self.logger.info("执行阶段1: Legacy策略基线验证")
        
        # 模拟基线验证逻辑
        # 在实际实现中，这里需要：
        # 1. 配置策略工厂使用Legacy策略
        # 2. 运行指定时间的监控
        # 3. 收集基线性能数据
        
        # 配置为仅使用Legacy策略
        # config.update({'http_strategy': {'primary_strategy': 'legacy'}})
        
        # 运行基线测试
        health_reports = []
        start_time = datetime.now()
        
        # 模拟24小时的基线验证（实际中需要根据配置调整）
        validation_duration = min(config.max_duration_hours, 24.0) * 3600  # 转换为秒
        end_time = start_time + timedelta(seconds=validation_duration)
        
        # 定期健康检查
        while datetime.now() < end_time and not self._stop_requested:
            health_report = self.health_monitor.monitor_dual_strategy_health(
                self.migration_state
            )
            health_reports.append(health_report)
            
            # 检查成功标准
            success_criteria = config.success_criteria
            legacy_success_rate = health_report.metrics.get_legacy_usage_ratio()
            error_rate = health_report.metrics.overall_error_rate
            
            if (legacy_success_rate < success_criteria.get('legacy_success_rate', 0.95) or
                error_rate > success_criteria.get('error_rate', 0.05)):
                return PhaseResult.failure(
                    MigrationPhase.PHASE_1_BASELINE,
                    f"基线验证失败: Legacy成功率{legacy_success_rate:.1%}, "
                    f"错误率{error_rate:.1%}"
                )
            
            # 等待下一次检查
            await asyncio.sleep(config.monitoring_interval_seconds)
        
        result = PhaseResult.success(
            MigrationPhase.PHASE_1_BASELINE,
            "Legacy策略基线验证通过"
        )
        result.health_reports = health_reports
        
        return result
    
    async def _phase_2_small_scale_ab_test(self, config: PhaseConfig) -> PhaseResult:
        """阶段2: 小规模A/B测试 - 1%流量验证"""
        self.logger.info("执行阶段2: 1%流量A/B测试")
        
        # 配置为1%流量A/B测试
        self.migration_state.ab_test_ratio = 0.01
        self.migration_state.target_ab_ratio = 0.01
        
        # 模拟A/B测试配置更新
        # 实际实现需要更新策略工厂配置
        
        health_reports = []
        start_time = datetime.now()
        test_duration = min(config.max_duration_hours, 24.0) * 3600
        end_time = start_time + timedelta(seconds=test_duration)
        
        while datetime.now() < end_time and not self._stop_requested:
            health_report = self.health_monitor.monitor_dual_strategy_health(
                self.migration_state
            )
            health_reports.append(health_report)
            
            # 检查A/B测试成功标准
            success_criteria = config.success_criteria
            overall_success_rate = 1 - health_report.metrics.overall_error_rate
            scanning_success_rate = 1 - health_report.metrics.scanning_error_rate
            
            if (overall_success_rate < success_criteria.get('overall_success_rate', 0.95) or
                scanning_success_rate < success_criteria.get('scanning_success_rate', 0.90)):
                return PhaseResult.failure(
                    MigrationPhase.PHASE_2_SMALL_AB,
                    f"A/B测试失败: 整体成功率{overall_success_rate:.1%}, "
                    f"Scanning成功率{scanning_success_rate:.1%}"
                )
            
            await asyncio.sleep(config.monitoring_interval_seconds)
        
        result = PhaseResult.success(
            MigrationPhase.PHASE_2_SMALL_AB,
            "1%流量A/B测试通过"
        )
        result.health_reports = health_reports
        
        return result
    
    async def _phase_3_gradual_rollout(self, config: PhaseConfig) -> PhaseResult:
        """阶段3: 渐进推广 - 逐步增加Scanning策略使用比例"""
        self.logger.info("执行阶段3: 渐进推广")
        
        rollout_schedule = [0.05, 0.1, 0.25, 0.5, 0.75]
        
        for ratio in rollout_schedule:
            if self._stop_requested:
                break
                
            self.logger.info(f"推广至{ratio*100}%流量使用Scanning策略")
            
            self.migration_state.ab_test_ratio = ratio
            self.migration_state.target_ab_ratio = ratio
            
            # 运行48小时监控
            monitoring_duration = 48 * 3600  # 48小时
            start_time = datetime.now()
            end_time = start_time + timedelta(seconds=monitoring_duration)
            
            phase_health_reports = []
            while datetime.now() < end_time and not self._stop_requested:
                health_report = self.health_monitor.monitor_dual_strategy_health(
                    self.migration_state
                )
                phase_health_reports.append(health_report)
                
                # 检查健康状态
                if health_report.health_status == HealthStatus.CRITICAL:
                    return PhaseResult.failure(
                        MigrationPhase.PHASE_3_GRADUAL,
                        f"健康检查失败在{ratio*100}%阶段: "
                        f"健康分数{health_report.overall_health_score:.2f}"
                    )
                
                await asyncio.sleep(config.monitoring_interval_seconds)
        
        result = PhaseResult.success(
            MigrationPhase.PHASE_3_GRADUAL,
            "渐进推广完成"
        )
        
        return result
    
    async def _phase_4_full_migration(self, config: PhaseConfig) -> PhaseResult:
        """阶段4: 完全迁移 - 切换到Scanning策略"""
        self.logger.info("执行阶段4: 完全切换到Scanning策略")
        
        # 切换到Scanning策略
        self.migration_state.ab_test_ratio = 1.0
        self.migration_state.target_ab_ratio = 1.0
        
        # 运行72小时全量监控
        monitoring_duration = min(config.max_duration_hours, 72.0) * 3600
        start_time = datetime.now()
        end_time = start_time + timedelta(seconds=monitoring_duration)
        
        health_reports = []
        while datetime.now() < end_time and not self._stop_requested:
            health_report = self.health_monitor.monitor_dual_strategy_health(
                self.migration_state
            )
            health_reports.append(health_report)
            
            # 检查完全迁移成功标准
            success_criteria = config.success_criteria
            if health_report.overall_health_score < success_criteria.get('health_score', 0.8):
                return PhaseResult.failure(
                    MigrationPhase.PHASE_4_FULL,
                    f"完全迁移健康检查失败: "
                    f"健康分数{health_report.overall_health_score:.2f}"
                )
            
            await asyncio.sleep(config.monitoring_interval_seconds)
        
        result = PhaseResult.success(
            MigrationPhase.PHASE_4_FULL,
            "完全迁移成功"
        )
        result.health_reports = health_reports
        
        return result
    
    async def _phase_5_legacy_cleanup(self, config: PhaseConfig) -> PhaseResult:
        """阶段5: Legacy清理 - 可选的代码清理阶段"""
        self.logger.info("执行阶段5: Legacy代码清理准备")
        
        # 这个阶段主要是标记和准备清理工作
        # 不进行实际的代码删除，只是标记状态
        
        self.migration_state.metadata['legacy_cleanup_ready'] = True
        self.migration_state.metadata['cleanup_timestamp'] = datetime.now().isoformat()
        
        # 生成清理建议报告
        cleanup_recommendations = [
            "HTTPTrimStrategy (1082行) 可以标记为废弃",
            "相关配置项可以逐步移除",
            "文档需要更新以反映新的策略架构",
            "测试用例需要更新"
        ]
        
        self.migration_state.metadata['cleanup_recommendations'] = cleanup_recommendations
        
        result = PhaseResult.success(
            MigrationPhase.PHASE_5_CLEANUP,
            "迁移完成，Legacy代码已标记为可清理"
        )
        result.warnings = cleanup_recommendations
        
        return result
    
    async def _rollback_migration(self, reason: str) -> MigrationResult:
        """回退迁移"""
        self.logger.error(f"开始迁移回退: {reason}")
        
        self.migration_state.rollback_migration(reason)
        
        # 回退到Legacy策略
        self.migration_state.ab_test_ratio = 0.0
        
        # 执行回退后的健康检查
        health_report = self.health_monitor.monitor_dual_strategy_health(
            self.migration_state
        )
        
        result = MigrationResult.failure(self.migration_state, reason)
        result.rollback_performed = True
        result.final_health_report = health_report
        
        self.migration_history.append(result)
        
        return result
    
    def stop_migration(self):
        """停止迁移"""
        self.logger.info("收到停止迁移请求")
        self._stop_requested = True
    
    def get_migration_status(self) -> Dict[str, Any]:
        """获取迁移状态"""
        return {
            'status': self.migration_state.status.value,
            'current_phase': self.migration_state.current_phase.value,
            'completed_phases': [p.value for p in self.migration_state.completed_phases],
            'failed_phases': [p.value for p in self.migration_state.failed_phases],
            'ab_test_ratio': self.migration_state.ab_test_ratio,
            'health_status': self.migration_state.health_status.value,
            'duration': self.migration_state.get_migration_duration(),
            'rollback_count': self.migration_state.rollback_count,
            'in_progress': self._migration_in_progress
        } 