"""
DeduplicationStage 兼容性适配器

将新的 DedupStage 包装为旧的 DeduplicationStage 接口，
确保向后兼容性。
"""
from typing import Optional, Dict, List
from pktmask.core.pipeline.stages.dedup import DedupStage
from pktmask.core.base_step import ProcessingStep
from pktmask.common.constants import ProcessingConstants


class DeduplicationStageCompat(ProcessingStep):
    """
    DeduplicationStage 兼容性适配器
    
    包装新的 DedupStage 以提供旧的 DeduplicationStage 接口。
    这确保了现有代码可以无缝使用新实现。
    """
    
    suffix: str = ProcessingConstants.DEDUP_PACKET_SUFFIX
    
    def __init__(self):
        super().__init__()
        # 创建底层的新实现
        self._stage = DedupStage()
        self._stage.initialize()
    
    @property
    def name(self) -> str:
        return "Remove Dupes"
    
    def process_file_legacy(self, input_path: str, output_path: str) -> Optional[Dict]:
        """
        处理单个文件 - 兼容旧接口
        
        这个方法保持与旧 DeduplicationStage.process_file 完全相同的签名和行为。
        """
        # 调用新实现
        result = self._stage.process_file(input_path, output_path)
        
        if result is None:
            return None
        
        # 将 StageStats 转换为旧格式的字典
        if hasattr(result, 'extra_metrics') and result.extra_metrics:
            # 使用 extra_metrics 中的详细信息
            stats = result.extra_metrics
            return {
                'subdir': stats.get('subdir', ''),
                'input_filename': stats.get('input_filename', ''),
                'output_filename': stats.get('output_filename', ''),
                'total_packets': result.packets_processed,
                'unique_packets': result.packets_processed - result.packets_modified,
                'removed_count': result.packets_modified,
            }
        else:
            # 基本转换
            import os
            return {
                'subdir': os.path.basename(os.path.dirname(input_path)),
                'input_filename': os.path.basename(input_path),
                'output_filename': os.path.basename(output_path),
                'total_packets': result.packets_processed,
                'unique_packets': result.packets_processed - result.packets_modified,
                'removed_count': result.packets_modified,
            }
    
    def prepare_for_directory(self, subdir_path: str, all_files: List[str]):
        """保持与旧接口兼容"""
        # 新实现可能不需要这个方法，但保持接口
        if hasattr(self._stage, 'prepare_for_directory'):
            self._stage.prepare_for_directory(subdir_path, all_files)
    
    def process_directory(self, subdir_path: str, base_path: str = None, progress_callback=None, all_suffixes=None):
        """
        保持与旧接口兼容 - 这个方法在旧实现中存在
        
        注意：新实现可能不支持这个方法，这里提供一个基本的兼容实现
        """
        import warnings
        warnings.warn(
            "process_directory 方法已废弃，请使用新的 Pipeline 架构进行批处理。",
            DeprecationWarning,
            stacklevel=2
        )
        
        # 简单的单文件处理循环作为兼容实现
        from pktmask.utils.file_selector import select_files
        import os
        
        if base_path is None:
            base_path = os.path.dirname(subdir_path)
        
        files_to_process, reason = select_files(subdir_path, self.suffix, all_suffixes or [])
        
        for f in files_to_process:
            file_path = os.path.join(subdir_path, f)
            base, ext = os.path.splitext(file_path)
            if not base.endswith(self.suffix):
                output_path = f"{base}{self.suffix}{ext}"
            else:
                output_path = file_path
            
            try:
                self.process_file_legacy(file_path, output_path)
            except Exception as e:
                if progress_callback:
                    from pktmask.core.events import PipelineEvents
                    progress_callback(PipelineEvents.LOG, {
                        'level': 'error', 
                        'message': f"Error processing {f}: {e}"
                    })
