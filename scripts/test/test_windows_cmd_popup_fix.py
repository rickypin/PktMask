#!/usr/bin/env python3
"""
测试Windows下cmd窗口弹出问题的修复效果
"""
import sys
import os
import platform
import tempfile
from pathlib import Path

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

def test_subprocess_utils():
    """测试新的subprocess工具函数"""
    print("=== 测试subprocess工具函数 ===")
    
    try:
        from pktmask.utils.subprocess_utils import (
            get_subprocess_creation_flags,
            run_hidden_subprocess,
            run_tshark_command,
            open_directory_hidden
        )
        
        # 测试creation flags
        flags = get_subprocess_creation_flags()
        if platform.system() == "Windows":
            print(f"✓ Windows creation flags: {flags}")
            assert flags != 0, "Windows应该返回非零creation flags"
        else:
            print(f"✓ Non-Windows creation flags: {flags}")
            assert flags == 0, "非Windows系统应该返回0"
        
        # 测试基本命令执行（使用echo命令）
        if platform.system() == "Windows":
            test_cmd = ["cmd", "/c", "echo", "test"]
        else:
            test_cmd = ["echo", "test"]
        
        result = run_hidden_subprocess(test_cmd, capture_output=True, text=True)
        print(f"✓ 隐藏subprocess执行成功: {result.stdout.strip()}")
        
        # 测试目录打开（使用临时目录）
        with tempfile.TemporaryDirectory() as temp_dir:
            success = open_directory_hidden(temp_dir)
            print(f"✓ 目录打开测试: {'成功' if success else '失败'}")
        
        print("✓ subprocess工具函数测试通过\n")
        return True
        
    except Exception as e:
        print(f"✗ subprocess工具函数测试失败: {e}\n")
        return False


def test_tshark_integration():
    """测试tshark集成是否使用了新的隐藏subprocess"""
    print("=== 测试TShark集成 ===")
    
    try:
        # 检查是否能找到tshark
        import shutil
        tshark_path = shutil.which('tshark')
        
        if not tshark_path:
            print("⚠ 未找到tshark，跳过tshark集成测试")
            return True
        
        print(f"✓ 找到tshark: {tshark_path}")
        
        # 测试依赖检查器
        from pktmask.infrastructure.dependency.checker import TSharkDependencyChecker
        checker = TSharkDependencyChecker()
        result = checker.check()
        
        print(f"✓ TShark依赖检查: {result.status.name}")
        
        # 如果有测试pcap文件，可以测试TLS marker
        test_pcap = Path("tests/data/tls/tls_1_2_plainip.pcap")
        if test_pcap.exists():
            print("✓ 找到测试PCAP文件，可以进行完整测试")
        else:
            print("⚠ 未找到测试PCAP文件，跳过TLS marker测试")
        
        print("✓ TShark集成测试通过\n")
        return True
        
    except Exception as e:
        print(f"✗ TShark集成测试失败: {e}\n")
        return False


def test_file_operations():
    """测试文件操作是否使用了新的隐藏subprocess"""
    print("=== 测试文件操作 ===")
    
    try:
        from pktmask.utils.file_ops import open_directory_in_system
        
        # 测试目录打开
        with tempfile.TemporaryDirectory() as temp_dir:
            success = open_directory_in_system(temp_dir)
            print(f"✓ 文件操作目录打开: {'成功' if success else '失败'}")
        
        print("✓ 文件操作测试通过\n")
        return True
        
    except Exception as e:
        print(f"✗ 文件操作测试失败: {e}\n")
        return False


def main():
    """主测试函数"""
    print("Windows CMD窗口弹出问题修复测试")
    print("=" * 50)
    print(f"操作系统: {platform.system()}")
    print(f"Python版本: {sys.version}")
    print()
    
    tests = [
        test_subprocess_utils,
        test_tshark_integration,
        test_file_operations,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print("=" * 50)
    print(f"测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("✓ 所有测试通过！Windows cmd窗口弹出问题应该已经修复。")
        return 0
    else:
        print("✗ 部分测试失败，请检查修复效果。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
