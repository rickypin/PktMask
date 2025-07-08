# PktMask 文档状态清单

**最后更新**: 2025年1月9日  
**维护者**: 开发团队

## 文档分类说明

### current/ - 当前有效文档
与当前代码版本同步的文档，开发者和用户应该参考这些文档。

### archive/ - 历史文档
包含历史设计、废弃功能和旧版本的文档，仅供参考。

## 文档状态表

### 架构和设计文档

| 文档路径 | 状态 | 最后更新 | 说明 |
|---------|------|----------|------|
| docs/archive/design/maskstage_flow_analysis.md | 已过时 | 2024-07 | 描述旧架构，包含不存在的组件 |
| docs/archive/design/MASK_STAGE_*.md | 已归档 | 2024 | 多个版本的MaskStage设计文档 |
| docs/current/architecture/mask_payload_stage.md | 需创建 | - | 需要编写新的架构文档 |

### 开发文档

| 文档路径 | 状态 | 最后更新 | 说明 |
|---------|------|----------|------|
| docs/current/development/refactoring/ | 当前有效 | 2025-01 | 适配器重构相关文档 |
| docs/development/ENTRYPOINT_*.md | 当前有效 | 2025-01 | 入口点统一相关文档 |
| docs/development/DEPENDENCY_*.md | 当前有效 | 2025-01 | 依赖管理文档 |

### 用户文档

| 文档路径 | 状态 | 最后更新 | 说明 |
|---------|------|----------|------|
| docs/current/user/adapters_usage_guide.md | 当前有效 | 2025-01 | 适配器使用指南 |
| docs/TLS23_*.md | 需整理 | 2024 | TLS工具相关文档需要整理 |
| docs/UNIFIED_PIPELINE_EXECUTION_GUIDE.md | 需更新 | 2024 | 管道执行指南需要更新 |

### 已归档文档

| 文档路径 | 归档原因 |
|---------|----------|
| docs/archive/deprecated/ENHANCED_TRIMMER_*.md | 功能已废弃 |
| docs/archive/deprecated/ENHANCED_MASK_STAGE_API_DOCUMENTATION.md | API已变更 |
| docs/archive/plans/REFACTOR_PLAN.md | 重构已完成 |

## 待办事项

### 高优先级
1. [ ] 创建新的 MaskPayloadStage 架构文档
2. [ ] 更新管道执行指南
3. [ ] 整理 TLS 工具文档

### 中优先级
1. [ ] 审查所有 development/ 目录下的文档
2. [ ] 创建 API 参考文档
3. [ ] 更新 README.md 中的文档链接

### 低优先级
1. [ ] 为归档文档添加版本标记
2. [ ] 创建文档模板
3. [ ] 建立文档审查流程

## 文档维护指南

1. **新增文档**：
   - 添加到 `current/` 相应子目录
   - 在本清单中登记

2. **更新文档**：
   - 同步更新代码和文档
   - 更新本清单中的"最后更新"时间

3. **归档文档**：
   - 移动到 `archive/` 相应子目录
   - 在文档顶部添加过时警告
   - 更新本清单

4. **命名规范**：
   - 使用小写字母和下划线
   - 避免版本号后缀（使用 Git 管理版本）
   - 描述性命名，避免缩写
