# 名称冲突与重复命名分析

## 一、概述
在当前项目中，不同模块层级出现多套平行或相似命名，导致概念混淆和维护成本增加。下面列出主要冲突与重复命名点，供统一命名改造方案参考。

## 二、问题列表

1. **双重 PipelineAdapter**
   - 路径1：`src/pktmask/core/processors/pipeline_adapter.py`
   - 路径2：`src/pktmask/core/pipeline/stages/processor_stage_adapter.py`
   - 问题：两者都负责将 Processor 适配到流水线，但目录、类名、接口不一致。

2. **双重抽象基类：ProcessingStep vs StageBase**
   - `src/pktmask/core/base_step.py` 中的 `ProcessingStep`
   - `src/pktmask/core/pipeline/base_stage.py` 中的 `StageBase`
   - 问题：旧系统使用 `ProcessingStep` 派生 `*Step`，新系统使用 `StageBase` 派生 `*Stage`，概念隔离不清。

3. **旧“steps”目录 vs 新“pipeline/stages”目录**
   - 旧：`src/pktmask/steps/…`（GUI/CLI “Step” 实现）
   - 新：`src/pktmask/core/pipeline/stages/…`（新 “Stage” 实现）
   - 问题：两套代码并存，导入路径冲突，示例和文档需维护双份。

4. **Step vs Stage 后缀并存**
   - 如 `DeduplicationStep` vs `DeduplicationStage`
   - `IpAnonymizationStep` vs `IpAnonymizationStage`
   - `IntelligentTrimmingStep` vs `IntelligentTrimmingStage`
   - 问题：混用后缀，维护别名映射增加复杂度。

5. **Trimming vs Trimmer vs EnhancedTrimmer**
   - Stage 层：`trimming.py` 定义 `*TrimmingStage`
   - Processor 层：`trimmer.py` 定义 `class Trimmer`
   - 测试/脚本中：`EnhancedTrimmer`
   - 问题：不同层级使用不同术语，不易区分职责。

6. **掩码相关命名不一致**
   - Stage：`mask_payload/stage.py` 中的 `MaskStage`
   - Processor：`masking_processor.py` → `MaskingProcessor`
   - Applier：`scapy_mask_applier.py` → `ScapyMaskApplier`
   - TCP Payload：`tcp_payload_masker/…` → `TcpPayloadMasker`, `MaskApplier`
   - 配置/常量多处字符串 `"mask_payload"`
   - 问题：命名范围混杂，难以一目了然。

7. **Dedup vs Deduplicator**
   - Stage：`deduplication.py` 定义 `DeduplicationStage`
   - Processor：`deduplicator.py` 定义 `Deduplicator`
   - 问题：文件名、类名后缀不统一。

8. **Adapter 目录分散**
   - `core/processors/pipeline_adapter.py`
   - `core/pipeline/stages/processor_stage_adapter.py`
   - 拟议中：`core/adapters/…`
   - 领域层：`domain/adapters/…` 及 `tcp_payload_masker/api`
   - 问题：适配器分散在多层目录，命名难以集中管理。

9. **领域模型结果命名差异**
   - 域模型：`DeduplicationResult`, `TrimmingResult` 等
   - 与 `BaseStepResult`, `FileStepResults` 混用，别名映射 `remove_dupes`, `intelligent_trim` 并存
   - 问题：结果数据结构命名与处理逻辑命名不一致。

## 三、下一步
请将上述分析补充到“统一命名改造方案”文档中，或直接合并至重构方案，以确保改造过程中覆盖所有冲突点。 