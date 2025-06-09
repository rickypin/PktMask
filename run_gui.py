#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PktMask GUI应用程序启动脚本
"""

import sys
import os

# 添加src目录到Python路径，以便能够导入pktmask模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from pktmask.gui.main_window import main

if __name__ == "__main__":
    main() 