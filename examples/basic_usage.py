#!/usr/bin/env python3
"""
独立PCAP掩码处理器 - 基础使用示例

本示例展示了如何使用IndependentPcapMasker进行基础的PCAP文件掩码处理。
包含TLS和HTTP流量的典型掩码场景。

作者: PktMask开发团队
版本: 1.0.0
日期: 2025-06-22
"""

import os
import sys
from pathlib import Path

# 添加项目路径到sys.path以便导入模块
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from pktmask.core.independent_pcap_masker import (
    IndependentPcapMasker,
    SequenceMaskTable, 
    MaskEntry, 
    MaskingResult
)


def example_1_basic_tls_masking():
    """
    示例1: 基础TLS流量掩码
    
    场景: 对TLS Application Data进行掩码处理，保留5字节TLS头部
    适用于: 隐藏TLS载荷内容但保留协议信息
    """
    print("=" * 60)
    print("示例1: 基础TLS流量掩码")
    print("=" * 60)
    
    # 创建掩码处理器
    masker = IndependentPcapMasker()
    
    # 创建掩码表
    mask_table = SequenceMaskTable()
    
    # 添加TLS Application Data掩码条目
    # 保留TLS记录头部的前5个字节 (Type(1) + Version(2) + Length(2))
    mask_table.add_entry(MaskEntry(
        stream_id="TCP_192.168.1.100:443_10.0.0.1:54321_forward",
        sequence_start=1000,
        sequence_end=5000,
        mask_type="mask_after",
        mask_params={"keep_bytes": 5}
    ))
    
    # 添加另一个TLS流的掩码条目（反向流）
    mask_table.add_entry(MaskEntry(
        stream_id="TCP_10.0.0.1:54321_192.168.1.100:443_reverse",
        sequence_start=2000,
        sequence_end=8000,
        mask_type="mask_after",
        mask_params={"keep_bytes": 5}
    ))
    
    print(f"创建掩码表，包含 {mask_table.get_total_entries()} 个条目")
    
    # 示例文件路径（请根据实际情况修改）
    base_dir = Path(__file__).parent.parent
    input_pcap = base_dir / "tests/samples/tls-single/tls_sample.pcap"
    output_pcap = Path(__file__).parent / "output/tls_masked_basic.pcap"
    
    # 确保输出目录存在
    output_pcap.parent.mkdir(parents=True, exist_ok=True)
    
    # 检查输入文件是否存在
    if not input_pcap.exists():
        print(f"⚠️  输入文件不存在: {input_pcap}")
        print("请使用实际的PCAP文件路径")
        # 使用相对路径重试
        alt_input = Path("tests/samples/tls-single/tls_sample.pcap")
        if alt_input.exists():
            input_pcap = alt_input
            print(f"🔄 使用替代路径: {input_pcap}")
        else:
            return None
    
    try:
        # 执行掩码处理
        print(f"正在处理文件: {input_pcap}")
        result = masker.mask_pcap_with_sequences(str(input_pcap), mask_table, str(output_pcap))
        
        # 显示结果
        if result.success:
            print("✅ 处理成功!")
            print(f"   总数据包数: {result.total_packets}")
            print(f"   修改数据包数: {result.modified_packets}")
            print(f"   掩码字节数: {result.bytes_masked}")
            print(f"   处理TCP流数: {result.streams_processed}")
            print(f"   处理时间: {result.processing_time:.3f} 秒")
            print(f"   输出文件: {output_pcap}")
            
            # 计算修改率
            modify_rate = (result.modified_packets / result.total_packets) * 100 if result.total_packets > 0 else 0
            print(f"   修改率: {modify_rate:.1f}%")
            
            return result
        else:
            print("❌ 处理失败!")
            print(f"   错误信息: {result.error_message}")
            return result
            
    except Exception as e:
        print(f"❌ 处理异常: {str(e)}")
        return None


def example_2_http_post_data_masking():
    """
    示例2: HTTP POST数据掩码
    
    场景: 掩码HTTP POST请求中的敏感数据字段
    适用于: 隐藏HTTP表单数据或API请求载荷
    """
    print("\n" + "=" * 60)
    print("示例2: HTTP POST数据掩码")
    print("=" * 60)
    
    # 使用调试配置获取详细日志
    config = {
        'log_level': 'INFO',
        'recalculate_checksums': True,
        'strict_consistency_mode': True
    }
    
    masker = IndependentPcapMasker(config)
    mask_table = SequenceMaskTable()
    
    # 添加HTTP POST数据掩码条目
    # 掩码载荷中的敏感数据范围，保留HTTP头部
    mask_table.add_entry(MaskEntry(
        stream_id="TCP_192.168.1.100:80_10.0.0.1:54321_forward",
        sequence_start=500,    # HTTP头部后的数据体起始位置
        sequence_end=2000,     # 数据体结束位置
        mask_type="mask_range",
        mask_params={
            "ranges": [
                (50, 150),    # 掩码用户名字段
                (200, 300),   # 掩码密码字段
                (400, 600)    # 掩码其他敏感字段
            ]
        }
    ))
    
    # 添加响应流的掩码（通常包含敏感的返回数据）
    mask_table.add_entry(MaskEntry(
        stream_id="TCP_10.0.0.1:54321_192.168.1.100:80_reverse",
        sequence_start=1000,
        sequence_end=3000,
        mask_type="mask_after",
        mask_params={"keep_bytes": 200}  # 保留HTTP响应头部
    ))
    
    print(f"创建掩码表，包含 {mask_table.get_total_entries()} 个条目")
    
    # 示例文件路径
    base_dir = Path(__file__).parent.parent
    input_pcap = base_dir / "tests/samples/http/http_sample.pcap"
    output_pcap = Path(__file__).parent / "output/http_masked_basic.pcap"
    
    # 确保输出目录存在
    output_pcap.parent.mkdir(parents=True, exist_ok=True)
    
    if not input_pcap.exists():
        print(f"⚠️  输入文件不存在: {input_pcap}")
        print("请使用实际的PCAP文件路径")
        return None
    
    try:
        print(f"正在处理文件: {input_pcap}")
        result = masker.mask_pcap_with_sequences(str(input_pcap), mask_table, str(output_pcap))
        
        if result.success:
            print("✅ 处理成功!")
            print(f"   总数据包数: {result.total_packets}")
            print(f"   修改数据包数: {result.modified_packets}")
            print(f"   掩码字节数: {result.bytes_masked}")
            print(f"   处理时间: {result.processing_time:.3f} 秒")
            print(f"   输出文件: {output_pcap}")
            
            # 显示详细统计信息（如果有）
            if result.statistics:
                print("   详细统计:")
                for key, value in result.statistics.items():
                    print(f"     {key}: {value}")
            
            return result
        else:
            print("❌ 处理失败!")
            print(f"   错误信息: {result.error_message}")
            return result
            
    except Exception as e:
        print(f"❌ 处理异常: {str(e)}")
        return None


def example_3_configuration_usage():
    """
    示例3: 配置使用演示
    
    展示如何使用不同的配置选项来优化性能或调整行为
    """
    print("\n" + "=" * 60)
    print("示例3: 配置使用演示")
    print("=" * 60)
    
    # 高性能配置
    performance_config = {
        'mask_byte_value': 0x00,              # 标准掩码值
        'preserve_timestamps': True,          # 保留时间戳
        'recalculate_checksums': False,       # 跳过校验和重算以提升性能
        'strict_consistency_mode': False,     # 放宽一致性检查以提升性能
        'log_level': 'WARNING',               # 减少日志输出
        'batch_size': 2000,                   # 增加批处理大小
        'memory_limit_mb': 1024,              # 增加内存限制
        'cleanup_temp_files': True,           # 确保清理临时文件
    }
    
    print("使用高性能配置:")
    for key, value in performance_config.items():
        print(f"  {key}: {value}")
    
    masker = IndependentPcapMasker(performance_config)
    
    # 创建简单的掩码表
    mask_table = SequenceMaskTable()
    mask_table.add_entry(MaskEntry(
        stream_id="TCP_192.168.1.100:443_10.0.0.1:54321_forward",
        sequence_start=1000,
        sequence_end=3000,
        mask_type="mask_after",
        mask_params={"keep_bytes": 10}
    ))
    
    print(f"创建掩码表，包含 {mask_table.get_total_entries()} 个条目")
    
    # 使用默认示例文件（如果存在）
    input_pcap = "tests/samples/tls-single/tls_sample.pcap"
    output_pcap = "examples/output/performance_test.pcap"
    
    os.makedirs(os.path.dirname(output_pcap), exist_ok=True)
    
    if os.path.exists(input_pcap):
        try:
            import time
            start_time = time.time()
            
            result = masker.mask_pcap_with_sequences(input_pcap, mask_table, output_pcap)
            
            end_time = time.time()
            
            if result.success:
                print("✅ 高性能处理完成!")
                print(f"   总处理时间: {end_time - start_time:.3f} 秒")
                print(f"   内部处理时间: {result.processing_time:.3f} 秒")
                print(f"   处理速度: {result.total_packets / result.processing_time:.1f} pps")
                
                return result
            else:
                print(f"❌ 处理失败: {result.error_message}")
                return result
                
        except Exception as e:
            print(f"❌ 处理异常: {str(e)}")
            return None
    else:
        print(f"⚠️  输入文件不存在: {input_pcap}")
        return None


def example_4_error_handling():
    """
    示例4: 错误处理演示
    
    展示如何正确处理各种错误情况
    """
    print("\n" + "=" * 60)
    print("示例4: 错误处理演示")
    print("=" * 60)
    
    masker = IndependentPcapMasker({
        'log_level': 'INFO'
    })
    
    # 测试空掩码表错误
    print("1. 测试空掩码表错误:")
    empty_table = SequenceMaskTable()
    
    try:
        result = masker.mask_pcap_with_sequences(
            "nonexistent.pcap", 
            empty_table, 
            "output.pcap"
        )
        print("   未检测到空掩码表错误（可能需要改进）")
    except ValueError as e:
        print(f"   ✅ 正确捕获ValueError: {e}")
    except Exception as e:
        print(f"   ❓ 捕获其他异常: {type(e).__name__}: {e}")
    
    # 测试文件不存在错误
    print("\n2. 测试文件不存在错误:")
    mask_table = SequenceMaskTable()
    mask_table.add_entry(MaskEntry(
        stream_id="TCP_1.2.3.4:80_5.6.7.8:1234_forward",
        sequence_start=100,
        sequence_end=200,
        mask_type="keep_all",
        mask_params={}
    ))
    
    try:
        result = masker.mask_pcap_with_sequences(
            "definitely_nonexistent_file.pcap",
            mask_table,
            "output.pcap"
        )
        print("   未检测到文件不存在错误")
    except FileNotFoundError as e:
        print(f"   ✅ 正确捕获FileNotFoundError: {e}")
    except Exception as e:
        print(f"   ❓ 捕获其他异常: {type(e).__name__}: {e}")
    
    # 测试无效参数错误
    print("\n3. 测试无效参数错误:")
    try:
        result = masker.mask_pcap_with_sequences(
            "",  # 空文件路径
            mask_table,
            ""   # 空输出路径
        )
        print("   未检测到无效参数错误")
    except ValueError as e:
        print(f"   ✅ 正确捕获ValueError: {e}")
    except Exception as e:
        print(f"   ❓ 捕获其他异常: {type(e).__name__}: {e}")
    
    print("\n错误处理演示完成")


def example_5_mask_table_operations():
    """
    示例5: 掩码表操作演示
    
    展示掩码表的各种操作和查询功能
    """
    print("\n" + "=" * 60)
    print("示例5: 掩码表操作演示")
    print("=" * 60)
    
    # 创建掩码表
    mask_table = SequenceMaskTable()
    
    print("1. 添加掩码条目:")
    entries = [
        MaskEntry(
            stream_id="TCP_192.168.1.100:443_10.0.0.1:54321_forward",
            sequence_start=1000,
            sequence_end=2000,
            mask_type="mask_after",
            mask_params={"keep_bytes": 5}
        ),
        MaskEntry(
            stream_id="TCP_192.168.1.100:443_10.0.0.1:54321_forward",
            sequence_start=3000,
            sequence_end=4000,
            mask_type="mask_range",
            mask_params={"ranges": [(0, 100), (200, 300)]}
        ),
        MaskEntry(
            stream_id="TCP_192.168.1.100:80_10.0.0.1:54322_forward",
            sequence_start=500,
            sequence_end=1500,
            mask_type="keep_all",
            mask_params={}
        )
    ]
    
    for i, entry in enumerate(entries, 1):
        mask_table.add_entry(entry)
        print(f"   条目 {i}: {entry.stream_id}, 序列号 {entry.sequence_start}-{entry.sequence_end}, 类型 {entry.mask_type}")
    
    print(f"\n掩码表统计:")
    print(f"   总条目数: {mask_table.get_total_entries()}")
    
    print("\n2. 掩码条目查找演示:")
    # 查找匹配的条目
    test_cases = [
        ("TCP_192.168.1.100:443_10.0.0.1:54321_forward", 1500),
        ("TCP_192.168.1.100:443_10.0.0.1:54321_forward", 3500),
        ("TCP_192.168.1.100:80_10.0.0.1:54322_forward", 1000),
        ("TCP_192.168.1.100:22_10.0.0.1:54323_forward", 2000),  # 应该找不到
    ]
    
    for stream_id, sequence in test_cases:
        matches = mask_table.find_matches(stream_id, sequence)
        print(f"   查找 {stream_id}:{sequence}")
        if matches:
            for match in matches:
                print(f"     ✅ 匹配: {match.mask_type} ({match.sequence_start}-{match.sequence_end})")
        else:
            print(f"     ❌ 无匹配")
    
    print("\n3. 掩码表统计信息:")
    try:
        stats = mask_table.get_statistics()
        print(f"   掩码表统计: {stats}")
    except AttributeError:
        print(f"   总条目数: {mask_table.get_total_entries()}")
        print("   (详细统计功能不可用)")
    
    print("\n掩码表操作演示完成")


def example_6_statistics_monitoring():
    """
    示例6: 统计信息监控
    
    展示如何监控和分析处理统计信息
    """
    print("\n" + "=" * 60)
    print("示例6: 统计信息监控")
    print("=" * 60)
    
    # 创建配置，启用详细统计
    config = {
        'log_level': 'INFO',
        'strict_consistency_mode': True
    }
    
    masker = IndependentPcapMasker(config)
    
    # 创建测试掩码表
    mask_table = SequenceMaskTable()
    mask_table.add_entry(MaskEntry(
        stream_id="TCP_192.168.1.100:443_10.0.0.1:54321_forward",
        sequence_start=1000,
        sequence_end=3000,
        mask_type="mask_after",
        mask_params={"keep_bytes": 8}
    ))
    
    print("处理文件并收集统计信息...")
    
    # 使用示例文件（如果存在）
    input_pcap = "tests/samples/tls-single/tls_sample.pcap"
    output_pcap = "examples/output/statistics_test.pcap"
    
    os.makedirs(os.path.dirname(output_pcap), exist_ok=True)
    
    if os.path.exists(input_pcap):
        try:
            result = masker.mask_pcap_with_sequences(input_pcap, mask_table, output_pcap)
            
            if result.success:
                print("✅ 处理完成，统计信息:")
                
                # 基础统计
                print(f"   总数据包数: {result.total_packets}")
                print(f"   修改数据包数: {result.modified_packets}")
                print(f"   掩码字节数: {result.bytes_masked}")
                print(f"   处理TCP流数: {result.streams_processed}")
                print(f"   处理时间: {result.processing_time:.3f} 秒")
                
                # 计算衍生统计
                if result.total_packets > 0:
                    modify_rate = (result.modified_packets / result.total_packets) * 100
                    print(f"   数据包修改率: {modify_rate:.1f}%")
                
                if result.processing_time > 0:
                    pps = result.total_packets / result.processing_time
                    print(f"   处理速度: {pps:.1f} pps")
                
                if result.modified_packets > 0:
                    avg_bytes_per_packet = result.bytes_masked / result.modified_packets
                    print(f"   平均每包掩码字节数: {avg_bytes_per_packet:.1f}")
                
                # 详细统计信息（如果有）
                if result.statistics:
                    print("   详细统计信息:")
                    for key, value in result.statistics.items():
                        print(f"     {key}: {value}")
                
                return result
            else:
                print(f"❌ 处理失败: {result.error_message}")
                return result
        except Exception as e:
            print(f"❌ 处理异常: {str(e)}")
            return None
    else:
        print(f"⚠️  输入文件不存在: {input_pcap}")
        print("跳过统计信息演示")
        return None


def main():
    """主函数，运行所有示例"""
    print("独立PCAP掩码处理器 - 基础使用示例")
    print("=" * 60)
    print("本示例将演示各种基础使用场景")
    print("注意: 部分示例需要实际的PCAP文件才能完整运行")
    print()
    
    # 创建输出目录
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 运行所有示例
    examples = [
        example_1_basic_tls_masking,
        example_2_http_post_data_masking,
        example_3_configuration_usage,
        example_4_error_handling,
        example_5_mask_table_operations,
        example_6_statistics_monitoring
    ]
    
    results = []
    
    for example_func in examples:
        try:
            result = example_func()
            results.append((example_func.__name__, result))
        except Exception as e:
            print(f"❌ 示例 {example_func.__name__} 执行失败: {str(e)}")
            results.append((example_func.__name__, None))
    
    # 显示总结
    print("\n" + "=" * 60)
    print("示例执行总结")
    print("=" * 60)
    
    successful_count = 0
    
    for example_name, result in results:
        if result is None:
            status = "⚠️  跳过/异常"
        elif isinstance(result, MaskingResult):
            if result.success:
                status = "✅ 成功"
                successful_count += 1
            else:
                status = "❌ 失败"
        else:
            status = "✅ 完成"
            successful_count += 1
        
        print(f"   {example_name}: {status}")
    
    print(f"\n成功运行 {successful_count}/{len(examples)} 个示例")
    
    print("\n输出文件位置:")
    if output_dir.exists():
        for output_file in output_dir.glob("*.pcap"):
            size = output_file.stat().st_size
            print(f"   {output_file.name}: {size:,} bytes")
    
    print("\n基础使用示例演示完成！")
    print("更多高级用法请参见 advanced_usage.py")


if __name__ == "__main__":
    main() 