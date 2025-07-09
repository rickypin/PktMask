#!/usr/bin/env python3
"""
桌面应用优化的统一处理阶段基类
保持现有功能，简化架构，避免过度工程化
"""

import abc
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from enum import Enum

# 保持与现有 StageStats 的兼容性
@dataclass
class StageStats:
    """处理阶段统计信息 - 兼容现有格式"""
    stage_name: str = ""
    packets_processed: int = 0
    packets_modified: int = 0
    duration_ms: float = 0.0
    extra_metrics: Dict[str, Any] = None

    def __post_init__(self):
        if self.extra_metrics is None:
            self.extra_metrics = {}

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式，保持向后兼容"""
        return {
            "stage_name": self.stage_name,
            "packets_processed": self.packets_processed,
            "packets_modified": self.packets_modified,
            "duration_ms": self.duration_ms,
            **self.extra_metrics
        }

class StageBase(metaclass=abc.ABCMeta):
    """
    统一的处理阶段基类 - 桌面应用优化版

    设计原则：
    1. 保持现有接口兼容性
    2. 简化不必要的复杂性
    3. 专注于桌面应用需求
    4. 避免过度抽象
    """

    # 类属性 - 保持现有命名约定
    name: str = "UnnamedStage"
    _initialized: bool = False

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._logger = self._create_logger()

    def _create_logger(self):
        """创建日志记录器"""
        return logging.getLogger(f"stage.{self.__class__.__name__.lower()}")

    # -------------------------------------------------------------------------
    # 生命周期管理 - 保持现有接口
    # -------------------------------------------------------------------------

    def initialize(self, config: Optional[Dict] = None) -> None:
        """初始化阶段 - 保持现有签名"""
        if config:
            self._config.update(config)

        try:
            self._do_initialize()
            self._initialized = True
            self._logger.info(f"{self.name} initialized successfully")
        except Exception as e:
            self._logger.error(f"Failed to initialize {self.name}: {e}")
            raise

    def _do_initialize(self) -> None:
        """子类可重写的初始化逻辑"""
        pass

    # -------------------------------------------------------------------------
    # 核心处理接口 - 保持现有签名
    # -------------------------------------------------------------------------

    @abc.abstractmethod
    def process_file(self, input_path: Union[str, Path], output_path: Union[str, Path]) -> Union[StageStats, Dict, None]:
        """
        处理单个文件 - 保持现有接口签名

        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径

        Returns:
            StageStats 或兼容字典，保持向后兼容
        """
        pass

    # -------------------------------------------------------------------------
    # 目录级生命周期 - 保持现有接口
    # -------------------------------------------------------------------------

    def prepare_for_directory(self, directory: Union[str, Path], all_files: List[str]) -> None:
        """目录处理前的准备工作"""
        pass

    def finalize_directory_processing(self) -> Optional[Dict]:
        """目录处理完成后的清理工作"""
        return None

    # -------------------------------------------------------------------------
    # 工具链检测 - 保持现有接口
    # -------------------------------------------------------------------------

    def get_required_tools(self) -> List[str]:
        """获取依赖的外部工具列表"""
        return []

    def stop(self) -> None:
        """停止处理"""
        pass

    # -------------------------------------------------------------------------
    # 配置管理 - 简化版本
    # -------------------------------------------------------------------------

    @property
    def config(self) -> Dict[str, Any]:
        """获取当前配置"""
        return self._config.copy()

    def update_config(self, config: Dict[str, Any]) -> None:
        """更新配置"""
        self._config.update(config)
        self._logger.debug(f"Config updated for {self.name}")

    # -------------------------------------------------------------------------
    # 辅助方法 - 保持简单
    # -------------------------------------------------------------------------

    def __str__(self) -> str:
        return f"{self.name} ({'initialized' if self._initialized else 'not initialized'})"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}')"


# 向后兼容的别名
UnifiedStageBase = StageBase  # 为了文档一致性

# 简化的工厂函数
def create_stage(stage_type: str, config: Optional[Dict[str, Any]] = None) -> StageBase:
    """
    创建处理阶段实例

    Args:
        stage_type: 阶段类型 ('dedup', 'anon', 'mask')
        config: 配置字典

    Returns:
        处理阶段实例
    """
    # 使用现有的阶段实现，避免重复造轮子
    stage_mapping = {
        'dedup': 'pktmask.core.pipeline.stages.dedup.DedupStage',
        'anon': 'pktmask.core.pipeline.stages.anon_ip.AnonStage',
        'mask': 'pktmask.core.pipeline.stages.mask_payload.stage.MaskPayloadStage'
    }

    if stage_type not in stage_mapping:
        raise ValueError(f"Unknown stage type: {stage_type}")

    module_path, class_name = stage_mapping[stage_type].rsplit('.', 1)

    try:
        import importlib
        module = importlib.import_module(module_path)
        stage_class = getattr(module, class_name)

        # 创建实例并初始化
        stage = stage_class()
        if config:
            stage.initialize(config)
        else:
            stage.initialize()

        return stage
    except ImportError as e:
        raise RuntimeError(f"Failed to import stage {stage_type}: {e}")


# ProcessingStep 兼容层已移除 - 统一使用 StageBase


# -------------------------------------------------------------------------
# 现代化的 Pipeline 执行器
# -------------------------------------------------------------------------

@dataclass
class PipelineConfig:
    """Pipeline 配置"""
    stages: List[Dict[str, Any]]
    fail_fast: bool = True
    max_retries: int = 0
    cleanup_temp: bool = True
    temp_dir: Optional[str] = None

@dataclass
class PipelineResult:
    """Pipeline 执行结果"""
    success: bool
    total_duration_ms: float
    stage_results: List[Union[StageStats, Dict]]
    error_message: Optional[str] = None

class ModernPipelineExecutor:
    """
    现代化的 Pipeline 执行器
    专注于桌面应用需求，避免过度复杂化
    """

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.stages: List[StageBase] = []
        self.logger = logging.getLogger('pipeline.executor')
        self._initialized = False

    def initialize(self) -> None:
        """初始化 Pipeline"""
        if self._initialized:
            return

        self.logger.info("Initializing pipeline with %d stages", len(self.config.stages))

        # 创建阶段实例
        for stage_config in self.config.stages:
            stage = self._create_stage(stage_config)
            stage.initialize(stage_config.get('config', {}))
            self.stages.append(stage)

        # 验证所有阶段
        self._validate_pipeline()

        self._initialized = True
        self.logger.info("Pipeline initialized successfully")

    def _create_stage(self, stage_config: Dict[str, Any]) -> StageBase:
        """创建阶段实例"""
        stage_type = stage_config['type']
        config = stage_config.get('config', {})

        return create_stage(stage_type, config)

    def _validate_pipeline(self) -> None:
        """验证 Pipeline 配置"""
        errors = []

        for i, stage in enumerate(self.stages):
            if not stage._initialized:
                errors.append(f"Stage {i} ({stage.name}) is not initialized")

        if errors:
            raise ValueError(f"Pipeline validation failed: {'; '.join(errors)}")

    def execute(
        self,
        input_path: Union[str, Path],
        output_path: Union[str, Path],
        progress_callback: Optional[callable] = None
    ) -> PipelineResult:
        """
        执行完整的 Pipeline

        Args:
            input_path: 输入文件路径
            output_path: 最终输出文件路径
            progress_callback: 进度回调函数

        Returns:
            PipelineResult: 执行结果
        """
        if not self._initialized:
            self.initialize()

        start_time = time.time()
        stage_results: List[Union[StageStats, Dict]] = []
        current_input = Path(input_path)

        try:
            # 创建临时目录
            temp_dir = self._create_temp_directory()

            for i, stage in enumerate(self.stages):
                self.logger.info(f"Executing stage {i+1}/{len(self.stages)}: {stage.name}")

                # 确定输出路径
                if i == len(self.stages) - 1:
                    # 最后一个阶段输出到最终路径
                    stage_output = Path(output_path)
                else:
                    # 中间阶段输出到临时文件
                    stage_output = temp_dir / f"stage_{i+1}_{current_input.name}"

                # 执行阶段
                result = stage.process_file(current_input, stage_output)
                stage_results.append(result)

                # 调用进度回调
                if progress_callback:
                    progress_callback(stage.name, i+1, len(self.stages), result)

                # 检查执行结果
                if isinstance(result, StageStats) and hasattr(result, 'success'):
                    if not result.success and self.config.fail_fast:
                        raise RuntimeError(f"Stage {stage.name} failed")

                # 更新下一阶段的输入
                current_input = stage_output

            total_duration = (time.time() - start_time) * 1000

            # 清理临时文件
            if self.config.cleanup_temp:
                self._cleanup_temp_directory(temp_dir)

            return PipelineResult(
                success=True,
                total_duration_ms=total_duration,
                stage_results=stage_results
            )

        except Exception as e:
            total_duration = (time.time() - start_time) * 1000
            self.logger.error(f"Pipeline execution failed: {e}")

            return PipelineResult(
                success=False,
                total_duration_ms=total_duration,
                stage_results=stage_results,
                error_message=str(e)
            )

    def _create_temp_directory(self) -> Path:
        """创建临时目录"""
        import tempfile

        if self.config.temp_dir:
            temp_dir = Path(self.config.temp_dir)
            temp_dir.mkdir(parents=True, exist_ok=True)
        else:
            temp_dir = Path(tempfile.mkdtemp(prefix='pktmask_pipeline_'))

        self.logger.debug(f"Created temp directory: {temp_dir}")
        return temp_dir

    def _cleanup_temp_directory(self, temp_dir: Path) -> None:
        """清理临时目录"""
        try:
            import shutil
            shutil.rmtree(temp_dir)
            self.logger.debug(f"Cleaned up temp directory: {temp_dir}")
        except Exception as e:
            self.logger.warning(f"Failed to cleanup temp directory {temp_dir}: {e}")

    def cleanup(self) -> None:
        """清理 Pipeline 资源"""
        for stage in self.stages:
            try:
                stage.stop()
            except Exception as e:
                self.logger.warning(f"Error stopping stage {stage.name}: {e}")

        self.stages.clear()
        self._initialized = False
        self.logger.info("Pipeline cleanup completed")
