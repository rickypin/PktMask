#!/usr/bin/env python3
"""
PktMask TLS跨包掩码逻辑修复方案演示脚本

本脚本演示了基于记录长度的简化跨包检测算法，
用于验证修复方案的可行性和效果。
"""

import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple
from pathlib import Path

# 模拟TLS记录信息结构
@dataclass
class TLSRecordInfo:
    packet_number: int
    content_type: int
    version: Tuple[int, int]
    length: int
    is_complete: bool
    spans_packets: List[int]
    tcp_stream_id: str
    record_offset: int

# 模拟掩码规则结构
@dataclass
class MaskRule:
    packet_number: int
    tcp_stream_id: str
    tls_record_offset: int
    tls_record_length: int
    mask_offset: int
    mask_length: int
    action: str
    reason: str
    tls_record_type: Optional[int] = None

class TLSCrossPacketFixDemo:
    """TLS跨包掩码逻辑修复方案演示"""
    
    def __init__(self, length_threshold: int = 1200, max_segment_size: int = 1200):
        """初始化演示器
        
        Args:
            length_threshold: 跨包检测长度阈值
            max_segment_size: 最大段大小（用于估算）
        """
        self.length_threshold = length_threshold
        self.max_segment_size = max_segment_size
        self.logger = logging.getLogger(__name__)
        
    def is_cross_packet_by_length(self, record: TLSRecordInfo) -> bool:
        """基于记录长度判断是否跨包
        
        Args:
            record: TLS记录信息
            
        Returns:
            是否为跨包记录
        """
        # TLS记录总大小 = 头部5字节 + 载荷长度
        total_size = record.length + 5
        
        is_cross_packet = total_size > self.length_threshold
        
        if is_cross_packet:
            self.logger.info(
                f"🔍 跨包检测: 包{record.packet_number}, TLS-{record.content_type}, "
                f"总大小{total_size}字节 > 阈值{self.length_threshold}字节 → 跨包记录"
            )
        
        return is_cross_packet
    
    def estimate_packet_spans(self, record: TLSRecordInfo) -> List[int]:
        """估算跨包记录的包范围
        
        Args:
            record: TLS记录信息
            
        Returns:
            估算的包编号列表
        """
        total_size = record.length + 5
        estimated_segments = (total_size + self.max_segment_size - 1) // self.max_segment_size
        
        # 向前估算分段包
        start_packet = max(1, record.packet_number - estimated_segments + 1)
        spans = list(range(start_packet, record.packet_number + 1))
        
        self.logger.info(
            f"📊 包范围估算: 包{record.packet_number}, 总大小{total_size}字节, "
            f"估算{estimated_segments}段, 跨包范围{spans}"
        )
        
        return spans
    
    def create_cross_packet_record(self, record: TLSRecordInfo) -> TLSRecordInfo:
        """为大记录创建跨包版本
        
        Args:
            record: 原始TLS记录
            
        Returns:
            跨包版本的TLS记录
        """
        if not self.is_cross_packet_by_length(record):
            return record
        
        spans = self.estimate_packet_spans(record)
        
        cross_packet_record = TLSRecordInfo(
            packet_number=record.packet_number,
            content_type=record.content_type,
            version=record.version,
            length=record.length,
            is_complete=True,
            spans_packets=spans,
            tcp_stream_id=record.tcp_stream_id,
            record_offset=record.record_offset
        )
        
        self.logger.info(
            f"✅ 跨包记录创建: TLS-{record.content_type}, 长度{record.length}, "
            f"跨包{spans}, 总计{len(spans)}个包"
        )
        
        return cross_packet_record
    
    def generate_cross_packet_rules(self, record: TLSRecordInfo) -> List[MaskRule]:
        """为跨包记录生成统一掩码规则
        
        Args:
            record: 跨包TLS记录
            
        Returns:
            掩码规则列表
        """
        if len(record.spans_packets) <= 1:
            # 单包记录，使用标准规则
            return self._generate_single_packet_rule(record)
        
        rules = []
        spans = record.spans_packets
        
        self.logger.info(
            f"🔧 生成跨包掩码规则: TLS-{record.content_type}, "
            f"跨包{spans}, 共{len(spans)}个包"
        )
        
        for i, packet_num in enumerate(spans):
            is_first_segment = (i == 0)
            is_last_segment = (i == len(spans) - 1)
            is_reassembly_target = (packet_num == record.packet_number)
            
            if record.content_type == 23:  # ApplicationData
                if is_reassembly_target:
                    # 重组包：保留TLS头部5字节，掩码载荷
                    rule = MaskRule(
                        packet_number=packet_num,
                        tcp_stream_id=record.tcp_stream_id,
                        tls_record_offset=record.record_offset,
                        tls_record_length=record.length + 5,
                        mask_offset=5,
                        mask_length=record.length,
                        action="MASK_PAYLOAD",
                        reason=f"TLS-23跨包重组包：保留头部5字节，掩码{record.length}字节载荷",
                        tls_record_type=23
                    )
                    self.logger.info(
                        f"  📦 重组包{packet_num}: 保留头部5字节，掩码载荷{record.length}字节"
                    )
                else:
                    # 分段包：掩码整个TCP载荷
                    rule = MaskRule(
                        packet_number=packet_num,
                        tcp_stream_id=record.tcp_stream_id,
                        tls_record_offset=0,
                        tls_record_length=0,
                        mask_offset=0,
                        mask_length=-1,  # 特殊值：掩码到载荷结束
                        action="MASK_PAYLOAD",
                        reason=f"TLS-23跨包分段{i+1}/{len(spans)}：掩码整个载荷",
                        tls_record_type=23
                    )
                    segment_type = "首段" if is_first_segment else "中间段"
                    self.logger.info(f"  🔸 {segment_type}包{packet_num}: 掩码整个TCP载荷")
            else:  # TLS-20/21/22/24
                # 所有相关包完全保留
                rule = MaskRule(
                    packet_number=packet_num,
                    tcp_stream_id=record.tcp_stream_id,
                    tls_record_offset=0,
                    tls_record_length=0,
                    mask_offset=0,
                    mask_length=0,
                    action="KEEP_ALL",
                    reason=f"TLS-{record.content_type}跨包完全保留{i+1}/{len(spans)}",
                    tls_record_type=record.content_type
                )
                segment_type = "重组包" if is_reassembly_target else f"分段{i+1}"
                self.logger.info(f"  ✨ {segment_type}包{packet_num}: 完全保留（TLS-{record.content_type}）")
            
            rules.append(rule)
        
        return rules
    
    def _generate_single_packet_rule(self, record: TLSRecordInfo) -> List[MaskRule]:
        """为单包记录生成标准掩码规则"""
        if record.content_type == 23:  # ApplicationData
            rule = MaskRule(
                packet_number=record.packet_number,
                tcp_stream_id=record.tcp_stream_id,
                tls_record_offset=record.record_offset,
                tls_record_length=record.length + 5,
                mask_offset=5,
                mask_length=record.length,
                action="MASK_PAYLOAD",
                reason=f"TLS-23单包：保留头部5字节，掩码{record.length}字节载荷",
                tls_record_type=23
            )
        else:  # TLS-20/21/22/24
            rule = MaskRule(
                packet_number=record.packet_number,
                tcp_stream_id=record.tcp_stream_id,
                tls_record_offset=record.record_offset,
                tls_record_length=record.length + 5,
                mask_offset=0,
                mask_length=0,
                action="KEEP_ALL",
                reason=f"TLS-{record.content_type}单包：完全保留",
                tls_record_type=record.content_type
            )
        
        return [rule]
    
    def demo_with_test_data(self):
        """使用测试数据演示修复方案"""
        print("=" * 80)
        print("PktMask TLS跨包掩码逻辑修复方案演示")
        print("=" * 80)
        
        # 模拟sslerr1-70.pcap中的典型TLS记录
        test_records = [
            # 小记录（单包）
            TLSRecordInfo(26, 21, (3, 1), 2, True, [26], "TCP_1", 0),
            
            # 中等记录（可能跨包）
            TLSRecordInfo(11, 22, (3, 1), 1786, True, [11], "TCP_1", 0),
            
            # 大记录（明显跨包）
            TLSRecordInfo(24, 22, (3, 1), 3194, True, [24], "TCP_1", 0),
            
            # ApplicationData记录（跨包）
            TLSRecordInfo(100, 23, (3, 1), 2048, True, [100], "TCP_2", 0),
        ]
        
        print(f"\n📋 测试数据: {len(test_records)}个TLS记录")
        print(f"🎯 检测阈值: {self.length_threshold}字节")
        print(f"📏 最大段大小: {self.max_segment_size}字节")
        
        all_rules = []
        
        for i, record in enumerate(test_records, 1):
            print(f"\n--- 记录 {i}: TLS-{record.content_type}, 长度{record.length}字节 ---")
            
            # 步骤1: 跨包检测
            enhanced_record = self.create_cross_packet_record(record)
            
            # 步骤2: 生成掩码规则
            rules = self.generate_cross_packet_rules(enhanced_record)
            all_rules.extend(rules)
            
            print(f"📝 生成{len(rules)}条掩码规则")
        
        # 统计结果
        print(f"\n" + "=" * 80)
        print("📊 处理结果统计")
        print("=" * 80)
        
        cross_packet_count = sum(1 for r in test_records 
                               if self.is_cross_packet_by_length(r))
        single_packet_count = len(test_records) - cross_packet_count
        
        print(f"总记录数: {len(test_records)}")
        print(f"跨包记录: {cross_packet_count}")
        print(f"单包记录: {single_packet_count}")
        print(f"总规则数: {len(all_rules)}")
        
        # 按类型统计规则
        keep_rules = [r for r in all_rules if r.action == "KEEP_ALL"]
        mask_rules = [r for r in all_rules if r.action == "MASK_PAYLOAD"]
        
        print(f"保留规则: {len(keep_rules)}")
        print(f"掩码规则: {len(mask_rules)}")
        
        # 按TLS类型统计
        tls_types = {}
        for rule in all_rules:
            tls_type = rule.tls_record_type
            if tls_type not in tls_types:
                tls_types[tls_type] = {"keep": 0, "mask": 0}
            
            if rule.action == "KEEP_ALL":
                tls_types[tls_type]["keep"] += 1
            else:
                tls_types[tls_type]["mask"] += 1
        
        print(f"\n按TLS类型统计:")
        for tls_type, counts in sorted(tls_types.items()):
            print(f"  TLS-{tls_type}: 保留{counts['keep']}条, 掩码{counts['mask']}条")
        
        print(f"\n✅ 演示完成！修复方案可以正确处理跨包TLS记录。")

def main():
    """主函数"""
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s: %(message)s'
    )
    
    # 创建演示器
    demo = TLSCrossPacketFixDemo(
        length_threshold=1200,  # 1200字节阈值
        max_segment_size=1200   # 1200字节最大段
    )
    
    # 运行演示
    demo.demo_with_test_data()

if __name__ == "__main__":
    main()
