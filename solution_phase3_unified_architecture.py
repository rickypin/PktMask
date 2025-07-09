#!/usr/bin/env python3
"""
阶段三：完全统一架构
目标：移除 ProcessingStep，所有实现统一使用 StageBase
"""

import abc
from pathlib import Path
from typing import Dict, List, Optional, Any, Union

from .models import StageStats


class UnifiedStageBase(metaclass=abc.ABCMeta):
    """统一的处理阶段基类
    
    这是最终的统一接口，合并了 ProcessingStep 和 StageBase 的优点：
    - 简洁的核心接口
    - 完整的生命周期管理
    - 现代化的类型提示
    - 向后兼容的属性支持
    """
    
    #: 阶段名称，用于 GUI/CLI 显示
    name: str = "UnnamedStage"
    
    #: 向后兼容：保留 suffix 属性
    suffix: str = ""
    
    #: 初始化状态
    _initialized: bool = False
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """统一的构造函数
        
        Args:
            config: 可选的配置字典
        """
        self._config = config or {}
        self._initialized = False
    
    # -------------------------------------------------------------------------
    # 生命周期管理
    # -------------------------------------------------------------------------
    
    def initialize(self, config: Optional[Dict[str, Any]] = None) -> None:
        """初始化阶段
        
        Args:
            config: 运行时配置，会与构造时配置合并
        """
        if config:
            self._config.update(config)
        self._initialized = True
    
    def prepare_for_directory(self, directory: Union[str, Path], all_files: List[str]) -> None:
        """目录处理前的准备工作
        
        Args:
            directory: 目录路径
            all_files: 目录中所有待处理的文件列表
        """
        pass
    
    def finalize_directory_processing(self) -> Optional[Dict[str, Any]]:
        """目录处理完成后的清理工作
        
        Returns:
            可选的汇总信息字典
        """
        return None
    
    def stop(self) -> None:
        """停止处理，用于清理资源"""
        pass
    
    # -------------------------------------------------------------------------
    # 核心处理接口
    # -------------------------------------------------------------------------
    
    @abc.abstractmethod
    def process_file(self, input_path: Union[str, Path], output_path: Union[str, Path]) -> StageStats:
        """处理单个文件
        
        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径
            
        Returns:
            处理统计信息
        """
        pass
    
    # -------------------------------------------------------------------------
    # 工具和依赖管理
    # -------------------------------------------------------------------------
    
    def get_required_tools(self) -> List[str]:
        """获取依赖的外部工具列表
        
        Returns:
            工具名称列表，如 ['tshark', 'editcap']
        """
        return []
    
    def validate_dependencies(self) -> List[str]:
        """验证依赖是否满足
        
        Returns:
            缺失的依赖列表
        """
        missing = []
        for tool in self.get_required_tools():
            # 这里应该实现实际的工具检查逻辑
            # if not tool_available(tool):
            #     missing.append(tool)
            pass
        return missing
    
    # -------------------------------------------------------------------------
    # 配置和状态管理
    # -------------------------------------------------------------------------
    
    @property
    def config(self) -> Dict[str, Any]:
        """获取当前配置"""
        return self._config.copy()
    
    @property
    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return self._initialized
    
    def update_config(self, config: Dict[str, Any]) -> None:
        """更新配置"""
        self._config.update(config)
    
    # -------------------------------------------------------------------------
    # 向后兼容支持
    # -------------------------------------------------------------------------
    
    @property
    def display_name(self) -> str:
        """显示名称（向后兼容）"""
        return self.name


# 统一的工厂函数
def create_stage(stage_type: str, config: Optional[Dict[str, Any]] = None) -> UnifiedStageBase:
    """统一的阶段创建工厂
    
    Args:
        stage_type: 阶段类型 ('dedup', 'anon', 'mask')
        config: 配置字典
        
    Returns:
        创建的阶段实例
    """
    from .stages.dedup import DeduplicationStage
    from .stages.anon_ip import AnonStage
    from .stages.mask_payload.stage import MaskPayloadStage
    
    stage_map = {
        'dedup': DeduplicationStage,
        'anon': AnonStage,
        'mask': MaskPayloadStage
    }
    
    if stage_type not in stage_map:
        raise ValueError(f"Unknown stage type: {stage_type}")
    
    stage_class = stage_map[stage_type]
    return stage_class(config)


# 迁移辅助类
class LegacyStageAdapter(UnifiedStageBase):
    """遗留代码适配器
    
    用于包装旧的 ProcessingStep 实现，提供平滑的迁移路径
    """
    
    def __init__(self, legacy_instance, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._legacy_instance = legacy_instance
        self.name = getattr(legacy_instance, 'name', legacy_instance.__class__.__name__)
        self.suffix = getattr(legacy_instance, 'suffix', '')
    
    def process_file(self, input_path: Union[str, Path], output_path: Union[str, Path]) -> StageStats:
        """适配旧实现到新接口"""
        if hasattr(self._legacy_instance, 'process_file_legacy'):
            result = self._legacy_instance.process_file_legacy(str(input_path), str(output_path))
        else:
            result = self._legacy_instance.process_file(str(input_path), str(output_path))
        
        # 转换结果格式
        if isinstance(result, StageStats):
            return result
        elif isinstance(result, dict):
            return StageStats(
                stage_name=self.name,
                packets_processed=result.get('total_packets', 0),
                packets_modified=result.get('modified_packets', 
                                          result.get('anonymized_packets', 
                                                   result.get('removed_count', 0))),
                duration_ms=result.get('duration_ms', 0.0),
                extra_metrics=result
            )
        else:
            return StageStats(stage_name=self.name)
    
    def prepare_for_directory(self, directory: Union[str, Path], all_files: List[str]) -> None:
        """委托给旧实现"""
        if hasattr(self._legacy_instance, 'prepare_for_directory'):
            self._legacy_instance.prepare_for_directory(str(directory), all_files)
    
    def finalize_directory_processing(self) -> Optional[Dict[str, Any]]:
        """委托给旧实现"""
        if hasattr(self._legacy_instance, 'finalize_directory_processing'):
            return self._legacy_instance.finalize_directory_processing()
        return None


# 使用示例
def example_usage():
    """统一架构的使用示例"""
    
    # 方式1：直接创建
    dedup_stage = create_stage('dedup', {'algorithm': 'sha256'})
    
    # 方式2：适配旧实现
    from .legacy_stages import OldDeduplicationStep
    old_instance = OldDeduplicationStep()
    adapted_stage = LegacyStageAdapter(old_instance)
    
    # 统一的使用方式
    for stage in [dedup_stage, adapted_stage]:
        stage.initialize()
        result = stage.process_file('input.pcap', 'output.pcap')
        print(f"Processed {result.packets_processed} packets")


# 类型别名，用于向后兼容
ProcessingStep = UnifiedStageBase  # 废弃别名
StageBase = UnifiedStageBase       # 新别名
