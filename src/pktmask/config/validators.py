#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
配置验证器
提供配置值验证和一致性检查功能
"""

import os
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from ..infrastructure.logging import get_logger
from ..common.exceptions import ValidationError, ConfigError
from .models import PktMaskConfig, UIConfig, ProcessingConfig, PerformanceConfig, FileConfig, LoggingConfig


class ConfigValidator:
    """配置验证器"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.errors: List[str] = []
        self.warnings: List[str] = []
    
    def validate_config(self, config: PktMaskConfig) -> Tuple[bool, List[str], List[str]]:
        """
        验证完整配置
        
        Args:
            config: 配置对象
            
        Returns:
            Tuple[bool, List[str], List[str]]: (是否有效, 错误列表, 警告列表)
        """
        self.errors.clear()
        self.warnings.clear()
        
        # 验证各个子配置
        self._validate_ui_config(config.ui)
        self._validate_processing_config(config.processing)
        self._validate_performance_config(config.performance)
        self._validate_file_config(config.file)
        self._validate_logging_config(config.logging)
        
        # 验证配置间的一致性
        self._validate_config_consistency(config)
        
        is_valid = len(self.errors) == 0
        
        if is_valid:
            self.logger.info("配置验证通过")
        else:
            self.logger.error(f"配置验证失败，发现 {len(self.errors)} 个错误")
            
        if self.warnings:
            self.logger.warning(f"配置验证发现 {len(self.warnings)} 个警告")
        
        return is_valid, self.errors.copy(), self.warnings.copy()
    
    def _validate_ui_config(self, ui_config: UIConfig) -> None:
        """验证UI配置"""
        try:
            # 验证窗口尺寸
            if ui_config.window_width < ui_config.window_min_width:
                self.errors.append(f"窗口宽度 ({ui_config.window_width}) 小于最小宽度 ({ui_config.window_min_width})")
                
            if ui_config.window_height < ui_config.window_min_height:
                self.errors.append(f"窗口高度 ({ui_config.window_height}) 小于最小高度 ({ui_config.window_min_height})")
            
            # 验证主题
            valid_themes = ['auto', 'light', 'dark']
            if ui_config.theme not in valid_themes:
                self.errors.append(f"无效的主题: {ui_config.theme}，必须是 {valid_themes} 之一")
            
            # 验证语言
            valid_languages = ['zh_CN', 'en_US']
            if ui_config.language not in valid_languages:
                self.errors.append(f"无效的语言: {ui_config.language}，必须是 {valid_languages} 之一")
            
            # 验证字体大小
            if ui_config.font_size < 8 or ui_config.font_size > 24:
                self.warnings.append(f"字体大小 ({ui_config.font_size}) 超出推荐范围 (8-24)")
                
        except Exception as e:
            self.errors.append(f"UI配置验证失败: {e}")
    
    def _validate_processing_config(self, processing_config: ProcessingConfig) -> None:
        """验证处理配置"""
        try:
            # 验证块大小
            if processing_config.chunk_size < 1:
                self.errors.append("块大小必须大于0")
            elif processing_config.chunk_size > 1000:
                self.warnings.append(f"块大小 ({processing_config.chunk_size}) 过大，可能影响性能")
            
            # 验证重试次数
            if processing_config.max_retry_attempts < 1:
                self.errors.append("最大重试次数必须大于0")
            elif processing_config.max_retry_attempts > 10:
                self.warnings.append(f"重试次数 ({processing_config.max_retry_attempts}) 过多，可能影响性能")
            
            # 验证超时时间
            if processing_config.timeout_seconds < 60:
                self.warnings.append("超时时间过短，可能导致大文件处理失败")
            elif processing_config.timeout_seconds > 3600:
                self.warnings.append("超时时间过长，可能导致界面假死")
            
            # 验证匿名化策略
            valid_strategies = ['hierarchical', 'random', 'cryptographic']
            if processing_config.anonymization_strategy not in valid_strategies:
                self.errors.append(f"无效的匿名化策略: {processing_config.anonymization_strategy}")
            
            # 验证去重算法
            valid_algorithms = ['hash_based', 'content_based', 'hybrid']
            if processing_config.dedup_algorithm not in valid_algorithms:
                self.errors.append(f"无效的去重算法: {processing_config.dedup_algorithm}")
            
            # 验证去重阈值
            if processing_config.dedup_threshold < 0.0 or processing_config.dedup_threshold > 1.0:
                self.errors.append("去重阈值必须在0.0-1.0之间")
            
            # 验证载荷大小
            if processing_config.max_payload_size < 0:
                self.errors.append("最大载荷大小不能为负数")
            elif processing_config.max_payload_size > 65535:
                self.warnings.append("载荷大小超过65535字节，可能超出协议限制")
                
        except Exception as e:
            self.errors.append(f"处理配置验证失败: {e}")
    
    def _validate_performance_config(self, perf_config: PerformanceConfig) -> None:
        """验证性能配置"""
        try:
            # 验证工作线程数
            cpu_count = os.cpu_count() or 1
            if perf_config.max_workers < 1:
                self.errors.append("工作线程数必须大于0")
            elif perf_config.max_workers > cpu_count * 2:
                self.warnings.append(f"工作线程数 ({perf_config.max_workers}) 超过CPU核心数的2倍，可能降低性能")
            
            # 验证内存限制
            if perf_config.memory_limit_mb < 256:
                self.warnings.append("内存限制过低，可能影响大文件处理")
            elif perf_config.memory_limit_mb > 8192:
                self.warnings.append("内存限制过高，注意系统可用内存")
            
            # 验证缓存设置
            if perf_config.enable_caching:
                if perf_config.cache_size_mb < 64:
                    self.warnings.append("缓存大小过小，可能无法有效提升性能")
                elif perf_config.cache_size_mb > perf_config.memory_limit_mb // 2:
                    self.warnings.append("缓存大小占用过多内存")
            
            # 验证进度更新间隔
            if perf_config.progress_update_interval < 10:
                self.warnings.append("进度更新间隔过小，可能影响性能")
            elif perf_config.progress_update_interval > 10000:
                self.warnings.append("进度更新间隔过大，用户体验可能不佳")
                
        except Exception as e:
            self.errors.append(f"性能配置验证失败: {e}")
    
    def _validate_file_config(self, file_config: FileConfig) -> None:
        """验证文件配置"""
        try:
            # 验证目录路径
            if file_config.default_input_dir:
                input_path = Path(file_config.default_input_dir)
                if not input_path.exists():
                    self.warnings.append(f"默认输入目录不存在: {file_config.default_input_dir}")
                elif not input_path.is_dir():
                    self.errors.append(f"默认输入路径不是目录: {file_config.default_input_dir}")
            
            if file_config.default_output_dir:
                output_path = Path(file_config.default_output_dir)
                if not output_path.exists():
                    self.warnings.append(f"默认输出目录不存在: {file_config.default_output_dir}")
                elif not output_path.is_dir():
                    self.errors.append(f"默认输出路径不是目录: {file_config.default_output_dir}")
            
            # 验证文件大小限制
            if file_config.max_file_size_gb < 0.1:
                self.warnings.append("最大文件大小限制过小")
            elif file_config.max_file_size_gb > 100:
                self.warnings.append("最大文件大小限制过大，可能导致内存不足")
            
            if file_config.min_file_size_bytes < 1:
                self.errors.append("最小文件大小必须大于0")
            elif file_config.min_file_size_bytes > 1024:
                self.warnings.append("最小文件大小过大，可能过滤掉有效的小文件")
            
            # 验证支持的文件扩展名
            if not file_config.supported_extensions:
                self.errors.append("必须指定至少一种支持的文件扩展名")
            else:
                for ext in file_config.supported_extensions:
                    if not ext.startswith('.'):
                        self.warnings.append(f"文件扩展名应以'.'开头: {ext}")
            
            # 验证输出目录命名模式
            if '{timestamp}' not in file_config.output_dir_pattern:
                self.warnings.append("输出目录命名模式建议包含{timestamp}以避免冲突")
                
        except Exception as e:
            self.errors.append(f"文件配置验证失败: {e}")
    
    def _validate_logging_config(self, logging_config: LoggingConfig) -> None:
        """验证日志配置"""
        try:
            # 验证日志级别
            valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
            if logging_config.console_level not in valid_levels:
                self.errors.append(f"无效的控制台日志级别: {logging_config.console_level}")
            
            if logging_config.file_level not in valid_levels:
                self.errors.append(f"无效的文件日志级别: {logging_config.file_level}")
            
            # 验证日志文件路径
            if logging_config.log_file_path:
                log_path = Path(logging_config.log_file_path)
                if log_path.exists() and not log_path.is_file():
                    self.errors.append(f"日志文件路径不是文件: {logging_config.log_file_path}")
                
                # 检查目录是否可写
                log_dir = log_path.parent
                if not log_dir.exists():
                    try:
                        log_dir.mkdir(parents=True, exist_ok=True)
                    except PermissionError:
                        self.errors.append(f"无法创建日志目录: {log_dir}")
            
            # 验证日志文件大小
            if logging_config.max_log_size_mb < 1:
                self.warnings.append("日志文件大小限制过小，可能频繁轮转")
            elif logging_config.max_log_size_mb > 100:
                self.warnings.append("日志文件大小限制过大，可能占用过多磁盘空间")
            
            # 验证备份文件数量
            if logging_config.log_backup_count < 1:
                self.warnings.append("日志备份文件数量过少，可能丢失历史日志")
            elif logging_config.log_backup_count > 20:
                self.warnings.append("日志备份文件数量过多，可能占用过多磁盘空间")
                
        except Exception as e:
            self.errors.append(f"日志配置验证失败: {e}")
    
    def _validate_config_consistency(self, config: PktMaskConfig) -> None:
        """验证配置间的一致性"""
        try:
            # 检查性能配置与处理配置的一致性
            if config.performance.max_workers > 1 and config.processing.chunk_size < 10:
                self.warnings.append("多线程处理时建议增加块大小以提升效率")
            
            # 检查内存限制与缓存大小的一致性
            if config.performance.enable_caching:
                total_memory_usage = config.performance.cache_size_mb + 200  # 基础内存占用
                if total_memory_usage > config.performance.memory_limit_mb:
                    self.warnings.append("缓存大小加基础内存占用超过内存限制")
            
            # 检查文件大小限制与性能配置的一致性
            max_file_size_mb = config.file.max_file_size_gb * 1024
            if max_file_size_mb > config.performance.memory_limit_mb * 2:
                self.warnings.append("文件大小限制远超内存限制，可能需要调整处理策略")
            
            # 检查超时时间与文件大小的一致性
            if config.file.max_file_size_gb > 1.0 and config.processing.timeout_seconds < 600:
                self.warnings.append("处理大文件时建议增加超时时间")
            
            # 检查日志级别的一致性
            log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
            console_level_idx = log_levels.index(config.logging.console_level)
            file_level_idx = log_levels.index(config.logging.file_level)
            
            if console_level_idx < file_level_idx:
                self.warnings.append("控制台日志级别低于文件日志级别，可能产生过多控制台输出")
                
        except Exception as e:
            self.errors.append(f"配置一致性检查失败: {e}")
    
    def validate_config_field(self, field_name: str, value: Any, 
                             config_type: str = 'ui') -> Tuple[bool, Optional[str]]:
        """
        验证单个配置字段
        
        Args:
            field_name: 字段名
            value: 字段值
            config_type: 配置类型 ('ui', 'processing', 'performance', 'file', 'logging')
            
        Returns:
            Tuple[bool, Optional[str]]: (是否有效, 错误信息)
        """
        try:
            if config_type == 'ui':
                return self._validate_ui_field(field_name, value)
            elif config_type == 'processing':
                return self._validate_processing_field(field_name, value)
            elif config_type == 'performance':
                return self._validate_performance_field(field_name, value)
            elif config_type == 'file':
                return self._validate_file_field(field_name, value)
            elif config_type == 'logging':
                return self._validate_logging_field(field_name, value)
            else:
                return False, f"Unknown config type: {config_type}"
                
        except Exception as e:
            return False, f"Field validation error: {e}"
    
    def _validate_ui_field(self, field_name: str, value: Any) -> Tuple[bool, Optional[str]]:
        """验证UI配置字段"""
        if field_name == 'window_width':
            if not isinstance(value, int) or value < 800:
                return False, "窗口宽度必须是大于等于800的整数"
        elif field_name == 'window_height':
            if not isinstance(value, int) or value < 600:
                return False, "窗口高度必须是大于等于600的整数"
        elif field_name == 'theme':
            if value not in ['auto', 'light', 'dark']:
                return False, "主题必须是 'auto', 'light', 'dark' 之一"
        elif field_name == 'language':
            if value not in ['zh_CN', 'en_US']:
                return False, "语言必须是 'zh_CN', 'en_US' 之一"
        elif field_name == 'font_size':
            if not isinstance(value, int) or value < 8 or value > 24:
                return False, "字体大小必须是8-24之间的整数"
        
        return True, None
    
    def _validate_processing_field(self, field_name: str, value: Any) -> Tuple[bool, Optional[str]]:
        """验证处理配置字段"""
        if field_name == 'chunk_size':
            if not isinstance(value, int) or value < 1:
                return False, "块大小必须是大于0的整数"
        elif field_name == 'max_retry_attempts':
            if not isinstance(value, int) or value < 1:
                return False, "重试次数必须是大于0的整数"
        elif field_name == 'timeout_seconds':
            if not isinstance(value, int) or value < 60:
                return False, "超时时间必须是大于等于60的整数"
        elif field_name == 'dedup_threshold':
            if not isinstance(value, (int, float)) or value < 0.0 or value > 1.0:
                return False, "去重阈值必须是0.0-1.0之间的数值"
        
        return True, None
    
    def _validate_performance_field(self, field_name: str, value: Any) -> Tuple[bool, Optional[str]]:
        """验证性能配置字段"""
        if field_name == 'max_workers':
            if not isinstance(value, int) or value < 1:
                return False, "工作线程数必须是大于0的整数"
        elif field_name == 'memory_limit_mb':
            if not isinstance(value, int) or value < 256:
                return False, "内存限制必须是大于等于256的整数"
        elif field_name == 'cache_size_mb':
            if not isinstance(value, int) or value < 64:
                return False, "缓存大小必须是大于等于64的整数"
        
        return True, None
    
    def _validate_file_field(self, field_name: str, value: Any) -> Tuple[bool, Optional[str]]:
        """验证文件配置字段"""
        if field_name == 'max_file_size_gb':
            if not isinstance(value, (int, float)) or value < 0.1:
                return False, "最大文件大小必须是大于等于0.1的数值"
        elif field_name == 'min_file_size_bytes':
            if not isinstance(value, int) or value < 1:
                return False, "最小文件大小必须是大于0的整数"
        
        return True, None
    
    def _validate_logging_field(self, field_name: str, value: Any) -> Tuple[bool, Optional[str]]:
        """验证日志配置字段"""
        if field_name in ['console_level', 'file_level']:
            if value not in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
                return False, "日志级别必须是有效的级别之一"
        elif field_name == 'max_log_size_mb':
            if not isinstance(value, int) or value < 1:
                return False, "日志文件大小必须是大于0的整数"
        
        return True, None 