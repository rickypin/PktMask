# PktMask 入口点统一迁移实施指南

本文档为开发人员提供详细的迁移步骤和代码示例，确保平滑完成入口点统一工作。

## 迁移概览

- **目标**：将三个入口点统一为单一入口，GUI 为默认模式
- **时间**：3 天核心实施 + 1 个月过渡期
- **风险**：低（保持向后兼容）

## 第一天：核心实施

### 步骤 1：修改 `src/pktmask/__main__.py`

**文件路径**：`src/pktmask/__main__.py`

**完整代码**：
```python
#!/usr/bin/env python3
"""PktMask 统一入口 - 桌面应用优先"""
import sys
import typer
from typing import Optional

# 延迟导入，避免 CLI 用户加载 GUI 依赖
app = typer.Typer(
    help="PktMask - PCAP/PCAPNG 文件处理工具",
    add_completion=False  # 桌面应用不需要 shell 补全
)

@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """默认启动 GUI，除非明确调用 CLI 命令"""
    if ctx.invoked_subcommand is None:
        # 无子命令时启动 GUI
        from pktmask.gui.main_window import main as gui_main
        gui_main()
    # 有子命令时，Typer 会自动处理

# 导入并注册 CLI 命令（不使用嵌套，保持简单）
from pktmask.cli import cmd_mask, cmd_dedup, cmd_anon

app.command("mask", help="处理 PCAP 文件（去重、匿名化、掩码）")(cmd_mask)
app.command("dedup", help="仅执行去重")(cmd_dedup)  
app.command("anon", help="仅执行 IP 匿名化")(cmd_anon)

if __name__ == "__main__":
    app()
```

**验证命令**：
```bash
# 测试 GUI 启动
python -m pktmask

# 测试 CLI 命令
python -m pktmask mask --help
```

### 步骤 2：调整 `src/pktmask/cli.py`

**修改位置**：文件末尾（第 153-154 行附近）

**原代码**：
```python
if __name__ == "__main__":
    app()
```

**修改为**：
```python
# CLI 命令由 __main__.py 统一管理
# 直接运行此文件已不再支持
```

**注意**：保留所有命令函数定义（`cmd_mask`、`cmd_dedup`、`cmd_anon`）

### 步骤 3：创建根目录启动脚本

#### 3.1 创建 `pktmask`（无扩展名）

**文件路径**：`/Users/ricky/Downloads/PktMask/pktmask`

```python
#!/usr/bin/env python3
"""PktMask 启动脚本"""
import sys
from pktmask.__main__ import app

if __name__ == '__main__':
    sys.exit(app())
```

**设置执行权限**：
```bash
chmod +x pktmask
```

#### 3.2 创建 `pktmask.py`（Windows 兼容）

**文件路径**：`/Users/ricky/Downloads/PktMask/pktmask.py`

```python
#!/usr/bin/env python3
"""PktMask 启动脚本（Windows 兼容）"""
import sys
from pktmask.__main__ import app

if __name__ == '__main__':
    sys.exit(app())
```

### 步骤 4：更新 `pyproject.toml`

**文件路径**：`pyproject.toml`

**定位第 79 行**：
```toml
[project.scripts]
pktmask = "pktmask.cli:app"
```

**修改为**：
```toml
[project.scripts]
pktmask = "pktmask.__main__:app"
```

### 第一天验证清单

- [ ] `python -m pktmask` 启动 GUI
- [ ] `./pktmask` 启动 GUI
- [ ] `python pktmask.py` 启动 GUI
- [ ] `./pktmask mask --help` 显示帮助
- [ ] `./pktmask dedup --help` 显示帮助
- [ ] `./pktmask anon --help` 显示帮助
- [ ] 所有现有测试通过：`pytest tests/`

## 第二天：过渡处理

### 步骤 5：修改 `run_gui.py` 添加弃用警告

**文件路径**：`run_gui.py`

**完整替换内容**：
```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PktMask GUI应用程序启动脚本（已弃用）
"""

import warnings
import sys
import os

# 显示弃用警告
warnings.warn(
    "\n" + "="*60 + "\n" +
    "⚠️  run_gui.py 已弃用！\n" +
    "\n" +
    "请使用以下方式启动 PktMask：\n" +
    "  • GUI 模式：./pktmask 或 python pktmask.py\n" +
    "  • CLI 模式：./pktmask mask|dedup|anon ...\n" +
    "\n" +
    "此文件将在下个版本中移除。\n" +
    "="*60,
    DeprecationWarning,
    stacklevel=2
)

# 添加src目录到Python路径，以便能够导入pktmask模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from pktmask.gui.main_window import main

if __name__ == "__main__":
    main()
```

### 步骤 6：更新 README.md

**添加新的使用说明**（在 Installation 或 Usage 部分）：

```markdown
## 使用方法

### 启动 GUI
```bash
# 推荐方式
./pktmask

# Windows 用户
python pktmask.py

# 使用 Python 模块
python -m pktmask
```

### 使用 CLI
```bash
# 掩码处理
./pktmask mask input.pcap -o output.pcap --dedup --anon

# 仅去重
./pktmask dedup input.pcap -o output.pcap

# 仅匿名化
./pktmask anon input.pcap -o output.pcap

# 查看帮助
./pktmask --help
./pktmask mask --help
```
```

### 步骤 7：测试所有入口方式

**创建测试脚本**：`scripts/test/test_all_entrypoints.sh`

```bash
#!/bin/bash
# 测试所有入口方式

echo "=== 测试 GUI 启动 ==="
echo "1. 测试 ./pktmask （按 Ctrl+C 退出）"
./pktmask &
PID=$!
sleep 3
kill $PID 2>/dev/null

echo "2. 测试 python pktmask.py"
python pktmask.py &
PID=$!
sleep 3
kill $PID 2>/dev/null

echo "3. 测试 python -m pktmask"
python -m pktmask &
PID=$!
sleep 3
kill $PID 2>/dev/null

echo "4. 测试 run_gui.py（应显示弃用警告）"
python run_gui.py &
PID=$!
sleep 3
kill $PID 2>/dev/null

echo -e "\n=== 测试 CLI 命令 ==="
echo "5. 测试 mask 命令帮助"
./pktmask mask --help

echo -e "\n6. 测试 dedup 命令帮助"
./pktmask dedup --help

echo -e "\n7. 测试 anon 命令帮助"
./pktmask anon --help

echo -e "\n=== 测试完成 ==="
```

## 第三天：文档更新

### 步骤 8：更新用户文档

**创建/更新**：`docs/user/quickstart.md`

```markdown
# PktMask 快速开始

## 安装

```bash
pip install -e .
```

## 启动应用

PktMask 是一个桌面应用，默认以图形界面模式运行。

### 图形界面模式

双击 `pktmask` 文件或在终端运行：

```bash
./pktmask
```

Windows 用户可以运行：
```bash
python pktmask.py
```

### 命令行模式

PktMask 也提供命令行接口用于批处理：

```bash
# 完整处理（Remove Dupes + Anonymize IPs + Mask Payloads）
./pktmask mask input.pcap -o output.pcap --dedup --anon

# 仅 Remove Dupes
./pktmask dedup input.pcap -o output.pcap

# 仅 Anonymize IPs
./pktmask anon input.pcap -o output.pcap
```
```

### 步骤 9：更新开发文档

**创建**：`docs/development/architecture/entrypoint.md`

```markdown
# 入口点架构

## 概述

PktMask 使用统一入口点设计，通过 `__main__.py` 智能分发到 GUI 或 CLI。

## 入口点结构

```
pktmask/pktmask.py     # Windows 兼容启动脚本
       /pktmask        # Unix 启动脚本
       /src/pktmask/
           /__main__.py   # 统一入口（Typer 应用）
           /cli.py        # CLI 命令实现
           /gui/main_window.py  # GUI 主窗口
```

## 工作流程

1. 用户运行 `./pktmask` 或 `python pktmask.py`
2. 启动脚本调用 `pktmask.__main__.app()`
3. Typer 检查是否有子命令：
   - 无子命令 → 启动 GUI（默认）
   - 有子命令 → 执行对应的 CLI 命令

## 设计决策

- **GUI 优先**：符合桌面软件特性
- **延迟导入**：CLI 用户不加载 GUI 依赖
- **简单命令**：避免嵌套，直接注册命令
```

### 步骤 10：创建变更日志

**更新**：`CHANGELOG.md`

在文件顶部添加：

```markdown
## [Unreleased]

### Changed
- 统一入口点：所有功能通过 `pktmask` 命令访问
- GUI 成为默认模式（无参数启动）
- CLI 命令简化（移除 `cli` 前缀）

### Deprecated
- `run_gui.py` 已弃用，请使用 `./pktmask` 或 `python pktmask.py`
- 直接运行 `src/pktmask/cli.py` 已不再支持

### Migration Guide
- GUI 用户：使用 `./pktmask` 替代 `python run_gui.py`
- CLI 用户：命令更简洁，如 `./pktmask mask` 替代之前的调用方式
```

## 后续工作（1个月后）

### 清理任务

1. **删除 `run_gui.py`**
   ```bash
   git rm run_gui.py
   ```

2. **更新所有文档中的示例**
   - 搜索并替换所有 `run_gui.py` 引用
   - 更新 CI/CD 脚本
   - 更新测试文档

3. **发布新版本**
   - 更新版本号
   - 发布 release notes
   - 通知用户

## 故障排查

### 常见问题

1. **ImportError: No module named 'pktmask'**
   - 确保在项目根目录运行
   - 或先安装：`pip install -e .`

2. **Permission denied: ./pktmask**
   - 运行：`chmod +x pktmask`

3. **CLI 命令不工作**
   - 检查 Typer 是否正确安装：`pip install typer`
   - 确认命令函数正确导入

### 回滚方案

如果迁移出现严重问题，可以快速回滚：

```bash
# 恢复 __main__.py
git checkout HEAD -- src/pktmask/__main__.py

# 恢复 cli.py
git checkout HEAD -- src/pktmask/cli.py

# 恢复 pyproject.toml
git checkout HEAD -- pyproject.toml

# 删除新增文件
rm -f pktmask pktmask.py
```

## 验证检查表

### 功能验证
- [ ] GUI 默认启动正常
- [ ] 所有 CLI 命令工作正常
- [ ] 帮助信息显示正确
- [ ] 错误处理正常

### 兼容性验证
- [ ] 旧入口显示弃用警告
- [ ] pip 安装后命令可用
- [ ] Windows/Mac/Linux 测试通过

### 文档验证
- [ ] README 更新完成
- [ ] 用户文档更新完成
- [ ] 开发文档更新完成
- [ ] CHANGELOG 更新完成

---

迁移完成后，PktMask 将拥有更清晰的入口结构，提升用户体验和代码可维护性。
