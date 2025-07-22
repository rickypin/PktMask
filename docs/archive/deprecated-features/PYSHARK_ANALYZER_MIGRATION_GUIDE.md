# PySharkAnalyzer 迁移指南

## 概述

从 PktMask v3.0 开始，过时的 PySharkAnalyzer 实现已被移除。如果您的代码或配置中使用了 PySharkAnalyzer，请参考以下迁移指南。

## 迁移说明

### 替换组件
- **旧组件**: `PySharkAnalyzer`
- **新组件**: `EnhancedPySharkAnalyzer`

### 主要变更
1. `PySharkAnalyzer` 已完全移除
2. 请使用 `EnhancedPySharkAnalyzer` 替代
3. 新组件提供更好的性能和更完整的功能

### 配置迁移
如果您的配置文件中包含 PySharkAnalyzer 相关配置，请按以下方式更新：

```yaml
# 旧配置（已废弃）
analyzer:
  type: "PySharkAnalyzer"
  timeout: 300

# 新配置
analyzer:
  type: "EnhancedPySharkAnalyzer"
  timeout: 300
  enable_protocol_detection: true
  tls_strategy_enabled: true
```

### 代码迁移
如果您的代码中直接使用了 PySharkAnalyzer：

```python
# 旧代码（已废弃）
from pktmask.core.pyshark_analyzer import PySharkAnalyzer

# 新代码
from pktmask.core.pipeline.stages.analyze.pyshark import EnhancedPySharkAnalyzer
```

## 获取帮助

如果您在迁移过程中遇到问题，请：
1. 查看最新的 API 文档
2. 提交 Issue 到项目仓库
3. 联系技术支持

## 兼容性说明

- 新组件完全兼容旧组件的功能
- 配置格式基本保持一致
- 性能和稳定性有显著提升
