from pathlib import Path
from typing import Optional
import warnings

import typer

from pktmask.core.pipeline.executor import PipelineExecutor

# ---------------------------------------------------------------------------
# Typer Application Initialization
# ---------------------------------------------------------------------------
app = typer.Typer(help="PktMask CLI - Command line interface based on PipelineExecutor")

# ---------------------------------------------------------------------------
# Common Helper Functions
# ---------------------------------------------------------------------------

def _run_pipeline(
    input_file: Path,
    output_file: Path,
    enable_dedup: bool = False,
    enable_anon: bool = False,
    enable_mask: bool = False,
    recipe_path: Optional[str] = None,
    mask_mode: Optional[str] = None,
    verbose: bool = False,
) -> None:
    """Build pipeline configuration and execute."""

    cfg = {
        "dedup": {"enabled": enable_dedup},
        "anon": {"enabled": enable_anon},
        "mask": {
            "enabled": enable_mask,
        },
    }

    if recipe_path:
        # 发出强化的废弃警告
        warnings.warn(
            "\n" + "="*60 + "\n"
            "⚠️  参数 'recipe_path' 已废弃！\n"
            "\n"
            "原因：依赖的 BlindPacketMasker 组件已被移除\n"
            "影响：该参数已被完全忽略，不会影响处理流程\n"
            "\n"
            "迁移建议：\n"
            "1. 推荐：使用默认的 processor_adapter 模式进行智能协议分析\n"
            "2. 高级：通过编程接口直接传入 MaskingRecipe 对象\n"
            "3. 简单：移除 --recipe-path 参数，使用自动分析模式\n"
            "\n"
            "当前操作将以智能模式继续执行以保持向后兼容性。\n"
            "="*60,
            DeprecationWarning,
            stacklevel=2
        )
        # 同时打印到终端，确保用户看到
        typer.echo(
            typer.style(
                "⚠️  WARNING: --recipe-path 参数已废弃并被忽略 (BlindPacketMasker 已移除)",
                fg=typer.colors.YELLOW,
                bold=True
            )
        )
        # 注意：废弃的 recipe_path 被忽略，不再传递给配置
        # cfg["mask"]["recipe_path"] = recipe_path  # 已废弃，不再使用

    if mask_mode:
        cfg["mask"]["mode"] = mask_mode

    executor = PipelineExecutor(cfg)

    # Decide whether to pass progress callback based on verbose flag
    if verbose:
        def _progress(stage, stats):  # type: ignore
            typer.echo(f"[{stage.name}] Processed {stats.packets_processed} packets, modified {stats.packets_modified} packets, took {stats.duration_ms:.1f} ms")
        result = executor.run(str(input_file), str(output_file), progress_cb=_progress)
    else:
        result = executor.run(str(input_file), str(output_file))

    # Brief statistical output; detailed info can be serialized via result.to_dict()
    typer.echo(
        f"✅ Processing completed! Duration: {result.duration_ms:.1f} ms | Output file: {result.output_file}"
    )


# ---------------------------------------------------------------------------
# Main Command: mask
# ---------------------------------------------------------------------------


@app.command("mask")
def cmd_mask(
    input_path: Path = typer.Argument(..., exists=True, readable=True, help="Input PCAP/PCAPNG file"),
    output_path: Path = typer.Option(..., "-o", "--output", help="Output file path"),
    dedup: bool = typer.Option(False, "--dedup", help="Enable deduplication stage"),
    anon: bool = typer.Option(False, "--anon", help="Enable IP anonymization stage"),
    mode: str = typer.Option("processor_adapter", "--mode", help="Mask mode: enhanced|processor_adapter|basic"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose progress output"),
    recipe_path: Optional[str] = typer.Option(
        None,
        "--recipe-path",
        help="Optional MaskRecipe JSON path (已废弃，BlindPacketMasker 已移除)",
    ),
):
    """Execute payload masking Pipeline (BlindPacketMasker 已废弃，使用 TSharkEnhancedMaskProcessor)."""

    _run_pipeline(
        input_file=input_path,
        output_file=output_path,
        enable_dedup=dedup,
        enable_anon=anon,
        enable_mask=True,
        recipe_path=recipe_path,
        mask_mode=mode,
        verbose=verbose,
    )


# ---------------------------------------------------------------------------
# Standalone dedup/anon commands (for quick processing)
# ---------------------------------------------------------------------------


@app.command("dedup")
def cmd_dedup(
    input_path: Path = typer.Argument(..., exists=True, readable=True, help="Input PCAP/PCAPNG file"),
    output_path: Path = typer.Option(..., "-o", "--output", help="Output file path"),
):
    """Execute deduplication stage only."""

    _run_pipeline(
        input_file=input_path,
        output_file=output_path,
        enable_dedup=True,
    )


@app.command("anon")
def cmd_anon(
    input_path: Path = typer.Argument(..., exists=True, readable=True, help="Input PCAP/PCAPNG file"),
    output_path: Path = typer.Option(..., "-o", "--output", help="Output file path"),
):
    """Execute IP anonymization stage only."""

    _run_pipeline(
        input_file=input_path,
        output_file=output_path,
        enable_anon=True,
    )


# CLI 命令由 __main__.py 统一管理
# 直接运行此文件已不再支持
