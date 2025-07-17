#!/usr/bin/env python3
"""
Windows TShark 快速修复脚本

针对Windows平台TShark TLS marker验证失败问题的快速修复工具。
提供自动化的诊断和修复建议。
"""

import os
import sys
import subprocess
import platform
import shutil
from pathlib import Path


def print_header(title: str):
    """打印标题"""
    print("\n" + "="*60)
    print(f" {title}")
    print("="*60)


def print_section(title: str):
    """打印章节标题"""
    print(f"\n📋 {title}")
    print("-" * 40)


def check_windows_system():
    """检查是否在Windows系统上运行"""
    if platform.system() != 'Windows':
        print("❌ This script is designed for Windows only")
        print(f"   Current platform: {platform.system()}")
        return False
    return True


def find_tshark_installations():
    """查找TShark安装"""
    print_section("Scanning TShark Installations")
    
    # Windows常见路径
    common_paths = [
        r'C:\Program Files\Wireshark\tshark.exe',
        r'C:\Program Files (x86)\Wireshark\tshark.exe',
        r'C:\ProgramData\chocolatey\bin\tshark.exe',
        r'C:\tools\wireshark\tshark.exe',
    ]
    
    found_installations = []
    
    # 检查预定义路径
    for path in common_paths:
        if Path(path).exists():
            found_installations.append(path)
            print(f"✅ Found: {path}")
    
    # 检查系统PATH
    system_tshark = shutil.which('tshark')
    if system_tshark:
        found_installations.append(system_tshark)
        print(f"✅ Found in PATH: {system_tshark}")
    
    if not found_installations:
        print("❌ No TShark installations found")
    
    return found_installations


def check_tshark_version(tshark_path):
    """检查TShark版本"""
    try:
        result = subprocess.run(
            [tshark_path, '-v'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            version_output = result.stdout
            print(f"✅ Version check successful")
            
            # 简单的版本解析
            if 'TShark' in version_output:
                lines = version_output.split('\n')
                version_line = lines[0] if lines else ""
                print(f"   {version_line}")
                return True
            
        print(f"❌ Version check failed: {result.stderr}")
        return False
        
    except Exception as e:
        print(f"❌ Version check error: {e}")
        return False


def check_basic_functionality(tshark_path):
    """检查基本TShark功能 (简化版，提升性能)"""
    print_section("Checking Basic TShark Functionality")

    results = {}

    # 单次调用检查版本和基本功能
    try:
        # 使用CREATE_NO_WINDOW避免CMD窗口闪烁
        subprocess_kwargs = {
            'capture_output': True,
            'text': True,
            'timeout': 10
        }

        if platform.system() == 'Windows':
            subprocess_kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW

        result = subprocess.run([tshark_path, '-v'], **subprocess_kwargs)

        if result.returncode == 0:
            results['Executable'] = True
            print("✅ Executable: Available")

            # 解析版本
            version_output = result.stdout
            if 'TShark' in version_output:
                results['Version'] = True
                print("✅ Version: Compatible")

                # 提取版本号进行基本检查
                import re
                version_match = re.search(r'TShark.*?(\d+)\.(\d+)\.(\d+)', version_output)
                if version_match:
                    major, minor, patch = map(int, version_match.groups())
                    if (major, minor, patch) >= (4, 2, 0):
                        results['Version Compatible'] = True
                        print(f"✅ Version Compatible: {major}.{minor}.{patch} >= 4.2.0")
                    else:
                        results['Version Compatible'] = False
                        print(f"❌ Version Compatible: {major}.{minor}.{patch} < 4.2.0")
                else:
                    results['Version Compatible'] = False
                    print("❌ Version Compatible: Could not parse version")
            else:
                results['Version'] = False
                print("❌ Version: Could not detect TShark")
        else:
            results['Executable'] = False
            print(f"❌ Executable: Failed to run - {result.stderr}")

    except Exception as e:
        results['Executable'] = False
        print(f"❌ Executable: Error - {e}")

    return results


def provide_fix_recommendations(installations, capabilities_results):
    """提供修复建议"""
    print_section("Fix Recommendations")
    
    if not installations:
        print("🔧 No TShark found - Installation required:")
        print("   1. Download Wireshark from: https://www.wireshark.org/download.html")
        print("   2. Run installer as Administrator")
        print("   3. Ensure 'Command Line Tools' option is selected")
        print("   4. Add C:\\Program Files\\Wireshark to system PATH")
        print("\n   Alternative - Use Chocolatey:")
        print("   1. Install Chocolatey: https://chocolatey.org/install")
        print("   2. Run: choco install wireshark")
        return
    
    # 检查功能问题 (简化版)
    missing_capabilities = []
    for install in installations:
        caps = check_basic_functionality(install)
        for cap, available in caps.items():
            if not available:
                missing_capabilities.append(cap)
    
    if missing_capabilities:
        print("🔧 TShark found but missing capabilities:")
        print("   Recommended fixes:")
        print("   1. Uninstall current Wireshark version")
        print("   2. Download latest Wireshark (>= 4.2.0)")
        print("   3. Install with ALL components selected")
        print("   4. Run as Administrator during installation")
        
        if 'JSON output' in missing_capabilities:
            print("\n   JSON output issue:")
            print("   • Upgrade to TShark >= 4.2.0")
            
        if 'TLS protocol' in missing_capabilities:
            print("\n   TLS protocol issue:")
            print("   • Install complete Wireshark package")
            print("   • Avoid 'minimal' or 'portable' versions")
    else:
        print("✅ TShark capabilities look good!")
        print("   If you're still experiencing issues:")
        print("   1. Restart your command prompt/terminal")
        print("   2. Check Windows firewall settings")
        print("   3. Run PktMask as Administrator")


def attempt_auto_fix():
    """尝试自动修复"""
    print_section("Attempting Auto-Fix")
    
    # 检查管理员权限
    try:
        import ctypes
        is_admin = ctypes.windll.shell32.IsUserAnAdmin()
    except:
        is_admin = False
    
    if not is_admin:
        print("❌ Administrator privileges required for auto-fix")
        print("   Please run this script as Administrator")
        return False
    
    # 尝试Chocolatey安装
    if shutil.which('choco'):
        print("🔧 Attempting Chocolatey installation...")
        try:
            result = subprocess.run(
                ['choco', 'install', 'wireshark', '-y'],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode == 0:
                print("✅ Chocolatey installation successful!")
                return True
            else:
                print(f"❌ Chocolatey installation failed: {result.stderr}")
        except Exception as e:
            print(f"❌ Chocolatey installation error: {e}")
    else:
        print("❌ Chocolatey not found - manual installation required")
    
    return False


def main():
    """主函数"""
    print_header("Windows TShark Quick Fix Tool")
    
    # 检查系统
    if not check_windows_system():
        sys.exit(1)
    
    print(f"Platform: {platform.platform()}")
    print(f"Python: {sys.version.split()[0]}")
    
    # 查找安装
    installations = find_tshark_installations()
    
    # 检查版本和功能
    capabilities_results = {}
    for install in installations:
        print(f"\n🔍 Checking: {install}")
        version_ok = check_tshark_version(install)
        if version_ok:
            capabilities_results[install] = check_basic_functionality(install)
    
    # 提供建议
    provide_fix_recommendations(installations, capabilities_results)
    
    # 询问是否尝试自动修复
    if not installations:
        print("\n❓ Attempt automatic installation? (requires Administrator)")
        response = input("   Type 'yes' to continue: ").lower().strip()
        
        if response == 'yes':
            success = attempt_auto_fix()
            if success:
                print("\n🎉 Auto-fix completed! Please run validation again.")
            else:
                print("\n❌ Auto-fix failed. Please follow manual steps above.")
    
    print("\n📖 For detailed troubleshooting, see:")
    print("   docs/WINDOWS_TSHARK_TROUBLESHOOTING.md")
    
    print("\n🔍 To validate the fix, run:")
    print("   python scripts/validate_tshark_setup.py --all")


if __name__ == '__main__':
    main()
