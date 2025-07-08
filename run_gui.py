#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PktMask GUI应用程序启动脚本（已弃用）
"""

import warnings
import sys
import os

# 显示弃用警告
warnings.warn(
    "\n" + "="*60 + "\n" +
    "⚠️  run_gui.py 已弃用！\n" +
    "\n" +
    "请使用以下方式启动 PktMask：\n" +
    "  • GUI 模式：./pktmask 或 python pktmask.py\n" +
    "  • CLI 模式：./pktmask mask|dedup|anon ...\n" +
    "\n" +
    "此文件将在下个版本中移除。\n" +
    "="*60,
    DeprecationWarning,
    stacklevel=2
)

# 添加src目录到Python路径，以便能够导入pktmask模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from pktmask.gui.main_window import main

if __name__ == "__main__":
    main()
