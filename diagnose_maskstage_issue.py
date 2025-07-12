#!/usr/bin/env python3
"""
PktMask MaskStage 问题诊断脚本

专门诊断为什么新版maskstage双模块架构没有修改任何数据包的问题。
重点分析：
1. Marker模块生成的保留规则是否正确
2. Masker模块的序列号匹配逻辑是否有问题
3. TLS ApplicationData是否被错误地包含在保留规则中
"""

import sys
import os
import logging
import json
from pathlib import Path
from typing import Dict, Any, List

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

def setup_logging():
    """设置详细日志"""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('diagnose_maskstage_issue.log', mode='w')
        ]
    )
    return logging.getLogger(__name__)

def analyze_original_tls_data():
    """分析原始TLS数据，了解应该掩码的内容"""
    logger = logging.getLogger(__name__)
    logger.info("=" * 80)
    logger.info("分析原始TLS数据")
    logger.info("=" * 80)
    
    input_file = "tests/samples/tls-single/tls_sample.pcap"
    
    try:
        # 运行原始tls_flow_analyzer获取详细信息
        import subprocess
        
        cmd = [
            sys.executable, "-m", "pktmask.tools.tls_flow_analyzer",
            "--pcap", input_file,
            "--formats", "json",
            "--output-dir", "output",
            "--detailed",
            "--verbose"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=".")
        if result.returncode == 0:
            logger.info("TLS流量分析完成")
            
            # 读取详细分析结果
            analysis_file = "output/tls_sample_tls_flow_analysis.json"
            if Path(analysis_file).exists():
                with open(analysis_file, 'r') as f:
                    analysis_data = json.load(f)
                
                logger.info("TLS消息统计:")
                if 'protocol_type_statistics' in analysis_data:
                    for tls_type, stats in analysis_data['protocol_type_statistics'].items():
                        type_name = analysis_data['metadata']['tls_content_types'].get(tls_type, f'Unknown-{tls_type}')
                        strategy = analysis_data['metadata']['processing_strategies'].get(tls_type, 'unknown')
                        logger.info(f"  TLS-{tls_type} ({type_name}, {strategy}): {stats['frames']} 帧, {stats['records']} 记录")
                
                # 分析详细帧信息，查找ApplicationData
                logger.info("\n详细帧分析:")
                app_data_frames = []
                if 'detailed_frames' in analysis_data:
                    for frame in analysis_data['detailed_frames']:
                        if 'tls_messages' in frame:
                            for msg in frame['tls_messages']:
                                if msg.get('tls_type') == 23:  # ApplicationData
                                    app_data_frames.append({
                                        'frame': frame['frame'],
                                        'tcp_seq': msg.get('tcp_seq_start'),
                                        'tcp_len': msg.get('tcp_len'),
                                        'tls_length': msg.get('tls_length')
                                    })
                                    logger.info(f"  帧 {frame['frame']}: TLS-23 ApplicationData")
                                    logger.info(f"    TCP序列号: {msg.get('tcp_seq_start')}")
                                    logger.info(f"    TCP长度: {msg.get('tcp_len')}")
                                    logger.info(f"    TLS长度: {msg.get('tls_length')}")
                
                logger.info(f"\n发现 {len(app_data_frames)} 个ApplicationData消息")
                return app_data_frames
        else:
            logger.error(f"TLS流量分析失败: {result.stderr}")
            return []
        
    except Exception as e:
        logger.error(f"分析原始TLS数据失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return []

def analyze_marker_rules():
    """分析Marker模块生成的保留规则"""
    logger = logging.getLogger(__name__)
    logger.info("=" * 80)
    logger.info("分析Marker模块保留规则")
    logger.info("=" * 80)
    
    input_file = "tests/samples/tls-single/tls_sample.pcap"
    
    try:
        from pktmask.core.pipeline.stages.mask_payload_v2.marker.tls_marker import TLSProtocolMarker
        
        marker_config = {
            "preserve": {
                "handshake": True,
                "application_data": False,  # 关键：ApplicationData应该被掩码
                "alert": True,
                "change_cipher_spec": True,
                "heartbeat": True
            }
        }
        
        marker = TLSProtocolMarker(marker_config)
        marker.initialize()
        
        # 生成保留规则
        keep_rules = marker.analyze_file(input_file, marker_config)
        
        logger.info(f"生成的保留规则数量: {len(keep_rules.rules)}")
        
        # 详细分析每个规则
        for i, rule in enumerate(keep_rules.rules):
            logger.info(f"\n规则 {i+1}:")
            logger.info(f"  流ID: {rule.stream_id}")
            logger.info(f"  方向: {rule.direction}")
            logger.info(f"  序列号范围: {rule.seq_start} - {rule.seq_end}")
            logger.info(f"  长度: {rule.seq_end - rule.seq_start}")
            logger.info(f"  规则类型: {rule.rule_type}")
            
            if hasattr(rule, 'metadata') and rule.metadata:
                logger.info(f"  元数据:")
                for key, value in rule.metadata.items():
                    logger.info(f"    {key}: {value}")
        
        # 检查是否有过度合并的规则
        logger.info("\n规则合并分析:")
        large_rules = [rule for rule in keep_rules.rules if (rule.seq_end - rule.seq_start) > 500]
        if large_rules:
            logger.warning(f"发现 {len(large_rules)} 个大的保留区间（>500字节）:")
            for rule in large_rules:
                logger.warning(f"  流{rule.stream_id}:{rule.direction} - {rule.seq_start}:{rule.seq_end} "
                             f"(长度: {rule.seq_end - rule.seq_start})")
                logger.warning(f"  规则类型: {rule.rule_type}")
                
                # 检查是否包含了多种TLS消息类型
                if '+' in rule.rule_type:
                    logger.warning(f"  ⚠️  这个规则合并了多种TLS消息类型，可能包含了ApplicationData")
        
        return keep_rules
        
    except Exception as e:
        logger.error(f"分析Marker规则失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

def analyze_masker_processing():
    """分析Masker模块的处理逻辑"""
    logger = logging.getLogger(__name__)
    logger.info("=" * 80)
    logger.info("分析Masker模块处理逻辑")
    logger.info("=" * 80)
    
    input_file = "tests/samples/tls-single/tls_sample.pcap"
    output_file = "output/diagnose_masker_output.pcap"
    
    try:
        # 先获取保留规则
        keep_rules = analyze_marker_rules()
        if not keep_rules:
            logger.error("无法获取保留规则")
            return False
        
        from pktmask.core.pipeline.stages.mask_payload_v2.masker.payload_masker import PayloadMasker
        
        masker_config = {
            "enable_optimization": True,
            "debug_mode": True,
            "chunk_size": 1000
        }
        
        masker = PayloadMasker(masker_config)
        
        # 应用掩码规则
        logger.info("开始应用掩码规则...")
        masking_stats = masker.apply_masking(input_file, output_file, keep_rules)
        
        logger.info("掩码处理统计:")
        logger.info(f"  处理包数: {masking_stats.packets_processed}")
        logger.info(f"  修改包数: {masking_stats.packets_modified}")
        logger.info(f"  掩码字节数: {masking_stats.masked_bytes}")
        logger.info(f"  保留字节数: {masking_stats.preserved_bytes}")
        
        # 如果没有修改任何包，深入分析原因
        if masking_stats.packets_modified == 0:
            logger.warning("⚠️  没有任何数据包被修改，深入分析原因...")
            
            # 检查是否有TCP载荷数据包
            logger.info("检查输入文件中的TCP载荷数据包...")
            
            # 使用scapy直接读取文件分析
            try:
                from scapy.all import rdpcap, TCP
                
                packets = rdpcap(input_file)
                tcp_payload_packets = []
                
                for i, packet in enumerate(packets):
                    if packet.haslayer(TCP):
                        tcp_layer = packet[TCP]
                        if hasattr(tcp_layer, 'payload') and tcp_layer.payload:
                            payload_len = len(bytes(tcp_layer.payload))
                            if payload_len > 0:
                                tcp_payload_packets.append({
                                    'packet_num': i + 1,
                                    'tcp_seq': tcp_layer.seq,
                                    'payload_len': payload_len
                                })
                                logger.info(f"  包 {i+1}: TCP序列号={tcp_layer.seq}, 载荷长度={payload_len}")
                
                logger.info(f"总共发现 {len(tcp_payload_packets)} 个有TCP载荷的数据包")
                
                # 检查序列号匹配问题
                logger.info("\n检查序列号匹配:")
                for rule in keep_rules.rules:
                    logger.info(f"  规则: 流{rule.stream_id}:{rule.direction}, 序列号范围 {rule.seq_start}-{rule.seq_end}")
                    
                    matched_packets = []
                    for pkt in tcp_payload_packets:
                        pkt_seq = pkt['tcp_seq']
                        pkt_end = pkt_seq + pkt['payload_len']
                        
                        # 检查是否有重叠
                        if not (pkt_end <= rule.seq_start or rule.seq_end <= pkt_seq):
                            matched_packets.append(pkt)
                    
                    logger.info(f"    匹配的数据包: {len(matched_packets)}")
                    for pkt in matched_packets:
                        logger.info(f"      包 {pkt['packet_num']}: 序列号 {pkt['tcp_seq']}-{pkt['tcp_seq'] + pkt['payload_len']}")
                
            except Exception as e:
                logger.error(f"Scapy分析失败: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"分析Masker处理失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def main():
    """主诊断函数"""
    logger = setup_logging()
    
    print("PktMask MaskStage 问题诊断")
    print("=" * 80)
    
    # 步骤1: 分析原始TLS数据
    print("\n1. 分析原始TLS数据...")
    app_data_frames = analyze_original_tls_data()
    
    # 步骤2: 分析Marker规则
    print("\n2. 分析Marker模块保留规则...")
    keep_rules = analyze_marker_rules()
    
    # 步骤3: 分析Masker处理
    print("\n3. 分析Masker模块处理逻辑...")
    masker_success = analyze_masker_processing()
    
    print("\n" + "=" * 80)
    print("诊断总结:")
    
    if app_data_frames:
        print(f"✅ 发现 {len(app_data_frames)} 个ApplicationData消息需要掩码")
    else:
        print("❌ 未发现ApplicationData消息")
    
    if keep_rules and len(keep_rules.rules) > 0:
        print(f"✅ Marker模块生成了 {len(keep_rules.rules)} 条保留规则")
        
        # 检查规则合并问题
        large_rules = [rule for rule in keep_rules.rules if (rule.seq_end - rule.seq_start) > 500]
        if large_rules:
            print(f"⚠️  发现 {len(large_rules)} 个大的保留区间，可能存在过度合并问题")
    else:
        print("❌ Marker模块未生成有效的保留规则")
    
    if masker_success:
        print("✅ Masker模块处理完成")
    else:
        print("❌ Masker模块处理失败")
    
    print("\n详细日志已保存到: diagnose_maskstage_issue.log")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
