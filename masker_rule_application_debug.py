#!/usr/bin/env python3
"""
Masker模块规则应用调试脚本

专门调试Masker模块中_apply_keep_rules方法的实际掩码应用过程，
验证TLS-23头部保留规则是否被正确应用到TCP载荷。
"""

import sys
import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Tuple

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from pktmask.core.pipeline.stages.mask_payload_v2.stage import NewMaskPayloadStage
from pktmask.core.pipeline.stages.mask_payload_v2.marker.tls_marker import TLSProtocolMarker
from pktmask.core.pipeline.stages.mask_payload_v2.masker.payload_masker import PayloadMasker
from scapy.all import *

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

class MaskerRuleApplicationDebugger:
    """Masker规则应用调试器"""
    
    def __init__(self):
        self.test_file = "tests/data/tls/tls_1_3_0-RTT-2_22_23_mix.pcap"
        self.output_dir = Path("output/masker_application_debug")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 配置
        self.config = {
            'protocol': 'tls',
            'mode': 'enhanced',
            'marker_config': {},
            'masker_config': {},
            'preserve': {
                'handshake': True,
                'application_data': False,  # 关键：TLS-23应该只保留头部
                'alert': True,
                'change_cipher_spec': True,
                'heartbeat': True
            }
        }
    
    def debug_rule_application(self):
        """调试规则应用过程"""
        logger.info("开始调试Masker规则应用过程")
        
        debug_results = {
            "test_file": self.test_file,
            "config": self.config,
            "rule_generation": {},
            "packet_analysis": {},
            "rule_matching": {},
            "masking_application": {},
            "problem_diagnosis": {}
        }
        
        try:
            # 1. 生成规则
            debug_results["rule_generation"] = self._generate_rules()
            
            # 2. 分析数据包
            debug_results["packet_analysis"] = self._analyze_packets()
            
            # 3. 调试规则匹配
            debug_results["rule_matching"] = self._debug_rule_matching(
                debug_results["rule_generation"]["keep_rules"],
                debug_results["packet_analysis"]["tls23_packets"]
            )
            
            # 4. 调试掩码应用
            debug_results["masking_application"] = self._debug_masking_application(
                debug_results["rule_generation"]["keep_rules"]
            )
            
            # 5. 问题诊断
            debug_results["problem_diagnosis"] = self._diagnose_problems(debug_results)
            
        except Exception as e:
            logger.error(f"调试过程出错: {e}")
            debug_results["error"] = str(e)
        
        # 保存结果
        report_file = self.output_dir / "masker_rule_application_debug.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(debug_results, f, indent=2, ensure_ascii=False, default=str)
        
        logger.info(f"调试报告已保存: {report_file}")
        
        return debug_results
    
    def _generate_rules(self) -> Dict[str, Any]:
        """生成保留规则"""
        logger.info("生成保留规则")
        
        rule_results = {
            "keep_rules": None,
            "tls23_rules": [],
            "rule_lookup": {}
        }
        
        try:
            # 创建TLS Marker
            marker = TLSProtocolMarker(self.config.get('marker_config', {}))
            marker.preserve_config = self.config.get('preserve', {})
            
            # 生成规则
            keep_rules = marker.analyze_file(self.test_file, self.config)
            rule_results["keep_rules"] = keep_rules
            
            # 提取TLS-23规则
            for rule in keep_rules.rules:
                if rule.metadata.get('tls_content_type') == 23:
                    rule_results["tls23_rules"].append({
                        'stream_id': rule.stream_id,
                        'direction': rule.direction,
                        'seq_start': rule.seq_start,
                        'seq_end': rule.seq_end,
                        'rule_type': rule.rule_type,
                        'preserve_strategy': rule.metadata.get('preserve_strategy')
                    })
            
            # 创建Masker并预处理规则
            masker = PayloadMasker(self.config.get('masker_config', {}))
            rule_lookup = masker._preprocess_keep_rules(keep_rules)
            rule_results["rule_lookup"] = rule_lookup
            
            logger.info(f"生成了 {len(keep_rules.rules)} 条规则，其中 {len(rule_results['tls23_rules'])} 条TLS-23规则")
            
        except Exception as e:
            logger.error(f"规则生成失败: {e}")
            rule_results["error"] = str(e)
        
        return rule_results
    
    def _analyze_packets(self) -> Dict[str, Any]:
        """分析数据包中的TLS-23消息"""
        logger.info("分析数据包中的TLS-23消息")
        
        packet_analysis = {
            "total_packets": 0,
            "tcp_packets": 0,
            "tls23_packets": [],
            "stream_mapping": {}
        }
        
        try:
            packets = rdpcap(self.test_file)
            packet_analysis["total_packets"] = len(packets)
            
            stream_counter = 0
            stream_map = {}
            
            for i, packet in enumerate(packets):
                if packet.haslayer(TCP) and packet[TCP].payload:
                    packet_analysis["tcp_packets"] += 1
                    
                    # 构建流标识
                    tcp_layer = packet[TCP]
                    ip_layer = packet[IP] if packet.haslayer(IP) else None
                    
                    if ip_layer:
                        src_ip = ip_layer.src
                        dst_ip = ip_layer.dst
                        src_port = tcp_layer.sport
                        dst_port = tcp_layer.dport
                        
                        # 创建流标识（与Masker中的逻辑一致）
                        flow_key = f"{src_ip}:{src_port}-{dst_ip}:{dst_port}"
                        reverse_key = f"{dst_ip}:{dst_port}-{src_ip}:{src_port}"
                        
                        if flow_key not in stream_map and reverse_key not in stream_map:
                            stream_map[flow_key] = str(stream_counter)
                            stream_counter += 1
                        
                        stream_id = stream_map.get(flow_key) or stream_map.get(reverse_key)
                        
                        # 确定方向
                        if flow_key in stream_map:
                            direction = "forward"
                        else:
                            direction = "reverse"
                        
                        # 检查是否包含TLS-23消息
                        payload = bytes(tcp_layer.payload)
                        if len(payload) >= 5 and payload[0] == 23:  # TLS ApplicationData
                            tls23_info = {
                                "packet_index": i,
                                "frame_number": i + 1,
                                "stream_id": stream_id,
                                "direction": direction,
                                "tcp_seq": tcp_layer.seq,
                                "payload_length": len(payload),
                                "payload_preview": payload[:20].hex(),
                                "tls_record_length": int.from_bytes(payload[3:5], 'big') if len(payload) >= 5 else 0
                            }
                            packet_analysis["tls23_packets"].append(tls23_info)
            
            packet_analysis["stream_mapping"] = stream_map
            
            logger.info(f"分析了 {packet_analysis['total_packets']} 个数据包，"
                       f"发现 {len(packet_analysis['tls23_packets'])} 个TLS-23消息")
            
        except Exception as e:
            logger.error(f"数据包分析失败: {e}")
            packet_analysis["error"] = str(e)
        
        return packet_analysis
    
    def _debug_rule_matching(self, keep_rules, tls23_packets) -> Dict[str, Any]:
        """调试规则匹配过程"""
        logger.info("调试规则匹配过程")
        
        matching_results = {
            "packet_rule_matches": [],
            "unmatched_packets": [],
            "matching_statistics": {}
        }
        
        try:
            # 为每个TLS-23数据包查找匹配的规则
            for packet_info in tls23_packets:
                stream_id = packet_info["stream_id"]
                direction = packet_info["direction"]
                tcp_seq = packet_info["tcp_seq"]
                payload_length = packet_info["payload_length"]
                
                # 查找匹配的规则
                matching_rules = []
                for rule in keep_rules.rules:
                    if (rule.stream_id == stream_id and 
                        rule.direction == direction and
                        rule.metadata.get('tls_content_type') == 23):
                        
                        # 检查序列号范围是否匹配
                        packet_seq_start = tcp_seq
                        packet_seq_end = tcp_seq + payload_length
                        
                        # 检查是否有重叠
                        if (rule.seq_start < packet_seq_end and rule.seq_end > packet_seq_start):
                            matching_rules.append({
                                "rule_seq_start": rule.seq_start,
                                "rule_seq_end": rule.seq_end,
                                "rule_type": rule.rule_type,
                                "preserve_strategy": rule.metadata.get('preserve_strategy'),
                                "overlap_start": max(rule.seq_start, packet_seq_start),
                                "overlap_end": min(rule.seq_end, packet_seq_end)
                            })
                
                match_info = {
                    "packet": packet_info,
                    "matching_rules": matching_rules,
                    "has_matches": len(matching_rules) > 0
                }
                
                matching_results["packet_rule_matches"].append(match_info)
                
                if not matching_rules:
                    matching_results["unmatched_packets"].append(packet_info)
            
            # 统计匹配情况
            total_packets = len(tls23_packets)
            matched_packets = sum(1 for m in matching_results["packet_rule_matches"] if m["has_matches"])
            
            matching_results["matching_statistics"] = {
                "total_tls23_packets": total_packets,
                "matched_packets": matched_packets,
                "unmatched_packets": len(matching_results["unmatched_packets"]),
                "matching_rate": matched_packets / total_packets if total_packets > 0 else 0.0
            }
            
            logger.info(f"规则匹配: {matched_packets}/{total_packets} 数据包匹配到规则 "
                       f"({matching_results['matching_statistics']['matching_rate']:.2%})")
            
        except Exception as e:
            logger.error(f"规则匹配调试失败: {e}")
            matching_results["error"] = str(e)
        
        return matching_results
    
    def _debug_masking_application(self, keep_rules) -> Dict[str, Any]:
        """调试掩码应用过程"""
        logger.info("调试掩码应用过程")
        
        masking_results = {
            "processing_results": [],
            "masking_effectiveness": {},
            "output_verification": {}
        }
        
        try:
            # 创建NewMaskPayloadStage并处理文件
            stage = NewMaskPayloadStage(self.config)
            stage.initialize()
            
            output_file = self.output_dir / "debug_output.pcap"
            stats = stage.process_file(self.test_file, str(output_file))
            
            masking_results["processing_results"] = {
                "packets_processed": stats.packets_processed,
                "packets_modified": stats.packets_modified,
                "duration_ms": stats.duration_ms,
                "output_file": str(output_file)
            }
            
            # 验证输出文件
            if output_file.exists():
                masking_results["output_verification"] = self._verify_output_file(str(output_file))
            
            logger.info(f"掩码应用完成: 处理 {stats.packets_processed} 个包，修改 {stats.packets_modified} 个包")
            
        except Exception as e:
            logger.error(f"掩码应用调试失败: {e}")
            masking_results["error"] = str(e)
        
        return masking_results
    
    def _verify_output_file(self, output_file: str) -> Dict[str, Any]:
        """验证输出文件的掩码效果"""
        logger.info(f"验证输出文件: {output_file}")
        
        verification = {
            "file_exists": True,
            "tls23_messages": [],
            "masking_analysis": {}
        }
        
        try:
            packets = rdpcap(output_file)
            
            for i, packet in enumerate(packets):
                if packet.haslayer(TCP) and packet[TCP].payload:
                    payload = bytes(packet[TCP].payload)
                    
                    if len(payload) >= 5 and payload[0] == 23:  # TLS ApplicationData
                        # 分析掩码状态
                        header_bytes = payload[:5]
                        body_bytes = payload[5:] if len(payload) > 5 else b''
                        
                        # 检查头部是否保留
                        header_preserved = header_bytes[0] == 23  # 第一个字节应该是23
                        
                        # 检查消息体是否被掩码
                        if body_bytes:
                            zero_count = sum(1 for b in body_bytes if b == 0)
                            body_masked = zero_count / len(body_bytes) > 0.8
                        else:
                            body_masked = True  # 没有消息体，认为已掩码
                        
                        tls23_analysis = {
                            "packet_index": i,
                            "tcp_seq": packet[TCP].seq,
                            "payload_length": len(payload),
                            "header_preserved": header_preserved,
                            "body_masked": body_masked,
                            "header_hex": header_bytes.hex(),
                            "body_preview": body_bytes[:10].hex() if body_bytes else "",
                            "zero_percentage": zero_count / len(body_bytes) if body_bytes else 1.0
                        }
                        
                        verification["tls23_messages"].append(tls23_analysis)
            
            # 统计掩码效果
            total_messages = len(verification["tls23_messages"])
            headers_preserved = sum(1 for m in verification["tls23_messages"] if m["header_preserved"])
            bodies_masked = sum(1 for m in verification["tls23_messages"] if m["body_masked"])
            
            verification["masking_analysis"] = {
                "total_tls23_messages": total_messages,
                "headers_preserved": headers_preserved,
                "bodies_masked": bodies_masked,
                "header_preservation_rate": headers_preserved / total_messages if total_messages > 0 else 0.0,
                "body_masking_rate": bodies_masked / total_messages if total_messages > 0 else 0.0
            }
            
            logger.info(f"输出验证: {total_messages} 个TLS-23消息，"
                       f"头部保留率 {verification['masking_analysis']['header_preservation_rate']:.2%}，"
                       f"消息体掩码率 {verification['masking_analysis']['body_masking_rate']:.2%}")
            
        except Exception as e:
            logger.error(f"输出文件验证失败: {e}")
            verification["error"] = str(e)
        
        return verification
    
    def _diagnose_problems(self, debug_results) -> Dict[str, Any]:
        """诊断问题"""
        logger.info("诊断问题")
        
        diagnosis = {
            "identified_issues": [],
            "root_cause_analysis": {},
            "recommendations": []
        }
        
        try:
            # 检查规则匹配情况
            matching_stats = debug_results.get("rule_matching", {}).get("matching_statistics", {})
            if matching_stats.get("matching_rate", 0.0) < 1.0:
                diagnosis["identified_issues"].append({
                    "type": "rule_matching_incomplete",
                    "description": f"只有 {matching_stats.get('matching_rate', 0.0):.2%} 的TLS-23数据包匹配到规则",
                    "details": matching_stats
                })
            
            # 检查掩码效果
            masking_analysis = debug_results.get("masking_application", {}).get("output_verification", {}).get("masking_analysis", {})
            body_masking_rate = masking_analysis.get("body_masking_rate", 0.0)
            
            if body_masking_rate < 0.8:
                diagnosis["identified_issues"].append({
                    "type": "insufficient_body_masking",
                    "description": f"TLS-23消息体掩码率只有 {body_masking_rate:.2%}",
                    "details": masking_analysis
                })
            
            # 根本原因分析
            if diagnosis["identified_issues"]:
                diagnosis["root_cause_analysis"] = {
                    "primary_cause": "规则匹配或掩码应用过程存在问题",
                    "possible_causes": [
                        "TCP序列号计算不匹配",
                        "流标识构建不一致",
                        "规则应用逻辑错误",
                        "载荷修改失败"
                    ]
                }
                
                diagnosis["recommendations"] = [
                    "检查TCP序列号计算的一致性",
                    "验证流标识构建逻辑",
                    "调试_apply_keep_rules方法的具体实现",
                    "检查载荷修改和写入过程"
                ]
            
        except Exception as e:
            logger.error(f"问题诊断失败: {e}")
            diagnosis["error"] = str(e)
        
        return diagnosis


def main():
    """主函数"""
    debugger = MaskerRuleApplicationDebugger()
    results = debugger.debug_rule_application()
    
    # 打印关键结果
    print("\n" + "="*60)
    print("Masker规则应用调试结果")
    print("="*60)
    
    if "error" in results:
        print(f"❌ 调试失败: {results['error']}")
        return
    
    # 规则匹配统计
    matching_stats = results.get("rule_matching", {}).get("matching_statistics", {})
    print(f"规则匹配率: {matching_stats.get('matching_rate', 0.0):.2%}")
    print(f"匹配的数据包: {matching_stats.get('matched_packets', 0)}/{matching_stats.get('total_tls23_packets', 0)}")
    
    # 掩码效果
    masking_analysis = results.get("masking_application", {}).get("output_verification", {}).get("masking_analysis", {})
    print(f"头部保留率: {masking_analysis.get('header_preservation_rate', 0.0):.2%}")
    print(f"消息体掩码率: {masking_analysis.get('body_masking_rate', 0.0):.2%}")
    
    # 问题诊断
    issues = results.get("problem_diagnosis", {}).get("identified_issues", [])
    print(f"\n发现问题: {len(issues)} 个")
    for i, issue in enumerate(issues, 1):
        print(f"  {i}. {issue.get('description', 'Unknown issue')}")
    
    print("="*60)
    
    return results


if __name__ == "__main__":
    main()
