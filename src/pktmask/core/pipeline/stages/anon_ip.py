from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, Optional
import warnings

from pktmask.core.pipeline.base_stage import StageBase
from pktmask.core.pipeline.models import StageStats
from pktmask.core.processors.ip_anonymizer import IPAnonymizer, ProcessorConfig, ProcessorResult


class AnonStage(StageBase):
    """基于 :class:`~pktmask.core.processors.ip_anonymizer.IPAnonymizer` 的 Pipeline 匿名化阶段。"""

    name: str = "AnonStage"

    def __init__(self, config: Optional[Dict[str, Any]] | None = None):
        self._config: Dict[str, Any] = config or {}
        proc_cfg = ProcessorConfig(enabled=True, name="anon_ip")
        self._processor: IPAnonymizer = IPAnonymizer(proc_cfg)
        super().__init__()

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------
    def initialize(self, config: Optional[Dict[str, Any]] | None = None) -> None:  # noqa: D401
        if config is not None:
            self._config.update(config)

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
        """对单文件执行IP匿名化处理，并返回 :class:`StageStats`."""

        input_path = str(input_path)
        output_path = str(output_path)

        start_ts = time.time()

        result: ProcessorResult = self._processor.process_file(input_path, output_path)

        duration_ms = (time.time() - start_ts) * 1000

        if not result.success:
            warnings.warn(
                f"AnonStage processing failed: {result.error}",
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
            packets_modified=int(stats_dict.get("anonymized_packets", 0)),
            duration_ms=duration_ms,
            extra_metrics=stats_dict,
        ) 