# TShark 跨平台安装指南

> **适用于**: PktMask v3.2+
> **更新日期**: 2025-07-17
> **支持平台**: macOS, Windows, Linux

PktMask 需要 TShark (Wireshark 命令行工具) 来处理网络数据包文件，特别是 TLS marker 功能。本指南提供跨平台的安装和配置说明。

---

## 系统要求

- **最低版本**: TShark >= 4.2.0
- **推荐版本**: TShark >= 4.4.0
- **来源**: Wireshark 官方发行版
- **必需功能**: TLS/SSL 协议支持、JSON 输出、TCP 重组

## 自动检测和验证

PktMask 会在启动时自动检测 TShark 安装：

1. **自动路径检测**: 检查常见安装路径和系统 PATH
2. **版本验证**: 确保版本满足最低要求
3. **功能验证**: 验证 TLS marker 所需的协议支持
4. **用户指导**: 提供平台特定的安装指导

---

## 安装方法

### macOS

#### 方法 1: Homebrew (推荐)
```bash
# 安装 Homebrew (如果尚未安装)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 安装 Wireshark (包含 tshark)
brew install --cask wireshark

# 验证安装
tshark -v
```

**自动检测路径**:
- Intel Mac: `/usr/local/bin/tshark`
- Apple Silicon Mac: `/opt/homebrew/bin/tshark`
- 应用程序路径: `/Applications/Wireshark.app/Contents/MacOS/tshark`

#### 方法 2: 官方安装包
1. 访问 [Wireshark 下载页面](https://www.wireshark.org/download.html)
2. 下载 macOS 版本的 `.dmg` 文件
3. 双击安装包并按照提示安装
4. 安装后，tshark 位于: `/Applications/Wireshark.app/Contents/MacOS/tshark`

#### 故障排除 (macOS)
```bash
# 检查 Homebrew 安装路径
which tshark

# 手动添加到 PATH (如果需要)
echo 'export PATH="/opt/homebrew/bin:$PATH"' >> ~/.zshrc  # Apple Silicon
echo 'export PATH="/usr/local/bin:$PATH"' >> ~/.zshrc     # Intel

# 重新加载 shell 配置
source ~/.zshrc
```

### Linux (Ubuntu/Debian)

```bash
# 更新包列表
sudo apt update

# 安装 Wireshark
sudo apt install wireshark

# 如果需要最新版本，添加官方 PPA
sudo add-apt-repository ppa:wireshark-dev/stable
sudo apt update
sudo apt install wireshark

# 验证安装
tshark -v
```

### Linux (CentOS/RHEL/Fedora)

```bash
# CentOS/RHEL 8+
sudo dnf install wireshark-cli

# CentOS/RHEL 7
sudo yum install wireshark

# Fedora
sudo dnf install wireshark-cli

# 验证安装
tshark -v
```

### Windows

#### 方法 1: 官方安装包 (推荐)
1. 访问 [Wireshark 下载页面](https://www.wireshark.org/download.html)
2. 下载 Windows 版本的 `.exe` 安装包
3. 以管理员权限运行安装程序
4. 在安装选项中确保选择了 "Command Line Tools"
5. 安装后，tshark 位于: `C:\Program Files\Wireshark\tshark.exe`

**自动检测路径**:
- `C:\Program Files\Wireshark\tshark.exe`
- `C:\Program Files (x86)\Wireshark\tshark.exe`

#### 方法 2: Chocolatey
```powershell
# 安装 Chocolatey (如果尚未安装)
Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))

# 安装 Wireshark
choco install wireshark

# 验证安装
tshark -v
```

**Chocolatey 自动检测路径**:
- `C:\ProgramData\chocolatey\bin\tshark.exe`
- `C:\tools\wireshark\tshark.exe`
- `C:\chocolatey\bin\tshark.exe` (旧版本)

#### 故障排除 (Windows)
```cmd
# 检查 PATH 环境变量
echo %PATH%

# 手动添加到 PATH (系统级)
setx PATH "%PATH%;C:\Program Files\Wireshark" /M

# 或者用户级
setx PATH "%PATH%;C:\Program Files\Wireshark"

# 重新打开命令提示符测试
tshark -v
```

#### PowerShell 配置
```powershell
# 检查执行策略
Get-ExecutionPolicy

# 如果需要，设置执行策略
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

---

## 安装验证

### 基本验证
```bash
# 检查 tshark 是否可用
tshark -v

# 检查版本是否满足要求 (>= 4.2.0)
tshark -v | grep -E "TShark.*[0-9]+\.[0-9]+\.[0-9]+"
```

### 使用 PktMask 验证脚本

#### 基础验证
```bash
# 运行基础 TShark 检测
python scripts/validate_tshark_setup.py --basic-only

# 完整验证（推荐）
python scripts/validate_tshark_setup.py --all

# 生成详细报告
python scripts/validate_tshark_setup.py --report
```

#### 自定义路径验证
```bash
# 验证自定义 TShark 路径
python scripts/validate_tshark_setup.py --tshark-path /custom/path/to/tshark

# 使用示例 PCAP 文件测试
python scripts/validate_tshark_setup.py --sample-pcap test.pcap --all
```

#### 旧版检查脚本（兼容性）
```bash
# 运行旧版依赖检查脚本
python scripts/check_tshark_dependencies.py

# 详细检查
python scripts/check_tshark_dependencies.py --verbose

# 如果 tshark 不在 PATH 中
python scripts/check_tshark_dependencies.py --tshark-path /path/to/tshark
```

---

## 跨平台故障排除

### 自动检测失败

如果 PktMask 无法自动检测到 TShark：

1. **检查安装**: 确认 TShark 已正确安装
2. **验证路径**: 使用验证脚本检查常见路径
3. **手动配置**: 在 PktMask 中配置自定义路径
4. **重新启动**: 安装后重新启动终端/应用程序

### TLS 功能验证失败

如果 TLS marker 功能验证失败：

```bash
# 检查 TLS 协议支持
tshark -G protocols | grep -i tls

# 检查必需字段支持
tshark -G fields | grep -E "(tls\.|tcp\.)"

# 测试 JSON 输出
tshark -T json -c 0

# 测试两遍分析
tshark -2 -c 0
```

### 权限问题

#### Linux/macOS
```bash
# 添加用户到 wireshark 组
sudo usermod -a -G wireshark $USER

# 或者使用 sudo 运行
sudo tshark -v
```

#### Windows
- 以管理员权限运行命令提示符
- 确保用户有执行权限

### 版本兼容性

```bash
# 检查当前版本
tshark -v

# 升级到最新版本
# macOS (Homebrew)
brew upgrade wireshark

# Windows (Chocolatey)
choco upgrade wireshark

# Linux (Ubuntu/Debian)
sudo apt update && sudo apt upgrade wireshark
```

---

## 常见问题解决

### 问题 1: "tshark: command not found"

**原因**: tshark 不在系统 PATH 中

**解决方案**:
```bash
# macOS: 添加到 PATH
echo 'export PATH="/Applications/Wireshark.app/Contents/MacOS:$PATH"' >> ~/.zshrc
source ~/.zshrc

# Linux: 通常安装后自动在 PATH 中
which tshark

# Windows: 添加到系统 PATH
# 将 C:\Program Files\Wireshark 添加到系统环境变量 PATH 中
```

### 问题 2: 版本过低

**症状**: `tshark 版本过低 (x.x.x)，需要 ≥ 4.2.0`

**解决方案**:
```bash
# Ubuntu: 使用官方 PPA 获取最新版本
sudo add-apt-repository ppa:wireshark-dev/stable
sudo apt update
sudo apt upgrade wireshark

# macOS: 更新 Homebrew 版本
brew upgrade wireshark

# Windows: 下载最新版本重新安装
```

### 问题 3: 权限问题 (Linux)

**症状**: 无法捕获网络接口或访问某些功能

**解决方案**:
```bash
# 将用户添加到 wireshark 组
sudo usermod -a -G wireshark $USER

# 重新登录或重启系统使更改生效

# 或者临时使用 sudo
sudo tshark -v
```

### 问题 4: 协议支持缺失

**症状**: 缺少 TCP、TLS 等协议支持

**解决方案**:
- 确保安装的是完整版 Wireshark，而不是精简版
- 重新安装 Wireshark，确保选择了所有组件
- 检查是否有多个版本冲突

---

## 配置建议

### 性能优化
```bash
# 对于大文件处理，可以调整内存限制
export WIRESHARK_MEMORY_LIMIT=2048

# 设置临时目录
export TMPDIR=/path/to/large/temp/directory
```

### 自定义路径配置
如果 tshark 安装在非标准位置，可以在 PktMask 配置中指定：

```python
# 在 PktMask 配置文件中
{
    "tools": {
        "tshark": {
            "custom_executable": "/custom/path/to/tshark"
        }
    }
}
```

---

## 验证清单

安装完成后，请确认以下项目：

- [ ] `tshark -v` 命令可以正常执行
- [ ] 版本号 >= 4.2.0
- [ ] 支持 JSON 输出: `tshark -T json -c 0`
- [ ] 支持协议列表: `tshark -G protocols | grep -E "(tcp|tls|ssl)"`
- [ ] 支持字段列表: `tshark -G fields | grep "tcp.stream"`
- [ ] PktMask 依赖检查脚本通过

---

## 获取帮助

如果遇到安装问题：

1. **查看 Wireshark 官方文档**: https://www.wireshark.org/docs/
2. **运行 PktMask 依赖检查**: `python scripts/check_tshark_dependencies.py --verbose`
3. **检查系统日志**: 查看是否有相关错误信息
4. **联系支持**: 提交 Issue 到 PktMask 项目仓库

---

## 相关链接

- [Wireshark 官方网站](https://www.wireshark.org/)
- [TShark 手册](https://www.wireshark.org/docs/man-pages/tshark.html)
- [PktMask TShark 依赖分析](docs/dev/TSHARK_DEPENDENCY_ANALYSIS.md)
- [PktMask 安装指南](README.md#installation)
