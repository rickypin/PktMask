"""
扫描式HTTP策略的数据结构模型

这个模块定义了扫描式HTTP策略所需的所有数据结构，包括扫描结果、
消息边界、Chunked编码分析等核心数据类。

作者: PktMask Team
创建时间: 2025-01-16
版本: 1.0.0
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import time


@dataclass
class MessageBoundary:
    """HTTP消息边界信息"""
    start: int                      # 消息起始位置
    header_end: int                 # 头部结束位置(指向\r\n\r\n的第一个\r)
    message_end: Optional[int]      # 消息结束位置(基于Content-Length计算)
    content_length: Optional[int]   # Content-Length值
    is_complete: bool = True        # 消息是否完整
    
    @property
    def header_size(self) -> int:
        """计算头部大小"""
        return self.header_end - self.start + 4  # +4为\r\n\r\n长度
    
    @property 
    def body_size(self) -> Optional[int]:
        """计算消息体大小"""
        if self.message_end is not None and self.content_length is not None:
            return self.content_length
        return None


@dataclass
class ChunkInfo:
    """Chunked编码块信息"""
    size_start: int      # chunk大小行起始位置
    size_end: int        # chunk大小行结束位置
    data_start: int      # chunk数据起始位置
    data_end: int        # chunk数据结束位置
    size_value: Optional[int] = None  # chunk大小值(可选)
    
    @property
    def data_size(self) -> int:
        """获取chunk数据大小"""
        return self.data_end - self.data_start
    
    @property
    def total_size(self) -> int:
        """获取chunk总大小(包括大小行和\r\n)"""
        return self.data_end - self.size_start + 2  # +2为trailing \r\n


@dataclass
class ChunkedAnalysis:
    """Chunked分析结果"""
    chunks: List[ChunkInfo]      # 检测到的chunk列表
    total_data_size: int         # 总数据大小
    is_complete: bool            # 是否检测到结束chunk(0\r\n)
    last_offset: int             # 最后分析位置
    parsing_errors: List[str]    # 解析错误列表
    
    @property
    def chunk_count(self) -> int:
        """获取chunk数量"""
        return len(self.chunks)
    
    @property
    def has_errors(self) -> bool:
        """是否有解析错误"""
        return len(self.parsing_errors) > 0


@dataclass
class ScanResult:
    """HTTP载荷扫描结果"""
    # 核心检测结果
    is_http: bool                    # 是否检测为HTTP
    header_boundary: int             # HTTP头部边界位置(-1表示未找到)
    confidence: float                # 检测置信度(0.0-1.0)
    scan_method: str                 # 扫描方法标识
    
    # 消息结构信息
    message_type: Optional[str] = None       # 'request' 或 'response'
    http_version: Optional[str] = None       # HTTP版本
    status_code: Optional[int] = None        # 状态码(响应)
    method: Optional[str] = None             # HTTP方法(请求)
    
    # 内容分析
    content_length: Optional[int] = None     # Content-Length值
    is_chunked: bool = False                 # 是否chunked编码
    is_compressed: bool = False              # 是否压缩内容
    content_type: Optional[str] = None       # Content-Type
    
    # 多消息检测
    message_boundaries: List[MessageBoundary] = None    # 消息边界列表
    chunked_analysis: Optional[ChunkedAnalysis] = None  # Chunked分析结果
    
    # 处理建议
    preserve_bytes: Optional[int] = None     # 建议保留字节数
    body_preserve_bytes: Optional[int] = None # 消息体保留字节数
    preserve_strategy: Optional[str] = None  # 保留策略类型
    
    # 元数据
    warnings: List[str] = None               # 警告信息
    debug_info: Dict[str, Any] = None        # 调试信息
    scan_duration_ms: Optional[float] = None # 扫描耗时(毫秒)
    
    def __post_init__(self):
        """初始化后处理"""
        if self.warnings is None:
            self.warnings = []
        if self.debug_info is None:
            self.debug_info = {}
        if self.message_boundaries is None:
            self.message_boundaries = []
    
    @classmethod
    def conservative_fallback(cls, reason: str) -> 'ScanResult':
        """创建保守回退的扫描结果"""
        return cls(
            is_http=False,
            header_boundary=-1,
            confidence=0.0,
            scan_method='conservative_fallback',
            preserve_strategy='keep_all',
            warnings=[f"保守回退: {reason}"]
        )
    
    @classmethod
    def create_success(cls, header_boundary: int, confidence: float,
                      scan_method: str, **kwargs) -> 'ScanResult':
        """创建成功的扫描结果"""
        result = cls(
            is_http=True,
            header_boundary=header_boundary,
            confidence=confidence,
            scan_method=scan_method,
            **kwargs
        )
        return result
    
    @property
    def is_successful(self) -> bool:
        """是否扫描成功"""
        return self.is_http and self.header_boundary > 0
    
    @property
    def is_multi_message(self) -> bool:
        """是否检测到多个HTTP消息"""
        return len(self.message_boundaries) > 1
    
    @property
    def total_preserve_bytes(self) -> int:
        """计算总的建议保留字节数"""
        if self.preserve_bytes is not None:
            return self.preserve_bytes
        
        if self.header_boundary > 0:
            preserve = self.header_boundary + 4  # +4为\r\n\r\n
            if self.body_preserve_bytes is not None:
                preserve += self.body_preserve_bytes
            return preserve
        
        return 0
    
    def add_warning(self, warning: str):
        """添加警告信息"""
        if warning not in self.warnings:
            self.warnings.append(warning)
    
    def add_debug_info(self, key: str, value: Any):
        """添加调试信息"""
        self.debug_info[key] = value


@dataclass 
class HttpPatterns:
    """HTTP特征模式集合"""
    
    # 基于真实HTTP流量分析的核心特征模式集合
    REQUEST_METHODS = [
        b'GET ', b'POST ', b'PUT ', b'DELETE ', b'HEAD ', 
        b'OPTIONS ', b'PATCH ', b'TRACE ', b'CONNECT '
    ]
    
    RESPONSE_VERSIONS = [
        b'HTTP/1.0 ', b'HTTP/1.1 '  # 移除HTTP/2.0支持
    ]
    
    HEADER_BOUNDARIES = [
        b'\r\n\r\n',  # 标准HTTP (95%案例)
        b'\n\n',      # Unix格式 (4%案例)
        b'\r\n\n',    # 混合格式 (1%案例)
    ]
    
    CONTENT_INDICATORS = [
        b'Content-Length:', b'content-length:',
        b'Content-Type:', b'content-type:',
        b'Transfer-Encoding:', b'transfer-encoding:'
    ]
    
    CHUNKED_INDICATORS = [
        b'Transfer-Encoding: chunked', b'transfer-encoding: chunked',
        b'Transfer-Encoding:chunked', b'transfer-encoding:chunked'
    ]
    
    ERROR_INDICATORS = [
        b'400 Bad Request', b'404 Not Found', b'500 Internal Server Error',
        b'401 Unauthorized', b'403 Forbidden', b'502 Bad Gateway',
        b'503 Service Unavailable', b'504 Gateway Timeout'
    ]
    
    @classmethod
    def get_all_request_patterns(cls) -> List[bytes]:
        """获取所有请求特征模式"""
        return cls.REQUEST_METHODS.copy()
    
    @classmethod
    def get_all_response_patterns(cls) -> List[bytes]:
        """获取所有响应特征模式"""
        return cls.RESPONSE_VERSIONS.copy()
    
    @classmethod
    def get_all_http_patterns(cls) -> List[bytes]:
        """获取所有HTTP特征模式"""
        return cls.REQUEST_METHODS + cls.RESPONSE_VERSIONS


# 策略常量
class ScanConstants:
    """扫描策略常量"""
    
    # 扫描窗口配置
    MAX_SCAN_WINDOW = 8192      # 最大扫描窗口 8KB
    MIN_HEADER_SIZE = 16        # 最小HTTP头部大小
    MAX_HEADER_SIZE = 8192      # 最大HTTP头部大小
    
    # 置信度阈值
    HIGH_CONFIDENCE = 0.9       # 高置信度阈值
    MEDIUM_CONFIDENCE = 0.7     # 中等置信度阈值
    LOW_CONFIDENCE = 0.5        # 低置信度阈值
    
    # 保留策略配置
    CHUNKED_SAMPLE_SIZE = 1024  # Chunked样本大小
    MAX_CHUNKS_TO_ANALYZE = 10  # 最大分析chunk数量
    CONSERVATIVE_PRESERVE_RATIO = 0.8  # 保守保留比例
    
    # 多消息处理配置
    MAX_MESSAGES_PER_PAYLOAD = 5    # 每个载荷最大消息数
    FIRST_MESSAGE_BODY_SAMPLE = 512 # 第一个消息体样本大小
    
    # 性能配置
    SCAN_TIMEOUT_MS = 100       # 扫描超时(毫秒)
    PATTERN_CACHE_SIZE = 1000   # 模式缓存大小 