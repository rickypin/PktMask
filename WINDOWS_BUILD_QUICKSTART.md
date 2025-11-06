# Windows 软件包构建快速指南

## 🎯 目标

生成可在 Windows 上运行的 PktMask 软件包（Artifact）

## 📋 前提条件

- 已修复 GitHub Actions 构建配置
- 有 Git 和 GitHub 仓库访问权限

## 🚀 快速步骤

### 方法 1: 使用 GitHub Actions（推荐）

这是最简单的方法，无需 Windows 机器。

#### 步骤 1: 提交修复

```bash
# 添加修改的文件
git add .github/workflows/build.yml
git add docs/dev/WINDOWS_BUILD_GUIDE.md
git add scripts/build/test_build_windows.sh

# 提交更改
git commit -m "fix: update Windows build configuration for GitHub Actions"

# 推送到远程仓库
git push origin main
```

#### 步骤 2: 创建并推送版本标签

```bash
# 创建新版本标签（例如 v0.8.3）
git tag v0.8.3

# 推送标签到 GitHub（这会触发构建）
git push origin v0.8.3
```

#### 步骤 3: 监控构建过程

1. 打开浏览器，访问您的 GitHub 仓库
2. 点击 "Actions" 标签
3. 查看 "Build and Release" 工作流
4. 等待构建完成（通常需要 5-10 分钟）

#### 步骤 4: 下载 Windows 软件包

构建成功后，有两种方式获取软件包：

**方式 A: 从 Releases 页面下载（推荐）**
1. 访问 GitHub 仓库的 "Releases" 页面
2. 找到刚创建的版本（如 v0.8.3）
3. 下载 `PktMask-Windows.zip`

**方式 B: 从 Actions Artifacts 下载**
1. 在 Actions 页面，点击成功的工作流运行
2. 滚动到底部的 "Artifacts" 部分
3. 下载 `PktMask-Windows` artifact

### 方法 2: 本地构建（需要 Windows 机器）

如果您有 Windows 机器，可以本地构建：

```cmd
# 1. 克隆仓库
git clone https://github.com/yourusername/pktmask.git
cd pktmask

# 2. 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate

# 3. 安装依赖
pip install -e ".[build]"

# 4. 运行 PyInstaller
pyinstaller PktMask-Windows.spec

# 5. 测试
cd dist\PktMask
PktMask.exe
```

## 📦 构建产物说明

成功构建后，您会得到：

```
PktMask-Windows.zip
└── PktMask/
    ├── PktMask.exe          # 主程序（双击运行）
    ├── _internal/           # 依赖库（不要删除）
    │   ├── *.dll
    │   ├── PyQt6/
    │   ├── scapy/
    │   └── ...
    └── resources/           # 资源文件
        ├── log_template.html
        ├── summary.md
        └── ...
```

## ✅ 测试软件包

1. **解压缩** `PktMask-Windows.zip`
2. **双击** `PktMask.exe` 启动程序
3. **测试功能**:
   - 打开一个 pcap 文件
   - 点击 "Start Masking"
   - 验证输出文件

## 🔧 本次修复内容

修复了以下问题：

1. ✅ 更新 `.github/workflows/build.yml`:
   - Windows 构建使用 `PktMask-Windows.spec`（而非通用的 `PktMask.spec`）
   - 添加 `pyinstaller-hooks-contrib` 依赖
   - 启用 `fail-fast: false`，允许一个平台失败时其他平台继续构建
   - 修复 Windows 的 `ls` 命令为 `dir`

2. ✅ 创建文档:
   - `docs/dev/WINDOWS_BUILD_GUIDE.md` - 详细构建指南
   - `scripts/build/test_build_windows.sh` - 构建验证脚本

## 🐛 故障排除

### 如果构建失败

1. **查看构建日志**:
   - 在 GitHub Actions 页面点击失败的工作流
   - 展开 "Build Windows Installer" 步骤
   - 查看错误信息

2. **常见问题**:

   **问题**: `ModuleNotFoundError: No module named 'xxx'`
   **解决**: 在 `PktMask-Windows.spec` 的 `windows_hidden_imports` 中添加缺失的模块

   **问题**: `FileNotFoundError: [Errno 2] No such file or directory: 'xxx'`
   **解决**: 检查 `scripts/build/pyinstaller_common.py` 中的 `common_datas` 路径

   **问题**: PyQt6 相关错误
   **解决**: 确保 `PyQt6.QtCore`, `PyQt6.QtGui`, `PyQt6.QtWidgets` 在 hidden imports 中

### 如果需要重新构建

```bash
# 删除远程标签
git push --delete origin v0.8.3

# 删除本地标签
git tag -d v0.8.3

# 创建新标签并推送
git tag v0.8.3
git push origin v0.8.3
```

## 📚 更多信息

详细的构建文档请参考：
- `docs/dev/WINDOWS_BUILD_GUIDE.md` - 完整的 Windows 构建指南
- `.github/workflows/build.yml` - GitHub Actions 配置
- `PktMask-Windows.spec` - PyInstaller 配置

## 🎉 下一步

构建成功后，您可以：

1. **分发软件包**: 将 `PktMask-Windows.zip` 分享给用户
2. **发布 Release**: 在 GitHub Releases 页面添加发布说明
3. **测试**: 在不同的 Windows 版本上测试（Windows 10, 11）

## 💡 提示

- 每次推送新标签都会触发构建
- 构建过程完全自动化，无需手动干预
- 如果只想测试构建，可以使用 `v0.8.3-test` 这样的标签
- 构建产物会保留 90 天（GitHub Actions 默认设置）

---

**需要帮助？** 查看 [GitHub Issues](https://github.com/yourusername/pktmask/issues) 或参考详细文档。

