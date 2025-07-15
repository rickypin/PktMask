"""
简化的处理器注册表

替代复杂的插件发现、依赖管理、沙箱等企业级功能，
使用简单直观的注册表模式。
"""
from typing import Dict, Type, List, Optional
from .base_processor import BaseProcessor, ProcessorConfig


class ProcessorRegistry:
    """处理器注册表
    
    简单的注册表系统，替代复杂的插件管理架构。
    支持基本的处理器注册、获取和发现功能。
    """
    
    # 内置处理器映射 (延迟导入避免循环依赖)
    _processors: Dict[str, Type[BaseProcessor]] = {}
    _loaded = False
    
    @classmethod
    def _load_builtin_processors(cls):
        """延迟加载内置处理器"""
        if cls._loaded:
            return
            
        try:
            # 延迟导入避免循环依赖
            from .ip_anonymizer import IPAnonymizer
            from .deduplicator import Deduplicator
            from .masker import Masker
            # 旧版处理器已移除，使用新版双模块架构
            from ..pipeline.stages.mask_payload_v2.stage import NewMaskPayloadStage as MaskingProcessor
            
            cls._processors.update({
                # 标准命名键（与GUI界面一致）
                'anonymize_ips': IPAnonymizer,
                'remove_dupes': Deduplicator,
                'mask_payloads': MaskingProcessor,

                # 旧键 → 别名，保持向后兼容并抛出 DeprecationWarning
                'anon_ip': IPAnonymizer,
                'dedup_packet': Deduplicator,
                'mask_payload': MaskingProcessor,
            })
            cls._loaded = True
            
        except ImportError as e:
            print(f"Error loading built-in processors: {e}")
            print("Warning: Unable to load payload trimming processor")
    
    @classmethod
    def get_processor(cls, name: str, config: ProcessorConfig) -> BaseProcessor:
        """获取处理器实例"""
        cls._load_builtin_processors()
        
        if name not in cls._processors:
            available = list(cls._processors.keys())
            raise ValueError(f"未知处理器: {name}。可用处理器: {available}")
            
        processor_class = cls._processors[name]
        return processor_class(config)
    
    @classmethod
    def register_processor(cls, name: str, processor_class: Type[BaseProcessor]):
        """注册新的处理器"""
        if not issubclass(processor_class, BaseProcessor):
            raise TypeError(f"处理器类必须继承自BaseProcessor: {processor_class}")
            
        cls._processors[name] = processor_class
        print(f"已注册处理器: {name} -> {processor_class.__name__}")
    
    @classmethod
    def list_processors(cls) -> List[str]:
        """列出所有可用处理器"""
        cls._load_builtin_processors()
        return list(cls._processors.keys())
    
    @classmethod
    def get_processor_info(cls, name: str) -> Dict[str, str]:
        """获取处理器信息"""
        cls._load_builtin_processors()
        
        if name not in cls._processors:
            raise ValueError(f"未知处理器: {name}")
            
        processor_class = cls._processors[name]
        
        # 创建临时实例获取信息
        temp_config = ProcessorConfig(name=name)
        temp_instance = processor_class(temp_config)
        
        return {
            'name': name,
            'display_name': temp_instance.get_display_name(),
            'description': temp_instance.get_description(),
            'class': processor_class.__name__
        }
    
    @classmethod
    def create_processor_set(cls, processor_names: List[str]) -> List[BaseProcessor]:
        """创建一组处理器实例"""
        processors = []
        
        for name in processor_names:
            config = ProcessorConfig(enabled=True, name=name)
            processor = cls.get_processor(name, config)
            processors.append(processor)
            
        return processors
    
    @classmethod
    def is_processor_available(cls, name: str) -> bool:
        """检查处理器是否可用"""
        cls._load_builtin_processors()
        return name in cls._processors
    
    @classmethod
    def unregister_processor(cls, name: str) -> bool:
        """注销处理器 (主要用于测试)"""
        if name in cls._processors:
            del cls._processors[name]
            return True
        return False
        
    @classmethod
    def clear_registry(cls):
        """清空注册表 (主要用于测试)"""
        cls._processors.clear()
        cls._loaded = False
        
    # Phase 4.2: 新增便利方法
    @classmethod
    def get_active_trimmer_class(cls) -> Type[BaseProcessor]:
        """获取当前活跃的载荷裁切处理器类"""
        cls._load_builtin_processors()
        return cls._processors.get('trim_packet', None)
        
    @classmethod
    def is_enhanced_mode_enabled(cls) -> bool:
        """检查是否启用了增强模式 - 现在基于双模块架构"""
        # 双模块架构(NewMaskPayloadStage)始终为增强模式
        return True