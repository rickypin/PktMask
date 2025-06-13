#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
调试三个阶段文件处理脚本
分析TShark、PyShark、Scapy三个阶段处理的文件对象，找出载荷裁切不生效的原因
"""

import sys
from pathlib import Path
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    import pyshark
    import scapy.all as scapy
    from scapy.all import rdpcap
    print("✅ PyShark和Scapy都可用")
except ImportError as e:
    logger.error(f"缺少依赖: {e}")
    sys.exit(1)

def analyze_original_file(pcap_file: str):
    """分析原始PCAP文件"""
    logger.info(f"\n=== 1. 分析原始文件: {pcap_file} ===")
    
    try:
        # 使用PyShark分析
        cap = pyshark.FileCapture(pcap_file)
        packets = list(cap)
        cap.close()
        
        logger.info(f"PyShark读取: {len(packets)} 个数据包")
        
        # 分析TCP流和序列号
        tcp_streams = {}
        for i, pkt in enumerate(packets, 1):
            if hasattr(pkt, 'tcp') and hasattr(pkt, 'ip'):
                src_ip = pkt.ip.src
                dst_ip = pkt.ip.dst
                src_port = int(pkt.tcp.srcport)
                dst_port = int(pkt.tcp.dstport)
                seq = int(pkt.tcp.seq) if hasattr(pkt.tcp, 'seq') else None
                
                stream_key = f"{src_ip}:{src_port}-{dst_ip}:{dst_port}"
                if stream_key not in tcp_streams:
                    tcp_streams[stream_key] = []
                
                payload_len = 0
                if hasattr(pkt, 'tcp') and hasattr(pkt.tcp, 'payload'):
                    try:
                        payload_len = len(bytes.fromhex(pkt.tcp.payload.replace(':', '')))
                    except:
                        pass
                
                tcp_streams[stream_key].append({
                    'packet': i,
                    'seq': seq,
                    'payload_len': payload_len
                })
                
                logger.info(f"  包{i}: {stream_key}, seq={seq}, payload={payload_len}")
        
        return tcp_streams
        
    except Exception as e:
        logger.error(f"分析原始文件失败: {e}")
        return {}

def analyze_tshark_output(pcap_file: str):
    """分析TShark重组后的文件"""
    logger.info(f"\n=== 2. 分析TShark重组文件: {pcap_file} ===")
    
    try:
        # 使用PyShark分析重组后文件
        cap = pyshark.FileCapture(pcap_file)
        packets = list(cap)
        cap.close()
        
        logger.info(f"PyShark读取重组文件: {len(packets)} 个数据包")
        
        # 分析TCP流和序列号
        tcp_streams = {}
        for i, pkt in enumerate(packets, 1):
            if hasattr(pkt, 'tcp') and hasattr(pkt, 'ip'):
                src_ip = pkt.ip.src
                dst_ip = pkt.ip.dst
                src_port = int(pkt.tcp.srcport)
                dst_port = int(pkt.tcp.dstport)
                seq = int(pkt.tcp.seq) if hasattr(pkt.tcp, 'seq') else None
                
                stream_key = f"{src_ip}:{src_port}-{dst_ip}:{dst_port}"
                if stream_key not in tcp_streams:
                    tcp_streams[stream_key] = []
                
                payload_len = 0
                if hasattr(pkt, 'tcp') and hasattr(pkt.tcp, 'payload'):
                    try:
                        payload_len = len(bytes.fromhex(pkt.tcp.payload.replace(':', '')))
                    except:
                        pass
                
                tcp_streams[stream_key].append({
                    'packet': i,
                    'seq': seq,
                    'payload_len': payload_len
                })
                
                logger.info(f"  包{i}: {stream_key}, seq={seq}, payload={payload_len}")
        
        return tcp_streams
        
    except Exception as e:
        logger.error(f"分析TShark重组文件失败: {e}")
        return {}

def analyze_scapy_view(pcap_file: str):
    """分析Scapy读取的文件"""
    logger.info(f"\n=== 3. 分析Scapy读取: {pcap_file} ===")
    
    try:
        # 使用Scapy读取
        packets = rdpcap(pcap_file)
        
        logger.info(f"Scapy读取: {len(packets)} 个数据包")
        
        # 分析TCP流和序列号
        tcp_streams = {}
        for i, pkt in enumerate(packets, 1):
            if pkt.haslayer(scapy.TCP) and pkt.haslayer(scapy.IP):
                src_ip = pkt[scapy.IP].src
                dst_ip = pkt[scapy.IP].dst
                src_port = pkt[scapy.TCP].sport
                dst_port = pkt[scapy.TCP].dport
                seq = pkt[scapy.TCP].seq
                
                stream_key = f"{src_ip}:{src_port}-{dst_ip}:{dst_port}"
                if stream_key not in tcp_streams:
                    tcp_streams[stream_key] = []
                
                payload_len = 0
                if pkt.haslayer(scapy.Raw):
                    payload_len = len(pkt[scapy.Raw].load)
                
                tcp_streams[stream_key].append({
                    'packet': i,
                    'seq': seq,
                    'payload_len': payload_len
                })
                
                logger.info(f"  包{i}: {stream_key}, seq={seq}, payload={payload_len}")
        
        return tcp_streams
        
    except Exception as e:
        logger.error(f"分析Scapy文件失败: {e}")
        return {}

def compare_analyses(original_streams, tshark_streams, scapy_streams):
    """比较三种分析结果"""
    logger.info(f"\n=== 4. 比较分析结果 ===")
    
    logger.info(f"原始文件流数: {len(original_streams)}")
    logger.info(f"TShark重组流数: {len(tshark_streams)}")
    logger.info(f"Scapy读取流数: {len(scapy_streams)}")
    
    # 比较流的一致性
    all_stream_keys = set(original_streams.keys()) | set(tshark_streams.keys()) | set(scapy_streams.keys())
    
    for stream_key in all_stream_keys:
        logger.info(f"\n流: {stream_key}")
        
        original_packets = original_streams.get(stream_key, [])
        tshark_packets = tshark_streams.get(stream_key, [])
        scapy_packets = scapy_streams.get(stream_key, [])
        
        logger.info(f"  原始包数: {len(original_packets)}")
        logger.info(f"  TShark包数: {len(tshark_packets)}")
        logger.info(f"  Scapy包数: {len(scapy_packets)}")
        
        # 比较序列号
        if tshark_packets and scapy_packets:
            logger.info("  序列号比较:")
            for t_pkt, s_pkt in zip(tshark_packets, scapy_packets):
                if t_pkt['seq'] != s_pkt['seq']:
                    logger.warning(f"    包{t_pkt['packet']}: TShark seq={t_pkt['seq']}, Scapy seq={s_pkt['seq']} - 不匹配!")
                else:
                    logger.info(f"    包{t_pkt['packet']}: seq={t_pkt['seq']} - 匹配")
                    
                if t_pkt['payload_len'] != s_pkt['payload_len']:
                    logger.warning(f"    包{t_pkt['packet']}: TShark payload={t_pkt['payload_len']}, Scapy payload={s_pkt['payload_len']} - 载荷长度不匹配!")
                else:
                    logger.info(f"    包{t_pkt['packet']}: payload={t_pkt['payload_len']} - 载荷长度匹配")

def main():
    """主函数"""
    if len(sys.argv) != 3:
        print("用法: python debug_three_stages.py <原始文件> <TShark重组文件>")
        print("示例: python debug_three_stages.py /path/to/original.pcap /path/to/tshark_output.pcap")
        sys.exit(1)
    
    original_file = sys.argv[1]
    tshark_file = sys.argv[2]
    
    if not Path(original_file).exists():
        logger.error(f"原始文件不存在: {original_file}")
        sys.exit(1)
    
    if not Path(tshark_file).exists():
        logger.error(f"TShark文件不存在: {tshark_file}")
        sys.exit(1)
    
    logger.info("开始分析三个阶段的文件处理差异...")
    
    # 分析原始文件
    original_streams = analyze_original_file(original_file)
    
    # 分析TShark重组文件
    tshark_streams = analyze_tshark_output(tshark_file)
    
    # 分析Scapy读取结果（使用TShark重组文件）
    scapy_streams = analyze_scapy_view(tshark_file)
    
    # 比较结果
    compare_analyses(original_streams, tshark_streams, scapy_streams)
    
    logger.info("\n分析完成！")

if __name__ == "__main__":
    main() 