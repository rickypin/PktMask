# TLS23 Marker 使用指南

> 版本：v1.3.0 · 适用范围：PktMask ≥ 3.0 · 作者：AI 设计助手

本指南介绍了如何在命令行、CI/CD 及 PktMask 工作流中使用 **tls23_marker** 工具，以及如何利用 **validate_tls23_frames.py** 脚本对多文件批量验证。

---

## 1. 安装与前置条件

1. **Python ≥ 3.9**（已包含于 PktMask 发行包中）。
2. **Wireshark CLI 套件（tshark / editcap）≥ 4.2.0**，并位于 `$PATH`，或通过 `--tshark-path /path/to/tshark` 指定。

```bash
# macOS（使用 Homebrew）
brew install --cask wireshark

# Ubuntu / Debian
sudo apt-get update && sudo apt-get install wireshark
```

> 若仅需扫描而 **不写回注释**，`editcap` 可选；使用 `--no-annotate` 即可跳过。

---

## 2. 快速开始

### 2.0 版本升级提示（v1.2.0+）

自 v1.2.0 起，**tls23_marker** 在 v1.1.0 多 Record 统计基础上，进一步带来了两项重要增强：

1. **TLS 1.3 字段兼容**：自动同时解析 `tls.record.content_type` (TLS ≤1.2) 与 `tls.record.opaque_type` (TLS 1.3)。无需额外参数即可跨版本扫描。
2. **混合类型帧检测**：对同一 TCP 段内混合 `20 / 22 / 23 …` 多种 TLS Record 的场景，能够准确定位后续出现的 `23 (Application Data)` Record，并正确统计 `num_records/lengths`，前置的非 23 Record 不计入统计。

> 注：依旧支持 `--legacy` 兼容模式（关闭多记录统计 & 仅 2 列 TSV）。

自 v1.3.0 起新增 **零字节统计** 功能，可用于快速判断 TLS 23 记录是否已被完全 Payload Trim 置零。

新增/改进列表：

1. **零字节统计 (`zero_bytes`)**：对每个命中的 TLS23 数据包，统计其 TLS 23 **消息体** 中值为 `0x00` 的字节数量。若该值恰等于 `lengths` 字段所有长度之和，即可判定其已被完全置零掩码。

2. 其余 v1.2.0 两项增强保持不变：TLS 1.3 字段兼容、混合类型帧检测。

升级后默认输出字段（相对 v1.0 新增）：

| 字段 | 含义 |
|------|------|
| `num_records` | 当前帧命中的 TLS23 Record 数量，≥1 |
| `lengths` | 可选，命中 Record 的长度列表 (byte) |
| `zero_bytes` | 可选，本帧 TLS 23 消息体中值为 `0x00` 的字节数 |

若仅需保持 v1.0 行为（每帧视作 1 条记录、TSV 仅 2 列），可通过 `--legacy` 关闭多记录统计。

### 2.1 单文件扫描

```bash
# 默认行为（统计多 Record）
python -m pktmask.tools.tls23_marker \
  --pcap tests/data/tls/tls_1_2_plainip.pcap \
  --formats json,tsv          # 同时输出 JSON + TSV

# 旧版兼容模式（不统计多 Record）
python -m pktmask.tools.tls23_marker \
  --pcap tests/data/tls/tls_1_2_plainip.pcap \
  --legacy --formats json
```

* **输出文件**（与输入文件同目录）：
  * `tls_1_2_plainip_tls23_frames.json` – 命中帧列表 + **汇总统计** (English)，含 `total_records`/`num_records`/`zero_bytes` 字段
  * `tls_1_2_plainip_tls23_frames.tsv`  – 命中帧列表 + **汇总统计** (English)，TSV 第 3/4/5 列依次为 `num_records`、`lengths`、`zero_bytes`
  * `tls_1_2_plainip_annotated.pcapng`  – 已写入注释的 PCAPNG（含 **文件级汇总注释**，English）

### 2.2 禁用注释写回

```bash
python -m pktmask.tools.tls23_marker \
  --pcap sample.pcapng --no-annotate --formats json
```

> 建议在 **CI / 大文件扫描** 场景下使用 `--no-annotate`，可显著减少执行时间。

### 2.3 自定义解码端口

```bash
python -m pktmask.tools.tls23_marker \
  --pcap captured.pcapng \
  --decode-as 8443,tls --decode-as 9443,tls
```

---

## 3. 批量验证脚本

`scripts/validation/validate_tls23_frames.py` 可对目录内所有 PCAP/PCAPNG 批量运行扫描并生成汇总。

```bash
python scripts/validation/validate_tls23_frames.py \
  --input-dir tests/data/tls \
  --output-dir output/reports/tls23_validation \
  --no-annotate --verbose
```

* **汇总文件**：`tls23_validation_summary.json`
  * `frames_detected` 字段表示每个文件命中的 TLS23 帧数量
  * `status` 字段值为 `ok / missing_json / parse_error`

退出码：

| 代码 | 含义 |
|-----:|------|
| 0 | 所有文件扫描成功且生成 JSON 结果 |
| 1 | 至少 1 个文件处理失败或输出缺失 |
| 2 | 输入目录不存在 / 不含 PCAP 文件 |

---

## 4. 在 CI/CD 流程中使用

1. **准备 Wireshark CLI**：GitHub Actions 可使用官方包或 `apt-get install wireshark`。
2. 在测试步骤前加入：

```yaml
- name: TLS23 Frame Validation
  run: |
    python scripts/validation/validate_tls23_frames.py \
      --input-dir tests/data/tls \
      --no-annotate --verbose
```
3. 若退出码非 0 流水线将失败，确保回归测试覆盖。

---

## 5. 与 PktMask 主流程集成

在端到端集成测试（`tests/e2e/test_complete_workflow.py`）中，可按以下顺序调用：

1. 运行 `tls23_marker` 生成命中帧 JSON；
2. 运行 PktMask **Enhanced Trimmer** 对同一文件进行 Payload Trim；
3. 使用 Scapy／PyShark 验证输出文件，对比命中帧载荷应已被置零，其余帧保持不变。

示例代码片段：

```python
import subprocess, json, pathlib

pcap = pathlib.Path("tests/data/tls/tls_1_2_plainip.pcap")
result_dir = pathlib.Path("output/tmp")
subprocess.run([
    sys.executable, "-m", "pktmask.tools.tls23_marker",
    "--pcap", str(pcap), "--no-annotate", "--output-dir", str(result_dir)
], check=True)
frames = json.loads((result_dir / f"{pcap.stem}_tls23_frames.json").read_text())
# 继续调用 PktMask 执行裁切…
```

---

## 6. 常见问题

| 问题 | 解决方法 |
|------|----------|
| *tshark not found* | 确认 Wireshark CLI 已安装并位于 `$PATH`，或使用 `--tshark-path` 指定绝对路径 |
| tshark 版本过低 | 升级到 ≥ 4.2.0；Ubuntu 22.04 可使用 `ppa:wireshark-dev/stable` |
| editcap 写回失败 | 使用 `--no-annotate` 跳过，或检查文件是否只读 |

---

## 7. 参考链接

* [Wireshark User's Guide](https://www.wireshark.org/docs/wsug_html_chunked/)
* [Editcap Manual](https://www.wireshark.org/docs/man-pages/editcap.html)

---

## 8. 实现原理概览（可选阅读）

1. **环境与参数校验**：启动时检查 `tshark -v` ≥ 4.2.0，并解析 CLI 参数（`--pcap / --decode-as / --legacy …`）。
2. **首轮显式扫描**：
   * 使用 `tshark -T json` 仅提取少量字段（`frame.number`、`tls.record.content_type`、`tls.record.opaque_type`、`tls.record.length` 等）。
   * 遍历每个包，将 `content_type / opaque_type` 字段合并后查找 `23 / 0x17`，即 Application Data。
   * 记录命中帧、所属 TCP 流、Record 长度与计数。
3. **缺头补标（第二轮解析）**：
   * 对首轮命中的每个 TCP 流重新调用 `tshark`，抓取 `tcp.payload` 原始 hex。
   * 依据 TLS 记录头 `type(1)+version(2)+length(2)` 顺序流式解析，捕获漏报的 Application Data 记录（常见于首段缺 TLS 头或混合类型情况下）。
4. **统计与输出**：
   * 生成 `total_frames / total_records / by_path` 汇总，并在 JSON/TSV 中输出；
   * 如未指定 `--no-annotate`，通过 `editcap` 在数据包注释中写入帧级与文件级标记。
5. **兼顾性能与兼容性**：
   * 最小化 `tshark` 字段，减少 JSON 体积；
   * 自动兼容 TLS 1.0/1.2 与 TLS 1.3 字段差异；
   * 可选 `--legacy` 旗标保持旧版解析脚本向后兼容。

© 2025 PktMask Project 