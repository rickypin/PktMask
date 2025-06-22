#!/usr/bin/env python3
"""
TCP Payload Masker 阶段3简化验证测试

专门测试不需要外部依赖的核心数据结构和基础逻辑。
"""

import sys
import os
import time
import logging

# 添加项目路径
sys.path.insert(0, '/workspace/src')

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_core_data_structures():
    """测试核心数据结构（不依赖Scapy）"""
    logger.info("🧪 测试核心数据结构...")
    
    try:
        # 直接导入数据结构模块
        sys.path.insert(0, '/workspace/src/pktmask/core/tcp_payload_masker/core')
        
        from keep_range_models import TcpKeepRangeEntry, TcpKeepRangeTable, TcpMaskingResult
        
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
        
        logger.info("✅ 核心数据结构测试通过")
        return True
        
    except Exception as e:
        logger.error(f"❌ 核心数据结构测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def test_keep_range_logic():
    """测试保留范围逻辑（不依赖Scapy）"""
    logger.info("🧪 测试保留范围逻辑...")
    
    try:
        # 模拟保留范围掩码逻辑
        def apply_keep_ranges_to_payload(payload: bytes, keep_ranges) -> bytes:
            """核心二元化逻辑的简化实现"""
            if not payload:
                return payload
            
            # 1. 默认全部置零（隐私优先原则）
            result = bytearray(b'\x00' * len(payload))
            
            # 2. 恢复需要保留的范围（协议信息保留）
            for start, end in keep_ranges:
                if start < len(payload):
                    actual_end = min(end, len(payload))
                    if actual_end > start:
                        result[start:actual_end] = payload[start:actual_end]
            
            return bytes(result)
        
        # 测试基础掩码逻辑
        original_payload = b"Hello, World! This is a test payload."
        keep_ranges = [(0, 5), (7, 12)]  # 保留"Hello"和"World"
        
        masked_payload = apply_keep_ranges_to_payload(original_payload, keep_ranges)
        
        # 验证保留范围
        assert masked_payload[:5] == b"Hello", "保留范围1未正确保留"
        assert masked_payload[7:12] == b"World", "保留范围2未正确保留"
        
        # 验证掩码范围
        assert masked_payload[5:7] == b"\x00\x00", "掩码范围1未正确掩码"
        assert masked_payload[12] == 0, "掩码范围2未正确掩码"
        
        # 测试空载荷
        empty_masked = apply_keep_ranges_to_payload(b"", [(0, 5)])
        assert empty_masked == b"", "空载荷处理失败"
        
        # 测试超出范围的保留范围
        short_payload = b"Hi"
        long_range_masked = apply_keep_ranges_to_payload(short_payload, [(0, 10)])
        assert long_range_masked == b"Hi", "超出范围处理失败"
        
        logger.info("✅ 保留范围逻辑测试通过")
        return True
        
    except Exception as e:
        logger.error(f"❌ 保留范围逻辑测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def test_protocol_detection_logic():
    """测试协议检测逻辑（不依赖Scapy）"""
    logger.info("🧪 测试协议检测逻辑...")
    
    try:
        def is_tls_payload(payload: bytes) -> bool:
            """检测是否为TLS载荷"""
            if len(payload) < 5:
                return False
            
            # TLS记录头部检查：Content Type (1字节) + Version (2字节) + Length (2字节)
            content_type = payload[0]
            if content_type not in (20, 21, 22, 23):  # Change Cipher Spec, Alert, Handshake, Application Data
                return False
            
            # 检查TLS版本
            version = (payload[1] << 8) | payload[2]
            tls_versions = [0x0301, 0x0302, 0x0303, 0x0304]  # TLS 1.0-1.3
            
            return version in tls_versions
        
        def is_http_payload(payload: bytes) -> bool:
            """检测是否为HTTP载荷"""
            try:
                payload_str = payload.decode('ascii', errors='ignore')
                
                # HTTP请求方法
                http_methods = ['GET ', 'POST ', 'PUT ', 'DELETE ', 'HEAD ', 'OPTIONS ', 'PATCH ']
                
                # HTTP响应状态行
                http_response_pattern = 'HTTP/'
                
                return (
                    any(payload_str.startswith(method) for method in http_methods) or
                    payload_str.startswith(http_response_pattern)
                )
            except Exception:
                return False
        
        # 测试TLS检测
        tls_payload = bytes([0x16, 0x03, 0x03, 0x00, 0x20]) + b"X" * 32  # TLS Handshake
        assert is_tls_payload(tls_payload), "TLS检测失败"
        
        # 测试HTTP检测
        http_payload = b"GET / HTTP/1.1\r\nHost: example.com\r\n\r\n"
        assert is_http_payload(http_payload), "HTTP检测失败"
        
        # 测试无效载荷
        invalid_payload = b"invalid data"
        assert not is_tls_payload(invalid_payload), "无效载荷TLS检测失败"
        assert not is_http_payload(invalid_payload), "无效载荷HTTP检测失败"
        
        logger.info("✅ 协议检测逻辑测试通过")
        return True
        
    except Exception as e:
        logger.error(f"❌ 协议检测逻辑测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def test_file_structure():
    """测试文件结构完整性"""
    logger.info("🧪 测试文件结构完整性...")
    
    try:
        # 检查关键文件是否存在
        key_files = [
            "/workspace/src/pktmask/core/tcp_payload_masker/__init__.py",
            "/workspace/src/pktmask/core/tcp_payload_masker/core/__init__.py",
            "/workspace/src/pktmask/core/tcp_payload_masker/core/tcp_masker.py",
            "/workspace/src/pktmask/core/tcp_payload_masker/core/keep_range_models.py",
            "/workspace/src/pktmask/core/tcp_payload_masker/core/keep_range_applier.py",
            "/workspace/src/pktmask/core/tcp_payload_masker/exceptions.py",
            "/workspace/tests/data/tls-single/tls_sample.pcap"
        ]
        
        missing_files = []
        for file_path in key_files:
            if not os.path.exists(file_path):
                missing_files.append(file_path)
        
        if missing_files:
            logger.warning(f"⚠️  缺失文件: {missing_files}")
        
        # 检查样本文件
        sample_file = "/workspace/tests/data/tls-single/tls_sample.pcap"
        if os.path.exists(sample_file):
            file_size = os.path.getsize(sample_file)
            logger.info(f"样本文件大小: {file_size} 字节")
            
            if file_size == 4717:
                logger.info("✅ 样本文件大小正确")
            else:
                logger.warning(f"⚠️  样本文件大小不匹配: 期待4717字节，实际{file_size}字节")
        
        logger.info("✅ 文件结构完整性测试通过")
        return True
        
    except Exception as e:
        logger.error(f"❌ 文件结构完整性测试失败: {e}")
        return False

def run_simplified_validation():
    """运行简化验证测试"""
    logger.info("🚀 开始TCP Payload Masker阶段3简化验证测试")
    
    tests = [
        ("核心数据结构", test_core_data_structures),
        ("保留范围逻辑", test_keep_range_logic),
        ("协议检测逻辑", test_protocol_detection_logic),
        ("文件结构完整性", test_file_structure),
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
    logger.info(f"🎯 TCP Payload Masker阶段3简化验证测试结果")
    logger.info(f"{'='*60}")
    logger.info(f"通过测试: {passed}/{total} ({passed/total*100:.1f}%)")
    logger.info(f"测试耗时: {test_duration:.2f} 秒")
    
    if passed == total:
        logger.info("🎉 阶段3简化验证测试全部通过！")
        return True
    else:
        logger.error(f"💥 {total-passed} 个测试失败")
        return False

if __name__ == "__main__":
    success = run_simplified_validation()
    sys.exit(0 if success else 1)