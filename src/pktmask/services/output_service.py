"""
Output service interface
Provides unified output formatting and display services
"""

import json
import sys
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional, TextIO

from pktmask.infrastructure.logging import get_logger

logger = get_logger("OutputService")


class OutputFormat(Enum):
    """Output format enumeration"""

    TEXT = "text"
    JSON = "json"
    SUMMARY = "summary"
    DETAILED = "detailed"


class OutputLevel(Enum):
    """Output verbosity enumeration"""

    MINIMAL = "minimal"
    NORMAL = "normal"
    VERBOSE = "verbose"
    DEBUG = "debug"


class OutputService:
    """Unified output service"""

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
        """Print processing start information"""
        if self.level == OutputLevel.MINIMAL:
            return

        if total_files == 1:
            self._print(f"🚀 Processing file: {input_path}")
        else:
            self._print(f"🚀 Processing {total_files} files from: {input_path}")

    def print_file_progress(self, filename: str, current: int, total: int):
        """Print file processing progress"""
        if self.level == OutputLevel.MINIMAL:
            return

        progress = (current / total) * 100 if total > 0 else 0
        self._print(f"📄 [{current}/{total}] ({progress:.1f}%) Processing: {filename}")

    def print_stage_progress(self, stage_name: str, stats: Dict[str, Any]):
        """Print stage processing progress"""
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
        """Print file processing completion information"""
        if self.level == OutputLevel.MINIMAL and success:
            return

        if success:
            self._print(f"✅ Completed: {input_file} → {output_file}")
        else:
            self._print(f"❌ Failed: {input_file}")

    def print_processing_summary(self, result: Dict[str, Any]):
        """Print processing summary"""
        if self.format == OutputFormat.JSON:
            self._print_json_summary(result)
        else:
            self._print_text_summary(result)

    def print_error(self, error_message: str):
        """Print error information"""
        self._print(f"❌ Error: {error_message}", file=sys.stderr)

    def print_warning(self, warning_message: str):
        """Print warning information"""
        if self.level == OutputLevel.MINIMAL:
            return
        self._print(f"⚠️  Warning: {warning_message}")

    def _print_text_summary(self, result: Dict[str, Any]):
        """Print text format summary"""
        success = result.get("success", False)
        duration_ms = result.get("duration_ms", 0.0)

        # Basic information
        if success:
            self._print("✅ Processing completed successfully!")
        else:
            self._print("❌ Processing completed with errors!")

        # Time information
        duration_sec = duration_ms / 1000.0
        if duration_sec < 60:
            self._print(f"⏱️  Duration: {duration_sec:.2f} seconds")
        else:
            minutes = int(duration_sec // 60)
            seconds = duration_sec % 60
            self._print(f"⏱️  Duration: {minutes}m {seconds:.2f}s")

        # File statistics
        if "total_files" in result:
            total_files = result["total_files"]
            processed_files = result.get("processed_files", 0)
            failed_files = result.get("failed_files", 0)

            self._print(f"📊 Files: {processed_files}/{total_files} processed")
            if failed_files > 0:
                self._print(f"   Failed: {failed_files}")

        # Output file information
        if "output_file" in result:
            self._print(f"📄 Output: {result['output_file']}")
        elif "output_dir" in result:
            self._print(f"📁 Output directory: {result['output_dir']}")

        # Detailed statistics（verbosemode）
        if self.level in [OutputLevel.VERBOSE, OutputLevel.DEBUG]:
            self._print_detailed_stats(result)

        # Error information
        errors = result.get("errors", [])
        if errors:
            self._print("\n❌ Errors encountered:")
            for error in errors[:5]:  # Only show first5errors
                self._print(f"   • {error}")
            if len(errors) > 5:
                self._print(f"   ... and {len(errors) - 5} more errors")

    def _print_detailed_stats(self, result: Dict[str, Any]):
        """Print detailed statistics information"""
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
        """Print JSON format summary"""
        # Add timestamp
        result_with_timestamp = {"timestamp": datetime.now().isoformat(), **result}

        json_str = json.dumps(result_with_timestamp, indent=2, ensure_ascii=False)
        self._print(json_str)

    def _print(self, message: str, file: Optional[TextIO] = None):
        """Unified print method"""
        output_file = file or self.stream
        print(message, file=output_file)
        output_file.flush()


# Convenience functions
def create_output_service(
    format_str: str = "text",
    level_str: str = "normal",
    output_stream: TextIO = sys.stdout,
) -> OutputService:
    """Create output service instance"""
    try:
        output_format = OutputFormat(format_str.lower())
    except ValueError:
        output_format = OutputFormat.TEXT

    try:
        output_level = OutputLevel(level_str.lower())
    except ValueError:
        output_level = OutputLevel.NORMAL

    return OutputService(output_format, output_level, output_stream)
