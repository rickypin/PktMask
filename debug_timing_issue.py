#!/usr/bin/env python3
"""
调试TCP Payload Masker时机控制问题
"""

import sys
import logging
from pathlib import Path
from scapy.all import rdpcap, Raw
import yaml

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from pktmask.core.tcp_payload_masker.core.tcp_masker import TcpPayloadMasker
from pktmask.core.tcp_payload_masker.core.keep_range_models import TcpKeepRangeEntry, TcpKeepRangeTable
from pktmask.core.tcp_payload_masker.core.file_handler import PcapFileHandler
from pktmask.core.tcp_payload_masker.core.protocol_control import ProtocolBindingController

def setup_logging():
    """设置详细日志"""
    logging.basicConfig(
        level=logging.INFO,
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

def check_packet6_raw_status(label: str):
    """检查包6的Raw层状态"""
    pcap_file = Path("tests/data/tls-single/tls_sample.pcap")
    packets = rdpcap(str(pcap_file))
    packet6 = packets[5]
    
    has_raw = packet6.haslayer(Raw)
    print(f"  {label}: 包6有Raw层 = {has_raw}")
    return has_raw

def debug_full_process():
    """调试完整的TCP掩码处理过程"""
    logger = setup_logging()
    
    logger.info("=" * 70)
    logger.info("调试TCP Payload Masker完整处理时机")
    logger.info("=" * 70)
    
    # 准备输入
    input_pcap = "tests/data/tls-single/tls_sample.pcap"
    output_pcap = "test_output_debug.pcap"
    keep_range_table = load_scenario_config()
    
    # 步骤1: 检查初始状态
    logger.info("\n步骤1: 检查初始协议解析状态")
    initial_status = check_packet6_raw_status("初始状态")
    
    # 步骤2: 创建TcpPayloadMasker
    logger.info("\n步骤2: 创建TcpPayloadMasker")
    masker = TcpPayloadMasker()
    creation_status = check_packet6_raw_status("创建masker后")
    
    # 步骤3: 手动测试协议控制器
    logger.info("\n步骤3: 手动测试协议控制器")
    controller = ProtocolBindingController(logger)
    
    logger.info("手动禁用协议解析:")
    controller.disable_protocol_parsing()
    manual_disable_status = check_packet6_raw_status("手动禁用后")
    
    logger.info("手动恢复协议解析:")
    controller.restore_protocol_parsing()
    manual_restore_status = check_packet6_raw_status("手动恢复后")
    
    # 步骤4: 测试File Handler在不同状态下的行为
    logger.info("\n步骤4: 测试PcapFileHandler")
    file_handler = PcapFileHandler(logger)
    
    logger.info("禁用协议解析状态下读取:")
    controller.disable_protocol_parsing()
    packets_disabled = file_handler.read_packets(input_pcap)
    packet6_disabled = packets_disabled[5]
    disabled_has_raw = packet6_disabled.haslayer(Raw)
    logger.info(f"  禁用状态下包6有Raw层: {disabled_has_raw}")
    
    logger.info("恢复协议解析状态下读取:")
    controller.restore_protocol_parsing()
    packets_enabled = file_handler.read_packets(input_pcap)
    packet6_enabled = packets_enabled[5]
    enabled_has_raw = packet6_enabled.haslayer(Raw)
    logger.info(f"  启用状态下包6有Raw层: {enabled_has_raw}")
    
    # 步骤5: 完整的mask_tcp_payloads_with_keep_ranges调用
    logger.info("\n步骤5: 完整处理调用")
    logger.info("调用mask_tcp_payloads_with_keep_ranges...")
    
    # 在调用前检查状态
    before_call_status = check_packet6_raw_status("调用前")
    
    try:
        result = masker.mask_tcp_payloads_with_keep_ranges(
            input_pcap, keep_range_table, output_pcap
        )
        
        logger.info(f"处理结果: {result.get_summary()}")
        
        # 在调用后检查状态
        after_call_status = check_packet6_raw_status("调用后")
        
        # 检查输出文件
        if Path(output_pcap).exists():
            output_packets = rdpcap(output_pcap)
            output_packet6 = output_packets[5]
            
            # 比较载荷
            input_packet6 = packets_enabled[5]
            input_payload = bytes(input_packet6[Raw].load) if input_packet6.haslayer(Raw) else b""
            output_payload = bytes(output_packet6[Raw].load) if output_packet6.haslayer(Raw) else b""
            
            logger.info(f"\n载荷对比:")
            logger.info(f"  输入载荷长度: {len(input_payload)}字节")
            logger.info(f"  输出载荷长度: {len(output_payload)}字节")
            logger.info(f"  载荷是否相同: {input_payload == output_payload}")
            
            if len(input_payload) > 0 and len(output_payload) > 0:
                # 检查前16字节
                logger.info(f"  输入前16字节: {input_payload[:16].hex()}")
                logger.info(f"  输出前16字节: {output_payload[:16].hex()}")
                
                # 检查是否被掩码
                zero_bytes = output_payload.count(0)
                zero_rate = zero_bytes / len(output_payload) if len(output_payload) > 0 else 0
                logger.info(f"  输出零字节比例: {zero_rate:.2%}")
        
    except Exception as e:
        logger.error(f"处理失败: {e}")
    
    # 总结
    logger.info("\n" + "=" * 70)
    logger.info("总结 - 各阶段包6的Raw层状态:")
    logger.info("=" * 70)
    logger.info(f"  初始状态: {initial_status}")
    logger.info(f"  创建masker后: {creation_status}")
    logger.info(f"  手动禁用后: {manual_disable_status}")
    logger.info(f"  手动恢复后: {manual_restore_status}")
    logger.info(f"  文件读取(禁用状态): {disabled_has_raw}")
    logger.info(f"  文件读取(启用状态): {enabled_has_raw}")
    logger.info(f"  完整调用前: {before_call_status}")
    logger.info(f"  完整调用后: {after_call_status}")

if __name__ == "__main__":
    debug_full_process() 