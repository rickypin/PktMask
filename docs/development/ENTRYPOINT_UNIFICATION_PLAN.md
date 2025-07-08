# 统一入口方案（优化版）

## 1. 背景

当前项目存在三个入口脚本，职责重叠且维护困难：

- `run_gui.py`（根目录）- 仅启动 GUI
- `src/pktmask/cli.py` - CLI 命令实现
- `src/pktmask/__main__.py` - 当前直接启动 GUI

## 2. 目标

- 统一为单一入口，GUI 为默认模式（符合桌面软件特性）
- 保持 CLI 功能可用，但作为高级功能
- 明确文件职责，避免过度工程化
- 确保平滑迁移，最小化用户影响

## 3. 设计原则

### 3.1 符合桌面软件特性
- **GUI 优先**：双击运行或无参数启动时默认打开 GUI
- **CLI 可选**：通过明确的命令行参数调用 CLI 功能
- **简单直观**：避免过多的子命令嵌套

### 3.2 符合目录规范
根据项目目录结构规范：
- ✓ 根目录可包含入口脚本（`.py` 或无扩展名）
- ✓ `src/` 存放源码包，核心逻辑在 `src/pktmask/`
- ✓ 避免在 `scripts/` 放置用户入口

### 3.3 实施策略
- 保留 `run_gui.py` 作为过渡（添加弃用警告）
- 新建统一入口 `pktmask`（无扩展名）
- `__main__.py` 实现智能分发逻辑

## 4. 详细实施步骤

### 4.1 修改 `src/pktmask/__main__.py`

**设计思路**：桌面软件默认启动 GUI，CLI 作为高级功能

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

### 4.2 调整 `src/pktmask/cli.py`

最小化改动，保持代码稳定：

1. **移除** 文件末尾的 `if __name__ == "__main__": app()`
2. **保留** 现有的命令函数定义
3. **可选**：移除 `app = typer.Typer(...)` 定义（因为命令已在 `__main__.py` 注册）

```python
# 文件末尾改为：
# CLI 命令由 __main__.py 统一管理
# 直接运行此文件已不再支持
```

### 4.3 GUI 入口无需修改

`src/pktmask/gui/main_window.py` 已有 `main()` 函数，无需额外修改：
- 保持现有的 `main()` 函数不变
- `__main__.py` 直接导入并调用即可
- 避免不必要的代码改动

### 4.4 创建根目录启动脚本

创建两个入口文件，满足不同使用习惯：

#### 4.4.1 `pktmask`（无扩展名，Unix 风格）
```bash
#!/usr/bin/env python3
"""PktMask 启动脚本"""
import sys
from pktmask.__main__ import app

if __name__ == '__main__':
    sys.exit(app())
```

#### 4.4.2 `pktmask.py`（Windows 友好）
```python
#!/usr/bin/env python3
"""PktMask 启动脚本（Windows 兼容）"""
import sys
from pktmask.__main__ import app

if __name__ == '__main__':
    sys.exit(app())
```

执行：`chmod +x pktmask`（仅 Unix 需要）

### 4.5 更新 `pyproject.toml`

修改现有的脚本入口配置：

```toml
[project.scripts]
# 从 pktmask.cli:app 改为 __main__:app
pktmask = "pktmask.__main__:app"
```

这样 `pip install` 后会自动创建 `pktmask` 命令。

### 4.6 过渡期处理

#### 第一阶段（1-2 周）
修改 `run_gui.py` 添加弃用提示：
```python
#!/usr/bin/env python3
import warnings
import sys
import os

warnings.warn(
    "run_gui.py 已弃用，请使用 'python pktmask.py' 或 './pktmask' 启动",
    DeprecationWarning,
    stacklevel=2
)

# 继续执行原逻辑
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
from pktmask.gui.main_window import main

if __name__ == "__main__":
    main()
```

#### 第二阶段（1 个月后）
- 删除 `run_gui.py`
- 更新所有文档和示例

## 5. 验证清单

### 5.1 功能测试
- [ ] GUI 启动：`./pktmask` （应直接打开 GUI）
- [ ] GUI 启动：`python pktmask.py` （Windows 用户习惯）
- [ ] CLI 掩码：`./pktmask mask input.pcap -o output.pcap`
- [ ] CLI 去重：`./pktmask dedup input.pcap -o output.pcap`
- [ ] CLI 匿名：`./pktmask anon input.pcap -o output.pcap`
- [ ] 帮助信息：`./pktmask --help`

### 5.2 兼容性测试
- [ ] 旧入口 `run_gui.py` 显示弃用警告但仍可运行
- [ ] `python -m pktmask` 行为正确（启动 GUI）
- [ ] 安装后 `pktmask` 命令可用

### 5.3 自动化测试
- [ ] 现有 pytest 测试通过
- [ ] CLI 命令的退出码正确

## 6. 实施步骤

### 第 1 天：核心实现
1. **修改** `src/pktmask/__main__.py` - 实现统一入口
2. **调整** `src/pktmask/cli.py` - 移除独立运行代码
3. **创建** `pktmask` 和 `pktmask.py` - 根目录启动脚本
4. **更新** `pyproject.toml` - 修改脚本入口配置

### 第 2 天：过渡处理
5. **修改** `run_gui.py` - 添加弃用警告
6. **测试** 所有入口方式 - 确保功能正常
7. **更新** README.md - 新的使用说明

### 第 3 天：文档更新
8. **更新** 用户文档 - 新的启动方式
9. **更新** 开发文档 - 架构变更说明
10. **发布** 变更日志 - 通知用户

## 7. 用户影响分析

### 7.1 最小影响原则
- GUI 用户：几乎无感知（双击运行体验相同）
- CLI 用户：命令更简洁（去掉 `cli` 前缀）
- 开发者：入口逻辑更清晰

### 7.2 迁移指南（面向用户）
```bash
# 旧方式 → 新方式
python run_gui.py        → ./pktmask 或 python pktmask.py
python -m pktmask        → ./pktmask （行为不变）
python src/pktmask/cli.py mask ... → ./pktmask mask ...
```

---

本方案遵循"简单实用"原则，避免过度工程化，同时确保桌面软件的用户体验。
