"""
TShark增强掩码处理器

基于TShark深度协议解析的增强掩码处理器。
整合TShark分析、掩码规则生成、Scapy应用的三阶段流程。
支持TLS 20-24所有协议类型的智能分类处理。

特性:
- 三阶段处理流程：TShark → 规则生成 → Scapy应用
- TLS协议类型完整支持：20/21/22/23/24
- 跨TCP段TLS消息识别和处理
- 智能降级机制：确保系统健壮性
- 完整的错误处理和恢复机制
- 增强的错误分类、重试和诊断系统 (Phase 2, Day 13)

降级策略:
1. TShark不可用 → 降级到EnhancedTrimmer
2. 协议解析失败 → 降级到标准MaskStage
3. 其他错误 → 错误恢复+重试机制

作者: PktMask Team
创建时间: 2025-07-02
版本: 1.0.0 (Phase 1, Day 5)
更新时间: 2025-01-22 (Phase 2, Day 13 - 错误处理完善)
"""

import os
import tempfile
import shutil
from typing import Optional, Dict, Any, List, Union
from pathlib import Path
import logging
import time
import traceback
from dataclasses import dataclass, field
from enum import Enum

from .base_processor import BaseProcessor, ProcessorConfig, ProcessorResult
from ...infrastructure.logging import get_logger


class ErrorCategory(Enum):
    """错误分类枚举"""
    DEPENDENCY_ERROR = "dependency_error"         # 依赖工具错误（TShark等）
    CONFIGURATION_ERROR = "configuration_error"   # 配置错误
    INITIALIZATION_ERROR = "initialization_error" # 初始化错误
    PROCESSING_ERROR = "processing_error"         # 处理过程错误
    IO_ERROR = "io_error"                        # 文件I/O错误
    MEMORY_ERROR = "memory_error"                # 内存错误
    TIMEOUT_ERROR = "timeout_error"              # 超时错误
    PROTOCOL_ERROR = "protocol_error"            # 协议解析错误
    VALIDATION_ERROR = "validation_error"        # 输入验证错误
    UNKNOWN_ERROR = "unknown_error"              # 未知错误


class ErrorSeverity(Enum):
    """错误严重性枚举"""
    LOW = "low"           # 可忽略的错误
    MEDIUM = "medium"     # 中等严重性，可以降级处理
    HIGH = "high"         # 高严重性，需要立即处理
    CRITICAL = "critical" # 严重错误，停止处理


@dataclass
class ErrorContext:
    """错误上下文信息"""
    category: ErrorCategory
    severity: ErrorSeverity
    error_code: str
    message: str
    exception: Optional[Exception] = None
    stack_trace: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    file_context: Optional[str] = None
    stage_context: Optional[str] = None
    retry_count: int = 0
    recovery_attempted: bool = False
    mitigation_suggestions: List[str] = field(default_factory=list)


@dataclass
class RetryConfig:
    """重试配置"""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    exponential_backoff: bool = True
    retry_on_categories: List[ErrorCategory] = field(default_factory=lambda: [
        ErrorCategory.TIMEOUT_ERROR,
        ErrorCategory.PROCESSING_ERROR,
        ErrorCategory.IO_ERROR
    ])


class FallbackMode(Enum):
    """降级模式枚举"""
    NONE = "none"                    # 无降级，直接失败
    ENHANCED_TRIMMER = "enhanced_trimmer"   # 降级到EnhancedTrimmer
    MASK_STAGE = "mask_stage"        # 降级到标准MaskStage
    RETRY = "retry"                  # 错误恢复+重试


@dataclass
class FallbackConfig:
    """降级机制配置"""
    enable_fallback: bool = True
    max_retries: int = 2
    retry_delay_seconds: float = 1.0
    tshark_check_timeout: float = 5.0
    fallback_on_tshark_unavailable: bool = True
    fallback_on_parse_error: bool = True
    fallback_on_other_errors: bool = True
    preferred_fallback_order: List[FallbackMode] = field(
        default_factory=lambda: [
            FallbackMode.ENHANCED_TRIMMER,
            FallbackMode.MASK_STAGE
        ]
    )


@dataclass
class TSharkEnhancedConfig:
    """TShark增强掩码处理器配置"""
    # 核心功能配置
    enable_tls_processing: bool = True
    enable_cross_segment_detection: bool = True
    
    # TLS协议策略配置  
    tls_20_strategy: str = "keep_all"  # ChangeCipherSpec完全保留
    tls_21_strategy: str = "keep_all"  # Alert完全保留
    tls_22_strategy: str = "keep_all"  # Handshake完全保留
    tls_23_strategy: str = "mask_payload"  # ApplicationData智能掩码
    tls_24_strategy: str = "keep_all"  # Heartbeat完全保留
    tls_23_header_preserve_bytes: int = 5
    
    # 性能和资源配置
    chunk_size: int = 1000
    max_memory_mb: int = 512
    enable_parallel_processing: bool = False
    temp_dir: Optional[str] = None
    cleanup_temp_files: bool = True
    
    # 调试和诊断配置
    enable_detailed_logging: bool = False
    enable_performance_monitoring: bool = True
    enable_boundary_safety: bool = True
    
    # 降级机制配置
    fallback_config: FallbackConfig = field(default_factory=FallbackConfig)
    
    # Phase 2, Day 13: 增强错误处理配置
    retry_config: RetryConfig = field(default_factory=RetryConfig)
    enable_error_analytics: bool = True
    error_report_detail_level: str = "detailed"  # basic, detailed, verbose


class ErrorTracker:
    """错误跟踪和分析器"""
    
    def __init__(self):
        self.error_history: List[ErrorContext] = []
        self.error_patterns: Dict[str, int] = {}
        self.recovery_success_rate: Dict[ErrorCategory, float] = {}
        self.logger = get_logger('error_tracker')
    
    def record_error(self, error_context: ErrorContext):
        """记录错误"""
        self.error_history.append(error_context)
        
        # 更新错误模式统计
        pattern_key = f"{error_context.category.value}:{error_context.error_code}"
        self.error_patterns[pattern_key] = self.error_patterns.get(pattern_key, 0) + 1
        
        self.logger.debug(f"记录错误: {error_context.category.value} - {error_context.message}")
    
    def analyze_error_patterns(self) -> Dict[str, Any]:
        """分析错误模式"""
        if not self.error_history:
            return {"total_errors": 0, "patterns": {}}
            
        # 按类别统计
        category_stats = {}
        for error in self.error_history:
            category = error.category.value
            category_stats[category] = category_stats.get(category, 0) + 1
        
        # 按严重性统计
        severity_stats = {}
        for error in self.error_history:
            severity = error.severity.value
            severity_stats[severity] = severity_stats.get(severity, 0) + 1
        
        # 最近错误趋势
        recent_errors = [e for e in self.error_history if time.time() - e.timestamp < 3600]  # 最近1小时
        
        return {
            "total_errors": len(self.error_history),
            "recent_errors": len(recent_errors),
            "category_distribution": category_stats,
            "severity_distribution": severity_stats,
            "most_common_patterns": dict(sorted(self.error_patterns.items(), 
                                              key=lambda x: x[1], reverse=True)[:5]),
            "recovery_success_rate": self.recovery_success_rate.copy()
        }
    
    def suggest_mitigations(self, error_context: ErrorContext) -> List[str]:
        """基于错误历史和模式建议缓解措施"""
        suggestions = []
        
        # 基于错误类别的通用建议
        if error_context.category == ErrorCategory.DEPENDENCY_ERROR:
            suggestions.extend([
                "检查TShark是否正确安装",
                "验证TShark版本兼容性（推荐4.0+）",
                "检查系统PATH环境变量",
                "考虑使用降级处理模式"
            ])
        elif error_context.category == ErrorCategory.MEMORY_ERROR:
            suggestions.extend([
                "减少处理批次大小",
                "启用临时文件清理",
                "检查系统可用内存",
                "考虑分批处理大文件"
            ])
        elif error_context.category == ErrorCategory.TIMEOUT_ERROR:
            suggestions.extend([
                "增加超时时间设置",
                "检查网络连接",
                "优化处理参数",
                "使用更快的存储设备"
            ])
        elif error_context.category == ErrorCategory.PROTOCOL_ERROR:
            suggestions.extend([
                "验证输入文件格式",
                "检查文件是否损坏",
                "尝试使用不同的协议解析参数",
                "考虑预处理输入文件"
            ])
        
        # 基于错误模式的特定建议
        error_pattern = f"{error_context.category.value}:{error_context.error_code}"
        if self.error_patterns.get(error_pattern, 0) > 3:
            suggestions.append("此错误模式频繁出现，建议检查系统配置或输入数据质量")
        
        return suggestions


class TSharkEnhancedMaskProcessor(BaseProcessor):
    """
    TShark增强掩码处理器
    
    基于TShark深度协议解析的三阶段掩码处理器：
    1. TShark TLS分析：深度协议解析，识别跨TCP段TLS消息
    2. 掩码规则生成：将TLS分析结果转换为精确掩码规则
    3. Scapy掩码应用：根据规则进行字节级精确掩码操作
    
    支持完整的TLS协议类型处理：
    - TLS-20 (ChangeCipherSpec): 完全保留
    - TLS-21 (Alert): 完全保留
    - TLS-22 (Handshake): 完全保留  
    - TLS-23 (ApplicationData): 智能掩码（保留5字节头部）
    - TLS-24 (Heartbeat): 完全保留
    
    提供智能降级机制：
    - TShark不可用时降级到EnhancedTrimmer
    - 协议解析失败时降级到标准MaskStage
    - 其他错误时进行错误恢复和重试
    
    Phase 2, Day 13 增强：
    - 详细错误分类和上下文记录
    - 智能重试机制和指数退避
    - 错误模式分析和缓解建议
    - 完整的错误统计和报告系统
    """
    
    def __init__(self, config: ProcessorConfig):
        super().__init__(config)
        self._logger = get_logger('tshark_enhanced_mask_processor')
        
        # 增强配置（从AppConfig加载）
        self.enhanced_config = self._load_enhanced_config()
        
        # 核心组件（延迟初始化）
        self._tshark_analyzer: Optional[Any] = None
        self._rule_generator: Optional[Any] = None  
        self._scapy_applier: Optional[Any] = None
        
        # 降级处理器（延迟初始化）
        self._fallback_processors: Dict[FallbackMode, Any] = {}
        self._current_fallback_mode: Optional[FallbackMode] = None
        
        # Phase 2, Day 13: 增强错误处理系统
        self._error_tracker = ErrorTracker()
        self._retry_history: Dict[str, List[float]] = {}  # 文件路径 -> 重试时间戳列表
        
        # 处理统计
        self._processing_stats = {
            'total_files_processed': 0,
            'successful_files': 0,
            'fallback_usage': {},
            'tls_records_processed': 0,
            'mask_rules_generated': 0,
            'packets_modified': 0,
            'stage_performance': {},
            'error_recovery_count': 0,
            # Phase 2, Day 13: 增强统计
            'error_statistics': {},
            'retry_statistics': {},
            'recovery_success_rate': 0.0
        }
        
        # 临时工作目录
        self._temp_dir: Optional[Path] = None
    
    def _create_error_context(self, category: ErrorCategory, severity: ErrorSeverity,
                            error_code: str, message: str, exception: Optional[Exception] = None,
                            file_context: Optional[str] = None, stage_context: Optional[str] = None) -> ErrorContext:
        """创建详细的错误上下文"""
        context = ErrorContext(
            category=category,
            severity=severity,
            error_code=error_code,
            message=message,
            exception=exception,
            stack_trace=traceback.format_exc() if exception else None,
            file_context=file_context,
            stage_context=stage_context
        )
        
        # 添加缓解建议
        context.mitigation_suggestions = self._error_tracker.suggest_mitigations(context)
        
        return context
    
    def _handle_error_with_context(self, error_context: ErrorContext) -> bool:
        """带上下文的错误处理，返回是否可以继续处理"""
        # 记录错误
        self._error_tracker.record_error(error_context)
        
        # 根据错误严重性决定处理策略
        if error_context.severity == ErrorSeverity.CRITICAL:
            self._logger.critical(f"严重错误: {error_context.message}")
            return False
        elif error_context.severity == ErrorSeverity.HIGH:
            self._logger.error(f"高级错误: {error_context.message}")
            return self._attempt_error_recovery(error_context)
        elif error_context.severity == ErrorSeverity.MEDIUM:
            self._logger.warning(f"中级错误: {error_context.message}")
            return self._attempt_error_recovery(error_context)
        else:  # LOW
            self._logger.debug(f"低级错误: {error_context.message}")
            return True
    
    def _attempt_error_recovery(self, error_context: ErrorContext) -> bool:
        """尝试错误恢复"""
        error_context.recovery_attempted = True
        
        # 根据错误类别尝试不同的恢复策略
        if error_context.category == ErrorCategory.DEPENDENCY_ERROR:
            return self._recover_from_dependency_error(error_context)
        elif error_context.category == ErrorCategory.MEMORY_ERROR:
            return self._recover_from_memory_error(error_context)
        elif error_context.category == ErrorCategory.TIMEOUT_ERROR:
            return self._recover_from_timeout_error(error_context)
        elif error_context.category == ErrorCategory.PROTOCOL_ERROR:
            return self._recover_from_protocol_error(error_context)
        else:
            # 通用恢复策略：尝试降级处理
            return self._can_use_fallback()
    
    def _recover_from_dependency_error(self, error_context: ErrorContext) -> bool:
        """从依赖错误中恢复"""
        self._logger.info("尝试从依赖错误中恢复，检查降级选项...")
        return self._can_use_fallback()
    
    def _recover_from_memory_error(self, error_context: ErrorContext) -> bool:
        """从内存错误中恢复"""
        self._logger.info("尝试从内存错误中恢复，调整处理参数...")
        
        # 减少块大小
        if hasattr(self.enhanced_config, 'chunk_size') and self.enhanced_config.chunk_size > 100:
            self.enhanced_config.chunk_size = max(100, self.enhanced_config.chunk_size // 2)
            self._logger.info(f"调整块大小为: {self.enhanced_config.chunk_size}")
            return True
        
        return self._can_use_fallback()
    
    def _recover_from_timeout_error(self, error_context: ErrorContext) -> bool:
        """从超时错误中恢复"""
        self._logger.info("尝试从超时错误中恢复，调整超时参数...")
        
        # 增加超时时间
        if hasattr(self.enhanced_config.fallback_config, 'tshark_check_timeout'):
            self.enhanced_config.fallback_config.tshark_check_timeout *= 1.5
            self._logger.info(f"调整超时时间为: {self.enhanced_config.fallback_config.tshark_check_timeout}秒")
            return True
        
        return self._can_use_fallback()
    
    def _recover_from_protocol_error(self, error_context: ErrorContext) -> bool:
        """从协议错误中恢复"""
        self._logger.info("尝试从协议错误中恢复，使用降级处理...")
        return self._can_use_fallback()
    
    def _can_use_fallback(self) -> bool:
        """检查是否可以使用降级处理"""
        return (self.enhanced_config.fallback_config.enable_fallback and 
                len(self._fallback_processors) > 0)
    
    def _should_retry(self, error_context: ErrorContext, file_path: str) -> bool:
        """判断是否应该重试处理"""
        retry_config = self.enhanced_config.retry_config
        
        # 检查错误类别是否支持重试
        if error_context.category not in retry_config.retry_on_categories:
            return False
        
        # 检查重试次数限制
        if error_context.retry_count >= retry_config.max_retries:
            return False
        
        # 检查最近重试频率（防止重试风暴）
        current_time = time.time()
        if file_path in self._retry_history:
            recent_retries = [t for t in self._retry_history[file_path] 
                            if current_time - t < 300]  # 5分钟内的重试
            if len(recent_retries) >= retry_config.max_retries:
                return False
        
        return True
    
    def _calculate_retry_delay(self, retry_count: int) -> float:
        """计算重试延迟时间"""
        retry_config = self.enhanced_config.retry_config
        
        if retry_config.exponential_backoff:
            delay = retry_config.base_delay * (2 ** retry_count)
            return min(delay, retry_config.max_delay)
        else:
            return retry_config.base_delay
    
    def _execute_with_retry(self, func, *args, **kwargs):
        """带重试机制的函数执行"""
        retry_config = self.enhanced_config.retry_config
        last_error = None
        
        for attempt in range(retry_config.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_error = e
                
                if attempt < retry_config.max_retries:
                    delay = self._calculate_retry_delay(attempt)
                    self._logger.warning(f"执行失败，{delay}秒后重试 (尝试 {attempt + 1}/{retry_config.max_retries + 1}): {e}")
                    time.sleep(delay)
                else:
                    self._logger.error(f"重试失败，已达到最大重试次数: {e}")
        
        # 所有重试都失败，抛出最后一个错误
        raise last_error
    
    def _load_enhanced_config(self) -> TSharkEnhancedConfig:
        """从AppConfig加载TShark增强配置"""
        try:
            # 延迟导入避免循环依赖
            from ...config.settings import get_app_config
            
            app_config = get_app_config()
            enhanced_settings = app_config.tools.tshark_enhanced
            
            # 创建FallbackConfig
            fallback_config = FallbackConfig(
                enable_fallback=enhanced_settings.fallback_config.enable_fallback,
                max_retries=enhanced_settings.fallback_config.max_retries,
                retry_delay_seconds=enhanced_settings.fallback_config.retry_delay_seconds,
                tshark_check_timeout=enhanced_settings.fallback_config.tshark_check_timeout,
                fallback_on_tshark_unavailable=enhanced_settings.fallback_config.fallback_on_tshark_unavailable,
                fallback_on_parse_error=enhanced_settings.fallback_config.fallback_on_parse_error,
                fallback_on_other_errors=enhanced_settings.fallback_config.fallback_on_other_errors,
                preferred_fallback_order=[
                    FallbackMode(mode) for mode in enhanced_settings.fallback_config.preferred_fallback_order
                ]
            )
            
            # 创建TSharkEnhancedConfig
            enhanced_config = TSharkEnhancedConfig(
                # 核心功能配置
                enable_tls_processing=enhanced_settings.enable_tls_processing,
                enable_cross_segment_detection=enhanced_settings.enable_cross_segment_detection,
                enable_boundary_safety=enhanced_settings.enable_boundary_safety,
                
                # TLS协议类型处理配置
                tls_20_strategy=enhanced_settings.tls_20_strategy,
                tls_21_strategy=enhanced_settings.tls_21_strategy,
                tls_22_strategy=enhanced_settings.tls_22_strategy,
                tls_23_strategy=enhanced_settings.tls_23_strategy,
                tls_24_strategy=enhanced_settings.tls_24_strategy,
                tls_23_header_preserve_bytes=enhanced_settings.tls_23_header_preserve_bytes,
                
                # 性能配置
                temp_dir=enhanced_settings.temp_dir,
                cleanup_temp_files=enhanced_settings.cleanup_temp_files,
                enable_parallel_processing=enhanced_settings.enable_parallel_processing,
                chunk_size=enhanced_settings.chunk_size,
                
                # 调试配置
                enable_detailed_logging=enhanced_settings.enable_detailed_logging,
                enable_performance_monitoring=enhanced_settings.enable_performance_monitoring,
                
                # 降级机制配置
                fallback_config=fallback_config
            )
            
            self._logger.info("TShark增强配置已从AppConfig加载")
            self._logger.debug(f"TLS处理: {enhanced_config.enable_tls_processing}")
            self._logger.debug(f"跨段检测: {enhanced_config.enable_cross_segment_detection}")
            self._logger.debug(f"降级机制: {enhanced_config.fallback_config.enable_fallback}")
            
            return enhanced_config
            
        except Exception as e:
            self._logger.warning(f"从AppConfig加载配置失败，使用默认配置: {e}")
            return TSharkEnhancedConfig()  # 回退到默认配置
        
    def _initialize_impl(self):
        """初始化TShark增强掩码处理器（Phase 2, Day 13 增强版）"""
        try:
            self._logger.info("开始初始化TShark增强掩码处理器...")
            
            # 创建临时工作目录
            self._setup_temp_directory()
            
            # 检查TShark可用性
            if not self._check_tshark_availability():
                error_context = self._create_error_context(
                    ErrorCategory.DEPENDENCY_ERROR,
                    ErrorSeverity.HIGH,
                    "TSHARK_UNAVAILABLE",
                    "TShark工具不可用，无法执行深度协议解析"
                )
                
                if self.enhanced_config.fallback_config.fallback_on_tshark_unavailable:
                    self._logger.warning("TShark不可用，准备降级到备用处理器")
                    if self._handle_error_with_context(error_context):
                        return self._initialize_fallback_processors()
                else:
                    self._handle_error_with_context(error_context)
                    raise RuntimeError("TShark不可用且降级功能已禁用")
            
            # 初始化三阶段处理组件
            self._initialize_core_components()
            
            # 预初始化降级处理器（保险措施）
            if self.enhanced_config.fallback_config.enable_fallback:
                self._initialize_fallback_processors()
            
            self._logger.info("TShark增强掩码处理器初始化成功")
            self._logger.info(f"工作目录: {self._temp_dir}")
            self._logger.info(f"TLS处理配置: 20-24协议类型支持")
            self._logger.info(f"降级机制: {'启用' if self.enhanced_config.fallback_config.enable_fallback else '禁用'}")
            self._logger.info(f"错误分析: {'启用' if self.enhanced_config.enable_error_analytics else '禁用'}")
            
        except Exception as e:
            error_context = self._create_error_context(
                ErrorCategory.INITIALIZATION_ERROR,
                ErrorSeverity.HIGH,
                "INIT_FAILED",
                f"TShark增强掩码处理器初始化失败: {e}",
                exception=e
            )
            
            # 尝试降级初始化
            if self.enhanced_config.fallback_config.enable_fallback and self._handle_error_with_context(error_context):
                self._logger.info("尝试降级初始化...")
                return self._initialize_fallback_processors()
            else:
                raise
                
    def _setup_temp_directory(self):
        """设置临时工作目录"""
        if self.enhanced_config.temp_dir:
            self._temp_dir = Path(self.enhanced_config.temp_dir)
        else:
            self._temp_dir = Path(tempfile.mkdtemp(prefix="tshark_enhanced_mask_"))
        
        self._temp_dir.mkdir(parents=True, exist_ok=True)
        self._logger.debug(f"临时工作目录已创建: {self._temp_dir}")
        
    def _check_tshark_availability(self) -> bool:
        """检查TShark工具的可用性"""
        try:
            import subprocess
            import signal
            
            # 延迟导入TShark路径配置
            from ...config.defaults import get_tshark_paths
            
            tshark_paths = get_tshark_paths()
            timeout = self.enhanced_config.fallback_config.tshark_check_timeout
            
            for tshark_path in tshark_paths:
                try:
                    # 使用超时检查TShark版本
                    result = subprocess.run(
                        [tshark_path, '--version'],
                        capture_output=True,
                        text=True,
                        timeout=timeout
                    )
                    
                    if result.returncode == 0 and 'TShark' in result.stdout:
                        self._logger.info(f"TShark可用: {tshark_path}")
                        version_line = result.stdout.split('\n')[0]
                        self._logger.info(f"版本信息: {version_line}")
                        return True
                        
                except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
                    self._logger.debug(f"TShark路径检查失败 {tshark_path}: {e}")
                    continue
            
            self._logger.warning("所有TShark路径检查失败")
            return False
            
        except Exception as e:
            self._logger.error(f"TShark可用性检查异常: {e}")
            return False
            
    def _initialize_core_components(self):
        """初始化三阶段核心组件"""
        try:
            # Stage 1: TShark TLS分析器
            from .tshark_tls_analyzer import TSharkTLSAnalyzer
            self._tshark_analyzer = TSharkTLSAnalyzer(self._create_analyzer_config())
            
            # Stage 2: TLS掩码规则生成器  
            from .tls_mask_rule_generator import TLSMaskRuleGenerator
            self._rule_generator = TLSMaskRuleGenerator(self._create_generator_config())
            
            # Stage 3: Scapy掩码应用器
            from .scapy_mask_applier import ScapyMaskApplier  
            self._scapy_applier = ScapyMaskApplier(self._create_applier_config())
            
            self._logger.info("三阶段核心组件初始化成功")
            
        except ImportError as e:
            self._logger.error(f"核心组件导入失败: {e}")
            raise RuntimeError(f"核心组件不可用: {e}")
        except Exception as e:
            self._logger.error(f"核心组件初始化失败: {e}")
            raise
            
    def _initialize_fallback_processors(self) -> bool:
        """初始化降级处理器"""
        fallback_initialized = False
        
        for fallback_mode in self.enhanced_config.fallback_config.preferred_fallback_order:
            try:
                if fallback_mode == FallbackMode.ENHANCED_TRIMMER:
                    self._initialize_enhanced_trimmer_fallback()
                    fallback_initialized = True
                    self._logger.info("EnhancedTrimmer降级处理器初始化成功")
                    
                elif fallback_mode == FallbackMode.MASK_STAGE:
                    self._initialize_mask_stage_fallback()
                    fallback_initialized = True 
                    self._logger.info("MaskStage降级处理器初始化成功")
                    
            except Exception as e:
                self._logger.warning(f"降级处理器{fallback_mode.value}初始化失败: {e}")
                continue
        
        if not fallback_initialized:
            self._logger.error("所有降级处理器初始化失败")
            return False
            
        return True
        
    def _initialize_enhanced_trimmer_fallback(self):
        """初始化EnhancedTrimmer降级处理器"""
        try:
            from .enhanced_trimmer import EnhancedTrimmer
            
            fallback_config = ProcessorConfig(
                enabled=True,
                name="enhanced_trimmer_fallback",
                priority=1
            )
            
            trimmer = EnhancedTrimmer(fallback_config)
            if trimmer.initialize():
                self._fallback_processors[FallbackMode.ENHANCED_TRIMMER] = trimmer
            else:
                raise RuntimeError("EnhancedTrimmer初始化返回False")
                
        except Exception as e:
            self._logger.warning(f"EnhancedTrimmer降级处理器初始化失败: {e}")
            raise
            
    def _initialize_mask_stage_fallback(self):
        """初始化MaskStage降级处理器"""
        try:
            from ..pipeline.stages.mask_payload.stage import MaskStage
            
            # 创建基础模式的MaskStage配置
            mask_stage_config = {
                "mode": "basic",  # 使用基础模式
                "preserve_ratio": 0.3,
                "min_preserve_bytes": 100
            }
            
            mask_stage = MaskStage(mask_stage_config)
            mask_stage.initialize()
            
            self._fallback_processors[FallbackMode.MASK_STAGE] = mask_stage
            
        except Exception as e:
            self._logger.warning(f"MaskStage降级处理器初始化失败: {e}")
            raise
            
    def _create_analyzer_config(self) -> Dict[str, Any]:
        """创建TShark分析器配置"""
        return {
            'enable_tls_processing': self.enhanced_config.enable_tls_processing,
            'enable_cross_segment_detection': self.enhanced_config.enable_cross_segment_detection,
            'enable_detailed_logging': self.enhanced_config.enable_detailed_logging,
            'temp_dir': str(self._temp_dir),
            'chunk_size': self.enhanced_config.chunk_size
        }
        
    def _create_generator_config(self) -> Dict[str, Any]:
        """创建掩码规则生成器配置"""
        return {
            'tls_20_strategy': self.enhanced_config.tls_20_strategy,
            'tls_21_strategy': self.enhanced_config.tls_21_strategy,
            'tls_22_strategy': self.enhanced_config.tls_22_strategy,
            'tls_23_strategy': self.enhanced_config.tls_23_strategy,
            'tls_24_strategy': self.enhanced_config.tls_24_strategy,
            'tls_23_header_preserve_bytes': self.enhanced_config.tls_23_header_preserve_bytes,
            'enable_boundary_safety': self.enhanced_config.enable_boundary_safety,
            'enable_detailed_logging': self.enhanced_config.enable_detailed_logging
        }
        
    def _create_applier_config(self) -> Dict[str, Any]:
        """创建Scapy掩码应用器配置"""
        return {
            'enable_boundary_safety': self.enhanced_config.enable_boundary_safety,
            'enable_detailed_logging': self.enhanced_config.enable_detailed_logging,
            'enable_checksum_recalculation': True,
            'enable_error_recovery': True
        }
        
    def process_file(self, input_path: str, output_path: str) -> ProcessorResult:
        """处理文件的核心方法，包含完整的降级机制和重试机制（Phase 2, Day 13 增强版）"""
        start_time = time.time()
        
        try:
            # 输入验证
            self.validate_inputs(input_path, output_path)
            
            # 使用重试机制尝试主要处理流程
            if self._has_core_components():
                try:
                    result = self._execute_with_retry(
                        self._process_with_core_pipeline_safe, 
                        input_path, 
                        output_path
                    )
                    if result.success:
                        self._update_success_stats(result, time.time() - start_time)
                        return result
                except Exception as e:
                    error_context = self._create_error_context(
                        ErrorCategory.PROCESSING_ERROR,
                        ErrorSeverity.MEDIUM,
                        "CORE_PIPELINE_FAILED",
                        f"核心处理流程执行失败: {e}",
                        exception=e,
                        file_context=input_path,
                        stage_context="core_pipeline"
                    )
                    
                    if not self._handle_error_with_context(error_context):
                        return ProcessorResult(success=False, error=str(e))
                    
            # 主要流程失败，尝试降级处理
            if self.enhanced_config.fallback_config.enable_fallback:
                self._logger.warning("主要处理流程失败，开始降级处理")
                return self._process_with_fallback_enhanced(input_path, output_path, start_time)
            else:
                error_context = self._create_error_context(
                    ErrorCategory.PROCESSING_ERROR,
                    ErrorSeverity.HIGH,
                    "NO_FALLBACK_AVAILABLE",
                    "主要处理流程失败且降级功能已禁用",
                    file_context=input_path
                )
                self._handle_error_with_context(error_context)
                return ProcessorResult(
                    success=False,
                    error="主要处理流程失败且降级功能已禁用"
                )
                
        except Exception as e:
            error_context = self._create_error_context(
                ErrorCategory.PROCESSING_ERROR,
                ErrorSeverity.HIGH,
                "UNEXPECTED_ERROR",
                f"文件处理发生意外异常: {e}",
                exception=e,
                file_context=input_path
            )
            
            # 异常情况下的降级处理
            if self.enhanced_config.fallback_config.enable_fallback and self._handle_error_with_context(error_context):
                return self._process_with_fallback_enhanced(input_path, output_path, start_time, str(e))
            else:
                return ProcessorResult(success=False, error=str(e))
    
    def _process_with_core_pipeline_safe(self, input_path: str, output_path: str) -> ProcessorResult:
        """安全的核心处理流程，包含详细错误处理"""
        try:
            return self._process_with_core_pipeline(input_path, output_path)
        except MemoryError as e:
            error_context = self._create_error_context(
                ErrorCategory.MEMORY_ERROR,
                ErrorSeverity.HIGH,
                "MEMORY_EXHAUSTED",
                f"内存不足: {e}",
                exception=e,
                file_context=input_path,
                stage_context="core_pipeline"
            )
            self._handle_error_with_context(error_context)
            raise
        except TimeoutError as e:
            error_context = self._create_error_context(
                ErrorCategory.TIMEOUT_ERROR,
                ErrorSeverity.MEDIUM,
                "PROCESSING_TIMEOUT",
                f"处理超时: {e}",
                exception=e,
                file_context=input_path,
                stage_context="core_pipeline"
            )
            self._handle_error_with_context(error_context)
            raise
        except FileNotFoundError as e:
            error_context = self._create_error_context(
                ErrorCategory.IO_ERROR,
                ErrorSeverity.HIGH,
                "FILE_NOT_FOUND",
                f"文件不存在: {e}",
                exception=e,
                file_context=input_path,
                stage_context="core_pipeline"
            )
            self._handle_error_with_context(error_context)
            raise
        except Exception as e:
            error_context = self._create_error_context(
                ErrorCategory.PROCESSING_ERROR,
                ErrorSeverity.MEDIUM,
                "PIPELINE_ERROR",
                f"处理流程错误: {e}",
                exception=e,
                file_context=input_path,
                stage_context="core_pipeline"
            )
            self._handle_error_with_context(error_context)
            raise
                
    def _has_core_components(self) -> bool:
        """检查核心组件是否可用"""
        return (self._tshark_analyzer is not None and 
                self._rule_generator is not None and 
                self._scapy_applier is not None)
                
    def _process_with_core_pipeline(self, input_path: str, output_path: str) -> ProcessorResult:
        """使用三阶段核心流程处理文件"""
        try:
            self._logger.info(f"开始三阶段处理: {input_path}")
            
            # Stage 1: TShark TLS分析
            stage1_start = time.time()
            tls_records = self._tshark_analyzer.analyze_file(input_path)
            stage1_duration = time.time() - stage1_start
            
            if not tls_records:
                self._logger.warning("TShark分析未发现TLS记录")
                
            self._logger.info(f"Stage 1完成: 发现{len(tls_records)}个TLS记录，耗时{stage1_duration:.2f}秒")
            
            # Stage 2: 生成掩码规则
            stage2_start = time.time()
            mask_rules = self._rule_generator.generate_rules(tls_records)
            stage2_duration = time.time() - stage2_start
            
            self._logger.info(f"Stage 2完成: 生成{len(mask_rules)}条掩码规则，耗时{stage2_duration:.2f}秒")
            
            # Stage 3: Scapy应用掩码
            stage3_start = time.time()
            apply_result = self._scapy_applier.apply_masks(input_path, output_path, mask_rules)
            stage3_duration = time.time() - stage3_start
            
            self._logger.info(f"Stage 3完成: 处理完成，耗时{stage3_duration:.2f}秒")
            
            # 汇总结果
            total_duration = stage1_duration + stage2_duration + stage3_duration
            
            return ProcessorResult(
                success=True,
                stats={
                    'tls_records_found': len(tls_records),
                    'mask_rules_generated': len(mask_rules),
                    'packets_processed': apply_result.get('packets_processed', 0),
                    'packets_modified': apply_result.get('packets_modified', 0),
                    'processing_mode': 'tshark_enhanced',
                    'stage_performance': {
                        'stage1_tshark_analysis': stage1_duration,
                        'stage2_rule_generation': stage2_duration,  
                        'stage3_scapy_application': stage3_duration,
                        'total_duration': total_duration
                    }
                }
            )
            
        except Exception as e:
            self._logger.error(f"三阶段处理流程失败: {e}")
            raise
            
    def _process_with_fallback(self, input_path: str, output_path: str, start_time: float, 
                              error_context: Optional[str] = None) -> ProcessorResult:
        """使用降级机制处理文件"""
        
        # 确定降级策略
        fallback_mode = self._determine_fallback_mode(error_context)
        
        # 尝试降级处理
        for mode in self.enhanced_config.fallback_config.preferred_fallback_order:
            if mode in self._fallback_processors:
                try:
                    self._logger.info(f"使用降级处理器: {mode.value}")
                    result = self._execute_fallback_processor(mode, input_path, output_path)
                    
                    if result.success:
                        duration = time.time() - start_time
                        self._update_fallback_stats(mode, result, duration)
                        
                        # 在结果中标记降级模式
                        if result.stats:
                            result.stats['processing_mode'] = f'fallback_{mode.value}'
                            result.stats['fallback_reason'] = error_context or 'primary_pipeline_failed'
                        
                        return result
                        
                except Exception as e:
                    self._logger.warning(f"降级处理器{mode.value}执行失败: {e}")
                    continue
                    
        # 所有降级处理器都失败
        return ProcessorResult(
            success=False,
            error=f"主要处理流程和所有降级处理器都失败。原始错误: {error_context}"
        )
        
    def _determine_fallback_mode(self, error_context: Optional[str]) -> FallbackMode:
        """根据错误上下文确定降级模式"""
        if not error_context:
            return FallbackMode.ENHANCED_TRIMMER
            
        error_lower = error_context.lower()
        
        if 'tshark' in error_lower or '不可用' in error_lower:
            return FallbackMode.ENHANCED_TRIMMER
        elif '协议解析' in error_lower or 'protocol' in error_lower:
            return FallbackMode.MASK_STAGE  
        else:
            return FallbackMode.ENHANCED_TRIMMER
            
    def _execute_fallback_processor(self, mode: FallbackMode, input_path: str, output_path: str) -> ProcessorResult:
        """执行指定的降级处理器"""
        processor = self._fallback_processors[mode]
        
        if mode == FallbackMode.ENHANCED_TRIMMER:
            # EnhancedTrimmer使用BaseProcessor接口
            return processor.process_file(input_path, output_path)
            
        elif mode == FallbackMode.MASK_STAGE:
            # MaskStage使用StageBase接口，需要适配
            result = processor.process_file(input_path, output_path)
            
            # 将StageStats转换为ProcessorResult
            if hasattr(result, 'packets_processed'):
                return ProcessorResult(
                    success=True,
                    stats={
                        'packets_processed': getattr(result, 'packets_processed', 0),
                        'packets_modified': getattr(result, 'packets_modified', 0),
                        'duration_ms': getattr(result, 'duration_ms', 0)
                    }
                )
            else:
                return ProcessorResult(success=False, error="MaskStage处理结果格式异常")
                
        else:
            raise ValueError(f"不支持的降级模式: {mode}")
            
    def _update_success_stats(self, result: ProcessorResult, duration: float):
        """更新成功处理统计"""
        self._processing_stats['total_files_processed'] += 1
        self._processing_stats['successful_files'] += 1
        
        if result.stats:
            self._processing_stats['tls_records_processed'] += result.stats.get('tls_records_found', 0)
            self._processing_stats['mask_rules_generated'] += result.stats.get('mask_rules_generated', 0)
            self._processing_stats['packets_modified'] += result.stats.get('packets_modified', 0)
            
    def _update_fallback_stats(self, mode: FallbackMode, result: ProcessorResult, duration: float):
        """更新降级处理统计"""
        self._processing_stats['total_files_processed'] += 1
        
        mode_key = mode.value
        if mode_key not in self._processing_stats['fallback_usage']:
            self._processing_stats['fallback_usage'][mode_key] = 0
        self._processing_stats['fallback_usage'][mode_key] += 1
        
        if result.success:
            self._processing_stats['successful_files'] += 1
            
    def get_display_name(self) -> str:
        """获取用户友好的显示名称"""
        return "TShark增强掩码处理器"
        
    def get_description(self) -> str:
        """获取处理器描述"""
        return ("基于TShark深度协议解析的增强掩码处理器，"
                "支持TLS 20-24协议类型的智能分类处理，"
                "包含完整的降级机制确保系统健壮性")
                
    def get_enhanced_stats(self) -> Dict[str, Any]:
        """获取增强统计信息"""
        stats = self.get_stats().copy()
        stats.update(self._processing_stats)
        
        # 添加降级使用率统计
        total_files = self._processing_stats['total_files_processed']
        if total_files > 0:
            fallback_total = sum(self._processing_stats['fallback_usage'].values())
            stats['primary_success_rate'] = (total_files - fallback_total) / total_files
            stats['fallback_usage_rate'] = fallback_total / total_files
        else:
            stats['primary_success_rate'] = 0.0
            stats['fallback_usage_rate'] = 0.0
            
        return stats
        
    def cleanup(self):
        """清理资源"""
        try:
            # 清理临时目录
            if (self._temp_dir and 
                self._temp_dir.exists() and 
                self.enhanced_config.cleanup_temp_files):
                shutil.rmtree(self._temp_dir, ignore_errors=True)
                self._logger.debug(f"已清理临时目录: {self._temp_dir}")
                self._temp_dir = None  # 重要：清理后设置为None
                
            # 清理降级处理器
            for processor in self._fallback_processors.values():
                if hasattr(processor, 'cleanup'):
                    processor.cleanup()
                    
        except Exception as e:
            self._logger.warning(f"资源清理失败: {e}")
            
    def _process_with_fallback_enhanced(self, input_path: str, output_path: str, start_time: float, 
                                      error_context: Optional[str] = None) -> ProcessorResult:
        """使用增强降级机制处理文件（Phase 2, Day 13 增强版）"""
        
        # 记录降级尝试
        if input_path not in self._retry_history:
            self._retry_history[input_path] = []
        self._retry_history[input_path].append(time.time())
        
        # 确定降级策略
        fallback_mode = self._determine_fallback_mode(error_context)
        
        # 尝试降级处理
        for mode in self.enhanced_config.fallback_config.preferred_fallback_order:
            if mode in self._fallback_processors:
                try:
                    self._logger.info(f"使用降级处理器: {mode.value}")
                    
                    # 使用重试机制执行降级处理器
                    result = self._execute_with_retry(
                        self._execute_fallback_processor_safe,
                        mode, input_path, output_path
                    )
                    
                    if result.success:
                        duration = time.time() - start_time
                        self._update_fallback_stats(mode, result, duration)
                        
                        # 在结果中标记降级模式
                        if result.stats:
                            result.stats['processing_mode'] = f'fallback_{mode.value}'
                            result.stats['fallback_reason'] = error_context or 'primary_pipeline_failed'
                            result.stats['fallback_duration'] = duration
                        
                        # 记录成功恢复
                        self._processing_stats['error_recovery_count'] += 1
                        return result
                        
                except Exception as e:
                    fallback_error_context = self._create_error_context(
                        ErrorCategory.PROCESSING_ERROR,
                        ErrorSeverity.MEDIUM,
                        f"FALLBACK_{mode.value.upper()}_FAILED",
                        f"降级处理器{mode.value}执行失败: {e}",
                        exception=e,
                        file_context=input_path,
                        stage_context=f"fallback_{mode.value}"
                    )
                    self._handle_error_with_context(fallback_error_context)
                    continue
                    
        # 所有降级处理器都失败
        final_error_context = self._create_error_context(
            ErrorCategory.PROCESSING_ERROR,
            ErrorSeverity.CRITICAL,
            "ALL_FALLBACKS_FAILED",
            f"主要处理流程和所有降级处理器都失败。原始错误: {error_context}",
            file_context=input_path
        )
        self._handle_error_with_context(final_error_context)
        
        return ProcessorResult(
            success=False,
            error=f"主要处理流程和所有降级处理器都失败。原始错误: {error_context}"
        )
    
    def _execute_fallback_processor_safe(self, mode: FallbackMode, input_path: str, output_path: str) -> ProcessorResult:
        """安全的降级处理器执行，包含详细错误处理"""
        try:
            return self._execute_fallback_processor(mode, input_path, output_path)
        except Exception as e:
            error_context = self._create_error_context(
                ErrorCategory.PROCESSING_ERROR,
                ErrorSeverity.MEDIUM,
                f"FALLBACK_{mode.value.upper()}_ERROR",
                f"降级处理器{mode.value}执行异常: {e}",
                exception=e,
                file_context=input_path,
                stage_context=f"fallback_{mode.value}"
            )
            self._handle_error_with_context(error_context)
            raise
    
    def get_error_report(self, detail_level: str = None) -> Dict[str, Any]:
        """获取详细的错误报告（Phase 2, Day 13 新增）"""
        if detail_level is None:
            detail_level = self.enhanced_config.error_report_detail_level
        
        error_analysis = self._error_tracker.analyze_error_patterns()
        
        report = {
            "processor_info": {
                "name": self.get_display_name(),
                "version": "1.0.0 (Phase 2, Day 13)",
                "error_analytics_enabled": self.enhanced_config.enable_error_analytics
            },
            "error_summary": error_analysis,
            "processing_stats": self._processing_stats.copy(),
            "configuration": {
                "retry_config": {
                    "max_retries": self.enhanced_config.retry_config.max_retries,
                    "base_delay": self.enhanced_config.retry_config.base_delay,
                    "exponential_backoff": self.enhanced_config.retry_config.exponential_backoff
                },
                "fallback_enabled": self.enhanced_config.fallback_config.enable_fallback,
                "fallback_order": [mode.value for mode in self.enhanced_config.fallback_config.preferred_fallback_order]
            }
        }
        
        if detail_level in ["detailed", "verbose"]:
            # 添加详细错误历史
            report["error_history"] = []
            for error in self._error_tracker.error_history[-10:]:  # 最近10个错误
                error_detail = {
                    "timestamp": error.timestamp,
                    "category": error.category.value,
                    "severity": error.severity.value,
                    "error_code": error.error_code,
                    "message": error.message,
                    "file_context": error.file_context,
                    "stage_context": error.stage_context,
                    "retry_count": error.retry_count,
                    "recovery_attempted": error.recovery_attempted,
                    "mitigation_suggestions": error.mitigation_suggestions[:3]  # 前3个建议
                }
                
                if detail_level == "verbose" and error.exception:
                    error_detail["exception_type"] = type(error.exception).__name__
                    if error.stack_trace:
                        error_detail["stack_trace"] = error.stack_trace.split('\n')[:5]  # 前5行堆栈
                
                report["error_history"].append(error_detail)
            
            # 添加重试历史统计
            report["retry_history"] = {}
            current_time = time.time()
            for file_path, retry_times in self._retry_history.items():
                recent_retries = [t for t in retry_times if current_time - t < 3600]
                if recent_retries:
                    report["retry_history"][file_path] = {
                        "total_retries": len(retry_times),
                        "recent_retries": len(recent_retries),
                        "last_retry": max(retry_times) if retry_times else None
                    }
        
        if detail_level == "verbose":
            # 添加系统诊断信息
            report["system_diagnostics"] = {
                "temp_dir": str(self._temp_dir) if self._temp_dir else None,
                "temp_dir_exists": self._temp_dir.exists() if self._temp_dir else False,
                "fallback_processors_available": list(self._fallback_processors.keys()),
                "core_components_available": self._has_core_components(),
                "current_fallback_mode": self._current_fallback_mode.value if self._current_fallback_mode else None
            }
        
        return report
    
    def generate_mitigation_recommendations(self) -> List[str]:
        """基于错误历史生成缓解建议（Phase 2, Day 13 新增）"""
        error_analysis = self._error_tracker.analyze_error_patterns()
        recommendations = []
        
        # 基于错误模式的建议
        if error_analysis.get("total_errors", 0) > 0:
            category_stats = error_analysis.get("category_distribution", {})
            
            # 依赖错误建议
            if category_stats.get("dependency_error", 0) > 0:
                recommendations.extend([
                    "验证TShark安装和版本兼容性（推荐4.0+）",
                    "检查系统PATH环境变量包含TShark路径",
                    "考虑启用降级处理模式以提高系统健壮性"
                ])
            
            # 内存错误建议
            if category_stats.get("memory_error", 0) > 0:
                recommendations.extend([
                    f"减少处理批次大小（当前: {self.enhanced_config.chunk_size}）",
                    "启用临时文件自动清理功能",
                    "考虑分批处理大文件以减少内存使用"
                ])
            
            # 超时错误建议
            if category_stats.get("timeout_error", 0) > 0:
                recommendations.extend([
                    f"增加超时时间设置（当前: {self.enhanced_config.fallback_config.tshark_check_timeout}s）",
                    "优化处理参数以提升性能",
                    "检查系统负载和可用资源"
                ])
            
            # 协议错误建议
            if category_stats.get("protocol_error", 0) > 0:
                recommendations.extend([
                    "验证输入文件格式和完整性",
                    "检查文件是否为有效的PCAP/PCAPNG格式",
                    "考虑使用文件预处理工具修复损坏的数据包"
                ])
        
        # 基于统计的建议
        total_files = self._processing_stats.get('total_files_processed', 0)
        if total_files > 0:
            fallback_usage = sum(self._processing_stats.get('fallback_usage', {}).values())
            fallback_rate = fallback_usage / total_files
            
            if fallback_rate > 0.3:  # 降级使用率超过30%
                recommendations.append(
                    f"降级使用率较高（{fallback_rate:.1%}），建议检查主要处理流程的配置和依赖"
                )
            
            success_rate = self._processing_stats.get('successful_files', 0) / total_files
            if success_rate < 0.8:  # 成功率低于80%
                recommendations.append(
                    f"处理成功率偏低（{success_rate:.1%}），建议检查输入数据质量和系统配置"
                )
        
        # 去重和限制数量
        recommendations = list(dict.fromkeys(recommendations))  # 去重
        return recommendations[:10]  # 最多返回10个建议

    def __del__(self):
        """析构函数，确保资源清理"""
        self.cleanup() 