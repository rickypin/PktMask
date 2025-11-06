# GitHub Actions Build Fix - 2024

## 问题描述

GitHub Actions 构建失败，导致无法生成 Windows 软件包 Artifact。

### 错误现象

- **build (windows-latest, 3.11)** - 失败 ❌
- **build (macos-latest, 3.11)** - 被取消 ⚠️
- **release** - 未运行

### 根本原因

1. **错误的 spec 文件**: Windows 构建使用了通用的 `PktMask.spec` 而不是 Windows 专用的 `PktMask-Windows.spec`
2. **缺少依赖**: 未安装 `pyinstaller-hooks-contrib`
3. **错误的命令**: Windows 上使用了 `ls` 命令（应该用 `dir`）
4. **fail-fast 策略**: 一个平台失败导致其他平台构建被取消

## 修复方案

### 1. 更新 `.github/workflows/build.yml`

#### 修改 1: 添加 fail-fast: false

**位置**: 第 15 行

**修改前**:
```yaml
  build:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [windows-latest, macos-latest]
        python-version: ['3.11']
```

**修改后**:
```yaml
  build:
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false  # 允许一个平台失败时其他平台继续构建
      matrix:
        os: [windows-latest, macos-latest]
        python-version: ['3.11']
```

**原因**: 允许 macOS 构建在 Windows 构建失败时继续进行

---

#### 修改 2: 使用正确的 Windows spec 文件

**位置**: 第 38-43 行

**修改前**:
```yaml
    - name: Build Windows Installer
      if: matrix.os == 'windows-latest'
      run: |
        pip install pyinstaller
        pyinstaller PktMask.spec
        ls dist
```

**修改后**:
```yaml
    - name: Build Windows Installer
      if: matrix.os == 'windows-latest'
      run: |
        pip install pyinstaller pyinstaller-hooks-contrib
        pyinstaller PktMask-Windows.spec
        dir dist
```

**原因**:
- `PktMask-Windows.spec` 包含 Windows 特定的配置
- `pyinstaller-hooks-contrib` 提供额外的 hook 支持
- `dir` 是 Windows 的正确命令

---

#### 修改 3: 添加 pyinstaller-hooks-contrib 到 macOS 构建

**位置**: 第 45-50 行

**修改前**:
```yaml
    - name: Build macOS App
      if: matrix.os == 'macos-latest'
      run: |
        pip install pyinstaller
        pyinstaller PktMask.spec
        ls dist
```

**修改后**:
```yaml
    - name: Build macOS App
      if: matrix.os == 'macos-latest'
      run: |
        pip install pyinstaller pyinstaller-hooks-contrib
        pyinstaller PktMask.spec
        ls dist
```

**原因**: 保持一致性，确保 macOS 构建也有完整的依赖

---

### 2. 创建支持文档

#### 新增文件

1. **`docs/dev/WINDOWS_BUILD_GUIDE.md`**
   - 完整的 Windows 构建指南
   - 包含本地构建和 GitHub Actions 构建方法
   - 故障排除指南

2. **`WINDOWS_BUILD_QUICKSTART.md`**
   - 快速开始指南
   - 简化的步骤说明
   - 中文文档，便于理解

3. **`scripts/build/test_build_windows.sh`**
   - 构建验证脚本
   - 检查依赖和配置
   - 验证 spec 文件语法

## 验证步骤

### 1. 本地验证（可选）

```bash
# 运行验证脚本
bash scripts/build/test_build_windows.sh
```

### 2. 提交更改

```bash
# 添加修改的文件
git add .github/workflows/build.yml
git add docs/dev/WINDOWS_BUILD_GUIDE.md
git add docs/dev/GITHUB_ACTIONS_BUILD_FIX.md
git add WINDOWS_BUILD_QUICKSTART.md
git add scripts/build/test_build_windows.sh

# 提交
git commit -m "fix: update Windows build configuration for GitHub Actions

- Use PktMask-Windows.spec for Windows builds
- Add pyinstaller-hooks-contrib dependency
- Fix Windows command (dir instead of ls)
- Enable fail-fast: false for parallel builds
- Add comprehensive build documentation"

# 推送
git push origin main
```

### 3. 触发构建

```bash
# 创建新版本标签
git tag v0.8.3

# 推送标签（触发 GitHub Actions）
git push origin v0.8.3
```

### 4. 监控构建

1. 访问 GitHub Actions 页面
2. 查看 "Build and Release" 工作流
3. 确认两个平台都成功构建

### 5. 验证产物

1. 访问 Releases 页面
2. 下载 `PktMask-Windows.zip`
3. 解压并测试 `PktMask.exe`

## 预期结果

### 成功的构建流程

```
Build and Release Workflow
├── build (windows-latest, 3.11) ✅
│   ├── Checkout code
│   ├── Setup Python 3.11
│   ├── Install dependencies
│   ├── Build package
│   ├── Build Windows Installer (PktMask-Windows.spec)
│   └── Upload Windows Artifact
│
├── build (macos-latest, 3.11) ✅
│   ├── Checkout code
│   ├── Setup Python 3.11
│   ├── Install dependencies
│   ├── Build package
│   ├── Build macOS App (PktMask.spec)
│   ├── Sign macOS App (if certificates available)
│   └── Upload macOS Artifact
│
└── release ✅
    ├── Download all artifacts
    ├── Zip Windows App
    ├── Prepare macOS Release
    └── Create GitHub Release
```

### 构建产物

1. **PktMask-Windows.zip**
   - 包含 `PktMask.exe` 和所有依赖
   - 可在 Windows 10/11 上直接运行

2. **PktMask-macOS.dmg** (如果有签名证书)
   - 或 **PktMask-macOS-Unsigned.zip** (无签名证书)

## 技术细节

### PktMask-Windows.spec vs PktMask.spec

| 特性 | PktMask-Windows.spec | PktMask.spec |
|------|---------------------|--------------|
| 目标平台 | Windows | macOS |
| 图标文件 | PktMask.ico | PktMask.icns |
| 控制台窗口 | False (无窗口) | False |
| UPX 压缩 | False (兼容性) | True |
| 输出格式 | COLLECT | BUNDLE (.app) |
| 特殊配置 | Windows hidden imports | macOS bundle |

### Hidden Imports

Windows 特定的 hidden imports:

```python
windows_hidden_imports = [
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'PyQt6.sip',
    'pktmask',
    'pktmask.__main__',
    'pktmask.gui',
    'pktmask.gui.main_window',
    'scapy.all',
    'scapy.layers',
    'scapy.layers.inet',
    'scapy.layers.l2',
    'typer',
    'jinja2',
]
```

### 依赖包

构建所需的包:

```toml
[project.optional-dependencies]
build = [
    "pyinstaller",
    "pyinstaller-hooks-contrib",  # 新增
    "altgraph",
    "macholib"
]
```

## 故障排除

### 如果构建仍然失败

1. **检查构建日志**:
   ```
   GitHub Actions → 失败的工作流 → Build Windows Installer
   ```

2. **常见错误及解决方案**:

   | 错误 | 原因 | 解决方案 |
   |------|------|----------|
   | ModuleNotFoundError | 缺少 hidden import | 添加到 `windows_hidden_imports` |
   | FileNotFoundError | 数据文件路径错误 | 检查 `common_datas` 路径 |
   | ImportError: DLL load failed | 缺少系统库 | 添加到 `binaries` |
   | Qt platform plugin error | Qt 插件未包含 | 检查 PyQt6 安装 |

3. **重新触发构建**:
   ```bash
   # 删除标签
   git push --delete origin v0.8.3
   git tag -d v0.8.3
   
   # 重新创建并推送
   git tag v0.8.3
   git push origin v0.8.3
   ```

## 后续优化建议

1. **添加构建缓存**:
   - 缓存 pip 依赖
   - 缓存 PyInstaller 构建

2. **添加自动测试**:
   - 在构建后运行基本测试
   - 验证可执行文件能够启动

3. **优化构建时间**:
   - 并行化构建步骤
   - 使用更快的 runner

4. **添加构建通知**:
   - 构建成功/失败时发送通知
   - 集成 Slack/Discord

## 参考资料

- [PyInstaller Documentation](https://pyinstaller.org/en/stable/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [PyInstaller Hooks Contrib](https://github.com/pyinstaller/pyinstaller-hooks-contrib)

## 更新历史

- **2024-11-06**: 初始修复
  - 修复 Windows 构建配置
  - 添加 fail-fast: false
  - 创建构建文档

---

**修复完成**: 现在可以通过 GitHub Actions 成功构建 Windows 软件包了！

