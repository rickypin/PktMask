#!/usr/bin/env python3
"""
Phase 4 集成测试

验证 IndependentPcapMasker 主要API和核心掩码处理逻辑的集成效果。
"""

import os
import tempfile
import logging
from scapy.all import Ether, IP, TCP, Raw, wrpcap, rdpcap

from src.pktmask.core.independent_pcap_masker.core.masker import IndependentPcapMasker
from src.pktmask.core.independent_pcap_masker.core.models import MaskEntry, SequenceMaskTable


def create_test_pcap(file_path: str):
    """创建测试PCAP文件"""
    packets = []
    
    # 创建模拟TLS流量
    # TLS握手包
    tls_handshake = b"\x16\x03\x03\x00\x47" + b"handshake_data" * 5
    packets.append(
        Ether()/IP(src="192.168.1.10", dst="198.51.100.10")/TCP(sport=12345, dport=443, seq=1000)/Raw(load=tls_handshake)
    )
    
    # TLS应用数据包
    tls_app_data = b"\x17\x03\x03\x00\x40" + b"sensitive_application_data" * 8
    packets.extend([
        Ether()/IP(src="192.168.1.10", dst="198.51.100.10")/TCP(sport=12345, dport=443, seq=1100)/Raw(load=tls_app_data),
        Ether()/IP(src="192.168.1.10", dst="198.51.100.10")/TCP(sport=12345, dport=443, seq=1200)/Raw(load=tls_app_data),
        Ether()/IP(src="192.168.1.10", dst="198.51.100.10")/TCP(sport=12345, dport=443, seq=1300)/Raw(load=tls_app_data),
    ])
    
    # 写入PCAP文件
    wrpcap(file_path, packets)
    print(f"✅ 创建测试PCAP文件: {file_path}, {len(packets)} 个数据包")


def create_test_mask_table() -> SequenceMaskTable:
    """创建测试掩码表"""
    mask_table = SequenceMaskTable()
    
    # TLS握手包：完全保留
    mask_table.add_entry(MaskEntry(
        stream_id="TCP_192.168.1.10:12345_198.51.100.10:443_forward",
        sequence_start=1000,
        sequence_end=1100,
        mask_type="keep_all",
        mask_params={}
    ))
    
    # TLS应用数据包：保留TLS头部5字节，掩码其余内容
    mask_table.add_entry(MaskEntry(
        stream_id="TCP_192.168.1.10:12345_198.51.100.10:443_forward",
        sequence_start=1100,
        sequence_end=1400,
        mask_type="mask_after",
        mask_params={"keep_bytes": 5}
    ))
    
    print(f"✅ 创建掩码表: {mask_table.get_total_entries()} 个条目，{mask_table.get_streams_count()} 个流")
    return mask_table


def verify_masking_results(original_file: str, masked_file: str):
    """验证掩码处理结果"""
    print("\n🔍 验证掩码处理结果...")
    
    # 读取原始和掩码后的数据包
    original_packets = rdpcap(original_file)
    masked_packets = rdpcap(masked_file)
    
    assert len(original_packets) == len(masked_packets), "数据包数量不匹配"
    print(f"✅ 数据包数量一致: {len(original_packets)} 个")
    
    # 验证握手包未被修改（第一个包）
    orig_handshake = original_packets[0].getlayer(Raw).load
    masked_handshake = masked_packets[0].getlayer(Raw).load
    assert orig_handshake == masked_handshake, "TLS握手包不应被修改"
    print("✅ TLS握手包未被修改")
    
    # 验证应用数据包被正确掩码（后续包）
    for i in range(1, len(original_packets)):
        orig_payload = original_packets[i].getlayer(Raw).load
        masked_payload = masked_packets[i].getlayer(Raw).load
        
        # 检查长度相同
        assert len(orig_payload) == len(masked_payload), f"包{i}载荷长度不匹配"
        
        # 检查前5字节保留（TLS头部）
        assert orig_payload[:5] == masked_payload[:5], f"包{i}的TLS头部应被保留"
        
        # 检查后续字节被掩码
        assert all(b == 0x00 for b in masked_payload[5:]), f"包{i}的应用数据应被掩码"
        
        print(f"✅ 包{i}: TLS头部保留({len(orig_payload[:5])}字节)，应用数据掩码({len(orig_payload[5:])}字节)")


def test_phase4_integration():
    """Phase 4核心掩码处理集成测试"""
    print("🚀 开始Phase 4集成测试")
    
    # 配置日志
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)8s] %(name)s: %(message)s')
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # 创建测试文件路径
        input_pcap = os.path.join(temp_dir, "test_input.pcap")
        output_pcap = os.path.join(temp_dir, "test_output.pcap")
        
        try:
            # 步骤1: 创建测试数据
            print("\n📦 创建测试数据...")
            create_test_pcap(input_pcap)
            mask_table = create_test_mask_table()
            
            # 步骤2: 初始化掩码处理器
            print("\n⚙️ 初始化掩码处理器...")
            config = {
                'mask_byte_value': 0x00,
                'disable_protocol_parsing': True,
                'strict_consistency_mode': True
            }
            masker = IndependentPcapMasker(config)
            print("✅ 掩码处理器初始化完成")
            
            # 步骤3: 执行掩码处理
            print("\n🎯 执行掩码处理...")
            result = masker.mask_pcap_with_sequences(input_pcap, mask_table, output_pcap)
            
            # 步骤4: 验证处理结果
            print("\n📊 处理结果:")
            print(f"  - 成功: {result.success}")
            print(f"  - 总数据包: {result.total_packets}")
            print(f"  - 修改数据包: {result.modified_packets}")
            print(f"  - 掩码字节数: {result.bytes_masked}")
            print(f"  - 处理时间: {result.processing_time:.3f}秒")
            print(f"  - 处理速度: {result.get_processing_speed():.1f} pps")
            print(f"  - 修改率: {result.get_modification_rate():.1%}")
            
            # 验证基本指标
            assert result.success == True, "处理应该成功"
            assert result.total_packets == 4, f"应该有4个数据包，实际: {result.total_packets}"
            assert result.modified_packets == 3, f"应该修改3个数据包，实际: {result.modified_packets}"
            assert result.bytes_masked > 0, "应该有字节被掩码"
            assert result.processing_time > 0, "应该有处理时间"
            
            print("✅ 处理结果验证通过")
            
            # 步骤5: 验证输出文件
            assert os.path.exists(output_pcap), "输出文件应该存在"
            verify_masking_results(input_pcap, output_pcap)
            
            # 步骤6: 验证统计信息
            print("\n📈 详细统计信息:")
            stats = result.statistics
            if stats:
                mask_stats = stats.get('mask_application_stats', {})
                print(f"  - 序列号匹配率: {mask_stats.get('sequence_match_rate', 0):.1%}")
                print(f"  - 应用成功率: {mask_stats.get('application_success_rate', 0):.1%}")
                print(f"  - MaskAfter应用次数: {mask_stats.get('mask_after_applied', 0)}")
                print(f"  - KeepAll应用次数: {mask_stats.get('keep_all_applied', 0)}")
                
                # 验证协议解析禁用效果
                protocol_stats = stats.get('protocol_parsing_verification', {})
                if protocol_stats:
                    raw_rate = protocol_stats.get('raw_layer_rate', 0)
                    print(f"  - Raw层存在率: {raw_rate:.1%}")
                    assert raw_rate >= 0.9, f"Raw层存在率应该>=90%，实际: {raw_rate:.1%}"
                    print("✅ 协议解析禁用效果验证通过")
            
            print("\n🎉 Phase 4集成测试完成！所有验证通过。")
            
            return result
            
        except Exception as e:
            print(f"\n❌ 集成测试失败: {e}")
            raise


if __name__ == "__main__":
    # 运行集成测试
    result = test_phase4_integration()
    
    print(f"\n✨ 最终结果摘要: {result.get_summary()}")
    print("✅ Phase 4核心掩码处理逻辑实现成功！") 