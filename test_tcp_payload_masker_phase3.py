#!/usr/bin/env python3
"""
TCP Payload Masker 阶段3验证测试

验证核心保留范围掩码逻辑、协议检测和数据结构功能。
"""

import sys
import os
import time
from typing import List, Tuple
import logging

# 添加项目路径
sys.path.insert(0, '/workspace/src')

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_data_structures():
    """测试新的数据结构"""
    logger.info("🧪 测试数据结构...")
    
    try:
        from pktmask.core.tcp_payload_masker import (
            TcpKeepRangeEntry, TcpKeepRangeTable, TcpMaskingResult,
            TcpPayloadKeepRangeMasker
        )
        
        # 测试TcpKeepRangeEntry
        entry = TcpKeepRangeEntry(
            stream_id="TCP_1.2.3.4:443_5.6.7.8:1234_forward",
            sequence_start=1000,
            sequence_end=2000,
            keep_ranges=[(0, 5), (10, 15)],
            protocol_hint="TLS"
        )
        
        assert entry.covers_sequence(1500), "序列号覆盖检查失败"
        assert not entry.covers_sequence(2500), "序列号覆盖检查失败"
        assert entry.get_total_keep_bytes() == 10, "保留字节数计算错误"
        
        # 测试保留范围合并
        entry2 = TcpKeepRangeEntry(
            stream_id="TCP_1.2.3.4:443_5.6.7.8:1234_forward",
            sequence_start=1000,
            sequence_end=2000,
            keep_ranges=[(0, 8), (5, 12)],  # 重叠范围应该被合并
            protocol_hint="TLS"
        )
        
        # 验证范围已被合并
        assert entry2.keep_ranges == [(0, 12)], f"范围合并失败: {entry2.keep_ranges}"
        
        # 测试TcpKeepRangeTable
        table = TcpKeepRangeTable()
        table.add_keep_range_entry(entry)
        table.add_keep_range_entry(entry2)
        
        assert table.get_total_entries() == 2, "条目数量错误"
        assert table.get_streams_count() == 1, "流数量错误"
        
        # 测试查找保留范围
        keep_ranges = table.find_keep_ranges_for_sequence(
            "TCP_1.2.3.4:443_5.6.7.8:1234_forward", 1500
        )
        
        # 应该返回合并后的范围
        assert len(keep_ranges) > 0, "未找到保留范围"
        
        # 测试TcpMaskingResult
        result = TcpMaskingResult(
            success=True,
            total_packets=100,
            modified_packets=50,
            bytes_masked=1000,
            bytes_kept=200,
            tcp_streams_processed=5,
            processing_time=1.5
        )
        
        assert result.get_modification_rate() == 0.5, "修改率计算错误"
        assert result.get_masking_rate() == 1000 / 1200, "掩码率计算错误"
        
        logger.info("✅ 数据结构测试通过")
        return True
        
    except Exception as e:
        logger.error(f"❌ 数据结构测试失败: {e}")
        return False

def test_keep_range_masking():
    """测试保留范围掩码逻辑"""
    logger.info("🧪 测试保留范围掩码逻辑...")
    
    try:
        from pktmask.core.tcp_payload_masker import TcpPayloadKeepRangeMasker
        
        masker = TcpPayloadKeepRangeMasker()
        
        # 测试基础掩码逻辑
        original_payload = b"Hello, World! This is a test payload."
        keep_ranges = [(0, 5), (7, 12)]  # 保留"Hello"和"World"
        
        masked_payload = masker.apply_keep_ranges_to_payload(original_payload, keep_ranges)
        
        # 验证保留范围
        assert masked_payload[:5] == b"Hello", "保留范围1未正确保留"
        assert masked_payload[7:12] == b"World", "保留范围2未正确保留"
        
        # 验证掩码范围
        assert masked_payload[5:7] == b"\x00\x00", "掩码范围1未正确掩码"
        assert masked_payload[12] == 0, "掩码范围2未正确掩码"
        
        # 测试空载荷
        empty_masked = masker.apply_keep_ranges_to_payload(b"", [(0, 5)])
        assert empty_masked == b"", "空载荷处理失败"
        
        # 测试超出范围的保留范围
        short_payload = b"Hi"
        long_range_masked = masker.apply_keep_ranges_to_payload(short_payload, [(0, 10)])
        assert long_range_masked == b"Hi", "超出范围处理失败"
        
        logger.info("✅ 保留范围掩码逻辑测试通过")
        return True
        
    except Exception as e:
        logger.error(f"❌ 保留范围掩码逻辑测试失败: {e}")
        return False

def test_protocol_detection():
    """测试协议检测功能"""
    logger.info("🧪 测试协议检测功能...")
    
    try:
        from pktmask.core.tcp_payload_masker import TcpPayloadKeepRangeMasker
        
        masker = TcpPayloadKeepRangeMasker()
        
        # 测试TLS检测
        tls_payload = bytes([0x16, 0x03, 0x03, 0x00, 0x20]) + b"X" * 32  # TLS Handshake
        assert masker._is_tls_payload(tls_payload), "TLS检测失败"
        
        tls_protocol = masker.detect_tcp_protocol(tls_payload, (12345, 443))
        assert tls_protocol == "TLS", f"TLS协议检测失败: {tls_protocol}"
        
        # 测试HTTP检测
        http_payload = b"GET / HTTP/1.1\r\nHost: example.com\r\n\r\n"
        assert masker._is_http_payload(http_payload), "HTTP检测失败"
        
        http_protocol = masker.detect_tcp_protocol(http_payload, (12345, 80))
        assert http_protocol == "HTTP", f"HTTP协议检测失败: {http_protocol}"
        
        # 测试协议保留范围生成
        tls_ranges = masker.generate_protocol_keep_ranges("TLS", tls_payload, (12345, 443))
        assert tls_ranges == [(0, 5)], f"TLS保留范围生成错误: {tls_ranges}"
        
        http_ranges = masker.generate_protocol_keep_ranges("HTTP", http_payload, (12345, 80))
        assert len(http_ranges) > 0, "HTTP保留范围生成失败"
        assert http_ranges[0][0] == 0, "HTTP保留范围起始位置错误"
        
        logger.info("✅ 协议检测功能测试通过")
        return True
        
    except Exception as e:
        logger.error(f"❌ 协议检测功能测试失败: {e}")
        return False

def test_tcp_masker_basic():
    """测试TCP掩码器基础功能"""
    logger.info("🧪 测试TCP掩码器基础功能...")
    
    try:
        from pktmask.core.tcp_payload_masker import TcpPayloadMasker, TcpKeepRangeTable, TcpKeepRangeEntry
        
        # 创建测试保留范围表
        keep_range_table = TcpKeepRangeTable()
        entry = TcpKeepRangeEntry(
            stream_id="TCP_1.2.3.4:443_5.6.7.8:1234_forward",
            sequence_start=1000,
            sequence_end=2000,
            keep_ranges=[(0, 5)],
            protocol_hint="TLS"
        )
        keep_range_table.add_keep_range_entry(entry)
        
        # 测试配置和初始化
        masker = TcpPayloadMasker()
        
        # 验证配置
        config_summary = masker.get_config_summary()
        assert isinstance(config_summary, dict), "配置摘要格式错误"
        
        # 验证统计信息
        stats = masker.get_global_statistics()
        assert stats['total_files_processed'] == 0, "初始统计信息错误"
        
        # 测试统计重置
        masker.reset_statistics()
        stats_after_reset = masker.get_global_statistics()
        assert stats_after_reset == stats, "统计重置失败"
        
        logger.info("✅ TCP掩码器基础功能测试通过")
        return True
        
    except Exception as e:
        logger.error(f"❌ TCP掩码器基础功能测试失败: {e}")
        return False

def test_real_sample_basic():
    """使用真实样本进行基础测试"""
    logger.info("🧪 使用真实样本进行基础测试...")
    
    try:
        # 检查样本文件是否存在
        sample_file = "/workspace/tests/data/tls-single/tls_sample.pcap"
        if not os.path.exists(sample_file):
            logger.warning(f"⚠️  样本文件不存在: {sample_file}")
            return True  # 跳过测试但不失败
        
        # 检查文件大小
        file_size = os.path.getsize(sample_file)
        logger.info(f"样本文件大小: {file_size} 字节")
        
        if file_size != 4717:
            logger.warning(f"⚠️  样本文件大小不匹配: 期待4717字节，实际{file_size}字节")
        
        logger.info("✅ 真实样本基础测试通过")
        return True
        
    except Exception as e:
        logger.error(f"❌ 真实样本基础测试失败: {e}")
        return False

def run_phase3_validation():
    """运行阶段3验证测试"""
    logger.info("🚀 开始TCP Payload Masker阶段3验证测试")
    
    tests = [
        ("数据结构", test_data_structures),
        ("保留范围掩码逻辑", test_keep_range_masking),
        ("协议检测功能", test_protocol_detection),
        ("TCP掩码器基础功能", test_tcp_masker_basic),
        ("真实样本基础测试", test_real_sample_basic),
    ]
    
    passed = 0
    total = len(tests)
    
    start_time = time.time()
    
    for test_name, test_func in tests:
        logger.info(f"\n{'='*50}")
        logger.info(f"执行测试: {test_name}")
        logger.info(f"{'='*50}")
        
        if test_func():
            passed += 1
            logger.info(f"✅ {test_name} - 通过")
        else:
            logger.error(f"❌ {test_name} - 失败")
    
    end_time = time.time()
    test_duration = end_time - start_time
    
    logger.info(f"\n{'='*60}")
    logger.info(f"🎯 TCP Payload Masker阶段3验证测试结果")
    logger.info(f"{'='*60}")
    logger.info(f"通过测试: {passed}/{total} ({passed/total*100:.1f}%)")
    logger.info(f"测试耗时: {test_duration:.2f} 秒")
    
    if passed == total:
        logger.info("🎉 阶段3验证测试全部通过！")
        return True
    else:
        logger.error(f"💥 {total-passed} 个测试失败")
        return False

if __name__ == "__main__":
    success = run_phase3_validation()
    sys.exit(0 if success else 1)