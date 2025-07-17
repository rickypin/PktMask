from __future__ import annotations

import logging
import shutil
import tempfile
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

from pktmask.core.pipeline.base_stage import StageBase
from pktmask.core.pipeline.models import ProcessResult, StageStats

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
        self._logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
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
        if not input_path.exists():
            raise FileNotFoundError(f"Input file does not exist: {input_path}")

        temp_dir = Path(tempfile.mkdtemp(prefix="pktmask_pipeline_"))

        try:
            overall_start = time.time()
            current_input = input_path
            stage_stats_list: List[StageStats] = []
            errors: List[str] = []

            for idx, stage in enumerate(self.stages):
                try:
                    is_last = idx == len(self.stages) - 1
                    stage_output = output_path if is_last else temp_dir / f"stage_{idx}_{output_path.name}"

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
                    # Enhanced error logging with professional English
                    import platform
                    error_msg = f"Stage {stage.name} execution failed: {str(e)}"
                    errors.append(error_msg)

                    # Log detailed error information for debugging
                    self._logger.error(f"Pipeline stage failure details:")
                    self._logger.error(f" - Stage: {stage.name}")
                    self._logger.error(f" - Input file: {current_input}")
                    self._logger.error(f" - Output file: {stage_output}")
                    self._logger.error(f" - Platform: {platform.system()}")
                    self._logger.error(f" - Error: {str(e)}", exc_info=True)

                    # Windows-specific error analysis
                    if platform.system() == "Windows":
                        self._logger.error(f" - Windows-specific diagnostics:")
                        try:
                            import os
                            if os.path.exists(current_input):
                                self._logger.error(f"   • Input file exists: Yes")
                                self._logger.error(f"   • Input file readable: {os.access(current_input, os.R_OK)}")
                                self._logger.error(f"   • Input file size: {os.path.getsize(current_input)} bytes")
                            else:
                                self._logger.error(f"   • Input file exists: No")

                            output_dir = Path(stage_output).parent
                            if output_dir.exists():
                                self._logger.error(f"   • Output directory exists: Yes")
                                self._logger.error(f"   • Output directory writable: {os.access(output_dir, os.W_OK)}")
                            else:
                                self._logger.error(f"   • Output directory exists: No")

                        except Exception as diag_e:
                            self._logger.error(f"   • Diagnostic check failed: {diag_e}")

                    # 创建失败统计
                    failed_stats = StageStats(
                        stage_name=stage.name,
                        packets_processed=0,
                        packets_modified=0,
                        duration_ms=0.0,
                        extra_metrics={
                            "error": str(e),
                            "error_type": type(e).__name__,
                            "platform": platform.system()
                        },
                    )
                    stage_stats_list.append(failed_stats)

                    # 如果任何 Stage 失败，则整个过程失败
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

        except Exception as e:
            # Handle top-level pipeline exceptions
            error_msg = f"Pipeline execution failed: {str(e)}"
            return ProcessResult(
                success=False,
                input_file=str(input_path),
                output_file=None,
                duration_ms=0.0,
                stage_stats=[],
                errors=[error_msg],
            )

        finally:
            # Enhanced temporary file cleanup with Windows-specific logging
            try:
                import platform
                import os

                # Log temporary directory cleanup start
                self._logger.debug(f"Cleaning up temporary directory: {temp_dir}")

                # Windows-specific temporary file handling
                if platform.system() == "Windows":
                    try:
                        # Check temporary directory contents before cleanup
                        if temp_dir.exists():
                            temp_files = list(temp_dir.iterdir())
                            self._logger.debug(f"Windows temp cleanup: {len(temp_files)} files to remove")

                            # Try to remove files individually for better error reporting
                            for temp_file in temp_files:
                                try:
                                    if temp_file.is_file():
                                        temp_file.unlink()
                                        self._logger.debug(f"Removed temp file: {temp_file.name}")
                                    elif temp_file.is_dir():
                                        shutil.rmtree(temp_file, ignore_errors=True)
                                        self._logger.debug(f"Removed temp directory: {temp_file.name}")
                                except Exception as file_e:
                                    self._logger.warning(f"Failed to remove temp file {temp_file.name}: {file_e}")

                            # Remove the main temporary directory
                            temp_dir.rmdir()
                            self._logger.debug("Windows temp directory cleanup completed successfully")
                        else:
                            self._logger.debug("Temporary directory does not exist, nothing to clean")

                    except Exception as win_e:
                        self._logger.warning(f"Windows-specific temp cleanup failed, falling back to standard cleanup: {win_e}")
                        # Fallback to standard cleanup
                        shutil.rmtree(temp_dir, ignore_errors=True)
                else:
                    # Standard cleanup for non-Windows platforms
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    self._logger.debug("Standard temporary directory cleanup completed")

            except Exception as cleanup_e:
                self._logger.error(f"Temporary directory cleanup failed: {cleanup_e}")
                # Ensure cleanup doesn't fail the entire pipeline
                try:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except:
                    pass  # Ignore final cleanup errors

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------
    def _get_config_with_fallback(self, config: Dict, standard_key: str, legacy_key: str) -> Dict:
        """获取配置，支持标准键名和旧键名的向后兼容性"""
        # 优先使用标准键名
        if standard_key in config:
            return config[standard_key]
        # 回退到旧键名
        elif legacy_key in config:
            self._logger.warning(f"Using legacy configuration key '{legacy_key}', recommend updating to '{standard_key}'")
            return config[legacy_key]
        # 返回空配置
        return {}

    def _build_pipeline(self, config: Dict) -> List[StageBase]:
        """根据配置动态装配 Pipeline。"""

        stages: List[StageBase] = []

        # ------------------------------------------------------------------
        # Remove Dupes Stage (标准命名：remove_dupes，向后兼容：dedup)
        # ------------------------------------------------------------------
        dedup_cfg = self._get_config_with_fallback(config, "remove_dupes", "dedup")
        if dedup_cfg.get("enabled", False):
            from pktmask.core.pipeline.stages.dedup import DeduplicationStage

            stage = DeduplicationStage(dedup_cfg)
            stage.initialize()
            stages.append(stage)

        # ------------------------------------------------------------------
        # Anonymize IPs Stage (标准命名：anonymize_ips，向后兼容：anon)
        # ------------------------------------------------------------------
        anon_cfg = self._get_config_with_fallback(config, "anonymize_ips", "anon")
        if anon_cfg.get("enabled", False):
            from pktmask.core.pipeline.stages.anon_ip import AnonStage

            stage = AnonStage(anon_cfg)
            stage.initialize()
            stages.append(stage)

        # ------------------------------------------------------------------
        # Mask Payloads Stage (标准命名：mask_payloads，向后兼容：mask)
        # ------------------------------------------------------------------
        mask_cfg = self._get_config_with_fallback(config, "mask_payloads", "mask")
        if mask_cfg.get("enabled", False):
            # 直接使用新一代双模块架构
            from pktmask.core.pipeline.stages.mask_payload_v2.stage import NewMaskPayloadStage

            # 创建 MaskStage 实例
            stage = NewMaskPayloadStage(mask_cfg)
            stage.initialize()
            stages.append(stage)

        return stages 