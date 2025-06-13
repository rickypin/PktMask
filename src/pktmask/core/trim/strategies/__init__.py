"""
协议策略包

这个包包含了PktMask智能载荷裁切功能的所有协议策略实现。
策略模式使得系统可以灵活地支持不同协议的裁切算法。

主要组件:
- BaseStrategy: 策略基类，定义标准接口
- ProtocolStrategyFactory: 策略工厂，管理策略创建和选择
- 具体策略实现: HTTP策略、TLS策略等

作者: PktMask Team
创建时间: 2025-01-15
版本: 1.0.0
"""

from .base_strategy import (
    BaseStrategy,
    ProtocolInfo,
    TrimContext,
    TrimResult
)

from .factory import (
    ProtocolStrategyFactory,
    StrategyRegistry,
    get_strategy_factory,
    register_strategy
)

from .default_strategy import DefaultStrategy
from .http_strategy import HTTPTrimStrategy
from .tls_strategy import TLSTrimStrategy

# 自动注册所有可用的策略
def auto_register_all_strategies():
    """自动注册所有可用的策略"""
    factory = get_strategy_factory()
    
    # 注册默认策略
    factory.register_strategy(DefaultStrategy)
    
    # 注册HTTP策略
    factory.register_strategy(HTTPTrimStrategy)
    
    # 注册TLS策略
    factory.register_strategy(TLSTrimStrategy)

# 模块导入时自动注册
auto_register_all_strategies()

__all__ = [
    # 基础策略类
    'BaseStrategy',
    'ProtocolInfo', 
    'TrimContext',
    'TrimResult',
    
    # 策略工厂
    'ProtocolStrategyFactory',
    'StrategyRegistry',
    'get_strategy_factory',
    'register_strategy',
    
    # 具体策略
    'DefaultStrategy',
    'HTTPTrimStrategy',
    'TLSTrimStrategy',
]

# 版本信息
__version__ = '1.0.0'
__author__ = 'PktMask Team' 