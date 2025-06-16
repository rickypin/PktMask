"""
协议策略工厂

这个模块实现了策略工厂模式，负责管理所有可用的协议裁切策略，
提供策略注册、发现、创建和选择的功能。

增强版：支持双策略并存，A/B测试，性能对比等功能。

作者: PktMask Team
创建时间: 2025-01-15
版本: 2.0.0 (双策略增强版)
"""

from typing import Dict, List, Type, Optional, Any
import logging
import time
import random
from collections import defaultdict
from abc import ABC, abstractmethod

from .base_strategy import BaseStrategy, ProtocolInfo, TrimContext, TrimResult
from ..models.mask_spec import MaskSpec, KeepAll

# 双策略配置导入
try:
    from ....config.http_strategy_config import (
        HttpStrategyConfiguration, StrategyMode, 
        get_default_http_strategy_config
    )
    HTTP_STRATEGY_CONFIG_AVAILABLE = True
except ImportError:
    HTTP_STRATEGY_CONFIG_AVAILABLE = False


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


class ComparisonWrapper(BaseStrategy):
    """
    双策略对比包装器
    
    同时运行Legacy和Scanning策略进行性能对比，收集详细的性能数据。
    """
    
    def __init__(self, legacy_strategy: BaseStrategy, scanning_strategy: BaseStrategy,
                 config: Dict[str, Any], http_config: Optional['HttpStrategyConfiguration'] = None):
        super().__init__(config)
        self.legacy_strategy = legacy_strategy
        self.scanning_strategy = scanning_strategy
        self.http_config = http_config or get_default_http_strategy_config()
        self.comparison_data = []
        
    @property
    def strategy_name(self) -> str:
        return "comparison_wrapper"
    
    @property
    def supported_protocols(self) -> List[str]:
        # 合并两个策略支持的协议
        protocols = set(self.legacy_strategy.supported_protocols)
        protocols.update(self.scanning_strategy.supported_protocols)
        return list(protocols)
    
    def can_handle(self, protocol_info: ProtocolInfo, context: TrimContext) -> bool:
        """能力检查 - 只要任一策略能处理即可"""
        return (self.legacy_strategy.can_handle(protocol_info, context) or
                self.scanning_strategy.can_handle(protocol_info, context))
    
    def analyze_payload(self, payload: bytes, protocol_info: ProtocolInfo,
                       context: TrimContext) -> Dict[str, Any]:
        """并行分析 - 同时运行两种策略"""
        
        comparison_result = {
            'comparison_metadata': {
                'payload_size': len(payload),
                'timestamp': time.time(),
                'file_path': context.input_file
            }
        }
        
        # 运行Legacy策略
        legacy_start = time.perf_counter()
        try:
            legacy_analysis = self.legacy_strategy.analyze_payload(
                payload, protocol_info, context
            )
            legacy_success = True
            legacy_error = None
        except Exception as e:
            legacy_analysis = {}
            legacy_success = False
            legacy_error = str(e)
        legacy_duration = time.perf_counter() - legacy_start
        
        # 运行Scanning策略
        scanning_start = time.perf_counter()
        try:
            scanning_analysis = self.scanning_strategy.analyze_payload(
                payload, protocol_info, context
            )
            scanning_success = True
            scanning_error = None
        except Exception as e:
            scanning_analysis = {}
            scanning_success = False
            scanning_error = str(e)
        scanning_duration = time.perf_counter() - scanning_start
        
        # 记录对比结果
        comparison_result.update({
            'legacy_result': {
                'analysis': legacy_analysis,
                'duration_ms': legacy_duration * 1000,
                'success': legacy_success,
                'error': legacy_error
            },
            'scanning_result': {
                'analysis': scanning_analysis,
                'duration_ms': scanning_duration * 1000,
                'success': scanning_success,
                'error': scanning_error
            },
            'performance_comparison': {
                'speed_improvement': ((legacy_duration - scanning_duration) / legacy_duration 
                                    if legacy_duration > 0 else 0),
                'both_successful': legacy_success and scanning_success,
                'results_match': self._compare_analysis_results(legacy_analysis, scanning_analysis)
            }
        })
        
        # 保存对比数据
        self.comparison_data.append(comparison_result)
        
        # 决定使用哪个结果（优先使用Legacy确保兼容性）
        if legacy_success:
            comparison_result['selected_strategy'] = 'legacy'
            return legacy_analysis
        elif scanning_success:
            comparison_result['selected_strategy'] = 'scanning'
            return scanning_analysis
        else:
            comparison_result['selected_strategy'] = 'fallback'
            return {}
    
    def _compare_analysis_results(self, legacy: Dict[str, Any], 
                                scanning: Dict[str, Any]) -> bool:
        """比较两种策略的分析结果是否一致"""
        
        # 关键字段对比
        key_fields = ['header_boundary', 'is_chunked', 'content_length', 
                     'message_count', 'is_complete']
        
        for field in key_fields:
            if legacy.get(field) != scanning.get(field):
                return False
                
        return True

    def generate_mask_spec(self, payload: bytes, protocol_info: ProtocolInfo,
                          context: TrimContext, analysis: Dict[str, Any]) -> TrimResult:
        """
        生成掩码规范 - 使用选中的策略
        
        Args:
            payload: 原始载荷数据
            protocol_info: 协议信息
            context: 裁切上下文
            analysis: 载荷分析结果
            
        Returns:
            裁切结果
        """
        comparison_start = time.time()
        
        try:
            # 从分析结果中获取选中的策略
            selected_strategy = analysis.get('selected_strategy', 'legacy')
            
            # 生成两种策略的掩码规范进行对比
            legacy_result = None
            scanning_result = None
            
            # 运行Legacy策略掩码生成
            legacy_mask_start = time.perf_counter()
            try:
                legacy_result = self.legacy_strategy.generate_mask_spec(
                    payload, protocol_info, context, analysis.get('legacy_result', {}).get('analysis', {})
                )
                legacy_mask_success = True
                legacy_mask_error = None
            except Exception as e:
                legacy_result = TrimResult(
                    success=False,
                    mask_spec=None,
                    preserved_bytes=len(payload),
                    trimmed_bytes=0,
                    confidence=0.0,
                    reason=f"Legacy策略掩码生成失败: {str(e)}",
                    warnings=[],
                    metadata={}
                )
                legacy_mask_success = False
                legacy_mask_error = str(e)
            legacy_mask_duration = time.perf_counter() - legacy_mask_start
            
            # 运行Scanning策略掩码生成
            scanning_mask_start = time.perf_counter()
            try:
                scanning_result = self.scanning_strategy.generate_mask_spec(
                    payload, protocol_info, context, analysis.get('scanning_result', {}).get('analysis', {})
                )
                scanning_mask_success = True
                scanning_mask_error = None
            except Exception as e:
                scanning_result = TrimResult(
                    success=False,
                    mask_spec=None,
                    preserved_bytes=len(payload),
                    trimmed_bytes=0,
                    confidence=0.0,
                    reason=f"Scanning策略掩码生成失败: {str(e)}",
                    warnings=[],
                    metadata={}
                )
                scanning_mask_success = False
                scanning_mask_error = str(e)
            scanning_mask_duration = time.perf_counter() - scanning_mask_start
            
            # 记录掩码生成对比数据
            mask_comparison = {
                'comparison_metadata': {
                    'payload_size': len(payload),
                    'timestamp': comparison_start,
                    'file_path': getattr(context, 'input_file', 'unknown')
                },
                'legacy_mask_result': {
                    'result': legacy_result,
                    'duration_ms': legacy_mask_duration * 1000,
                    'success': legacy_mask_success,
                    'error': legacy_mask_error
                },
                'scanning_mask_result': {
                    'result': scanning_result,
                    'duration_ms': scanning_mask_duration * 1000,
                    'success': scanning_mask_success,
                    'error': scanning_mask_error
                },
                'mask_comparison': {
                    'speed_improvement': ((legacy_mask_duration - scanning_mask_duration) / legacy_mask_duration 
                                        if legacy_mask_duration > 0 else 0),
                    'both_successful': legacy_mask_success and scanning_mask_success,
                    'results_consistent': self._compare_mask_results(legacy_result, scanning_result)
                }
            }
            
            # 添加到对比数据收集
            self.comparison_data.append(mask_comparison)
            
            # 根据选中的策略返回结果
            if selected_strategy == 'legacy' and legacy_result:
                final_result = legacy_result
                final_result.metadata['comparison_wrapper'] = mask_comparison
                self.logger.debug(f"ComparisonWrapper: 使用Legacy策略掩码结果")
                return final_result
            elif selected_strategy == 'scanning' and scanning_result:
                final_result = scanning_result
                final_result.metadata['comparison_wrapper'] = mask_comparison
                self.logger.debug(f"ComparisonWrapper: 使用Scanning策略掩码结果")
                return final_result
            else:
                # 回退策略：优先使用成功的结果
                if legacy_result and legacy_result.success:
                    final_result = legacy_result
                    final_result.metadata['comparison_wrapper'] = mask_comparison
                    final_result.metadata['fallback_reason'] = f"选中策略{selected_strategy}失败，回退到Legacy"
                    self.logger.warning(f"ComparisonWrapper: 回退到Legacy策略掩码结果")
                    return final_result
                elif scanning_result and scanning_result.success:
                    final_result = scanning_result
                    final_result.metadata['comparison_wrapper'] = mask_comparison
                    final_result.metadata['fallback_reason'] = f"选中策略{selected_strategy}失败，回退到Scanning"
                    self.logger.warning(f"ComparisonWrapper: 回退到Scanning策略掩码结果")
                    return final_result
                else:
                    # 两个策略都失败，返回保守结果
                    from ..models.mask_spec import KeepAll
                    fallback_result = TrimResult(
                        success=False,
                        mask_spec=KeepAll(),
                        preserved_bytes=len(payload),
                        trimmed_bytes=0,
                        confidence=0.0,
                        reason="ComparisonWrapper: 两种策略掩码生成都失败，保守保留全部内容",
                        warnings=["Legacy和Scanning策略都失败"],
                        metadata={'comparison_wrapper': mask_comparison}
                    )
                    self.logger.error(f"ComparisonWrapper: 两种策略都失败，使用保守回退")
                    return fallback_result
                    
        except Exception as e:
            self.logger.error(f"ComparisonWrapper掩码生成异常: {e}", exc_info=True)
            # 异常情况保守处理
            from ..models.mask_spec import KeepAll
            return TrimResult(
                success=False,
                mask_spec=KeepAll(),
                preserved_bytes=len(payload),
                trimmed_bytes=0,
                confidence=0.0,
                reason=f"ComparisonWrapper异常: {str(e)}",
                warnings=["ComparisonWrapper掩码生成异常"],
                metadata={'comparison_error': str(e)}
            )

    def _compare_mask_results(self, legacy_result: 'TrimResult', 
                            scanning_result: 'TrimResult') -> bool:
        """
        比较两种策略的掩码结果是否一致
        
        Args:
            legacy_result: Legacy策略结果
            scanning_result: Scanning策略结果
            
        Returns:
            是否一致
        """
        if not legacy_result or not scanning_result:
            return False
            
        if not (legacy_result.success and scanning_result.success):
            return legacy_result.success == scanning_result.success
        
        # 比较关键指标
        preserved_bytes_diff = abs(legacy_result.preserved_bytes - scanning_result.preserved_bytes)
        preserved_bytes_ratio = preserved_bytes_diff / max(legacy_result.preserved_bytes, 1)
        
        # 允许5%的差异
        if preserved_bytes_ratio > 0.05:
            return False
        
        # 比较置信度差异
        confidence_diff = abs(legacy_result.confidence - scanning_result.confidence)
        if confidence_diff > 0.2:  # 允许20%置信度差异
            return False
        
        return True

    @property
    def priority(self) -> int:
        """返回策略优先级"""
        # 对比包装器使用较高优先级
        return max(self.legacy_strategy.priority, self.scanning_strategy.priority) + 10


class EnhancedStrategyFactory:
    """
    增强策略工厂 - 支持双策略动态选择
    
    在原有策略工厂基础上增加双策略并存、A/B测试、性能对比等功能。
    """
    
    def __init__(self, http_config: Optional['HttpStrategyConfiguration'] = None):
        self.base_factory = ProtocolStrategyFactory()
        if HTTP_STRATEGY_CONFIG_AVAILABLE:
            self.http_config = http_config or get_default_http_strategy_config()
        else:
            self.http_config = None
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        # 策略缓存
        self._legacy_strategy_cache = None
        self._scanning_strategy_cache = None
        
        # 策略实例缓存
        self._legacy_strategy_cache: Optional[BaseStrategy] = None
        self._scanning_strategy_cache: Optional[BaseStrategy] = None
        
    def register_strategy(self, strategy_class: Type[BaseStrategy]) -> None:
        """注册策略类"""
        self.base_factory.register_strategy(strategy_class)
        
    def get_http_strategy(self, protocol_info: ProtocolInfo, 
                         context: TrimContext, config: Dict[str, Any]) -> Optional[BaseStrategy]:
        """智能HTTP策略选择"""
        
        if not HTTP_STRATEGY_CONFIG_AVAILABLE:
            self.logger.warning("HTTP策略配置不可用，回退到基础工厂")
            return self.base_factory.get_best_strategy(protocol_info, context, config)
        
        strategy_mode = self.http_config.strategy.primary_strategy
        
        if strategy_mode == StrategyMode.LEGACY:
            return self._get_legacy_strategy(config)
        elif strategy_mode == StrategyMode.SCANNING:
            return self._get_scanning_strategy(config)
        elif strategy_mode == StrategyMode.AUTO:
            return self._auto_select_strategy(protocol_info, context, config)
        elif strategy_mode == StrategyMode.AB_TEST:
            return self._ab_test_select_strategy(protocol_info, context, config)
        elif strategy_mode == StrategyMode.COMPARISON:
            return self._comparison_mode_strategy(protocol_info, context, config)
        else:
            # 默认回退到Legacy策略
            self.logger.warning(f"未知策略模式: {strategy_mode}，回退到Legacy")
            return self._get_legacy_strategy(config)
    
    def _get_legacy_strategy(self, config: Dict[str, Any]) -> Optional[BaseStrategy]:
        """获取Legacy策略实例"""
        if self._legacy_strategy_cache is None:
            self._legacy_strategy_cache = self.base_factory.get_strategy_by_name(
                "http", config
            )
        return self._legacy_strategy_cache
    
    def _get_scanning_strategy(self, config: Dict[str, Any]) -> Optional[BaseStrategy]:
        """获取Scanning策略实例"""
        if self._scanning_strategy_cache is None:
            self._scanning_strategy_cache = self.base_factory.get_strategy_by_name(
                "http_scanning", config
            )
        return self._scanning_strategy_cache
    
    def _ab_test_select_strategy(self, protocol_info: ProtocolInfo, 
                               context: TrimContext, config: Dict[str, Any]) -> Optional[BaseStrategy]:
        """A/B测试策略选择"""
        
        if not self.http_config.strategy.enable_ab_testing:
            return self._get_legacy_strategy(config)
        
        use_scanning = self.http_config.should_use_scanning_strategy(context.input_file)
        
        if use_scanning:
            self.logger.info(f"A/B测试: 选择Scanning策略处理 {context.input_file}")
            return self._get_scanning_strategy(config)
        else:
            self.logger.info(f"A/B测试: 选择Legacy策略处理 {context.input_file}")
            return self._get_legacy_strategy(config)
    
    def _comparison_mode_strategy(self, protocol_info: ProtocolInfo,
                                context: TrimContext, config: Dict[str, Any]) -> Optional[BaseStrategy]:
        """性能对比模式 - 同时运行两种策略进行对比"""
        
        legacy_strategy = self._get_legacy_strategy(config)
        scanning_strategy = self._get_scanning_strategy(config)
        
        if not legacy_strategy or not scanning_strategy:
            self.logger.warning("无法创建对比策略，回退到可用策略")
            return legacy_strategy or scanning_strategy
        
        return ComparisonWrapper(
            legacy_strategy=legacy_strategy,
            scanning_strategy=scanning_strategy,
            config=config,
            http_config=self.http_config
        )
    
    def _auto_select_strategy(self, protocol_info: ProtocolInfo,
                            context: TrimContext, config: Dict[str, Any]) -> Optional[BaseStrategy]:
        """自动策略选择"""
        
        # 自动选择逻辑可以基于文件大小、协议复杂度等因素
        # 目前先简单返回Legacy策略，后续可以扩展智能选择算法
        
        use_scanning = self.http_config._auto_selection(context.input_file)
        
        if use_scanning:
            return self._get_scanning_strategy(config)
        else:
            return self._get_legacy_strategy(config)
    
    def get_strategy_for_protocol(self, protocol_info: ProtocolInfo,
                                 context: TrimContext, config: Dict[str, Any]) -> Optional[BaseStrategy]:
        """为指定协议获取最佳策略"""
        
        # 如果是HTTP协议，使用增强的HTTP策略选择
        if protocol_info.name.lower() in ['http', 'https']:
            return self.get_http_strategy(protocol_info, context, config)
        else:
            # 其他协议使用基础工厂
            return self.base_factory.get_best_strategy(protocol_info, context, config)
    
    def update_config(self, http_config: 'HttpStrategyConfiguration'):
        """更新HTTP策略配置"""
        self.http_config = http_config
        # 清空缓存，强制重新创建策略实例
        self._legacy_strategy_cache = None
        self._scanning_strategy_cache = None
    
    def get_comparison_data(self) -> List[Dict[str, Any]]:
        """获取性能对比数据"""
        comparison_data = []
        
        # 从ComparisonWrapper实例收集数据
        for strategy_name in self.base_factory.registry.list_all_strategies():
            strategy = self.base_factory.create_strategy(strategy_name, {})
            if isinstance(strategy, ComparisonWrapper):
                comparison_data.extend(strategy.comparison_data)
        
        return comparison_data


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
            from .http_scanning_strategy import HTTPScanningStrategy
            self.register_strategy(HTTPScanningStrategy)
            self.logger.info("已注册HTTPScanningStrategy")
        except ImportError as e:
            self.logger.warning(f"无法导入HTTPScanningStrategy: {e}")
            
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
_enhanced_strategy_factory = None


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


def get_enhanced_strategy_factory(http_config: Optional['HttpStrategyConfiguration'] = None) -> EnhancedStrategyFactory:
    """
    获取增强策略工厂实例
    
    Args:
        http_config: HTTP策略配置，如果为None则使用默认配置
        
    Returns:
        增强策略工厂实例
    """
    global _enhanced_strategy_factory
    if _enhanced_strategy_factory is None:
        _enhanced_strategy_factory = EnhancedStrategyFactory(http_config)
        _enhanced_strategy_factory.base_factory.auto_register_strategies()
    elif http_config is not None:
        _enhanced_strategy_factory.update_config(http_config)
    return _enhanced_strategy_factory


def register_strategy(strategy_class: Type[BaseStrategy]) -> None:
    """
    便捷的策略注册函数
    
    Args:
        strategy_class: 策略类
    """
    factory = get_strategy_factory()
    factory.register_strategy(strategy_class) 