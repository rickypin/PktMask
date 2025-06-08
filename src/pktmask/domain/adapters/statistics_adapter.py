"""
统计数据适配器

提供新旧统计数据格式之间的双向转换。
"""

from typing import Dict, Any, Optional
from datetime import datetime
from PyQt6.QtCore import QTime

from ..models.statistics_data import (
    StatisticsData, ProcessingMetrics, TimingData, 
    FileProcessingResults, IPMappingData, ProcessingState
)
from ...infrastructure.logging import get_logger


class StatisticsDataAdapter:
    """统计数据适配器 - 在新旧统计数据格式之间转换"""
    
    def __init__(self):
        self._logger = get_logger(__name__)
    
    def from_legacy_manager(self, legacy_manager) -> StatisticsData:
        """从遗留的StatisticsManager转换为新的StatisticsData模型"""
        try:
            # 处理指标
            metrics = ProcessingMetrics(
                files_processed=legacy_manager.files_processed,
                total_files_to_process=legacy_manager.total_files_to_process,
                packets_processed=legacy_manager.packets_processed
            )
            
            # 时间统计
            timing = TimingData(
                start_time=self._qtime_to_datetime(legacy_manager.start_time),
                processing_time_ms=legacy_manager.processing_time
            )
            
            # 文件处理结果
            file_results = {}
            for filename, result_data in legacy_manager.file_processing_results.items():
                file_results[filename] = FileProcessingResults(
                    filename=filename,
                    steps=result_data.get('steps', {}),
                    timestamp=result_data.get('timestamp'),
                    status="completed" if result_data.get('steps') else "pending"
                )
            
            # IP映射数据
            ip_mapping = IPMappingData(
                global_mappings=legacy_manager.global_ip_mappings.copy(),
                reports_by_subdir=legacy_manager.all_ip_reports.copy()
            )
            
            # 处理状态
            state = ProcessingState(
                current_processing_file=legacy_manager.current_processing_file,
                subdirs_files_counted=legacy_manager.subdirs_files_counted.copy(),
                subdirs_packets_counted=legacy_manager.subdirs_packets_counted.copy(),
                printed_summary_headers=legacy_manager.printed_summary_headers.copy()
            )
            
            # 创建完整的统计数据模型
            stats_data = StatisticsData(
                metrics=metrics,
                timing=timing,
                file_results=file_results,
                step_results=legacy_manager.step_results.copy(),
                ip_mapping=ip_mapping,
                state=state
            )
            
            self._logger.debug(f"从遗留管理器转换统计数据: {metrics.files_processed} files")
            return stats_data
            
        except Exception as e:
            self._logger.error(f"统计数据转换失败: {e}")
            # 返回默认的统计数据
            return StatisticsData()
    
    def to_legacy_dict(self, stats_data: StatisticsData) -> Dict[str, Any]:
        """将新的StatisticsData模型转换为遗留字典格式"""
        try:
            return {
                'files_processed': stats_data.metrics.files_processed,
                'total_files_to_process': stats_data.metrics.total_files_to_process,
                'packets_processed': stats_data.metrics.packets_processed,
                'processing_time': stats_data.timing.get_elapsed_time_string(),
                'step_results': stats_data.step_results.copy(),
                'file_processing_results': {
                    filename: result.dict() for filename, result in stats_data.file_results.items()
                },
                'global_ip_mappings': stats_data.ip_mapping.global_mappings.copy(),
                'all_ip_reports': stats_data.ip_mapping.reports_by_subdir.copy(),
                'current_processing_file': stats_data.state.current_processing_file,
                'completion_rate': stats_data.metrics.get_completion_rate(),
                'processing_speed': stats_data.timing.get_processing_speed(stats_data.metrics.packets_processed)
            }
            
        except Exception as e:
            self._logger.error(f"转换为遗留字典格式失败: {e}")
            return {}
    
    def update_legacy_manager(self, legacy_manager, stats_data: StatisticsData):
        """使用新的StatisticsData模型更新遗留的StatisticsManager"""
        try:
            # 更新基础统计
            legacy_manager.files_processed = stats_data.metrics.files_processed
            legacy_manager.total_files_to_process = stats_data.metrics.total_files_to_process
            legacy_manager.packets_processed = stats_data.metrics.packets_processed
            
            # 更新时间统计
            if stats_data.timing.start_time:
                legacy_manager.start_time = self._datetime_to_qtime(stats_data.timing.start_time)
            legacy_manager.processing_time = stats_data.timing.processing_time_ms
            
            # 更新文件处理结果
            legacy_manager.file_processing_results = {
                filename: result.dict() for filename, result in stats_data.file_results.items()
            }
            
            # 更新步骤结果
            legacy_manager.step_results = stats_data.step_results.copy()
            
            # 更新IP映射
            legacy_manager.global_ip_mappings = stats_data.ip_mapping.global_mappings.copy()
            legacy_manager.all_ip_reports = stats_data.ip_mapping.reports_by_subdir.copy()
            
            # 更新处理状态
            legacy_manager.current_processing_file = stats_data.state.current_processing_file
            legacy_manager.subdirs_files_counted = stats_data.state.subdirs_files_counted.copy()
            legacy_manager.subdirs_packets_counted = stats_data.state.subdirs_packets_counted.copy()
            legacy_manager.printed_summary_headers = stats_data.state.printed_summary_headers.copy()
            
            self._logger.debug(f"更新遗留管理器: {stats_data.metrics.files_processed} files")
            
        except Exception as e:
            self._logger.error(f"更新遗留管理器失败: {e}")
    
    def merge_statistics(self, base_stats: StatisticsData, update_data: Dict[str, Any]) -> StatisticsData:
        """将更新数据合并到基础统计数据中"""
        try:
            # 创建更新后的统计数据
            updated_stats = base_stats.copy(deep=True)
            
            # 更新处理指标
            if 'files_processed' in update_data:
                updated_stats.metrics.files_processed = update_data['files_processed']
            if 'total_files_to_process' in update_data:
                updated_stats.metrics.total_files_to_process = update_data['total_files_to_process']
            if 'packets_processed' in update_data:
                updated_stats.metrics.packets_processed = update_data['packets_processed']
            
            # 更新时间信息
            if 'start_time' in update_data:
                updated_stats.timing.start_time = update_data['start_time']
            if 'processing_time_ms' in update_data:
                updated_stats.timing.processing_time_ms = update_data['processing_time_ms']
            
            # 更新文件结果
            if 'file_processing_results' in update_data:
                for filename, result_data in update_data['file_processing_results'].items():
                    updated_stats.file_results[filename] = FileProcessingResults(
                        filename=filename,
                        steps=result_data.get('steps', {}),
                        timestamp=result_data.get('timestamp'),
                        status=result_data.get('status', 'completed')
                    )
            
            # 更新步骤结果
            if 'step_results' in update_data:
                updated_stats.step_results.update(update_data['step_results'])
            
            # 更新IP映射
            if 'global_ip_mappings' in update_data:
                updated_stats.ip_mapping.global_mappings.update(update_data['global_ip_mappings'])
            if 'all_ip_reports' in update_data:
                updated_stats.ip_mapping.reports_by_subdir.update(update_data['all_ip_reports'])
            
            # 更新处理状态
            if 'current_processing_file' in update_data:
                updated_stats.state.current_processing_file = update_data['current_processing_file']
            
            self._logger.debug(f"合并统计数据: {len(update_data)} 个更新字段")
            return updated_stats
            
        except Exception as e:
            self._logger.error(f"合并统计数据失败: {e}")
            return base_stats
    
    def create_dashboard_update(self, stats_data: StatisticsData) -> Dict[str, Any]:
        """创建仪表盘更新数据"""
        return stats_data.get_dashboard_summary()
    
    def create_processing_summary(self, stats_data: StatisticsData) -> Dict[str, Any]:
        """创建处理摘要数据"""
        return stats_data.get_processing_summary()
    
    def _qtime_to_datetime(self, qtime: Optional[QTime]) -> Optional[datetime]:
        """将QTime转换为datetime"""
        if qtime is None:
            return None
        
        # 由于QTime只包含时间，我们使用今天的日期
        from datetime import date, time
        today = date.today()
        time_obj = time(qtime.hour(), qtime.minute(), qtime.second(), qtime.msec() * 1000)
        return datetime.combine(today, time_obj)
    
    def _datetime_to_qtime(self, dt: Optional[datetime]) -> Optional[QTime]:
        """将datetime转换为QTime"""
        if dt is None:
            return None
        
        return QTime(dt.hour, dt.minute, dt.second, dt.microsecond // 1000)
    
    def validate_statistics_data(self, stats_data: StatisticsData) -> bool:
        """验证统计数据的完整性"""
        try:
            # 检查基础指标
            if stats_data.metrics.files_processed < 0:
                self._logger.warning("文件处理数不能为负数")
                return False
            
            if (stats_data.metrics.total_files_to_process > 0 and 
                stats_data.metrics.files_processed > stats_data.metrics.total_files_to_process):
                self._logger.warning("已处理文件数不能超过总文件数")
                return False
            
            # 检查时间数据
            if stats_data.timing.processing_time_ms < 0:
                self._logger.warning("处理时间不能为负数")
                return False
            
            self._logger.debug("统计数据验证通过")
            return True
            
        except Exception as e:
            self._logger.error(f"统计数据验证失败: {e}")
            return False
    
    def get_performance_metrics(self, stats_data: StatisticsData) -> Dict[str, Any]:
        """获取性能指标"""
        try:
            duration_seconds = stats_data.timing.processing_time_ms / 1000.0
            
            metrics = {
                'files_per_minute': 0.0,
                'packets_per_second': 0.0,
                'completion_rate': stats_data.metrics.get_completion_rate(),
                'processing_speed': stats_data.timing.get_processing_speed(stats_data.metrics.packets_processed)
            }
            
            if duration_seconds > 0:
                metrics['files_per_minute'] = (stats_data.metrics.files_processed / duration_seconds) * 60
                metrics['packets_per_second'] = stats_data.metrics.packets_processed / duration_seconds
            
            return metrics
            
        except Exception as e:
            self._logger.error(f"获取性能指标失败: {e}")
            return {} 