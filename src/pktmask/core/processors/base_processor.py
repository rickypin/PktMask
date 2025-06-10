"""
简化的处理器基础架构

替代复杂的插件系统，使用简单直观的处理器模式。
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ProcessorConfig:
    """处理器配置"""
    enabled: bool = True
    name: str = ""
    priority: int = 0
    
    def __post_init__(self):
        if not self.name:
            self.name = self.__class__.__name__


class ProcessorResult:
    """处理器结果"""
    
    def __init__(self, success: bool, data: Any = None, 
                 stats: Optional[Dict] = None, error: Optional[str] = None):
        self.success = success
        self.data = data  
        self.stats = stats or {}
        self.error = error
        
    def __bool__(self):
        return self.success
        
    def __str__(self):
        if self.success:
            return f"成功 - 统计: {self.stats}"
        else:
            return f"失败 - 错误: {self.error}"


class BaseProcessor(ABC):
    """处理器基类
    
    简单直观的处理器接口，替代复杂的插件架构。
    每个处理器负责单一功能：IP匿名化、去重或裁切。
    """
    
    def __init__(self, config: ProcessorConfig):
        self.config = config
        self.stats = {}
        self._is_initialized = False
        
    def initialize(self) -> bool:
        """初始化处理器"""
        try:
            self._initialize_impl()
            self._is_initialized = True
            return True
        except Exception as e:
            print(f"处理器初始化失败: {e}")
            return False
    
    def _initialize_impl(self):
        """子类可重写的初始化实现"""
        pass
    
    @property
    def is_initialized(self) -> bool:
        """检查处理器是否已初始化"""
        return self._is_initialized
    
    @abstractmethod
    def process_file(self, input_path: str, output_path: str) -> ProcessorResult:
        """处理文件的核心方法"""
        pass
    
    @abstractmethod 
    def get_display_name(self) -> str:
        """获取用户友好的显示名称"""
        pass
        
    def get_description(self) -> str:
        """获取处理器描述"""
        return f"{self.get_display_name()} 处理器"
        
    def validate_inputs(self, input_path: str, output_path: str) -> bool:
        """验证输入参数"""
        if not Path(input_path).exists():
            raise FileNotFoundError(f"输入文件不存在: {input_path}")
            
        output_dir = Path(output_path).parent
        if not output_dir.exists():
            output_dir.mkdir(parents=True, exist_ok=True)
            
        return True
        
    def get_stats(self) -> Dict[str, Any]:
        """获取处理统计信息"""
        return self.stats.copy()
        
    def reset_stats(self):
        """重置统计信息"""
        self.stats.clear() 