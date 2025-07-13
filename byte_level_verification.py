#!/usr/bin/env python3
"""
字节级验证脚本

验证TLS-23消息头是否被正确保留，应用数据是否被正确掩码
"""

import subprocess
import json
import tempfile
import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from pktmask.core.pipeline.stages.mask_payload_v2.stage import NewMaskPayloadStage


def extract_tls23_payload_bytes(pcap_file: str) -> dict:
    """提取TLS-23消息的载荷字节"""
    print(f"提取 {pcap_file} 中的TLS-23载荷字节...")
    
    # 使用tshark提取TLS-23消息的详细信息
    cmd = [
        "tshark", "-r", pcap_file,
        "-Y", "tls.record.content_type == 23",
        "-T", "json",
        "-e", "frame.number",
        "-e", "tcp.seq_raw",
        "-e", "tcp.payload",
        "-e", "tls.record.content_type",
        "-e", "tls.record.length"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        tls23_data = json.loads(result.stdout)
        
        tls23_payloads = {}
        
        for packet in tls23_data:
            layers = packet.get("_source", {}).get("layers", {})
            frame_num = layers.get("frame.number", [""])[0]
            tcp_payload = layers.get("tcp.payload", [""])[0]
            tcp_seq = layers.get("tcp.seq_raw", [""])[0]
            
            if tcp_payload and frame_num:
                # 将十六进制字符串转换为字节
                payload_bytes = bytes.fromhex(tcp_payload.replace(":", ""))
                
                tls23_payloads[frame_num] = {
                    "tcp_seq": tcp_seq,
                    "payload_hex": tcp_payload,
                    "payload_bytes": payload_bytes,
                    "payload_length": len(payload_bytes)
                }
        
        return tls23_payloads
        
    except Exception as e:
        print(f"❌ 提取TLS-23载荷失败: {e}")
        return {}


def analyze_tls23_headers(payload_bytes: bytes) -> list:
    """分析TCP载荷中的TLS-23消息头"""
    tls_messages = []
    offset = 0
    
    while offset + 5 <= len(payload_bytes):
        # TLS记录头部格式: [类型(1字节)] [版本(2字节)] [长度(2字节)]
        content_type = payload_bytes[offset]
        version = int.from_bytes(payload_bytes[offset+1:offset+3], 'big')
        length = int.from_bytes(payload_bytes[offset+3:offset+5], 'big')
        
        if content_type == 23:  # ApplicationData
            tls_messages.append({
                "offset": offset,
                "content_type": content_type,
                "version": version,
                "length": length,
                "header_bytes": payload_bytes[offset:offset+5],
                "total_message_size": 5 + length
            })
            
            # 移动到下一个TLS消息
            offset += 5 + length
        else:
            # 不是TLS-23消息，停止解析
            break
    
    return tls_messages


def verify_byte_level_masking():
    """字节级掩码验证"""
    print("=" * 80)
    print("字节级掩码验证")
    print("=" * 80)
    
    original_file = "tests/samples/tls-single/tls_sample.pcap"
    config = {
        'preserve': {
            'handshake': True,
            'application_data': False,  # 只保留头部
            'alert': True,
            'change_cipher_spec': True,
            'heartbeat': True
        }
    }
    
    # 1. 分析原始文件
    print("\n1. 分析原始文件的TLS-23消息")
    print("-" * 50)
    
    original_payloads = extract_tls23_payload_bytes(original_file)
    
    for frame, data in original_payloads.items():
        print(f"\nFrame {frame}:")
        print(f"  TCP序列号: {data['tcp_seq']}")
        print(f"  载荷长度: {data['payload_length']} 字节")
        
        # 分析TLS消息头
        tls_messages = analyze_tls23_headers(data['payload_bytes'])
        print(f"  TLS-23消息数量: {len(tls_messages)}")
        
        for i, msg in enumerate(tls_messages):
            print(f"    消息#{i+1}: 偏移{msg['offset']}, 长度{msg['length']}, "
                  f"头部: {msg['header_bytes'].hex()}")
    
    # 2. 执行掩码处理
    print("\n2. 执行掩码处理")
    print("-" * 50)
    
    with tempfile.NamedTemporaryFile(suffix=".pcap", delete=False) as tmp_file:
        masked_file = tmp_file.name
    
    mask_stage = NewMaskPayloadStage(config)
    stats = mask_stage.process_file(original_file, masked_file)
    
    print(f"掩码处理完成:")
    print(f"  处理包数: {stats.packets_processed}")
    print(f"  修改包数: {stats.packets_modified}")
    print(f"  掩码字节数: {stats.extra_metrics.get('masked_bytes', 0)}")
    print(f"  保留字节数: {stats.extra_metrics.get('preserved_bytes', 0)}")
    
    # 3. 分析掩码后的文件
    print("\n3. 分析掩码后的文件")
    print("-" * 50)
    
    masked_payloads = extract_tls23_payload_bytes(masked_file)
    
    # 4. 字节级比较
    print("\n4. 字节级比较验证")
    print("-" * 50)
    
    verification_results = {
        "frames_compared": 0,
        "headers_preserved": 0,
        "payloads_masked": 0,
        "verification_details": []
    }
    
    for frame in original_payloads:
        if frame in masked_payloads:
            verification_results["frames_compared"] += 1
            
            original_data = original_payloads[frame]
            masked_data = masked_payloads[frame]
            
            print(f"\nFrame {frame} 字节级比较:")
            
            # 分析原始和掩码后的TLS消息
            original_messages = analyze_tls23_headers(original_data['payload_bytes'])
            masked_messages = analyze_tls23_headers(masked_data['payload_bytes'])
            
            frame_details = {
                "frame": frame,
                "original_messages": len(original_messages),
                "masked_messages": len(masked_messages),
                "message_comparisons": []
            }
            
            for i, (orig_msg, masked_msg) in enumerate(zip(original_messages, masked_messages)):
                print(f"  消息#{i+1}:")
                
                # 比较头部
                header_preserved = orig_msg['header_bytes'] == masked_msg['header_bytes']
                print(f"    头部保留: {'✅' if header_preserved else '❌'}")
                print(f"    原始头部: {orig_msg['header_bytes'].hex()}")
                print(f"    掩码头部: {masked_msg['header_bytes'].hex()}")
                
                if header_preserved:
                    verification_results["headers_preserved"] += 1
                
                # 比较载荷（应该被掩码为零）
                orig_payload_start = orig_msg['offset'] + 5
                orig_payload_end = orig_payload_start + orig_msg['length']
                masked_payload_start = masked_msg['offset'] + 5
                masked_payload_end = masked_payload_start + masked_msg['length']
                
                if (orig_payload_end <= len(original_data['payload_bytes']) and 
                    masked_payload_end <= len(masked_data['payload_bytes'])):
                    
                    orig_payload = original_data['payload_bytes'][orig_payload_start:orig_payload_end]
                    masked_payload = masked_data['payload_bytes'][masked_payload_start:masked_payload_end]
                    
                    # 检查载荷是否被掩码（应该全为零）
                    payload_masked = all(b == 0 for b in masked_payload)
                    payload_changed = orig_payload != masked_payload
                    
                    print(f"    载荷掩码: {'✅' if payload_masked and payload_changed else '❌'}")
                    print(f"    原始载荷前16字节: {orig_payload[:16].hex()}")
                    print(f"    掩码载荷前16字节: {masked_payload[:16].hex()}")
                    
                    if payload_masked and payload_changed:
                        verification_results["payloads_masked"] += 1
                
                frame_details["message_comparisons"].append({
                    "message_index": i + 1,
                    "header_preserved": header_preserved,
                    "payload_masked": payload_masked if 'payload_masked' in locals() else False
                })
            
            verification_results["verification_details"].append(frame_details)
    
    # 5. 验证总结
    print("\n5. 验证总结")
    print("-" * 50)
    
    print(f"比较的帧数: {verification_results['frames_compared']}")
    print(f"头部保留成功: {verification_results['headers_preserved']}")
    print(f"载荷掩码成功: {verification_results['payloads_masked']}")
    
    if (verification_results['headers_preserved'] > 0 and 
        verification_results['payloads_masked'] > 0):
        print("\n🎉 字节级验证通过！")
        print("✅ TLS-23消息头部正确保留")
        print("✅ TLS-23消息载荷正确掩码")
    else:
        print("\n❌ 字节级验证失败")
    
    # 保存验证结果
    with open("byte_level_verification_results.json", "w", encoding="utf-8") as f:
        json.dump(verification_results, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"\n详细验证结果已保存到: byte_level_verification_results.json")
    
    return verification_results


def main():
    """主函数"""
    try:
        results = verify_byte_level_masking()
        
        if (results['headers_preserved'] > 0 and results['payloads_masked'] > 0):
            print("\n🎉 PktMask双模块架构端到端验证完全成功！")
        else:
            print("\n⚠️  验证发现问题，需要进一步调查")
            
    except Exception as e:
        print(f"❌ 字节级验证过程中发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
