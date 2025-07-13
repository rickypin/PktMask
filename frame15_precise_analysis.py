#!/usr/bin/env python3
"""
Frame 15精确分析

详细分析Frame 15的TLS-23消息载荷，确定哪些字节应该被掩码
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


def analyze_frame15_precise():
    """精确分析Frame 15"""
    print("=" * 80)
    print("Frame 15精确分析")
    print("=" * 80)
    
    test_file = "tests/samples/tls-single/tls_sample.pcap"
    config = {
        'preserve': {
            'handshake': True,
            'application_data': False,  # 只保留头部
            'alert': True,
            'change_cipher_spec': True,
            'heartbeat': True
        }
    }
    
    # 1. 提取Frame 15的原始载荷
    print("\n1. 提取Frame 15的原始载荷")
    print("-" * 50)
    
    cmd = [
        "tshark", "-r", test_file,
        "-Y", "frame.number == 15",
        "-T", "json",
        "-e", "tcp.payload"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        frame_data = json.loads(result.stdout)[0]
        tcp_payload_hex = frame_data["_source"]["layers"]["tcp.payload"][0]
        original_payload = bytes.fromhex(tcp_payload_hex.replace(":", ""))
        
        print(f"Frame 15原始载荷长度: {len(original_payload)} 字节")
        print(f"完整载荷: {original_payload.hex()}")
        
        # 分析TLS消息结构
        print(f"\nTLS消息结构分析:")
        print(f"前5字节 (TLS头部): {original_payload[:5].hex()}")
        print(f"第6-111字节 (TLS载荷): {original_payload[5:].hex()}")
        
        # 分析载荷中的零字节和非零字节
        tls_payload = original_payload[5:]  # 跳过5字节头部
        zero_bytes = 0
        non_zero_bytes = 0
        first_non_zero_pos = None
        
        for i, byte in enumerate(tls_payload):
            if byte == 0:
                zero_bytes += 1
            else:
                non_zero_bytes += 1
                if first_non_zero_pos is None:
                    first_non_zero_pos = i
        
        print(f"\nTLS载荷分析:")
        print(f"  总长度: {len(tls_payload)} 字节")
        print(f"  零字节: {zero_bytes} 个")
        print(f"  非零字节: {non_zero_bytes} 个")
        print(f"  第一个非零字节位置: {first_non_zero_pos}")
        
        if first_non_zero_pos is not None:
            print(f"  前{first_non_zero_pos}字节: {tls_payload[:first_non_zero_pos].hex()} (全零)")
            print(f"  从位置{first_non_zero_pos}开始: {tls_payload[first_non_zero_pos:first_non_zero_pos+16].hex()}")
        
    except Exception as e:
        print(f"❌ 原始载荷提取失败: {e}")
        return None
    
    # 2. 执行掩码处理
    print("\n2. 执行掩码处理")
    print("-" * 50)
    
    with tempfile.NamedTemporaryFile(suffix=".pcap", delete=False) as tmp_file:
        masked_file = tmp_file.name
    
    mask_stage = NewMaskPayloadStage(config)
    stats = mask_stage.process_file(test_file, masked_file)
    
    print(f"掩码处理完成")
    
    # 3. 提取掩码后的Frame 15载荷
    print("\n3. 提取掩码后的Frame 15载荷")
    print("-" * 50)
    
    cmd_masked = [
        "tshark", "-r", masked_file,
        "-Y", "frame.number == 15",
        "-T", "json",
        "-e", "tcp.payload"
    ]
    
    try:
        result_masked = subprocess.run(cmd_masked, capture_output=True, text=True, check=True)
        masked_data = json.loads(result_masked.stdout)[0]
        tcp_payload_hex_masked = masked_data["_source"]["layers"]["tcp.payload"][0]
        masked_payload = bytes.fromhex(tcp_payload_hex_masked.replace(":", ""))
        
        print(f"Frame 15掩码后载荷长度: {len(masked_payload)} 字节")
        print(f"完整载荷: {masked_payload.hex()}")
        
        # 分析掩码后的TLS消息结构
        print(f"\n掩码后TLS消息结构:")
        print(f"前5字节 (TLS头部): {masked_payload[:5].hex()}")
        print(f"第6-111字节 (TLS载荷): {masked_payload[5:].hex()}")
        
    except Exception as e:
        print(f"❌ 掩码后载荷提取失败: {e}")
        return None
    
    # 4. 字节级比较
    print("\n4. 字节级比较")
    print("-" * 50)
    
    # 比较头部
    original_header = original_payload[:5]
    masked_header = masked_payload[:5]
    header_preserved = original_header == masked_header
    
    print(f"TLS头部比较:")
    print(f"  原始: {original_header.hex()}")
    print(f"  掩码: {masked_header.hex()}")
    print(f"  保留: {'✅' if header_preserved else '❌'}")
    
    # 比较载荷
    original_tls_payload = original_payload[5:]
    masked_tls_payload = masked_payload[5:]
    
    print(f"\nTLS载荷比较:")
    print(f"  原始长度: {len(original_tls_payload)} 字节")
    print(f"  掩码长度: {len(masked_tls_payload)} 字节")
    
    # 逐字节比较
    changed_bytes = 0
    unchanged_bytes = 0
    
    for i, (orig, masked) in enumerate(zip(original_tls_payload, masked_tls_payload)):
        if orig != masked:
            changed_bytes += 1
        else:
            unchanged_bytes += 1
    
    print(f"  变化字节: {changed_bytes} 个")
    print(f"  未变化字节: {unchanged_bytes} 个")
    
    # 检查是否正确掩码
    if changed_bytes == 0:
        print(f"  ❌ 载荷未被掩码")
        
        # 分析为什么没有被掩码
        print(f"\n问题分析:")
        if non_zero_bytes == 0:
            print(f"  - 原始载荷本身就全为零，无需掩码")
        else:
            print(f"  - 原始载荷有{non_zero_bytes}个非零字节，但未被掩码")
            print(f"  - 这表明掩码规则没有正确应用到Frame 15")
    else:
        print(f"  ✅ 载荷已被掩码")
        
        # 检查是否正确掩码为零
        all_zero = all(b == 0 for b in masked_tls_payload)
        print(f"  全零掩码: {'✅' if all_zero else '❌'}")
    
    # 5. 详细的字节位置分析
    print("\n5. 详细字节位置分析")
    print("-" * 50)
    
    print("字节位置分析 (显示前32字节):")
    for i in range(min(32, len(original_tls_payload))):
        orig_byte = original_tls_payload[i]
        masked_byte = masked_tls_payload[i]
        status = "✅" if orig_byte == masked_byte else "❌"
        
        if i < 16:  # 只显示前16字节的详细信息
            print(f"  位置{i:2d}: {orig_byte:02x} -> {masked_byte:02x} {status}")
    
    return {
        "original_payload": original_payload.hex(),
        "masked_payload": masked_payload.hex(),
        "header_preserved": header_preserved,
        "tls_payload_changed": changed_bytes > 0,
        "changed_bytes": changed_bytes,
        "unchanged_bytes": unchanged_bytes,
        "non_zero_bytes_in_original": non_zero_bytes,
        "first_non_zero_position": first_non_zero_pos
    }


def main():
    """主函数"""
    try:
        results = analyze_frame15_precise()
        
        if results:
            # 保存分析结果
            with open("frame15_precise_analysis_results.json", "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False, default=str)
            
            print(f"\n详细分析结果已保存到: frame15_precise_analysis_results.json")
        
    except Exception as e:
        print(f"❌ Frame 15精确分析过程中发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
