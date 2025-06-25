# TLS Trim 端到端验证方案

## 1. 目标
1. 自动化验证 `Trim Payloads` 阶段对真实 TLS 流量的裁切效果。
2. 针对 `tests/data/tls` 目录下 9 个 **未修改的** 样本，统计并对比裁切前后 *TLS Application Data* (content-type = 23) 的处理结果。
3. 无需 GUI，完整流程可在 CI 中一键运行，输出可机读报告(JSON) 与人读摘要(Markdown)。

---

## 2. 样本清单
| 序号 | 文件名 | 备注 |
|---|---|---|
| 1 | `tls_plainip.pcap` | 纯 IPv4 TCP + TLS |
| 2 | `tls_vlan.pcap` | 单层 802.1Q VLAN |
| 3 | `tls_double_vlan.pcap` | 双层 802.1ad(QinQ) |
| 4 | `tls_mpls.pcapng` | MPLS over IP |
| 5 | `tls_vxlan.pcap` | VXLAN 隧道 | 
| 6 | `tls_gre.pcap` | GRE 隧道 |
| 7 | `tls_mixed_encap.pcap` | 组合封装 (VLAN+MPLS) |
| 8 | `tls_partial_reassembly.pcap` | 存在跨段 TLS 记录 |
| 9 | `tls_large_records.pcapng` | 大 Application Data 记录 |

> **说明**：如文件名与实际不符，后续脚本以扫描目录的方式动态收集。表格仅用于文档说明。

---

## 3. 验证指标
| 指标 | 说明 |
|---|---|
| `app_records_before` | 裁切前 TLS Application Data 记录数 (content-type 23) |
| `app_packets_before` | 裁切前 *包含* Application Data 的数据包数 |
| `app_records_after` | 裁切后仍可识别的 Application Data 记录数 (应等于前值) |
| `app_packets_after` | 裁切后 *包含* Application Data 的数据包数 (应等于前值) |
| `masked_bytes` | 被置零的累计字节数 (>0 即视为生效) |
| `modified_packets` | 实际发生修改的数据包数 (>0 即视为生效) |

验证通过条件：
1. `app_records_before == app_records_after` 且 `app_packets_before == app_packets_after`  
   (裁切不会破坏 TLS 结构，仅修改负载)
2. `masked_bytes > 0` 且 `modified_packets > 0`

---

## 4. 流程概览
```mermaid
graph TD;
    A[收集样本] --> B[Baseline 统计]\n(TShark);
    B --> C[执行 Trim 流程]\n(Python API);
    C --> D[结果统计]\n(TShark + Scapy);
    D --> E[生成报告]\n(JSON & MD);
```

### 4.1 Baseline 统计
使用 `tshark` 逐文件执行：
```bash
# 输出字段: 帧号 + 记录长度
$ tshark -r <file> -Y "tls.record.content_type == 23" \
        -T fields -e frame.number -e tls.record.length
```
统计规则：
* 行数 = `app_records_before`
* 去重后的 `frame.number` 数量 = `app_packets_before`

结果写入 `baseline.json`：
```json
{
  "tls_plainip.pcap": {"app_records_before": 42, "app_packets_before": 21},
  ...
}
```

### 4.2 执行 Trim
提供轻量脚本 `run_trim_batch.py`：
```bash
$ python run_trim_batch.py \
        --input-dir tests/data/tls \
        --output-dir tmp/trim_out
```
脚本逻辑：
1. 递归扫描 `*.pcap*` 文件
2. 调用 `EnhancedTrimmer.process_file()`，输出与输入文件同名、加后缀 `-Trimmed.pcap`
3. 收集 `ProcessorResult.stats`，写入 `trim_stats.json`

### 4.3 结果统计
1. 对裁切后的文件重复 **Baseline 统计** 流程，得到 `app_records_after / app_packets_after`。
2. 使用 `scapy` 校验：对 baseline 列出的每个帧，确认其 TCP 负载 5 字节之后全部为 `0x00`；累计置零字节数 `masked_bytes`。
3. 汇总到 `verification.json`。

### 4.4 生成报告
* **机器可读**：`verification.json` 合并 baseline 与 after 结果及裁切统计。
* **人类可读**：`verification_report.md`，表格化展示每个文件的各项指标及通过/失败标记。

---

## 5. 脚本与目录结构
```
.tests_tls_trim/
├── baseline_collector.py      # 步骤 4.1
├── run_trim_batch.py          # 步骤 4.2
├── verification.py            # 步骤 4.3
├── generate_report.py         # 步骤 4.4 (可选合并到 verification)
└── README.md                  # 使用说明
```

全部脚本均使用 **纯 Python + subprocess**，不引入额外依赖。CI 可执行：
```bash
python -m tests_tls_trim.baseline_collector && \
python -m tests_tls_trim.run_trim_batch && \
python -m tests_tls_trim.verification
```

---

## 6. 后续迭代 (非必需)
* 针对 TLS 1.3 `EncryptedHandshake` 记录可扩充更多字段统计。
* 增加 *VLAN ID / 隧道信息* 验证，确保头部保持不变。
* 对比裁切前后文件哈希（除载荷区域外），深化一致性验证。

---

## 7. 结论
该方案聚焦 **TLS Application Data 裁切准确性**，依赖现成工具 (tshark + scapy) 与内部 `EnhancedTrimmer` API，无 GUI、无复杂框架，可在本地或 CI 中快速运行并给出清晰的通过/失败结论。 