#!/usr/bin/env python3
"""
PktMask TShark 依赖检查脚本

此脚本用于验证系统中的tshark安装是否满足PktMask的要求。
可以在部署前或故障排除时使用。

使用方法:
    python scripts/check_tshark_dependencies.py
    python scripts/check_tshark_dependencies.py --tshark-path /custom/path/to/tshark
    python scripts/check_tshark_dependencies.py --verbose
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# PktMask要求的最低tshark版本
MIN_TSHARK_VERSION = (4, 2, 0)

# 默认搜索路径
DEFAULT_TSHARK_PATHS = [
    '/usr/bin/tshark',
    '/usr/local/bin/tshark',
    '/opt/wireshark/bin/tshark',
    'C:\\Program Files\\Wireshark\\tshark.exe',
    'C:\\Program Files (x86)\\Wireshark\\tshark.exe',
    '/Applications/Wireshark.app/Contents/MacOS/tshark'
]

# 必需的协议支持
REQUIRED_PROTOCOLS = ['tcp', 'tls', 'ssl', 'ip', 'ipv6']

# 必需的字段支持
REQUIRED_FIELDS = [
    'frame.number',
    'frame.protocols',
    'tcp.stream',
    'tcp.seq',
    'tcp.seq_raw',
    'tcp.payload',
    'tls.record.content_type',
    'tls.app_data'
]


def parse_tshark_version(output: str) -> Optional[Tuple[int, int, int]]:
    """解析tshark版本号"""
    match = re.search(r'(\d+)\.(\d+)\.(\d+)', output)
    if match:
        return tuple(map(int, match.groups()))
    return None


def is_executable(path: str) -> bool:
    """检查文件是否可执行"""
    try:
        path_obj = Path(path)
        if not path_obj.exists():
            return False

        # Windows下检查文件扩展名
        if os.name == 'nt':
            return path_obj.suffix.lower() == '.exe'
        else:
            # Unix-like系统检查执行权限
            return os.access(path, os.X_OK)
    except Exception as e:
        print(f"Error checking if path is executable: {path}, error: {e}", file=sys.stderr)
        return False


def find_tshark_executable(custom_path: Optional[str] = None) -> Optional[str]:
    """查找tshark可执行文件"""
    # 1. 检查自定义路径
    if custom_path:
        if Path(custom_path).exists() and is_executable(custom_path):
            return custom_path
        else:
            print(f"❌ 自定义路径不存在或不可执行: {custom_path}")
            return None

    # 2. 检查默认路径
    for path in DEFAULT_TSHARK_PATHS:
        if Path(path).exists() and is_executable(path):
            print(f"✅ 在默认路径找到tshark: {path}")
            return path

    # 3. 在系统PATH中搜索
    which_result = shutil.which('tshark')
    if which_result and is_executable(which_result):
        print(f"✅ 在系统PATH中找到tshark: {which_result}")
        return which_result

    # 4. Windows特殊处理：检查常见的Wireshark安装位置
    if os.name == 'nt':  # Windows
        additional_paths = [
            r"C:\Program Files\Wireshark\tshark.exe",
            r"C:\Program Files (x86)\Wireshark\tshark.exe",
            # 检查用户目录下的便携版本
            os.path.expanduser(r"~\AppData\Local\Programs\Wireshark\tshark.exe"),
            # 检查当前目录下的便携版本（打包应用可能包含）
            os.path.join(os.getcwd(), "tshark.exe"),
            os.path.join(os.path.dirname(sys.executable), "tshark.exe"),
        ]

        for path in additional_paths:
            if Path(path).exists() and is_executable(path):
                print(f"✅ 在Windows特定路径找到tshark: {path}")
                return path

    print("❌ 在所有已知位置都未找到tshark可执行文件")
    return None


def check_tshark_version(tshark_path: str) -> Dict[str, any]:
    """检查tshark版本"""
    result = {
        'success': False,
        'version': None,
        'version_string': '',
        'meets_requirement': False,
        'error': None
    }
    
    try:
        proc = subprocess.run(
            [tshark_path, '-v'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if proc.returncode != 0:
            result['error'] = f"tshark -v 返回非零退出码: {proc.returncode}"
            return result
        
        output = proc.stdout + proc.stderr
        result['version_string'] = output.strip()
        
        version = parse_tshark_version(output)
        if version:
            result['version'] = version
            result['meets_requirement'] = version >= MIN_TSHARK_VERSION
            result['success'] = True
        else:
            result['error'] = "无法解析版本号"
            
    except subprocess.TimeoutExpired:
        result['error'] = "tshark -v 执行超时"
    except Exception as e:
        result['error'] = f"执行tshark -v 失败: {e}"
    
    return result


def check_protocol_support(tshark_path: str) -> Dict[str, any]:
    """检查协议支持"""
    result = {
        'success': False,
        'supported_protocols': [],
        'missing_protocols': [],
        'error': None
    }

    try:
        proc = subprocess.run(
            [tshark_path, '-G', 'protocols'],
            capture_output=True,
            text=True,
            timeout=30
        )

        if proc.returncode != 0:
            stderr_info = proc.stderr if proc.stderr else "No error details available"
            result['error'] = f"tshark -G protocols 返回非零退出码: {proc.returncode}, stderr: {stderr_info}"
            return result

        # 检查stdout是否为None (Windows打包环境下可能出现)
        if proc.stdout is None:
            result['error'] = "tshark -G protocols 返回空输出 (stdout is None)"
            print(f"Warning: TShark protocol check returned None stdout. Path: {tshark_path}, returncode: {proc.returncode}", file=sys.stderr)
            return result

        # 检查stdout是否为空字符串
        if not proc.stdout.strip():
            result['error'] = "tshark -G protocols 返回空输出"
            print(f"Warning: TShark protocol check returned empty stdout. Path: {tshark_path}", file=sys.stderr)
            return result

        protocols = proc.stdout.lower()

        for protocol in REQUIRED_PROTOCOLS:
            if protocol in protocols:
                result['supported_protocols'].append(protocol)
            else:
                result['missing_protocols'].append(protocol)

        result['success'] = len(result['missing_protocols']) == 0

    except subprocess.TimeoutExpired:
        result['error'] = "tshark -G protocols 执行超时"
        print(f"Error: TShark protocol check timeout for path: {tshark_path}", file=sys.stderr)
    except Exception as e:
        result['error'] = f"检查协议支持失败: {e}"
        print(f"Error: TShark protocol check exception for path: {tshark_path}, error: {e}", file=sys.stderr)

    return result


def check_field_support(tshark_path: str) -> Dict[str, any]:
    """检查字段支持"""
    result = {
        'success': False,
        'supported_fields': [],
        'missing_fields': [],
        'error': None
    }

    try:
        proc = subprocess.run(
            [tshark_path, '-G', 'fields'],
            capture_output=True,
            text=True,
            timeout=30
        )

        if proc.returncode != 0:
            stderr_info = proc.stderr if proc.stderr else "No error details available"
            result['error'] = f"tshark -G fields 返回非零退出码: {proc.returncode}, stderr: {stderr_info}"
            return result

        # 检查stdout是否为None (Windows打包环境下可能出现)
        if proc.stdout is None:
            result['error'] = "tshark -G fields 返回空输出 (stdout is None)"
            print(f"Warning: TShark field check returned None stdout. Path: {tshark_path}, returncode: {proc.returncode}", file=sys.stderr)
            return result

        # 检查stdout是否为空字符串
        if not proc.stdout.strip():
            result['error'] = "tshark -G fields 返回空输出"
            print(f"Warning: TShark field check returned empty stdout. Path: {tshark_path}", file=sys.stderr)
            return result

        fields = proc.stdout

        for field in REQUIRED_FIELDS:
            if field in fields:
                result['supported_fields'].append(field)
            else:
                result['missing_fields'].append(field)

        result['success'] = len(result['missing_fields']) == 0

    except subprocess.TimeoutExpired:
        result['error'] = "tshark -G fields 执行超时"
        print(f"Error: TShark field check timeout for path: {tshark_path}", file=sys.stderr)
    except Exception as e:
        result['error'] = f"检查字段支持失败: {e}"
        print(f"Error: TShark field check exception for path: {tshark_path}, error: {e}", file=sys.stderr)

    return result


def check_json_output(tshark_path: str) -> Dict[str, any]:
    """检查JSON输出功能"""
    result = {
        'success': False,
        'error': None
    }
    
    try:
        # 创建一个最小的测试命令
        proc = subprocess.run(
            [tshark_path, '-T', 'json', '-c', '0'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        # 即使没有输入文件，tshark也应该能够识别JSON格式选项
        # 返回码可能不是0，但不应该有格式错误
        if 'json' in proc.stderr.lower() and 'invalid' in proc.stderr.lower():
            result['error'] = "JSON输出格式不被支持"
        else:
            result['success'] = True
            
    except subprocess.TimeoutExpired:
        result['error'] = "JSON输出测试超时"
    except Exception as e:
        result['error'] = f"JSON输出测试失败: {e}"
    
    return result


def print_results(results: Dict[str, any], verbose: bool = False):
    """打印检查结果"""
    print("=" * 60)
    print("PktMask TShark 依赖检查结果")
    print("=" * 60)
    
    # 可执行文件检查
    if results['executable']['found']:
        print(f"✅ TShark可执行文件: {results['executable']['path']}")
    else:
        print("❌ TShark可执行文件: 未找到")
        print("   请安装Wireshark或配置正确的路径")
        return
    
    # 版本检查
    version_result = results['version']
    if version_result['success']:
        version_str = '.'.join(map(str, version_result['version']))
        min_version_str = '.'.join(map(str, MIN_TSHARK_VERSION))
        
        if version_result['meets_requirement']:
            print(f"✅ TShark版本: {version_str} (>= {min_version_str})")
        else:
            print(f"❌ TShark版本: {version_str} (需要 >= {min_version_str})")
    else:
        print(f"❌ 版本检查失败: {version_result['error']}")
    
    # 协议支持检查
    protocol_result = results['protocols']
    if protocol_result['success']:
        print(f"✅ 协议支持: 所有必需协议都支持")
        if verbose:
            print(f"   支持的协议: {', '.join(protocol_result['supported_protocols'])}")
    else:
        print(f"❌ 协议支持: 缺少必需协议")
        if protocol_result['missing_protocols']:
            print(f"   缺少的协议: {', '.join(protocol_result['missing_protocols'])}")
    
    # 字段支持检查
    field_result = results['fields']
    if field_result['success']:
        print(f"✅ 字段支持: 所有必需字段都支持")
        if verbose:
            print(f"   支持的字段数: {len(field_result['supported_fields'])}")
    else:
        print(f"❌ 字段支持: 缺少必需字段")
        if field_result['missing_fields']:
            print(f"   缺少的字段: {', '.join(field_result['missing_fields'][:5])}")
            if len(field_result['missing_fields']) > 5:
                print(f"   ... 还有 {len(field_result['missing_fields']) - 5} 个字段")
    
    # JSON输出检查
    json_result = results['json']
    if json_result['success']:
        print("✅ JSON输出: 支持")
    else:
        print(f"❌ JSON输出: {json_result['error']}")
    
    # 总体结果
    print("-" * 60)
    all_passed = all([
        results['executable']['found'],
        version_result['success'] and version_result['meets_requirement'],
        protocol_result['success'],
        field_result['success'],
        json_result['success']
    ])
    
    if all_passed:
        print("🎉 所有检查通过！TShark满足PktMask的要求。")
    else:
        print("⚠️  存在问题，请解决上述问题后重新检查。")
        print("\n建议解决方案:")
        print("1. 安装或升级Wireshark到最新版本")
        print("2. 确保tshark在系统PATH中或使用--tshark-path指定路径")
        print("3. 参考PktMask文档中的安装指南")


def main():
    parser = argparse.ArgumentParser(
        description="检查TShark依赖是否满足PktMask要求",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        '--tshark-path',
        help="自定义tshark可执行文件路径"
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help="显示详细信息"
    )
    parser.add_argument(
        '--json-output',
        action='store_true',
        help="以JSON格式输出结果"
    )
    
    args = parser.parse_args()
    
    # 查找tshark可执行文件
    tshark_path = find_tshark_executable(args.tshark_path)
    
    results = {
        'executable': {
            'found': tshark_path is not None,
            'path': tshark_path
        }
    }
    
    if not tshark_path:
        if args.json_output:
            print(json.dumps(results, indent=2))
        else:
            print_results(results, args.verbose)
        sys.exit(1)
    
    # 执行各项检查
    results['version'] = check_tshark_version(tshark_path)
    results['protocols'] = check_protocol_support(tshark_path)
    results['fields'] = check_field_support(tshark_path)
    results['json'] = check_json_output(tshark_path)
    
    # 输出结果
    if args.json_output:
        print(json.dumps(results, indent=2))
    else:
        print_results(results, args.verbose)
    
    # 设置退出码
    all_passed = all([
        results['executable']['found'],
        results['version']['success'] and results['version']['meets_requirement'],
        results['protocols']['success'],
        results['fields']['success'],
        results['json']['success']
    ])
    
    sys.exit(0 if all_passed else 1)


if __name__ == '__main__':
    main()
