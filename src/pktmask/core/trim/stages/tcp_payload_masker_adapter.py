"""
TCP载荷掩码器适配器 (v2)

该Stage将 `EnhancedPySharkAnalyzer` 生成的 `MaskingRecipe` 应用到PCAP文件。
它作为 `BlindPacketMasker` 的适配器，在多阶段执行器框架内工作。
"""
import logging
from pathlib import Path
from scapy.all import rdpcap, wrpcap, Packet
from typing import List, Optional, Dict

from ...tcp_payload_masker.core.blind_masker import BlindPacketMasker
from .base_stage import BaseStage, StageContext
from ...processors.base_processor import ProcessorResult

logger = logging.getLogger(__name__)


class TcpPayloadMaskerAdapter(BaseStage):
    """将掩码配方应用到PCAP文件的Stage (批量处理模式)"""

    def __init__(self, config: Optional[Dict] = None):
        # 明确传递 Stage 名称，避免 BaseStage 参数错位
        super().__init__("TcpPayloadMaskerAdapter", config)
        self._masker: BlindPacketMasker | None = None
        self.logger = logger.getChild("TcpPayloadMaskerAdapter")

    def execute(self, context: StageContext) -> ProcessorResult:
        """
        对PCAP文件应用掩码配方。

        此方法采用批量处理模式：
        1. 使用rdpcap一次性读取所有数据包。
        2. 初始化BlindPacketMasker。
        3. 调用mask_packets()进行批量处理。
        4. 使用wrpcap一次性写入所有修改后的数据包。
        """
        # 当前Stage实际应基于原始 PCAP 文件进行掩码处理
        # 为向后兼容，如果调用方已设置了 custom 字段，则优先使用
        input_path: Path = getattr(context, "current_file_path", None) or context.input_file
        output_path: Path = getattr(context, "output_file_path", None) or context.output_file

        if not input_path or not output_path:
            return ProcessorResult(success=False, error="输入或输出文件路径未提供")

        self.logger.info(f"开始使用批量模式处理PCAP文件: {input_path}")

        try:
            # 1. 一次性读取所有数据包到内存
            self.logger.info(f"读取原始文件 {input_path}，准备批量处理...")
            packets: List[Packet] = rdpcap(str(input_path))
            self.logger.info(f"成功读取 {len(packets)} 个数据包到内存")

            # 2. 初始化盲操作掩码器
            masking_recipe = context.masking_recipe
            if not masking_recipe:
                self.logger.warning("上下文中未找到掩码配方，将复制原文件并跳过处理")
                wrpcap(str(output_path), packets)
                return ProcessorResult(
                    success=True,
                    data={
                        "message": "处理跳过：未提供掩码配方",
                        "packets_processed": len(packets),
                        "packets_modified": 0,
                        "bytes_processed": 0,
                        "bytes_masked": 0,
                        "details": {}
                    },
                    stats={}
                )

            self._masker = BlindPacketMasker(masking_recipe=masking_recipe)

            # 3. 调用批量处理方法
            modified_packets = self._masker.mask_packets(packets)
            stats = self._masker.get_statistics()
            self.logger.info(f"批量掩码处理完成。统计: {stats.to_dict()}")

            # 4. 一次性写入所有修改后的数据包
            wrpcap(str(output_path), modified_packets)
            self.logger.info(f"已将 {len(modified_packets)} 个处理后的数据包写入: {output_path}")

            return ProcessorResult(
                success=True,
                data={
                    "message": f"批量处理成功，{stats.modified_packets}个数据包被修改",
                    "packets_processed": stats.processed_packets,
                    "packets_modified": stats.modified_packets,
                    "bytes_processed": stats.total_bytes_processed,
                    "bytes_masked": stats.total_bytes_masked,
                    "details": stats.to_dict(),
                },
                stats=stats.to_dict()
            )

        except Exception as e:
            self.logger.error(f"TcpPayloadMaskerAdapter 执行失败: {e}", exc_info=True)
            return ProcessorResult(success=False, error=f"处理失败: {e}")

    # ------------------------------------------------------------------
    # 抽象方法实现
    # ------------------------------------------------------------------

    def validate_inputs(self, context: StageContext) -> bool:
        """验证输入、输出路径以及掩码配方是否就绪"""

        input_path: Path = getattr(context, "current_file_path", None) or context.input_file
        output_path: Path = getattr(context, "output_file_path", None) or context.output_file

        # 输入文件需存在且非空
        if not input_path or not Path(input_path).exists():
            self.logger.error("输入文件不存在: %s", input_path)
            return False
        if Path(input_path).stat().st_size == 0:
            self.logger.error("输入文件为空: %s", input_path)
            return False

        # 确保输出目录可写
        if not output_path:
            self.logger.error("未提供输出文件路径")
            return False
        output_dir = Path(output_path).parent
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.logger.error("无法创建输出目录 %s: %s", output_dir, e)
            return False

        # 掩码配方校验
        if context.masking_recipe is None:
            self.logger.warning("未在上下文中找到掩码配方，将按原样复制文件")
        return True

# ------------------------------------------------------------------
# (已移除 ScapyRewriter 兼容别名)
# ------------------------------------------------------------------ 