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

app.command("mask", help="处理 PCAP 文件（Remove Dupes、Anonymize IPs、Mask Payloads）")(cmd_mask)
app.command("dedup", help="仅执行 Remove Dupes")(cmd_dedup)
app.command("anon", help="仅执行 Anonymize IPs")(cmd_anon)

if __name__ == "__main__":
    app()
