# TLS23 标记工具设计文档

> 版本：v1.0 ‧ 作者：AI 设计助手 ‧ 状态：草案（待评审）

## 1. 背景与目标

PktMask 在对 PCAP/PCAPNG 文件进行 **Payload Trim/TLS 掩码** 处理后，需要有一套独立工具快速检验 *原始* 报文中 **TLS Application-Data** (content-type = 23) 的分布情况，方便：

1. **效果验证** – 对比掩码前后帧注释或统计，确认掩码算法只作用于正确帧。
2. **回归测试** – 在 CI / E2E 流程中自动核对，防止未来修改导致误判。
3. **问题定位** – 为分析 TLS 流乱序、分片、丢包等复杂场景提供精准帧列表。

因此，需要设计一款 **Python + tshark** 的轻量级命令行工具 `tls23_marker.py`，可以单独运行，也能被测试框架调用。

---

## 2. 需求汇总

| #  | 需求 | 备注 |
|----|------|------|
| R1 | **Wireshark/tshark ≥ 4.2.0** | 依赖最新 TLS 字段与 `-a comment` 支持 |
| R2 | 捕获所有 **TLS content-type = 23** 的帧，包括同帧同时出现 22/23 的情况 | |
| R3 | 覆盖任何外层封装（VLAN/GRE/VXLAN/MPLS/IP-in-IP…） | 只要 tshark 能解析到 TLS 层即可 |
| R4 | 支持 **分段场景 1**（仅 Body 被拆分）与 **分段场景 2**（5 B 头被拆分） | 乱序/丢包/IP 分片仍需尽量标记到 |
| R5 | **依赖 Wireshark 重组** 并将 TCP 重组缓存提升至 **256 MiB** | `tcp.reassembly_memory_limit` |
| R6 | **输出两种形式**<br>① 注释写回 pcap/pcapng；② JSON / TSV 文本列表 | 默认双输出，可通过 CLI 选项关闭某一种 |
| R7 | **保持原始帧号与时间戳**，不得重新写文件顺序 | 注释时仅添加 comment block |
| R8 | 输出需包含 **协议封装路径描述**（`eth/ip/tcp/tls`…） | 便于后续分类着色或统计 |
| R9 | 工具可在 **CI/E2E** 里以无交互方式运行 | 返回非零退出码代表失败 |

---

## 3. 总体架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                     tls23_marker.py                        │
├─────────────────────────────────────────────────────────────┤
│ 1️⃣ CLI & 参数解析 (argparse)                               │
│ 2️⃣ 环境检查与 tshark 路径解析                               │
│ 3️⃣ 首轮 tshark JSON 输出                                   │
│     • 解析显式 content-type=23                              │
│ 4️⃣ 第二阶段流级补扫                                        │
│     • 缺头帧 / 仅 Body 片段补标记                           │
│ 5️⃣ 结果汇总与输出                                          │
│     • TSV / JSON 列表                                       │
│     • editcap 写注释                                        │
└─────────────────────────────────────────────────────────────┘
```

### 3.1 关键依赖

* **Python ≥ 3.9**（标准库：`subprocess`、`json`、`argparse`、`tempfile`、`binascii`、`collections`、`pathlib`）
* **tshark / editcap**（来自 Wireshark CLI 套件，≥ 4.2.0）

> 设计上避免任何三方 Python 包，保证零额外依赖、易于 CI

---

## 4. 详细流程设计

### 4.1 第一阶段：显式命中扫描

1. 调用 `tshark -2 -T json`，开启 TCP/IP/TLS 重组及 256 MiB 缓存。
2. 仅提取必要字段：
   * `frame.number` – 帧号
   * `frame.protocols` – 封装路径
   * `tcp.stream` – 流 ID
   * `tls.record.content_type` – 可能多值，配合 `-E occurrence=a`
3. Python 解析 JSON，快速判定包含 **23** 的帧；若同帧同时出现 22 & 23 亦命中。
4. 将结果按 `tcp.stream` 聚合到 `hits_by_stream: Dict[int, Set[int]]`。

### 4.2 第二阶段：缺头补标

* 目标：补捡 "TLS 5 B 头拆两帧" 导致第一帧缺少 `tls.record.content_type` 的情况。
* 实现：
  1. 针对 **步骤 4.1** 中 *已命中* 的 `tcp.stream`，再次运行 tshark 提取：
     * `tcp.seq_relative`、`tcp.len`、`tcp.payload`
  2. 将同一流内片段按序号拼接成连续 `bytearray`；保存区间索引 `(start, end, frame_no)`。
  3. 逐字节解析 TLS Record：读取 content-type、version、length，遇到 **0x17** 时回溯索引，补记所有覆盖帧号。
  4. 合并到 `hits_by_stream` 最终结果。

### 4.3 输出生成

| 输出类型 | 触发条件 (CLI) | 核心实现 |
|----------|---------------|---------|
| **TSV/JSON 列表** | 默认 | 遍历 `hits_by_stream`，输出 `frame_no` + `path` |
| **PCAP 注释** | `--annotate` (默认开启，可 `--no-annotate` 关闭) | 生成 `comments.txt` → `editcap -A comments.txt` 注释写回；若输入为 pcap 则写出 pcapng 副本 |

> **JSON** 格式示例
>
> ```json
> [
>   {"frame": 1284, "path": "eth/ip/vlan/ip/tcp/tls"},
>   {"frame": 1285, "path": "eth/ip/vlan/ip/tcp/tls"}
> ]
> ```

### 4.4 错误处理与退出码

| 退出码 | 场景 |
|-------|------|
| 0 | 扫描成功，至少生成 TSV/JSON 文件 |
| 1 | tshark / editcap 不可用、版本过低 |
| 2 | 输入文件不存在或格式不支持 |
| 3 | 解析异常（JSON 无法解析 / 字段缺失） |

---

## 5. 模块 & 文件结构

```
src/pktmask/tools/
 └── tls23_marker.py        # 主工具脚本 (可 Python -m 运行)

scripts/validation/
 └── validate_tls23_frames.py  # 调用工具 + 比对掩码结果 (后续可选)

docs/
 └── TLS23_MARKER_TOOL_DESIGN.md  # 本设计文档
```

> 说明：主脚本放进 **src/pktmask/tools**，保持与其它 utility 一致；同时保留入口 `python -m pktmask.tools.tls23_marker`。

---

## 6. CLI 接口草案

```bash
usage: tls23_marker.py [-h] --pcap FILE [--decode-as PORT,PROTO ...]
                       [--no-annotate] [--formats json,tsv]
                       [--tshark-path /usr/bin/tshark]
                       [--memory 256] [--verbose]
                       [--output-dir DIR]
```

| 选项 | 说明 | 默认 |
|------|------|------|
| `--pcap` | 待分析的 pcap/pcapng 文件 | **必填** |
| `--decode-as` | 额外端口解码，如 `8443,tls` | 可多次 |
| `--no-annotate` | 仅输出列表，不写 PCAP 注释 | 关闭注释 |
| `--formats` | 输出格式：逗号分隔 `json`, `tsv` | `json,tsv` |
| `--memory` | TCP 重组缓存 (MiB) | 256 |
| `--output-dir` | 结果文件保存目录 | 与输入同目录 |
| `--verbose` | 输出调试日志 | False |

---

## 7. 性能与资源估算

| 数据规模 | 显式扫描 | 补标阶段 (命中流) | 内存峰值 |
|-----------|---------|------------------|----------|
| 1 GB PCAP | ≈ 8 s | ≈ 1–2 s | `256 MiB + Python ≈ 60 MiB` |
| 10 GB PCAP | ≈ 80 s | ≈ 10–15 s | `256 MiB + Python ≈ 80 MiB` |

> 显式扫描占用绝大多数时间；Python 端逻辑 O(N) 线性，开销可忽略。

---

## 8. 与现有项目的集成方案

1. **端到端测试**：
   * 在 `tests/e2e/test_complete_workflow.py` 增加一步：
     1) 调用 `tls23_marker.py` 生成 `frames.json`；
     2) 调用主程序执行掩码；
     3) 读取输出 PCAP 并确认对应帧 Payload 被清零/保留符合预期。
2. **验证脚本**：在 `scripts/validation/analyze_tls_sample.py` 类似脚本中直接调用。
3. **CI**：新增 GitHub Action Job，跑工具并与基线结果比对。

---

## 9. 实施计划

| 阶段 | 负责人 | 预计工时 | 关键交付物 |
|------|--------|---------|-----------|
| 0. 评审与确认 | 全体 | 0.5 d | 设计文档定稿 |
| 1. 环境探测 & CLI 雏形 | Dev | 0.5 d | `argparse` + 版本检查模块 |
| 2. **显式扫描实现** | Dev | 1 d | Tshark 调用 + JSON 解析 + 基本命中 |
| 3. **补标算法实现** | Dev | 1.5 d | 流级重构 + 缺头补标 + 单元测试 |
| 4. 输出 & 注释功能 | Dev | 0.5 d | TSV/JSON & editcap 写注释 |
| 5. 集成测试脚本 | QA | 0.5 d | 新增 e2e & unit 测试 |
| 6. 文档与示例 | Doc | 0.5 d | README 使用指南 |
| **总计** |  | **~5 d** | |

---

## 10. 风险 & 缓解措施

| 风险 | 等级 | 缓解策略 |
|------|------|---------|
| 现场 tshark 版本过低 | ★★☆ | 工具启动即检查版本，低版本时退出并提示安装指南 |
| 超大文件导致 JSON 输出过大 | ★★☆ | 支持 `--streams-only` 模式，按流拆分扫描；或分块管道读取 |
| editcap 写注释生成 pcapng 体积过大 | ★☆☆ | 加 `--no-annotate` 选项；或仅在测试环境使用注释 |
| 解析失败（字段缺失） | ★☆☆ | 捕获异常，记录日志并退出码 3 |

---

## 11. 验收标准

* 单元测试 **≥ 15**，覆盖显式命中、缺头补标、各种封装解析。
* 随机抽样 5 × 真实流量文件，标记正确率 **≥ 99 %**（与手动 Wireshark 结果比对）。
* 10 GB PCAP 扫描用时 ≤ 2 min，内存峰值 ≤ 350 MiB。
* CI / E2E 流程接入后 **0 False-Positive / 0 False-Negative**。

---

## 12. 结论

该工具将为 PktMask 提供一条 **自动化、可追溯、与 Wireshark 完全一致** 的 TLS Application-Data 帧标记方案，既方便开发验证，也能在生产环境快速定位问题。请评审并提出修改意见，确认后即可进入开发阶段。 