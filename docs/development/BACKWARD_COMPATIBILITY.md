# 向后兼容性说明

## 概述

PktMask 在保持公共接口签名不变的同时，对部分配置项进行了现代化升级。本文档说明了这些变更以及如何迁移到新的配置方式。

## 公共接口保持不变

以下核心接口的签名保持完全不变，确保现有代码的兼容性：

### 1. `__init__` 方法
所有类的构造函数签名保持不变：
- `MaskStage.__init__(self, config: Optional[Dict[str, Any]] | None = None)`
- `BaseProcessor.__init__(self, config: ProcessorConfig)`
- `PipelineExecutor.__init__(self, config: Optional[Dict] | None = None)`

### 2. `initialize` 方法
初始化方法签名保持不变：
- `BaseProcessor.initialize(self) -> bool`
- `MaskStage.initialize(self, config: Optional[Dict[str, Any]] | None = None) -> None`

### 3. `process_file` 方法
文件处理方法签名保持不变：
- `BaseProcessor.process_file(self, input_path: str, output_path: str) -> ProcessorResult`
- `MaskStage.process_file(self, input_path: str | Path, output_path: str | Path) -> StageStats | Dict[str, Any] | None`

## 废弃的配置项

### 1. `recipe_dict` 配置项

**状态**: 已废弃，将在未来版本中移除  
**替代方案**: 使用 `processor_adapter` 模式或直接传入 `MaskingRecipe` 对象

**废弃行为**:
- 系统会发出 `DeprecationWarning` 警告
- 配置项被忽略，不会抛出错误
- 操作将以透传模式继续执行以保持兼容性

### 2. `recipe_path` 配置项

**状态**: 已废弃，将在未来版本中移除  
**替代方案**: 使用 `processor_adapter` 模式进行智能协议分析

**废弃行为**:
- 系统会发出 `DeprecationWarning` 警告
- 配置项被忽略，不会抛出错误
- 操作将以智能模式继续执行以保持兼容性

## 新版本推荐的配置方式

### 1. 使用 Processor Adapter 模式（推荐）

```python
config = {
    "mask": {
        "enabled": True,
        "mode": "processor_adapter"  # 智能协议分析模式
    }
}
```

**优势**:
- 自动协议识别和分析
- 智能掩码策略应用
- 更好的性能和准确性

### 2. 通过编程接口直接传入 MaskingRecipe 对象

```python
from pktmask.core.tcp_payload_masker.api.types import MaskingRecipe

recipe = MaskingRecipe(...)  # 创建配方对象
config = {
    "mask": {
        "enabled": True,
        "recipe": recipe,  # 直接传入对象
        "mode": "basic"
    }
}
```

## 迁移指南

### CLI 用户

**旧的使用方式**:
```bash
pktmask mask input.pcap -o output.pcap --recipe-path config/recipe.json
```

**新的使用方式**:
```bash
pktmask mask input.pcap -o output.pcap --mode processor_adapter
```

### GUI 用户

GUI 界面已自动更新为使用新的配置方式，无需用户手动迁移。

### 编程接口用户

**旧的配置方式**:
```python
config = {
    "mask": {
        "enabled": True,
        "recipe_path": "config/recipe.json",
        "recipe_dict": {...}
    }
}
```

**新的配置方式**:
```python
# 方式1：使用智能模式（推荐）
config = {
    "mask": {
        "enabled": True,
        "mode": "processor_adapter"
    }
}

# 方式2：直接传入 MaskingRecipe 对象
config = {
    "mask": {
        "enabled": True,
        "recipe": recipe_object,
        "mode": "basic"
    }
}
```

## 警告消息示例

当使用废弃配置项时，您会看到类似以下的警告消息：

```
DeprecationWarning: 配置项 recipe_dict, recipe_path 已废弃，将在未来版本中移除。
这些配置项已被忽略，请使用新的配置方式：直接传入 MaskingRecipe 对象到 'recipe' 键，
或使用 processor_adapter 模式进行智能协议分析。
当前操作将以透传模式继续执行以保持兼容性。
```

## 时间表

- **当前版本**: 废弃配置项继续工作，但会发出警告
- **下一个主要版本**: 废弃配置项将被完全移除
- **建议**: 请尽快迁移到新的配置方式

## 支持

如果您在迁移过程中遇到问题，请：

1. 查看本文档的迁移指南
2. 检查日志中的警告消息
3. 参考代码示例进行配置更新
4. 如有疑问，请提交 issue 或联系开发团队

## 版本兼容性矩阵

| 配置项 | v0.1.0 | v0.2.0+ | 计划移除版本 |
|--------|---------|---------|-------------|
| `recipe_dict` | ✅ 支持 | ⚠️ 废弃（继续工作） | v1.0.0 |
| `recipe_path` | ✅ 支持 | ⚠️ 废弃（继续工作） | v1.0.0 |
| `mode: "processor_adapter"` | ❌ 不支持 | ✅ 推荐 | - |
| `recipe` (对象) | ❌ 不支持 | ✅ 支持 | - |
