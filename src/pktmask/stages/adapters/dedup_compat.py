"""
向后兼容代理文件

此文件用于保持向后兼容性。
请使用新的导入路径：pktmask.adapters.compatibility.dedup_compat
"""

import warnings
from pktmask.adapters.compatibility.dedup_compat import *

warnings.warn(
    f"导入路径 '{__name__}' 已废弃，"
    f"请使用 'pktmask.adapters.compatibility.dedup_compat' 替代。"
    f"此兼容性支持将在 v2.0 中移除。",
    DeprecationWarning,
    stacklevel=2
)
