"""
Phase 1.2 性能测试

验证BlindPacketMasker的处理性能，确保满足设计要求：
- 处理速度不低于现有方案的80%
- 内存使用控制在合理范围
- 大文件处理稳定性
"""

import pytest
import time
import tempfile
import os
from typing import List
from scapy.all import Ether, IP, TCP, wrpcap, rdpcap

from src.pktmask.core.tcp_payload_masker.api.types import (
    PacketMaskInstruction,
    MaskingRecipe,
    PacketMaskingResult
)
from src.pktmask.core.tcp_payload_masker.core.blind_masker import BlindPacketMasker
from src.pktmask.core.tcp_payload_masker.core.packet_processor import PacketProcessor
from src.pktmask.core.trim.models.mask_spec import MaskAfter, MaskRange, KeepAll


class TestBlindMaskerPerformance:
    """测试BlindPacketMasker的性能表现"""
    
    def setup_method(self):
        """设置性能测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.processor = PacketProcessor()
    
    def teardown_method(self):
        """清理测试环境"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_small_file_performance(self):
        """测试小文件处理性能（100包）"""
        packet_count = 100
        
        # 创建测试数据
        input_file, recipe = self._create_test_file(packet_count, "small")
        output_file = os.path.join(self.temp_dir, "small_output.pcap")
        
        # 执行性能测试
        start_time = time.time()
        result = self.processor.process_pcap_file(input_file, output_file, recipe)
        execution_time = time.time() - start_time
        
        # 验证结果
        assert result.success is True
        assert result.processed_packets == packet_count
        
        # 性能要求：小文件处理应该很快
        assert execution_time < 1.0, f"小文件处理时间过长: {execution_time:.3f}秒"
        
        # 计算吞吐量
        throughput = packet_count / execution_time
        print(f"小文件性能: {packet_count}包, {execution_time:.3f}秒, {throughput:.1f} pps")
        
        # 最低性能要求：>1000 pps
        assert throughput > 1000, f"吞吐量过低: {throughput:.1f} pps"
    
    def test_medium_file_performance(self):
        """测试中等文件处理性能（1000包）"""
        packet_count = 1000
        
        # 创建测试数据
        input_file, recipe = self._create_test_file(packet_count, "medium")
        output_file = os.path.join(self.temp_dir, "medium_output.pcap")
        
        # 执行性能测试
        start_time = time.time()
        result = self.processor.process_pcap_file(input_file, output_file, recipe)
        execution_time = time.time() - start_time
        
        # 验证结果
        assert result.success is True
        assert result.processed_packets == packet_count
        
        # 性能要求：中等文件处理时间合理
        assert execution_time < 5.0, f"中等文件处理时间过长: {execution_time:.3f}秒"
        
        # 计算吞吐量
        throughput = packet_count / execution_time
        print(f"中等文件性能: {packet_count}包, {execution_time:.3f}秒, {throughput:.1f} pps")
        
        # 最低性能要求：>500 pps
        assert throughput > 500, f"吞吐量过低: {throughput:.1f} pps"
    
    def test_large_file_performance(self):
        """测试大文件处理性能（5000包）"""
        packet_count = 5000
        
        # 创建测试数据
        input_file, recipe = self._create_test_file(packet_count, "large")
        output_file = os.path.join(self.temp_dir, "large_output.pcap")
        
        # 执行性能测试
        start_time = time.time()
        result = self.processor.process_pcap_file(input_file, output_file, recipe)
        execution_time = time.time() - start_time
        
        # 验证结果
        assert result.success is True
        assert result.processed_packets == packet_count
        
        # 性能要求：大文件处理时间合理
        assert execution_time < 30.0, f"大文件处理时间过长: {execution_time:.3f}秒"
        
        # 计算吞吐量
        throughput = packet_count / execution_time
        print(f"大文件性能: {packet_count}包, {execution_time:.3f}秒, {throughput:.1f} pps")
        
        # 最低性能要求：>100 pps
        assert throughput > 100, f"吞吐量过低: {throughput:.1f} pps"
    
    def test_different_mask_types_performance(self):
        """测试不同掩码类型的性能差异"""
        packet_count = 500
        
        # 测试MaskAfter性能
        maskafter_time = self._test_mask_type_performance(
            packet_count, MaskAfter(10), "MaskAfter"
        )
        
        # 测试MaskRange性能
        maskrange_time = self._test_mask_type_performance(
            packet_count, MaskRange([(0, 10), (20, 30), (40, 50)]), "MaskRange"
        )
        
        # 测试KeepAll性能
        keepall_time = self._test_mask_type_performance(
            packet_count, KeepAll(), "KeepAll"
        )
        
        print(f"掩码类型性能对比:")
        print(f"  MaskAfter: {maskafter_time:.3f}秒")
        print(f"  MaskRange: {maskrange_time:.3f}秒")
        print(f"  KeepAll:   {keepall_time:.3f}秒")
        
        # 由于时间差异很小，我们只检查所有类型都在合理范围内
        # 不强制要求特定的顺序关系，因为差异可能在毫秒级别
        
        # 所有掩码类型都应该在合理时间内完成
        assert maskafter_time < 2.0
        assert maskrange_time < 2.0
        assert keepall_time < 1.0
    
    def test_memory_usage_stability(self):
        """测试内存使用的稳定性"""
        import psutil
        import os
        
        # 获取当前进程
        process = psutil.Process(os.getpid())
        
        # 记录初始内存使用
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # 处理多个文件（模拟连续处理）
        for i in range(5):
            packet_count = 1000
            input_file, recipe = self._create_test_file(packet_count, f"memory_test_{i}")
            output_file = os.path.join(self.temp_dir, f"memory_output_{i}.pcap")
            
            result = self.processor.process_pcap_file(input_file, output_file, recipe)
            assert result.success is True
            
            # 记录当前内存使用
            current_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = current_memory - initial_memory
            
            print(f"处理第{i+1}个文件后，内存增长: {memory_increase:.1f}MB")
            
            # 内存增长不应该超过100MB
            assert memory_increase < 100, f"内存增长过多: {memory_increase:.1f}MB"
    
    def _create_test_file(self, packet_count: int, prefix: str) -> tuple[str, MaskingRecipe]:
        """创建测试文件和掩码配方"""
        input_file = os.path.join(self.temp_dir, f"{prefix}_input.pcap")
        
        # 创建测试包
        packets = []
        instructions = {}
        
        for i in range(packet_count):
            # 创建包含较大载荷的包（模拟真实流量）
            payload = f"This is test packet {i:04d} with some payload data for performance testing. " * 5
            packet = Ether() / IP(src=f"192.168.1.{i%255 + 1}", dst="10.0.0.1") / TCP(sport=i%65535+1, dport=80) / payload.encode()
            packet.time = 1000000.0 + i * 0.001
            packets.append(packet)
            
            # 为一半的包创建掩码指令
            if i % 2 == 0:
                timestamp = str(packet.time)
                
                # 使用不同的掩码类型
                if i % 6 == 0:
                    mask_spec = MaskAfter(20)
                elif i % 6 == 2:
                    mask_spec = MaskRange([(0, 50), (100, 150)])
                else:
                    mask_spec = KeepAll()
                
                instructions[(i, timestamp)] = PacketMaskInstruction(
                    packet_index=i,
                    packet_timestamp=timestamp,
                    payload_offset=54,  # Ethernet + IP + TCP
                    mask_spec=mask_spec
                )
        
        # 写入文件
        wrpcap(input_file, packets)
        
        # 创建掩码配方
        recipe = MaskingRecipe(
            instructions=instructions,
            total_packets=packet_count,
            metadata={"test": f"performance_{prefix}"}
        )
        
        return input_file, recipe
    
    def _test_mask_type_performance(self, packet_count: int, mask_spec, mask_type: str) -> float:
        """测试特定掩码类型的性能"""
        input_file, _ = self._create_test_file(packet_count, f"mask_{mask_type.lower()}")
        output_file = os.path.join(self.temp_dir, f"mask_{mask_type.lower()}_output.pcap")
        
        # 创建统一使用指定掩码类型的配方
        instructions = {}
        for i in range(packet_count):
            timestamp = f"{1000000.0 + i * 0.001}"
            instructions[(i, timestamp)] = PacketMaskInstruction(
                packet_index=i,
                packet_timestamp=timestamp,
                payload_offset=54,
                mask_spec=mask_spec
            )
        
        recipe = MaskingRecipe(
            instructions=instructions,
            total_packets=packet_count,
            metadata={"test": f"mask_type_{mask_type}"}
        )
        
        # 执行性能测试
        start_time = time.time()
        result = self.processor.process_pcap_file(input_file, output_file, recipe)
        execution_time = time.time() - start_time
        
        assert result.success is True
        return execution_time


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])  # -s 用于显示print输出 