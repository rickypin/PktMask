import os
import tempfile
import shutil
from functools import partial
from typing import Callable, Optional, List, Dict, Set, Tuple
from scapy.all import PcapReader, PcapNgReader

from .events import PipelineEvents
from .strategy import AnonymizationStrategy
from .base_step import ProcessingStep
from .factory import STEP_REGISTRY

class Pipeline:
    """定义和执行处理步骤的流水线"""

    def __init__(self, steps: List[ProcessingStep]):
        self._steps = steps
        self.is_running = False
        
        # 从已实例化的步骤中直接获取所有后缀，确保准确性
        self._all_known_suffixes = {step.suffix for step in steps if hasattr(step, 'suffix')}

    def _is_original_file(self, filename: str) -> bool:
        """检查一个文件是否是原始文件（不包含任何处理后缀）。"""
        for suffix in self._all_known_suffixes:
            if suffix in filename:
                return False
        return True

    def _scan_packets_with_progress(self, filepath: str, progress_callback: Callable):
        """扫描文件，分块报告数据包计数以实现动态效果。"""
        chunk_size = 10  # 每次上报的数据包数量
        current_chunk_count = 0
        try:
            ext = os.path.splitext(filepath)[1].lower()
            Reader = PcapNgReader if ext == '.pcapng' else PcapReader
            with Reader(filepath) as reader:
                for _ in reader:
                    if not self.is_running:  # 检查是否需要停止
                        return
                    current_chunk_count += 1
                    if current_chunk_count == chunk_size:
                        progress_callback(PipelineEvents.PACKETS_SCANNED, {'count': current_chunk_count})
                        current_chunk_count = 0
            
            # 发送剩余的数据包计数
            if current_chunk_count > 0:
                progress_callback(PipelineEvents.PACKETS_SCANNED, {'count': current_chunk_count})
        except Exception:
            # 在无法读取文件时忽略错误，后续步骤会处理
            pass

    def run(self, root_path: str, progress_callback: Optional[Callable] = None):
        """
        在指定路径上运行所有处理步骤。
        此方法只处理原始文件，并直接生成最终产物，以避免重复处理。
        """
        self.is_running = True
        
        # 按字母顺序排序后缀以创建标准的输出文件名
        sorted_target_suffixes = sorted([step.suffix for step in self._steps])
        standard_suffix = "".join(sorted_target_suffixes)

        subdirs = [root_path]
        total_subdirs = len(subdirs)

        if progress_callback:
            progress_callback(PipelineEvents.PIPELINE_START, {'total_subdirs': total_subdirs})

        for i, subdir_path in enumerate(subdirs):
            if not self.is_running: break
            
            rel_subdir = os.path.relpath(subdir_path, root_path)
            all_pcap_files_in_dir = [f.path for f in os.scandir(subdir_path) if f.name.endswith(('.pcap', '.pcapng'))]
            source_files = [f for f in all_pcap_files_in_dir if self._is_original_file(os.path.basename(f))]

            if progress_callback:
                progress_callback(PipelineEvents.SUBDIR_START, {
                    'name': rel_subdir, 
                    'current': i + 1, 
                    'total': total_subdirs,
                    'file_count': len(source_files)
                })
            
            # 2. 准备目录级操作 (如IP映射预扫描)
            # 这一步仍然需要所有文件来确保IP映射在所有版本间的一致性
            for step in self._steps:
                if not self.is_running: break
                step.prepare_for_directory(subdir_path, all_pcap_files_in_dir)
                if hasattr(step, 'set_reporter_path'):
                    step.set_reporter_path(subdir_path, rel_subdir)
            
            if not self.is_running: break

            # 3. 遍历并处理每个源文件
            original_order_map = {step: i for i, step in enumerate(self._steps)}
            steps_to_run_instances = sorted(self._steps, key=lambda s: original_order_map[s])

            for input_path in source_files:
                if not self.is_running: break

                # 在处理前预先扫描数据包数量，并分块报告进度
                if progress_callback:
                    self._scan_packets_with_progress(input_path, progress_callback)

                base_name, ext = os.path.splitext(os.path.basename(input_path))
                final_output_path = os.path.join(subdir_path, f"{base_name}{standard_suffix}{ext}")

                if progress_callback:
                    progress_callback(PipelineEvents.FILE_START, {'path': input_path})

                if os.path.exists(final_output_path):
                    if progress_callback:
                        msg = f"  - Skipped: Target file '{os.path.basename(final_output_path)}' already exists."
                        progress_callback(PipelineEvents.LOG, {'message': msg})
                        progress_callback(PipelineEvents.FILE_END, {'path': input_path})
                    continue
                
                temp_files = []
                current_input_path = input_path
                try:
                    for j, step in enumerate(steps_to_run_instances):
                        if not self.is_running: break

                        is_last_step = (j == len(steps_to_run_instances) - 1)
                        output_path = final_output_path if is_last_step else tempfile.mktemp(suffix=ext)
                        if not is_last_step: temp_files.append(output_path)
                        
                        if progress_callback:
                            progress_callback(PipelineEvents.LOG, {'message': f"  - Running step: {step.name}..."})

                        summary = step.process_file(current_input_path, output_path)
                        
                        if summary and progress_callback:
                            # 确保从实例的 'name' 属性获取类型，并进行规范化
                            summary['type'] = step.name.lower().replace(' ', '_').replace('-', '_')
                            progress_callback(PipelineEvents.STEP_SUMMARY, summary)
                        
                        current_input_path = output_path
                finally:
                    for temp_file in temp_files:
                        if os.path.exists(temp_file): os.remove(temp_file)
                
                if progress_callback:
                    progress_callback(PipelineEvents.FILE_END, {'path': input_path})

            # 在目录中所有文件处理完毕后，调用任何最终化方法
            for step in self._steps:
                if hasattr(step, 'finalize_directory_processing'):
                    summary = step.finalize_directory_processing()
                    if summary and progress_callback:
                        step_name = step.name.lower().replace(' ', '_').replace('-', '_')
                        summary['type'] = f"{step_name}_final"
                        progress_callback(PipelineEvents.STEP_SUMMARY, summary)

            if progress_callback:
                progress_callback(PipelineEvents.SUBDIR_END, {'name': rel_subdir})

        self.is_running = False
        if progress_callback:
            progress_callback(PipelineEvents.PIPELINE_END, {})

    def stop(self):
        self.is_running = False
        for step in self._steps:
            if hasattr(step, 'stop'):
                step.stop() 