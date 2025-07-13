#!/usr/bin/env python3
"""
测试脚本：运行Marker模块并输出KeepRuleSet详细信息
用于人工检验Marker模块生成的保留规则
"""

import sys
import json
import logging
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from pktmask.core.pipeline.stages.mask_payload_v2.marker.tls_marker import TLSProtocolMarker
from pktmask.core.pipeline.stages.mask_payload_v2.marker.types import KeepRule, KeepRuleSet


def setup_logging():
    """设置日志"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def print_separator(title: str):
    """打印分隔符"""
    print("\n" + "=" * 80)
    print(f" {title}")
    print("=" * 80)


def print_keep_rule(rule: KeepRule, index: int):
    """打印单个保留规则的详细信息"""
    print(f"\n规则 #{index + 1}:")
    print(f"  流标识: {rule.stream_id}")
    print(f"  方向: {rule.direction}")
    print(f"  序列号范围: {rule.seq_start} - {rule.seq_end} (长度: {rule.seq_end - rule.seq_start})")
    print(f"  规则类型: {rule.rule_type}")
    if rule.metadata:
        print(f"  元数据: {json.dumps(rule.metadata, indent=4, ensure_ascii=False)}")


def print_flow_info(flows: dict):
    """打印TCP流信息"""
    print_separator("TCP流信息")
    
    if not flows:
        print("未发现TCP流信息")
        return
    
    for stream_id, flow_info in flows.items():
        print(f"\n流 {stream_id}:")
        print(f"  源地址: {flow_info.src_ip}:{flow_info.src_port}")
        print(f"  目标地址: {flow_info.dst_ip}:{flow_info.dst_port}")
        print(f"  协议: {flow_info.protocol}")
        print(f"  方向: {flow_info.direction}")
        print(f"  数据包数: {flow_info.packet_count}")
        print(f"  字节数: {flow_info.byte_count}")
        print(f"  首次出现: {flow_info.first_seen}")
        print(f"  最后出现: {flow_info.last_seen}")
        if flow_info.metadata:
            print(f"  元数据: {json.dumps(flow_info.metadata, indent=4, ensure_ascii=False)}")


def print_statistics(stats: dict):
    """打印统计信息"""
    print_separator("统计信息")
    
    if not stats:
        print("无统计信息")
        return
    
    for key, value in stats.items():
        print(f"  {key}: {value}")


def print_metadata(metadata: dict):
    """打印元数据"""
    print_separator("元数据信息")
    
    if not metadata:
        print("无元数据")
        return
    
    for key, value in metadata.items():
        if key == 'preserve_config':
            print(f"  {key}:")
            for sub_key, sub_value in value.items():
                print(f"    {sub_key}: {sub_value}")
        else:
            print(f"  {key}: {value}")


def analyze_rules_by_type(rules: list):
    """按规则类型分析保留规则"""
    print_separator("规则类型分析")
    
    rule_types = {}
    total_preserved_bytes = 0
    
    for rule in rules:
        rule_type = rule.rule_type
        if rule_type not in rule_types:
            rule_types[rule_type] = {
                'count': 0,
                'total_bytes': 0,
                'rules': []
            }
        
        rule_length = rule.seq_end - rule.seq_start
        rule_types[rule_type]['count'] += 1
        rule_types[rule_type]['total_bytes'] += rule_length
        rule_types[rule_type]['rules'].append(rule)
        total_preserved_bytes += rule_length
    
    print(f"总保留字节数: {total_preserved_bytes}")
    print(f"规则类型统计:")
    
    for rule_type, info in rule_types.items():
        print(f"\n  {rule_type}:")
        print(f"    规则数量: {info['count']}")
        print(f"    保留字节数: {info['total_bytes']}")
        print(f"    平均规则长度: {info['total_bytes'] / info['count']:.2f}")
        
        # 显示该类型的前3个规则
        print(f"    示例规则:")
        for i, rule in enumerate(info['rules'][:3]):
            print(f"      规则{i+1}: 流{rule.stream_id} {rule.direction} "
                  f"[{rule.seq_start}-{rule.seq_end}] 长度{rule.seq_end - rule.seq_start}")


def analyze_rules_by_stream(rules: list):
    """按流分析保留规则"""
    print_separator("流分析")
    
    streams = {}
    
    for rule in rules:
        stream_key = f"{rule.stream_id}_{rule.direction}"
        if stream_key not in streams:
            streams[stream_key] = {
                'rules': [],
                'total_bytes': 0
            }
        
        streams[stream_key]['rules'].append(rule)
        streams[stream_key]['total_bytes'] += (rule.seq_end - rule.seq_start)
    
    for stream_key, info in streams.items():
        stream_id, direction = stream_key.split('_')
        print(f"\n流 {stream_id} ({direction}):")
        print(f"  规则数量: {len(info['rules'])}")
        print(f"  保留字节数: {info['total_bytes']}")
        
        # 按序列号排序显示规则
        sorted_rules = sorted(info['rules'], key=lambda r: r.seq_start)
        print(f"  规则序列:")
        for i, rule in enumerate(sorted_rules):
            print(f"    {i+1}. [{rule.seq_start}-{rule.seq_end}] {rule.rule_type} "
                  f"(长度: {rule.seq_end - rule.seq_start})")


def main():
    """主函数"""
    setup_logging()
    
    # 测试文件路径
    pcap_path = "tests/samples/tls-single/tls_sample.pcap"
    
    print_separator("PktMask Marker模块测试 - KeepRuleSet输出")
    print(f"测试文件: {pcap_path}")
    
    # 检查文件是否存在
    if not Path(pcap_path).exists():
        print(f"错误: 测试文件不存在: {pcap_path}")
        return 1
    
    # 创建TLS标记器配置
    marker_config = {
        'preserve': {
            'handshake': True,
            'application_data': False,  # 只保留头部
            'alert': True,
            'change_cipher_spec': True,
            'heartbeat': True
        },
        'tshark_path': None,  # 使用系统默认
        'decode_as': []
    }
    
    print(f"Marker配置:")
    print(json.dumps(marker_config, indent=2, ensure_ascii=False))
    
    try:
        # 创建TLS标记器
        print_separator("初始化TLS标记器")
        marker = TLSProtocolMarker(marker_config)
        
        # 分析文件
        print_separator("分析PCAP文件")
        print("正在分析文件，请稍候...")
        
        ruleset = marker.analyze_file(pcap_path, {})
        
        # 输出结果
        print_separator("KeepRuleSet详细信息")
        print(f"规则总数: {len(ruleset.rules)}")
        
        # 打印元数据
        print_metadata(ruleset.metadata)
        
        # 打印TCP流信息
        print_flow_info(ruleset.tcp_flows)
        
        # 打印统计信息
        print_statistics(ruleset.statistics)
        
        # 按类型分析规则
        if ruleset.rules:
            analyze_rules_by_type(ruleset.rules)
            analyze_rules_by_stream(ruleset.rules)
            
            # 打印所有规则详情
            print_separator("所有保留规则详情")
            for i, rule in enumerate(ruleset.rules):
                print_keep_rule(rule, i)
        else:
            print("\n未生成任何保留规则!")
        
        # 输出JSON格式（用于进一步分析）
        print_separator("JSON格式输出")
        try:
            # 手动构建字典格式
            ruleset_dict = {
                'rules': [
                    {
                        'stream_id': rule.stream_id,
                        'direction': rule.direction,
                        'seq_start': rule.seq_start,
                        'seq_end': rule.seq_end,
                        'rule_type': rule.rule_type,
                        'metadata': rule.metadata
                    }
                    for rule in ruleset.rules
                ],
                'tcp_flows': {
                    stream_id: {
                        'stream_id': flow.stream_id,
                        'src_ip': flow.src_ip,
                        'dst_ip': flow.dst_ip,
                        'src_port': flow.src_port,
                        'dst_port': flow.dst_port,
                        'protocol': flow.protocol,
                        'direction': flow.direction,
                        'packet_count': flow.packet_count,
                        'byte_count': flow.byte_count,
                        'first_seen': flow.first_seen,
                        'last_seen': flow.last_seen,
                        'metadata': flow.metadata
                    }
                    for stream_id, flow in ruleset.tcp_flows.items()
                },
                'statistics': ruleset.statistics,
                'metadata': ruleset.metadata
            }
            print(json.dumps(ruleset_dict, indent=2, ensure_ascii=False))
        except Exception as e:
            print(f"JSON序列化错误: {e}")
            print("原始对象信息:")
            print(f"  规则数量: {len(ruleset.rules)}")
            print(f"  流数量: {len(ruleset.tcp_flows)}")
            print(f"  统计信息: {ruleset.statistics}")
            print(f"  元数据: {ruleset.metadata}")
        
        print_separator("测试完成")
        return 0
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
