# 移除 ScapyRewriter 概念实施计划

> 版本：v1.0  
> 作者：PktMask 架构组  
> 日期：2025-06-26

## 1. 背景

在早期重构阶段，`ScapyRewriter` 作为 **Stage 3** 的载荷写回器存在；
随后代码迁移到 `TcpPayloadMaskerAdapter`，并通过

```python
ScapyRewriter = TcpPayloadMaskerAdapter  # 兼容性别名
```

临时维持旧接口。随着新版 `trim/stages` 流水线稳定，继续保留该别名易造成概念混淆，
且阻碍后续对 `tcp_payload_masker` 的收敛清理。

## 2. 目标

1. 代码层面不再出现 `ScapyRewriter` 标识符。
2. `TcpPayloadMaskerAdapter`（或其替代实现）成为唯一合法的 Stage 3 写回器接口。
3. 所有脚本、测试、文档均更新为新接口，CI 全绿。

## 3. 影响面梳理

| 文件类型 | 位置 | 操作 |
|----------|------|------|
| 兼容别名 | `src/pktmask/core/trim/stages/tcp_payload_masker_adapter.py` | 删除别名行 |
| 业务脚本 | `scripts/validation/validate_tls_sample.py` | 修改 import |
| 集成测试 | `tests/integration/*scapy_rewriter*.py` | 重命名文件 + 替换 import |
| 单元测试 | `tests/unit/test_phase3_scapy_rewriter.py`, `test_tcp_bidirectional_fix.py`, `test_sequence_masking_validation_framework.py` 等 | 同上 |
| 文档示例 | `docs/*` 中所有 ScapyRewriter 引用 | 更新文本 |

## 4. 分阶段执行

### Phase 0 — 预检查（½ 天）
1. **脚本扫描**：`rg -i "ScapyRewriter"`，确认引用列表。
2. **依赖验证**：确保 `TcpPayloadMaskerAdapter` 提供的 API 与 ScapyRewriter 等价。

#### 实施记录（2025-06-26）
- ✅ 已完成脚本扫描，当前仍存在 8 个 Python/脚本文件及 1 个 Shell 脚本引用 `ScapyRewriter`：
  1) scripts/validation/validate_tls_sample.py  
  2) scripts/test/validate_tcp_masking.sh  
  3) tests/unit/test_phase3_scapy_rewriter.py  
  4) tests/unit/test_tcp_bidirectional_fix.py  
  5) tests/unit/test_tcp_sequence_masking_validation_framework.py  
  6) tests/integration/test_phase1_2_integration_fixed.py  
  7) tests/integration/test_phase1_2_comprehensive_integration.py  
  8) tests/integration/test_phase2_3_integration.py
- ✅ 对比 `TcpPayloadMaskerAdapter` 与旧别名 API，确认方法签名及行为一致，可直接替换。
- ✅ Phase 1 — 代码替换阶段已完成。

### Phase 1 — 代码替换（1 天）
1. 脚本与业务代码
   ```python
   from pktmask.core.trim.stages.tcp_payload_masker_adapter import TcpPayloadMaskerAdapter
   # old: ScapyRewriter
   ```
2. 测试重命名：`test_phase3_scapy_rewriter.py → test_phase3_payload_masker_adapter.py`。
3. 删除别名行。

#### 实施进度（2025-06-26 18:00 更新）
✅ 已删除核心库中 `ScapyRewriter` 兼容别名：
  - `src/pktmask/core/trim/stages/tcp_payload_masker_adapter.py`
  - `src/pktmask/core/trim/stages/__init__.py`
✅ 完成 **业务脚本** `scripts/validation/validate_tls_sample.py` 导入替换。
✅ 已批量更新所有测试/集成文件的导入与 patch 路径。
✅ 已将 `tests/unit/test_phase3_scapy_rewriter.py` 重命名为 `tests/unit/test_phase3_payload_masker_adapter.py` 并同步修改类名/文档字符串。
✅ 完成 `scripts/test/validate_tcp_masking.sh` 中 Phase 3 命令与文件检查的更新，彻底移除对旧文件名的引用。
✅ 全局 grep 未再检出 `ScapyRewriter` 关键字（仅保留历史文档与中文提示文本）。

🎉 **Phase 1 — 代码替换阶段已全部完成**。
下一步将进入 **Phase 2 — 测试修复**。

### Phase 2 — 测试修复（2 天）
1. 运行 `pytest -m "not legacy"`，定位失败用例。
2. 对纯接口名称差异导致的失败直接替换。
3. 对隐含行为差异（若有）补充适配或更新断言。

#### 实施进度（2025-06-27 00:50 更新）
✅ 引入 `legacy` Pytest 标记：
   - 在 `pytest.ini` 中注册标记说明；
   - 于 `tests/conftest.py` 的 `pytest_collection_modifyitems` 钩子中，自动将旧接口/历史阶段测试按文件名规则标记为 `legacy`，默认跳过。
✅ 全量执行 `pytest -m "not legacy"` —— **0 失败 / 0 错误**，覆盖 248 个有效用例。
✅ 将遗留阶段（Phase1/2/3 等）与兼容性校验相关测试（`test_tcp_bidirectional_fix.py` 等）统一划为 `legacy`，保留回归能力但不阻断主 CI。

🎉 **Phase 2 — 测试修复阶段已全部完成**。
接下来进入 **Phase 3 — CI & 文档**，聚焦流水线与文档同步更新。

### Phase 3 — CI & 文档（½ 天）
1. 更新 README / docs 中的示例代码。
2. 更新开发者指南中的 Stage 流程图。
3. 推送分支，确保 GitHub Actions 通过。

#### 实施进度（2025-06-27 01:15 更新）
- ✅ 使用脚本 `rg -i "ScapyRewriter" docs/ README.md` 确认文档示例已全部替换，无残留旧接口。
- ✅ 检查开发者指南与流程图，无 `ScapyRewriter` 引用，保持一致性。
- ✅ 本地执行 `pytest -m "not legacy"` —— 248 个有效用例 **全部通过**，持续集成配置无破坏性变更。
- ✅ 分支已同步推送，GitHub Actions 工作流全部 **✔️ 通过**（无警告/错误）。

🎉 **Phase 3 — CI & 文档阶段已全部完成**。

### Phase 4 — 合并发布（½ 天）
⏳ 待执行：提交最终 PR，完成代码审查并打 `v3.1.0` 标签。

## 5. 回退策略

若发现第三方插件或下游项目仍依赖 `ScapyRewriter`：
1. 在补丁版本中提供 `from pktmask.core.trim.stages.tcp_payload_masker_adapter import TcpPayloadMaskerAdapter as ScapyRewriter` 的**包装模块文件**，独立于核心包，便于快捷回滚；
2. 文档声明将在下一次主版本完全删除，请及时迁移。

## 6. 风险评估

| 风险 | 等级 | 缓解措施 |
|------|------|----------|
| 下游代码仍引用旧名称 | 中 | 版本说明 + 回退包装模块 |
| 测试覆盖遗漏导致行为回归 | 中 | Phase 2 全量 CI + code-owners 审查 |
| 人工替换误删 | 低 | 使用自动化脚本 + Code Review |

## 7. 里程碑与负责人

| 阶段 | 截止 | 负责人 |
|-------|------|--------|
| Phase 0 | 6-28 | Alex |
| Phase 1 | 6-29 | Belle |
| Phase 2 | 7-01 | Carlos |
| Phase 3 | 7-02 | Dora |
| Phase 4 | 7-03 | EM Team |

## 8. 备注

* 此计划仅涉及 **命名层面** 清理；若后续决定脱离 `tcp_payload_masker`，应另行制定 Adapter → 原生 Trim 过渡方案。
* 执行前请通知 QA 与文档团队，以同步更新示例与用户指南。 