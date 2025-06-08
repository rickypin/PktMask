#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PyInstaller hook for pydantic
确保pydantic及其所有依赖被正确包含在打包中
"""

from PyInstaller.utils.hooks import collect_all

# 收集pydantic的所有模块、数据文件和二进制文件
datas, binaries, hiddenimports = collect_all('pydantic')

# 添加额外的隐藏导入
hiddenimports += [
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
    'pydantic.config',
    'pydantic.dataclasses',
    'pydantic.json_schema',
    'pydantic.types',
    'pydantic.networks',
    'pydantic.color',
    'typing_extensions',
    'annotated_types',
] 