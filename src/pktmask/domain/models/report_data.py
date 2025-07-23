"""
报告数据模型

定义各种报告的数据结构。
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator

from .statistics_data import StatisticsData
from .step_result_data import FileStepResults, StepResultData


class ReportType(str, Enum):
    """报告类型"""

    SUMMARY = "summary"  # 摘要报告
    DETAILED = "detailed"  # 详细报告
    PROGRESS = "progress"  # 进度报告
    ERROR = "error"  # 错误报告
    PERFORMANCE = "performance"  # 性能报告


class ReportFormat(str, Enum):
    """报告格式"""

    TEXT = "text"
    HTML = "html"
    JSON = "json"
    CSV = "csv"
    MARKDOWN = "markdown"


class ReportSection(BaseModel):
    """报告段落"""

    title: str = Field(..., description="段落标题")
    content: str = Field(..., description="段落内容")
    level: int = Field(default=1, ge=1, le=6, description="标题级别")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="段落元数据")


class ProcessingSummary(BaseModel):
    """处理摘要数据"""

    total_files: int = Field(default=0, ge=0, description="总文件数")
    completed_files: int = Field(default=0, ge=0, description="已完成文件数")
    failed_files: int = Field(default=0, ge=0, description="失败文件数")
    skipped_files: int = Field(default=0, ge=0, description="跳过文件数")
    total_packets: int = Field(default=0, ge=0, description="总处理包数")
    processing_time: str = Field(default="00:00.00", description="处理耗时")
    success_rate: float = Field(default=0.0, ge=0.0, le=100.0, description="成功率")

    def get_completion_rate(self) -> float:
        """获取完成率"""
        if self.total_files == 0:
            return 0.0
        return (self.completed_files / self.total_files) * 100.0


class StepStatistics(BaseModel):
    """步骤统计信息"""

    step_name: str = Field(..., description="步骤名称")
    total_executions: int = Field(default=0, ge=0, description="总执行次数")
    successful_executions: int = Field(default=0, ge=0, description="成功执行次数")
    failed_executions: int = Field(default=0, ge=0, description="失败执行次数")
    average_duration_ms: float = Field(
        default=0.0, ge=0.0, description="平均执行时间(毫秒)"
    )
    total_packets_processed: int = Field(default=0, ge=0, description="总处理包数")

    def get_success_rate(self) -> float:
        """获取成功率"""
        if self.total_executions == 0:
            return 0.0
        return (self.successful_executions / self.total_executions) * 100.0


class ErrorSummary(BaseModel):
    """错误摘要"""

    total_errors: int = Field(default=0, ge=0, description="总错误数")
    error_types: Dict[str, int] = Field(
        default_factory=dict, description="错误类型统计"
    )
    critical_errors: int = Field(default=0, ge=0, description="严重错误数")
    recoverable_errors: int = Field(default=0, ge=0, description="可恢复错误数")
    most_common_error: Optional[str] = Field(default=None, description="最常见错误")

    def add_error(
        self, error_type: str, is_critical: bool = False, is_recoverable: bool = False
    ):
        """添加错误统计"""
        self.total_errors += 1
        self.error_types[error_type] = self.error_types.get(error_type, 0) + 1

        if is_critical:
            self.critical_errors += 1
        if is_recoverable:
            self.recoverable_errors += 1

        # 更新最常见错误
        if not self.most_common_error or self.error_types[
            error_type
        ] > self.error_types.get(self.most_common_error, 0):
            self.most_common_error = error_type


class PerformanceMetrics(BaseModel):
    """性能指标"""

    files_per_minute: float = Field(default=0.0, ge=0.0, description="每分钟处理文件数")
    packets_per_second: float = Field(default=0.0, ge=0.0, description="每秒处理包数")
    throughput_mbps: float = Field(default=0.0, ge=0.0, description="吞吐量(MB/s)")
    average_file_size_mb: float = Field(
        default=0.0, ge=0.0, description="平均文件大小(MB)"
    )
    peak_memory_usage_mb: float = Field(
        default=0.0, ge=0.0, description="峰值内存使用(MB)"
    )
    cpu_utilization_percent: float = Field(
        default=0.0, ge=0.0, le=100.0, description="CPU使用率"
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
        """计算性能指标"""
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
    """报告元数据"""

    generated_at: datetime = Field(default_factory=datetime.now, description="生成时间")
    generated_by: str = Field(default="PktMask", description="生成者")
    version: str = Field(default="1.0", description="报告版本")
    report_id: Optional[str] = Field(default=None, description="报告ID")
    tags: List[str] = Field(default_factory=list, description="报告标签")
    custom_fields: Dict[str, Any] = Field(
        default_factory=dict, description="自定义字段"
    )


class ReportData(BaseModel):
    """完整报告数据模型"""

    metadata: ReportMetadata = Field(
        default_factory=ReportMetadata, description="报告元数据"
    )
    report_type: ReportType = Field(..., description="报告类型")
    title: str = Field(..., description="报告标题")

    # 核心数据
    summary: ProcessingSummary = Field(
        default_factory=ProcessingSummary, description="处理摘要"
    )
    step_statistics: List[StepStatistics] = Field(
        default_factory=list, description="步骤统计"
    )
    error_summary: ErrorSummary = Field(
        default_factory=ErrorSummary, description="错误摘要"
    )
    performance_metrics: PerformanceMetrics = Field(
        default_factory=PerformanceMetrics, description="性能指标"
    )

    # 详细数据
    file_results: List[FileStepResults] = Field(
        default_factory=list, description="文件结果详情"
    )
    sections: List[ReportSection] = Field(default_factory=list, description="报告段落")

    # 配置和上下文
    processing_config: Dict[str, Any] = Field(
        default_factory=dict, description="处理配置"
    )
    environment_info: Dict[str, Any] = Field(
        default_factory=dict, description="环境信息"
    )

    def add_section(self, title: str, content: str, level: int = 1, **metadata):
        """添加报告段落"""
        section = ReportSection(
            title=title, content=content, level=level, metadata=metadata
        )
        self.sections.append(section)

    def add_step_statistics(self, step_stats: StepStatistics):
        """添加步骤统计"""
        self.step_statistics.append(step_stats)

    def add_file_result(self, file_result: FileStepResults):
        """添加文件结果"""
        self.file_results.append(file_result)

    def get_formatted_content(
        self, format_type: ReportFormat = ReportFormat.TEXT
    ) -> str:
        """获取格式化的报告内容"""
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
        """格式化为文本"""
        lines = [
            f"# {self.title}",
            f"生成时间: {self.metadata.generated_at.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## 处理摘要",
            f"总文件数: {self.summary.total_files}",
            f"完成文件数: {self.summary.completed_files}",
            f"失败文件数: {self.summary.failed_files}",
            f"成功率: {self.summary.success_rate:.1f}%",
            f"处理时间: {self.summary.processing_time}",
            f"总处理包数: {self.summary.total_packets}",
            "",
        ]

        if self.step_statistics:
            lines.append("## 步骤统计")
            for step in self.step_statistics:
                lines.extend(
                    [
                        f"### {step.step_name}",
                        f"  执行次数: {step.total_executions}",
                        f"  成功率: {step.get_success_rate():.1f}%",
                        f"  平均耗时: {step.average_duration_ms:.1f}ms",
                        "",
                    ]
                )

        if self.error_summary.total_errors > 0:
            lines.extend(
                [
                    "## 错误摘要",
                    f"总错误数: {self.error_summary.total_errors}",
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
        """格式化为HTML"""
        html_parts = [
            f"<html><head><title>{self.title}</title></head><body>",
            f"<h1>{self.title}</h1>",
            f"<p>生成时间: {self.metadata.generated_at.strftime('%Y-%m-%d %H:%M:%S')}</p>",
            "<h2>处理摘要</h2>",
            "<table border='1'>",
            f"<tr><td>总文件数</td><td>{self.summary.total_files}</td></tr>",
            f"<tr><td>完成文件数</td><td>{self.summary.completed_files}</td></tr>",
            f"<tr><td>失败文件数</td><td>{self.summary.failed_files}</td></tr>",
            f"<tr><td>成功率</td><td>{self.summary.success_rate:.1f}%</td></tr>",
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
        """格式化为Markdown"""
        lines = [
            f"# {self.title}",
            f"**生成时间**: {self.metadata.generated_at.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## 处理摘要",
            "| 项目 | 数值 |",
            "|------|------|",
            f"| 总文件数 | {self.summary.total_files} |",
            f"| 完成文件数 | {self.summary.completed_files} |",
            f"| 失败文件数 | {self.summary.failed_files} |",
            f"| 成功率 | {self.summary.success_rate:.1f}% |",
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
        title: str = "处理报告",
    ) -> "ReportData":
        """从统计数据创建报告"""
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

        # 计算性能指标
        duration_seconds = stats.timing.processing_time_ms / 1000.0
        performance = PerformanceMetrics.calculate(
            total_files=stats.metrics.files_processed,
            total_packets=stats.metrics.packets_processed,
            total_bytes=0,  # 需要从文件结果中计算
            duration_seconds=duration_seconds,
        )

        report = cls(
            report_type=ReportType.SUMMARY,
            title=title,
            summary=summary,
            performance_metrics=performance,
        )

        return report
