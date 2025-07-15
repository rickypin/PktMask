# PktMask当前架构状态报告

> **版本**: v1.0  
> **更新日期**: 2025-07-15  
> **状态**: 🔄 **混合架构 - 部分迁移完成**  
> **准确性**: ✅ **与实际代码库状态一致**  

---

## 📋 执行摘要

### 当前架构状态
PktMask项目当前处于架构迁移的**中间状态**，存在两套并行的处理系统：
- **BaseProcessor系统**（旧架构）：IP匿名化、去重功能
- **StageBase Pipeline系统**（新架构）：载荷掩码功能

### 关键澄清
**重要**: 之前的文档中存在误导性描述，声称"ProcessingStep系统已被移除"和"完全统一到StageBase架构"。实际情况是：
- ✅ **ProcessingStep系统确实已被移除**（这部分描述正确）
- ❌ **但BaseProcessor系统仍然存在并在使用**（之前文档未准确描述）
- 🔄 **项目处于混合架构状态，而非完全统一状态**

---

## 🏗️ 详细架构分析

### 1. 当前存在的架构系统

#### 1.1 BaseProcessor系统（旧架构 - 仍在使用）
**位置**: `src/pktmask/core/processors/`

**核心组件**:
```
📁 src/pktmask/core/processors/
├── base_processor.py          # BaseProcessor抽象基类
├── ip_anonymizer.py          # IPAnonymizer (继承BaseProcessor)
├── deduplicator.py           # Deduplicator (继承BaseProcessor)
├── masker.py                 # Masker (继承BaseProcessor, 已废弃)
└── registry.py               # ProcessorRegistry (桥接层)
```

**使用状态**:
- ✅ **IPAnonymizer**: 生产使用中，负责IP匿名化
- ✅ **Deduplicator**: 生产使用中，负责数据包去重
- ❌ **Masker**: 已废弃，被NewMaskPayloadStage替代

#### 1.2 StageBase Pipeline系统（新架构 - 部分使用）
**位置**: `src/pktmask/core/pipeline/`

**核心组件**:
```
📁 src/pktmask/core/pipeline/
├── base_stage.py             # StageBase抽象基类
├── executor.py               # PipelineExecutor统一执行器
├── models.py                 # StageStats等数据模型
└── stages/
    └── mask_payload_v2/
        └── stage.py          # NewMaskPayloadStage (继承StageBase)
```

**使用状态**:
- ✅ **NewMaskPayloadStage**: 生产使用中，双模块架构（Marker + Masker）
- ✅ **PipelineExecutor**: 统一执行器，处理新旧架构差异

### 2. 桥接机制

#### 2.1 ProcessorRegistry桥接功能
**位置**: `src/pktmask/core/processors/registry.py`

**桥接映射**:
```python
cls._processors.update({
    # Standard naming keys
    'anonymize_ips': IPAnonymizer,        # → BaseProcessor系统
    'remove_dupes': Deduplicator,         # → BaseProcessor系统
    'mask_payloads': MaskingProcessor,    # → NewMaskPayloadStage (StageBase系统)
    
    # Legacy aliases
    'anon_ip': IPAnonymizer,
    'dedup_packet': Deduplicator,
    'mask_payload': MaskingProcessor,
})
```

**功能**: 为新旧架构提供统一的访问接口，隐藏架构差异

### 3. 已移除的架构组件

#### 3.1 ProcessingStep系统（已完全移除）
```bash
❌ src/pktmask/core/base_step.py - 不存在
❌ src/pktmask/steps/ - 目录不存在
```

#### 3.2 ProcessorStageAdapter适配层（已移除）
```bash
❌ src/pktmask/core/pipeline/processor_stage.py - 已删除
❌ src/pktmask/adapters/processor_adapter.py - 已删除
❌ src/pktmask/stages/ - 目录已删除
```

---

## 📊 迁移进度

### 已完成的迁移 ✅

#### 载荷掩码功能
- **组件**: `NewMaskPayloadStage`
- **架构**: StageBase
- **状态**: 完全迁移，生产就绪
- **特性**: 双模块架构（Marker + Masker分离）

### 待迁移的组件 🔄

#### IP匿名化功能
- **组件**: `IPAnonymizer`
- **当前架构**: BaseProcessor
- **目标架构**: StageBase
- **功能**: 前缀保持匿名化、目录级映射构建、频率统计

#### 去重功能
- **组件**: `Deduplicator`
- **当前架构**: BaseProcessor
- **目标架构**: StageBase
- **功能**: 数据包去重、哈希计算、统计分析

### 临时桥接组件 🔧

#### ProcessorRegistry
- **功能**: 新旧架构统一访问接口
- **状态**: 临时桥接，完成迁移后可简化
- **作用**: 隐藏架构差异，提供统一API

---

## 🎯 推荐使用方式

### 当前最佳实践
```python
from pktmask.core.pipeline.executor import PipelineExecutor

# 推荐：通过PipelineExecutor统一访问
config = {
    'anonymize_ips': {'enabled': True},    # 自动使用IPAnonymizer (BaseProcessor)
    'remove_dupes': {'enabled': True},     # 自动使用Deduplicator (BaseProcessor)
    'mask_payloads': {'enabled': True}     # 自动使用NewMaskPayloadStage (StageBase)
}

executor = PipelineExecutor(config)
result = executor.run(input_path, output_path)
```

### 直接访问（高级用户）
```python
from pktmask.core.processors.registry import ProcessorRegistry

# 通过ProcessorRegistry访问具体组件
anonymizer = ProcessorRegistry.get_processor('anonymize_ips')
deduplicator = ProcessorRegistry.get_processor('remove_dupes')
masker = ProcessorRegistry.get_processor('mask_payloads')
```

---

## 🔮 未来迁移计划

### 第一阶段：IP匿名化迁移
- 创建 `IPAnonymizationStage` 继承 `StageBase`
- 迁移IP匿名化逻辑和配置
- 更新ProcessorRegistry映射

### 第二阶段：去重功能迁移
- 创建 `DeduplicationStage` 继承 `StageBase`
- 迁移去重逻辑和统计功能
- 更新ProcessorRegistry映射

### 第三阶段：架构清理
- 移除BaseProcessor系统
- 简化ProcessorRegistry为纯Stage注册表
- 更新所有文档和示例

---

## 📝 文档修正记录

### 已修正的误导性文档
- ✅ `docs/architecture/LEGACY_ARCHITECTURE_REMOVAL_REPORT.md` - 更新架构状态描述
- ✅ `docs/current/user/adapters_usage_guide.md` - 纠正适配器使用说明
- ✅ `CHANGELOG.md` - 修正版本变更描述
- ✅ `docs/architecture/RADICAL_ARCHITECTURE_UNIFICATION_PLAN.md` - 更新项目背景

### 关键修正内容
1. **澄清ProcessingStep vs BaseProcessor**: 前者已移除，后者仍存在
2. **纠正"完全统一"声明**: 实际为混合架构状态
3. **准确描述迁移进度**: 载荷掩码已迁移，其他待迁移
4. **更新使用建议**: 推荐通过PipelineExecutor统一访问

---

---

## ✅ 验证确认

### 代码库状态验证
经过全面的代码库检索和验证，确认以下关键点与实际代码完全一致：

#### ✅ BaseProcessor系统确实仍在使用
- `src/pktmask/core/processors/base_processor.py` - ✅ 存在
- `src/pktmask/core/processors/ip_anonymizer.py` - ✅ 存在，继承BaseProcessor
- `src/pktmask/core/processors/deduplicator.py` - ✅ 存在，继承BaseProcessor
- `src/pktmask/core/processors/registry.py` - ✅ 存在，提供桥接功能

#### ✅ StageBase系统部分实现
- `src/pktmask/core/pipeline/base_stage.py` - ✅ 存在，StageBase抽象基类
- `src/pktmask/core/pipeline/stages/mask_payload_v2/stage.py` - ✅ 存在，NewMaskPayloadStage继承StageBase

#### ✅ ProcessorRegistry桥接映射正确
```python
# 验证确认的实际映射关系
'anonymize_ips': IPAnonymizer,        # BaseProcessor系统
'remove_dupes': Deduplicator,         # BaseProcessor系统
'mask_payloads': MaskingProcessor,    # NewMaskPayloadStage (StageBase系统)
```

#### ✅ ProcessingStep系统确实已移除
- `src/pktmask/core/base_step.py` - ❌ 不存在（正确）
- `src/pktmask/steps/` - ❌ 目录不存在（正确）

### 文档修正验证
所有修正的文档现在与实际代码库状态完全一致：
- ✅ 准确描述混合架构状态
- ✅ 正确区分ProcessingStep（已移除）vs BaseProcessor（仍存在）
- ✅ 准确标注迁移进度和待迁移组件
- ✅ 提供正确的使用建议和代码示例

---

**最后更新**: 2025-07-15
**验证状态**: ✅ 与实际代码库状态完全一致
**验证方法**: 全面代码库检索和交叉验证
**维护责任**: 架构团队，每次架构变更后及时更新
