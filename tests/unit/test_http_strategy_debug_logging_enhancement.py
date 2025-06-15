"""
HTTP策略调试日志增强测试 - 阶段4验证

验证HTTP策略的调试日志增强功能，包括：
1. 详细的分析过程日志
2. 边界检测方法识别
3. 性能监控信息
4. 前提条件和范围声明
5. 异常情况详细记录

作者: PktMask Team
创建时间: 2025-01-15 - 阶段4实施
版本: 1.0.0
"""

import unittest
import logging
import io
import time
from unittest.mock import patch, MagicMock

from src.pktmask.core.trim.strategies.http_strategy import HTTPTrimStrategy
from src.pktmask.core.trim.strategies.base_strategy import ProtocolInfo, TrimContext


class TestHTTPStrategyDebugLoggingEnhancement(unittest.TestCase):
    """HTTP策略调试日志增强测试类"""
    
    def setUp(self):
        """测试初始化"""
        self.config = {
            'preserve_headers': True,
            'confidence_threshold': 0.8,
            'body_preserve_bytes': 64
        }
        self.strategy = HTTPTrimStrategy(self.config)
        
        # 设置日志捕获
        self.log_stream = io.StringIO()
        self.log_handler = logging.StreamHandler(self.log_stream)
        self.log_handler.setLevel(logging.DEBUG)
        
        # 配置策略的logger
        self.strategy.logger.setLevel(logging.DEBUG)
        self.strategy.logger.addHandler(self.log_handler)
        
        # 测试数据 - 修复ProtocolInfo和TrimContext的参数
        self.protocol_info = ProtocolInfo(
            name='HTTP', 
            version='1.1', 
            layer=7, 
            port=80,
            characteristics={'text_protocol': True}
        )
        self.context = TrimContext(
            packet_index=42,
            stream_id='test_stream',
            flow_direction='client_to_server',
            protocol_stack=['ETH', 'IP', 'TCP', 'HTTP'],
            payload_size=1024,
            timestamp=1640995200.0,
            metadata={'test': True}
        )
        
    def tearDown(self):
        """测试清理"""
        self.strategy.logger.removeHandler(self.log_handler)
        self.log_handler.close()
        
    def get_log_output(self):
        """获取日志输出"""
        return self.log_stream.getvalue()
        
    def test_initialization_logging(self):
        """测试初始化时的前提条件和范围声明日志"""
        # 重新创建策略以捕获初始化日志
        log_stream = io.StringIO()
        log_handler = logging.StreamHandler(log_stream)
        log_handler.setLevel(logging.INFO)
        
        # 临时配置根logger
        root_logger = logging.getLogger('src.pktmask.core.trim.strategies.http_strategy')
        root_logger.setLevel(logging.INFO)
        root_logger.addHandler(log_handler)
        
        try:
            strategy = HTTPTrimStrategy(self.config)
            log_output = log_stream.getvalue()
            
            # 验证前提条件和范围声明日志
            self.assertIn("=== HTTP策略初始化 - 技术前提和处理范围 ===", log_output)
            self.assertIn("技术前提: 基于TShark预处理器完成TCP流重组和IP碎片重组", log_output)
            self.assertIn("协议支持: HTTP/1.0 和 HTTP/1.1 文本协议", log_output)
            self.assertIn("处理范围: Content-Length定长消息体", log_output)
            self.assertIn("多消息策略: 单消息处理", log_output)
            self.assertIn("HTTP策略配置完成", log_output)
            
        finally:
            root_logger.removeHandler(log_handler)
            log_handler.close()
    
    def test_can_handle_logging(self):
        """测试can_handle方法的详细日志"""
        self.strategy.can_handle(self.protocol_info, self.context)
        
        log_output = self.get_log_output()
        
        # 验证能力评估日志
        self.assertIn("包42: 评估HTTP处理能力", log_output)
        self.assertIn("协议=HTTP, 层=7, 端口=80", log_output)
        self.assertIn("HTTP端口80匹配", log_output)
        # 注意：当端口匹配时，方法会提前返回，不会输出"HTTP处理能力评估通过"
    
    def test_analyze_payload_detailed_logging(self):
        """测试analyze_payload方法的详细调试日志"""
        # 标准HTTP请求载荷
        http_request = b"""GET /api/test HTTP/1.1\r
Host: example.com\r
User-Agent: TestAgent\r
Content-Length: 13\r
\r
Hello, World!"""
        
        analysis = self.strategy.analyze_payload(http_request, self.protocol_info, self.context)
        
        log_output = self.get_log_output()
        
        # 验证分析入口日志
        self.assertIn("包42: === HTTP载荷分析开始 ===", log_output)
        self.assertIn(f"载荷大小={len(http_request)}字节", log_output)
        self.assertIn("验证技术前提", log_output)
        
        # 验证边界检测日志
        self.assertIn("包42: 开始HTTP边界检测", log_output)
        self.assertIn("检测到标准\\r\\n\\r\\n边界", log_output)
        self.assertIn("边界检测成功", log_output)
        
        # 验证头部解析日志
        self.assertIn("包42: 开始HTTP头部解析", log_output)
        self.assertIn("头部解析完成", log_output)
        self.assertIn("类型=请求", log_output)
        
        # 验证最终结果日志
        self.assertIn("包42: === HTTP载荷分析完成 ===", log_output)
        self.assertIn("最终结果", log_output)
        
        # 验证性能监控信息
        self.assertIn("total_processing_ms", str(analysis))
        self.assertIn("debug_info", str(analysis))
    
    def test_boundary_detection_logging(self):
        """测试边界检测方法的详细日志"""
        # Unix格式的HTTP响应
        http_response_unix = b"""HTTP/1.1 200 OK\nContent-Type: text/plain\nContent-Length: 5\n\nHello"""
        
        self.strategy.analyze_payload(http_response_unix, self.protocol_info, self.context)
        
        log_output = self.get_log_output()
        
        # 验证边界检测详细过程
        self.assertIn("边界检测: 开始多层次检测", log_output)
        self.assertIn("边界检测: 层次2成功 - Unix\\n\\n边界", log_output)
    
    def test_confidence_calculation_logging(self):
        """测试置信度计算的详细日志"""
        http_request = b"""GET /test HTTP/1.1\r
Host: example.com\r
\r
"""
        
        self.strategy.analyze_payload(http_request, self.protocol_info, self.context)
        
        log_output = self.get_log_output()
        
        # 验证置信度计算日志
        self.assertIn("置信度计算: 开始HTTP检测置信度计算", log_output)
        self.assertIn("识别为HTTP request", log_output)
        self.assertIn("检测到HTTP版本", log_output)
        self.assertIn("置信度计算: 完成", log_output)
        self.assertIn("置信度计算: 详细分解", log_output)
    
    def test_mask_spec_generation_logging(self):
        """测试掩码规范生成的详细日志"""
        http_request = b"""POST /api/data HTTP/1.1\r
Host: example.com\r
Content-Length: 26\r
\r
{"message": "test data"}"""
        
        # 先分析载荷
        analysis = self.strategy.analyze_payload(http_request, self.protocol_info, self.context)
        
        # 清除之前的日志
        self.log_stream.seek(0)
        self.log_stream.truncate(0)
        
        # 生成掩码规范
        result = self.strategy.generate_mask_spec(http_request, self.protocol_info, self.context, analysis)
        
        log_output = self.get_log_output()
        
        # 验证掩码生成日志
        self.assertIn("包42: === HTTP掩码规范生成开始 ===", log_output)
        self.assertIn("开始创建HTTP掩码规范", log_output)
        self.assertIn("掩码创建: 载荷结构", log_output)
        self.assertIn("掩码规范创建完成", log_output)
        self.assertIn("包42: === HTTP掩码规范生成完成 ===", log_output)
        
        # 验证性能监控信息
        self.assertTrue(result.success)
        self.assertIn('processing_time_ms', result.metadata)
        self.assertIn('performance_breakdown', result.metadata)
    
    def test_mask_creation_detailed_logging(self):
        """测试掩码创建的详细日志"""
        http_request = b"""GET /api/test HTTP/1.1\r
Host: example.com\r
\r
"""
        
        analysis = self.strategy.analyze_payload(http_request, self.protocol_info, self.context)
        
        # 清除之前的日志
        self.log_stream.seek(0)
        self.log_stream.truncate(0)
        
        # 直接调用掩码创建方法
        mask_spec = self.strategy._create_http_mask_spec(http_request.encode() if isinstance(http_request, str) else http_request, analysis)
        
        log_output = self.get_log_output()
        
        # 验证掩码创建详细日志
        self.assertIn("掩码创建: 开始HTTP掩码规范创建", log_output)
        self.assertIn("掩码创建: 载荷结构", log_output)
    
    def test_performance_monitoring(self):
        """测试性能监控功能"""
        # 创建一个较大的载荷来测试性能监控
        large_payload = b"""GET /large-test HTTP/1.1\r
Host: example.com\r
Content-Length: 1000\r
\r
""" + b"X" * 1000
        
        analysis = self.strategy.analyze_payload(large_payload, self.protocol_info, self.context)
        
        # 验证性能监控数据
        self.assertIn('processing_time_ms', analysis)
        self.assertIn('debug_info', analysis)
        self.assertIn('boundary_detection_ms', analysis['debug_info'])
        self.assertIn('header_parsing_ms', analysis['debug_info'])
        self.assertIn('total_processing_ms', analysis['debug_info'])
        
        # 性能时间应该是合理的（不为0，不过大）
        total_time = analysis['processing_time_ms']
        self.assertGreater(total_time, 0)
        self.assertLess(total_time, 1000)  # 不应超过1秒
    
    def test_exception_handling_logging(self):
        """测试异常处理的详细日志"""
        # 创建一个会导致异常的场景
        with patch.object(self.strategy, '_find_header_boundary_tolerant', side_effect=Exception("测试异常")):
            analysis = self.strategy.analyze_payload(b"invalid data", self.protocol_info, self.context)
            
            log_output = self.get_log_output()
            
            # 验证异常日志
            self.assertIn("包42: HTTP载荷分析失败", log_output)
            self.assertIn("异常=Exception: 测试异常", log_output)
            self.assertIn("异常详情", log_output)
            
            # 验证分析结果包含警告
            self.assertIn("分析异常: 测试异常", analysis['warnings'])
    
    def test_confidence_threshold_failure_logging(self):
        """测试置信度阈值失败的详细日志"""
        # 创建低置信度的分析结果
        low_confidence_analysis = {
            'is_http': False,
            'confidence': 0.5,  # 低于默认阈值0.8
            'warnings': []
        }
        
        result = self.strategy.generate_mask_spec(b"test data", self.protocol_info, self.context, low_confidence_analysis)
        
        log_output = self.get_log_output()
        
        # 验证失败原因日志
        self.assertIn("HTTP验证失败", log_output)
        self.assertIn("置信度0.500 < 阈值0.800", log_output)
        
        # 验证结果
        self.assertFalse(result.success)
        self.assertIn("不是有效的HTTP载荷", result.reason)
    
    def test_empty_payload_logging(self):
        """测试空载荷的日志处理"""
        analysis = self.strategy.analyze_payload(b"", self.protocol_info, self.context)
        
        log_output = self.get_log_output()
        
        # 验证空载荷日志
        self.assertIn("包42: 空载荷，跳过分析", log_output)
        
        # 验证处理时间仍然被记录
        self.assertIn('processing_time_ms', analysis)
    
    def test_boundary_detection_failure_logging(self):
        """测试边界检测失败的日志"""
        # 创建没有明确边界的载荷
        no_boundary_payload = b"""GET /test HTTP/1.1
Host: example.com
Content-Type: text/plain"""  # 没有\r\n\r\n或\n\n边界
        
        analysis = self.strategy.analyze_payload(no_boundary_payload, self.protocol_info, self.context)
        
        log_output = self.get_log_output()
        
        # 验证边界检测失败日志
        self.assertIn("未找到明确边界，启用回退估算", log_output)
        self.assertIn("边界检测: 所有层次都失败", log_output) 