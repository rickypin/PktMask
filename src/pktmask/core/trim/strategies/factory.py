"""
协议策略工厂

这个模块实现了策略工厂模式，负责管理所有可用的协议裁切策略，
提供策略注册、发现、创建和选择的功能。

作者: PktMask Team
创建时间: 2025-01-15
版本: 1.0.0
"""

from typing import Dict, List, Type, Optional, Any
import logging
from collections import defaultdict

from .base_strategy import BaseStrategy, ProtocolInfo, TrimContext


class StrategyRegistry:
    """策略注册表，管理所有可用的策略"""
    
    def __init__(self):
        self._strategies: Dict[str, Type[BaseStrategy]] = {}
        self._protocol_map: Dict[str, List[str]] = defaultdict(list)
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        
    def register(self, strategy_class: Type[BaseStrategy]) -> None:
        """
        注册一个策略类
        
        Args:
            strategy_class: 策略类，必须继承自BaseStrategy
            
        Raises:
            ValueError: 策略类无效时
            TypeError: 类型错误时
        """
        if not issubclass(strategy_class, BaseStrategy):
            raise TypeError(f"策略类 {strategy_class.__name__} 必须继承自 BaseStrategy")
            
        # 创建临时实例来获取策略信息
        try:
            temp_instance = strategy_class({})
            strategy_name = temp_instance.strategy_name
            supported_protocols = temp_instance.supported_protocols
        except Exception as e:
            raise ValueError(f"无法获取策略 {strategy_class.__name__} 的信息: {e}")
            
        if strategy_name in self._strategies:
            self.logger.warning(f"策略 {strategy_name} 已存在，将被覆盖")
            
        # 注册策略
        self._strategies[strategy_name] = strategy_class
        
        # 更新协议映射
        for protocol in supported_protocols:
            if strategy_name not in self._protocol_map[protocol]:
                self._protocol_map[protocol].append(strategy_name)
                
        self.logger.info(f"已注册策略: {strategy_name} (支持协议: {supported_protocols})")
        
    def unregister(self, strategy_name: str) -> bool:
        """
        注销一个策略
        
        Args:
            strategy_name: 策略名称
            
        Returns:
            True 如果成功注销，False 如果策略不存在
        """
        if strategy_name not in self._strategies:
            return False
            
        # 创建临时实例获取支持的协议
        try:
            temp_instance = self._strategies[strategy_name]({})
            supported_protocols = temp_instance.supported_protocols
        except Exception:
            supported_protocols = []
            
        # 从协议映射中移除
        for protocol in supported_protocols:
            if strategy_name in self._protocol_map[protocol]:
                self._protocol_map[protocol].remove(strategy_name)
                if not self._protocol_map[protocol]:
                    del self._protocol_map[protocol]
                    
        # 移除策略
        del self._strategies[strategy_name]
        self.logger.info(f"已注销策略: {strategy_name}")
        return True
        
    def get_strategy_class(self, strategy_name: str) -> Optional[Type[BaseStrategy]]:
        """
        根据名称获取策略类
        
        Args:
            strategy_name: 策略名称
            
        Returns:
            策略类，如果不存在则返回None
        """
        return self._strategies.get(strategy_name)
        
    def get_strategies_for_protocol(self, protocol: str) -> List[str]:
        """
        获取支持指定协议的所有策略名称
        
        Args:
            protocol: 协议名称
            
        Returns:
            支持该协议的策略名称列表
        """
        strategies = self._protocol_map.get(protocol, []).copy()
        
        # 添加支持通配符协议的策略
        wildcard_strategies = self._protocol_map.get('*', [])
        for strategy in wildcard_strategies:
            if strategy not in strategies:
                strategies.append(strategy)
                
        return strategies
        
    def list_all_strategies(self) -> List[str]:
        """
        列出所有已注册的策略名称
        
        Returns:
            所有策略名称列表
        """
        return list(self._strategies.keys())
        
    def list_all_protocols(self) -> List[str]:
        """
        列出所有支持的协议
        
        Returns:
            所有支持的协议名称列表
        """
        return list(self._protocol_map.keys())


class ProtocolStrategyFactory:
    """
    协议策略工厂
    
    负责创建和管理协议裁切策略，提供策略选择和实例化功能。
    """
    
    def __init__(self):
        self.registry = StrategyRegistry()
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        self._strategy_cache: Dict[str, BaseStrategy] = {}
        
    def register_strategy(self, strategy_class: Type[BaseStrategy]) -> None:
        """
        注册策略类
        
        Args:
            strategy_class: 策略类
        """
        self.registry.register(strategy_class)
        
    def create_strategy(self, strategy_name: str, config: Dict[str, Any]) -> Optional[BaseStrategy]:
        """
        创建策略实例
        
        Args:
            strategy_name: 策略名称
            config: 配置参数
            
        Returns:
            策略实例，如果创建失败则返回None
        """
        strategy_class = self.registry.get_strategy_class(strategy_name)
        if not strategy_class:
            self.logger.error(f"未找到策略: {strategy_name}")
            return None
            
        try:
            strategy = strategy_class(config)
            self.logger.debug(f"已创建策略实例: {strategy_name}")
            return strategy
        except Exception as e:
            self.logger.error(f"创建策略 {strategy_name} 失败: {e}", exc_info=True)
            return None
            
    def get_best_strategy(self, protocol_info: ProtocolInfo, context: TrimContext,
                         config: Dict[str, Any]) -> Optional[BaseStrategy]:
        """
        为指定协议和上下文选择最佳策略
        
        Args:
            protocol_info: 协议信息
            context: 裁切上下文
            config: 配置参数
            
        Returns:
            最佳策略实例，如果没有合适策略则返回None
        """
        # 获取支持该协议的所有策略
        strategy_names = self.registry.get_strategies_for_protocol(protocol_info.name)
        
        if not strategy_names:
            self.logger.warning(f"没有找到支持协议 {protocol_info.name} 的策略")
            return None
            
        # 创建候选策略实例并测试
        candidates = []
        for strategy_name in strategy_names:
            strategy = self.create_strategy(strategy_name, config)
            if strategy and strategy.can_handle(protocol_info, context):
                candidates.append(strategy)
                
        if not candidates:
            self.logger.warning(f"没有策略可以处理协议 {protocol_info.name} 和给定上下文")
            return None
            
        # 按优先级排序，选择最高优先级的策略
        best_strategy = max(candidates, key=lambda s: s.priority)
        self.logger.debug(f"为协议 {protocol_info.name} 选择策略: {best_strategy.strategy_name}")
        
        return best_strategy
        
    def get_strategy_by_name(self, strategy_name: str, config: Dict[str, Any]) -> Optional[BaseStrategy]:
        """
        根据名称获取策略实例
        
        Args:
            strategy_name: 策略名称
            config: 配置参数
            
        Returns:
            策略实例，如果不存在则返回None
        """
        return self.create_strategy(strategy_name, config)
        
    def list_available_strategies(self) -> Dict[str, List[str]]:
        """
        列出所有可用的策略和它们支持的协议
        
        Returns:
            策略信息字典，格式为 {strategy_name: [supported_protocols]}
        """
        result = {}
        for strategy_name in self.registry.list_all_strategies():
            strategy_class = self.registry.get_strategy_class(strategy_name)
            if strategy_class:
                try:
                    temp_instance = strategy_class({})
                    result[strategy_name] = temp_instance.supported_protocols
                except Exception:
                    result[strategy_name] = []
                    
        return result
        
    def auto_register_strategies(self) -> None:
        """
        自动注册所有可用的策略
        
        扫描strategies包并自动注册所有找到的策略类。
        """
        self.logger.info("开始自动注册策略...")
        
        # 导入并注册所有可用策略
        try:
            from .default_strategy import DefaultStrategy
            self.register_strategy(DefaultStrategy)
            self.logger.info("已注册DefaultStrategy")
        except ImportError as e:
            self.logger.warning(f"无法导入DefaultStrategy: {e}")
            
        try:
            from .http_strategy import HTTPTrimStrategy
            self.register_strategy(HTTPTrimStrategy)
            self.logger.info("已注册HTTPTrimStrategy")
        except ImportError as e:
            self.logger.warning(f"无法导入HTTPTrimStrategy: {e}")
            
        try:
            from .tls_strategy import TLSTrimStrategy
            self.register_strategy(TLSTrimStrategy)
            self.logger.info("已注册TLSTrimStrategy")
        except ImportError as e:
            self.logger.warning(f"无法导入TLSTrimStrategy: {e}")
        
        # 输出已注册的策略
        registered_strategies = self.list_available_strategies()
        self.logger.info(f"策略自动注册完成，共注册 {len(registered_strategies)} 个策略: {list(registered_strategies.keys())}")


# 全局策略工厂实例
_strategy_factory = None


def get_strategy_factory() -> ProtocolStrategyFactory:
    """
    获取全局策略工厂实例
    
    Returns:
        策略工厂实例
    """
    global _strategy_factory
    if _strategy_factory is None:
        _strategy_factory = ProtocolStrategyFactory()
        _strategy_factory.auto_register_strategies()
    return _strategy_factory


def register_strategy(strategy_class: Type[BaseStrategy]) -> None:
    """
    便捷的策略注册函数
    
    Args:
        strategy_class: 策略类
    """
    factory = get_strategy_factory()
    factory.register_strategy(strategy_class) 