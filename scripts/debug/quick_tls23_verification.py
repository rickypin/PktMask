#!/usr/bin/env python3
"""
快速TLS-23掩码效果验证脚本

本脚本提供快速验证TLS-23 ApplicationData掩码效果的功能，
专门用于GUI操作后的结果验证。

使用方法：
    python scripts/debug/quick_tls23_verification.py <processed_pcap_file>
"""

import sys
from pathlib import Path
from typing import Dict, List, Any

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

def quick_verify_tls23_masking(pcap_file: str) -> Dict[str, Any]:
    """快速验证TLS-23掩码效果"""
    print(f"🔍 快速验证TLS-23掩码效果: {pcap_file}")
    print("="*60)
    
    try:
        # 使用scapy进行快速分析
        from scapy.all import rdpcap, TCP
        from scapy.layers.tls.record import TLS
        
        packets = rdpcap(pcap_file)
        
        tls23_stats = {
            "total_tls23_messages": 0,
            "masked_tls23_messages": 0,
            "unmasked_tls23_messages": 0,
            "sample_unmasked_data": [],
            "tcp_streams": set()
        }
        
        print("📊 分析TLS-23消息...")
        
        for packet in packets:
            if TCP in packet and TLS in packet:
                # 提取TCP流标识
                stream_id = f"{packet[TCP].sport}-{packet[TCP].dport}"
                tls23_stats["tcp_streams"].add(stream_id)
                
                # 检查TLS记录
                tls_layer = packet[TLS]
                while tls_layer:
                    if hasattr(tls_layer, 'type') and tls_layer.type == 23:  # ApplicationData
                        tls23_stats["total_tls23_messages"] += 1
                        
                        # 检查payload是否被掩码
                        if hasattr(tls_layer, 'msg') and tls_layer.msg:
                            payload_data = bytes(tls_layer.msg)
                            
                            # 检查是否全零（被掩码）
                            if all(b == 0 for b in payload_data):
                                tls23_stats["masked_tls23_messages"] += 1
                            else:
                                tls23_stats["unmasked_tls23_messages"] += 1
                                # 保存未掩码数据样本（前16字节）
                                if len(tls23_stats["sample_unmasked_data"]) < 5:
                                    sample = payload_data[:16]
                                    tls23_stats["sample_unmasked_data"].append({
                                        "stream": stream_id,
                                        "data_hex": sample.hex(),
                                        "data_preview": repr(sample[:8])
                                    })
                    
                    # 移动到下一个TLS层
                    tls_layer = tls_layer.payload if hasattr(tls_layer, 'payload') else None
        
        # 计算掩码成功率
        total_messages = tls23_stats["total_tls23_messages"]
        masked_messages = tls23_stats["masked_tls23_messages"]
        success_rate = masked_messages / total_messages if total_messages > 0 else 0.0
        
        tls23_stats["masking_success_rate"] = success_rate
        tls23_stats["tcp_stream_count"] = len(tls23_stats["tcp_streams"])
        
        # 输出结果
        print(f"📈 验证结果:")
        print(f"   - TCP流数量: {tls23_stats['tcp_stream_count']}")
        print(f"   - TLS-23消息总数: {total_messages}")
        print(f"   - 已掩码消息数: {masked_messages}")
        print(f"   - 未掩码消息数: {tls23_stats['unmasked_tls23_messages']}")
        print(f"   - 掩码成功率: {success_rate:.2%}")
        
        if success_rate < 1.0:
            print(f"\n⚠️ 发现未掩码的TLS-23消息！")
            print(f"📋 未掩码数据样本:")
            for i, sample in enumerate(tls23_stats["sample_unmasked_data"], 1):
                print(f"   {i}. 流 {sample['stream']}: {sample['data_hex']} ({sample['data_preview']})")
        else:
            print(f"\n✅ 所有TLS-23消息都已正确掩码！")
        
        return tls23_stats
        
    except ImportError:
        print("❌ 缺少scapy依赖，尝试使用备用方法...")
        return _fallback_verification(pcap_file)
    except Exception as e:
        print(f"❌ 验证失败: {e}")
        return {"error": str(e)}

def _fallback_verification(pcap_file: str) -> Dict[str, Any]:
    """备用验证方法（使用tshark）"""
    import subprocess
    import json
    
    try:
        print("🔄 使用tshark进行备用验证...")
        
        # 使用tshark提取TLS记录
        cmd = [
            "tshark", "-r", pcap_file,
            "-Y", "tls.record.content_type == 23",  # ApplicationData
            "-T", "json",
            "-e", "tcp.stream",
            "-e", "tls.record.content_type",
            "-e", "tls.record.length",
            "-e", "tls.app_data"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            return {"error": f"tshark执行失败: {result.stderr}"}
        
        if not result.stdout.strip():
            return {
                "total_tls23_messages": 0,
                "masked_tls23_messages": 0,
                "masking_success_rate": 1.0,
                "method": "tshark_fallback"
            }
        
        # 解析JSON输出
        packets = json.loads(result.stdout)
        
        total_messages = len(packets)
        masked_messages = 0
        
        for packet in packets:
            layers = packet.get("_source", {}).get("layers", {})
            app_data = layers.get("tls.app_data")
            
            if app_data:
                # 检查是否全零
                data_bytes = bytes.fromhex(app_data[0].replace(":", ""))
                if all(b == 0 for b in data_bytes):
                    masked_messages += 1
        
        success_rate = masked_messages / total_messages if total_messages > 0 else 0.0
        
        print(f"📈 tshark验证结果:")
        print(f"   - TLS-23消息总数: {total_messages}")
        print(f"   - 已掩码消息数: {masked_messages}")
        print(f"   - 掩码成功率: {success_rate:.2%}")
        
        return {
            "total_tls23_messages": total_messages,
            "masked_tls23_messages": masked_messages,
            "masking_success_rate": success_rate,
            "method": "tshark_fallback"
        }
        
    except Exception as e:
        return {"error": f"备用验证失败: {e}"}

def compare_with_original(original_file: str, processed_file: str):
    """对比原始文件和处理后文件的TLS-23消息"""
    print(f"\n🔄 对比原始文件和处理后文件...")
    print("="*60)
    
    print("📋 分析原始文件:")
    original_stats = quick_verify_tls23_masking(original_file)
    
    print(f"\n📋 分析处理后文件:")
    processed_stats = quick_verify_tls23_masking(processed_file)
    
    # 对比结果
    if "error" not in original_stats and "error" not in processed_stats:
        print(f"\n📊 对比结果:")
        print(f"   - 原始TLS-23消息数: {original_stats.get('total_tls23_messages', 0)}")
        print(f"   - 处理后TLS-23消息数: {processed_stats.get('total_tls23_messages', 0)}")
        print(f"   - 原始掩码率: {original_stats.get('masking_success_rate', 0):.2%}")
        print(f"   - 处理后掩码率: {processed_stats.get('masking_success_rate', 0):.2%}")
        
        # 判断处理效果
        if processed_stats.get('masking_success_rate', 0) > original_stats.get('masking_success_rate', 0):
            print(f"   ✅ 掩码处理有效！")
        else:
            print(f"   ❌ 掩码处理可能无效！")

def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("使用方法:")
        print("  python scripts/debug/quick_tls23_verification.py <processed_pcap_file>")
        print("  python scripts/debug/quick_tls23_verification.py <original_file> <processed_file>  # 对比模式")
        sys.exit(1)
    
    if len(sys.argv) == 2:
        # 单文件验证模式
        pcap_file = sys.argv[1]
        if not Path(pcap_file).exists():
            print(f"❌ 文件不存在: {pcap_file}")
            sys.exit(1)
        
        quick_verify_tls23_masking(pcap_file)
        
    elif len(sys.argv) == 3:
        # 对比模式
        original_file = sys.argv[1]
        processed_file = sys.argv[2]
        
        if not Path(original_file).exists():
            print(f"❌ 原始文件不存在: {original_file}")
            sys.exit(1)
        
        if not Path(processed_file).exists():
            print(f"❌ 处理后文件不存在: {processed_file}")
            sys.exit(1)
        
        compare_with_original(original_file, processed_file)


if __name__ == "__main__":
    main()
