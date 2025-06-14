#!/usr/bin/env python3
"""
综合载荷掩码问题诊断脚本
从多个角度交叉检验载荷掩码不生效的问题
"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from pathlib import Path
from typing import Dict, List, Any, Optional
import json

from pktmask.core.trim.models.mask_spec import MaskAfter, KeepAll, MaskRange
from pktmask.core.trim.models.mask_table import StreamMaskTable, StreamMaskEntry

def diagnose_maskafter_logic():
    """诊断MaskAfter逻辑问题"""
    print("=== 1. MaskAfter逻辑诊断 ===")
    
    # 测试各种载荷长度和MaskAfter参数组合
    test_cases = [
        (b"", 5, "空载荷"),
        (b"ABC", 5, "载荷小于keep_bytes"),
        (b"ABCD", 5, "载荷小于keep_bytes"),  
        (b"ABCDE", 5, "载荷等于keep_bytes"),
        (b"ABCDEF", 5, "载荷大于keep_bytes"),
        (b"ABCDEFGHIJK", 5, "载荷远大于keep_bytes"),
        (b"\x00\x00\x00\x00\x00\x00", 5, "全零载荷"),
        (b"\x00\x00\x00\x00", 5, "全零载荷(短)"),
    ]
    
    for payload, keep_bytes, desc in test_cases:
        mask = MaskAfter(keep_bytes)
        result = mask.apply_to_payload(payload)
        changed = payload != result
        
        print(f"  {desc}:")
        print(f"    原始: {payload.hex() if payload else '(空)'} (长度{len(payload)})")
        print(f"    结果: {result.hex() if result else '(空)'} (长度{len(result)})")
        print(f"    掩码: MaskAfter({keep_bytes})")
        print(f"    改变: {changed}")
        print()

def diagnose_scapy_rewriter_logic():
    """诊断Scapy回写器掩码应用逻辑"""
    print("=== 2. Scapy回写器掩码应用逻辑诊断 ===")
    
    # 模拟_apply_mask_spec的逻辑
    def simulate_apply_mask_spec(payload_bytes, start, end, mask_spec):
        """模拟_apply_mask_spec方法"""
        payload = bytearray(payload_bytes)
        original = bytes(payload)
        
        print(f"    模拟_apply_mask_spec: start={start}, end={end}, 载荷长度={len(payload)}")
        
        if isinstance(mask_spec, KeepAll):
            print(f"    KeepAll: 不修改载荷")
            return bytes(payload), original != bytes(payload)
        
        elif isinstance(mask_spec, MaskAfter):
            keep_bytes = mask_spec.keep_bytes
            mask_start = max(start, keep_bytes)
            
            print(f"    MaskAfter({keep_bytes}): mask_start={mask_start}")
            
            if mask_start < end:
                bytes_to_mask = end - mask_start
                print(f"    将掩码范围[{mask_start}:{end}), {bytes_to_mask}字节")
                
                for i in range(mask_start, end):
                    if i < len(payload):
                        old_byte = payload[i]
                        payload[i] = 0x00
                        print(f"      位置{i}: 0x{old_byte:02x} -> 0x00")
            else:
                print(f"    无需掩码 - mask_start({mask_start}) >= end({end})")
        
        return bytes(payload), original != bytes(payload)
    
    # 测试问题场景
    test_scenarios = [
        {
            "desc": "典型问题：MaskAfter(5)处理4字节载荷",
            "payload": b"\x00\x00\x00\x00",
            "masks": [(0, 4, MaskAfter(5))],
        },
        {
            "desc": "典型问题：MaskAfter(5)处理6字节载荷，只有1字节需要掩码",
            "payload": b"\x00\x00\x00\x00\x00\x00",
            "masks": [(0, 6, MaskAfter(5))],
        },
        {
            "desc": "正常情况：MaskAfter(5)处理大载荷",
            "payload": b"Hello, World! This is a test payload.",
            "masks": [(0, len(b"Hello, World! This is a test payload."), MaskAfter(5))],
        },
        {
            "desc": "全零载荷掩码问题",
            "payload": b"\x00" * 10,
            "masks": [(0, 10, MaskAfter(5))],
        },
        {
            "desc": "多个掩码应用",
            "payload": b"ABCDEFGHIJKLMNOP",
            "masks": [(0, 8, MaskAfter(3)), (8, 16, MaskAfter(2))],
        }
    ]
    
    for scenario in test_scenarios:
        print(f"  {scenario['desc']}:")
        print(f"    原始载荷: {scenario['payload'].hex()} (长度{len(scenario['payload'])})")
        
        payload = scenario['payload']
        for i, (start, end, mask_spec) in enumerate(scenario['masks']):
            print(f"    掩码{i+1}: [{start}:{end}) {mask_spec.get_description()}")
            payload, changed = simulate_apply_mask_spec(payload, start, end, mask_spec)
            print(f"    结果载荷: {payload.hex()} (改变: {changed})")
        print()

def diagnose_buffer_and_memory():
    """诊断buffer和内存相关问题"""
    print("=== 3. Buffer和内存问题诊断 ===")
    
    # 测试各种载荷大小
    sizes = [0, 1, 4, 5, 6, 64, 1024, 1460, 9000, 65536]
    
    for size in sizes:
        payload = b"A" * size
        mask = MaskAfter(5)
        
        try:
            result = mask.apply_to_payload(payload)
            changed = payload != result
            bytes_masked = sum(1 for i in range(len(result)) if i >= 5 and result[i] == 0)
            
            print(f"  载荷大小{size:5d}: 成功处理, 改变={changed}, 掩码字节数={bytes_masked}")
            
            # 检查结果完整性
            if len(result) != len(payload):
                print(f"    ⚠️ 长度不匹配: {len(payload)} -> {len(result)}")
            
            if size > 5:
                expected_mask_bytes = size - 5
                if bytes_masked != expected_mask_bytes:
                    print(f"    ⚠️ 掩码字节数不正确: 期望{expected_mask_bytes}, 实际{bytes_masked}")
                    
        except Exception as e:
            print(f"  载荷大小{size:5d}: 处理失败 - {e}")

def diagnose_sequence_number_matching():
    """诊断序列号匹配问题"""
    print("=== 4. 序列号匹配问题诊断 ===")
    
    # 创建测试掩码表
    mask_table = StreamMaskTable()
    
    # 添加测试条目
    test_entries = [
        ("TCP_10.3.221.132:18080_110.53.220.4:42516_forward", 1, 1461, MaskAfter(5)),
        ("TCP_10.3.221.132:18080_110.53.220.4:42516_forward", 1462, 2922, MaskAfter(5)),
        ("TCP_10.3.221.132:18080_110.53.220.4:42516_reverse", 1, 518, KeepAll()),
        ("TCP_10.3.221.132:18080_110.53.220.4:50563_forward", 1, 29145, MaskAfter(5)),
        ("TCP_10.3.221.132:18080_110.53.220.4:50563_reverse", 1, 9885, MaskAfter(5)),
    ]
    
    for stream_id, seq_start, seq_end, mask_spec in test_entries:
        mask_table.add_mask_range(stream_id, seq_start, seq_end, mask_spec)
    
    mask_table.finalize()
    
    print(f"  创建掩码表: {len(test_entries)}个条目")
    
    # 测试查找场景
    test_lookups = [
        # 精确匹配
        ("TCP_10.3.221.132:18080_110.53.220.4:42516_forward", 1, 6, "精确匹配开始"),
        ("TCP_10.3.221.132:18080_110.53.220.4:42516_forward", 1460, 6, "精确匹配结尾"),
        
        # 部分重叠
        ("TCP_10.3.221.132:18080_110.53.220.4:42516_forward", 1000, 100, "部分重叠"),
        
        # 跨边界
        ("TCP_10.3.221.132:18080_110.53.220.4:42516_forward", 1460, 10, "跨条目边界"),
        
        # 小载荷问题场景
        ("TCP_10.3.221.132:18080_110.53.220.4:50563_forward", 28223, 6, "小载荷6字节"),
        ("TCP_10.3.221.132:18080_110.53.220.4:50563_forward", 28223, 4, "小载荷4字节"),
        
        # 序列号偏移
        ("TCP_10.3.221.132:18080_110.53.220.4:50563_forward", 28230, 6, "序列号偏移"),
        
        # 不存在的流
        ("TCP_1.1.1.1:80_2.2.2.2:8080_forward", 1, 10, "不存在的流"),
    ]
    
    for stream_id, seq, length, desc in test_lookups:
        masks = mask_table.lookup_multiple(stream_id, seq, length)
        
        print(f"  {desc}:")
        print(f"    查找: 流={stream_id.split('_')[-2]}, 序列号={seq}, 长度={length}")
        print(f"    结果: {len(masks)}个掩码")
        
        if masks:
            for i, (start, end, spec) in enumerate(masks):
                print(f"      掩码{i+1}: [{start}:{end}) {spec.get_description()}")
                
                # 分析小载荷问题
                if isinstance(spec, MaskAfter) and length <= 5:
                    will_mask = start < end and spec.keep_bytes < end
                    print(f"        小载荷分析: keep_bytes={spec.keep_bytes}, 会掩码={will_mask}")
        print()

def diagnose_zero_payload_issue():
    """诊断全零载荷掩码识别问题"""
    print("=== 5. 全零载荷掩码识别问题诊断 ===")
    
    # 模拟日志中出现的全零载荷场景
    zero_payloads = [
        (b"\x00\x00\x00\x00\x00\x00", "6字节全零"),
        (b"\x00\x00\x00\x00", "4字节全零"),
        (b"\x00\x00", "2字节全零"),
    ]
    
    for payload, desc in zero_payloads:
        print(f"  {desc}: {payload.hex()}")
        
        # 测试不同的掩码
        masks_to_test = [
            MaskAfter(0),
            MaskAfter(5),
            MaskAfter(10),
            KeepAll(),
        ]
        
        for mask in masks_to_test:
            result = mask.apply_to_payload(payload)
            changed = payload != result
            
            print(f"    {mask.get_description()}: {result.hex()} (改变: {changed})")
            
            # 分析为什么没有改变
            if not changed:
                if isinstance(mask, MaskAfter):
                    if mask.keep_bytes >= len(payload):
                        print(f"      -> 原因: keep_bytes({mask.keep_bytes}) >= 载荷长度({len(payload)})")
                    elif all(b == 0 for b in payload[mask.keep_bytes:]):
                        print(f"      -> 原因: 需要掩码的部分已经是全零")
                elif isinstance(mask, KeepAll):
                    print(f"      -> 原因: KeepAll掩码")
        print()

def generate_comprehensive_report():
    """生成综合诊断报告"""
    print("=" * 60)
    print("载荷掩码问题综合诊断报告")
    print("=" * 60)
    
    diagnose_maskafter_logic()
    diagnose_scapy_rewriter_logic()
    diagnose_buffer_and_memory()
    diagnose_sequence_number_matching()
    diagnose_zero_payload_issue()
    
    print("=== 6. 问题根源总结 ===")
    print()
    
    issues = [
        {
            "问题": "MaskAfter(5)对小载荷无效",
            "原因": "当载荷长度≤5字节时，mask_start=max(0,5)=5，而end=载荷长度≤5，导致mask_start≥end，不执行掩码",
            "影响": "大量小TLS段（6字节心跳、4字节关闭通知等）无法被掩码",
            "解决方案": "调整MaskAfter逻辑，当载荷长度小于keep_bytes时，根据策略决定是完全保留还是部分掩码"
        },
        {
            "问题": "全零载荷掩码后看起来未改变",
            "原因": "载荷本身已经是全零，掩码成零后视觉上无变化，但逻辑上已处理",
            "影响": "触发'载荷未改变但存在非保留掩码'警告，造成困惑",
            "解决方案": "改进掩码后的变化检测逻辑，考虑原始内容特征"
        },
        {
            "问题": "序列号匹配精度问题",
            "原因": "Scapy重组可能导致序列号偏移，掩码表中的序列号与实际包序列号不完全匹配",
            "影响": "部分数据包找不到对应掩码",
            "解决方案": "增强模糊匹配和范围匹配机制"
        },
        {
            "问题": "掩码应用边界处理",
            "原因": "_apply_mask_spec中的边界条件判断可能存在off-by-one错误",
            "影响": "边界载荷可能掩码不完整",
            "解决方案": "重新审查边界条件和范围计算逻辑"
        }
    ]
    
    for i, issue in enumerate(issues, 1):
        print(f"问题{i}: {issue['问题']}")
        print(f"  原因: {issue['原因']}")
        print(f"  影响: {issue['影响']}")
        print(f"  解决方案: {issue['解决方案']}")
        print()
    
    print("=== 7. 推荐修复优先级 ===")
    priorities = [
        "🔥 高优先级：修复MaskAfter对小载荷的处理逻辑",
        "🔧 中优先级：改进全零载荷的变化检测机制",
        "📈 低优先级：增强序列号匹配容错性",
        "🧹 清理：优化日志输出，减少误导性警告"
    ]
    
    for priority in priorities:
        print(f"  {priority}")
    print()

if __name__ == "__main__":
    generate_comprehensive_report() 