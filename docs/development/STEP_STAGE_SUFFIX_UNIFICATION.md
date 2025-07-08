# Step vs Stage 后缀统一解决方案

## 问题分析

当前存在混用的 Step/Stage 后缀，造成概念混淆：

### 现状梳理
| 功能 | Step 命名 | Stage 命名 | 状态 |
|------|-----------|------------|------|
| 去重 | `DeduplicationStep` | `DeduplicationStage` | 两者并存 |
| IP匿名化 | `IpAnonymizationStep` | `IpAnonymizationStage` | 两者并存 |
| 智能裁剪 | `IntelligentTrimmingStep` | `IntelligentTrimmingStage` | 仅 Stage 存在 |
| 载荷掩码 | ❌ 无 | `MaskStage` | 仅 Stage 存在 |

### 使用场景
- **Step 后缀** - 主要在 `pktmask.steps` 和 `pktmask.stages` 中作为别名使用
- **Stage 后缀** - 在 `pktmask.core.pipeline.stages` 和 `pktmask.stages` 中的实际实现

## 简化策略：统一使用 Stage 后缀

### 决定：全面采用 Stage 后缀

**理由**：
1. **趋势明确** - 新架构统一使用 Stage，这是未来方向
2. **概念清晰** - Stage 更符合管道处理的概念
3. **已有基础** - 大部分新实现已使用 Stage 后缀
4. **最小改动** - 主要通过别名映射实现兼容

### 实施方案

#### 第一阶段：别名统一（立即实施）
1. **更新 `steps/__init__.py`** - 将 Step 后缀映射到 Stage 实现
2. **保持向后兼容** - 所有现有的 Step 导入继续工作
3. **添加废弃警告** - 提示开发者使用 Stage 后缀

#### 第二阶段：文档更新（短期）
1. **更新示例代码** - 使用 Stage 后缀
2. **更新 API 文档** - 推荐 Stage 命名
3. **迁移指南** - 提供清晰的迁移路径

#### 第三阶段：清理（长期）
1. **移除 Step 别名** - 在适当时机移除兼容性导入
2. **统一内部引用** - 所有内部代码使用 Stage 后缀

## 具体实施

### 第一步：更新 steps/__init__.py 为完全映射

```python
# src/pktmask/steps/__init__.py
import warnings

warnings.warn(
    "pktmask.steps 和 *Step 后缀已废弃，请使用 pktmask.stages 和 *Stage 后缀。",
    DeprecationWarning,
    stacklevel=2
)

# 统一映射到 Stage 实现
from ..stages import (
    DeduplicationStage as DeduplicationStep,
    IpAnonymizationStage as IpAnonymizationStep, 
    IntelligentTrimmingStage as IntelligentTrimmingStep,
)

__all__ = [
    'DeduplicationStep',
    'IpAnonymizationStep', 
    'IntelligentTrimmingStep',
]
```

### 第二步：在相关文件中添加废弃提示

在直接定义 Step 类的地方添加废弃警告，引导开发者使用 Stage 版本。

### 第三步：更新文档和示例

将所有面向用户的文档统一使用 Stage 后缀。

## 风险评估

### 极低风险
- **别名映射** - 不破坏任何现有代码
- **渐进式废弃** - 友好的迁移提示
- **完全兼容** - 所有 Step 导入继续工作

### 预期效果

1. **概念统一** - 消除 Step/Stage 后缀混用
2. **清晰方向** - 明确未来使用 Stage 后缀
3. **平滑过渡** - 现有代码无需修改

## 迁移指南

### 推荐做法
```python
# 旧写法（仍然工作，但会有废弃警告）
from pktmask.steps import DeduplicationStep

# 新写法（推荐）
from pktmask.stages import DeduplicationStage
```

### 批量迁移
开发者可以通过简单的查找替换进行迁移：
- `DeduplicationStep` → `DeduplicationStage`
- `IpAnonymizationStep` → `IpAnonymizationStage`  
- `IntelligentTrimmingStep` → `IntelligentTrimmingStage`

这个方案避免了复杂的重命名操作，通过简单的别名映射实现统一，确保平滑过渡。
