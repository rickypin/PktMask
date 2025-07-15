"""
Trim module data models

Contains core data structures such as masking specifications and TLS protocol processing.
"""

# Basic masking specifications (actual existing files)
from .mask_spec import MaskSpec, MaskAfter, MaskRange, KeepAll

# TLS protocol processing models (actual existing files)
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