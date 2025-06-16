"""
迁移数据模型

定义迁移过程中使用的数据结构、枚举和状态管理类。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any
from datetime import datetime
import time


class MigrationPhase(Enum):
    """迁移阶段枚举"""
    PHASE_1_BASELINE = "baseline_validation"       # 阶段1: 基线验证
    PHASE_2_SMALL_AB = "small_scale_ab_test"       # 阶段2: 小规模A/B测试
    PHASE_3_GRADUAL = "gradual_rollout"            # 阶段3: 渐进推广
    PHASE_4_FULL = "full_migration"                # 阶段4: 完全迁移
    PHASE_5_CLEANUP = "legacy_cleanup"             # 阶段5: Legacy清理


class MigrationStatus(Enum):
    """迁移状态枚举"""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class HealthStatus(Enum):
    """健康状态枚举"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class MigrationMetrics:
    """迁移指标数据"""
    # 基础指标
    timestamp: float = field(default_factory=time.time)
    phase: MigrationPhase = MigrationPhase.PHASE_1_BASELINE
    
    # 策略使用统计
    legacy_usage_count: int = 0
    scanning_usage_count: int = 0
    fallback_count: int = 0
    total_requests: int = 0
    
    # 性能指标
    avg_processing_time_ms: float = 0.0
    legacy_avg_time_ms: float = 0.0
    scanning_avg_time_ms: float = 0.0
    throughput_pps: float = 0.0
    
    # 错误率指标
    legacy_error_rate: float = 0.0
    scanning_error_rate: float = 0.0
    overall_error_rate: float = 0.0
    
    # 资源使用
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0
    
    def get_legacy_usage_ratio(self) -> float:
        """获取Legacy策略使用比例"""
        if self.total_requests == 0:
            return 0.0
        return self.legacy_usage_count / self.total_requests
    
    def get_scanning_usage_ratio(self) -> float:
        """获取Scanning策略使用比例"""
        if self.total_requests == 0:
            return 0.0
        return self.scanning_usage_count / self.total_requests
    
    def get_fallback_ratio(self) -> float:
        """获取回退比例"""
        if self.total_requests == 0:
            return 0.0
        return self.fallback_count / self.total_requests
    
    def get_performance_improvement(self) -> float:
        """获取性能改进比例"""
        if self.legacy_avg_time_ms == 0:
            return 0.0
        return (self.legacy_avg_time_ms - self.scanning_avg_time_ms) / self.legacy_avg_time_ms


@dataclass
class MigrationState:
    """迁移状态管理"""
    current_phase: MigrationPhase = MigrationPhase.PHASE_1_BASELINE
    status: MigrationStatus = MigrationStatus.NOT_STARTED
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    # 阶段进度追踪
    completed_phases: List[MigrationPhase] = field(default_factory=list)
    failed_phases: List[MigrationPhase] = field(default_factory=list)
    current_phase_start: Optional[datetime] = None
    
    # A/B测试配置
    ab_test_ratio: float = 0.0  # 当前A/B测试比例
    target_ab_ratio: float = 0.0  # 目标A/B测试比例
    
    # 健康状态
    health_status: HealthStatus = HealthStatus.UNKNOWN
    last_health_check: Optional[datetime] = None
    
    # 回退信息
    rollback_enabled: bool = True
    rollback_reason: Optional[str] = None
    rollback_count: int = 0
    
    # 自定义属性
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def start_migration(self):
        """开始迁移"""
        self.status = MigrationStatus.IN_PROGRESS
        self.start_time = datetime.now()
        self.health_status = HealthStatus.UNKNOWN
    
    def complete_phase(self, phase: MigrationPhase):
        """完成一个阶段"""
        if phase not in self.completed_phases:
            self.completed_phases.append(phase)
        if phase in self.failed_phases:
            self.failed_phases.remove(phase)
    
    def fail_phase(self, phase: MigrationPhase, reason: str):
        """标记阶段失败"""
        if phase not in self.failed_phases:
            self.failed_phases.append(phase)
        self.metadata[f"{phase.value}_failure_reason"] = reason
    
    def complete_migration(self):
        """完成迁移"""
        self.status = MigrationStatus.COMPLETED
        self.end_time = datetime.now()
        self.health_status = HealthStatus.HEALTHY
    
    def rollback_migration(self, reason: str):
        """回退迁移"""
        self.status = MigrationStatus.ROLLED_BACK
        self.rollback_reason = reason
        self.rollback_count += 1
        self.health_status = HealthStatus.CRITICAL
    
    def get_migration_duration(self) -> Optional[float]:
        """获取迁移持续时间（秒）"""
        if not self.start_time:
            return None
        end_time = self.end_time or datetime.now()
        return (end_time - self.start_time).total_seconds()
    
    def get_current_phase_duration(self) -> Optional[float]:
        """获取当前阶段持续时间（秒）"""
        if not self.current_phase_start:
            return None
        return (datetime.now() - self.current_phase_start).total_seconds()


@dataclass 
class PhaseConfig:
    """阶段配置"""
    phase: MigrationPhase
    max_duration_hours: float = 24.0  # 最大持续时间
    success_criteria: Dict[str, float] = field(default_factory=dict)  # 成功标准
    monitoring_interval_seconds: int = 300  # 监控间隔
    auto_advance: bool = True  # 是否自动推进到下一阶段
    rollback_on_failure: bool = True  # 失败时是否自动回退
    
    @classmethod
    def get_default_configs(cls) -> Dict[MigrationPhase, 'PhaseConfig']:
        """获取默认阶段配置"""
        return {
            MigrationPhase.PHASE_1_BASELINE: PhaseConfig(
                phase=MigrationPhase.PHASE_1_BASELINE,
                max_duration_hours=24.0,
                success_criteria={
                    'legacy_success_rate': 0.95,
                    'error_rate': 0.05
                }
            ),
            MigrationPhase.PHASE_2_SMALL_AB: PhaseConfig(
                phase=MigrationPhase.PHASE_2_SMALL_AB,
                max_duration_hours=24.0,
                success_criteria={
                    'overall_success_rate': 0.95,
                    'scanning_success_rate': 0.90,
                    'performance_degradation': 0.10
                }
            ),
            MigrationPhase.PHASE_3_GRADUAL: PhaseConfig(
                phase=MigrationPhase.PHASE_3_GRADUAL,
                max_duration_hours=96.0,  # 4天渐进推广
                success_criteria={
                    'health_score': 0.8,
                    'error_rate': 0.02
                }
            ),
            MigrationPhase.PHASE_4_FULL: PhaseConfig(
                phase=MigrationPhase.PHASE_4_FULL,
                max_duration_hours=72.0,  # 3天全量监控
                success_criteria={
                    'health_score': 0.8,
                    'scanning_success_rate': 0.95
                }
            ),
            MigrationPhase.PHASE_5_CLEANUP: PhaseConfig(
                phase=MigrationPhase.PHASE_5_CLEANUP,
                max_duration_hours=8.0,
                success_criteria={},  # 清理阶段无严格标准
                rollback_on_failure=False  # 清理失败不回退
            )
        } 