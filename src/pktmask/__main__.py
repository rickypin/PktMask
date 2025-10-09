#!/usr/bin/env python3
"""PktMask Unified Entry Point - Desktop Application Priority"""

import os

import typer

# Import and register simplified CLI commands
from pktmask.cli.commands import config_command, process_command, validate_command

# Delayed import to avoid loading GUI dependencies for CLI users
app = typer.Typer(
    help="PktMask - PCAP/PCAPNG File Processing Tool",
    add_completion=False,  # Desktop application doesn't need shell completion
)


# Initialize logging system with environment variable support
try:
    import logging

    from pktmask.infrastructure.logging import get_logger as _ensure_logger

    _ensure_logger()  # Initialize logging system

    # Support PKTMASK_LOG_LEVEL environment variable for runtime log level control
    # Valid values: DEBUG, INFO, WARNING, ERROR, CRITICAL
    # Example: PKTMASK_LOG_LEVEL=DEBUG pktmask process input.pcap -o output.pcap
    env_log_level = os.environ.get("PKTMASK_LOG_LEVEL", "").upper()
    if env_log_level in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        pkt_logger = logging.getLogger("pktmask")
        log_level = getattr(logging, env_log_level)
        pkt_logger.setLevel(log_level)
        for handler in pkt_logger.handlers:
            if isinstance(handler, logging.StreamHandler):
                handler.setLevel(log_level)
        pkt_logger.debug(f"Log level set to {env_log_level} via PKTMASK_LOG_LEVEL environment variable")
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
app.command("process", help="Process PCAP/PCAPNG files with unified core processing")(process_command)
app.command("validate", help="Validate PCAP/PCAPNG files without processing")(validate_command)
app.command("config", help="Display configuration summary for given options")(config_command)

if __name__ == "__main__":
    app()
