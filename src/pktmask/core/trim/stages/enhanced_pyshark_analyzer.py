#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EnhancedPySharkAnalyzer - Phase 2 Revised Implementation

该阶段替换原有基于序列号的 PySharkAnalyzer，输出基于包索引的
MaskingRecipe 供 BlindPacketMasker 使用。

当前版本 (Phase 2-B) 仅支持：
    • 纯以太网 + IPv4/IPv6 + TCP
    • 单层 IEEE 802.1Q VLAN

仅实现 TLS 协议处理要求：
    • Handshake / Alert 等报文保持不变
    • 对 Application-Data (content-type = 23) 报文应用 MaskRange 精确掩码

实现要点：
1. 双文件映射：使用高精度时间戳将重组文件中的包映射回原始文件。
2. 深度协议分析：在重组文件上通过 Scapy 精确解析每个TCP载荷中的TLS记录。
3. 掩码配方：根据映射关系和TLS记录分析生成精确的 MaskingRecipe。
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Dict, List, Optional

try:
    import pyshark
except ImportError:  # pragma: no cover
    pyshark = None  # type: ignore

from scapy.all import rdpcap, TCP

from .base_stage import BaseStage, StageContext
from ...processors.base_processor import ProcessorResult

from ...tcp_payload_masker.api.types import (
    PacketMaskInstruction,
    MaskingRecipe,
    SkippedPacketInfo,
)

__all__ = ["EnhancedPySharkAnalyzer"]

_logger = logging.getLogger(__name__)


class EnhancedPySharkAnalyzer(BaseStage):
    """Phase 2-B Enhanced PyShark Analyzer - with deep TLS record parsing"""

    def __init__(self, config: Optional[Dict] = None):
        super().__init__("EnhancedPySharkAnalyzer", config)
        self._logger = _logger.getChild(self.name)

    # ------------------------------------------------------------------
    # BaseStage 接口实现
    # ------------------------------------------------------------------

    def _initialize_impl(self) -> None:
        if pyshark is None:
            raise RuntimeError(
                "PyShark 未安装，请先运行 `pip install pyshark` 以启用协议分析功能"
            )
        self._logger.info("EnhancedPySharkAnalyzer 初始化完成")

    def validate_inputs(self, context: StageContext) -> bool:
        if not context.input_file or not Path(context.input_file).exists():
            self._logger.error("缺少或无法找到原始输入文件")
            return False
        if not context.tshark_output or not Path(context.tshark_output).exists():
            self._logger.error("缺少或无法找到 TShark 预处理输出文件")
            return False
        return True

    def execute(self, context: StageContext) -> ProcessorResult:
        context.current_stage = self.name
        progress_cb = self.get_progress_callback(context)
        start_time = time.time()

        try:
            # 1. 构建时间戳映射
            progress_cb(0.1)
            self._logger.debug("构建时间戳映射...")
            mapping = self._build_timestamp_mapping(
                Path(context.input_file), Path(context.tshark_output)
            )
            if not mapping:
                raise RuntimeError("无法建立原始文件与重组文件的映射关系")
            self._logger.info(f"时间戳映射成功，{len(mapping)} 个包已映射")

            # 2. 深度分析重组文件并生成掩码配方
            progress_cb(0.3)
            self._logger.debug("开始深度分析重组文件以生成掩码配方...")
            # rdpcap is slow, so we read it once and pass the count
            original_packets = rdpcap(str(context.input_file))
            recipe = self._generate_recipe_from_deep_analysis(
                reassembled_file=Path(context.tshark_output),
                mapping=mapping,
                original_packet_count=len(original_packets),
            )
            self._logger.info(
                f"深度分析完成，生成 {recipe.get_instruction_count()} 条掩码指令"
            )

            # 3. 写入上下文，供后续阶段使用
            context.masking_recipe = recipe

            duration = time.time() - start_time
            progress_cb(1.0)
            self._logger.info(f"EnhancedPySharkAnalyzer 完成，耗时 {duration:.2f}s")
            return ProcessorResult(
                success=True,
                data={
                    "instruction_count": recipe.get_instruction_count(),
                    "total_packets": recipe.total_packets,
                    "processing_time": duration,
                },
            )
        except Exception as e:
            self._logger.error(f"EnhancedPySharkAnalyzer 失败: {e}", exc_info=True)
            return ProcessorResult(success=False, data={"error": str(e)})

    # ------------------------------------------------------------------
    # 内部实现
    # ------------------------------------------------------------------

    @staticmethod
    def _build_timestamp_mapping(
        original_file: Path, reassembled_file: Path
    ) -> Dict[int, int]:
        """建立 *重组文件包索引 → 原始文件包索引* 的映射"""
        _logger.debug("构建时间戳映射 …")

        orig_cap = pyshark.FileCapture(
            str(original_file), keep_packets=False, include_raw=False, use_json=False
        )
        orig_ts_map: Dict[str, int] = {}
        for i, pkt in enumerate(orig_cap):
            orig_ts_map[pkt.sniff_timestamp] = i
        orig_cap.close()

        mapping: Dict[int, int] = {}
        re_cap = pyshark.FileCapture(
            str(reassembled_file), keep_packets=False, include_raw=False, use_json=False
        )
        for i, pkt in enumerate(re_cap):
            ts = pkt.sniff_timestamp
            if ts in orig_ts_map:
                mapping[i] = orig_ts_map[ts]
        re_cap.close()

        _logger.info(f"映射建立完成，共 {len(mapping)} 条")
        return mapping

    def _generate_recipe_from_deep_analysis(
        self,
        reassembled_file: Path,
        mapping: Dict[int, int],
        original_packet_count: int,
    ) -> MaskingRecipe:
        """
        使用Scapy对TCP载荷进行深度TLS记录分析。

        该方法遍历重组文件中的每个数据包，解析TCP载荷以识别
        单个TLS记录，并为每个Application Data记录生成精确的
        MaskRange指令。
        """
        from ...tcp_payload_masker.api.types import MaskRange

        reassembled_packets = rdpcap(str(reassembled_file))
        instructions: Dict[int, List[PacketMaskInstruction]] = {}
        skipped_packets: List[SkippedPacketInfo] = []

        for re_idx, pkt in enumerate(reassembled_packets):
            if not pkt.haslayer(TCP) or not pkt[TCP].payload:
                continue

            orig_idx = mapping.get(re_idx)
            if orig_idx is None:
                skipped_packets.append(
                    SkippedPacketInfo(
                        packet_index=re_idx,
                        reason="重组文件中的包无法映射回原始文件。",
                        packet_summary=pkt.summary(),
                    )
                )
                continue

            payload = bytes(pkt[TCP].payload)
            ptr = 0
            packet_instructions: List[PacketMaskInstruction] = []

            try:
                while ptr + 5 <= len(payload):
                    content_type = payload[ptr]
                    length = int.from_bytes(payload[ptr + 3 : ptr + 5], "big")

                    if ptr + 5 + length > len(payload):
                        self._logger.warning(
                            f"包 {orig_idx}: 检测到残缺的TLS记录，"
                            f"声明长度 {length} 超出载荷边界。已停止解析该包。"
                        )
                        break

                    if content_type == 23:  # TLS Application Data
                        # 掩码载荷，保留5字节TLS记录头
                        # MaskRange的偏移是相对于TCP载荷起点的
                        mask_start = ptr + 5
                        mask_end = ptr + 5 + length
                        if mask_start < mask_end:
                            packet_instructions.append(
                                MaskRange(start=mask_start, end=mask_end)
                            )

                    # 移动到下一个TLS记录的起点
                    ptr += 5 + length

                if packet_instructions:
                    # 使用 setdefault 优雅地处理首次添加
                    instructions.setdefault(orig_idx, []).extend(packet_instructions)

            except IndexError:
                # 载荷可能已损坏，停止解析该包
                skipped_packets.append(
                    SkippedPacketInfo(
                        packet_index=orig_idx,
                        reason="载荷中的TLS记录残缺，解析已停止。",
                        packet_summary=pkt.summary(),
                    )
                )

        return MaskingRecipe(
            total_packets=original_packet_count,
            packet_instructions=instructions,
            skipped_packets=skipped_packets,
        )

    def get_description(self) -> str:
        return (
            "增强版PyShark分析器，使用深度TLS记录解析生成精确的掩码配方"
        ) 