from __future__ import annotations

from typing import Dict, Any, Optional
from pathlib import Path

from pktmask.core.pipeline.base_stage import StageBase
from pktmask.core.pipeline.models import StageStats
from pktmask.core.processors.base_processor import BaseProcessor, ProcessorResult


class ProcessorStageAdapter(StageBase):
    """将 BaseProcessor 适配为 StageBase 接口的适配器
    
    这个适配器允许现有的 BaseProcessor 实现（如 TSharkEnhancedMaskProcessor）
    被集成到新的 PipelineExecutor 中，实现调用路径的统一。
    """
    
    def __init__(self, processor: BaseProcessor, config: Optional[Dict[str, Any]] = None):
        self._processor = processor
        self._config = config or {}
        super().__init__()
    
    @property 
    def name(self) -> str:
        return f"Adapter_{self._processor.__class__.__name__}"
    
    def initialize(self, config: Optional[Dict[str, Any]] = None) -> None:
        """初始化适配器和底层处理器"""
        if config:
            self._config.update(config)
        
        # 初始化底层处理器
        if not self._processor.is_initialized:
            if not self._processor.initialize():
                raise RuntimeError(f"底层处理器 {self._processor.__class__.__name__} 初始化失败")
        
        # 调用父类初始化
        super().initialize(self._config)
    
    def process_file(self, input_path: str | Path, output_path: str | Path) -> StageStats:
        """将 ProcessorResult 转换为 StageStats"""
        # 调用底层处理器
        result: ProcessorResult = self._processor.process_file(str(input_path), str(output_path))
        
        if not result.success:
            raise RuntimeError(f"Processor {self._processor.__class__.__name__} 失败: {result.error}")
        
        # 转换结果格式
        return StageStats(
            stage_name=self.name,
            packets_processed=result.stats.get('packets_processed', 0) if result.stats else 0,
            packets_modified=result.stats.get('packets_modified', 0) if result.stats else 0,
            duration_ms=result.stats.get('duration_ms', 0.0) if result.stats else 0.0,
            extra_metrics=result.stats or {}
        )
    
    def get_required_tools(self) -> list[str]:
        """获取底层处理器需要的工具"""
        # 如果底层处理器有此方法，调用它
        if hasattr(self._processor, 'get_required_tools'):
            return self._processor.get_required_tools()
        return []
    
    def stop(self) -> None:
        """停止底层处理器"""
        if hasattr(self._processor, 'stop'):
            self._processor.stop()
        super().stop() 