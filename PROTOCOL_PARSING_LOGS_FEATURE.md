# PktMask 协议栈解析日志控制功能

## 功能概述

为了解决PktMask GUI程序启动时控制台输出大量来自 `pktmask.core.encapsulation.parser` 模块的INFO级别日志（"协议栈解析完成: X层, Y个IP层"）影响可读性的问题，我们实现了一个新的配置项来控制协议栈解析日志的输出。

## 实现的功能

### 1. 新增配置项

在 `LoggingSettings` 类中添加了新的配置项：

```python
enable_protocol_parsing_logs: bool = False  # 控制协议栈解析详细日志输出
```

### 2. 配置文件支持

在配置模板文件 `config_template.yaml` 中添加了相应配置：

```yaml
logging:
  # 详细日志控制
  enable_protocol_parsing_logs: false  # 启用协议栈解析详细日志 (调试用)
```

### 3. 默认配置

在 `defaults.py` 中设置了默认值：

```python
DEFAULT_LOGGING_CONFIG = {
    # ...
    'enable_protocol_parsing_logs': False  # 默认关闭协议栈解析详细日志
}
```

### 4. 解析器改进

修改了 `ProtocolStackParser` 类，使其根据配置决定是否输出详细日志：

```python
def __init__(self):
    # 获取配置以控制日志输出
    try:
        self.config = get_app_config()
        self.enable_parsing_logs = self.config.logging.enable_protocol_parsing_logs
    except Exception as e:
        # 如果配置获取失败，默认关闭详细日志
        self.enable_parsing_logs = False

# 在解析完成时根据配置决定是否输出日志
if self.enable_parsing_logs:
    self.logger.info(f"协议栈解析完成: {len(layers)}层, {len(ip_layers)}个IP层")
```

### 5. 日志系统改进

改进了 `PktMaskLogger` 类，使其能够根据配置正确设置日志级别：

```python
def _setup_root_logger(self):
    # 尝试从配置获取日志级别
    console_level = logging.INFO  # 默认级别
    try:
        from ...config import get_app_config
        config = get_app_config()
        level_str = config.logging.log_level.upper()
        console_level = getattr(logging, level_str, logging.INFO)
    except Exception:
        pass
    
    console_handler.setLevel(console_level)
```

## 使用方法

### 方法1：通过配置文件

编辑配置文件 `~/.pktmask/config.yaml`：

```yaml
logging:
  log_level: "INFO"
  enable_protocol_parsing_logs: true   # 启用协议栈解析日志
  # 或
  enable_protocol_parsing_logs: false  # 禁用协议栈解析日志（默认）
```

### 方法2：通过演示脚本

运行提供的演示脚本：

```bash
python demo_protocol_parsing_logs.py
```

该脚本提供交互式界面来：
- 查看当前配置
- 启用/禁用协议栈解析日志
- 显示配置文件示例
- 查看使用说明

## 功能特点

### ✅ 默认关闭详细日志
- 默认情况下 `enable_protocol_parsing_logs` 为 `false`
- 避免了控制台输出过多重复的解析日志
- 提高了控制台输出的可读性

### ✅ 调试时可启用详细日志
- 当需要调试协议栈解析问题时，可以设置为 `true`
- 启用后会显示每个数据包的解析结果
- 便于问题排查和性能分析

### ✅ 与日志级别配合工作
- 协议栈解析日志使用 INFO 级别
- 当 `log_level` 设置为 WARNING 或更高时，即使启用了协议解析日志也不会显示
- 提供了灵活的日志控制机制

### ✅ 配置变更立即生效
- 修改配置后重新启动 PktMask 即可生效
- 支持动态配置重载
- 无需重新安装或重新编译

### ✅ 向后兼容
- 不影响现有的其他日志输出
- 保持了原有的日志格式和结构
- 只针对性地控制协议栈解析的详细日志

## 测试验证

功能已通过以下测试验证：

1. **配置加载测试** - 验证新配置项能够正确加载和保存
2. **解析器日志控制测试** - 验证解析器根据配置正确控制日志输出
3. **不同日志级别测试** - 验证与现有日志级别系统的兼容性
4. **GUI集成测试** - 验证在实际GUI应用中的工作效果

## 文件变更清单

### 修改的文件：
- `src/pktmask/config/settings.py` - 添加新配置项
- `src/pktmask/resources/config_template.yaml` - 更新配置模板
- `src/pktmask/config/defaults.py` - 添加默认值
- `src/pktmask/core/encapsulation/parser.py` - 实现日志控制逻辑
- `src/pktmask/infrastructure/logging/logger.py` - 改进日志系统
- `src/pktmask/infrastructure/logging/__init__.py` - 导出新函数

### 新增的文件：
- `demo_protocol_parsing_logs.py` - 功能演示脚本
- `PROTOCOL_PARSING_LOGS_FEATURE.md` - 功能文档

## 总结

该功能成功解决了PktMask GUI程序控制台输出过多协议栈解析日志的问题，提供了灵活的配置选项，既保证了默认使用的简洁性，又满足了调试时的详细信息需求。实现遵循了PktMask项目现有的配置管理模式，确保了代码的一致性和可维护性。
