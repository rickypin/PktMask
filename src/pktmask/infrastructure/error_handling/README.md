# PktMask 错误处理系统

## 概述

Phase 3错误处理重构为PktMask应用建立了统一、全面的异常处理机制。这个系统提供了自动错误恢复、详细的错误报告、上下文感知的错误处理等功能。

## 🏗️ 架构组件

### 1. 核心组件

| 组件 | 文件 | 功能 |
|------|------|------|
| 错误处理器 | `handler.py` | 统一的错误处理入口，支持自动恢复和用户通知 |
| 上下文管理 | `context.py` | 收集错误发生时的完整上下文信息 |
| 恢复管理 | `recovery.py` | 提供多种错误恢复策略（重试、跳过、备用方案） |
| 错误报告 | `reporter.py` | 生成详细错误报告，支持分析和导出 |
| 装饰器 | `decorators.py` | 提供便捷的装饰器用于不同场景 |
| 注册表 | `registry.py` | 管理错误处理器的注册和配置 |

### 2. 错误类型层次

```
Exception
└── PktMaskError (基础异常)
    ├── ConfigurationError (配置错误)
    ├── ProcessingError (处理错误)
    ├── ValidationError (验证错误)
    ├── FileError (文件错误)
    ├── NetworkError (网络错误)
    ├── UIError (界面错误)
    ├── PluginError (插件错误)
    ├── DependencyError (依赖错误)
    └── ResourceError (资源错误)
```

## 🚀 快速开始

### 基本使用

```python
from pktmask.infrastructure.error_handling import (
    handle_errors, get_error_handler, install_global_exception_handler
)

# 1. 安装全局异常处理器（推荐在应用启动时）
install_global_exception_handler()

# 2. 使用装饰器处理函数错误
@handle_errors(
    operation="file_processing",
    component="my_component",
    auto_recover=True,
    fallback_return_value=None
)
def process_file(file_path: str):
    # 处理文件的代码
    pass

# 3. 手动处理错误
error_handler = get_error_handler()
try:
    # 一些可能出错的代码
    pass
except Exception as e:
    recovery_result = error_handler.handle_exception(
        e, operation="manual_operation", component="my_component"
    )
```

### 使用上下文管理器

```python
from pktmask.infrastructure.error_handling import ErrorHandlingContext

with ErrorHandlingContext("batch_processing", "batch_processor"):
    # 在这个上下文中的任何错误都会被自动处理
    for file in files:
        process_file(file)
```

## 🔧 装饰器详解

### 1. `@handle_errors` - 通用错误处理

```python
@handle_errors(
    operation="custom_operation",      # 操作名称
    component="custom_component",      # 组件名称
    auto_recover=True,                 # 是否自动恢复
    reraise_on_failure=False,         # 恢复失败时是否重新抛出
    fallback_return_value=None,       # 失败时的返回值
    log_success=True                   # 是否记录成功日志
)
def my_function():
    pass
```

### 2. `@handle_gui_errors` - GUI错误处理

```python
@handle_gui_errors(
    component="main_window",
    show_user_dialog=True,
    fallback_return_value=False
)
def on_button_click(self):
    pass
```

### 3. `@handle_processing_errors` - 处理步骤错误

```python
@handle_processing_errors(
    step_name="deduplication",
    file_path_arg="input_file",
    skip_on_error=True,
    max_retries=3
)
def deduplicate_packets(input_file, output_file):
    pass
```

### 4. `@handle_config_errors` - 配置错误处理

```python
@handle_config_errors(
    config_key="window_size",
    use_defaults=True,
    default_value=(800, 600)
)
def get_window_size():
    pass
```

## 🔄 错误恢复策略

系统支持多种恢复策略：

| 策略 | 说明 | 适用场景 |
|------|------|----------|
| `RETRY` | 重试操作 | 网络请求、临时性错误 |
| `SKIP` | 跳过当前项 | 批量处理中的单个失败项 |
| `FALLBACK` | 使用备用方法 | 主要方法失败时的替代方案 |
| `USER_PROMPT` | 提示用户决定 | 需要用户干预的错误 |
| `CONTINUE` | 继续执行 | 非关键错误 |
| `ABORT` | 中止操作 | 严重错误 |

### 自定义恢复处理器

```python
from pktmask.infrastructure.error_handling.recovery import RecoveryHandler, RecoveryStrategy

class CustomRecoveryHandler(RecoveryHandler):
    @property
    def strategy(self) -> RecoveryStrategy:
        return RecoveryStrategy.FALLBACK
    
    def can_handle(self, error: PktMaskError, context: ErrorContext) -> bool:
        return isinstance(error, MyCustomError)
    
    def recover(self, error: PktMaskError, context: ErrorContext) -> RecoveryResult:
        # 自定义恢复逻辑
        pass

# 注册自定义处理器
from pktmask.infrastructure.error_handling import get_recovery_manager
recovery_manager = get_recovery_manager()
recovery_manager.register_handler(CustomRecoveryHandler())
```

## 📊 错误报告和分析

### 获取错误统计

```python
from pktmask.infrastructure.error_handling import get_error_handler

error_handler = get_error_handler()
stats = error_handler.get_error_stats()

print(f"总错误数: {stats['total_errors']}")
print(f"已恢复错误: {stats['recovered_errors']}")
print(f"严重性分布: {stats['severity_counts']}")
```

### 生成错误报告

```python
from pktmask.infrastructure.error_handling import get_error_reporter

error_reporter = get_error_reporter()

# 获取最近的错误报告
recent_reports = error_reporter.get_recent_reports(limit=10)

# 生成汇总报告
summary = error_reporter.generate_summary_report(time_range_hours=24)

# 导出报告
error_reporter.export_reports(Path("error_reports.json"))
```

## 🎯 错误上下文信息

错误上下文自动收集以下信息：

- **基本信息**: 时间戳、线程信息
- **异常信息**: 异常类型、消息、堆栈跟踪
- **应用状态**: 当前操作、组件、文件路径、用户操作
- **系统信息**: Python版本、平台、当前目录
- **性能信息**: 内存使用、CPU占用
- **用户环境**: 配置值、最近操作历史

### 添加自定义上下文

```python
from pktmask.infrastructure.error_handling import (
    set_current_operation, set_current_component, add_recent_action
)

# 设置操作上下文
set_current_operation("file_processing")
set_current_component("file_processor")

# 添加用户操作记录
add_recent_action("User clicked process button")
add_recent_action("Started file validation")
```

## ⚙️ 配置和自定义

### 错误处理器配置

```python
from pktmask.infrastructure.error_handling import get_error_handler

error_handler = get_error_handler()

# 配置错误处理行为
error_handler.set_auto_recovery_enabled(True)
error_handler.set_user_notification_enabled(True)
error_handler.set_detailed_logging_enabled(True)

# 注册错误回调
def custom_error_callback(error, context, recovery_result):
    print(f"Custom handling for error: {error}")

error_handler.register_error_callback(custom_error_callback)
```

### 错误报告配置

```python
from pktmask.infrastructure.error_handling import get_error_reporter

error_reporter = get_error_reporter()

# 配置报告生成
error_reporter.max_reports_to_keep = 200
error_reporter.enable_detailed_reports = True
error_reporter.enable_summary_reports = True
```

## 📝 最佳实践

### 1. 错误处理层次

```python
# 应用级别 - 使用全局异常处理器
install_global_exception_handler()

# 组件级别 - 使用装饰器
@handle_errors(component="my_component")
def component_method():
    pass

# 操作级别 - 使用上下文管理器
with ErrorHandlingContext("critical_operation"):
    # 关键操作
    pass

# 细粒度 - 手动处理
try:
    risky_operation()
except SpecificError as e:
    handle_error(e, operation="specific_task")
```

### 2. 错误分类

```python
# 根据错误类型使用合适的处理方式
@handle_gui_errors(component="main_window")  # GUI错误
def ui_operation():
    pass

@handle_processing_errors(step_name="validation")  # 处理错误
def validate_data():
    pass

@handle_config_errors(config_key="database_url")  # 配置错误
def connect_database():
    pass
```

### 3. 恢复策略选择

- **网络操作**: 使用重试策略
- **文件处理**: 使用跳过策略
- **用户操作**: 使用用户提示策略
- **配置加载**: 使用备用方案策略

### 4. 性能考虑

- 错误处理会增加一些开销，在性能关键路径上谨慎使用
- 大量重试可能导致性能问题，设置合理的重试次数和延迟
- 错误报告会写入文件，高频错误可能影响I/O性能

## 🧪 测试

运行错误处理系统测试：

```bash
python test_error_handling.py
```

测试覆盖以下功能：
- 基本错误处理
- 装饰器功能
- 上下文管理器
- 错误恢复
- 错误报告
- 全局异常处理
- 错误统计

## 🔮 未来扩展

可能的扩展方向：

1. **智能恢复**: 基于机器学习的错误模式识别和自动恢复
2. **远程报告**: 将错误报告发送到远程服务器进行集中分析
3. **用户反馈**: 集成用户反馈机制，改进错误处理策略
4. **性能监控**: 集成APM工具，监控错误对性能的影响
5. **A/B测试**: 测试不同错误处理策略的效果

## 📚 相关文档

- [异常定义文档](../../common/exceptions.py)
- [日志系统文档](../logging/README.md)
- [配置系统文档](../../config/README.md) 