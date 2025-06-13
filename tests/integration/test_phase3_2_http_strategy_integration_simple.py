#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Phase 3.2 HTTP策略集成测试 (简化版)

验证HTTP策略与现有PktMask系统的集成效果，包括：
- HTTP策略注册和发现
- HTTP策略与配置系统的集成
- HTTP载荷分析和掩码生成
- 基础性能验证

作者: PktMask Team  
创建时间: 2025-06-13
版本: 1.0.0
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any
import time
import logging

# 策略框架组件
from src.pktmask.core.trim.strategies import (
    BaseStrategy, ProtocolInfo, TrimContext, TrimResult,
    ProtocolStrategyFactory, get_strategy_factory
)
from src.pktmask.core.trim.strategies.http_strategy import HTTPTrimStrategy
from src.pktmask.core.trim.strategies.default_strategy import DefaultStrategy
from src.pktmask.core.trim.models.mask_spec import MaskAfter, MaskRange, KeepAll


class TestPhase32HTTPStrategyIntegrationSimple:
    """Phase 3.2 HTTP策略集成测试 (简化版)"""
    
    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)
        
    @pytest.fixture
    def mock_config(self):
        """创建模拟配置"""
        return {
            'trim': {
                'enabled': True,
                'max_file_size': 1024 * 1024 * 100,
                'output_format': 'pcap'
            },
            'strategies': {
                'http': {
                    'preserve_headers': True,
                    'header_only_mode': False,
                    'body_preserve_bytes': 64,
                    'confidence_threshold': 0.8,
                    'preserve_content_type': True,
                    'preserve_host': True
                },
                'default': {
                    'default_preserve_bytes': 32,
                    'confidence_threshold': 0.5
                }
            }
        }
        
    @pytest.fixture
    def strategy_factory(self):
        """创建策略工厂"""
        factory = ProtocolStrategyFactory()
        factory.register_strategy(HTTPTrimStrategy)
        factory.register_strategy(DefaultStrategy)
        return factory
        
    def test_http_strategy_registration_and_discovery(self, mock_config, strategy_factory):
        """测试HTTP策略注册和发现机制"""
        
        # 验证HTTP策略已注册
        http_config = mock_config['strategies']['http']
        http_strategy = strategy_factory.create_strategy('http', http_config)
        
        assert http_strategy is not None
        assert isinstance(http_strategy, HTTPTrimStrategy)
        assert http_strategy.strategy_name == 'http'
        assert 'HTTP' in http_strategy.supported_protocols
        assert 'HTTPS' in http_strategy.supported_protocols
        assert http_strategy.priority == 80
        
        # 验证配置正确应用
        assert http_strategy.config['preserve_headers'] is True
        assert http_strategy.config['body_preserve_bytes'] == 64
        assert http_strategy.config['confidence_threshold'] == 0.8
        
    def test_http_protocol_strategy_selection(self, mock_config, strategy_factory):
        """测试HTTP协议策略选择"""
        
        config = mock_config['trim']
        context = TrimContext(0, 'test_stream', 'client_to_server', [], 1500, 0.0, {})
        
        # 测试HTTP协议策略选择
        http_protocols = [
            ProtocolInfo('HTTP', '1.1', 7, 80, {'method': 'GET'}),
            ProtocolInfo('HTTP', '1.0', 7, 8080, {'method': 'POST'}),
            ProtocolInfo('HTTPS', '1.1', 7, 443, {'method': 'GET'})
        ]
        
        for protocol in http_protocols:
            strategy = strategy_factory.get_best_strategy(protocol, context, config)
            
            assert strategy is not None
            assert isinstance(strategy, HTTPTrimStrategy)
            assert strategy.can_handle(protocol, context)
            
        # 测试非HTTP协议应该选择默认策略
        non_http_protocol = ProtocolInfo('FTP', None, 7, 21, {})
        strategy = strategy_factory.get_best_strategy(non_http_protocol, context, config)
        
        assert strategy is not None
        assert isinstance(strategy, DefaultStrategy)
        
    def test_http_get_request_analysis(self, mock_config, strategy_factory):
        """测试HTTP GET请求分析"""
        
        config = mock_config['strategies']['http']
        http_strategy = HTTPTrimStrategy(config)
        
        # 创建HTTP GET请求载荷
        get_payload = (
            b'GET /api/users?page=1&limit=10 HTTP/1.1\r\n'
            b'Host: api.example.com\r\n'
            b'Accept: application/json\r\n'
            b'Authorization: Bearer token123\r\n'
            b'\r\n'
        )
        
        protocol_info = ProtocolInfo('HTTP', '1.1', 7, 80, {'method': 'GET'})
        context = TrimContext(0, 'http_get', 'client_to_server', [], len(get_payload), 0.0, {})
        
        # 执行分析
        analysis = http_strategy.analyze_payload(get_payload, protocol_info, context)
        
        # 验证分析结果
        assert analysis['is_http'] is True
        assert analysis['is_request'] is True
        assert analysis['method'] == 'GET'
        assert analysis['uri'] == '/api/users?page=1&limit=10'
        assert analysis['http_version'] == '1.1'
        assert analysis['confidence'] > 0.8
        assert 'host' in analysis['headers']
        assert analysis['headers']['host'] == 'api.example.com'
        assert analysis['body_size'] == 0
        
    def test_http_post_request_analysis(self, mock_config, strategy_factory):
        """测试HTTP POST请求分析"""
        
        config = mock_config['strategies']['http']
        http_strategy = HTTPTrimStrategy(config)
        
        # 创建HTTP POST请求载荷
        post_body = b'{"name": "test", "email": "test@example.com"}'
        post_payload = b'POST /api/users HTTP/1.1\r\n'
        post_payload += b'Host: api.example.com\r\n'
        post_payload += b'Content-Type: application/json\r\n'
        post_payload += b'Content-Length: ' + str(len(post_body)).encode() + b'\r\n'
        post_payload += b'\r\n'
        post_payload += post_body
        
        protocol_info = ProtocolInfo('HTTP', '1.1', 7, 80, {'method': 'POST'})
        context = TrimContext(0, 'http_post', 'client_to_server', [], len(post_payload), 0.0, {})
        
        # 执行分析
        analysis = http_strategy.analyze_payload(post_payload, protocol_info, context)
        
        # 验证分析结果
        assert analysis['is_http'] is True
        assert analysis['is_request'] is True
        assert analysis['method'] == 'POST'
        assert analysis['content_type'] == 'application/json'
        assert analysis['content_length'] == len(post_body)
        assert analysis['body_size'] == len(post_body)
        
    def test_http_response_analysis(self, mock_config, strategy_factory):
        """测试HTTP响应分析"""
        
        config = mock_config['strategies']['http']
        http_strategy = HTTPTrimStrategy(config)
        
        # 创建HTTP响应载荷
        response_body = b'Hello, World!'
        response_payload = b'HTTP/1.1 200 OK\r\n'
        response_payload += b'Content-Type: text/html\r\n'
        response_payload += b'Content-Length: ' + str(len(response_body)).encode() + b'\r\n'
        response_payload += b'Server: nginx/1.18\r\n'
        response_payload += b'\r\n'
        response_payload += response_body
        
        protocol_info = ProtocolInfo('HTTP', '1.1', 7, 80, {})
        context = TrimContext(0, 'http_response', 'server_to_client', [], len(response_payload), 0.0, {})
        
        # 执行分析
        analysis = http_strategy.analyze_payload(response_payload, protocol_info, context)
        
        # 验证分析结果
        assert analysis['is_http'] is True
        assert analysis['is_response'] is True
        assert analysis['is_request'] is False
        assert analysis['status_code'] == 200
        assert analysis['reason_phrase'] == 'OK'
        assert analysis['http_version'] == '1.1'
        assert analysis['content_type'] == 'text/html'
        assert analysis['content_length'] == len(response_body)
        assert analysis['body_size'] == len(response_body)
        
    def test_http_mask_generation_for_response(self, mock_config, strategy_factory):
        """测试HTTP响应掩码生成"""
        
        config = mock_config['strategies']['http']
        http_strategy = HTTPTrimStrategy(config)
        
        # 创建HTTP响应载荷
        response_body = b'X' * 500  # 500字节响应体
        response_payload = b'HTTP/1.1 200 OK\r\n'
        response_payload += b'Content-Type: text/html\r\n'
        response_payload += b'Content-Length: 500\r\n'
        response_payload += b'Server: nginx/1.18\r\n'
        response_payload += b'\r\n'
        response_payload += response_body
        
        protocol_info = ProtocolInfo('HTTP', '1.1', 7, 80, {})
        context = TrimContext(0, 'http_response', 'server_to_client', [], len(response_payload), 0.0, {})
        
        # 执行完整的裁切流程
        result = http_strategy.trim_payload(response_payload, protocol_info, context)
        
        # 验证掩码生成结果
        assert result.success is True
        assert isinstance(result.mask_spec, MaskAfter)
        assert result.preserved_bytes > 0
        assert result.preserved_bytes < len(response_payload)  # 响应体应该被部分裁切
        assert result.trimmed_bytes > 0
        assert result.confidence > 0.8
        assert 'HTTP 200 响应' in result.reason
        
    def test_http_strategy_performance(self, mock_config, strategy_factory):
        """测试HTTP策略性能"""
        
        config = mock_config['strategies']['http']
        http_strategy = HTTPTrimStrategy(config)
        
        # 创建不同大小的HTTP载荷进行性能测试
        test_cases = [
            (1024, "小型HTTP请求"),
            (8192, "中型HTTP请求"),
            (65536, "大型HTTP请求")
        ]
        
        for payload_size, description in test_cases:
            # 创建测试载荷
            body_size = payload_size - 200  # 预留200字节给头部
            body = b'X' * body_size
            
            payload = b'POST /api/data HTTP/1.1\r\n'
            payload += b'Host: api.example.com\r\n'
            payload += b'Content-Type: application/octet-stream\r\n'
            payload += b'Content-Length: ' + str(len(body)).encode() + b'\r\n'
            payload += b'\r\n'
            payload += body
            
            protocol_info = ProtocolInfo('HTTP', '1.1', 7, 80, {'method': 'POST'})
            context = TrimContext(0, f'perf_test_{payload_size}', 'client_to_server', [], len(payload), 0.0, {})
            
            # 测量处理时间
            start_time = time.time()
            result = http_strategy.trim_payload(payload, protocol_info, context)
            processing_time = time.time() - start_time
            
            # 验证性能要求
            assert result.success is True, f"处理失败: {description}"
            assert processing_time < 1.0, f"处理时间过长: {description} 用时 {processing_time:.3f}s"
            assert result.confidence > 0.8, f"置信度过低: {description} 置信度 {result.confidence:.2f}"
            
    def test_http_strategy_config_integration(self, mock_config, strategy_factory):
        """测试HTTP策略配置集成"""
        
        # 测试不同配置的HTTP策略
        configs = [
            # 头部模式
            {
                'preserve_headers': True,
                'header_only_mode': True,
                'confidence_threshold': 0.8
            },
            # 正常模式
            {
                'preserve_headers': True,
                'header_only_mode': False,
                'body_preserve_bytes': 128,
                'confidence_threshold': 0.7
            }
        ]
        
        for config in configs:
            http_strategy = HTTPTrimStrategy(config)
            
            # 创建测试载荷
            body = b'{"data": "test"}'
            payload = b'POST /api/test HTTP/1.1\r\n'
            payload += b'Host: test.com\r\n'
            payload += b'Content-Type: application/json\r\n'
            payload += b'Content-Length: ' + str(len(body)).encode() + b'\r\n'
            payload += b'\r\n'
            payload += body
            
            protocol_info = ProtocolInfo('HTTP', '1.1', 7, 80, {'method': 'POST'})
            context = TrimContext(0, 'config_test', 'client_to_server', [], len(payload), 0.0, {})
            
            result = http_strategy.trim_payload(payload, protocol_info, context)
            
            # 验证配置效果
            assert result.success is True
            
            if config.get('header_only_mode', False):
                # 头部模式：应该只保留头部
                header_size = payload.find(b'\r\n\r\n') + 4
                assert result.preserved_bytes == header_size
                assert result.trimmed_bytes == len(body)
            else:
                # 正常模式：应该保留头部+部分消息体
                assert result.preserved_bytes > payload.find(b'\r\n\r\n') + 4
                assert result.trimmed_bytes < len(body)
                
    def test_http_strategy_integration_summary(self, temp_dir, mock_config, strategy_factory):
        """测试HTTP策略集成总结"""
        
        # 准备HTTP策略和配置
        config = mock_config['strategies']['http']
        http_strategy = HTTPTrimStrategy(config)
        
        # 模拟多种HTTP协议的处理
        test_protocols = [
            ('GET', b'GET /index.html HTTP/1.1\r\nHost: www.example.com\r\n\r\n'),
            ('POST', b'POST /api/data HTTP/1.1\r\nHost: api.example.com\r\nContent-Length: 13\r\n\r\n{"test":"data"}'),
            ('PUT', b'PUT /api/update HTTP/1.1\r\nHost: api.example.com\r\nContent-Length: 15\r\n\r\n{"update":"data"}')
        ]
        
        protocol_results = []
        total_preserved = 0
        total_trimmed = 0
        
        # 处理每种协议
        for i, (method, payload) in enumerate(test_protocols):
            protocol_info = ProtocolInfo('HTTP', '1.1', 7, 80, {'method': method})
            context = TrimContext(i, f'http_{method.lower()}', 'client_to_server', [], len(payload), 0.0, {})
            
            # 执行HTTP策略
            result = http_strategy.trim_payload(payload, protocol_info, context)
            
            # 记录结果
            protocol_results.append({
                'method': method,
                'success': result.success,
                'preserved_bytes': result.preserved_bytes if result.success else 0,
                'trimmed_bytes': result.trimmed_bytes if result.success else 0,
                'confidence': result.confidence if result.success else 0
            })
            
            if result.success:
                total_preserved += result.preserved_bytes
                total_trimmed += result.trimmed_bytes
        
        # 验证整体工作流程
        assert len(protocol_results) == 3
        success_count = sum(1 for pr in protocol_results if pr['success'])
        assert success_count == 3  # 所有协议都应该处理成功
        
        # 验证性能指标
        average_confidence = sum(pr['confidence'] for pr in protocol_results) / len(protocol_results)
        assert average_confidence > 0.8
        
        # 生成集成测试报告
        report = {
            'test_timestamp': time.time(),
            'protocols_tested': len(test_protocols),
            'success_rate': success_count / len(test_protocols),
            'total_preserved_bytes': total_preserved,
            'total_trimmed_bytes': total_trimmed,
            'average_confidence': average_confidence,
            'protocol_results': protocol_results
        }
        
        # 保存测试报告
        report_file = temp_dir / "phase3_2_http_integration_report.json"
        import json
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
            
        # 最终验证
        assert report['success_rate'] == 1.0
        assert report['average_confidence'] > 0.8
        assert report['total_preserved_bytes'] > 0
        
        # 打印总结信息
        print(f"\n🎉 Phase 3.2 HTTP策略集成测试完成:")
        print(f"- 测试协议数: {report['protocols_tested']}")
        print(f"- 成功率: {report['success_rate']:.2%}")
        print(f"- 平均置信度: {report['average_confidence']:.2f}")
        print(f"- 总保留字节: {report['total_preserved_bytes']}")
        print(f"- 总裁切字节: {report['total_trimmed_bytes']}")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short']) 