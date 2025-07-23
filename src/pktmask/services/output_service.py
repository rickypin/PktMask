"""
输出服务接口
提供统一的输出格式化和显示服务
"""

from typing import Dict, Any, List, Optional, TextIO
from enum import Enum
import sys
import json
from datetime import datetime
from pktmask.infrastructure.logging import get_logger

logger = get_logger("OutputService")


class OutputFormat(Enum):
    """输出格式枚举"""

    TEXT = "text"
    JSON = "json"
    SUMMARY = "summary"
    DETAILED = "detailed"


class OutputLevel(Enum):
    """输出详细程度枚举"""

    MINIMAL = "minimal"
    NORMAL = "normal"
    VERBOSE = "verbose"
    DEBUG = "debug"


class OutputService:
    """统一输出服务"""

    def __init__(
        self,
        output_format: OutputFormat = OutputFormat.TEXT,
        output_level: OutputLevel = OutputLevel.NORMAL,
        output_stream: TextIO = sys.stdout,
    ):
        self.format = output_format
        self.level = output_level
        self.stream = output_stream
        self._stats_buffer = []

    def print_processing_start(self, input_path: str, total_files: int = 1):
        """打印处理开始信息"""
        if self.level == OutputLevel.MINIMAL:
            return

        if total_files == 1:
            self._print(f"🚀 Processing file: {input_path}")
        else:
            self._print(f"🚀 Processing {total_files} files from: {input_path}")

    def print_file_progress(self, filename: str, current: int, total: int):
        """打印文件处理进度"""
        if self.level == OutputLevel.MINIMAL:
            return

        progress = (current / total) * 100 if total > 0 else 0
        self._print(f"📄 [{current}/{total}] ({progress:.1f}%) Processing: {filename}")

    def print_stage_progress(self, stage_name: str, stats: Dict[str, Any]):
        """打印阶段处理进度"""
        if self.level not in [OutputLevel.VERBOSE, OutputLevel.DEBUG]:
            return

        packets_processed = stats.get("packets_processed", 0)
        packets_modified = stats.get("packets_modified", 0)
        duration_ms = stats.get("duration_ms", 0.0)

        self._print(
            f"  ⚙️  [{stage_name}] Processed {packets_processed:,} packets, "
            f"modified {packets_modified:,} packets, took {duration_ms:.1f} ms"
        )

    def print_file_complete(self, input_file: str, output_file: str, success: bool):
        """打印文件处理完成信息"""
        if self.level == OutputLevel.MINIMAL and success:
            return

        if success:
            self._print(f"✅ Completed: {input_file} → {output_file}")
        else:
            self._print(f"❌ Failed: {input_file}")

    def print_processing_summary(self, result: Dict[str, Any]):
        """打印处理摘要"""
        if self.format == OutputFormat.JSON:
            self._print_json_summary(result)
        else:
            self._print_text_summary(result)

    def print_error(self, error_message: str):
        """打印错误信息"""
        self._print(f"❌ Error: {error_message}", file=sys.stderr)

    def print_warning(self, warning_message: str):
        """打印警告信息"""
        if self.level == OutputLevel.MINIMAL:
            return
        self._print(f"⚠️  Warning: {warning_message}")

    def _print_text_summary(self, result: Dict[str, Any]):
        """打印文本格式摘要"""
        success = result.get("success", False)
        duration_ms = result.get("duration_ms", 0.0)

        # 基本信息
        if success:
            self._print("✅ Processing completed successfully!")
        else:
            self._print("❌ Processing completed with errors!")

        # 时间信息
        duration_sec = duration_ms / 1000.0
        if duration_sec < 60:
            self._print(f"⏱️  Duration: {duration_sec:.2f} seconds")
        else:
            minutes = int(duration_sec // 60)
            seconds = duration_sec % 60
            self._print(f"⏱️  Duration: {minutes}m {seconds:.2f}s")

        # 文件统计
        if "total_files" in result:
            total_files = result["total_files"]
            processed_files = result.get("processed_files", 0)
            failed_files = result.get("failed_files", 0)

            self._print(f"📊 Files: {processed_files}/{total_files} processed")
            if failed_files > 0:
                self._print(f"   Failed: {failed_files}")

        # 输出文件信息
        if "output_file" in result:
            self._print(f"📄 Output: {result['output_file']}")
        elif "output_dir" in result:
            self._print(f"📁 Output directory: {result['output_dir']}")

        # 详细统计（verbose模式）
        if self.level in [OutputLevel.VERBOSE, OutputLevel.DEBUG]:
            self._print_detailed_stats(result)

        # 错误信息
        errors = result.get("errors", [])
        if errors:
            self._print("\n❌ Errors encountered:")
            for error in errors[:5]:  # 只显示前5个错误
                self._print(f"   • {error}")
            if len(errors) > 5:
                self._print(f"   ... and {len(errors) - 5} more errors")

    def _print_detailed_stats(self, result: Dict[str, Any]):
        """打印详细统计信息"""
        stage_stats = result.get("stage_stats", [])
        if not stage_stats:
            return

        self._print("\n📈 Stage Statistics:")
        total_packets = 0
        total_modified = 0

        for stats in stage_stats:
            if isinstance(stats, dict):
                stage_name = stats.get("stage_name", "Unknown")
                packets_processed = stats.get("packets_processed", 0)
                packets_modified = stats.get("packets_modified", 0)
                duration_ms = stats.get("duration_ms", 0.0)

                self._print(f"   {stage_name}:")
                self._print(f"     Packets processed: {packets_processed:,}")
                self._print(f"     Packets modified: {packets_modified:,}")
                self._print(f"     Duration: {duration_ms:.1f} ms")

                total_packets = max(total_packets, packets_processed)
                total_modified += packets_modified

        if total_packets > 0:
            modification_rate = (total_modified / total_packets) * 100
            self._print(f"\n   Overall modification rate: {modification_rate:.1f}%")

    def _print_json_summary(self, result: Dict[str, Any]):
        """打印JSON格式摘要"""
        # 添加时间戳
        result_with_timestamp = {"timestamp": datetime.now().isoformat(), **result}

        json_str = json.dumps(result_with_timestamp, indent=2, ensure_ascii=False)
        self._print(json_str)

    def _print(self, message: str, file: Optional[TextIO] = None):
        """统一打印方法"""
        output_file = file or self.stream
        print(message, file=output_file)
        output_file.flush()


# 便捷函数
def create_output_service(
    format_str: str = "text",
    level_str: str = "normal",
    output_stream: TextIO = sys.stdout,
) -> OutputService:
    """创建输出服务实例"""
    try:
        output_format = OutputFormat(format_str.lower())
    except ValueError:
        output_format = OutputFormat.TEXT

    try:
        output_level = OutputLevel(level_str.lower())
    except ValueError:
        output_level = OutputLevel.NORMAL

    return OutputService(output_format, output_level, output_stream)
