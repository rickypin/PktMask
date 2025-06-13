#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
基础Stage处理器类

定义所有Stage处理器的通用接口和行为。
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging
import time
from pathlib import Path

from ...processors.base_processor import ProcessorResult


class StageContext:
    """Stage执行上下文
    
    在Stage之间传递数据和状态信息。
    """
    
    def __init__(self, input_file: Path, output_file: Path, work_dir: Path):
        self.input_file = input_file
        self.output_file = output_file
        self.work_dir = work_dir
        
        # 数据传递
        self.mask_table = None
        self.tshark_output = None
        self.pyshark_results = None
        
        # 执行状态
        self.current_stage = ""
        self.stage_progress = 0.0
        
        # 统计信息
        self.stats = {}
        
        # 临时文件管理
        self.temp_files = []
    
    def register_temp_file(self, temp_file: Path) -> None:
        """注册临时文件以便后续清理"""
        self.temp_files.append(temp_file)
    
    def create_temp_file(self, prefix: str, suffix: str) -> Path:
        """创建临时文件并自动注册
        
        Args:
            prefix: 文件名前缀
            suffix: 文件扩展名
            
        Returns:
            创建的临时文件路径
        """
        import uuid
        temp_file = self.work_dir / f"{prefix}_{uuid.uuid4().hex}{suffix}"
        temp_file.touch()
        self.register_temp_file(temp_file)
        return temp_file
    
    def cleanup_temp_files(self) -> None:
        """清理所有临时文件"""
        for temp_file in self.temp_files:
            try:
                if temp_file.exists():
                    temp_file.unlink()
            except Exception as e:
                logging.getLogger(__name__).warning(f"清理临时文件失败: {temp_file}, 错误: {e}")
        self.temp_files.clear()
    
    def cleanup(self) -> None:
        """清理资源 (cleanup_temp_files的别名)"""
        self.cleanup_temp_files()


class BaseStage(ABC):
    """Stage处理器抽象基类
    
    定义各个处理阶段的标准接口和通用行为。
    所有具体的Stage实现都应该继承此类。
    """
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        """初始化Stage
        
        Args:
            name: Stage名称
            config: Stage配置参数
        """
        self.name = name
        self.config = config or {}
        self.stats = {}
        self._logger = logging.getLogger(f"{__name__}.{name}")
        
        # 执行状态
        self._is_initialized = False
        self._last_execution_time = 0.0
    
    def initialize(self) -> bool:
        """初始化Stage
        
        Returns:
            初始化是否成功
        """
        try:
            self._initialize_impl()
            self._is_initialized = True
            self._logger.info(f"Stage '{self.name}' 初始化成功")
            return True
        except Exception as e:
            self._logger.error(f"Stage '{self.name}' 初始化失败: {e}")
            return False
    
    def _initialize_impl(self) -> None:
        """子类可重写的初始化实现"""
        pass
    
    @property
    def is_initialized(self) -> bool:
        """检查Stage是否已初始化"""
        return self._is_initialized
    
    @abstractmethod
    def execute(self, context: StageContext) -> ProcessorResult:
        """执行处理阶段
        
        Args:
            context: 阶段执行上下文
            
        Returns:
            处理结果
        """
        pass
    
    @abstractmethod
    def validate_inputs(self, context: StageContext) -> bool:
        """验证输入参数
        
        Args:
            context: 阶段执行上下文
            
        Returns:
            验证是否成功
        """
        pass
    
    def get_estimated_duration(self, context: StageContext) -> float:
        """估算处理时间（秒）
        
        Args:
            context: 阶段执行上下文
            
        Returns:
            估算的处理时间
        """
        # 基于文件大小的简单估算
        if context.input_file.exists():
            file_size_mb = context.input_file.stat().st_size / (1024 * 1024)
            # 假设每MB需要0.1秒处理时间
            return max(0.5, file_size_mb * 0.1)
        return 1.0
    
    def get_progress_callback(self, context: StageContext):
        """获取进度回调函数
        
        Args:
            context: 阶段执行上下文
            
        Returns:
            进度回调函数
        """
        def update_progress(progress: float):
            """更新Stage进度
            
            Args:
                progress: 进度百分比 (0.0 - 1.0)
            """
            context.stage_progress = max(0.0, min(1.0, progress))
            self._logger.debug(f"Stage '{self.name}' 进度: {progress:.1%}")
        
        return update_progress
    
    def cleanup(self, context: StageContext) -> None:
        """清理Stage资源
        
        Args:
            context: 阶段执行上下文
        """
        try:
            self._cleanup_impl(context)
            self._logger.debug(f"Stage '{self.name}' 资源清理完成")
        except Exception as e:
            self._logger.warning(f"Stage '{self.name}' 清理资源时发生异常: {e}")
    
    def _cleanup_impl(self, context: StageContext) -> None:
        """子类可重写的清理实现"""
        pass
    
    def get_stats(self) -> Dict[str, Any]:
        """获取处理统计信息"""
        base_stats = {
            'name': self.name,
            'initialized': self._is_initialized,
            'last_execution_time': self._last_execution_time
        }
        base_stats.update(self.stats)
        return base_stats
    
    def reset_stats(self) -> None:
        """重置统计信息"""
        self.stats.clear()
        self._last_execution_time = 0.0
    
    def record_execution_time(self, duration: float) -> None:
        """记录执行时间
        
        Args:
            duration: 执行时间（秒）
        """
        self._last_execution_time = duration
        self.stats['execution_time'] = duration
    
    def get_description(self) -> str:
        """获取Stage描述"""
        return f"{self.name} 处理阶段"
    
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """获取配置值
        
        Args:
            key: 配置键
            default: 默认值
            
        Returns:
            配置值
        """
        return self.config.get(key, default)
    
    def validate_config(self) -> bool:
        """验证配置参数
        
        Returns:
            配置是否有效
        """
        # 基础验证，子类可以重写
        return True
    
    def get_required_tools(self) -> list:
        """获取Stage所需的外部工具列表
        
        Returns:
            外部工具列表
        """
        return []
    
    def check_tool_availability(self) -> Dict[str, bool]:
        """检查外部工具可用性
        
        Returns:
            工具可用性字典
        """
        tools = self.get_required_tools()
        availability = {}
        
        for tool in tools:
            try:
                import subprocess
                subprocess.run([tool, '--version'], 
                             capture_output=True, 
                             check=True, 
                             timeout=5)
                availability[tool] = True
            except (subprocess.CalledProcessError, 
                   subprocess.TimeoutExpired, 
                   FileNotFoundError):
                availability[tool] = False
        
        return availability 