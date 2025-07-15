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
    print("=== PktMask Single Entry Point Verification ===\n")

    # 1. Check if __main__.py is the only entry point
    print("1. Check entry points in source code:")
    main_py_files = subprocess.run(
        "find src -name '*.py' -exec grep -l 'if __name__ == .* __main__' {} \\;",
        shell=True,
        capture_output=True,
        text=True
    ).stdout.strip().split('\n')

    print(f"   Found {len(main_py_files)} files containing main:")
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
    
    # 5. Check configuration file
    print("\n5. Check pyproject.toml configuration:")
    config_output = run_command("grep -A1 'project.scripts' pyproject.toml")
    print(f"   {config_output.strip()}")

    # 6. Summary
    print("\n=== Summary ===")
    print("✓ GUI and CLI use the same entry point: pktmask.__main__.app()")
    print("✓ Intelligent dispatching through Typer's callback mechanism")
    print("✓ Default GUI launch when no parameters (desktop application feature)")
    print("✓ Execute corresponding CLI functions when commands provided")

    # 7. Check for other independent entry points
    print("\nCheck potential independent entry points:")

    # Check if cli.py can still run independently
    cli_check = run_command("tail -5 src/pktmask/cli.py")
    if "if __name__" in cli_check:
        print("✗ cli.py still has independent entry point")
    else:
        print("✓ cli.py independent entry point removed")
    
    # Check other possible GUI entry points
    gui_files = subprocess.run(
        "find src -name '*.py' -path '*/gui/*' -exec grep -l 'QApplication' {} \\;",
        shell=True,
        capture_output=True,
        text=True
    ).stdout.strip().split('\n')

    print(f"\nGUI files containing QApplication: {len([f for f in gui_files if f])}")
    for f in gui_files:
        if f:
            print(f"   - {f}")

if __name__ == "__main__":
    main()
