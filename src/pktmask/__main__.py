#!/usr/bin/env python3
"""PktMask Unified Entry Point - Desktop Application Priority"""

import typer

# Import and register simplified CLI commands
from pktmask.cli.commands import config_command, process_command, validate_command

# Delayed import to avoid loading GUI dependencies for CLI users
app = typer.Typer(
    help="PktMask - PCAP/PCAPNG File Processing Tool",
    add_completion=False,  # Desktop application doesn't need shell completion
)


# TEMP: force pktmask logger to DEBUG for troubleshooting
try:
    import logging

    from pktmask.infrastructure.logging import get_logger  # ensure handlers initialized

    pkt_logger = logging.getLogger("pktmask")
    pkt_logger.setLevel(logging.DEBUG)
    for _h in pkt_logger.handlers:
        _h.setLevel(logging.DEBUG)
    pkt_logger.debug("[TEMP] Logger level forced to DEBUG (will be reverted later)")
except Exception:
    pass


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """Launch GUI by default unless CLI command is explicitly called"""
    if ctx.invoked_subcommand is None:
        # Launch GUI when no subcommand
        from pktmask.gui.main_window import main as gui_main

        gui_main()
    # When there are subcommands, Typer handles automatically


# Register core commands using new simplified interface
app.command("process", help="Process PCAP/PCAPNG files with unified core processing")(
    process_command
)
app.command("validate", help="Validate PCAP/PCAPNG files without processing")(
    validate_command
)
app.command("config", help="Display configuration summary for given options")(
    config_command
)

if __name__ == "__main__":
    app()
