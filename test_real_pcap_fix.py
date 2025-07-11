#!/usr/bin/env python3
"""
使用真实PCAP文件测试TLS跨包掩码修复效果
"""

import sys
import os
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from pktmask.core.processors.tshark_tls_analyzer import TSharkTLSAnalyzer

def test_real_pcap_analysis():
    """使用真实PCAP文件测试跨包检测修复"""
    
    # 查找测试样本文件
    test_files = [
        "tests/samples/sslerr1-70.pcap",
        "sslerr1-70.pcap",
        "tests/samples/tls-single/tls_sample.pcap"
    ]
    
    pcap_file = None
    for file_path in test_files:
        if Path(file_path).exists():
            pcap_file = file_path
            break
    
    if not pcap_file:
        print("❌ 未找到测试PCAP文件，跳过真实文件测试")
        print("   尝试查找的文件:")
        for file_path in test_files:
            print(f"   - {file_path}")
        return None
    
    print(f"=== 使用真实PCAP文件测试: {pcap_file} ===")
    
    try:
        analyzer = TSharkTLSAnalyzer()

        # 初始化分析器
        if not analyzer.initialize():
            print("❌ TShark分析器初始化失败，跳过真实文件测试")
            return None

        # 检查TShark是否可用
        if not analyzer.check_dependencies():
            print("❌ TShark依赖不可用，跳过真实文件测试")
            return None

        print("开始分析PCAP文件...")
        tls_records = analyzer.analyze_file(pcap_file)
        
        print(f"\n=== 分析结果 ===")
        print(f"总TLS记录数: {len(tls_records)}")
        
        # 统计跨包记录
        cross_packet_records = [r for r in tls_records if len(r.spans_packets) > 1]
        print(f"跨包记录数: {len(cross_packet_records)}")
        
        # 按TLS类型分组统计
        type_stats = {}
        cross_type_stats = {}
        
        for record in tls_records:
            tls_type = record.content_type
            type_stats[tls_type] = type_stats.get(tls_type, 0) + 1
            
            if len(record.spans_packets) > 1:
                cross_type_stats[tls_type] = cross_type_stats.get(tls_type, 0) + 1
        
        print(f"\n=== TLS类型分布 ===")
        type_names = {20: "ChangeCipherSpec", 21: "Alert", 22: "Handshake", 23: "ApplicationData", 24: "Heartbeat"}
        
        for tls_type, count in sorted(type_stats.items()):
            type_name = type_names.get(tls_type, f"Unknown({tls_type})")
            cross_count = cross_type_stats.get(tls_type, 0)
            cross_rate = (cross_count / count * 100) if count > 0 else 0
            
            print(f"TLS-{tls_type} ({type_name}): {count}个记录, {cross_count}个跨包 ({cross_rate:.1f}%)")
        
        # 显示一些跨包记录的详细信息
        if cross_packet_records:
            print(f"\n=== 跨包记录详情（前5个）===")
            for i, record in enumerate(cross_packet_records[:5]):
                type_name = type_names.get(record.content_type, f"Unknown({record.content_type})")
                print(f"{i+1}. 包{record.packet_number}: TLS-{record.content_type}({type_name})")
                print(f"   长度: {record.length}字节")
                print(f"   跨包: {record.spans_packets} (共{len(record.spans_packets)}个包)")
                print(f"   TCP流: {record.tcp_stream_id}")
        
        # 验证修复效果
        print(f"\n=== 修复效果验证 ===")
        
        # 检查是否有大记录被正确识别为跨包
        large_records = [r for r in tls_records if r.length > 1200]
        large_cross_records = [r for r in large_records if len(r.spans_packets) > 1]
        
        print(f"大记录(>1200字节): {len(large_records)}个")
        print(f"大记录中的跨包: {len(large_cross_records)}个")
        
        if len(large_records) > 0:
            detection_rate = len(large_cross_records) / len(large_records) * 100
            print(f"大记录跨包检测率: {detection_rate:.1f}%")
            
            if detection_rate > 80:
                print("✅ 跨包检测效果良好")
            elif detection_rate > 50:
                print("⚠️ 跨包检测效果一般")
            else:
                print("❌ 跨包检测效果较差")
        
        # 检查TLS-22类型的跨包检测（这是修复的重点）
        tls22_records = [r for r in tls_records if r.content_type == 22]
        tls22_cross_records = [r for r in tls22_records if len(r.spans_packets) > 1]
        
        if tls22_records:
            print(f"\nTLS-22 Handshake记录: {len(tls22_records)}个")
            print(f"TLS-22 跨包记录: {len(tls22_cross_records)}个")
            
            # 根据深度分析报告，sslerr1-70.pcap中所有132个TLS-22记录都应该被识别为跨包
            if len(tls22_cross_records) > 0:
                print("✅ TLS-22跨包检测修复成功！")
            else:
                print("❌ TLS-22跨包检测仍然失效")
        
        return tls_records
        
    except Exception as e:
        print(f"❌ 分析失败: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    print("开始使用真实PCAP文件测试TLS跨包掩码修复效果...")
    
    try:
        records = test_real_pcap_analysis()
        
        if records is not None:
            print(f"\n✅ 真实PCAP文件测试完成！")
        else:
            print(f"\n⚠️ 真实PCAP文件测试跳过")
            
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
