# ProcessingStep vs StageBase 双重抽象基类简化方案

## 问题分析

当前存在两套并行的抽象基类体系：

### 旧系统：ProcessingStep
- **位置**：`src/pktmask/core/base_step.py`
- **使用场景**：GUI/CLI 的旧 Step 实现
- **实现类**：`IpAnonymizationStage`, `DeduplicationStep`, `TrimmingStep` 等
- **目录**：`src/pktmask/stages/`
- **接口特点**：简单，返回 `Optional[Dict]`

### 新系统：StageBase
- **位置**：`src/pktmask/core/pipeline/base_stage.py`
- **使用场景**：新的 Pipeline 架构
- **实现类**：`AnonStage`, `DeduplicationStage`, `MaskStage` 等
- **目录**：`src/pktmask/core/pipeline/stages/`
- **接口特点**：更完整，返回 `StageStats`，支持工具检测等

## 简化策略：迁移到单一基类

### 决定：保留 StageBase，迁移 ProcessingStep

**理由**：
1. `StageBase` 设计更完整，支持现代需求
2. `StageBase` 有更好的类型提示和结构化返回值
3. 新的 Pipeline 架构是未来方向
4. `StageBase` 已经考虑了向后兼容性

### 实施计划

#### 第一阶段：兼容性适配（低风险）
1. **修改 ProcessingStep 继承 StageBase**
   - 让 `ProcessingStep` 继承 `StageBase` 而不是 `ABC`
   - 添加兼容性方法，将旧接口映射到新接口
   - 保持所有现有代码正常工作

2. **逐步迁移实现类**
   - 更新 `IpAnonymizationStage` 等类直接继承 `StageBase`
   - 保持向后兼容的方法签名

#### 第二阶段：完全迁移（适时进行）
1. **移除 ProcessingStep**
   - 所有实现类直接使用 `StageBase`
   - 清理兼容性代码

2. **统一目录结构**
   - 将 `stages/` 目录的类迁移到 `core/pipeline/stages/`
   - 或者废弃旧目录，使用新目录

## 具体实施

### 第一步：修改 ProcessingStep 为兼容层

```python
# src/pktmask/core/base_step.py
from .pipeline.base_stage import StageBase
from .pipeline.models import StageStats

class ProcessingStep(StageBase):
    """处理步骤的抽象基类 - 兼容性包装"""
    
    # 保持旧的 suffix 属性以兼容
    suffix: str = ""
    
    # 新的实现委托给抽象方法
    def process_file(self, input_path: str | Path, output_path: str | Path) -> StageStats | Dict | None:
        # 调用旧的接口，包装返回值
        result = self.process_file_legacy(str(input_path), str(output_path))
        if result is None:
            return None
        if isinstance(result, dict):
            # 转换为 StageStats
            return StageStats(
                stage_name=self.name,
                packets_processed=result.get('total_packets', 0),
                packets_modified=result.get('anonymized_packets', 0),
                duration_ms=0.0,  # 旧接口没有时间信息
                extra_metrics=result
            )
        return result
    
    @abc.abstractmethod
    def process_file_legacy(self, input_path: str, output_path: str) -> Optional[Dict]:
        """向后兼容的处理方法"""
        pass
```

### 第二步：逐步更新实现类

只需要简单的方法重命名：

```python
# src/pktmask/stages/ip_anonymization.py
class IpAnonymizationStage(ProcessingStep):
    def process_file_legacy(self, input_path: str, output_path: str) -> Optional[Dict]:
        # 原有的实现
        ...
```

### 第三步：长期迁移到 StageBase

当准备好时，直接继承 StageBase：

```python
# src/pktmask/stages/ip_anonymization.py  
class IpAnonymizationStage(StageBase):
    def process_file(self, input_path: str | Path, output_path: str | Path) -> StageStats:
        # 直接返回 StageStats，无需兼容层
        ...
```

## 风险评估

### 极低风险
- 第一阶段只是添加兼容层，不破坏任何现有功能
- 所有现有的 ProcessingStep 实现都能无缝工作
- 类型检查仍然有效

### 中等风险
- 长期迁移需要修改具体实现类
- 需要测试确保行为一致性

## 效果预期

1. **立即效果**：消除双重抽象基类的概念混淆
2. **中期效果**：统一接口，简化开发
3. **长期效果**：完全统一到新架构，清理遗留代码

## 实施时间表

- **立即**：实施第一阶段兼容性适配
- **1-2周后**：开始迁移核心实现类
- **1个月后**：评估是否移除兼容层

这个方案避免了过度工程化，通过渐进式迁移确保稳定性。
