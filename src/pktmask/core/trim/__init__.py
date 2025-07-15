#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Trim module core components

Provides masking specifications and TLS protocol processing functionality.

Core components:
- Masking specification models (models/mask_spec.py)
- TLS protocol processing models (models/tls_models.py)
"""

# 导入实际存在的数据结构模型
from .models.mask_spec import (
    MaskSpec, MaskAfter, MaskRange, KeepAll
)

# 导入TLS协议处理模型
from .models.tls_models import (
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
    # Masking specifications
    'MaskSpec', 'MaskAfter', 'MaskRange', 'KeepAll',

    # TLS protocol processing models
    'TLSProcessingStrategy', 'MaskAction', 'TLSRecordInfo', 'MaskRule', 'TLSAnalysisResult',
    'create_mask_rule_for_tls_record', 'validate_tls_record_boundary', 'get_tls_processing_strategy'
]

# 版本信息
__version__ = '1.0.0'
__author__ = 'PktMask Trim Team'
__description__ = 'Mask specification and TLS processing framework for PCAP files' 