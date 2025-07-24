"""
Next-Generation MaskStage End-to-End Integration Tests

Tests complete file processing workflow: input pcap file -> Marker module analysis -> Masker module masking -> output masked file
Validates dual-module architecture complete functionality and performance.
"""

import pytest
import tempfile
import time
import os
from pathlib import Path
from unittest.mock import patch

from pktmask.core.pipeline.stages.mask_payload_v2.stage import MaskingStage
from pktmask.core.pipeline.models import StageStats


class TestMaskPayloadV2EndToEnd:
    """Next-Generation MaskStage End-to-End Tests"""

    @pytest.fixture
    def test_files(self):
        """Get test file list"""
        test_data_dir = Path("tests/data/tls")
        if not test_data_dir.exists():
            pytest.skip("TLS test data directory does not exist")

        pcap_files = list(test_data_dir.glob("*.pcap")) + list(
            test_data_dir.glob("*.pcapng")
        )
        if not pcap_files:
            pytest.skip("No TLS test files found")

        return pcap_files[:2]  # Only use first 2 files for end-to-end testing

    @pytest.fixture
    def temp_output_dir(self):
        """Create temporary output directory"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def stage_config(self):
        """标准测试配置"""
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

    def test_end_to_end_file_processing(
        self, test_files, temp_output_dir, stage_config
    ):
        """测试端到端文件处理流程"""
        stage = MaskingStage(stage_config)

        # 初始化阶段
        success = stage.initialize()
        assert success, "阶段初始化失败"

        results = []

        for input_file in test_files:
            print(f"\n处理文件: {input_file.name}")

            # 生成输出文件路径
            output_file = temp_output_dir / f"masked_{input_file.name}"

            # 记录开始时间
            start_time = time.time()

            try:
                # 执行文件处理
                stats = stage.process_file(str(input_file), str(output_file))

                # 记录处理时间
                processing_time = time.time() - start_time

                # 验证返回的统计信息
                assert isinstance(stats, StageStats)
                assert stats.packets_processed >= 0
                assert stats.packets_modified >= 0
                assert stats.packets_modified <= stats.packets_processed

                # 验证输出文件存在
                assert output_file.exists(), f"输出文件不存在: {output_file}"
                assert output_file.stat().st_size > 0, f"输出文件为空: {output_file}"

                # 记录结果
                result = {
                    "input_file": input_file.name,
                    "output_file": output_file.name,
                    "success": True,
                    "processing_time": processing_time,
                    "packets_processed": stats.packets_processed,
                    "packets_modified": stats.packets_modified,
                    "input_size": input_file.stat().st_size,
                    "output_size": output_file.stat().st_size,
                    "stats": stats,
                }
                results.append(result)

                print(
                    f"  - 处理成功: {stats.packets_processed} 包处理, {stats.packets_modified} 包修改"
                )
                print(f"  - 处理时间: {processing_time:.3f}s")
                print(
                    f"  - 文件大小: {input_file.stat().st_size} -> {output_file.stat().st_size}"
                )

            except Exception as e:
                result = {
                    "input_file": input_file.name,
                    "success": False,
                    "error": str(e),
                    "processing_time": time.time() - start_time,
                }
                results.append(result)
                print(f"  - 处理失败: {e}")

        # 清理资源
        stage.cleanup()

        # 验证至少有一个文件处理成功
        successful_results = [r for r in results if r["success"]]
        assert len(successful_results) > 0, f"所有文件处理都失败了: {results}"

        # 打印总结
        print(f"\n端到端测试总结:")
        print(f"  - 成功处理: {len(successful_results)}/{len(results)}")

        if successful_results:
            total_packets = sum(r["packets_processed"] for r in successful_results)
            total_modified = sum(r["packets_modified"] for r in successful_results)
            total_time = sum(r["processing_time"] for r in successful_results)

            print(f"  - 总包数: {total_packets}")
            print(f"  - 修改包数: {total_modified}")
            print(f"  - 总处理时间: {total_time:.3f}s")
            print(
                f"  - 平均速度: {total_packets/total_time:.1f} 包/秒"
                if total_time > 0
                else "  - 平均速度: N/A"
            )

        return results

    def test_dual_module_architecture_verification(
        self, test_files, temp_output_dir, stage_config
    ):
        """验证双模块架构的正确工作"""
        stage = MaskingStage(stage_config)
        stage.initialize()

        input_file = test_files[0]
        output_file = temp_output_dir / f"dual_module_test_{input_file.name}"

        # 使用 patch 来监控模块调用
        with (
            patch.object(
                stage.marker, "analyze_file", wraps=stage.marker.analyze_file
            ) as mock_marker,
            patch.object(
                stage.masker, "apply_masking", wraps=stage.masker.apply_masking
            ) as mock_masker,
        ):

            stats = stage.process_file(str(input_file), str(output_file))

            # 验证两个模块都被调用
            mock_marker.assert_called_once()
            mock_masker.assert_called_once()

            # 验证调用参数
            marker_args = mock_marker.call_args
            masker_args = mock_masker.call_args

            assert marker_args[0][0] == str(input_file)  # Marker 输入文件路径
            assert masker_args[0][0] == str(input_file)  # Masker 输入文件路径
            assert masker_args[0][1] == str(output_file)  # Masker 输出文件路径

            print(f"双模块架构验证成功:")
            print(f"  - Marker模块调用: ✓")
            print(f"  - Masker模块调用: ✓")
            print(f"  - 参数传递正确: ✓")

        stage.cleanup()

    def test_error_handling_and_recovery(self, temp_output_dir, stage_config):
        """测试错误处理和恢复机制"""
        stage = MaskingStage(stage_config)
        stage.initialize()

        # 测试不存在的输入文件
        non_existent_file = "/tmp/non_existent_file.pcap"
        output_file = temp_output_dir / "error_test_output.pcap"

        try:
            stats = stage.process_file(non_existent_file, str(output_file))
            # 如果没有抛出异常，检查是否使用了降级处理
            print(f"错误处理测试: 使用降级处理，返回统计: {stats}")
        except Exception as e:
            print(f"错误处理测试: 正确抛出异常: {e}")

        stage.cleanup()

    def test_configuration_compatibility(self, test_files, temp_output_dir):
        """测试配置兼容性"""
        input_file = test_files[0]

        # 测试不同的配置格式
        configs = [
            # 新格式配置
            {
                "protocol": "tls",
                "mode": "enhanced",
                "marker_config": {"tls": {"preserve_handshake": True}},
                "masker_config": {"chunk_size": 500},
            },
            # 旧版兼容配置
            {
                "mode": "enhanced",
                "recipe_dict": {
                    "tls_20_strategy": "preserve",
                    "tls_21_strategy": "preserve",
                    "tls_22_strategy": "mask",
                    "tls_23_strategy": "mask",
                    "tls_24_strategy": "preserve",
                },
            },
            # 最小配置
            {},
        ]

        for i, config in enumerate(configs):
            print(f"\n测试配置 {i+1}: {config}")

            stage = MaskingStage(config)
            success = stage.initialize()

            if success:
                output_file = temp_output_dir / f"config_test_{i+1}_{input_file.name}"

                try:
                    stats = stage.process_file(str(input_file), str(output_file))
                    print(f"  - 配置兼容性测试成功: {stats.packets_processed} 包处理")
                except Exception as e:
                    print(f"  - 配置兼容性测试失败: {e}")

                stage.cleanup()
            else:
                print(f"  - 配置初始化失败")
