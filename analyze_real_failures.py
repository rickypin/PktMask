#!/usr/bin/env python3
"""
基于验证报告的实际失败案例分析
分析tls_1_0_multi_segment_google-https.pcap和tls_1_2_double_vlan.pcap的具体失败原因
"""

import subprocess
import json
import sys
from pathlib import Path

def analyze_frame_with_tshark(pcap_file, frame_number):
    """使用tshark分析特定帧"""
    print(f"\n=== 分析 {pcap_file} 帧 {frame_number} ===")
    
    # 获取帧的详细信息
    cmd = [
        'tshark', '-r', pcap_file, 
        '-Y', f'frame.number=={frame_number}',
        '-T', 'json', '-V'
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        if not result.stdout.strip():
            print(f"未找到帧 {frame_number}")
            return None
            
        frame_data = json.loads(result.stdout)[0]
        layers = frame_data['_source']['layers']
        
        print(f"协议栈: {' -> '.join(layers.keys())}")
        
        # 分析TCP信息
        if 'tcp' in layers:
            tcp = layers['tcp']
            print(f"TCP序列号: {tcp.get('tcp.seq_raw', 'N/A')}")
            print(f"TCP载荷长度: {tcp.get('tcp.len', 'N/A')}")
            
        # 分析TLS层
        tls_keys = [k for k in layers.keys() if k.startswith('tls')]
        print(f"TLS层数量: {len(tls_keys)}")
        
        for i, tls_key in enumerate(tls_keys):
            tls = layers[tls_key]
            content_type = tls.get('tls.record.content_type')
            length = tls.get('tls.record.length')
            print(f"  TLS层{i+1}: 类型={content_type}, 长度={length}")
            
        return frame_data
        
    except Exception as e:
        print(f"tshark分析失败: {e}")
        return None

def get_tcp_payload_hex(pcap_file, frame_number):
    """获取TCP载荷的十六进制数据"""
    cmd = [
        'tshark', '-r', pcap_file,
        '-Y', f'frame.number=={frame_number}',
        '-T', 'fields', '-e', 'tcp.payload'
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        payload_hex = result.stdout.strip()
        
        if payload_hex:
            print(f"TCP载荷长度: {len(payload_hex)//2} 字节")
            print(f"载荷前32字节: {payload_hex[:64]}")
            
            # 分析TLS记录结构
            offset = 0
            record_num = 0
            while offset + 10 <= len(payload_hex):
                try:
                    content_type = int(payload_hex[offset:offset+2], 16)
                    version = payload_hex[offset+2:offset+6]
                    length = int(payload_hex[offset+6:offset+10], 16)
                    
                    record_num += 1
                    print(f"  TLS记录{record_num}: 类型={content_type}, 版本=0x{version}, 长度={length}")
                    
                    if content_type == 23:
                        print(f"    -> ApplicationData记录，应该被掩码")
                    else:
                        print(f"    -> 非ApplicationData记录，应该被保留")
                        
                    offset += 10 + length * 2
                except ValueError:
                    break
                    
        return payload_hex
        
    except Exception as e:
        print(f"载荷分析失败: {e}")
        return None

def analyze_marker_rules(pcap_file):
    """分析Marker模块生成的规则"""
    print(f"\n=== 分析Marker规则 {pcap_file} ===")

    try:
        # 添加项目路径
        project_root = Path(__file__).parent
        sys.path.insert(0, str(project_root / "src"))
        from pktmask.core.pipeline.stages.mask_payload_v2.marker import TLSProtocolMarker

        # 创建默认配置
        config = {
            'preserve': {
                'handshake': True,
                'application_data': False,
                'alert': True,
                'change_cipher_spec': True,
                'heartbeat': True
            },
            'tshark_path': None,
            'decode_as': []
        }

        marker = TLSProtocolMarker(config)
        keep_rules = marker.analyze_file(pcap_file, config)
        
        print(f"生成的保留规则数: {len(keep_rules.rules)}")
        
        # 按流分组
        flows = {}
        for rule in keep_rules.rules:
            flow_key = f"{rule.stream_id}:{rule.direction}"
            if flow_key not in flows:
                flows[flow_key] = []
            flows[flow_key].append(rule)

        for flow_key, rules in flows.items():
            print(f"\n流 {flow_key} ({len(rules)} 规则):")
            for i, rule in enumerate(rules[:5]):  # 只显示前5个规则
                print(f"  规则{i+1}: [{rule.seq_start}, {rule.seq_end}) 类型={rule.rule_type}")
            if len(rules) > 5:
                print(f"  ... 还有 {len(rules)-5} 个规则")
                
        return keep_rules
        
    except Exception as e:
        print(f"Marker分析失败: {e}")
        return None

def check_masker_application(pcap_file, frame_number, keep_rules):
    """检查Masker模块对特定帧的处理"""
    print(f"\n=== 检查Masker对帧{frame_number}的处理 ===")
    
    # 获取帧的TCP信息
    cmd = [
        'tshark', '-r', pcap_file,
        '-Y', f'frame.number=={frame_number}',
        '-T', 'fields', 
        '-e', 'ip.src', '-e', 'ip.dst',
        '-e', 'tcp.srcport', '-e', 'tcp.dstport',
        '-e', 'tcp.seq_raw', '-e', 'tcp.len'
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        fields = result.stdout.strip().split('\t')
        
        if len(fields) >= 6:
            src_ip, dst_ip, src_port, dst_port, seq_raw, tcp_len = fields
            
            print(f"帧信息: {src_ip}:{src_port} -> {dst_ip}:{dst_port}")
            print(f"TCP序列号: {seq_raw}, 载荷长度: {tcp_len}")
            
            # 检查是否有匹配的保留规则
            seq_start = int(seq_raw)
            seq_end = seq_start + int(tcp_len)
            
            matching_rules = []

            # 构建流标识（需要查看实际的流信息）
            for stream_id, flow_info in keep_rules.tcp_flows.items():
                # 检查是否匹配当前帧的流
                if ((flow_info.src_ip == src_ip and flow_info.dst_ip == dst_ip and
                     flow_info.src_port == int(src_port) and flow_info.dst_port == int(dst_port)) or
                    (flow_info.src_ip == dst_ip and flow_info.dst_ip == src_ip and
                     flow_info.src_port == int(dst_port) and flow_info.dst_port == int(src_port))):

                    # 找到匹配的流，检查该流的规则
                    for rule in keep_rules.rules:
                        if rule.stream_id == stream_id:
                            # 检查序列号范围重叠
                            if not (seq_end <= rule.seq_start or seq_start >= rule.seq_end):
                                matching_rules.append(rule)
                        
            print(f"匹配的保留规则数: {len(matching_rules)}")
            for i, rule in enumerate(matching_rules):
                overlap_start = max(seq_start, rule.seq_start)
                overlap_end = min(seq_end, rule.seq_end)
                overlap_len = max(0, overlap_end - overlap_start)
                print(f"  规则{i+1}: [{rule.seq_start}, {rule.seq_end}) 类型={rule.rule_type}, 重叠长度: {overlap_len}")
                
            return matching_rules
            
    except Exception as e:
        print(f"Masker检查失败: {e}")
        return []

def main():
    """主分析函数"""
    print("PktMask Maskstage 实际失败案例分析")
    print("=" * 60)
    
    # 基于验证报告的实际失败案例
    cases = [
        {
            'file': 'tests/data/tls/tls_1_0_multi_segment_google-https.pcap',
            'frame': 150,
            'description': '跨TLS层问题 (tls:tls)'
        },
        {
            'file': 'tests/data/tls/tls_1_2_double_vlan.pcap',
            'frame': 144, 
            'description': '双VLAN环境掩码失效'
        }
    ]
    
    for case in cases:
        pcap_file = case['file']
        frame_number = case['frame']
        
        print(f"\n{'='*80}")
        print(f"案例: {case['description']}")
        print(f"文件: {pcap_file}")
        print(f"失败帧: {frame_number}")
        print(f"{'='*80}")
        
        if not Path(pcap_file).exists():
            print(f"文件不存在: {pcap_file}")
            continue
            
        # 1. 分析失败帧的详细信息
        frame_data = analyze_frame_with_tshark(pcap_file, frame_number)
        
        # 2. 分析TCP载荷
        payload_hex = get_tcp_payload_hex(pcap_file, frame_number)
        
        # 3. 分析Marker规则
        keep_rules = analyze_marker_rules(pcap_file)
        
        # 4. 检查Masker应用
        if keep_rules:
            matching_rules = check_masker_application(pcap_file, frame_number, keep_rules)
            
        print(f"\n{'-'*60}")
        print("分析完成")

if __name__ == '__main__':
    main()
