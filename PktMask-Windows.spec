# -*- mode: python ; coding: utf-8 -*-
"""
Windows-specific PyInstaller spec file for PktMask
解决Windows构建中start button无反应的问题
"""

import sys
import os
from pathlib import Path

# 获取项目根目录
project_root = Path(__file__).parent
src_path = project_root / 'src'

# 将项目根目录添加到 Python 路径，以便导入 scripts 模块
sys.path.insert(0, str(project_root))

from scripts.build.pyinstaller_common import common_datas, common_hiddenimports

# Windows特定的隐藏导入
windows_hidden_imports = common_hiddenimports + [
    # PyQt6 (Windows)
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'PyQt6.sip',

    # PktMask core modules (high-level only)
    'pktmask',
    'pktmask.__main__',
    'pktmask.gui',
    'pktmask.gui.main_window',

    # Scapy extras
    'scapy.all',
    'scapy.layers',
    'scapy.layers.inet',
    'scapy.layers.l2',

    # CLI/templating
    'typer',
    'jinja2',
]

a = Analysis(
    ['scripts/pktmask_launcher.py'],
    pathex=[str(src_path)],
    binaries=[],
    datas=common_datas,
    hiddenimports=windows_hidden_imports,
    hookspath=['hooks'] if os.path.exists('hooks') else [],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PktMask',
    icon='assets/PktMask.ico' if os.path.exists('assets/PktMask.ico') else None,
    debug=False,  # 禁用调试模式以减少控制台输出
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # 禁用UPX压缩，避免Windows兼容性问题
    console=False,  # 禁用控制台窗口，防止cmd窗口弹出
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,  # 禁用UPX压缩
    upx_exclude=[],
    name='PktMask',
)
