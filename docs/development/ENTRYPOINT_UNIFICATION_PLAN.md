# 统一入口方案

## 1. 背景

当前项目存在三个入口脚本，职责重叠且维护困难：

- `run_gui.py`（根目录）
- `src/pktmask/cli.py`
- `src/pktmask/__main__.py`

## 2. 目标

- 统一为单一入口 `pktmask`，支持 CLI 与 GUI 子命令
- 明确文件职责与位置，遵循目录结构规范
- 保持向后兼容，平滑迁移

## 3. 参考目录规范（Context7 检验）

根据 **目录与文件结构规范**：

- 根目录可包含用户启动脚本：`.py` 或无扩展名入口脚本 ✓
- `src/` 存放源码包，入口逻辑应集中于 `src/pktmask/` ✓
- `scripts/` 用于 CI/迁移脚本，不宜放最终用户入口 x

本方案：

- 将根目录 `run_gui.py` 标记弃用或删除，仅保留新的轻量化启动脚本 `pktmask`（根级无扩展名）
- 主入口集中于 `src/pktmask/__main__.py`
- CLI 定义保留在 `src/pktmask/cli.py`，入口调用由顶层 `__main__` 进行分发
- GUI 调用逻辑保留在 `src/pktmask/gui/main_window.py` 的 `launch_gui()` 接口

## 4. 详细实施步骤

### 4.1 新建/修改 `src/pktmask/__main__.py`

- **路径**：`src/pktmask/__main__.py`
- **使用 Typer** 统一 CLI+GUI：

```python
#!/usr/bin/env python3
import typer
from pktmask.cli import app as cli_app
from pktmask.gui.main_window import launch_gui

app = typer.Typer(help="PktMask CLI & GUI 统一入口")

@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    gui: bool = typer.Option(False, "--gui", help="启动图形界面")
):
    """统一入口，根据参数分发到 GUI 或 CLI"""
    if gui:
        launch_gui()
    elif ctx.invoked_subcommand is None:
        typer.echo("请指定子命令或使用 --gui 启动 GUI。")

# 挂载原 CLI 子命令
app.add_typer(cli_app, name="cli")

if __name__ == "__main__":
    app()
```

### 4.2 重构 CLI：`src/pktmask/cli.py`

- **移除** 文件末尾的 `if __name__ == "__main__": app()`
- 保留 `app = typer.Typer(...)` 及命令函数 (`cmd_mask`, `cmd_dedup`, `cmd_anon`)
- 验证：在顶层执行 `pktmask cli` 可正常调用原命令

### 4.3 重构 GUI：`src/pktmask/gui/main_window.py`

- **提取** 原 `run_gui.py` 的启动逻辑
- **实现** 对外接口 `launch_gui()`：

```python
# src/pktmask/gui/main_window.py
# ... existing code ...

def launch_gui():
    # 原 main() 启动函数
    main()
```

### 4.4 新建根级启动脚本 `pktmask`

- **路径**：根目录 `/pktmask`（无扩展名）
- **内容**：

```bash
#!/usr/bin/env python3
"""轻量级统一启动脚本，符合 Context7 根级入口规范"""
from pktmask.__main__ import main

if __name__ == '__main__':
    main()
```

- **权限**：`chmod +x pktmask`

### 4.5 配置 `pyproject.toml`

根据 PEP621/Poetry，添加：

```toml
[tool.poetry.scripts]
pktmask = "pktmask.__main__:main"
```

或者 PEP621：

```toml
[project.scripts]
pktmask = "pktmask.__main__:main"
```

### 4.6 标记弃用 & 清理

- 根目录：`run_gui.py` → 重命名为 `deprecated_run_gui.py` 或直接删除
- `src/pktmask/__main__.py` 旧逻辑已重写，无需保留
- 更新所有 CI、Dockerfile、文档示例为 `pktmask [--gui|cli]`

## 5. 验证与测试

- **单元测试**：`pytest tests/unit`
- **集成测试**：`pytest tests/integration`
- **E2E**：`pktmask cli -c config/default/mask_config.yaml`
- **GUI 验证**：`pktmask --gui`

## 6. 时间表

| 序号 | 文件/命令                           | 操作描述                              | 完成时限 |
| ---- | ------------------------------------ | ------------------------------------- | -------- |
| 1    | `src/pktmask/__main__.py`           | 新建并实现 Typer 统一入口             | Day1     |
| 2    | `src/pktmask/cli.py`                | 移除脚本入口，保留命令定义            | Day1     |
| 3    | `src/pktmask/gui/main_window.py`    | 提取并实现 `launch_gui()` 接口        | Day1     |
| 4    | `/pktmask`                           | 新建根级启动脚本并赋予执行权限         | Day2     |
| 5    | `pyproject.toml`                     | 添加 console_scripts 脚本映射          | Day2     |
| 6    | 根目录 `run_gui.py`                  | 标记弃用或删除                         | Day2     |
| 7    | 文档、CI、Dockerfile                 | 全面替换启动示例命令                  | Day3     |
| 8    | 测试与回归                          | 验证新入口兼容性                      | Day3     |

---

以上方案结合 Context7 目录规范，确保文件位置与命名合理，职责清晰，便于维护与扩展。 