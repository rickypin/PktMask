#!/usr/bin/env python3
"""
PktMask 样本数据验证脚本
独立运行脚本，用于验证 tests/data/samples/ 下的所有样本文件
"""
import sys
import argparse
import subprocess
from pathlib import Path


def run_samples_validation(verbose: bool = True, 
                          quick: bool = False,
                          category: str = None,
                          html_report: bool = True) -> int:
    """运行样本验证测试"""
    
    # 构建pytest命令
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/integration/test_real_data_validation.py",
        "-m", "real_data",
        "--tb=short"
    ]
    
    # 详细输出
    if verbose:
        cmd.extend(["-v", "-s"])
    else:
        cmd.append("-q")
    
    # 快速模式（限制测试包数量）
    if quick:
        cmd.append("--maxfail=3")  # 最多3个失败就停止
    
    # 特定类别测试
    if category:
        cmd.extend(["-k", f"test_sample_category_validation and {category}"])
    
    # HTML报告
    if html_report:
        cmd.extend([
            "--html=reports/samples_validation_report.html",
            "--self-contained-html"
        ])
    
    # 显示最慢的测试
    cmd.append("--durations=10")
    
    print("🚀 PktMask 样本数据验证测试")
    print("=" * 50)
    print(f"📁 测试范围: tests/data/samples/ 所有目录")
    print(f"🎯 测试模式: {'快速' if quick else '完整'}")
    if category:
        print(f"📋 测试类别: {category}")
    print(f"📊 HTML报告: {'启用' if html_report else '禁用'}")
    print("-" * 50)
    print(f"🔧 执行命令: {' '.join(cmd)}")
    print("-" * 50)
    
    # 执行测试
    return subprocess.run(cmd).returncode


def list_available_categories():
    """列出可用的测试类别"""
    categories = [
        ("plain_ip", "基础TCP/IP + TLS流量"),
        ("plain_ip_tls70", "TLS 7.0版本流量"),
        ("single_vlan", "单层VLAN封装(802.1Q)"),
        ("double_vlan", "双层VLAN封装(802.1ad QinQ)"),
        ("double_vlan_tls", "双层VLAN + TLS组合"),
        ("mpls", "MPLS标签交换"),
        ("gre_tunnel", "GRE隧道封装"),
        ("vxlan", "VXLAN虚拟化网络"),
        ("vxlan_custom", "VXLAN自定义端口4787"),
        ("vxlan_vlan_composite", "VXLAN + VLAN复合封装"),
        ("vlan_gre_composite", "VLAN + GRE复合封装"),
        ("large_ip_set", "大IP地址集测试数据"),
        ("test_case_001", "测试用例001系列"),
        ("test_case_002_5", "测试用例002-5系列"),
        ("test_case_002_8", "测试用例002-8系列")
    ]
    
    print("\n📋 可用的测试类别:")
    print("-" * 60)
    for category, description in categories:
        print(f"  {category:<25} - {description}")
    print()


def check_samples_directory():
    """检查样本目录是否存在"""
    samples_dir = Path("tests/data/samples")
    if not samples_dir.exists():
        print(f"❌ 错误: 样本目录不存在: {samples_dir}")
        print("   请确保在PktMask项目根目录下运行此脚本")
        return False
    
    # 统计目录和文件
    dirs = [d for d in samples_dir.iterdir() if d.is_dir() and not d.name.startswith('.')]
    total_files = 0
    
    print(f"📁 样本目录检查: {samples_dir}")
    print(f"📊 发现 {len(dirs)} 个子目录:")
    
    for dir_path in sorted(dirs):
        pcap_files = list(dir_path.glob("*.pcap")) + list(dir_path.glob("*.pcapng"))
        pcap_files = [f for f in pcap_files if not f.name.startswith('.')]
        total_files += len(pcap_files)
        
        status = "✅" if pcap_files else "⚠️ "
        print(f"  {status} {dir_path.name:<20} - {len(pcap_files)} 个文件")
    
    print(f"\n📈 总计: {total_files} 个样本文件待测试")
    return True


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="PktMask 样本数据验证脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python validate_samples.py                    # 完整验证所有样本
  python validate_samples.py --quick            # 快速验证模式
  python validate_samples.py --category mpls    # 只测试MPLS类别
  python validate_samples.py --list-categories  # 显示所有可用类别
  python validate_samples.py --check            # 只检查样本目录
  python validate_samples.py --quiet            # 静默模式
        """
    )
    
    parser.add_argument("--quick", action="store_true",
                       help="快速验证模式 - 限制测试深度")
    parser.add_argument("--category", type=str,
                       help="只测试特定类别的样本")
    parser.add_argument("--list-categories", action="store_true",
                       help="列出所有可用的测试类别")
    parser.add_argument("--check", action="store_true",
                       help="只检查样本目录，不运行测试")
    parser.add_argument("--quiet", action="store_true",
                       help="静默模式 - 减少输出")
    parser.add_argument("--no-html", action="store_true",
                       help="不生成HTML报告")
    
    args = parser.parse_args()
    
    # 显示类别列表
    if args.list_categories:
        list_available_categories()
        return 0
    
    # 检查样本目录
    if not check_samples_directory():
        return 1
    
    # 只检查不测试
    if args.check:
        print("\n✅ 样本目录检查完成")
        return 0
    
    # 运行验证测试
    try:
        exit_code = run_samples_validation(
            verbose=not args.quiet,
            quick=args.quick,
            category=args.category,
            html_report=not args.no_html
        )
        
        if exit_code == 0:
            print("\n🎉 样本验证测试完成！")
            if not args.no_html:
                print("📊 查看详细报告: reports/samples_validation_report.html")
        else:
            print(f"\n❌ 样本验证测试失败 (退出码: {exit_code})")
            
        return exit_code
        
    except KeyboardInterrupt:
        print("\n⏹️ 测试被用户中断")
        return 1
    except Exception as e:
        print(f"\n❌ 运行错误: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 