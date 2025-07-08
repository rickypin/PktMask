from __future__ import annotations

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
                "mode": "processor_adapter"  # 使用智能协议分析模式
            },
        }
        
    注意：recipe_path 和 recipe_dict 配置项已废弃。
    新版本使用 processor_adapter 模式进行智能协议分析，
    或通过编程接口直接传入 MaskingRecipe 对象。

    缺失的键或 `enabled=False` 将导致对应 Stage 被跳过。
    """

    # ---------------------------------------------------------------------
    # 构造与 Pipeline 组装
    # ---------------------------------------------------------------------
    def __init__(self, config: Optional[Dict] | None = None):
        self._config: Dict = config or {}
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
            raise FileNotFoundError(f"输入文件不存在: {input_path}")

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
                    error_msg = f"Stage {stage.name} 执行失败: {str(e)}"
                    errors.append(error_msg)
                    
                    # 创建失败统计
                    failed_stats = StageStats(
                        stage_name=stage.name,
                        packets_processed=0,
                        packets_modified=0,
                        duration_ms=0.0,
                        extra_metrics={"error": str(e)},
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
                output_file=str(current_input) if len(errors) == 0 else None,
                duration_ms=total_duration_ms,
                stage_stats=stage_stats_list,
                errors=errors,
            )
            return result

        except Exception as e:
            # 处理顶级异常
            error_msg = f"Pipeline 执行失败: {str(e)}"
            return ProcessResult(
                success=False,
                input_file=str(input_path),
                output_file=None,
                duration_ms=0.0,
                stage_stats=[],
                errors=[error_msg],
            )

        finally:
            # 清理临时目录
            shutil.rmtree(temp_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------
    def _build_pipeline(self, config: Dict) -> List[StageBase]:
        """根据配置动态装配 Pipeline。"""

        stages: List[StageBase] = []

        # ------------------------------------------------------------------
        # Dedup Stage
        # ------------------------------------------------------------------
        dedup_cfg = config.get("dedup", {})
        if dedup_cfg.get("enabled", False):
            from pktmask.core.pipeline.stages.dedup import DeduplicationStage

            stage = DeduplicationStage(dedup_cfg)
            stage.initialize()
            stages.append(stage)

        # ------------------------------------------------------------------
        # Anon Stage
        # ------------------------------------------------------------------
        anon_cfg = config.get("anon", {})
        if anon_cfg.get("enabled", False):
            from pktmask.core.pipeline.stages.anon_ip import AnonStage

            stage = AnonStage(anon_cfg)
            stage.initialize()
            stages.append(stage)

        # ------------------------------------------------------------------
        # Mask Stage - Enhanced MaskStage (Phase 2完整实现)
        # ------------------------------------------------------------------
        mask_cfg = config.get("mask", {})
        if mask_cfg.get("enabled", False):
            from pktmask.core.pipeline.stages.mask_payload.stage import MaskPayloadStage as MaskStage
            
            # 创建 Enhanced MaskStage 实例
            stage = MaskStage(mask_cfg)
            stage.initialize()
            stages.append(stage)

        return stages 