"""
TCP载荷掩码处理器自定义异常

定义了TCP载荷掩码处理过程中可能的异常类型，提供明确的错误分类和处理指导。
"""

from typing import Optional


class TcpPayloadMaskerError(Exception):
    """TCP载荷掩码处理器基础异常类
    
    所有其他异常都继承自这个基类
    """
    
    def __init__(self, message: str, details: Optional[str] = None):
        self.message = message
        self.details = details
        super().__init__(self.message)
    
    def __str__(self) -> str:
        if self.details:
            return f"{self.message}\n详细信息: {self.details}"
        return self.message


class ProtocolBindingError(TcpPayloadMaskerError):
    """协议绑定控制相关错误
    
    当Scapy协议解析禁用/恢复过程中发生错误时抛出
    """
    pass


class FileConsistencyError(TcpPayloadMaskerError):
    """文件一致性验证错误
    
    当输出文件与输入文件一致性验证失败时抛出
    """
    pass


class TcpKeepRangeApplicationError(TcpPayloadMaskerError):
    """TCP保留范围应用错误
    
    当TCP载荷保留范围掩码应用过程中发生错误时抛出
    """
    pass


class ValidationError(TcpPayloadMaskerError):
    """输入验证错误
    
    当输入参数验证失败时抛出
    """
    pass


class ConfigurationError(TcpPayloadMaskerError):
    """配置错误
    
    当配置参数无效时抛出
    """
    pass 