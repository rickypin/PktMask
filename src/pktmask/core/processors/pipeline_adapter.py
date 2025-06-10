"""
处理器管道适配器

将新的处理器系统适配到现有的Pipeline架构中，
提供向后兼容性而无需重写整个管道系统。
"""
from typing import List, Optional, Dict, Any
from ..base_step import ProcessingStep
from .base_processor import BaseProcessor, ProcessorResult
from ...infrastructure.logging import get_logger


class ProcessorAdapter(ProcessingStep):
    """处理器适配器
    
    将新的BaseProcessor包装为现有的ProcessingStep接口，
    使新处理器系统能够与现有Pipeline兼容。
    """
    
    def __init__(self, processor: BaseProcessor):
        super().__init__()
        self._processor = processor
        self._logger = get_logger('processor_adapter')
        
    @property
    def name(self) -> str:
        """获取步骤名称"""
        return self._processor.get_display_name()
    
    @property
    def suffix(self) -> str:
        """获取文件后缀"""
        # 根据处理器类型返回相应后缀
        name = self._processor.config.name
        suffix_map = {
            'mask_ip': '-Masked',
            'dedup_packet': '-Deduped', 
            'trim_packet': '-Trimmed'
        }
        return suffix_map.get(name, f'-{name.title()}')
    
    def process_file(self, input_path: str, output_path: str) -> Optional[Dict[str, Any]]:
        """处理单个文件"""
        try:
            # 确保处理器已初始化
            if not self._processor.is_initialized:
                if not self._processor.initialize():
                    self._logger.error(f"处理器 {self.name} 初始化失败")
                    return None
            
            # 调用处理器处理文件
            result = self._processor.process_file(input_path, output_path)
            
            if result.success:
                # 转换处理器结果为步骤结果格式
                step_result = {
                    'success': True,
                    'input_file': input_path,
                    'output_file': output_path,
                    'processor_name': self._processor.config.name,
                    'display_name': self._processor.get_display_name()
                }
                
                # 合并处理器的统计数据
                if result.stats:
                    step_result.update(result.stats)
                
                # 合并处理器的数据
                if result.data:
                    if isinstance(result.data, dict):
                        step_result.update(result.data)
                    else:
                        step_result['data'] = result.data
                
                self._logger.info(f"处理器 {self.name} 处理完成: {input_path} -> {output_path}")
                return step_result
            else:
                self._logger.error(f"处理器 {self.name} 处理失败: {result.error}")
                return None
                
        except Exception as e:
            self._logger.error(f"处理器适配器发生错误: {e}")
            return None
    
    def prepare_for_directory(self, subdir_path: str, all_pcap_files: List[str]):
        """为目录处理做准备"""
        try:
            if hasattr(self._processor, 'prepare_for_directory'):
                self._processor.prepare_for_directory(subdir_path, all_pcap_files)
        except Exception as e:
            self._logger.warning(f"处理器目录准备失败: {e}")
    
    def set_reporter_path(self, path: str, rel_path: str):
        """设置报告器路径（保持兼容性）"""
        # 新处理器系统不需要这个，但保持接口兼容
        pass
    
    def finalize_directory_processing(self) -> Optional[Dict[str, Any]]:
        """完成目录处理"""
        try:
            if hasattr(self._processor, 'finalize_directory_processing'):
                return self._processor.finalize_directory_processing()
        except Exception as e:
            self._logger.warning(f"处理器目录完成失败: {e}")
        return None
    
    def stop(self):
        """停止处理器"""
        try:
            if hasattr(self._processor, 'stop'):
                self._processor.stop()
        except Exception as e:
            self._logger.warning(f"停止处理器失败: {e}")


def adapt_processors_to_pipeline(processors: List[BaseProcessor]) -> List[ProcessingStep]:
    """将处理器列表转换为管道步骤列表"""
    adapted_steps = []
    
    for processor in processors:
        try:
            adapter = ProcessorAdapter(processor)
            adapted_steps.append(adapter)
        except Exception as e:
            logger = get_logger('pipeline_adapter')
            logger.error(f"适配处理器失败: {processor.config.name if processor else 'None'} - {e}")
    
    return adapted_steps


class ProcessorPipeline:
    """简化的处理器管道（可选实现）
    
    这是一个可选的替代方案，直接使用处理器而不需要适配器。
    但需要更多的修改来替代现有的Pipeline类。
    """
    
    def __init__(self, processors: List[BaseProcessor]):
        self._processors = processors
        self._logger = get_logger('processor_pipeline')
        self.is_running = True
    
    def run(self, input_path: str, output_path: str, progress_callback=None):
        """运行处理器管道"""
        current_input = input_path
        
        for i, processor in enumerate(self._processors):
            if not self.is_running:
                break
                
            # 确保处理器已初始化
            if not processor.is_initialized:
                processor.initialize()
            
            # 确定输出路径
            if i == len(self._processors) - 1:
                # 最后一个处理器使用最终输出路径
                current_output = output_path
            else:
                # 中间处理器使用临时文件
                import tempfile
                current_output = tempfile.mktemp(suffix='.pcap')
            
            # 处理文件
            result = processor.process_file(current_input, current_output)
            
            if not result.success:
                raise RuntimeError(f"处理器 {processor.get_display_name()} 失败: {result.error}")
            
            # 更新下一次的输入
            current_input = current_output
            
            # 报告进度
            if progress_callback:
                progress_callback(f"完成: {processor.get_display_name()}")
    
    def stop(self):
        """停止管道"""
        self.is_running = False
        for processor in self._processors:
            if hasattr(processor, 'stop'):
                processor.stop() 