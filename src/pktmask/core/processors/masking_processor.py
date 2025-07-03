from warnings import warn

from .base_processor import BaseProcessor, ProcessorConfig, ProcessorResult
from .tshark_enhanced_mask_processor import TSharkEnhancedMaskProcessor


class MaskingProcessor(BaseProcessor):
    """新版官方载荷掩码处理器。

    该类作为官方推荐的载荷掩码处理器，基于TSharkEnhancedMaskProcessor实现。
    提供稳定可靠的载荷掩码功能，支持智能协议识别和精确掩码。
    """

    def __init__(self, config: ProcessorConfig):
        super().__init__(config)
        self._tshark_processor: TSharkEnhancedMaskProcessor = None

    def _initialize_impl(self):
        """初始化内部TShark处理器"""
        try:
            self._tshark_processor = TSharkEnhancedMaskProcessor(self.config)
            if not self._tshark_processor.initialize():
                raise RuntimeError("TSharkEnhancedMaskProcessor初始化失败")
        except Exception as e:
            raise RuntimeError(f"MaskingProcessor初始化失败: {e}")

    def process_file(self, input_path: str, output_path: str) -> ProcessorResult:
        """处理文件的核心方法"""
        try:
            self.validate_inputs(input_path, output_path)
            
            if not self.is_initialized:
                if not self.initialize():
                    return ProcessorResult(
                        success=False,
                        error="处理器初始化失败"
                    )
            
            # 委托给TSharkEnhancedMaskProcessor处理
            result = self._tshark_processor.process_file(input_path, output_path)
            
            # 更新统计信息
            if result.success:
                self.stats.update(result.stats)
            
            return result
            
        except Exception as e:
            return ProcessorResult(
                success=False,
                error=f"MaskingProcessor处理失败: {str(e)}"
            )

    def get_display_name(self) -> str:
        return "Mask Payloads"

    def get_description(self) -> str:
        return (
            "智能载荷掩码处理器，"
            "基于TShark深度协议解析，支持TLS/HTTP等协议的精确掩码。"
        )

    def cleanup(self):
        """清理资源"""
        if self._tshark_processor:
            self._tshark_processor.cleanup() 