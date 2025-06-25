# Phase 2（修订版）：PyShark → Blind TCP Payload Masker 集成实施方案

> 本文档在原 `PHASE2_PYSHARK_ANALYZER_INTEGRATION.md` 基础上，融合了近期评审提出的六项关键改进（编号 2 / 3 / 4 / 5 / 6 / 9），对第二阶段进行重新拆解并给出更可执行的计划。

---

## 一、阶段目标
1. **数据流切换**：从 `SequenceMaskTable → ScapyRewriter` 切换至 `MaskingRecipe → BlindPacketMasker`。
2. **资源友好**：确保在 ≥10 GB PCAP 场景中内存稳健、处理速度≤旧方案 120%。
3. **可回滚**：新旧链路并存，可通过配置/环境变量即时切换。
4. **向前兼容**：保留旧 API，但发出 Deprecation Warning，文档定义迁移窗口。

---

## 二、核心技术决策（采纳改进建议）

### 2.1 指令键方案（建议 #2）
- **Primary Key**：`packet_index`（0-based）
- **Integrity Fields**：`timestamp_ns`（原 sniff_timestamp ×1e9 取 int）、`orig_len`（caplen）可选；校验失败时仅警告不终止。
- **匹配流程**：BlindPacketMasker 先按 index 查指令，若索引命中但校验字段不一致 → 记录 stats.mismatch++ 并 fallback 为"有指令"处理，保证不漏掩码。

### 2.2 偏移量计算服务化（建议 #3）
- 新建 `src/pktmask/common/tcp_offset.py`
  - `def get_tcp_payload_offset(pkt_bytes) -> int`
  - `def get_tcp_payload_offset_ps(packet) -> int`  （针对 PyShark layer 对象）
- 单元测试覆盖 7 种封装：Plain, VLAN, Double VLAN, MPLS, GRE, VXLAN, Mixed。
- 所有调用方（PySharkAnalyzer、验证脚本、潜在 CLI）统一依赖该模块。

### 2.3 MaskSpec 解耦（建议 #4）
- **迁移**：在 `tcp_payload_masker.api.types` 下重新声明 `MaskSpec / MaskAfter / MaskRange / KeepAll`。
- **桥接**：`trim.models.mask_spec` 暂时 `from ...tcp_payload_masker.api.types import *` 以维持旧代码。
- **Phase 2 完成时**：文档中提示外部插件应改为新路径，v3.0 删除旧模块。 

### 2.4 旧方案渐退（建议 #5）
- 在 `tcp_payload_masker.__init__` 中对旧类 `TcpPayloadMasker` 等加：
  ```python
  import warnings
  warnings.warn("Deprecated – will be removed in v3.0", DeprecationWarning, stacklevel=2)
  ```
- MultiStageExecutor 默认注册新 `TcpPayloadMaskerAdapter`；通过 `PKTMASK_USE_LEGACY_MASKER=1` 环境变量回退。
- GUI 和 CLI 在启动时读取该变量并提示用户当前链路。

### 2.5 任务拆分微调（建议 #6）
| 子阶段 | 目标 | 主要任务 | 预计工时 |
|-------|------|---------|---------|
| 2-A MVP | 最小可运行链路 | • `_translate_to_packet_instructions` 仅支持 Plain IPv4
  • `TcpPayloadMaskerAdapter` 集成 & CI | 1 天 |
| 2-B 封装扩展 | VLAN/MPLS/GRE/VXLAN | • 在偏移服务中实现多层头部解析 | 1 天 |
| 2-C 资源优化 | 流式写出 | • 替换 `wrpcap` → `PcapWriter(iter_mode=True)`
  • 性能基准 | 0.5 天 |
| 2-D 双轨验证 | 一致性 & 回滚 | • 同时跑旧/新链路 diff
  • 自动回滚脚本 | 0.5 天 |
| 2-E 文档&版本化 | 迁移指南 | • 更新 README / CHANGELOG
  • Deprecation Policy  | 0.5 天 |

> **总计**：≈ 3.5 天，高于原计划 3 天但风险更低。

### 2.6 文档及版本管理（建议 #9）
- 版本号自 `2.0.0-phase1.3` → `2.1.0`。
- 更新 `CHANGELOG.md` ➜ "Added – Blind Masker Integration, Deprecated – Legacy Sequence Masker"。
- 新增 `docs/MIGRATION_GUIDE_V2.md` 详细列出 API 变更与迁移步骤。

---

## 三、详细实施里程碑
1. **MVP 交付（2-A）**：Day 1 结束前 CI 通过、能掩码 Plain IP 流量。
2. **封装扩展完成（2-B）**：Day 2 结束前全部封装测试通过（pytest marker encap）。
3. **资源优化 & 基准（2-C）**：Day 3 上午完成，1 GB PCAP mem < 600 MB，速度 ≤120% 旧链路。
4. **双轨验证 + 回滚（2-D）**：Day 3 下午完成，脚本 `run_dual_validation.py` 输出 diff=0。
5. **文档封板 & 版本发布（2-E）**：Day 3 晚上 tag v2.1.0，更新 PyPI beta 包。

---

## 四、风险与缓解
| 风险 | 描述 | 缓解措施 |
|------|------|-----------|
| 指令索引错位 | PyShark 滤包后 index 与 Scapy 读取不一致 | 在 Phase 2-A 中引入 "index+timestamp" 双校验，同时对差异打警告；后续如需可改用 caplen/hash。 |
| Offset 计算错误 | 多层封装时难以保证偏移绝对正确 | 独立 `tcp_offset` 单元测试 + 集成真实样本；CI 必须绿。 |
| 内存暴涨 | 大文件 wrpcap 一次性缓存 | Phase 2-C 引入流式写出；Benchmark 强制测试 10 GB 文件。 |
| 回滚路径遗漏 | 新链路异常导致用户无法处理 | 环境变量回退 + `--legacy` CLI flag + 自动 diff 验证；CI 覆盖。 |

---

## 五、接受标准
1. **功能**：所有现有测试 + 新端到端测试通过，diff=0。
2. **性能**：100 MB 基准 ≤120% 旧链路时间，内存峰值≤70%。
3. **稳定性**：真实样本 100% 通过，无崩溃、无数据丢失。
4. **可维护性**：
   - 单元测试覆盖新代码 ≥90%。
   - 文档齐全，Deprecation 策略明确。 