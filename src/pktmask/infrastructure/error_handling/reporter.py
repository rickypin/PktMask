#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
错误报告系统
提供错误报告的生成、存储和分析功能
"""

import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict

from ...common.exceptions import PktMaskError
from ...infrastructure.logging import get_logger
from .context import ErrorContext
from .recovery import RecoveryResult

logger = get_logger(__name__)


@dataclass
class ErrorReport:
    """错误报告数据结构"""
    report_id: str
    timestamp: datetime
    error_info: Dict[str, Any]
    context_info: Dict[str, Any]
    recovery_info: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'report_id': self.report_id,
            'timestamp': self.timestamp.isoformat(),
            'error_info': self.error_info,
            'context_info': self.context_info,
            'recovery_info': self.recovery_info
        }


class ErrorReporter:
    """错误报告器"""
    
    def __init__(self, report_directory: Optional[Path] = None):
        self.report_directory = report_directory or Path.home() / '.config' / 'pktmask' / 'error_reports'
        self.ensure_report_directory()
        
        # 报告配置
        self.max_reports_to_keep = 100
        self.enable_detailed_reports = True
        self.enable_summary_reports = True
        
        # 报告统计
        self.reports_generated = 0
        
        logger.debug(f"Error reporter initialized, reports directory: {self.report_directory}")
    
    def ensure_report_directory(self) -> None:
        """确保报告目录存在"""
        try:
            self.report_directory.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create error reports directory: {e}")
    
    def report_error(self, error: PktMaskError, context: ErrorContext, 
                    recovery_result: Optional[RecoveryResult] = None) -> ErrorReport:
        """生成错误报告"""
        # 生成报告ID
        report_id = f"error_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self.reports_generated:04d}"
        
        # 准备错误信息
        error_info = error.to_dict()
        
        # 准备上下文信息
        context_info = context.to_dict()
        
        # 准备恢复信息
        recovery_info = None
        if recovery_result:
            recovery_info = {
                'action': recovery_result.action.value,
                'success': recovery_result.success,
                'message': recovery_result.message,
                'retry_count': recovery_result.retry_count,
                'custom_data': recovery_result.custom_data
            }
        
        # 创建报告
        report = ErrorReport(
            report_id=report_id,
            timestamp=datetime.now(),
            error_info=error_info,
            context_info=context_info,
            recovery_info=recovery_info
        )
        
        # 保存报告
        if self.enable_detailed_reports:
            self._save_detailed_report(report)
        
        self.reports_generated += 1
        
        # 清理旧报告
        self._cleanup_old_reports()
        
        logger.debug(f"Generated error report: {report_id}")
        return report
    
    def _save_detailed_report(self, report: ErrorReport) -> None:
        """保存详细报告"""
        try:
            report_file = self.report_directory / f"{report.report_id}.json"
            
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)
            
            logger.debug(f"Saved detailed error report: {report_file}")
            
        except Exception as e:
            logger.error(f"Failed to save error report: {e}")
    
    def _cleanup_old_reports(self) -> None:
        """清理旧的报告文件"""
        try:
            report_files = list(self.report_directory.glob("error_*.json"))
            
            if len(report_files) > self.max_reports_to_keep:
                # 按修改时间排序，删除最旧的文件
                report_files.sort(key=lambda f: f.stat().st_mtime)
                files_to_delete = report_files[:-self.max_reports_to_keep]
                
                for file_to_delete in files_to_delete:
                    try:
                        file_to_delete.unlink()
                        logger.debug(f"Deleted old error report: {file_to_delete}")
                    except Exception as e:
                        logger.warning(f"Failed to delete old report {file_to_delete}: {e}")
                        
        except Exception as e:
            logger.error(f"Failed to cleanup old reports: {e}")
    
    def get_recent_reports(self, limit: int = 10) -> List[ErrorReport]:
        """获取最近的错误报告"""
        reports = []
        
        try:
            report_files = list(self.report_directory.glob("error_*.json"))
            report_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            
            for report_file in report_files[:limit]:
                try:
                    with open(report_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    report = ErrorReport(
                        report_id=data['report_id'],
                        timestamp=datetime.fromisoformat(data['timestamp']),
                        error_info=data['error_info'],
                        context_info=data['context_info'],
                        recovery_info=data.get('recovery_info')
                    )
                    
                    reports.append(report)
                    
                except Exception as e:
                    logger.warning(f"Failed to load report {report_file}: {e}")
                    
        except Exception as e:
            logger.error(f"Failed to get recent reports: {e}")
        
        return reports
    
    def generate_summary_report(self, time_range_hours: int = 24) -> Dict[str, Any]:
        """生成汇总报告"""
        end_time = datetime.now()
        start_time = end_time.replace(hour=end_time.hour - time_range_hours)
        
        summary = {
            'time_range': {
                'start': start_time.isoformat(),
                'end': end_time.isoformat(),
                'hours': time_range_hours
            },
            'total_errors': 0,
            'error_types': {},
            'severity_distribution': {},
            'component_errors': {},
            'operation_errors': {},
            'recovery_stats': {
                'attempted': 0,
                'successful': 0,
                'failed': 0,
                'success_rate': 0.0
            }
        }
        
        try:
            recent_reports = self.get_recent_reports(limit=1000)  # 获取更多报告用于分析
            
            for report in recent_reports:
                # 检查时间范围
                if report.timestamp < start_time:
                    continue
                
                summary['total_errors'] += 1
                
                # 错误类型统计
                error_type = report.error_info.get('type', 'Unknown')
                summary['error_types'][error_type] = summary['error_types'].get(error_type, 0) + 1
                
                # 严重性分布
                severity = report.error_info.get('severity', 'Unknown')
                summary['severity_distribution'][severity] = summary['severity_distribution'].get(severity, 0) + 1
                
                # 组件错误统计
                component = report.context_info.get('application', {}).get('component', 'Unknown')
                summary['component_errors'][component] = summary['component_errors'].get(component, 0) + 1
                
                # 操作错误统计
                operation = report.context_info.get('application', {}).get('operation', 'Unknown')
                summary['operation_errors'][operation] = summary['operation_errors'].get(operation, 0) + 1
                
                # 恢复统计
                if report.recovery_info:
                    summary['recovery_stats']['attempted'] += 1
                    if report.recovery_info.get('success', False):
                        summary['recovery_stats']['successful'] += 1
                    else:
                        summary['recovery_stats']['failed'] += 1
            
            # 计算成功率
            if summary['recovery_stats']['attempted'] > 0:
                summary['recovery_stats']['success_rate'] = (
                    summary['recovery_stats']['successful'] / summary['recovery_stats']['attempted']
                )
            
        except Exception as e:
            logger.error(f"Failed to generate summary report: {e}")
        
        return summary
    
    def export_reports(self, output_file: Path, format_type: str = 'json') -> bool:
        """导出错误报告"""
        try:
            reports = self.get_recent_reports(limit=1000)
            
            if format_type.lower() == 'json':
                export_data = {
                    'export_timestamp': datetime.now().isoformat(),
                    'total_reports': len(reports),
                    'reports': [report.to_dict() for report in reports]
                }
                
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=2, ensure_ascii=False)
                    
            else:
                logger.error(f"Unsupported export format: {format_type}")
                return False
            
            logger.info(f"Exported {len(reports)} error reports to {output_file}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export reports: {e}")
            return False
    
    def get_report_stats(self) -> Dict[str, Any]:
        """获取报告统计信息"""
        return {
            'reports_generated': self.reports_generated,
            'report_directory': str(self.report_directory),
            'max_reports_to_keep': self.max_reports_to_keep,
            'detailed_reports_enabled': self.enable_detailed_reports,
            'summary_reports_enabled': self.enable_summary_reports
        }


# 全局错误报告器实例
_error_reporter = ErrorReporter()


def get_error_reporter() -> ErrorReporter:
    """获取全局错误报告器"""
    return _error_reporter 