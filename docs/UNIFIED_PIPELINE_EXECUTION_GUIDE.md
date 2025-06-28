# PktMask 统一流水线（长期治理）实施手册

> 版本：v1.0  撰写日期：2025-07-XX  
> 适用范围：GUI / CLI / MCP / Validator 全部入口  
> 目标读者：PktMask 核心开发者、QA 与 Dev-Ops

---

## 0. 背景
当前项目存在两条掩码执行链：

* **旧链路**：Enhanced Trimmer（TShark → PyShark → BlindPacketMasker），TLS-23 Validator 全部通过。
* **新链路**：轻量化 PipelineExecutor（DedupStage / AnonymizeStage / MaskStage），GUI 与 CLI 已切换，但缺乏协议感知，导致 TLS-23 掩码失效。

双轨维护成本高且容易产生结果不一致，故需统一到 **单一受 CI 保护的流水线**。

---

## 1. 总体方案
1. **Composite MaskStage**：对外仍叫 `MaskStage`，内部展开为三个子-Stage：
   1) `TSharkPreprocessorStage`
   2) `PySharkAnalyzerStage`
   3) `TcpPayloadMaskerAdapterStage`
2. **PipelineExecutor 展开规则**：遇到实现 `get_sub_stages()` 的 Stage 时，将其子列表展开并顺序执行。
3. **入口统一**：GUI、CLI、MCP、Validator 均调用 `PipelineExecutor.run()`，配置键保持 `dedup / anon / mask`。
4. **策略扩展机制**：PySharkAnalyzerStage 通过 StrategyFactory 自动发现 `ProtocolStrategy` 子类（TLS、HTTP…），动态生成 `MaskingRecipe`。
5. **CI Gate**：引入 TLS-23 + HTTP End-to-End Validator，所有入口必跑，全部通过方可合并。

---

## 2. 目录与类设计
```text
src/pktmask/
  core/
    pipeline/
      stages/
        mask_payload/
          __init__.py
          composite.py     # ← 新建，Composite MaskStage
        preprocess/
          tshark.py        # ← 原 TSharkPreprocessorStage
        analyze/
          pyshark.py       # ← 原 EnhancedPySharkAnalyzerStage
        apply/
          tcp_mask.py      # ← 原 TcpPayloadMaskerAdapterStage
```

### 2.1 CompositeMaskStage 核心接口
```python
class CompositeMaskStage(StageBase, CompositeStage):
    name = "MaskStage"

    def initialize(...):
        self._sub_stages = [TSharkPreprocessorStage(cfg),
                            PySharkAnalyzerStage(cfg),
                            TcpPayloadMaskerAdapterStage(cfg)]
        for s in self._sub_stages:  # 递归 init
            s.initialize()

    def get_sub_stages(self):
        return self._sub_stages
```

### 2.2 PipelineExecutor 修改
```python
for stage in user_defined_stages:
    if isinstance(stage, CompositeStage):
        stages.extend(stage.get_sub_stages())
    else:
        stages.append(stage)
```

---

## 3. 入口路由调整

| 入口 | 处理逻辑 | 影响代码 |
|------|-----------|----------|
| GUI | `PipelineManager._build_pipeline_config()` 仅设置 `mask.enabled = True`；不再指定静态配方 | `src/pktmask/gui/managers/pipeline_manager.py` |
| CLI | Typer 子命令 `pktmask mask` 直传相同配置；保留 `trim` 别名输出 DeprecationWarning | `src/pktmask/cli.py` |
| MCP | FastAPI `POST /process` JSON 中 `"mask":{"enabled":true}` | `src/pktmask/adapters/mcp/` |
| Validator | `EnhancedTrimmer` 内部改为调用 `PipelineExecutor.run()`，保证结果一致 | `scripts/validation/tls23_e2e_validator.py` |

---

## 4. 策略扩展指引（以 HTTP 为例）
1. 新建 `trim/strategies/http_mask_strategy.py`，实现 `ProtocolStrategy` 接口。
2. 在 `StrategyFactory.auto_register_strategies()` 自动发现并注册。
3. 配置可选参数示例：
   ```json
   {
     "mask": {
       "enabled": true,
       "strategies": {
         "http": {"enabled": true, "keep_body_bytes": 50}
       }
     }
   }
   ```
4. 单元测试覆盖常见 HTTP 场景；新增 `scripts/validation/http_e2e_validator.py`。

---

## 5. CI 流程
```yaml
jobs:
  build-test:
    steps:
      - run: pytest -q
      - run: python scripts/validation/tls23_e2e_validator.py \
              --input-dir tests/data/tls \
              --output-dir tmp/ci_tls
      - run: python scripts/validation/http_e2e_validator.py \
              --input-dir tests/data/http \
              --output-dir tmp/ci_http
```
• 任一验证脚本非 0 退出即失败。  
• 通过率 <100 % 将阻止 PR 合并。

---

## 6. 向后兼容与弃用策略
| 组件 | 处理方式 |
|-------|-----------|
| **EnhancedTrimmer** | 保留别名；`process_file()` 内部调用 `PipelineExecutor.run()` 并发 DeprecationWarning。|
| **静态 JSON 配方** | 移动到 `examples/recipes/`；文档标注学习用途，不在生产流程使用。|
| **旧 CLI flag `trim`** | 保留；输出 DeprecationWarning 并转发到 `mask` 子命令。|

---

## 7. 里程碑与人日估算
| 阶段 | 任务 | 负责人 | 预估 |
|------|------|--------|-------|
| 0 | 设计评审 & 文件结构调整 | Team | 0.5 d |
| 1 | CompositeMaskStage 实现 | Dev-A | 0.9 d |
| 2 | PipelineExecutor 展开支持 | Dev-B | 0.3 d |
| 3 | GUI/CLI/MCP 路由修改 | Dev-C | 0.3 d |
| 4 | EnhancedTrimmer 重定向 | Dev-C | 0.1 d |
| 5 | CI 脚本与 HTTP Validator | QA/Dev-Ops | 0.5 d |
| **合计** | **~2.6 人日** |

---

## 8. 验收标准
1. GUI、CLI、MCP、Validator 处理同一文件，生成的掩码输出二进制比对无差异。  
2. TLS-23 Validator 通过率 100 %。  
3. HTTP Validator 通过率 ≥95 %（小报文或边缘情况允许极少数 false-negative）。  
4. CI 全绿，无新增 DeprecationWarning。  
5. `pktmask --help` 仅列出 `mask / anon / dedup` 三个主命令，`trim` 标记弃用。

---

> **备注**：若未来再支持 QUIC、gRPC 等协议，仅需在「策略层」添加对应 `ProtocolStrategy` 并在 PySharkAnalyzerStage 中自动加载，无需触碰外层入口或 Pipeline 结构。 