"""
Step result data模型

定义各种处理步骤的结果数据结构。
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator


class StepStatus(str, Enum):
    """步骤状态"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class BaseStepResult(BaseModel):
    """基础Step results

    命名说明：
    - step_name：显示用的Step name（如 "Deduplication", "IP Anonymization"）
    - step_type：内部处理标识符（如 "dedup_packet", "mask_ip"）
    - 两者间的mapping关系请参考 config/naming_aliases.yaml
    """

    step_name: str = Field(..., description="Step name（用于显示）")
    step_type: str = Field(..., description="步骤类型（内部标识符）")
    status: StepStatus = Field(default=StepStatus.PENDING, description="步骤状态")
    start_time: Optional[datetime] = Field(default=None, description="Start time")
    end_time: Optional[datetime] = Field(default=None, description="结束时间")
    duration_ms: int = Field(default=0, ge=0, description="执行耗时(milliseconds)")
    input_filename: Optional[str] = Field(default=None, description="输入Filename")
    output_filename: Optional[str] = Field(default=None, description="输出Filename")
    error_message: Optional[str] = Field(default=None, description="Error information")

    def get_duration_string(self) -> str:
        """Get formatted duration string"""
        if self.duration_ms == 0:
            return "0ms"

        if self.duration_ms < 1000:
            return f"{self.duration_ms}ms"

        seconds = self.duration_ms / 1000.0
        if seconds < 60:
            return f"{seconds:.2f}s"

        minutes = int(seconds // 60)
        remaining_seconds = seconds % 60
        return f"{minutes}m{remaining_seconds:.2f}s"

    def is_successful(self) -> bool:
        """检查步骤是否成功完成"""
        return self.status == StepStatus.COMPLETED and self.error_message is None


class IPAnonymizationResult(BaseStepResult):
    """IP匿名化Step results"""

    original_ips_count: int = Field(default=0, ge=0, description="原始IP数量")
    anonymized_ips_count: int = Field(default=0, ge=0, description="匿名化IP数量")
    ip_mappings: Dict[str, str] = Field(default_factory=dict, description="IPmapping表")
    file_ip_mappings: Dict[str, str] = Field(
        default_factory=dict, description="文件级IPmapping"
    )
    packets_modified: int = Field(default=0, ge=0, description="修改的packets数量")

    def __init__(self, **data):
        super().__init__(step_type="mask_ip", **data)

    def get_anonymization_rate(self) -> float:
        """获取匿名化比率"""
        if self.original_ips_count == 0:
            return 0.0
        return (self.anonymized_ips_count / self.original_ips_count) * 100.0


class DeduplicationResult(BaseStepResult):
    """去重Step results"""

    original_packets: int = Field(default=0, ge=0, description="原始packets数量")
    unique_packets: int = Field(default=0, ge=0, description="去重后packets数量")
    duplicates_removed: int = Field(default=0, ge=0, description="移除的重复packets数量")
    deduplication_ratio: float = Field(
        default=0.0, ge=0.0, le=100.0, description="去重比例"
    )

    def __init__(self, **data):
        super().__init__(step_type="dedup_packet", **data)

    @field_validator("deduplication_ratio", mode="before")
    @classmethod
    def calculate_deduplication_ratio(cls, v, info):
        """自动计算去重比例"""
        if v is not None:
            return v

        original = info.data.get("original_packets", 0) if info.data else 0
        duplicates = info.data.get("duplicates_removed", 0) if info.data else 0

        if original == 0:
            return 0.0

        return (duplicates / original) * 100.0


class MaskingResult(BaseStepResult):
    """掩码Step results"""

    original_packets: int = Field(default=0, ge=0, description="原始packets数量")
    masked_packets: int = Field(default=0, ge=0, description="掩码后packets数量")
    packets_modified: int = Field(default=0, ge=0, description="修改的packets数量")
    total_bytes_removed: int = Field(default=0, ge=0, description="移除的总字节数")
    tls_packets_identified: int = Field(default=0, ge=0, description="识别的TLSpackets数量")
    payload_size_before: int = Field(default=0, ge=0, description="掩码前载荷大小")
    payload_size_after: int = Field(default=0, ge=0, description="裁切后载荷大小")

    def __init__(self, **data):
        super().__init__(step_type="trim_packet", **data)

    def get_size_reduction_ratio(self) -> float:
        """获取大小减少比例"""
        if self.payload_size_before == 0:
            return 0.0
        return (self.total_bytes_removed / self.payload_size_before) * 100.0

    def get_modification_rate(self) -> float:
        """获取修改率"""
        if self.original_packets == 0:
            return 0.0
        return (self.packets_modified / self.original_packets) * 100.0


class CustomStepResult(BaseStepResult):
    """自定义Step results"""

    custom_metrics: Dict[str, Any] = Field(
        default_factory=dict, description="自定义指标"
    )

    def add_metric(self, key: str, value: Any):
        """添加自定义指标"""
        self.custom_metrics[key] = value

    def get_metric(self, key: str, default: Any = None) -> Any:
        """获取自定义指标"""
        return self.custom_metrics.get(key, default)


# Step results类型mapping（使用标准GUI命名）
# 注意：此mapping表定义了处理逻辑标识符与领域模型类之间的对应关系
# 详细的命名规则和别名mapping请参考：config/naming_aliases.yaml
STEP_RESULT_MAPPING = {
    # 标准命名（与GUI界面一致）
    "anonymize_ips": IPAnonymizationResult,  # 标准处理标识符
    "remove_dupes": DeduplicationResult,  # 标准处理标识符
    "mask_payloads": MaskingResult,  # 标准处理标识符
    # 旧命名 - 保持向后兼容
    "mask_ip": IPAnonymizationResult,  # 废弃别名
    "mask_ips": IPAnonymizationResult,  # 废弃别名
    "dedup_packet": DeduplicationResult,  # 废弃别名
    "trim_packet": MaskingResult,  # 废弃别名
    "intelligent_trim": MaskingResult,  # 废弃别名
    "mask_payload": MaskingResult,  # 废弃别名
}

# 为了向后兼容，创建别名
TrimmingResult = MaskingResult


class FileStepResults(BaseModel):
    """文件的所有Step results"""

    filename: str = Field(..., description="Filename")
    file_path: str = Field(..., description="文件路径")
    start_time: Optional[datetime] = Field(default=None, description="文件处理Start time")
    end_time: Optional[datetime] = Field(default=None, description="文件处理结束时间")
    steps: Dict[str, BaseStepResult] = Field(
        default_factory=dict, description="Step results"
    )
    overall_status: StepStatus = Field(
        default=StepStatus.PENDING, description="整体状态"
    )
    total_duration_ms: int = Field(default=0, ge=0, description="总耗时(milliseconds)")

    def add_step_result(self, step_result: BaseStepResult):
        """添加Step results"""
        self.steps[step_result.step_name] = step_result
        self._update_overall_status()

    def get_step_result(self, step_name: str) -> Optional[BaseStepResult]:
        """获取指定步骤的结果"""
        return self.steps.get(step_name)

    def _update_overall_status(self):
        """更新整体状态"""
        if not self.steps:
            self.overall_status = StepStatus.PENDING
            return

        statuses = [step.status for step in self.steps.values()]

        if any(status == StepStatus.FAILED for status in statuses):
            self.overall_status = StepStatus.FAILED
        elif any(status == StepStatus.RUNNING for status in statuses):
            self.overall_status = StepStatus.RUNNING
        elif all(status == StepStatus.COMPLETED for status in statuses):
            self.overall_status = StepStatus.COMPLETED
        elif all(
            status in [StepStatus.COMPLETED, StepStatus.SKIPPED] for status in statuses
        ):
            self.overall_status = StepStatus.COMPLETED
        else:
            self.overall_status = StepStatus.PENDING

    def get_success_rate(self) -> float:
        """获取Success rate"""
        if not self.steps:
            return 0.0

        successful_steps = sum(
            1 for step in self.steps.values() if step.is_successful()
        )
        return (successful_steps / len(self.steps)) * 100.0

    def get_total_packets_processed(self) -> int:
        """获取处理的Total packets"""
        total = 0
        for step in self.steps.values():
            if hasattr(step, "original_packets"):
                total = max(total, step.original_packets)
        return total


class StepResultData(BaseModel):
    """Step result data的根模型"""

    file_results: Dict[str, FileStepResults] = Field(
        default_factory=dict, description="File results"
    )
    global_statistics: Dict[str, Any] = Field(
        default_factory=dict, description="Global统计"
    )

    def add_file_result(self, file_result: FileStepResults):
        """添加File results"""
        self.file_results[file_result.filename] = file_result

    def get_file_result(self, filename: str) -> Optional[FileStepResults]:
        """获取File results"""
        return self.file_results.get(filename)

    def get_overall_statistics(self) -> Dict[str, Any]:
        """获取整体Statistics data"""
        total_files = len(self.file_results)
        completed_files = sum(
            1
            for result in self.file_results.values()
            if result.overall_status == StepStatus.COMPLETED
        )
        failed_files = sum(
            1
            for result in self.file_results.values()
            if result.overall_status == StepStatus.FAILED
        )

        total_packets = sum(
            result.get_total_packets_processed()
            for result in self.file_results.values()
        )

        avg_success_rate = 0.0
        if self.file_results:
            avg_success_rate = sum(
                result.get_success_rate() for result in self.file_results.values()
            ) / len(self.file_results)

        return {
            "total_files": total_files,
            "completed_files": completed_files,
            "failed_files": failed_files,
            "success_rate": (
                (completed_files / total_files * 100.0) if total_files > 0 else 0.0
            ),
            "total_packets_processed": total_packets,
            "average_step_success_rate": avg_success_rate,
        }

    @classmethod
    def create_step_result(cls, step_type: str, **data) -> BaseStepResult:
        """创建指定类型的Step results"""
        result_class = STEP_RESULT_MAPPING.get(step_type, CustomStepResult)
        return result_class(**data)
