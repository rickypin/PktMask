"""
HTTP头部边界检测算法

提供高效、精确的HTTP头部边界识别功能，支持：
- 多种行结束符模式 (\r\n\r\n, \n\n, \r\n\n)
- 容错机制和异常处理
- 多消息边界检测
- 性能优化的扫描算法

设计原则：
1. 优先级匹配：\r\n\r\n > \n\n > \r\n\n
2. 容错处理：格式异常时提供合理的回退策略
3. 性能优先：使用高效的字节匹配而非正则表达式
4. 多消息支持：检测载荷中的多个HTTP消息

作者: PktMask Team
版本: 1.0.0
创建时间: 2025-01-16
"""

from typing import List, Optional, Tuple, NamedTuple
import logging
from dataclasses import dataclass
from enum import Enum


class HeaderBoundaryPattern(Enum):
    """HTTP头部边界模式枚举"""
    CRLF_CRLF = b'\r\n\r\n'    # 标准HTTP (95%案例)
    LF_LF = b'\n\n'            # Unix格式 (4%案例)
    CRLF_LF = b'\r\n\n'        # 混合格式 (1%案例)


@dataclass
class BoundaryDetectionResult:
    """边界检测结果"""
    found: bool                    # 是否找到边界
    position: int                  # 边界位置 (指向第一个\r或\n)
    pattern: Optional[HeaderBoundaryPattern] = None  # 匹配的模式
    pattern_length: int = 0        # 模式长度
    confidence: float = 0.0        # 检测置信度 (0.0-1.0)
    scan_method: str = "none"      # 扫描方法
    warnings: List[str] = None     # 警告信息
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
    
    @property
    def header_end_position(self) -> int:
        """头部结束位置 (指向边界模式的最后一个字节)"""
        if not self.found:
            return -1
        return self.position + self.pattern_length - 1
    
    @property
    def body_start_position(self) -> int:
        """消息体起始位置"""
        if not self.found:
            return -1
        return self.position + self.pattern_length
    
    @classmethod
    def not_found(cls, method: str = "not_found", warnings: List[str] = None) -> 'BoundaryDetectionResult':
        """创建未找到边界的结果"""
        return cls(
            found=False,
            position=-1,
            scan_method=method,
            warnings=warnings or []
        )
    
    @classmethod
    def found_at(cls, position: int, pattern: HeaderBoundaryPattern, 
                 method: str = "found", confidence: float = 1.0) -> 'BoundaryDetectionResult':
        """创建找到边界的结果"""
        return cls(
            found=True,
            position=position,
            pattern=pattern,
            pattern_length=len(pattern.value),
            confidence=confidence,
            scan_method=method
        )


@dataclass
class MessageBoundaryInfo:
    """单个HTTP消息边界信息"""
    start_position: int           # 消息起始位置
    header_boundary: BoundaryDetectionResult  # 头部边界检测结果
    estimated_length: Optional[int] = None    # 预估消息长度
    message_type: str = "unknown"             # 消息类型 (request/response)
    confidence: float = 0.0                   # 检测置信度


class BoundaryDetector:
    """
    高效的HTTP头部边界检测器
    
    使用优化的算法检测HTTP头部边界，支持多种格式和容错机制。
    """
    
    # 边界模式优先级（从高到低）
    BOUNDARY_PATTERNS = [
        HeaderBoundaryPattern.CRLF_CRLF,  # 最常见，标准HTTP
        HeaderBoundaryPattern.CRLF_LF,    # 混合格式，优先于LF_LF
        HeaderBoundaryPattern.LF_LF,      # Unix格式
    ]
    
    # HTTP消息起始模式
    HTTP_REQUEST_PATTERNS = [
        b'GET ', b'POST ', b'PUT ', b'DELETE ', b'HEAD ',
        b'OPTIONS ', b'PATCH ', b'TRACE ', b'CONNECT '
    ]
    
    HTTP_RESPONSE_PATTERNS = [
        b'HTTP/1.0 ', b'HTTP/1.1 '
    ]
    
    def __init__(self, max_scan_distance: int = 8192, enable_logging: bool = False):
        """
        初始化边界检测器
        
        Args:
            max_scan_distance: 最大扫描距离，避免扫描过大的载荷
            enable_logging: 是否启用详细日志
        """
        self.max_scan_distance = max_scan_distance
        self.enable_logging = enable_logging
        self.logger = logging.getLogger(__name__)
        
    def detect_header_boundary(self, payload: bytes, start_offset: int = 0) -> BoundaryDetectionResult:
        """
        检测HTTP头部边界
        
        Args:
            payload: 载荷数据
            start_offset: 扫描起始偏移量
            
        Returns:
            边界检测结果
        """
        if not payload or start_offset >= len(payload):
            return BoundaryDetectionResult.not_found("empty_payload")
        
        # 限制扫描范围
        scan_end = min(len(payload), start_offset + self.max_scan_distance)
        scan_data = payload[start_offset:scan_end]
        
        if self.enable_logging:
            self.logger.debug(f"开始边界检测: 扫描{len(scan_data)}字节 "
                             f"(偏移{start_offset}-{scan_end})")
        
        # 按优先级查找边界模式
        for pattern in self.BOUNDARY_PATTERNS:
            position = scan_data.find(pattern.value)
            if position != -1:
                absolute_position = start_offset + position
                confidence = self._calculate_boundary_confidence(payload, absolute_position, pattern)
                
                if self.enable_logging:
                    self.logger.debug(f"找到边界模式 {pattern.name} 在位置 {absolute_position}, "
                                     f"置信度 {confidence:.2f}")
                
                return BoundaryDetectionResult.found_at(
                    position=absolute_position,
                    pattern=pattern,
                    method="pattern_match",
                    confidence=confidence
                )
        
        # 未找到标准边界，尝试启发式检测
        heuristic_result = self._heuristic_boundary_detection(scan_data, start_offset)
        if heuristic_result.found:
            return heuristic_result
        
        # 完全未找到
        return BoundaryDetectionResult.not_found(
            method="no_boundary_found",
            warnings=["未找到HTTP头部边界模式"]
        )
    
    def detect_multiple_message_boundaries(self, payload: bytes) -> List[MessageBoundaryInfo]:
        """
        检测载荷中的多个HTTP消息边界
        
        Args:
            payload: 载荷数据
            
        Returns:
            消息边界信息列表
        """
        if not payload:
            return []
        
        messages = []
        search_offset = 0
        max_messages = 10  # 防止无限循环
        
        if self.enable_logging:
            self.logger.debug(f"开始多消息检测: 载荷大小{len(payload)}字节")
        
        while search_offset < len(payload) and len(messages) < max_messages:
            # 1. 查找HTTP消息起始位置
            message_start = self._find_http_message_start(payload, search_offset)
            if message_start == -1:
                break  # 没有更多HTTP消息
            
            # 2. 检测此消息的头部边界
            header_boundary = self.detect_header_boundary(payload, message_start)
            if not header_boundary.found:
                # 这个消息没有完整的头部，停止检测
                if self.enable_logging:
                    self.logger.debug(f"消息{len(messages)+1}在位置{message_start}缺少完整头部")
                break
            
            # 3. 确定消息类型
            message_type = self._identify_message_type(payload, message_start)
            
            # 4. 估算消息长度
            estimated_length = self._estimate_message_length(payload, header_boundary)
            
            # 5. 创建消息边界信息
            message_info = MessageBoundaryInfo(
                start_position=message_start,
                header_boundary=header_boundary,
                estimated_length=estimated_length,
                message_type=message_type,
                confidence=header_boundary.confidence
            )
            
            messages.append(message_info)
            
            if self.enable_logging:
                self.logger.debug(f"检测到消息{len(messages)}: {message_type} "
                                 f"起始{message_start}, 头部边界{header_boundary.position}")
            
            # 6. 移动搜索位置到下一个可能的消息位置
            if estimated_length and estimated_length > 0:
                search_offset = message_start + estimated_length
            else:
                # 无法确定消息长度，移动到头部结束位置
                search_offset = header_boundary.body_start_position
        
        return messages
    
    def _calculate_boundary_confidence(self, payload: bytes, position: int, 
                                     pattern: HeaderBoundaryPattern) -> float:
        """
        计算边界检测置信度
        
        Args:
            payload: 载荷数据
            position: 边界位置
            pattern: 匹配的模式
            
        Returns:
            置信度 (0.0-1.0)
        """
        confidence = 0.5  # 基础分数
        
        # 模式类型加分
        if pattern == HeaderBoundaryPattern.CRLF_CRLF:
            confidence += 0.4  # 标准格式最高分
        elif pattern == HeaderBoundaryPattern.LF_LF:
            confidence += 0.3  # Unix格式中等分
        else:
            confidence += 0.2  # 混合格式低分
        
        # 位置合理性检查
        if 10 <= position <= 2048:  # 合理的头部长度范围
            confidence += 0.1
        elif position > 8192:  # 头部过长
            confidence -= 0.2
        
        # 检查前后内容的合理性
        try:
            # 检查边界前是否有HTTP头部特征
            header_content = payload[max(0, position-200):position]
            if b'Content-Length:' in header_content or b'Content-Type:' in header_content:
                confidence += 0.1
                
            # 检查边界后是否有合理的内容
            if position + pattern.value.__len__() < len(payload):
                confidence += 0.05
                
        except Exception:
            pass  # 忽略检查错误
        
        return min(1.0, max(0.0, confidence))
    
    def _heuristic_boundary_detection(self, scan_data: bytes, start_offset: int) -> BoundaryDetectionResult:
        """
        启发式边界检测（当标准模式匹配失败时使用）
        
        Args:
            scan_data: 扫描数据
            start_offset: 起始偏移量
            
        Returns:
            启发式检测结果
        """
        # 查找单独的\r\n模式，然后检查是否有连续的两个
        crlf_positions = []
        offset = 0
        
        while offset < len(scan_data) - 1:
            pos = scan_data.find(b'\r\n', offset)
            if pos == -1:
                break
            crlf_positions.append(pos)
            offset = pos + 2
        
        # 检查连续的\r\n对
        for i in range(len(crlf_positions) - 1):
            pos1 = crlf_positions[i]
            pos2 = crlf_positions[i + 1]
            
            # 检查是否是连续的\r\n\r\n模式
            if pos2 == pos1 + 2:
                absolute_position = start_offset + pos1
                return BoundaryDetectionResult.found_at(
                    position=absolute_position,
                    pattern=HeaderBoundaryPattern.CRLF_CRLF,
                    method="heuristic_detection",
                    confidence=0.6  # 启发式检测置信度较低
                )
        
        return BoundaryDetectionResult.not_found("heuristic_failed")
    
    def _find_http_message_start(self, payload: bytes, start_offset: int) -> int:
        """
        查找HTTP消息起始位置
        
        Args:
            payload: 载荷数据
            start_offset: 搜索起始偏移量
            
        Returns:
            消息起始位置，-1表示未找到
        """
        search_data = payload[start_offset:]
        
        # 查找请求模式
        for pattern in self.HTTP_REQUEST_PATTERNS:
            pos = search_data.find(pattern)
            if pos != -1:
                return start_offset + pos
        
        # 查找响应模式
        for pattern in self.HTTP_RESPONSE_PATTERNS:
            pos = search_data.find(pattern)
            if pos != -1:
                return start_offset + pos
        
        return -1
    
    def _identify_message_type(self, payload: bytes, start_position: int) -> str:
        """
        识别HTTP消息类型
        
        Args:
            payload: 载荷数据
            start_position: 消息起始位置
            
        Returns:
            消息类型 ("request" 或 "response")
        """
        message_start = payload[start_position:start_position + 20]
        
        for pattern in self.HTTP_REQUEST_PATTERNS:
            if message_start.startswith(pattern):
                return "request"
        
        for pattern in self.HTTP_RESPONSE_PATTERNS:
            if message_start.startswith(pattern):
                return "response"
        
        return "unknown"
    
    def _estimate_message_length(self, payload: bytes, 
                               header_boundary: BoundaryDetectionResult) -> Optional[int]:
        """
        估算HTTP消息长度（基于Content-Length或启发式方法）
        
        Args:
            payload: 载荷数据
            header_boundary: 头部边界检测结果
            
        Returns:
            估算的消息长度，None表示无法确定
        """
        if not header_boundary.found:
            return None
        
        try:
            # 提取头部内容
            header_content = payload[:header_boundary.position]
            
            # 查找Content-Length
            import re
            content_length_match = re.search(rb'[Cc]ontent-[Ll]ength:\s*(\d+)', header_content)
            if content_length_match:
                content_length = int(content_length_match.group(1))
                return header_boundary.body_start_position + content_length
                
        except Exception:
            pass
        
        # 无法确定精确长度
        return None


# 便捷函数
def detect_header_boundary(payload: bytes, start_offset: int = 0, 
                          max_scan_distance: int = 8192) -> BoundaryDetectionResult:
    """
    便捷函数：检测HTTP头部边界
    
    Args:
        payload: 载荷数据
        start_offset: 扫描起始偏移量
        max_scan_distance: 最大扫描距离
        
    Returns:
        边界检测结果
    """
    detector = BoundaryDetector(max_scan_distance=max_scan_distance)
    return detector.detect_header_boundary(payload, start_offset)


def detect_multiple_message_boundaries(payload: bytes, 
                                     max_scan_distance: int = 8192) -> List[MessageBoundaryInfo]:
    """
    便捷函数：检测多个HTTP消息边界
    
    Args:
        payload: 载荷数据
        max_scan_distance: 最大扫描距离
        
    Returns:
        消息边界信息列表
    """
    detector = BoundaryDetector(max_scan_distance=max_scan_distance)
    return detector.detect_multiple_message_boundaries(payload) 