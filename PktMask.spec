# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['scripts/pktmask_launcher.py'],
    pathex=['src'],
    binaries=[],
    datas=[
        ('config/templates/log_template.html', 'resources'),
        ('config/templates/summary.md', 'resources'),
        ('config/templates/config_template.yaml', 'resources'),
        ('config/templates/tls_flow_analysis_template.html', 'resources'),
    ],
    hiddenimports=[
        # Keep hidden imports minimal and high-level; rely on pyinstaller-hooks-contrib
        'markdown',
        'pydantic',
        'pydantic_core',
        'yaml',
        'typing_extensions',
        'annotated_types',
        'scapy',
    ],
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