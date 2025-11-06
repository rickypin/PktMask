# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

# 将项目根目录添加到 Python 路径，以便导入 scripts 模块
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from scripts.build.pyinstaller_common import common_datas, common_hiddenimports

a = Analysis(
    ['scripts/pktmask_launcher.py'],
    pathex=['src'],
    binaries=[],
    datas=common_datas,
    hiddenimports=common_hiddenimports,
    hookspath=['hooks'],
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
    icon='assets/PktMask.ico',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
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
    upx=True,
    upx_exclude=[],
    name='PktMask',
)
app = BUNDLE(
    coll,
    name='PktMask.app',
    icon='assets/PktMask.icns',
    bundle_identifier=None,
)