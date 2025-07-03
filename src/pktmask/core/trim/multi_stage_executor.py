#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
多阶段执行器框架

协调TShark预处理、PyShark分析、TcpPayloadMaskerAdapter 回写的三阶段处理流程。
集成现有的事件系统，提供进度报告和错误处理。
"""

from typing import List, Optional, Dict, Any, Callable, Type
from pathlib import Path
from dataclasses import dataclass
import logging
import time
from abc import ABC, abstractmethod

from ..processors.base_processor import ProcessorResult
from ..events import PipelineEvents
from .models.simple_execution_result import SimpleExecutionResult, SimpleStageState
from .models.mask_table import StreamMaskTable
from .stages.base_stage import StageContext, BaseStage
from .exceptions import (
    StageExecutionError, PipelineExecutionError, ContextError,
    ResourceManagementError
)


class StageResult:
    """Stage处理结果
    
    封装单个Stage的处理结果和统计信息。
    """
    
    def __init__(self, stage_name: str, success: bool, 
                 duration: float = 0.0, data: Any = None, 
                 stats: Optional[Dict] = None, error: Optional[str] = None):
        self.stage_name = stage_name
        self.success = success
        self.duration = duration
        self.data = data
        self.stats = stats or {}
        self.error = error
        self.timestamp = time.time()
    
    def __bool__(self):
        return self.success
    
    def __str__(self):
        status = "成功" if self.success else "失败"
        return f"[{self.stage_name}] {status} - 耗时: {self.duration:.2f}s"


class MultiStageExecutor:
    """多阶段执行器
    
    协调执行多个Stage的处理流程，提供进度报告和错误处理。
    """
    
    def __init__(self, work_dir: Optional[Path] = None, 
                 event_callback: Optional[Callable] = None):
        """初始化多阶段执行器
        
        Args:
            work_dir: 工作目录，如果为None则使用临时目录
            event_callback: 事件回调函数，用于进度报告
        """
        self.work_dir = work_dir or Path.cwd() / "tmp"
        self.work_dir.mkdir(parents=True, exist_ok=True)
        
        self.event_callback = event_callback
        self._logger = logging.getLogger(__name__)
        
        # 注册的Stage
        self.stages: List[BaseStage] = []
        
        # 执行状态
        self._current_context: Optional[StageContext] = None
        self._execution_results: List[StageResult] = []
        
        self._logger.info(f"Multi-stage executor initialization completed, working directory: {self.work_dir}")
    
    def register_stage(self, stage: BaseStage) -> None:
        """注册处理阶段
        
        Args:
            stage: 要注册的Stage
        """
        # 确保Stage已经初始化
        if not stage.is_initialized:
            success = stage.initialize()
            if not success:
                raise RuntimeError(f"Stage '{stage.name}' 初始化失败")
        
        self.stages.append(stage)
        self._logger.debug(f"注册Stage: {stage.name} (已初始化)")
    
    def clear_stages(self) -> None:
        """清除所有注册的Stage"""
        self.stages.clear()
        self._logger.debug("清除所有Stage")
    
    def execute_pipeline(self, input_file: Path, output_file: Path) -> SimpleExecutionResult:
        """执行完整的处理管道
        
        Args:
            input_file: 输入文件路径
            output_file: 输出文件路径
            
        Returns:
            执行结果
        """
        if not self.stages:
            raise PipelineExecutionError("没有注册任何处理Stage")
        
        # 初始化执行上下文
        context = StageContext(
            input_file=input_file,
            output_file=output_file,
            work_dir=self.work_dir
        )
        
        self._current_context = context
        self._execution_results.clear()
        
        start_time = time.time()
        
        try:
            # 发送开始事件
            self._emit_event(PipelineEvents.PIPELINE_START, {
                'input_file': str(input_file),
                'output_file': str(output_file),
                'total_stages': len(self.stages)
            })
            
            # 执行各个Stage
            for i, stage in enumerate(self.stages):
                stage_result = self._execute_stage(stage, context, i)
                self._execution_results.append(stage_result)
                
                if not stage_result.success:
                    # Stage失败，终止执行
                    raise StageExecutionError(
                        stage_name=stage.name,
                        message=stage_result.error or "未知错误",
                        stage_data={"stage_index": i, "total_stages": len(self.stages)}
                    )
            
            # 所有Stage执行成功
            result = self._create_execution_result(
                success=True,
                state=SimpleStageState.COMPLETED,
                start_time=start_time
            )
            
            # 发送完成事件
            self._emit_event(PipelineEvents.PIPELINE_END, {
                'success': True,
                'total_duration': result.duration,
                'output_file': str(output_file)
            })
            
            return result
            
        except (StageExecutionError, PipelineExecutionError) as e:
            # 重新抛出特定异常
            self._logger.error(f"管道执行失败: {e}")
            self._emit_event(PipelineEvents.ERROR, {
                'message': str(e),
                'stage': context.current_stage,
                'error_details': getattr(e, 'details', {})
            })
            raise
        except Exception as e:
            error_msg = f"执行管道时发生未预期异常: {str(e)}"
            self._logger.error(error_msg, exc_info=True)
            
            # 发送错误事件
            self._emit_event(PipelineEvents.ERROR, {
                'message': error_msg,
                'stage': context.current_stage
            })
            
            # 包装为Pipeline异常
            raise PipelineExecutionError(
                message=error_msg,
                failed_stage=context.current_stage,
                pipeline_stats={'execution_time': time.time() - start_time}
            ) from e
        
        finally:
            # 清理资源
            self._cleanup_execution(context)
            self._current_context = None
    
    def _execute_stage(self, stage: BaseStage, context: StageContext, stage_index: int) -> StageResult:
        """执行单个Stage
        
        Args:
            stage: 要执行的Stage
            context: 执行上下文
            stage_index: Stage索引
            
        Returns:
            Stage执行结果
        """
        context.current_stage = stage.name
        stage_start_time = time.time()
        
        try:
            # 发送Stage开始事件
            self._emit_event(PipelineEvents.STEP_START, {
                'stage_name': stage.name,
                'stage_index': stage_index,
                'total_stages': len(self.stages)
            })
            
            # 验证输入
            if not stage.validate_inputs(context):
                return StageResult(
                    stage_name=stage.name,
                    success=False,
                    error="输入验证失败"
                )
            
            # 执行Stage
            self._logger.info(f"开始执行Stage: {stage.name}")
            result = stage.execute(context)
            
            duration = time.time() - stage_start_time
            
            if result.success:
                # Stage执行成功
                stage_result = StageResult(
                    stage_name=stage.name,
                    success=True,
                    duration=duration,
                    data=result.data,
                    stats=result.stats
                )
                
                self._logger.info(f"Stage '{stage.name}' 执行成功，耗时: {duration:.2f}s")
                
                # 发送Stage完成事件
                self._emit_event(PipelineEvents.STEP_END, {
                    'stage_name': stage.name,
                    'success': True,
                    'duration': duration,
                    'stats': result.stats
                })
                
            else:
                # Stage执行失败
                stage_result = StageResult(
                    stage_name=stage.name,
                    success=False,
                    duration=duration,
                    error=result.error
                )
                
                self._logger.error(f"Stage '{stage.name}' 执行失败: {result.error}")
                
                # 发送Stage错误事件
                self._emit_event(PipelineEvents.ERROR, {
                    'stage_name': stage.name,
                    'message': result.error,
                    'duration': duration
                })
            
            return stage_result
            
        except Exception as e:
            duration = time.time() - stage_start_time
            error_msg = f"Stage执行异常: {str(e)}"
            
            self._logger.error(f"Stage '{stage.name}' 执行异常: {e}", exc_info=True)
            
            return StageResult(
                stage_name=stage.name,
                success=False,
                duration=duration,
                error=error_msg
            )
        
        finally:
            # 清理Stage资源
            try:
                stage.cleanup(context)
            except Exception as e:
                self._logger.warning(f"Stage '{stage.name}' 清理资源时发生异常: {e}")
    
    def _create_execution_result(self, success: bool, state: SimpleStageState, 
                               start_time: float, error: Optional[str] = None) -> SimpleExecutionResult:
        """创建执行结果
        
        Args:
            success: 是否成功
            state: 执行状态
            start_time: 开始时间
            error: 错误信息
            
        Returns:
            执行结果
        """
        duration = time.time() - start_time
        
        # 收集所有Stage的统计信息
        all_stats = {}
        for result in self._execution_results:
            if result.stats:
                all_stats[result.stage_name] = result.stats
        
        return SimpleExecutionResult(
            success=success,
            state=state,
            duration=duration,
            total_stages=len(self.stages),
            stats=all_stats,
            error=error,
            stage_results=[
                {
                    'name': r.stage_name,
                    'success': r.success,
                    'duration': r.duration,
                    'error': r.error
                }
                for r in self._execution_results
            ]
        )
    
    def _cleanup_execution(self, context: StageContext) -> None:
        """清理执行环境
        
        Args:
            context: 执行上下文
        """
        try:
            # 清理所有注册的临时文件
            context.cleanup_temp_files()
            self._logger.debug("清理所有临时文件完成")
            # 其他清理操作...
        except Exception as e:
            self._logger.warning(f"清理执行环境时发生异常: {e}")
    
    def _emit_event(self, event_type: PipelineEvents, data: Dict[str, Any]) -> None:
        """发送事件
        
        Args:
            event_type: 事件类型
            data: 事件数据
        """
        if self.event_callback:
            try:
                self.event_callback(event_type, data)
            except Exception as e:
                self._logger.warning(f"事件回调执行异常: {e}")
    
    def get_current_progress(self) -> float:
        """获取当前执行进度
        
        Returns:
            进度百分比 (0.0 - 1.0)
        """
        if not self.stages:
            return 0.0
        
        completed_stages = len(self._execution_results)
        current_stage_progress = 0.0
        
        if self._current_context:
            current_stage_progress = self._current_context.stage_progress
        
        return (completed_stages + current_stage_progress) / len(self.stages)
    
    def get_execution_summary(self) -> Dict[str, Any]:
        """获取执行摘要
        
        Returns:
            执行摘要信息
        """
        total_duration = sum(r.duration for r in self._execution_results)
        successful_stages = sum(1 for r in self._execution_results if r.success)
        
        return {
            'total_stages': len(self.stages),
            'completed_stages': len(self._execution_results),
            'successful_stages': successful_stages,
            'failed_stages': len(self._execution_results) - successful_stages,
            'total_duration': total_duration,
            'stage_results': [
                {
                    'name': r.stage_name,
                    'success': r.success,
                    'duration': r.duration
                }
                for r in self._execution_results
            ]
        } 