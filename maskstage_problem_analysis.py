#!/usr/bin/env python3
"""
PktMask Maskstage双模块架构问题分析脚本

基于 marker_validation_report.md 的发现，对以下关键问题进行交叉分析验证：
1. KeepRuleSet协议层级混淆
2. KeepRuleSet帧信息记录不准确  
3. TLS-23消息头保留策略缺失

严格禁止修改主程序代码，仅用于问题分析和验证。
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from pktmask.core.pipeline.stages.mask_payload_v2.marker.tls_marker import TLSProtocolMarker
from pktmask.core.pipeline.stages.mask_payload_v2.marker.types import KeepRule, KeepRuleSet


class MaskstageProblemsAnalyzer:
    """Maskstage双模块架构问题分析器"""
    
    def __init__(self):
        self.test_file = "tests/samples/tls-single/tls_sample.pcap"
        self.config = {
            'preserve': {
                'handshake': True,
                'application_data': False,  # 关键：应该只保留头部
                'alert': True,
                'change_cipher_spec': True,
                'heartbeat': True
            }
        }
        
    def analyze_all_problems(self) -> Dict[str, Any]:
        """分析所有发现的问题"""
        print("=" * 80)
        print("PktMask Maskstage双模块架构问题分析")
        print("=" * 80)
        
        # 生成当前的KeepRuleSet
        marker = TLSProtocolMarker(self.config)
        try:
            ruleset = marker.analyze_file(self.test_file, self.config)
        except Exception as e:
            print(f"❌ 无法生成KeepRuleSet: {e}")
            return {"error": str(e)}
        
        analysis_results = {
            "problem_1_protocol_confusion": self._analyze_protocol_confusion(ruleset),
            "problem_2_frame_info_inaccuracy": self._analyze_frame_info_inaccuracy(ruleset),
            "problem_3_tls23_header_missing": self._analyze_tls23_header_missing(ruleset),
            "overall_assessment": self._overall_assessment(ruleset)
        }
        
        return analysis_results
    
    def _analyze_protocol_confusion(self, ruleset: KeepRuleSet) -> Dict[str, Any]:
        """问题1：KeepRuleSet协议层级混淆分析"""
        print("\n" + "=" * 60)
        print("问题1：KeepRuleSet协议层级混淆分析")
        print("=" * 60)
        
        protocol_issues = []
        
        for i, rule in enumerate(ruleset.rules):
            # 检查规则类型是否包含应用层协议信息
            if "tls_" in rule.rule_type:
                protocol_issues.append({
                    "rule_index": i,
                    "rule_type": rule.rule_type,
                    "issue": "规则类型包含TLS协议标识符",
                    "expected": "应为纯TCP层面的序列号保留规则"
                })
            
            # 检查元数据是否包含应用层协议信息
            metadata_issues = []
            for key in rule.metadata:
                if key.startswith("tls_"):
                    metadata_issues.append(key)
            
            if metadata_issues:
                protocol_issues.append({
                    "rule_index": i,
                    "metadata_keys": metadata_issues,
                    "issue": "元数据包含TLS协议相关信息",
                    "expected": "应为协议无关的TCP序列号信息"
                })
        
        print(f"发现协议层级混淆问题: {len(protocol_issues)}个")
        for issue in protocol_issues:
            print(f"  - 规则#{issue['rule_index']}: {issue['issue']}")
            if 'rule_type' in issue:
                print(f"    当前类型: {issue['rule_type']}")
            if 'metadata_keys' in issue:
                print(f"    问题元数据: {issue['metadata_keys']}")
        
        return {
            "issues_found": len(protocol_issues),
            "details": protocol_issues,
            "severity": "HIGH" if protocol_issues else "NONE",
            "recommendation": "修改Marker模块生成协议无关的TCP序列号保留规则"
        }
    
    def _analyze_frame_info_inaccuracy(self, ruleset: KeepRuleSet) -> Dict[str, Any]:
        """问题2：KeepRuleSet帧信息记录不准确分析"""
        print("\n" + "=" * 60)
        print("问题2：KeepRuleSet帧信息记录不准确分析")
        print("=" * 60)
        
        frame_issues = []
        
        for i, rule in enumerate(ruleset.rules):
            metadata = rule.metadata
            
            # 检查是否只记录了单个帧信息
            if "frame_number" in metadata:
                frame_number = metadata["frame_number"]
                
                # 检查规则是否可能涉及多个帧
                rule_length = rule.seq_end - rule.seq_start
                tcp_len = metadata.get("tcp_len", 0)
                
                if rule_length > tcp_len and tcp_len > 0:
                    frame_issues.append({
                        "rule_index": i,
                        "single_frame": frame_number,
                        "rule_length": rule_length,
                        "single_frame_tcp_len": tcp_len,
                        "issue": "规则长度超过单帧TCP载荷长度，可能涉及多帧",
                        "expected": "应记录所有涉及帧的帧号"
                    })
                
                # 检查是否记录了不必要的单帧详细信息
                unnecessary_fields = []
                for field in ["tcp_seq_raw", "tcp_len"]:
                    if field in metadata:
                        unnecessary_fields.append(field)
                
                if unnecessary_fields:
                    frame_issues.append({
                        "rule_index": i,
                        "unnecessary_fields": unnecessary_fields,
                        "issue": "记录了单帧的原始TCP序列号和载荷长度",
                        "expected": "应移除单帧详细信息，仅记录规则覆盖的序列号区段"
                    })
        
        print(f"发现帧信息记录问题: {len(frame_issues)}个")
        for issue in frame_issues:
            print(f"  - 规则#{issue['rule_index']}: {issue['issue']}")
            if 'rule_length' in issue:
                print(f"    规则长度: {issue['rule_length']}, 单帧长度: {issue['single_frame_tcp_len']}")
            if 'unnecessary_fields' in issue:
                print(f"    不必要字段: {issue['unnecessary_fields']}")
        
        return {
            "issues_found": len(frame_issues),
            "details": frame_issues,
            "severity": "MEDIUM" if frame_issues else "NONE",
            "recommendation": "修改规则生成逻辑，记录涉及的所有帧号，移除单帧详细信息"
        }
    
    def _analyze_tls23_header_missing(self, ruleset: KeepRuleSet) -> Dict[str, Any]:
        """问题3：TLS-23消息头保留策略缺失分析"""
        print("\n" + "=" * 60)
        print("问题3：TLS-23消息头保留策略缺失分析")
        print("=" * 60)
        
        # 根据报告，应该有TLS-23消息但缺少保留规则
        expected_tls23_frames = [14, 15]  # 来自报告的Frame 14和Frame 15
        
        tls23_issues = []
        
        # 检查是否有TLS-23相关的规则
        tls23_rules = []
        for rule in ruleset.rules:
            if "applicationdata" in rule.rule_type.lower():
                tls23_rules.append(rule)
        
        if not tls23_rules:
            tls23_issues.append({
                "issue": "完全缺少TLS-23 ApplicationData的保留规则",
                "expected_frames": expected_tls23_frames,
                "current_rules": 0,
                "expected": "应为每个TLS-23消息生成头部保留规则(5字节)"
            })
        else:
            # 检查现有TLS-23规则是否正确
            for rule in tls23_rules:
                # TLS-23应该只保留头部(5字节)，但当前可能保留了整个消息
                rule_length = rule.seq_end - rule.seq_start
                if rule_length > 5:
                    tls23_issues.append({
                        "rule": rule,
                        "issue": f"TLS-23规则保留了{rule_length}字节，应该只保留5字节头部",
                        "expected": "只保留TLS记录头部(5字节)"
                    })
        
        print(f"发现TLS-23处理问题: {len(tls23_issues)}个")
        for issue in tls23_issues:
            print(f"  - {issue['issue']}")
            if 'expected_frames' in issue:
                print(f"    预期涉及帧: {issue['expected_frames']}")
        
        return {
            "issues_found": len(tls23_issues),
            "details": tls23_issues,
            "severity": "HIGH" if tls23_issues else "NONE",
            "recommendation": "修复TLS-23处理逻辑，为每个ApplicationData消息生成5字节头部保留规则"
        }
    
    def _overall_assessment(self, ruleset: KeepRuleSet) -> Dict[str, Any]:
        """整体评估"""
        print("\n" + "=" * 60)
        print("整体评估")
        print("=" * 60)
        
        print(f"生成的规则总数: {len(ruleset.rules)}")
        print(f"TCP流数量: {len(ruleset.tcp_flows)}")
        
        # 统计规则类型
        rule_types = {}
        for rule in ruleset.rules:
            rule_types[rule.rule_type] = rule_types.get(rule.rule_type, 0) + 1
        
        print("规则类型分布:")
        for rule_type, count in rule_types.items():
            print(f"  - {rule_type}: {count}个")
        
        return {
            "total_rules": len(ruleset.rules),
            "total_flows": len(ruleset.tcp_flows),
            "rule_type_distribution": rule_types,
            "ruleset_statistics": ruleset.statistics
        }


def main():
    """主函数"""
    analyzer = MaskstageProblemsAnalyzer()
    
    try:
        results = analyzer.analyze_all_problems()
        
        print("\n" + "=" * 80)
        print("分析结果摘要")
        print("=" * 80)
        
        if "error" in results:
            print(f"❌ 分析失败: {results['error']}")
            return
        
        # 汇总问题严重程度
        high_severity = 0
        medium_severity = 0
        
        for problem_key, problem_data in results.items():
            if problem_key == "overall_assessment":
                continue
            
            severity = problem_data.get("severity", "NONE")
            if severity == "HIGH":
                high_severity += 1
            elif severity == "MEDIUM":
                medium_severity += 1
        
        print(f"高严重性问题: {high_severity}个")
        print(f"中等严重性问题: {medium_severity}个")
        
        if high_severity > 0 or medium_severity > 0:
            print("\n建议修复优先级:")
            print("1. 问题3 (TLS-23消息头保留策略缺失) - 影响掩码效果")
            print("2. 问题1 (协议层级混淆) - 违反架构设计原则")
            print("3. 问题2 (帧信息记录不准确) - 影响调试和验证")
        else:
            print("✅ 未发现严重问题")
        
        # 保存详细结果
        with open("maskstage_analysis_results.json", "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"\n详细分析结果已保存到: maskstage_analysis_results.json")
        
    except Exception as e:
        print(f"❌ 分析过程中发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
