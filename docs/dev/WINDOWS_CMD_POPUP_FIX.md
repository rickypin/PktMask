# Windows CMD窗口弹出问题修复方案

## 问题概述

在Windows环境下运行PktMask时，会反复弹出cmd窗口，严重影响用户体验。经过分析，发现问题主要来源于以下几个方面：

1. **TShark/Editcap调用**: 大量使用`subprocess.run()`调用外部工具时未设置Windows特定的创建标志
2. **系统文件管理器调用**: 打开目录时会短暂显示cmd窗口
3. **PyInstaller配置**: 启用了控制台窗口显示

## 修复方案

### 1. 创建统一的隐藏subprocess工具

**文件**: `src/pktmask/utils/subprocess_utils.py`

创建了专门的工具函数来处理Windows下的subprocess调用：

- `get_subprocess_creation_flags()`: 获取Windows特定的创建标志
- `run_hidden_subprocess()`: 通用的隐藏subprocess执行函数
- `run_tshark_command()`: 专门用于tshark命令的执行
- `run_editcap_command()`: 专门用于editcap命令的执行
- `open_directory_hidden()`: 隐藏方式打开系统文件管理器

**关键技术**:
```python
# Windows下使用这些标志隐藏控制台窗口
subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
```

### 2. 修复的文件和场景

#### 2.1 TShark相关调用

**修复文件**:
- `src/pktmask/tools/tls23_marker.py`
- `src/pktmask/tools/enhanced_tls_marker.py`
- `src/pktmask/tools/tls_flow_analyzer.py`
- `src/pktmask/core/pipeline/stages/mask_payload_v2/marker/tls_marker.py`
- `src/pktmask/infrastructure/dependency/checker.py`

**修复场景**:
- TShark版本检查 (`tshark -v`)
- TShark协议支持检查 (`tshark -G protocols`)
- TShark JSON输出测试 (`tshark -T json`)
- TLS消息扫描和分析
- TCP流分析

#### 2.2 Editcap调用

**修复文件**:
- `src/pktmask/tools/tls23_marker.py`

**修复场景**:
- PCAP文件注释写入

#### 2.3 系统文件管理器调用

**修复文件**:
- `src/pktmask/utils/file_ops.py`

**修复场景**:
- 在系统文件管理器中打开目录

#### 2.4 PyInstaller配置

**修复文件**:
- `PktMask-Windows.spec`

**修复内容**:
- 将`console=True`改为`console=False`
- 将`debug=True`改为`debug=False`

## 修复效果

### 修复前
- 每次调用tshark都会弹出cmd窗口
- 每次调用editcap都会弹出cmd窗口
- 打开文件夹时会短暂显示cmd窗口
- PyInstaller打包的程序会显示控制台窗口

### 修复后
- 所有外部工具调用都在后台静默执行
- 用户界面更加流畅，无cmd窗口干扰
- 保持所有原有功能不变

## 测试验证

### 自动化测试
运行测试脚本验证修复效果：
```bash
python scripts/test/test_windows_cmd_popup_fix.py
```

### 手动测试场景
1. **启动GUI**: 确认无控制台窗口显示
2. **处理PCAP文件**: 确认处理过程中无cmd窗口弹出
3. **打开输出目录**: 确认文件管理器打开时无cmd窗口
4. **依赖检查**: 确认tshark检查时无cmd窗口

## 兼容性说明

- **Windows**: 完全修复cmd窗口弹出问题
- **macOS/Linux**: 保持原有行为不变
- **功能**: 所有原有功能完全保持不变
- **性能**: 无性能影响，仅改变窗口显示行为

## 技术细节

### Windows创建标志说明
```python
subprocess.CREATE_NO_WINDOW    # 不创建控制台窗口
subprocess.DETACHED_PROCESS    # 从父控制台分离
```

### 导入路径调整
由于文件层级较深，部分文件需要使用相对导入：
```python
# 示例：在深层文件中导入
from ......utils.subprocess_utils import run_hidden_subprocess
```

## 后续维护

1. **新增外部工具调用**: 应使用`subprocess_utils`中的函数
2. **代码审查**: 确保新的subprocess调用使用隐藏方式
3. **测试**: 在Windows环境下验证无cmd窗口弹出

## 相关文件清单

### 新增文件
- `src/pktmask/utils/subprocess_utils.py`
- `scripts/test/test_windows_cmd_popup_fix.py`
- `docs/dev/WINDOWS_CMD_POPUP_FIX.md`

### 修改文件
- `src/pktmask/utils/file_ops.py`
- `src/pktmask/tools/tls23_marker.py`
- `src/pktmask/tools/enhanced_tls_marker.py`
- `src/pktmask/tools/tls_flow_analyzer.py`
- `src/pktmask/core/pipeline/stages/mask_payload_v2/marker/tls_marker.py`
- `src/pktmask/infrastructure/dependency/checker.py`
- `PktMask-Windows.spec`
