"""
Report data模型

Defines data structures for various reports。
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .statistics_data import StatisticsData
from .step_result_data import FileStepResults, StepResultData


class ReportType(str, Enum):
    """Report type"""

    SUMMARY = "summary"  # Summary report
    DETAILED = "detailed"  # Detailed report
    PROGRESS = "progress"  # Progress report
    ERROR = "error"  # Error report
    PERFORMANCE = "performance"  # Performance report


class ReportFormat(str, Enum):
    """Report format"""

    TEXT = "text"
    HTML = "html"
    JSON = "json"
    CSV = "csv"
    MARKDOWN = "markdown"


class ReportSection(BaseModel):
    """Report section"""

    title: str = Field(..., description="段落Title")
    content: str = Field(..., description="Section content")
    level: int = Field(default=1, ge=1, le=6, description="Title级别")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Section metadata")


class ProcessingSummary(BaseModel):
    """Processing summary data"""

    total_files: int = Field(default=0, ge=0, description="Total files")
    completed_files: int = Field(default=0, ge=0, description="Completed files")
    failed_files: int = Field(default=0, ge=0, description="Failed files")
    skipped_files: int = Field(default=0, ge=0, description="Skipped files")
    total_packets: int = Field(default=0, ge=0, description="总处理packets数")
    processing_time: str = Field(default="00:00.00", description="Processing duration")
    success_rate: float = Field(default=0.0, ge=0.0, le=100.0, description="Success rate")

    def get_completion_rate(self) -> float:
        """Get completion rate"""
        if self.total_files == 0:
            return 0.0
        return (self.completed_files / self.total_files) * 100.0


class StepStatistics(BaseModel):
    """Step statistics information"""

    step_name: str = Field(..., description="Step name")
    total_executions: int = Field(default=0, ge=0, description="Total executions")
    successful_executions: int = Field(default=0, ge=0, description="Successful executions")
    failed_executions: int = Field(default=0, ge=0, description="Failed executions")
    average_duration_ms: float = Field(
        default=0.0, ge=0.0, description="Average execution time(milliseconds)"
    )
    total_packets_processed: int = Field(default=0, ge=0, description="总处理packets数")

    def get_success_rate(self) -> float:
        """获取Success rate"""
        if self.total_executions == 0:
            return 0.0
        return (self.successful_executions / self.total_executions) * 100.0


class ErrorSummary(BaseModel):
    """Error summary"""

    total_errors: int = Field(default=0, ge=0, description="Total errors")
    error_types: Dict[str, int] = Field(
        default_factory=dict, description="Error type statistics"
    )
    critical_errors: int = Field(default=0, ge=0, description="Critical errors")
    recoverable_errors: int = Field(default=0, ge=0, description="Recoverable errors")
    most_common_error: Optional[str] = Field(default=None, description="Most common error")

    def add_error(
        self, error_type: str, is_critical: bool = False, is_recoverable: bool = False
    ):
        """Add error statistics"""
        self.total_errors += 1
        self.error_types[error_type] = self.error_types.get(error_type, 0) + 1

        if is_critical:
            self.critical_errors += 1
        if is_recoverable:
            self.recoverable_errors += 1

        # 更新Most common error
        if not self.most_common_error or self.error_types[
            error_type
        ] > self.error_types.get(self.most_common_error, 0):
            self.most_common_error = error_type


class PerformanceMetrics(BaseModel):
    """Performance metrics"""

    files_per_minute: float = Field(default=0.0, ge=0.0, description="Files per minute")
    packets_per_second: float = Field(default=0.0, ge=0.0, description="每seconds处理packets数")
    throughput_mbps: float = Field(default=0.0, ge=0.0, description="Throughput(MB/s)")
    average_file_size_mb: float = Field(
        default=0.0, ge=0.0, description="Average file size(MB)"
    )
    peak_memory_usage_mb: float = Field(
        default=0.0, ge=0.0, description="Peak memory usage(MB)"
    )
    cpu_utilization_percent: float = Field(
        default=0.0, ge=0.0, le=100.0, description="CPUUsage rate"
    )

    @classmethod
    def calculate(
        cls,
        total_files: int,
        total_packets: int,
        total_bytes: int,
        duration_seconds: float,
        memory_mb: float = 0.0,
        cpu_percent: float = 0.0,
    ) -> "PerformanceMetrics":
        """计算Performance metrics"""
        if duration_seconds <= 0:
            return cls()

        duration_minutes = duration_seconds / 60.0
        total_mb = total_bytes / (1024 * 1024)

        return cls(
            files_per_minute=(
                total_files / duration_minutes if duration_minutes > 0 else 0.0
            ),
            packets_per_second=total_packets / duration_seconds,
            throughput_mbps=total_mb / duration_seconds,
            average_file_size_mb=total_mb / total_files if total_files > 0 else 0.0,
            peak_memory_usage_mb=memory_mb,
            cpu_utilization_percent=cpu_percent,
        )


class ReportMetadata(BaseModel):
    """Report metadata"""

    generated_at: datetime = Field(default_factory=datetime.now, description="Generation time")
    generated_by: str = Field(default="PktMask", description="Generator")
    version: str = Field(default="1.0", description="Report version")
    report_id: Optional[str] = Field(default=None, description="ReportID")
    tags: List[str] = Field(default_factory=list, description="Report标签")
    custom_fields: Dict[str, Any] = Field(
        default_factory=dict, description="Custom fields"
    )


class ReportData(BaseModel):
    """完整Report data模型"""

    metadata: ReportMetadata = Field(
        default_factory=ReportMetadata, description="Report metadata"
    )
    report_type: ReportType = Field(..., description="Report type")
    title: str = Field(..., description="ReportTitle")

    # Core data
    summary: ProcessingSummary = Field(
        default_factory=ProcessingSummary, description="Processing summary"
    )
    step_statistics: List[StepStatistics] = Field(
        default_factory=list, description="步骤统计"
    )
    error_summary: ErrorSummary = Field(
        default_factory=ErrorSummary, description="Error summary"
    )
    performance_metrics: PerformanceMetrics = Field(
        default_factory=PerformanceMetrics, description="Performance metrics"
    )

    # Detailed data
    file_results: List[FileStepResults] = Field(
        default_factory=list, description="File results详情"
    )
    sections: List[ReportSection] = Field(default_factory=list, description="Report section")

    # Configuration and context
    processing_config: Dict[str, Any] = Field(
        default_factory=dict, description="Processing configuration"
    )
    environment_info: Dict[str, Any] = Field(
        default_factory=dict, description="Environment information"
    )

    def add_section(self, title: str, content: str, level: int = 1, **metadata):
        """添加Report section"""
        section = ReportSection(
            title=title, content=content, level=level, metadata=metadata
        )
        self.sections.append(section)

    def add_step_statistics(self, step_stats: StepStatistics):
        """Add step statistics"""
        self.step_statistics.append(step_stats)

    def add_file_result(self, file_result: FileStepResults):
        """添加File results"""
        self.file_results.append(file_result)

    def get_formatted_content(
        self, format_type: ReportFormat = ReportFormat.TEXT
    ) -> str:
        """获取格式化的Report内容"""
        if format_type == ReportFormat.TEXT:
            return self._format_as_text()
        elif format_type == ReportFormat.HTML:
            return self._format_as_html()
        elif format_type == ReportFormat.MARKDOWN:
            return self._format_as_markdown()
        elif format_type == ReportFormat.JSON:
            return self.json(indent=2, ensure_ascii=False)
        else:
            return self._format_as_text()

    def _format_as_text(self) -> str:
        """Format as text"""
        lines = [
            f"# {self.title}",
            f"Generation time: {self.metadata.generated_at.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Processing summary",
            f"Total files: {self.summary.total_files}",
            f"完成文件数: {self.summary.completed_files}",
            f"Failed files: {self.summary.failed_files}",
            f"Success rate: {self.summary.success_rate:.1f}%",
            f"处理时间: {self.summary.processing_time}",
            f"总处理packets数: {self.summary.total_packets}",
            "",
        ]

        if self.step_statistics:
            lines.append("## 步骤统计")
            for step in self.step_statistics:
                lines.extend(
                    [
                        f"### {step.step_name}",
                        f"  执行次数: {step.total_executions}",
                        f"  Success rate: {step.get_success_rate():.1f}%",
                        f"  平均耗时: {step.average_duration_ms:.1f}ms",
                        "",
                    ]
                )

        if self.error_summary.total_errors > 0:
            lines.extend(
                [
                    "## Error summary",
                    f"Total errors: {self.error_summary.total_errors}",
                    f"严重错误: {self.error_summary.critical_errors}",
                    f"可恢复错误: {self.error_summary.recoverable_errors}",
                    "",
                ]
            )

        for section in self.sections:
            prefix = "#" * section.level
            lines.extend([f"{prefix} {section.title}", section.content, ""])

        return "\n".join(lines)

    def _format_as_html(self) -> str:
        """Format asHTML"""
        html_parts = [
            f"<html><head><title>{self.title}</title></head><body>",
            f"<h1>{self.title}</h1>",
            f"<p>Generation time: {self.metadata.generated_at.strftime('%Y-%m-%d %H:%M:%S')}</p>",
            "<h2>Processing summary</h2>",
            "<table border='1'>",
            f"<tr><td>Total files</td><td>{self.summary.total_files}</td></tr>",
            f"<tr><td>完成文件数</td><td>{self.summary.completed_files}</td></tr>",
            f"<tr><td>Failed files</td><td>{self.summary.failed_files}</td></tr>",
            f"<tr><td>Success rate</td><td>{self.summary.success_rate:.1f}%</td></tr>",
            f"<tr><td>处理时间</td><td>{self.summary.processing_time}</td></tr>",
            "</table>",
        ]

        for section in self.sections:
            html_parts.extend(
                [
                    f"<h{section.level}>{section.title}</h{section.level}>",
                    f"<p>{section.content}</p>",
                ]
            )

        html_parts.append("</body></html>")
        return "\n".join(html_parts)

    def _format_as_markdown(self) -> str:
        """Format asMarkdown"""
        lines = [
            f"# {self.title}",
            f"**Generation time**: {self.metadata.generated_at.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Processing summary",
            "| Item | Value |",
            "|------|------|",
            f"| Total files | {self.summary.total_files} |",
            f"| 完成文件数 | {self.summary.completed_files} |",
            f"| Failed files | {self.summary.failed_files} |",
            f"| Success rate | {self.summary.success_rate:.1f}% |",
            f"| 处理时间 | {self.summary.processing_time} |",
            "",
        ]

        for section in self.sections:
            prefix = "#" * section.level
            lines.extend([f"{prefix} {section.title}", section.content, ""])

        return "\n".join(lines)

    @classmethod
    def from_statistics(
        cls,
        stats: StatisticsData,
        step_results: StepResultData,
        title: str = "处理Report",
    ) -> "ReportData":
        """从Statistics data创建Report"""
        summary = ProcessingSummary(
            total_files=stats.metrics.total_files_to_process,
            completed_files=stats.metrics.files_processed,
            total_packets=stats.metrics.packets_processed,
            processing_time=stats.timing.get_elapsed_time_string(),
            success_rate=(
                (
                    stats.metrics.files_processed
                    / stats.metrics.total_files_to_process
                    * 100.0
                )
                if stats.metrics.total_files_to_process > 0
                else 0.0
            ),
        )

        # 计算Performance metrics
        duration_seconds = stats.timing.processing_time_ms / 1000.0
        performance = PerformanceMetrics.calculate(
            total_files=stats.metrics.files_processed,
            total_packets=stats.metrics.packets_processed,
            total_bytes=0,  # 需要从File results中计算
            duration_seconds=duration_seconds,
        )

        report = cls(
            report_type=ReportType.SUMMARY,
            title=title,
            summary=summary,
            performance_metrics=performance,
        )

        return report
