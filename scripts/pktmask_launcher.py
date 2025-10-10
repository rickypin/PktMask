#!/usr/bin/env python3
"""Launcher script for PyInstaller builds.
It delegates to pktmask.__main__.app, which launches the GUI by default
and handles CLI subcommands when provided.
"""
from pktmask.__main__ import app

if __name__ == "__main__":
    app()
