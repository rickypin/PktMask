"""
HTTP载荷扫描算法模块

提供高效、可靠的HTTP协议分析算法，支持：
- 头部边界检测算法
- 内容长度解析算法
- Chunked编码处理算法
- 多消息边界识别算法

作者: PktMask Team
版本: 1.0.0
创建时间: 2025-01-16
"""

from .boundary_detection import (
    BoundaryDetector,
    BoundaryDetectionResult,
    HeaderBoundaryPattern,
    detect_header_boundary,
    detect_multiple_message_boundaries
)

from .content_length_parser import (
    ContentLengthParser,
    ContentLengthResult,
    ChunkedEncoder,
    ChunkedAnalysisResult,
    parse_content_length,
    analyze_chunked_structure
)

__all__ = [
    # 边界检测算法
    'BoundaryDetector',
    'BoundaryDetectionResult',
    'HeaderBoundaryPattern',
    'detect_header_boundary',
    'detect_multiple_message_boundaries',
    
    # 内容长度解析算法
    'ContentLengthParser',
    'ContentLengthResult',
    'ChunkedEncoder',
    'ChunkedAnalysisResult',
    'parse_content_length',
    'analyze_chunked_structure',
]

# 模块版本信息
__version__ = "1.0.0"
__author__ = "PktMask Team"
__description__ = "HTTP载荷扫描算法模块" 