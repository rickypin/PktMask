#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
算法配置集成适配器 - Phase 6.3
将配置管理器与插件系统集成，支持插件配置的热更新
"""

import threading
from typing import Dict, List, Optional, Any, Set
from datetime import datetime

from .enhanced_plugin_manager import EnhancedPluginManager, PluginRegistration
from ..interfaces.algorithm_interface import (
    AlgorithmInterface, AlgorithmConfig, AlgorithmType, AlgorithmInfo
)
from ...config.config_manager import (
    AlgorithmConfigManager, ConfigChangeEvent, get_config_manager
)
from ...config.algorithm_configs import AlgorithmConfigFactory
from ...infrastructure.logging import get_logger


class ConfiguredAlgorithmProxy:
    """配置化算法代理"""
    
    def __init__(
        self,
        algorithm: AlgorithmInterface,
        config_name: str,
        config_manager: AlgorithmConfigManager
    ):
        self._algorithm = algorithm
        self._config_name = config_name
        self._config_manager = config_manager
        self._logger = get_logger(f'config.proxy.{config_name}')
        
        # 缓存当前配置
        self._current_config = self._config_manager.get_config(config_name)
        
        # 监听配置变更
        self._config_manager.add_change_handler(self._on_config_changed)
    
    def _on_config_changed(self, event: ConfigChangeEvent):
        """处理配置变更事件"""
        if event.config_name == self._config_name:
            self._logger.info(f"配置 {self._config_name} 发生变更: {event.change_type}")
            
            if event.change_type == "updated":
                # 热更新算法配置
                try:
                    if hasattr(self._algorithm, 'update_config'):
                        self._algorithm.update_config(event.new_config)
                        self._current_config = event.new_config
                        self._logger.info(f"成功热更新算法配置: {self._config_name}")
                    else:
                        self._logger.warning(f"算法 {self._algorithm.get_info().name} 不支持配置热更新")
                except Exception as e:
                    self._logger.error(f"配置热更新失败: {e}")
    
    def __getattr__(self, name):
        """代理方法调用"""
        return getattr(self._algorithm, name)
    
    def get_current_config(self) -> Optional[AlgorithmConfig]:
        """获取当前配置"""
        return self._current_config


class AlgorithmConfigIntegrator:
    """算法配置集成器"""
    
    def __init__(
        self,
        plugin_manager: Optional[EnhancedPluginManager] = None,
        config_manager: Optional[AlgorithmConfigManager] = None
    ):
        self._plugin_manager = plugin_manager
        self._config_manager = config_manager or get_config_manager()
        self._logger = get_logger('config.integrator')
        
        # 配置化算法注册表
        self._configured_algorithms: Dict[str, ConfiguredAlgorithmProxy] = {}
        self._algorithm_configs: Dict[str, str] = {}  # algorithm_id -> config_name
        
        # 线程安全
        self._lock = threading.RLock()
        
        # 监听配置变更
        self._config_manager.add_change_handler(self._on_config_changed)
        
        self._logger.info("算法配置集成器初始化完成")
    
    def register_algorithm_with_config(
        self,
        algorithm_id: str,
        algorithm: AlgorithmInterface,
        config_name: Optional[str] = None,
        config_data: Optional[Dict[str, Any]] = None,
        template_name: Optional[str] = None
    ) -> ConfiguredAlgorithmProxy:
        """
        注册带配置的算法
        
        Args:
            algorithm_id: 算法ID
            algorithm: 算法实例
            config_name: 配置名称
            config_data: 配置数据
            template_name: 模板名称
            
        Returns:
            ConfiguredAlgorithmProxy: 配置化算法代理
        """
        with self._lock:
            if algorithm_id in self._configured_algorithms:
                raise ValueError(f"算法 {algorithm_id} 已注册")
            
            # 确定配置名称
            if config_name is None:
                config_name = f"{algorithm_id}_config"
            
            # 获取算法信息
            algorithm_info = algorithm.get_algorithm_info()
            algorithm_type = self._determine_algorithm_type(algorithm_info)
            
            # 创建或获取配置
            existing_config = self._config_manager.get_config(config_name)
            if existing_config is None:
                # 创建新配置
                if template_name:
                    config = self._config_manager.create_config(
                        name=config_name,
                        algorithm_type=algorithm_type,
                        template_name=template_name,
                        config_data=config_data
                    )
                else:
                    config = self._config_manager.create_config(
                        name=config_name,
                        algorithm_type=algorithm_type,
                        config_data=config_data or {}
                    )
            else:
                config = existing_config
            
            # 应用配置到算法
            if hasattr(algorithm, 'update_config'):
                algorithm.update_config(config)
            
            # 创建配置化代理
            proxy = ConfiguredAlgorithmProxy(algorithm, config_name, self._config_manager)
            
            # 注册
            self._configured_algorithms[algorithm_id] = proxy
            self._algorithm_configs[algorithm_id] = config_name
            
            # 如果有插件管理器，也注册到插件系统
            if self._plugin_manager:
                self._plugin_manager.register_algorithm(algorithm_id, algorithm)
            
            self._logger.info(f"注册配置化算法: {algorithm_id} (配置: {config_name})")
            return proxy
    
    def unregister_algorithm(self, algorithm_id: str) -> bool:
        """
        注销算法
        
        Args:
            algorithm_id: 算法ID
            
        Returns:
            bool: 注销是否成功
        """
        with self._lock:
            if algorithm_id not in self._configured_algorithms:
                return False
            
            # 移除配置监听
            proxy = self._configured_algorithms[algorithm_id]
            config_name = self._algorithm_configs[algorithm_id]
            
            # 从插件管理器注销
            if self._plugin_manager:
                self._plugin_manager.unregister_algorithm(algorithm_id)
            
            # 清理
            del self._configured_algorithms[algorithm_id]
            del self._algorithm_configs[algorithm_id]
            
            self._logger.info(f"注销配置化算法: {algorithm_id}")
            return True
    
    def get_configured_algorithm(self, algorithm_id: str) -> Optional[ConfiguredAlgorithmProxy]:
        """获取配置化算法代理"""
        with self._lock:
            return self._configured_algorithms.get(algorithm_id)
    
    def update_algorithm_config(
        self,
        algorithm_id: str,
        config_data: Dict[str, Any],
        comment: Optional[str] = None
    ) -> bool:
        """
        更新算法配置
        
        Args:
            algorithm_id: 算法ID
            config_data: 新配置数据
            comment: 变更注释
            
        Returns:
            bool: 更新是否成功
        """
        with self._lock:
            if algorithm_id not in self._algorithm_configs:
                return False
            
            config_name = self._algorithm_configs[algorithm_id]
            
            try:
                self._config_manager.update_config(
                    name=config_name,
                    config_data=config_data,
                    comment=comment
                )
                return True
            except Exception as e:
                self._logger.error(f"更新算法配置失败 {algorithm_id}: {e}")
                return False
    
    def get_algorithm_config(self, algorithm_id: str) -> Optional[AlgorithmConfig]:
        """获取算法配置"""
        with self._lock:
            if algorithm_id not in self._algorithm_configs:
                return None
            
            config_name = self._algorithm_configs[algorithm_id]
            return self._config_manager.get_config(config_name)
    
    def list_configured_algorithms(self) -> List[str]:
        """列出所有配置化算法ID"""
        with self._lock:
            return list(self._configured_algorithms.keys())
    
    def _determine_algorithm_type(self, algorithm_info: AlgorithmInfo) -> AlgorithmType:
        """根据算法信息确定算法类型"""
        # 根据算法名称或描述推断类型
        name_lower = algorithm_info.name.lower()
        description_lower = algorithm_info.description.lower()
        
        if any(keyword in name_lower or keyword in description_lower 
               for keyword in ['ip', 'anonymization', 'anonymize']):
            return AlgorithmType.IP_ANONYMIZATION
        elif any(keyword in name_lower or keyword in description_lower 
                 for keyword in ['packet', 'processing', 'trim', 'filter']):
            return AlgorithmType.PACKET_PROCESSING
        elif any(keyword in name_lower or keyword in description_lower 
                 for keyword in ['dedup', 'duplicate', 'unique']):
            return AlgorithmType.DEDUPLICATION
        else:
            return AlgorithmType.CUSTOM
    
    def _on_config_changed(self, event: ConfigChangeEvent):
        """处理配置变更事件"""
        # 查找使用该配置的算法
        affected_algorithms = [
            alg_id for alg_id, config_name in self._algorithm_configs.items()
            if config_name == event.config_name
        ]
        
        if affected_algorithms:
            self._logger.info(f"配置 {event.config_name} 变更影响算法: {affected_algorithms}")
    
    def create_algorithm_config_from_template(
        self,
        algorithm_id: str,
        template_name: str,
        config_name: Optional[str] = None,
        overrides: Optional[Dict[str, Any]] = None
    ) -> AlgorithmConfig:
        """
        从模板创建算法配置
        
        Args:
            algorithm_id: 算法ID
            template_name: 模板名称
            config_name: 配置名称
            overrides: 覆盖参数
            
        Returns:
            AlgorithmConfig: 创建的配置
        """
        if config_name is None:
            config_name = f"{algorithm_id}_config"
        
        # 从模板创建配置
        config = self._config_manager._template_manager.create_config_from_template(
            template_name,
            overrides
        )
        
        # 获取算法类型
        template = self._config_manager._template_manager.get_template(template_name)
        if template is None:
            raise ValueError(f"模板不存在: {template_name}")
        
        # 保存配置
        return self._config_manager.create_config(
            name=config_name,
            algorithm_type=template.algorithm_type,
            config_data=config.dict()
        )
    
    def export_algorithm_configs(
        self,
        output_dir: str,
        format: str = "json"
    ):
        """
        导出所有算法配置
        
        Args:
            output_dir: 输出目录
            format: 导出格式
        """
        from pathlib import Path
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        with self._lock:
            for algorithm_id, config_name in self._algorithm_configs.items():
                output_file = output_path / f"{algorithm_id}_config.{format}"
                self._config_manager.export_config(
                    name=config_name,
                    file_path=output_file,
                    format=format
                )
        
        self._logger.info(f"导出 {len(self._algorithm_configs)} 个算法配置到: {output_dir}")
    
    def import_algorithm_configs(self, config_dir: str):
        """
        导入算法配置
        
        Args:
            config_dir: 配置目录
        """
        from pathlib import Path
        
        config_path = Path(config_dir)
        if not config_path.exists():
            raise FileNotFoundError(f"配置目录不存在: {config_dir}")
        
        imported_count = 0
        for config_file in config_path.glob("*.*"):
            if config_file.suffix.lower() in ['.json', '.yaml', '.yml', '.toml']:
                try:
                    self._config_manager.load_config_from_file(config_file)
                    imported_count += 1
                except Exception as e:
                    self._logger.error(f"导入配置文件失败 {config_file}: {e}")
        
        self._logger.info(f"成功导入 {imported_count} 个配置文件")
    
    def get_integration_stats(self) -> Dict[str, Any]:
        """获取集成统计信息"""
        with self._lock:
            return {
                "configured_algorithms": len(self._configured_algorithms),
                "algorithm_configs": len(self._algorithm_configs),
                "algorithm_list": list(self._configured_algorithms.keys()),
                "config_manager_stats": self._config_manager.get_manager_stats()
            }
    
    def cleanup(self):
        """清理资源"""
        with self._lock:
            # 注销所有算法
            algorithm_ids = list(self._configured_algorithms.keys())
            for algorithm_id in algorithm_ids:
                self.unregister_algorithm(algorithm_id)
            
            # 移除配置变更监听
            self._config_manager.remove_change_handler(self._on_config_changed)
        
        self._logger.info("配置集成器资源已清理")


# 全局配置集成器实例
_config_integrator: Optional[AlgorithmConfigIntegrator] = None


def get_config_integrator(
    plugin_manager: Optional[EnhancedPluginManager] = None
) -> AlgorithmConfigIntegrator:
    """获取全局配置集成器实例"""
    global _config_integrator
    if _config_integrator is None:
        _config_integrator = AlgorithmConfigIntegrator(plugin_manager)
    return _config_integrator 