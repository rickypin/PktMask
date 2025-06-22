"""
独立PCAP掩码处理器自定义异常

定义了所有可能的异常类型，提供明确的错误分类和处理指导。
"""

from typing import Optional


class IndependentMaskerError(Exception):
    """独立掩码处理器基础异常类
    
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


class ProtocolBindingError(IndependentMaskerError):
    """协议绑定控制相关错误
    
    当Scapy协议解析禁用/恢复过程中发生错误时抛出
    """
    pass


class FileConsistencyError(IndependentMaskerError):
    """文件一致性验证错误
    
    当输出文件与输入文件一致性验证失败时抛出
    """
    pass


class MaskApplicationError(IndependentMaskerError):
    """掩码应用错误
    
    当掩码应用过程中发生错误时抛出
    """
    pass


class ValidationError(IndependentMaskerError):
    """输入验证错误
    
    当输入参数验证失败时抛出
    """
    pass


class ConfigurationError(IndependentMaskerError):
    """配置错误
    
    当配置参数无效时抛出
    """
    pass 