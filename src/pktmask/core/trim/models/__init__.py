"""
Trim模块数据模型

包含掩码规范和TLS协议处理等核心数据结构。
"""

# 基础掩码规范（实际存在的文件）
from .mask_spec import MaskSpec, MaskAfter, MaskRange, KeepAll

# TLS协议处理模型（实际存在的文件）
from .tls_models import (
    TLSProcessingStrategy,
    MaskAction,
    TLSRecordInfo,
    MaskRule,
    TLSAnalysisResult,
    create_mask_rule_for_tls_record,
    validate_tls_record_boundary,
    get_tls_processing_strategy
)

__all__ = [
    # 掩码规范
    'MaskSpec', 'MaskAfter', 'MaskRange', 'KeepAll',
    
    # TLS协议处理模型
    'TLSProcessingStrategy', 'MaskAction', 'TLSRecordInfo', 'MaskRule', 'TLSAnalysisResult',
    'create_mask_rule_for_tls_record', 'validate_tls_record_boundary', 'get_tls_processing_strategy'
] 