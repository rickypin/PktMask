# 适配器异常处理机制设计

## 1. 设计目标

- **统一性**：所有适配器使用相同的异常层次结构
- **可追溯性**：异常信息包含足够的上下文便于调试
- **降级处理**：提供合理的默认行为避免程序崩溃
- **向后兼容**：保持与现有代码的兼容性

## 2. 异常层次结构

```python
Exception
└── AdapterError                    # 适配器基础异常
    ├── ConfigurationError          # 配置相关异常
    │   ├── MissingConfigError      # 缺少必要配置
    │   └── InvalidConfigError      # 配置格式错误
    ├── DataFormatError             # 数据格式异常
    │   ├── InputFormatError        # 输入格式错误
    │   └── OutputFormatError       # 输出格式错误
    ├── CompatibilityError          # 兼容性异常
    │   ├── VersionMismatchError    # 版本不匹配
    │   └── FeatureNotSupportedError # 功能不支持
    └── ProcessingError             # 处理过程异常
        ├── TimeoutError            # 处理超时
        └── ResourceError           # 资源不足
```

## 3. 异常类实现

```python
"""
适配器异常定义

提供适配器模块统一的异常处理机制。
"""

from typing import Optional, Dict, Any


class AdapterError(Exception):
    """
    适配器基础异常类
    
    所有适配器异常的基类，提供统一的错误信息格式。
    
    Attributes:
        message: 错误消息
        error_code: 错误代码
        context: 额外的上下文信息
    """
    
    def __init__(self, 
                 message: str, 
                 error_code: Optional[str] = None,
                 context: Optional[Dict[str, Any]] = None):
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.context = context or {}
        super().__init__(self.format_message())
    
    def format_message(self) -> str:
        """格式化错误消息"""
        base_msg = f"[{self.error_code}] {self.message}"
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{base_msg} (Context: {context_str})"
        return base_msg


class ConfigurationError(AdapterError):
    """配置相关异常"""
    pass


class MissingConfigError(ConfigurationError):
    """缺少必要配置"""
    
    def __init__(self, config_key: str, adapter_name: str):
        super().__init__(
            f"Missing required configuration: {config_key}",
            context={"adapter": adapter_name, "missing_key": config_key}
        )


class InvalidConfigError(ConfigurationError):
    """配置格式错误"""
    
    def __init__(self, config_key: str, expected_type: str, actual_value: Any):
        super().__init__(
            f"Invalid configuration value for {config_key}",
            context={
                "key": config_key,
                "expected_type": expected_type,
                "actual_value": str(actual_value)
            }
        )


class DataFormatError(AdapterError):
    """数据格式异常"""
    pass


class InputFormatError(DataFormatError):
    """输入数据格式错误"""
    
    def __init__(self, expected_format: str, actual_format: str = "unknown"):
        super().__init__(
            f"Invalid input format",
            context={
                "expected": expected_format,
                "actual": actual_format
            }
        )


class OutputFormatError(DataFormatError):
    """输出数据格式错误"""
    pass


class CompatibilityError(AdapterError):
    """兼容性异常"""
    pass


class VersionMismatchError(CompatibilityError):
    """版本不匹配"""
    
    def __init__(self, required_version: str, current_version: str):
        super().__init__(
            f"Version mismatch",
            context={
                "required": required_version,
                "current": current_version
            }
        )


class FeatureNotSupportedError(CompatibilityError):
    """功能不支持"""
    
    def __init__(self, feature_name: str, adapter_name: str):
        super().__init__(
            f"Feature not supported: {feature_name}",
            context={
                "feature": feature_name,
                "adapter": adapter_name
            }
        )


class ProcessingError(AdapterError):
    """处理过程异常"""
    pass


class TimeoutError(ProcessingError):
    """处理超时"""
    
    def __init__(self, operation: str, timeout_seconds: float):
        super().__init__(
            f"Operation timed out: {operation}",
            context={
                "operation": operation,
                "timeout": f"{timeout_seconds}s"
            }
        )


class ResourceError(ProcessingError):
    """资源不足"""
    
    def __init__(self, resource_type: str, details: str = ""):
        super().__init__(
            f"Insufficient {resource_type}",
            context={
                "resource": resource_type,
                "details": details
            }
        )
```

## 4. 使用示例

### 4.1 抛出异常
```python
from pktmask.adapters.exceptions import (
    MissingConfigError, 
    InputFormatError,
    TimeoutError
)

class EventAdapter:
    def __init__(self, config: Dict[str, Any]):
        if "format_version" not in config:
            raise MissingConfigError("format_version", "EventAdapter")
        
        self.format_version = config["format_version"]
    
    def adapt_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        # 验证输入格式
        if not isinstance(event_data, dict):
            raise InputFormatError(
                expected_format="dict",
                actual_format=type(event_data).__name__
            )
        
        # 模拟超时情况
        if self._is_timeout():
            raise TimeoutError("event_adaptation", 30.0)
        
        # 适配逻辑...
        return adapted_data
```

### 4.2 捕获和处理异常
```python
from pktmask.adapters.exceptions import AdapterError, ConfigurationError

try:
    adapter = EventAdapter(config)
    result = adapter.adapt_event(data)
except ConfigurationError as e:
    # 配置错误，记录并使用默认配置
    logger.error(f"Configuration error: {e}")
    adapter = EventAdapter(DEFAULT_CONFIG)
except AdapterError as e:
    # 其他适配器错误，记录并返回原始数据
    logger.warning(f"Adapter error: {e}")
    result = data  # 降级处理
except Exception as e:
    # 未预期的错误
    logger.exception("Unexpected error in adapter")
    raise
```

## 5. 日志集成

### 5.1 异常日志记录
```python
import logging
from functools import wraps

logger = logging.getLogger(__name__)

def log_adapter_errors(func):
    """装饰器：自动记录适配器异常"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except AdapterError as e:
            logger.error(
                f"Adapter error in {func.__name__}: {e}",
                extra={
                    "error_code": e.error_code,
                    "context": e.context
                }
            )
            raise
        except Exception as e:
            logger.exception(f"Unexpected error in {func.__name__}")
            raise
    return wrapper

class ProcessorAdapter:
    @log_adapter_errors
    def adapt_processor_to_stage(self, processor):
        # 适配逻辑...
        pass
```

## 6. 测试策略

### 6.1 异常测试模板
```python
import pytest
from pktmask.adapters.exceptions import *

class TestAdapterExceptions:
    def test_missing_config_error(self):
        """测试缺少配置异常"""
        with pytest.raises(MissingConfigError) as exc_info:
            raise MissingConfigError("api_key", "TestAdapter")
        
        error = exc_info.value
        assert "api_key" in str(error)
        assert error.context["adapter"] == "TestAdapter"
        assert error.context["missing_key"] == "api_key"
    
    def test_input_format_error(self):
        """测试输入格式异常"""
        with pytest.raises(InputFormatError) as exc_info:
            raise InputFormatError("json", "xml")
        
        error = exc_info.value
        assert error.context["expected"] == "json"
        assert error.context["actual"] == "xml"
    
    def test_exception_hierarchy(self):
        """测试异常层次结构"""
        assert issubclass(MissingConfigError, ConfigurationError)
        assert issubclass(ConfigurationError, AdapterError)
        assert issubclass(AdapterError, Exception)
```

## 7. 向后兼容策略

### 7.1 渐进式迁移
```python
# 旧代码兼容层
def legacy_error_handler(func):
    """将新异常转换为旧异常格式"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except AdapterError as e:
            # 转换为旧的异常格式
            if isinstance(e, ConfigurationError):
                raise ValueError(f"Config error: {e.message}")
            elif isinstance(e, DataFormatError):
                raise TypeError(f"Format error: {e.message}")
            else:
                raise RuntimeError(str(e))
    return wrapper
```

### 7.2 废弃警告
```python
import warnings

class OldStyleAdapter:
    def process(self, data):
        warnings.warn(
            "OldStyleAdapter is deprecated. "
            "Please use the new adapter with proper exception handling.",
            DeprecationWarning,
            stacklevel=2
        )
        # 旧逻辑...
```

## 8. 最佳实践

1. **具体化异常**：使用具体的异常类型而不是通用的 `AdapterError`
2. **提供上下文**：异常中包含足够的上下文信息便于调试
3. **合理降级**：在可能的情况下提供降级处理方案
4. **记录日志**：所有异常都应该被记录
5. **测试覆盖**：为每种异常情况编写测试用例
