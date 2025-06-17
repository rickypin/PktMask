"""
执行结果模型

封装Enhanced Trim Payloads多阶段处理的执行结果，包括各阶段的统计信息和错误报告。
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from ..exceptions import ConfigValidationError


class ExecutionStatus(Enum):
    """执行状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StageStatus(Enum):
    """阶段状态枚举"""
    NOT_STARTED = "not_started"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StageResult:
    """
    单个阶段的执行结果
    """
    
    stage_name: str
    status: StageStatus = StageStatus.NOT_STARTED
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_seconds: float = 0.0
    
    # 统计信息
    input_file_size: int = 0
    output_file_size: int = 0
    packets_processed: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    # 阶段特定数据
    stage_data: Dict[str, Any] = field(default_factory=dict)
    
    def mark_started(self) -> None:
        """标记阶段开始"""
        self.status = StageStatus.RUNNING
        self.start_time = datetime.now()
    
    def mark_completed(self, **data) -> None:
        """标记阶段完成"""
        self.status = StageStatus.COMPLETED
        self.end_time = datetime.now()
        if self.start_time:
            self.duration_seconds = (self.end_time - self.start_time).total_seconds()
        
        # 更新阶段特定数据
        self.stage_data.update(data)
    
    def mark_failed(self, error_message: str) -> None:
        """标记阶段失败"""
        self.status = StageStatus.FAILED
        self.end_time = datetime.now()
        if self.start_time:
            self.duration_seconds = (self.end_time - self.start_time).total_seconds()
        
        self.errors.append(error_message)
    
    def add_warning(self, warning_message: str) -> None:
        """添加警告"""
        self.warnings.append(warning_message)
    
    def add_error(self, error_message: str) -> None:
        """添加错误"""
        self.errors.append(error_message)
    
    def is_successful(self) -> bool:
        """检查阶段是否成功"""
        return self.status == StageStatus.COMPLETED
    
    def get_summary(self) -> Dict[str, Any]:
        """获取阶段摘要"""
        return {
            'stage_name': self.stage_name,
            'status': self.status.value,
            'duration_seconds': self.duration_seconds,
            'packets_processed': self.packets_processed,
            'error_count': len(self.errors),
            'warning_count': len(self.warnings),
            'success': self.is_successful()
        }


@dataclass
class TrimmerConfig:
    """
    载荷裁切配置
    
    包含所有Enhanced Trim Payloads功能的配置参数（已移除HTTP支持）。
    """
    
    # TLS协议处理策略
    tls_keep_signaling: bool = True
    tls_keep_handshake: bool = True
    tls_keep_alerts: bool = True
    tls_trim_application_data: bool = True
    
    # 通用策略
    default_trim_strategy: str = "mask_all"  # mask_all, keep_all, mask_after_n
    default_keep_bytes: int = 0
    
    # 自定义协议处理
    custom_protocols: Dict[str, str] = field(default_factory=dict)
    custom_port_mappings: Dict[int, str] = field(default_factory=dict)
    
    # 处理模式
    processing_mode: str = "preserve_length"  # preserve_length, shrink_length
    validation_enabled: bool = True
    detailed_logging: bool = False
    
    # 性能参数
    chunk_size: int = 1000
    max_memory_usage_mb: int = 1024
    temp_dir: Optional[str] = None
    parallel_stages: bool = False
    
    # TShark配置
    tshark_executable: Optional[str] = None
    tshark_timeout_seconds: int = 300
    tshark_enable_reassembly: bool = True
    tshark_enable_defragmentation: bool = True
    
    # PyShark配置
    pyshark_display_filter: Optional[str] = None
    pyshark_override_prefs: Dict[str, str] = field(default_factory=dict)
    pyshark_keep_packets: bool = False
    
    # Scapy配置
    scapy_preserve_timestamps: bool = True
    scapy_recalculate_checksums: bool = True
    scapy_output_format: str = "pcap"  # pcap, pcapng
    
    def validate(self) -> List[str]:
        """
        验证配置参数
        
        Returns:
            验证错误列表，空列表表示验证通过
        """
        errors = []
        
        # 验证数值范围（移除HTTP验证）
        if self.default_keep_bytes < 0:
            errors.append("默认保留字节数不能为负数")
        elif self.default_keep_bytes > 65536:
            errors.append("默认保留字节数不能超过64KB")
        
        if self.chunk_size <= 0:
            errors.append("块大小必须大于0")
        elif self.chunk_size > 10000:
            errors.append("块大小过大，建议不超过10000")
        
        if self.max_memory_usage_mb <= 0:
            errors.append("最大内存使用量必须大于0")
        elif self.max_memory_usage_mb < 128:
            errors.append("最大内存使用量建议不少于128MB")
        elif self.max_memory_usage_mb > 32768:
            errors.append("最大内存使用量不能超过32GB")
        
        if self.tshark_timeout_seconds <= 0:
            errors.append("TShark超时时间必须大于0")
        elif self.tshark_timeout_seconds > 3600:
            errors.append("TShark超时时间不建议超过1小时")
        
        # 验证枚举值
        valid_processing_modes = ["preserve_length", "shrink_length"]
        if self.processing_mode not in valid_processing_modes:
            errors.append(f"处理模式必须是: {valid_processing_modes}")
        
        valid_trim_strategies = ["mask_all", "keep_all", "mask_after_n"]
        if self.default_trim_strategy not in valid_trim_strategies:
            errors.append(f"默认裁切策略必须是: {valid_trim_strategies}")
        
        valid_output_formats = ["pcap", "pcapng"]
        if self.scapy_output_format not in valid_output_formats:
            errors.append(f"输出格式必须是: {valid_output_formats}")
        
        # 交叉验证
        errors.extend(self._validate_cross_dependencies())
        
        return errors
    
    def _validate_cross_dependencies(self) -> List[str]:
        """验证配置项之间的交叉依赖（移除HTTP交叉验证）"""
        errors = []
        
        # TLS配置交叉验证
        if not self.tls_keep_signaling and not self.tls_keep_handshake:
            errors.append("TLS配置：至少需要保留信令或握手消息之一")
        
        # 内存和性能配置交叉验证
        if self.chunk_size * 1500 > self.max_memory_usage_mb * 1024 * 1024 / 4:
            errors.append("性能配置：块大小过大，可能导致内存不足")
        
        # 策略一致性验证
        if self.default_trim_strategy == "mask_after_n" and self.default_keep_bytes == 0:
            errors.append("策略配置：选择mask_after_n策略时，保留字节数不应为0")
        
        # TShark配置验证
        if self.tshark_enable_reassembly and not self.pyshark_keep_packets:
            errors.append("TShark配置建议：启用重组时建议保留PyShark包对象以提高精度")
        
        # 自定义协议验证（移除HTTP协议支持）
        for port, protocol in self.custom_port_mappings.items():
            if not isinstance(port, int) or port < 1 or port > 65535:
                errors.append(f"端口映射错误：端口{port}超出有效范围[1-65535]")
            if protocol not in ["tls", "tcp", "udp"]:  # 移除http
                errors.append(f"协议映射错误：不支持的协议类型'{protocol}'（HTTP支持已移除）")
        
        return errors
    
    def validate_strict(self) -> None:
        """严格验证，发现错误立即抛出异常"""
        errors = self.validate()
        if errors:
            first_error = errors[0]
            # 尝试确定错误的配置键
            config_key = "unknown"
            if "保留字节数" in first_error:
                config_key = "default_keep_bytes"
            elif "块大小" in first_error:
                config_key = "chunk_size"
            elif "内存" in first_error:
                config_key = "max_memory_usage_mb"
            elif "TShark" in first_error:
                config_key = "tshark_timeout_seconds"
            
            raise ConfigValidationError(
                config_key=config_key,
                config_value=getattr(self, config_key, None),
                reason=first_error
            )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式（移除HTTP字段）"""
        return {
            'tls_keep_signaling': self.tls_keep_signaling,
            'tls_keep_handshake': self.tls_keep_handshake,
            'tls_keep_alerts': self.tls_keep_alerts,
            'tls_trim_application_data': self.tls_trim_application_data,
            'default_trim_strategy': self.default_trim_strategy,
            'default_keep_bytes': self.default_keep_bytes,
            'custom_protocols': self.custom_protocols,
            'custom_port_mappings': self.custom_port_mappings,
            'processing_mode': self.processing_mode,
            'validation_enabled': self.validation_enabled,
            'detailed_logging': self.detailed_logging,
            'chunk_size': self.chunk_size,
            'max_memory_usage_mb': self.max_memory_usage_mb,
            'temp_dir': self.temp_dir,
            'parallel_stages': self.parallel_stages,
            'tshark_executable': self.tshark_executable,
            'tshark_timeout_seconds': self.tshark_timeout_seconds,
            'tshark_enable_reassembly': self.tshark_enable_reassembly,
            'tshark_enable_defragmentation': self.tshark_enable_defragmentation,
            'pyshark_display_filter': self.pyshark_display_filter,
            'pyshark_override_prefs': self.pyshark_override_prefs,
            'pyshark_keep_packets': self.pyshark_keep_packets,
            'scapy_preserve_timestamps': self.scapy_preserve_timestamps,
            'scapy_recalculate_checksums': self.scapy_recalculate_checksums,
            'scapy_output_format': self.scapy_output_format
        }


@dataclass
class ExecutionResult:
    """
    多阶段处理执行结果
    
    封装整个Enhanced Trim Payloads处理流程的执行结果，包括各阶段的详细信息。
    """
    
    # 基本信息
    input_file: str
    output_file: str
    config: TrimmerConfig
    
    # 执行状态
    status: ExecutionStatus = ExecutionStatus.PENDING
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    total_duration_seconds: float = 0.0
    
    # 阶段结果
    stages: Dict[str, StageResult] = field(default_factory=dict)
    
    # 整体统计
    total_packets_input: int = 0
    total_packets_output: int = 0
    total_bytes_input: int = 0
    total_bytes_output: int = 0
    compression_ratio: float = 0.0
    
    # 协议统计
    protocol_stats: Dict[str, int] = field(default_factory=dict)
    trimming_stats: Dict[str, Any] = field(default_factory=dict)
    
    # 错误和警告
    global_errors: List[str] = field(default_factory=list)
    global_warnings: List[str] = field(default_factory=list)
    
    def add_stage(self, stage_name: str) -> StageResult:
        """
        添加处理阶段
        
        Args:
            stage_name: 阶段名称
            
        Returns:
            新创建的阶段结果对象
        """
        stage_result = StageResult(stage_name=stage_name)
        self.stages[stage_name] = stage_result
        return stage_result
    
    def get_stage(self, stage_name: str) -> Optional[StageResult]:
        """获取指定阶段的结果"""
        return self.stages.get(stage_name)
    
    def mark_started(self) -> None:
        """标记执行开始"""
        self.status = ExecutionStatus.RUNNING
        self.start_time = datetime.now()
    
    def mark_completed(self) -> None:
        """标记执行完成"""
        self.status = ExecutionStatus.SUCCESS
        self.end_time = datetime.now()
        if self.start_time:
            self.total_duration_seconds = (self.end_time - self.start_time).total_seconds()
        
        # 计算压缩比
        if self.total_bytes_input > 0:
            self.compression_ratio = (1.0 - self.total_bytes_output / self.total_bytes_input) * 100
    
    def mark_failed(self, error_message: str) -> None:
        """标记执行失败"""
        self.status = ExecutionStatus.FAILED
        self.end_time = datetime.now()
        if self.start_time:
            self.total_duration_seconds = (self.end_time - self.start_time).total_seconds()
        
        self.global_errors.append(error_message)
    
    def mark_cancelled(self) -> None:
        """标记执行取消"""
        self.status = ExecutionStatus.CANCELLED
        self.end_time = datetime.now()
        if self.start_time:
            self.total_duration_seconds = (self.end_time - self.start_time).total_seconds()
    
    def add_global_error(self, error_message: str) -> None:
        """添加全局错误"""
        self.global_errors.append(error_message)
    
    def add_global_warning(self, warning_message: str) -> None:
        """添加全局警告"""
        self.global_warnings.append(warning_message)
    
    def is_successful(self) -> bool:
        """检查整体执行是否成功"""
        return (self.status == ExecutionStatus.SUCCESS and 
                all(stage.is_successful() for stage in self.stages.values()))
    
    def get_failed_stages(self) -> List[str]:
        """获取失败的阶段列表"""
        return [name for name, stage in self.stages.items() 
                if stage.status == StageStatus.FAILED]
    
    def get_total_error_count(self) -> int:
        """获取总错误数量"""
        stage_errors = sum(len(stage.errors) for stage in self.stages.values())
        return len(self.global_errors) + stage_errors
    
    def get_total_warning_count(self) -> int:
        """获取总警告数量"""
        stage_warnings = sum(len(stage.warnings) for stage in self.stages.values())
        return len(self.global_warnings) + stage_warnings
    
    def get_summary(self) -> Dict[str, Any]:
        """
        获取执行摘要
        
        Returns:
            包含主要执行信息的字典
        """
        return {
            'input_file': self.input_file,
            'output_file': self.output_file,
            'status': self.status.value,
            'success': self.is_successful(),
            'total_duration_seconds': self.total_duration_seconds,
            'total_packets_input': self.total_packets_input,
            'total_packets_output': self.total_packets_output,
            'compression_ratio': self.compression_ratio,
            'stages_completed': len([s for s in self.stages.values() if s.is_successful()]),
            'stages_total': len(self.stages),
            'total_errors': self.get_total_error_count(),
            'total_warnings': self.get_total_warning_count(),
            'failed_stages': self.get_failed_stages()
        }
    
    def get_detailed_report(self) -> Dict[str, Any]:
        """
        获取详细报告
        
        Returns:
            包含完整执行信息的字典
        """
        return {
            'summary': self.get_summary(),
            'config': self.config.to_dict(),
            'stages': {name: stage.get_summary() for name, stage in self.stages.items()},
            'protocol_stats': self.protocol_stats,
            'trimming_stats': self.trimming_stats,
            'global_errors': self.global_errors,
            'global_warnings': self.global_warnings,
            'timestamps': {
                'start_time': self.start_time.isoformat() if self.start_time else None,
                'end_time': self.end_time.isoformat() if self.end_time else None
            }
        } 