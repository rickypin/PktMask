"""
进度服务接口
提供统一的进度显示和回调管理服务
"""

from typing import Dict, Any, Callable, Optional, List
from dataclasses import dataclass
from enum import Enum
import time
import sys
from pktmask.core.events import PipelineEvents
from pktmask.infrastructure.logging import get_logger

logger = get_logger("ProgressService")


class ProgressStyle(Enum):
    """进度显示样式"""

    NONE = "none"
    SIMPLE = "simple"
    DETAILED = "detailed"
    RICH = "rich"


@dataclass
class ProgressState:
    """进度状态"""

    total_files: int = 0
    processed_files: int = 0
    current_file: Optional[str] = None
    current_stage: Optional[str] = None
    start_time: float = 0.0
    last_update_time: float = 0.0
    total_packets: int = 0
    processed_packets: int = 0


class ProgressService:
    """统一进度服务"""

    def __init__(
        self,
        style: ProgressStyle = ProgressStyle.SIMPLE,
        update_interval: float = 0.1,
        show_eta: bool = True,
    ):
        self.style = style
        self.update_interval = update_interval
        self.show_eta = show_eta
        self.state = ProgressState()
        self._callbacks: List[Callable[[PipelineEvents, Dict], None]] = []
        self._last_line_length = 0

    def add_callback(self, callback: Callable[[PipelineEvents, Dict], None]):
        """添加进度回调"""
        self._callbacks.append(callback)

    def remove_callback(self, callback: Callable[[PipelineEvents, Dict], None]):
        """移除进度回调"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def start_processing(self, total_files: int = 1):
        """开始处理"""
        self.state.total_files = total_files
        self.state.processed_files = 0
        self.state.start_time = time.time()
        self.state.last_update_time = self.state.start_time

        self._emit_event(
            PipelineEvents.PIPELINE_START,
            {"total_files": total_files, "start_time": self.state.start_time},
        )

        if self.style != ProgressStyle.NONE:
            if total_files == 1:
                self._print("🚀 Starting processing...")
            else:
                self._print(f"🚀 Starting processing {total_files} files...")

    def start_file(self, filename: str):
        """开始处理文件"""
        self.state.current_file = filename

        self._emit_event(
            PipelineEvents.FILE_START,
            {
                "path": filename,
                "current": self.state.processed_files + 1,
                "total": self.state.total_files,
            },
        )

        if self.style in [ProgressStyle.DETAILED, ProgressStyle.RICH]:
            progress = ((self.state.processed_files + 1) / self.state.total_files) * 100
            self._print(
                f"📄 [{self.state.processed_files + 1}/{self.state.total_files}] "
                f"({progress:.1f}%) {filename}"
            )

    def update_stage(self, stage_name: str, stats: Dict[str, Any]):
        """更新阶段进度"""
        self.state.current_stage = stage_name

        # 更新包统计
        packets_processed = stats.get("packets_processed", 0)
        if packets_processed > 0:
            self.state.processed_packets += packets_processed

        self._emit_event(
            PipelineEvents.STEP_SUMMARY,
            {"step_name": stage_name, "filename": self.state.current_file, **stats},
        )

        # 显示阶段进度
        if self.style == ProgressStyle.RICH:
            packets_modified = stats.get("packets_modified", 0)
            duration_ms = stats.get("duration_ms", 0.0)
            self._print(
                f"  ⚙️  [{stage_name}] {packets_processed:,} packets, "
                f"{packets_modified:,} modified, {duration_ms:.1f}ms"
            )
        elif self.style == ProgressStyle.DETAILED:
            self._update_progress_line(f"Processing: {stage_name}")

    def complete_file(self, filename: str, success: bool = True):
        """完成文件处理"""
        self.state.processed_files += 1

        self._emit_event(
            PipelineEvents.FILE_END,
            {
                "path": filename,
                "success": success,
                "processed": self.state.processed_files,
                "total": self.state.total_files,
            },
        )

        if self.style in [
            ProgressStyle.SIMPLE,
            ProgressStyle.DETAILED,
            ProgressStyle.RICH,
        ]:
            if success:
                self._print(f"✅ Completed: {filename}")
            else:
                self._print(f"❌ Failed: {filename}")

    def complete_processing(self):
        """完成所有处理"""
        end_time = time.time()
        duration = end_time - self.state.start_time

        self._emit_event(
            PipelineEvents.PIPELINE_END,
            {
                "total_files": self.state.total_files,
                "processed_files": self.state.processed_files,
                "duration_seconds": duration,
                "total_packets": self.state.total_packets,
                "processed_packets": self.state.processed_packets,
            },
        )

        if self.style != ProgressStyle.NONE:
            self._clear_progress_line()
            if self.state.processed_files == self.state.total_files:
                self._print(
                    f"🎉 All {self.state.total_files} files processed successfully!"
                )
            else:
                failed = self.state.total_files - self.state.processed_files
                self._print(
                    f"⚠️  Processed {self.state.processed_files}/{self.state.total_files} files "
                    f"({failed} failed)"
                )

            # 显示总耗时
            if duration < 60:
                self._print(f"⏱️  Total time: {duration:.2f} seconds")
            else:
                minutes = int(duration // 60)
                seconds = duration % 60
                self._print(f"⏱️  Total time: {minutes}m {seconds:.2f}s")

    def report_error(self, error_message: str):
        """报告错误"""
        self._emit_event(PipelineEvents.ERROR, {"message": error_message})

        if self.style != ProgressStyle.NONE:
            self._clear_progress_line()
            self._print(f"❌ Error: {error_message}")

    def _emit_event(self, event_type: PipelineEvents, data: Dict[str, Any]):
        """发送事件到所有回调"""
        for callback in self._callbacks:
            try:
                callback(event_type, data)
            except Exception as e:
                logger.error(f"Progress callback error: {e}")

    def _update_progress_line(self, message: str):
        """更新进度行（覆盖式显示）"""
        if self.style not in [ProgressStyle.DETAILED]:
            return

        # 计算进度百分比
        if self.state.total_files > 0:
            progress = (self.state.processed_files / self.state.total_files) * 100
            progress_bar = self._create_progress_bar(progress)
            full_message = f"\r{progress_bar} {message}"
        else:
            full_message = f"\r{message}"

        # 清除之前的行
        if self._last_line_length > 0:
            sys.stdout.write("\r" + " " * self._last_line_length + "\r")

        # 写入新消息
        sys.stdout.write(full_message)
        sys.stdout.flush()
        self._last_line_length = len(full_message)

    def _clear_progress_line(self):
        """清除进度行"""
        if self._last_line_length > 0:
            sys.stdout.write("\r" + " " * self._last_line_length + "\r")
            sys.stdout.flush()
            self._last_line_length = 0

    def _create_progress_bar(self, progress: float, width: int = 20) -> str:
        """创建进度条"""
        filled = int(width * progress / 100)
        bar = "█" * filled + "░" * (width - filled)
        return f"[{bar}] {progress:.1f}%"

    def _print(self, message: str):
        """打印消息"""
        self._clear_progress_line()
        print(message)
        sys.stdout.flush()


# 便捷函数
def create_progress_service(
    style_str: str = "simple", update_interval: float = 0.1, show_eta: bool = True
) -> ProgressService:
    """创建进度服务实例"""
    try:
        style = ProgressStyle(style_str.lower())
    except ValueError:
        style = ProgressStyle.SIMPLE

    return ProgressService(style, update_interval, show_eta)


def create_cli_progress_callback(
    verbose: bool = False, show_stages: bool = False
) -> Callable[[PipelineEvents, Dict], None]:
    """创建CLI专用的进度回调函数"""
    progress_service = create_progress_service("detailed" if verbose else "simple")

    def progress_callback(event_type: PipelineEvents, data: Dict[str, Any]):
        """CLI进度回调实现"""
        if event_type == PipelineEvents.PIPELINE_START:
            total_files = data.get("total_files", 1)
            progress_service.start_processing(total_files)

        elif event_type == PipelineEvents.FILE_START:
            filename = data.get("path", "Unknown")
            progress_service.start_file(filename)

        elif event_type == PipelineEvents.STEP_SUMMARY and show_stages:
            stage_name = data.get("step_name", "Unknown")
            progress_service.update_stage(stage_name, data)

        elif event_type == PipelineEvents.FILE_END:
            filename = data.get("path", "Unknown")
            success = data.get("success", True)
            progress_service.complete_file(filename, success)

        elif event_type == PipelineEvents.PIPELINE_END:
            progress_service.complete_processing()

        elif event_type == PipelineEvents.ERROR:
            error_message = data.get("message", "Unknown error")
            progress_service.report_error(error_message)

    return progress_callback
