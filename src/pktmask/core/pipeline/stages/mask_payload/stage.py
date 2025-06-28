from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from scapy.all import rdpcap, wrpcap, Packet  # type: ignore

from pktmask.core.pipeline.base_stage import StageBase
from pktmask.core.pipeline.models import StageStats
from pktmask.core.tcp_payload_masker.core.blind_masker import BlindPacketMasker
from pktmask.core.tcp_payload_masker.api.types import MaskingRecipe  # 核心数据结构
from pktmask.core.tcp_payload_masker.utils.helpers import (
    create_masking_recipe_from_dict,
)


class MaskStage(StageBase):
    """Payload Mask 处理阶段。

    该 Stage 封装了底层 **BlindPacketMasker** 引擎，遵循新的 *StageBase* 接口
    ，可被统一的 ``pipeline.executor`` 调度。

    配置 ``config`` 字典支持以下键：

    1. ``recipe``: 直接传入 :class:`MaskingRecipe` 实例。
    2. ``recipe_dict``: 传入兼容 ``create_masking_recipe_from_dict`` 的字典。
    3. ``recipe_path``: 指向 JSON 文件路径；文件内容必须为配方字典格式。

    当三个键均不存在或解析失败时，本 Stage 将回退为 *透传模式* —— 复制
    输入文件至输出路径而不做任何改动。
    """

    name: str = "MaskStage"

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------
    def __init__(self, config: Optional[Dict[str, Any]] | None = None):
        self._config: Dict[str, Any] = config or {}
        self._masker: Optional[BlindPacketMasker] = None
        super().__init__()

    # NOTE: StageBase.initialize 仅标记 _initialized，我们在子类中解析配方
    def initialize(self, config: Optional[Dict[str, Any]] | None = None) -> None:  # noqa: D401
        """初始化 Stage。

        该方法将在 Pipeline 构建阶段被调用，用于提前解析掩码配方并创建
        ``BlindPacketMasker`` 实例以便复用。"""

        # 先调用父类实现，确保 _initialized 状态正确
        super().initialize(config)

        # 合并外部传入的 runtime config — 后者优先生效
        merged_cfg: Dict[str, Any] = {**self._config, **(config or {})}

        recipe_obj: Optional[MaskingRecipe] = None

        if isinstance(merged_cfg.get("recipe"), MaskingRecipe):
            recipe_obj = merged_cfg["recipe"]
        elif "recipe_dict" in merged_cfg and isinstance(merged_cfg["recipe_dict"], dict):
            try:
                recipe_obj = create_masking_recipe_from_dict(merged_cfg["recipe_dict"])
            except Exception as exc:  # pylint: disable=broad-except
                # 延迟至 process_file 时再报错/透传
                recipe_obj = None
        elif "recipe_path" in merged_cfg:
            path = Path(merged_cfg["recipe_path"])
            if path.is_file():
                try:
                    with path.open("r", encoding="utf-8") as fp:
                        data = json.load(fp)
                    recipe_obj = create_masking_recipe_from_dict(data)
                except Exception:  # pylint: disable=broad-except
                    recipe_obj = None

        # 创建 BlindPacketMasker（若配方有效）
        if recipe_obj is not None:
            self._masker = BlindPacketMasker(masking_recipe=recipe_obj)

    # ------------------------------------------------------------------
    # 核心方法
    # ------------------------------------------------------------------
    def process_file(
        self,
        input_path: str | Path,
        output_path: str | Path,
    ) -> StageStats | Dict[str, Any] | None:
        """对单个文件应用载荷掩码。

        Args:
            input_path: 输入 PCAP/PCAPNG 文件路径。
            output_path: 输出处理后文件路径。"""

        input_path = Path(input_path)
        output_path = Path(output_path)

        start_time = time.time()

        # ------------------------------------------------------------------
        # 读取全部数据包
        # ------------------------------------------------------------------
        packets: List[Packet] = rdpcap(str(input_path))

        # 无有效掩码器 -> 复制文件，无改动
        if self._masker is None:
            wrpcap(str(output_path), packets)
            duration_ms = (time.time() - start_time) * 1000
            return StageStats(
                stage_name=self.name,
                packets_processed=len(packets),
                packets_modified=0,
                duration_ms=duration_ms,
                extra_metrics={"mode": "bypass"},
            )

        # ------------------------------------------------------------------
        # 掩码处理
        # ------------------------------------------------------------------
        modified_packets = self._masker.mask_packets(packets)
        stats = self._masker.get_statistics()

        # 写入输出文件
        wrpcap(str(output_path), modified_packets)

        duration_ms = (time.time() - start_time) * 1000

        return StageStats(
            stage_name=self.name,
            packets_processed=stats.processed_packets,
            packets_modified=stats.modified_packets,
            duration_ms=duration_ms,
            extra_metrics=stats.to_dict(),
        ) 