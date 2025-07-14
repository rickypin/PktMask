#!/usr/bin/env python3
"""
PktMask GUI TLS-23掩码失效结构化调试脚本

本脚本采用结构化调试方法，在GUI处理链条的关键环节添加详细日志输出，
逐步追踪数据流，识别导致TLS-23 ApplicationData掩码失效的具体环节。

调试策略：
1. GUI触发的maskstage调用入口追踪
2. Marker模块的TLS消息识别和规则生成验证
3. Masker模块的规则应用和payload掩码处理验证
4. 最终pcap文件写入过程验证

使用方法：
    python scripts/debug/gui_tls23_masking_debug.py <test_pcap_file>
"""

import sys
import json
import logging
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass, asdict

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

@dataclass
class DebugStep:
    """调试步骤记录"""
    step_id: str
    step_name: str
    success: bool
    data: Dict[str, Any]
    error: Optional[str] = None
    duration_ms: Optional[float] = None

class GUITLSMaskingDebugger:
    """GUI TLS掩码调试器"""
    
    def __init__(self, test_file: str):
        self.test_file = Path(test_file)
        self.output_dir = Path(tempfile.mkdtemp(prefix="gui_tls23_debug_"))
        self.debug_steps: List[DebugStep] = []
        
        # 配置日志
        self.logger = self._setup_logging()
        
        # GUI配置（模拟真实GUI环境）
        self.gui_config = self._create_gui_config()
        
        self.logger.info(f"🔍 开始GUI TLS-23掩码调试")
        self.logger.info(f"📁 测试文件: {self.test_file}")
        self.logger.info(f"📁 输出目录: {self.output_dir}")
    
    def _setup_logging(self) -> logging.Logger:
        """设置详细日志"""
        logger = logging.getLogger("GUITLSMaskingDebugger")
        logger.setLevel(logging.DEBUG)
        
        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        
        # 文件处理器
        log_file = self.output_dir / "debug.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        
        # 格式化器
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(formatter)
        file_handler.setFormatter(formatter)
        
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
        
        return logger
    
    def _create_gui_config(self) -> Dict[str, Any]:
        """创建GUI配置（模拟真实GUI环境）"""
        return {
            "enabled": True,
            "protocol": "tls",
            "mode": "enhanced",
            "marker_config": {
                "preserve": {
                    "handshake": True,
                    "application_data": False,  # 关键：TLS-23应该被掩码
                    "alert": True,
                    "change_cipher_spec": True,
                    "heartbeat": True
                }
            },
            "masker_config": {
                "preserve_ratio": 0.3
            }
        }
    
    def run_debug_analysis(self) -> Dict[str, Any]:
        """运行完整的调试分析"""
        self.logger.info("🚀 开始结构化调试分析")
        
        try:
            # 步骤1: GUI配置传递链条追踪
            self._debug_gui_config_chain()
            
            # 步骤2: NewMaskPayloadStage实例化和初始化
            self._debug_stage_initialization()
            
            # 步骤3: Marker模块TLS消息识别验证
            self._debug_marker_module()
            
            # 步骤4: Masker模块规则应用验证
            self._debug_masker_module()
            
            # 步骤5: 完整GUI流程端到端测试
            self._debug_end_to_end_gui_flow()
            
            # 步骤6: 结果对比分析
            self._debug_result_comparison()
            
            # 生成调试报告
            return self._generate_debug_report()
            
        except Exception as e:
            self.logger.error(f"❌ 调试分析失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "debug_steps": [asdict(step) for step in self.debug_steps]
            }
    
    def _debug_gui_config_chain(self):
        """调试GUI配置传递链条"""
        import time
        start_time = time.time()
        
        self.logger.info("📋 步骤1: GUI配置传递链条追踪")
        
        try:
            # 1.1 模拟MainWindow复选框状态
            checkbox_states = {
                "mask_ip_cb": False,
                "dedup_packet_cb": False,
                "mask_payload_cb": True
            }
            self.logger.debug(f"复选框状态: {checkbox_states}")
            
            # 1.2 模拟build_pipeline_config调用
            from pktmask.services.pipeline_service import build_pipeline_config
            pipeline_config = build_pipeline_config(
                enable_anon=checkbox_states["mask_ip_cb"],
                enable_dedup=checkbox_states["dedup_packet_cb"],
                enable_mask=checkbox_states["mask_payload_cb"]
            )
            self.logger.debug(f"Pipeline配置: {json.dumps(pipeline_config, indent=2)}")
            
            # 1.3 提取mask配置
            mask_config = pipeline_config.get("mask", {})
            self.logger.debug(f"Mask配置: {json.dumps(mask_config, indent=2)}")
            
            # 1.4 验证关键配置项
            preserve_config = mask_config.get("marker_config", {}).get("preserve", {})
            application_data_preserve = preserve_config.get("application_data", True)
            
            self.logger.info(f"🔑 关键配置验证:")
            self.logger.info(f"   - application_data保留: {application_data_preserve}")
            self.logger.info(f"   - 预期行为: TLS-23应该被{'保留' if application_data_preserve else '掩码'}")
            
            step = DebugStep(
                step_id="gui_config_chain",
                step_name="GUI配置传递链条追踪",
                success=True,
                data={
                    "checkbox_states": checkbox_states,
                    "pipeline_config": pipeline_config,
                    "mask_config": mask_config,
                    "application_data_preserve": application_data_preserve
                },
                duration_ms=(time.time() - start_time) * 1000
            )
            self.debug_steps.append(step)
            
        except Exception as e:
            self.logger.error(f"❌ GUI配置链条追踪失败: {e}")
            step = DebugStep(
                step_id="gui_config_chain",
                step_name="GUI配置传递链条追踪",
                success=False,
                data={},
                error=str(e),
                duration_ms=(time.time() - start_time) * 1000
            )
            self.debug_steps.append(step)
            raise
    
    def _debug_stage_initialization(self):
        """调试NewMaskPayloadStage实例化和初始化"""
        import time
        start_time = time.time()
        
        self.logger.info("🔧 步骤2: NewMaskPayloadStage实例化和初始化")
        
        try:
            from pktmask.core.pipeline.stages.mask_payload_v2.stage import NewMaskPayloadStage
            
            # 2.1 创建Stage实例
            stage = NewMaskPayloadStage(self.gui_config)
            self.logger.debug(f"Stage创建成功: protocol={stage.protocol}, mode={stage.mode}")
            
            # 2.2 初始化Stage
            init_success = stage.initialize()
            self.logger.debug(f"Stage初始化: {'成功' if init_success else '失败'}")
            
            # 2.3 验证模块实例
            marker_created = stage.marker is not None
            masker_created = stage.masker is not None
            
            self.logger.info(f"🔑 模块实例验证:")
            self.logger.info(f"   - Marker模块: {'已创建' if marker_created else '未创建'}")
            self.logger.info(f"   - Masker模块: {'已创建' if masker_created else '未创建'}")
            
            if marker_created:
                self.logger.debug(f"   - Marker类型: {type(stage.marker).__name__}")
            if masker_created:
                self.logger.debug(f"   - Masker类型: {type(stage.masker).__name__}")
            
            step = DebugStep(
                step_id="stage_initialization",
                step_name="NewMaskPayloadStage实例化和初始化",
                success=init_success,
                data={
                    "protocol": stage.protocol,
                    "mode": stage.mode,
                    "marker_created": marker_created,
                    "masker_created": masker_created,
                    "marker_config": stage.marker_config,
                    "masker_config": stage.masker_config
                },
                duration_ms=(time.time() - start_time) * 1000
            )
            self.debug_steps.append(step)
            
            # 保存stage实例供后续使用
            self.stage = stage
            
        except Exception as e:
            self.logger.error(f"❌ Stage初始化失败: {e}")
            step = DebugStep(
                step_id="stage_initialization",
                step_name="NewMaskPayloadStage实例化和初始化",
                success=False,
                data={},
                error=str(e),
                duration_ms=(time.time() - start_time) * 1000
            )
            self.debug_steps.append(step)
            raise
    
    def _debug_marker_module(self):
        """调试Marker模块TLS消息识别"""
        import time
        start_time = time.time()
        
        self.logger.info("🎯 步骤3: Marker模块TLS消息识别验证")
        
        try:
            # 3.1 调用Marker模块分析文件
            keep_rules = self.stage.marker.analyze_file(str(self.test_file), self.gui_config)
            
            # 3.2 分析生成的规则
            rule_count = len(keep_rules.rules)
            self.logger.info(f"📊 生成保留规则数量: {rule_count}")
            
            # 3.3 详细分析每个规则
            tls_type_stats = {}
            for rule in keep_rules.rules:
                rule_type = getattr(rule, 'rule_type', 'unknown')
                if rule_type not in tls_type_stats:
                    tls_type_stats[rule_type] = 0
                tls_type_stats[rule_type] += 1
                
                self.logger.debug(f"规则: {rule.stream_id} [{rule.seq_start}:{rule.seq_end}] "
                                f"类型={rule_type}")
            
            self.logger.info(f"🔑 TLS消息类型统计: {tls_type_stats}")
            
            step = DebugStep(
                step_id="marker_module",
                step_name="Marker模块TLS消息识别验证",
                success=True,
                data={
                    "rule_count": rule_count,
                    "tls_type_stats": tls_type_stats,
                    "rules_summary": [
                        {
                            "stream_id": rule.stream_id,
                            "seq_range": f"[{rule.seq_start}:{rule.seq_end}]",
                            "rule_type": getattr(rule, 'rule_type', 'unknown')
                        }
                        for rule in keep_rules.rules[:10]  # 只显示前10个规则
                    ]
                },
                duration_ms=(time.time() - start_time) * 1000
            )
            self.debug_steps.append(step)
            
            # 保存规则供后续使用
            self.keep_rules = keep_rules
            
        except Exception as e:
            self.logger.error(f"❌ Marker模块分析失败: {e}")
            step = DebugStep(
                step_id="marker_module",
                step_name="Marker模块TLS消息识别验证",
                success=False,
                data={},
                error=str(e),
                duration_ms=(time.time() - start_time) * 1000
            )
            self.debug_steps.append(step)
            raise

    def _debug_masker_module(self):
        """调试Masker模块规则应用"""
        import time
        start_time = time.time()

        self.logger.info("⚙️ 步骤4: Masker模块规则应用验证")

        try:
            # 4.1 应用掩码规则
            output_file = self.output_dir / f"masker_output_{self.test_file.name}"
            masking_stats = self.stage.masker.apply_masking(
                str(self.test_file),
                str(output_file),
                self.keep_rules
            )

            # 4.2 分析掩码统计
            self.logger.info(f"📊 掩码处理统计:")
            self.logger.info(f"   - 处理成功: {masking_stats.success}")
            self.logger.info(f"   - 处理包数: {masking_stats.processed_packets}")
            self.logger.info(f"   - 修改包数: {masking_stats.modified_packets}")

            # 4.3 验证输出文件
            output_exists = output_file.exists()
            output_size = output_file.stat().st_size if output_exists else 0

            self.logger.info(f"📁 输出文件验证:")
            self.logger.info(f"   - 文件存在: {output_exists}")
            self.logger.info(f"   - 文件大小: {output_size} 字节")

            step = DebugStep(
                step_id="masker_module",
                step_name="Masker模块规则应用验证",
                success=masking_stats.success,
                data={
                    "packets_processed": masking_stats.processed_packets,
                    "packets_modified": masking_stats.modified_packets,
                    "output_file": str(output_file),
                    "output_exists": output_exists,
                    "output_size": output_size
                },
                duration_ms=(time.time() - start_time) * 1000
            )
            self.debug_steps.append(step)

            # 保存输出文件路径供后续使用
            self.masker_output_file = output_file

        except Exception as e:
            self.logger.error(f"❌ Masker模块处理失败: {e}")
            step = DebugStep(
                step_id="masker_module",
                step_name="Masker模块规则应用验证",
                success=False,
                data={},
                error=str(e),
                duration_ms=(time.time() - start_time) * 1000
            )
            self.debug_steps.append(step)
            raise

    def _debug_end_to_end_gui_flow(self):
        """调试完整GUI流程端到端测试"""
        import time
        start_time = time.time()

        self.logger.info("🔄 步骤5: 完整GUI流程端到端测试")

        try:
            # 5.1 模拟完整GUI调用流程
            output_file = self.output_dir / f"gui_e2e_output_{self.test_file.name}"
            stats = self.stage.process_file(str(self.test_file), str(output_file))

            # 5.2 分析处理统计
            self.logger.info(f"📊 端到端处理统计:")
            self.logger.info(f"   - 阶段名称: {stats.stage_name}")
            self.logger.info(f"   - 处理包数: {stats.packets_processed}")
            self.logger.info(f"   - 修改包数: {stats.packets_modified}")
            self.logger.info(f"   - 处理时间: {stats.duration_ms:.2f} ms")

            # 5.3 验证输出文件
            output_exists = output_file.exists()
            output_size = output_file.stat().st_size if output_exists else 0

            self.logger.info(f"📁 端到端输出文件验证:")
            self.logger.info(f"   - 文件存在: {output_exists}")
            self.logger.info(f"   - 文件大小: {output_size} 字节")

            step = DebugStep(
                step_id="end_to_end_gui_flow",
                step_name="完整GUI流程端到端测试",
                success=True,
                data={
                    "stage_name": stats.stage_name,
                    "packets_processed": stats.packets_processed,
                    "packets_modified": stats.packets_modified,
                    "duration_ms": stats.duration_ms,
                    "output_file": str(output_file),
                    "output_exists": output_exists,
                    "output_size": output_size,
                    "extra_metrics": stats.extra_metrics
                },
                duration_ms=(time.time() - start_time) * 1000
            )
            self.debug_steps.append(step)

            # 保存端到端输出文件路径供后续使用
            self.e2e_output_file = output_file

        except Exception as e:
            self.logger.error(f"❌ 端到端GUI流程失败: {e}")
            step = DebugStep(
                step_id="end_to_end_gui_flow",
                step_name="完整GUI流程端到端测试",
                success=False,
                data={},
                error=str(e),
                duration_ms=(time.time() - start_time) * 1000
            )
            self.debug_steps.append(step)
            raise

    def _debug_result_comparison(self):
        """调试结果对比分析"""
        import time
        start_time = time.time()

        self.logger.info("🔍 步骤6: 结果对比分析")

        try:
            # 6.1 验证TLS-23掩码效果
            tls23_verification = self._verify_tls23_masking(str(self.e2e_output_file))

            self.logger.info(f"🔑 TLS-23掩码验证结果:")
            self.logger.info(f"   - TLS-23消息总数: {tls23_verification['total_tls23_messages']}")
            self.logger.info(f"   - 已掩码消息数: {tls23_verification['masked_tls23_messages']}")
            self.logger.info(f"   - 掩码成功率: {tls23_verification['masking_success_rate']:.2%}")

            # 6.2 对比不同处理方式的结果
            comparison_results = {
                "masker_only": {
                    "file": str(self.masker_output_file) if hasattr(self, 'masker_output_file') else None,
                    "exists": self.masker_output_file.exists() if hasattr(self, 'masker_output_file') else False
                },
                "end_to_end": {
                    "file": str(self.e2e_output_file),
                    "exists": self.e2e_output_file.exists(),
                    "tls23_verification": tls23_verification
                }
            }

            step = DebugStep(
                step_id="result_comparison",
                step_name="结果对比分析",
                success=True,
                data={
                    "tls23_verification": tls23_verification,
                    "comparison_results": comparison_results
                },
                duration_ms=(time.time() - start_time) * 1000
            )
            self.debug_steps.append(step)

        except Exception as e:
            self.logger.error(f"❌ 结果对比分析失败: {e}")
            step = DebugStep(
                step_id="result_comparison",
                step_name="结果对比分析",
                success=False,
                data={},
                error=str(e),
                duration_ms=(time.time() - start_time) * 1000
            )
            self.debug_steps.append(step)
            raise

    def _verify_tls23_masking(self, pcap_file: str) -> Dict[str, Any]:
        """验证TLS-23掩码效果"""
        try:
            # 重用现有的TLS流分析工具
            sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))
            from tls_flow_analyzer import TLSFlowAnalyzer

            analyzer = TLSFlowAnalyzer(pcap_file)
            flows = analyzer.analyze_flows()

            total_tls23 = 0
            masked_tls23 = 0

            for flow in flows:
                for message in flow.get('tls_messages', []):
                    if message.get('tls_type') == 23:  # ApplicationData
                        total_tls23 += 1
                        # 检查payload是否被掩码（全零）
                        payload = message.get('payload_data', b'')
                        if payload and all(b == 0 for b in payload):
                            masked_tls23 += 1

            return {
                "total_tls23_messages": total_tls23,
                "masked_tls23_messages": masked_tls23,
                "masking_success_rate": masked_tls23 / total_tls23 if total_tls23 > 0 else 0.0
            }

        except Exception as e:
            self.logger.warning(f"TLS-23验证失败: {e}")
            return {
                "total_tls23_messages": 0,
                "masked_tls23_messages": 0,
                "masking_success_rate": 0.0,
                "error": str(e)
            }

    def _generate_debug_report(self) -> Dict[str, Any]:
        """生成调试报告"""
        self.logger.info("📋 生成调试报告")

        # 统计成功/失败步骤
        successful_steps = [step for step in self.debug_steps if step.success]
        failed_steps = [step for step in self.debug_steps if not step.success]

        # 识别问题环节
        problem_analysis = self._analyze_problems()

        report = {
            "success": len(failed_steps) == 0,
            "total_steps": len(self.debug_steps),
            "successful_steps": len(successful_steps),
            "failed_steps": len(failed_steps),
            "test_file": str(self.test_file),
            "output_directory": str(self.output_dir),
            "debug_steps": [asdict(step) for step in self.debug_steps],
            "problem_analysis": problem_analysis,
            "recommendations": self._generate_recommendations(problem_analysis)
        }

        # 保存报告到文件
        report_file = self.output_dir / "debug_report.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        self.logger.info(f"📄 调试报告已保存: {report_file}")

        return report

    def _analyze_problems(self) -> Dict[str, Any]:
        """分析问题环节"""
        problems = []

        # 检查每个步骤的问题
        for step in self.debug_steps:
            if not step.success:
                problems.append({
                    "step": step.step_name,
                    "error": step.error,
                    "impact": "高" if step.step_id in ["marker_module", "masker_module"] else "中"
                })

        # 检查TLS-23掩码效果
        result_step = next((s for s in self.debug_steps if s.step_id == "result_comparison"), None)
        if result_step and result_step.success:
            tls23_data = result_step.data.get("tls23_verification", {})
            success_rate = tls23_data.get("masking_success_rate", 0.0)

            if success_rate < 1.0:
                problems.append({
                    "step": "TLS-23掩码效果",
                    "error": f"掩码成功率仅为 {success_rate:.2%}",
                    "impact": "高",
                    "details": tls23_data
                })

        return {
            "problem_count": len(problems),
            "problems": problems,
            "critical_issues": [p for p in problems if p["impact"] == "高"]
        }

    def _generate_recommendations(self, problem_analysis: Dict[str, Any]) -> List[str]:
        """生成修复建议"""
        recommendations = []

        critical_issues = problem_analysis.get("critical_issues", [])

        if not critical_issues:
            recommendations.append("✅ 所有关键步骤都成功执行，问题可能在细节实现中")

        for issue in critical_issues:
            if "Marker模块" in issue["step"]:
                recommendations.append("🎯 检查Marker模块的TLS消息识别逻辑，确保正确识别TLS-23消息")
                recommendations.append("🔍 验证保留规则生成是否正确排除TLS-23消息体")

            elif "Masker模块" in issue["step"]:
                recommendations.append("⚙️ 检查Masker模块的规则应用逻辑，确保正确掩码非保留区域")
                recommendations.append("🔍 验证TCP序列号匹配和掩码应用算法")

            elif "TLS-23掩码效果" in issue["step"]:
                recommendations.append("🔑 重点检查TLS-23 ApplicationData的掩码处理逻辑")
                recommendations.append("📊 对比Marker生成的规则与Masker应用的效果")

        if len(critical_issues) > 1:
            recommendations.append("🔄 建议逐步隔离问题，先修复Marker模块，再验证Masker模块")

        return recommendations


def main():
    """主函数"""
    if len(sys.argv) != 2:
        print("使用方法: python scripts/debug/gui_tls23_masking_debug.py <test_pcap_file>")
        sys.exit(1)

    test_file = sys.argv[1]
    if not Path(test_file).exists():
        print(f"❌ 测试文件不存在: {test_file}")
        sys.exit(1)

    # 创建调试器并运行分析
    debugger = GUITLSMaskingDebugger(test_file)
    report = debugger.run_debug_analysis()

    # 输出摘要
    print("\n" + "="*60)
    print("🔍 GUI TLS-23掩码调试摘要")
    print("="*60)
    print(f"📁 测试文件: {test_file}")

    if report.get('success', False):
        print(f"📊 总步骤数: {report.get('total_steps', 0)}")
        print(f"✅ 成功步骤: {report.get('successful_steps', 0)}")
        print(f"❌ 失败步骤: {report.get('failed_steps', 0)}")
        print(f"🎯 整体状态: {'成功' if report.get('success', False) else '失败'}")

        # 输出问题分析
        problem_analysis = report.get("problem_analysis", {})
        if problem_analysis.get("problem_count", 0) > 0:
            print(f"\n🚨 发现 {problem_analysis['problem_count']} 个问题:")
            for i, problem in enumerate(problem_analysis.get("problems", []), 1):
                print(f"   {i}. {problem['step']}: {problem['error']} (影响: {problem['impact']})")

        # 输出修复建议
        recommendations = report.get("recommendations", [])
        if recommendations:
            print(f"\n💡 修复建议:")
            for i, rec in enumerate(recommendations, 1):
                print(f"   {i}. {rec}")

        print(f"\n📄 详细报告: {debugger.output_dir}/debug_report.json")
        print(f"📄 调试日志: {debugger.output_dir}/debug.log")
    else:
        print(f"❌ 调试分析失败: {report.get('error', '未知错误')}")
        print(f"📄 调试日志: {debugger.output_dir}/debug.log")


if __name__ == "__main__":
    main()
