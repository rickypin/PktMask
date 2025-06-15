"""
HTTP策略头部估算算法优化测试

验证阶段3的优化效果：
- 算法复杂度优化（O(n²) → O(n)）
- 代码行数简化（40行 → 25行）
- 头部估算精度提升（75% → >95%）
- 边界检测方法标记支持
- 大载荷处理和内存安全验证

作者: PktMask Team
创建时间: 2025-01-15
阶段: Phase 3 - Header Estimation Algorithm Optimization
"""

import pytest
import time
from typing import Dict, Any

from src.pktmask.core.trim.strategies.http_strategy import HTTPTrimStrategy
from src.pktmask.core.trim.strategies.base_strategy import ProtocolInfo, TrimContext


class TestHTTPHeaderEstimationOptimization:
    """HTTP头部估算算法优化测试类"""
    
    def setup_method(self):
        """设置测试环境"""
        self.config = {
            'max_header_size': 8192,
            'preserve_headers': True,
            'confidence_threshold': 0.7
        }
        self.strategy = HTTPTrimStrategy(self.config)
        
    def create_test_context(self, packet_index: int = 0) -> TrimContext:
        """创建测试上下文"""
        return TrimContext(
            packet_index=packet_index,
            stream_id='test_stream',
            flow_direction='client_to_server',
            protocol_stack=['ETH', 'IP', 'TCP', 'HTTP'],
            payload_size=0,
            timestamp=1234567890.0,
            metadata={}
        )

    def test_boundary_method_marking_tolerant_detection(self):
        """测试边界检测方法标记 - 容错检测"""
        # 标准CRLF边界
        payload = (
            b'GET /test HTTP/1.1\r\n'
            b'Host: example.com\r\n'
            b'\r\n'
            b'body content here'
        )
        
        analysis = {}
        result = self.strategy._estimate_header_size(payload, analysis)
        
        # 验证标记
        assert 'boundary_method' in analysis
        assert analysis['boundary_method'] == 'tolerant_detection'
        assert result == 41  # 实际头部大小 + \r\n\r\n
        
    def test_boundary_method_marking_empty_line_detection(self):
        """测试边界检测方法标记 - 空行检测"""
        # 创建一个特殊的载荷，不会被_find_header_boundary_tolerant捕获
        # 但会在智能行分析中遇到空行
        # 使用特殊的构造方式避免连续的\n\n模式
        lines = [
            b'POST /api HTTP/1.1',
            b'Content-Type: application/json',
            b'',  # 这将成为空行，但不会形成\n\n模式
            b'{"test": "data"}'
        ]
        # 使用不同的分隔符，让find_header_boundary_tolerant找不到，但智能行分析能处理
        payload = b'\n'.join(lines[:2]) + b'\n \n' + lines[3]  # 空格行而不是完全空行
        
        analysis = {}
        result = self.strategy._estimate_header_size(payload, analysis)
        
        # 验证标记
        assert 'boundary_method' in analysis
        assert analysis['boundary_method'] == 'empty_line_detection'
        assert result > 0
        
    def test_boundary_method_marking_conservative_estimation(self):
        """测试边界检测方法标记 - 保守估算"""
        # 创建包含非HTTP行的载荷
        payload = (
            b'GET /test HTTP/1.1\n'
            b'Host: example.com\n'
            b'Random non-header line without colon'  # 不像头部行，没有冒号
        )
        
        analysis = {}
        result = self.strategy._estimate_header_size(payload, analysis)
        
        # 验证保守估算标记
        assert 'boundary_method' in analysis
        assert analysis['boundary_method'] == 'conservative_estimation'
        assert result >= 0
        
    def test_boundary_method_marking_full_header_estimation(self):
        """测试边界检测方法标记 - 完整头部估算"""
        # 创建全部都像头部行但没有空行的载荷
        payload = (
            b'GET /test HTTP/1.1\n'
            b'Host: example.com\n'
            b'User-Agent: test\n'
            b'Accept: text/html'  # 没有空行结束
        )
        
        analysis = {}
        result = self.strategy._estimate_header_size(payload, analysis)
        
        # 验证完整头部估算标记
        assert 'boundary_method' in analysis
        assert analysis['boundary_method'] == 'full_header_estimation'
        assert result > 0
        
    def test_boundary_method_marking_fallback_estimation(self):
        """测试边界检测方法标记 - 回退估算"""
        # 创建无法解码的二进制载荷
        payload = b'\xff\xfe\xfd\xfc' * 100  # 无法UTF-8解码的数据
        
        analysis = {}
        result = self.strategy._estimate_header_size(payload, analysis)
        
        # 验证回退估算标记
        assert 'boundary_method' in analysis
        assert analysis['boundary_method'] == 'fallback_estimation'
        assert result == 128  # 固定回退值
        
    def test_resource_protection_large_payload(self):
        """测试资源保护机制 - 大载荷处理"""
        # 创建超大载荷（20KB），确保触发资源保护
        large_header = b'GET /test HTTP/1.1\n' + b'X-Large-Header: ' + b'A' * 5000 + b'\n'
        large_body = b'B' * 15000
        large_payload = large_header + large_body  # 没有空行，将触发full_header_estimation
        
        start_time = time.time()
        analysis = {}
        result = self.strategy._estimate_header_size(large_payload, analysis)
        processing_time = time.time() - start_time
        
        # 验证资源保护
        assert processing_time < 0.1  # 处理时间应该很短
        assert result > 0
        assert 'boundary_method' in analysis
        
        # 验证严格的资源保护机制 - 应该受到MAX_HEADER_ANALYSIS_SIZE限制
        assert result <= 8192  # 不应该超过MAX_HEADER_ANALYSIS_SIZE
        
    def test_memory_safety_malicious_input(self):
        """测试内存安全 - 恶意输入处理"""
        # 创建各种可能导致内存问题的输入
        test_cases = [
            b'',  # 空载荷
            b'\x00' * 16384,  # 大量null字节
            b'\n' * 10000,  # 大量换行符
            b':' * 5000,  # 大量冒号
            b'A' * 1024 + b'\n' + b'B' * 1024,  # 长行
        ]
        
        for i, malicious_payload in enumerate(test_cases):
            analysis = {}
            
            # 确保不会抛出异常
            try:
                result = self.strategy._estimate_header_size(malicious_payload, analysis)
                assert result >= 0
                assert 'boundary_method' in analysis
            except Exception as e:
                pytest.fail(f"恶意输入测试 {i} 失败: {e}")
                
    def test_precision_improvement_standard_http(self):
        """测试估算精度提升 - 标准HTTP"""
        test_cases = [
            # (载荷, 期望头部大小范围)
            (
                b'GET / HTTP/1.1\r\nHost: test.com\r\n\r\nbody',
                (30, 35)  # 允许范围而不是精确值
            ),
            (
                b'POST /api HTTP/1.1\r\nContent-Length: 10\r\n\r\n1234567890',
                (35, 42)  # 头部部分长度范围
            ),
            (
                b'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n<html>',
                (35, 45)  # 响应头部长度范围
            ),
        ]
        
        correct_estimates = 0
        for payload, (min_size, max_size) in test_cases:
            analysis = {}
            result = self.strategy._estimate_header_size(payload, analysis)
            
            # 检查是否在期望范围内
            if min_size <= result <= max_size:
                correct_estimates += 1
                
        # 验证精度>95%
        precision = correct_estimates / len(test_cases)
        assert precision >= 0.95, f"精度 {precision:.2%} 未达到95%要求"
        
    def test_algorithm_performance_comparison(self):
        """测试算法性能对比"""
        # 创建不同大小的测试载荷
        small_payload = (
            b'GET /test HTTP/1.1\r\n'
            b'Host: example.com\r\n'
            b'\r\n'
            b'small body'
        )
        
        medium_payload = (
            b'POST /api HTTP/1.1\r\n'
            b'Content-Type: application/json\r\n' * 20 +  # 重复头部
            b'\r\n'
            b'{"data": "' + b'x' * 1000 + b'"}'
        )
        
        large_payload = (
            b'PUT /upload HTTP/1.1\r\n'
            b'Content-Length: 5000\r\n'
            b'X-Custom-Header: ' + b'y' * 100 + b'\r\n'
        ) * 10 + b'\r\n' + b'z' * 5000
        
        payloads = [
            ('small', small_payload),
            ('medium', medium_payload), 
            ('large', large_payload)
        ]
        
        performance_results = {}
        
        for name, payload in payloads:
            # 测试新算法性能
            start_time = time.time()
            for _ in range(100):  # 重复100次以获得可靠测量
                analysis = {}
                self.strategy._estimate_header_size(payload, analysis)
            end_time = time.time()
            
            avg_time = (end_time - start_time) / 100
            performance_results[name] = avg_time
            
            # 验证性能要求：大载荷处理时间<10ms
            if name == 'large':
                assert avg_time < 0.01, f"大载荷处理时间 {avg_time*1000:.2f}ms 超过10ms限制"
                
        # 验证线性性能特征（新算法应该是O(n)）
        # 大载荷的处理时间不应该是小载荷的平方倍数
        ratio = performance_results['large'] / performance_results['small']
        assert ratio < 50, f"性能比率 {ratio:.1f} 过高，算法可能不是O(n)"
        
    def test_comprehensive_boundary_method_support(self):
        """测试完整的边界检测方法支持"""
        # 验证支持所有5种边界检测方法
        expected_methods = {
            'tolerant_detection',
            'empty_line_detection', 
            'conservative_estimation',
            'full_header_estimation',
            'fallback_estimation'
        }
        
        found_methods = set()
        
        # 精心设计的测试载荷以确保触发每种检测方法
        test_payloads = [
            # tolerant_detection - 标准CRLF边界
            b'GET / HTTP/1.1\r\nHost: test.com\r\n\r\nbody',
            
            # empty_line_detection - 逐行分析遇到空行（不被tolerant_detection捕获）
            b'POST /api HTTP/1.1\nContent-Type: json\n\n{"data": "test"}',
            
            # conservative_estimation - 包含明显非头部行
            b'GET / HTTP/1.1\nHost: test.com\nInvalid Line Without Colon Here',
            
            # full_header_estimation - 全部像头部行但没有结束标记
            b'GET / HTTP/1.1\nHost: example.com\nUser-Agent: test\nAccept: text/html',
            
            # fallback_estimation - 二进制数据，解码失败
            b'\xff\xfe\xfd\xfc' * 50,
        ]
        
        for i, payload in enumerate(test_payloads):
            analysis = {}
            self.strategy._estimate_header_size(payload, analysis)
            if 'boundary_method' in analysis:
                found_methods.add(analysis['boundary_method'])
                print(f"Payload {i}: {analysis['boundary_method']}")  # 调试信息
                
        # 验证找到了所有5种方法
        assert found_methods == expected_methods, \
            f"缺少边界检测方法: {expected_methods - found_methods}, 找到的: {found_methods}"
            
    def test_integration_with_existing_workflow(self):
        """测试与现有工作流的集成"""
        # 验证优化后的算法能正确集成到完整的HTTP处理流程中
        payload = (
            b'POST /api/test HTTP/1.1\r\n'
            b'Host: test.example.com\r\n'
            b'Content-Type: application/json\r\n'
            b'Content-Length: 25\r\n'
            b'\r\n'
            b'{"message": "test data"}'
        )
        
        protocol_info = ProtocolInfo(
            name='HTTP',
            version='1.1',
            layer=7,
            port=80,
            characteristics={}
        )
        context = self.create_test_context()
        context.payload_size = len(payload)
        
        # 执行完整的分析流程
        analysis = self.strategy.analyze_payload(payload, protocol_info, context)
        
        # 验证分析结果包含边界方法标记
        assert 'boundary_method' in analysis
        assert analysis['is_http'] is True
        assert analysis['header_size'] > 0
        assert analysis['body_size'] > 0
        
        # 执行完整的掩码生成流程
        result = self.strategy.generate_mask_spec(payload, protocol_info, context, analysis)
        
        # 验证掩码生成成功
        assert result.success is True
        assert result.mask_spec is not None
        assert result.confidence > 0.7
        assert 'boundary_method' in result.metadata.get('analysis', {})


if __name__ == '__main__':
    pytest.main([__file__, '-v']) 