from __future__ import annotations

import json
import logging
import shutil
import time
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional

from scapy.all import rdpcap, wrpcap, Packet  # type: ignore

from pktmask.core.pipeline.base_stage import StageBase
from pktmask.core.pipeline.models import StageStats
from pktmask.core.tcp_payload_masker.api.types import MaskingRecipe  # 核心数据结构
from pktmask.core.tcp_payload_masker.utils.helpers import (
    create_masking_recipe_from_dict,
)


class MaskPayloadStage(StageBase):
    """完整功能的载荷掩码阶段

    该 Stage 提供两种处理模式：
    - 智能协议识别和策略应用
    - 完整统计和事件集成

    支持两种处理模式：
    1. Processor Adapter Mode (默认): 使用 TSharkEnhancedMaskProcessor + PipelineProcessorAdapter
    2. Basic Mode (降级): 纯透传复制模式（BlindPacketMasker 已移除）

    配置 ``config`` 字典支持以下键：

    1. ``recipe``: 直接传入 :class:`MaskingRecipe` 实例。
    2. ``recipe_dict``: 传入兼容 ``create_masking_recipe_from_dict`` 的字典。
    3. ``recipe_path``: 指向 JSON 文件路径；文件内容必须为配方字典格式。
    4. ``mode``: 处理模式 - "processor_adapter" (默认), 或 "basic"

    当三个键均不存在或解析失败时，Processor Adapter Mode 会进行智能协议分析；
    Basic Mode 统一为 *透传模式* (不再使用 BlindPacketMasker)。
    """

    name: str = "MaskPayloadStage"

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------
    def __init__(self, config: Optional[Dict[str, Any]] | None = None):
        self._config: Dict[str, Any] = config or {}
        
        # 创建日志记录器
        self._logger = logging.getLogger(self.name)
        
        # 处理模式选择
        mode = self._config.get("mode", "processor_adapter")
        self._use_processor_adapter_mode = mode == "processor_adapter"
        
        # Processor Adapter Mode 组件
        self._processor_adapter: Optional[Any] = None  # PipelineProcessorAdapter，延迟导入
        
        # Basic Mode 组件：仅透传复制，无外部依赖
        self._masker = None  # 占位，保持接口一致
        
        super().__init__()

    # NOTE: StageBase.initialize 仅标记 _initialized，我们在子类中解析配方
    def initialize(self, config: Optional[Dict[str, Any]] | None = None) -> None:  # noqa: D401
        """初始化 Stage。

        该方法将在 Pipeline 构建阶段被调用，用于提前解析掩码配方并创建
        相应的处理器实例以便复用。"""

        # 先调用父类实现，确保 _initialized 状态正确
        super().initialize(config)

        # 合并外部传入的 runtime config — 后者优先生效
        merged_cfg: Dict[str, Any] = {**self._config, **(config or {})}
        
        # 更新处理模式选择
        mode = merged_cfg.get("mode", "processor_adapter")
        self._use_processor_adapter_mode = mode == "processor_adapter"

        if self._use_processor_adapter_mode:
            self._initialize_processor_adapter_mode(merged_cfg)
        else:
            # basic 模式仅透传，不再尝试创建 BlindPacketMasker
            self._logger.info("MaskStage basic 模式已简化为纯透传，无 BlindPacketMasker")
            self._masker = None



    def _initialize_processor_adapter_mode(self, config: Dict[str, Any]) -> None:
        """初始化处理器适配器模式（TSharkEnhancedMaskProcessor + PipelineProcessorAdapter）"""
        try:
            # 创建增强处理器并用适配器包装
            self._processor_adapter = self._create_enhanced_processor(config)
            
            # 初始化适配器
            self._processor_adapter.initialize(config)
            
        except ImportError as e:
            # 如果处理器适配器组件不可用，降级到基础模式
            self._logger.error("MaskStage降级为Basic Mode: %s", e, exc_info=True)
            self._use_processor_adapter_mode = False
            self._initialize_basic_mode(config)
        except Exception as e:
            # 处理器适配器模式初始化失败，降级到基础模式
            self._logger.error("MaskStage降级为Basic Mode: %s", e, exc_info=True)
            self._use_processor_adapter_mode = False
            self._initialize_basic_mode(config)

    def _create_enhanced_processor(self, config: Dict[str, Any]):
        """创建增强掩码处理器"""
        from pktmask.core.processors.tshark_enhanced_mask_processor import TSharkEnhancedMaskProcessor
        from pktmask.core.processors.base_processor import ProcessorConfig
        from pktmask.core.adapters.processor_adapter import PipelineProcessorAdapter
        
        # 创建处理器配置
        processor_config = ProcessorConfig(
            enabled=True,
            name="tshark_enhanced_mask",
            priority=1
        )
        
        # 创建 TSharkEnhancedMaskProcessor 实例
        processor = TSharkEnhancedMaskProcessor(processor_config)
        
        # 用 PipelineProcessorAdapter 包装
        adapter = PipelineProcessorAdapter(processor, config)
        
        return adapter

    # NOTE: basic 模式已简化为纯透传，无需初始化任何掩码器
    def _initialize_basic_mode(self, config: Dict[str, Any]) -> None:  # noqa: D401
        self._masker = None

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

        if self._use_processor_adapter_mode and self._processor_adapter:
            return self._process_with_processor_adapter_mode(input_path, output_path)
        else:
            return self._process_with_basic_mode(input_path, output_path)

    def _process_with_processor_adapter_mode(self, input_path: Path, output_path: Path) -> StageStats:
        """使用 TSharkEnhancedMaskProcessor + PipelineProcessorAdapter 进行处理"""
        start_time = time.time()
        
        try:
            # 通过适配器调用 TSharkEnhancedMaskProcessor
            result = self._processor_adapter.process_file(input_path, output_path)
            
            # PipelineProcessorAdapter.process_file 返回 StageStats，直接返回
            return result
            
        except Exception as e:
            # 处理器适配器模式执行异常，降级到基础模式
            self._logger.error("MaskStage降级为Basic Mode: %s", e, exc_info=True)
            duration_ms = (time.time() - start_time) * 1000
            return self._process_with_basic_mode_fallback(
                input_path, output_path, duration_ms, 
                f"processor_adapter_mode_failed: {e}"
            )



    def _process_with_basic_mode(self, input_path: Path, output_path: Path) -> StageStats:
        """使用透传模式进行基础处理（BlindPacketMasker 已移除）"""
        start_time = time.time()

        # basic 模式统一为透传复制
        self._logger.info("MaskStage Basic Mode 透传复制执行")

        shutil.copyfile(str(input_path), str(output_path))

        duration_ms = (time.time() - start_time) * 1000

        # 统计：读取包数，但不对数据包做任何修改
        packets: List[Packet] = rdpcap(str(input_path))

        return StageStats(
            stage_name=self.name,
            packets_processed=len(packets),
            packets_modified=0,
            duration_ms=duration_ms,
            extra_metrics={
                "processor_adapter_mode": False,
                "mode": "basic_passthrough",
                "reason": "blind_packet_masker_removed"
            },
        )

    def _process_with_basic_mode_fallback(self, input_path: Path, output_path: Path, 
                                        duration_ms: float, error: Optional[str] = None) -> StageStats:
        """处理器适配器模式失败时的降级处理"""
        # 简单复制文件作为降级方案
        packets: List[Packet] = rdpcap(str(input_path))
        wrpcap(str(output_path), packets)
        
        return StageStats(
            stage_name=self.name,
            packets_processed=len(packets),
            packets_modified=0,
            duration_ms=duration_ms,
            extra_metrics={
                "processor_adapter_mode": False,
                "mode": "fallback",
                "original_mode": "processor_adapter",
                "fallback_reason": error or "processor_adapter_mode_execution_failed",
                "graceful_degradation": True,
                "downgrade_trace": True
            },
        )


# Backward compatibility alias
MaskStage = MaskPayloadStage
