#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Trim模块核心组件

提供掩码规范和TLS协议处理功能。

核心组件:
- 掩码规范模型 (models/mask_spec.py)
- TLS协议处理模型 (models/tls_models.py)
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
    # 掩码规范
    'MaskSpec', 'MaskAfter', 'MaskRange', 'KeepAll',
    
    # TLS协议处理模型
    'TLSProcessingStrategy', 'MaskAction', 'TLSRecordInfo', 'MaskRule', 'TLSAnalysisResult',
    'create_mask_rule_for_tls_record', 'validate_tls_record_boundary', 'get_tls_processing_strategy'
]

# 版本信息
__version__ = '1.0.0'
__author__ = 'PktMask Trim Team'
__description__ = 'Mask specification and TLS processing framework for PCAP files' 