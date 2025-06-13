#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
调试载荷分析脚本
用于分析TLS文件中每个数据包的载荷情况，诊断掩码表生成问题
"""

import sys
from pathlib import Path
import logging

# 设置日志 - 启用DEBUG级别来查看详细计算过程
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    import pyshark
except ImportError:
    logger.error("PyShark未安装，请运行: pip install pyshark")
    sys.exit(1)

def analyze_packet_payload(pcap_file: str):
    """分析PCAP文件中每个数据包的载荷情况"""
    
    logger.info(f"开始分析文件: {pcap_file}")
    
    try:
        cap = pyshark.FileCapture(pcap_file)
        
        total_packets = 0
        tcp_packets = 0
        packets_with_payload = []
        
        for packet in cap:
            total_packets += 1
            packet_num = int(packet.number)
            
            # 检查是否为TCP
            if hasattr(packet, 'tcp'):
                tcp_packets += 1
                tcp_layer = packet.tcp
                
                # 改进的载荷长度计算 (与PySharkAnalyzer保持一致)
                payload_length = 0
                
                # 方法1: 尝试直接从TCP层获取载荷数据
                if hasattr(tcp_layer, 'payload'):
                    try:
                        payload_raw = tcp_layer.payload
                        if payload_raw:
                            # 转换为字节并计算长度
                            payload_bytes = bytes.fromhex(payload_raw.replace(':', ''))
                            payload_length = len(payload_bytes)
                            logger.debug(f"数据包{packet_num}: 方法1(TCP payload) 载荷长度={payload_length}")
                    except Exception as e:
                        logger.debug(f"数据包{packet_num}: 方法1失败: {e}")
                
                # 方法2: 如果方法1失败，尝试从frame长度计算
                if payload_length == 0:
                    try:
                        # 获取整个frame的长度
                        frame_len = int(packet.length) if hasattr(packet, 'length') else 0
                        
                        # 获取各层头部长度
                        ip_layer = packet.ip if hasattr(packet, 'ip') else packet.ipv6
                        eth_len = 14  # 以太网头部固定14字节
                        ip_len = int(getattr(ip_layer, 'hdr_len', 20)) if hasattr(ip_layer, 'hdr_len') else 20
                        tcp_len = int(getattr(tcp_layer, 'hdr_len', 20)) if hasattr(tcp_layer, 'hdr_len') else 20
                        
                        # 计算载荷长度
                        header_total = eth_len + ip_len + tcp_len
                        payload_length = max(0, frame_len - header_total)
                        logger.debug(f"数据包{packet_num}: 方法2(frame计算) frame={frame_len}, headers={header_total}, payload={payload_length}")
                        
                    except Exception as e:
                        logger.debug(f"数据包{packet_num}: 方法2失败: {e}")
                
                # 方法3: 原有的TCP长度计算方法（作为后备）
                if payload_length == 0:
                    try:
                        if hasattr(tcp_layer, 'len'):
                            tcp_header_len = int(getattr(tcp_layer, 'hdr_len', 20))
                            total_len = int(tcp_layer.len)
                            payload_length = max(0, total_len - tcp_header_len)
                            logger.debug(f"数据包{packet_num}: 方法3(TCP len) tcp_total={total_len}, tcp_header={tcp_header_len}, payload={payload_length}")
                    except Exception as e:
                        logger.debug(f"数据包{packet_num}: 方法3失败: {e}")
                
                # 检查TLS层
                has_tls = hasattr(packet, 'tls')
                has_ssl = hasattr(packet, 'ssl')
                tls_info = ""
                
                if has_tls or has_ssl:
                    tls_layer = packet.tls if has_tls else packet.ssl
                    
                    # 尝试获取TLS内容类型
                    content_types = []
                    try:
                        all_fields = getattr(tls_layer, '_all_fields', {})
                        
                        if 'tls.record' in all_fields:
                            tls_record = all_fields['tls.record']
                            if isinstance(tls_record, list):
                                for record in tls_record:
                                    if isinstance(record, dict) and 'tls.record.content_type' in record:
                                        content_types.append(int(record['tls.record.content_type']))
                            elif isinstance(tls_record, dict) and 'tls.record.content_type' in tls_record:
                                content_types.append(int(tls_record['tls.record.content_type']))
                        
                        # 检查其他可能的字段
                        for field_name in ['record_content_type', 'content_type', 'tls.record.content_type']:
                            if hasattr(tls_layer, field_name):
                                content_types.append(int(getattr(tls_layer, field_name)))
                                break
                                
                    except Exception as e:
                        logger.debug(f"获取TLS内容类型失败: {e}")
                    
                    # 构造TLS信息字符串
                    if content_types:
                        type_names = []
                        for ct in content_types:
                            if ct == 20:
                                type_names.append("ChangeCipherSpec")
                            elif ct == 21:
                                type_names.append("Alert")
                            elif ct == 22:
                                type_names.append("Handshake")
                            elif ct == 23:
                                type_names.append("ApplicationData")
                            else:
                                type_names.append(f"Unknown({ct})")
                        tls_info = f" TLS={','.join(type_names)}"
                    else:
                        tls_info = " TLS=Unknown"
                
                # 获取序列号
                seq_num = int(tcp_layer.seq) if hasattr(tcp_layer, 'seq') else None
                
                # 端口信息
                src_port = int(tcp_layer.srcport)
                dst_port = int(tcp_layer.dstport)
                
                packet_info = {
                    'number': packet_num,
                    'payload_length': payload_length,
                    'seq_number': seq_num,
                    'src_port': src_port,
                    'dst_port': dst_port,
                    'has_tls': has_tls or has_ssl,
                    'tls_info': tls_info
                }
                
                logger.info(f"数据包{packet_num:2d}: 载荷={payload_length:4d}字节, seq={seq_num}, {src_port}->{dst_port}{tls_info}")
                
                if payload_length > 0:
                    packets_with_payload.append(packet_info)
        
        cap.close()
        
        logger.info(f"\n=== 分析结果 ===")
        logger.info(f"总数据包数: {total_packets}")
        logger.info(f"TCP数据包数: {tcp_packets}")
        logger.info(f"有载荷的数据包数: {len(packets_with_payload)}")
        
        logger.info(f"\n=== 有载荷的数据包详情 ===")
        for i, pkt in enumerate(packets_with_payload, 1):
            logger.info(f"{i:2d}. 数据包{pkt['number']:2d}: {pkt['payload_length']:4d}字节 {pkt['tls_info']}")
        
        return packets_with_payload
        
    except Exception as e:
        logger.error(f"分析失败: {e}")
        return []

if __name__ == "__main__":
    # 使用测试用例中的TLS文件
    tls_file = "tests/samples/TLS/tls_sample.pcap"
    
    if not Path(tls_file).exists():
        logger.error(f"文件不存在: {tls_file}")
        sys.exit(1)
    
    result = analyze_packet_payload(tls_file)
    
    logger.info(f"\n=== 期望掩码条目数 ===")
    logger.info(f"应该生成 {len(result)} 个掩码条目（每个有载荷的数据包一个）") 