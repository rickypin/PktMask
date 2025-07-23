"""
降级处理器

在异常情况下提供安全的降级处理方案。
"""

from __future__ import annotations

import logging
import shutil
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union


class FallbackMode(Enum):
    """降级模式"""

    COPY_ORIGINAL = "copy_original"  # 复制原始文件
    MINIMAL_MASKING = "minimal_masking"  # 最小掩码处理
    SKIP_PROCESSING = "skip_processing"  # 跳过处理
    SAFE_MODE = "safe_mode"  # 安全模式处理


@dataclass
class FallbackResult:
    """降级处理结果"""

    success: bool
    mode_used: FallbackMode
    message: str
    details: Dict[str, Any] = None
    execution_time: float = 0.0

    def __post_init__(self):
        if self.details is None:
            self.details = {}


class FallbackHandler:
    """降级处理器

    在异常情况下提供安全的降级处理方案。
    """

    def __init__(self, config: Dict[str, Any]):
        """初始化降级处理器

        Args:
            config: 配置字典
        """
        self.config = config
        self.logger = logging.getLogger(
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )

        # 配置参数
        self.default_fallback_mode = FallbackMode(
            config.get("default_fallback_mode", FallbackMode.COPY_ORIGINAL.value)
        )
        self.enable_fallback = config.get("enable_fallback", True)
        self.preserve_original = config.get("preserve_original", True)
        self.fallback_timeout = config.get("fallback_timeout", 300)  # 5分钟超时

        # 降级策略映射
        self.fallback_strategies: Dict[FallbackMode, Callable] = {
            FallbackMode.COPY_ORIGINAL: self._copy_original_strategy,
            FallbackMode.MINIMAL_MASKING: self._minimal_masking_strategy,
            FallbackMode.SKIP_PROCESSING: self._skip_processing_strategy,
            FallbackMode.SAFE_MODE: self._safe_mode_strategy,
        }

        self.logger.info(
            f"降级处理器初始化: 默认模式={self.default_fallback_mode.value}, "
            f"启用={'是' if self.enable_fallback else '否'}"
        )

    def execute_fallback(
        self,
        input_path: Union[str, Path],
        output_path: Union[str, Path],
        fallback_mode: Optional[FallbackMode] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> FallbackResult:
        """执行降级处理

        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径
            fallback_mode: 降级模式，如果为None则使用默认模式
            context: 上下文信息

        Returns:
            FallbackResult: 降级处理结果
        """
        if not self.enable_fallback:
            return FallbackResult(
                success=False,
                mode_used=self.default_fallback_mode,
                message="降级处理已禁用",
            )

        start_time = time.time()
        mode = fallback_mode or self.default_fallback_mode
        context = context or {}

        self.logger.warning(f"执行降级处理: {mode.value}")

        try:
            # 获取对应的降级策略
            strategy = self.fallback_strategies.get(mode)
            if not strategy:
                return FallbackResult(
                    success=False,
                    mode_used=mode,
                    message=f"不支持的降级模式: {mode.value}",
                )

            # 执行降级策略
            result = strategy(input_path, output_path, context)
            result.execution_time = time.time() - start_time

            if result.success:
                self.logger.info(
                    f"降级处理成功: {mode.value}, 耗时: {result.execution_time:.2f}秒"
                )
            else:
                self.logger.error(f"降级处理失败: {result.message}")

            return result

        except Exception as e:
            execution_time = time.time() - start_time
            self.logger.error(f"降级处理异常: {e}")

            return FallbackResult(
                success=False,
                mode_used=mode,
                message=f"降级处理异常: {e}",
                execution_time=execution_time,
            )

    def _copy_original_strategy(
        self,
        input_path: Union[str, Path],
        output_path: Union[str, Path],
        context: Dict[str, Any],
    ) -> FallbackResult:
        """复制原始文件策略"""
        try:
            input_path = Path(input_path)
            output_path = Path(output_path)

            # 确保输出目录存在
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # 复制文件
            shutil.copy2(input_path, output_path)

            # 验证复制结果
            if not output_path.exists():
                return FallbackResult(
                    success=False,
                    mode_used=FallbackMode.COPY_ORIGINAL,
                    message="文件复制失败，输出文件不存在",
                )

            input_size = input_path.stat().st_size
            output_size = output_path.stat().st_size

            if input_size != output_size:
                return FallbackResult(
                    success=False,
                    mode_used=FallbackMode.COPY_ORIGINAL,
                    message=f"文件大小不匹配: {input_size} vs {output_size}",
                )

            return FallbackResult(
                success=True,
                mode_used=FallbackMode.COPY_ORIGINAL,
                message="成功复制原始文件",
                details={"file_size": input_size, "preserved_original": True},
            )

        except Exception as e:
            return FallbackResult(
                success=False,
                mode_used=FallbackMode.COPY_ORIGINAL,
                message=f"复制原始文件失败: {e}",
            )

    def _minimal_masking_strategy(
        self,
        input_path: Union[str, Path],
        output_path: Union[str, Path],
        context: Dict[str, Any],
    ) -> FallbackResult:
        """最小掩码处理策略"""
        try:
            # 这是一个简化的掩码策略，只对明显的敏感数据进行掩码
            # 在实际实现中，这里会包含基本的掩码逻辑

            # 目前先复制文件，后续可以实现简化的掩码逻辑
            result = self._copy_original_strategy(input_path, output_path, context)

            if result.success:
                result.mode_used = FallbackMode.MINIMAL_MASKING
                result.message = "执行最小掩码处理（当前为复制模式）"
                result.details["masking_applied"] = False
                result.details["fallback_reason"] = "最小掩码逻辑尚未实现"

            return result

        except Exception as e:
            return FallbackResult(
                success=False,
                mode_used=FallbackMode.MINIMAL_MASKING,
                message=f"最小掩码处理失败: {e}",
            )

    def _skip_processing_strategy(
        self,
        input_path: Union[str, Path],
        output_path: Union[str, Path],
        context: Dict[str, Any],
    ) -> FallbackResult:
        """跳过处理策略"""
        try:
            # 创建一个空的输出文件或者标记文件
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # 创建一个标记文件，表示处理被跳过
            skip_marker = output_path.with_suffix(".skipped")
            with open(skip_marker, "w") as f:
                f.write(f"Processing skipped at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Original file: {input_path}\n")
                f.write(f"Reason: Fallback processing\n")

            return FallbackResult(
                success=True,
                mode_used=FallbackMode.SKIP_PROCESSING,
                message="跳过处理，创建标记文件",
                details={
                    "skip_marker": str(skip_marker),
                    "original_file": str(input_path),
                },
            )

        except Exception as e:
            return FallbackResult(
                success=False,
                mode_used=FallbackMode.SKIP_PROCESSING,
                message=f"跳过处理失败: {e}",
            )

    def _safe_mode_strategy(
        self,
        input_path: Union[str, Path],
        output_path: Union[str, Path],
        context: Dict[str, Any],
    ) -> FallbackResult:
        """安全模式处理策略"""
        try:
            # 安全模式：复制文件并添加安全标记
            result = self._copy_original_strategy(input_path, output_path, context)

            if result.success:
                # 添加安全模式标记
                output_path = Path(output_path)
                safe_marker = output_path.with_suffix(".safe_mode")

                with open(safe_marker, "w") as f:
                    f.write(
                        f"Safe mode processing at {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    )
                    f.write(f"Original file preserved without modification\n")
                    f.write(f"Reason: Fallback to safe mode\n")

                result.mode_used = FallbackMode.SAFE_MODE
                result.message = "安全模式处理完成"
                result.details["safe_marker"] = str(safe_marker)
                result.details["data_preserved"] = True

            return result

        except Exception as e:
            return FallbackResult(
                success=False,
                mode_used=FallbackMode.SAFE_MODE,
                message=f"安全模式处理失败: {e}",
            )

    def get_recommended_fallback_mode(
        self, error_context: Dict[str, Any]
    ) -> FallbackMode:
        """根据错误上下文推荐降级模式

        Args:
            error_context: 错误上下文信息

        Returns:
            FallbackMode: 推荐的降级模式
        """
        # 根据错误类型推荐不同的降级模式
        error_category = error_context.get("error_category", "")
        error_severity = error_context.get("error_severity", "")

        if "memory" in error_category.lower():
            # 内存错误：使用最小掩码处理
            return FallbackMode.MINIMAL_MASKING
        elif "input" in error_category.lower():
            # 输入错误：跳过处理
            return FallbackMode.SKIP_PROCESSING
        elif "critical" in error_severity.lower():
            # 严重错误：使用安全模式
            return FallbackMode.SAFE_MODE
        else:
            # 默认：复制原始文件
            return FallbackMode.COPY_ORIGINAL

    def cleanup_fallback_artifacts(self, output_path: Union[str, Path]):
        """清理降级处理产生的辅助文件

        Args:
            output_path: 输出文件路径
        """
        try:
            output_path = Path(output_path)

            # 清理可能的标记文件
            markers = [
                output_path.with_suffix(".skipped"),
                output_path.with_suffix(".safe_mode"),
                output_path.with_suffix(".fallback"),
            ]

            for marker in markers:
                if marker.exists():
                    marker.unlink()
                    self.logger.debug(f"清理标记文件: {marker}")

        except Exception as e:
            self.logger.warning(f"清理降级辅助文件失败: {e}")


def create_fallback_handler(config: Dict[str, Any]) -> FallbackHandler:
    """创建降级处理器实例的工厂函数

    Args:
        config: 配置字典

    Returns:
        FallbackHandler: 降级处理器实例
    """
    return FallbackHandler(config)
