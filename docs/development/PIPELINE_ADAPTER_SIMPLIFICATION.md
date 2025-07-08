# 双重 PipelineAdapter 简化方案

## 问题诊断

当前存在两个功能重叠的适配器：
1. **ProcessorAdapter** - 将 BaseProcessor 适配为 ProcessingStep
2. **ProcessorStageAdapter** - 将 BaseProcessor 适配为 StageBase

## 简化策略

### 方案：选择单一适配器架构

**决定**：保留 `ProcessorStageAdapter`，移除 `ProcessorAdapter`

**理由**：
1. `ProcessorStageAdapter` 更简洁，代码量更少
2. 新的 Pipeline 架构 (`StageBase`) 是未来方向
3. 只有一个地方在使用 `ProcessorStageAdapter`，迁移成本低
4. `ProcessorAdapter` 在导出中暴露，但实际使用较少

### 具体步骤

#### 第一步：移除 ProcessorAdapter 的导出
- 从 `src/pktmask/core/processors/__init__.py` 中移除相关导出
- 保留文件但标记为废弃

#### 第二步：确认没有其他地方使用 ProcessorAdapter
- 检查整个代码库的使用情况
- 如有使用则迁移到 ProcessorStageAdapter

#### 第三步：清理 ProcessorAdapter 文件
- 移除 `src/pktmask/core/processors/pipeline_adapter.py`
- 更新相关文档

#### 第四步：优化 ProcessorStageAdapter
- 如果需要，增加 ProcessorAdapter 的缺失功能
- 确保功能完整性

## 风险评估

### 低风险
- 只有一个地方使用 ProcessorStageAdapter
- ProcessorAdapter 的导出可能未被广泛使用
- 向后兼容性影响小

### 验证步骤
1. 搜索整个代码库确认使用情况
2. 运行测试确保无破坏性更改
3. 检查文档更新需求

## 预期效果

1. **代码简化**：消除重复适配器
2. **维护性提升**：只需维护一个适配器
3. **架构清晰**：统一使用新的 Pipeline 架构
4. **性能优化**：减少适配层次
