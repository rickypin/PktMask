# 适配器迁移准备报告

## 生成日期
2025-01-09

## 迁移概述

本报告总结了适配器重构的准备情况，包括受影响的文件、需要执行的操作以及潜在风险。

## 1. 需要迁移的适配器文件

| 原路径 | 新路径 | 文件大小 | 状态 |
|--------|--------|----------|------|
| `src/pktmask/core/adapters/processor_adapter.py` | `src/pktmask/adapters/processor_adapter.py` | 2.1KB | ✅ 存在 |
| `src/pktmask/core/encapsulation/adapter.py` | `src/pktmask/adapters/encapsulation_adapter.py` | - | ❓ 需确认 |
| `src/pktmask/domain/adapters/event_adapter.py` | `src/pktmask/adapters/event_adapter.py` | - | ❓ 需确认 |
| `src/pktmask/domain/adapters/statistics_adapter.py` | `src/pktmask/adapters/statistics_adapter.py` | - | ❓ 需确认 |
| `src/pktmask/stages/adapters/anon_compat.py` | `src/pktmask/adapters/compatibility/anon_compat.py` | - | ❓ 需确认 |
| `src/pktmask/stages/adapters/dedup_compat.py` | `src/pktmask/adapters/compatibility/dedup_compat.py` | - | ❓ 需确认 |

## 2. 受影响的文件统计

### 2.1 导入路径更新
- **受影响文件数**: 4 个
- **需要更新的导入语句**: 7 处

### 2.2 受影响文件列表
1. `src/pktmask/core/pipeline/stages/mask_payload/stage.py` (2处)
2. `tests/unit/test_pipeline_processor_adapter.py` (2处)
3. `tests/unit/test_infrastructure_basic.py` (2处)
4. `scripts/migration/migrate_adapters.py` (1处)

## 3. 迁移工具准备

### 3.1 已创建的工具
- ✅ `scripts/migration/analyze_adapter_imports.py` - 导入关系分析脚本
- ✅ `scripts/migration/migrate_adapters.py` - 自动化迁移脚本
- ✅ `scripts/test/adapter_baseline.py` - 测试基线记录脚本

### 3.2 工具功能
1. **分析脚本**: 扫描代码库，识别所有需要更新的导入语句
2. **迁移脚本**: 
   - 支持 dry-run 模式，安全预览变更
   - 分步执行：移动文件、更新导入
   - 创建向后兼容的代理文件
3. **测试脚本**: 记录迁移前的测试状态，便于回归验证

## 4. 向后兼容策略

### 4.1 代理文件
- 在原位置保留代理文件，使用 `DeprecationWarning` 提醒开发者
- 代理文件将转发所有导入到新位置
- 计划在 v2.0 版本移除这些代理文件

### 4.2 示例代理文件内容
```python
"""
向后兼容代理文件

此文件用于保持向后兼容性。
请使用新的导入路径：pktmask.adapters.processor_adapter
"""

import warnings
from pktmask.adapters.processor_adapter import *

warnings.warn(
    f"导入路径 '{__name__}' 已废弃，"
    f"请使用 'pktmask.adapters.processor_adapter' 替代。"
    f"此兼容性支持将在 v2.0 中移除。",
    DeprecationWarning,
    stacklevel=2
)
```

## 5. 风险评估

### 5.1 低风险
- ✅ 导入路径更新（自动化工具支持）
- ✅ 向后兼容（代理文件）
- ✅ 测试覆盖（已有测试基线）

### 5.2 中等风险
- ⚠️ 某些适配器文件可能不存在（需要在执行前确认）
- ⚠️ 动态导入可能无法自动检测
- ⚠️ IDE 或编辑器的缓存可能需要刷新

### 5.3 缓解措施
1. 执行前运行 dry-run 模式确认
2. 保留完整的 Git 历史，便于回滚
3. 分阶段执行，每步都进行测试验证

## 6. 执行建议

### 6.1 执行顺序
1. 确认所有适配器文件存在
2. 运行 `migrate_adapters.py --dry-run` 预览变更
3. 执行实际迁移
4. 运行测试验证功能正常
5. 提交变更

### 6.2 验证清单
- [ ] 所有适配器文件已成功移动
- [ ] 所有导入路径已更新
- [ ] 代理文件已创建
- [ ] 单元测试全部通过
- [ ] 无运行时警告（除了预期的废弃警告）

## 7. 后续步骤

1. **阶段二**: 开始实际的文件迁移和导入更新
2. **阶段三**: 执行全面的测试验证
3. **阶段四**: 更新文档和开发指南

## 总结

迁移准备工作已经完成，所有必要的工具和文档都已就位。建议在正式执行迁移前，再次确认所有适配器文件的存在性，并在测试环境中先行验证迁移脚本的正确性。
