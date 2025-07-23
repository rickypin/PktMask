"""
Statistics data模型

定义处理过程中的各种Statistics data结构。
"""

from datetime import datetime
from typing import Any, Dict, Optional, Set

from pydantic import BaseModel, Field, field_validator


class PacketStatistics(BaseModel):
    """数据Packet statistics信息"""

    total_packets: int = Field(default=0, ge=0, description="Total packets")
    processed_packets: int = Field(default=0, ge=0, description="Processed packets")
    filtered_packets: int = Field(default=0, ge=0, description="Filtered packets")
    dropped_packets: int = Field(default=0, ge=0, description="Dropped packets")
    error_packets: int = Field(default=0, ge=0, description="Error packets")

    def get_success_rate(self) -> float:
        """Get success processing rate"""
        if self.total_packets == 0:
            return 0.0
        return (self.processed_packets / self.total_packets) * 100.0

    def get_filter_rate(self) -> float:
        """Get filter rate"""
        if self.total_packets == 0:
            return 0.0
        return (self.filtered_packets / self.total_packets) * 100.0


class ProcessingMetrics(BaseModel):
    """Processing metrics data"""

    files_processed: int = Field(default=0, ge=0, description="Processed files")
    total_files_to_process: int = Field(default=0, ge=0, description="Total files")
    packets_processed: int = Field(default=0, ge=0, description="Processed packets")

    @field_validator("files_processed")
    @classmethod
    def validate_files_processed(cls, v, info):
        total = info.data.get("total_files_to_process", 0) if info.data else 0
        if total > 0 and v > total:
            raise ValueError(f"Processed files({v})不能超过Total files({total})")
        return v

    def get_completion_rate(self) -> float:
        """Get completion rate"""
        if self.total_files_to_process == 0:
            return 0.0
        return (self.files_processed / self.total_files_to_process) * 100.0


class TimingData(BaseModel):
    """时间Statistics data"""

    start_time: Optional[datetime] = Field(default=None, description="Start time")
    processing_time_ms: int = Field(default=0, ge=0, description="Processing duration(milliseconds)")

    model_config = {"arbitrary_types_allowed": True}

    def get_elapsed_time_string(self) -> str:
        """Get formatted duration string"""
        if self.processing_time_ms == 0:
            return "00:00.00"

        total_seconds = self.processing_time_ms / 1000.0
        minutes = int(total_seconds // 60)
        seconds = total_seconds % 60
        return f"{minutes:02d}:{seconds:05.2f}"

    def get_processing_speed(self, packets_count: int) -> float:
        """Get processing speed（packets/seconds）"""
        if self.processing_time_ms == 0 or packets_count == 0:
            return 0.0

        elapsed_seconds = self.processing_time_ms / 1000.0
        return packets_count / elapsed_seconds


class FileProcessingResults(BaseModel):
    """File processing result data"""

    filename: str = Field(..., description="Filename")
    steps: Dict[str, Any] = Field(default_factory=dict, description="Step processing results")
    timestamp: Optional[str] = Field(default=None, description="Processing timestamp")
    status: str = Field(default="pending", description="Processing status")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        valid_statuses = ["pending", "processing", "completed", "failed", "skipped"]
        if v not in valid_statuses:
            raise ValueError(f"Invalid status value: {v}. Valid values: {valid_statuses}")
        return v


class IPMappingData(BaseModel):
    """IPMapping data"""

    global_mappings: Dict[str, str] = Field(
        default_factory=dict, description="GlobalIPmapping"
    )
    reports_by_subdir: Dict[str, Any] = Field(
        default_factory=dict, description="Reports by subdirectory"
    )

    def get_mapping_count(self) -> int:
        """获取mapping数量"""
        return len(self.global_mappings)

    def add_mappings(self, new_mappings: Dict[str, str]):
        """添加新的mapping"""
        self.global_mappings.update(new_mappings)

    def get_report_for_subdir(self, subdir: str) -> Optional[Any]:
        """Get report for specified subdirectory"""
        return self.reports_by_subdir.get(subdir)


class ProcessingState(BaseModel):
    """Processing status数据"""

    current_processing_file: Optional[str] = Field(
        default=None, description="Current processing file"
    )
    subdirs_files_counted: Set[str] = Field(
        default_factory=set, description="Subdirectories with counted files"
    )
    subdirs_packets_counted: Set[str] = Field(
        default_factory=set, description="已计数packets的子目录"
    )
    printed_summary_headers: Set[str] = Field(
        default_factory=set, description="Set of printed summary headers"
    )

    model_config = {"arbitrary_types_allowed": True}


class StatisticsData(BaseModel):
    """完整的Statistics data模型"""

    metrics: ProcessingMetrics = Field(
        default_factory=ProcessingMetrics, description="Processing metrics"
    )
    timing: TimingData = Field(default_factory=TimingData, description="Time statistics")
    file_results: Dict[str, FileProcessingResults] = Field(
        default_factory=dict, description="File results"
    )
    step_results: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict, description="Step results"
    )
    ip_mapping: IPMappingData = Field(
        default_factory=IPMappingData, description="IPMapping data"
    )
    state: ProcessingState = Field(
        default_factory=ProcessingState, description="Processing status"
    )

    def get_dashboard_summary(self) -> Dict[str, Any]:
        """Get dashboard summary data"""
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
        """Get complete processing summary"""
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
        """重置所有Statistics data"""
        self.metrics = ProcessingMetrics()
        self.timing = TimingData()
        self.file_results.clear()
        self.step_results.clear()
        self.ip_mapping = IPMappingData()
        self.state = ProcessingState()

    def is_processing_complete(self) -> bool:
        """Check if processing is complete"""
        return (
            self.metrics.total_files_to_process > 0
            and self.metrics.files_processed >= self.metrics.total_files_to_process
        )
