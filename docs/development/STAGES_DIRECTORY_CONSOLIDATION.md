# 旧"stages"目录 vs 新"pipeline/stages"目录整合方案

## 问题分析

当前存在三套并行的 Stage 目录结构：

### 1. 旧系统：`src/pktmask/steps/` (已废弃)
- **状态**：已标记废弃，只有别名映射
- **用途**：向后兼容的别名导入
- **内容**：仅包含 `__init__.py` 中的别名映射

### 2. 中间层：`src/pktmask/stages/`
- **状态**：GUI/CLI 使用的 ProcessingStep 实现
- **用途**：传统的 Step 实现，继承 ProcessingStep
- **内容**：
  - `DeduplicationStage`
  - `IpAnonymizationStage` 
  - `IntelligentTrimmingStage`

### 3. 新系统：`src/pktmask/core/pipeline/stages/`
- **状态**：新的 Pipeline 架构
- **用途**：现代化的 Stage 实现，继承 StageBase
- **内容**：
  - `AnonStage` (对应 IpAnonymizationStage)
  - `DedupStage` (对应 DeduplicationStage)  
  - `MaskStage` (新功能)
  - `ProcessorStageAdapter`

## 简化策略：统一到 pipeline/stages

### 决定：保留 `core/pipeline/stages/`，迁移 `stages/`

**理由**：
1. `core/pipeline/stages/` 是新架构的核心部分
2. 新的 Stage 实现更现代化，支持更多功能
3. 已有明确的迁移路径（ProcessingStep → StageBase）
4. 避免破坏现有的 Pipeline 架构

### 实施计划

#### 第一阶段：创建迁移映射（低风险）
1. **修改 `stages/__init__.py`** 
   - 将导入指向 `core/pipeline/stages/` 中的对应实现
   - 添加废弃警告
   - 保持 API 兼容性

2. **保留现有文件**（暂时）
   - 不立即删除现有实现
   - 添加废弃标记
   - 确保向后兼容

#### 第二阶段：完善新实现（中期）
1. **确保功能对等**
   - 验证新实现包含所有旧功能
   - 补充缺失的方法或属性
   - 保持接口兼容性

2. **更新文档和示例**
   - 指向新的导入路径
   - 更新使用示例

#### 第三阶段：清理（长期）
1. **移除旧实现**
   - 删除 `stages/` 目录中的具体实现
   - 保留 `steps/` 的废弃警告
   - 清理相关文档

## 具体实施

### 第一步：修改 stages/__init__.py 为迁移层

```python
# src/pktmask/stages/__init__.py
import warnings

# 废弃警告
warnings.warn(
    "pktmask.stages 已废弃，请使用 pktmask.core.pipeline.stages 替代。",
    DeprecationWarning,
    stacklevel=2
)

# 重新导入到新实现
from pktmask.core.pipeline.stages.anon_ip import AnonStage as IpAnonymizationStage
from pktmask.core.pipeline.stages.dedup import DedupStage as DeduplicationStage

# 这个还没有对应实现，暂时保持原有
from .trimming import IntelligentTrimmingStage

__all__ = [
    "DeduplicationStage", 
    "IpAnonymizationStage",
    "IntelligentTrimmingStage",
]
```

### 第二步：确保新实现兼容性

需要检查 `AnonStage` 和 `DedupStage` 是否与对应的旧实现兼容：

1. **接口兼容性** - 确保方法签名一致
2. **属性兼容性** - 确保必要的属性存在
3. **行为兼容性** - 确保处理结果一致

### 第三步：处理 IntelligentTrimmingStage

由于新系统中还没有对应的 Trimming Stage，有两个选择：
1. **创建新的 TrimmingStage** 在 `core/pipeline/stages/`
2. **暂时保留旧实现** 直到有新实现

## 风险评估

### 极低风险
- 通过别名映射保持完全向后兼容
- 所有现有导入路径继续工作
- 渐进式迁移，无破坏性变更

### 中等风险
- 新旧实现可能存在细微差异
- 需要全面测试确保行为一致

## 预期效果

1. **立即效果**：统一导入路径，减少概念混淆
2. **中期效果**：简化目录结构，降低维护成本
3. **长期效果**：完全统一到新架构

## 实施时间表

- **立即**：实施第一阶段映射
- **1周后**：验证兼容性和补充缺失功能
- **1个月后**：评估是否可以清理旧实现

这个方案避免了复杂的合并操作，通过简单的别名映射实现平滑过渡。
