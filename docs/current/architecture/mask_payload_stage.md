# MaskPayloadStage 架构文档

**版本**: v3.1  
**最后更新**: 2025年1月9日  
**状态**: 当前有效

## 概述

`MaskPayloadStage` 是 PktMask 管道系统中负责数据包载荷掩码的核心阶段。它提供了灵活的双模式处理机制，能够根据系统环境和配置自动选择最优的处理策略。

## 架构设计

### 类层次结构

```
StageBase (抽象基类)
    └── MaskPayloadStage
            ├── Processor Adapter Mode (默认)
            └── Basic Mode (降级)
```

### 核心组件

#### 1. MaskPayloadStage
- **位置**: `src/pktmask/core/pipeline/stages/mask_payload/stage.py`
- **职责**: 管理载荷掩码处理的生命周期和模式选择

#### 2. TSharkEnhancedMaskProcessor
- **位置**: `src/pktmask/core/processors/tshark_enhanced_mask_processor.py`
- **职责**: 使用 TShark 进行智能协议识别和掩码处理

#### 3. PipelineProcessorAdapter
- **位置**: `src/pktmask/adapters/processor_adapter.py`
- **职责**: 将处理器适配为管道阶段接口

## 处理模式

### 1. Processor Adapter Mode（默认）

这是推荐的处理模式，提供完整的协议识别和智能掩码功能。

```python
# 初始化流程
MaskPayloadStage.__init__()
    └── mode = "processor_adapter" (默认)
    
MaskPayloadStage.initialize()
    ├── 创建 TSharkEnhancedMaskProcessor
    ├── 使用 PipelineProcessorAdapter 包装
    └── 初始化处理器

# 处理流程
MaskPayloadStage.process_file()
    └── _process_with_processor_adapter_mode()
        └── adapter.process_file()
            └── TSharkEnhancedMaskProcessor.process_file()
```

**特点**：
- 智能 TLS 协议识别
- 跨数据包处理支持
- 完整的统计信息
- 自动错误恢复

### 2. Basic Mode（降级）

当处理器组件不可用或出现错误时，系统自动降级到基础模式。

```python
# 降级触发条件
- ImportError: 组件导入失败
- Exception: 初始化或执行失败

# 处理流程
MaskPayloadStage.process_file()
    └── _process_with_basic_mode()
        └── shutil.copyfile()  # 透传复制
```

**特点**：
- 零依赖，保证可用性
- 快速透传，不修改数据
- 适用于故障恢复场景

## 配置选项

```python
config = {
    # 处理模式选择
    "mode": "processor_adapter",  # 或 "basic"

    # 掩码配方（可选，仅在processor_adapter模式下使用）
    "recipe": MaskingRecipe(),           # 直接传入实例
    "recipe_dict": {...},                # 从字典创建
    # 注意：recipe_path 已废弃，现在使用智能协议分析
}
```

## 错误处理策略

### 自动降级机制

1. **初始化阶段降级**
   - 检测到组件缺失时立即降级
   - 记录详细错误日志
   - 继续以 Basic Mode 运行

2. **执行阶段降级**
   - 处理器执行失败时降级
   - 保存已处理的进度
   - 使用 Basic Mode 完成剩余工作

### 日志记录

```python
# 降级日志示例
ERROR - MaskStage降级为Basic Mode: cannot import name 'ProcessorAdapter'
INFO - MaskStage Basic Mode 透传复制执行
```

## 性能特征

| 模式 | 处理速度 | 内存占用 | 功能完整性 |
|------|---------|----------|------------|
| Processor Adapter | 中等 | 中等 | 完整 |
| Basic | 极快 | 极低 | 仅复制 |

## 使用示例

### 基本使用

```python
from pktmask.core.pipeline.stages.mask_payload import MaskPayloadStage

# 创建实例
stage = MaskPayloadStage(config={"mode": "processor_adapter"})

# 初始化
stage.initialize()

# 处理文件
stats = stage.process_file("input.pcap", "output.pcap")
```

### 配置掩码策略

```python
# 使用智能协议分析（推荐）
config = {
    "mode": "processor_adapter"  # 自动进行TLS协议分析和掩码
}
stage = MaskPayloadStage(config=config)

# 或使用自定义配方
config = {
    "mode": "processor_adapter",
    "recipe": custom_recipe_instance
}
stage = MaskPayloadStage(config=config)
```

## 扩展指南

### 添加新的处理器

1. 继承 `BaseProcessor` 类
2. 实现 `process_file()` 方法
3. 在 `_create_enhanced_processor()` 中集成

### 自定义降级策略

1. 重写 `_initialize_basic_mode()` 方法
2. 实现自定义的降级处理逻辑

## 相关文档

- [适配器使用指南](../../current/user/adapters_usage_guide.md)
- [管道执行指南](../../UNIFIED_PIPELINE_EXECUTION_GUIDE.md)
- [处理器开发指南](../development/processor_development.md)

## 版本历史

- v3.1 (2025-01): 简化架构，移除 BlindPacketMasker
- v3.0 (2024-12): 引入 PipelineProcessorAdapter
- v2.x (2024): 初始双模式设计
