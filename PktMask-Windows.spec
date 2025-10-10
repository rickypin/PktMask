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

# Windows特定的隐藏导入
windows_hidden_imports = [
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
    'pktmask.gui.managers',

    # Third-party high-level imports
    'markdown',
    'pydantic',
    'pydantic_core',
    'yaml',
    'typing_extensions',
    'annotated_types',

    # Scapy
    'scapy',
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
    datas=[
        (str(Path.cwd() / 'config' / 'templates' / 'log_template.html'), 'resources'),
        (str(Path.cwd() / 'config' / 'templates' / 'summary.md'), 'resources'),
        (str(Path.cwd() / 'config' / 'templates' / 'config_template.yaml'), 'resources'),
        (str(Path.cwd() / 'config' / 'templates' / 'tls_flow_analysis_template.html'), 'resources'),
    ],
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
