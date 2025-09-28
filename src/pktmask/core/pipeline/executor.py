from __future__ import annotations

import logging
import tempfile
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

from pktmask.core.pipeline.base_stage import StageBase
from pktmask.core.pipeline.models import ProcessResult, StageStats
from pktmask.infrastructure.logging.logger import log_exception

# ---------------------------------------------------------------------------
# 公共类型
# ---------------------------------------------------------------------------
ProgressCallback = Callable[[StageBase, StageStats], None]


class PipelineExecutor:
    """轻量化 Pipeline 执行器，实现统一的 Stage 调度逻辑。

    该执行器遵循 **REFACTOR_PLAN.md** 中定义的目标：GUI、CLI、MCP
    共享同一套执行逻辑，通过传入 `config` 动态装配 Stage。

    Config 格式示例::

        config = {
            "dedup": {"enabled": True},
            "anon": {"enabled": True},
            "mask": {
                "enabled": True,
                "protocol": "tls",
                "mode": "enhanced"
            },
        }

    注意：掩码处理使用双模块架构（Marker + Masker）进行智能协议分析。

    缺失的键或 `enabled=False` 将导致对应 Stage 被跳过。
    """

    # ---------------------------------------------------------------------
    # 构造与 Pipeline 组装
    # ---------------------------------------------------------------------
    def __init__(self, config: Optional[Dict] | None = None):
        self._config: Dict = config or {}
        self._logger = logging.getLogger(
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )
        self.stages: List[StageBase] = self._build_pipeline(self._config)

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------
    def run(
        self,
        input_path: str | Path,
        output_path: str | Path,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> ProcessResult:
        """执行完整 Pipeline。

        Args:
            input_path: 原始 PCAP/PCAPNG 文件路径。
            output_path: 最终输出文件路径。
            progress_cb: 可选进度回调，签名 ``cb(stage, stats)``。
        """

        input_path = Path(input_path)
        output_path = Path(output_path)

        # Check input file existence and handle error properly
        if not input_path.exists():
            error_msg = f"Input file not found: {input_path}"
            self._logger.error(f"Pipeline execution failed: {error_msg}")

            # Log exception with context for backend logging
            file_not_found_error = FileNotFoundError(error_msg)
            log_exception(
                file_not_found_error,
                logger_name="PipelineExecutor.InputValidation",
                context={
                    "input_file": str(input_path),
                    "output_file": str(output_path),
                    "pipeline_config": self._config,
                    "failure_level": "input_validation",
                },
            )

            return ProcessResult(
                success=False,
                input_file=str(input_path),
                output_file=None,
                duration_ms=0.0,
                stage_stats=[],
                errors=[error_msg],
            )

        # Use TemporaryDirectory context manager for automatic cleanup
        with tempfile.TemporaryDirectory(prefix="pktmask_pipeline_") as temp_dir_str:
            temp_dir = Path(temp_dir_str)

            try:
                overall_start = time.time()
                current_input = input_path
                stage_stats_list: List[StageStats] = []
                errors: List[str] = []

                for idx, stage in enumerate(self.stages):
                    try:
                        is_last = idx == len(self.stages) - 1
                        stage_output = (
                            output_path
                            if is_last
                            else temp_dir / f"stage_{idx}_{output_path.name}"
                        )

                        stats = stage.process_file(current_input, stage_output)  # type: ignore[arg-type]
                        if stats is None:
                            # 兼容少数 Stage 返回 None 的情况
                            stats = StageStats(
                                stage_name=stage.name,
                                packets_processed=0,
                                packets_modified=0,
                                duration_ms=0.0,
                                extra_metrics={},
                            )
                        stage_stats_list.append(stats)

                        if progress_cb is not None:
                            progress_cb(stage, stats)

                        current_input = stage_output

                    except Exception as e:
                        # Log detailed error information for debugging
                        self._logger.error(
                            f"Stage '{stage.name}' failed during pipeline execution. "
                            f"Error: {type(e).__name__}: {str(e)}. "
                            f"Input file: {current_input}. "
                            f"Stage index: {idx}/{len(self.stages)-1}",
                            exc_info=True,
                        )

                        # Log exception with full context for backend logging
                        log_exception(
                            e,
                            logger_name=f"PipelineExecutor.{stage.name}",
                            context={
                                "stage_name": stage.name,
                                "stage_index": idx,
                                "total_stages": len(self.stages),
                                "input_file": str(current_input),
                                "output_file": (
                                    str(stage_output)
                                    if "stage_output" in locals()
                                    else None
                                ),
                                "pipeline_config": self._config,
                            },
                        )

                        # Create user-friendly error message for GUI display
                        user_friendly_msg = f"Processing failed at stage '{stage.name}': {self._get_user_friendly_error_message(e)}"
                        error_msg = f"Stage {stage.name} execution failed: {str(e)}"
                        errors.append(error_msg)

                        # Create failure statistics with detailed error information
                        failed_stats = StageStats(
                            stage_name=stage.name,
                            packets_processed=0,
                            packets_modified=0,
                            duration_ms=0.0,
                            extra_metrics={
                                "error": str(e),
                                "error_type": type(e).__name__,
                                "user_message": user_friendly_msg,
                                "stage_index": idx,
                            },
                        )
                        stage_stats_list.append(failed_stats)

                        # Fail-fast: if any Stage fails, the entire process fails
                        self._logger.info(
                            f"Pipeline execution terminated due to stage failure. Processed {idx} out of {len(self.stages)} stages successfully."
                        )
                        break

                # 计算总执行时间
                total_duration_ms = (time.time() - overall_start) * 1000

                # 创建最终结果（一次性构造，不修改）
                result = ProcessResult(
                    success=len(errors) == 0,
                    input_file=str(input_path),
                    output_file=str(output_path) if len(errors) == 0 else None,
                    duration_ms=total_duration_ms,
                    stage_stats=stage_stats_list,
                    errors=errors,
                )
                return result

            # Handle exceptions that occur within the temporary directory context
            except Exception as e:
                # Handle top-level pipeline exceptions with detailed logging
                self._logger.error(
                    f"Critical pipeline failure occurred. "
                    f"Error: {type(e).__name__}: {str(e)}. "
                    f"Input file: {input_path}. "
                    f"Output file: {output_path}",
                    exc_info=True,
                )

                # Log exception with full context for backend logging
                log_exception(
                    e,
                    logger_name="PipelineExecutor.Critical",
                    context={
                        "input_file": str(input_path),
                        "output_file": str(output_path),
                        "pipeline_config": self._config,
                        "total_stages": len(self.stages),
                        "failure_level": "pipeline_critical",
                    },
                )

                # Create user-friendly error message
                user_friendly_msg = f"Pipeline execution failed: {self._get_user_friendly_error_message(e)}"
                error_msg = f"Pipeline execution failed: {str(e)}"

                return ProcessResult(
                    success=False,
                    input_file=str(input_path),
                    output_file=None,
                    duration_ms=0.0,
                    stage_stats=[],
                    errors=[error_msg],
                )
        # Temporary directory is automatically cleaned up by context manager

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------
    def _get_user_friendly_error_message(self, exception: Exception) -> str:
        """Convert technical exception to user-friendly error message.

        Args:
            exception: The exception that occurred

        Returns:
            str: User-friendly error message in English
        """
        error_type = type(exception).__name__
        error_msg = str(exception)

        # Map common exceptions to user-friendly messages
        if isinstance(exception, FileNotFoundError):
            return "Input file not found or inaccessible"
        elif isinstance(exception, PermissionError):
            return "Permission denied - check file access rights"
        elif isinstance(exception, MemoryError):
            return "Insufficient memory to process the file"
        elif isinstance(exception, ValueError):
            return "Invalid data format or configuration"
        elif isinstance(exception, ImportError):
            return "Required dependency not available"
        elif "tshark" in error_msg.lower():
            return "Tshark tool not found or not working properly"
        elif "scapy" in error_msg.lower():
            return "Network packet processing library error"
        elif "timeout" in error_msg.lower():
            return "Operation timed out - file may be too large"
        else:
            # For unknown errors, provide generic but helpful message
            return f"Unexpected error occurred ({error_type})"

    def _build_pipeline(self, config: Dict) -> List[StageBase]:
        """根据配置动态装配 Pipeline。"""

        stages: List[StageBase] = []

        # ------------------------------------------------------------------
        # Remove Dupes Stage (标准命名：remove_dupes)
        # ------------------------------------------------------------------
        dedup_cfg = config.get("remove_dupes", {})
        if dedup_cfg.get("enabled", False):
            from pktmask.core.pipeline.stages.deduplication_stage import (
                DeduplicationStage,
            )

            stage = DeduplicationStage(dedup_cfg)
            stage.initialize()
            stages.append(stage)

        # ------------------------------------------------------------------
        # Anonymize IPs Stage (标准命名：anonymize_ips)
        # ------------------------------------------------------------------
        anon_cfg = config.get("anonymize_ips", {})
        if anon_cfg.get("enabled", False):
            from pktmask.core.pipeline.stages.anonymization_stage import (
                AnonymizationStage,
            )

            stage = AnonymizationStage(anon_cfg)
            stage.initialize()
            stages.append(stage)

        # ------------------------------------------------------------------
        # Mask Payloads Stage (标准命名：mask_payloads)
        # ------------------------------------------------------------------
        mask_cfg = config.get("mask_payloads", {})
        if mask_cfg.get("enabled", False):
            # 直接使用新一代双模块架构
            from pktmask.core.pipeline.stages.masking_stage.stage import MaskingStage

            # 创建 MaskStage 实例
            stage = MaskingStage(mask_cfg)
            stage.initialize()
            stages.append(stage)

        return stages
