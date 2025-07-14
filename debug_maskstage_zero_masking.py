#!/usr/bin/env python3
"""
PktMask NewMaskPayloadStage 零掩码问题诊断脚本

分析为什么GUI显示大部分文件 "masked 0 pkts" 的根本原因。
严格禁止修改主程序代码，仅用于问题诊断和验证。
"""

import sys
import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from src.pktmask.core.pipeline.stages.mask_payload_v2.stage import NewMaskPayloadStage
from src.pktmask.core.pipeline.stages.mask_payload_v2.marker.tls_marker import TLSProtocolMarker
from src.pktmask.core.pipeline.stages.mask_payload_v2.masker.payload_masker import PayloadMasker

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def analyze_zero_masking_issue():
    """分析零掩码问题的根本原因"""
    
    print("🔍 PktMask NewMaskPayloadStage 零掩码问题诊断")
    print("=" * 60)
    
    # 测试文件列表（从GUI日志中提取的问题文件）
    problem_files = [
        "tests/data/tls/tls_1_2_plainip.pcap",
        "tests/data/tls/tls_1_3_0-RTT-2_22_23_mix.pcap",
        "tests/data/tls/tls_1_0_multi_segment_google-https.pcap",
        "tests/data/tls/https-justlaunchpage.pcap",
        "tests/data/tls/tls_1_2-2.pcap",
        "tests/data/tls/tls_1_2_single_vlan.pcap",
        "tests/data/tls/tls_1_0_sslerr1-70.pcap",
        "tests/data/tls/google-https-cachedlink_plus_sitelink.pcap"
    ]

    # 工作文件（有掩码的文件）
    working_files = [
        "tests/data/tls/ssl_3.pcap",
        "tests/data/tls/tls_1_2_double_vlan.pcap"
    ]
    
    # 创建标准配置
    config = {
        'protocol': 'tls',
        'mode': 'enhanced',
        'marker_config': {
            'preserve': {
                'handshake': True,
                'application_data': False,  # 只保留头部
                'alert': True,
                'change_cipher_spec': True,
                'heartbeat': True
            }
        },
        'masker_config': {}
    }
    
    print(f"📋 配置信息:")
    print(f"   协议: {config['protocol']}")
    print(f"   模式: {config['mode']}")
    print(f"   TLS-23保留策略: {'完全保留' if config['marker_config']['preserve']['application_data'] else '仅头部'}")
    print()
    
    # 分析问题文件
    print("🚨 分析问题文件 (masked 0 pkts):")
    print("-" * 40)
    
    for i, filename in enumerate(problem_files[:3]):  # 先分析前3个
        if not Path(filename).exists():
            print(f"❌ 文件不存在: {filename}")
            continue
            
        print(f"\n📁 [{i+1}] 分析文件: {filename}")
        result = analyze_single_file(filename, config)
        print_analysis_result(result)
        
        if i == 0:  # 详细分析第一个文件
            print("\n🔬 详细诊断第一个问题文件:")
            detailed_analysis = detailed_file_analysis(filename, config)
            print_detailed_analysis(detailed_analysis)
    
    # 对比分析工作文件
    print(f"\n✅ 对比分析工作文件 (有掩码):")
    print("-" * 40)
    
    for filename in working_files[:1]:  # 分析一个工作文件
        if not Path(filename).exists():
            print(f"❌ 文件不存在: {filename}")
            continue
            
        print(f"\n📁 分析工作文件: {filename}")
        result = analyze_single_file(filename, config)
        print_analysis_result(result)

def analyze_single_file(filename: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """分析单个文件的掩码处理结果"""
    
    try:
        # 创建NewMaskPayloadStage实例
        stage = NewMaskPayloadStage(config)
        
        # 初始化
        if not stage.initialize():
            return {
                'success': False,
                'error': 'Stage初始化失败',
                'filename': filename
            }
        
        # 创建临时输出文件
        output_file = f"temp_output_{Path(filename).stem}.pcap"
        
        # 处理文件
        stats = stage.process_file(filename, output_file)
        
        # 清理临时文件
        if Path(output_file).exists():
            Path(output_file).unlink()
        
        return {
            'success': True,
            'filename': filename,
            'packets_processed': stats.packets_processed,
            'packets_modified': stats.packets_modified,
            'masking_ratio': stats.packets_modified / stats.packets_processed if stats.packets_processed > 0 else 0,
            'extra_metrics': stats.extra_metrics
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'filename': filename
        }

def detailed_file_analysis(filename: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """对文件进行详细的分步分析"""
    
    result = {
        'filename': filename,
        'marker_analysis': {},
        'masker_analysis': {},
        'integration_analysis': {}
    }
    
    try:
        # 第一步：分析Marker模块
        print("   🎯 步骤1: 分析Marker模块...")
        marker = TLSProtocolMarker(config['marker_config'])
        marker.initialize()
        
        keep_rules = marker.analyze_file(filename, config)
        
        result['marker_analysis'] = {
            'rules_generated': len(keep_rules.rules),
            'tcp_flows_found': len(keep_rules.tcp_flows),
            'metadata': keep_rules.metadata,
            'rules_summary': []
        }
        
        # 分析规则详情
        for rule in keep_rules.rules[:5]:  # 只显示前5条规则
            rule_info = {
                'stream_id': rule.stream_id,
                'direction': rule.direction,
                'seq_range': f"{rule.seq_start}-{rule.seq_end}",
                'rule_type': rule.rule_type,
                'preserve_strategy': rule.metadata.get('preserve_strategy', 'unknown')
            }
            result['marker_analysis']['rules_summary'].append(rule_info)
        
        print(f"      ✓ 生成规则数: {len(keep_rules.rules)}")
        print(f"      ✓ TCP流数: {len(keep_rules.tcp_flows)}")
        
        # 第二步：分析Masker模块
        print("   🎭 步骤2: 分析Masker模块...")
        masker = PayloadMasker(config['masker_config'])
        
        # 创建临时输出文件
        temp_output = f"temp_detailed_{Path(filename).stem}.pcap"
        
        masking_stats = masker.apply_masking(filename, temp_output, keep_rules)
        
        result['masker_analysis'] = {
            'processed_packets': masking_stats.processed_packets,
            'modified_packets': masking_stats.modified_packets,
            'masked_bytes': masking_stats.masked_bytes,
            'preserved_bytes': masking_stats.preserved_bytes,
            'success': masking_stats.success,
            'errors': masking_stats.errors,
            'warnings': masking_stats.warnings
        }
        
        print(f"      ✓ 处理包数: {masking_stats.processed_packets}")
        print(f"      ✓ 修改包数: {masking_stats.modified_packets}")
        print(f"      ✓ 掩码字节: {masking_stats.masked_bytes}")
        print(f"      ✓ 保留字节: {masking_stats.preserved_bytes}")
        
        # 清理临时文件
        if Path(temp_output).exists():
            Path(temp_output).unlink()
        
        # 第三步：集成分析
        print("   🔗 步骤3: 集成分析...")
        result['integration_analysis'] = {
            'rules_to_packets_ratio': len(keep_rules.rules) / masking_stats.processed_packets if masking_stats.processed_packets > 0 else 0,
            'masking_effectiveness': masking_stats.modified_packets / masking_stats.processed_packets if masking_stats.processed_packets > 0 else 0,
            'potential_issues': []
        }
        
        # 识别潜在问题
        if len(keep_rules.rules) == 0:
            result['integration_analysis']['potential_issues'].append("Marker模块未生成任何保留规则")
        
        if masking_stats.modified_packets == 0 and len(keep_rules.rules) > 0:
            result['integration_analysis']['potential_issues'].append("有保留规则但Masker模块未修改任何包")
        
        if masking_stats.masked_bytes == 0 and masking_stats.preserved_bytes == 0:
            result['integration_analysis']['potential_issues'].append("既没有掩码也没有保留任何字节")
        
        return result
        
    except Exception as e:
        result['error'] = str(e)
        return result

def print_analysis_result(result: Dict[str, Any]):
    """打印分析结果"""
    
    if not result['success']:
        print(f"   ❌ 分析失败: {result['error']}")
        return
    
    print(f"   📊 处理包数: {result['packets_processed']}")
    print(f"   🎭 修改包数: {result['packets_modified']}")
    print(f"   📈 掩码比例: {result['masking_ratio']:.2%}")
    
    if result['packets_modified'] == 0:
        print("   🚨 问题: 零掩码 - 没有任何包被修改")
    else:
        print("   ✅ 正常: 有包被掩码处理")

def print_detailed_analysis(result: Dict[str, Any]):
    """打印详细分析结果"""
    
    if 'error' in result:
        print(f"   ❌ 详细分析失败: {result['error']}")
        return
    
    # Marker分析结果
    marker = result['marker_analysis']
    print(f"   🎯 Marker模块:")
    print(f"      - 生成规则: {marker['rules_generated']} 条")
    print(f"      - TCP流: {marker['tcp_flows_found']} 个")
    
    if marker['rules_generated'] > 0:
        print(f"      - 规则示例:")
        for i, rule in enumerate(marker['rules_summary'][:3]):
            print(f"        [{i+1}] 流{rule['stream_id']}-{rule['direction']}: {rule['seq_range']} ({rule['rule_type']})")
    
    # Masker分析结果
    masker = result['masker_analysis']
    print(f"   🎭 Masker模块:")
    print(f"      - 处理包数: {masker['processed_packets']}")
    print(f"      - 修改包数: {masker['modified_packets']}")
    print(f"      - 掩码字节: {masker['masked_bytes']}")
    print(f"      - 保留字节: {masker['preserved_bytes']}")
    
    if masker['errors']:
        print(f"      - 错误: {masker['errors']}")
    if masker['warnings']:
        print(f"      - 警告: {masker['warnings']}")
    
    # 集成分析结果
    integration = result['integration_analysis']
    print(f"   🔗 集成分析:")
    print(f"      - 规则密度: {integration['rules_to_packets_ratio']:.3f} 规则/包")
    print(f"      - 掩码效率: {integration['masking_effectiveness']:.2%}")
    
    if integration['potential_issues']:
        print(f"      - 潜在问题:")
        for issue in integration['potential_issues']:
            print(f"        • {issue}")

if __name__ == "__main__":
    try:
        analyze_zero_masking_issue()
    except KeyboardInterrupt:
        print("\n\n⏹️  分析被用户中断")
    except Exception as e:
        print(f"\n\n❌ 分析过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
