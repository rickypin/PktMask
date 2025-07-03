"""
裁切处理器

简化版的裁切处理器，直接使用TSharkEnhancedMaskProcessor实现。
"""
import os
from typing import Optional

from .base_processor import BaseProcessor, ProcessorConfig, ProcessorResult
from .tshark_enhanced_mask_processor import TSharkEnhancedMaskProcessor
from ...infrastructure.logging import get_logger


class Trimmer(BaseProcessor):
    """裁切处理器
    
    直接使用TSharkEnhancedMaskProcessor实现载荷裁切功能。
    """
    
    def __init__(self, config: ProcessorConfig):
        super().__init__(config)
        self._logger = get_logger('trimmer')
        self._enhanced_trimmer: Optional[TSharkEnhancedMaskProcessor] = None
        
    def _initialize_impl(self):
        """初始化裁切组件"""
        try:
            # 创建TSharkEnhancedMaskProcessor实例
            enhanced_config = ProcessorConfig(
                enabled=True,
                name='enhanced_trim',
                priority=self.config.priority
            )
            self._enhanced_trimmer = TSharkEnhancedMaskProcessor(enhanced_config)
            
            # 初始化TSharkEnhancedMaskProcessor
            if not self._enhanced_trimmer.initialize():
                raise RuntimeError("TSharkEnhancedMaskProcessor初始化失败")
            
            self._logger.info("裁切处理器初始化成功")
            
        except Exception as e:
            self._logger.error(f"裁切处理器初始化失败: {e}")
            raise
            
    def process_file(self, input_path: str, output_path: str) -> ProcessorResult:
        """处理单个文件的裁切"""
        if not self._is_initialized:
            if not self.initialize():
                return ProcessorResult(
                    success=False, 
                    error="处理器未正确初始化"
                )
        
        try:
            # 验证输入
            self.validate_inputs(input_path, output_path)
            
            # 重置统计信息
            self.reset_stats()
            
            self._logger.info(f"开始裁切处理: {input_path} -> {output_path}")
            
            # 委托给TSharkEnhancedMaskProcessor处理
            result = self._enhanced_trimmer.process_file(input_path, output_path)
            
            if not result.success:
                return ProcessorResult(
                    success=False,
                    error=f"TSharkEnhancedMaskProcessor处理失败: {result.error}"
                )
            
            # 从TSharkEnhancedMaskProcessor结果提取数据
            result_data = result.data or {}
            
            # 更新统计信息
            self.stats.update({
                'total_packets': result_data.get('total_packets', 0),
                'trimmed_packets': result_data.get('trimmed_packets', 0),
                'trim_rate': result_data.get('trim_rate', 0.0),
                'space_saved': self._calculate_space_saved(input_path, output_path),
                'processing_efficiency': self._calculate_processing_efficiency(result_data)
            })
            
            trimmed_count = result_data.get('trimmed_packets', 0)
            trim_rate = result_data.get('trim_rate', 0.0)
            self._logger.info(f"裁切完成: 裁切 {trimmed_count} 个数据包 ({trim_rate:.1f}%)")
            
            return ProcessorResult(
                success=True,
                data=result_data,
                stats=self.stats
            )
            
        except FileNotFoundError as e:
            error_msg = f"文件未找到: {e}"
            self._logger.error(error_msg)
            return ProcessorResult(success=False, error=error_msg)
            
        except Exception as e:
            error_msg = f"裁切处理失败: {e}"
            self._logger.error(error_msg)
            return ProcessorResult(success=False, error=error_msg)
    
    def get_display_name(self) -> str:
        """获取用户友好的显示名称"""
        return "Mask Payloads"
    
    def get_description(self) -> str:
        """获取处理器描述"""
        return "智能裁切TLS应用数据载荷，保留握手信令"
        
    def _calculate_space_saved(self, input_path: str, output_path: str) -> dict:
        """计算空间节省情况"""
        try:
            if not os.path.exists(input_path) or not os.path.exists(output_path):
                return {'input_size': 0, 'output_size': 0, 'saved_bytes': 0, 'saved_percentage': 0.0}
            
            input_size = os.path.getsize(input_path)
            output_size = os.path.getsize(output_path)
            saved_bytes = input_size - output_size
            saved_percentage = (saved_bytes / input_size * 100.0) if input_size > 0 else 0.0
            
            return {
                'input_size': input_size,
                'output_size': output_size,
                'saved_bytes': saved_bytes,
                'saved_percentage': saved_percentage
            }
            
        except Exception as e:
            self._logger.warning(f"计算空间节省失败: {e}")
            return {'input_size': 0, 'output_size': 0, 'saved_bytes': 0, 'saved_percentage': 0.0}
            
    def _calculate_processing_efficiency(self, result_data: dict) -> dict:
        """计算处理效率指标"""
        total_packets = result_data.get('total_packets', 0)
        trimmed_packets = result_data.get('trimmed_packets', 0)
        
        if total_packets == 0:
            return {'preservation_rate': 0.0, 'modification_rate': 0.0}
        
        preservation_rate = ((total_packets - trimmed_packets) / total_packets) * 100.0
        modification_rate = (trimmed_packets / total_packets) * 100.0
        
        return {
            'preservation_rate': preservation_rate,
            'modification_rate': modification_rate,
            'packets_preserved': total_packets - trimmed_packets,
            'packets_modified': trimmed_packets
        }
        
    def get_trimming_stats(self) -> dict:
        """获取裁切统计信息"""
        return {
            'total_processed': self.stats.get('total_packets', 0),
            'packets_trimmed': self.stats.get('trimmed_packets', 0),
            'trim_rate': self.stats.get('trim_rate', 0.0),
            'space_saved': self.stats.get('space_saved', {}),
            'efficiency': self.stats.get('processing_efficiency', {})
        } 