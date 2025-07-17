from pathlib import Path
from typing import Optional
import warnings

import typer

from pktmask.core.pipeline.executor import PipelineExecutor
from pktmask.infrastructure.startup import validate_tshark_dependency

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

    # Check TShark dependency before processing
    validation_result = validate_tshark_dependency()
    if not validation_result.success:
        typer.echo("❌ TShark dependency validation failed:", err=True)
        for error in validation_result.error_messages:
            typer.echo(f"   {error}", err=True)

        # Show installation guide
        if 'tshark' in validation_result.installation_guides:
            guide = validation_result.installation_guides['tshark']
            platform = guide.get('platform', 'your system')
            typer.echo(f"\n📋 To install TShark on {platform}:", err=True)

            methods = guide.get('methods', [])
            if methods:
                primary_method = methods[0]
                typer.echo(f"   {primary_method['description']}", err=True)
                if primary_method.get('commands'):
                    for cmd in primary_method['commands']:
                        typer.echo(f"   $ {cmd}", err=True)
                elif primary_method.get('url'):
                    typer.echo(f"   Download: {primary_method['url']}", err=True)

        raise typer.Exit(1)

    cfg = {
        "remove_dupes": {"enabled": enable_dedup},
        "anonymize_ips": {"enabled": enable_anon},
        "mask_payloads": {
            "enabled": enable_mask,
        },
    }

    if mask_mode:
        cfg["mask_payloads"]["mode"] = mask_mode

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
    dedup: bool = typer.Option(False, "--dedup", help="Enable Remove Dupes processing"),
    anon: bool = typer.Option(False, "--anon", help="Enable Anonymize IPs processing"),
    mode: str = typer.Option("enhanced", "--mode", help="Mask Payloads mode: enhanced|basic"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose progress output"),
):
    """Execute Mask Payloads pipeline with optional Remove Dupes and Anonymize IPs processing."""

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
    """Execute Remove Dupes processing only."""

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
    """Execute Anonymize IPs processing only."""

    _run_pipeline(
        input_file=input_path,
        output_file=output_path,
        enable_anon=True,
    )


# CLI commands are managed uniformly by __main__.py
# Direct execution of this file is no longer supported
