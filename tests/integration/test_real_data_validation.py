#!/usr/bin/env python3
"""
PktMask 真实样本数据完整验证测试
覆盖 tests/data/samples/ 下的所有目录
"""
import pytest
import time
import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from scapy.all import rdpcap, Packet

# 导入PktMask核心组件
from src.pktmask.core.encapsulation.detector import EncapsulationDetector
from src.pktmask.core.encapsulation.parser import ProtocolStackParser
from src.pktmask.core.encapsulation.adapter import ProcessingAdapter
from src.pktmask.core.strategy import HierarchicalAnonymizationStrategy
from src.pktmask.core.processors import EnhancedTrimmer


@dataclass
class SampleFileInfo:
    """样本文件信息"""
    path: Path
    category: str
    expected_encapsulation: str
    description: str
    min_packets: int = 1
    max_test_packets: int = 100  # 限制测试包数量，避免过慢


@dataclass
class TestResult:
    """测试结果数据"""
    file_path: str
    category: str
    success: bool
    total_packets: int
    tested_packets: int
    encapsulation_stats: Dict[str, int]
    ip_count: int
    tcp_sessions: int
    processing_time: float
    errors: List[str]
    validation_details: Dict


class RealDataValidator:
    """真实数据验证器"""
    
    def __init__(self):
        self.detector = EncapsulationDetector()
        self.parser = ProtocolStackParser()
        self.adapter = ProcessingAdapter()
        self.ip_strategy = HierarchicalAnonymizationStrategy()
        self.trimming = IntelligentTrimmingStep()
        self.logger = logging.getLogger(__name__)
        
    def get_sample_file_map(self) -> Dict[str, List[SampleFileInfo]]:
        """获取所有样本文件的分类映射"""
        samples_dir = Path("tests/data/samples")
        
        # 定义所有目录的预期封装类型和描述
        directory_config = {
            "TLS": {
                "category": "plain_ip",
                "encapsulation": "plain",
                "description": "基础TCP/IP + TLS流量",
                "pattern": "*.pcap"
            },
            "TLS70": {
                "category": "plain_ip_tls70",
                "encapsulation": "plain",
                "description": "TLS 7.0版本流量",
                "pattern": "*.pcap"
            },
            "singlevlan": {
                "category": "single_vlan",
                "encapsulation": "vlan",
                "description": "单层VLAN封装(802.1Q)",
                "pattern": "*.pcap"
            },
            "doublevlan": {
                "category": "double_vlan",
                "encapsulation": "double_vlan",
                "description": "双层VLAN封装(802.1ad QinQ)",
                "pattern": "*.pcap"
            },
            "doublevlan_tls": {
                "category": "double_vlan_tls",
                "encapsulation": "double_vlan",
                "description": "双层VLAN + TLS组合",
                "pattern": "*.pcap"
            },
            "mpls": {
                "category": "mpls",
                "encapsulation": "mpls",
                "description": "MPLS标签交换",
                "pattern": "*.pcap"
            },
            "gre": {
                "category": "gre_tunnel",
                "encapsulation": "gre",
                "description": "GRE隧道封装",
                "pattern": "*.pcap"
            },
            "vxlan": {
                "category": "vxlan",
                "encapsulation": "vxlan",
                "description": "VXLAN虚拟化网络",
                "pattern": "*.pcap"
            },
            "vxlan4787": {
                "category": "vxlan_custom",
                "encapsulation": "vxlan",
                "description": "VXLAN自定义端口4787",
                "pattern": "*.pcap"
            },
            "vxlan_vlan": {
                "category": "vxlan_vlan_composite",
                "encapsulation": "composite",
                "description": "VXLAN + VLAN复合封装",
                "pattern": "*.pcap"
            },
            "vlan_gre": {
                "category": "vlan_gre_composite",
                "encapsulation": "composite",
                "description": "VLAN + GRE复合封装",
                "pattern": "*.pcap"
            },
            "IPTCP-200ips": {
                "category": "large_ip_set",
                "encapsulation": "plain",
                "description": "大IP地址集测试数据",
                "pattern": "*.pcap*"
            },
            "IPTCP-TC-001-1-20160407": {
                "category": "test_case_001",
                "encapsulation": "mixed",
                "description": "测试用例001系列",
                "pattern": "*.pcap*"
            },
            "IPTCP-TC-002-5-20220215": {
                "category": "test_case_002_5",
                "encapsulation": "mixed",
                "description": "测试用例002-5系列",
                "pattern": "*.pcap*"
            },
            "IPTCP-TC-002-8-20210817": {
                "category": "test_case_002_8",
                "encapsulation": "mixed",
                "description": "测试用例002-8系列",
                "pattern": "*.pcap*"
            },
            "empty": {
                "category": "empty_directory",
                "encapsulation": "none",
                "description": "空目录（跳过测试）",
                "pattern": "*.pcap*"
            }
        }
        
        file_map = {}
        
        for dir_name, config in directory_config.items():
            dir_path = samples_dir / dir_name
            if not dir_path.exists():
                self.logger.warning(f"目录不存在: {dir_path}")
                continue
                
            # 跳过空目录
            if config["category"] == "empty_directory":
                continue
                
            files = list(dir_path.glob(config["pattern"]))
            # 过滤掉.DS_Store等系统文件
            files = [f for f in files if not f.name.startswith('.') and f.suffix in ['.pcap', '.pcapng']]
            
            if not files:
                self.logger.warning(f"目录 {dir_name} 中没有找到pcap文件")
                continue
                
            category = config["category"]
            if category not in file_map:
                file_map[category] = []
                
            for file_path in files:
                file_info = SampleFileInfo(
                    path=file_path,
                    category=category,
                    expected_encapsulation=config["encapsulation"],
                    description=config["description"]
                )
                file_map[category].append(file_info)
                
        return file_map
    
    def validate_sample_file(self, sample_info: SampleFileInfo) -> TestResult:
        """验证单个样本文件"""
        start_time = time.time()
        errors = []
        encapsulation_stats = {}
        ip_addresses = set()
        tcp_sessions = 0
        
        try:
            # 读取pcap文件
            packets = rdpcap(str(sample_info.path))
            total_packets = len(packets)
            
            if total_packets == 0:
                errors.append("文件中没有数据包")
                return TestResult(
                    file_path=str(sample_info.path),
                    category=sample_info.category,
                    success=False,
                    total_packets=0,
                    tested_packets=0,
                    encapsulation_stats={},
                    ip_count=0,
                    tcp_sessions=0,
                    processing_time=time.time() - start_time,
                    errors=errors,
                    validation_details={}
                )
            
            # 限制测试包数量
            test_packets = packets[:sample_info.max_test_packets]
            tested_count = len(test_packets)
            
            # 处理每个数据包
            for i, packet in enumerate(test_packets):
                try:
                    # 1. 封装类型检测
                    encap_type = self.detector.detect_encapsulation_type(packet)
                    encap_name = encap_type.value
                    encapsulation_stats[encap_name] = encapsulation_stats.get(encap_name, 0) + 1
                    
                    # 2. 协议栈解析
                    layer_info = self.parser.parse_packet_layers(packet)
                    
                    # 3. IP地址提取
                    adapter_result = self.adapter.analyze_packet_for_ip_processing(packet)
                    if 'ip_layers' in adapter_result:
                        for ip_layer in adapter_result['ip_layers']:
                            if hasattr(ip_layer, 'src_ip'):
                                ip_addresses.add(str(ip_layer.src_ip))
                            if hasattr(ip_layer, 'dst_ip'):
                                ip_addresses.add(str(ip_layer.dst_ip))
                    
                    # 4. TCP会话计数（简化版）
                    if packet.haslayer('TCP'):
                        tcp_sessions += 1
                        
                except Exception as e:
                    errors.append(f"包 {i+1} 处理错误: {str(e)}")
                    continue
            
            # 验证结果
            validation_details = {
                "expected_encapsulation": sample_info.expected_encapsulation,
                "detected_encapsulations": encapsulation_stats,
                "layer_analysis_success": len(errors) < tested_count * 0.1,  # 90%成功率
                "ip_extraction_success": len(ip_addresses) > 0,
                "file_size_mb": sample_info.path.stat().st_size / (1024 * 1024)
            }
            
            # 判断测试是否成功
            success = (
                len(errors) < tested_count * 0.2 and  # 错误率小于20%
                len(encapsulation_stats) > 0 and     # 至少检测到一种封装
                len(ip_addresses) > 0                # 至少提取到一个IP
            )
            
            processing_time = time.time() - start_time
            
            return TestResult(
                file_path=str(sample_info.path),
                category=sample_info.category,
                success=success,
                total_packets=total_packets,
                tested_packets=tested_count,
                encapsulation_stats=encapsulation_stats,
                ip_count=len(ip_addresses),
                tcp_sessions=tcp_sessions,
                processing_time=processing_time,
                errors=errors[:10],  # 只保留前10个错误
                validation_details=validation_details
            )
            
        except Exception as e:
            errors.append(f"文件读取失败: {str(e)}")
            return TestResult(
                file_path=str(sample_info.path),
                category=sample_info.category,
                success=False,
                total_packets=0,
                tested_packets=0,
                encapsulation_stats={},
                ip_count=0,
                tcp_sessions=0,
                processing_time=time.time() - start_time,
                errors=errors,
                validation_details={}
            )


@pytest.mark.integration
@pytest.mark.real_data
@pytest.mark.slow
class TestRealDataValidation:
    """真实数据验证测试类"""
    
    @pytest.fixture(scope="class")
    def validator(self):
        """创建验证器实例"""
        return RealDataValidator()
    
    @pytest.fixture(scope="class")
    def sample_files(self, validator):
        """获取所有样本文件"""
        return validator.get_sample_file_map()
    
    def test_all_sample_directories_covered(self, sample_files):
        """测试确保所有目录都被覆盖"""
        samples_dir = Path("tests/data/samples")
        all_dirs = [d for d in samples_dir.iterdir() if d.is_dir() and not d.name.startswith('.')]
        
        covered_dirs = set()
        for category, files in sample_files.items():
            for file_info in files:
                covered_dirs.add(file_info.path.parent.name)
        
        # 排除empty目录
        expected_dirs = {d.name for d in all_dirs if d.name != "empty"}
        
        missing_dirs = expected_dirs - covered_dirs
        assert not missing_dirs, f"以下目录没有测试覆盖: {missing_dirs}"
        
        print(f"✅ 目录覆盖检查通过: {len(covered_dirs)}/{len(expected_dirs)} 个目录")
    
    @pytest.mark.parametrize("category", [
        "plain_ip", "plain_ip_tls70", "single_vlan", "double_vlan", 
        "double_vlan_tls", "mpls", "gre_tunnel", "vxlan", "vxlan_custom",
        "vxlan_vlan_composite", "vlan_gre_composite", "large_ip_set",
        "test_case_001", "test_case_002_5", "test_case_002_8"
    ])
    def test_sample_category_validation(self, validator, sample_files, category):
        """测试特定类别的样本文件"""
        if category not in sample_files:
            pytest.skip(f"类别 {category} 没有可用的样本文件")
        
        category_files = sample_files[category]
        results = []
        
        for sample_info in category_files:
            print(f"\n🧪 测试文件: {sample_info.path.name} ({category})")
            result = validator.validate_sample_file(sample_info)
            results.append(result)
            
            # 打印结果摘要
            if result.success:
                print(f"   ✅ 成功 - {result.tested_packets}/{result.total_packets} 包")
                print(f"   📦 封装类型: {result.encapsulation_stats}")
                print(f"   🌐 IP地址: {result.ip_count} 个")
                print(f"   ⏱️  处理时间: {result.processing_time:.3f}s")
            else:
                print(f"   ❌ 失败 - 错误: {len(result.errors)}")
                for error in result.errors[:3]:  # 只显示前3个错误
                    print(f"      • {error}")
        
        # 验证至少有一个文件测试成功
        successful_files = [r for r in results if r.success]
        total_files = len(results)
        success_rate = len(successful_files) / total_files if total_files > 0 else 0
        
        assert success_rate >= 0.8, f"类别 {category} 成功率太低: {success_rate:.1%} ({len(successful_files)}/{total_files})"
        
        print(f"\n📊 类别 {category} 测试完成:")
        print(f"   成功率: {success_rate:.1%} ({len(successful_files)}/{total_files})")
    
    def test_comprehensive_real_data_validation(self, validator, sample_files):
        """综合真实数据验证测试"""
        all_results = []
        category_stats = {}
        
        print("\n🚀 开始综合真实数据验证")
        print("=" * 60)
        
        for category, files in sample_files.items():
            print(f"\n📁 处理类别: {category} ({len(files)} 个文件)")
            category_results = []
            
            for sample_info in files:
                result = validator.validate_sample_file(sample_info)
                category_results.append(result)
                all_results.append(result)
            
            # 计算类别统计
            successful = [r for r in category_results if r.success]
            category_stats[category] = {
                "total_files": len(files),
                "successful_files": len(successful),
                "success_rate": len(successful) / len(files) if files else 0,
                "total_packets": sum(r.total_packets for r in category_results),
                "avg_processing_time": sum(r.processing_time for r in category_results) / len(category_results) if category_results else 0
            }
            
            print(f"   ✅ 成功: {len(successful)}/{len(files)} 文件")
        
        # 生成详细报告
        self._generate_validation_report(all_results, category_stats)
        
        # 整体验证
        total_files = len(all_results)
        successful_files = len([r for r in all_results if r.success])
        overall_success_rate = successful_files / total_files if total_files > 0 else 0
        
        print(f"\n🎯 综合验证结果:")
        print(f"   总文件数: {total_files}")
        print(f"   成功文件数: {successful_files}")
        print(f"   整体成功率: {overall_success_rate:.1%}")
        
        # 要求整体成功率至少90%
        assert overall_success_rate >= 0.9, f"整体成功率太低: {overall_success_rate:.1%}"
        assert total_files >= 8, f"测试文件数量太少: {total_files}"
    
    def _generate_validation_report(self, results: List[TestResult], category_stats: Dict):
        """生成验证报告"""
        reports_dir = Path("reports")
        reports_dir.mkdir(exist_ok=True)
        
        report_data = {
            "test_summary": {
                "total_files": len(results),
                "successful_files": len([r for r in results if r.success]),
                "success_rate": len([r for r in results if r.success]) / len(results) if results else 0,
                "test_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "categories_tested": len(category_stats)
            },
            "category_stats": category_stats,
            "detailed_results": [
                {
                    "file": result.file_path,
                    "category": result.category,
                    "success": result.success,
                    "total_packets": result.total_packets,
                    "tested_packets": result.tested_packets,
                    "encapsulation_stats": result.encapsulation_stats,
                    "ip_count": result.ip_count,
                    "tcp_sessions": result.tcp_sessions,
                    "processing_time": result.processing_time,
                    "validation_details": result.validation_details,
                    "errors": result.errors
                }
                for result in results
            ]
        }
        
        # 保存JSON报告
        report_file = reports_dir / "real_data_validation_report.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n📄 详细报告已保存: {report_file}")


# 独立运行支持
if __name__ == "__main__":
    import sys
    
    # 设置日志
    logging.basicConfig(level=logging.INFO)
    
    validator = RealDataValidator()
    sample_files = validator.get_sample_file_map()
    
    print("🔍 发现的样本文件:")
    for category, files in sample_files.items():
        print(f"  {category}: {len(files)} 个文件")
    
    # 运行快速验证
    print("\n🚀 运行快速验证...")
    for category, files in sample_files.items():
        if files:
            sample = files[0]  # 测试每个类别的第一个文件
            result = validator.validate_sample_file(sample)
            status = "✅" if result.success else "❌"
            print(f"  {status} {category}: {sample.path.name}") 