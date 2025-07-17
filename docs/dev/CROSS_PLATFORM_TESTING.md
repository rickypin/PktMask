# PktMask 跨平台测试指南

> **更新日期**: 2025-07-17  
> **适用版本**: PktMask v3.2+

本文档描述了 PktMask 跨平台功能的测试方法和验证流程，特别是 TShark 集成的跨平台支持。

---

## 测试环境

### 支持的平台

| 平台 | 版本 | TShark 来源 | 测试状态 |
|------|------|-------------|----------|
| macOS | 10.15+ | Homebrew, 官方安装包 | ✅ 已测试 |
| Windows | 10/11 | 官方安装包, Chocolatey | ✅ 已测试 |
| Linux | Ubuntu 20.04+ | apt, 官方包 | ✅ 已测试 |

### 测试工具

- **自动化验证**: `scripts/validate_tshark_setup.py`
- **依赖检查**: `scripts/check_tshark_dependencies.py`
- **GUI 测试**: 内置依赖对话框
- **单元测试**: `tests/infrastructure/test_tshark_manager.py`

---

## 自动化测试

### 基础功能测试

```bash
# 运行所有平台测试
python scripts/validate_tshark_setup.py --all

# 生成详细报告
python scripts/validate_tshark_setup.py --report

# 测试特定路径
python scripts/validate_tshark_setup.py --tshark-path /custom/path
```

### TLS 功能测试

```bash
# 验证 TLS marker 功能
python -c "
from pktmask.infrastructure.tshark import validate_tls_marker_functionality
result = validate_tls_marker_functionality()
print('TLS validation:', 'PASSED' if result.success else 'FAILED')
"

# 使用示例 PCAP 测试
python scripts/validate_tshark_setup.py --sample-pcap tests/data/sample_tls.pcap
```

### 启动依赖测试

```bash
# 测试启动时依赖检查
python -c "
from pktmask.infrastructure.startup import validate_startup_dependencies
result = validate_startup_dependencies(strict_mode=True)
print('Startup validation:', 'PASSED' if result.success else 'FAILED')
"
```

---

## 手动测试流程

### 1. 安装验证

#### macOS 测试
```bash
# Homebrew 安装测试
brew install --cask wireshark
which tshark
tshark -v

# 官方安装包测试
# 下载并安装 .dmg 文件
ls -la /Applications/Wireshark.app/Contents/MacOS/tshark
/Applications/Wireshark.app/Contents/MacOS/tshark -v
```

#### Windows 测试
```cmd
# 官方安装包测试
"C:\Program Files\Wireshark\tshark.exe" -v

# Chocolatey 测试
choco install wireshark
tshark -v
```

#### Linux 测试
```bash
# Ubuntu/Debian
sudo apt install wireshark
tshark -v

# 检查权限
sudo usermod -a -G wireshark $USER
```

### 2. 路径检测测试

```python
# 测试自动路径检测
from pktmask.infrastructure.tshark import TSharkManager

manager = TSharkManager()
info = manager.detect_tshark()

print(f"Status: {info.status}")
print(f"Path: {info.path}")
print(f"Version: {info.version_formatted}")
```

### 3. GUI 集成测试

1. 启动 PktMask GUI
2. 如果 TShark 未安装，应显示依赖对话框
3. 测试手动路径配置功能
4. 验证安装指导的准确性

---

## 测试用例

### TC001: 基础 TShark 检测
- **目标**: 验证 TShark 自动检测功能
- **步骤**: 
  1. 在有 TShark 的系统上运行检测
  2. 验证返回正确的路径和版本
- **预期**: 检测成功，返回有效信息

### TC002: 跨平台路径检测
- **目标**: 验证不同平台的路径检测
- **步骤**:
  1. 在每个支持平台上安装 TShark
  2. 运行路径检测测试
- **预期**: 正确检测到平台特定的安装路径

### TC003: TLS 功能验证
- **目标**: 验证 TLS marker 所需功能
- **步骤**:
  1. 运行 TLS 功能验证
  2. 检查所有必需能力
- **预期**: 所有 TLS 功能检查通过

### TC004: 版本兼容性
- **目标**: 验证版本要求检查
- **步骤**:
  1. 测试低于最低版本的 TShark
  2. 测试满足要求的版本
- **预期**: 正确识别版本兼容性

### TC005: 错误处理
- **目标**: 验证错误情况处理
- **步骤**:
  1. 测试 TShark 不存在的情况
  2. 测试权限错误
  3. 测试版本过低
- **预期**: 提供清晰的错误信息和指导

### TC006: 自定义路径配置
- **目标**: 验证手动路径配置
- **步骤**:
  1. 配置自定义 TShark 路径
  2. 验证路径有效性
- **预期**: 正确使用自定义路径

---

## 性能测试

### 检测性能
```bash
# 测量检测时间
time python -c "
from pktmask.infrastructure.tshark import TSharkManager
manager = TSharkManager()
info = manager.detect_tshark()
"
```

### 验证性能
```bash
# 测量 TLS 验证时间
time python -c "
from pktmask.infrastructure.tshark import validate_tls_marker_functionality
result = validate_tls_marker_functionality()
"
```

---

## 回归测试

### 自动化回归测试脚本

```bash
#!/bin/bash
# regression_test.sh

echo "=== PktMask 跨平台回归测试 ==="

# 基础功能测试
echo "1. 基础 TShark 检测..."
python scripts/validate_tshark_setup.py --basic-only || exit 1

# TLS 功能测试
echo "2. TLS 功能验证..."
python -c "
from pktmask.infrastructure.tshark import validate_tls_marker_functionality
result = validate_tls_marker_functionality()
exit(0 if result.success else 1)
" || exit 1

# 启动依赖测试
echo "3. 启动依赖检查..."
python -c "
from pktmask.infrastructure.startup import validate_startup_dependencies
result = validate_startup_dependencies()
exit(0 if result.success else 1)
" || exit 1

echo "✅ 所有回归测试通过"
```

### CI/CD 集成

```yaml
# .github/workflows/cross-platform-test.yml
name: Cross-Platform TShark Tests

on: [push, pull_request]

jobs:
  test:
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]
    
    runs-on: ${{ matrix.os }}
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.9'
    
    - name: Install TShark (Ubuntu)
      if: matrix.os == 'ubuntu-latest'
      run: |
        sudo apt update
        sudo apt install -y wireshark
    
    - name: Install TShark (macOS)
      if: matrix.os == 'macos-latest'
      run: |
        brew install --cask wireshark
    
    - name: Install TShark (Windows)
      if: matrix.os == 'windows-latest'
      run: |
        choco install wireshark
    
    - name: Run cross-platform tests
      run: |
        python scripts/validate_tshark_setup.py --all
```

---

## 故障排除

### 常见测试问题

1. **权限错误** (Linux/macOS)
   ```bash
   sudo usermod -a -G wireshark $USER
   newgrp wireshark
   ```

2. **PATH 问题** (Windows)
   ```cmd
   setx PATH "%PATH%;C:\Program Files\Wireshark"
   ```

3. **版本不兼容**
   - 升级到 TShark >= 4.2.0
   - 检查发行版本兼容性

### 测试数据

测试用的示例 PCAP 文件应包含：
- TLS 握手数据
- 应用数据记录
- 多个 TCP 流
- IPv4 和 IPv6 流量

---

## 报告问题

测试失败时，请收集以下信息：

1. **系统信息**:
   ```bash
   python -c "import platform; print(platform.platform())"
   ```

2. **TShark 信息**:
   ```bash
   tshark -v
   which tshark  # Linux/macOS
   where tshark  # Windows
   ```

3. **验证报告**:
   ```bash
   python scripts/validate_tshark_setup.py --report > tshark_report.txt
   ```

4. **错误日志**: 包含完整的错误堆栈跟踪

将这些信息连同问题描述一起提交到项目 issue 跟踪器。
