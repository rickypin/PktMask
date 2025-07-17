"""
协议标记器基类

定义了协议分析器的通用接口和基础功能。
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List

from .types import KeepRuleSet


class ProtocolMarker(ABC):
    """协议标记模块基类
    
    定义了协议分析器的通用接口，所有具体的协议标记器都应该继承此类。
    """
    
    def __init__(self, config: Dict[str, Any]):
        """初始化协议标记器
        
        Args:
            config: 配置字典
        """
        self.config = config
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        self._initialized = False
    
    @abstractmethod
    def analyze_file(self, pcap_path: str, config: Dict[str, Any]) -> KeepRuleSet:
        """分析文件并生成保留规则
        
        Args:
            pcap_path: PCAP/PCAPNG 文件路径
            config: 分析配置
            
        Returns:
            KeepRuleSet: 保留规则集合
        """
        pass
    
    @abstractmethod
    def get_supported_protocols(self) -> List[str]:
        """获取支持的协议列表
        
        Returns:
            支持的协议名称列表
        """
        pass
    
    def initialize(self) -> bool:
        """初始化标记器

        Returns:
            初始化是否成功
        """
        if self._initialized:
            self.logger.debug(f"{self.__class__.__name__} already initialized, skipping")
            return True

        try:
            import platform
            self.logger.info(f"Starting {self.__class__.__name__} initialization on {platform.system()}")
            self.logger.debug(f"Config: {self.config}")

            self._initialize_components()
            self._initialized = True
            self.logger.info(f"{self.__class__.__name__} 初始化成功")
            return True
        except Exception as e:
            import traceback
            self.logger.error(f"{self.__class__.__name__} 初始化失败: {e}")
            self.logger.error(f"Exception type: {type(e).__name__}")
            self.logger.error(f"Exception details: {str(e)}")

            # 记录完整的错误堆栈
            self.logger.error(f"{self.__class__.__name__} initialization failure traceback:")
            for line in traceback.format_exc().splitlines():
                self.logger.error(f"[{self.__class__.__name__}] {line}")

            return False
    
    def _initialize_components(self) -> None:
        """初始化组件，子类可以重写此方法"""
        pass
    
    def validate_config(self, config: Dict[str, Any]) -> List[str]:
        """验证配置参数
        
        Args:
            config: 配置字典
            
        Returns:
            错误信息列表，空列表表示配置有效
        """
        errors = []
        
        # 基础验证
        if not isinstance(config, dict):
            errors.append("配置必须是字典类型")
            return errors
        
        # 子类可以重写此方法添加特定验证
        return self._validate_specific_config(config)
    
    def _validate_specific_config(self, config: Dict[str, Any]) -> List[str]:
        """验证特定协议的配置，子类应该重写此方法
        
        Args:
            config: 配置字典
            
        Returns:
            错误信息列表
        """
        return []
    
    def get_display_name(self) -> str:
        """获取显示名称"""
        return self.__class__.__name__
    
    def get_description(self) -> str:
        """获取描述信息"""
        protocols = ", ".join(self.get_supported_protocols())
        return f"协议标记器，支持协议: {protocols}"
    
    def get_version(self) -> str:
        """获取版本信息"""
        return "1.0.0"
    
    def cleanup(self) -> None:
        """清理资源"""
        self.logger.debug(f"{self.__class__.__name__} 清理资源")
        self._initialized = False
