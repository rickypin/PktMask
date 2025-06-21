"""
TCP流方向性标识和管理

提供基于TCP连接方向的流标识生成、序列号空间管理等功能。
实现方案中要求的方向性TCP连接处理机制。
"""

from enum import Enum
from typing import Tuple, Optional
from dataclasses import dataclass
import ipaddress
import logging

from ..exceptions import StreamMaskTableError


class ConnectionDirection(Enum):
    """TCP连接方向枚举"""
    FORWARD = "forward"
    REVERSE = "reverse"


@dataclass(frozen=True)
class TCPConnection:
    """
    TCP连接标识
    
    表示一个TCP连接的四元组信息，用于生成唯一的连接标识符。
    """
    src_ip: str
    src_port: int
    dst_ip: str
    dst_port: int
    
    def __post_init__(self):
        # 验证IP地址格式
        try:
            ipaddress.ip_address(self.src_ip)
            ipaddress.ip_address(self.dst_ip)
        except ValueError as e:
            raise StreamMaskTableError(
                operation="create_tcp_connection",
                stream_id=f"{self.src_ip}:{self.src_port}_{self.dst_ip}:{self.dst_port}",
                message=f"无效的IP地址: {e}"
            )
        
        # 验证端口范围
        if not (1 <= self.src_port <= 65535) or not (1 <= self.dst_port <= 65535):
            raise StreamMaskTableError(
                operation="create_tcp_connection",
                stream_id=f"{self.src_ip}:{self.src_port}_{self.dst_ip}:{self.dst_port}",
                message=f"端口号必须在1-65535范围内: src_port={self.src_port}, dst_port={self.dst_port}"
            )
    
    def get_reverse(self) -> 'TCPConnection':
        """获取反向连接"""
        return TCPConnection(
            src_ip=self.dst_ip,
            src_port=self.dst_port,
            dst_ip=self.src_ip,
            dst_port=self.src_port
        )
    
    def to_stream_base(self) -> str:
        """转换为基础流标识符（不含方向）"""
        return f"TCP_{self.src_ip}:{self.src_port}_{self.dst_ip}:{self.dst_port}"


class DirectionalTCPStream:
    """
    方向性TCP流
    
    管理TCP连接的单个方向，维护该方向的序列号空间和状态信息。
    """
    
    def __init__(self, connection: TCPConnection, direction: ConnectionDirection):
        self.connection = connection
        self.direction = direction
        self._initial_seq: Optional[int] = None
        self._last_seq: Optional[int] = None
        self._seq_ranges: list = []  # 记录已处理的序列号范围
        self._logger = logging.getLogger(__name__)
    
    @property
    def stream_id(self) -> str:
        """获取完整的方向性流标识符"""
        base_id = self.connection.to_stream_base()
        return f"{base_id}_{self.direction.value}"
    
    @property
    def initial_seq(self) -> Optional[int]:
        """获取初始序列号"""
        return self._initial_seq
    
    def set_initial_seq(self, seq: int) -> None:
        """设置初始序列号"""
        if self._initial_seq is not None and self._initial_seq != seq:
            self._logger.warning(
                f"流 {self.stream_id} 初始序列号发生变化: {self._initial_seq} -> {seq}"
            )
        self._initial_seq = seq
        self._logger.debug(f"流 {self.stream_id} 设置初始序列号: {seq}")
    
    def get_relative_seq(self, absolute_seq: int) -> int:
        """
        将绝对序列号转换为相对序列号
        
        Args:
            absolute_seq: 绝对序列号
            
        Returns:
            相对序列号（相对于初始序列号的偏移）
        """
        if self._initial_seq is None:
            raise StreamMaskTableError(
                operation="get_relative_seq",
                stream_id=self.stream_id,
                message="尚未设置初始序列号"
            )
        
        # 处理序列号回绕情况
        relative_seq = (absolute_seq - self._initial_seq) % (2**32)
        return relative_seq
    
    def get_absolute_seq(self, relative_seq: int) -> int:
        """
        将相对序列号转换为绝对序列号
        
        Args:
            relative_seq: 相对序列号
            
        Returns:
            绝对序列号
        """
        if self._initial_seq is None:
            raise StreamMaskTableError(
                operation="get_absolute_seq",
                stream_id=self.stream_id,
                message="尚未设置初始序列号"
            )
        
        # 处理序列号回绕情况
        absolute_seq = (self._initial_seq + relative_seq) % (2**32)
        return absolute_seq
    
    def update_last_seq(self, seq: int, length: int) -> None:
        """
        更新最后处理的序列号
        
        Args:
            seq: 数据包序列号
            length: 数据包载荷长度
        """
        end_seq = seq + length
        if self._last_seq is None or end_seq > self._last_seq:
            self._last_seq = end_seq
        
        # 记录序列号范围
        self._seq_ranges.append((seq, end_seq))
    
    def has_sequence_gap(self, seq: int) -> bool:
        """
        检查是否存在序列号间隙
        
        Args:
            seq: 当前序列号
            
        Returns:
            是否存在间隙
        """
        if self._last_seq is None:
            return False
        
        return seq > self._last_seq
    
    def get_sequence_coverage(self) -> list:
        """获取已覆盖的序列号范围"""
        return sorted(self._seq_ranges)


class TCPStreamManager:
    """
    TCP流管理器
    
    管理所有TCP连接的双向流，提供流创建、查询和序列号管理功能。
    """
    
    def __init__(self):
        self._streams: dict[str, DirectionalTCPStream] = {}
        self._logger = logging.getLogger(__name__)
    
    def get_or_create_stream(
        self, 
        src_ip: str, 
        src_port: int, 
        dst_ip: str, 
        dst_port: int,
        direction: ConnectionDirection
    ) -> DirectionalTCPStream:
        """
        获取或创建方向性TCP流
        
        Args:
            src_ip: 源IP地址
            src_port: 源端口
            dst_ip: 目标IP地址
            dst_port: 目标端口
            direction: 连接方向
            
        Returns:
            方向性TCP流对象
        """
        connection = TCPConnection(src_ip, src_port, dst_ip, dst_port)
        stream = DirectionalTCPStream(connection, direction)
        stream_id = stream.stream_id
        
        if stream_id not in self._streams:
            self._streams[stream_id] = stream
            self._logger.debug(f"创建新的TCP流: {stream_id}")
        
        return self._streams[stream_id]
    
    def get_stream_by_id(self, stream_id: str) -> Optional[DirectionalTCPStream]:
        """
        根据流ID获取TCP流
        
        Args:
            stream_id: 流标识符
            
        Returns:
            TCP流对象，如果不存在则返回None
        """
        return self._streams.get(stream_id)
    
    def parse_stream_id(self, stream_id: str) -> Tuple[TCPConnection, ConnectionDirection]:
        """
        解析流ID获取连接信息和方向
        
        Args:
            stream_id: 流标识符，格式为 TCP_{src_ip}:{src_port}_{dst_ip}:{dst_port}_{direction}
            
        Returns:
            (TCP连接对象, 连接方向)
        """
        if not stream_id.startswith("TCP_"):
            raise StreamMaskTableError(
                operation="parse_stream_id",
                stream_id=stream_id,
                message="无效的TCP流ID格式，必须以'TCP_'开头"
            )
        
        # 移除TCP_前缀
        parts = stream_id[4:].split("_")
        if len(parts) != 3:
            raise StreamMaskTableError(
                operation="parse_stream_id",
                stream_id=stream_id,
                message="无效的TCP流ID格式，应为 TCP_{src_ip}:{src_port}_{dst_ip}:{dst_port}_{direction}"
            )
        
        src_part, dst_part, direction_str = parts
        
        # 解析源地址和端口
        try:
            src_ip, src_port_str = src_part.rsplit(":", 1)
            src_port = int(src_port_str)
        except ValueError:
            raise StreamMaskTableError(
                operation="parse_stream_id",
                stream_id=stream_id,
                message=f"无效的源地址格式: {src_part}"
            )
        
        # 解析目标地址和端口
        try:
            dst_ip, dst_port_str = dst_part.rsplit(":", 1)
            dst_port = int(dst_port_str)
        except ValueError:
            raise StreamMaskTableError(
                operation="parse_stream_id",
                stream_id=stream_id,
                message=f"无效的目标地址格式: {dst_part}"
            )
        
        # 解析方向
        try:
            direction = ConnectionDirection(direction_str)
        except ValueError:
            raise StreamMaskTableError(
                operation="parse_stream_id",
                stream_id=stream_id,
                message=f"无效的连接方向: {direction_str}"
            )
        
        connection = TCPConnection(src_ip, src_port, dst_ip, dst_port)
        return connection, direction
    
    def generate_stream_id(
        self,
        src_ip: str,
        src_port: int,
        dst_ip: str,
        dst_port: int,
        direction: ConnectionDirection
    ) -> str:
        """
        生成方向性流标识符
        
        Args:
            src_ip: 源IP地址
            src_port: 源端口
            dst_ip: 目标IP地址
            dst_port: 目标端口
            direction: 连接方向
            
        Returns:
            方向性流标识符
        """
        connection = TCPConnection(src_ip, src_port, dst_ip, dst_port)
        stream = DirectionalTCPStream(connection, direction)
        return stream.stream_id
    
    def get_all_stream_ids(self) -> list[str]:
        """获取所有流ID列表"""
        return list(self._streams.keys())
    
    def get_stream_count(self) -> int:
        """获取流数量"""
        return len(self._streams)
    
    def clear(self) -> None:
        """清除所有流"""
        self._streams.clear()
        self._logger.debug("已清除所有TCP流")


def detect_packet_direction(
    packet_src_ip: str,
    packet_src_port: int,
    packet_dst_ip: str,
    packet_dst_port: int,
    connection_src_ip: str,
    connection_src_port: int,
    connection_dst_ip: str,
    connection_dst_port: int
) -> ConnectionDirection:
    """
    检测数据包在TCP连接中的方向
    
    Args:
        packet_src_ip: 数据包源IP
        packet_src_port: 数据包源端口
        packet_dst_ip: 数据包目标IP
        packet_dst_port: 数据包目标端口
        connection_src_ip: 连接源IP
        connection_src_port: 连接源端口
        connection_dst_ip: 连接目标IP
        connection_dst_port: 连接目标端口
        
    Returns:
        连接方向
    """
    # 正向：数据包方向与连接方向一致
    if (packet_src_ip == connection_src_ip and packet_src_port == connection_src_port and
        packet_dst_ip == connection_dst_ip and packet_dst_port == connection_dst_port):
        return ConnectionDirection.FORWARD
    
    # 反向：数据包方向与连接方向相反
    elif (packet_src_ip == connection_dst_ip and packet_src_port == connection_dst_port and
          packet_dst_ip == connection_src_ip and packet_dst_port == connection_src_port):
        return ConnectionDirection.REVERSE
    
    else:
        raise StreamMaskTableError(
            operation="detect_packet_direction",
            stream_id=f"{packet_src_ip}:{packet_src_port}_{packet_dst_ip}:{packet_dst_port}",
            message="数据包不属于指定的TCP连接"
        ) 