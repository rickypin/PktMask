#!/usr/bin/env python3
"""
修复验证脚本

用于验证PktMask maskstage双模块架构问题的修复效果。
严格禁止修改主程序代码，仅用于修复后的验证。
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))


class FixVerificationTester:
    """修复验证测试器"""
    
    def __init__(self):
        self.test_file = "tests/samples/tls-single/tls_sample.pcap"
        self.config = {
            'preserve': {
                'handshake': True,
                'application_data': False,  # 关键：应该生成头部保留规则
                'alert': True,
                'change_cipher_spec': True,
                'heartbeat': True
            }
        }
        
    def verify_all_fixes(self) -> Dict[str, Any]:
        """验证所有问题的修复效果"""
        print("=" * 80)
        print("PktMask Maskstage双模块架构修复验证")
        print("=" * 80)
        
        # 生成修复后的KeepRuleSet
        try:
            from pktmask.core.pipeline.stages.mask_payload_v2.marker.tls_marker import TLSProtocolMarker
            marker = TLSProtocolMarker(self.config)
            ruleset = marker.analyze_file(self.test_file, self.config)
        except Exception as e:
            print(f"❌ 无法生成KeepRuleSet: {e}")
            return {"error": str(e)}
        
        verification_results = {
            "fix_1_protocol_confusion": self._verify_protocol_confusion_fix(ruleset),
            "fix_2_frame_info_accuracy": self._verify_frame_info_fix(ruleset),
            "fix_3_tls23_header_preservation": self._verify_tls23_fix(ruleset),
            "overall_verification": self._overall_verification(ruleset)
        }
        
        return verification_results
    
    def _verify_protocol_confusion_fix(self, ruleset) -> Dict[str, Any]:
        """验证问题1：协议层级混淆的修复效果"""
        print("\n" + "=" * 60)
        print("验证修复1：协议层级混淆")
        print("=" * 60)
        
        protocol_issues = []
        
        for i, rule in enumerate(ruleset.rules):
            # 检查规则类型是否还包含协议标识符
            if any(proto in rule.rule_type.lower() for proto in ['tls_', 'http_', 'ssl_']):
                protocol_issues.append({
                    "rule_index": i,
                    "rule_type": rule.rule_type,
                    "issue": "规则类型仍包含协议标识符"
                })
            
            # 检查元数据是否还包含协议信息
            protocol_metadata = []
            for key in rule.metadata:
                if any(proto in key.lower() for proto in ['tls_', 'http_', 'ssl_']):
                    protocol_metadata.append(key)
            
            if protocol_metadata:
                protocol_issues.append({
                    "rule_index": i,
                    "protocol_metadata": protocol_metadata,
                    "issue": "元数据仍包含协议相关信息"
                })
        
        if protocol_issues:
            print(f"❌ 协议层级混淆未完全修复: {len(protocol_issues)}个问题")
            for issue in protocol_issues:
                print(f"  - 规则#{issue['rule_index']}: {issue['issue']}")
        else:
            print("✅ 协议层级混淆已修复: 所有规则都是协议无关的")
        
        return {
            "fixed": len(protocol_issues) == 0,
            "remaining_issues": len(protocol_issues),
            "details": protocol_issues
        }
    
    def _verify_frame_info_fix(self, ruleset) -> Dict[str, Any]:
        """验证问题2：帧信息记录准确性的修复效果"""
        print("\n" + "=" * 60)
        print("验证修复2：帧信息记录准确性")
        print("=" * 60)
        
        frame_issues = []
        
        for i, rule in enumerate(ruleset.rules):
            metadata = rule.metadata
            
            # 检查是否使用了新的帧记录格式
            if "frame_number" in metadata and "covered_frames" not in metadata:
                frame_issues.append({
                    "rule_index": i,
                    "issue": "仍使用单帧记录格式，未使用covered_frames"
                })
            
            # 检查是否还有不必要的单帧详细信息
            unnecessary_fields = []
            for field in ["tcp_seq_raw", "tcp_len"]:
                if field in metadata:
                    unnecessary_fields.append(field)
            
            if unnecessary_fields:
                frame_issues.append({
                    "rule_index": i,
                    "unnecessary_fields": unnecessary_fields,
                    "issue": "仍记录不必要的单帧详细信息"
                })
        
        if frame_issues:
            print(f"❌ 帧信息记录问题未完全修复: {len(frame_issues)}个问题")
            for issue in frame_issues:
                print(f"  - 规则#{issue['rule_index']}: {issue['issue']}")
        else:
            print("✅ 帧信息记录已修复: 使用正确的多帧记录格式")
        
        return {
            "fixed": len(frame_issues) == 0,
            "remaining_issues": len(frame_issues),
            "details": frame_issues
        }
    
    def _verify_tls23_fix(self, ruleset) -> Dict[str, Any]:
        """验证问题3：TLS-23消息头保留的修复效果"""
        print("\n" + "=" * 60)
        print("验证修复3：TLS-23消息头保留")
        print("=" * 60)
        
        # 检查是否生成了TLS-23相关的规则
        tls23_related_rules = []
        header_preservation_rules = []
        
        for rule in ruleset.rules:
            # 检查是否有针对TLS-23的规则
            metadata = rule.metadata
            if (metadata.get("preserve_reason") == "tls_record_header" or
                metadata.get("header_size") == 5):
                header_preservation_rules.append(rule)
            
            # 或者检查是否有任何可能与TLS-23相关的规则
            if any(keyword in str(metadata).lower() for keyword in ['application', 'header']):
                tls23_related_rules.append(rule)
        
        expected_tls23_frames = [14, 15]  # 来自报告的预期帧
        
        if not header_preservation_rules and not tls23_related_rules:
            print("❌ TLS-23消息头保留未修复: 仍未生成任何相关规则")
            return {
                "fixed": False,
                "header_rules_count": 0,
                "expected_frames": expected_tls23_frames,
                "issue": "完全缺少TLS-23头部保留规则"
            }
        
        print(f"✅ 检测到TLS-23相关规则: {len(header_preservation_rules)}个头部保留规则")
        print(f"   其他相关规则: {len(tls23_related_rules)}个")
        
        # 验证头部保留规则的正确性
        correct_header_rules = 0
        for rule in header_preservation_rules:
            rule_length = rule.seq_end - rule.seq_start
            if rule_length == 5:  # TLS记录头部应该是5字节
                correct_header_rules += 1
                print(f"   ✅ 正确的5字节头部保留规则: {rule.seq_start}-{rule.seq_end}")
            else:
                print(f"   ⚠️  头部规则长度异常: {rule_length}字节 (期望5字节)")
        
        return {
            "fixed": len(header_preservation_rules) > 0,
            "header_rules_count": len(header_preservation_rules),
            "correct_header_rules": correct_header_rules,
            "total_related_rules": len(tls23_related_rules),
            "expected_frames": expected_tls23_frames
        }
    
    def _overall_verification(self, ruleset) -> Dict[str, Any]:
        """整体验证结果"""
        print("\n" + "=" * 60)
        print("整体验证结果")
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
        
        # 检查是否符合协议无关性原则
        protocol_agnostic = all(
            not any(proto in rule.rule_type.lower() for proto in ['tls_', 'http_', 'ssl_'])
            for rule in ruleset.rules
        )
        
        print(f"\n协议无关性检查: {'✅ 通过' if protocol_agnostic else '❌ 未通过'}")
        
        return {
            "total_rules": len(ruleset.rules),
            "total_flows": len(ruleset.tcp_flows),
            "rule_type_distribution": rule_types,
            "protocol_agnostic": protocol_agnostic,
            "ruleset_statistics": ruleset.statistics
        }


def main():
    """主函数"""
    tester = FixVerificationTester()
    
    try:
        results = tester.verify_all_fixes()
        
        print("\n" + "=" * 80)
        print("修复验证摘要")
        print("=" * 80)
        
        if "error" in results:
            print(f"❌ 验证失败: {results['error']}")
            return
        
        # 汇总修复状态
        fix1_status = results.get("fix_1_protocol_confusion", {}).get("fixed", False)
        fix2_status = results.get("fix_2_frame_info_accuracy", {}).get("fixed", False)
        fix3_status = results.get("fix_3_tls23_header_preservation", {}).get("fixed", False)
        
        print(f"修复1 (协议层级混淆): {'✅ 已修复' if fix1_status else '❌ 未修复'}")
        print(f"修复2 (帧信息记录): {'✅ 已修复' if fix2_status else '❌ 未修复'}")
        print(f"修复3 (TLS-23头部保留): {'✅ 已修复' if fix3_status else '❌ 未修复'}")
        
        total_fixed = sum([fix1_status, fix2_status, fix3_status])
        print(f"\n总体修复进度: {total_fixed}/3 个问题已修复")
        
        if total_fixed == 3:
            print("🎉 所有问题已成功修复！")
        else:
            print(f"⚠️  还有 {3 - total_fixed} 个问题需要修复")
        
        # 保存验证结果
        with open("fix_verification_results.json", "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"\n详细验证结果已保存到: fix_verification_results.json")
        
    except Exception as e:
        print(f"❌ 验证过程中发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
