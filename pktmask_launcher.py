#!/usr/bin/env python3
"""PktMask 启动脚本（Windows 兼容）"""
import os
import sys

# 添加 src 目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from pktmask.__main__ import app

if __name__ == "__main__":
    sys.exit(app())
