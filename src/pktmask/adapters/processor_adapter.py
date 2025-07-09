import warnings
from typing import Dict, Optional, Any
from pktmask.core.processors.base_processor import BaseProcessor, ProcessorResult
from pktmask.core.pipeline.base_stage import StageBase
from pktmask.core.pipeline.models import StageStats


class PipelineProcessorAdapter(StageBase):
    """Simplified Pipeline Processor Adapter - 桌面应用优化版本

    轻量级适配器，专注于桌面应用的性能需求：
    - 最小化转换开销
    - 简化错误处理逻辑
    - 优化内存使用
    - 减少对象创建

    桌面应用优化特点：
    - 延迟初始化，提升启动速度
    - 直接调用，最小化包装开销
    - 简化的结果转换
    """

    def __init__(self, processor: BaseProcessor, config: Optional[Dict[str, Any]] = None):
        warnings.warn(
            "PipelineProcessorAdapter is deprecated. Use ProcessorStage with direct integration instead.",
            DeprecationWarning,
            stacklevel=2
        )
        self._processor = processor
        self._config = config or {}
        self._initialized = False
        super().__init__()

    @property
    def name(self) -> str:
        return self._processor.__class__.__name__

    def initialize(self, config: Optional[Dict[str, Any]] = None) -> None:
        """延迟初始化，优化桌面应用启动时间"""
        if self._initialized:
            return

        if config:
            self._config.update(config)

        if not self._processor.is_initialized:
            if not self._processor.initialize():
                raise RuntimeError(f"Failed to initialize: {self._processor.__class__.__name__}")

        self._initialized = True
        super().initialize(self._config)

    def process_file(self, input_path: str, output_path: str) -> StageStats:
        """直接处理，最小化转换开销"""
        if not self._initialized:
            self.initialize()

        result: ProcessorResult = self._processor.process_file(str(input_path), str(output_path))
        if not result.success:
            raise RuntimeError(f"Processor failed: {result.error}")

        # 简化的结果转换，减少对象创建
        return StageStats(
            stage_name=self.name,
            packets_processed=result.stats.get('packets_processed', 0),
            packets_modified=result.stats.get('packets_modified', 0),
            duration_ms=result.stats.get('duration_ms', 0.0)
        )

    def get_required_tools(self) -> list[str]:
        """获取底层处理器需要的工具"""
        if hasattr(self._processor, 'get_required_tools'):
            return self._processor.get_required_tools()
        return []

    def stop(self) -> None:
        if hasattr(self._processor, 'stop'):
            self._processor.stop()
        super().stop()
