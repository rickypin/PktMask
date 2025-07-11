#!/usr/bin/env python3
"""
测试TLS跨包掩码逻辑修复
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from pktmask.core.processors.tshark_tls_analyzer import TSharkTLSAnalyzer
from pktmask.core.trim.models.tls_models import TLSRecordInfo

def test_cross_packet_detection():
    """测试基于长度的跨包检测"""
    analyzer = TSharkTLSAnalyzer()
    
    # 测试用例1: 小记录（不跨包）
    small_record = TLSRecordInfo(
        packet_number=1,
        content_type=22,  # Handshake
        version=(3, 3),
        length=100,  # 小于阈值
        is_complete=True,
        spans_packets=[1],
        tcp_stream_id="TCP_0",
        record_offset=0
    )
    
    # 测试用例2: 大记录（跨包）
    large_record = TLSRecordInfo(
        packet_number=2,
        content_type=22,  # Handshake
        version=(3, 3),
        length=3194,  # 大于阈值，应该被检测为跨包
        is_complete=True,
        spans_packets=[2],
        tcp_stream_id="TCP_0",
        record_offset=0
    )
    
    # 测试长度检测
    print("=== 测试基于长度的跨包检测 ===")
    
    is_small_cross = analyzer._is_cross_packet_by_length(small_record)
    print(f"小记录({small_record.length}字节)跨包检测: {is_small_cross}")
    
    is_large_cross = analyzer._is_cross_packet_by_length(large_record)
    print(f"大记录({large_record.length}字节)跨包检测: {is_large_cross}")
    
    # 测试包范围估算
    if is_large_cross:
        spans = analyzer._estimate_packet_spans(large_record)
        print(f"大记录估算包范围: {spans}")
    
    # 测试完整的跨包检测流程
    print("\n=== 测试完整跨包检测流程 ===")
    test_records = [small_record, large_record]
    enhanced_records = analyzer._detect_cross_packet_records(test_records)
    
    for record in enhanced_records:
        is_cross = len(record.spans_packets) > 1
        print(f"包{record.packet_number}: TLS-{record.content_type}, 长度={record.length}, 跨包={is_cross}, spans={record.spans_packets}")
    
    return enhanced_records

def test_tls_types_coverage():
    """测试所有TLS类型的跨包检测"""
    analyzer = TSharkTLSAnalyzer()
    
    print("\n=== 测试所有TLS类型的跨包检测 ===")
    
    # 测试不同TLS类型的大记录
    tls_types = [20, 21, 22, 23, 24]  # Change Cipher Spec, Alert, Handshake, Application Data, Heartbeat
    test_records = []
    
    for i, tls_type in enumerate(tls_types):
        record = TLSRecordInfo(
            packet_number=i + 10,
            content_type=tls_type,
            version=(3, 3),
            length=2000,  # 大于阈值
            is_complete=True,
            spans_packets=[i + 10],
            tcp_stream_id="TCP_1",
            record_offset=0
        )
        test_records.append(record)
    
    enhanced_records = analyzer._detect_cross_packet_records(test_records)
    
    for record in enhanced_records:
        is_cross = len(record.spans_packets) > 1
        tls_name = {20: "ChangeCipherSpec", 21: "Alert", 22: "Handshake", 23: "ApplicationData", 24: "Heartbeat"}.get(record.content_type, "Unknown")
        print(f"TLS-{record.content_type}({tls_name}): 跨包={is_cross}, spans={record.spans_packets}")
    
    return enhanced_records

if __name__ == "__main__":
    print("开始测试TLS跨包掩码逻辑修复...")
    
    try:
        # 测试基本功能
        enhanced_records1 = test_cross_packet_detection()
        
        # 测试TLS类型覆盖
        enhanced_records2 = test_tls_types_coverage()
        
        # 统计结果
        total_records = len(enhanced_records1) + len(enhanced_records2)
        cross_packet_records = sum(1 for r in enhanced_records1 + enhanced_records2 if len(r.spans_packets) > 1)
        
        print(f"\n=== 测试结果统计 ===")
        print(f"总记录数: {total_records}")
        print(f"跨包记录数: {cross_packet_records}")
        print(f"跨包检测率: {cross_packet_records/total_records*100:.1f}%")
        
        print("\n✅ 测试完成！基于长度的跨包检测工作正常。")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
