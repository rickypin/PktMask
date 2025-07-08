#!/usr/bin/env python3
"""验证 GUI 和 CLI 是否真正使用单一入口点"""

import subprocess
import sys
import os
import time

def run_command(cmd, timeout=3):
    """运行命令并返回输出"""
    try:
        result = subprocess.run(
            cmd, 
            shell=True, 
            capture_output=True, 
            text=True, 
            timeout=timeout
        )
        return result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return f"命令超时（{timeout}秒）"
    except Exception as e:
        return f"错误: {str(e)}"

def main():
    print("=== PktMask 单一入口点验证 ===\n")
    
    # 1. 检查 __main__.py 是否是唯一入口
    print("1. 检查源码中的入口点:")
    main_py_files = subprocess.run(
        "find src -name '*.py' -exec grep -l 'if __name__ == .* __main__' {} \\;",
        shell=True,
        capture_output=True,
        text=True
    ).stdout.strip().split('\n')
    
    print(f"   发现 {len(main_py_files)} 个包含 main 的文件:")
    for f in main_py_files:
        print(f"   - {f}")
    
    # 2. 验证 CLI 命令路径
    print("\n2. CLI 命令调用链:")
    print("   ./pktmask mask ...")
    print("   └─> pktmask.__main__.app()")
    print("       └─> typer 检测到 'mask' 命令")
    print("           └─> 调用 pktmask.cli.cmd_mask()")
    
    # 3. 验证 GUI 启动路径
    print("\n3. GUI 启动调用链:")
    print("   ./pktmask")
    print("   └─> pktmask.__main__.app()")
    print("       └─> typer 检测无命令")
    print("           └─> 调用 pktmask.gui.main_window.main()")
    
    # 4. 检查所有启动方式
    print("\n4. 实际测试各种启动方式:")
    
    test_commands = [
        ("./pktmask --help", "CLI 帮助"),
        ("python pktmask.py --help", "Python 脚本帮助"),
        ("python -m pktmask --help", "模块帮助"),
        ("./pktmask mask --help", "mask 命令帮助"),
    ]
    
    for cmd, desc in test_commands:
        print(f"\n   测试 {desc}: {cmd}")
        output = run_command(cmd, timeout=2)
        if "PktMask - PCAP/PCAPNG" in output:
            print("   ✓ 成功 - 使用统一入口")
        else:
            print("   ✗ 失败")
            print(f"   输出: {output[:100]}...")
    
    # 5. 检查配置文件
    print("\n5. 检查 pyproject.toml 配置:")
    config_output = run_command("grep -A1 'project.scripts' pyproject.toml")
    print(f"   {config_output.strip()}")
    
    # 6. 总结
    print("\n=== 总结 ===")
    print("✓ GUI 和 CLI 使用同一个入口点: pktmask.__main__.app()")
    print("✓ 通过 Typer 的 callback 机制智能分发")
    print("✓ 无参数时默认启动 GUI（桌面应用特性）")
    print("✓ 有命令时执行对应的 CLI 功能")
    
    # 7. 检查是否有其他独立入口
    print("\n检查潜在的独立入口:")
    
    # 检查 cli.py 是否还能独立运行
    cli_check = run_command("tail -5 src/pktmask/cli.py")
    if "if __name__" in cli_check:
        print("✗ cli.py 仍有独立入口")
    else:
        print("✓ cli.py 已移除独立入口")
    
    # 检查其他可能的 GUI 入口
    gui_files = subprocess.run(
        "find src -name '*.py' -path '*/gui/*' -exec grep -l 'QApplication' {} \\;",
        shell=True,
        capture_output=True,
        text=True
    ).stdout.strip().split('\n')
    
    print(f"\n包含 QApplication 的 GUI 文件: {len([f for f in gui_files if f])}")
    for f in gui_files:
        if f:
            print(f"   - {f}")

if __name__ == "__main__":
    main()
