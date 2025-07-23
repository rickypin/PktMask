#!/usr/bin/env python3
"""PktMask Unified Entry Point - Desktop Application Priority"""

import typer

# Delayed import to avoid loading GUI dependencies for CLI users
app = typer.Typer(
    help="PktMask - PCAP/PCAPNG File Processing Tool",
    add_completion=False,  # Desktop application doesn't need shell completion
)


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """Launch GUI by default unless CLI command is explicitly called"""
    if ctx.invoked_subcommand is None:
        # Launch GUI when no subcommand
        from pktmask.gui.main_window import main as gui_main

        gui_main()
    # When there are subcommands, Typer handles automatically


# Import and register CLI commands (no nesting, keep simple)
from pktmask.cli import cmd_anon, cmd_batch, cmd_dedup, cmd_info, cmd_mask

app.command(
    "mask", help="Process PCAP files (Remove Dupes, Anonymize IPs, Mask Payloads)"
)(cmd_mask)
app.command("dedup", help="Execute Remove Dupes only")(cmd_dedup)
app.command("anon", help="Execute Anonymize IPs only")(cmd_anon)
app.command(
    "batch", help="Batch process all PCAP files in a directory with full pipeline"
)(cmd_batch)
app.command("info", help="Display information about PCAP files or directories")(
    cmd_info
)

if __name__ == "__main__":
    app()
