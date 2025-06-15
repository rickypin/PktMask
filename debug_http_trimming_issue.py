#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
HTTP Trimming Issue 调试脚本

用于诊断HTTP协议在Trimming模块中未按预期处理的问题
"""

import sys
import logging
from pathlib import Path
from typing import Dict, Any
import tempfile
import os

# 添加源码路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from pktmask.core.trim.stages.tshark_preprocessor import TSharkPreprocessor
from pktmask.core.trim.stages.pyshark_analyzer import PySharkAnalyzer
from pktmask.core.trim.stages.base_stage import StageContext
from pktmask.core.trim.models.mask_table import StreamMaskTable


def setup_logging():
    """设置详细的日志输出"""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('http_trimming_debug.log', mode='w')
        ]
    )


def analyze_http_sample(sample_file: Path, config_overrides: Dict[str, Any] = None) -> Dict[str, Any]:
    """分析HTTP样本文件
    
    Args:
        sample_file: HTTP样本PCAP文件路径
        config_overrides: 配置覆盖项
        
    Returns:
        分析结果字典
    """
    print(f"\n🔍 分析HTTP样本: {sample_file.name}")
    print("=" * 60)
    
    results = {
        'file': str(sample_file),
        'file_size': 0,
        'tshark_success': False,
        'pyshark_success': False,
        'streams_found': 0,
        'http_streams': 0,
        'total_packets': 0,
        'http_packets': 0,
        'mask_entries': 0,
        'protocol_distribution': {},
        'stream_details': {},
        'config_used': {},
        'error': None
    }
    
    if not sample_file.exists():
        results['error'] = f"文件不存在: {sample_file}"
        return results
    
    results['file_size'] = sample_file.stat().st_size
    print(f"📁 文件大小: {results['file_size']:,} 字节")
    
    # 创建临时目录
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        try:
            # 阶段1: TShark预处理
            print("\n📡 阶段1: TShark预处理")
            print("-" * 30)
            
            tshark_config = {
                'tcp_stream_reassembly': True,
                'ip_defragmentation': True,
                'memory_limit_mb': 512,
                'timeout_seconds': 60
            }
            if config_overrides:
                tshark_config.update(config_overrides.get('tshark', {}))
            
            tshark_processor = TSharkPreprocessor(tshark_config)
            tshark_processor.initialize()
            
            context = StageContext(
                input_file=Path(sample_file),
                output_file=temp_path / "output.pcap",
                work_dir=temp_path
            )
            
            tshark_result = tshark_processor.execute(context)
            
            if tshark_result.success:
                results['tshark_success'] = True
                print("✅ TShark预处理成功")
                if tshark_result.stats:
                    duration = tshark_result.stats.get('execution_duration_seconds', 0)
                    print(f"   处理时间: {duration:.2f}秒")
                print(f"   输出文件: {context.tshark_output}")
            else:
                results['error'] = f"TShark预处理失败: {tshark_result.error}"
                print(f"❌ TShark预处理失败: {tshark_result.error}")
                return results
                
            # 阶段2: PyShark分析
            print("\n🔬 阶段2: PyShark协议分析")
            print("-" * 30)
            
            # 创建PyShark配置，特别注意HTTP相关配置
            pyshark_config = {
                'analyze_http': True,
                'analyze_tls': True,
                'analyze_tcp': True,
                'analyze_udp': True,
                'http_keep_headers': True,
                'http_mask_body': True,
                'http_full_mask': False,  # 重点：确保HTTP不被全部掩码
                'tls_keep_handshake': True,
                'tls_mask_application_data': True,
                'max_packets_per_batch': 1000,
                'memory_cleanup_interval': 5000,
                'analysis_timeout_seconds': 300
            }
            if config_overrides:
                pyshark_config.update(config_overrides.get('pyshark', {}))
            
            results['config_used'] = pyshark_config
            
            print("🔧 使用的配置:")
            for key, value in pyshark_config.items():
                if 'http' in key.lower():
                    print(f"   {key}: {value} {'⚠️' if key == 'http_full_mask' and value else ''}")
            
            pyshark_analyzer = PySharkAnalyzer(pyshark_config)
            pyshark_analyzer.initialize()
            
            pyshark_result = pyshark_analyzer.execute(context)
            
            if pyshark_result.success:
                results['pyshark_success'] = True
                print("✅ PyShark分析成功")
                if pyshark_result.stats:
                    duration = pyshark_result.stats.get('execution_duration_seconds', 0)
                    print(f"   处理时间: {duration:.2f}秒")
                
                # 提取详细统计信息
                stats = pyshark_result.stats
                results['total_packets'] = stats.get('packets_processed', 0)
                results['streams_found'] = stats.get('streams_identified', 0)
                results['http_packets'] = stats.get('http_packets', 0)
                results['mask_entries'] = stats.get('mask_entries_generated', 0)
                
                print(f"   处理数据包: {results['total_packets']}")
                print(f"   识别流数量: {results['streams_found']}")
                print(f"   HTTP数据包: {results['http_packets']}")
                print(f"   生成掩码条目: {results['mask_entries']}")
                
                # 分析协议分布
                if hasattr(pyshark_analyzer, '_streams'):
                    protocol_dist = {}
                    http_streams = 0
                    
                    for stream_id, stream_info in pyshark_analyzer._streams.items():
                        protocol = stream_info.application_protocol or 'Unknown'
                        protocol_dist[protocol] = protocol_dist.get(protocol, 0) + 1
                        
                        if protocol == 'HTTP':
                            http_streams += 1
                            
                        results['stream_details'][stream_id] = {
                            'protocol': protocol,
                            'packets': stream_info.packet_count,
                            'bytes': stream_info.total_bytes,
                            'src': f"{stream_info.src_ip}:{stream_info.src_port}",
                            'dst': f"{stream_info.dst_ip}:{stream_info.dst_port}"
                        }
                    
                    results['protocol_distribution'] = protocol_dist
                    results['http_streams'] = http_streams
                    
                    print(f"\n📊 协议分布:")
                    for protocol, count in protocol_dist.items():
                        indicator = "🌐" if protocol == "HTTP" else "🔒" if protocol == "TLS" else "❓"
                        print(f"   {indicator} {protocol}: {count} 个流")
                    
                    print(f"\n🌐 HTTP流详情:")
                    for stream_id, details in results['stream_details'].items():
                        if details['protocol'] == 'HTTP':
                            print(f"   流 {stream_id}:")
                            print(f"      {details['src']} → {details['dst']}")
                            print(f"      数据包: {details['packets']}, 字节: {details['bytes']}")
                
                # 分析掩码表
                if hasattr(pyshark_analyzer, '_mask_table') and pyshark_analyzer._mask_table:
                    mask_table = pyshark_analyzer._mask_table
                    print(f"\n🎭 掩码表分析:")
                    print(f"   总条目数: {mask_table.get_total_entry_count()}")
                    
                    # 分析每个流的掩码条目
                    for stream_id in mask_table.get_stream_ids():
                        entries = mask_table.get_entries_for_stream(stream_id)
                        print(f"   流 {stream_id}: {len(entries)} 个掩码条目")
                        
                        # 分析掩码类型分布
                        mask_types = {}
                        for entry in entries[:5]:  # 只显示前5个条目
                            mask_type = type(entry.mask_spec).__name__
                            mask_types[mask_type] = mask_types.get(mask_type, 0) + 1
                            print(f"      序列号 {entry.seq_start}-{entry.seq_end}: {mask_type}")
                            
                        if len(entries) > 5:
                            print(f"      ... 还有 {len(entries) - 5} 个条目")
                
            else:
                results['error'] = f"PyShark分析失败: {pyshark_result.error}"
                print(f"❌ PyShark分析失败: {pyshark_result.error}")
                return results
                
        except Exception as e:
            results['error'] = f"分析过程异常: {str(e)}"
            print(f"💥 分析过程发生异常: {str(e)}")
            logging.exception("分析过程异常")
            
    return results


def main():
    """主函数"""
    setup_logging()
    
    print("🔍 HTTP Trimming Issue 诊断工具")
    print("=" * 60)
    
    # HTTP样本文件目录
    samples_dir = Path("tests/samples/http")
    
    if not samples_dir.exists():
        print(f"❌ HTTP样本目录不存在: {samples_dir}")
        return 1
    
    # 获取所有PCAP文件
    pcap_files = list(samples_dir.glob("*.pcap*"))
    
    if not pcap_files:
        print(f"❌ 在 {samples_dir} 中未找到PCAP文件")
        return 1
    
    print(f"📁 找到 {len(pcap_files)} 个HTTP样本文件:")
    for f in pcap_files:
        size_mb = f.stat().st_size / (1024 * 1024)
        print(f"   📄 {f.name} ({size_mb:.1f} MB)")
    
    # 测试不同配置
    test_configs = [
        {
            'name': '默认配置 (保留HTTP头)',
            'config': {
                'pyshark': {
                    'http_full_mask': False,
                    'http_keep_headers': True,
                    'http_mask_body': True
                }
            }
        },
        {
            'name': '简化配置 (全部掩码)',
            'config': {
                'pyshark': {
                    'http_full_mask': True,
                    'http_keep_headers': False,
                    'http_mask_body': True
                }
            }
        },
        {
            'name': '保守配置 (完全保留)',
            'config': {
                'pyshark': {
                    'http_full_mask': False,
                    'http_keep_headers': True,
                    'http_mask_body': False
                }
            }
        }
    ]
    
    # 只分析第一个文件（通常是最小的）
    sample_file = min(pcap_files, key=lambda f: f.stat().st_size)
    
    print(f"\n🎯 重点分析: {sample_file.name}")
    
    all_results = []
    
    for test_config in test_configs:
        print(f"\n🧪 测试配置: {test_config['name']}")
        print("=" * 60)
        
        result = analyze_http_sample(sample_file, test_config['config'])
        result['config_name'] = test_config['name']
        all_results.append(result)
        
        if result['error']:
            print(f"❌ 配置测试失败: {result['error']}")
            continue
            
        # 总结本次测试结果
        print(f"\n📋 配置 '{test_config['name']}' 测试结果:")
        print(f"   ✅ 成功处理: {result['total_packets']} 个数据包")
        print(f"   🌐 HTTP数据包: {result['http_packets']} 个")
        print(f"   📊 HTTP流: {result['http_streams']} 个")
        print(f"   🎭 掩码条目: {result['mask_entries']} 个")
        
        if result['http_packets'] == 0:
            print("   ⚠️  警告: 未检测到HTTP数据包!")
        
    # 总结所有测试结果
    print(f"\n📊 所有配置测试总结")
    print("=" * 60)
    
    for result in all_results:
        if result['error']:
            print(f"❌ {result['config_name']}: 失败 - {result['error']}")
        else:
            print(f"✅ {result['config_name']}:")
            print(f"   HTTP包: {result['http_packets']}, HTTP流: {result['http_streams']}, 掩码: {result['mask_entries']}")
    
    # 问题诊断
    print(f"\n🔬 问题诊断")
    print("=" * 60)
    
    successful_results = [r for r in all_results if not r['error']]
    
    if not successful_results:
        print("❌ 所有配置测试都失败了!")
        return 1
    
    # 检查HTTP识别问题
    http_detected = any(r['http_packets'] > 0 for r in successful_results)
    
    if not http_detected:
        print("🚨 主要问题: HTTP协议识别失败!")
        print("   可能原因:")
        print("   1. PyShark无法识别HTTP数据包")
        print("   2. PCAP文件中实际不包含HTTP流量")
        print("   3. HTTP流量被其他协议(如TLS)覆盖")
        
        # 检查协议分布
        for result in successful_results:
            if result['protocol_distribution']:
                print(f"   实际检测到的协议: {list(result['protocol_distribution'].keys())}")
    else:
        print("✅ HTTP协议识别正常")
        
        # 检查掩码生成问题
        mask_issues = []
        
        for result in successful_results:
            if result['http_packets'] > 0 and result['mask_entries'] == 0:
                mask_issues.append(result['config_name'])
        
        if mask_issues:
            print(f"🚨 掩码生成问题: 以下配置检测到HTTP但未生成掩码条目:")
            for config_name in mask_issues:
                print(f"   - {config_name}")
        else:
            print("✅ 掩码生成正常")
    
    print(f"\n📝 详细日志已保存到: http_trimming_debug.log")
    return 0


if __name__ == "__main__":
    sys.exit(main()) 