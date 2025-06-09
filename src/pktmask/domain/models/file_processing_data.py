"""
文件处理数据模型

定义文件处理过程中的数据结构。
"""

from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator
from enum import Enum


class FileStatus(str, Enum):
    """文件处理状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class FileType(str, Enum):
    """文件类型"""
    PCAP = "pcap"
    PCAPNG = "pcapng"
    UNKNOWN = "unknown"


class FileInfo(BaseModel):
    """文件基本信息"""
    filename: str = Field(..., description="文件名")
    file_path: str = Field(..., description="文件完整路径")
    file_type: FileType = Field(..., description="文件类型")
    size_bytes: int = Field(default=0, ge=0, description="文件大小(字节)")
    creation_time: Optional[datetime] = Field(default=None, description="文件创建时间")
    modification_time: Optional[datetime] = Field(default=None, description="文件修改时间")
    
    @field_validator('file_type', mode='before')
    @classmethod
    def determine_file_type(cls, v, info):
        """根据文件名确定文件类型"""
        if v != FileType.UNKNOWN:
            return v
        
        filename = info.data.get('filename', '') if info.data else ''
        if filename.lower().endswith('.pcap'):
            return FileType.PCAP
        elif filename.lower().endswith('.pcapng'):
            return FileType.PCAPNG
        else:
            return FileType.UNKNOWN
    
    def get_size_string(self) -> str:
        """获取格式化的文件大小字符串"""
        if self.size_bytes < 1024:
            return f"{self.size_bytes} B"
        elif self.size_bytes < 1024 * 1024:
            return f"{self.size_bytes / 1024:.1f} KB"
        elif self.size_bytes < 1024 * 1024 * 1024:
            return f"{self.size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{self.size_bytes / (1024 * 1024 * 1024):.1f} GB"
    
    @classmethod
    def from_path(cls, file_path: str) -> 'FileInfo':
        """从文件路径创建FileInfo对象"""
        path = Path(file_path)
        
        size = 0
        creation_time = None
        modification_time = None
        
        try:
            if path.exists():
                stat = path.stat()
                size = stat.st_size
                creation_time = datetime.fromtimestamp(stat.st_ctime)
                modification_time = datetime.fromtimestamp(stat.st_mtime)
        except (OSError, ValueError):
            pass  # 忽略文件系统错误
        
        return cls(
            filename=path.name,
            file_path=str(path),
            file_type=FileType.UNKNOWN,  # 将通过validator自动确定
            size_bytes=size,
            creation_time=creation_time,
            modification_time=modification_time
        )


class ProcessingProgress(BaseModel):
    """处理进度信息"""
    current_step: Optional[str] = Field(default=None, description="当前处理步骤")
    steps_completed: int = Field(default=0, ge=0, description="已完成步骤数")
    total_steps: int = Field(default=0, ge=0, description="总步骤数")
    packets_processed: int = Field(default=0, ge=0, description="已处理包数")
    estimated_total_packets: int = Field(default=0, ge=0, description="估计总包数")
    
    def get_step_progress_percentage(self) -> float:
        """获取步骤进度百分比"""
        if self.total_steps == 0:
            return 0.0
        return (self.steps_completed / self.total_steps) * 100.0
    
    def get_packet_progress_percentage(self) -> float:
        """获取包处理进度百分比"""
        if self.estimated_total_packets == 0:
            return 0.0
        return min((self.packets_processed / self.estimated_total_packets) * 100.0, 100.0)


class ProcessingContext(BaseModel):
    """处理上下文信息"""
    input_directory: str = Field(..., description="输入目录")
    output_directory: str = Field(..., description="输出目录")
    selected_steps: List[str] = Field(default_factory=list, description="选择的处理步骤")
    configuration: Dict[str, Any] = Field(default_factory=dict, description="处理配置")
    worker_id: Optional[str] = Field(default=None, description="工作线程ID")
    
    def has_step(self, step_name: str) -> bool:
        """检查是否包含指定步骤"""
        return step_name in self.selected_steps
    
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        return self.configuration.get(key, default)


class OutputInfo(BaseModel):
    """输出文件信息"""
    output_filename: Optional[str] = Field(default=None, description="输出文件名")
    output_path: Optional[str] = Field(default=None, description="输出文件路径")
    output_size_bytes: int = Field(default=0, ge=0, description="输出文件大小")
    intermediate_files: List[str] = Field(default_factory=list, description="中间文件列表")
    
    def add_intermediate_file(self, file_path: str):
        """添加中间文件"""
        if file_path not in self.intermediate_files:
            self.intermediate_files.append(file_path)
    
    def get_size_reduction_ratio(self, original_size: int) -> float:
        """获取大小减少比例"""
        if original_size == 0:
            return 0.0
        return ((original_size - self.output_size_bytes) / original_size) * 100.0


class ProcessingError(BaseModel):
    """处理错误信息"""
    error_message: str = Field(..., description="错误消息")
    error_code: Optional[str] = Field(default=None, description="错误代码")
    error_step: Optional[str] = Field(default=None, description="出错的步骤")
    error_time: datetime = Field(default_factory=datetime.now, description="错误发生时间")
    traceback: Optional[str] = Field(default=None, description="错误堆栈")
    is_recoverable: bool = Field(default=False, description="是否可恢复")


class FileProcessingData(BaseModel):
    """完整的文件处理数据"""
    file_info: FileInfo = Field(..., description="文件信息")
    status: FileStatus = Field(default=FileStatus.PENDING, description="处理状态")
    context: ProcessingContext = Field(..., description="处理上下文")
    progress: ProcessingProgress = Field(default_factory=ProcessingProgress, description="处理进度")
    output_info: OutputInfo = Field(default_factory=OutputInfo, description="输出信息")
    
    # 时间信息
    start_time: Optional[datetime] = Field(default=None, description="开始处理时间")
    end_time: Optional[datetime] = Field(default=None, description="结束处理时间")
    duration_ms: int = Field(default=0, ge=0, description="处理耗时(毫秒)")
    
    # 错误信息
    errors: List[ProcessingError] = Field(default_factory=list, description="处理错误列表")
    
    # 元数据
    metadata: Dict[str, Any] = Field(default_factory=dict, description="附加元数据")
    
    def start_processing(self):
        """开始处理"""
        self.status = FileStatus.PROCESSING
        self.start_time = datetime.now()
    
    def complete_processing(self):
        """完成处理"""
        self.status = FileStatus.COMPLETED
        self.end_time = datetime.now()
        if self.start_time:
            delta = self.end_time - self.start_time
            self.duration_ms = int(delta.total_seconds() * 1000)
    
    def fail_processing(self, error: ProcessingError):
        """处理失败"""
        self.status = FileStatus.FAILED
        self.end_time = datetime.now()
        if self.start_time:
            delta = self.end_time - self.start_time
            self.duration_ms = int(delta.total_seconds() * 1000)
        self.errors.append(error)
    
    def skip_processing(self, reason: str):
        """跳过处理"""
        self.status = FileStatus.SKIPPED
        self.end_time = datetime.now()
        self.metadata['skip_reason'] = reason
    
    def add_error(self, error: ProcessingError):
        """添加错误信息"""
        self.errors.append(error)
    
    def has_errors(self) -> bool:
        """检查是否有错误"""
        return len(self.errors) > 0
    
    def get_last_error(self) -> Optional[ProcessingError]:
        """获取最后一个错误"""
        return self.errors[-1] if self.errors else None
    
    def is_completed_successfully(self) -> bool:
        """检查是否成功完成"""
        return self.status == FileStatus.COMPLETED and not self.has_errors()
    
    def get_duration_string(self) -> str:
        """获取格式化的耗时字符串"""
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
    
    def get_summary(self) -> Dict[str, Any]:
        """获取处理摘要"""
        return {
            'filename': self.file_info.filename,
            'status': self.status.value,
            'duration': self.get_duration_string(),
            'file_size': self.file_info.get_size_string(),
            'output_size': self.output_info.output_size_bytes,
            'size_reduction': self.output_info.get_size_reduction_ratio(self.file_info.size_bytes),
            'steps_completed': self.progress.steps_completed,
            'total_steps': self.progress.total_steps,
            'packets_processed': self.progress.packets_processed,
            'error_count': len(self.errors),
            'is_successful': self.is_completed_successfully()
        } 