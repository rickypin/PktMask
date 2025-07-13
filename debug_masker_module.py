#!/usr/bin/env python3
"""
调试Masker模块

专门调试Masker模块的工作情况，检查为什么掩码字节数和保留字节数都是0
"""

import json
import sys
import tempfile
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from pktmask.core.pipeline.stages.mask_payload_v2.marker.tls_marker import TLSProtocolMarker
from pktmask.core.pipeline.stages.mask_payload_v2.masker.payload_masker import PayloadMasker


def debug_masker_module():
    """调试Masker模块"""
    print("=" * 80)
    print("调试Masker模块")
    print("=" * 80)
    
    test_file = "tests/samples/tls-single/tls_sample.pcap"
    config = {
        'preserve': {
            'handshake': True,
            'application_data': False,  # 关键：只保留头部
            'alert': True,
            'change_cipher_spec': True,
            'heartbeat': True
        }
    }
    
    # 步骤1: 生成KeepRuleSet
    print("\n1. 生成KeepRuleSet")
    print("-" * 40)
    
    marker = TLSProtocolMarker(config)
    ruleset = marker.analyze_file(test_file, config)
    
    print(f"生成的规则数量: {len(ruleset.rules)}")
    print(f"TCP流数量: {len(ruleset.tcp_flows)}")
    
    print("\n规则详情:")
    for i, rule in enumerate(ruleset.rules):
        print(f"  规则#{i+1}: {rule.rule_type}")
        print(f"    序列号范围: {rule.seq_start} - {rule.seq_end} ({rule.seq_end - rule.seq_start}字节)")
        print(f"    流ID: {rule.stream_id}, 方向: {rule.direction}")
        if "preserve_strategy" in rule.metadata:
            print(f"    保留策略: {rule.metadata['preserve_strategy']}")
    
    # 步骤2: 测试Masker模块
    print("\n2. 测试Masker模块")
    print("-" * 40)
    
    try:
        # 创建临时输出文件
        with tempfile.NamedTemporaryFile(suffix=".pcap", delete=False) as tmp_file:
            output_file = tmp_file.name
        
        print(f"输入文件: {test_file}")
        print(f"输出文件: {output_file}")
        
        # 创建Masker实例
        masker = PayloadMasker({})
        
        # 应用掩码
        print("\n开始应用掩码...")
        masking_stats = masker.apply_masking(test_file, output_file, ruleset)
        
        print(f"\n掩码处理结果:")
        print(f"  成功: {masking_stats.success}")
        print(f"  处理包数: {masking_stats.processed_packets}")
        print(f"  修改包数: {masking_stats.modified_packets}")
        print(f"  掩码字节数: {masking_stats.masked_bytes}")
        print(f"  保留字节数: {masking_stats.preserved_bytes}")
        print(f"  执行时间: {masking_stats.execution_time:.3f}秒")
        
        if masking_stats.errors:
            print(f"\n错误信息:")
            for error in masking_stats.errors:
                print(f"  - {error}")
        
        if masking_stats.warnings:
            print(f"\n警告信息:")
            for warning in masking_stats.warnings:
                print(f"  - {warning}")
        
        # 步骤3: 分析问题
        print("\n3. 问题分析")
        print("-" * 40)
        
        if masking_stats.masked_bytes == 0 and masking_stats.preserved_bytes == 0:
            print("❌ 问题确认: 没有字节被处理")
            
            print("\n可能的原因:")
            print("1. KeepRuleSet为空或无效")
            print("2. Masker模块无法正确解析规则")
            print("3. 序列号匹配失败")
            print("4. 文件格式或协议解析问题")
            
            # 检查KeepRuleSet
            if len(ruleset.rules) == 0:
                print("\n❌ KeepRuleSet为空")
            else:
                print(f"\n✅ KeepRuleSet包含{len(ruleset.rules)}条规则")
                
                # 检查规则有效性
                for rule in ruleset.rules:
                    if rule.seq_start >= rule.seq_end:
                        print(f"❌ 无效规则: {rule.seq_start} >= {rule.seq_end}")
                    elif rule.seq_end - rule.seq_start == 0:
                        print(f"⚠️  零长度规则: {rule.seq_start} - {rule.seq_end}")
        
        elif masking_stats.preserved_bytes > 0:
            print("✅ 有字节被保留，TLS头部保留可能正常工作")
        
        # 步骤4: 检查输出文件
        print("\n4. 检查输出文件")
        print("-" * 40)
        
        output_path = Path(output_file)
        if output_path.exists():
            file_size = output_path.stat().st_size
            print(f"输出文件大小: {file_size} 字节")
            
            if file_size == 0:
                print("❌ 输出文件为空")
            else:
                print("✅ 输出文件已生成")
        else:
            print("❌ 输出文件不存在")
        
        return {
            "ruleset": {
                "rules_count": len(ruleset.rules),
                "flows_count": len(ruleset.tcp_flows),
                "rules": [
                    {
                        "rule_type": rule.rule_type,
                        "seq_start": rule.seq_start,
                        "seq_end": rule.seq_end,
                        "length": rule.seq_end - rule.seq_start,
                        "stream_id": rule.stream_id,
                        "direction": rule.direction,
                        "metadata": rule.metadata
                    } for rule in ruleset.rules
                ]
            },
            "masking_stats": {
                "success": masking_stats.success,
                "processed_packets": masking_stats.processed_packets,
                "modified_packets": masking_stats.modified_packets,
                "masked_bytes": masking_stats.masked_bytes,
                "preserved_bytes": masking_stats.preserved_bytes,
                "execution_time": masking_stats.execution_time,
                "errors": masking_stats.errors,
                "warnings": masking_stats.warnings
            },
            "output_file": output_file
        }
        
    except Exception as e:
        print(f"❌ Masker模块测试失败: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}


def main():
    """主函数"""
    try:
        results = debug_masker_module()
        
        # 保存调试结果
        with open("masker_debug_results.json", "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"\n调试结果已保存到: masker_debug_results.json")
        
    except Exception as e:
        print(f"❌ 调试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
