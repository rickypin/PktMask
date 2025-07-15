"""
新一代 MaskPayload 阶段主类

实现基于双模块架构的新一代掩码处理阶段，集成 Marker 和 Masker 模块。
支持完全向后兼容的配置格式转换。
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict, Union, Optional

from pktmask.core.pipeline.processor_stage import ProcessorStage
from pktmask.core.pipeline.models import StageStats


class NewMaskPayloadStage(ProcessorStage):
    """双模块架构掩码处理阶段

    基于双模块分离设计：
    - Marker模块: 协议分析和规则生成
    - Masker模块: 通用载荷掩码应用
    """
    
    def __init__(self, config: Dict[str, Any]):
        """初始化新一代掩码处理阶段

        Args:
            config: 配置字典，支持以下参数：
                - protocol: 协议类型 ("tls", "http", "auto")
                - marker_config: Marker模块配置
                - masker_config: Masker模块配置
                - mode: 处理模式 ("enhanced", "basic")
        """
        super().__init__(config)
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")

        # 配置解析
        self.protocol = config.get('protocol', 'tls')
        self.mode = config.get('mode', 'enhanced')
        self.marker_config = config.get('marker_config', {})
        self.masker_config = config.get('masker_config', {})

        # 模块实例（延迟初始化）
        self.marker = None
        self.masker = None

        # 配置验证器（可选）
        self.config_validator = None

        self.logger.info(f"NewMaskPayloadStage created: protocol={self.protocol}, mode={self.mode}")







    def initialize(self) -> bool:
        """初始化阶段

        Returns:
            初始化是否成功
        """
        if self._initialized:
            return True

        try:
            self.logger.info("Starting NewMaskPayloadStage initialization")

            # 创建 Marker 模块
            self.marker = self._create_marker()
            if not self.marker.initialize():
                raise RuntimeError("Marker模块初始化失败")

            # 创建 Masker 模块
            self.masker = self._create_masker()

            self._initialized = True
            self.logger.info("NewMaskPayloadStage initialization successful")
            return True

        except Exception as e:
            self.logger.error(f"NewMaskPayloadStage initialization failed: {e}")
            return False
    
    def process_file(self, input_path: Union[str, Path],
                    output_path: Union[str, Path]) -> StageStats:
        """处理文件

        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径

        Returns:
            StageStats: 处理统计信息
        """
        if not self._initialized and not self.initialize():
            raise RuntimeError("NewMaskPayloadStage 未初始化")

        self.validate_inputs(input_path, output_path)

        input_path = Path(input_path)
        output_path = Path(output_path)

        self.logger.info(f"Starting file processing: {input_path} -> {output_path}")

        start_time = time.time()

        try:
            # 检查是否为 basic 模式（降级处理）
            if self.mode == 'basic':
                return self._process_with_basic_mode(input_path, output_path, start_time)

            # 双模块处理模式
            return self._process_with_dual_module_mode(input_path, output_path, start_time)

        except Exception as e:
            self.logger.error(f"File processing failed: {e}")
            raise

    def _process_with_dual_module_mode(self, input_path: Path, output_path: Path, start_time: float) -> StageStats:
        """使用新版双模块架构处理文件"""
        self.logger.debug("Using dual-module architecture processing mode")

        # Phase 1: Call Marker module to generate KeepRuleSet
        self.logger.debug("Phase 1: Generate keep rules")
        keep_rules = self.marker.analyze_file(str(input_path), self.config)

        # Phase 2: Call Masker module to apply rules
        self.logger.debug("Phase 2: Apply masking rules")
        masking_stats = self.masker.apply_masking(str(input_path), str(output_path), keep_rules)

        # 阶段3: 转换统计信息
        stage_stats = self._convert_to_stage_stats(masking_stats)

        self.logger.info(f"Dual-module processing completed: processed_packets={stage_stats.packets_processed}, "
                        f"modified_packets={stage_stats.packets_modified}")

        return stage_stats



    def _process_with_basic_mode(self, input_path: Path, output_path: Path, start_time: float) -> StageStats:
        """基础模式处理（透传复制）"""
        self.logger.debug("Using basic mode (passthrough copy)")

        import shutil

        # 验证输入文件
        if not input_path.exists():
            raise FileNotFoundError(f"输入文件不存在: {input_path}")
        if not input_path.is_file():
            raise ValueError(f"输入路径不是文件: {input_path}")

        # 简单复制文件
        shutil.copy2(str(input_path), str(output_path))

        duration_ms = (time.time() - start_time) * 1000

        # 创建基础统计信息
        stage_stats = StageStats(
            stage_name=self.get_display_name(),
            packets_processed=0,  # 基础模式不统计包数
            packets_modified=0,
            duration_ms=duration_ms,
            extra_metrics={
                'mode': 'basic',
                'operation': 'passthrough_copy',
                'success': True,
                'file_size': input_path.stat().st_size
            }
        )

        self.logger.info(f"Basic mode processing completed: file_size={stage_stats.extra_metrics['file_size']} bytes")

        return stage_stats

    def _create_marker(self):
        """创建 Marker 模块实例

        Returns:
            ProtocolMarker 实例
        """
        if self.protocol == 'tls':
            from .marker.tls_marker import TLSProtocolMarker
            return TLSProtocolMarker(self.marker_config)
        else:
            raise ValueError(f"不支持的协议: {self.protocol}")

    def _create_masker(self):
        """创建 Masker 模块实例

        Returns:
            PayloadMasker 实例
        """
        from .masker.payload_masker import PayloadMasker
        return PayloadMasker(self.masker_config)
    
    def _convert_to_stage_stats(self, masking_stats) -> StageStats:
        """转换掩码统计信息为阶段统计信息
        
        Args:
            masking_stats: MaskingStats 实例
            
        Returns:
            StageStats 实例
        """
        return StageStats(
            stage_name=self.get_display_name(),
            packets_processed=masking_stats.processed_packets,
            packets_modified=masking_stats.modified_packets,
            duration_ms=masking_stats.execution_time * 1000,
            extra_metrics={
                'masked_bytes': masking_stats.masked_bytes,
                'preserved_bytes': masking_stats.preserved_bytes,
                'masking_ratio': masking_stats.masking_ratio,
                'preservation_ratio': masking_stats.preservation_ratio,
                'processing_speed_mbps': masking_stats.processing_speed_mbps,
                'protocol': self.protocol,
                'mode': self.mode,
                'success': masking_stats.success,
                'errors': masking_stats.errors,
                'warnings': masking_stats.warnings
            }
        )
    
    def get_display_name(self) -> str:
        """获取显示名称"""
        return "Mask Payloads (v2)"
    
    def get_description(self) -> str:
        """获取描述信息"""
        return (
            f"新一代载荷掩码处理器 (协议: {self.protocol}, 模式: {self.mode})。"
            "基于双模块架构，支持协议分析与掩码应用分离。"
        )
    
    def get_required_tools(self) -> list[str]:
        """获取所需工具列表"""
        tools = ['scapy']
        if self.protocol == 'tls':
            tools.append('tshark')
        return tools
    
    def cleanup(self) -> None:
        """清理资源"""
        if self.marker:
            self.marker.cleanup()
        if self.masker:
            # Masker 模块暂时没有清理方法
            pass
        self._initialized = False
        self.logger.debug("NewMaskPayloadStage resource cleanup completed")


