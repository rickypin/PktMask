"""
去重处理器

简化版的去重处理器，包装现有的DeduplicationStep实现。
"""
import os
from typing import Optional

from .base_processor import BaseProcessor, ProcessorConfig, ProcessorResult
from ...steps.deduplication import DeduplicationStep
from ...infrastructure.logging import get_logger


class Deduplicator(BaseProcessor):
    """去重处理器
    
    使用现有的DeduplicationStep实现，
    但通过简化的处理器接口暴露功能。
    """
    
    def __init__(self, config: ProcessorConfig):
        super().__init__(config)
        self._logger = get_logger('deduplicator')
        self._step: Optional[DeduplicationStep] = None
        
    def _initialize_impl(self):
        """初始化去重组件"""
        try:
            self._step = DeduplicationStep()
            self._logger.info("去重处理器初始化成功")
            
        except Exception as e:
            self._logger.error(f"去重处理器初始化失败: {e}")
            raise
            
    def process_file(self, input_path: str, output_path: str) -> ProcessorResult:
        """处理单个文件的去重"""
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
            
            self._logger.info(f"开始去重处理: {input_path} -> {output_path}")
            
            # 处理文件
            result_data = self._step.process_file(input_path, output_path)
            
            if result_data is None:
                return ProcessorResult(
                    success=False,
                    error="去重处理失败，未返回结果"
                )
            
            # 更新统计信息
            self.stats.update({
                'total_packets': result_data.get('total_packets', 0),
                'unique_packets': result_data.get('unique_packets', 0),
                'removed_count': result_data.get('removed_count', 0),
                'deduplication_rate': self._calculate_deduplication_rate(result_data),
                'space_saved': self._calculate_space_saved(input_path, output_path)
            })
            
            removed_count = result_data.get('removed_count', 0)
            self._logger.info(f"去重完成: 移除 {removed_count} 个重复数据包")
            
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
            error_msg = f"去重处理失败: {e}"
            self._logger.error(error_msg)
            return ProcessorResult(success=False, error=error_msg)
    
    def get_display_name(self) -> str:
        """获取用户友好的显示名称"""
        return "Remove Dupes"
    
    def get_description(self) -> str:
        """获取处理器描述"""
        return "移除完全重复的数据包，减少文件大小"
        
    def _calculate_deduplication_rate(self, result_data: dict) -> float:
        """计算去重比率"""
        total_packets = result_data.get('total_packets', 0)
        removed_count = result_data.get('removed_count', 0)
        
        if total_packets == 0:
            return 0.0
        
        return (removed_count / total_packets) * 100.0
        
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
            
    def get_duplication_stats(self) -> dict:
        """获取去重统计信息"""
        return {
            'total_processed': self.stats.get('total_packets', 0),
            'unique_found': self.stats.get('unique_packets', 0),
            'duplicates_removed': self.stats.get('removed_count', 0),
            'deduplication_rate': self.stats.get('deduplication_rate', 0.0),
            'space_saved': self.stats.get('space_saved', {})
        } 