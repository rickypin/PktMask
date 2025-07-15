# EnhancedMasker 概念澄清

## 概述

在项目的文档和代码中，存在对 `EnhancedMasker` 的多处引用。本文档澄清这个概念，明确其与现有类的关系。

## 核心发现

### `EnhancedMasker` 不是一个具体的类名

通过代码分析发现，`EnhancedMasker` 实际上是对以下组件的非正式引用：

1. **主要引用**: `TSharkEnhancedMaskProcessor`
   - 位置: `src/pktmask/core/processors/tshark_enhanced_mask_processor.py`
   - 描述: 基于TShark深度协议解析的增强掩码处理器

2. **次要引用**: `IntelligentMaskingStage` 的增强功能
   - 位置: `src/pktmask/stages/masking.py`
   - 描述: 智能掩码处理步骤，支持多层封装的载荷掩码处理

## 引用位置分析

### 1. 脚本中的引用
**文件**: `scripts/validation/tls23_e2e_validator.py`
```python
def run_pktmask_mask_internal(input_path: Path, output_path: Path, verbose: bool = False) -> None:
    """使用内部 EnhancedMasker 处理文件，避免启动 GUI。"""
    # 实际使用的是 TSharkEnhancedMaskProcessor
    from pktmask.core.processors.tshark_enhanced_mask_processor import TSharkEnhancedMaskProcessor
```

### 2. 文档中的引用
在以下文档中发现对 `EnhancedMasker` 的引用：
- `docs/ENHANCED_MASKER_DEPRECATION_PLAN.md`
- `docs/ENHANCED_MASKER_DELETION_PLAN.md`
- 多个技术报告和分析文档

这些引用主要是在描述载荷处理增强功能时使用的术语。

### 3. 测试文件中的引用
测试文件中对 `EnhancedMasker` 的引用主要出现在注释和描述中，实际测试的是：
- `IntelligentMaskingStage` 类
- `TSharkEnhancedMaskProcessor` 类

## 命名统一建议

### 推荐做法
1. **在代码中**: 使用具体的类名
   - `TSharkEnhancedMaskProcessor` - 用于基于TShark的增强掩码处理
   - `IntelligentMaskingStage` - 用于智能载荷掩码

2. **在文档中**: 明确指代
   - "增强载荷处理器" - 指代 `TSharkEnhancedMaskProcessor`
   - "增强掩码阶段" - 指代 `IntelligentMaskingStage`

3. **避免使用**: `EnhancedMasker` 作为类名或接口名

### 迁移建议
对于现有文档中的 `EnhancedMasker` 引用：

1. **技术文档**: 用具体类名替换
2. **用户文档**: 用功能描述替换（如"增强载荷处理功能"）
3. **注释代码**: 更新为准确的类名引用

## 与 Step/Stage 统一的关系

`EnhancedMasker` 概念澄清是 Step/Stage 命名统一工作的补充：

1. **不冲突**: `EnhancedMasker` 不是类名，不与 Step/Stage 后缀统一冲突
2. **互补**: 澄清概念有助于减少命名混淆
3. **一致性**: 推动使用准确、一致的命名约定

## 实施行动

### 已完成
- ✅ 识别和分析所有 `EnhancedMasker` 引用
- ✅ 明确其与现有类的关系
- ✅ 制定命名建议

### 待完成
- [ ] 更新技术文档中的引用
- [ ] 更新代码注释中的引用
- [ ] 统一用户文档中的术语

## 结论

`EnhancedMasker` 是一个非正式的概念术语，而不是具体的类名。在 Step/Stage 命名统一的框架下，应该：

1. 使用准确的类名：`TSharkEnhancedMaskProcessor` 和 `IntelligentMaskingStage`
2. 在文档中使用清晰的功能描述
3. 避免创建名为 `EnhancedMasker` 的类或接口

这种澄清有助于保持代码库的命名一致性，减少概念混淆。

---

*最后更新: 2025-07-08*
*状态: 概念澄清完成*
