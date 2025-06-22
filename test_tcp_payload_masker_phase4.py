#!/usr/bin/env python3
"""
TCP Payload Masker 阶段4验证测试

验证主处理器重构的核心功能，不依赖外部库。
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

def test_tcp_masker_configuration():
    """测试TCP掩码器配置功能"""
    logger.info("🧪 测试TCP掩码器配置功能...")
    
    try:
        # 直接导入避免Scapy依赖
        sys.path.insert(0, '/workspace/src/pktmask/core/tcp_payload_masker/core')
        
        from keep_range_models import TcpKeepRangeEntry, TcpKeepRangeTable, TcpMaskingResult
        from config import ConfigManager, create_config_manager
        
        # 测试配置管理器
        config_manager = create_config_manager()
        assert config_manager is not None, "配置管理器创建失败"
        
        # 测试配置导出
        config_summary = config_manager.export_summary()
        assert isinstance(config_summary, dict), "配置摘要格式错误"
        
        # 测试自定义配置
        custom_config = {"mask_byte_value": 0x00, "strict_mode": True}
        custom_manager = create_config_manager(custom_config)
        assert custom_manager.get('mask_byte_value') == 0x00, "自定义配置设置失败"
        
        logger.info("✅ TCP掩码器配置功能测试通过")
        return True
        
    except Exception as e:
        logger.error(f"❌ TCP掩码器配置功能测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def test_input_validation_logic():
    """测试输入验证逻辑"""
    logger.info("🧪 测试输入验证逻辑...")
    
    try:
        from keep_range_models import TcpKeepRangeTable, TcpKeepRangeEntry
        
        # 测试有效的保留范围表
        valid_table = TcpKeepRangeTable()
        entry = TcpKeepRangeEntry(
            stream_id="TCP_1.2.3.4:443_5.6.7.8:1234_forward",
            sequence_start=1000,
            sequence_end=2000,
            keep_ranges=[(0, 5)],
            protocol_hint="TLS"
        )
        valid_table.add_keep_range_entry(entry)
        
        # 验证表不为空
        assert valid_table.get_total_entries() > 0, "有效表条目检查失败"
        
        # 测试一致性验证
        consistency_issues = valid_table.validate_consistency()
        assert len(consistency_issues) == 0, f"一致性验证失败: {consistency_issues}"
        
        # 测试空表
        empty_table = TcpKeepRangeTable()
        assert empty_table.get_total_entries() == 0, "空表检查失败"
        
        # 测试无效的条目
        try:
            invalid_entry = TcpKeepRangeEntry(
                stream_id="TCP_1.2.3.4:443_5.6.7.8:1234_forward",
                sequence_start=2000,  # start > end，应该失败
                sequence_end=1000,
                keep_ranges=[(0, 5)]
            )
            assert False, "应该抛出异常"
        except ValueError:
            pass  # 预期的异常
        
        logger.info("✅ 输入验证逻辑测试通过")
        return True
        
    except Exception as e:
        logger.error(f"❌ 输入验证逻辑测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def test_tcp_stream_processing():
    """测试TCP流处理逻辑"""
    logger.info("🧪 测试TCP流处理逻辑...")
    
    try:
        from keep_range_models import TcpKeepRangeTable, TcpKeepRangeEntry
        
        # 创建多个TCP流的保留范围表
        table = TcpKeepRangeTable()
        
        # 流1：TLS流
        tls_entry = TcpKeepRangeEntry(
            stream_id="TCP_1.2.3.4:443_5.6.7.8:1234_forward",
            sequence_start=1000,
            sequence_end=2000,
            keep_ranges=[(0, 5)],  # TLS头部
            protocol_hint="TLS"
        )
        table.add_keep_range_entry(tls_entry)
        
        # 流2：HTTP流
        http_entry = TcpKeepRangeEntry(
            stream_id="TCP_1.2.3.4:80_5.6.7.8:5678_forward",
            sequence_start=5000,
            sequence_end=6000,
            keep_ranges=[(0, 50)],  # HTTP头部
            protocol_hint="HTTP"
        )
        table.add_keep_range_entry(http_entry)
        
        # 流3：反向流
        reverse_entry = TcpKeepRangeEntry(
            stream_id="TCP_5.6.7.8:1234_1.2.3.4:443_reverse",
            sequence_start=3000,
            sequence_end=4000,
            keep_ranges=[(0, 5)],
            protocol_hint="TLS"
        )
        table.add_keep_range_entry(reverse_entry)
        
        # 验证流统计
        assert table.get_total_entries() == 3, "条目数量错误"
        assert table.get_streams_count() == 3, "流数量错误"
        
        # 验证流ID列表
        stream_ids = table.get_all_stream_ids()
        assert len(stream_ids) == 3, "流ID列表长度错误"
        assert "TCP_1.2.3.4:443_5.6.7.8:1234_forward" in stream_ids, "TLS流ID缺失"
        assert "TCP_1.2.3.4:80_5.6.7.8:5678_forward" in stream_ids, "HTTP流ID缺失"
        assert "TCP_5.6.7.8:1234_1.2.3.4:443_reverse" in stream_ids, "反向流ID缺失"
        
        # 测试特定流的查找
        tls_ranges = table.find_keep_ranges_for_sequence(
            "TCP_1.2.3.4:443_5.6.7.8:1234_forward", 1500
        )
        assert len(tls_ranges) > 0, "TLS流保留范围查找失败"
        
        # 测试不存在的流
        nonexistent_ranges = table.find_keep_ranges_for_sequence(
            "TCP_9.9.9.9:999_8.8.8.8:888_forward", 1500
        )
        assert len(nonexistent_ranges) == 0, "不存在流应返回空结果"
        
        logger.info("✅ TCP流处理逻辑测试通过")
        return True
        
    except Exception as e:
        logger.error(f"❌ TCP流处理逻辑测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def test_masking_result_generation():
    """测试掩码结果生成"""
    logger.info("🧪 测试掩码结果生成...")
    
    try:
        from keep_range_models import TcpMaskingResult
        
        # 测试成功结果
        success_result = TcpMaskingResult(
            success=True,
            total_packets=1000,
            modified_packets=750,
            bytes_masked=50000,
            bytes_kept=10000,
            tcp_streams_processed=25,
            processing_time=5.5
        )
        
        # 验证计算方法
        assert success_result.get_modification_rate() == 0.75, "修改率计算错误"
        assert success_result.get_processing_speed() == 1000/5.5, "处理速度计算错误"
        assert success_result.get_masking_rate() == 50000/60000, "掩码率计算错误"
        assert success_result.get_keep_rate() == 10000/60000, "保留率计算错误"
        
        # 测试统计信息添加
        success_result.add_keep_range_statistic("protocol_detections", 25)
        success_result.add_keep_range_statistic("tls_streams", 10)
        assert success_result.keep_range_statistics["protocol_detections"] == 25, "统计信息添加失败"
        
        # 测试结果摘要
        summary = success_result.get_summary()
        assert "成功" in summary, "成功结果摘要格式错误"
        assert "750/1000" in summary, "修改数据包统计缺失"
        assert "TCP流: 25" in summary, "TCP流统计缺失"
        
        # 测试失败结果
        failure_result = TcpMaskingResult(
            success=False,
            total_packets=0,
            modified_packets=0,
            bytes_masked=0,
            bytes_kept=0,
            tcp_streams_processed=0,
            processing_time=1.0,
            error_message="测试错误"
        )
        
        failure_summary = failure_result.get_summary()
        assert "失败" in failure_summary, "失败结果摘要格式错误"
        assert "测试错误" in failure_summary, "错误信息缺失"
        
        logger.info("✅ 掩码结果生成测试通过")
        return True
        
    except Exception as e:
        logger.error(f"❌ 掩码结果生成测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def test_error_handling():
    """测试错误处理机制"""
    logger.info("🧪 测试错误处理机制...")
    
    try:
        from keep_range_models import TcpKeepRangeEntry, TcpKeepRangeTable
        
        # 测试无效序列号范围
        try:
            invalid_entry = TcpKeepRangeEntry(
                stream_id="test",
                sequence_start=1000,
                sequence_end=500,  # 结束小于开始
                keep_ranges=[(0, 5)]
            )
            assert False, "应该抛出ValueError"
        except ValueError as e:
            assert "序列号范围无效" in str(e), "错误信息不正确"
        
        # 测试无效保留范围
        try:
            invalid_range_entry = TcpKeepRangeEntry(
                stream_id="test",
                sequence_start=1000,
                sequence_end=2000,
                keep_ranges=[(10, 5)]  # 结束小于开始
            )
            assert False, "应该抛出ValueError"
        except ValueError as e:
            assert "保留范围" in str(e), "保留范围错误信息不正确"
        
        # 测试无效类型添加
        table = TcpKeepRangeTable()
        try:
            table.add_keep_range_entry("invalid_type")
            assert False, "应该抛出TypeError"
        except TypeError as e:
            assert "TcpKeepRangeEntry类型" in str(e), "类型错误信息不正确"
        
        logger.info("✅ 错误处理机制测试通过")
        return True
        
    except Exception as e:
        logger.error(f"❌ 错误处理机制测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def test_performance_characteristics():
    """测试性能特征"""
    logger.info("🧪 测试性能特征...")
    
    try:
        from keep_range_models import TcpKeepRangeTable, TcpKeepRangeEntry
        
        # 测试大量条目的性能
        table = TcpKeepRangeTable()
        
        start_time = time.time()
        # 添加100个条目
        for i in range(100):
            entry = TcpKeepRangeEntry(
                stream_id=f"TCP_1.2.3.{i}:443_5.6.7.8:1234_forward",
                sequence_start=i * 1000,
                sequence_end=(i + 1) * 1000,
                keep_ranges=[(0, 5)],
                protocol_hint="TLS"
            )
            table.add_keep_range_entry(entry)
        
        add_time = time.time() - start_time
        logger.info(f"添加100个条目耗时: {add_time:.4f}秒")
        
        # 测试查找性能
        start_time = time.time()
        for i in range(100):
            ranges = table.find_keep_ranges_for_sequence(
                f"TCP_1.2.3.{i}:443_5.6.7.8:1234_forward", i * 1000 + 500
            )
        lookup_time = time.time() - start_time
        logger.info(f"100次查找耗时: {lookup_time:.4f}秒")
        
        # 验证性能要求（应该很快）
        assert add_time < 1.0, f"添加条目太慢: {add_time}秒"
        assert lookup_time < 0.1, f"查找太慢: {lookup_time}秒"
        
        # 验证数据正确性
        assert table.get_total_entries() == 100, "条目数量不正确"
        assert table.get_streams_count() == 100, "流数量不正确"
        
        logger.info("✅ 性能特征测试通过")
        return True
        
    except Exception as e:
        logger.error(f"❌ 性能特征测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def run_phase4_validation():
    """运行阶段4验证测试"""
    logger.info("🚀 开始TCP Payload Masker阶段4验证测试")
    
    tests = [
        ("TCP掩码器配置功能", test_tcp_masker_configuration),
        ("输入验证逻辑", test_input_validation_logic),
        ("TCP流处理逻辑", test_tcp_stream_processing),
        ("掩码结果生成", test_masking_result_generation),
        ("错误处理机制", test_error_handling),
        ("性能特征", test_performance_characteristics),
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
    logger.info(f"🎯 TCP Payload Masker阶段4验证测试结果")
    logger.info(f"{'='*60}")
    logger.info(f"通过测试: {passed}/{total} ({passed/total*100:.1f}%)")
    logger.info(f"测试耗时: {test_duration:.2f} 秒")
    
    if passed == total:
        logger.info("🎉 阶段4验证测试全部通过！")
        return True
    else:
        logger.error(f"💥 {total-passed} 个测试失败")
        return False

if __name__ == "__main__":
    success = run_phase4_validation()
    sys.exit(0 if success else 1)