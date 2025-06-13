# PyShark + Scapy 桌面脱敏完整设计方案

> **版本 1.4 – 2025‑06‑13**  （修复时间戳、IP.len、跨帧掩码、碎片处理与 NPA 校验缺口）

---

## 目录

1. [需求与非功能目标](#需求与非功能目标)
2. [术语与约定](#术语与约定)
3. [总体流程](#总体流程)
4. [处理机制与算法](#处理机制与算法)

   * 4.1 Stage 0 – 统一首选项 & 预重组
   * 4.2 Stage 1 – 生成 **StreamMaskTable**
   * 4.3 Stage 2 – 长度保持型掩码回写
   * 4.4 Stage 3 – 输出验证 (解析 + NPA 回归)
5. [插件框架 & 配置文件](#插件框架--配置文件)
6. [CLI 与兼容模式](#cli-与兼容模式)
7. [测试与验证](#测试与验证)
8. [风险与对策](#风险与对策)
9. [附录 A – 参考代码骨架](#附录-a--参考代码骨架)

---

## 1 需求与非功能目标

| 编号  | 说明                                                                                      |
| --- | --------------------------------------------------------------------------------------- |
| R‑1 | 对 **单/少量 PCAP** 文件做一次性脱敏并生成新文件。                                                         |
| R‑2 | **识别** 满足 Display Filter/YAML 条件的帧号或字节区间。                                               |
| R‑3 | **HTTP** — 保留完整请求/响应 **头**，正文全部置零。                                                      |
| R‑4 | **TLS** — ApplicationData (content\_type 23) 仅保留 5‑byte Record Header，其余密文置零；非 AD 完整保留。 |
| R‑5 | 默认对所有非白名单载荷，以 **不改变长度** 的方式，全体置零 (TCP/UDP 皆然)。                                          |
| R‑6 | 处理 IPv4/IPv6 **碎片**、TCP **乱序/分段/重传**。                                                   |
| R‑7 | 输出文件解析无错；Wireshark Expert 不出现 Malformed。                                                |
| R‑8 | **网络性能分析友好**：保持原始 `ts_sec/usec`, `seq/ack`, `ip.len`, `tcp.len`，RTT、吞吐等指标不被扭曲。          |
| R‑9 | 易扩展到新协议、额外裁切策略；旧版本兼容。                                                                   |

---

## 2 术语与约定

* **Frame No**：pcap 中的物理帧序号。
* **Stream ID**：`tcp.stream` / `udp.stream`。
* **ByteRange**：以 **(stream‑id, seq\_start, seq\_end)** 标识的连续 TCP 字节区间。
* **MaskSpec**：帧/区间遮蔽策略：

  * `MASK_AFTER(n)` —— 保留前 *n* 字节，后续全部 0x00 填充；
  * `MASK_RANGE(ranges)` —— 多段区间遮蔽；
  * `KEEP_ALL` —— 整段原样保留。

> **变更**：废弃 v1.2 “ΔSEQ(stream)”；一律 **保持原字节长度与序列号**。

---

## 3 总体流程

```
┌──────────┐ prefs.ini ┌───────────────┐ StreamMaskTable ┌──────────────┐
│ Stage 0  │──────────▶│ Stage 1       │───────────────▶│ Stage 2      │──▶ out.pcap
│ (TShark) │           │  Indexer +    │                │ Re‑writer    │
└──────────┘           │  Reassembler  │                └──────────────┘
          ▲            └───────────────┘                        │
          └───── Stage 3 – Expert & NPA Check (tshark / tcptrace / custom‑hash)
```

### 组件映射一览

| Stage   | 主要组件/库                             | 主要职责                          |
| ------- | ---------------------------------- | ----------------------------- |
| Stage 0 | **TShark (CLI)** / *PyShark*       | 分段重组、首选项覆盖、导出重组 PCAP‑NG       |
| Stage 1 | **PyShark**                        | 精确解析协议字段，生成 `StreamMaskTable` |
| Stage 2 | **Scapy**                          | 按字节掩码回写、校验和重算、保持时间戳并输出 PCAP   |
| Stage 3 | **TShark**、**tcptrace**、*Scapy 脚本* | 解析完整性检查、NPA 指标对比、逐帧摘要验证       |

**核心差异**：

1. Stage 0 额外执行 **TCP 流重组 & IP 分片重组**，确保准确界定需遮蔽的字节区间。
2. Stage 1 输出 **StreamMaskTable**（基于 Seq Range 而非 Frame No）。
3. Stage 2 根据 Seq Range 在每帧原位填 0x00；**保留抓包时间戳与长度字段**。

---

## 4 处理机制与算法

### 4.1 Stage 0 – 统一首选项 & 预重组

**组件：TShark (CLI) + PyShark（加载首选项、生成重组文件）**

| 步骤  | 目的                          | 说明                                                   |
| --- | --------------------------- | ---------------------------------------------------- |
| 0‑1 | 统一 Wireshark 首选项            | `tshark -r pcap -o tcp.desegment_tcp_streams:TRUE …` |
| 0‑2 | IPv4/IPv6 **碎片重组**          | `-o ip.reassemble:TRUE -o ipv6.reassemble:TRUE`      |
| 0‑3 | 导出重组后 PCAP‑NG `*.rs.pcapng` | 供 Stage 1 扫描使用；FrameNo 与原始文件保持映射表。                   |

### 4.2 Stage 1 – 生成 StreamMaskTable

**组件：PyShark（深度解析、提取协议字段）**

1. 读取 **重组后的** pcapng 以 PyShark **逐报文解析**；
2. 根据 YAML queries 生成 `MaskSpec` 并映射到 **(stream‑id, seq\_start, seq\_end)**；
3. 合并/去重同一流内相邻区间，写入 `mask_table.msgpack`：

```text
stream=5  [0‑312):MASK_AFTER(312)
stream=5  [312‑∞):MASK_AFTER(0)
stream=9  [200‑360):MASK_RANGE([(205,360)])
…
```

> **跨分段/重传安全**：因基于 **Seq Range**，即使载荷被拆分或重传，也能正确匹配。

#### 4.2.1 核心策略摘要

| 协议/类型               | 命中条件                            | MaskSpec                                         | 备注               |                                                 |                          |
| ------------------- | ------------------------------- | ------------------------------------------------ | ---------------- | ----------------------------------------------- | ------------------------ |
| HTTP Header         | \`http.request                  |                                                  | http.response\`  | 首帧：`MASK_AFTER(header_len)`其后同流：`MASK_AFTER(0)` | 重组后计算准确 header\_len 防止截断 |
| TLS ApplicationData | `tls.record.content_type == 23` | 对每条 Record 生成 `MASK_RANGE([(off+5, off+5+len)])` | 多 Record / 跨帧均支持 |                                                 |                          |
| TLS 非 AD            | `tls && content_type != 23`     | `KEEP_ALL`                                       | 保留握手 & Alert     |                                                 |                          |
| 其他                  | —                               | `MASK_AFTER(0)`                                  | 整包载荷置零           |                                                 |                          |
| 白名单                 | `keep_type: keep_all`           | `KEEP_ALL`                                       | 完全保留             |                                                 |                          |

### 4.3 Stage 2 – 长度保持型掩码回写

**组件：Scapy（字节级修改、校验和重算、pcap 写出）**

逐帧读取 **原始 pcap**，根据 (stream‑id, seq) 查询 `StreamMaskTable`：

```python
for raw_pkt, meta in RawPcapReader(infile):
    pkt = Ether(raw_pkt)  # 保留 raw 副本

    # ——— 时间戳保真 ———
    ts_sec, ts_usec = meta.sec, meta.usec

    # ——— 流 & seq 定位 ———
    if pkt.haslayer(TCP):
        sid = f"tcp/{pkt[TCP].sport}->{pkt[TCP].dport}/{pkt[TCP].stream}"
        seq = pkt[TCP].seq
        spec = mask_table.lookup(sid, seq, len(pkt[Raw].load))
    elif pkt.haslayer(UDP):
        sid = f"udp/{pkt[UDP].sport}->{pkt[UDP].dport}/{pkt[UDP].stream}"
        seq = 0
        spec = mask_table.lookup(sid, 0, len(pkt[Raw].load))
    else:
        spec = MaskAfter(0)  # 非 L4 仍可置零

    apply_mask(pkt, spec)

    # ——— 校验和仅重算 chksum 字段 ———
    for layer in (IP, IPv6, TCP, UDP):
        if pkt.haslayer(layer) and hasattr(pkt[layer], 'chksum'):
            pkt[layer].chksum = None

    # ——— 写回保留原始 ts ———
    writer.write(pkt, sec=ts_sec, usec=ts_usec)
```

> * \*\*不触碰 **`** / **`** / \*\*\`\`，确保长度字段与原始完全一致。
> * IPv4/IPv6 **碎片**：`lookup()` 会根据 `frag_offset` 纠偏；使同一 Datagram 内所有碎片应用相同掩码。

#### 4.3.1 apply\_mask 实现

同 v1.3，但 **仅修改目标 ByteRange**。若区间跨层边界，递归进入 TCP/UDP payload；碎片场景先根据 `frag_offset` 递补偏移。

### 4.4 Stage 3 – 输出验证

**组件：TShark + tcptrace + Scapy（辅助摘要脚本）**

| 步骤  | 工具                 | 检查目标                        |   |     |   |     |   |       |   |       |   |     |   |     |   |                                      |
| --- | ------------------ | --------------------------- | - | --- | - | --- | - | ----- | - | ----- | - | --- | - | --- | - | ------------------------------------ |
| 3‑1 | `tshark -z expert` | 无 Malformed/Length‑Mismatch |   |     |   |     |   |       |   |       |   |     |   |     |   |                                      |
| 3‑2 | \*\*自研 \*\*\`\`    | 对每帧计算 \`sha256(ts           |   | src |   | dst |   | sport |   | dport |   | seq |   | ack |   | len)\`脱敏前后摘要 **逐帧对比**，仅 Raw 载荷不同亦可匹配 |
| 3‑3 | `tcptrace -l -n`   | 流量统计、RTT、重传次数一致             |   |     |   |     |   |       |   |       |   |     |   |     |   |                                      |
| 3‑4 | `editcap -E`       | 字段增删检查（可选）                  |   |     |   |     |   |       |   |       |   |     |   |     |   |                                      |

---

## 5 插件框架 & 配置文件

### 5.1 插件 API v1.4

```python
class Plugin:
    def scan(self, pcap_reassembled: str, query: dict, prefs: str):
        """Yield (stream_id, seq_start, seq_end, MaskSpec)"""
```

* 返回 **Seq 区间**，而不再依赖 FrameNo。第三方插件需升级。
* 核心内置插件：`http_header`, `tls_appdata`, `keep_all`, `raw_zero`。

### 5.2 YAML 样例

```yaml
input: sample.pcap
output: sample_desens.pcap
prefs: prefs.ini
queries:
  - id: http
    filter: "http.request || http.response"
    keep_type: http_header
    priority: 100
  - id: tls_appdata
    filter: "tls.record.content_type == 23"
    keep_type: tls_appdata
    priority: 90
  - id: whitelist
    filter: "ip.addr == 10.0.0.1"
    keep_type: keep_all
    priority: 110
```

---

## 6 CLI 与兼容模式

```
usage: pydesens [-h] -i IN.pcap -o OUT.pcap [--prefs PREFS]
                [--mode {preserve_len,shrink_len}]
```

* `preserve_len`（默认）—— v1.4 新逻辑。
* `shrink_len` —— 维持 v1.2 旧逻辑（ΔSEQ 重写）。若选择此模式，将自动载入 **legacy delta\_seq.py** 插件集，接口兼容但不与 v1.4 共存。

---

## 7 测试与验证

| 项目     | 指标                     | 通过标准                          |
| ------ | ---------------------- | ----------------------------- |
| 解析完整性  | tshark Expert          | 无 Malformed / Length‑Mismatch |
| NPA 对比 | pktdigest.py, tcptrace | **逐帧摘要** 与关键 RTT/吞吐指标一致       |
| 性能     | 1 GB / 10 核            | < 50 s，峰值 RSS < 1 GB          |

---

## 8 风险与对策

| 风险              | 等级 | 缓解策略                                      |
| --------------- | -- | ----------------------------------------- |
| **大小模式泄漏**（侧信道） | 中  | `--mode shrink_len` 或 `--jitter N` 随机长填充。 |
| 置零后触发 IDS 误报    | 低  | `--pad 0x20` 自定义填充值；或对特定端口 `KEEP_ALL`。    |
| 第三方插件未升级导致加载失败  | 低  | 插件加载时自动检测 `scan` 签名；提供兼容 shim 与错误提示。      |

---

## 9 附录 A – 参考代码骨架

```python
# mask_table.py
class MaskTable:
    def __init__(self):
        self._table = defaultdict(list)  # stream_id -> list[(start,end,spec)]

    def add(self, sid, s, e, spec):
        self._table[sid].append((s, e, spec))

    def finalize(self):
        # merge & sort
        for sid, lst in self._table.items():
            lst.sort()
            merged = []
            for s, e, spec in lst:
                if merged and merged[-1][1] >= s and merged[-1][2] == spec:
                    merged[-1] = (merged[-1][0], max(merged[-1][1], e), spec)
                else:
                    merged.append([s, e, spec])
            self._table[sid] = merged

    def lookup(self, sid, seq, length):
        """Return MaskSpec for byte range [seq, seq+len)"""
        for s, e, spec in self._table.get(sid, []):
            if seq < e and seq + length > s:
                return spec
        return MaskAfter(0)
```

```python
# plugins/http_header.py
class HTTPHeaderPlugin(Plugin):
    def scan(self, pcap, q, prefs):
        cap = FileCapture(pcap, display_filter=q['filter'], override_prefs=prefs)
        for p in cap:
            sid = f"tcp/{p.tcp.srcport}->{p.tcp.dstport}/{p.tcp.stream}"
            hdr_len = int(p.http.header_length)
            seq_start = int(p.tcp.seq)
            yield sid, seq_start, seq_start + hdr_len, MaskAfter(hdr_len)
            total_len = int(p.tcp.len)
            if hdr_len < total_len:
                yield sid, seq_start + hdr_len, seq_start + total_len, MaskAfter(0)
        cap.close()
```
