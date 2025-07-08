from typing import Dict, Optional, Any
from pktmask.core.processors.base_processor import BaseProcessor, ProcessorResult
from pktmask.core.pipeline.base_stage import StageBase
from pktmask.core.pipeline.models import StageStats


class PipelineProcessorAdapter(StageBase):
    """Pipeline Processor Adapter - 统一的处理器适配器
    
    该适配器将 BaseProcessor 适配为 StageBase 接口，使得现有的处理器
    能够无缝集成到新的 PipelineExecutor 中。这是项目中唯一的官方适配器实现。
    
    主要功能：
    - 将 ProcessorResult 转换为 StageStats
    - 代理处理器的生命周期管理（初始化、停止）
    - 传递工具依赖要求
    - 提供异常处理和错误转换
    """
    
    def __init__(self, processor: BaseProcessor, config: Optional[Dict[str, Any]] = None):
        self._processor = processor
        self._config = config or {}
        super().__init__()
    
    @property 
    def name(self) -> str:
        return f"Adapter_{self._processor.__class__.__name__}"
    
    def initialize(self, config: Optional[Dict[str, Any]] = None) -> None:
        if config:
            self._config.update(config)
        
        if not self._processor.is_initialized:
            if not self._processor.initialize():
                raise RuntimeError(f"Failed to initialize: {self._processor.__class__.__name__}")
        super().initialize(self._config)
    
    def process_file(self, input_path: str, output_path: str) -> StageStats:
        result: ProcessorResult = self._processor.process_file(str(input_path), str(output_path))
        if not result.success:
            raise RuntimeError(f"Processor failed: {result.error}")
        return StageStats(
            stage_name=self.name,
            packets_processed=result.stats.get('packets_processed', 0),
            packets_modified=result.stats.get('packets_modified', 0),
            duration_ms=result.stats.get('duration_ms', 0.0),
            extra_metrics=result.stats or {}
        )
    
    def get_required_tools(self) -> list[str]:
        """获取底层处理器需要的工具"""
        # 如果底层处理器有此方法，调用它
        if hasattr(self._processor, 'get_required_tools'):
            return self._processor.get_required_tools()
        return []
    
    def stop(self) -> None:
        if hasattr(self._processor, 'stop'):
            self._processor.stop()
        super().stop()
