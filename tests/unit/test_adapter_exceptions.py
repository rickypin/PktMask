"""
适配器异常测试

测试适配器异常类的功能和行为。
"""

import pytest
from pktmask.adapters.adapter_exceptions import (
    AdapterError,
    ConfigurationError,
    MissingConfigError,
    InvalidConfigError,
    DataFormatError,
    InputFormatError,
    OutputFormatError,
    CompatibilityError,
    VersionMismatchError,
    FeatureNotSupportedError,
    ProcessingError,
    TimeoutError,
    ResourceError
)


class TestAdapterExceptions:
    """测试适配器异常类"""
    
    def test_base_adapter_error(self):
        """测试基础适配器异常"""
        # 测试默认参数
        error = AdapterError("Test error message")
        assert str(error) == "[AdapterError] Test error message"
        assert error.message == "Test error message"
        assert error.error_code == "AdapterError"
        assert error.context == {}
        
        # 测试自定义参数
        error = AdapterError(
            "Custom error",
            error_code="CUSTOM_001",
            context={"file": "test.py", "line": 42}
        )
        assert "[CUSTOM_001]" in str(error)
        assert "file=test.py" in str(error)
        assert "line=42" in str(error)
    
    def test_missing_config_error(self):
        """测试缺少配置异常"""
        error = MissingConfigError("api_key", "TestAdapter")
        
        assert "Missing required configuration: api_key" in str(error)
        assert error.context["adapter"] == "TestAdapter"
        assert error.context["missing_key"] == "api_key"
        assert isinstance(error, ConfigurationError)
        assert isinstance(error, AdapterError)
    
    def test_invalid_config_error(self):
        """测试配置格式错误异常"""
        error = InvalidConfigError("port", "int", "abc")
        
        assert "Invalid configuration value for port" in str(error)
        assert error.context["key"] == "port"
        assert error.context["expected_type"] == "int"
        assert error.context["actual_value"] == "abc"
    
    def test_input_format_error(self):
        """测试输入格式错误异常"""
        error = InputFormatError("json", "xml")
        
        assert "Invalid input format" in str(error)
        assert error.context["expected"] == "json"
        assert error.context["actual"] == "xml"
        assert isinstance(error, DataFormatError)
        
        # 测试默认实际格式
        error = InputFormatError("json")
        assert error.context["actual"] == "unknown"
    
    def test_version_mismatch_error(self):
        """测试版本不匹配异常"""
        error = VersionMismatchError("2.0", "1.5")
        
        assert "Version mismatch" in str(error)
        assert error.context["required"] == "2.0"
        assert error.context["current"] == "1.5"
        assert isinstance(error, CompatibilityError)
    
    def test_feature_not_supported_error(self):
        """测试功能不支持异常"""
        error = FeatureNotSupportedError("async_processing", "LegacyAdapter")
        
        assert "Feature not supported: async_processing" in str(error)
        assert error.context["feature"] == "async_processing"
        assert error.context["adapter"] == "LegacyAdapter"
    
    def test_timeout_error(self):
        """测试超时异常"""
        error = TimeoutError("data_processing", 30.5)
        
        assert "Operation timed out: data_processing" in str(error)
        assert error.context["operation"] == "data_processing"
        assert error.context["timeout"] == "30.5s"
        assert isinstance(error, ProcessingError)
    
    def test_resource_error(self):
        """测试资源不足异常"""
        error = ResourceError("memory", "需要至少 4GB")
        
        assert "Insufficient memory" in str(error)
        assert error.context["resource"] == "memory"
        assert error.context["details"] == "需要至少 4GB"
        
        # 测试无详情的情况
        error = ResourceError("disk_space")
        assert error.context["details"] == ""
    
    def test_exception_hierarchy(self):
        """测试异常层次结构"""
        # 配置异常层次
        assert issubclass(MissingConfigError, ConfigurationError)
        assert issubclass(InvalidConfigError, ConfigurationError)
        assert issubclass(ConfigurationError, AdapterError)
        
        # 数据格式异常层次
        assert issubclass(InputFormatError, DataFormatError)
        assert issubclass(OutputFormatError, DataFormatError)
        assert issubclass(DataFormatError, AdapterError)
        
        # 兼容性异常层次
        assert issubclass(VersionMismatchError, CompatibilityError)
        assert issubclass(FeatureNotSupportedError, CompatibilityError)
        assert issubclass(CompatibilityError, AdapterError)
        
        # 处理异常层次
        assert issubclass(TimeoutError, ProcessingError)
        assert issubclass(ResourceError, ProcessingError)
        assert issubclass(ProcessingError, AdapterError)
        
        # 基础异常层次
        assert issubclass(AdapterError, Exception)
    
    def test_exception_catching(self):
        """测试异常捕获"""
        # 可以通过基类捕获所有适配器异常
        try:
            raise MissingConfigError("test_key", "TestAdapter")
        except AdapterError as e:
            assert isinstance(e, MissingConfigError)
            assert "test_key" in str(e)
        
        # 可以通过中间类捕获特定类型的异常
        try:
            raise InputFormatError("yaml", "json")
        except DataFormatError as e:
            assert isinstance(e, InputFormatError)
            assert e.context["expected"] == "yaml"
    
    def test_context_serialization(self):
        """测试上下文信息序列化"""
        import json
        
        error = AdapterError(
            "Test error",
            context={
                "number": 42,
                "string": "test",
                "list": [1, 2, 3],
                "dict": {"nested": "value"}
            }
        )
        
        # 验证上下文可以被序列化
        context_json = json.dumps(error.context)
        assert context_json is not None
        
        # 验证反序列化
        loaded_context = json.loads(context_json)
        assert loaded_context == error.context


class TestExceptionUsagePatterns:
    """测试异常使用模式"""
    
    def test_adapter_with_exception_handling(self):
        """测试适配器中的异常处理"""
        class TestAdapter:
            def __init__(self, config):
                if "required_field" not in config:
                    raise MissingConfigError("required_field", "TestAdapter")
                self.config = config
            
            def process(self, data):
                if not isinstance(data, dict):
                    raise InputFormatError("dict", type(data).__name__)
                return {"processed": True}
        
        # 测试配置错误
        with pytest.raises(MissingConfigError):
            TestAdapter({})
        
        # 测试正常初始化和处理
        adapter = TestAdapter({"required_field": "value"})
        result = adapter.process({"input": "data"})
        assert result["processed"] is True
        
        # 测试输入格式错误
        with pytest.raises(InputFormatError):
            adapter.process("invalid")
    
    def test_exception_chaining(self):
        """测试异常链"""
        try:
            try:
                raise ValueError("Original error")
            except ValueError as e:
                raise AdapterError("Wrapped error") from e
        except AdapterError as e:
            assert e.__cause__ is not None
            assert isinstance(e.__cause__, ValueError)
            assert str(e.__cause__) == "Original error"
