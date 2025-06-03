# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['src/pktmask/main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('src/pktmask/resources/log_template.html', 'resources'),
        ('src/pktmask/resources/summary.md', 'resources'),
    ],
    hiddenimports=[
        'markdown',
        'markdown.extensions',
        'markdown.preprocessors',
        'markdown.postprocessors',
        'markdown.blockprocessors',
        'markdown.inlinepatterns',
        'markdown.treeprocessors',
        'markdown.util'
    ],
    hookspath=[],
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
    icon=None,
    bundle_identifier=None,
)
