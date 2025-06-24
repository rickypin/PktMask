#!/usr/bin/env python3
"""
检查协议解析状态和包6层结构的调试脚本
"""

import sys
import logging
from pathlib import Path
from scapy.all import rdpcap, conf

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

def check_protocol_parsing_state():
    """检查当前协议解析状态"""
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 60)
    logger.info("协议解析状态检查")
    logger.info("=" * 60)
    
    # 检查Scapy配置
    logger.info(f"Scapy配置:")
    logger.info(f"  conf.padding: {conf.padding}")
    logger.info(f"  conf.check_TCPerror: {getattr(conf, 'check_TCPerror', 'N/A')}")
    
    # 读取PCAP文件
    pcap_file = Path("tests/data/tls-single/tls_sample.pcap")
    packets = rdpcap(str(pcap_file))
    
    logger.info(f"\n读取了{len(packets)}个数据包")
    
    # 检查几个包的层结构
    for i in [3, 5, 13]:  # 包4, 包6, 包14 (索引-1)
        packet = packets[i]
        packet_num = i + 1
        
        logger.info(f"\n包{packet_num}层结构分析:")
        
        # 获取层名称（正确的方式）
        try:
            layer_names = []
            current_layer = packet
            while current_layer:
                layer_names.append(type(current_layer).__name__)
                current_layer = current_layer.payload if hasattr(current_layer, 'payload') else None
                if current_layer and type(current_layer).__name__ == 'NoPayload':
                    break
            
            logger.info(f"  层序列: {' -> '.join(layer_names)}")
            
            # 检查是否有Raw层
            from scapy.all import Raw
            has_raw = packet.haslayer(Raw)
            logger.info(f"  有Raw层: {has_raw}")
            
            # 检查TCP载荷
            from scapy.all import TCP
            if packet.haslayer(TCP):
                tcp_layer = packet[TCP]
                payload_type = type(tcp_layer.payload).__name__
                logger.info(f"  TCP载荷类型: {payload_type}")
                
                if hasattr(tcp_layer.payload, 'load'):
                    payload_len = len(tcp_layer.payload.load)
                    logger.info(f"  载荷长度: {payload_len}字节")
                else:
                    logger.info(f"  载荷长度: 0字节")
            
        except Exception as e:
            logger.error(f"  层分析失败: {e}")

def test_protocol_parsing_disable():
    """测试协议解析禁用功能"""
    logger = logging.getLogger(__name__)
    
    logger.info("\n" + "=" * 60)
    logger.info("测试协议解析禁用")
    logger.info("=" * 60)
    
    from pktmask.core.tcp_payload_masker.core.protocol_control import ProtocolBindingController
    
    # 创建协议控制器
    controller = ProtocolBindingController(logger)
    
    logger.info("禁用协议解析前:")
    check_packet6_before = check_single_packet()
    
    # 禁用协议解析
    try:
        controller.disable_protocol_parsing()
        logger.info("✅ 协议解析已禁用")
        
        logger.info("\n禁用协议解析后:")
        check_packet6_after = check_single_packet()
        
        # 恢复协议解析
        controller.restore_protocol_parsing()
        logger.info("✅ 协议解析已恢复")
        
        # 比较结果
        logger.info(f"\n效果对比:")
        logger.info(f"  禁用前包6有Raw层: {check_packet6_before}")
        logger.info(f"  禁用后包6有Raw层: {check_packet6_after}")
        
    except Exception as e:
        logger.error(f"协议解析控制失败: {e}")
        # 确保恢复
        try:
            controller.restore_protocol_parsing()
        except:
            pass

def check_single_packet():
    """检查单个包6的Raw层状态"""
    pcap_file = Path("tests/data/tls-single/tls_sample.pcap")
    packets = rdpcap(str(pcap_file))
    packet6 = packets[5]
    
    from scapy.all import Raw
    return packet6.haslayer(Raw)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(name)s - %(message)s')
    
    check_protocol_parsing_state()
    test_protocol_parsing_disable() 