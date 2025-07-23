"""
掩码统计信息数据结构

定义了掩码处理过程中的统计信息和结果数据结构。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MaskingStats:
    """掩码处理统计信息

    包含了掩码处理过程的详细统计信息和结果。
    """

    success: bool  # 处理是否成功
    processed_packets: int = 0  # 处理的包总数
    modified_packets: int = 0  # 实际修改的包数
    masked_bytes: int = 0  # 掩码的字节数
    preserved_bytes: int = 0  # 保留的字节数
    execution_time: float = 0.0  # 执行时间（秒）
    input_file: str = ""  # 输入文件路径
    output_file: str = ""  # 输出文件路径
    errors: List[str] = field(default_factory=list)  # 错误信息列表
    warnings: List[str] = field(default_factory=list)  # 警告信息列表
    performance_metrics: Dict[str, Any] = field(default_factory=dict)  # 性能指标
    debug_info: Dict[str, Any] = field(default_factory=dict)  # 调试信息

    # 降级处理相关字段
    fallback_used: bool = False  # 是否使用了降级处理
    fallback_mode: Optional[str] = None  # 降级模式
    fallback_details: Dict[str, Any] = field(default_factory=dict)  # 降级处理详情

    # 验证结果
    validation_results: Dict[str, Any] = field(default_factory=dict)  # 验证结果
    error_details: Dict[str, Any] = field(default_factory=dict)  # 错误详情

    @property
    def total_bytes_processed(self) -> int:
        """获取处理的总字节数"""
        return self.masked_bytes + self.preserved_bytes

    @property
    def masking_ratio(self) -> float:
        """获取掩码比例"""
        total = self.total_bytes_processed
        if total == 0:
            return 0.0
        return self.masked_bytes / total

    @property
    def preservation_ratio(self) -> float:
        """获取保留比例"""
        total = self.total_bytes_processed
        if total == 0:
            return 0.0
        return self.preserved_bytes / total

    @property
    def modification_ratio(self) -> float:
        """获取修改包的比例"""
        if self.processed_packets == 0:
            return 0.0
        return self.modified_packets / self.processed_packets

    @property
    def processing_speed_mbps(self) -> float:
        """获取处理速度（MB/s）"""
        if self.execution_time == 0:
            return 0.0
        return (self.total_bytes_processed / (1024 * 1024)) / self.execution_time

    def add_error(self, error: str) -> None:
        """添加错误信息"""
        self.errors.append(error)
        self.success = False

    def add_warning(self, warning: str) -> None:
        """添加警告信息"""
        self.warnings.append(warning)

    def update_performance_metric(self, key: str, value: Any) -> None:
        """更新性能指标"""
        self.performance_metrics[key] = value

    def update_debug_info(self, key: str, value: Any) -> None:
        """更新调试信息"""
        self.debug_info[key] = value

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "success": self.success,
            "processed_packets": self.processed_packets,
            "modified_packets": self.modified_packets,
            "masked_bytes": self.masked_bytes,
            "preserved_bytes": self.preserved_bytes,
            "execution_time": self.execution_time,
            "input_file": self.input_file,
            "output_file": self.output_file,
            "errors": self.errors,
            "warnings": self.warnings,
            "performance_metrics": self.performance_metrics,
            "debug_info": self.debug_info,
            "fallback_used": self.fallback_used,
            "fallback_mode": self.fallback_mode,
            "fallback_details": self.fallback_details,
            "validation_results": self.validation_results,
            "error_details": self.error_details,
            "computed_metrics": {
                "total_bytes_processed": self.total_bytes_processed,
                "masking_ratio": self.masking_ratio,
                "preservation_ratio": self.preservation_ratio,
                "modification_ratio": self.modification_ratio,
                "processing_speed_mbps": self.processing_speed_mbps,
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MaskingStats:
        """从字典创建实例"""
        # 提取基础字段
        stats = cls(
            success=data.get("success", False),
            processed_packets=data.get("processed_packets", 0),
            modified_packets=data.get("modified_packets", 0),
            masked_bytes=data.get("masked_bytes", 0),
            preserved_bytes=data.get("preserved_bytes", 0),
            execution_time=data.get("execution_time", 0.0),
            input_file=data.get("input_file", ""),
            output_file=data.get("output_file", ""),
            errors=data.get("errors", []),
            warnings=data.get("warnings", []),
            performance_metrics=data.get("performance_metrics", {}),
            debug_info=data.get("debug_info", {}),
        )

        # 设置降级处理和验证相关字段
        stats.fallback_used = data.get("fallback_used", False)
        stats.fallback_mode = data.get("fallback_mode", None)
        stats.fallback_details = data.get("fallback_details", {})
        stats.validation_results = data.get("validation_results", {})
        stats.error_details = data.get("error_details", {})
        return stats

    def merge_with(self, other: MaskingStats) -> MaskingStats:
        """合并两个统计信息"""
        merged = MaskingStats(
            success=self.success and other.success,
            processed_packets=self.processed_packets + other.processed_packets,
            modified_packets=self.modified_packets + other.modified_packets,
            masked_bytes=self.masked_bytes + other.masked_bytes,
            preserved_bytes=self.preserved_bytes + other.preserved_bytes,
            execution_time=max(self.execution_time, other.execution_time),
            input_file=f"{self.input_file}, {other.input_file}",
            output_file=f"{self.output_file}, {other.output_file}",
            errors=self.errors + other.errors,
            warnings=self.warnings + other.warnings,
        )

        # 合并性能指标
        merged.performance_metrics = {
            **self.performance_metrics,
            **other.performance_metrics,
        }
        merged.debug_info = {**self.debug_info, **other.debug_info}

        return merged

    def __str__(self) -> str:
        """字符串表示"""
        status = "成功" if self.success else "失败"
        return (
            f"MaskingStats(状态={status}, "
            f"处理包数={self.processed_packets}, "
            f"修改包数={self.modified_packets}, "
            f"掩码字节={self.masked_bytes}, "
            f"保留字节={self.preserved_bytes}, "
            f"执行时间={self.execution_time:.2f}s)"
        )
