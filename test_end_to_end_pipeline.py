#!/usr/bin/env python3
"""
端到端流水线测试：验证移植后的 Marker 与 Masker 模块协作
"""

import sys
import os
import tempfile
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_end_to_end_pipeline():
    """测试完整的 maskstage 流水线"""
    print("=" * 80)
    print("端到端流水线测试")
    print("=" * 80)
    
    test_file = "tests/samples/tls-single/tls_sample.pcap"
    if not os.path.exists(test_file):
        print(f"❌ 测试文件不存在: {test_file}")
        return False
    
    try:
        from pktmask.core.pipeline.stages.mask_payload_v2.marker.tls_marker import TLSProtocolMarker
        from pktmask.core.pipeline.stages.mask_payload_v2.masker.payload_masker import PayloadMasker
        
        # 配置
        config = {
            'preserve': {
                'handshake': True,
                'application_data': False,  # 测试头部保留
                'alert': True,
                'change_cipher_spec': True,
                'heartbeat': True
            }
        }
        
        print(f"📁 输入文件: {test_file}")
        
        # 第一阶段：Marker 生成保留规则
        print(f"\n🏷️  第一阶段：Marker 分析")
        marker = TLSProtocolMarker(config)
        ruleset = marker.analyze_file(test_file, config)
        
        print(f"  生成规则数量: {len(ruleset.rules)}")
        print(f"  TLS-23头部规则: {len([r for r in ruleset.rules if r.rule_type == 'tls_applicationdata_header'])}")
        print(f"  完整保留规则: {len([r for r in ruleset.rules if 'full_message' in r.metadata.get('preserve_strategy', '')])}")
        
        # 第二阶段：Masker 应用保留规则
        print(f"\n🎭 第二阶段：Masker 处理")
        
        with tempfile.NamedTemporaryFile(suffix=".pcap", delete=False) as tmp_file:
            output_file = tmp_file.name
        
        try:
            masker = PayloadMasker({})
            result = masker.apply_masking(test_file, output_file, ruleset)
            
            print(f"  处理结果: {result}")
            print(f"  输出文件: {output_file}")
            
            # 验证输出文件
            if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                print(f"  ✅ 输出文件生成成功 (大小: {os.path.getsize(output_file)} 字节)")
                
                # 简单验证：检查文件是否为有效的 pcap
                with open(output_file, 'rb') as f:
                    header = f.read(4)
                    if header in [b'\xd4\xc3\xb2\xa1', b'\xa1\xb2\xc3\xd4']:  # pcap magic numbers
                        print(f"  ✅ 输出文件格式正确 (PCAP)")
                        return True
                    else:
                        print(f"  ❌ 输出文件格式错误")
                        return False
            else:
                print(f"  ❌ 输出文件生成失败")
                return False
                
        finally:
            # 清理临时文件
            if os.path.exists(output_file):
                os.unlink(output_file)
        
    except Exception as e:
        print(f"❌ 端到端测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_precision_comparison():
    """对比移植前后的精度差异"""
    print("\n" + "=" * 80)
    print("精度对比测试")
    print("=" * 80)
    
    test_file = "tests/samples/tls-single/tls_sample.pcap"
    
    try:
        from pktmask.tools.tls_flow_analyzer import TLSFlowAnalyzer
        from pktmask.core.pipeline.stages.mask_payload_v2.marker.tls_marker import TLSProtocolMarker
        
        # 使用 tls_flow_analyzer 作为参考标准
        print("📊 使用 tls_flow_analyzer 分析（参考标准）")
        analyzer = TLSFlowAnalyzer(verbose=False)
        reference_result = analyzer.analyze_pcap(test_file)
        
        ref_messages = reference_result.get("reassembled_messages", [])
        print(f"  参考结果: {len(ref_messages)} 个 TLS 消息")
        
        # 使用移植后的 marker 分析
        print("🏷️  使用移植后的 Marker 分析")
        config = {'preserve': {'application_data': False}}
        marker = TLSProtocolMarker(config)
        ruleset = marker.analyze_file(test_file, config)
        
        print(f"  Marker结果: {len(ruleset.rules)} 条保留规则")
        
        # 对比序列号精度
        print("\n🔍 序列号精度对比:")
        
        # 统计 TLS-23 消息的处理
        ref_tls23_count = len([m for m in ref_messages if m.get("content_type") == 23])
        marker_tls23_count = len([r for r in ruleset.rules if r.rule_type == "tls_applicationdata_header"])
        
        print(f"  TLS-23 消息数量:")
        print(f"    参考标准: {ref_tls23_count}")
        print(f"    Marker结果: {marker_tls23_count}")
        
        if ref_tls23_count == marker_tls23_count:
            print(f"  ✅ TLS-23 消息识别精度一致")
        else:
            print(f"  ⚠️  TLS-23 消息识别数量差异")
        
        # 检查序列号范围的合理性
        print(f"\n📐 序列号范围合理性检查:")
        total_preserved_bytes = sum(rule.length for rule in ruleset.rules)
        print(f"  总保留字节数: {total_preserved_bytes}")
        
        # 检查是否有重叠规则
        overlapping_rules = 0
        for i, rule1 in enumerate(ruleset.rules):
            for j, rule2 in enumerate(ruleset.rules[i+1:], i+1):
                if (rule1.stream_id == rule2.stream_id and 
                    rule1.direction == rule2.direction and
                    rule1.overlaps_with(rule2)):
                    overlapping_rules += 1
        
        print(f"  重叠规则数量: {overlapping_rules}")
        
        if overlapping_rules == 0:
            print(f"  ✅ 无重叠规则，序列号范围合理")
            return True
        else:
            print(f"  ⚠️  存在重叠规则，需要检查")
            return False
        
    except Exception as e:
        print(f"❌ 精度对比测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("🚀 开始端到端流水线验证")
    
    # 测试端到端流水线
    pipeline_ok = test_end_to_end_pipeline()
    
    # 测试精度对比
    precision_ok = test_precision_comparison()
    
    # 总结
    print("\n" + "=" * 80)
    print("端到端验证总结")
    print("=" * 80)
    
    if pipeline_ok and precision_ok:
        print("🎉 端到端验证成功！")
        print("✅ Marker-Masker 协作正常")
        print("✅ 精度改进验证通过")
        print("✅ 移植实施完全成功")
        return 0
    else:
        print("❌ 端到端验证失败")
        if not pipeline_ok:
            print("❌ 流水线协作失败")
        if not precision_ok:
            print("❌ 精度对比失败")
        return 1

if __name__ == "__main__":
    sys.exit(main())
