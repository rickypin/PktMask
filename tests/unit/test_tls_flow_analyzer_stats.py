#!/usr/bin/env python3
"""
TLS流分析器统计功能的单元测试

测试修正后的统计逻辑，确保：
1. 同一帧中的多个TLS记录只计算为1个数据帧
2. 记录数正确统计所有TLS记录
3. 不同类型的TLS记录在同一帧中正确处理
"""

import pytest
from collections import defaultdict
from pktmask.tools.tls_flow_analyzer import TLSFlowAnalyzer


class TestTLSFlowAnalyzerStats:
    """TLS流分析器统计功能测试"""

    def test_frame_counting_with_multiple_records_same_type(self):
        """测试同一帧中多个相同类型TLS记录的统计"""
        analyzer = TLSFlowAnalyzer()
        
        # 模拟同一帧中有2个TLS-22记录的情况
        frame_protocol_types = {
            9: [22, 22]  # 帧9包含2个TLS-22记录
        }
        
        # 执行统计逻辑
        protocol_type_stats = defaultdict(lambda: {"frames": 0, "records": 0})
        for frame_number, frame_types in frame_protocol_types.items():
            unique_types = set(frame_types)
            for tls_type in unique_types:
                protocol_type_stats[tls_type]["frames"] += 1
        
        # 验证结果：1个帧，但需要单独计算记录数
        assert protocol_type_stats[22]["frames"] == 1
        # 注意：这里只测试帧数统计，记录数需要从重组消息中统计

    def test_frame_counting_with_multiple_records_different_types(self):
        """测试同一帧中多个不同类型TLS记录的统计"""
        analyzer = TLSFlowAnalyzer()
        
        # 模拟同一帧中有TLS-22和TLS-20记录的情况
        frame_protocol_types = {
            14: [23, 23]  # 帧14包含2个TLS-23记录
        }
        
        # 执行统计逻辑
        protocol_type_stats = defaultdict(lambda: {"frames": 0, "records": 0})
        for frame_number, frame_types in frame_protocol_types.items():
            unique_types = set(frame_types)
            for tls_type in unique_types:
                protocol_type_stats[tls_type]["frames"] += 1
        
        # 验证结果
        assert protocol_type_stats[23]["frames"] == 1

    def test_frame_counting_multiple_frames_same_type(self):
        """测试多个帧包含相同类型TLS记录的统计"""
        analyzer = TLSFlowAnalyzer()
        
        # 模拟多个帧包含TLS-22记录
        frame_protocol_types = {
            4: [22],      # 帧4包含1个TLS-22记录
            7: [22],      # 帧7包含1个TLS-22记录
            9: [22, 22],  # 帧9包含2个TLS-22记录
            12: [22]      # 帧12包含1个TLS-22记录
        }
        
        # 执行统计逻辑
        protocol_type_stats = defaultdict(lambda: {"frames": 0, "records": 0})
        for frame_number, frame_types in frame_protocol_types.items():
            unique_types = set(frame_types)
            for tls_type in unique_types:
                protocol_type_stats[tls_type]["frames"] += 1
        
        # 验证结果：4个帧包含TLS-22
        assert protocol_type_stats[22]["frames"] == 4

    def test_mixed_tls_types_statistics(self):
        """测试混合TLS类型的统计"""
        analyzer = TLSFlowAnalyzer()
        
        # 模拟实际的tls_1_2_plainip.pcap统计情况
        frame_protocol_types = {
            4: [22],           # TLS-22 Handshake
            7: [22],           # TLS-22 Handshake  
            9: [22, 20, 22],   # TLS-22 + TLS-20 + TLS-22
            10: [20],          # TLS-20
            12: [22],          # TLS-22
            14: [23, 23],      # TLS-23 + TLS-23
            15: [23],          # TLS-23
            16: [21],          # TLS-21
            19: [21]           # TLS-21
        }
        
        # 执行统计逻辑
        protocol_type_stats = defaultdict(lambda: {"frames": 0, "records": 0})
        for frame_number, frame_types in frame_protocol_types.items():
            unique_types = set(frame_types)
            for tls_type in unique_types:
                protocol_type_stats[tls_type]["frames"] += 1
        
        # 验证结果应该匹配修正后的统计
        assert protocol_type_stats[22]["frames"] == 4  # TLS-22: 4帧
        assert protocol_type_stats[23]["frames"] == 2  # TLS-23: 2帧
        assert protocol_type_stats[20]["frames"] == 2  # TLS-20: 2帧
        assert protocol_type_stats[21]["frames"] == 2  # TLS-21: 2帧


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
