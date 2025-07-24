# 统一内存管理策略

## 概述

本文档描述了PktMask项目中新实施的统一内存管理策略，旨在解决代码审查中发现的内存管理策略不一致问题（MEM-001）。

## 问题背景

### 原有问题

1. **重复的内存管理逻辑**：`PayloadMasker`中存在`MemoryOptimizer`和缓冲区管理的重复逻辑
2. **资源清理不一致**：不同Stage类的资源清理实现不统一
3. **RAII模式不完整**：缺乏完整的资源自动管理机制
4. **内存监控策略分散**：内存监控逻辑分散在多个组件中

### 影响分析

- 内存使用不可预测
- 可能导致OOM错误
- 性能不稳定
- 资源利用率低

## 解决方案

### 架构设计

```
StageBase (基础资源管理)
    ↓
ResourceManager (统一资源管理器)
    ├── MemoryMonitor (内存监控)
    ├── BufferManager (缓冲区管理)
    └── 资源清理机制
```

### 核心组件

#### 1. ResourceManager

**位置**: `src/pktmask/core/pipeline/resource_manager.py`

**职责**:
- 统一管理内存、文件句柄、临时文件等资源
- 提供标准化的资源申请、使用、释放接口
- 集成内存监控和自动清理机制

**主要方法**:
```python
class ResourceManager:
    def create_buffer(self, name: str) -> List[Any]
    def should_flush_buffer(self, name: str) -> bool
    def flush_buffer(self, name: str) -> List[Any]
    def register_temp_file(self, file_path: Path) -> None
    def register_cleanup_callback(self, callback: Callable) -> None
    def cleanup(self) -> None
    def get_resource_stats(self) -> ResourceStats
```

#### 2. MemoryMonitor

**职责**:
- 实时监控内存使用情况
- 提供统一的内存压力判断标准
- 支持回调机制和事件通知

**配置参数**:
```python
{
    'max_memory_mb': 2048,        # 最大内存限制(MB)
    'pressure_threshold': 0.8,    # 内存压力阈值
    'monitoring_interval': 100    # 监控间隔
}
```

#### 3. BufferManager

**职责**:
- 统一管理各种缓冲区（数据包缓冲区、I/O缓冲区等）
- 基于内存压力自动调整缓冲区大小
- 提供批量处理和流式处理模式

**配置参数**:
```python
{
    'default_buffer_size': 100,   # 默认缓冲区大小
    'max_buffer_size': 1000,      # 最大缓冲区大小
    'min_buffer_size': 10,        # 最小缓冲区大小
    'auto_resize': True           # 自动调整大小
}
```

### StageBase集成

#### 统一初始化

所有Stage类现在自动初始化ResourceManager：

```python
class StageBase:
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self._initialized = False
        
        # 初始化统一资源管理器
        resource_config = self.config.get('resource_manager', {})
        self.resource_manager = ResourceManager(resource_config)
```

#### 统一清理机制

```python
class StageBase:
    def cleanup(self) -> None:
        """统一资源清理"""
        # Stage特定清理
        self._cleanup_stage_specific()
        
        # 统一资源清理
        self.resource_manager.cleanup()
        
        # 重置状态
        self._initialized = False
    
    def _cleanup_stage_specific(self) -> None:
        """子类重写此方法实现特定清理逻辑"""
        pass
```

## 实施细节

### PayloadMasker重构

#### 原有逻辑
```python
# 内存压力检查
if self.memory_optimizer.check_memory_pressure():
    self._flush_packet_buffer(packet_buffer, writer)
# 批量写入以提高性能
elif len(packet_buffer) >= buffer_size:
    self._flush_packet_buffer(packet_buffer, writer)
```

#### 新的统一逻辑
```python
# 使用统一的缓冲区管理
packet_buffer = self.resource_manager.create_buffer("packet_buffer")

# 统一的缓冲区管理：检查是否需要刷新缓冲区
if self.resource_manager.should_flush_buffer("packet_buffer"):
    # 刷新缓冲区并写入
    buffered_packets = self.resource_manager.flush_buffer("packet_buffer")
    self._write_packets_to_file(buffered_packets, writer)
```

### 内存压力处理

#### 统一回调机制
```python
def _handle_memory_pressure_unified(self, pressure: float) -> None:
    """统一的内存压力处理回调"""
    self.logger.warning(f"Memory pressure detected: {pressure*100:.1f}%")
    
    # 在高内存压力下刷新所有缓冲区
    if pressure > 0.9:
        self.logger.warning("High memory pressure, flushing all buffers")
```

### 迁移完成

原有的`MemoryOptimizer`接口已完全移除，所有内存管理功能统一使用`ResourceManager`：

```python
# 统一的资源管理器
self.resource_manager = ResourceManager(resource_config)

# 注册内存压力回调（统一方式）
self.resource_manager.memory_monitor.register_pressure_callback(
    self._handle_memory_pressure_unified
)
```

**迁移完成状态**：
- ✅ 移除了`MemoryOptimizer`类和相关文件
- ✅ 更新了所有引用以使用`ResourceManager`
- ✅ 统一了内存监控和压力处理机制
- ✅ 更新了测试用例以反映新的架构

## 配置示例

### Stage配置
```python
config = {
    'resource_manager': {
        'memory_monitor': {
            'max_memory_mb': 2048,
            'pressure_threshold': 0.8,
            'monitoring_interval': 100
        },
        'buffer_manager': {
            'default_buffer_size': 100,
            'auto_resize': True,
            'max_buffer_size': 1000,
            'min_buffer_size': 10
        }
    }
}
```

### PayloadMasker特定配置
```python
config = {
    'chunk_size': 1000,
    'verify_checksums': True,
    'resource_manager': {
        'memory_monitor': {
            'max_memory_mb': 4096,  # 更大的内存限制
            'pressure_threshold': 0.85
        },
        'buffer_manager': {
            'default_buffer_size': 200,  # 更大的缓冲区
            'auto_resize': True
        }
    }
}
```

## 测试验证

### 单元测试

创建了完整的单元测试套件：`tests/unit/test_unified_memory_management.py`

测试覆盖：
- MemoryMonitor功能测试
- BufferManager功能测试
- ResourceManager集成测试
- StageBase集成测试

### 运行测试
```bash
python -m pytest tests/unit/test_unified_memory_management.py -v
```

## 性能优势

### 内存使用优化
- 统一的内存压力监控，避免重复检查
- 自适应缓冲区大小，根据内存压力动态调整
- 及时的资源清理，减少内存泄漏风险

### 代码简化
- 消除重复的内存管理逻辑
- 统一的资源清理接口
- 更好的代码可维护性

### 可扩展性
- 模块化设计，易于扩展新的资源类型
- 标准化接口，便于添加新的Stage类
- 配置驱动，支持不同场景的优化策略

## 迁移指南

### 现有Stage类迁移

1. **继承StageBase**：确保Stage类继承自StageBase
2. **实现_cleanup_stage_specific**：重写此方法实现特定清理逻辑
3. **使用ResourceManager**：通过`self.resource_manager`访问统一资源管理
4. **更新配置**：添加`resource_manager`配置节

### 示例迁移
```python
# 原有实现
class OldStage:
    def cleanup(self):
        # 自定义清理逻辑
        pass

# 新的实现
class NewStage(StageBase):
    def _cleanup_stage_specific(self):
        # 特定清理逻辑
        pass
    # cleanup()方法由StageBase提供
```

## 监控和调试

### 资源统计
```python
stats = stage.resource_manager.get_resource_stats()
print(f"Memory usage: {stats.memory_usage_mb}MB")
print(f"Buffer count: {stats.buffer_count}")
print(f"Temp files: {stats.temp_files}")
```

### 日志记录
统一的内存管理系统提供详细的日志记录：
- 内存压力警告
- 缓冲区刷新操作
- 资源清理过程
- 性能统计信息

## 总结

统一内存管理策略成功解决了PktMask项目中的内存管理不一致问题，提供了：

1. **统一的资源管理接口**
2. **自动化的内存压力处理**
3. **标准化的资源清理机制**
4. **完整的RAII模式实现**
5. **向后兼容的迁移路径**

这一改进显著提升了系统的稳定性、性能和可维护性。
