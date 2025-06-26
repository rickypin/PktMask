#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PyInstaller hook for PyYAML
确保PyYAML及其所有依赖被正确包含在打包中
"""

from PyInstaller.utils.hooks import collect_all

# 收集yaml的所有模块、数据文件和二进制文件
datas, binaries, hiddenimports = collect_all('yaml')

# 添加额外的隐藏导入
hiddenimports += [
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
    'yaml.nodes',
    'yaml.events',
    'yaml.tokens',
    '_yaml',  # C扩展模块
] 