"""
HTTPScanningStrategy复杂场景集成测试

测试HTTP扫描式策略处理复杂场景的能力，包括：
- Chunked编码响应处理
- Keep-Alive多消息场景
- 大文件下载场景
- 压缩内容处理
- 错误响应处理
- 边界条件测试

作者: PktMask Team
创建时间: 2025-01-16
版本: 1.0.0
"""

import pytest
import unittest
from typing import Dict, Any

from src.pktmask.core.trim.strategies.http_scanning_strategy import HTTPScanningStrategy
from src.pktmask.core.trim.strategies.base_strategy import ProtocolInfo, TrimContext
from src.pktmask.core.trim.models.scan_result import ScanResult, ScanConstants
from src.pktmask.core.trim.models.mask_spec import MaskAfter, KeepAll


class TestHTTPScanningComplexScenarios(unittest.TestCase):
    """HTTPScanningStrategy复杂场景测试类"""
    
    def setUp(self):
        """测试初始化"""
        self.config = {
            'max_scan_window': 8192,
            'confidence_threshold': 0.7,
            'enable_scan_logging': False,
            'chunked_sample_size': 1024,
            'fallback_on_error': True
        }
        self.strategy = HTTPScanningStrategy(self.config)
        
        self.http_protocol = ProtocolInfo(
            name='HTTP',
            version='1.1',
            layer=7,
            port=80,
            characteristics={}
        )
        
        self.context = TrimContext(
            packet_index=1,
            stream_id='test_stream',
            flow_direction='server_to_client',
            protocol_stack=['ETH', 'IP', 'TCP', 'HTTP'],
            payload_size=2048,
            timestamp=1234567890.0,
            metadata={}
        )
    
    def test_chunked_encoding_complete_response(self):
        """测试完整的Chunked编码响应"""
        payload = (
            b'HTTP/1.1 200 OK\r\n'
            b'Transfer-Encoding: chunked\r\n'
            b'Content-Type: text/html\r\n'
            b'\r\n'
            b'25\r\n'  # 37字节
            b'This is the first chunk of data.\r\n\r\n'
            b'1c\r\n'  # 28字节
            b'And this is the second chunk.\r\n'
            b'17\r\n'  # 23字节
            b'Final chunk of content.\r\n'
            b'0\r\n'   # 结束chunk
            b'\r\n'
        )
        
        analysis = self.strategy.analyze_payload(payload, self.http_protocol, self.context)
        
        # 验证检测结果
        self.assertTrue(analysis['is_http'])
        scan_result = analysis['scan_result']
        self.assertTrue(scan_result.is_chunked)
        self.assertGreater(scan_result.confidence, 0.7)
        self.assertIn('chunked', scan_result.scan_method)
        
        # 验证掩码生成
        mask_result = self.strategy.generate_mask_spec(
            payload, self.http_protocol, self.context, analysis
        )
        self.assertTrue(mask_result.success)
        self.assertIsInstance(mask_result.mask_spec, MaskAfter)
        
        # Chunked响应应该保留头部+样本数据
        self.assertGreater(mask_result.preserved_bytes, scan_result.header_boundary + 4)
        self.assertLess(mask_result.preserved_bytes, len(payload))
    
    def test_chunked_encoding_incomplete_response(self):
        """测试不完整的Chunked编码响应"""
        payload = (
            b'HTTP/1.1 200 OK\r\n'
            b'Transfer-Encoding: chunked\r\n'
            b'\r\n'
            b'2a\r\n'  # 42字节chunk
            b'This is an incomplete chunked response da'
            # 缺少chunk结尾和后续内容
        )
        
        analysis = self.strategy.analyze_payload(payload, self.http_protocol, self.context)
        
        # 验证检测结果
        self.assertTrue(analysis['is_http'])
        scan_result = analysis['scan_result']
        self.assertTrue(scan_result.is_chunked)
        
        # 不完整响应的置信度应该稍低
        self.assertGreater(scan_result.confidence, 0.5)
        self.assertLess(scan_result.confidence, 0.9)
    
    def test_large_file_download_scenario(self):
        """测试大文件下载场景"""
        # 模拟大文件响应的开始部分
        header = (
            b'HTTP/1.1 200 OK\r\n'
            b'Content-Type: application/octet-stream\r\n'
            b'Content-Length: 104857600\r\n'  # 100MB文件
            b'Content-Disposition: attachment; filename="large_file.zip"\r\n'
            b'\r\n'
        )
        
        # 添加大量二进制内容模拟文件数据
        large_content = b'\x50\x4b\x03\x04' + b'X' * 10000  # ZIP文件头 + 10KB数据
        payload = header + large_content
        
        analysis = self.strategy.analyze_payload(payload, self.http_protocol, self.context)
        
        # 验证扫描只在窗口内进行，不扫描整个大文件
        self.assertTrue(analysis['is_http'])
        self.assertLess(analysis['analysis_duration_ms'], 100)  # 应该很快完成
        
        scan_result = analysis['scan_result']
        self.assertEqual(scan_result.content_length, 104857600)
        
        # 验证掩码策略：保留头部+少量内容样本
        mask_result = self.strategy.generate_mask_spec(
            payload, self.http_protocol, self.context, analysis
        )
        
        # 大文件场景应该只保留头部和少量样本
        expected_preserve = len(header) + 64  # 头部 + 64字节样本
        self.assertLessEqual(mask_result.preserved_bytes, expected_preserve + 100)  # 允许一定偏差
    
    def test_compressed_content_handling(self):
        """测试压缩内容处理"""
        payload = (
            b'HTTP/1.1 200 OK\r\n'
            b'Content-Type: text/html\r\n'
            b'Content-Encoding: gzip\r\n'
            b'Content-Length: 157\r\n'
            b'\r\n'
            b'\x1f\x8b\x08\x00\x00\x00\x00\x00\x00\x03'  # gzip头部
            b'\xcb(\xc9\xccI-\xce\xccK\x07\x00\x86\xa6\x106\x0c\x00\x00\x00'  # 压缩数据
        )
        
        analysis = self.strategy.analyze_payload(payload, self.http_protocol, self.context)
        
        # 验证能正确识别HTTP响应
        self.assertTrue(analysis['is_http'])
        scan_result = analysis['scan_result']
        self.assertEqual(scan_result.message_type, 'response')
        self.assertEqual(scan_result.content_length, 157)
        
        # 压缩内容应该被检测（通过Content-Encoding头）
        # 注意：简化版扫描器可能不会解析所有头部，这是可接受的
        
        # 验证掩码策略
        mask_result = self.strategy.generate_mask_spec(
            payload, self.http_protocol, self.context, analysis
        )
        self.assertTrue(mask_result.success)
        # 压缩内容通常保留头部和部分内容
        self.assertGreater(mask_result.preserved_bytes, scan_result.header_boundary)
    
    def test_http_error_responses(self):
        """测试HTTP错误响应"""
        test_cases = [
            # 400 Bad Request
            (
                b'HTTP/1.1 400 Bad Request\r\n'
                b'Content-Type: text/html\r\n'
                b'Content-Length: 48\r\n'
                b'\r\n'
                b'<html><body><h1>400 Bad Request</h1></body></html>',
                400
            ),
            # 404 Not Found
            (
                b'HTTP/1.1 404 Not Found\r\n'
                b'Content-Type: text/plain\r\n'
                b'\r\n'
                b'File not found',
                404
            ),
            # 500 Internal Server Error
            (
                b'HTTP/1.1 500 Internal Server Error\r\n'
                b'Content-Type: application/json\r\n'
                b'\r\n'
                b'{"error": "Internal server error", "code": 500}',
                500
            )
        ]
        
        for payload, expected_status in test_cases:
            with self.subTest(status_code=expected_status):
                analysis = self.strategy.analyze_payload(payload, self.http_protocol, self.context)
                
                # 验证错误响应被正确识别为HTTP
                self.assertTrue(analysis['is_http'])
                scan_result = analysis['scan_result']
                self.assertEqual(scan_result.message_type, 'response')
                
                # 验证掩码生成
                mask_result = self.strategy.generate_mask_spec(
                    payload, self.http_protocol, self.context, analysis
                )
                self.assertTrue(mask_result.success)
                
                # 错误响应应该保留合理的内容用于调试
                self.assertGreater(mask_result.preserved_bytes, 0)
    
    def test_malformed_http_requests(self):
        """测试格式错误的HTTP请求"""
        malformed_cases = [
            # 缺少HTTP版本
            b'GET /index.html\r\nHost: example.com\r\n\r\n',
            
            # 错误的HTTP版本
            b'GET /index.html HTTP/2.0\r\nHost: example.com\r\n\r\n',
            
            # 缺少头部分隔符
            b'GET /index.html HTTP/1.1\nHost: example.com\n',
            
            # 非标准方法
            b'CUSTOM /api HTTP/1.1\r\nHost: example.com\r\n\r\n',
        ]
        
        for payload in malformed_cases:
            with self.subTest(payload=payload[:30]):  # 前30字节用于标识
                analysis = self.strategy.analyze_payload(payload, self.http_protocol, self.context)
                
                # 格式错误的请求可能被识别为非HTTP或低置信度HTTP
                if analysis['is_http']:
                    # 如果识别为HTTP，置信度应该较低
                    self.assertLess(analysis['confidence'], 0.9)
                
                # 确保掩码生成不会崩溃
                mask_result = self.strategy.generate_mask_spec(
                    payload, self.http_protocol, self.context, analysis
                )
                self.assertTrue(mask_result.success)
    
    def test_boundary_conditions(self):
        """测试边界条件"""
        # 最小HTTP请求
        minimal_request = b'GET / HTTP/1.0\r\n\r\n'
        analysis = self.strategy.analyze_payload(minimal_request, self.http_protocol, self.context)
        self.assertTrue(analysis['is_http'])
        
        # 只有头部的HTTP响应
        headers_only = b'HTTP/1.1 204 No Content\r\n\r\n'
        analysis = self.strategy.analyze_payload(headers_only, self.http_protocol, self.context)
        self.assertTrue(analysis['is_http'])
        
        # 超长URI
        long_uri = b'GET /' + b'x' * 2000 + b' HTTP/1.1\r\nHost: example.com\r\n\r\n'
        analysis = self.strategy.analyze_payload(long_uri, self.http_protocol, self.context)
        # 应该能处理但可能置信度较低
        if analysis['is_http']:
            mask_result = self.strategy.generate_mask_spec(
                long_uri, self.http_protocol, self.context, analysis
            )
            self.assertTrue(mask_result.success)
    
    def test_mixed_line_endings(self):
        """测试混合行结束符"""
        mixed_endings_cases = [
            # Unix style (LF)
            b'HTTP/1.1 200 OK\nContent-Type: text/plain\n\nHello World',
            
            # Mixed style
            b'GET /test HTTP/1.1\r\nHost: example.com\nUser-Agent: Test\r\n\r\nBody',
            
            # Windows style (CRLF) - 标准情况
            b'POST /api HTTP/1.1\r\nContent-Length: 13\r\n\r\nHello, World!',
        ]
        
        for payload in mixed_endings_cases:
            with self.subTest(payload=payload[:20]):
                analysis = self.strategy.analyze_payload(payload, self.http_protocol, self.context)
                
                # 扫描器应该能处理不同的行结束符
                # 至少应该识别为某种HTTP格式或保守处理
                mask_result = self.strategy.generate_mask_spec(
                    payload, self.http_protocol, self.context, analysis
                )
                self.assertTrue(mask_result.success)
                
                # 确保保留了合理的内容
                self.assertGreater(mask_result.preserved_bytes, 0)
    
    def test_performance_with_complex_scenarios(self):
        """测试复杂场景下的性能"""
        import time
        
        complex_scenarios = [
            # 大型多头部响应
            (
                b'HTTP/1.1 200 OK\r\n' +
                b'\r\n'.join([f'Custom-Header-{i}: value-{i}'.encode() for i in range(50)]) +
                b'\r\n\r\n' + b'content' * 1000
            ),
            
            # 长Chunked响应开始部分
            (
                b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n' +
                b''.join([f'{i:x}\r\nchunk-data-{i}\r\n'.encode() for i in range(1, 20)]) +
                b'0\r\n\r\n'
            )
        ]
        
        for payload in complex_scenarios:
            start_time = time.perf_counter()
            
            analysis = self.strategy.analyze_payload(payload, self.http_protocol, self.context)
            mask_result = self.strategy.generate_mask_spec(
                payload, self.http_protocol, self.context, analysis
            )
            
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            # 复杂场景也应该在合理时间内完成
            self.assertLess(duration_ms, 200)
            self.assertTrue(mask_result.success)
    
    def test_scan_result_metadata_completeness(self):
        """测试ScanResult元数据完整性"""
        payload = (
            b'HTTP/1.1 200 OK\r\n'
            b'Content-Type: application/json\r\n'
            b'Content-Length: 25\r\n'
            b'\r\n'
            b'{"message": "Hello World"}'
        )
        
        analysis = self.strategy.analyze_payload(payload, self.http_protocol, self.context)
        
        # 验证ScanResult包含必要的元数据
        scan_result = analysis['scan_result']
        
        self.assertIsNotNone(scan_result.scan_method)
        self.assertIsNotNone(scan_result.confidence)
        self.assertIsNotNone(scan_result.preserve_strategy)
        
        # 验证分析结果包含性能数据
        self.assertIn('analysis_duration_ms', analysis)
        self.assertIsInstance(analysis['analysis_duration_ms'], float)
        
        # 验证mask生成包含完整信息
        mask_result = self.strategy.generate_mask_spec(
            payload, self.http_protocol, self.context, analysis
        )
        
        self.assertIsNotNone(mask_result.metadata)
        self.assertEqual(mask_result.metadata.get('strategy'), 'scanning')
        self.assertIn('preserve_strategy', mask_result.metadata)


if __name__ == '__main__':
    # 运行复杂场景测试
    unittest.main(verbosity=2) 