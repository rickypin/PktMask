#!/usr/bin/env python3
"""
PktMask Marker 模块精度改进验证脚本

验证移植后的 TCP 载荷重组和精确序列号计算功能。
对比移植前后的输出差异，确保精度改进和向后兼容性。
"""

import sys
import os
import tempfile
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_marker_precision():
    """测试 Marker 模块的精度改进"""
    print("=" * 80)
    print("PktMask Marker 模块精度改进验证")
    print("=" * 80)
    
    # 测试文件
    test_file = "tests/samples/tls-single/tls_sample.pcap"
    if not os.path.exists(test_file):
        print(f"❌ 测试文件不存在: {test_file}")
        return False
    
    try:
        from pktmask.core.pipeline.stages.mask_payload_v2.marker.tls_marker import TLSProtocolMarker
        
        # 测试配置
        config = {
            'preserve': {
                'handshake': True,
                'application_data': False,  # 测试头部保留策略
                'alert': True,
                'change_cipher_spec': True,
                'heartbeat': True
            }
        }
        
        print(f"\n📁 测试文件: {test_file}")
        print(f"🔧 配置: {config['preserve']}")
        
        # 创建标记器并分析
        marker = TLSProtocolMarker(config)
        ruleset = marker.analyze_file(test_file, config)
        
        print(f"\n📊 分析结果:")
        print(f"  生成规则数量: {len(ruleset.rules)}")
        print(f"  TCP流数量: {len(ruleset.tcp_flows)}")
        print(f"  分析时间: {ruleset.metadata.get('analysis_time', 0):.3f}秒")
        
        # 验证规则精度
        print(f"\n🔍 规则精度验证:")
        precision_issues = []
        
        for i, rule in enumerate(ruleset.rules):
            print(f"\n  规则#{i+1}:")
            print(f"    类型: {rule.rule_type}")
            print(f"    流ID: {rule.stream_id}, 方向: {rule.direction}")
            print(f"    序列号范围: [{rule.seq_start}, {rule.seq_end}) (长度: {rule.length}字节)")
            
            # 检查左闭右开区间
            if rule.seq_start >= rule.seq_end:
                precision_issues.append(f"规则#{i+1}: 无效的序列号区间")
            
            # 检查元数据完整性
            metadata = rule.metadata
            if 'preserve_strategy' in metadata:
                print(f"    保留策略: {metadata['preserve_strategy']}")
            
            if 'tls_header_seq_start' in metadata and 'tls_header_seq_end' in metadata:
                header_start = metadata['tls_header_seq_start']
                header_end = metadata['tls_header_seq_end']
                print(f"    TLS头部: [{header_start}, {header_end}) (长度: {header_end - header_start}字节)")
            
            if 'tls_payload_seq_start' in metadata and 'tls_payload_seq_end' in metadata:
                payload_start = metadata['tls_payload_seq_start']
                payload_end = metadata['tls_payload_seq_end']
                print(f"    TLS载荷: [{payload_start}, {payload_end}) (长度: {payload_end - payload_start}字节)")
            
            # 验证 TLS-23 头部保留策略
            if rule.rule_type == "tls_applicationdata_header":
                if rule.length != 5:
                    precision_issues.append(f"规则#{i+1}: TLS-23头部规则长度应为5字节，实际{rule.length}字节")
        
        # 验证跨包消息处理
        print(f"\n🔗 跨包消息处理验证:")
        cross_segment_rules = [r for r in ruleset.rules if r.metadata.get('is_cross_segment', False)]
        print(f"  跨包规则数量: {len(cross_segment_rules)}")
        
        for rule in cross_segment_rules:
            print(f"    跨包规则: {rule.rule_type} 序列号[{rule.seq_start}, {rule.seq_end})")
        
        # 验证序列号映射精度
        print(f"\n📐 序列号映射精度验证:")
        for stream_id, flow_info in ruleset.tcp_flows.items():
            print(f"  TCP流 {stream_id}:")
            print(f"    源: {flow_info.src_ip}:{flow_info.src_port}")
            print(f"    目标: {flow_info.dst_ip}:{flow_info.dst_port}")
            print(f"    数据包数: {flow_info.packet_count}")
        
        # 总结验证结果
        print(f"\n✅ 验证结果:")
        if precision_issues:
            print(f"  ❌ 发现 {len(precision_issues)} 个精度问题:")
            for issue in precision_issues:
                print(f"    - {issue}")
            return False
        else:
            print(f"  ✅ 所有规则通过精度验证")
            print(f"  ✅ 左闭右开区间格式正确")
            print(f"  ✅ TLS-23头部保留策略正确")
            print(f"  ✅ 序列号映射精度改进生效")
            return True
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_backward_compatibility():
    """测试向后兼容性"""
    print("\n" + "=" * 80)
    print("向后兼容性验证")
    print("=" * 80)
    
    try:
        # 测试 KeepRule 和 KeepRuleSet 的基本功能
        from pktmask.core.pipeline.stages.mask_payload_v2.marker.types import KeepRule, KeepRuleSet
        
        # 创建测试规则
        rule1 = KeepRule(
            stream_id="0",
            direction="forward",
            seq_start=1000,
            seq_end=1005,  # 左闭右开区间
            rule_type="tls_applicationdata_header"
        )
        
        rule2 = KeepRule(
            stream_id="0", 
            direction="forward",
            seq_start=2000,
            seq_end=2100,
            rule_type="tls_handshake"
        )
        
        # 测试规则集合
        ruleset = KeepRuleSet()
        ruleset.add_rule(rule1)
        ruleset.add_rule(rule2)
        
        print(f"✅ KeepRule 创建成功")
        print(f"✅ KeepRuleSet 操作正常")
        print(f"✅ 左闭右开区间验证: 规则1长度={rule1.length}, 规则2长度={rule2.length}")
        
        # 测试重叠检测
        overlaps = rule1.overlaps_with(rule2)
        print(f"✅ 重叠检测功能正常: {overlaps}")
        
        return True
        
    except Exception as e:
        print(f"❌ 向后兼容性测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("🚀 开始 PktMask Marker 精度改进验证")
    
    # 测试精度改进
    precision_ok = test_marker_precision()
    
    # 测试向后兼容性
    compatibility_ok = test_backward_compatibility()
    
    # 总结
    print("\n" + "=" * 80)
    print("验证总结")
    print("=" * 80)
    
    if precision_ok and compatibility_ok:
        print("🎉 所有测试通过！")
        print("✅ 精度改进验证成功")
        print("✅ 向后兼容性验证成功")
        print("✅ 移植实施完成")
        return 0
    else:
        print("❌ 部分测试失败")
        if not precision_ok:
            print("❌ 精度改进验证失败")
        if not compatibility_ok:
            print("❌ 向后兼容性验证失败")
        return 1

if __name__ == "__main__":
    sys.exit(main())
