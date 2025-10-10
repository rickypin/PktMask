# CLI与GUI共享核心总结

## 快速回答

### ✅ 是的，CLI和GUI完全共享核心处理逻辑

**共同调用点：**
1. **最终执行点:** `PipelineExecutor.run()` - `src/pktmask/core/pipeline/executor.py:53`
2. **统一接口:** `ConsistentProcessor` - `src/pktmask/core/consistency.py`
3. **配置构建:** `PipelineExecutor.__init__(config)` - `src/pktmask/core/pipeline/executor.py:45`

---

## 核心架构

```
┌─────────────┐         ┌─────────────┐
│     CLI     │         │     GUI     │
│  commands   │         │  managers   │
└──────┬──────┘         └──────┬──────┘
       │                       │
       │                       │
       └───────┬───────────────┘
               │
               ▼
    ┌──────────────────────┐
    │ ConsistentProcessor  │  ← 统一接口层
    │  (consistency.py)    │
    └──────────┬───────────┘
               │
               ▼
    ┌──────────────────────┐
    │  PipelineExecutor    │  ← 核心执行引擎
    │   (executor.py)      │
    └──────────┬───────────┘
               │
               ▼
    ┌──────────────────────┐
    │  Processing Stages   │  ← 处理阶段
    │  - Dedup             │
    │  - Anonymize         │
    │  - Mask              │
    └──────────────────────┘
```

---

## 调用路径对比

### CLI调用路径
```
用户命令
  ↓
cli/commands.py::process_command()
  ↓
ConsistentProcessor.process_file()
  ↓
ConsistentProcessor.create_executor()
  ↓
PipelineExecutor(config)
  ↓
executor.run(input, output)
  ↓
遍历执行各个Stage
  ↓
返回ProcessResult
```

### GUI调用路径
```
用户点击Start
  ↓
gui/managers/pipeline_manager.py::start_pipeline_processing()
  ↓
GUIConsistentProcessor.create_executor_from_gui()
  ↓
ConsistentProcessor.create_executor()  ← 与CLI汇合
  ↓
PipelineExecutor(config)
  ↓
GUIServicePipelineThread.run()
  ↓
executor.run(input, output, progress_cb)
  ↓
遍历执行各个Stage (与CLI完全相同)
  ↓
返回ProcessResult → Qt信号
```

---

## 关键代码位置

### 1. 统一接口层 (100%共享)

**文件:** `src/pktmask/core/consistency.py`

```python
class ConsistentProcessor:
    @staticmethod
    def create_executor(dedup, anon, mask, mask_protocol="auto") -> PipelineExecutor:
        """CLI和GUI都调用这个方法创建执行器"""
        config = {}
        if dedup:
            config["remove_dupes"] = {"enabled": True}
        if anon:
            config["anonymize_ips"] = {"enabled": True}
        if mask:
            config["mask_payloads"] = {
                "enabled": True,
                "protocol": mask_protocol,
                "mode": "enhanced"
            }
        return PipelineExecutor(config)  # ← 共同调用点
```

### 2. 核心执行引擎 (100%共享)

**文件:** `src/pktmask/core/pipeline/executor.py`

```python
class PipelineExecutor:
    def run(self, input_path, output_path, progress_cb=None) -> ProcessResult:
        """CLI和GUI最终都执行这个方法"""
        # 1. 验证输入
        # 2. 创建临时目录
        # 3. 遍历stages执行
        for stage in self.stages:
            stats = stage.process_file(current_input, stage_output)
            if progress_cb:
                progress_cb(stage, stats)  # CLI不传，GUI传Qt信号
        # 4. 返回结果
        return ProcessResult(...)
```

### 3. CLI调用

**文件:** `src/pktmask/cli/commands.py:115`

```python
def _process_single_file(...):
    result = ConsistentProcessor.process_file(
        input_path, output_path, 
        dedup, anon, mask, mask_protocol
    )
```

### 4. GUI调用

**文件:** `src/pktmask/gui/core/gui_consistent_processor.py:57-61`

```python
@staticmethod
def create_executor_from_gui(remove_dupes_checked, anonymize_ips_checked, mask_payloads_checked):
    # 转换参数名后调用相同的核心
    return ConsistentProcessor.create_executor(
        dedup=remove_dupes_checked,
        anon=anonymize_ips_checked,
        mask=mask_payloads_checked
    )
```

---

## 共享程度分析

### ✅ 100%共享的部分

| 组件 | 位置 | 说明 |
|------|------|------|
| **PipelineExecutor** | `core/pipeline/executor.py` | 核心执行引擎 |
| **ConsistentProcessor** | `core/consistency.py` | 统一接口 |
| **配置构建逻辑** | `ConsistentProcessor.create_executor()` | 配置生成 |
| **验证逻辑** | `ConsistentProcessor.validate_options()` | 参数验证 |
| **Stage装配** | `PipelineExecutor._build_pipeline()` | 动态装配 |
| **执行流程** | `PipelineExecutor.run()` | 处理流程 |
| **错误处理** | `PipelineExecutor.run()` | 异常处理 |
| **结果格式** | `ProcessResult` | 返回数据结构 |

### ⚠️ 适配层差异（不影响核心）

| 方面 | CLI | GUI | 影响核心？ |
|------|-----|-----|-----------|
| **参数来源** | 命令行参数 | Checkbox状态 | ❌ 否 |
| **线程模型** | 同步阻塞 | 异步QThread | ❌ 否 |
| **进度反馈** | 控制台输出 | Qt信号 | ❌ 否 |
| **结果展示** | 文本格式化 | GUI更新 | ❌ 否 |
| **协议参数** | 用户指定 | 固定值 | ❌ 否* |

*注：协议参数虽然来源不同，但都传递给相同的核心逻辑处理。

---

## 设计优势

### 1. 结果一致性保证
- CLI和GUI处理相同文件得到**完全相同**的结果
- 无论使用哪个界面，底层算法完全一致

### 2. 维护成本降低
- 核心逻辑只需维护**一份代码**
- Bug修复自动应用到两个界面
- 新功能添加一次即可

### 3. 测试覆盖率提升
- 测试核心逻辑即可覆盖两个界面
- 减少重复测试工作

### 4. 扩展性增强
- 未来添加新界面（Web UI、MCP等）可直接复用核心
- 只需实现适配层

### 5. 代码质量提升
- 减少代码重复
- 降低不一致风险
- 提高可读性和可维护性

---

## 唯一的实质性差异

### 协议参数来源

**CLI:**
```bash
pktmask process input.pcap --mask --mask-protocol auto
```
- 用户通过 `--mask-protocol` 参数指定
- 支持: `tls`, `http`, `auto`

**GUI:**
```python
# 硬编码在代码中
mask_protocol = "tls"  # 传统模式
# 或
mask_protocol = "auto"  # 新模式（特性标志控制）
```
- 无用户控制界面
- 由特性标志决定

**但是：** 一旦参数传入 `ConsistentProcessor`，后续处理**完全相同**。

---

## 验证方法

### 如何验证两者使用相同核心？

1. **查看导入语句:**
   ```python
   # CLI
   from ..core.consistency import ConsistentProcessor
   
   # GUI
   from ...core.consistency import ConsistentProcessor
   ```
   两者导入同一个类。

2. **追踪调用链:**
   - CLI: `commands.py` → `ConsistentProcessor.process_file()` → `PipelineExecutor.run()`
   - GUI: `pipeline_manager.py` → `GUIConsistentProcessor` → `ConsistentProcessor.create_executor()` → `PipelineExecutor.run()`
   
   最终都到达 `PipelineExecutor.run()`。

3. **检查配置格式:**
   ```python
   # CLI和GUI生成的配置格式完全相同
   config = {
       "remove_dupes": {"enabled": True},
       "anonymize_ips": {"enabled": True},
       "mask_payloads": {
           "enabled": True,
           "protocol": "auto",  # 唯一可能不同的值
           "mode": "enhanced"
       }
   }
   ```

4. **对比处理结果:**
   - 使用相同输入文件
   - 使用相同处理选项
   - CLI和GUI输出文件应该**字节级完全相同**

---

## 架构图例

### 层次结构

```
┌─────────────────────────────────────────────────┐
│              表现层 (Presentation)               │
│  ┌──────────────┐         ┌──────────────┐     │
│  │     CLI      │         │     GUI      │     │
│  │   Typer      │         │    PyQt6     │     │
│  └──────────────┘         └──────────────┘     │
└─────────────────┬───────────────┬───────────────┘
                  │               │
┌─────────────────┴───────────────┴───────────────┐
│              适配层 (Adapter)                    │
│  ┌──────────────┐         ┌──────────────┐     │
│  │  直接调用     │         │ GUI包装器     │     │
│  └──────────────┘         └──────────────┘     │
└─────────────────┬───────────────┬───────────────┘
                  │               │
                  └───────┬───────┘
┌─────────────────────────┴───────────────────────┐
│           统一接口层 (Unified Interface)         │
│          ConsistentProcessor                    │
│  - create_executor()                           │
│  - process_file()                              │
│  - validate_options()                          │
└─────────────────────────┬───────────────────────┘
                          │
┌─────────────────────────┴───────────────────────┐
│           核心引擎层 (Core Engine)               │
│          PipelineExecutor                       │
│  - __init__(config)                            │
│  - run(input, output, progress_cb)             │
│  - _build_pipeline(config)                     │
└─────────────────────────┬───────────────────────┘
                          │
┌─────────────────────────┴───────────────────────┐
│           处理层 (Processing)                    │
│  - DeduplicationStage                          │
│  - IPAnonymizationStage                        │
│  - MaskPayloadStage                            │
└─────────────────────────────────────────────────┘
```

---

## 总结

### 核心要点

1. ✅ **CLI和GUI 100%共享核心处理逻辑**
2. ✅ **共同调用点是 `PipelineExecutor.run()`**
3. ✅ **通过 `ConsistentProcessor` 统一接口**
4. ✅ **配置构建、验证、执行完全相同**
5. ⚠️ **唯一差异是协议参数来源（不影响核心）**

### 设计模式

- **Facade模式:** `ConsistentProcessor` 统一门面
- **Strategy模式:** 配置驱动的Stage装配
- **Template Method:** `PipelineExecutor.run()` 执行模板
- **Adapter模式:** `GUIConsistentProcessor` GUI适配

### 文档参考

- 详细分析: `docs/dev/CLI_GUI_SHARED_CORE_ANALYSIS.md`
- 功能差异: `docs/dev/CLI_GUI_FUNCTIONAL_DIFFERENCES_ANALYSIS.md`
- 流程图: 已通过Mermaid渲染展示

---

**结论:** CLI和GUI是同一个核心引擎的两个不同用户界面，确保了处理结果的完全一致性。

