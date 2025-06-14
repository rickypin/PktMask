#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试Scapy对大量连续TCP Segment的Application Data重组/识别问题
"""

import logging
import tempfile
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import sys
import os

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from pktmask.core.trim.stages.pyshark_analyzer import PySharkAnalyzer, PacketAnalysis
from pktmask.core.trim.stages.scapy_rewriter import ScapyRewriter
from pktmask.core.trim.stages.base_stage import StageContext
from pktmask.core.trim.models.mask_table import StreamMaskTable
from pktmask.core.trim.models.mask_spec import MaskAfter
from pktmask.config.settings import AppConfig

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def create_test_scenario():
    """创建测试场景：大量连续TCP Segment的Application Data"""
    
    # 模拟大量连续TCP Segment的Application Data包
    packets = []
    
    # 创建30个连续的Application Data包
    for i in range(30):
        analysis = PacketAnalysis(
            packet_number=100 + i,
            timestamp=1000.0 + i * 0.1,
            stream_id="TCP_192.168.1.1:443_192.168.1.100:12345_forward",
            seq_number=1000 + i * 1400,  # 连续的序列号
            payload_length=1400,
            application_layer="TLS",
            is_tls_application_data=True,
            tls_content_type=23
        )
        packets.append(analysis)
    
    # 添加几个Handshake包
    packets.append(PacketAnalysis(
        packet_number=1046,
        timestamp=1003.0,
        stream_id="TCP_192.168.1.1:443_192.168.1.100:12345_forward",
        seq_number=43000,
        payload_length=500,
        application_layer="TLS",
        is_tls_handshake=True,
        tls_content_type=22
    ))
    
    packets.append(PacketAnalysis(
        packet_number=1119,
        timestamp=1003.1,
        stream_id="TCP_192.168.1.1:443_192.168.1.100:12345_forward",
        seq_number=43500,
        payload_length=300,
        application_layer="TLS",
        is_tls_handshake=True,
        tls_content_type=22
    ))
    
    return packets

def test_scapy_tcp_segment_processing():
    """测试Scapy对TCP段的处理"""
    
    print("开始测试Scapy TCP段处理...")
    
    # 使用真实的测试文件
    test_files = [
        "tests/data/samples/TLS/tls_capture.pcap",
        "tests/data/samples/TLS70/tls_mixed.pcap"
    ]
    
    for test_file in test_files:
        file_path = Path(test_file)
        if not file_path.exists():
            print(f"跳过不存在的测试文件: {file_path}")
            continue
            
        print(f"\n=== 测试文件: {file_path} ===")
        
        # 创建临时输出文件
        with tempfile.NamedTemporaryFile(suffix='.pcap', delete=False) as tmp_file:
            tmp_output = Path(tmp_file.name)
        
        try:
            # 第一步：PyShark分析
            print("步骤1: PyShark分析...")
            pyshark_analyzer = PySharkAnalyzer()
            pyshark_analyzer.initialize()
            
            # 创建TShark输出文件
            with tempfile.NamedTemporaryFile(suffix='.pcap', delete=False) as tshark_tmp:
                tshark_output = Path(tshark_tmp.name)
            
            # 复制原文件作为TShark输出
            import shutil
            shutil.copy2(file_path, tshark_output)
            
            pyshark_context = StageContext(
                input_file=str(file_path),
                output_file=tmp_output,
                tshark_output=str(tshark_output),
                app_config=AppConfig()
            )
            
            pyshark_result = pyshark_analyzer.execute(pyshark_context)
            
            if pyshark_result.success:
                print(f"  PyShark分析成功，掩码表条目: {pyshark_context.mask_table.get_total_entry_count()}")
                
                # 分析掩码表的TCP段分布
                analyze_mask_table_tcp_segments(pyshark_context.mask_table)
                
                # 第二步：Scapy回写
                print("步骤2: Scapy回写...")
                scapy_rewriter = ScapyRewriter()
                scapy_rewriter.initialize()
                
                scapy_context = StageContext(
                    input_file=str(file_path),  # 使用原始文件
                    output_file=tmp_output,
                    mask_table=pyshark_context.mask_table,
                    app_config=AppConfig()
                )
                
                scapy_result = scapy_rewriter.execute(scapy_context)
                
                if scapy_result.success:
                    print(f"  Scapy回写成功，修改包数: {scapy_result.additional_info.get('packets_modified', 0)}")
                else:
                    print(f"  Scapy回写失败: {scapy_result.error_message}")
            else:
                print(f"  PyShark分析失败: {pyshark_result.error_message}")
                
        except Exception as e:
            print(f"  测试失败: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # 清理临时文件
            if tmp_output.exists():
                tmp_output.unlink()
            if 'tshark_output' in locals() and tshark_output.exists():
                tshark_output.unlink()

def analyze_mask_table_tcp_segments(mask_table: StreamMaskTable):
    """分析掩码表中的TCP段分布"""
    
    print("  分析掩码表中的TCP段分布:")
    
    for stream_id, entries in mask_table._table.items():
        print(f"    流 {stream_id}:")
        
        # 按序列号排序
        sorted_entries = sorted(entries, key=lambda e: e.seq_start)
        
        # 检查连续性
        consecutive_segments = []
        current_segment = []
        
        for entry in sorted_entries:
            if not current_segment:
                current_segment = [entry]
            elif current_segment[-1].seq_end == entry.seq_start:
                # 连续的段
                current_segment.append(entry)
            else:
                # 非连续，保存当前段并开始新段
                if len(current_segment) > 1:
                    consecutive_segments.append(current_segment)
                current_segment = [entry]
        
        # 处理最后一个段
        if len(current_segment) > 1:
            consecutive_segments.append(current_segment)
        
        print(f"      总掩码条目: {len(entries)}")
        print(f"      连续TCP段组: {len(consecutive_segments)}")
        
        for i, segment_group in enumerate(consecutive_segments):
            if len(segment_group) > 5:  # 只显示大的连续段组
                start_seq = segment_group[0].seq_start
                end_seq = segment_group[-1].seq_end
                total_length = end_seq - start_seq
                print(f"        大连续段组{i+1}: {len(segment_group)}个段, seq:{start_seq}-{end_seq}, 总长度:{total_length}")
                
                # 检查掩码类型
                mask_types = set(type(e.mask_spec).__name__ for e in segment_group)
                print(f"          掩码类型: {mask_types}")

def test_tcp_segment_sequence_analysis():
    """测试TCP段序列号分析"""
    
    print("\n=== TCP段序列号分析测试 ===")
    
    # 模拟场景：分成多个TCP段的大TLS Application Data
    test_segments = [
        # 第一个大的Application Data，分成多个TCP段
        {"seq": 1000, "len": 1400, "type": "ApplicationData", "packet_num": 100},
        {"seq": 2400, "len": 1400, "type": "ApplicationData", "packet_num": 101},
        {"seq": 3800, "len": 1400, "type": "ApplicationData", "packet_num": 102},
        {"seq": 5200, "len": 1400, "type": "ApplicationData", "packet_num": 103},
        {"seq": 6600, "len": 1400, "type": "ApplicationData", "packet_num": 104},
        {"seq": 8000, "len": 1400, "type": "ApplicationData", "packet_num": 105},
        
        # 第二个大的Application Data，分成多个TCP段
        {"seq": 10000, "len": 1400, "type": "ApplicationData", "packet_num": 106},
        {"seq": 11400, "len": 1400, "type": "ApplicationData", "packet_num": 107},
        {"seq": 12800, "len": 1400, "type": "ApplicationData", "packet_num": 108},
        {"seq": 14200, "len": 1400, "type": "ApplicationData", "packet_num": 109},
        {"seq": 15600, "len": 1400, "type": "ApplicationData", "packet_num": 110},
        
        # 一个Handshake包
        {"seq": 17000, "len": 500, "type": "Handshake", "packet_num": 200},
    ]
    
    print("模拟TCP段序列:")
    for segment in test_segments:
        print(f"  包{segment['packet_num']}: seq={segment['seq']}, len={segment['len']}, type={segment['type']}")
    
    # 分析潜在的重组问题
    print("\n分析潜在重组问题:")
    
    # 检查是否有序列号重叠
    for i, seg1 in enumerate(test_segments):
        for j, seg2 in enumerate(test_segments[i+1:], i+1):
            seg1_end = seg1["seq"] + seg1["len"]
            seg2_start = seg2["seq"]
            
            if seg1_end > seg2_start:
                print(f"  ⚠️  序列号重叠: 包{seg1['packet_num']} (end={seg1_end}) 与 包{seg2['packet_num']} (start={seg2_start})")
            elif seg1_end == seg2_start:
                print(f"  ✅ 序列号连续: 包{seg1['packet_num']} -> 包{seg2['packet_num']}")
    
    # 检查大的连续Application Data段
    app_data_segments = [s for s in test_segments if s["type"] == "ApplicationData"]
    if len(app_data_segments) > 5:
        total_app_data_length = sum(s["len"] for s in app_data_segments)
        print(f"\n  📊 大量Application Data段检测:")
        print(f"     Application Data段数: {len(app_data_segments)}")
        print(f"     总Application Data长度: {total_app_data_length}")
        print(f"     这种场景可能触发Scapy的TCP重组逻辑问题")

if __name__ == "__main__":
    print("TCP Segment处理问题调试")
    print("=" * 50)
    
    # 测试1: 模拟场景分析
    test_tcp_segment_sequence_analysis()
    
    # 测试2: 实际文件处理
    test_scapy_tcp_segment_processing()
    
    print("\n" + "=" * 50)
    print("测试完成") 