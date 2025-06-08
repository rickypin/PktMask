#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
配置数据模型定义
使用Pydantic提供类型安全的配置模型
"""

from typing import Optional, List, Dict, Any
from pathlib import Path
from pydantic import BaseModel, Field, validator


class UIConfig(BaseModel):
    """用户界面配置"""
    # 窗口设置
    window_width: int = Field(default=1200, ge=800, le=2560, description="窗口宽度")
    window_height: int = Field(default=800, ge=600, le=1440, description="窗口高度")
    window_min_width: int = Field(default=800, ge=600, description="最小窗口宽度")
    window_min_height: int = Field(default=600, ge=400, description="最小窗口高度")
    
    # 主题和外观
    theme: str = Field(default="auto", description="主题模式")
    language: str = Field(default="zh_CN", description="界面语言")
    font_size: int = Field(default=12, ge=8, le=24, description="字体大小")
    
    # 默认选项
    default_dedup: bool = Field(default=True, description="默认启用去重")
    default_mask_ip: bool = Field(default=True, description="默认启用IP匿名化")
    default_trim: bool = Field(default=False, description="默认启用载荷裁切")
    
    # 界面行为
    remember_last_dir: bool = Field(default=True, description="记住上次使用的目录")
    auto_open_output: bool = Field(default=False, description="处理完成后自动打开输出目录")
    show_progress_details: bool = Field(default=True, description="显示详细进度信息")
    
    @validator('theme')
    def validate_theme(cls, v):
        valid_themes = ['auto', 'light', 'dark']
        if v not in valid_themes:
            raise ValueError(f"Theme must be one of {valid_themes}")
        return v
    
    @validator('language')
    def validate_language(cls, v):
        valid_languages = ['zh_CN', 'en_US']
        if v not in valid_languages:
            raise ValueError(f"Language must be one of {valid_languages}")
        return v


class ProcessingConfig(BaseModel):
    """处理过程配置"""
    # 算法参数
    chunk_size: int = Field(default=10, ge=1, le=1000, description="数据包处理块大小")
    max_retry_attempts: int = Field(default=3, ge=1, le=10, description="最大重试次数")
    timeout_seconds: int = Field(default=300, ge=60, le=3600, description="处理超时时间(秒)")
    
    # IP匿名化设置
    anonymization_strategy: str = Field(default="hierarchical", description="匿名化策略")
    preserve_subnet_structure: bool = Field(default=True, description="保持子网结构")
    consistent_mapping: bool = Field(default=True, description="保持一致性映射")
    
    # 去重设置
    dedup_algorithm: str = Field(default="hash_based", description="去重算法")
    dedup_threshold: float = Field(default=0.95, ge=0.0, le=1.0, description="去重相似度阈值")
    
    # 裁切设置
    preserve_tls_handshake: bool = Field(default=True, description="保留TLS握手数据")
    trim_application_data: bool = Field(default=True, description="裁切应用数据")
    max_payload_size: int = Field(default=1024, ge=0, le=65535, description="最大载荷大小")
    
    @validator('anonymization_strategy')
    def validate_anonymization_strategy(cls, v):
        valid_strategies = ['hierarchical', 'random', 'cryptographic']
        if v not in valid_strategies:
            raise ValueError(f"Anonymization strategy must be one of {valid_strategies}")
        return v
    
    @validator('dedup_algorithm')
    def validate_dedup_algorithm(cls, v):
        valid_algorithms = ['hash_based', 'content_based', 'hybrid']
        if v not in valid_algorithms:
            raise ValueError(f"Deduplication algorithm must be one of {valid_algorithms}")
        return v


class PerformanceConfig(BaseModel):
    """性能配置"""
    # 并发设置
    max_workers: int = Field(default=4, ge=1, le=16, description="最大工作线程数")
    use_multiprocessing: bool = Field(default=False, description="使用多进程处理")
    memory_limit_mb: int = Field(default=1024, ge=256, le=8192, description="内存限制(MB)")
    
    # 缓存设置
    enable_caching: bool = Field(default=True, description="启用缓存")
    cache_size_mb: int = Field(default=256, ge=64, le=2048, description="缓存大小(MB)")
    cache_cleanup_interval: int = Field(default=300, ge=60, le=3600, description="缓存清理间隔(秒)")
    
    # 进度报告
    progress_update_interval: int = Field(default=100, ge=10, le=10000, description="进度更新间隔(包数)")
    enable_detailed_stats: bool = Field(default=True, description="启用详细统计")


class FileConfig(BaseModel):
    """文件处理配置"""
    # 目录设置
    default_input_dir: Optional[str] = Field(default=None, description="默认输入目录")
    default_output_dir: Optional[str] = Field(default=None, description="默认输出目录")
    output_dir_pattern: str = Field(default="pktmask_output_{timestamp}", description="输出目录命名模式")
    
    # 文件大小限制
    max_file_size_gb: float = Field(default=2.0, ge=0.1, le=100.0, description="最大文件大小(GB)")
    min_file_size_bytes: int = Field(default=24, ge=1, le=1024, description="最小文件大小(字节)")
    
    # 支持的文件类型
    supported_extensions: List[str] = Field(default=['.pcap', '.pcapng'], description="支持的文件扩展名")
    
    # 输出设置
    preserve_timestamps: bool = Field(default=True, description="保留文件时间戳")
    create_backup: bool = Field(default=False, description="创建原文件备份")
    cleanup_temp_files: bool = Field(default=True, description="自动清理临时文件")
    
    # 报告设置
    generate_html_report: bool = Field(default=True, description="生成HTML报告")
    generate_json_report: bool = Field(default=True, description="生成JSON报告")
    include_detailed_stats: bool = Field(default=True, description="包含详细统计信息")


class LoggingConfig(BaseModel):
    """日志配置"""
    # 日志级别
    console_level: str = Field(default="INFO", description="控制台日志级别")
    file_level: str = Field(default="DEBUG", description="文件日志级别")
    
    # 日志文件设置
    log_file_path: Optional[str] = Field(default=None, description="日志文件路径")
    max_log_size_mb: int = Field(default=10, ge=1, le=100, description="最大日志文件大小(MB)")
    log_backup_count: int = Field(default=5, ge=1, le=20, description="日志备份文件数量")
    
    # 日志格式
    include_timestamp: bool = Field(default=True, description="包含时间戳")
    include_module_name: bool = Field(default=True, description="包含模块名")
    include_line_number: bool = Field(default=False, description="包含行号")
    
    @validator('console_level', 'file_level')
    def validate_log_level(cls, v):
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}")
        return v


class PktMaskConfig(BaseModel):
    """PktMask主配置模型"""
    # 版本信息
    config_version: str = Field(default="1.0", description="配置版本")
    
    # 子配置
    ui: UIConfig = Field(default_factory=UIConfig, description="用户界面配置")
    processing: ProcessingConfig = Field(default_factory=ProcessingConfig, description="处理配置")
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig, description="性能配置")
    file: FileConfig = Field(default_factory=FileConfig, description="文件配置")
    logging: LoggingConfig = Field(default_factory=LoggingConfig, description="日志配置")
    
    # 元数据
    created_at: Optional[str] = Field(default=None, description="配置创建时间")
    updated_at: Optional[str] = Field(default=None, description="配置更新时间")
    
    class Config:
        # 允许额外字段以支持扩展
        extra = "allow"
        # 字段的JSON编码使用别名
        validate_by_name = True
        # 验证赋值
        validate_assignment = True
    
    def dict_for_serialization(self) -> Dict[str, Any]:
        """返回用于序列化的字典，排除敏感信息"""
        data = self.dict()
        
        # 可以在这里过滤敏感信息
        # 例如: data.pop('sensitive_field', None)
        
        return data
    
    def update_timestamp(self):
        """更新时间戳"""
        from ..utils.time import current_timestamp
        timestamp = current_timestamp()
        self.updated_at = timestamp
        if not self.created_at:
            self.created_at = timestamp 