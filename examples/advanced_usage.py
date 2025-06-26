#!/usr/bin/env python3
"""
独立PCAP掩码处理器 - 高级使用示例

本示例展示了IndependentPcapMasker的高级功能，包括：
- 复杂掩码表创建和管理
- 批量文件处理
- 性能优化配置
- 并行处理
- 协议解析控制
- 上下文管理器使用

作者: PktMask开发团队
版本: 1.0.0
日期: 2025-06-22
"""

import os
import sys
import time
import json
import logging
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from typing import List, Dict, Tuple, Optional

# 添加项目路径到sys.path以便导入模块
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from pktmask.core.independent_pcap_masker import (
    IndependentPcapMasker,
    SequenceMaskTable, 
    MaskEntry, 
    MaskingResult
)


class AdvancedMaskTableBuilder:
    """高级掩码表构建器"""
    
    def __init__(self):
        self.mask_table = SequenceMaskTable()
        self._stream_counter = {}
    
    def add_tls_stream_masks(self, src_ip: str, src_port: int, dst_ip: str, dst_port: int, 
                           app_data_ranges: List[Tuple[int, int]]) -> 'AdvancedMaskTableBuilder':
        """添加TLS流的完整掩码规则"""
        
        # 正向流（客户端到服务器）
        forward_stream_id = f"TCP_{src_ip}:{src_port}_{dst_ip}:{dst_port}_forward"
        
        for start_seq, end_seq in app_data_ranges:
            self.mask_table.add_entry(MaskEntry(
                stream_id=forward_stream_id,
                sequence_start=start_seq,
                sequence_end=end_seq,
                mask_type="mask_after",
                mask_params={"keep_bytes": 5}  # TLS头部
            ))
        
        # 反向流（服务器到客户端）
        reverse_stream_id = f"TCP_{dst_ip}:{dst_port}_{src_ip}:{src_port}_reverse"
        
        for start_seq, end_seq in app_data_ranges:
            # 服务器响应通常序列号不同，这里使用偏移
            self.mask_table.add_entry(MaskEntry(
                stream_id=reverse_stream_id,
                sequence_start=start_seq + 1000,  # 假设的偏移
                sequence_end=end_seq + 1000,
                mask_type="mask_after",
                mask_params={"keep_bytes": 5}
            ))
        
        return self
    
    def add_http_api_masks(self, src_ip: str, src_port: int, dst_ip: str, dst_port: int,
                          request_body_ranges: List[Tuple[int, int]],
                          response_body_ranges: List[Tuple[int, int]]) -> 'AdvancedMaskTableBuilder':
        """添加HTTP API的敏感数据掩码规则"""
        
        forward_stream_id = f"TCP_{src_ip}:{src_port}_{dst_ip}:{dst_port}_forward"
        reverse_stream_id = f"TCP_{dst_ip}:{dst_port}_{src_ip}:{src_port}_reverse"
        
        # 掩码请求体中的敏感数据
        for start_seq, end_seq in request_body_ranges:
            self.mask_table.add_entry(MaskEntry(
                stream_id=forward_stream_id,
                sequence_start=start_seq,
                sequence_end=end_seq,
                mask_type="mask_range",
                mask_params={
                    "ranges": [
                        (50, 150),   # 用户名/密码字段
                        (200, 300),  # API密钥
                        (400, 600)   # 其他敏感数据
                    ]
                }
            ))
        
        # 掩码响应体中的敏感数据
        for start_seq, end_seq in response_body_ranges:
            self.mask_table.add_entry(MaskEntry(
                stream_id=reverse_stream_id,
                sequence_start=start_seq,
                sequence_end=end_seq,
                mask_type="mask_after",
                mask_params={"keep_bytes": 100}  # 保留响应头部
            ))
        
        return self
    
    def add_debug_stream(self, stream_id: str, seq_ranges: List[Tuple[int, int]]) -> 'AdvancedMaskTableBuilder':
        """添加调试流（保留所有数据）"""
        
        for start_seq, end_seq in seq_ranges:
            self.mask_table.add_entry(MaskEntry(
                stream_id=stream_id,
                sequence_start=start_seq,
                sequence_end=end_seq,
                mask_type="keep_all",
                mask_params={}
            ))
        
        return self
    
    def build(self) -> SequenceMaskTable:
        """构建最终的掩码表"""
        return self.mask_table
    
    def get_statistics(self) -> Dict[str, int]:
        """获取构建统计信息"""
        try:
            # 尝试使用内置统计方法
            stats = self.mask_table.get_statistics()
            return {
                "total_entries": stats.get("total_entries", 0),
                "unique_streams": stats.get("streams_count", 0),
                "mask_after_count": 0,  # 暂时不可用
                "mask_range_count": 0,  # 暂时不可用
                "keep_all_count": 0     # 暂时不可用
            }
        except AttributeError:
            # 降级到基本统计
            return {
                "total_entries": self.mask_table.get_total_entries(),
                "unique_streams": 0,  # 不可用
                "mask_after_count": 0,  # 不可用
                "mask_range_count": 0,  # 不可用
                "keep_all_count": 0     # 不可用
            }


class BatchProcessor:
    """批量文件处理器"""
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.results = []
        self.lock = threading.Lock()
    
    def process_file(self, input_file: Path, output_file: Path, mask_table: SequenceMaskTable) -> Tuple[str, MaskingResult]:
        """处理单个文件"""
        masker = IndependentPcapMasker(self.config)
        
        try:
            start_time = time.time()
            result = masker.mask_pcap_with_sequences(
                str(input_file),
                mask_table,
                str(output_file)
            )
            end_time = time.time()
            
            # 添加额外的统计信息
            if result.statistics is None:
                result.statistics = {}
            
            result.statistics.update({
                "file_name": input_file.name,
                "file_size": input_file.stat().st_size,
                "total_time": end_time - start_time,
                "processing_speed_pps": result.total_packets / result.processing_time if result.processing_time > 0 else 0
            })
            
            return input_file.name, result
            
        except Exception as e:
            # 创建失败结果
            error_result = MaskingResult(
                success=False,
                total_packets=0,
                modified_packets=0,
                bytes_masked=0,
                processing_time=0.0,
                streams_processed=0,
                error_message=str(e)
            )
            return input_file.name, error_result
    
    def process_directory(self, input_dir: Path, output_dir: Path, mask_table: SequenceMaskTable, 
                         max_workers: int = 4) -> List[Tuple[str, MaskingResult]]:
        """批量处理目录中的所有PCAP文件"""
        
        # 确保输出目录存在
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 查找所有PCAP文件
        pcap_files = list(input_dir.glob("*.pcap")) + list(input_dir.glob("*.pcapng"))
        
        if not pcap_files:
            print(f"⚠️  在目录 {input_dir} 中未找到PCAP文件")
            return []
        
        print(f"🚀 开始批量处理 {len(pcap_files)} 个文件，使用 {max_workers} 个线程")
        
        # 并行处理文件
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_file = {}
            for pcap_file in pcap_files:
                output_file = output_dir / f"masked_{pcap_file.name}"
                future = executor.submit(self.process_file, pcap_file, output_file, mask_table)
                future_to_file[future] = pcap_file
            
            # 收集结果
            results = []
            completed = 0
            
            for future in as_completed(future_to_file):
                completed += 1
                try:
                    file_name, result = future.result()
                    results.append((file_name, result))
                    
                    status = "✅" if result.success else "❌"
                    print(f"   [{completed}/{len(pcap_files)}] {status} {file_name}")
                    
                except Exception as e:
                    file_name = future_to_file[future].name
                    print(f"   [{completed}/{len(pcap_files)}] ❌ {file_name}: {str(e)}")
                    
                    error_result = MaskingResult(
                        success=False,
                        total_packets=0,
                        modified_packets=0,
                        bytes_masked=0,
                        processing_time=0.0,
                        streams_processed=0,
                        error_message=str(e)
                    )
                    results.append((file_name, error_result))
        
        return results
    
    def generate_batch_report(self, results: List[Tuple[str, MaskingResult]], output_file: Path):
        """生成批量处理报告"""
        
        report = {
            "summary": {
                "total_files": len(results),
                "successful_files": len([r for _, r in results if r.success]),
                "failed_files": len([r for _, r in results if not r.success]),
                "total_packets": sum(r.total_packets for _, r in results),
                "total_modified_packets": sum(r.modified_packets for _, r in results),
                "total_bytes_masked": sum(r.bytes_masked for _, r in results),
                "total_processing_time": sum(r.processing_time for _, r in results)
            },
            "file_details": []
        }
        
        for file_name, result in results:
            detail = {
                "file_name": file_name,
                "success": result.success,
                "total_packets": result.total_packets,
                "modified_packets": result.modified_packets,
                "bytes_masked": result.bytes_masked,
                "processing_time": result.processing_time,
                "streams_processed": result.streams_processed
            }
            
            if result.error_message:
                detail["error_message"] = result.error_message
            
            if result.statistics:
                detail["statistics"] = result.statistics
            
            report["file_details"].append(detail)
        
        # 写入报告文件
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"📊 批量处理报告已保存: {output_file}")
        
        # 显示摘要
        summary = report["summary"]
        print(f"\n批量处理摘要:")
        print(f"   总文件数: {summary['total_files']}")
        print(f"   成功文件: {summary['successful_files']}")
        print(f"   失败文件: {summary['failed_files']}")
        print(f"   总数据包: {summary['total_packets']:,}")
        print(f"   修改数据包: {summary['total_modified_packets']:,}")
        print(f"   掩码字节数: {summary['total_bytes_masked']:,}")
        print(f"   总处理时间: {summary['total_processing_time']:.2f} 秒")
        
        if summary['total_processing_time'] > 0:
            avg_pps = summary['total_packets'] / summary['total_processing_time']
            print(f"   平均处理速度: {avg_pps:.1f} pps")


@contextmanager
def performance_monitor(operation_name: str):
    """性能监控上下文管理器"""
    start_time = time.time()
    start_memory = get_memory_usage()
    
    print(f"🏁 开始操作: {operation_name}")
    
    try:
        yield
    finally:
        end_time = time.time()
        end_memory = get_memory_usage()
        
        elapsed_time = end_time - start_time
        memory_delta = end_memory - start_memory
        
        print(f"⏱️  操作完成: {operation_name}")
        print(f"   耗时: {elapsed_time:.3f} 秒")
        print(f"   内存变化: {memory_delta:+.2f} MB")


def get_memory_usage() -> float:
    """获取当前内存使用量（MB）"""
    try:
        import psutil
        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024
    except ImportError:
        return 0.0


def example_1_complex_mask_table_creation():
    """
    示例1: 复杂掩码表创建
    
    演示如何使用AdvancedMaskTableBuilder创建复杂的多协议掩码表
    """
    print("=" * 60)
    print("示例1: 复杂掩码表创建")
    print("=" * 60)
    
    with performance_monitor("复杂掩码表创建"):
        builder = AdvancedMaskTableBuilder()
        
        # 添加多个TLS流的掩码规则
        print("添加TLS流掩码规则...")
        builder.add_tls_stream_masks(
            src_ip="192.168.1.100", src_port=54321,
            dst_ip="10.0.0.1", dst_port=443,
            app_data_ranges=[(1000, 5000), (10000, 15000), (20000, 25000)]
        )
        
        builder.add_tls_stream_masks(
            src_ip="192.168.1.101", src_port=54322,
            dst_ip="10.0.0.2", dst_port=443,
            app_data_ranges=[(2000, 8000), (12000, 18000)]
        )
        
        # 添加HTTP API流的掩码规则
        print("添加HTTP API流掩码规则...")
        builder.add_http_api_masks(
            src_ip="192.168.1.100", src_port=54323,
            dst_ip="10.0.0.3", dst_port=80,
            request_body_ranges=[(500, 2000), (3000, 4000)],
            response_body_ranges=[(1000, 3000), (5000, 7000)]
        )
        
        # 添加调试流
        print("添加调试流...")
        builder.add_debug_stream(
            stream_id="TCP_192.168.1.100:22_10.0.0.4:54324_forward",
            seq_ranges=[(0, 10000)]
        )
        
        # 构建掩码表
        mask_table = builder.build()
        stats = builder.get_statistics()
        
        print("✅ 复杂掩码表创建完成")
        print(f"   总条目数: {stats['total_entries']}")
        print(f"   唯一流数: {stats['unique_streams']}")
        print(f"   MaskAfter条目: {stats['mask_after_count']}")
        print(f"   MaskRange条目: {stats['mask_range_count']}")
        print(f"   KeepAll条目: {stats['keep_all_count']}")
        
        return mask_table


def example_2_performance_optimization():
    """
    示例2: 性能优化配置
    
    演示不同配置对性能的影响
    """
    print("\n" + "=" * 60)
    print("示例2: 性能优化配置")
    print("=" * 60)
    
    # 测试不同的配置
    configs = {
        "默认配置": {},
        "高性能配置": {
            'recalculate_checksums': False,
            'strict_consistency_mode': False,
            'log_level': 'ERROR',
            'processing_batch_size': 3000,
            'memory_limit_mb': 2048
        },
        "高质量配置": {
            'recalculate_checksums': True,
            'strict_consistency_mode': True,
            'log_level': 'DEBUG',
            'processing_batch_size': 500,
            'memory_limit_mb': 512
        }
    }
    
    # 创建测试掩码表
    mask_table = SequenceMaskTable()
    mask_table.add_entry(MaskEntry(
        stream_id="TCP_192.168.1.100:443_10.0.0.1:54321_forward",
        sequence_start=1000,
        sequence_end=3000,
        mask_type="mask_after",
        mask_params={"keep_bytes": 8}
    ))
    
    # 测试文件
    test_file = "tests/samples/tls-single/tls_sample.pcap"
    
    if not os.path.exists(test_file):
        print(f"⚠️  测试文件不存在: {test_file}")
        print("跳过性能测试")
        return None
    
    results = {}
    
    for config_name, config in configs.items():
        print(f"\n测试配置: {config_name}")
        
        # 确保输出目录存在
        output_file = f"examples/output/processed/perf_test_{config_name.replace(' ', '_').lower()}.pcap"
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        try:
            with performance_monitor(f"配置测试: {config_name}"):
                masker = IndependentPcapMasker(config)
                
                # 运行多次取平均值
                times = []
                for i in range(3):
                    start_time = time.time()
                    result = masker.mask_pcap_with_sequences(test_file, mask_table, output_file)
                    end_time = time.time()
                    
                    if result.success:
                        times.append(end_time - start_time)
                    else:
                        print(f"   ❌ 第{i+1}次运行失败: {result.error_message}")
                        break
                
                if times:
                    avg_time = sum(times) / len(times)
                    min_time = min(times)
                    max_time = max(times)
                    
                    results[config_name] = {
                        "avg_time": avg_time,
                        "min_time": min_time,
                        "max_time": max_time,
                        "total_packets": result.total_packets,
                        "modified_packets": result.modified_packets,
                        "processing_speed": result.total_packets / avg_time if avg_time > 0 else 0
                    }
                    
                    print(f"   平均处理时间: {avg_time:.3f} 秒")
                    print(f"   处理速度: {results[config_name]['processing_speed']:.1f} pps")
                
        except Exception as e:
            print(f"   ❌ 配置测试失败: {str(e)}")
    
    # 显示性能对比
    if results:
        print("\n性能对比摘要:")
        print("-" * 60)
        
        baseline = None
        for config_name, data in results.items():
            speed = data['processing_speed']
            
            if baseline is None:
                baseline = speed
                improvement = "基准"
            else:
                improvement = f"{speed/baseline:.1f}x"
            
            print(f"{config_name:12s}: {speed:7.1f} pps ({improvement})")
    
    return results


def example_3_batch_processing():
    """
    示例3: 批量文件处理
    
    演示如何批量处理多个PCAP文件
    """
    print("\n" + "=" * 60)
    print("示例3: 批量文件处理")
    print("=" * 60)
    
    # 创建批量处理器
    batch_config = {
        'log_level': 'WARNING',  # 减少日志输出
        'processing_batch_size': 2000,
        'memory_limit_mb': 1024
    }
    
    processor = BatchProcessor(batch_config)
    
    # 创建掩码表
    mask_table = SequenceMaskTable()
    
    # 添加通用的掩码规则
    common_streams = [
        ("TCP_192.168.1.100:443_10.0.0.1:54321_forward", [(1000, 5000)]),
        ("TCP_192.168.1.100:80_10.0.0.1:54322_forward", [(500, 2000)]),
        ("TCP_192.168.1.101:443_10.0.0.2:54323_forward", [(2000, 8000)])
    ]
    
    for stream_id, ranges in common_streams:
        for start_seq, end_seq in ranges:
            mask_table.add_entry(MaskEntry(
                stream_id=stream_id,
                sequence_start=start_seq,
                sequence_end=end_seq,
                mask_type="mask_after",
                mask_params={"keep_bytes": 5}
            ))
    
    print(f"创建掩码表，包含 {mask_table.get_total_entries()} 个条目")
    
    # 设置输入输出目录
    input_dir = Path("tests/samples")
    output_dir = Path("examples/output/processed/batch_results")
    
    if not input_dir.exists():
        print(f"⚠️  输入目录不存在: {input_dir}")
        print("跳过批量处理演示")
        return None
    
    with performance_monitor("批量文件处理"):
        # 执行批量处理
        results = processor.process_directory(input_dir, output_dir, mask_table, max_workers=4)
        
        # 生成报告
        report_file = output_dir / "batch_processing_report.json"
        processor.generate_batch_report(results, report_file)
        
        return results


def example_4_parallel_batch_processing():
    """
    示例4: 并行批量处理
    
    演示高级并行处理模式
    """
    print("\n" + "=" * 60)
    print("示例4: 并行批量处理")
    print("=" * 60)
    
    def process_file_group(group_name: str, file_list: List[Path], mask_table: SequenceMaskTable) -> Dict:
        """处理一组文件"""
        print(f"   开始处理组: {group_name} ({len(file_list)} 个文件)")
        
        group_config = {
            'log_level': 'ERROR',
            'processing_batch_size': 1500,
            'memory_limit_mb': 512
        }
        
        masker = IndependentPcapMasker(group_config)
        group_results = []
        
        for file_path in file_list:
            output_file = Path(f"examples/output/processed/parallel/{group_name}_{file_path.name}")
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            try:
                result = masker.mask_pcap_with_sequences(
                    str(file_path), mask_table, str(output_file)
                )
                group_results.append((file_path.name, result))
            except Exception as e:
                error_result = MaskingResult(
                    success=False, total_packets=0, modified_packets=0,
                    bytes_masked=0, processing_time=0.0, streams_processed=0,
                    error_message=str(e)
                )
                group_results.append((file_path.name, error_result))
        
        successful = len([r for _, r in group_results if r.success])
        print(f"   完成处理组: {group_name} ({successful}/{len(group_results)} 成功)")
        
        return {
            "group_name": group_name,
            "total_files": len(group_results),
            "successful_files": successful,
            "results": group_results
        }
    
    # 查找所有PCAP文件并分组
    input_dir = Path("tests/samples")
    
    if not input_dir.exists():
        print(f"⚠️  输入目录不存在: {input_dir}")
        print("跳过并行批量处理演示")
        return None
    
    pcap_files = list(input_dir.rglob("*.pcap")) + list(input_dir.rglob("*.pcapng"))
    
    if not pcap_files:
        print("⚠️  未找到PCAP文件")
        return None
    
    # 按目录分组
    file_groups = {}
    for file_path in pcap_files:
        group_name = file_path.parent.name
        if group_name not in file_groups:
            file_groups[group_name] = []
        file_groups[group_name].append(file_path)
    
    print(f"发现 {len(file_groups)} 个文件组，总共 {len(pcap_files)} 个文件")
    
    # 创建掩码表
    mask_table = SequenceMaskTable()
    mask_table.add_entry(MaskEntry(
        stream_id="TCP_192.168.1.100:443_10.0.0.1:54321_forward",
        sequence_start=1000,
        sequence_end=5000,
        mask_type="mask_after",
        mask_params={"keep_bytes": 8}
    ))
    
    with performance_monitor("并行批量处理"):
        # 并行处理各组
        with ThreadPoolExecutor(max_workers=min(4, len(file_groups))) as executor:
            futures = []
            
            for group_name, files in file_groups.items():
                future = executor.submit(process_file_group, group_name, files, mask_table)
                futures.append(future)
            
            # 收集结果
            all_results = []
            for future in as_completed(futures):
                try:
                    group_result = future.result()
                    all_results.append(group_result)
                except Exception as e:
                    print(f"❌ 组处理失败: {str(e)}")
        
        # 汇总结果
        total_files = sum(r["total_files"] for r in all_results)
        total_successful = sum(r["successful_files"] for r in all_results)
        
        print(f"\n并行处理完成:")
        print(f"   总文件数: {total_files}")
        print(f"   成功处理: {total_successful}")
        print(f"   成功率: {total_successful/total_files*100:.1f}%" if total_files > 0 else "   成功率: 0%")
        
        for group_result in all_results:
            group_name = group_result["group_name"]
            success_rate = group_result["successful_files"] / group_result["total_files"] * 100
            print(f"   组 {group_name}: {group_result['successful_files']}/{group_result['total_files']} ({success_rate:.1f}%)")
        
        return all_results


def example_5_protocol_parsing_control():
    """
    示例5: 协议解析控制演示
    
    演示协议解析禁用机制的效果
    """
    print("\n" + "=" * 60)
    print("示例5: 协议解析控制演示")
    print("=" * 60)
    
    # 测试不同的协议解析设置
    test_configs = [
        ("协议解析启用", {'disable_protocol_parsing': False}),
        ("协议解析禁用", {'disable_protocol_parsing': True})
    ]
    
    mask_table = SequenceMaskTable()
    mask_table.add_entry(MaskEntry(
        stream_id="TCP_192.168.1.100:443_10.0.0.1:54321_forward",
        sequence_start=1000,
        sequence_end=3000,
        mask_type="mask_after",
        mask_params={"keep_bytes": 5}
    ))
    
    test_file = "tests/samples/tls-single/tls_sample.pcap"
    
    if not os.path.exists(test_file):
        print(f"⚠️  测试文件不存在: {test_file}")
        print("跳过协议解析控制演示")
        return None
    
    results = {}
    
    for config_name, config in test_configs:
        print(f"\n测试: {config_name}")
        
        try:
            masker = IndependentPcapMasker(config)
            
            output_file = f"examples/output/processed/protocol_test_{config_name.replace(' ', '_')}.pcap"
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            
            start_time = time.time()
            result = masker.mask_pcap_with_sequences(test_file, mask_table, output_file)
            end_time = time.time()
            
            if result.success:
                results[config_name] = {
                    "total_packets": result.total_packets,
                    "modified_packets": result.modified_packets,
                    "bytes_masked": result.bytes_masked,
                    "processing_time": end_time - start_time,
                    "success": True
                }
                
                print(f"   ✅ 处理成功")
                print(f"   修改数据包: {result.modified_packets}/{result.total_packets}")
                print(f"   掩码字节数: {result.bytes_masked}")
                print(f"   处理时间: {end_time - start_time:.3f} 秒")
            else:
                print(f"   ❌ 处理失败: {result.error_message}")
                results[config_name] = {"success": False, "error": result.error_message}
        
        except Exception as e:
            print(f"   ❌ 配置测试异常: {str(e)}")
            results[config_name] = {"success": False, "error": str(e)}
    
    # 比较结果
    if len([r for r in results.values() if r.get("success")]) >= 2:
        print("\n协议解析控制效果对比:")
        print("-" * 40)
        
        for config_name, data in results.items():
            if data.get("success"):
                modified_rate = data["modified_packets"] / data["total_packets"] * 100 if data["total_packets"] > 0 else 0
                print(f"{config_name}:")
                print(f"   修改率: {modified_rate:.1f}%")
                print(f"   掩码字节: {data['bytes_masked']}")
                print(f"   处理时间: {data['processing_time']:.3f}s")
    
    return results


def example_6_context_manager_usage():
    """
    示例6: 上下文管理器使用
    
    演示资源管理和自动清理
    """
    print("\n" + "=" * 60)
    print("示例6: 上下文管理器使用")
    print("=" * 60)
    
    class MaskingSession:
        """掩码处理会话上下文管理器"""
        
        def __init__(self, config: Optional[Dict] = None):
            self.config = config or {}
            self.masker = None
            self.temp_files = []
            self.start_time = None
        
        def __enter__(self):
            self.start_time = time.time()
            self.masker = IndependentPcapMasker(self.config)
            print("🚀 开始掩码处理会话")
            return self
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            end_time = time.time()
            session_time = end_time - self.start_time
            
            # 清理临时文件
            for temp_file in self.temp_files:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                        print(f"   🗑️  清理临时文件: {temp_file}")
                except Exception as e:
                    print(f"   ⚠️  清理文件失败: {temp_file} - {e}")
            
            if exc_type is None:
                print(f"✅ 掩码处理会话完成，耗时 {session_time:.3f} 秒")
            else:
                print(f"❌ 掩码处理会话异常结束: {exc_val}")
                print(f"   会话耗时: {session_time:.3f} 秒")
            
            return False  # 不抑制异常
        
        def process_with_backup(self, input_file: str, mask_table: SequenceMaskTable, output_file: str) -> MaskingResult:
            """带备份的处理方法"""
            # 创建备份文件
            backup_file = f"{input_file}.backup"
            if not os.path.exists(backup_file):
                import shutil
                shutil.copy2(input_file, backup_file)
                self.temp_files.append(backup_file)
                print(f"   📋 创建备份文件: {backup_file}")
            
            # 执行处理
            result = self.masker.mask_pcap_with_sequences(input_file, mask_table, output_file)
            
            if result.success:
                print(f"   ✅ 处理成功，备份已保留")
            else:
                print(f"   ❌ 处理失败，可从备份恢复")
            
            return result
    
    # 使用上下文管理器
    session_config = {
        'log_level': 'INFO',
        'cleanup_temp_files': True
    }
    
    mask_table = SequenceMaskTable()
    mask_table.add_entry(MaskEntry(
        stream_id="TCP_192.168.1.100:443_10.0.0.1:54321_forward",
        sequence_start=1000,
        sequence_end=3000,
        mask_type="mask_after",
        mask_params={"keep_bytes": 8}
    ))
    
    test_file = "tests/samples/tls-single/tls_sample.pcap"
    output_file = "examples/output/processed/context_manager_test.pcap"
    
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    if os.path.exists(test_file):
        try:
            with MaskingSession(session_config) as session:
                result = session.process_with_backup(test_file, mask_table, output_file)
                
                if result.success:
                    print(f"   处理统计: {result.modified_packets}/{result.total_packets} 包被修改")
                
                return result
        
        except Exception as e:
            print(f"❌ 上下文管理器使用异常: {str(e)}")
            return None
    else:
        print(f"⚠️  测试文件不存在: {test_file}")
        print("演示上下文管理器基本用法...")
        
        try:
            with MaskingSession(session_config) as session:
                print("   会话已启动，模拟一些操作...")
                time.sleep(0.1)
                print("   模拟操作完成")
        except Exception as e:
            print(f"❌ 上下文管理器演示异常: {str(e)}")
        
        return None


def main():
    """主函数，运行所有高级示例"""
    print("独立PCAP掩码处理器 - 高级使用示例")
    print("=" * 60)
    print("本示例演示高级功能，包括复杂掩码表、批量处理、性能优化等")
    print("注意: 部分示例需要实际的PCAP文件才能完整运行")
    print()
    
    # 设置日志级别
    logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')
    
    # 创建输出目录
    output_dirs = [
        "examples/output",
        "examples/output/processed/batch_results",
        "examples/output/processed/parallel"
    ]
    
    for output_dir in output_dirs:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # 运行所有高级示例
    examples = [
        ("复杂掩码表创建", example_1_complex_mask_table_creation),
        ("性能优化配置", example_2_performance_optimization),
        ("批量文件处理", example_3_batch_processing),
        ("并行批量处理", example_4_parallel_batch_processing),
        ("协议解析控制", example_5_protocol_parsing_control),
        ("上下文管理器使用", example_6_context_manager_usage)
    ]
    
    results = {}
    successful_count = 0
    
    total_start_time = time.time()
    
    for example_name, example_func in examples:
        print(f"\n{'='*20} {example_name} {'='*20}")
        
        try:
            result = example_func()
            results[example_name] = result
            
            if result is not None:
                successful_count += 1
                status = "✅ 成功"
            else:
                status = "⚠️  跳过"
            
        except Exception as e:
            print(f"❌ 示例执行异常: {str(e)}")
            results[example_name] = None
            status = "❌ 失败"
        
        print(f"\n{example_name}: {status}")
    
    total_end_time = time.time()
    total_time = total_end_time - total_start_time
    
    # 显示总结
    print("\n" + "=" * 60)
    print("高级示例执行总结")
    print("=" * 60)
    
    for example_name, result in results.items():
        if result is None:
            status = "⚠️  跳过/失败"
        else:
            status = "✅ 成功"
        
        print(f"   {example_name}: {status}")
    
    print(f"\n成功运行 {successful_count}/{len(examples)} 个高级示例")
    print(f"总耗时: {total_time:.2f} 秒")
    
    # 显示输出文件
    print("\n生成的输出文件:")
    for output_dir in output_dirs:
        output_path = Path(output_dir)
        if output_path.exists():
            for file_path in output_path.rglob("*"):
                if file_path.is_file():
                    size = file_path.stat().st_size
                    relative_path = file_path.relative_to(Path("examples"))
                    print(f"   {relative_path}: {size:,} bytes")
    
    print("\n高级使用示例演示完成！")
    print("有关更多信息，请参阅API文档和基础使用示例")


if __name__ == "__main__":
    main() 