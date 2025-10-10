"""
Compatibility layer: re-export exceptions from the new location.

Legacy path: `pktmask.shared.exceptions`
Current path: `pktmask.common.exceptions`
"""

from pktmask.common.exceptions import *  # noqa: F401,F403
