# PktMask 适配器使用指南

## 概述

适配器（Adapter）是 PktMask 中用于连接不同组件和保证向后兼容的重要模块。本指南详细介绍如何使用各种适配器。

## 目录结构

自 2025 年 1 月重构后，所有适配器统一存放在 `src/pktmask/adapters/` 目录下：

```
src/pktmask/adapters/
├── __init__.py                    # 统一导出接口
├── adapter_exceptions.py          # 异常类定义
├── processor_adapter.py           # 处理器适配器
├── event_adapter.py              # 事件数据适配器
├── statistics_adapter.py         # 统计数据适配器
├── encapsulation_adapter.py      # 封装处理适配器
└── compatibility/                # 兼容性适配器
    ├── __init__.py
    ├── anon_compat.py           # 匿名化兼容
    └── dedup_compat.py          # 去重兼容
```

## 核心适配器

### 1. 混合架构状态说明

**重要说明**: PktMask当前处于架构迁移的中间状态，存在两套并行的处理系统：

#### ✅ 已迁移到StageBase的组件
```python
from pktmask.core.pipeline.stages.mask_payload_v2.stage import NewMaskPayloadStage

# 载荷掩码已完全迁移到StageBase架构
mask_stage = NewMaskPayloadStage()
mask_stage.initialize(config)
```

#### 🔄 仍使用BaseProcessor的组件
```python
from pktmask.core.processors.ip_anonymizer import IPAnonymizer
from pktmask.core.processors.deduplicator import Deduplicator

# IP匿名化和去重仍使用BaseProcessor架构
anonymizer = IPAnonymizer(config)
deduplicator = Deduplicator(config)
```

#### 🔧 统一访问接口（推荐）
```python
from pktmask.core.processors.registry import ProcessorRegistry

# 通过ProcessorRegistry统一访问新旧架构
anonymizer = ProcessorRegistry.get_processor('anonymize_ips')
deduplicator = ProcessorRegistry.get_processor('remove_dupes')
masker = ProcessorRegistry.get_processor('mask_payloads')  # 实际返回NewMaskPayloadStage
```

### 2. EventDataAdapter

在新旧事件数据格式之间转换。

```python
from pktmask.adapters import EventDataAdapter
from pktmask.core.events import PipelineEvents

adapter = EventDataAdapter()

# 旧格式 -> 新格式
legacy_event = {
    'message': 'Processing started',
    'total_files': 100
}
new_event = adapter.from_legacy_dict(
    PipelineEvents.PIPELINE_START, 
    legacy_event
)

# 新格式 -> 旧格式
legacy_dict = adapter.to_legacy_dict(new_event)
```

### 3. StatisticsDataAdapter

转换统计数据格式。

```python
from pktmask.adapters import StatisticsDataAdapter

adapter = StatisticsDataAdapter()

# 从旧的 StatisticsManager 转换
stats_data = adapter.from_legacy_manager(legacy_manager)

# 更新旧的 manager
adapter.update_legacy_manager(legacy_manager, stats_data)

# 合并统计数据
updated_stats = adapter.merge_statistics(base_stats, update_dict)
```

### 4. ProcessingAdapter (EncapsulationAdapter)

处理复杂的封装协议。

```python
from pktmask.adapters import ProcessingAdapter
from scapy.all import rdpcap

adapter = ProcessingAdapter()

# 分析数据包的 IP 层
packet = rdpcap("sample.pcap")[0]
ip_analysis = adapter.analyze_packet_for_ip_processing(packet)

# 提取需要匿名化的 IP
ip_pairs = adapter.extract_ips_for_anonymization(ip_analysis)

# 分析载荷信息
payload_analysis = adapter.analyze_packet_for_payload_processing(packet)
```

## 架构迁移状态

### 当前迁移进度

#### ✅ 已完成迁移的功能
- **载荷掩码**: `NewMaskPayloadStage` (StageBase架构)
  - 双模块设计（Marker + Masker）
  - 完全兼容StageBase接口
  - 生产就绪状态

#### 🔄 待迁移的功能
- **IP匿名化**: `IPAnonymizer` (BaseProcessor架构)
  - 功能: 前缀保持匿名化、目录级映射构建
  - 状态: 待迁移到StageBase
  - 临时访问: 通过ProcessorRegistry

- **去重处理**: `Deduplicator` (BaseProcessor架构)
  - 功能: 数据包去重、哈希计算、统计分析
  - 状态: 待迁移到StageBase
  - 临时访问: 通过ProcessorRegistry

### 迁移建议

```python
# 当前推荐的使用方式（通过统一接口）
from pktmask.core.pipeline.executor import PipelineExecutor

config = {
    'anonymize_ips': {'enabled': True},
    'remove_dupes': {'enabled': True},
    'mask_payloads': {'enabled': True}
}

# PipelineExecutor自动处理新旧架构的差异
executor = PipelineExecutor(config)
result = executor.run(input_path, output_path)
```

## 异常处理

适配器模块提供了统一的异常层次结构：

```python
from pktmask.adapters.adapter_exceptions import (
    AdapterError,
    MissingConfigError,
    InputFormatError,
    TimeoutError
)

try:
    # 使用适配器
    adapter = SomeAdapter(config)
    result = adapter.process(data)
except MissingConfigError as e:
    print(f"配置缺失: {e.context['missing_key']}")
except InputFormatError as e:
    print(f"格式错误: 期望 {e.context['expected']}")
except AdapterError as e:
    # 捕获所有适配器相关异常
    print(f"适配器错误: {e}")
```

## 迁移指南

### 从旧导入路径迁移

旧的导入路径仍然可用但会产生废弃警告：

```python
# 旧路径（不推荐）
from pktmask.core.adapters.processor_adapter import ProcessorAdapter
from pktmask.domain.adapters.event_adapter import EventDataAdapter

# 新路径（推荐）
from pktmask.adapters import (
    PipelineProcessorAdapter,
    EventDataAdapter,
    StatisticsDataAdapter
)
```

### 批量导入

可以一次导入所有常用的适配器：

```python
from pktmask.adapters import (
    # 核心适配器
    PipelineProcessorAdapter,
    ProcessingAdapter,
    EventDataAdapter,
    StatisticsDataAdapter,
    
    # 兼容性适配器
    IpAnonymizationStageCompat,
    DeduplicationStageCompat,
    
    # 异常类
    AdapterError,
    ConfigurationError,
    DataFormatError
)
```

## 最佳实践

1. **优先使用新接口**：尽可能使用新的适配器接口，避免依赖兼容层。

2. **异常处理**：始终捕获并处理适配器异常。

3. **配置验证**：在初始化时验证配置完整性。

4. **日志记录**：适配器会自动记录重要操作，确保日志级别正确设置。

5. **性能考虑**：
   - 重用适配器实例而不是频繁创建
   - 对于批量操作，使用适当的批处理方法

## 示例项目

完整的使用示例可以在以下位置找到：
- `examples/adapter_basic_usage.py`
- `examples/adapter_migration.py`
- `tests/unit/test_adapter_*.py`

## 故障排除

### 常见问题

1. **ImportError**: 确保使用正确的导入路径
2. **DeprecationWarning**: 更新到新的导入路径
3. **ConfigurationError**: 检查必需的配置项
4. **循环导入**: 避免从 `pktmask.domain` 导入适配器

### 调试技巧

```python
# 启用详细日志
import logging
logging.getLogger('pktmask.adapters').setLevel(logging.DEBUG)

# 检查适配器版本
from pktmask.adapters import __version__
print(f"Adapters version: {__version__}")
```

## 更新日志

- **v1.0.0** (2025-01-09): 统一适配器目录结构，添加异常处理机制
- **v0.9.x**: 分散在各个模块中的适配器实现

## 相关文档

- [适配器架构设计](./refactoring/adapter_refactoring_plan.md)
- [异常处理设计](./refactoring/adapter_exception_design.md)
- [命名规范](./refactoring/adapter_naming_convention.md)
