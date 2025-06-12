# PktMask 应用打包指南

## 概述

本文档描述了如何将 PktMask 应用打包为独立的可执行文件，特别是在添加了配置管理系统（Pydantic + PyYAML）后的打包配置。

## 依赖要求

### 运行时依赖
- Python 3.8+
- PyQt6
- Scapy
- Pydantic 2.x
- PyYAML
- Markdown
- Jinja2

### 构建依赖
- PyInstaller
- 自定义钩子文件（位于 `hooks/` 目录）

## 快速打包

### 使用自动化脚本
```bash
./build_app.sh
```

### 手动打包
```bash
# 1. 清理之前的构建
rm -rf build/ dist/

# 2. 运行 PyInstaller
pyinstaller PktMask.spec

# 3. 测试应用
./dist/PktMask.app/Contents/MacOS/PktMask
```

## 打包配置详解

### 1. PyInstaller Spec 文件 (PktMask.spec)

关键配置项：

```python
a = Analysis(
    ['run_gui.py'],
    pathex=['src'],
    binaries=[],
    datas=[
        ('src/pktmask/resources/log_template.html', 'resources'),
        ('src/pktmask/resources/summary.md', 'resources'),
        ('src/pktmask/resources/config_template.yaml', 'resources'),  # 新增
    ],
    hiddenimports=[
        # Markdown 依赖
        'markdown',
        'markdown.extensions',
        'markdown.preprocessors',
        # ... 其他 markdown 模块
        
        # Pydantic 依赖 (新增)
        'pydantic',
        'pydantic.fields',
        'pydantic.main',
        'pydantic.typing',
        'pydantic.validators',
        'pydantic._internal',
        'pydantic.config',
        'pydantic.dataclasses',
        'pydantic.json_schema',
        'pydantic.types',
        'pydantic.networks',
        'pydantic.color',
        
        # PyYAML 依赖 (新增)
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
        
        # 类型注解依赖 (新增)
        'typing_extensions',
        'annotated_types'
    ],
    hookspath=['hooks'],  # 使用自定义钩子
    # ... 其他配置
)
```

### 2. 自定义钩子文件

#### hooks/hook-pydantic.py
确保 Pydantic 及其所有依赖被正确包含：

```python
from PyInstaller.utils.hooks import collect_all

# 收集pydantic的所有模块、数据文件和二进制文件
datas, binaries, hiddenimports = collect_all('pydantic')

# 添加额外的隐藏导入
hiddenimports += [
    'pydantic.fields',
    'pydantic.main',
    # ... 其他pydantic模块
]
```

#### hooks/hook-yaml.py
确保 PyYAML 及其所有依赖被正确包含：

```python
from PyInstaller.utils.hooks import collect_all

# 收集yaml的所有模块、数据文件和二进制文件
datas, binaries, hiddenimports = collect_all('yaml')

# 添加额外的隐藏导入
hiddenimports += [
    'yaml.loader',
    'yaml.dumper',
    # ... 其他yaml模块
]
```

## 常见问题与解决方案

### 1. ModuleNotFoundError: No module named 'pydantic'

**问题**: 打包后运行时找不到 pydantic 模块

**解决方案**:
1. 确保在 `hiddenimports` 中包含了所有 pydantic 相关模块
2. 使用自定义钩子文件 `hooks/hook-pydantic.py`
3. 在 spec 文件中设置 `hookspath=['hooks']`

### 2. ModuleNotFoundError: No module named 'yaml'

**问题**: 打包后运行时找不到 yaml 模块

**解决方案**:
1. 确保在 `hiddenimports` 中包含了所有 yaml 相关模块
2. 使用自定义钩子文件 `hooks/hook-yaml.py`
3. 特别注意包含 C 扩展模块 `_yaml`

### 3. 配置文件找不到

**问题**: 打包后运行时找不到配置模板文件

**解决方案**:
在 spec 文件的 `datas` 中添加：
```python
('src/pktmask/resources/config_template.yaml', 'resources'),
```

### 4. Pydantic 验证错误

**问题**: 打包后 Pydantic 模型验证失败

**解决方案**:
1. 确保包含了 `pydantic._internal` 的所有子模块
2. 包含 `typing_extensions` 和 `annotated_types`
3. 在钩子文件中使用 `collect_all('pydantic')` 自动收集所有依赖

## 构建优化

### 减少应用大小
1. 使用 `--exclude-module` 排除不需要的模块
2. 考虑使用 `--onefile` 模式（但启动可能较慢）
3. 移除调试信息：`debug=False`

### 提高启动速度
1. 使用 `upx=True` 压缩可执行文件
2. 避免过多的隐藏导入
3. 优化导入顺序

## 测试检查清单

打包完成后，请验证以下功能：

- [ ] 应用能正常启动
- [ ] 配置系统正常工作
- [ ] 配置文件能正确创建和读取
- [ ] YAML/JSON 配置格式都支持
- [ ] 配置验证功能正常
- [ ] 主要处理功能正常
- [ ] 日志系统正常工作
- [ ] GUI 主题和样式正确

## 版本兼容性

| 组件 | 版本要求 | 备注 |
|------|----------|------|
| Python | 3.8+ | 推荐 3.9+ |
| PyInstaller | 6.0+ | 支持最新的 Python 版本 |
| Pydantic | 2.0+ | V2 有重大变更，需要特殊处理 |
| PyYAML | 6.0+ | 包含 C 扩展，需要钩子支持 |
| PyQt6 | 6.4+ | GUI 框架 |

## 打包脚本说明

`build_app.sh` 脚本自动化了整个打包过程：

1. **环境检查**: 验证虚拟环境和依赖
2. **清理构建**: 删除之前的构建文件
3. **依赖验证**: 确保所有必要的包都已安装
4. **执行打包**: 运行 PyInstaller
5. **结果验证**: 检查打包结果和应用大小

使用方法：
```bash
chmod +x build_app.sh
./build_app.sh
```

## 故障排除

### 查看详细错误信息
```bash
# 运行打包的应用并查看完整错误信息
./dist/PktMask.app/Contents/MacOS/PktMask

# 查看 PyInstaller 警告
cat build/PktMask/warn-PktMask.txt
```

### 调试缺失的模块
```bash
# 检查哪些模块被包含
python -c "
import sys
sys.path.insert(0, 'dist/PktMask.app/Contents/MacOS')
import PyInstaller.loader.pyimod02_importers
print(sys.modules.keys())
"
```

### 重新生成 spec 文件
如果需要重新生成 spec 文件：
```bash
pyi-makespec --onedir --windowed \
    --paths src \
    --add-data "src/pktmask/resources:resources" \
    --hidden-import pydantic \
    --hidden-import yaml \
    run_gui.py
```

## 更新日志

### v2.0 (配置系统集成)
- 添加 Pydantic 和 PyYAML 支持
- 创建自定义钩子文件
- 更新 spec 文件配置
- 添加配置模板文件支持
- 创建自动化打包脚本

### v1.0 (初始版本)
- 基础 PyInstaller 配置
- PyQt6 和 Scapy 支持
- Markdown 和 Jinja2 支持 