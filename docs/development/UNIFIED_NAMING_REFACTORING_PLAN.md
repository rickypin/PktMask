# 统一命名改造方案（修订版）

## 一、问题分析

### 1.1 核心问题识别
**主要命名冲突：**
- `Step` vs `Stage` 概念重叠，造成开发者困惑
- `ProcessingStep` 和 `StageBase` 两套相似抽象基类
- 导入路径不一致：`pktmask.steps` vs `pktmask.core.pipeline.stages`

**实际影响评估：**
- 新手开发者学习成本高
- 代码审查时容易混淆概念
- 文档和示例需要维护两套

### 1.2 现状务实分析
**真实使用情况：**
- 旧系统（`steps`）：GUI、CLI 主要使用，稳定运行
- 新系统（`core/pipeline`）：部分重构代码使用，仍在完善
- 适配器层：主要用于过渡期兼容，非长期方案

## 二、核心概念词汇表
| 术语      | 英文        | 说明                                                                 |
|---------|-----------|--------------------------------------------------------------------|
| 管道／流水线 | Pipeline   | 整体处理流程，由多个 Stage 串联，负责调度、临时文件管理、错误恢复等。             |
| 阶段      | Stage      | Pipeline 中的单一处理单元，如 `DedupStage`、`AnonStage`、`MaskStage`。            |
| 处理器     | Processor  | Stage 内部的具体算法单元，如 `TSharkEnhancedMaskProcessor`、`ScapyMaskApplier`。 |
| 掩码器     | Masker     | 特指执行掩码操作的 Processor，如 `TLSMaskRuleGenerator`、`ScapyMaskApplier`。   |
| 适配器     | Adapter    | 连接或转换不同组件接口的中间层，如 `ProcessorStageAdapter`、`PipelineAdapter`。  |

## 三、现存冲突模块与建议新命名
| 现有模块路径                                    | 功能定位              | 建议新路径/新名                                               |
|----------------------------------------------|-------------------|----------------------------------------------------------|
| `src/pktmask/steps/`                         | 顶层“步骤”集合，与 Stage 同义 | `src/pktmask/stages/`                                      |
| `src/pktmask/core/pipeline/`                 | Pipeline 引擎包         | `src/pktmask/core/pipeline_engine/`                       |
| `src/pktmask/core/processors/pipeline_adapter.py` | Processor ↔ Stage 适配器 | `src/pktmask/core/adapters/processor_stage_adapter.py` |

- 统一类/函数命名：  
  - `*Step` → `*Stage`  
  - 包名 `pipeline` → `pipeline_engine`  
  - 适配器统一置于 `core/adapters`，命名为 `*Adapter`

## 四、详细现状分析

### 4.1 当前文件结构分析
**旧系统（基于 ProcessingStep）：**
```
src/pktmask/steps/
├── __init__.py                    # 导出 *Step 类
├── deduplication.py              # DeduplicationStep
├── ip_anonymization.py           # IpAnonymizationStep  
└── trimming.py                   # IntelligentTrimmingStep

src/pktmask/core/base_step.py     # ProcessingStep 抽象基类
```

**新系统（基于 StageBase）：**
```
src/pktmask/core/pipeline/
├── base_stage.py                 # StageBase 抽象基类
├── executor.py                   # PipelineExecutor
├── models.py                     # StageStats, ProcessResult
└── stages/
    ├── dedup.py                  # DedupStage
    ├── anon_ip.py                # AnonStage
    ├── processor_stage_adapter.py # 适配器
    └── mask_payload/stage.py     # MaskStage
```

**适配层：**
```
src/pktmask/core/processors/pipeline_adapter.py  # ProcessorAdapter
```

### 4.2 依赖影响分析
**核心导入路径：**
- GUI: `from pktmask.steps import *`
- CLI: `from pktmask.core.pipeline.stages import *`  
- 测试: 两套导入并存
- 文档示例: 使用旧的 `*Step` 类名

**适配器使用情况：**
- `ProcessorStageAdapter`: 新 Pipeline 调用旧 Processor
- `ProcessorAdapter`: 旧 Pipeline 调用新 Processor
- 双向适配增加维护复杂度

## 三、简化的重构方案

### 3.1 方案原则
**保守策略：**
- 最小化影响范围，优先保证现有功能不受影响
- 避免过度设计，不引入不必要的抽象层
- 优先解决用户可见的命名冲突

**阶段化执行：**
1. 先统一对外可见的命名（类名、导入路径）
2. 再逐步统一内部实现（可选）

### 3.2 核心操作（3-5天）

**步骤 1：创建分支和基础重命名（半天）**
```bash
# 在当前分支创建新分支
git checkout -b unified-naming

# 只重命名关键目录
git mv src/pktmask/steps/ src/pktmask/stages/
```

**步骤 2：更新类名和导入（1天）**
- 只修改 `src/pktmask/stages/` 中的类名
- 更新所有 `from pktmask.steps` 导入为 `from pktmask.stages`
- 类名统一：`*Step` → `*Stage`

**步骤 3：创建简单兼容层（半天）**
```python
# src/pktmask/steps/__init__.py
from ..stages import (
    DeduplicationStage as DeduplicationStep,
    IpAnonymizationStage as IpAnonymizationStep,
    IntelligentTrimmingStage as IntelligentTrimmingStep,
)

# 简单警告，不阻断执行
import warnings
warnings.warn(
    "pktmask.steps is deprecated, use pktmask.stages", 
    DeprecationWarning
)
```

**步骤 4：更新测试和文档（1-2天）**
- 更新测试文件中的导入路径
- 更新 `README.md` 和示例代码
- 运行完整测试确保没有回归

**步骤 5：发布与清理（半天）**
- 更新 `CHANGELOG.md`
- 合并到主分支
- 在下个大版本计划移除 `steps` 目录

## 四、风险控制

### 4.1 主要风险
**向后兼容性：**保留兼容层，确保现有代码继续工作
**测试覆盖：**在更改后运行完整测试套件
**文档同步：**代码变更和文档更新同步进行

### 4.2 成功标准
- [ ] 所有现有测试通过
- [ ] 新旧导入路径都能正常工作
- [ ] 文档示例更新完毕
- [ ] 命名冲突得到解决

## 五、后续计划

### 5.1 短期（当前版本）
- 完成基础命名统一
- 维护兼容层稳定运行
- 在新代码中优先使用 `stages` 命名

### 5.2 中期（下个大版本）
- 移除 `steps` 兼容层
- 考虑统一 `ProcessingStep` 和 `StageBase` 抽象（如有必要）
- 添加命名规范到开发指南

### 5.3 学习总结
**避免的问题：**
- 过度复杂的阶段化计划
- 不必要的适配器层
- 过度详细的风险分析和成功指标

**有效的做法：**
- 保守的重构策略
- 简单直接的解决方案
- 对用户影响最小的方法
