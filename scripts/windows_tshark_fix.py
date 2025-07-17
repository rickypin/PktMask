#!/usr/bin/env python3
"""
Windows TShark 问题诊断和修复脚本

专门用于解决Windows平台下TShark TLS marker验证失败的问题。
提供自动诊断、修复建议和验证功能。
"""

import os
import sys
import subprocess
import platform
import shutil
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import argparse

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.pktmask.infrastructure.tshark.manager import TSharkManager
from src.pktmask.infrastructure.tshark.tls_validator import TLSValidator


class WindowsTSharkFixer:
    """Windows TShark 问题修复器"""
    
    def __init__(self):
        self.tshark_manager = TSharkManager()
        self.tls_validator = TLSValidator()
        
        # Windows特定的TShark路径
        self.windows_paths = [
            r'C:\Program Files\Wireshark\tshark.exe',
            r'C:\Program Files (x86)\Wireshark\tshark.exe',
            r'C:\ProgramData\chocolatey\bin\tshark.exe',
            r'C:\tools\wireshark\tshark.exe',
            r'C:\Wireshark\tshark.exe',
        ]
        
        # 必需的TLS功能
        self.required_capabilities = [
            'tls_protocol_support',
            'json_output_support', 
            'field_extraction_support',
            'tcp_reassembly_support',
            'tls_record_parsing',
            'tls_app_data_extraction',
            'tcp_stream_tracking',
            'two_pass_analysis'
        ]
    
    def check_system_info(self) -> Dict:
        """检查系统信息"""
        info = {
            'platform': platform.platform(),
            'system': platform.system(),
            'release': platform.release(),
            'version': platform.version(),
            'machine': platform.machine(),
            'python_version': sys.version,
            'is_admin': self._is_admin()
        }
        return info
    
    def _is_admin(self) -> bool:
        """检查是否以管理员权限运行"""
        try:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False
    
    def scan_tshark_installations(self) -> List[Dict]:
        """扫描所有可能的TShark安装"""
        installations = []
        
        print("🔍 Scanning for TShark installations...")
        
        # 检查预定义路径
        for path in self.windows_paths:
            if Path(path).exists():
                info = self._analyze_tshark_installation(path)
                installations.append(info)
                print(f"   Found: {path}")
        
        # 检查系统PATH
        system_tshark = shutil.which('tshark')
        if system_tshark:
            info = self._analyze_tshark_installation(system_tshark)
            installations.append(info)
            print(f"   Found in PATH: {system_tshark}")
        
        # 检查注册表中的Wireshark安装
        registry_paths = self._get_registry_paths()
        for path in registry_paths:
            tshark_path = Path(path) / 'tshark.exe'
            if tshark_path.exists():
                info = self._analyze_tshark_installation(str(tshark_path))
                installations.append(info)
                print(f"   Found in registry: {tshark_path}")
        
        return installations
    
    def _get_registry_paths(self) -> List[str]:
        """从Windows注册表获取Wireshark安装路径"""
        paths = []
        try:
            import winreg
            
            # 检查常见的注册表位置
            registry_keys = [
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Wireshark"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Wireshark"),
                (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Wireshark"),
            ]
            
            for hkey, subkey in registry_keys:
                try:
                    with winreg.OpenKey(hkey, subkey) as key:
                        install_path, _ = winreg.QueryValueEx(key, "InstallDir")
                        paths.append(install_path)
                except (FileNotFoundError, OSError):
                    continue
                    
        except ImportError:
            # winreg不可用
            pass
        
        return paths
    
    def _analyze_tshark_installation(self, path: str) -> Dict:
        """分析TShark安装的详细信息"""
        info = {
            'path': path,
            'exists': Path(path).exists(),
            'version': None,
            'version_string': '',
            'capabilities': {},
            'issues': [],
            'recommendations': []
        }
        
        if not info['exists']:
            info['issues'].append('File does not exist')
            return info
        
        # 检查版本
        try:
            result = subprocess.run(
                [path, '-v'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                info['version_string'] = result.stdout.strip()
                info['version'] = self._parse_version(result.stdout)
            else:
                info['issues'].append(f'Version check failed: {result.stderr}')
                
        except Exception as e:
            info['issues'].append(f'Version check error: {e}')
        
        # 检查TLS功能
        if info['version']:
            info['capabilities'] = self.tshark_manager.verify_tls_capabilities(path)
            
            # 分析缺失的功能
            missing_caps = [
                cap for cap in self.required_capabilities 
                if not info['capabilities'].get(cap, False)
            ]
            
            if missing_caps:
                info['issues'].extend([f'Missing capability: {cap}' for cap in missing_caps])
                info['recommendations'].extend(self._get_capability_recommendations(missing_caps))
        
        return info
    
    def _parse_version(self, version_output: str) -> Optional[Tuple[int, int, int]]:
        """解析TShark版本号"""
        import re
        
        # 查找版本号模式
        pattern = r'TShark.*?(\d+)\.(\d+)\.(\d+)'
        match = re.search(pattern, version_output)
        
        if match:
            return (int(match.group(1)), int(match.group(2)), int(match.group(3)))
        
        return None
    
    def _get_capability_recommendations(self, missing_caps: List[str]) -> List[str]:
        """根据缺失功能提供修复建议"""
        recommendations = []
        
        if 'tls_protocol_support' in missing_caps:
            recommendations.append('Reinstall Wireshark with full protocol support')
        
        if 'json_output_support' in missing_caps:
            recommendations.append('Upgrade to TShark version >= 4.2.0')
        
        if any('tls_' in cap for cap in missing_caps):
            recommendations.append('Install complete Wireshark package (not minimal)')
        
        if 'two_pass_analysis' in missing_caps:
            recommendations.append('Ensure TShark supports -2 flag (version >= 4.0.0)')
        
        return recommendations
    
    def generate_fix_report(self, installations: List[Dict]) -> Dict:
        """生成修复报告"""
        report = {
            'system_info': self.check_system_info(),
            'installations_found': len(installations),
            'working_installations': [],
            'problematic_installations': [],
            'recommendations': [],
            'next_steps': []
        }
        
        for install in installations:
            if not install['issues']:
                report['working_installations'].append(install)
            else:
                report['problematic_installations'].append(install)
        
        # 生成总体建议
        if not report['working_installations']:
            report['recommendations'].extend([
                'No working TShark installation found',
                'Download and install latest Wireshark from https://www.wireshark.org/',
                'Ensure "Command Line Tools" option is selected during installation',
                'Run installation as Administrator'
            ])
            
            report['next_steps'].extend([
                '1. Uninstall existing Wireshark versions',
                '2. Download Wireshark >= 4.2.0 from official website',
                '3. Install as Administrator with all components',
                '4. Run this script again to verify'
            ])
        
        elif len(report['working_installations']) > 1:
            report['recommendations'].append('Multiple TShark installations found - consider using the latest version')
        
        return report
    
    def print_report(self, report: Dict):
        """打印修复报告"""
        print("\n" + "="*60)
        print(" Windows TShark 诊断报告")
        print("="*60)
        
        # 系统信息
        sys_info = report['system_info']
        print(f"\n📋 系统信息:")
        print(f"   Platform: {sys_info['platform']}")
        print(f"   Python: {sys_info['python_version'].split()[0]}")
        print(f"   Admin Rights: {'✅' if sys_info['is_admin'] else '❌'}")
        
        # 安装情况
        print(f"\n🔍 TShark 安装扫描:")
        print(f"   Found {report['installations_found']} installation(s)")
        
        # 工作的安装
        if report['working_installations']:
            print(f"\n✅ 可用的安装 ({len(report['working_installations'])}):")
            for install in report['working_installations']:
                version_str = f"v{'.'.join(map(str, install['version']))}" if install['version'] else "Unknown"
                print(f"   • {install['path']} ({version_str})")
        
        # 有问题的安装
        if report['problematic_installations']:
            print(f"\n❌ 有问题的安装 ({len(report['problematic_installations'])}):")
            for install in report['problematic_installations']:
                print(f"   • {install['path']}")
                for issue in install['issues'][:3]:  # 只显示前3个问题
                    print(f"     - {issue}")
                if len(install['issues']) > 3:
                    print(f"     - ... and {len(install['issues']) - 3} more issues")
        
        # 建议
        if report['recommendations']:
            print(f"\n💡 修复建议:")
            for i, rec in enumerate(report['recommendations'], 1):
                print(f"   {i}. {rec}")
        
        # 下一步
        if report['next_steps']:
            print(f"\n🔧 下一步操作:")
            for step in report['next_steps']:
                print(f"   {step}")
    
    def auto_fix(self) -> bool:
        """尝试自动修复TShark问题"""
        print("\n🔧 Attempting automatic fixes...")
        
        # 检查是否有管理员权限
        if not self._is_admin():
            print("❌ Administrator privileges required for auto-fix")
            print("   Please run this script as Administrator")
            return False
        
        # 尝试通过Chocolatey安装
        if self._try_chocolatey_install():
            return True
        
        # 尝试修复现有安装
        if self._try_repair_existing():
            return True
        
        print("❌ Auto-fix failed. Please follow manual installation steps.")
        return False
    
    def _try_chocolatey_install(self) -> bool:
        """尝试通过Chocolatey安装Wireshark"""
        print("   Trying Chocolatey installation...")
        
        # 检查Chocolatey是否可用
        if not shutil.which('choco'):
            print("   Chocolatey not found, skipping...")
            return False
        
        try:
            # 安装Wireshark
            result = subprocess.run(
                ['choco', 'install', 'wireshark', '-y'],
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )
            
            if result.returncode == 0:
                print("   ✅ Chocolatey installation successful")
                return True
            else:
                print(f"   ❌ Chocolatey installation failed: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"   ❌ Chocolatey installation error: {e}")
            return False
    
    def _try_repair_existing(self) -> bool:
        """尝试修复现有安装"""
        print("   Trying to repair existing installations...")
        
        # 这里可以添加修复逻辑，比如：
        # - 重新注册协议解析器
        # - 修复权限问题
        # - 重建配置文件
        
        # 目前只是占位符
        return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='Windows TShark 问题诊断和修复工具')
    parser.add_argument('--scan-only', action='store_true', help='只扫描，不尝试修复')
    parser.add_argument('--auto-fix', action='store_true', help='尝试自动修复')
    parser.add_argument('--verbose', action='store_true', help='详细输出')
    
    args = parser.parse_args()
    
    # 检查是否在Windows上运行
    if platform.system() != 'Windows':
        print("❌ This script is designed for Windows only")
        print(f"   Current platform: {platform.system()}")
        sys.exit(1)
    
    print("🔧 Windows TShark 问题诊断和修复工具")
    print("="*50)
    
    fixer = WindowsTSharkFixer()
    
    # 扫描安装
    installations = fixer.scan_tshark_installations()
    
    # 生成报告
    report = fixer.generate_fix_report(installations)
    
    # 打印报告
    fixer.print_report(report)
    
    # 自动修复
    if args.auto_fix and not args.scan_only:
        if not report['working_installations']:
            success = fixer.auto_fix()
            if success:
                print("\n🎉 Auto-fix completed! Please run validation script to verify.")
            else:
                print("\n❌ Auto-fix failed. Please follow manual steps above.")
        else:
            print("\n✅ Working TShark installation found, no auto-fix needed.")
    
    # 退出码
    if report['working_installations']:
        sys.exit(0)  # 成功
    else:
        sys.exit(1)  # 需要修复


if __name__ == '__main__':
    main()
