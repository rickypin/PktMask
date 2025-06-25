#!/usr/bin/env python3
"""
TCP载荷掩码器 Phase 1.4 真实样本验证脚本

验证目标:
1. 基础功能验证: 验证API基本工作
2. TLS样本验证: 使用tests/data/tls-single/tls_sample.pcap
3. 性能基准测试: 验证处理速度

验收标准:
- API能够正常导入和调用
- 能够处理真实的PCAP文件
- 基本性能满足要求
"""

import os
import sys
import time
import tempfile
import logging
from typing import Dict, List, Any
from dataclasses import dataclass

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

print("🚀 启动 TCP载荷掩码器 Phase 1.4 真实样本验证")

try:
    # 导入新的tcp_payload_masker API
    from pktmask.core.tcp_payload_masker import (
        mask_pcap_with_instructions,
        validate_masking_recipe,
        create_masking_recipe_from_dict,
        PacketMaskInstruction,
        MaskingRecipe,
        PacketMaskingResult,
        verify_file_consistency,
        get_api_version
    )
    from pktmask.core.trim.models.mask_spec import MaskAfter, MaskRange, KeepAll
    
    print(f"✅ 成功导入 tcp_payload_masker API")
    print(f"📌 API版本: {get_api_version()}")
    
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    print("请确保已完成 Phase 1.1-1.3 的实现")
    sys.exit(1)

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class ValidationResult:
    """验证结果"""
    test_name: str
    success: bool
    processed_packets: int
    modified_packets: int
    processing_time: float
    throughput_pps: float
    errors: List[str]
    details: Dict[str, Any]

class SimplePhase1Validator:
    """简化的Phase 1.4验证器"""
    
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp(prefix="tcp_masker_phase1_4_")
        self.results: List[ValidationResult] = []
        print(f"📁 临时目录: {self.temp_dir}")
        
    def __del__(self):
        """清理临时文件"""
        try:
            import shutil
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
        except:
            pass
    
    def test_basic_api_functionality(self) -> ValidationResult:
        """测试1: 基础API功能验证"""
        print("\n🧪 测试1: 基础API功能验证")
        
        start_time = time.time()
        errors = []
        
        try:
            # 创建简单的测试数据
            from scapy.all import Ether, IP, TCP, wrpcap
            
            # 创建测试包
            packet = (Ether(dst="00:11:22:33:44:55", src="aa:bb:cc:dd:ee:ff") /
                     IP(src="192.168.1.1", dst="192.168.1.2") /
                     TCP(sport=12345, dport=80) /
                     b"Hello World! This is test data for masking.")
            
            test_file = os.path.join(self.temp_dir, "basic_test.pcap")
            output_file = os.path.join(self.temp_dir, "basic_test_output.pcap")
            
            wrpcap(test_file, [packet])
            print(f"  📝 创建测试文件: {test_file}")
            
            # 创建简单的掩码配方
            # Ethernet(14) + IP(20) + TCP(20) = 54字节偏移到载荷
            payload_offset = 54
            timestamp = str(packet.time)
            
            instruction = PacketMaskInstruction(
                packet_index=0,
                packet_timestamp=timestamp,
                payload_offset=payload_offset,
                mask_spec=MaskAfter(keep_bytes=5)  # 保留前5字节，掩码其余部分
            )
            
            recipe = MaskingRecipe(
                instructions={(0, timestamp): instruction},
                total_packets=1,
                metadata={"test": "basic_functionality"}
            )
            
            print(f"  🔧 创建掩码配方: 1个指令, MaskAfter(5)")
            
            # 验证配方
            validation_errors = validate_masking_recipe(recipe, test_file)
            if validation_errors:
                errors.extend(validation_errors)
                print(f"  ⚠️ 配方验证警告: {validation_errors}")
            
            # 执行掩码处理
            print(f"  ⚙️ 执行掩码处理...")
            result = mask_pcap_with_instructions(
                input_file=test_file,
                output_file=output_file,
                masking_recipe=recipe
            )
            
            processing_time = time.time() - start_time
            throughput = result.processed_packets / processing_time if processing_time > 0 else 0
            
            print(f"  📊 处理结果:")
            print(f"     成功: {result.success}")
            print(f"     处理包数: {result.processed_packets}")
            print(f"     修改包数: {result.modified_packets}")
            print(f"     处理时间: {processing_time:.3f}s")
            print(f"     吞吐量: {throughput:.2f} pps")
            
            if result.errors:
                errors.extend(result.errors)
                print(f"  ❌ 处理错误: {result.errors}")
            
            # 验证输出文件存在
            if not os.path.exists(output_file):
                errors.append("输出文件未创建")
            
            success = result.success and len(errors) == 0 and result.processed_packets > 0
            
            return ValidationResult(
                test_name="basic_api_functionality",
                success=success,
                processed_packets=result.processed_packets,
                modified_packets=result.modified_packets,
                processing_time=processing_time,
                throughput_pps=throughput,
                errors=errors,
                details={
                    "input_file": test_file,
                    "output_file": output_file,
                    "api_result": result.statistics if hasattr(result, 'statistics') else {}
                }
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = f"基础API测试异常: {str(e)}"
            print(f"  💥 {error_msg}")
            logger.exception(error_msg)
            
            return ValidationResult(
                test_name="basic_api_functionality",
                success=False,
                processed_packets=0,
                modified_packets=0,
                processing_time=processing_time,
                throughput_pps=0,
                errors=[error_msg],
                details={"exception": str(e)}
            )
    
    def test_tls_sample_processing(self) -> ValidationResult:
        """测试2: TLS样本处理验证"""
        print("\n🧪 测试2: TLS样本处理验证")
        
        tls_sample_path = "tests/data/tls-single/tls_sample.pcap"
        if not os.path.exists(tls_sample_path):
            print(f"  ⚠️ TLS样本文件不存在: {tls_sample_path}")
            return ValidationResult(
                test_name="tls_sample_processing",
                success=False,
                processed_packets=0,
                modified_packets=0,
                processing_time=0,
                throughput_pps=0,
                errors=[f"TLS样本文件不存在: {tls_sample_path}"],
                details={"missing_file": tls_sample_path}
            )
        
        start_time = time.time()
        errors = []
        
        try:
            from scapy.all import rdpcap
            
            # 加载TLS样本
            packets = rdpcap(tls_sample_path)
            total_packets = len(packets)
            print(f"  📊 TLS样本包含 {total_packets} 个数据包")
            
            output_file = os.path.join(self.temp_dir, "tls_sample_output.pcap")
            
            # 创建保守的掩码配方 - 只对前几个包进行轻度掩码
            instructions = {}
            process_count = min(3, total_packets)  # 只处理前3个包
            
            for i in range(process_count):
                timestamp = str(packets[i].time)
                # 使用保守的载荷偏移量
                payload_offset = 66  # Eth(14) + IP(20) + TCP(20) + 可能的选项(12)
                
                instructions[(i, timestamp)] = PacketMaskInstruction(
                    packet_index=i,
                    packet_timestamp=timestamp,
                    payload_offset=payload_offset,
                    mask_spec=MaskAfter(keep_bytes=10)  # 保守的掩码策略
                )
            
            recipe = MaskingRecipe(
                instructions=instructions,
                total_packets=total_packets,
                metadata={"test": "tls_sample", "description": f"处理前{process_count}个包"}
            )
            
            print(f"  🔧 创建掩码配方: {len(instructions)}个指令")
            
            # 验证配方（允许警告）
            validation_errors = validate_masking_recipe(recipe, tls_sample_path)
            if validation_errors:
                print(f"  ⚠️ 配方验证警告: {validation_errors[:3]}...")  # 只显示前3个
            
            # 执行掩码处理
            print(f"  ⚙️ 执行TLS样本掩码处理...")
            result = mask_pcap_with_instructions(
                input_file=tls_sample_path,
                output_file=output_file,
                masking_recipe=recipe
            )
            
            processing_time = time.time() - start_time
            throughput = result.processed_packets / processing_time if processing_time > 0 else 0
            
            print(f"  📊 TLS处理结果:")
            print(f"     成功: {result.success}")
            print(f"     处理包数: {result.processed_packets}")
            print(f"     修改包数: {result.modified_packets}")
            print(f"     处理时间: {processing_time:.3f}s")
            print(f"     吞吐量: {throughput:.2f} pps")
            
            if result.errors:
                errors.extend(result.errors)
                print(f"  ⚠️ 处理警告: {result.errors[:2]}...")  # 只显示前2个
            
            # 宽松的成功标准 - 只要能处理大部分包就算成功
            success = (result.success and 
                      result.processed_packets >= total_packets * 0.8 and  # 处理80%以上的包
                      os.path.exists(output_file))
            
            return ValidationResult(
                test_name="tls_sample_processing",
                success=success,
                processed_packets=result.processed_packets,
                modified_packets=result.modified_packets,
                processing_time=processing_time,
                throughput_pps=throughput,
                errors=errors,
                details={
                    "input_file": tls_sample_path,
                    "output_file": output_file,
                    "total_packets": total_packets,
                    "instructions_count": len(instructions),
                    "api_result": result.statistics if hasattr(result, 'statistics') else {}
                }
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = f"TLS样本测试异常: {str(e)}"
            print(f"  💥 {error_msg}")
            logger.exception(error_msg)
            
            return ValidationResult(
                test_name="tls_sample_processing",
                success=False,
                processed_packets=0,
                modified_packets=0,
                processing_time=processing_time,
                throughput_pps=0,
                errors=[error_msg],
                details={"exception": str(e)}
            )
    
    def test_performance_benchmark(self) -> ValidationResult:
        """测试3: 性能基准测试"""
        print("\n🧪 测试3: 性能基准测试")
        
        start_time = time.time()
        errors = []
        
        try:
            from scapy.all import Ether, IP, TCP, wrpcap
            
            # 创建50个测试包（适中的数量，既能测试性能又不会太慢）
            packets = []
            for i in range(50):
                packet = (
                    Ether(dst="00:11:22:33:44:55", src="aa:bb:cc:dd:ee:ff")
                    / IP(src=f"192.168.1.{i % 254 + 1}", dst="192.168.1.100")
                    / TCP(sport=12345 + i, dport=80)
                    / (f"Performance test packet {i:02d} - " * 5)
                )  # 约100字节载荷

                # 显式设置时间戳，确保 packet.time 可用
                packet.time = time.time()

                packets.append(packet)
            
            test_file = os.path.join(self.temp_dir, "performance_test.pcap")
            output_file = os.path.join(self.temp_dir, "performance_output.pcap")
            
            wrpcap(test_file, packets)
            print(f"  📝 创建性能测试文件: {len(packets)}个包")
            
            # 创建掩码配方 - 写入文件后重新读取一次，使用PCAP中的实际时间戳，避免时间精度差异
            from scapy.all import PcapReader

            instructions = {}
            payload_offset = 54  # Eth + IP + TCP

            with PcapReader(test_file) as reader:
                for i, pkt in enumerate(reader):
                    ts_str = str(pkt.time)
                    instructions[(i, ts_str)] = PacketMaskInstruction(
                        packet_index=i,
                        packet_timestamp=ts_str,
                        payload_offset=payload_offset,
                        mask_spec=MaskAfter(keep_bytes=10),
                    )
            
            recipe = MaskingRecipe(
                instructions=instructions,
                total_packets=len(packets),
                metadata={"test": "performance", "description": f"{len(packets)}包性能测试"}
            )
            
            print(f"  🔧 创建掩码配方: {len(instructions)}个指令")
            
            # 执行掩码处理
            print(f"  ⚙️ 执行性能基准测试...")
            processing_start = time.time()
            
            result = mask_pcap_with_instructions(
                input_file=test_file,
                output_file=output_file,
                masking_recipe=recipe
            )
            
            processing_time = time.time() - processing_start
            total_time = time.time() - start_time
            throughput = result.processed_packets / processing_time if processing_time > 0 else 0
            
            print(f"  📊 性能测试结果:")
            print(f"     成功: {result.success}")
            print(f"     处理包数: {result.processed_packets}")
            print(f"     修改包数: {result.modified_packets}")
            print(f"     纯处理时间: {processing_time:.3f}s")
            print(f"     总耗时: {total_time:.3f}s")
            print(f"     处理吞吐量: {throughput:.2f} pps")
            
            if result.errors:
                errors.extend(result.errors)
                print(f"  ⚠️ 处理错误: {result.errors}")
            
            # 性能目标：至少100 pps（比较宽松的要求）
            target_throughput = 100
            success = (result.success and 
                      result.processed_packets == len(packets) and
                      result.modified_packets == len(packets) and
                      throughput >= target_throughput and
                      os.path.exists(output_file))
            
            if not success and throughput < target_throughput:
                errors.append(f"性能不达标: {throughput:.2f} pps < {target_throughput} pps")
            
            return ValidationResult(
                test_name="performance_benchmark",
                success=success,
                processed_packets=result.processed_packets,
                modified_packets=result.modified_packets,
                processing_time=processing_time,
                throughput_pps=throughput,
                errors=errors,
                details={
                    "packets_count": len(packets),
                    "target_throughput": target_throughput,
                    "actual_throughput": throughput,
                    "total_time": total_time,
                    "api_result": result.statistics if hasattr(result, 'statistics') else {}
                }
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = f"性能测试异常: {str(e)}"
            print(f"  💥 {error_msg}")
            logger.exception(error_msg)
            
            return ValidationResult(
                test_name="performance_benchmark",
                success=False,
                processed_packets=0,
                modified_packets=0,
                processing_time=processing_time,
                throughput_pps=0,
                errors=[error_msg],
                details={"exception": str(e)}
            )
    
    def run_all_tests(self) -> List[ValidationResult]:
        """运行所有验证测试"""
        print("🚀 开始 Phase 1.4 真实样本验证")
        print("=" * 60)
        
        all_results = []
        
        # 测试1: 基础API功能
        result1 = self.test_basic_api_functionality()
        all_results.append(result1)
        
        # 测试2: TLS样本处理
        result2 = self.test_tls_sample_processing()
        all_results.append(result2)
        
        # 测试3: 性能基准测试
        result3 = self.test_performance_benchmark()
        all_results.append(result3)
        
        self.results = all_results
        return all_results
    
    def generate_summary_report(self) -> str:
        """生成验证报告摘要"""
        if not self.results:
            return "❌ 没有可用的测试结果"
        
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r.success)
        pass_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        # 计算性能指标
        valid_throughputs = [r.throughput_pps for r in self.results if r.throughput_pps > 0]
        avg_throughput = sum(valid_throughputs) / len(valid_throughputs) if valid_throughputs else 0
        
        report_lines = [
            "",
            "=" * 60,
            "🏆 Phase 1.4 验证结果摘要",
            "=" * 60,
            "",
            f"📊 总体结果:",
            f"   测试总数: {total_tests}",
            f"   通过测试: {passed_tests}",
            f"   失败测试: {total_tests - passed_tests}",
            f"   通过率: {pass_rate:.1f}%",
            "",
            f"⚡ 性能指标:",
            f"   平均吞吐量: {avg_throughput:.2f} pps",
            "",
            f"🔍 测试详情:",
        ]
        
        for i, result in enumerate(self.results, 1):
            status = "✅ PASS" if result.success else "❌ FAIL"
            report_lines.extend([
                f"   {i}. {result.test_name} - {status}",
                f"      处理包数: {result.processed_packets}",
                f"      修改包数: {result.modified_packets}",
                f"      处理时间: {result.processing_time:.3f}s",
                f"      吞吐量: {result.throughput_pps:.2f} pps",
            ])
            
            if result.errors:
                report_lines.append(f"      错误: {result.errors[0]}")  # 只显示第一个错误
        
        # 验收标准检查
        report_lines.extend([
            "",
            "✅ Phase 1.4 验收标准检查:",
            f"   1. API基础功能正常: {'✅ 是' if self._check_basic_functionality() else '❌ 否'}",
            f"   2. 能处理真实PCAP: {'✅ 是' if self._check_real_pcap_processing() else '❌ 否'}",
            f"   3. 性能达到要求: {'✅ 是' if avg_throughput >= 100 else '❌ 否'}",
            "",
        ])
        
        if pass_rate >= 66 and avg_throughput >= 100:  # 2/3通过率 + 基本性能
            report_lines.append("🎉 Phase 1.4 验证基本成功! API可以进入Phase 2集成阶段")
        else:
            report_lines.append("⚠️  Phase 1.4 验证存在问题，建议修复后重新验证")
        
        return "\n".join(report_lines)
    
    def _check_basic_functionality(self) -> bool:
        """检查基础功能是否正常"""
        basic_results = [r for r in self.results if r.test_name == "basic_api_functionality"]
        return len(basic_results) > 0 and basic_results[0].success
    
    def _check_real_pcap_processing(self) -> bool:
        """检查真实PCAP处理能力"""
        tls_results = [r for r in self.results if r.test_name == "tls_sample_processing"]
        return len(tls_results) > 0 and tls_results[0].success

def main():
    """主函数"""
    print("🏗️  TCP载荷掩码器 Phase 1.4 真实样本验证")
    print("📝 验证目标: 确认API基础功能、真实样本处理能力、基本性能要求")
    
    # 创建验证器并运行测试
    validator = SimplePhase1Validator()
    
    try:
        results = validator.run_all_tests()
        
        # 生成并显示报告
        report = validator.generate_summary_report()
        print(report)
        
        # 保存报告
        report_file = "tcp_payload_masker_phase1_4_validation_report.md"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(f"# TCP载荷掩码器 Phase 1.4 验证报告\n\n")
            f.write(f"生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(report)
        
        print(f"\n📄 详细报告已保存到: {report_file}")
        
        # 确定退出状态
        passed_tests = sum(1 for r in results if r.success)
        total_tests = len(results)
        
        if passed_tests >= total_tests * 0.66:  # 66%通过率
            print(f"\n🎯 Phase 1.4 验证基本成功! ({passed_tests}/{total_tests} 测试通过)")
            return 0
        else:
            print(f"\n⚠️  Phase 1.4 验证需要改进 ({passed_tests}/{total_tests} 测试通过)")
            return 1
            
    except Exception as e:
        print(f"\n💥 验证过程异常: {e}")
        logger.exception("验证过程异常")
        return 1

if __name__ == "__main__":
    exit_code = main()
    print(f"\n🏁 验证完成，退出码: {exit_code}")
    sys.exit(exit_code) 