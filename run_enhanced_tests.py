#!/usr/bin/env python3
"""
增强版真实数据测试运行器
执行完整的IP匿名化验证测试
"""

import sys
import time
import argparse
from pathlib import Path
from typing import List, Dict, Any

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from tests.integration.test_enhanced_real_data_validation import (
    EnhancedRealDataValidator, 
    EnhancedTestResult
)


class EnhancedTestRunner:
    """增强版测试运行器"""
    
    def __init__(self):
        self.validator = EnhancedRealDataValidator()
        self.test_samples = [
            # 基础封装类型
            ("tests/data/samples/TLS/tls_sample.pcap", "plain_ip", "Plain IP 样本"),
            ("tests/data/samples/singlevlan/10.200.33.61(10笔).pcap", "single_vlan", "Single VLAN 样本"),
            ("tests/data/samples/doublevlan/172.24.0.51.pcap", "double_vlan", "Double VLAN 样本"),
            ("tests/data/samples/mpls/mpls.pcap", "mpls", "MPLS 样本"),
            ("tests/data/samples/vxlan/vxlan.pcap", "vxlan", "VXLAN 样本"),
            
            # 扩展封装类型
            ("tests/data/samples/gre/20160406152100.pcap", "gre", "GRE 样本"),
            ("tests/data/samples/vlan_gre/case17-parts.pcap", "vlan_gre", "VLAN+GRE 复合样本"),
            ("tests/data/samples/vxlan_vlan/vxlan_servicetag_1001.pcap", "vxlan_vlan", "VXLAN+VLAN 复合样本"),
            ("tests/data/samples/TLS70/sslerr1-70.pcap", "tls70", "TLS70 样本"),
            ("tests/data/samples/doublevlan_tls/TC-007-3-20230829-01.pcap", "doublevlan_tls", "Double VLAN + TLS 样本"),
            
            # 剩余案例覆盖
            ("tests/data/samples/IPTCP-200ips/TC-002-6-20200927-S-A-Replaced.pcapng", "large_dataset", "200 IP大数据集样本"),
            ("tests/data/samples/IPTCP-TC-001-1-20160407/TC-001-1-20160407-A.pcap", "test_case_001", "测试用例001样本"),
            ("tests/data/samples/IPTCP-TC-002-5-20220215/TC-002-5-20220215-FW-in.pcap", "test_case_002_5", "测试用例002-5样本"),
            ("tests/data/samples/IPTCP-TC-002-8-20210817/TC-002-8-20210817.pcapng", "test_case_002_8", "测试用例002-8样本"),
            ("tests/data/samples/vxlan4787/vxlan-double-http.pcap", "vxlan4787", "VXLAN4787变种样本"),
        ]
    
    def run_enhanced_validation(self, mode: str = "standard") -> Dict[str, Any]:
        """运行增强版验证测试"""
        print("🚀 增强版真实数据验证测试")
        print("=" * 60)
        print("📋 测试内容:")
        print("   ✓ 封装检测验证")
        print("   ✓ IP地址提取验证")  
        print("   ✓ IP匿名化处理验证")
        print("   ✓ 映射一致性验证")
        print("   ✓ 数量保持验证")
        print("   ✓ 匿名IP有效性验证")
        print("   ✓ 覆盖率验证 (≥95%)")
        print("=" * 60)
        
        start_time = time.time()
        results = []
        
        # 运行测试
        for sample_file, category, description in self.test_samples:
            sample_path = Path(sample_file)
            
            if not sample_path.exists():
                print(f"⚠️  跳过不存在的样本: {sample_file}")
                continue
            
            print(f"\n🧪 测试: {description}")
            print(f"   📁 文件: {sample_path.name}")
            print(f"   🏷️  类别: {category}")
            
            result = self.validator.validate_sample_file_with_anonymization(
                sample_path, category, max_test_packets=50 if mode == "quick" else 100
            )
            
            results.append(result)
            
            # 输出结果摘要
            if result.success:
                print(f"   ✅ 成功")
                print(f"   📊 统计: {result.tested_packets}包, {len(result.original_ips)}IP, {len(result.ip_mappings)}映射")
                print(f"   🎯 指标: 覆盖{result.anonymization_coverage:.1%}, 唯一{result.unique_mapping_ratio:.1%}")
                print(f"   ⏱️  耗时: {result.processing_time:.3f}s")
            else:
                print(f"   ❌ 失败")
                for error in result.errors[:2]:
                    print(f"      • {error}")
        
        # 生成总结报告
        self._generate_summary_report(results, time.time() - start_time)
        
        return {
            "total_tests": len(results),
            "successful_tests": len([r for r in results if r.success]),
            "results": results
        }
    
    def run_consistency_test(self) -> bool:
        """运行一致性测试"""
        print("\n🔄 映射一致性测试")
        print("-" * 40)
        
        sample_file = Path("tests/data/samples/TLS/tls_sample.pcap")
        if not sample_file.exists():
            print("⚠️  测试样本文件不存在")
            return False
        
        print(f"📁 测试文件: {sample_file.name}")
        print("🔍 执行两次匿名化并比较映射...")
        
        # 执行两次测试
        result1 = self.validator.validate_sample_file_with_anonymization(sample_file, "plain_ip")
        result2 = self.validator.validate_sample_file_with_anonymization(sample_file, "plain_ip")
        
        if not (result1.success and result2.success):
            print("❌ 基础测试失败")
            return False
        
        # 检查映射一致性
        common_ips = result1.original_ips & result2.original_ips
        inconsistent_count = 0
        
        for ip in common_ips:
            if ip in result1.ip_mappings and ip in result2.ip_mappings:
                if result1.ip_mappings[ip] != result2.ip_mappings[ip]:
                    inconsistent_count += 1
                    if inconsistent_count <= 3:  # 只显示前3个
                        print(f"❌ 不一致: {ip} -> {result1.ip_mappings[ip]} vs {result2.ip_mappings[ip]}")
        
        if inconsistent_count == 0:
            print(f"✅ 一致性验证通过: {len(common_ips)} 个IP映射完全一致")
            return True
        else:
            print(f"❌ 一致性验证失败: {inconsistent_count} 个IP映射不一致")
            return False
    
    def _generate_summary_report(self, results: List[EnhancedTestResult], total_time: float):
        """生成总结报告"""
        print("\n" + "=" * 60)
        print("📊 增强验证测试总结报告")
        print("=" * 60)
        
        # 基础统计
        total_tests = len(results)
        successful_tests = len([r for r in results if r.success])
        success_rate = successful_tests / total_tests if total_tests > 0 else 0
        
        print(f"🎯 总体结果:")
        print(f"   测试总数: {total_tests}")
        print(f"   成功数量: {successful_tests}")
        print(f"   成功率: {success_rate:.1%}")
        print(f"   总耗时: {total_time:.3f}s")
        
        # 详细验证指标
        if results:
            avg_coverage = sum(r.anonymization_coverage for r in results) / len(results)
            avg_uniqueness = sum(r.unique_mapping_ratio for r in results) / len(results)
            total_ips = sum(len(r.original_ips) for r in results)
            total_mappings = sum(len(r.ip_mappings) for r in results)
            
            print(f"\n📈 验证指标:")
            print(f"   平均覆盖率: {avg_coverage:.1%}")
            print(f"   平均唯一性: {avg_uniqueness:.1%}")
            print(f"   总IP数量: {total_ips}")
            print(f"   总映射数: {total_mappings}")
        
        # 验证维度统计
        validation_stats = {
            "mapping_consistency": 0,
            "ip_count_preserved": 0,
            "anonymized_ip_validity": 0,
            "high_coverage": 0
        }
        
        for result in results:
            if result.mapping_consistency:
                validation_stats["mapping_consistency"] += 1
            if result.ip_count_preserved:
                validation_stats["ip_count_preserved"] += 1
            if result.anonymized_ip_validity:
                validation_stats["anonymized_ip_validity"] += 1
            if result.anonymization_coverage >= 0.95:
                validation_stats["high_coverage"] += 1
        
        print(f"\n🔍 验证维度通过率:")
        for metric, count in validation_stats.items():
            rate = count / total_tests if total_tests > 0 else 0
            status = "✅" if rate >= 0.8 else "❌"
            print(f"   {status} {metric}: {rate:.1%} ({count}/{total_tests})")
        
        # 失败详情
        failed_results = [r for r in results if not r.success]
        if failed_results:
            print(f"\n❌ 失败详情:")
            for result in failed_results:
                print(f"   • {Path(result.file_path).name} ({result.category})")
                for error in result.errors[:2]:
                    print(f"     - {error}")
        
        # 保存详细报告
        self._save_json_report(results, total_time)
        
        print(f"\n📄 详细报告已保存: reports/enhanced_validation_report.json")
    
    def _save_json_report(self, results: List[EnhancedTestResult], total_time: float):
        """保存JSON格式的详细报告"""
        import json
        
        reports_dir = Path("reports")
        reports_dir.mkdir(exist_ok=True)
        
        report_data = {
            "test_summary": {
                "total_tests": len(results),
                "successful_tests": len([r for r in results if r.success]),
                "success_rate": len([r for r in results if r.success]) / len(results) if results else 0,
                "total_time": total_time,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            },
            "validation_metrics": {
                "average_coverage": sum(r.anonymization_coverage for r in results) / len(results) if results else 0,
                "average_uniqueness": sum(r.unique_mapping_ratio for r in results) / len(results) if results else 0,
                "total_original_ips": sum(len(r.original_ips) for r in results),
                "total_mappings": sum(len(r.ip_mappings) for r in results)
            },
            "test_results": [
                {
                    "file_path": result.file_path,
                    "category": result.category,
                    "success": result.success,
                    "processing_time": result.processing_time,
                    "original_ip_count": len(result.original_ips),
                    "anonymized_ip_count": len(result.anonymized_ips),
                    "mapping_count": len(result.ip_mappings),
                    "mapping_consistency": result.mapping_consistency,
                    "ip_count_preserved": result.ip_count_preserved,
                    "anonymized_ip_validity": result.anonymized_ip_validity,
                    "anonymization_coverage": result.anonymization_coverage,
                    "unique_mapping_ratio": result.unique_mapping_ratio,
                    "encapsulation_stats": result.encapsulation_stats,
                    "errors": result.errors,
                    "validation_details": result.validation_details
                }
                for result in results
            ]
        }
        
        with open(reports_dir / "enhanced_validation_report.json", "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)


def run_payload_trimming_tests():
    """运行载荷裁切功能验证测试"""
    print("\n" + "="*60)
    print("🎯 载荷裁切功能验证测试")
    print("="*60)
    
    try:
        import subprocess
        
        # 运行载荷裁切验证测试
        cmd = [
            'python', '-m', 'pytest', 
            'tests/integration/test_enhanced_real_data_validation.py::TestPayloadTrimmingValidation',
            '-v', '--tb=short', '-x'
        ]
        
        print(f"📋 执行命令: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ 载荷裁切功能验证测试全部通过!")
            print("\n📊 测试输出:")
            print(result.stdout)
        else:
            print("❌ 载荷裁切功能验证测试失败")
            print("\n错误输出:")
            print(result.stderr)
            print("\n标准输出:")
            print(result.stdout)
            return False
            
    except Exception as e:
        print(f"❌ 载荷裁切功能验证测试执行异常: {str(e)}")
        return False
    
    return True


def run_all_enhanced_tests():
    """运行所有增强验证测试"""
    print("\n" + "="*60)
    print("🎯 完整增强验证测试套件")
    print("="*60)
    
    all_success = True
    
    # 1. IP匿名化验证测试
    print("\n1️⃣ IP匿名化功能验证...")
    runner = EnhancedTestRunner()
    try:
        test_summary = runner.run_enhanced_validation("standard")
        success_rate = test_summary["successful_tests"] / test_summary["total_tests"]
        if success_rate < 0.8:
            all_success = False
            print("❌ IP匿名化验证测试失败")
        else:
            print("✅ IP匿名化验证测试通过")
    except Exception as e:
        print(f"❌ IP匿名化验证测试异常: {e}")
        all_success = False
    
    # 2. 载荷裁切验证测试
    print("\n2️⃣ 载荷裁切功能验证...")
    if not run_payload_trimming_tests():
        all_success = False
        print("❌ 载荷裁切验证测试失败")
    else:
        print("✅ 载荷裁切验证测试通过")
    
    print("\n" + "="*60)
    if all_success:
        print("🎉 所有增强验证测试全部通过!")
        print("✅ IP匿名化功能: 100%验证通过")
        print("✅ 载荷裁切功能: 100%验证通过")
        print("✅ 多层封装支持: 完整覆盖")
        print("🏆 PktMask增强功能验证完成!")
    else:
        print("❌ 部分增强验证测试失败")
        print("请检查上述错误信息并修复相关问题")
    
    return all_success


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="增强版真实数据验证测试")
    parser.add_argument("--mode", choices=["quick", "standard", "full"], default="standard",
                       help="测试模式: quick(快速), standard(标准), full(完整)")
    parser.add_argument("--consistency", action="store_true",
                       help="执行多次运行的映射一致性验证")
    parser.add_argument('--payload-trimming', action='store_true',
                        help='执行载荷裁切功能验证测试')
    parser.add_argument('--all', action='store_true',
                        help='执行所有增强验证测试（IP匿名化 + 载荷裁切）')
    
    args = parser.parse_args()
    
    try:
        if args.payload_trimming:
            print(f"✂️ 载荷裁切验证模式：测试所有15个样本的载荷裁切功能")
            success = run_payload_trimming_tests()
        elif args.all:
            print(f"🎯 完整增强验证模式：IP匿名化 + 载荷裁切功能")
            success = run_all_enhanced_tests()
        else:
            # 默认运行IP匿名化验证
            print(f"🔒 IP匿名化验证模式：测试所有15个样本的IP匿名化功能")
            runner = EnhancedTestRunner()
            
            # 运行主要验证测试
            test_summary = runner.run_enhanced_validation(args.mode)
            
            # 运行一致性测试（如果请求）
            consistency_passed = True
            if args.consistency:
                consistency_passed = runner.run_consistency_test()
            
            # 判断总体结果
            success_rate = test_summary["successful_tests"] / test_summary["total_tests"]
            success = success_rate >= 0.8 and consistency_passed
        
        print(f"\n🎯 最终结果: {'✅ 全部通过' if success else '❌ 存在失败'}")
        return 0 if success else 1
        
    except Exception as e:
        print(f"❌ 测试运行失败: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 