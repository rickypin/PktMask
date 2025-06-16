"""
HTTP内容长度解析和Chunked编码处理算法

提供精确、高效的HTTP消息体长度计算功能，支持：
- Content-Length头部解析和验证
- Transfer-Encoding: chunked 完整处理
- 消息体大小估算算法
- 压缩内容处理支持

核心功能：
1. 精确的Content-Length解析：支持大小写不敏感、空白处理、数值验证
2. 完整的Chunked编码解析：支持分块解析、尺寸计算、完整性检测
3. 智能消息体估算：基于多种线索进行消息体大小估算
4. 性能优化：使用高效算法避免全文件扫描

作者: PktMask Team
版本: 1.0.0
创建时间: 2025-01-16
"""

from typing import Optional, List, Tuple, Dict, Any
import re
import logging
from dataclasses import dataclass
from enum import Enum


class ContentEncodingType(Enum):
    """内容编码类型"""
    IDENTITY = "identity"      # 无编码
    GZIP = "gzip"             # GZIP压缩
    DEFLATE = "deflate"       # Deflate压缩
    COMPRESS = "compress"     # Compress压缩
    BR = "br"                 # Brotli压缩
    UNKNOWN = "unknown"       # 未知编码


class TransferEncodingType(Enum):
    """传输编码类型"""
    IDENTITY = "identity"     # 标准传输
    CHUNKED = "chunked"       # 分块传输
    GZIP = "gzip"            # GZIP传输编码
    DEFLATE = "deflate"      # Deflate传输编码
    UNKNOWN = "unknown"      # 未知编码


@dataclass
class ContentLengthResult:
    """Content-Length解析结果"""
    found: bool                           # 是否找到Content-Length
    length: Optional[int] = None          # 内容长度
    header_line: Optional[str] = None     # 原始头部行
    confidence: float = 0.0               # 解析置信度 (0.0-1.0)
    parsing_method: str = "none"          # 解析方法
    warnings: List[str] = None            # 警告信息
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
    
    @classmethod
    def not_found(cls, method: str = "not_found") -> 'ContentLengthResult':
        """创建未找到Content-Length的结果"""
        return cls(found=False, parsing_method=method)
    
    @classmethod
    def found_value(cls, length: int, header_line: str = None, 
                   method: str = "found", confidence: float = 1.0) -> 'ContentLengthResult':
        """创建找到Content-Length的结果"""
        return cls(
            found=True,
            length=length,
            header_line=header_line,
            confidence=confidence,
            parsing_method=method
        )


@dataclass
class ChunkInfo:
    """单个Chunk信息"""
    size_line_start: int      # 大小行起始位置
    size_line_end: int        # 大小行结束位置
    data_start: int           # 数据起始位置
    data_end: int             # 数据结束位置
    size: int                 # Chunk大小
    size_hex: str             # 十六进制大小字符串
    has_extensions: bool = False      # 是否有chunk扩展
    extensions: str = ""              # chunk扩展字符串
    
    @property
    def total_chunk_length(self) -> int:
        """整个chunk的总长度（包括大小行和数据）"""
        return self.data_end - self.size_line_start + 2  # +2 for trailing \r\n
    
    @property
    def is_last_chunk(self) -> bool:
        """是否是最后一个chunk（大小为0）"""
        return self.size == 0


@dataclass
class ChunkedAnalysisResult:
    """Chunked编码分析结果"""
    is_chunked: bool                      # 是否检测到chunked编码
    chunks: List[ChunkInfo] = None        # Chunk信息列表
    total_data_size: int = 0              # 总数据大小
    is_complete: bool = False             # 是否检测到结束chunk(0\r\n)
    last_chunk_position: int = -1         # 最后一个chunk位置
    parsing_errors: int = 0               # 解析错误数量
    confidence: float = 0.0               # 分析置信度
    analysis_method: str = "none"         # 分析方法
    warnings: List[str] = None            # 警告信息
    
    def __post_init__(self):
        if self.chunks is None:
            self.chunks = []
        if self.warnings is None:
            self.warnings = []
    
    @property
    def estimated_total_length(self) -> Optional[int]:
        """估算的总长度（如果完整）"""
        if not self.is_complete:
            return None
        return self.last_chunk_position + 5  # +5 for "0\r\n\r\n"
    
    @classmethod
    def not_chunked(cls, method: str = "not_chunked") -> 'ChunkedAnalysisResult':
        """创建非chunked的结果"""
        return cls(is_chunked=False, analysis_method=method)
    
    @classmethod
    def chunked_detected(cls, chunks: List[ChunkInfo], total_size: int, 
                        is_complete: bool, method: str = "chunked_detected") -> 'ChunkedAnalysisResult':
        """创建检测到chunked的结果"""
        return cls(
            is_chunked=True,
            chunks=chunks,
            total_data_size=total_size,
            is_complete=is_complete,
            analysis_method=method,
            confidence=0.9 if is_complete else 0.7
        )


class ContentLengthParser:
    """
    精确的Content-Length解析器
    
    支持各种格式的Content-Length头部解析，提供高准确度的内容长度提取。
    """
    
    # Content-Length匹配模式（大小写不敏感）
    CONTENT_LENGTH_PATTERNS = [
        # 标准格式
        re.compile(rb'^Content-Length:\s*(\d+)\s*$', re.IGNORECASE | re.MULTILINE),
        # 松散格式（允许额外空白）
        re.compile(rb'Content-Length\s*:\s*(\d+)', re.IGNORECASE),
        # HTTP/1.0格式（可能没有空格）
        re.compile(rb'Content-Length:(\d+)', re.IGNORECASE),
    ]
    
    # Transfer-Encoding匹配模式
    TRANSFER_ENCODING_PATTERNS = [
        re.compile(rb'Transfer-Encoding:\s*chunked', re.IGNORECASE),
        re.compile(rb'Transfer-Encoding:\s*([^,\r\n]+(?:,\s*[^,\r\n]+)*)', re.IGNORECASE),
    ]
    
    # Content-Encoding匹配模式
    CONTENT_ENCODING_PATTERNS = [
        re.compile(rb'Content-Encoding:\s*([^,\r\n]+(?:,\s*[^,\r\n]+)*)', re.IGNORECASE),
    ]
    
    def __init__(self, enable_logging: bool = False):
        """
        初始化Content-Length解析器
        
        Args:
            enable_logging: 是否启用详细日志
        """
        self.enable_logging = enable_logging
        self.logger = logging.getLogger(__name__)
    
    def parse_content_length(self, header_content: bytes) -> ContentLengthResult:
        """
        解析Content-Length头部
        
        Args:
            header_content: HTTP头部内容
            
        Returns:
            Content-Length解析结果
        """
        if not header_content:
            return ContentLengthResult.not_found("empty_header")
        
        if self.enable_logging:
            self.logger.debug(f"开始Content-Length解析: 头部大小{len(header_content)}字节")
        
        # 按优先级尝试不同的匹配模式
        for i, pattern in enumerate(self.CONTENT_LENGTH_PATTERNS):
            match = pattern.search(header_content)
            if match:
                try:
                    length = int(match.group(1))
                    header_line = match.group(0).decode('ascii', errors='ignore')
                    
                    # 验证长度合理性
                    confidence = self._calculate_content_length_confidence(length, header_line)
                    
                    if self.enable_logging:
                        self.logger.debug(f"Content-Length解析成功: {length}, "
                                         f"模式{i}, 置信度{confidence:.2f}")
                    
                    return ContentLengthResult.found_value(
                        length=length,
                        header_line=header_line,
                        method=f"pattern_match_{i}",
                        confidence=confidence
                    )
                    
                except (ValueError, OverflowError) as e:
                    if self.enable_logging:
                        self.logger.warning(f"Content-Length解析错误: {e}")
                    continue
        
        return ContentLengthResult.not_found("no_content_length_found")
    
    def detect_transfer_encoding(self, header_content: bytes) -> Tuple[bool, List[TransferEncodingType]]:
        """
        检测Transfer-Encoding
        
        Args:
            header_content: HTTP头部内容
            
        Returns:
            (是否找到, 编码类型列表)
        """
        encodings = []
        
        for pattern in self.TRANSFER_ENCODING_PATTERNS:
            match = pattern.search(header_content)
            if match:
                # 检查是否有捕获组
                if pattern.groups > 0:
                    encoding_str = match.group(1).decode('ascii', errors='ignore').lower()
                    
                    # 解析多个编码（逗号分隔）
                    for enc in encoding_str.split(','):
                        enc = enc.strip()
                        if enc == 'chunked':
                            encodings.append(TransferEncodingType.CHUNKED)
                        elif enc == 'gzip':
                            encodings.append(TransferEncodingType.GZIP)
                        elif enc == 'deflate':
                            encodings.append(TransferEncodingType.DEFLATE)
                        elif enc == 'identity':
                            encodings.append(TransferEncodingType.IDENTITY)
                        else:
                            encodings.append(TransferEncodingType.UNKNOWN)
                else:
                    # 没有捕获组，说明是简单的chunked匹配
                    encodings.append(TransferEncodingType.CHUNKED)
                
                break  # 找到第一个匹配即可
        
        return len(encodings) > 0, encodings
    
    def detect_content_encoding(self, header_content: bytes) -> Tuple[bool, List[ContentEncodingType]]:
        """
        检测Content-Encoding
        
        Args:
            header_content: HTTP头部内容
            
        Returns:
            (是否找到, 编码类型列表)
        """
        encodings = []
        
        for pattern in self.CONTENT_ENCODING_PATTERNS:
            match = pattern.search(header_content)
            if match:
                encoding_str = match.group(1).decode('ascii', errors='ignore').lower()
                
                # 解析多个编码（逗号分隔）
                for enc in encoding_str.split(','):
                    enc = enc.strip()
                    if enc == 'gzip':
                        encodings.append(ContentEncodingType.GZIP)
                    elif enc == 'deflate':
                        encodings.append(ContentEncodingType.DEFLATE)
                    elif enc == 'compress':
                        encodings.append(ContentEncodingType.COMPRESS)
                    elif enc == 'br':
                        encodings.append(ContentEncodingType.BR)
                    elif enc == 'identity':
                        encodings.append(ContentEncodingType.IDENTITY)
                    else:
                        encodings.append(ContentEncodingType.UNKNOWN)
        
        return len(encodings) > 0, encodings
    
    def _calculate_content_length_confidence(self, length: int, header_line: str) -> float:
        """计算Content-Length置信度"""
        confidence = 0.8  # 基础分数
        
        # 长度合理性检查
        if 0 <= length <= 1024 * 1024 * 1024:  # 0-1GB合理范围
            confidence += 0.1
        elif length > 1024 * 1024 * 1024 * 10:  # >10GB可疑
            confidence -= 0.3
        
        # 格式规范性检查
        if 'Content-Length: ' in header_line:  # 标准格式
            confidence += 0.1
        
        return min(1.0, max(0.0, confidence))


class ChunkedEncoder:
    """
    Chunked编码分析器
    
    提供完整的Transfer-Encoding: chunked 处理功能。
    """
    
    # Chunk大小行的正则表达式
    CHUNK_SIZE_PATTERN = re.compile(rb'^([0-9A-Fa-f]+)(?:;[^\r\n]*)?(\r?\n)', re.MULTILINE)
    
    def __init__(self, max_chunks: int = 50, enable_logging: bool = False):
        """
        初始化Chunked编码分析器
        
        Args:
            max_chunks: 最大分析chunk数量
            enable_logging: 是否启用详细日志
        """
        self.max_chunks = max_chunks
        self.enable_logging = enable_logging
        self.logger = logging.getLogger(__name__)
    
    def analyze_chunked_structure(self, payload: bytes, chunk_data_start: int) -> ChunkedAnalysisResult:
        """
        分析Chunked数据结构
        
        Args:
            payload: 完整载荷数据
            chunk_data_start: Chunk数据起始位置（HTTP头部之后）
            
        Returns:
            Chunked分析结果
        """
        if chunk_data_start >= len(payload):
            return ChunkedAnalysisResult.not_chunked("chunk_start_beyond_payload")
        
        if self.enable_logging:
            self.logger.debug(f"开始Chunked结构分析: 从位置{chunk_data_start}开始, "
                             f"载荷总长{len(payload)}字节")
        
        chunks = []
        offset = chunk_data_start
        total_data_size = 0
        parsing_errors = 0
        is_complete = False
        max_errors = 5  # 最多允许5个解析错误
        
        while offset < len(payload) and len(chunks) < self.max_chunks and parsing_errors < max_errors:
            try:
                # 1. 查找chunk大小行
                chunk_info = self._parse_single_chunk(payload, offset)
                if chunk_info is None:
                    # 解析失败，尝试跳过一些字节继续
                    parsing_errors += 1
                    offset += 1
                    continue
                
                chunks.append(chunk_info)
                total_data_size += chunk_info.size
                
                if self.enable_logging:
                    self.logger.debug(f"解析chunk {len(chunks)}: 大小{chunk_info.size}, "
                                     f"位置{chunk_info.size_line_start}-{chunk_info.data_end}")
                
                # 2. 检查是否是最后一个chunk
                if chunk_info.is_last_chunk:
                    is_complete = True
                    if self.enable_logging:
                        self.logger.debug("检测到结束chunk (大小为0)")
                    break
                
                # 3. 移动到下一个chunk
                offset = chunk_info.data_end + 2  # +2 for trailing \r\n
                
            except Exception as e:
                parsing_errors += 1
                if self.enable_logging:
                    self.logger.warning(f"Chunk解析异常: {e}")
                offset += 1
                continue
        
        # 计算置信度
        confidence = self._calculate_chunked_confidence(chunks, parsing_errors, is_complete)
        
        result = ChunkedAnalysisResult.chunked_detected(
            chunks=chunks,
            total_size=total_data_size,
            is_complete=is_complete,
            method="chunked_structure_analysis"
        )
        result.parsing_errors = parsing_errors
        result.confidence = confidence
        result.last_chunk_position = offset
        
        if parsing_errors > 0:
            result.warnings.append(f"Chunked解析过程中出现{parsing_errors}个错误")
        
        return result
    
    def _parse_single_chunk(self, payload: bytes, offset: int) -> Optional[ChunkInfo]:
        """
        解析单个chunk
        
        Args:
            payload: 载荷数据
            offset: 当前偏移量
            
        Returns:
            ChunkInfo或None（解析失败）
        """
        if offset >= len(payload):
            return None
        
        # 查找chunk大小行的结束位置
        size_line_end = payload.find(b'\r\n', offset)
        if size_line_end == -1:
            # 尝试查找单独的\n
            size_line_end = payload.find(b'\n', offset)
            if size_line_end == -1:
                return None
        
        # 提取大小行
        size_line = payload[offset:size_line_end]
        
        try:
            # 解析chunk大小（十六进制）
            size_line_str = size_line.decode('ascii', errors='ignore').strip()
            
            # 检查是否有chunk扩展
            if ';' in size_line_str:
                size_hex, extensions = size_line_str.split(';', 1)
                has_extensions = True
            else:
                size_hex = size_line_str
                extensions = ""
                has_extensions = False
            
            chunk_size = int(size_hex, 16)
            
            # 计算数据位置
            data_start = size_line_end + 2  # +2 for \r\n
            data_end = data_start + chunk_size
            
            # 验证数据位置合理性
            if data_end > len(payload):
                return None
            
            # 验证chunk结尾的\r\n（如果不是最后一个chunk）
            if chunk_size > 0 and data_end + 2 > len(payload):
                # 非结束chunk但没有足够的数据包含尾部\r\n
                return None
            
            return ChunkInfo(
                size_line_start=offset,
                size_line_end=size_line_end,
                data_start=data_start,
                data_end=data_end,
                size=chunk_size,
                size_hex=size_hex,
                has_extensions=has_extensions,
                extensions=extensions
            )
            
        except (ValueError, UnicodeDecodeError):
            return None
    
    def _calculate_chunked_confidence(self, chunks: List[ChunkInfo], 
                                    parsing_errors: int, is_complete: bool) -> float:
        """计算Chunked分析置信度"""
        if not chunks:
            return 0.0
        
        confidence = 0.7  # 基础分数
        
        # 完整性加分
        if is_complete:
            confidence += 0.2
        
        # chunk数量合理性
        if 1 <= len(chunks) <= 20:
            confidence += 0.1
        
        # 解析错误扣分
        if parsing_errors > 0:
            confidence -= min(0.3, parsing_errors * 0.05)
        
        # chunk大小合理性检查
        reasonable_chunks = sum(1 for chunk in chunks if 0 <= chunk.size <= 1024*1024)
        if reasonable_chunks == len(chunks):
            confidence += 0.1
        
        return min(1.0, max(0.0, confidence))


# 便捷函数
def parse_content_length(header_content: bytes) -> ContentLengthResult:
    """
    便捷函数：解析Content-Length
    
    Args:
        header_content: HTTP头部内容
        
    Returns:
        Content-Length解析结果
    """
    parser = ContentLengthParser()
    return parser.parse_content_length(header_content)


def analyze_chunked_structure(payload: bytes, chunk_data_start: int) -> ChunkedAnalysisResult:
    """
    便捷函数：分析Chunked结构
    
    Args:
        payload: 载荷数据
        chunk_data_start: Chunk数据起始位置
        
    Returns:
        Chunked分析结果
    """
    analyzer = ChunkedEncoder()
    return analyzer.analyze_chunked_structure(payload, chunk_data_start) 