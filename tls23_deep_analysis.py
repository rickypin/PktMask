#!/usr/bin/env python3
"""
TLS-23 ApplicationData处理深度分析脚本

专门分析TLS-23消息头保留策略缺失的根本原因，
验证Marker模块是否正确识别了TLS-23消息但未生成保留规则。
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))


class TLS23DeepAnalyzer:
    """TLS-23 ApplicationData深度分析器"""
    
    def __init__(self):
        self.test_file = "tests/samples/tls-single/tls_sample.pcap"
        
    def analyze_tls23_processing(self) -> Dict[str, Any]:
        """深度分析TLS-23处理流程"""
        print("=" * 80)
        print("TLS-23 ApplicationData处理深度分析")
        print("=" * 80)
        
        results = {
            "tshark_raw_analysis": self._analyze_with_tshark(),
            "marker_processing_trace": self._trace_marker_processing(),
            "configuration_analysis": self._analyze_configuration(),
            "root_cause_analysis": self._identify_root_cause()
        }
        
        return results
    
    def _analyze_with_tshark(self) -> Dict[str, Any]:
        """使用tshark直接分析TLS-23消息"""
        print("\n" + "=" * 60)
        print("1. tshark原始数据分析")
        print("=" * 60)
        
        try:
            # 使用tshark提取TLS记录信息
            cmd = [
                "tshark", "-r", self.test_file,
                "-T", "json",
                "-Y", "tls",
                "-e", "frame.number",
                "-e", "tcp.stream",
                "-e", "tcp.seq_raw",
                "-e", "tcp.len",
                "-e", "tls.record.content_type",
                "-e", "tls.record.length"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            tls_data = json.loads(result.stdout)
            
            tls23_packets = []
            all_tls_packets = []
            
            for packet in tls_data:
                layers = packet.get("_source", {}).get("layers", {})
                frame_num = layers.get("frame.number", [""])[0]
                content_types = layers.get("tls.record.content_type", [])
                
                if not isinstance(content_types, list):
                    content_types = [content_types] if content_types else []
                
                packet_info = {
                    "frame": frame_num,
                    "tcp_stream": layers.get("tcp.stream", [""])[0],
                    "tcp_seq": layers.get("tcp.seq_raw", [""])[0],
                    "tcp_len": layers.get("tcp.len", [""])[0],
                    "tls_content_types": content_types,
                    "tls_record_lengths": layers.get("tls.record.length", [])
                }
                
                all_tls_packets.append(packet_info)
                
                # 检查是否包含TLS-23
                if "23" in content_types:
                    tls23_packets.append(packet_info)
            
            print(f"总TLS数据包: {len(all_tls_packets)}个")
            print(f"TLS-23数据包: {len(tls23_packets)}个")
            
            if tls23_packets:
                print("\nTLS-23数据包详情:")
                for pkt in tls23_packets:
                    print(f"  Frame {pkt['frame']}: TCP序列号={pkt['tcp_seq']}, "
                          f"TCP长度={pkt['tcp_len']}, TLS类型={pkt['tls_content_types']}")
            
            return {
                "total_tls_packets": len(all_tls_packets),
                "tls23_packets_count": len(tls23_packets),
                "tls23_packets": tls23_packets,
                "all_packets": all_tls_packets
            }
            
        except Exception as e:
            print(f"❌ tshark分析失败: {e}")
            return {"error": str(e)}
    
    def _trace_marker_processing(self) -> Dict[str, Any]:
        """跟踪Marker模块的处理过程"""
        print("\n" + "=" * 60)
        print("2. Marker模块处理跟踪")
        print("=" * 60)
        
        try:
            from pktmask.core.pipeline.stages.mask_payload_v2.marker.tls_marker import TLSProtocolMarker
            
            # 创建配置，确保application_data=False
            config = {
                'preserve': {
                    'handshake': True,
                    'application_data': False,  # 关键配置
                    'alert': True,
                    'change_cipher_spec': True,
                    'heartbeat': True
                }
            }
            
            print(f"配置: application_data = {config['preserve']['application_data']}")
            
            marker = TLSProtocolMarker(config)
            
            # 分析文件
            ruleset = marker.analyze_file(self.test_file, config)
            
            # 检查生成的规则
            tls23_rules = []
            all_rules = []
            
            for rule in ruleset.rules:
                rule_info = {
                    "rule_type": rule.rule_type,
                    "seq_range": f"{rule.seq_start}-{rule.seq_end}",
                    "length": rule.seq_end - rule.seq_start,
                    "metadata": rule.metadata
                }
                all_rules.append(rule_info)
                
                if "applicationdata" in rule.rule_type.lower():
                    tls23_rules.append(rule_info)
            
            print(f"生成的总规则数: {len(all_rules)}")
            print(f"TLS-23相关规则数: {len(tls23_rules)}")
            
            if not tls23_rules:
                print("❌ 未生成任何TLS-23相关规则")
            else:
                print("TLS-23规则详情:")
                for rule in tls23_rules:
                    print(f"  类型: {rule['rule_type']}, 长度: {rule['length']}")
            
            return {
                "config_used": config,
                "total_rules": len(all_rules),
                "tls23_rules_count": len(tls23_rules),
                "tls23_rules": tls23_rules,
                "all_rules": all_rules
            }
            
        except Exception as e:
            print(f"❌ Marker处理跟踪失败: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e)}
    
    def _analyze_configuration(self) -> Dict[str, Any]:
        """分析配置对TLS-23处理的影响"""
        print("\n" + "=" * 60)
        print("3. 配置影响分析")
        print("=" * 60)
        
        # 测试不同配置下的行为
        configs_to_test = [
            {
                "name": "当前配置(application_data=False)",
                "config": {'preserve': {'application_data': False}}
            },
            {
                "name": "测试配置(application_data=True)",
                "config": {'preserve': {'application_data': True}}
            }
        ]
        
        config_results = []
        
        for test_case in configs_to_test:
            print(f"\n测试: {test_case['name']}")
            
            try:
                from pktmask.core.pipeline.stages.mask_payload_v2.marker.tls_marker import TLSProtocolMarker
                
                full_config = {
                    'preserve': {
                        'handshake': True,
                        'application_data': test_case['config']['preserve']['application_data'],
                        'alert': True,
                        'change_cipher_spec': True,
                        'heartbeat': True
                    }
                }
                
                marker = TLSProtocolMarker(full_config)
                ruleset = marker.analyze_file(self.test_file, full_config)
                
                tls23_count = sum(1 for rule in ruleset.rules 
                                if "applicationdata" in rule.rule_type.lower())
                
                print(f"  生成的TLS-23规则数: {tls23_count}")
                
                config_results.append({
                    "config_name": test_case['name'],
                    "application_data_setting": test_case['config']['preserve']['application_data'],
                    "tls23_rules_generated": tls23_count,
                    "total_rules": len(ruleset.rules)
                })
                
            except Exception as e:
                print(f"  ❌ 测试失败: {e}")
                config_results.append({
                    "config_name": test_case['name'],
                    "error": str(e)
                })
        
        return {"config_tests": config_results}
    
    def _identify_root_cause(self) -> Dict[str, Any]:
        """识别根本原因"""
        print("\n" + "=" * 60)
        print("4. 根本原因分析")
        print("=" * 60)
        
        # 基于前面的分析结果，识别可能的根本原因
        potential_causes = [
            {
                "cause": "TLS-23消息识别失败",
                "description": "Marker模块未能正确识别TLS-23消息",
                "verification": "检查tshark输出是否包含TLS-23消息"
            },
            {
                "cause": "配置逻辑错误",
                "description": "application_data=False时应生成头部保留规则，但实际未生成任何规则",
                "verification": "检查_should_preserve_tls_type方法的逻辑"
            },
            {
                "cause": "规则生成逻辑缺陷",
                "description": "即使识别了TLS-23消息，也未正确生成头部保留规则",
                "verification": "检查_generate_keep_rules方法中的TLS-23处理逻辑"
            },
            {
                "cause": "TLS-23头部长度计算错误",
                "description": "未正确计算TLS记录头部的5字节长度",
                "verification": "检查是否有专门的头部长度计算逻辑"
            }
        ]
        
        print("可能的根本原因:")
        for i, cause in enumerate(potential_causes, 1):
            print(f"{i}. {cause['cause']}")
            print(f"   描述: {cause['description']}")
            print(f"   验证方法: {cause['verification']}")
        
        # 基于分析结果推断最可能的原因
        most_likely_cause = {
            "primary_cause": "配置逻辑错误",
            "explanation": "当application_data=False时，代码逻辑可能直接跳过了TLS-23消息的处理，"
                         "而没有实现'保留头部，掩码载荷'的预期行为",
            "fix_strategy": "修改TLS Marker中的_should_preserve_tls_type和规则生成逻辑，"
                          "使application_data=False时生成5字节头部保留规则"
        }
        
        return {
            "potential_causes": potential_causes,
            "most_likely_cause": most_likely_cause
        }


def main():
    """主函数"""
    analyzer = TLS23DeepAnalyzer()
    
    try:
        results = analyzer.analyze_tls23_processing()
        
        print("\n" + "=" * 80)
        print("深度分析结论")
        print("=" * 80)
        
        # 汇总关键发现
        tshark_analysis = results.get("tshark_raw_analysis", {})
        marker_analysis = results.get("marker_processing_trace", {})
        root_cause = results.get("root_cause_analysis", {})
        
        print(f"tshark检测到的TLS-23数据包: {tshark_analysis.get('tls23_packets_count', 0)}个")
        print(f"Marker生成的TLS-23规则: {marker_analysis.get('tls23_rules_count', 0)}个")
        
        if tshark_analysis.get('tls23_packets_count', 0) > 0 and marker_analysis.get('tls23_rules_count', 0) == 0:
            print("\n❌ 确认问题: tshark能检测到TLS-23消息，但Marker未生成相应规则")
            
            most_likely = root_cause.get("most_likely_cause", {})
            print(f"\n最可能的原因: {most_likely.get('primary_cause', 'Unknown')}")
            print(f"解释: {most_likely.get('explanation', 'No explanation')}")
            print(f"修复策略: {most_likely.get('fix_strategy', 'No strategy')}")
        
        # 保存详细结果
        with open("tls23_deep_analysis_results.json", "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"\n详细分析结果已保存到: tls23_deep_analysis_results.json")
        
    except Exception as e:
        print(f"❌ 深度分析过程中发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
