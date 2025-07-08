# Step/Stage 后缀统一实施方案总结

## 一、问题分析

### 1.1 核心冲突
项目中存在 Step 和 Stage 两套平行的命名体系：

- **旧体系**：`*Step` 后缀，基于 `ProcessingStep` 基类
- **新体系**：`*Stage` 后缀，基于 `StageBase` 基类

### 1.2 具体冲突点
1. `DeduplicationStep` vs `DeduplicationStage`
2. `IpAnonymizationStep` vs `IpAnonymizationStage`  
3. `IntelligentTrimmingStep` vs `IntelligentTrimmingStage`
4. 导入路径：`pktmask.steps.*` vs `pktmask.stages.*` vs `pktmask.core.pipeline.stages.*`

### 1.3 架构层级分析

```
新架构 (推荐):
├── pktmask.core.pipeline.stages.*     # 核心新实现
│   ├── DedupStage
│   ├── AnonStage  
│   └── MaskStage

过渡层:
├── pktmask.stages.*                   # 兼容性适配器
│   ├── DeduplicationStageCompat (包装 DedupStage)
│   ├── IpAnonymizationStageCompat (包装 AnonStage)
│   └── IntelligentTrimmingStage (直接实现)

废弃层:
└── pktmask.steps.*                    # Step别名，映射到stages
    ├── DeduplicationStep -> DeduplicationStage
    ├── IpAnonymizationStep -> IpAnonymizationStage
    └── IntelligentTrimmingStep -> IntelligentTrimmingStage
```

## 二、实施方案

### 2.1 无破坏性迁移策略
- ✅ **Phase 1**: 创建别名映射，确保向后兼容
- ✅ **Phase 2**: 添加废弃警告，引导迁移
- 🔄 **Phase 3**: 更新文档和示例
- ⏳ **Phase 4**: 逐步移除旧接口（未来版本）

### 2.2 已完成的实现

#### 2.2.1 Step->Stage别名映射 (`src/pktmask/steps/__init__.py`)
```python
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

#### 2.2.2 兼容性适配器实现
- `DeduplicationStageCompat`: 包装新的 `DedupStage`
- `IpAnonymizationStageCompat`: 包装新的 `AnonStage`
- `IntelligentTrimmingStage`: 直接基于 `ProcessingStep` 实现

#### 2.2.3 废弃警告机制
所有旧类的文档字符串都包含迁移提示：
```python
"""
注意：该类使用 Stage 后缀，这是推荐的命名约定。
旧的 *Step 别名已废弃，请使用 *Stage。
"""
```

## 三、测试验证结果

### 3.1 导入测试
```python
# Stage 导入 - 正常工作，有废弃警告
from pktmask.stages import DeduplicationStage, IpAnonymizationStage, IntelligentTrimmingStage
# DeprecationWarning: pktmask.stages 已废弃，请使用 pktmask.core.pipeline.stages 替代。

# Step 导入 - 正常工作，有废弃警告  
from pktmask.steps import DeduplicationStep, IpAnonymizationStep, IntelligentTrimmingStep
# DeprecationWarning: pktmask.steps 和 *Step 后缀已废弃，请使用 pktmask.stages 和 *Stage 后缀。
```

### 3.2 别名验证
- ✅ `DeduplicationStep` 和 `DeduplicationStage` 引用同一个类
- ✅ `IpAnonymizationStep` 和 `IpAnonymizationStage` 引用同一个类
- ✅ `IntelligentTrimmingStep` 和 `IntelligentTrimmingStage` 引用同一个类

## 四、待完成任务

### 4.1 文档更新
- [ ] 更新 README.md 中的示例代码
- [ ] 更新 examples/ 目录中的示例
- [ ] 更新 docs/ 中的API文档

### 4.2 代码清理
- [ ] 检查并更新 GUI/CLI 代码中的导入
- [ ] 检查测试文件中的导入路径
- [ ] 更新配置文件中的类名引用

### 4.3 Enhanced Trimmer 处理
项目中还存在对 `EnhancedTrimmer` 的引用，需要明确其与 `IntelligentTrimmingStage` 的关系：

**发现的引用位置**：
- `scripts/validation/tls23_e2e_validator.py`
- 多个文档文件
- 测试文件

**处理建议**：
- 如果 `EnhancedTrimmer` 是 `IntelligentTrimmingStage` 的旧名称，添加别名映射
- 如果是不同的实现，需要明确区分并文档化差异

## 五、迁移指南

### 5.1 对于新代码
```python
# 推荐：使用新的核心实现
from pktmask.core.pipeline.stages import DedupStage, AnonStage, MaskStage

# 兼容：使用过渡层
from pktmask.stages import DeduplicationStage, IpAnonymizationStage
```

### 5.2 对于现有代码
```python
# 现有代码可以继续工作，但会收到废弃警告
from pktmask.steps import DeduplicationStep  # 有警告但可用
from pktmask.stages import DeduplicationStage  # 有警告但可用

# 建议迁移到：
from pktmask.core.pipeline.stages import DedupStage  # 新实现
```

### 5.3 迁移时间线
- **当前版本**: 所有接口可用，有废弃警告
- **下一个主版本**: 考虑移除 `pktmask.steps.*` 
- **未来版本**: 考虑移除 `pktmask.stages.*`，统一使用 `pktmask.core.pipeline.stages.*`

## 六、设计原则验证

### 6.1 向后兼容性 ✅
- 现有代码无需修改即可继续工作
- 通过别名映射保持API一致性

### 6.2 渐进式迁移 ✅  
- 废弃警告引导用户迁移
- 多层次的迁移路径

### 6.3 最小复杂度 ✅
- 避免了大规模重构
- 通过适配器模式复用现有实现

### 6.4 清晰的命名约定 ✅
- 统一使用 `*Stage` 后缀
- 明确的模块层级关系

## 七、风险评估

### 7.1 已控制的风险
- ✅ **兼容性风险**: 通过别名映射避免破坏性变更
- ✅ **性能风险**: 别名映射开销极小
- ✅ **维护风险**: 清晰的废弃路径

### 7.2 需要关注的风险
- ⚠️ **文档同步**: 需要及时更新文档避免混淆
- ⚠️ **过渡期管理**: 需要明确各个废弃阶段的时间表

## 八、结论

本实施方案成功解决了 Step/Stage 命名冲突问题，实现了：

1. **零破坏性迁移**: 现有代码无需修改
2. **清晰的迁移路径**: 从 Step -> Stage -> Core Implementation  
3. **适当的废弃警告**: 引导用户采用最佳实践
4. **架构统一**: 向新的 pipeline 架构迁移

下一步需要重点完成文档更新和示例代码的迁移工作。

---

*最后更新: 2025-07-08*
*状态: Phase 1-2 已完成，Phase 3 进行中*
