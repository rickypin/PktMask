# PktMask 轻量化重构方案与实施计划

> 版本：v0.1   撰写日期：2025-06-XX

---

## 0. 读取指北
本文件为 **PktMask** 下一轮重构的唯一依据，所有后续 PR / 任务拆分请对照本文件。文档遵循「先原则、后细节、再里程碑」结构。

---

## 1. 背景与动机
| 维度 | 现状 | 问题 |
|------|------|------|
| 功能管线 | TSharkEnhancedMaskProcessor（三阶段智能处理）<br/>统一的 PipelineExecutor 架构 | 架构已统一，维护成本降低 |
| 入口 | GUI + 部分脚本调用 | MCP/CLI 缺失，难以嵌入自动化流程 |
| 模块耦合 | GUI 内部直接实例化 Processor<br/>Stage ↔ GUI 回调大量交叉 | 代码层面 GUI 与核心算法耦合偏紧，影响后续扩展 |
| 用户体验 | GUI 交互/视觉成熟、被大量用户依赖 | **必须 100 % 保持不变** |

---

## 2. 重构目标（Must / Should / Could）
| 级别 | 目标 |
|------|------|
| **Must** |
|  | 1. **用户 GUI 行为、视觉、功能 100 % 原样**；改动对终端用户透明。|
|  | 2. 单一 Pre-process Pipeline，同一套 Stage 支撑 Dedup / IP Anon / Mask。|
|  | 3. GUI、CLI、MCP 三入口共享 Pipeline，核心业务无 UI 依赖。|
|  | 4. **TLS-23 Validator 依旧可直接验证改造后产物**（无需与旧版比对，仅需通过校验）。|
| **Should** |
|  | 5. 轻量依赖：标准库 + `pydantic` + `typer` + `fastapi`（可选）。|
|  | 6. 打包仍可用 PyInstaller 单文件；GUI 版不强依赖 FastAPI/Typer。|
| **Could** |
|  | 7. 可插拔 Stage 机制，为未来功能添加 (e.g. HTTP 清洗) 留接口。|

---

## 3. 统一命名与术语
| 逻辑功能 | **正式名称** | 缩写 / CLI Flag | Stage 类名 | 旧名称 | Deprecation 策略 |
|-----------|-------------|-----------------|-----------|--------|------------------|
| 去重      | Deduplicate | `dedup`         | `DedupStage` | `Deduplicator` | 保留旧 Processor 1 版本，`DeprecationWarning` → 移除 |
| IP 匿名化 | IP Anonymize| `anon`          | `AnonStage`  | `IPAnonymizer`  | 同上 |
| 载荷掩码  | Payload Mask| `mask`          | `MaskStage`  | `EnhancedTrimmer` / `trim_packet` | 同上 |

* **配置键**：统一使用 `dedup / anon / mask`，示例见 §7。
* **ProcessorRegistry**：键分别为 `dedup_packet`, `anon_ip`, `mask_payload`；旧键映射输出 DeprecationWarning。
* **文件/目录**：`stages/dedup.py`, `stages/anon_ip.py`, `stages/mask_payload/`。

---

## 4. 目标架构（够用的 Clean-ish）
```
╭─ adapters/ ───────────────────────────────────────╮
│   gui/    Qt6 UI (保持原 layout & signals)        │
│   cli/    Typer CLI   →  pktmask trim …           │
│   mcp/    FastAPI     →  POST /process            │
╰──────────────────┬───────────────────────────────╯
                   │ (dict config + progress cb)
               core.pipeline.executor
                   │
        ┌──────────┴──────────┬───────────┐
 DedupStage   AnonymizeStage   MaskStage
(可选)        (可选)           (可选, BlindPacketMasker)
```

### 4.1 关键说明
1. **Stage 可开关**：GUI 勾选框、CLI Flag、MCP JSON→`config`，由 `executor.build_pipeline(config)` 动态装配。  
2. **旧 Processor 别名**：`core/processors/enhanced_trimmer.py` 保留，但内容仅 `class EnhancedTrimmer(MaskingProcessor): pass`，保证验证器与旧脚本不崩。  
3. **数据模型**：`core.pipeline.models` 中定义 `PacketList`, `StageStats`, `ProcessResult`（pydantic）。  
4. **Progress 回调**：`executor.run(progress_cb=…)`；GUI 传 Qt Signal，其它入口可忽略或打印。  
5. **TLS-23 E2E**：Validator 默认走 CLI 路径；`--mode old|new` 比对输出 JSON。  

### 4.2 命名调整说明
* **Processor & CLI 名称统一由 `trim` → `mask`**：
  * `ProcessorRegistry` 键从 `trim_packet` 调整为 `mask_payload`。
  * CLI 子命令从 `pktmask trim` → `pktmask mask`（保留旧别名 `trim`，显示 DeprecationWarning）。
  * GUI 文案仍显示"Trim Payloads"以避免用户感知变化，但内部调用 `mask_payload` Processor。

* 旧接口别名策略：
  ```python
  # core/processors/enhanced_trimmer.py
  class EnhancedTrimmer(MaskingProcessor):
      """Deprecated alias for backward-compat."""
  ```

  运行时若检测到旧名称调用，会通过 `warnings.warn("EnhancedTrimmer is deprecated; use MaskingProcessor", DeprecationWarning)` 提示。

---

## 5. 任务拆分 & 里程碑
| Phase | 目标 & 交付 | 预计 | Owner |
|-------|-------------|------|-------|
| 0 | 文档评审、冻结契约 (`ProcessResult`, Stage 接口) | 0.5 d ✅ (完成于 2025-06-28) | ALL |
| 1 | 抽出 **MaskStage** (`engine.blind_masker.py`)→`stages/mask_payload/`<br/>编译通过 & 单测绿 ✅ (完成于 2025-06-28) | 1 d | Dev-A |
| 2 | 新建 **pipeline.executor / stage_base**<br/>实现 `DedupStage`、`AnonStage` 包装现有算法；同步替换 ProcessorRegistry 键 **✅ (完成于 2025-06-29，实际耗时 0.5 d)** | 1.5 d | Dev-B |
| 3 | **Thin-Alias 层**：EnhancedTrimmer→MaskingProcessor；ProcessorRegistry 映射更新；确保 GUI 运行无感 **✅ (完成于 2025-06-30，实际耗时 0.5 d)** | 1 d | Dev-C |
| 4 | **CLI Adapter**：`pktmask trim …` with Typer；在 CI 跑单测+TLS23 E2E（new pipeline） **✅ (完成于 2025-07-01，实际耗时 0.4 d)** | 0.5 d | Dev-D |
| 5 | **MCP Adapter**：FastAPI 20 行 Demo；文档 `docs/mcp_api.md` **✅ (完成于 2025-07-02，实际耗时 0.4 d)** | 0.5 d | Dev-E |
| 6 | **GUI 调用迁移**：内部改用 executor，外观/交互零变化；手工 & 自动 UI 回归 **✅ (完成于 2025-06-29，实际耗时 0.5 d)** | 1 d | Dev-A+B |
| 7 | **E2E 验证**：使用 TLS-23 Validator 验证新 Pipeline 产物；CI Gate **✅ (完成于 2025-07-03，实际耗时 0.3 d)** | 0.5 d | QA |
| 8 | 清理旧 tcp_payload_masker 目录（留 shim + DeprecationWarning） | 0.5 d | Dev-C |
| **总计** | **7.5 人日**（以 5d Sprint 计算 ≈ 1.5 周） |  |  |

---

## 6. 准入检查清单（Pre-merge Gate）
1. 代码全局搜索 **`EnhancedTrimmer`**, **`trim_packet`**, **`IPAnonymizer`**, **`Deduplicator`** → 仅剩别名 shim + DeprecationWarning。  
2. CLI `pktmask --help` 列出 `mask`、`dedup`、`anon` 子命令，`trim`/旧 flags 打出 DeprecationWarning。  
3. GUI 勾选框文本与旧版一致，但后台日志应输出新 Stage 名。
4. E2E TLS-23 Validator 成功（exit 0）。
5. 单元测试无 `DeprecationWarning` 除 alias shim 触发者外。

---

## 7. 附录
### 7.1 示例 CLI 命令
```bash
# 新推荐
pktmask mask sample.pcap -o sample_processed.pcap \
        --dedup --anon hierarchical --mask tls

# 兼容旧写法（将打印 DeprecationWarning）
pktmask trim sample.pcap -o sample_processed.pcap --dedup --anon --mask tls
```

### 7.2 MCP 请求示例
```json
POST /process HTTP/1.1
{
  "input_path": "sample.pcapng",
  "output_path": "out.pcapng",
  "steps": {
    "dedup": {"enabled": true},
    "anon": {"enabled": true, "strategy": "hierarchical"},
    "mask": {"enabled": true, "tls_mode": "mask-after-5"}
  }
}
```

---

> **后续更新**：若需求或优先级变化，请 PR 修改本文件并在导读区更新版本号。 