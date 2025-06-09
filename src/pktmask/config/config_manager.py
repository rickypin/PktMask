#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
配置管理器 - Phase 6.3
支持配置热更新、验证、导入导出和监控功能
"""

import os
import json
import yaml
import toml
import threading
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Set, Union
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from .algorithm_configs import (
    AlgorithmConfigFactory, ConfigTemplateManager, ConfigTemplate,
    config_template_manager
)
from ..algorithms.interfaces.algorithm_interface import (
    AlgorithmConfig, AlgorithmType, ValidationResult
)
from pydantic import BaseModel
from ..infrastructure.logging import get_logger


@dataclass
class ConfigVersion:
    """配置版本信息"""
    version: str
    timestamp: datetime
    config_hash: str
    comment: Optional[str] = None
    author: Optional[str] = None


@dataclass
class ConfigChangeEvent:
    """配置变更事件"""
    config_name: str
    old_config: Optional[AlgorithmConfig]
    new_config: AlgorithmConfig
    change_type: str  # created, updated, deleted
    timestamp: datetime
    source: str  # file, api, template, etc.


class ConfigFileWatcher(FileSystemEventHandler):
    """配置文件监控器"""
    
    def __init__(self, config_manager):
        self._config_manager = config_manager
        self._logger = get_logger('config.watcher')
    
    def on_modified(self, event):
        """文件修改事件"""
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        if file_path.suffix.lower() in ['.json', '.yaml', '.yml', '.toml']:
            self._logger.info(f"检测到配置文件变更: {file_path}")
            self._config_manager._handle_file_change(file_path)


class AlgorithmConfigManager:
    """算法配置管理器"""
    
    def __init__(self, config_directory: Optional[str] = None):
        self._logger = get_logger('config.manager')
        
        # 配置存储
        self._configs: Dict[str, AlgorithmConfig] = {}
        self._config_types: Dict[str, AlgorithmType] = {}
        self._config_versions: Dict[str, List[ConfigVersion]] = defaultdict(list)
        self._config_metadata: Dict[str, Dict[str, Any]] = {}
        
        # 配置文件管理
        self._config_directory = Path(config_directory or "configs")
        self._config_directory.mkdir(parents=True, exist_ok=True)
        
        # 文件监控
        self._file_watcher = ConfigFileWatcher(self)
        self._observer: Optional[Observer] = None
        self._watched_files: Set[Path] = set()
        
        # 事件处理
        self._change_handlers: List[Callable[[ConfigChangeEvent], None]] = []
        self._validation_handlers: Dict[AlgorithmType, List[Callable]] = defaultdict(list)
        
        # 线程安全
        self._lock = threading.RLock()
        
        # 模板管理器
        self._template_manager = config_template_manager
        
        self._logger.info("算法配置管理器初始化完成")
    
    def start_watching(self):
        """开始监控配置文件变更"""
        if self._observer is None:
            self._observer = Observer()
            self._observer.schedule(
                self._file_watcher,
                str(self._config_directory),
                recursive=True
            )
            self._observer.start()
            self._logger.info(f"开始监控配置目录: {self._config_directory}")
    
    def stop_watching(self):
        """停止监控配置文件变更"""
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None
            self._logger.info("停止配置文件监控")
    
    # ===== 配置管理核心方法 =====
    
    def create_config(
        self,
        name: str,
        algorithm_type: AlgorithmType,
        config_data: Optional[Dict[str, Any]] = None,
        template_name: Optional[str] = None,
        save_to_file: bool = True
    ) -> AlgorithmConfig:
        """
        创建新配置
        
        Args:
            name: 配置名称
            algorithm_type: 算法类型
            config_data: 配置数据
            template_name: 模板名称
            save_to_file: 是否保存到文件
            
        Returns:
            AlgorithmConfig: 创建的配置实例
        """
        with self._lock:
            if name in self._configs:
                raise ValueError(f"配置 {name} 已存在")
            
            # 从模板创建或使用提供的数据
            if template_name:
                config = self._template_manager.create_config_from_template(
                    template_name,
                    config_data
                )
            else:
                config_data = config_data or {}
                config = AlgorithmConfigFactory.create_config(
                    algorithm_type,
                    **config_data
                )
            
            # 验证配置
            validation_result = self._validate_config(name, config, algorithm_type)
            if not validation_result.is_valid:
                raise ValueError(f"配置验证失败: {validation_result.errors}")
            
            # 存储配置
            self._configs[name] = config
            self._config_types[name] = algorithm_type
            
            # 创建版本记录
            version = self._create_version(config, "初始创建")
            self._config_versions[name].append(version)
            
            # 保存到文件
            if save_to_file:
                self._save_config_to_file(name, config, algorithm_type)
            
            # 触发事件
            self._trigger_change_event(ConfigChangeEvent(
                config_name=name,
                old_config=None,
                new_config=config,
                change_type="created",
                timestamp=datetime.now(),
                source="api"
            ))
            
            self._logger.info(f"创建配置: {name} (类型: {algorithm_type.value})")
            return config
    
    def update_config(
        self,
        name: str,
        config_data: Dict[str, Any],
        comment: Optional[str] = None,
        save_to_file: bool = True
    ) -> AlgorithmConfig:
        """
        更新配置
        
        Args:
            name: 配置名称
            config_data: 新的配置数据
            comment: 变更注释
            save_to_file: 是否保存到文件
            
        Returns:
            AlgorithmConfig: 更新后的配置
        """
        with self._lock:
            if name not in self._configs:
                raise ValueError(f"配置 {name} 不存在")
            
            old_config = self._configs[name]
            algorithm_type = self._config_types[name]
            
            # 创建新配置
            old_data = old_config.dict()
            old_data.update(config_data)
            new_config = AlgorithmConfigFactory.create_config(
                algorithm_type,
                **old_data
            )
            
            # 验证配置
            validation_result = self._validate_config(name, new_config, algorithm_type)
            if not validation_result.is_valid:
                raise ValueError(f"配置验证失败: {validation_result.errors}")
            
            # 更新配置
            self._configs[name] = new_config
            
            # 创建版本记录
            version = self._create_version(new_config, comment or "配置更新")
            self._config_versions[name].append(version)
            
            # 保存到文件
            if save_to_file:
                self._save_config_to_file(name, new_config, algorithm_type)
            
            # 触发事件
            self._trigger_change_event(ConfigChangeEvent(
                config_name=name,
                old_config=old_config,
                new_config=new_config,
                change_type="updated",
                timestamp=datetime.now(),
                source="api"
            ))
            
            self._logger.info(f"更新配置: {name}")
            return new_config
    
    def get_config(self, name: str) -> Optional[AlgorithmConfig]:
        """获取配置"""
        with self._lock:
            return self._configs.get(name)
    
    def delete_config(self, name: str, delete_file: bool = True) -> bool:
        """
        删除配置
        
        Args:
            name: 配置名称
            delete_file: 是否删除配置文件
            
        Returns:
            bool: 删除是否成功
        """
        with self._lock:
            if name not in self._configs:
                return False
            
            old_config = self._configs[name]
            
            # 删除配置
            del self._configs[name]
            del self._config_types[name]
            if name in self._config_versions:
                del self._config_versions[name]
            if name in self._config_metadata:
                del self._config_metadata[name]
            
            # 删除文件
            if delete_file:
                config_file = self._get_config_file_path(name)
                if config_file.exists():
                    config_file.unlink()
                    self._watched_files.discard(config_file)
            
            # 触发事件
            self._trigger_change_event(ConfigChangeEvent(
                config_name=name,
                old_config=old_config,
                new_config=None,
                change_type="deleted",
                timestamp=datetime.now(),
                source="api"
            ))
            
            self._logger.info(f"删除配置: {name}")
            return True
    
    def list_configs(
        self,
        algorithm_type: Optional[AlgorithmType] = None
    ) -> List[str]:
        """
        列出配置名称
        
        Args:
            algorithm_type: 筛选的算法类型
            
        Returns:
            List[str]: 配置名称列表
        """
        with self._lock:
            if algorithm_type is None:
                return list(self._configs.keys())
            else:
                return [
                    name for name, config_type in self._config_types.items()
                    if config_type == algorithm_type
                ]
    
    # ===== 配置验证 =====
    
    def _validate_config(
        self,
        name: str,
        config: AlgorithmConfig,
        algorithm_type: AlgorithmType
    ) -> ValidationResult:
        """验证配置"""
        result = ValidationResult(is_valid=True)
        
        # 基础验证
        try:
            config.dict()  # Pydantic自动验证
        except Exception as e:
            result.add_error(f"配置格式错误: {e}")
            return result
        
        # 算法类型特定验证
        handlers = self._validation_handlers.get(algorithm_type, [])
        for handler in handlers:
            try:
                handler_result = handler(name, config)
                if not handler_result.is_valid:
                    result.errors.extend(handler_result.errors)
                    result.warnings.extend(handler_result.warnings)
                    result.is_valid = False
            except Exception as e:
                result.add_error(f"验证处理器错误: {e}")
        
        return result
    
    def add_validation_handler(
        self,
        algorithm_type: AlgorithmType,
        handler: Callable[[str, AlgorithmConfig], ValidationResult]
    ):
        """添加配置验证处理器"""
        self._validation_handlers[algorithm_type].append(handler)
    
    # ===== 配置版本管理 =====
    
    def _create_version(
        self,
        config: AlgorithmConfig,
        comment: str
    ) -> ConfigVersion:
        """创建配置版本"""
        config_json = json.dumps(config.dict(), sort_keys=True)
        config_hash = hashlib.sha256(config_json.encode()).hexdigest()[:16]
        
        return ConfigVersion(
            version=f"v{len(self._config_versions) + 1}",
            timestamp=datetime.now(),
            config_hash=config_hash,
            comment=comment
        )
    
    def get_config_versions(self, name: str) -> List[ConfigVersion]:
        """获取配置版本历史"""
        with self._lock:
            return self._config_versions.get(name, []).copy()
    
    # ===== 文件操作 =====
    
    def _get_config_file_path(self, name: str) -> Path:
        """获取配置文件路径"""
        return self._config_directory / f"{name}.json"
    
    def _save_config_to_file(
        self,
        name: str,
        config: AlgorithmConfig,
        algorithm_type: AlgorithmType
    ):
        """保存配置到文件"""
        config_file = self._get_config_file_path(name)
        
        config_data = {
            "name": name,
            "algorithm_type": algorithm_type.value,
            "config": config.dict(),
            "metadata": {
                "created_at": datetime.now().isoformat(),
                "version": self._config_versions[name][-1].version if name in self._config_versions else "v1"
            }
        }
        
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)
        
        self._watched_files.add(config_file)
    
    def load_config_from_file(self, file_path: Union[str, Path]) -> str:
        """
        从文件加载配置
        
        Args:
            file_path: 配置文件路径
            
        Returns:
            str: 加载的配置名称
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {file_path}")
        
        # 根据文件扩展名选择解析器
        if file_path.suffix.lower() == '.json':
            with open(file_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
        elif file_path.suffix.lower() in ['.yaml', '.yml']:
            with open(file_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
        elif file_path.suffix.lower() == '.toml':
            with open(file_path, 'r', encoding='utf-8') as f:
                config_data = toml.load(f)
        else:
            raise ValueError(f"不支持的配置文件格式: {file_path.suffix}")
        
        # 解析配置数据
        name = config_data.get('name')
        if not name:
            name = file_path.stem
        
        algorithm_type_str = config_data.get('algorithm_type')
        if not algorithm_type_str:
            raise ValueError("配置文件缺少 algorithm_type 字段")
        
        algorithm_type = AlgorithmType(algorithm_type_str)
        config_dict = config_data.get('config', {})
        
        # 创建配置
        config = AlgorithmConfigFactory.create_config(algorithm_type, **config_dict)
        
        with self._lock:
            # 如果配置已存在，更新它
            if name in self._configs:
                old_config = self._configs[name]
                self._configs[name] = config
                
                # 创建版本记录
                version = self._create_version(config, f"从文件加载: {file_path.name}")
                self._config_versions[name].append(version)
                
                # 触发更新事件
                self._trigger_change_event(ConfigChangeEvent(
                    config_name=name,
                    old_config=old_config,
                    new_config=config,
                    change_type="updated",
                    timestamp=datetime.now(),
                    source="file"
                ))
            else:
                # 创建新配置
                self._configs[name] = config
                self._config_types[name] = algorithm_type
                
                # 创建版本记录
                version = self._create_version(config, f"从文件加载: {file_path.name}")
                self._config_versions[name].append(version)
                
                # 触发创建事件
                self._trigger_change_event(ConfigChangeEvent(
                    config_name=name,
                    old_config=None,
                    new_config=config,
                    change_type="created",
                    timestamp=datetime.now(),
                    source="file"
                ))
        
        self._watched_files.add(file_path)
        self._logger.info(f"从文件加载配置: {name} (类型: {algorithm_type.value})")
        return name
    
    def export_config(
        self,
        name: str,
        file_path: Union[str, Path],
        format: str = "json"
    ):
        """
        导出配置到文件
        
        Args:
            name: 配置名称
            file_path: 导出文件路径
            format: 导出格式 (json, yaml, toml)
        """
        with self._lock:
            if name not in self._configs:
                raise ValueError(f"配置 {name} 不存在")
            
            config = self._configs[name]
            algorithm_type = self._config_types[name]
            
            export_data = {
                "name": name,
                "algorithm_type": algorithm_type.value,
                "config": config.dict(),
                "metadata": {
                    "exported_at": datetime.now().isoformat(),
                    "version": self._config_versions[name][-1].version if name in self._config_versions else "v1"
                }
            }
            
            file_path = Path(file_path)
            
            if format.lower() == "json":
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=2, ensure_ascii=False)
            elif format.lower() in ["yaml", "yml"]:
                with open(file_path, 'w', encoding='utf-8') as f:
                    yaml.dump(export_data, f, default_flow_style=False, allow_unicode=True)
            elif format.lower() == "toml":
                with open(file_path, 'w', encoding='utf-8') as f:
                    toml.dump(export_data, f)
            else:
                raise ValueError(f"不支持的导出格式: {format}")
            
            self._logger.info(f"导出配置 {name} 到文件: {file_path}")
    
    def _handle_file_change(self, file_path: Path):
        """处理文件变更"""
        try:
            self.load_config_from_file(file_path)
        except Exception as e:
            self._logger.error(f"处理文件变更失败 {file_path}: {e}")
    
    # ===== 事件处理 =====
    
    def _trigger_change_event(self, event: ConfigChangeEvent):
        """触发配置变更事件"""
        for handler in self._change_handlers:
            try:
                handler(event)
            except Exception as e:
                self._logger.error(f"配置变更事件处理失败: {e}")
    
    def add_change_handler(self, handler: Callable[[ConfigChangeEvent], None]):
        """添加配置变更事件处理器"""
        self._change_handlers.append(handler)
    
    def remove_change_handler(self, handler: Callable[[ConfigChangeEvent], None]):
        """移除配置变更事件处理器"""
        if handler in self._change_handlers:
            self._change_handlers.remove(handler)
    
    # ===== 统计和监控 =====
    
    def get_manager_stats(self) -> Dict[str, Any]:
        """获取管理器统计信息"""
        with self._lock:
            stats = {
                "total_configs": len(self._configs),
                "configs_by_type": {},
                "watched_files": len(self._watched_files),
                "total_versions": sum(len(versions) for versions in self._config_versions.values()),
                "change_handlers": len(self._change_handlers)
            }
            
            # 按类型统计
            for algorithm_type in AlgorithmType:
                count = sum(1 for config_type in self._config_types.values() if config_type == algorithm_type)
                if count > 0:
                    stats["configs_by_type"][algorithm_type.value] = count
            
            return stats
    
    def cleanup(self):
        """清理资源"""
        self.stop_watching()
        with self._lock:
            self._configs.clear()
            self._config_types.clear()
            self._config_versions.clear()
            self._config_metadata.clear()
            self._watched_files.clear()
        self._logger.info("配置管理器资源已清理")


# 全局配置管理器实例
_config_manager: Optional[AlgorithmConfigManager] = None


def get_config_manager() -> AlgorithmConfigManager:
    """获取全局配置管理器实例"""
    global _config_manager
    if _config_manager is None:
        _config_manager = AlgorithmConfigManager()
    return _config_manager


class ConfigManager:
    """配置管理器 - 为测试兼容性提供的简化接口"""
    
    def __init__(self, config_dir: Optional[Union[str, Path]] = None):
        """初始化配置管理器"""
        if config_dir is None:
            config_dir = Path.cwd() / "configs"
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(exist_ok=True, parents=True)
        
        # 内部使用AlgorithmConfigManager
        self._algorithm_manager = AlgorithmConfigManager()
    
    def save_config(self, config: BaseModel, filename: str, format: str = "json") -> str:
        """保存配置到文件"""
        config_path = self.config_dir / filename
        
        if format.lower() == "json":
            import json
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config.model_dump(), f, indent=2, ensure_ascii=False)
        elif format.lower() in ["yaml", "yml"]:
            import yaml
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config.model_dump(), f, default_flow_style=False, allow_unicode=True)
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        # 返回配置版本（简化版本号）
        import hashlib
        config_hash = hashlib.md5(str(config.model_dump()).encode()).hexdigest()[:8]
        return f"v{config_hash}"
    
    def load_config(self, filename: str, config_class: type) -> BaseModel:
        """从文件加载配置"""
        config_path = self.config_dir / filename
        
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        if filename.endswith('.json'):
            import json
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        elif filename.endswith(('.yaml', '.yml')):
            import yaml
            with open(config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
        else:
            raise ValueError(f"Unsupported file format: {filename}")
        
        return config_class(**data)
    
    def get_config(self, filename: str, config_class: type) -> BaseModel:
        """获取配置（load_config的别名）"""
        return self.load_config(filename, config_class)
    
    def get_template(self, template_name: str) -> Optional[BaseModel]:
        """获取配置模板"""
        from .algorithm_configs import IPAnonymizationConfig, DeduplicationConfig, PacketProcessingConfig
        
        templates = {
            'ip_anonymization': IPAnonymizationConfig(),
            'deduplication': DeduplicationConfig(),
            'packet_processing': PacketProcessingConfig()
        }
        
        return templates.get(template_name)
    
    def get_config_versions(self, filename: str) -> List[str]:
        """获取配置版本历史（简化实现）"""
        # 简化实现，返回当前版本
        config_path = self.config_dir / filename
        if config_path.exists():
            import hashlib
            with open(config_path, 'rb') as f:
                file_hash = hashlib.md5(f.read()).hexdigest()[:8]
            return [f"v{file_hash}"]
        return []
    
    def register_hot_reload(self, filename: str, callback):
        """注册热重载回调（占位实现）"""
        # 简化实现，实际项目中可以实现文件监听
        pass 