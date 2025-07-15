#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PktMask GUI application startup script (deprecated)
"""

import warnings
import sys
import os

# Show deprecation warning
warnings.warn(
    "\n" + "="*60 + "\n" +
    "⚠️  run_gui.py is deprecated!\n" +
    "\n" +
    "Please use the following methods to start PktMask:\n" +
    "  • GUI mode: ./pktmask or python pktmask.py\n" +
    "  • CLI mode: ./pktmask mask|dedup|anon ...\n" +
    "\n" +
    "This file will be removed in the next version.\n" +
    "="*60,
    DeprecationWarning,
    stacklevel=2
)

# Add src directory to Python path to enable importing pktmask module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from pktmask.gui.main_window import main

if __name__ == "__main__":
    main()
