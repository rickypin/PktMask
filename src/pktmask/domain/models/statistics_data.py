"""
统计数据模型

定义处理过程中的各种统计数据结构。
"""

from datetime import datetime
from typing import Any, Dict, Optional, Set

from pydantic import BaseModel, Field, field_validator


class PacketStatistics(BaseModel):
    """数据包统计信息"""

    total_packets: int = Field(default=0, ge=0, description="总包数")
    processed_packets: int = Field(default=0, ge=0, description="已处理包数")
    filtered_packets: int = Field(default=0, ge=0, description="过滤的包数")
    dropped_packets: int = Field(default=0, ge=0, description="丢弃的包数")
    error_packets: int = Field(default=0, ge=0, description="错误包数")

    def get_success_rate(self) -> float:
        """获取成功处理率"""
        if self.total_packets == 0:
            return 0.0
        return (self.processed_packets / self.total_packets) * 100.0

    def get_filter_rate(self) -> float:
        """获取过滤率"""
        if self.total_packets == 0:
            return 0.0
        return (self.filtered_packets / self.total_packets) * 100.0


class ProcessingMetrics(BaseModel):
    """处理指标数据"""

    files_processed: int = Field(default=0, ge=0, description="已处理文件数")
    total_files_to_process: int = Field(default=0, ge=0, description="总文件数")
    packets_processed: int = Field(default=0, ge=0, description="已处理包数")

    @field_validator("files_processed")
    @classmethod
    def validate_files_processed(cls, v, info):
        total = info.data.get("total_files_to_process", 0) if info.data else 0
        if total > 0 and v > total:
            raise ValueError(f"已处理文件数({v})不能超过总文件数({total})")
        return v

    def get_completion_rate(self) -> float:
        """获取完成率"""
        if self.total_files_to_process == 0:
            return 0.0
        return (self.files_processed / self.total_files_to_process) * 100.0


class TimingData(BaseModel):
    """时间统计数据"""

    start_time: Optional[datetime] = Field(default=None, description="开始时间")
    processing_time_ms: int = Field(default=0, ge=0, description="处理耗时(毫秒)")

    model_config = {"arbitrary_types_allowed": True}

    def get_elapsed_time_string(self) -> str:
        """获取格式化的耗时字符串"""
        if self.processing_time_ms == 0:
            return "00:00.00"

        total_seconds = self.processing_time_ms / 1000.0
        minutes = int(total_seconds // 60)
        seconds = total_seconds % 60
        return f"{minutes:02d}:{seconds:05.2f}"

    def get_processing_speed(self, packets_count: int) -> float:
        """获取处理速度（包/秒）"""
        if self.processing_time_ms == 0 or packets_count == 0:
            return 0.0

        elapsed_seconds = self.processing_time_ms / 1000.0
        return packets_count / elapsed_seconds


class FileProcessingResults(BaseModel):
    """文件处理结果数据"""

    filename: str = Field(..., description="文件名")
    steps: Dict[str, Any] = Field(default_factory=dict, description="步骤处理结果")
    timestamp: Optional[str] = Field(default=None, description="处理时间戳")
    status: str = Field(default="pending", description="处理状态")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        valid_statuses = ["pending", "processing", "completed", "failed", "skipped"]
        if v not in valid_statuses:
            raise ValueError(f"无效的状态值: {v}. 有效值: {valid_statuses}")
        return v


class IPMappingData(BaseModel):
    """IP映射数据"""

    global_mappings: Dict[str, str] = Field(
        default_factory=dict, description="全局IP映射"
    )
    reports_by_subdir: Dict[str, Any] = Field(
        default_factory=dict, description="按子目录的报告"
    )

    def get_mapping_count(self) -> int:
        """获取映射数量"""
        return len(self.global_mappings)

    def add_mappings(self, new_mappings: Dict[str, str]):
        """添加新的映射"""
        self.global_mappings.update(new_mappings)

    def get_report_for_subdir(self, subdir: str) -> Optional[Any]:
        """获取指定子目录的报告"""
        return self.reports_by_subdir.get(subdir)


class ProcessingState(BaseModel):
    """处理状态数据"""

    current_processing_file: Optional[str] = Field(
        default=None, description="当前处理文件"
    )
    subdirs_files_counted: Set[str] = Field(
        default_factory=set, description="已计数文件的子目录"
    )
    subdirs_packets_counted: Set[str] = Field(
        default_factory=set, description="已计数包的子目录"
    )
    printed_summary_headers: Set[str] = Field(
        default_factory=set, description="已打印摘要头的集合"
    )

    model_config = {"arbitrary_types_allowed": True}


class StatisticsData(BaseModel):
    """完整的统计数据模型"""

    metrics: ProcessingMetrics = Field(
        default_factory=ProcessingMetrics, description="处理指标"
    )
    timing: TimingData = Field(default_factory=TimingData, description="时间统计")
    file_results: Dict[str, FileProcessingResults] = Field(
        default_factory=dict, description="文件结果"
    )
    step_results: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict, description="步骤结果"
    )
    ip_mapping: IPMappingData = Field(
        default_factory=IPMappingData, description="IP映射数据"
    )
    state: ProcessingState = Field(
        default_factory=ProcessingState, description="处理状态"
    )

    def get_dashboard_summary(self) -> Dict[str, Any]:
        """获取仪表盘摘要数据"""
        return {
            "files_processed": self.metrics.files_processed,
            "total_files": self.metrics.total_files_to_process,
            "packets_processed": self.metrics.packets_processed,
            "elapsed_time": self.timing.get_elapsed_time_string(),
            "completion_rate": self.metrics.get_completion_rate(),
            "processing_speed": self.timing.get_processing_speed(
                self.metrics.packets_processed
            ),
            "ip_mappings_count": self.ip_mapping.get_mapping_count(),
        }

    def get_processing_summary(self) -> Dict[str, Any]:
        """获取完整的处理摘要"""
        return {
            "files_processed": self.metrics.files_processed,
            "total_files": self.metrics.total_files_to_process,
            "packets_processed": self.metrics.packets_processed,
            "processing_time": self.timing.get_elapsed_time_string(),
            "step_results": self.step_results.copy(),
            "file_processing_results": {
                filename: result.model_dump()
                for filename, result in self.file_results.items()
            },
            "global_ip_mappings": self.ip_mapping.global_mappings.copy(),
            "all_ip_reports": self.ip_mapping.reports_by_subdir.copy(),
        }

    def reset_all(self):
        """重置所有统计数据"""
        self.metrics = ProcessingMetrics()
        self.timing = TimingData()
        self.file_results.clear()
        self.step_results.clear()
        self.ip_mapping = IPMappingData()
        self.state = ProcessingState()

    def is_processing_complete(self) -> bool:
        """检查处理是否完成"""
        return (
            self.metrics.total_files_to_process > 0
            and self.metrics.files_processed >= self.metrics.total_files_to_process
        )
