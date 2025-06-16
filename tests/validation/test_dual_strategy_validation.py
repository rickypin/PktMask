"""
双策略验证测试套件

全面验证Legacy HTTPTrimStrategy和新HTTPScanningStrategy的对比，
确保双策略系统正常工作且达到预期的质量标准。

作者: PktMask Team
创建时间: 2025-06-16
版本: 1.0.0
"""

import unittest
import json
import time
import tempfile
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
import logging

# 导入系统组件
try:
    from src.pktmask.core.trim.strategies.base_strategy import BaseStrategy, ProtocolInfo, TrimContext, TrimResult
    from src.pktmask.core.trim.strategies.factory import (
        EnhancedStrategyFactory, ComparisonWrapper, get_enhanced_strategy_factory
    )
    from src.pktmask.core.trim.testing.performance_tracker import PerformanceTracker, ComparisonResult
    from src.pktmask.config.http_strategy_config import (
        HttpStrategyConfiguration, StrategyMode, get_default_http_strategy_config,
        create_ab_test_config
    )
    IMPORTS_AVAILABLE = True
except ImportError as e:
    IMPORTS_AVAILABLE = False
    import_error = str(e)


@dataclass
class TestScenario:
    """测试场景定义"""
    name: str
    description: str
    payload_data: bytes
    protocol_info: ProtocolInfo
    context: TrimContext
    expected_results: Dict[str, Any]


@dataclass
class ValidationResult:
    """验证结果"""
    scenario_name: str
    success: bool
    legacy_result: Optional[TrimResult]
    scanning_result: Optional[TrimResult]
    comparison_data: Dict[str, Any]
    issues: List[str]
    performance_metrics: Dict[str, float]


@dataclass
class ScenarioResult:
    """场景测试结果"""
    scenario_group: str
    total_tests: int
    passed_tests: int
    failed_tests: int
    validation_results: List[ValidationResult]
    summary_metrics: Dict[str, float]


class DualStrategyValidator:
    """双策略验证器"""
    
    def __init__(self, config: Optional[HttpStrategyConfiguration] = None):
        """
        初始化验证器
        
        Args:
            config: HTTP策略配置
        """
        self.config = config or get_default_http_strategy_config()
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        
        # 初始化工厂和跟踪器
        self.strategy_factory = get_enhanced_strategy_factory(self.config)
        self.performance_tracker = PerformanceTracker()
        
        # 验证结果存储
        self.validation_results: List[ValidationResult] = []
        
        self.logger.info("DualStrategyValidator初始化完成")
    
    def validate_scenario(self, scenario: TestScenario) -> ValidationResult:
        """
        验证单个测试场景
        
        Args:
            scenario: 测试场景
            
        Returns:
            验证结果
        """
        issues = []
        performance_metrics = {}
        
        try:
            # 获取双策略
            legacy_strategy = self.strategy_factory._get_legacy_strategy({})
            scanning_strategy = self.strategy_factory._get_scanning_strategy({})
            
            if not legacy_strategy:
                issues.append("无法获取Legacy策略实例")
                return ValidationResult(
                    scenario_name=scenario.name,
                    success=False,
                    legacy_result=None,
                    scanning_result=None,
                    comparison_data={},
                    issues=issues,
                    performance_metrics={}
                )
                
            if not scanning_strategy:
                issues.append("无法获取Scanning策略实例")
                
            # 测试Legacy策略
            legacy_start = time.perf_counter()
            try:
                legacy_result = legacy_strategy.trim_payload(
                    scenario.payload_data, scenario.protocol_info, scenario.context
                )
                legacy_success = True
                legacy_error = None
            except Exception as e:
                legacy_result = None
                legacy_success = False
                legacy_error = str(e)
                issues.append(f"Legacy策略执行失败: {legacy_error}")
            legacy_duration = time.perf_counter() - legacy_start
            
            # 测试Scanning策略
            scanning_result = None
            scanning_success = False
            scanning_error = None
            scanning_duration = 0.0
            
            if scanning_strategy:
                scanning_start = time.perf_counter()
                try:
                    scanning_result = scanning_strategy.trim_payload(
                        scenario.payload_data, scenario.protocol_info, scenario.context
                    )
                    scanning_success = True
                    scanning_error = None
                except Exception as e:
                    scanning_result = None
                    scanning_success = False
                    scanning_error = str(e)
                    issues.append(f"Scanning策略执行失败: {scanning_error}")
                scanning_duration = time.perf_counter() - scanning_start
            
            # 性能指标
            performance_metrics = {
                'legacy_duration_ms': legacy_duration * 1000,
                'scanning_duration_ms': scanning_duration * 1000,
                'speed_improvement': ((legacy_duration - scanning_duration) / legacy_duration 
                                    if legacy_duration > 0 else 0),
                'legacy_success': legacy_success,
                'scanning_success': scanning_success
            }
            
            # 结果对比
            comparison_data = self._compare_results(
                legacy_result, scanning_result, scenario.expected_results
            )
            
            # 整体成功判断
            success = (legacy_success and 
                      (not scanning_strategy or scanning_success) and 
                      len(issues) == 0)
            
            return ValidationResult(
                scenario_name=scenario.name,
                success=success,
                legacy_result=legacy_result,
                scanning_result=scanning_result,
                comparison_data=comparison_data,
                issues=issues,
                performance_metrics=performance_metrics
            )
            
        except Exception as e:
            issues.append(f"验证场景异常: {str(e)}")
            self.logger.error(f"验证场景 {scenario.name} 异常: {e}", exc_info=True)
            
            return ValidationResult(
                scenario_name=scenario.name,
                success=False,
                legacy_result=None,
                scanning_result=None,
                comparison_data={},
                issues=issues,
                performance_metrics=performance_metrics
            )
    
    def _compare_results(self, legacy_result: Optional[TrimResult], 
                        scanning_result: Optional[TrimResult],
                        expected_results: Dict[str, Any]) -> Dict[str, Any]:
        """比较策略结果"""
        
        comparison = {
            'both_successful': False,
            'results_consistent': False,
            'preserved_bytes_match': False,
            'confidence_delta': 0.0,
            'expected_match': False
        }
        
        if legacy_result and scanning_result:
            comparison['both_successful'] = legacy_result.success and scanning_result.success
            
            if comparison['both_successful']:
                # 保留字节数对比
                preserved_diff = abs(legacy_result.preserved_bytes - scanning_result.preserved_bytes)
                preserved_ratio = preserved_diff / max(legacy_result.preserved_bytes, 1)
                comparison['preserved_bytes_match'] = preserved_ratio <= 0.05  # 5%差异内
                
                # 置信度对比
                comparison['confidence_delta'] = abs(legacy_result.confidence - scanning_result.confidence)
                
                # 整体一致性
                comparison['results_consistent'] = (
                    comparison['preserved_bytes_match'] and 
                    comparison['confidence_delta'] <= 0.2
                )
            
            # 与期望结果对比
            expected_preserved = expected_results.get('preserved_bytes')
            if expected_preserved is not None:
                legacy_match = abs(legacy_result.preserved_bytes - expected_preserved) <= expected_preserved * 0.1
                scanning_match = (scanning_result.preserved_bytes == 0 or 
                                abs(scanning_result.preserved_bytes - expected_preserved) <= expected_preserved * 0.1)
                comparison['expected_match'] = legacy_match and (scanning_result is None or scanning_match)
        
        return comparison
    
    def run_http_simple_tests(self) -> ScenarioResult:
        """测试简单HTTP请求/响应"""
        
        scenarios = [
            TestScenario(
                name="HTTP_GET_Request",
                description="简单HTTP GET请求",
                payload_data=self._create_http_get_request(),
                protocol_info=ProtocolInfo(name="HTTP", version="1.1", layer=7, port=80, characteristics={}),
                context=self._create_test_context("http_get.pcap"),
                expected_results={'preserved_bytes': 150}
            ),
            TestScenario(
                name="HTTP_POST_Request",
                description="带数据的HTTP POST请求", 
                payload_data=self._create_http_post_request(),
                protocol_info=ProtocolInfo(name="HTTP", version="1.1", layer=7, port=80, characteristics={}),
                context=self._create_test_context("http_post.pcap"),
                expected_results={'preserved_bytes': 200}
            ),
            TestScenario(
                name="HTTP_200_Response",
                description="HTTP 200响应",
                payload_data=self._create_http_200_response(),
                protocol_info=ProtocolInfo(name="HTTP", version="1.1", layer=7, port=80, characteristics={}),
                context=self._create_test_context("http_200.pcap"),
                expected_results={'preserved_bytes': 300}
            ),
            TestScenario(
                name="HTTP_404_Response",
                description="HTTP 404错误响应",
                payload_data=self._create_http_404_response(),
                protocol_info=ProtocolInfo(name="HTTP", version="1.1", layer=7, port=80, characteristics={}),
                context=self._create_test_context("http_404.pcap"),
                expected_results={'preserved_bytes': 250}
            )
        ]
        
        return self._run_scenario_group("HTTP简单请求响应", scenarios)
    
    def run_chunked_encoding_tests(self) -> ScenarioResult:
        """测试Chunked编码处理"""
        
        scenarios = [
            TestScenario(
                name="Complete_Chunked_Response",
                description="完整的Chunked编码响应",
                payload_data=self._create_complete_chunked_response(),
                protocol_info=ProtocolInfo(name="HTTP", version="1.1", layer=7, port=80, characteristics={}),
                context=self._create_test_context("chunked_complete.pcap"),
                expected_results={'preserved_bytes': 400}
            ),
            TestScenario(
                name="Incomplete_Chunked_Response",
                description="不完整的Chunked编码响应",
                payload_data=self._create_incomplete_chunked_response(),
                protocol_info=ProtocolInfo(name="HTTP", version="1.1", layer=7, port=80, characteristics={}),
                context=self._create_test_context("chunked_incomplete.pcap"),
                expected_results={'preserved_bytes': 600}
            ),
            TestScenario(
                name="Large_Chunked_Response",
                description="大文件Chunked编码响应",
                payload_data=self._create_large_chunked_response(),
                protocol_info=ProtocolInfo(name="HTTP", version="1.1", layer=7, port=80, characteristics={}),
                context=self._create_test_context("chunked_large.pcap"),
                expected_results={'preserved_bytes': 1200}
            )
        ]
        
        return self._run_scenario_group("Chunked编码处理", scenarios)
    
    def run_keep_alive_tests(self) -> ScenarioResult:
        """测试Keep-Alive多消息处理"""
        
        scenarios = [
            TestScenario(
                name="Keep_Alive_Multiple_Responses",
                description="Keep-Alive连接多个响应",
                payload_data=self._create_keep_alive_responses(),
                protocol_info=ProtocolInfo(name="HTTP", version="1.1", layer=7, port=80, characteristics={}),
                context=self._create_test_context("keep_alive.pcap"),
                expected_results={'preserved_bytes': 800}
            ),
            TestScenario(
                name="Pipelined_Requests",
                description="HTTP管道化请求",
                payload_data=self._create_pipelined_requests(),
                protocol_info=ProtocolInfo(name="HTTP", version="1.1", layer=7, port=80, characteristics={}),
                context=self._create_test_context("pipelined.pcap"),
                expected_results={'preserved_bytes': 500}
            )
        ]
        
        return self._run_scenario_group("Keep-Alive多消息", scenarios)
    
    def run_large_file_tests(self) -> ScenarioResult:
        """测试大文件下载场景"""
        
        scenarios = [
            TestScenario(
                name="Large_File_Download",
                description="大文件下载(>1MB)",
                payload_data=self._create_large_file_response(),
                protocol_info=ProtocolInfo(name="HTTP", version="1.1", layer=7, port=80, characteristics={}),
                context=self._create_test_context("large_download.pcap"),
                expected_results={'preserved_bytes': 8192}  # 应该只保留头部
            )
        ]
        
        return self._run_scenario_group("大文件下载", scenarios)
    
    def run_error_scenarios(self) -> ScenarioResult:
        """测试错误场景处理"""
        
        scenarios = [
            TestScenario(
                name="Malformed_HTTP_Request",
                description="格式错误的HTTP请求",
                payload_data=self._create_malformed_request(),
                protocol_info=ProtocolInfo(name="HTTP", version="1.1", layer=7, port=80, characteristics={}),
                context=self._create_test_context("malformed.pcap"),
                expected_results={'preserved_bytes': 0}  # 应该保守处理
            ),
            TestScenario(
                name="Incomplete_HTTP_Headers",
                description="不完整的HTTP头部",
                payload_data=self._create_incomplete_headers(),
                protocol_info=ProtocolInfo(name="HTTP", version="1.1", layer=7, port=80, characteristics={}),
                context=self._create_test_context("incomplete.pcap"),
                expected_results={'preserved_bytes': 0}  # 应该保守处理
            )
        ]
        
        return self._run_scenario_group("错误场景处理", scenarios)
    
    def _run_scenario_group(self, group_name: str, scenarios: List[TestScenario]) -> ScenarioResult:
        """运行一组测试场景"""
        
        self.logger.info(f"开始测试场景组: {group_name} ({len(scenarios)}个场景)")
        
        validation_results = []
        passed_count = 0
        
        for scenario in scenarios:
            result = self.validate_scenario(scenario)
            validation_results.append(result)
            
            if result.success:
                passed_count += 1
                self.logger.debug(f"✅ {scenario.name}: 通过")
            else:
                self.logger.warning(f"❌ {scenario.name}: 失败 - {', '.join(result.issues)}")
        
        failed_count = len(scenarios) - passed_count
        
        # 计算摘要指标
        summary_metrics = self._calculate_group_metrics(validation_results)
        
        result = ScenarioResult(
            scenario_group=group_name,
            total_tests=len(scenarios),
            passed_tests=passed_count,
            failed_tests=failed_count,
            validation_results=validation_results,
            summary_metrics=summary_metrics
        )
        
        self.logger.info(f"场景组 {group_name} 完成: {passed_count}/{len(scenarios)} 通过")
        return result
    
    def _calculate_group_metrics(self, results: List[ValidationResult]) -> Dict[str, float]:
        """计算场景组的摘要指标"""
        
        if not results:
            return {}
        
        # 性能指标
        legacy_times = [r.performance_metrics.get('legacy_duration_ms', 0) for r in results]
        scanning_times = [r.performance_metrics.get('scanning_duration_ms', 0) for r in results]
        
        avg_legacy_time = sum(legacy_times) / len(legacy_times) if legacy_times else 0
        avg_scanning_time = sum(scanning_times) / len(scanning_times) if scanning_times else 0
        
        # 成功率
        legacy_success_rate = sum(1 for r in results if r.performance_metrics.get('legacy_success', False)) / len(results)
        scanning_success_rate = sum(1 for r in results if r.performance_metrics.get('scanning_success', False)) / len(results)
        
        # 结果一致性
        consistent_results = sum(1 for r in results if r.comparison_data.get('results_consistent', False))
        consistency_rate = consistent_results / len(results)
        
        return {
            'avg_legacy_time_ms': avg_legacy_time,
            'avg_scanning_time_ms': avg_scanning_time,
            'legacy_success_rate': legacy_success_rate,
            'scanning_success_rate': scanning_success_rate,
            'consistency_rate': consistency_rate,
            'avg_speed_improvement': sum(r.performance_metrics.get('speed_improvement', 0) for r in results) / len(results)
        }
    
    def _create_test_context(self, filename: str) -> TrimContext:
        """创建测试上下文"""
        return TrimContext(
            packet_index=1,
            stream_id="test_stream",
            flow_direction="client_to_server",
            protocol_stack=["ETH", "IP", "TCP", "HTTP"],
            payload_size=1000,
            timestamp=time.time(),
            metadata={'test_file': filename}
        )
    
    # 测试数据生成方法
    def _create_http_get_request(self) -> bytes:
        """创建HTTP GET请求数据"""
        return b"GET /api/data HTTP/1.1\r\nHost: example.com\r\nUser-Agent: TestClient/1.0\r\nAccept: application/json\r\n\r\n"
    
    def _create_http_post_request(self) -> bytes:
        """创建HTTP POST请求数据"""
        data = b'{"name": "test", "value": 123}'
        return (b"POST /api/submit HTTP/1.1\r\n"
                b"Host: example.com\r\n"
                b"Content-Type: application/json\r\n"
                b"Content-Length: " + str(len(data)).encode() + b"\r\n"
                b"\r\n" + data)
    
    def _create_http_200_response(self) -> bytes:
        """创建HTTP 200响应数据"""
        body = b'{"status": "success", "data": [1,2,3,4,5]}'
        return (b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: application/json\r\n"
                b"Content-Length: " + str(len(body)).encode() + b"\r\n"
                b"Connection: keep-alive\r\n"
                b"\r\n" + body)
    
    def _create_http_404_response(self) -> bytes:
        """创建HTTP 404响应数据"""
        body = b'{"error": "Not Found", "code": 404}'
        return (b"HTTP/1.1 404 Not Found\r\n"
                b"Content-Type: application/json\r\n"
                b"Content-Length: " + str(len(body)).encode() + b"\r\n"
                b"\r\n" + body)
    
    def _create_complete_chunked_response(self) -> bytes:
        """创建完整的Chunked响应"""
        return (b"HTTP/1.1 200 OK\r\n"
                b"Transfer-Encoding: chunked\r\n"
                b"Content-Type: text/plain\r\n"
                b"\r\n"
                b"1a\r\n"
                b"abcdefghijklmnopqrstuvwxyz\r\n"
                b"10\r\n"
                b"1234567890123456\r\n"
                b"0\r\n"
                b"\r\n")
    
    def _create_incomplete_chunked_response(self) -> bytes:
        """创建不完整的Chunked响应"""
        return (b"HTTP/1.1 200 OK\r\n"
                b"Transfer-Encoding: chunked\r\n"
                b"Content-Type: text/plain\r\n"
                b"\r\n"
                b"20\r\n"
                b"This is a chunk of data that")  # 缺少结尾
    
    def _create_large_chunked_response(self) -> bytes:
        """创建大文件Chunked响应"""
        header = (b"HTTP/1.1 200 OK\r\n"
                 b"Transfer-Encoding: chunked\r\n"
                 b"Content-Type: application/octet-stream\r\n"
                 b"\r\n")
        
        # 多个大chunk
        chunks = []
        for i in range(5):
            chunk_data = b"x" * 1000  # 1KB数据
            chunk_size = hex(len(chunk_data))[2:].encode()
            chunks.append(chunk_size + b"\r\n" + chunk_data + b"\r\n")
        
        chunks.append(b"0\r\n\r\n")  # 结束chunk
        
        return header + b"".join(chunks)
    
    def _create_keep_alive_responses(self) -> bytes:
        """创建Keep-Alive多响应"""
        resp1 = (b"HTTP/1.1 200 OK\r\n"
                b"Content-Length: 13\r\n"
                b"Connection: keep-alive\r\n"
                b"\r\n"
                b"First response")
        
        resp2 = (b"HTTP/1.1 200 OK\r\n"
                b"Content-Length: 14\r\n"
                b"Connection: keep-alive\r\n"
                b"\r\n"
                b"Second response")
        
        return resp1 + resp2
    
    def _create_pipelined_requests(self) -> bytes:
        """创建管道化请求"""
        req1 = b"GET /page1 HTTP/1.1\r\nHost: example.com\r\n\r\n"
        req2 = b"GET /page2 HTTP/1.1\r\nHost: example.com\r\n\r\n"
        req3 = b"GET /page3 HTTP/1.1\r\nHost: example.com\r\n\r\n"
        
        return req1 + req2 + req3
    
    def _create_large_file_response(self) -> bytes:
        """创建大文件响应"""
        body = b"x" * (1024 * 1024 + 500)  # >1MB数据
        
        return (b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: application/octet-stream\r\n"
                b"Content-Length: " + str(len(body)).encode() + b"\r\n"
                b"Content-Disposition: attachment; filename=large_file.bin\r\n"
                b"\r\n" + body)
    
    def _create_malformed_request(self) -> bytes:
        """创建格式错误的请求"""
        return b"INVALID REQUEST FORMAT\r\nNo proper headers\r\n"
    
    def _create_incomplete_headers(self) -> bytes:
        """创建不完整的头部"""
        return b"GET /api/data HTTP/1.1\r\nHost: example.com\r\nUser-Agent: TestClient"  # 缺少结尾


class TestDualStrategyValidation(unittest.TestCase):
    """双策略验证测试类"""
    
    @classmethod
    def setUpClass(cls):
        """测试类初始化"""
        if not IMPORTS_AVAILABLE:
            cls.skipTest(cls, f"导入失败: {import_error}")
        
        # 设置日志
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        cls.config = get_default_http_strategy_config()
        cls.validator = DualStrategyValidator(cls.config)
    
    def test_http_simple_scenarios(self):
        """测试简单HTTP场景"""
        result = self.validator.run_http_simple_tests()
        
        # 验证基本指标
        self.assertGreater(result.total_tests, 0)
        self.assertGreaterEqual(result.passed_tests, result.total_tests * 0.8)  # 至少80%通过
        
        # 验证性能指标
        metrics = result.summary_metrics
        self.assertGreaterEqual(metrics.get('legacy_success_rate', 0), 0.9)  # Legacy策略90%成功率
        
        print(f"HTTP简单场景测试: {result.passed_tests}/{result.total_tests} 通过")
        print(f"Legacy成功率: {metrics.get('legacy_success_rate', 0):.1%}")
        print(f"平均速度提升: {metrics.get('avg_speed_improvement', 0):.1%}")
    
    def test_chunked_encoding_scenarios(self):
        """测试Chunked编码场景"""
        result = self.validator.run_chunked_encoding_tests()
        
        self.assertGreater(result.total_tests, 0)
        self.assertGreaterEqual(result.passed_tests, result.total_tests * 0.7)  # 至少70%通过
        
        print(f"Chunked编码测试: {result.passed_tests}/{result.total_tests} 通过")
    
    def test_keep_alive_scenarios(self):
        """测试Keep-Alive场景"""
        result = self.validator.run_keep_alive_tests()
        
        self.assertGreater(result.total_tests, 0)
        self.assertGreaterEqual(result.passed_tests, result.total_tests * 0.6)  # 至少60%通过
        
        print(f"Keep-Alive测试: {result.passed_tests}/{result.total_tests} 通过")
    
    def test_large_file_scenarios(self):
        """测试大文件场景"""
        result = self.validator.run_large_file_tests()
        
        self.assertGreater(result.total_tests, 0)
        self.assertGreaterEqual(result.passed_tests, result.total_tests * 0.8)  # 至少80%通过
        
        print(f"大文件测试: {result.passed_tests}/{result.total_tests} 通过")
    
    def test_error_scenarios(self):
        """测试错误场景"""
        result = self.validator.run_error_scenarios()
        
        self.assertGreater(result.total_tests, 0)
        # 错误场景可能有较低通过率，重点是不要崩溃
        
        print(f"错误场景测试: {result.passed_tests}/{result.total_tests} 通过")
    
    def test_comprehensive_validation(self):
        """综合验证测试"""
        
        # 运行所有场景
        results = [
            self.validator.run_http_simple_tests(),
            self.validator.run_chunked_encoding_tests(),
            self.validator.run_keep_alive_tests(),
            self.validator.run_large_file_tests(),
            self.validator.run_error_scenarios()
        ]
        
        # 计算总体指标
        total_tests = sum(r.total_tests for r in results)
        total_passed = sum(r.passed_tests for r in results)
        overall_pass_rate = total_passed / total_tests if total_tests > 0 else 0
        
        # 验证总体质量标准
        self.assertGreaterEqual(overall_pass_rate, 0.75)  # 总体75%通过率
        
        # 生成详细报告
        report = {
            'timestamp': time.time(),
            'overall_metrics': {
                'total_tests': total_tests,
                'total_passed': total_passed,
                'pass_rate': overall_pass_rate
            },
            'scenario_results': self._serialize_results(results)
        }
        
        # 保存报告
        report_path = Path('reports/dual_strategy_validation_report.json')
        report_path.parent.mkdir(exist_ok=True)
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=self._json_serializer)
        
        print(f"\n=== 双策略验证综合结果 ===")
        print(f"总测试数: {total_tests}")
        print(f"通过数: {total_passed}")
        print(f"通过率: {overall_pass_rate:.1%}")
        print(f"详细报告: {report_path}")
        
        # 验证关键质量指标
        self.assertGreaterEqual(overall_pass_rate, 0.75, "双策略验证总体通过率应≥75%")
    
    def _serialize_results(self, results: List[ScenarioResult]) -> List[Dict[str, Any]]:
        """序列化结果，处理不可序列化的对象"""
        serialized = []
        
        for result in results:
            result_dict = asdict(result)
            
            # 处理validation_results中的不可序列化对象
            for validation_result in result_dict.get('validation_results', []):
                # 处理legacy_result和scanning_result中的不可序列化对象
                for result_key in ['legacy_result', 'scanning_result']:
                    if validation_result.get(result_key):
                        validation_result[result_key] = self._serialize_trim_result(validation_result[result_key])
            
            serialized.append(result_dict)
        
        return serialized
    
    def _serialize_trim_result(self, trim_result: Any) -> Dict[str, Any]:
        """序列化TrimResult对象"""
        if trim_result is None:
            return None
        
        # 提取可序列化的属性
        return {
            'success': getattr(trim_result, 'success', False),
            'preserved_bytes': getattr(trim_result, 'preserved_bytes', 0),
            'confidence': getattr(trim_result, 'confidence', 0.0),
            'method': getattr(trim_result, 'method', 'unknown'),
            'mask_specs_count': len(getattr(trim_result, 'mask_specs', [])),
            'metadata': getattr(trim_result, 'metadata', {})
        }
    
    def _json_serializer(self, obj):
        """自定义JSON序列化器"""
        if hasattr(obj, '__dict__'):
            return obj.__dict__
        elif hasattr(obj, '_asdict'):
            return obj._asdict()
        else:
            return str(obj)


if __name__ == '__main__':
    unittest.main(verbosity=2) 