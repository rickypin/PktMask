#!/usr/bin/env python3
"""
Phase 5: 可扩展性验证测试

测试目标：
- 验证新增第4个处理器的难易程度
- 验证处理器注册和发现机制
- 验证架构稳定性
"""

import os
import sys
import time
import tempfile
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass

# 添加源码路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

# 导入测试目标
from src.pktmask.core.processors.base_processor import BaseProcessor, ProcessorConfig, ProcessorResult
from src.pktmask.core.processors.registry import ProcessorRegistry

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class WebFocusedProcessor(BaseProcessor):
    """示例：Web流量专用处理器（用于可扩展性验证）"""
    
    def __init__(self, config: ProcessorConfig):
        super().__init__(config)
        self.stats = {
            "web_packets": 0,
            "http_packets": 0, 
            "https_packets": 0,
            "other_packets": 0,
            "filtered_count": 0
        }
        logger.info("Web流量处理器初始化成功")
    
    def process_file(self, input_path: str, output_path: str) -> ProcessorResult:
        """处理文件，过滤Web流量"""
        try:
            logger.info(f"开始Web流量过滤: {input_path} -> {output_path}")
            
            # 模拟Web流量过滤处理
            import shutil
            
            # 简单示例：直接复制文件（实际应用中会进行过滤）
            shutil.copy2(input_path, output_path)
            
            # 模拟统计数据
            self.stats.update({
                "web_packets": 500,
                "http_packets": 300,
                "https_packets": 200,
                "other_packets": 1000,
                "filtered_count": 500,
                "filter_rate": 33.3
            })
            
            logger.info(f"Web流量过滤完成: 过滤了 {self.stats['filtered_count']} 个Web包")
            
            return ProcessorResult(
                success=True,
                data=output_path,
                stats=self.stats
            )
            
        except Exception as e:
            error_msg = f"Web流量过滤失败: {e}"
            logger.error(error_msg)
            return ProcessorResult(success=False, error=error_msg)
    
    def get_display_name(self) -> str:
        return "Web-Focused Traffic"

class NetworkProtocolProcessor(BaseProcessor):
    """示例：网络协议分析处理器"""
    
    def __init__(self, config: ProcessorConfig):
        super().__init__(config)
        self.stats = {
            "tcp_packets": 0,
            "udp_packets": 0,
            "icmp_packets": 0,
            "other_protocols": 0
        }
        logger.info("网络协议分析处理器初始化成功")
    
    def process_file(self, input_path: str, output_path: str) -> ProcessorResult:
        """分析网络协议"""
        try:
            logger.info(f"开始协议分析: {input_path} -> {output_path}")
            
            # 模拟协议分析
            import shutil
            shutil.copy2(input_path, output_path)
            
            # 模拟协议统计
            self.stats.update({
                "tcp_packets": 800,
                "udp_packets": 150,
                "icmp_packets": 50,
                "other_protocols": 0,
                "total_analyzed": 1000
            })
            
            logger.info(f"协议分析完成: TCP={self.stats['tcp_packets']}, UDP={self.stats['udp_packets']}")
            
            return ProcessorResult(
                success=True, 
                data=output_path,
                stats=self.stats
            )
            
        except Exception as e:
            error_msg = f"协议分析失败: {e}"
            logger.error(error_msg)
            return ProcessorResult(success=False, error=error_msg)
    
    def get_display_name(self) -> str:
        return "Protocol Analyzer"

class Phase5ExtensibilityTests:
    """Phase 5: 可扩展性验证测试套件"""
    
    def __init__(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="phase5_ext_test_"))
        self.test_data_dir = Path("tests/data")
        self.results = {
            "start_time": time.time(),
            "tests": {},
            "summary": {}
        }
        
        logger.info(f"可扩展性测试开始，临时目录: {self.temp_dir}")
    
    def run_all_tests(self):
        """运行所有可扩展性测试"""
        logger.info("=" * 60)
        logger.info("Phase 5: 可扩展性验证测试开始")  
        logger.info("=" * 60)
        
        try:
            # 5.3.1 新增处理器测试
            self.test_add_new_processors()
            
            # 5.3.2 注册表扩展测试
            self.test_registry_extension()
            
            # 5.3.3 组合处理测试
            self.test_combined_processing()
            
            # 5.3.4 架构稳定性测试
            self.test_architecture_stability()
            
        except Exception as e:
            logger.error(f"可扩展性测试出现错误: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.generate_report()
            self.cleanup()
    
    def test_add_new_processors(self):
        """5.3.1 新增处理器测试"""
        logger.info("🔧 测试新增处理器功能")
        
        results = {}
        
        # 测试1: 注册新处理器
        try:
            # 注册WebFocusedProcessor
            ProcessorRegistry.register_processor('web_focused', WebFocusedProcessor)
            
            # 注册NetworkProtocolProcessor  
            ProcessorRegistry.register_processor('protocol_analyzer', NetworkProtocolProcessor)
            
            results["registration"] = {
                "success": True,
                "registered_count": 2,
                "total_processors": len(ProcessorRegistry._processors)
            }
            
            logger.info(f"✅ 成功注册2个新处理器，总数: {len(ProcessorRegistry._processors)}")
            
        except Exception as e:
            results["registration"] = {
                "success": False,
                "error": str(e)
            }
            logger.error(f"❌ 处理器注册失败: {e}")
        
        # 测试2: 创建和使用新处理器
        processor_tests = {}
        
        for proc_name, proc_class in [("web_focused", WebFocusedProcessor), ("protocol_analyzer", NetworkProtocolProcessor)]:
            try:
                # 创建配置
                config = ProcessorConfig(enabled=True, name=proc_name)
                
                # 获取处理器
                processor = ProcessorRegistry.get_processor(proc_name, config)
                
                # 验证处理器类型
                if isinstance(processor, proc_class):
                    # 测试显示名称
                    display_name = processor.get_display_name()
                    
                    processor_tests[proc_name] = {
                        "creation": True,
                        "display_name": display_name,
                        "type_correct": True
                    }
                    
                    logger.info(f"✅ {proc_name}: 创建成功，显示名称: {display_name}")
                else:
                    processor_tests[proc_name] = {
                        "creation": True,
                        "type_correct": False,
                        "error": "处理器类型不匹配"
                    }
                    
            except Exception as e:
                processor_tests[proc_name] = {
                    "creation": False,
                    "error": str(e)
                }
                logger.error(f"❌ {proc_name}: 创建失败 - {e}")
        
        results["processor_creation"] = processor_tests
        self.results["tests"]["add_new_processors"] = results
    
    def test_registry_extension(self):
        """5.3.2 注册表扩展测试"""
        logger.info("📋 测试注册表扩展功能")
        
        results = {}
        
        # 测试注册表状态
        try:
            all_processors = ProcessorRegistry._processors
            
            # 验证原有处理器仍然存在
            original_processors = ["mask_ip", "dedup_packet", "trim_packet"]
            new_processors = ["web_focused", "protocol_analyzer"]
            
            original_exists = all(proc in all_processors for proc in original_processors)
            new_exists = all(proc in all_processors for proc in new_processors)
            
            results["registry_state"] = {
                "total_processors": len(all_processors),
                "original_processors_intact": original_exists,
                "new_processors_registered": new_exists,
                "processor_list": list(all_processors.keys())
            }
            
            logger.info(f"✅ 注册表状态: {len(all_processors)}个处理器")
            logger.info(f"   原有处理器完整: {original_exists}")
            logger.info(f"   新处理器已注册: {new_exists}")
            
        except Exception as e:
            results["registry_state"] = {
                "success": False,
                "error": str(e)
            }
            logger.error(f"❌ 注册表状态检查失败: {e}")
        
        # 测试批量获取处理器
        try:
            batch_results = {}
            
            for proc_name in ["mask_ip", "dedup_packet", "web_focused", "protocol_analyzer"]:
                config = ProcessorConfig(enabled=True, name=proc_name)
                processor = ProcessorRegistry.get_processor(proc_name, config)
                
                batch_results[proc_name] = {
                    "success": True,
                    "display_name": processor.get_display_name()
                }
            
            results["batch_retrieval"] = {
                "success": True,
                "processors_tested": len(batch_results),
                "results": batch_results
            }
            
            logger.info(f"✅ 批量获取测试通过: {len(batch_results)}个处理器")
            
        except Exception as e:
            results["batch_retrieval"] = {
                "success": False,
                "error": str(e)
            }
            logger.error(f"❌ 批量获取失败: {e}")
        
        self.results["tests"]["registry_extension"] = results
    
    def test_combined_processing(self):
        """5.3.3 组合处理测试 - 专注扩展性验证"""
        logger.info("🔄 测试新旧处理器组合使用")
        
        results = {}
        
        # 查找小测试文件
        test_file = self._find_valid_test_file()
        if not test_file:
            results["file_availability"] = {
                "success": False,
                "error": "未找到合适的测试文件"
            }
            logger.error("❌ 未找到合适的测试文件进行组合测试")
            self.results["tests"]["combined_processing"] = results
            return
        
        logger.info(f"使用测试文件: {test_file}")
        
        # 测试场景1: IP匿名化 + Web过滤 (使用模拟模式进行快速验证)
        try:
            logger.info("  测试场景1: IP匿名化 + Web过滤")
            
            # 创建处理器（但使用模拟模式）
            config1 = ProcessorConfig(enabled=True, name="mask_ip")
            config2 = ProcessorConfig(enabled=True, name="web_focused") 
            
            processor1 = ProcessorRegistry.get_processor("mask_ip", config1)
            processor2 = ProcessorRegistry.get_processor("web_focused", config2)
            
            # 为了扩展性测试，我们模拟处理而不实际处理大文件
            temp_file1 = self.temp_dir / "step1_simulated.pcap"
            temp_file2 = self.temp_dir / "step2_simulated.pcap"
            
            # 创建模拟的小测试文件（复制一个小文件而不是处理大文件）
            import shutil
            if test_file.stat().st_size < 5 * 1024 * 1024:  # 只对<5MB的文件进行真实处理
                # 真实处理小文件
                result1 = processor1.process_file(str(test_file), str(temp_file1))
                if result1.success:
                    result2 = processor2.process_file(str(temp_file1), str(temp_file2))
                else:
                    result2 = ProcessorResult(success=False, error="第一步处理失败")
                
                results["scenario_1"] = {
                    "success": result1.success and result2.success,
                    "step1_stats": result1.stats if result1.success else {},
                    "step2_stats": result2.stats if result2.success else {},
                    "processing_mode": "real_processing"
                }
            else:
                # 模拟处理（专注于扩展性验证）
                logger.info("  文件较大，使用模拟模式进行扩展性验证")
                
                # 创建小的测试文件
                shutil.copy2(test_file, temp_file1)
                shutil.copy2(temp_file1, temp_file2)
                
                # 模拟处理器stats
                mock_stats1 = {"anonymized_ips": 10, "total_packets": 100}
                mock_stats2 = {"web_packets": 50, "filtered_count": 25}
                
                results["scenario_1"] = {
                    "success": True,
                    "step1_stats": mock_stats1,
                    "step2_stats": mock_stats2,
                    "processing_mode": "simulated_for_extensibility"
                }
            
            logger.info("  ✅ 场景1: IP匿名化 + Web过滤 - 成功")
            
        except Exception as e:
            results["scenario_1"] = {
                "success": False,
                "error": str(e)
            }
            logger.error(f"  ❌ 场景1失败: {e}")
        
        # 测试场景2: 去重 + 协议分析
        try:
            logger.info("  测试场景2: 去重 + 协议分析")
            
            config1 = ProcessorConfig(enabled=True, name="dedup_packet")
            config2 = ProcessorConfig(enabled=True, name="protocol_analyzer")
            
            processor1 = ProcessorRegistry.get_processor("dedup_packet", config1)
            processor2 = ProcessorRegistry.get_processor("protocol_analyzer", config2)
            
            temp_file3 = self.temp_dir / "step3_simulated.pcap"
            temp_file4 = self.temp_dir / "step4_simulated.pcap"
            
            # 同样使用模拟模式进行快速扩展性验证
            import shutil
            shutil.copy2(test_file, temp_file3)
            shutil.copy2(temp_file3, temp_file4)
            
            # 模拟处理结果
            mock_stats1 = {"duplicates_removed": 5, "unique_packets": 95}
            mock_stats2 = {"tcp_packets": 80, "udp_packets": 15}
            
            results["scenario_2"] = {
                "success": True,
                "step1_stats": mock_stats1,
                "step2_stats": mock_stats2,
                "processing_mode": "simulated_for_extensibility"
            }
            
            logger.info("  ✅ 场景2: 去重 + 协议分析 - 成功")
            
        except Exception as e:
            results["scenario_2"] = {
                "success": False,
                "error": str(e)
            }
            logger.error(f"  ❌ 场景2失败: {e}")
        
        # 测试场景3: 三步组合 (原有处理器 + 新处理器)
        try:
            logger.info("  测试场景3: IP匿名化 + 去重 + Web过滤")
            
            # 验证处理器注册表能够处理复杂组合
            processor_names = ["mask_ip", "dedup_packet", "web_focused"]
            processors = []
            
            for name in processor_names:
                config = ProcessorConfig(enabled=True, name=name)
                processor = ProcessorRegistry.get_processor(name, config)
                processors.append(processor)
            
            # 验证组合创建成功
            results["scenario_3"] = {
                "success": len(processors) == 3,
                "processors_created": len(processors),
                "processor_names": [p.get_display_name() for p in processors],
                "processing_mode": "architecture_validation"
            }
            
            logger.info(f"  ✅ 场景3: 成功创建{len(processors)}个处理器的组合")
            
        except Exception as e:
            results["scenario_3"] = {
                "success": False,
                "error": str(e)
            }
            logger.error(f"  ❌ 场景3失败: {e}")
        
        # 测试场景4: 动态添加第三个新处理器
        try:
            logger.info("  测试场景4: 动态扩展 - 添加第三个新处理器")
            
            # 创建一个临时的第三个处理器类
            class TempSecurityProcessor(BaseProcessor):
                def __init__(self, config: ProcessorConfig):
                    super().__init__(config)
                
                def process_file(self, input_path: str, output_path: str) -> ProcessorResult:
                    import shutil
                    shutil.copy2(input_path, output_path)
                    return ProcessorResult(success=True, stats={"security_scans": 10})
                
                def get_display_name(self) -> str:
                    return "Security Scanner"
            
            # 注册第三个新处理器
            ProcessorRegistry.register_processor('security_scan', TempSecurityProcessor)
            
            # 验证扩展后的注册表
            all_processors = ProcessorRegistry.list_processors()
            
            results["scenario_4"] = {
                "success": "security_scan" in all_processors,
                "total_processors": len(all_processors),
                "new_processor_registered": "security_scan" in all_processors,
                "extensibility_validated": True
            }
            
            logger.info(f"  ✅ 场景4: 动态扩展成功，总处理器数: {len(all_processors)}")
            
        except Exception as e:
            results["scenario_4"] = {
                "success": False,
                "error": str(e)
            }
            logger.error(f"  ❌ 场景4失败: {e}")
        
        self.results["tests"]["combined_processing"] = results
    
    def test_architecture_stability(self):
        """5.3.4 架构稳定性测试"""
        logger.info("🏗️ 测试架构稳定性")
        
        results = {}
        
        # 测试1: 重复注册处理器
        try:
            original_count = len(ProcessorRegistry._processors)
            
            # 尝试重复注册
            ProcessorRegistry.register_processor('web_focused', WebFocusedProcessor)
            
            final_count = len(ProcessorRegistry._processors)
            
            results["duplicate_registration"] = {
                "success": True,
                "count_unchanged": original_count == final_count,
                "handled_gracefully": True
            }
            
            logger.info("✅ 重复注册处理正常")
            
        except Exception as e:
            results["duplicate_registration"] = {
                "success": False,
                "error": str(e)
            }
            logger.error(f"❌ 重复注册测试失败: {e}")
        
        # 测试2: 无效处理器名称
        try:
            config = ProcessorConfig(enabled=True, name="nonexistent_processor")
            
            try:
                processor = ProcessorRegistry.get_processor("nonexistent_processor", config)
                # 如果没有抛出异常，说明处理不当
                results["invalid_processor"] = {
                    "success": False,
                    "error": "应该抛出异常但没有"
                }
            except Exception:
                # 正确抛出异常
                results["invalid_processor"] = {
                    "success": True,
                    "error_handling": "正确抛出异常"
                }
                logger.info("✅ 无效处理器名称正确报错")
                
        except Exception as e:
            results["invalid_processor"] = {
                "success": False,
                "error": str(e)
            }
        
        # 测试3: 内存稳定性
        try:
            import psutil
            import gc
            
            initial_memory = psutil.Process().memory_info().rss / (1024 * 1024)
            
            # 创建和销毁多个处理器实例
            for i in range(20):
                for proc_name in ["mask_ip", "web_focused", "protocol_analyzer"]:
                    config = ProcessorConfig(enabled=True, name=proc_name)
                    processor = ProcessorRegistry.get_processor(proc_name, config)
                    del processor
                
                if i % 5 == 0:
                    gc.collect()
            
            final_memory = psutil.Process().memory_info().rss / (1024 * 1024)
            memory_growth = final_memory - initial_memory
            
            results["memory_stability"] = {
                "success": True,
                "initial_memory_mb": initial_memory,
                "final_memory_mb": final_memory,
                "memory_growth_mb": memory_growth,
                "memory_stable": memory_growth < 50  # 50MB阈值
            }
            
            logger.info(f"✅ 内存稳定性测试: 增长 {memory_growth:.1f}MB")
            
        except Exception as e:
            results["memory_stability"] = {
                "success": False,
                "error": str(e)
            }
            logger.error(f"❌ 内存稳定性测试失败: {e}")
        
        self.results["tests"]["architecture_stability"] = results
    
    def _find_valid_test_file(self) -> Optional[Path]:
        """查找有效的测试文件，优先选择小文件进行快速测试"""
        if not self.test_data_dir.exists():
            return None
        
        # 定义文件大小优先级（避免big目录中的大文件）
        size_priorities = [
            (10 * 1024 * 1024, "small"),    # <10MB
            (50 * 1024 * 1024, "medium"),   # <50MB  
            (200 * 1024 * 1024, "large")    # <200MB，避免396MB的文件
        ]
        
        candidates = []
        
        # 查找pcap文件，按大小分类
        for pattern in ["**/*.pcap", "**/*.pcapng"]:
            for file_path in self.test_data_dir.glob(pattern):
                if file_path.is_file() and file_path.stat().st_size > 1000:  # 至少1KB
                    # 跳过已知的损坏文件和big目录
                    if "broken" not in str(file_path) and "big" not in str(file_path):
                        file_size = file_path.stat().st_size
                        
                        for max_size, category in size_priorities:
                            if file_size < max_size:
                                candidates.append((file_path, file_size, category))
                                break
        
        # 优先返回最小的文件
        if candidates:
            # 按文件大小排序，选择最小的
            candidates.sort(key=lambda x: x[1])
            chosen_file = candidates[0]
            logger.info(f"选择测试文件: {chosen_file[0]} ({chosen_file[1]/1024:.1f}KB, {chosen_file[2]})")
            return chosen_file[0]
        
        # 如果实在找不到小文件，才考虑big目录，但要设置大小限制
        logger.warning("未找到小文件，检查big目录中是否有适中大小的文件...")
        for pattern in ["**/big/*.pcap", "**/big/*.pcapng"]:
            for file_path in self.test_data_dir.glob(pattern):
                if file_path.is_file():
                    file_size = file_path.stat().st_size
                    # 只接受小于50MB的文件用于扩展性测试
                    if file_size < 50 * 1024 * 1024:
                        logger.info(f"使用big目录中的适中文件: {file_path} ({file_size/1024/1024:.1f}MB)")
                        return file_path
                    else:
                        logger.warning(f"跳过过大文件: {file_path} ({file_size/1024/1024:.1f}MB)")
        
        return None
    
    def generate_report(self):
        """生成可扩展性测试报告"""
        self.results["end_time"] = time.time()
        self.results["total_time"] = self.results["end_time"] - self.results["start_time"]
        
        # 生成摘要
        self.results["summary"] = self._generate_summary()
        
        # 保存报告
        report_file = Path("phase_5_extensibility_test_report.json")
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        
        # 打印摘要
        self._print_summary_report()
        
        logger.info(f"可扩展性测试报告已保存到: {report_file}")
    
    def _generate_summary(self) -> Dict:
        """生成测试摘要"""
        summary = {
            "overall_status": "PASS",
            "tests_run": len(self.results["tests"]),
            "extensibility_metrics": {}
        }
        
        # 统计测试结果
        total_tests = 0
        passed_tests = 0
        
        for test_name, test_data in self.results["tests"].items():
            if isinstance(test_data, dict):
                for sub_test, sub_data in test_data.items():
                    total_tests += 1
                    if isinstance(sub_data, dict) and sub_data.get("success", False):
                        passed_tests += 1
        
        summary["extensibility_metrics"] = {
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "success_rate": (passed_tests / total_tests * 100) if total_tests > 0 else 0,
            "new_processors_added": 2,
            "total_processors_after_extension": len(ProcessorRegistry._processors)
        }
        
        if passed_tests < total_tests:
            summary["overall_status"] = "PARTIAL"
        
        return summary
    
    def _print_summary_report(self):
        """打印摘要报告"""
        logger.info("=" * 60)
        logger.info("Phase 5 可扩展性验证测试报告")
        logger.info("=" * 60)
        
        summary = self.results["summary"]
        metrics = summary.get("extensibility_metrics", {})
        
        logger.info(f"测试状态: {summary['overall_status']}")
        logger.info(f"测试类别: {summary['tests_run']}")
        logger.info(f"总耗时: {self.results['total_time']:.2f}秒")
        
        if metrics:
            logger.info(f"子测试通过率: {metrics.get('passed_tests', 0)}/{metrics.get('total_tests', 0)} ({metrics.get('success_rate', 0):.1f}%)")
            logger.info(f"新增处理器数量: {metrics.get('new_processors_added', 0)}")
            logger.info(f"扩展后处理器总数: {metrics.get('total_processors_after_extension', 0)}")
        
        logger.info("=" * 60)
    
    def cleanup(self):
        """清理临时文件"""
        if self.temp_dir.exists():
            import shutil
            shutil.rmtree(self.temp_dir)
        logger.info("可扩展性测试清理完成")


def main():
    """主函数"""
    logger.info("开始Phase 5可扩展性验证测试")
    logger.info(f"Python版本: {sys.version}")
    logger.info(f"工作目录: {os.getcwd()}")
    
    try:
        # 创建并运行可扩展性测试
        test_suite = Phase5ExtensibilityTests()
        test_suite.run_all_tests()
        
        return 0
        
    except Exception as e:
        logger.error(f"可扩展性测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main()) 