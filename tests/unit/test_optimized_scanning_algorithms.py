"""
HTTP载荷扫描算法优化测试套件

测试阶段3实施的核心算法：
- 边界检测算法测试
- Content-Length解析测试
- Chunked编码处理测试
- 多消息边界检测测试
- 性能基准测试

作者: PktMask Team
版本: 1.0.0
创建时间: 2025-01-16
"""

import unittest
import time
from typing import List

try:
    from src.pktmask.core.trim.algorithms.boundary_detection import (
        BoundaryDetector,
        BoundaryDetectionResult,
        HeaderBoundaryPattern,
        MessageBoundaryInfo,
        detect_header_boundary,
        detect_multiple_message_boundaries
    )
    from src.pktmask.core.trim.algorithms.content_length_parser import (
        ContentLengthParser,
        ContentLengthResult,
        ChunkedEncoder,
        ChunkedAnalysisResult,
        ChunkInfo,
        parse_content_length,
        analyze_chunked_structure
    )
    ALGORITHMS_AVAILABLE = True
except ImportError as e:
    ALGORITHMS_AVAILABLE = False
    print(f"算法模块导入失败: {e}")


class TestBoundaryDetectionAlgorithms(unittest.TestCase):
    """边界检测算法测试"""
    
    def setUp(self):
        """测试准备"""
        if not ALGORITHMS_AVAILABLE:
            self.skipTest("算法模块不可用")
        
        self.detector = BoundaryDetector(enable_logging=False)
    
    def test_standard_boundary_detection(self):
        """测试标准HTTP边界检测"""
        payload = (
            b'GET /index.html HTTP/1.1\r\n'
            b'Host: example.com\r\n'
            b'User-Agent: TestAgent/1.0\r\n'
            b'\r\n'
            b'<html><body>Test</body></html>'
        )
        
        result = self.detector.detect_header_boundary(payload)
        
        self.assertTrue(result.found)
        self.assertEqual(result.pattern, HeaderBoundaryPattern.CRLF_CRLF)
        self.assertGreater(result.confidence, 0.8)
        self.assertEqual(result.body_start_position, payload.find(b'\r\n\r\n') + 4)
    
    def test_unix_format_boundary_detection(self):
        """测试Unix格式边界检测"""
        payload = (
            b'HTTP/1.1 200 OK\n'
            b'Content-Type: text/html\n'
            b'Content-Length: 27\n'
            b'\n'
            b'<html><body>Test</body></html>'
        )
        
        result = self.detector.detect_header_boundary(payload)
        
        self.assertTrue(result.found)
        self.assertEqual(result.pattern, HeaderBoundaryPattern.LF_LF)
        self.assertGreater(result.confidence, 0.7)
    
    def test_mixed_format_boundary_detection(self):
        """测试混合格式边界检测"""
        payload = (
            b'HTTP/1.1 200 OK\r\n'
            b'Content-Type: text/html\r\n'
            b'Content-Length: 27\r\n'
            b'\n'  # 混合格式：\r\n\n
            b'<html><body>Test</body></html>'
        )
        
        result = self.detector.detect_header_boundary(payload)
        
        self.assertTrue(result.found)
        self.assertEqual(result.pattern, HeaderBoundaryPattern.CRLF_LF)
        self.assertGreater(result.confidence, 0.6)
    
    def test_no_boundary_found(self):
        """测试无边界情况"""
        payload = b'GET /incomplete HTTP/1.1\r\nHost: example.com\r\n'
        
        result = self.detector.detect_header_boundary(payload)
        
        self.assertFalse(result.found)
        self.assertEqual(result.position, -1)
        self.assertEqual(result.confidence, 0.0)
    
    def test_heuristic_boundary_detection(self):
        """测试启发式边界检测"""
        # 构造稍微不规范但可识别的边界
        payload = (
            b'HTTP/1.1 200 OK\r\n'
            b'Content-Type: text/html\r\n'
            b'\r\n'  # 标准边界
            b'some content'
        )
        
        result = self.detector.detect_header_boundary(payload)
        
        self.assertTrue(result.found)
        self.assertEqual(result.pattern, HeaderBoundaryPattern.CRLF_CRLF)
    
    def test_multiple_message_detection(self):
        """测试多消息边界检测"""
        payload = (
            b'HTTP/1.1 200 OK\r\n'
            b'Content-Length: 27\r\n'
            b'\r\n'
            b'<html><body>Test</body></html>'
            b'HTTP/1.1 200 OK\r\n'
            b'Content-Length: 20\r\n'
            b'\r\n'
            b'Second response body'
        )
        
        messages = self.detector.detect_multiple_message_boundaries(payload)
        
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0].message_type, "response")
        self.assertEqual(messages[1].message_type, "response")
        self.assertTrue(all(msg.header_boundary.found for msg in messages))
    
    def test_performance_boundary_detection(self):
        """测试边界检测性能"""
        # 构造大载荷
        large_payload = (
            b'GET /large HTTP/1.1\r\n'
            b'Host: example.com\r\n'
            b'User-Agent: ' + b'x' * 1000 + b'\r\n'
            b'\r\n'
            b'x' * 10000
        )
        
        start_time = time.perf_counter()
        result = self.detector.detect_header_boundary(large_payload)
        duration = time.perf_counter() - start_time
        
        self.assertTrue(result.found)
        self.assertLess(duration, 0.01)  # 应该在10ms内完成


class TestContentLengthParser(unittest.TestCase):
    """Content-Length解析测试"""
    
    def setUp(self):
        """测试准备"""
        if not ALGORITHMS_AVAILABLE:
            self.skipTest("算法模块不可用")
        
        self.parser = ContentLengthParser(enable_logging=False)
    
    def test_standard_content_length_parsing(self):
        """测试标准Content-Length解析"""
        header = (
            b'HTTP/1.1 200 OK\r\n'
            b'Content-Type: text/html\r\n'
            b'Content-Length: 1234\r\n'
            b'\r\n'
        )
        
        result = self.parser.parse_content_length(header)
        
        self.assertTrue(result.found)
        self.assertEqual(result.length, 1234)
        self.assertGreater(result.confidence, 0.8)
        self.assertIn("Content-Length: 1234", result.header_line)
    
    def test_case_insensitive_content_length(self):
        """测试大小写不敏感的Content-Length解析"""
        header = (
            b'HTTP/1.1 200 OK\r\n'
            b'content-length: 567\r\n'
            b'Content-Type: text/html\r\n'
            b'\r\n'
        )
        
        result = self.parser.parse_content_length(header)
        
        self.assertTrue(result.found)
        self.assertEqual(result.length, 567)
    
    def test_content_length_with_extra_whitespace(self):
        """测试有额外空白的Content-Length解析"""
        header = (
            b'HTTP/1.1 200 OK\r\n'
            b'Content-Length:   890   \r\n'
            b'\r\n'
        )
        
        result = self.parser.parse_content_length(header)
        
        self.assertTrue(result.found)
        self.assertEqual(result.length, 890)
    
    def test_no_content_length_found(self):
        """测试无Content-Length情况"""
        header = (
            b'HTTP/1.1 200 OK\r\n'
            b'Content-Type: text/html\r\n'
            b'Transfer-Encoding: chunked\r\n'
            b'\r\n'
        )
        
        result = self.parser.parse_content_length(header)
        
        self.assertFalse(result.found)
        self.assertIsNone(result.length)
    
    def test_invalid_content_length(self):
        """测试无效的Content-Length值"""
        header = (
            b'HTTP/1.1 200 OK\r\n'
            b'Content-Length: invalid\r\n'
            b'\r\n'
        )
        
        result = self.parser.parse_content_length(header)
        
        self.assertFalse(result.found)
    
    def test_transfer_encoding_detection(self):
        """测试Transfer-Encoding检测"""
        header = (
            b'HTTP/1.1 200 OK\r\n'
            b'Transfer-Encoding: chunked\r\n'
            b'\r\n'
        )
        
        found, encodings = self.parser.detect_transfer_encoding(header)
        
        self.assertTrue(found)
        self.assertIn('chunked', [enc.value for enc in encodings])


class TestChunkedEncodingProcessor(unittest.TestCase):
    """Chunked编码处理测试"""
    
    def setUp(self):
        """测试准备"""
        if not ALGORITHMS_AVAILABLE:
            self.skipTest("算法模块不可用")
        
        self.encoder = ChunkedEncoder(enable_logging=False)
    
    def test_complete_chunked_analysis(self):
        """测试完整的Chunked编码分析"""
        payload = (
            b'HTTP/1.1 200 OK\r\n'
            b'Transfer-Encoding: chunked\r\n'
            b'\r\n'
            b'1a\r\n'
            b'abcdefghijklmnopqrstuvwxyz\r\n'
            b'10\r\n'
            b'1234567890abcdef\r\n'
            b'0\r\n'
            b'\r\n'
        )
        
        chunk_start = payload.find(b'\r\n\r\n') + 4
        result = self.encoder.analyze_chunked_structure(payload, chunk_start)
        
        self.assertTrue(result.is_chunked)
        self.assertTrue(result.is_complete)
        self.assertEqual(len(result.chunks), 3)  # 包括结束chunk
        self.assertEqual(result.chunks[0].size, 26)  # 0x1a = 26
        self.assertEqual(result.chunks[1].size, 16)  # 0x10 = 16
        self.assertEqual(result.chunks[2].size, 0)   # 结束chunk
        self.assertGreater(result.confidence, 0.8)
    
    def test_incomplete_chunked_analysis(self):
        """测试不完整的Chunked编码分析"""
        payload = (
            b'HTTP/1.1 200 OK\r\n'
            b'Transfer-Encoding: chunked\r\n'
            b'\r\n'
            b'1a\r\n'
            b'abcdefghijklmnopqrstuvwxyz\r\n'
            b'10\r\n'
            b'1234567890abc'  # 不完整的chunk
        )
        
        chunk_start = payload.find(b'\r\n\r\n') + 4
        result = self.encoder.analyze_chunked_structure(payload, chunk_start)
        
        self.assertTrue(result.is_chunked)
        self.assertFalse(result.is_complete)
        self.assertEqual(len(result.chunks), 1)  # 只有第一个完整的chunk
        self.assertLess(result.confidence, 0.8)  # 不完整降低置信度
    
    def test_chunked_with_extensions(self):
        """测试带扩展的Chunked编码"""
        payload = (
            b'HTTP/1.1 200 OK\r\n'
            b'Transfer-Encoding: chunked\r\n'
            b'\r\n'
            b'1a;some-extension=value\r\n'
            b'abcdefghijklmnopqrstuvwxyz\r\n'
            b'0\r\n'
            b'\r\n'
        )
        
        chunk_start = payload.find(b'\r\n\r\n') + 4
        result = self.encoder.analyze_chunked_structure(payload, chunk_start)
        
        self.assertTrue(result.is_chunked)
        self.assertTrue(result.is_complete)
        self.assertTrue(result.chunks[0].has_extensions)
        self.assertIn("some-extension=value", result.chunks[0].extensions)
    
    def test_malformed_chunked_recovery(self):
        """测试格式错误的Chunked编码恢复"""
        payload = (
            b'HTTP/1.1 200 OK\r\n'
            b'Transfer-Encoding: chunked\r\n'
            b'\r\n'
            b'invalid\r\n'  # 无效的chunk大小
            b'some data\r\n'
            b'5\r\n'
            b'hello\r\n'
            b'0\r\n'
            b'\r\n'
        )
        
        chunk_start = payload.find(b'\r\n\r\n') + 4
        result = self.encoder.analyze_chunked_structure(payload, chunk_start)
        
        self.assertTrue(result.is_chunked)
        self.assertGreater(result.parsing_errors, 0)
        self.assertLess(result.confidence, 0.7)  # 有错误降低置信度
    
    def test_chunked_performance(self):
        """测试Chunked编码处理性能"""
        # 构造大量chunk的载荷
        chunks_data = []
        for i in range(20):
            chunk_size = 100
            chunks_data.append(f'{chunk_size:x}\r\n'.encode())
            chunks_data.append(b'x' * chunk_size + b'\r\n')
        chunks_data.append(b'0\r\n\r\n')
        
        payload = (
            b'HTTP/1.1 200 OK\r\n'
            b'Transfer-Encoding: chunked\r\n'
            b'\r\n'
        ) + b''.join(chunks_data)
        
        chunk_start = payload.find(b'\r\n\r\n') + 4
        
        start_time = time.perf_counter()
        result = self.encoder.analyze_chunked_structure(payload, chunk_start)
        duration = time.perf_counter() - start_time
        
        self.assertTrue(result.is_chunked)
        self.assertTrue(result.is_complete)
        self.assertEqual(len(result.chunks), 21)  # 20个数据chunk + 1个结束chunk
        self.assertLess(duration, 0.05)  # 应该在50ms内完成


class TestIntegratedScanningAlgorithms(unittest.TestCase):
    """集成扫描算法测试"""
    
    def setUp(self):
        """测试准备"""
        if not ALGORITHMS_AVAILABLE:
            self.skipTest("算法模块不可用")
    
    def test_http_request_complete_analysis(self):
        """测试HTTP请求完整分析"""
        payload = (
            b'POST /api/data HTTP/1.1\r\n'
            b'Host: api.example.com\r\n'
            b'Content-Type: application/json\r\n'
            b'Content-Length: 45\r\n'
            b'\r\n'
            b'{"name": "test", "value": "Hello, World!"}'
        )
        
        # 边界检测
        boundary_result = detect_header_boundary(payload)
        self.assertTrue(boundary_result.found)
        
        # Content-Length解析
        header_content = payload[:boundary_result.position + 4]
        content_result = parse_content_length(header_content)
        self.assertTrue(content_result.found)
        self.assertEqual(content_result.length, 45)
        
        # 验证消息完整性
        expected_total_length = boundary_result.body_start_position + content_result.length
        self.assertEqual(len(payload), expected_total_length)
    
    def test_http_response_chunked_analysis(self):
        """测试HTTP响应Chunked编码分析"""
        payload = (
            b'HTTP/1.1 200 OK\r\n'
            b'Content-Type: text/html\r\n'
            b'Transfer-Encoding: chunked\r\n'
            b'\r\n'
            b'25\r\n'
            b'This is the data in the first chunk\r\n'
            b'1C\r\n'
            b'and this is the second one\r\n'
            b'3\r\n'
            b'con\r\n'
            b'8\r\n'
            b'sequence\r\n'
            b'0\r\n'
            b'\r\n'
        )
        
        # 边界检测
        boundary_result = detect_header_boundary(payload)
        self.assertTrue(boundary_result.found)
        
        # Chunked分析
        chunked_result = analyze_chunked_structure(payload, boundary_result.body_start_position)
        self.assertTrue(chunked_result.is_chunked)
        self.assertTrue(chunked_result.is_complete)
        self.assertEqual(len(chunked_result.chunks), 5)  # 4个数据chunk + 1个结束chunk
    
    def test_error_handling_and_recovery(self):
        """测试错误处理和恢复能力"""
        # 构造有问题的HTTP数据
        malformed_payload = b'INVALID HTTP DATA\x00\x01\x02\x03'
        
        # 边界检测应该优雅失败
        boundary_result = detect_header_boundary(malformed_payload)
        self.assertFalse(boundary_result.found)
        
        # Content-Length解析应该优雅失败
        content_result = parse_content_length(malformed_payload)
        self.assertFalse(content_result.found)
        
        # Chunked分析应该优雅失败
        chunked_result = analyze_chunked_structure(malformed_payload, 0)
        self.assertFalse(chunked_result.is_chunked)
    
    def test_performance_benchmark(self):
        """性能基准测试"""
        # 构造各种类型的测试载荷
        test_payloads = [
            # 简单HTTP请求
            b'GET /test HTTP/1.1\r\nHost: example.com\r\n\r\n',
            
            # 带Content-Length的POST请求
            b'POST /api HTTP/1.1\r\nContent-Length: 100\r\n\r\n' + b'x' * 100,
            
            # Chunked响应
            b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n' +
            b'64\r\n' + b'x' * 100 + b'\r\n0\r\n\r\n',
        ]
        
        total_time = 0
        iterations = 100
        
        for _ in range(iterations):
            for payload in test_payloads:
                start_time = time.perf_counter()
                
                # 运行完整的分析流程
                boundary_result = detect_header_boundary(payload)
                if boundary_result.found:
                    header_content = payload[:boundary_result.position + 4]
                    parse_content_length(header_content)
                    analyze_chunked_structure(payload, boundary_result.body_start_position)
                
                total_time += time.perf_counter() - start_time
        
        avg_time_per_analysis = total_time / (iterations * len(test_payloads))
        
        # 平均每次分析应该在1ms内完成
        self.assertLess(avg_time_per_analysis, 0.001)
        
        print(f"\n性能基准测试结果:")
        print(f"总测试次数: {iterations * len(test_payloads)}")
        print(f"总耗时: {total_time:.4f}秒")
        print(f"平均每次分析耗时: {avg_time_per_analysis*1000:.2f}ms")


if __name__ == '__main__':
    # 运行测试
    unittest.main(verbosity=2) 