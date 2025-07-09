#!/usr/bin/env python3
"""
立即统一方案：完全移除双重抽象基类
目标：一次性解决所有问题，但风险较高
"""

import abc
import warnings
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Protocol

from .models import StageStats


# 定义协议接口，用于类型检查
class ProcessorProtocol(Protocol):
    """处理器协议接口"""
    def process_file(self, input_path: str, output_path: str) -> Any: ...
    def initialize(self) -> None: ...


class ModernStageBase(metaclass=abc.ABCMeta):
    """现代化的统一阶段基类
    
    完全重新设计的接口，吸取两套旧系统的经验教训：
    - 简洁明确的接口定义
    - 强类型支持
    - 完整的生命周期管理
    - 内置的错误处理和日志记录
    """
    
    # 类属性
    name: str = "UnnamedStage"
    version: str = "1.0.0"
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._initialized = False
        self._logger = self._create_logger()
    
    def _create_logger(self):
        """创建专用的日志记录器"""
        from ..infrastructure.logging import get_logger
        return get_logger(f"stage.{self.__class__.__name__.lower()}")
    
    # -------------------------------------------------------------------------
    # 生命周期管理（简化版）
    # -------------------------------------------------------------------------
    
    def initialize(self, config: Optional[Dict[str, Any]] = None) -> None:
        """初始化阶段"""
        if config:
            self._config.update(config)
        
        self._logger.debug(f"Initializing {self.name}")
        self._do_initialize()
        self._initialized = True
        self._logger.info(f"{self.name} initialized successfully")
    
    def _do_initialize(self) -> None:
        """子类可重写的初始化逻辑"""
        pass
    
    def cleanup(self) -> None:
        """清理资源"""
        self._logger.debug(f"Cleaning up {self.name}")
        self._do_cleanup()
    
    def _do_cleanup(self) -> None:
        """子类可重写的清理逻辑"""
        pass
    
    # -------------------------------------------------------------------------
    # 核心处理接口
    # -------------------------------------------------------------------------
    
    @abc.abstractmethod
    def process_file(self, input_path: Union[str, Path], output_path: Union[str, Path]) -> StageStats:
        """处理单个文件 - 唯一的核心接口"""
        pass
    
    def process_files_batch(self, file_pairs: List[tuple[Union[str, Path], Union[str, Path]]]) -> List[StageStats]:
        """批量处理文件"""
        results = []
        for input_path, output_path in file_pairs:
            try:
                result = self.process_file(input_path, output_path)
                results.append(result)
            except Exception as e:
                self._logger.error(f"Failed to process {input_path}: {e}")
                # 创建错误结果
                error_result = StageStats(
                    stage_name=self.name,
                    packets_processed=0,
                    packets_modified=0,
                    duration_ms=0.0,
                    extra_metrics={"error": str(e)}
                )
                results.append(error_result)
        return results
    
    # -------------------------------------------------------------------------
    # 配置和状态
    # -------------------------------------------------------------------------
    
    @property
    def config(self) -> Dict[str, Any]:
        return self._config.copy()
    
    @property
    def is_initialized(self) -> bool:
        return self._initialized
    
    def validate_config(self) -> List[str]:
        """验证配置，返回错误列表"""
        return []
    
    # -------------------------------------------------------------------------
    # 依赖管理
    # -------------------------------------------------------------------------
    
    def get_dependencies(self) -> List[str]:
        """获取外部依赖列表"""
        return []
    
    def check_dependencies(self) -> Dict[str, bool]:
        """检查依赖可用性"""
        deps = self.get_dependencies()
        return {dep: True for dep in deps}  # 简化实现
    
    # -------------------------------------------------------------------------
    # 统计和监控
    # -------------------------------------------------------------------------
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """获取性能指标"""
        return {
            "stage_name": self.name,
            "version": self.version,
            "initialized": self._initialized
        }


# 基于处理器的现代实现基类
class ProcessorBasedStage(ModernStageBase):
    """基于处理器的阶段实现基类
    
    这个基类封装了使用底层处理器的通用逻辑，
    减少了具体阶段实现的重复代码。
    """
    
    def __init__(self, processor: ProcessorProtocol, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._processor = processor
    
    def _do_initialize(self) -> None:
        """初始化底层处理器"""
        if hasattr(self._processor, 'initialize'):
            self._processor.initialize()
    
    def process_file(self, input_path: Union[str, Path], output_path: Union[str, Path]) -> StageStats:
        """通用的处理器调用逻辑"""
        import time
        
        start_time = time.time()
        
        try:
            result = self._processor.process_file(str(input_path), str(output_path))
            duration_ms = (time.time() - start_time) * 1000
            
            # 转换处理器结果为 StageStats
            return self._convert_processor_result(result, duration_ms)
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self._logger.error(f"Processor failed: {e}")
            
            return StageStats(
                stage_name=self.name,
                packets_processed=0,
                packets_modified=0,
                duration_ms=duration_ms,
                extra_metrics={"error": str(e)}
            )
    
    def _convert_processor_result(self, result: Any, duration_ms: float) -> StageStats:
        """将处理器结果转换为 StageStats"""
        if hasattr(result, 'success') and not result.success:
            return StageStats(
                stage_name=self.name,
                packets_processed=0,
                packets_modified=0,
                duration_ms=duration_ms,
                extra_metrics={"error": getattr(result, 'error', 'unknown')}
            )
        
        stats_dict = getattr(result, 'stats', {}) or {}
        
        return StageStats(
            stage_name=self.name,
            packets_processed=int(stats_dict.get("total_packets", 0)),
            packets_modified=int(stats_dict.get("modified_packets", 
                                              stats_dict.get("anonymized_packets", 
                                                           stats_dict.get("removed_count", 0)))),
            duration_ms=duration_ms,
            extra_metrics=stats_dict
        )


# 具体实现示例
class ModernDeduplicationStage(ProcessorBasedStage):
    """现代化的去重阶段实现"""
    
    name: str = "Deduplication"
    version: str = "2.0.0"
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        from ..processors.deduplicator import DeduplicationProcessor, ProcessorConfig
        
        proc_config = ProcessorConfig(enabled=True, name="dedup")
        processor = DeduplicationProcessor(proc_config)
        
        super().__init__(processor, config)
    
    def get_dependencies(self) -> List[str]:
        return []  # 无外部依赖
    
    def validate_config(self) -> List[str]:
        errors = []
        algorithm = self._config.get('algorithm', 'sha256')
        if algorithm not in ['md5', 'sha1', 'sha256']:
            errors.append(f"Invalid algorithm: {algorithm}")
        return errors


class ModernAnonymizationStage(ProcessorBasedStage):
    """现代化的IP匿名化阶段实现"""
    
    name: str = "IP Anonymization"
    version: str = "2.0.0"
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        from ..processors.ip_anonymizer import IPAnonymizer, ProcessorConfig
        
        proc_config = ProcessorConfig(enabled=True, name="anon")
        processor = IPAnonymizer(proc_config)
        
        super().__init__(processor, config)
    
    def get_dependencies(self) -> List[str]:
        return []  # 无外部依赖


# 向后兼容的别名和废弃警告
def _deprecated_class_factory(new_class, old_name: str):
    """创建废弃类的工厂函数"""
    
    class DeprecatedClass(new_class):
        def __init__(self, *args, **kwargs):
            warnings.warn(
                f"{old_name} is deprecated. Use {new_class.__name__} instead.",
                DeprecationWarning,
                stacklevel=2
            )
            super().__init__(*args, **kwargs)
    
    DeprecatedClass.__name__ = old_name
    DeprecatedClass.__qualname__ = old_name
    return DeprecatedClass


# 创建向后兼容的别名
ProcessingStep = _deprecated_class_factory(ModernStageBase, "ProcessingStep")
StageBase = ModernStageBase  # 新的标准名称

# 具体实现的别名
DeduplicationStep = _deprecated_class_factory(ModernDeduplicationStage, "DeduplicationStep")
DeduplicationStage = ModernDeduplicationStage

IpAnonymizationStep = _deprecated_class_factory(ModernAnonymizationStage, "IpAnonymizationStep")
IpAnonymizationStage = ModernAnonymizationStage
