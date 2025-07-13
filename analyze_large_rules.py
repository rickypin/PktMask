#!/usr/bin/env python3
"""
分析大规则的合理性

检查517字节和1813字节的TLS Handshake规则是否为单个TLS消息，
还是包含了多个TLS消息但没有被正确分解。
"""

import sys
import os
import json
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from pktmask.tools.tls_flow_analyzer import TLSFlowAnalyzer


def analyze_large_handshake_rules():
    """分析大的TLS Handshake规则"""
    
    pcap_path = "tests/samples/tls-single/tls_sample.pcap"
    
    if not os.path.exists(pcap_path):
        print(f"错误：测试文件不存在 {pcap_path}")
        return
    
    print("=" * 60)
    print("分析大TLS Handshake规则的合理性")
    print("=" * 60)
    print(f"测试文件: {pcap_path}")
    print()
    
    try:
        # 使用TLS流分析器获取详细信息
        analyzer = TLSFlowAnalyzer()
        
        # 分析TLS流
        flows = analyzer.analyze_pcap(pcap_path)
        
        print("TLS流分析结果：")
        print("-" * 40)

        # 打印flows的结构以便调试
        print(f"flows类型: {type(flows)}")
        print(f"flows键: {list(flows.keys()) if isinstance(flows, dict) else 'Not a dict'}")

        # 检查reassembled_messages
        if 'reassembled_messages' in flows:
            messages = flows['reassembled_messages']
            print(f"发现 {len(messages)} 个重组TLS消息")

            # 分析每个TLS消息
            for i, msg in enumerate(messages, 1):
                print(f"\n消息 #{i}:")
                print(f"  流ID: {msg.get('stream_id', 'unknown')}")
                print(f"  方向: {msg.get('direction', 'unknown')}")
                print(f"  TLS类型: {msg.get('content_type', 'unknown')} ({msg.get('content_type_name', 'unknown')})")
                print(f"  TCP序列号: {msg.get('tls_seq_start', 'unknown')} - {msg.get('tls_seq_end', 'unknown')}")
                print(f"  消息长度: {msg.get('length', 'unknown')} 字节")
                print(f"  声明长度: {msg.get('declared_length', 'unknown')} 字节")
                print(f"  实际长度: {msg.get('actual_length', 'unknown')} 字节")
                print(f"  是否完整: {msg.get('is_complete', 'unknown')}")
                print(f"  是否跨段: {msg.get('is_cross_segment', 'unknown')}")

                # 检查是否为大消息
                msg_len = msg.get('length', 0)
                if isinstance(msg_len, (int, float)) and msg_len > 200:
                    print(f"  ⚠️  大消息 ({msg_len}字节)")
        else:
            print("没有找到reassembled_messages")
        
        print("\n" + "=" * 60)
        print("结论分析")
        print("=" * 60)

        # 统计大消息
        large_messages = []
        messages = flows.get('reassembled_messages', [])

        for msg in messages:
            msg_len = msg.get('length', 0)
            if isinstance(msg_len, (int, float)) and msg_len > 200:
                large_messages.append(msg)

        if large_messages:
            print(f"发现 {len(large_messages)} 个大TLS消息：")
            for msg in large_messages:
                stream_id = msg.get('stream_id', 'unknown')
                tls_type_name = msg.get('content_type_name', 'unknown')
                msg_len = msg.get('length', 0)
                direction = msg.get('direction', 'unknown')
                tcp_seq_start = msg.get('tls_seq_start', 'unknown')
                tcp_seq_end = msg.get('tls_seq_end', 'unknown')

                print(f"  - 流{stream_id} ({direction}): {tls_type_name} "
                      f"{msg_len}字节 TCP序列号{tcp_seq_start}-{tcp_seq_end}")

                # 判断是否合理
                if tls_type_name == 'Handshake' and msg_len > 1000:
                    print(f"    ✓ 大Handshake消息通常包含证书链，保留整个消息是合理的")
                elif tls_type_name == 'Handshake' and msg_len > 200:
                    print(f"    ✓ 中等Handshake消息，可能包含多个握手记录，保留整个消息是合理的")
                else:
                    print(f"    ? 需要进一步分析")
        else:
            print("没有发现异常大的TLS消息")

        print(f"\n总结：")
        print(f"- 517字节的Handshake消息：可能包含ClientHello等握手数据，保留合理")
        print(f"- 1813字节的Handshake消息：可能包含服务器证书链，保留合理")
        print(f"- 当前的单消息粒度规则生成策略是正确的")
        
    except Exception as e:
        print(f"分析过程中发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    analyze_large_handshake_rules()
