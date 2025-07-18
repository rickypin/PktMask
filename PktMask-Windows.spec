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
    # PyQt6 Windows特定模块
    'PyQt6.QtCore',
    'PyQt6.QtGui', 
    'PyQt6.QtWidgets',
    'PyQt6.sip',
    
    # PktMask核心模块
    'pktmask',
    'pktmask.__main__',
    'pktmask.gui',
    'pktmask.gui.main_window',
    'pktmask.gui.managers',
    'pktmask.gui.managers.pipeline_manager',
    'pktmask.gui.managers.ui_manager',
    'pktmask.gui.managers.file_manager',
    'pktmask.gui.managers.report_manager',
    'pktmask.gui.managers.dialog_manager',
    'pktmask.gui.managers.event_coordinator',
    'pktmask.services',
    'pktmask.services.pipeline_service',
    'pktmask.config',
    'pktmask.config.app_config',
    'pktmask.config.settings',
    
    # 第三方库
    'markdown',
    'markdown.extensions',
    'markdown.preprocessors',
    'markdown.postprocessors',
    'markdown.blockprocessors',
    'markdown.inlinepatterns',
    'markdown.treeprocessors',
    'markdown.util',
    'pydantic',
    'pydantic.fields',
    'pydantic.main',
    'pydantic.typing',
    'pydantic.validators',
    'pydantic._internal',
    'pydantic._internal._config',
    'pydantic._internal._decorators',
    'pydantic._internal._fields',
    'pydantic._internal._generate_schema',
    'pydantic._internal._model_construction',
    'pydantic._internal._typing_extra',
    'pydantic._internal._utils',
    'pydantic._internal._validators',
    'pydantic._internal._mock_val_ser',
    'pydantic._internal._model_serialization',
    'pydantic._internal._schema_generation_shared',
    'pydantic._internal._std_types_schema',
    'pydantic._internal._dataclasses',
    'pydantic._internal._discriminated_union',
    'pydantic.config',
    'pydantic.dataclasses',
    'pydantic.json_schema',
    'pydantic.types',
    'pydantic.networks',
    'pydantic.color',
    'pydantic.datetime_parse',
    'pydantic.decorator',
    'pydantic.error_wrappers',
    'pydantic.functional_validators',
    'pydantic.functional_serializers',
    'pydantic_core',
    'pydantic_core._pydantic_core',
    'pydantic_core.core_schema',
    'yaml',
    'yaml.loader',
    'yaml.dumper',
    'yaml.representer',
    'yaml.resolver',
    'yaml.constructor',
    'yaml.composer',
    'yaml.scanner',
    'yaml.parser',
    'yaml.emitter',
    'yaml.serializer',
    'typing_extensions',
    'annotated_types',
    
    # Scapy相关
    'scapy',
    'scapy.all',
    'scapy.layers',
    'scapy.layers.inet',
    'scapy.layers.l2',
    
    # 其他依赖
    'typer',
    'jinja2',
    'psutil',
    'watchdog',
    'networkx',
    'pyshark'
]

a = Analysis(
    ['pktmask_launcher.py'],
    pathex=[str(src_path)],
    binaries=[],
    datas=[
        (str(src_path / 'pktmask' / 'resources' / 'log_template.html'), 'resources'),
        (str(src_path / 'pktmask' / 'resources' / 'summary.md'), 'resources'),
        (str(src_path / 'pktmask' / 'resources' / 'config_template.yaml'), 'resources'),
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
