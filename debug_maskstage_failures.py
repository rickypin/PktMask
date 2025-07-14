#!/usr/bin/env python3
"""
PktMask Maskstage 双模块架构失败案例深度分析工具

分析validation_summary.html中的失败案例，识别具体失败模式和根因。
严格禁止修改主程序代码，仅用于问题诊断和分析。
"""

import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Any, Tuple
import tempfile
import os

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MaskstageFailureAnalyzer:
    """Maskstage失败案例分析器"""
    
    def __init__(self):
        self.test_data_dir = Path("tests/data/tls")
        self.output_dir = Path("output/maskstage_validation")
        
    def analyze_failure_cases(self):
        """分析主要失败案例"""
        logger.info("开始分析Maskstage失败案例")
        
        # 定义失败案例（从validation_summary.html提取）
        failure_cases = [
            {
                "file": "tls_1_2_pop_mix.pcapng",
                "input_tls23": 4,
                "masked_zero": 0,
                "output_tls23": 4,
                "masked": 0,
                "unmasked": 4,
                "issue": "完全未掩码"
            },
            {
                "file": "tls_1_0_multi_segment_google-https.pcap", 
                "input_tls23": 47,
                "masked_zero": 44,
                "output_tls23": 45,
                "masked": 44,
                "unmasked": 1,
                "issue": "部分未掩码"
            },
            {
                "file": "tls_1_2_single_vlan.pcap",
                "input_tls23": 607,
                "masked_zero": 584,
                "output_tls23": 588,
                "masked": 584,
                "unmasked": 4,
                "issue": "部分未掩码"
            }
        ]
        
        for case in failure_cases:
            logger.info(f"\n{'='*60}")
            logger.info(f"分析失败案例: {case['file']}")
            logger.info(f"问题类型: {case['issue']}")
            logger.info(f"TLS-23统计: 输入{case['input_tls23']}, 掩码{case['masked']}, 未掩码{case['unmasked']}")
            
            self._analyze_single_case(case)
    
    def _analyze_single_case(self, case: Dict[str, Any]):
        """分析单个失败案例"""
        file_path = self.test_data_dir / case["file"]
        
        if not file_path.exists():
            logger.error(f"测试文件不存在: {file_path}")
            return
            
        logger.info(f"分析文件: {file_path}")
        
        # 1. 分析原始文件的TLS消息分布
        logger.info("步骤1: 分析原始文件TLS消息")
        original_tls_analysis = self._analyze_tls_messages(file_path)
        
        # 2. 分析Marker模块生成的保留规则
        logger.info("步骤2: 分析Marker模块保留规则")
        marker_analysis = self._analyze_marker_rules(file_path)
        
        # 3. 分析Masker模块的掩码结果
        logger.info("步骤3: 分析Masker模块掩码结果")
        masker_analysis = self._analyze_masker_results(file_path, case)
        
        # 4. 对比分析，识别问题根因
        logger.info("步骤4: 根因分析")
        self._identify_root_cause(case, original_tls_analysis, marker_analysis, masker_analysis)
    
    def _analyze_tls_messages(self, file_path: Path) -> Dict[str, Any]:
        """分析原始文件中的TLS消息分布"""
        logger.info(f"使用tshark分析TLS消息: {file_path}")
        
        try:
            # 使用tshark提取TLS消息信息
            cmd = [
                "tshark", "-r", str(file_path), "-T", "json",
                "-Y", "tls",
                "-e", "frame.number",
                "-e", "tcp.stream", 
                "-e", "tcp.seq_raw",
                "-e", "tcp.len",
                "-e", "tls.record.content_type",
                "-e", "tls.record.length"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            packets = json.loads(result.stdout) if result.stdout.strip() else []
            
            # 统计TLS消息类型分布
            tls_stats = {
                "total_tls_packets": len(packets),
                "tls_23_count": 0,
                "tls_other_count": 0,
                "streams": set(),
                "tls_23_details": []
            }
            
            for packet in packets:
                layers = packet.get("_source", {}).get("layers", {})
                frame_num = self._get_first_value(layers.get("frame.number", ""))
                stream_id = self._get_first_value(layers.get("tcp.stream", ""))
                tcp_seq = self._get_first_value(layers.get("tcp.seq_raw", ""))
                tcp_len = self._get_first_value(layers.get("tcp.len", ""))
                content_types = layers.get("tls.record.content_type", [])
                record_lengths = layers.get("tls.record.length", [])
                
                if stream_id:
                    tls_stats["streams"].add(stream_id)
                
                # 处理TLS内容类型
                if isinstance(content_types, list):
                    for content_type in content_types:
                        if content_type == "23":
                            tls_stats["tls_23_count"] += 1
                            tls_stats["tls_23_details"].append({
                                "frame": frame_num,
                                "stream": stream_id,
                                "tcp_seq": tcp_seq,
                                "tcp_len": tcp_len,
                                "content_type": content_type
                            })
                        else:
                            tls_stats["tls_other_count"] += 1
                elif content_types == "23":
                    tls_stats["tls_23_count"] += 1
                    tls_stats["tls_23_details"].append({
                        "frame": frame_num,
                        "stream": stream_id, 
                        "tcp_seq": tcp_seq,
                        "tcp_len": tcp_len,
                        "content_type": content_types
                    })
                else:
                    tls_stats["tls_other_count"] += 1
            
            tls_stats["streams"] = list(tls_stats["streams"])
            
            logger.info(f"TLS消息统计: 总包数={tls_stats['total_tls_packets']}, "
                       f"TLS-23={tls_stats['tls_23_count']}, "
                       f"其他TLS={tls_stats['tls_other_count']}, "
                       f"流数量={len(tls_stats['streams'])}")
            
            return tls_stats
            
        except subprocess.CalledProcessError as e:
            logger.error(f"tshark分析失败: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"TLS消息分析异常: {e}")
            return {"error": str(e)}
    
    def _analyze_marker_rules(self, file_path: Path) -> Dict[str, Any]:
        """分析Marker模块生成的保留规则"""
        logger.info("模拟Marker模块分析（不修改主程序代码）")
        
        # 注意：这里我们不能直接调用主程序的Marker模块，
        # 因为约束条件禁止在验证分析阶段修改主程序代码
        # 我们只能通过间接方式分析规则生成逻辑
        
        try:
            # 通过检查现有的输出文件来推断Marker模块的行为
            marker_analysis = {
                "status": "indirect_analysis",
                "note": "由于约束条件限制，无法直接调用Marker模块",
                "inference": "需要通过输出文件反推Marker模块行为"
            }
            
            return marker_analysis
            
        except Exception as e:
            logger.error(f"Marker规则分析异常: {e}")
            return {"error": str(e)}
    
    def _analyze_masker_results(self, file_path: Path, case: Dict[str, Any]) -> Dict[str, Any]:
        """分析Masker模块的掩码结果"""
        logger.info("分析掩码结果文件")

        # 查找对应的输出文件（在masked_pcaps子目录中）
        base_name = case['file'].rsplit('.', 1)[0]  # 移除扩展名
        output_file = self.output_dir / "masked_pcaps" / f"{base_name}_masked.{case['file'].rsplit('.', 1)[1]}"

        if not output_file.exists():
            logger.warning(f"掩码输出文件不存在: {output_file}")
            return {"error": "output_file_not_found"}

        try:
            # 分析掩码后文件的TLS消息
            masked_tls_analysis = self._analyze_tls_messages(output_file)

            # 同时分析JSON统计文件
            json_file = self.output_dir / f"{base_name}_masked_tls23.json"
            json_analysis = {}
            if json_file.exists():
                with open(json_file, 'r') as f:
                    json_analysis = json.load(f)

            masker_analysis = {
                "output_file": str(output_file),
                "masked_tls_analysis": masked_tls_analysis,
                "json_stats": json_analysis
            }

            return masker_analysis

        except Exception as e:
            logger.error(f"Masker结果分析异常: {e}")
            return {"error": str(e)}
    
    def _identify_root_cause(self, case: Dict[str, Any],
                           original_analysis: Dict[str, Any],
                           marker_analysis: Dict[str, Any],
                           masker_analysis: Dict[str, Any]):
        """识别问题根因"""
        logger.info("进行根因分析")

        # 分析数据一致性
        original_tls23 = original_analysis.get("tls_23_count", 0)
        case_input_tls23 = case["input_tls23"]

        if original_tls23 != case_input_tls23:
            logger.warning(f"TLS-23计数不一致: tshark分析={original_tls23}, "
                          f"验证报告={case_input_tls23}")

        # 分析掩码结果
        if "masked_tls_analysis" in masker_analysis:
            masked_tls23 = masker_analysis["masked_tls_analysis"].get("tls_23_count", 0)
            logger.info(f"掩码后TLS-23计数: {masked_tls23}")

            # 对比原始和掩码后的TLS-23消息
            self._compare_tls23_messages(original_analysis, masker_analysis, case)

        # 分析JSON统计信息
        if "json_stats" in masker_analysis and masker_analysis["json_stats"]:
            json_stats = masker_analysis["json_stats"]
            logger.info(f"JSON统计信息: {json_stats}")

        # 根据失败模式分析可能原因
        if case["issue"] == "完全未掩码":
            logger.error("根因分析: 完全未掩码问题")
            logger.error("可能原因:")
            logger.error("1. Marker模块未生成任何保留规则")
            logger.error("2. Masker模块未正确应用保留规则")
            logger.error("3. 流ID或方向识别不一致")
            logger.error("4. 序列号计算错误")

        elif case["issue"] == "部分未掩码":
            logger.warning("根因分析: 部分未掩码问题")
            logger.warning("可能原因:")
            logger.warning("1. 跨TCP段TLS消息处理不完整")
            logger.warning("2. 序列号边界计算错误")
            logger.warning("3. 规则优化过程中丢失部分规则")
            logger.warning("4. 流方向识别在某些包上不一致")

        # 输出详细的诊断建议
        logger.info("\n诊断建议:")
        logger.info("1. 检查Marker和Masker模块的流ID构建逻辑一致性")
        logger.info("2. 验证序列号计算的准确性（绝对vs相对）")
        logger.info("3. 检查TLS消息边界识别的完整性")
        logger.info("4. 验证保留规则的应用逻辑")

    def _compare_tls23_messages(self, original_analysis: Dict[str, Any],
                               masker_analysis: Dict[str, Any],
                               case: Dict[str, Any]):
        """对比原始和掩码后的TLS-23消息"""
        logger.info("对比TLS-23消息详情")

        original_details = original_analysis.get("tls_23_details", [])
        masked_details = masker_analysis["masked_tls_analysis"].get("tls_23_details", [])

        logger.info(f"原始TLS-23消息数: {len(original_details)}")
        logger.info(f"掩码后TLS-23消息数: {len(masked_details)}")

        # 分析消息数量变化
        if len(original_details) == len(masked_details):
            logger.info("TLS-23消息数量保持不变（正常）")
        else:
            logger.warning(f"TLS-23消息数量发生变化: {len(original_details)} -> {len(masked_details)}")

        # 分析前几个TLS-23消息的详情
        logger.info("前5个TLS-23消息对比:")
        for i, orig_msg in enumerate(original_details[:5]):
            logger.info(f"  原始消息{i+1}: Frame {orig_msg.get('frame')}, "
                       f"Stream {orig_msg.get('stream')}, "
                       f"TCP序列号 {orig_msg.get('tcp_seq')}")

            if i < len(masked_details):
                masked_msg = masked_details[i]
                logger.info(f"  掩码消息{i+1}: Frame {masked_msg.get('frame')}, "
                           f"Stream {masked_msg.get('stream')}, "
                           f"TCP序列号 {masked_msg.get('tcp_seq')}")
            else:
                logger.warning(f"  掩码消息{i+1}: 缺失")
            logger.info("")
    
    def _get_first_value(self, value):
        """获取第一个值（处理tshark的数组输出）"""
        if isinstance(value, list) and value:
            return value[0]
        return value

def main():
    """主函数"""
    analyzer = MaskstageFailureAnalyzer()
    analyzer.analyze_failure_cases()

if __name__ == "__main__":
    main()
