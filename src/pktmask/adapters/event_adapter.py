"""
事件数据适配器

提供新旧事件数据格式之间的双向转换。
"""

from typing import Dict, Any, Optional, Union
from datetime import datetime

from pktmask.domain.models.pipeline_event_data import (
    PipelineEventData, BaseEventData, PipelineStartData, PipelineEndData,
    SubdirStartData, SubdirEndData, FileStartData, FileEndData,
    StepStartData, StepEndData, StepSummaryData, PacketsScannedData,
    LogEventData, ErrorEventData, EVENT_DATA_MAPPING
)
from pktmask.core.events import PipelineEvents
from pktmask.infrastructure.logging import get_logger


class EventDataAdapter:
    """事件数据适配器 - 在新旧数据格式之间转换"""
    
    def __init__(self):
        self._logger = get_logger(__name__)
    
    def from_legacy_dict(self, event_type: PipelineEvents, data: Dict[str, Any]) -> PipelineEventData:
        """从遗留字典格式转换为新的事件数据模型"""
        try:
            # 获取对应的数据类
            data_class = EVENT_DATA_MAPPING.get(event_type, BaseEventData)
            
            # 预处理数据，确保兼容性
            processed_data = self._preprocess_legacy_data(event_type, data)
            
            # 创建事件数据对象（注意：不要重复传递event_type，它在__init__中设置）
            event_data = data_class(**processed_data)
            
            # 包装在PipelineEventData中
            pipeline_event = PipelineEventData(event_type=event_type, data=event_data)
            
            self._logger.debug(f"转换事件数据: {event_type} -> {type(event_data).__name__}")
            return pipeline_event
            
        except Exception as e:
            self._logger.warning(f"事件数据转换失败，使用基础格式: {e}")
            # 回退到基础事件数据
            base_data = BaseEventData(
                event_type=event_type,
                message=data.get('message', str(data))
            )
            return PipelineEventData(event_type=event_type, data=base_data)
    
    def to_legacy_dict(self, event_data: PipelineEventData) -> Dict[str, Any]:
        """将新的事件数据模型转换为遗留字典格式"""
        try:
            # 获取基础字典
            result = event_data.data.dict()
            
            # 添加遗留格式需要的字段
            if 'type' not in result:
                result['type'] = event_data.event_type.name if hasattr(event_data.event_type, 'name') else str(event_data.event_type)
            
            # 移除新模型特有的字段
            result.pop('event_type', None)
            result.pop('timestamp', None)
            result.pop('severity', None)
            
            self._logger.debug(f"转换为遗留格式: {event_data.event_type}")
            return result
            
        except Exception as e:
            self._logger.error(f"转换为遗留格式失败: {e}")
            return {'message': str(event_data.data), 'type': str(event_data.event_type)}
    
    def _preprocess_legacy_data(self, event_type: PipelineEvents, data: Dict[str, Any]) -> Dict[str, Any]:
        """预处理遗留数据，确保与新模型兼容"""
        processed = data.copy()
        
        # 通用字段映射
        if 'message' not in processed and 'msg' in processed:
            processed['message'] = processed.pop('msg')
        
        # 根据事件类型进行特殊处理
        if event_type in [PipelineEvents.PIPELINE_START, PipelineEvents.PIPELINE_STARTED]:
            self._process_pipeline_start_data(processed)
        elif event_type in [PipelineEvents.PIPELINE_END, PipelineEvents.PIPELINE_COMPLETED]:
            self._process_pipeline_end_data(processed)
        elif event_type == PipelineEvents.SUBDIR_START:
            self._process_subdir_start_data(processed)
        elif event_type == PipelineEvents.SUBDIR_END:
            self._process_subdir_end_data(processed)
        elif event_type in [PipelineEvents.FILE_START, PipelineEvents.FILE_STARTED]:
            self._process_file_start_data(processed)
        elif event_type in [PipelineEvents.FILE_END, PipelineEvents.FILE_COMPLETED]:
            self._process_file_end_data(processed)
        elif event_type in [PipelineEvents.STEP_START, PipelineEvents.STEP_STARTED]:
            self._process_step_start_data(processed)
        elif event_type in [PipelineEvents.STEP_END, PipelineEvents.STEP_COMPLETED]:
            self._process_step_end_data(processed)
        elif event_type == PipelineEvents.STEP_SUMMARY:
            self._process_step_summary_data(processed)
        elif event_type == PipelineEvents.PACKETS_SCANNED:
            self._process_packets_scanned_data(processed)
        elif event_type == PipelineEvents.LOG:
            self._process_log_data(processed)
        elif event_type == PipelineEvents.ERROR:
            self._process_error_data(processed)
        
        return processed
    
    def _process_pipeline_start_data(self, data: Dict[str, Any]):
        """处理管道开始事件数据"""
        if 'total_subdirs' not in data:
            data['total_subdirs'] = data.get('total_dirs', data.get('total_files', 0))
        if 'root_path' not in data:
            data['root_path'] = data.get('base_dir', data.get('input_dir', ''))
        if 'output_dir' not in data:
            data['output_dir'] = data.get('output_directory', '')
    
    def _process_pipeline_end_data(self, data: Dict[str, Any]):
        """处理管道结束事件数据"""
        if 'success' not in data:
            data['success'] = data.get('status', 'success') == 'success'
        if 'files_processed' not in data:
            data['files_processed'] = data.get('total_files', 0)
        if 'duration_ms' not in data:
            data['duration_ms'] = data.get('elapsed_time', 0)
    
    def _process_subdir_start_data(self, data: Dict[str, Any]):
        """处理子目录开始事件数据"""
        if 'name' not in data:
            data['name'] = data.get('subdir', data.get('directory', 'Unknown'))
        if 'path' not in data:
            data['path'] = data.get('subdir_path', data.get('directory_path', ''))
        if 'file_count' not in data:
            data['file_count'] = data.get('files', data.get('total_files', 0))
    
    def _process_subdir_end_data(self, data: Dict[str, Any]):
        """处理子目录结束事件数据"""
        if 'name' not in data:
            data['name'] = data.get('subdir', data.get('directory', 'Unknown'))
        if 'files_processed' not in data:
            data['files_processed'] = data.get('files', 0)
    
    def _process_file_start_data(self, data: Dict[str, Any]):
        """处理文件开始事件数据"""
        if 'path' not in data:
            data['path'] = data.get('file', data.get('filename', ''))
        if 'filename' not in data and 'path' in data:
            data['filename'] = data['path'].split('/')[-1]
        if 'size_bytes' not in data:
            data['size_bytes'] = data.get('size', None)
    
    def _process_file_end_data(self, data: Dict[str, Any]):
        """处理文件结束事件数据"""
        if 'path' not in data:
            data['path'] = data.get('file', data.get('filename', ''))
        if 'filename' not in data and 'path' in data:
            data['filename'] = data['path'].split('/')[-1]
        if 'success' not in data:
            data['success'] = data.get('status', 'success') == 'success'
        if 'output_filename' not in data:
            data['output_filename'] = data.get('output', data.get('output_file'))
        if 'packets_processed' not in data:
            data['packets_processed'] = data.get('packets', 0)
    
    def _process_step_start_data(self, data: Dict[str, Any]):
        """处理步骤开始事件数据"""
        if 'step_name' not in data:
            data['step_name'] = data.get('step', data.get('name', 'Unknown Step'))
        if 'step_type' not in data:
            data['step_type'] = data.get('type', data.get('step_name', ''))
        if 'filename' not in data:
            data['filename'] = data.get('file', data.get('path', ''))
    
    def _process_step_end_data(self, data: Dict[str, Any]):
        """处理步骤结束事件数据"""
        if 'step_name' not in data:
            data['step_name'] = data.get('step', data.get('name', 'Unknown Step'))
        if 'step_type' not in data:
            data['step_type'] = data.get('type', data.get('step_name', ''))
        if 'filename' not in data:
            data['filename'] = data.get('file', data.get('path', ''))
        if 'success' not in data:
            data['success'] = data.get('status', 'success') == 'success'
        if 'duration_ms' not in data:
            data['duration_ms'] = data.get('elapsed_time', 0)
    
    def _process_step_summary_data(self, data: Dict[str, Any]):
        """处理步骤摘要事件数据"""
        if 'step_name' not in data:
            data['step_name'] = data.get('step', data.get('name', 'Unknown Step'))
        if 'step_type' not in data:
            data['step_type'] = data.get('type', data.get('step_name', ''))
        if 'filename' not in data:
            data['filename'] = data.get('file', data.get('path', ''))
        if 'result' not in data:
            # 收集所有非元数据字段作为结果
            excluded_keys = {'step_name', 'step_type', 'filename', 'type', 'message'}
            data['result'] = {k: v for k, v in data.items() if k not in excluded_keys}
    
    def _process_packets_scanned_data(self, data: Dict[str, Any]):
        """处理包扫描事件数据"""
        if 'count' not in data:
            data['count'] = data.get('packets', data.get('num_packets', 0))
        if 'filename' not in data:
            data['filename'] = data.get('file', None)
    
    def _process_log_data(self, data: Dict[str, Any]):
        """处理日志事件数据"""
        if 'log_message' not in data:
            data['log_message'] = data.get('message', data.get('msg', ''))
        if 'log_level' not in data:
            data['log_level'] = data.get('level', 'INFO')
        if 'source' not in data:
            data['source'] = data.get('logger', data.get('module'))
    
    def _process_error_data(self, data: Dict[str, Any]):
        """处理错误事件数据"""
        if 'error_message' not in data:
            data['error_message'] = data.get('message', data.get('error', data.get('msg', '')))
        if 'error_code' not in data:
            data['error_code'] = data.get('code', None)
        if 'error_step' not in data:
            data['error_step'] = data.get('step', None)
        if 'traceback' not in data:
            data['traceback'] = data.get('trace', data.get('stack_trace'))
        if 'context' not in data:
            # 收集除错误信息外的所有数据作为上下文
            excluded_keys = {'error_message', 'error_code', 'error_step', 'traceback', 'message', 'error', 'msg'}
            data['context'] = {k: v for k, v in data.items() if k not in excluded_keys}
    
    def create_enhanced_event(self, event_type: PipelineEvents, **kwargs) -> PipelineEventData:
        """创建增强的事件数据，直接使用新模型"""
        data_class = EVENT_DATA_MAPPING.get(event_type, BaseEventData)
        event_data = data_class(**kwargs)
        return PipelineEventData(event_type=event_type, data=event_data)
    
    def is_legacy_format(self, data: Any) -> bool:
        """检查数据是否为遗留格式"""
        return isinstance(data, dict) and not isinstance(data, PipelineEventData) 