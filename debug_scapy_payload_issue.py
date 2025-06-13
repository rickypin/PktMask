#!/usr/bin/env python3
"""
调试Scapy无法从TShark重组包中提取Raw载荷的问题

这个脚本比较：
1. 原始PCAP文件的包结构
2. TShark重组后的包结构
3. Scapy对两种文件的载荷检测差异
"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent / 'src'))

try:
    from scapy.all import rdpcap
    from scapy.layers.inet import IP, TCP
    from scapy.packet import Raw
    try:
        from scapy.layers.tls.all import TLS
    except ImportError:
        # 兼容旧版本Scapy
        TLS = None
except ImportError as e:
    print(f"❌ 无法导入Scapy: {e}")
    print("请确保已安装Scapy: pip install scapy")
    sys.exit(1)

def analyze_packet_structure(packet, packet_num, file_type):
    """分析数据包结构"""
    print(f"\n🔍 {file_type} - 数据包{packet_num}分析:")
    print(f"   摘要: {packet.summary()}")
    
    # 检查协议层
    layers = []
    layer = packet
    while layer:
        layers.append(layer.__class__.__name__)
        layer = layer.payload if hasattr(layer, 'payload') and layer.payload else None
    
    print(f"   协议栈: {' / '.join(layers)}")
    
    # 检查TCP层
    if packet.haslayer(TCP):
        tcp = packet[TCP]
        print(f"   TCP序列号: {tcp.seq}")
        print(f"   TCP负载(hasattr load): {hasattr(tcp, 'load')}")
        if hasattr(tcp, 'load'):
            print(f"   TCP载荷长度: {len(tcp.load)}")
            print(f"   TCP载荷前16字节: {tcp.load[:16].hex()}")
    
    # 检查Raw层
    has_raw = packet.haslayer(Raw)
    print(f"   Raw层存在: {has_raw}")
    if has_raw:
        raw = packet[Raw]
        print(f"   Raw载荷长度: {len(raw.load)}")
        print(f"   Raw载荷前16字节: {raw.load[:16].hex()}")
    
    # 检查TLS层
    if TLS:
        has_tls = packet.haslayer(TLS)
        print(f"   TLS层存在: {has_tls}")
        if has_tls:
            tls = packet[TLS]
            print(f"   TLS类型: {type(tls)}")
            print(f"   TLS字段: {list(tls.fields.keys()) if hasattr(tls, 'fields') else 'N/A'}")
    else:
        print(f"   TLS层: Scapy版本不支持TLS解析")
    
    # 检查包的bytes表示
    packet_bytes = bytes(packet)
    print(f"   数据包总长度: {len(packet_bytes)} 字节")
    
    return has_raw, len(raw.load) if has_raw else 0

def compare_pcap_files():
    """比较原始文件和TShark重组文件的差异"""
    
    original_file = Path("tests/samples/TLS/tls_sample.pcap")
    tshark_file = Path("/var/folders/wz/ql3l9vh10z3c4kt7h9c1ydvh0000gn/T/enhanced_trim_orsvqq_y/tshark_output_e_zws2jn.pcap")
    
    if not original_file.exists():
        print(f"❌ 原始文件不存在: {original_file}")
        return
    
    if not tshark_file.exists():
        print(f"❌ TShark重组文件不存在: {tshark_file}")
        print("提示：请先运行Enhanced Trimmer生成TShark重组文件")
        return
    
    print("🔬 Scapy载荷提取对比分析")
    print("=" * 70)
    
    # 读取两个文件
    try:
        original_packets = rdpcap(str(original_file))
        tshark_packets = rdpcap(str(tshark_file))
        
        print(f"📄 原始文件: {len(original_packets)} 个包")
        print(f"📄 TShark重组文件: {len(tshark_packets)} 个包")
        
        # 重点分析包14和包15（PyShark显示有载荷的包）
        target_packets = [14, 15]
        
        for packet_num in target_packets:
            if packet_num <= len(original_packets) and packet_num <= len(tshark_packets):
                
                # 分析原始包
                orig_packet = original_packets[packet_num - 1]  # 0-based index
                orig_has_raw, orig_payload_len = analyze_packet_structure(orig_packet, packet_num, "原始文件")
                
                # 分析TShark重组包
                tshark_packet = tshark_packets[packet_num - 1]  # 0-based index
                tshark_has_raw, tshark_payload_len = analyze_packet_structure(tshark_packet, packet_num, "TShark重组")
                
                # 对比结果
                print(f"\n📊 数据包{packet_num}对比:")
                print(f"   原始文件Raw层: {orig_has_raw}, 载荷长度: {orig_payload_len}")
                print(f"   TShark重组Raw层: {tshark_has_raw}, 载荷长度: {tshark_payload_len}")
                
                if orig_has_raw != tshark_has_raw:
                    print(f"   ⚠️  Raw层检测不一致!")
                    
                if orig_payload_len != tshark_payload_len:
                    print(f"   ⚠️  载荷长度不一致!")
                
                print("   " + "="*50)
    
    except Exception as e:
        print(f"❌ 读取文件失败: {e}")
        import traceback
        traceback.print_exc()

def test_payload_extraction_methods():
    """测试不同的载荷提取方法"""
    
    tshark_file = Path("/var/folders/wz/ql3l9vh10z3c4kt7h9c1ydvh0000gn/T/enhanced_trim_orsvqq_y/tshark_output_e_zws2jn.pcap")
    
    if not tshark_file.exists():
        print(f"❌ TShark重组文件不存在: {tshark_file}")
        return
    
    print("\n🧪 测试不同载荷提取方法")
    print("=" * 50)
    
    try:
        packets = rdpcap(str(tshark_file))
        
        # 测试包14（PyShark显示有205字节载荷）
        packet = packets[13]  # 0-based index
        
        print(f"🎯 测试数据包14载荷提取方法:")
        print(f"   数据包摘要: {packet.summary()}")
        
        # 方法1: Raw层
        if packet.haslayer(Raw):
            raw_payload = bytes(packet[Raw].load)
            print(f"   方法1 - Raw层: {len(raw_payload)} 字节")
            if raw_payload:
                print(f"   Raw前16字节: {raw_payload[:16].hex()}")
        else:
            print(f"   方法1 - Raw层: 无Raw层")
        
        # 方法2: TCP load属性
        if packet.haslayer(TCP):
            tcp = packet[TCP]
            if hasattr(tcp, 'load'):
                tcp_payload = bytes(tcp.load)
                print(f"   方法2 - TCP.load: {len(tcp_payload)} 字节")
                if tcp_payload:
                    print(f"   TCP.load前16字节: {tcp_payload[:16].hex()}")
            else:
                print(f"   方法2 - TCP.load: 无load属性")
        
        # 方法3: 数据包级别load
        if hasattr(packet, 'load'):
            packet_payload = bytes(packet.load)
            print(f"   方法3 - packet.load: {len(packet_payload)} 字节")
            if packet_payload:
                print(f"   packet.load前16字节: {packet_payload[:16].hex()}")
        else:
            print(f"   方法3 - packet.load: 无load属性")
        
        # 方法4: 手动计算载荷
        print(f"   方法4 - 手动计算:")
        try:
            packet_bytes = bytes(packet)
            print(f"     数据包总长度: {len(packet_bytes)} 字节")
            
            # 计算头部长度
            eth_len = 14  # 以太网头部
            ip_len = packet[IP].ihl * 4 if packet.haslayer(IP) else 0
            tcp_len = packet[TCP].dataofs * 4 if packet.haslayer(TCP) else 0
            headers_len = eth_len + ip_len + tcp_len
            
            print(f"     头部长度: ETH({eth_len}) + IP({ip_len}) + TCP({tcp_len}) = {headers_len}")
            
            payload_len = len(packet_bytes) - headers_len
            print(f"     计算载荷长度: {payload_len} 字节")
            
            if payload_len > 0:
                calculated_payload = packet_bytes[headers_len:]
                print(f"     计算载荷前16字节: {calculated_payload[:16].hex()}")
                
        except Exception as e:
            print(f"     计算失败: {e}")
    
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🚀 调试Scapy载荷提取问题")
    print("=" * 70)
    
    # 先比较文件差异
    compare_pcap_files()
    
    # 然后测试提取方法
    test_payload_extraction_methods()
    
    print("\n" + "=" * 70)
    print("✅ 调试完成 - 请查看上述分析结果") 