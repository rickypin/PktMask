from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PacketList(BaseModel):
    """统一的报文列表抽象。后续实现可根据需要扩展字段，但外部代码必须通过
    `packets` 字段访问报文集合。
    """

    packets: List[Any] = Field(
        default_factory=list, description="原始或解析后的报文对象列表"
    )

    class Config:
        arbitrary_types_allowed = True
        frozen = True  # PacketList 本身仅作为只读数据传递


class StageStats(BaseModel):
    """单个 Stage 执行完成后的统计信息。所有数字指标均使用基本类型，
    方便序列化到 JSON 以及 GUI/CLI 展示。"""

    stage_name: str = Field(..., description="Stage 的唯一名称标识")
    packets_processed: int = Field(0, ge=0, description="处理的数据包数量")
    packets_modified: int = Field(0, ge=0, description="被修改的数据包数量")
    duration_ms: float = Field(0.0, ge=0.0, description="执行时长，毫秒")
    extra_metrics: Dict[str, Any] = Field(
        default_factory=dict, description="可选的附加统计指标"
    )

    class Config:
        frozen = True

    @property
    def original_ips(self) -> int:
        """Get the number of original IPs processed (for IP anonymization stages)"""
        return self.extra_metrics.get("original_ips", 0)

    @property
    def anonymized_ips(self) -> int:
        """Get the number of anonymized IPs (for IP anonymization stages)"""
        return self.extra_metrics.get("anonymized_ips", 0)


class ProcessResult(BaseModel):
    """Complete Pipeline execution result, used as unified return value for GUI/CLI/MCP."""

    success: bool = Field(..., description="整体是否成功")
    input_file: str = Field(..., description="输入文件路径")
    output_file: Optional[str] = Field(
        None, description="输出文件路径 (可能为 None，如果失败)"
    )
    duration_ms: float = Field(0.0, ge=0.0, description="总执行时长，毫秒")
    stage_stats: List[StageStats] = Field(
        default_factory=list, description="各 Stage 执行统计"
    )
    errors: List[str] = Field(default_factory=list, description="过程中捕获的错误信息")

    class Config:
        arbitrary_types_allowed = True
        frozen = True
