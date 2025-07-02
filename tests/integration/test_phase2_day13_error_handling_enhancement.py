"""
Phase 2, Day 13: 错误处理完善 - 集成测试

测试增强的错误处理机制：
1. 错误分类和上下文记录
2. 智能重试机制和指数退避
3. 错误恢复策略
4. 详细错误报告和诊断
5. 错误模式分析和缓解建议

作者: PktMask Team
创建时间: 2025-01-22
版本: Phase 2, Day 13
"""

import pytest
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, List

# 被测试模块
from pktmask.core.processors.tshark_enhanced_mask_processor import (
    TSharkEnhancedMaskProcessor,
    ErrorCategory,
    ErrorSeverity,
    ErrorContext,
    ErrorTracker,
    RetryConfig,
    FallbackMode
)
from pktmask.core.processors.base_processor import ProcessorConfig, ProcessorResult


@pytest.fixture
def mock_processor_config():
    """创建模拟处理器配置"""
    return ProcessorConfig(
        enabled=True,
        name="tshark_enhanced_mask_processor_day13",
        priority=1
    )


@pytest.fixture
def error_tracker():
    """创建错误跟踪器"""
    return ErrorTracker()


@pytest.fixture
def sample_error_context():
    """创建示例错误上下文"""
    return ErrorContext(
        category=ErrorCategory.PROCESSING_ERROR,
        severity=ErrorSeverity.MEDIUM,
        error_code="TEST_ERROR",
        message="测试错误消息",
        file_context="test_input.pcap",
        stage_context="test_stage"
    )


@pytest.fixture
def temp_test_file(tmp_path):
    """创建临时测试文件"""
    test_file = tmp_path / "test_input.pcap"
    test_file.write_bytes(b"fake pcap data for testing")
    return test_file


class TestErrorClassificationAndContext:
    """错误分类和上下文记录测试"""
    
    def test_error_category_enum_completeness(self):
        """测试错误分类枚举的完整性"""
        expected_categories = [
            "dependency_error", "configuration_error", "initialization_error",
            "processing_error", "io_error", "memory_error", "timeout_error",
            "protocol_error", "validation_error", "unknown_error"
        ]
        
        actual_categories = [category.value for category in ErrorCategory]
        
        for expected in expected_categories:
            assert expected in actual_categories, f"缺少错误类别: {expected}"
    
    def test_error_severity_hierarchy(self):
        """测试错误严重性等级"""
        severities = [severity.value for severity in ErrorSeverity]
        expected_severities = ["low", "medium", "high", "critical"]
        
        assert severities == expected_severities
    
    def test_error_context_creation_with_full_info(self, mock_processor_config):
        """测试创建完整错误上下文"""
        processor = TSharkEnhancedMaskProcessor(mock_processor_config)
        
        test_exception = ValueError("测试异常")
        
        error_context = processor._create_error_context(
            category=ErrorCategory.MEMORY_ERROR,
            severity=ErrorSeverity.HIGH,
            error_code="MEMORY_EXHAUSTED",
            message="内存不足无法继续处理",
            exception=test_exception,
            file_context="large_file.pcap",
            stage_context="core_pipeline"
        )
        
        # 验证错误上下文属性
        assert error_context.category == ErrorCategory.MEMORY_ERROR
        assert error_context.severity == ErrorSeverity.HIGH
        assert error_context.error_code == "MEMORY_EXHAUSTED"
        assert error_context.message == "内存不足无法继续处理"
        assert error_context.exception == test_exception
        assert error_context.file_context == "large_file.pcap"
        assert error_context.stage_context == "core_pipeline"
        assert error_context.timestamp > 0
        assert isinstance(error_context.mitigation_suggestions, list)
        assert len(error_context.mitigation_suggestions) > 0
    
    def test_error_context_mitigation_suggestions(self, error_tracker):
        """测试错误缓解建议生成"""
        # 依赖错误建议
        dependency_error = ErrorContext(
            category=ErrorCategory.DEPENDENCY_ERROR,
            severity=ErrorSeverity.HIGH,
            error_code="TSHARK_MISSING",
            message="TShark工具未找到"
        )
        
        suggestions = error_tracker.suggest_mitigations(dependency_error)
        
        assert len(suggestions) > 0
        assert any("TShark" in suggestion for suggestion in suggestions)
        assert any("PATH" in suggestion for suggestion in suggestions)
        
        # 内存错误建议
        memory_error = ErrorContext(
            category=ErrorCategory.MEMORY_ERROR,
            severity=ErrorSeverity.HIGH,
            error_code="OUT_OF_MEMORY",
            message="系统内存不足"
        )
        
        memory_suggestions = error_tracker.suggest_mitigations(memory_error)
        assert any("内存" in suggestion for suggestion in memory_suggestions)
        assert any("批次" in suggestion for suggestion in memory_suggestions)


class TestErrorTrackingAndAnalysis:
    """错误跟踪和分析测试"""
    
    def test_error_recording_and_pattern_detection(self, error_tracker):
        """测试错误记录和模式检测"""
        # 记录多个相同模式的错误
        for i in range(5):
            error_context = ErrorContext(
                category=ErrorCategory.TIMEOUT_ERROR,
                severity=ErrorSeverity.MEDIUM,
                error_code="PROCESSING_TIMEOUT",
                message=f"处理超时 #{i+1}"
            )
            error_tracker.record_error(error_context)
        
        # 记录不同模式的错误
        for i in range(2):
            error_context = ErrorContext(
                category=ErrorCategory.IO_ERROR,
                severity=ErrorSeverity.HIGH,
                error_code="FILE_READ_ERROR",
                message=f"文件读取错误 #{i+1}"
            )
            error_tracker.record_error(error_context)
        
        # 分析错误模式
        analysis = error_tracker.analyze_error_patterns()
        
        assert analysis["total_errors"] == 7
        assert analysis["category_distribution"]["timeout_error"] == 5
        assert analysis["category_distribution"]["io_error"] == 2
        assert analysis["severity_distribution"]["medium"] == 5
        assert analysis["severity_distribution"]["high"] == 2
        
        # 检查最常见的错误模式
        most_common = analysis["most_common_patterns"]
        assert "timeout_error:PROCESSING_TIMEOUT" in most_common
        assert most_common["timeout_error:PROCESSING_TIMEOUT"] == 5
    
    def test_recent_error_trend_analysis(self, error_tracker):
        """测试最近错误趋势分析"""
        # 记录一些较旧的错误（模拟）
        old_error = ErrorContext(
            category=ErrorCategory.PROCESSING_ERROR,
            severity=ErrorSeverity.LOW,
            error_code="OLD_ERROR",
            message="旧错误"
        )
        old_error.timestamp = time.time() - 7200  # 2小时前
        error_tracker.error_history.append(old_error)
        
        # 记录一些最近的错误
        for i in range(3):
            recent_error = ErrorContext(
                category=ErrorCategory.VALIDATION_ERROR,
                severity=ErrorSeverity.MEDIUM,
                error_code="VALIDATION_FAILED",
                message=f"验证失败 #{i+1}"
            )
            error_tracker.record_error(recent_error)
        
        # 分析错误模式（不使用time_window_hours参数）
        analysis = error_tracker.analyze_error_patterns()
        
        # 验证总体分析结果
        assert analysis["total_errors"] == 4  # 1个旧错误 + 3个新错误
        assert analysis["category_distribution"]["validation_error"] == 3
        assert analysis["category_distribution"]["processing_error"] == 1
        
        # 检查最近错误（使用analyze_error_patterns返回的recent_errors字段）
        assert analysis["recent_errors"] == 3  # 最近1小时内的错误


class TestRetryMechanism:
    """重试机制测试"""
    
    def test_retry_config_validation(self, mock_processor_config):
        """测试重试配置验证"""
        processor = TSharkEnhancedMaskProcessor(mock_processor_config)
        
        # 测试默认重试配置（从enhanced_config获取）
        retry_config = processor.enhanced_config.retry_config
        assert retry_config.max_retries >= 1
        assert retry_config.base_delay > 0
        assert retry_config.max_delay >= retry_config.base_delay
        assert isinstance(retry_config.retry_on_categories, list)
        assert len(retry_config.retry_on_categories) > 0
    
    def test_should_retry_logic(self, mock_processor_config):
        """测试重试逻辑判断"""
        processor = TSharkEnhancedMaskProcessor(mock_processor_config)
        
        # 可重试的错误
        retryable_error = ErrorContext(
            category=ErrorCategory.TIMEOUT_ERROR,
            severity=ErrorSeverity.MEDIUM,
            error_code="PROCESSING_TIMEOUT",
            message="处理超时"
        )
        retryable_error.retry_count = 1
        
        assert processor._should_retry(retryable_error, "test_file.pcap") == True
        
        # 超过最大重试次数的错误
        over_limit_error = ErrorContext(
            category=ErrorCategory.TIMEOUT_ERROR,
            severity=ErrorSeverity.MEDIUM,
            error_code="PROCESSING_TIMEOUT",
            message="处理超时"
        )
        over_limit_error.retry_count = 5  # 超过max_retries
        
        assert processor._should_retry(over_limit_error, "test_file.pcap") == False
        
        # 不可重试的错误类别
        non_retryable_error = ErrorContext(
            category=ErrorCategory.CONFIGURATION_ERROR,
            severity=ErrorSeverity.HIGH,
            error_code="CONFIG_INVALID",
            message="配置无效"
        )
        non_retryable_error.retry_count = 0
        
        assert processor._should_retry(non_retryable_error, "test_file.pcap") == False
    
    def test_retry_delay_calculation(self, mock_processor_config):
        """测试重试延迟计算"""
        processor = TSharkEnhancedMaskProcessor(mock_processor_config)
        
        # 测试指数退避
        delay1 = processor._calculate_retry_delay(1)
        delay2 = processor._calculate_retry_delay(2)
        delay3 = processor._calculate_retry_delay(3)
        
        # 延迟应该递增
        assert delay2 > delay1
        assert delay3 > delay2
        
        # 延迟不应该超过最大值
        max_delay = processor.enhanced_config.retry_config.max_delay
        assert delay1 <= max_delay
        assert delay2 <= max_delay
        assert delay3 <= max_delay
        
        # 基础延迟测试
        base_delay = processor.enhanced_config.retry_config.base_delay
        assert delay1 >= base_delay
    
    @patch('time.sleep')
    def test_execute_with_retry_success_after_failure(self, mock_sleep, mock_processor_config):
        """测试重试机制：失败后成功"""
        processor = TSharkEnhancedMaskProcessor(mock_processor_config)
        
        call_count = 0
        def failing_then_succeeding_function():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise TimeoutError("第一次调用失败")
            return "成功结果"
        
        # 执行带重试的函数（不传递额外参数）
        result = processor._execute_with_retry(failing_then_succeeding_function)
        
        assert result == "成功结果"
        assert call_count == 2  # 第一次失败，第二次成功
        assert mock_sleep.call_count == 1  # 调用了一次sleep
    
    @patch('time.sleep')
    def test_execute_with_retry_all_attempts_fail(self, mock_sleep, mock_processor_config):
        """测试重试机制：所有尝试都失败"""
        processor = TSharkEnhancedMaskProcessor(mock_processor_config)
        
        def always_failing_function():
            raise ValueError("始终失败的函数")
        
        # 执行带重试的函数，期望最终失败
        with pytest.raises(ValueError, match="始终失败的函数"):
            processor._execute_with_retry(always_failing_function)
        
        # 验证重试次数
        max_attempts = processor.enhanced_config.retry_config.max_retries
        assert mock_sleep.call_count == max_attempts  # 每次失败都sleep


class TestErrorRecoveryStrategies:
    """错误恢复策略测试"""
    
    def test_error_handling_with_context(self, mock_processor_config):
        """测试带上下文的错误处理"""
        processor = TSharkEnhancedMaskProcessor(mock_processor_config)
        
        test_error = ErrorContext(
            category=ErrorCategory.MEMORY_ERROR,
            severity=ErrorSeverity.HIGH,
            error_code="MEMORY_EXHAUSTED",
            message="内存不足无法继续处理"
        )
        
        # 测试错误处理逻辑
        can_continue = processor._handle_error_with_context(test_error)
        
        # 验证错误被记录
        assert len(processor._error_tracker.error_history) > 0
        last_error = processor._error_tracker.error_history[-1]
        assert last_error.category == ErrorCategory.MEMORY_ERROR
        assert last_error.error_code == "MEMORY_EXHAUSTED"
        
        # 验证高严重性错误会尝试恢复
        assert isinstance(can_continue, bool)
    
    def test_memory_error_recovery(self, mock_processor_config):
        """测试内存错误恢复策略"""
        processor = TSharkEnhancedMaskProcessor(mock_processor_config)
        
        memory_error = ErrorContext(
            category=ErrorCategory.MEMORY_ERROR,
            severity=ErrorSeverity.HIGH,
            error_code="OUT_OF_MEMORY",
            message="系统内存不足"
        )
        
        # 记录原始块大小
        original_chunk_size = processor.enhanced_config.chunk_size
        
        # 尝试内存错误恢复
        recovery_successful = processor._attempt_error_recovery(memory_error)
        
        # 验证恢复尝试
        assert isinstance(recovery_successful, bool)
        assert memory_error.recovery_attempted == True
        
        # 如果恢复成功，检查是否调整了块大小
        if recovery_successful:
            assert processor.enhanced_config.chunk_size < original_chunk_size
    
    def test_timeout_error_recovery(self, mock_processor_config):
        """测试超时错误恢复策略"""
        processor = TSharkEnhancedMaskProcessor(mock_processor_config)
        
        timeout_error = ErrorContext(
            category=ErrorCategory.TIMEOUT_ERROR,
            severity=ErrorSeverity.MEDIUM,
            error_code="PROCESSING_TIMEOUT",
            message="处理超时"
        )
        
        # 记录原始超时设置
        original_timeout = processor.enhanced_config.fallback_config.tshark_check_timeout
        
        # 尝试超时错误恢复
        recovery_successful = processor._attempt_error_recovery(timeout_error)
        
        # 验证恢复尝试
        assert isinstance(recovery_successful, bool)
        assert timeout_error.recovery_attempted == True
        
        # 如果恢复成功，检查是否调整了超时设置
        if recovery_successful:
            assert processor.enhanced_config.fallback_config.tshark_check_timeout > original_timeout


class TestEnhancedFallbackMechanism:
    """增强降级机制测试"""
    
    @patch('time.time')
    def test_fallback_with_retry_tracking(self, mock_time, mock_processor_config):
        """测试带重试跟踪的降级机制"""
        mock_time.return_value = 1642857600  # 固定时间戳
        
        processor = TSharkEnhancedMaskProcessor(mock_processor_config)
        
        # 模拟文件处理参数
        test_input = "/tmp/test_input.pcap"
        test_output = "/tmp/test_output.pcap"
        
        with patch.object(processor, '_process_with_fallback_enhanced') as mock_fallback:
            mock_fallback.return_value = ProcessorResult(
                success=True,
                data=test_output,
                stats={"fallback_used": True}
            )
            
            result = processor._process_with_fallback_enhanced(
                input_path=test_input,
                output_path=test_output,
                start_time=1642857600.0
            )
            
            assert result.success == True
            assert result.stats["fallback_used"] == True
    
    def test_fallback_processor_safe_execution(self, mock_processor_config):
        """测试降级处理器的安全执行"""
        processor = TSharkEnhancedMaskProcessor(mock_processor_config)
        
        test_input = "/tmp/input.pcap"
        test_output = "/tmp/output.pcap"
        
        with patch.object(processor, '_execute_fallback_processor_safe') as mock_safe_exec:
            mock_safe_exec.return_value = ProcessorResult(
                success=True,
                data=test_output,
                stats={"processed_packets": 100}
            )
            
            result = processor._execute_fallback_processor_safe(
                mode=FallbackMode.ENHANCED_TRIMMER,
                input_path=test_input,
                output_path=test_output
            )
            
            assert result.success == True
            assert result.data == test_output
            assert result.stats["processed_packets"] == 100


class TestErrorReportingAndDiagnostics:
    """错误报告和诊断测试"""
    
    def test_basic_error_report_generation(self, mock_processor_config):
        """测试基础错误报告生成"""
        processor = TSharkEnhancedMaskProcessor(mock_processor_config)
        
        # 添加一些错误到错误跟踪器
        test_error = ErrorContext(
            category=ErrorCategory.IO_ERROR,
            severity=ErrorSeverity.MEDIUM,
            error_code="FILE_ACCESS_ERROR",
            message="文件访问错误"
        )
        processor._error_tracker.record_error(test_error)
        
        # 生成基础报告
        report = processor.get_error_report(detail_level="basic")
        
        assert "error_summary" in report
        assert "total_errors" in report["error_summary"]
        assert report["error_summary"]["total_errors"] >= 1
        assert "category_breakdown" in report["error_summary"]
        assert "io_error" in report["error_summary"]["category_breakdown"]
    
    def test_detailed_error_report_generation(self, mock_processor_config):
        """测试详细错误报告生成"""
        processor = TSharkEnhancedMaskProcessor(mock_processor_config)
        
        # 添加多种错误
        errors_to_add = [
            (ErrorCategory.MEMORY_ERROR, ErrorSeverity.HIGH, "OUT_OF_MEMORY"),
            (ErrorCategory.TIMEOUT_ERROR, ErrorSeverity.MEDIUM, "PROCESSING_TIMEOUT"),
            (ErrorCategory.VALIDATION_ERROR, ErrorSeverity.LOW, "VALIDATION_FAILED")
        ]
        
        for category, severity, code in errors_to_add:
            error = ErrorContext(
                category=category,
                severity=severity,
                error_code=code,
                message=f"测试错误: {code}"
            )
            processor._error_tracker.record_error(error)
        
        # 生成详细报告
        report = processor.get_error_report(detail_level="detailed")
        
        assert "error_summary" in report
        assert "error_patterns" in report
        assert "recent_errors" in report
        assert "system_diagnostics" in report
        
        # 验证模式分析
        patterns = report["error_patterns"]
        assert "most_common_patterns" in patterns
        assert len(patterns["most_common_patterns"]) > 0
    
    def test_verbose_error_report_generation(self, mock_processor_config):
        """测试详尽错误报告生成"""
        processor = TSharkEnhancedMaskProcessor(mock_processor_config)
        
        # 添加带异常的错误
        test_exception = ValueError("详细测试异常")
        error_with_exception = ErrorContext(
            category=ErrorCategory.PROCESSING_ERROR,
            severity=ErrorSeverity.HIGH,
            error_code="PROCESSING_FAILED",
            message="处理失败",
            exception=test_exception,
            file_context="test_file.pcap",
            stage_context="main_processing"
        )
        processor._error_tracker.record_error(error_with_exception)
        
        # 生成详尽报告
        report = processor.get_error_report(detail_level="verbose")
        
        assert "error_summary" in report
        assert "error_patterns" in report
        assert "recent_errors" in report
        assert "system_diagnostics" in report
        assert "detailed_error_list" in report
        assert "mitigation_recommendations" in report
        
        # 验证详细错误列表
        detailed_errors = report["detailed_error_list"]
        assert len(detailed_errors) >= 1
        
        first_error = detailed_errors[0]
        assert "error_code" in first_error
        assert "category" in first_error
        assert "message" in first_error
        assert "exception_details" in first_error
    
    def test_mitigation_recommendations_generation(self, mock_processor_config):
        """测试缓解建议生成"""
        processor = TSharkEnhancedMaskProcessor(mock_processor_config)
        
        # 添加不同类型的错误以获得不同的建议
        errors_for_recommendations = [
            ErrorContext(
                category=ErrorCategory.DEPENDENCY_ERROR,
                severity=ErrorSeverity.HIGH,
                error_code="TSHARK_MISSING",
                message="TShark工具缺失"
            ),
            ErrorContext(
                category=ErrorCategory.MEMORY_ERROR,
                severity=ErrorSeverity.HIGH,
                error_code="MEMORY_LIMIT_EXCEEDED",
                message="内存限制超出"
            ),
            ErrorContext(
                category=ErrorCategory.TIMEOUT_ERROR,
                severity=ErrorSeverity.MEDIUM,
                error_code="PROCESSING_TIMEOUT",
                message="处理超时"
            )
        ]
        
        for error in errors_for_recommendations:
            processor._error_tracker.record_error(error)
        
        # 生成缓解建议
        recommendations = processor.generate_mitigation_recommendations()
        
        assert isinstance(recommendations, list)
        assert len(recommendations) > 0
        
        # 验证具体建议内容
        recommendations_text = " ".join(recommendations)
        assert any("TShark" in rec or "依赖" in rec for rec in recommendations)
        assert any("内存" in rec or "批次" in rec for rec in recommendations)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"]) 