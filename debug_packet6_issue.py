#!/usr/bin/env python3
"""
调试包6未被掩码问题的脚本

验证PayloadExtractor的各个步骤：
1. 载荷提取
2. 流ID生成
3. 序列号获取
4. 保留范围查找
"""

import sys
import logging
from pathlib import Path
from scapy.all import rdpcap, Packet, Raw, IP, TCP
import yaml

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from pktmask.core.tcp_payload_masker.core.payload_extractor import PayloadExtractor
from pktmask.core.tcp_payload_masker.core.keep_range_models import TcpKeepRangeEntry, TcpKeepRangeTable

def setup_logging():
    """设置详细日志"""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(levelname)s - %(name)s - %(message)s'
    )
    return logging.getLogger(__name__)

def load_scenario_config():
    """加载包6的配置"""
    config_file = Path("test_scenarios/scenario_05_boundary_conditions.yaml")
    
    with open(config_file, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # 创建保留范围表
    keep_range_table = TcpKeepRangeTable()
    
    for rule in config['keep_range_rules']:
        entry = TcpKeepRangeEntry(
            stream_id=rule['stream_id'],
            sequence_start=rule['sequence_start'],
            sequence_end=rule['sequence_end'],
            keep_ranges=rule['keep_ranges'],
            protocol_hint=rule.get('protocol_hint')
        )
        keep_range_table.add_keep_range_entry(entry)
    
    return keep_range_table

def debug_packet6():
    """调试包6的处理过程"""
    logger = setup_logging()
    
    # 读取PCAP文件
    pcap_file = Path("tests/data/tls-single/tls_sample.pcap")
    packets = rdpcap(str(pcap_file))
    
    # 获取包6（索引5，因为从0开始）
    packet6 = packets[5]  # 包6
    
    logger.info("=" * 60)
    logger.info("开始调试包6处理过程")
    logger.info("=" * 60)
    
    # 加载配置
    keep_range_table = load_scenario_config()
    logger.info(f"加载配置完成，共{keep_range_table.get_total_entries()}条规则")
    
    # 创建载荷提取器
    payload_extractor = PayloadExtractor(logger)
    
    # 步骤1: 检查包结构
    logger.info("\n步骤1: 检查包6的基本结构")
    logger.info(f"包6层信息: {[layer.name for layer in packet6.layers()]}")
    
    ip_layer = packet6.getlayer(IP)
    tcp_layer = packet6.getlayer(TCP)
    raw_layer = packet6.getlayer(Raw)
    
    if ip_layer:
        logger.info(f"IP层: {ip_layer.src}:{tcp_layer.sport} -> {ip_layer.dst}:{tcp_layer.dport}")
    if tcp_layer:
        logger.info(f"TCP层: seq={tcp_layer.seq}, flags={tcp_layer.flags}")
    if raw_layer:
        logger.info(f"Raw层: 载荷长度={len(raw_layer.load)}字节")
        logger.info(f"载荷前16字节: {raw_layer.load[:16].hex()}")
    else:
        logger.warning("警告: 包6没有Raw层!")
    
    # 步骤2: 测试载荷提取
    logger.info("\n步骤2: 测试载荷提取")
    payload = payload_extractor.extract_tcp_payload(packet6)
    if payload:
        logger.info(f"✅ 载荷提取成功: {len(payload)}字节")
        logger.info(f"载荷前16字节: {payload[:16].hex()}")
    else:
        logger.error("❌ 载荷提取失败!")
        return
    
    # 步骤3: 测试流ID生成
    logger.info("\n步骤3: 测试流ID生成")
    stream_id = payload_extractor._generate_stream_id(packet6)
    if stream_id:
        logger.info(f"✅ 流ID生成成功: {stream_id}")
    else:
        logger.error("❌ 流ID生成失败!")
        return
    
    # 步骤4: 测试序列号获取
    logger.info("\n步骤4: 测试序列号获取")
    sequence = payload_extractor._get_sequence_number(packet6)
    if sequence is not None:
        logger.info(f"✅ 序列号获取成功: {sequence}")
    else:
        logger.error("❌ 序列号获取失败!")
        return
    
    # 步骤5: 完整流信息提取
    logger.info("\n步骤5: 完整流信息提取")
    stream_info = payload_extractor.extract_stream_info(packet6)
    if stream_info:
        extracted_stream_id, extracted_sequence, extracted_payload = stream_info
        logger.info(f"✅ 流信息提取成功:")
        logger.info(f"  流ID: {extracted_stream_id}")
        logger.info(f"  序列号: {extracted_sequence}")
        logger.info(f"  载荷长度: {len(extracted_payload)}字节")
    else:
        logger.error("❌ 流信息提取失败!")
        return
    
    # 步骤6: 查找保留范围
    logger.info("\n步骤6: 查找保留范围")
    
    # 先检查配置中的包6条目
    logger.info("配置中的包6条目:")
    for entry in keep_range_table.get_all_entries():
        if "reverse" in entry.stream_id:
            logger.info(f"  流ID: {entry.stream_id}")
            logger.info(f"  序列号范围: [{entry.sequence_start}, {entry.sequence_end})")
            logger.info(f"  保留范围: {entry.keep_ranges}")
            logger.info(f"  协议提示: {entry.protocol_hint}")
    
    # 检查流ID匹配
    logger.info(f"\n流ID匹配检查:")
    logger.info(f"  提取的流ID: '{extracted_stream_id}'")
    logger.info(f"  配置的流ID: 'TCP_10.171.250.80:33492_10.50.50.161:443_reverse'")
    logger.info(f"  匹配结果: {extracted_stream_id == 'TCP_10.171.250.80:33492_10.50.50.161:443_reverse'}")
    
    # 查找保留范围
    keep_ranges = keep_range_table.find_keep_ranges_for_sequence(extracted_stream_id, extracted_sequence)
    logger.info(f"\n保留范围查找结果: {len(keep_ranges)}个范围")
    if keep_ranges:
        for i, (start, end) in enumerate(keep_ranges):
            logger.info(f"  范围{i+1}: [{start}, {end})")
    else:
        logger.warning("⚠️  没有找到匹配的保留范围!")
        
        # 调试：检查条目是否覆盖该序列号
        logger.info("\n调试信息：检查条目覆盖")
        for entry in keep_range_table.get_all_entries():
            if entry.stream_id == extracted_stream_id:
                covers = entry.covers_sequence(extracted_sequence)
                logger.info(f"  条目[{entry.sequence_start}, {entry.sequence_end}) 覆盖序列号{extracted_sequence}: {covers}")
                if not covers:
                    logger.info(f"    条件检查: {entry.sequence_start} <= {extracted_sequence} < {entry.sequence_end}")
                    logger.info(f"    左边界: {entry.sequence_start <= extracted_sequence}")
                    logger.info(f"    右边界: {extracted_sequence < entry.sequence_end}")
    
    # 步骤7: 检查配置边界
    logger.info("\n步骤7: 检查配置边界计算")
    expected_sequence_end = 3913402951 + 1342  # sequence_start + payload_length
    logger.info(f"预期序列号结束: {expected_sequence_end}")
    logger.info(f"配置序列号结束: 3913404293")
    logger.info(f"边界匹配: {expected_sequence_end == 3913404293}")
    
    # 提取器统计信息
    logger.info("\n提取器统计信息:")
    stats = payload_extractor.get_statistics()
    for key, value in stats.items():
        logger.info(f"  {key}: {value}")

if __name__ == "__main__":
    debug_packet6() 