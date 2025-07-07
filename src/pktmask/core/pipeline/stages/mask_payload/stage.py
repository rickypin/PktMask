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
from pktmask.core.tcp_payload_masker.core.blind_masker import BlindPacketMasker
from pktmask.core.tcp_payload_masker.api.types import MaskingRecipe  # 核心数据结构
from pktmask.core.tcp_payload_masker.utils.helpers import (
    create_masking_recipe_from_dict,
)


class MaskStage(StageBase):
    """完整功能的载荷掩码阶段

    该 Stage 提供两种处理模式：
    - 智能协议识别和策略应用
    - 完整统计和事件集成

    支持两种处理模式：
    1. Processor Adapter Mode (默认): 使用 TSharkEnhancedMaskProcessor + ProcessorStageAdapter
    2. Basic Mode (降级): 使用原有 BlindPacketMasker 进行基础掩码

    配置 ``config`` 字典支持以下键：

    1. ``recipe``: 直接传入 :class:`MaskingRecipe` 实例。
    2. ``recipe_dict``: 传入兼容 ``create_masking_recipe_from_dict`` 的字典。
    3. ``recipe_path``: 指向 JSON 文件路径；文件内容必须为配方字典格式。
    4. ``mode``: 处理模式 - "processor_adapter" (默认), 或 "basic"

    当三个键均不存在或解析失败时，Processor Adapter Mode 会进行智能协议分析；
    Basic Mode 会回退为 *透传模式*。
    """

    name: str = "MaskStage"

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
        self._processor_adapter: Optional[Any] = None  # ProcessorStageAdapter，延迟导入
        
        # Basic Mode 组件 (降级备选方案)
        self._masker: Optional[BlindPacketMasker] = None
        
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
            self._initialize_basic_mode(merged_cfg)



    def _initialize_processor_adapter_mode(self, config: Dict[str, Any]) -> None:
        """初始化处理器适配器模式（TSharkEnhancedMaskProcessor + ProcessorStageAdapter）"""
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
        from pktmask.core.pipeline.stages.processor_stage_adapter import ProcessorStageAdapter
        
        # 创建处理器配置
        processor_config = ProcessorConfig(
            enabled=True,
            name="tshark_enhanced_mask",
            priority=1
        )
        
        # 创建 TSharkEnhancedMaskProcessor 实例
        processor = TSharkEnhancedMaskProcessor(processor_config)
        
        # 用 ProcessorStageAdapter 包装
        adapter = ProcessorStageAdapter(processor, config)
        
        return adapter

    def _initialize_basic_mode(self, config: Dict[str, Any]) -> None:
        """初始化基础模式（原有 BlindPacketMasker 逻辑）
        
        默认透传模式，除非直接注入 MaskingRecipe 对象才启用掩码功能。
        这种设计确保了 Basic Mode 的简洁性和明确性。
        
        注意：为保持向后兼容，此方法继续支持废弃的配置项，但会发出警告。
        
        Args:
            config: 配置字典，支持 "recipe" 键传入 MaskingRecipe 实例
        """
        recipe_obj: Optional[MaskingRecipe] = None

        # 优先接受直接传入的 MaskingRecipe 对象
        if isinstance(config.get("recipe"), MaskingRecipe):
            recipe_obj = config["recipe"]
        # 向后兼容：处理废弃的配置项，但发出警告
        elif "recipe_dict" in config or "recipe_path" in config:
            self._handle_deprecated_config_with_warning(config)
            # 注意：废弃配置项被忽略，不会创建实际的掩码器
            # 这确保老代码不会崩溃，但行为会改变为透传模式

        # 创建 BlindPacketMasker（若配方有效）
        if recipe_obj is not None:
            self._masker = BlindPacketMasker(masking_recipe=recipe_obj)
        # 如果没有有效的 MaskingRecipe 对象，_masker 保持 None，
        # 这样在 process_file 中会启用透传模式

    def _handle_deprecated_config_with_warning(self, config: Dict[str, Any]) -> None:
        """处理废弃的配置项并发出警告
        
        为保持向后兼容性，此方法会检查并警告废弃的配置项。
        废弃的配置项将被忽略，不会抛出错误。
        
        Args:
            config: 包含废弃配置项的配置字典
        """
        deprecated_items = []
        
        if "recipe_dict" in config:
            deprecated_items.append("recipe_dict")
            
        if "recipe_path" in config:
            deprecated_items.append("recipe_path")
            
        if deprecated_items:
            warning_msg = (
                f"配置项 {', '.join(deprecated_items)} 已废弃，将在未来版本中移除。"
                "这些配置项已被忽略，请使用新的配置方式：直接传入 MaskingRecipe 对象到 'recipe' 键，"
                "或使用 processor_adapter 模式进行智能协议分析。"
                "当前操作将以透传模式继续执行以保持兼容性。"
            )
            
            warnings.warn(
                warning_msg,
                DeprecationWarning,
                stacklevel=3  # 指向调用者的调用者，通常是用户代码
            )
            
            self._logger.warning(
                f"MaskStage 检测到废弃配置项: {deprecated_items}. "
                "这些配置项已被忽略。请更新到新的配置方式。"
            )

    def _create_stage_config(self, stage_type: str, base_config: Dict[str, Any]) -> Dict[str, Any]:
        """为指定阶段创建配置
        
        .. deprecated:: 
            此方法已过时，未被其他模块使用。将在后续版本中移除。
            现在推荐使用 Processor Adapter Mode 或直接传入 MaskingRecipe 对象。
        """
        # 延迟导入以避免循环导入
        from pktmask.config.defaults import get_tshark_paths
        
        stage_config = {
            'preserve_ratio': base_config.get('preserve_ratio', 0.3),
            'min_preserve_bytes': base_config.get('min_preserve_bytes', 100),
            'chunk_size': base_config.get('chunk_size', 1000),
            'enable_detailed_logging': base_config.get('enable_detailed_logging', False)
        }
        
        if stage_type == "tshark":
            stage_config.update({
                'enable_tcp_reassembly': True,
                'enable_ip_defragmentation': True,
                'enable_tls_desegmentation': True,
                'tshark_executable_paths': get_tshark_paths(),
                'tshark_custom_executable': base_config.get('tshark_custom_executable'),
                'tshark_enable_reassembly': True,
                'tshark_enable_defragmentation': True,
                'tshark_timeout_seconds': base_config.get('tshark_timeout_seconds', 300),
                'tshark_max_memory_mb': base_config.get('tshark_max_memory_mb', 1024)
            })
        elif stage_type == "pyshark":
            stage_config.update({
                'tls_strategy_enabled': base_config.get('tls_strategy_enabled', True),
                'default_strategy_enabled': base_config.get('default_strategy_enabled', True),
                'auto_protocol_detection': base_config.get('auto_protocol_detection', True)
            })
        elif stage_type == "scapy":
            stage_config.update({
                'preserve_timestamps': True,
                'recalculate_checksums': True,
                'enable_validation': base_config.get('enable_validation', True)
            })
            
        return stage_config

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
        """使用 TSharkEnhancedMaskProcessor + ProcessorStageAdapter 进行处理"""
        start_time = time.time()
        
        try:
            # 通过适配器调用 TSharkEnhancedMaskProcessor
            result = self._processor_adapter.process_file(input_path, output_path)
            
            # ProcessorStageAdapter.process_file 返回 StageStats，直接返回
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
        """使用原有 BlindPacketMasker 进行基础处理"""
        start_time = time.time()

        # 无有效掉码器 -> 直接复制文件，透传处理
        if self._masker is None:
            self._logger.info("MaskStage Basic Mode透传，无MaskingRecipe")
            shutil.copyfile(str(input_path), str(output_path))
            duration_ms = (time.time() - start_time) * 1000
            
            # 获取数据包数量用于统计（仅用于统计，不做处理）
            packets: List[Packet] = rdpcap(str(input_path))
            
            return StageStats(
                stage_name=self.name,
                packets_processed=len(packets),
                packets_modified=0,
                duration_ms=duration_ms,
                extra_metrics={
                    "processor_adapter_mode": False,
                    "mode": "basic_passthrough",
                    "reason": "no_valid_masking_recipe"
                },
            )

        # ------------------------------------------------------------------
        # 掩码处理
        # ------------------------------------------------------------------
        # 读取全部数据包
        packets: List[Packet] = rdpcap(str(input_path))
        
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
            extra_metrics={
                **stats.to_dict(),
                "processor_adapter_mode": False,
                "mode": "basic_masking"
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
