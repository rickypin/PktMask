#!/usr/bin/env python3
"""
跨平台TShark协议和字段检查工具

解决Windows (findstr) 和 Unix/Linux (grep) 命令差异问题，
提供统一的跨平台TShark功能验证。
"""

import os
import sys
import subprocess
import platform
from pathlib import Path
from typing import List, Dict, Optional, Tuple


def get_tshark_path() -> Optional[str]:
    """获取TShark可执行文件路径"""
    # 平台特定路径
    if platform.system() == 'Windows':
        common_paths = [
            r'C:\Program Files\Wireshark\tshark.exe',
            r'C:\Program Files (x86)\Wireshark\tshark.exe',
            r'C:\ProgramData\chocolatey\bin\tshark.exe',
        ]
        
        for path in common_paths:
            if Path(path).exists():
                return path
    
    # 系统PATH中查找
    import shutil
    return shutil.which('tshark')


def check_protocols_cross_platform(tshark_path: str, target_protocols: List[str]) -> Dict[str, bool]:
    """跨平台检查协议支持
    
    Args:
        tshark_path: TShark可执行文件路径
        target_protocols: 要检查的协议列表，如 ['tls', 'ssl', 'tcp']
    
    Returns:
        协议支持状态字典
    """
    results = {}
    
    try:
        # 执行 tshark -G protocols
        result = subprocess.run(
            [tshark_path, '-G', 'protocols'],
            capture_output=True,
            text=True,
            timeout=15
        )
        
        if result.returncode != 0:
            print(f"❌ Failed to get protocols: {result.stderr}")
            return {protocol: False for protocol in target_protocols}
        
        # 解析输出，不依赖外部命令
        protocols_output = result.stdout.lower()
        
        for protocol in target_protocols:
            # 检查协议是否在输出中
            protocol_found = protocol.lower() in protocols_output
            results[protocol] = protocol_found
            
            if protocol_found:
                print(f"✅ Protocol {protocol}: Supported")
            else:
                print(f"❌ Protocol {protocol}: Not found")
    
    except subprocess.TimeoutExpired:
        print("❌ Protocol check timeout")
        results = {protocol: False for protocol in target_protocols}
    except Exception as e:
        print(f"❌ Protocol check error: {e}")
        results = {protocol: False for protocol in target_protocols}
    
    return results


def check_fields_cross_platform(tshark_path: str, target_fields: List[str]) -> Dict[str, bool]:
    """跨平台检查字段支持
    
    Args:
        tshark_path: TShark可执行文件路径
        target_fields: 要检查的字段列表，如 ['tls.app_data', 'tcp.stream']
    
    Returns:
        字段支持状态字典
    """
    results = {}
    
    try:
        # 执行 tshark -G fields
        result = subprocess.run(
            [tshark_path, '-G', 'fields'],
            capture_output=True,
            text=True,
            timeout=20
        )
        
        if result.returncode != 0:
            print(f"❌ Failed to get fields: {result.stderr}")
            return {field: False for field in target_fields}
        
        # 解析输出，不依赖外部命令
        fields_output = result.stdout
        
        for field in target_fields:
            # 检查字段是否在输出中
            field_found = field in fields_output
            results[field] = field_found
            
            if field_found:
                print(f"✅ Field {field}: Available")
            else:
                print(f"❌ Field {field}: Not found")
    
    except subprocess.TimeoutExpired:
        print("❌ Field check timeout")
        results = {field: False for field in target_fields}
    except Exception as e:
        print(f"❌ Field check error: {e}")
        results = {field: False for field in target_fields}
    
    return results


def check_tls_capabilities_comprehensive(tshark_path: str) -> Dict[str, bool]:
    """全面检查TLS相关功能
    
    Args:
        tshark_path: TShark可执行文件路径
    
    Returns:
        TLS功能支持状态字典
    """
    print("🔍 Comprehensive TLS Capabilities Check")
    print("-" * 50)
    
    capabilities = {}
    
    # 1. 检查TLS相关协议
    print("\n📋 Protocol Support:")
    tls_protocols = ['tls', 'ssl', 'tcp']
    protocol_results = check_protocols_cross_platform(tshark_path, tls_protocols)
    capabilities.update({f'{p}_protocol': v for p, v in protocol_results.items()})
    
    # 2. 检查TLS相关字段
    print("\n📋 Field Support:")
    tls_fields = [
        'tls.app_data',
        'tls.record.content_type',
        'tls.record.length',
        'tls.handshake.type',
        'tcp.stream',
        'tcp.port',
        'frame.number'
    ]
    field_results = check_fields_cross_platform(tshark_path, tls_fields)
    capabilities.update({f'{f.replace(".", "_")}_field': v for f, v in field_results.items()})
    
    # 3. 检查JSON输出支持
    print("\n📋 JSON Output Support:")
    try:
        result = subprocess.run(
            [tshark_path, '-T', 'json', '--help'],
            capture_output=True,
            text=True,
            timeout=10
        )
        json_support = result.returncode == 0
        capabilities['json_output'] = json_support
        
        if json_support:
            print("✅ JSON output: Supported")
        else:
            print("❌ JSON output: Not supported")
    except Exception as e:
        capabilities['json_output'] = False
        print(f"❌ JSON output check error: {e}")
    
    # 4. 检查两遍分析支持
    print("\n📋 Two-pass Analysis Support:")
    try:
        result = subprocess.run(
            [tshark_path, '-2', '--help'],
            capture_output=True,
            text=True,
            timeout=10
        )
        two_pass_support = result.returncode == 0
        capabilities['two_pass_analysis'] = two_pass_support
        
        if two_pass_support:
            print("✅ Two-pass analysis (-2): Supported")
        else:
            print("❌ Two-pass analysis (-2): Not supported")
    except Exception as e:
        capabilities['two_pass_analysis'] = False
        print(f"❌ Two-pass analysis check error: {e}")
    
    return capabilities


def generate_platform_specific_commands(tshark_path: str):
    """生成平台特定的验证命令"""
    print("\n📋 Platform-Specific Verification Commands:")
    print("-" * 50)
    
    system = platform.system()
    
    if system == 'Windows':
        print("Windows Commands:")
        print(f'  Protocol check: "{tshark_path}" -G protocols | findstr /i "tls ssl tcp"')
        print(f'  Field check: "{tshark_path}" -G fields | findstr "tls.app_data"')
        print(f'  Version check: "{tshark_path}" -v')
    else:
        print("Unix/Linux/macOS Commands:")
        print(f"  Protocol check: {tshark_path} -G protocols | grep -i 'tls\\|ssl\\|tcp'")
        print(f"  Field check: {tshark_path} -G fields | grep 'tls.app_data'")
        print(f"  Version check: {tshark_path} -v")
    
    print("\nCross-platform Python alternative:")
    print("  python scripts/cross_platform_tshark_check.py")


def main():
    """主函数"""
    print("🔧 Cross-Platform TShark Capability Checker")
    print("=" * 60)
    
    # 查找TShark
    tshark_path = get_tshark_path()
    if not tshark_path:
        print("❌ TShark not found!")
        print("\nInstallation required:")
        if platform.system() == 'Windows':
            print("  • Download from: https://www.wireshark.org/download.html")
            print("  • Or use: choco install wireshark")
        else:
            print("  • macOS: brew install --cask wireshark")
            print("  • Ubuntu: sudo apt install wireshark")
            print("  • CentOS: sudo yum install wireshark")
        return
    
    print(f"📍 TShark found: {tshark_path}")
    print(f"🖥️  Platform: {platform.system()} {platform.release()}")
    
    # 检查版本
    try:
        result = subprocess.run([tshark_path, '-v'], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            print(f"📦 Version: {version_line}")
        else:
            print("❌ Version check failed")
    except Exception as e:
        print(f"❌ Version check error: {e}")
    
    # 全面检查TLS功能
    capabilities = check_tls_capabilities_comprehensive(tshark_path)
    
    # 生成平台特定命令
    generate_platform_specific_commands(tshark_path)
    
    # 总结
    print("\n📊 Summary:")
    print("-" * 30)
    total_checks = len(capabilities)
    passed_checks = sum(capabilities.values())
    
    print(f"Total checks: {total_checks}")
    print(f"Passed: {passed_checks}")
    print(f"Failed: {total_checks - passed_checks}")
    
    if passed_checks == total_checks:
        print("\n🎉 All TLS capabilities are available!")
    else:
        print(f"\n⚠️  {total_checks - passed_checks} capabilities missing")
        print("   Consider reinstalling Wireshark with full components")
    
    # 失败的检查
    failed_checks = [name for name, passed in capabilities.items() if not passed]
    if failed_checks:
        print(f"\n❌ Failed checks: {', '.join(failed_checks)}")


if __name__ == '__main__':
    main()
