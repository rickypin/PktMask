from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, Optional
import warnings

from pktmask.core.pipeline.base_stage import StageBase
from pktmask.core.pipeline.models import StageStats
from pktmask.core.processors.deduplicator import DeduplicationProcessor, ProcessorConfig, ProcessorResult


class DeduplicationStage(StageBase):
    """基于 :class:`~pktmask.core.processors.deduplicator.DeduplicationProcessor` 的 Pipeline 去重阶段。"""

    name: str = "DeduplicationStage"

    def __init__(self, config: Optional[Dict[str, Any]] | None = None):
        # Stage config 目前无需特殊解析，仅透传给底层处理器
        self._config: Dict[str, Any] = config or {}
        # Deduplicator 不直接消耗额外配置，构造轻量对象即可
        proc_cfg = ProcessorConfig(enabled=True, name="dedup_packet")
        self._processor: DeduplicationProcessor = DeduplicationProcessor(proc_cfg)
        super().__init__()

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------
    def initialize(self, config: Optional[Dict[str, Any]] | None = None) -> None:  # noqa: D401
        """初始化 Deduplicator。

        若调用方在 *runtime* 传递新的 ``config`` 参数，则覆盖构造时提供的
        `_config`。目前 Deduplicator 并未使用此配置，但保留以兼容未来扩展。"""

        if config is not None:
            self._config.update(config)

        # Deduplicator.initialize 可能在第一次调用 process_file 时被隐式调用，
        # 这里显式初始化可避免首包额外开销。
        self._processor.initialize()
        super().initialize(self._config)

    # ------------------------------------------------------------------
    # 核心处理
    # ------------------------------------------------------------------
    def process_file(
        self,
        input_path: str | Path,
        output_path: str | Path,
    ) -> StageStats | Dict[str, Any] | None:
        """Execute deduplication processing on a single file and return unified :class:`StageStats`."""

        input_path = str(input_path)
        output_path = str(output_path)

        start_ts = time.time()

        # Deduplicator::process_file 会在内部完成初始化检测
        result: ProcessorResult = self._processor.process_file(input_path, output_path)

        duration_ms = (time.time() - start_ts) * 1000

        if not result.success:
            warnings.warn(
                f"DeduplicationStage processing failed: {result.error}",
                RuntimeWarning,
                stacklevel=2,
            )
            return StageStats(
                stage_name=self.name,
                packets_processed=0,
                packets_modified=0,
                duration_ms=duration_ms,
                extra_metrics={"error": result.error or "unknown"},
            )

        stats_dict: Dict[str, Any] = result.stats or {}

        return StageStats(
            stage_name=self.name,
            packets_processed=int(stats_dict.get("total_packets", 0)),
            packets_modified=int(stats_dict.get("removed_count", 0)),
            duration_ms=duration_ms,
            extra_metrics=stats_dict,
        )


# 兼容性别名 - 保持向后兼容
class DedupStage(DeduplicationStage):
    """兼容性别名，请使用 DeduplicationStage 代替。
    
    .. deprecated:: 当前版本
       请使用 :class:`DeduplicationStage` 代替 :class:`DedupStage`
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] | None = None):
        warnings.warn(
            "DedupStage is deprecated, please use DeduplicationStage instead",
            DeprecationWarning,
            stacklevel=2
        )
        super().__init__(config)
