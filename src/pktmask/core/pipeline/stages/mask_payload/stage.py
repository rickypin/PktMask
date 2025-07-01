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
    """完整功能的载荷掩码阶段

    该 Stage 整合了 EnhancedTrimmer 的智能处理能力：
    - 多阶段处理 (TShark → PyShark → Scapy)
    - 智能协议识别和策略应用
    - 完整统计和事件集成

    支持两种处理模式：
    1. Enhanced Mode (默认): 使用 MultiStageExecutor 进行智能协议处理
    2. Basic Mode (降级): 使用原有 BlindPacketMasker 进行基础掩码

    配置 ``config`` 字典支持以下键：

    1. ``recipe``: 直接传入 :class:`MaskingRecipe` 实例。
    2. ``recipe_dict``: 传入兼容 ``create_masking_recipe_from_dict`` 的字典。
    3. ``recipe_path``: 指向 JSON 文件路径；文件内容必须为配方字典格式。
    4. ``mode``: 处理模式 - "enhanced" (默认) 或 "basic"

    当三个键均不存在或解析失败时，Enhanced Mode 会进行智能协议分析；
    Basic Mode 会回退为 *透传模式*。
    """

    name: str = "MaskStage"

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------
    def __init__(self, config: Optional[Dict[str, Any]] | None = None):
        self._config: Dict[str, Any] = config or {}
        
        # 处理模式选择
        self._use_enhanced_mode = self._config.get("mode", "enhanced") == "enhanced"
        
        # Enhanced Mode 组件
        self._executor: Optional[Any] = None  # MultiStageExecutor，延迟导入
        
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
        self._use_enhanced_mode = merged_cfg.get("mode", "enhanced") == "enhanced"

        if self._use_enhanced_mode:
            self._initialize_enhanced_mode(merged_cfg)
        else:
            self._initialize_basic_mode(merged_cfg)

    def _initialize_enhanced_mode(self, config: Dict[str, Any]) -> None:
        """初始化增强模式（EnhancedTrimmer 功能）"""
        try:
            # 延迟导入以避免循环导入
            from pktmask.core.trim.multi_stage_executor import MultiStageExecutor
            from pktmask.core.trim.stages.tshark_preprocessor import TSharkPreprocessor
            from pktmask.core.trim.stages.enhanced_pyshark_analyzer import EnhancedPySharkAnalyzer
            from pktmask.core.trim.stages.tcp_payload_masker_adapter import TcpPayloadMaskerAdapter
            
            # 创建多阶段执行器
            self._executor = MultiStageExecutor()
            
            # 注册三个处理阶段
            # Stage 0: TShark预处理器
            tshark_config = self._create_stage_config("tshark", config)
            tshark_stage = TSharkPreprocessor(tshark_config)
            if not tshark_stage.initialize():
                raise RuntimeError("TShark预处理器初始化失败")
            self._executor.register_stage(tshark_stage)
            
            # Stage 1: EnhancedPyShark分析器
            pyshark_config = self._create_stage_config("pyshark", config)
            pyshark_stage = EnhancedPySharkAnalyzer(pyshark_config)
            if not pyshark_stage.initialize():
                raise RuntimeError("EnhancedPySharkAnalyzer初始化失败")
            self._executor.register_stage(pyshark_stage)
            
            # Stage 2: TcpPayloadMaskerAdapter
            adapter_config = self._create_stage_config("scapy", config)
            adapter_stage = TcpPayloadMaskerAdapter(adapter_config)
            if not adapter_stage.initialize():
                raise RuntimeError("TcpPayloadMaskerAdapter初始化失败")
            self._executor.register_stage(adapter_stage)
            
        except ImportError as e:
            # 如果增强模式组件不可用，降级到基础模式
            self._use_enhanced_mode = False
            self._initialize_basic_mode(config)
        except Exception as e:
            # 增强模式初始化失败，降级到基础模式
            self._use_enhanced_mode = False
            self._initialize_basic_mode(config)

    def _initialize_basic_mode(self, config: Dict[str, Any]) -> None:
        """初始化基础模式（原有 BlindPacketMasker 逻辑）"""
        recipe_obj: Optional[MaskingRecipe] = None

        if isinstance(config.get("recipe"), MaskingRecipe):
            recipe_obj = config["recipe"]
        elif "recipe_dict" in config and isinstance(config["recipe_dict"], dict):
            try:
                recipe_obj = create_masking_recipe_from_dict(config["recipe_dict"])
            except Exception as exc:  # pylint: disable=broad-except
                # 延迟至 process_file 时再报错/透传
                recipe_obj = None
        elif "recipe_path" in config:
            path = Path(config["recipe_path"])
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

    def _create_stage_config(self, stage_type: str, base_config: Dict[str, Any]) -> Dict[str, Any]:
        """为指定阶段创建配置"""
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

        if self._use_enhanced_mode and self._executor:
            return self._process_with_enhanced_mode(input_path, output_path)
        else:
            return self._process_with_basic_mode(input_path, output_path)

    def _process_with_enhanced_mode(self, input_path: Path, output_path: Path) -> StageStats:
        """使用 MultiStageExecutor 进行智能处理"""
        start_time = time.time()
        
        try:
            # 执行多阶段处理管道
            result = self._executor.execute_pipeline(
                input_file=input_path,
                output_file=output_path
            )
            
            duration_ms = (time.time() - start_time) * 1000
            
            if result.success:
                # 计算总体统计信息
                total_packets_processed = 0
                total_packets_modified = 0
                
                for stage_result in result.stage_results:
                    if hasattr(stage_result, 'packets_processed'):
                        total_packets_processed = max(total_packets_processed, stage_result.packets_processed)
                    if hasattr(stage_result, 'packets_modified'):
                        total_packets_modified = max(total_packets_modified, stage_result.packets_modified)
                
                return StageStats(
                    stage_name=self.name,
                    packets_processed=total_packets_processed,
                    packets_modified=total_packets_modified,
                    duration_ms=duration_ms,
                    extra_metrics={
                        "enhanced_mode": True,
                        "stages_count": len(result.stage_results),
                        "success_rate": "100%",
                        "pipeline_success": True,
                        "multi_stage_processing": True,
                        "intelligent_protocol_detection": True
                    }
                )
            else:
                # 执行失败，降级到基础模式
                return self._process_with_basic_mode_fallback(input_path, output_path, duration_ms)
                
        except Exception as e:
            # 增强模式执行异常，降级到基础模式
            duration_ms = (time.time() - start_time) * 1000
            return self._process_with_basic_mode_fallback(input_path, output_path, duration_ms, str(e))

    def _process_with_basic_mode(self, input_path: Path, output_path: Path) -> StageStats:
        """使用原有 BlindPacketMasker 进行基础处理"""
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
                extra_metrics={
                    "enhanced_mode": False,
                    "mode": "bypass",
                    "reason": "no_valid_masking_recipe"
                },
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
            extra_metrics={
                **stats.to_dict(),
                "enhanced_mode": False,
                "mode": "basic_masking"
            },
        )

    def _process_with_basic_mode_fallback(self, input_path: Path, output_path: Path, 
                                        duration_ms: float, error: Optional[str] = None) -> StageStats:
        """增强模式失败时的降级处理"""
        # 简单复制文件作为降级方案
        packets: List[Packet] = rdpcap(str(input_path))
        wrpcap(str(output_path), packets)
        
        return StageStats(
            stage_name=self.name,
            packets_processed=len(packets),
            packets_modified=0,
            duration_ms=duration_ms,
            extra_metrics={
                "enhanced_mode": False,
                "mode": "fallback",
                "original_mode": "enhanced",
                "fallback_reason": error or "enhanced_mode_execution_failed",
                "graceful_degradation": True
            },
        ) 