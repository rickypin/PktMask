#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PyInstaller hook for pydantic
确保pydantic及其所有依赖被正确包含在打包中
专门针对Pydantic v2进行优化
"""

from PyInstaller.utils.hooks import collect_all

# 收集pydantic的所有模块、数据文件和二进制文件
datas, binaries, hiddenimports = collect_all('pydantic')

# 收集pydantic-core的所有依赖
try:
    pydantic_core_datas, pydantic_core_binaries, pydantic_core_hiddenimports = collect_all('pydantic_core')
    datas.extend(pydantic_core_datas)
    binaries.extend(pydantic_core_binaries)
    hiddenimports.extend(pydantic_core_hiddenimports)
except ImportError:
    pass

# 添加额外的隐藏导入 - Pydantic v2 核心模块
hiddenimports += [
    # Pydantic 核心模块
    'pydantic.fields',
    'pydantic.main',
    'pydantic.typing',
    'pydantic.validators',
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
    
    # Pydantic v2 内部模块
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
    
    # Pydantic-core 模块
    'pydantic_core',
    'pydantic_core._pydantic_core',
    'pydantic_core.core_schema',
    
    # 依赖模块
    'typing_extensions',
    'annotated_types',
] 