"""
基础协议裁切策略抽象类

这个模块定义了协议裁切策略的标准接口，所有具体的协议策略都应该继承BaseStrategy
并实现其抽象方法。策略模式使得系统可以灵活地支持不同协议的裁切算法。

作者: PktMask Team
创建时间: 2025-01-15
版本: 1.0.0
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
import logging

from ..models.mask_spec import MaskSpec


@dataclass
class ProtocolInfo:
    """协议信息数据类"""
    name: str                    # 协议名称，如 'HTTP', 'TLS'
    version: Optional[str]       # 协议版本，如 '1.1', '1.3'
    layer: int                  # 协议层级，应用层=7，传输层=4
    port: Optional[int]         # 端口号
    characteristics: Dict[str, Any]  # 协议特征，如 {'encrypted': True}


@dataclass
class TrimContext:
    """Trimming context data class"""
    packet_index: int           # 数据包在流中的索引
    stream_id: str             # 流ID
    flow_direction: str        # 流方向: 'client_to_server' or 'server_to_client'
    protocol_stack: List[str]  # 协议栈，如 ['ETH', 'IP', 'TCP', 'TLS']
    payload_size: int          # 原始载荷大小
    timestamp: float           # 数据包时间戳
    metadata: Dict[str, Any]   # 额外元数据


@dataclass
class TrimResult:
    """裁切结果数据类"""
    success: bool              # 是否成功裁切
    mask_spec: Optional[MaskSpec]  # 生成的掩码规范
    preserved_bytes: int       # 保留的字节数
    trimmed_bytes: int         # 裁切的字节数
    confidence: float          # 裁切置信度 (0.0-1.0)
    reason: str               # 裁切原因或错误信息
    warnings: List[str]       # 警告信息
    metadata: Dict[str, Any]  # 额外结果元数据


class BaseStrategy(ABC):
    """
    基础协议裁切策略抽象类
    
    所有协议策略的基础类，定义了策略的标准接口和通用功能。
    每个具体策略负责特定协议的载荷裁切逻辑。
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化策略
        
        Args:
            config: 策略配置字典
        """
        self.config = config
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        self._validate_config()
        
    @property
    @abstractmethod
    def supported_protocols(self) -> List[str]:
        """
        返回此策略支持的协议列表
        
        Returns:
            支持的协议名称列表，如 ['HTTP', 'HTTPS']
        """
        pass
        
    @property
    @abstractmethod
    def strategy_name(self) -> str:
        """
        返回策略名称
        
        Returns:
            策略的唯一标识名称
        """
        pass
        
    @property
    @abstractmethod
    def priority(self) -> int:
        """
        返回策略优先级
        
        优先级决定了当多个策略都支持同一协议时的选择顺序。
        数值越高优先级越高。
        
        Returns:
            策略优先级 (0-100)
        """
        pass
        
    @abstractmethod
    def can_handle(self, protocol_info: ProtocolInfo, context: TrimContext) -> bool:
        """
        判断是否可以处理指定的协议和上下文
        
        Args:
            protocol_info: 协议信息
            context: 裁切上下文
            
        Returns:
            True 如果可以处理，False 否则
        """
        pass
        
    @abstractmethod
    def analyze_payload(self, payload: bytes, protocol_info: ProtocolInfo, 
                       context: TrimContext) -> Dict[str, Any]:
        """
        分析载荷结构
        
        Args:
            payload: 原始载荷数据
            protocol_info: 协议信息
            context: 裁切上下文
            
        Returns:
            载荷分析结果字典
        """
        pass
        
    @abstractmethod
    def generate_mask_spec(self, payload: bytes, protocol_info: ProtocolInfo,
                          context: TrimContext, analysis: Dict[str, Any]) -> TrimResult:
        """
        生成掩码规范
        
        Args:
            payload: 原始载荷数据
            protocol_info: 协议信息
            context: 裁切上下文
            analysis: 载荷分析结果
            
        Returns:
            裁切结果
        """
        pass
        
    def trim_payload(self, payload: bytes, protocol_info: ProtocolInfo,
                    context: TrimContext) -> TrimResult:
        """
        执行载荷裁切的主方法
        
        这是策略的主要入口点，协调整个裁切过程。
        
        Args:
            payload: 原始载荷数据
            protocol_info: 协议信息
            context: 裁切上下文
            
        Returns:
            裁切结果
        """
        try:
            # 检查是否可以处理
            if not self.can_handle(protocol_info, context):
                return TrimResult(
                    success=False,
                    mask_spec=None,
                    preserved_bytes=len(payload),
                    trimmed_bytes=0,
                    confidence=0.0,
                    reason=f"策略 {self.strategy_name} 不支持协议 {protocol_info.name}",
                    warnings=[],
                    metadata={}
                )
            
            # 分析载荷
            analysis = self.analyze_payload(payload, protocol_info, context)
            
            # 生成掩码规范
            result = self.generate_mask_spec(payload, protocol_info, context, analysis)
            
            # 记录处理结果
            self.logger.debug(f"协议 {protocol_info.name} 裁切完成: "
                            f"保留 {result.preserved_bytes} 字节, "
                            f"裁切 {result.trimmed_bytes} 字节, "
                            f"置信度 {result.confidence:.2f}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"裁切载荷时发生错误: {e}", exc_info=True)
            return TrimResult(
                success=False,
                mask_spec=None,
                preserved_bytes=len(payload),
                trimmed_bytes=0,
                confidence=0.0,
                reason=f"处理过程中发生错误: {str(e)}",
                warnings=[],
                metadata={"error_type": type(e).__name__}
            )
    
    def _validate_config(self) -> None:
        """
        验证配置参数
        
        子类可以重写此方法来验证特定的配置参数。
        
        Raises:
            ValueError: 配置参数无效时
        """
        if not isinstance(self.config, dict):
            raise ValueError("配置必须是字典类型")
            
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """
        获取配置值
        
        Args:
            key: 配置键名
            default: 默认值
            
        Returns:
            配置值
        """
        return self.config.get(key, default)
        
    def update_config(self, updates: Dict[str, Any]) -> None:
        """
        更新配置
        
        Args:
            updates: 要更新的配置项
        """
        self.config.update(updates)
        self._validate_config() 