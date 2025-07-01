#!/usr/bin/env python3
"""
Enhanced MaskStage 性能基准测试

验证Enhanced MaskStage在不同负载下的性能表现，确保与EnhancedTrimmer性能对等。
"""

import pytest
import tempfile
import time
import statistics
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any
import os

from pktmask.core.pipeline.stages.mask_payload.stage import MaskStage
from pktmask.core.pipeline.models import StageStats


class TestEnhancedMaskStagePerformance:
    """Enhanced MaskStage 性能基准测试"""

    def setup_method(self):
        """测试前置设置"""
        self.test_data_dir = Path(__file__).parent.parent / "data" / "tls"
        self.temp_dir = Path(tempfile.mkdtemp(prefix="enhanced_mask_stage_perf_"))
        
    def teardown_method(self):
        """测试后清理"""
        import shutil
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch('pktmask.core.pipeline.stages.mask_payload.stage.MaskStage._initialize_enhanced_mode')
    def test_initialization_performance(self, mock_init):
        """测试初始化性能"""
        mock_init.return_value = None
        
        # 测量初始化时间
        times = []
        for _ in range(10):
            start_time = time.time()
            
            stage = MaskStage({
                "mode": "enhanced",
                "preserve_ratio": 0.3,
                "tls_strategy_enabled": True
            })
            stage.initialize()
            
            end_time = time.time()
            times.append((end_time - start_time) * 1000)  # 转换为毫秒
        
        # 性能基准：初始化应该在50ms内完成
        avg_time = statistics.mean(times)
        max_time = max(times)
        
        print(f"初始化性能统计:")
        print(f"  平均时间: {avg_time:.2f}ms")
        print(f"  最大时间: {max_time:.2f}ms")
        print(f"  标准差: {statistics.stdev(times):.2f}ms")
        
        assert avg_time < 50.0, f"初始化平均时间过长: {avg_time:.2f}ms"
        assert max_time < 100.0, f"初始化最大时间过长: {max_time:.2f}ms"

    def test_enhanced_mode_vs_basic_mode_performance(self):
        """测试增强模式与基础模式的性能对比"""
        # Mock 测试数据
        mock_packets = [Mock() for _ in range(100)]
        
        with patch('pktmask.core.pipeline.stages.mask_payload.stage.rdpcap') as mock_rdpcap, \
             patch('pktmask.core.pipeline.stages.mask_payload.stage.wrpcap') as mock_wrpcap:
            
            mock_rdpcap.return_value = mock_packets
            
            # 测试增强模式性能
            enhanced_times = []
            enhanced_stage = MaskStage({"mode": "enhanced"})
            
            # Mock MultiStageExecutor for enhanced mode
            mock_executor = Mock()
            mock_result = Mock()
            mock_result.success = True
            mock_result.stage_results = [Mock(packets_processed=100, packets_modified=50)]
            
            for _ in range(5):
                mock_executor.execute_pipeline.return_value = mock_result
                enhanced_stage._use_enhanced_mode = True
                enhanced_stage._executor = mock_executor
                
                with tempfile.NamedTemporaryFile(suffix='.pcap') as input_file, \
                     tempfile.NamedTemporaryFile(suffix='.pcap') as output_file:
                    
                    start_time = time.time()
                    enhanced_stage.process_file(input_file.name, output_file.name)
                    end_time = time.time()
                    
                    enhanced_times.append((end_time - start_time) * 1000)
            
            # 测试基础模式性能
            basic_times = []
            basic_stage = MaskStage({"mode": "basic"})
            basic_stage._use_enhanced_mode = False
            basic_stage._masker = None  # 无掩码器，直接复制
            
            for _ in range(5):
                with tempfile.NamedTemporaryFile(suffix='.pcap') as input_file, \
                     tempfile.NamedTemporaryFile(suffix='.pcap') as output_file:
                    
                    start_time = time.time()
                    basic_stage.process_file(input_file.name, output_file.name)
                    end_time = time.time()
                    
                    basic_times.append((end_time - start_time) * 1000)
            
            # 性能分析
            enhanced_avg = statistics.mean(enhanced_times)
            basic_avg = statistics.mean(basic_times)
            
            print(f"性能对比:")
            print(f"  增强模式平均: {enhanced_avg:.2f}ms")
            print(f"  基础模式平均: {basic_avg:.2f}ms")
            print(f"  性能差异: {(enhanced_avg / basic_avg):.2f}x")
            
            # 基础模式应该更快（因为功能简单）
            assert basic_avg < enhanced_avg, "基础模式应该比增强模式更快"
            
            # 增强模式不应该比基础模式慢太多（不超过10倍）
            assert enhanced_avg / basic_avg < 10.0, f"增强模式过慢，性能差异: {enhanced_avg / basic_avg:.2f}x"

    def test_memory_usage_simulation(self):
        """测试内存使用情况模拟"""
        import psutil
        import gc
        
        # 获取当前进程
        process = psutil.Process()
        
        # 记录初始内存
        gc.collect()  # 强制垃圾回收
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # 创建多个MaskStage实例
        stages = []
        for i in range(10):
            stage = MaskStage({
                "mode": "enhanced",
                "preserve_ratio": 0.3,
                "instance_id": i
            })
            stages.append(stage)
        
        # 记录创建后内存
        gc.collect()
        after_creation_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # 清理
        stages.clear()
        gc.collect()
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # 内存使用分析
        creation_overhead = after_creation_memory - initial_memory
        cleanup_efficiency = (after_creation_memory - final_memory) / creation_overhead if creation_overhead > 0 else 1.0
        
        print(f"内存使用分析:")
        print(f"  初始内存: {initial_memory:.2f}MB")
        print(f"  创建后内存: {after_creation_memory:.2f}MB")
        print(f"  清理后内存: {final_memory:.2f}MB")
        print(f"  创建开销: {creation_overhead:.2f}MB")
        print(f"  清理效率: {cleanup_efficiency:.2%}")
        
        # 内存基准：10个实例不应该占用超过50MB额外内存
        assert creation_overhead < 50.0, f"内存使用过多: {creation_overhead:.2f}MB"
        
        # 清理效率应该大于80%
        assert cleanup_efficiency > 0.8, f"内存清理效率低: {cleanup_efficiency:.2%}"

    def test_concurrent_processing_simulation(self):
        """测试并发处理能力模拟"""
        import threading
        import concurrent.futures
        
        def process_single_file(stage_config: Dict[str, Any], file_id: int) -> Dict[str, Any]:
            """单个文件处理任务"""
            stage = MaskStage(stage_config)
            
            # Mock处理结果
            mock_executor = Mock()
            mock_result = Mock()
            mock_result.success = True
            mock_result.stage_results = [Mock(packets_processed=100, packets_modified=30)]
            mock_executor.execute_pipeline.return_value = mock_result
            
            stage._use_enhanced_mode = True
            stage._executor = mock_executor
            
            start_time = time.time()
            
            with tempfile.NamedTemporaryFile(suffix='.pcap') as input_file, \
                 tempfile.NamedTemporaryFile(suffix='.pcap') as output_file:
                
                result = stage.process_file(input_file.name, output_file.name)
                
            end_time = time.time()
            
            return {
                'file_id': file_id,
                'duration': (end_time - start_time) * 1000,
                'packets_processed': result.packets_processed if result else 0,
                'success': result is not None
            }
        
        # 模拟并发处理
        config = {"mode": "enhanced", "preserve_ratio": 0.3}
        
        with patch('pktmask.core.pipeline.stages.mask_payload.stage.rdpcap') as mock_rdpcap, \
             patch('pktmask.core.pipeline.stages.mask_payload.stage.wrpcap') as mock_wrpcap:
            
            mock_rdpcap.return_value = [Mock() for _ in range(100)]
            
            # 并发处理5个文件
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                futures = [
                    executor.submit(process_single_file, config, i)
                    for i in range(5)
                ]
                
                results = [future.result(timeout=10) for future in futures]
        
        # 性能分析
        durations = [r['duration'] for r in results]
        success_rate = sum(1 for r in results if r['success']) / len(results)
        
        print(f"并发处理分析:")
        print(f"  任务数量: {len(results)}")
        print(f"  成功率: {success_rate:.2%}")
        print(f"  平均耗时: {statistics.mean(durations):.2f}ms")
        print(f"  最大耗时: {max(durations):.2f}ms")
        print(f"  耗时标准差: {statistics.stdev(durations):.2f}ms")
        
        # 并发基准：成功率应该100%，平均耗时应该合理
        assert success_rate == 1.0, f"并发处理成功率低: {success_rate:.2%}"
        assert statistics.mean(durations) < 100.0, f"并发处理平均耗时过长: {statistics.mean(durations):.2f}ms"

    def test_large_file_processing_simulation(self):
        """测试大文件处理能力模拟"""
        # 模拟不同大小的文件
        file_sizes = [100, 500, 1000, 5000]  # 数据包数量
        
        results = []
        
        with patch('pktmask.core.pipeline.stages.mask_payload.stage.rdpcap') as mock_rdpcap, \
             patch('pktmask.core.pipeline.stages.mask_payload.stage.wrpcap') as mock_wrpcap:
            
            for size in file_sizes:
                mock_packets = [Mock() for _ in range(size)]
                mock_rdpcap.return_value = mock_packets
                
                stage = MaskStage({"mode": "enhanced"})
                
                # Mock执行器
                mock_executor = Mock()
                mock_result = Mock()
                mock_result.success = True
                mock_result.stage_results = [Mock(packets_processed=size, packets_modified=size//3)]
                mock_executor.execute_pipeline.return_value = mock_result
                
                stage._use_enhanced_mode = True
                stage._executor = mock_executor
                
                # 执行处理
                with tempfile.NamedTemporaryFile(suffix='.pcap') as input_file, \
                     tempfile.NamedTemporaryFile(suffix='.pcap') as output_file:
                    
                    start_time = time.time()
                    result = stage.process_file(input_file.name, output_file.name)
                    end_time = time.time()
                    
                    duration = (end_time - start_time) * 1000
                    throughput = size / duration * 1000  # packets per second
                    
                    results.append({
                        'size': size,
                        'duration': duration,
                        'throughput': throughput,
                        'success': result is not None
                    })
        
        # 性能分析
        print(f"大文件处理分析:")
        for r in results:
            print(f"  {r['size']:4d} 包: {r['duration']:6.2f}ms, {r['throughput']:8.1f} pps")
        
        # 基准测试：所有大小文件都应该成功处理
        success_rates = [r['success'] for r in results]
        assert all(success_rates), "部分大文件处理失败"
        
        # 吞吐量应该相对稳定（不应该随文件大小急剧下降）
        throughputs = [r['throughput'] for r in results]
        min_throughput = min(throughputs)
        max_throughput = max(throughputs)
        
        assert min_throughput > 1000, f"最小吞吐量过低: {min_throughput:.1f} pps"
        assert max_throughput / min_throughput < 10, f"吞吐量变化过大: {max_throughput/min_throughput:.2f}x"

    def test_error_recovery_performance(self):
        """测试错误恢复性能"""
        error_scenarios = [
            {"name": "enhanced_mode_failure", "simulate_enhanced_failure": True},
            {"name": "file_read_error", "simulate_file_error": True},
            {"name": "normal_operation", "simulate_enhanced_failure": False}
        ]
        
        results = []
        
        for scenario in error_scenarios:
            stage = MaskStage({"mode": "enhanced"})
            
            times = []
            for _ in range(3):  # 多次测试
                with tempfile.NamedTemporaryFile(suffix='.pcap') as input_file, \
                     tempfile.NamedTemporaryFile(suffix='.pcap') as output_file:
                    
                    start_time = time.time()
                    
                    try:
                        if scenario.get("simulate_enhanced_failure"):
                            # 模拟增强模式失败，触发降级
                            stage._use_enhanced_mode = True
                            stage._executor = Mock()
                            stage._executor.execute_pipeline.side_effect = Exception("模拟失败")
                            
                            with patch('pktmask.core.pipeline.stages.mask_payload.stage.rdpcap') as mock_rdpcap, \
                                 patch('pktmask.core.pipeline.stages.mask_payload.stage.wrpcap'):
                                mock_rdpcap.return_value = [Mock() for _ in range(10)]
                                result = stage.process_file(input_file.name, output_file.name)
                        
                        elif scenario.get("simulate_file_error"):
                            # 模拟文件错误
                            with patch('pktmask.core.pipeline.stages.mask_payload.stage.rdpcap', 
                                     side_effect=Exception("文件读取失败")):
                                try:
                                    result = stage.process_file(input_file.name, output_file.name)
                                except Exception:
                                    result = None
                        
                        else:
                            # 正常操作
                            mock_executor = Mock()
                            mock_result = Mock()
                            mock_result.success = True
                            mock_result.stage_results = [Mock(packets_processed=10, packets_modified=5)]
                            mock_executor.execute_pipeline.return_value = mock_result
                            
                            stage._use_enhanced_mode = True
                            stage._executor = mock_executor
                            
                            with patch('pktmask.core.pipeline.stages.mask_payload.stage.rdpcap') as mock_rdpcap, \
                                 patch('pktmask.core.pipeline.stages.mask_payload.stage.wrpcap'):
                                mock_rdpcap.return_value = [Mock() for _ in range(10)]
                                result = stage.process_file(input_file.name, output_file.name)
                        
                    except Exception as e:
                        result = None
                    
                    end_time = time.time()
                    times.append((end_time - start_time) * 1000)
            
            avg_time = statistics.mean(times)
            results.append({
                'scenario': scenario['name'],
                'avg_time': avg_time,
                'times': times
            })
        
        # 分析结果
        print(f"错误恢复性能分析:")
        for r in results:
            print(f"  {r['scenario']:20s}: {r['avg_time']:6.2f}ms")
        
        # 基准：错误恢复不应该比正常操作慢太多
        normal_time = next(r['avg_time'] for r in results if r['scenario'] == 'normal_operation')
        
        for r in results:
            if r['scenario'] != 'normal_operation':
                recovery_overhead = r['avg_time'] / normal_time
                assert recovery_overhead < 5.0, f"{r['scenario']} 恢复时间过长: {recovery_overhead:.2f}x"


if __name__ == "__main__":
    # 可以单独运行性能测试
    pytest.main([__file__, "-v", "-s"]) 