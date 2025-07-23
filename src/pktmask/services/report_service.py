"""
Report generation service
Provides unified processing report generation and formatting services
"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from pktmask.infrastructure.logging import get_logger

logger = get_logger("ReportService")


@dataclass
class ProcessingReport:
    """Processing report data structure"""

    success: bool
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    input_path: str
    output_path: str
    total_files: int
    processed_files: int
    failed_files: int
    total_packets: int
    modified_packets: int
    stage_reports: List[Dict[str, Any]]
    errors: List[str]
    warnings: List[str]

    @property
    def duration_ms(self) -> float:
        return self.duration_seconds * 1000

    @property
    def success_rate(self) -> float:
        if self.total_files == 0:
            return 0.0
        return (self.processed_files / self.total_files) * 100

    @property
    def modification_rate(self) -> float:
        if self.total_packets == 0:
            return 0.0
        return (self.modified_packets / self.total_packets) * 100


class ReportService:
    """Unified report generation service"""

    def __init__(self):
        self._current_report: Optional[ProcessingReport] = None
        self._stage_stats = []
        self._errors = []
        self._warnings = []

    def start_report(self, input_path: str, output_path: str):
        """Start new report"""
        self._current_report = None
        self._stage_stats = []
        self._errors = []
        self._warnings = []

        self._start_time = datetime.now()
        self._input_path = input_path
        self._output_path = output_path

        logger.debug(f"Started report for: {input_path}")

    def add_stage_stats(self, stage_name: str, stats: Dict[str, Any]):
        """Add stage statistics"""
        stage_report = {
            "stage_name": stage_name,
            "timestamp": datetime.now().isoformat(),
            **stats,
        }
        self._stage_stats.append(stage_report)
        logger.debug(f"Added stage stats for: {stage_name}")

    def add_error(self, error_message: str):
        """Add error information"""
        self._errors.append(
            {"timestamp": datetime.now().isoformat(), "message": error_message}
        )
        logger.error(f"Added error: {error_message}")

    def add_warning(self, warning_message: str):
        """Add warning information"""
        self._warnings.append(
            {"timestamp": datetime.now().isoformat(), "message": warning_message}
        )
        logger.warning(f"Added warning: {warning_message}")

    def finalize_report(
        self,
        success: bool,
        total_files: int,
        processed_files: int,
        total_packets: int = 0,
        modified_packets: int = 0,
    ) -> ProcessingReport:
        """Complete report generation"""
        end_time = datetime.now()
        duration = (end_time - self._start_time).total_seconds()

        self._current_report = ProcessingReport(
            success=success,
            start_time=self._start_time,
            end_time=end_time,
            duration_seconds=duration,
            input_path=self._input_path,
            output_path=self._output_path,
            total_files=total_files,
            processed_files=processed_files,
            failed_files=total_files - processed_files,
            total_packets=total_packets,
            modified_packets=modified_packets,
            stage_reports=self._stage_stats.copy(),
            errors=[e["message"] for e in self._errors],
            warnings=[w["message"] for w in self._warnings],
        )

        logger.info(
            f"Finalized report: {processed_files}/{total_files} files processed"
        )
        return self._current_report

    def generate_text_report(
        self, report: ProcessingReport, detailed: bool = False
    ) -> str:
        """Generate text format report"""
        lines = []

        # Title
        lines.append("=" * 70)
        lines.append("PktMask Processing Report")
        lines.append("=" * 70)
        lines.append("")

        # Basic information
        lines.append("📋 Basic Information")
        lines.append("-" * 30)
        lines.append(f"Input Path:      {report.input_path}")
        lines.append(f"Output Path:     {report.output_path}")
        lines.append(
            f"Start Time:      {report.start_time.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        lines.append(
            f"End Time:        {report.end_time.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        lines.append(
            f"Duration:        {self._format_duration(report.duration_seconds)}"
        )
        lines.append(
            f"Status:          {'✅ Success' if report.success else '❌ Failed'}"
        )
        lines.append("")

        # File statistics
        lines.append("📊 File Statistics")
        lines.append("-" * 30)
        lines.append(f"Total Files:     {report.total_files}")
        lines.append(f"Processed:       {report.processed_files}")
        lines.append(f"Failed:          {report.failed_files}")
        lines.append(f"Success Rate:    {report.success_rate:.1f}%")
        lines.append("")

        # Packet statistics
        if report.total_packets > 0:
            lines.append("📦 Packet Statistics")
            lines.append("-" * 30)
            lines.append(f"Total Packets:   {report.total_packets:,}")
            lines.append(f"Modified:        {report.modified_packets:,}")
            lines.append(f"Modification:    {report.modification_rate:.1f}%")
            lines.append("")

        # Stage statistics
        if report.stage_reports and detailed:
            lines.append("⚙️  Stage Statistics")
            lines.append("-" * 30)
            for stage in report.stage_reports:
                stage_name = stage.get("stage_name", "Unknown")
                packets_processed = stage.get("packets_processed", 0)
                packets_modified = stage.get("packets_modified", 0)
                duration_ms = stage.get("duration_ms", 0.0)

                lines.append(f"{stage_name}:")
                lines.append(f"  Packets Processed: {packets_processed:,}")
                lines.append(f"  Packets Modified:  {packets_modified:,}")
                lines.append(f"  Duration:          {duration_ms:.1f} ms")
                lines.append("")

        # Warning information
        if report.warnings:
            lines.append("⚠️  Warnings")
            lines.append("-" * 30)
            for warning in report.warnings:
                lines.append(f"• {warning}")
            lines.append("")

        # Error information
        if report.errors:
            lines.append("❌ Errors")
            lines.append("-" * 30)
            for error in report.errors:
                lines.append(f"• {error}")
            lines.append("")

        # End
        lines.append("=" * 70)
        lines.append(
            f"Report generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        lines.append("=" * 70)

        return "\n".join(lines)

    def generate_json_report(self, report: ProcessingReport) -> str:
        """Generate JSON format report"""
        report_dict = {
            "report_version": "1.0",
            "generated_at": datetime.now().isoformat(),
            "basic_info": {
                "input_path": report.input_path,
                "output_path": report.output_path,
                "start_time": report.start_time.isoformat(),
                "end_time": report.end_time.isoformat(),
                "duration_seconds": report.duration_seconds,
                "duration_ms": report.duration_ms,
                "success": report.success,
            },
            "file_statistics": {
                "total_files": report.total_files,
                "processed_files": report.processed_files,
                "failed_files": report.failed_files,
                "success_rate": report.success_rate,
            },
            "packet_statistics": {
                "total_packets": report.total_packets,
                "modified_packets": report.modified_packets,
                "modification_rate": report.modification_rate,
            },
            "stage_reports": report.stage_reports,
            "warnings": report.warnings,
            "errors": report.errors,
        }

        return json.dumps(report_dict, indent=2, ensure_ascii=False)

    def save_report_to_file(
        self,
        report: ProcessingReport,
        output_path: str,
        format_type: str = "text",
        detailed: bool = False,
    ):
        """Save report to file"""
        try:
            if format_type.lower() == "json":
                content = self.generate_json_report(report)
                file_ext = ".json"
            else:
                content = self.generate_text_report(report, detailed)
                file_ext = ".txt"

            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"pktmask_report_{timestamp}{file_ext}"
            full_path = Path(output_path) / filename

            # Ensure directory exists
            full_path.parent.mkdir(parents=True, exist_ok=True)

            # Write file
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)

            logger.info(f"Report saved to: {full_path}")
            return str(full_path)

        except Exception as e:
            logger.error(f"Failed to save report: {e}")
            raise

    def _format_duration(self, seconds: float) -> str:
        """Format duration"""
        if seconds < 60:
            return f"{seconds:.2f} seconds"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            remaining_seconds = seconds % 60
            return f"{minutes}m {remaining_seconds:.2f}s"
        else:
            hours = int(seconds // 3600)
            remaining_minutes = int((seconds % 3600) // 60)
            remaining_seconds = seconds % 60
            return f"{hours}h {remaining_minutes}m {remaining_seconds:.2f}s"


# Global report service instance
_report_service = None


def get_report_service() -> ReportService:
    """Get report service instance（singleton pattern）"""
    global _report_service
    if _report_service is None:
        _report_service = ReportService()
    return _report_service
