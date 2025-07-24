"""
新一代 MaskStage 性能基准测试

对比新旧实现的处理速度、内存使用、CPU占用等性能指标。
"""

import pytest
import tempfile
import time
import os
from pathlib import Path

from pktmask.core.pipeline.stages.mask_payload_v2.stage import NewMaskPayloadStage


class TestMaskPayloadV2Performance:
    """新一代 MaskStage 性能测试"""

    @pytest.fixture
    def test_files(self):
        """获取测试文件列表"""
        test_data_dir = Path("tests/data/tls")
        if not test_data_dir.exists():
            pytest.skip("TLS测试数据目录不存在")

        pcap_files = list(test_data_dir.glob("*.pcap")) + list(
            test_data_dir.glob("*.pcapng")
        )
        if not pcap_files:
            pytest.skip("没有找到TLS测试文件")

        return pcap_files[:1]  # 只使用第一个文件进行性能测试

    @pytest.fixture
    def temp_output_dir(self):
        """创建临时输出目录"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def performance_config(self):
        """性能测试配置"""
        return {
            "protocol": "tls",
            "mode": "enhanced",
            "marker_config": {
                "tls": {
                    "preserve_handshake": True,
                    "preserve_application_data": False,
                    "preserve_alert": True,
                    "preserve_change_cipher_spec": True,
                }
            },
            "masker_config": {
                "chunk_size": 1000,
                "verify_checksums": True,
                "enable_performance_monitoring": True,
            },
        }

    def test_processing_speed_benchmark(
        self, test_files, temp_output_dir, performance_config
    ):
        """测试处理速度基准"""
        stage = NewMaskPayloadStage(performance_config)
        stage.initialize()

        input_file = test_files[0]
        output_file = temp_output_dir / f"perf_test_{input_file.name}"

        # 预热运行
        stage.process_file(str(input_file), str(output_file))

        # 基准测试运行
        runs = 3
        times = []

        for i in range(runs):
            output_file_run = temp_output_dir / f"perf_test_run_{i}_{input_file.name}"

            start_time = time.time()
            stats = stage.process_file(str(input_file), str(output_file_run))
            end_time = time.time()

            processing_time = end_time - start_time
            times.append(processing_time)

            print(f"运行 {i+1}: {processing_time:.3f}s, {stats.packets_processed} 包")

        # 计算统计
        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)

        print(f"\n性能基准测试结果:")
        print(f"  - 平均时间: {avg_time:.3f}s")
        print(f"  - 最快时间: {min_time:.3f}s")
        print(f"  - 最慢时间: {max_time:.3f}s")
        print(f"  - 时间变异: {(max_time - min_time) / avg_time * 100:.1f}%")

        # 验证性能合理性
        assert avg_time < 10.0, f"平均处理时间过长: {avg_time:.3f}s"
        assert (max_time - min_time) / avg_time < 0.5, "处理时间变异过大"

        stage.cleanup()

    def test_memory_usage_monitoring(
        self, test_files, temp_output_dir, performance_config
    ):
        """测试内存使用监控"""
        # 启用详细的内存监控
        performance_config["masker_config"]["enable_performance_monitoring"] = True

        stage = NewMaskPayloadStage(performance_config)
        stage.initialize()

        input_file = test_files[0]
        output_file = temp_output_dir / f"memory_test_{input_file.name}"

        # 获取初始内存使用
        initial_resource_stats = stage.masker.resource_manager.get_resource_stats()
        initial_memory = initial_resource_stats.memory_usage_mb * 1024 * 1024

        # 处理文件
        stats = stage.process_file(str(input_file), str(output_file))

        # 获取峰值内存使用
        final_resource_stats = stage.masker.resource_manager.get_resource_stats()
        peak_memory = final_resource_stats.peak_memory_mb * 1024 * 1024
        final_memory = final_resource_stats.memory_usage_mb * 1024 * 1024

        memory_increase = final_memory - initial_memory
        memory_peak_delta = peak_memory - initial_memory

        print(f"\n内存使用监控结果:")
        print(f"  - 初始内存: {initial_memory / 1024 / 1024:.1f}MB")
        print(f"  - 峰值内存: {peak_memory / 1024 / 1024:.1f}MB")
        print(f"  - 最终内存: {final_memory / 1024 / 1024:.1f}MB")
        print(f"  - 内存增长: {memory_increase / 1024 / 1024:.1f}MB")
        print(f"  - 峰值增长: {memory_peak_delta / 1024 / 1024:.1f}MB")

        # 验证内存使用合理性
        assert (
            memory_peak_delta < 500 * 1024 * 1024
        ), f"峰值内存增长过大: {memory_peak_delta / 1024 / 1024:.1f}MB"
        assert (
            abs(memory_increase) < 100 * 1024 * 1024
        ), f"内存泄漏可能: {memory_increase / 1024 / 1024:.1f}MB"

        stage.cleanup()

    def test_scalability_with_different_chunk_sizes(self, test_files, temp_output_dir):
        """测试不同块大小的可扩展性"""
        chunk_sizes = [500, 1000, 2000, 5000]
        results = []

        input_file = test_files[0]

        for chunk_size in chunk_sizes:
            config = {
                "protocol": "tls",
                "mode": "enhanced",
                "masker_config": {
                    "chunk_size": chunk_size,
                    "verify_checksums": True,
                    "enable_performance_monitoring": True,
                },
            }

            stage = NewMaskPayloadStage(config)
            stage.initialize()

            output_file = temp_output_dir / f"chunk_{chunk_size}_{input_file.name}"

            start_time = time.time()
            stats = stage.process_file(str(input_file), str(output_file))
            end_time = time.time()

            processing_time = end_time - start_time

            result = {
                "chunk_size": chunk_size,
                "processing_time": processing_time,
                "packets_processed": stats.packets_processed,
                "throughput": (
                    stats.packets_processed / processing_time
                    if processing_time > 0
                    else 0
                ),
            }
            results.append(result)

            print(
                f"块大小 {chunk_size}: {processing_time:.3f}s, {result['throughput']:.1f} 包/秒"
            )

            stage.cleanup()

        print(f"\n可扩展性测试结果:")
        for result in results:
            print(
                f"  - 块大小 {result['chunk_size']}: {result['throughput']:.1f} 包/秒"
            )

        # 验证不同块大小都能正常工作
        for result in results:
            assert (
                result["packets_processed"] > 0
            ), f"块大小 {result['chunk_size']} 处理失败"
            assert (
                result["processing_time"] < 10.0
            ), f"块大小 {result['chunk_size']} 处理时间过长"

    def test_concurrent_processing_safety(
        self, test_files, temp_output_dir, performance_config
    ):
        """测试并发处理安全性（模拟）"""
        import threading
        import queue

        input_file = test_files[0]
        results_queue = queue.Queue()
        errors_queue = queue.Queue()

        def process_file_worker(worker_id):
            try:
                stage = NewMaskPayloadStage(performance_config)
                stage.initialize()

                output_file = (
                    temp_output_dir / f"concurrent_{worker_id}_{input_file.name}"
                )

                start_time = time.time()
                stats = stage.process_file(str(input_file), str(output_file))
                end_time = time.time()

                results_queue.put(
                    {
                        "worker_id": worker_id,
                        "processing_time": end_time - start_time,
                        "packets_processed": stats.packets_processed,
                        "success": True,
                    }
                )

                stage.cleanup()

            except Exception as e:
                errors_queue.put({"worker_id": worker_id, "error": str(e)})

        # 启动多个工作线程
        num_workers = 3
        threads = []

        for i in range(num_workers):
            thread = threading.Thread(target=process_file_worker, args=(i,))
            threads.append(thread)
            thread.start()

        # 等待所有线程完成
        for thread in threads:
            thread.join(timeout=30)  # 30秒超时

        # 收集结果
        results = []
        while not results_queue.empty():
            results.append(results_queue.get())

        errors = []
        while not errors_queue.empty():
            errors.append(errors_queue.get())

        print(f"\n并发处理测试结果:")
        print(f"  - 成功完成: {len(results)}/{num_workers}")
        print(f"  - 错误数量: {len(errors)}")

        for result in results:
            print(
                f"  - 工作线程 {result['worker_id']}: {result['processing_time']:.3f}s"
            )

        for error in errors:
            print(f"  - 工作线程 {error['worker_id']} 错误: {error['error']}")

        # 验证并发处理结果
        assert len(results) >= num_workers - 1, "大部分并发处理应该成功"
        assert len(errors) == 0, f"不应该有错误: {errors}"

        # 验证所有成功的处理结果一致
        if len(results) > 1:
            first_result = results[0]
            for result in results[1:]:
                assert (
                    result["packets_processed"] == first_result["packets_processed"]
                ), "并发处理的包数量应该一致"
