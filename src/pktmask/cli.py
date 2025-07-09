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
    mode: str = typer.Option("enhanced", "--mode", help="Mask mode: enhanced|basic"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose progress output"),
):
    """Execute payload masking pipeline using TSharkEnhancedMaskProcessor."""

    _run_pipeline(
        input_file=input_path,
        output_file=output_path,
        enable_dedup=dedup,
        enable_anon=anon,
        enable_mask=True,
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
