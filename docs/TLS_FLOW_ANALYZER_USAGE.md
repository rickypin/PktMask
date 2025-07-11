# TLS 流量分析工具使用指南

> 版本：v1.1.0 · 适用范围：PktMask ≥ 3.0 · 作者：AI 设计助手

本指南介绍了如何使用 **tls_flow_analyzer** 工具进行全面的 TLS 协议流量分析，包括 TCP 流向识别、TLS 消息类型识别、跨 TCP 段处理、精确序列号范围分析等高级功能。

---

## 1. 功能概述

### 1.1 核心功能

**tls_flow_analyzer** 是一个全面的 TLS 流量分析工具，提供以下核心功能：

1. **TCP 流向识别**：准确区分 TCP 五元组（源IP、目标IP、源端口、目标端口、协议）的两个传输方向（客户端到服务器、服务器到客户端）
2. **TLS 消息类型识别**：识别并分类所有 TLS 消息类型（包括但不限于 Handshake、Application Data、Alert、Change Cipher Spec 等）
3. **跨 TCP 段处理**：正确处理单个 TLS 消息被分割到多个 TCP 段的情况，确保消息完整性分析
4. **协议层级分析**：显示每个数据包的协议封装层级（如 Ethernet -> IP -> TCP -> TLS）
5. **精确序列号范围分析**：将TLS消息头部和载荷的TCP序列号范围进行精确拆分，支持字节级定位
6. **详细的消息结构分析和统计信息**

### 1.2 支持的 TLS 协议类型

| 类型 | 名称 | 处理策略 | 说明 |
|------|------|----------|------|
| TLS-20 | ChangeCipherSpec | keep_all | 完全保留 |
| TLS-21 | Alert | keep_all | 完全保留 |
| TLS-22 | Handshake | keep_all | 完全保留 |
| TLS-23 | ApplicationData | mask_payload | 智能掩码(保留5字节头部) |
| TLS-24 | Heartbeat | keep_all | 完全保留 |

---

## 2. 安装与前置条件

### 2.1 系统要求

1. **Python ≥ 3.9**（已包含于 PktMask 发行包中）
2. **Wireshark CLI 套件（tshark）≥ 4.2.0**，并位于 `$PATH`，或通过 `--tshark-path` 指定

### 2.2 安装 Wireshark

```bash
# macOS（使用 Homebrew）
brew install --cask wireshark

# Ubuntu / Debian
sudo apt-get update && sudo apt-get install wireshark

# CentOS / RHEL
sudo yum install wireshark
```

---

## 3. 基本使用

### 3.1 快速开始

```bash
# 基本分析
python -m pktmask.tools.tls_flow_analyzer --pcap input.pcapng

# 详细分析模式
python -m pktmask.tools.tls_flow_analyzer --pcap input.pcapng --detailed --verbose

# 指定输出格式和目录
python -m pktmask.tools.tls_flow_analyzer --pcap input.pcapng --formats json,tsv,html --output-dir ./results
```

### 3.2 命令行参数

| 参数 | 说明 | 默认值 | 示例 |
|------|------|--------|------|
| `--pcap` | 待分析的 pcap/pcapng 文件路径 | 必需 | `--pcap input.pcapng` |
| `--decode-as` | 额外端口解码规则 | 无 | `--decode-as 8443,tls` |
| `--formats` | 输出格式 | `json,tsv` | `--formats json,html` |
| `--tshark-path` | 自定义 tshark 路径 | 自动检测 | `--tshark-path /usr/bin/tshark` |
| `--output-dir` | 输出目录 | 输入文件同目录 | `--output-dir ./results` |
| `--detailed` | 启用详细模式 | False | `--detailed` |
| `--filter-types` | 过滤特定 TLS 类型 | `20,21,22,23,24` | `--filter-types 22,23` |
| `--summary-only` | 仅输出摘要 | False | `--summary-only` |
| `--no-tcp-reassembly` | 禁用 TCP 重组 | False | `--no-tcp-reassembly` |
| `--verbose` | 详细日志输出 | False | `--verbose` |

---

## 4. 输出格式

### 4.1 JSON 输出

主要的 JSON 输出文件包含以下结构：

```json
{
  "metadata": {
    "analysis_timestamp": 1752221329.244925,
    "total_frames_with_tls": 9,
    "total_tls_records": 0,
    "total_tcp_streams": 1,
    "tls_content_types": {...},
    "processing_strategies": {...}
  },
  "global_statistics": {
    "frames_containing_tls": 9,
    "tls_records_total": 0,
    "tcp_streams_analyzed": 1
  },
  "protocol_type_statistics": {
    "22": {"frames": 5, "records": 0},
    "23": {"frames": 3, "records": 0}
  },
  "detailed_frames": [...],
  "reassembled_messages": [...],
  "tcp_flow_analysis": {...}
}
```

### 4.2 TSV 输出

TSV 输出提供表格格式的数据，便于进一步分析：

- `*_tls_flow_analysis.tsv`：详细帧信息
- `*_tls_message_structure.tsv`：消息结构分析（详细模式）

#### 4.2.1 消息结构TSV格式（v1.1.0新增）

消息结构TSV文件现在包含精确的序列号范围信息：

```
stream_id	direction	content_type	content_type_name	version_string
header_start	header_end	header_length	header_seq_start	header_seq_end
payload_start	payload_end	payload_length	payload_seq_start	payload_seq_end
declared_length	is_complete	is_cross_segment	processing_strategy
```

**新增字段说明**：
- `header_seq_start`/`header_seq_end`：TLS消息头部（5字节）在TCP流中的绝对序列号范围
- `payload_seq_start`/`payload_seq_end`：TLS消息载荷在TCP流中的绝对序列号范围

这种精确的序列号范围拆分便于：
- 字节级精确的协议边界定位
- 更细粒度的流量分析和调试
- 精确的掩码规则生成

### 4.3 HTML 输出

HTML 输出提供可视化的交互式报告，具有以下特性：

- **可视化界面**：清晰的视觉层次和现代化设计
- **颜色编码**：不同 TLS 消息类型使用不同颜色区分
- **交互式元素**：可折叠的详细信息部分
- **响应式设计**：支持不同屏幕尺寸
- **打印友好**：优化的打印样式

HTML 报告包含以下部分：
- 📊 基础统计：数据帧、记录和流的总数统计
- 🔐 TLS 消息类型统计：按类型分类的详细统计
- 🌐 TCP 流分析：流向识别和载荷分析
- 📦 详细数据帧信息：每个帧的完整信息
- 🔧 重组消息分析：跨段消息的重组结果（v1.1.0增强：包含分离的头部和载荷序列号范围）
- ℹ️ 分析元数据：技术信息和配置详情

#### 4.3.1 重组消息表格增强（v1.1.0）

重组消息分析表格现在包含两个独立的序列号范围列：
- **头部序列号范围**：显示TLS记录头部（5字节）的TCP序列号范围
- **载荷序列号范围**：显示TLS消息载荷的TCP序列号范围

这种拆分提供了更精确的协议边界信息，便于调试和分析。

**颜色编码说明**：
- 🔵 TLS-20 (ChangeCipherSpec)：蓝色
- 🔴 TLS-21 (Alert)：红色
- 🟢 TLS-22 (Handshake)：绿色
- 🟡 TLS-23 (ApplicationData)：橙色
- 🟣 TLS-24 (Heartbeat)：紫色

### 4.4 详细模式输出

启用 `--detailed` 选项时，会额外生成：

- `*_tls_detailed_analysis.json`：详细分析结果
- `*_tls_message_structure.tsv`：消息结构分析表格
- HTML 报告中会包含更详细的消息结构分析

---

## 5. 使用场景

### 5.1 基础 TLS 流量分析

```bash
# 分析 TLS 流量的基本信息
python -m pktmask.tools.tls_flow_analyzer --pcap tls_traffic.pcapng
```

### 5.2 特定协议类型分析

```bash
# 只分析 Handshake 和 Application Data
python -m pktmask.tools.tls_flow_analyzer --pcap tls_traffic.pcapng --filter-types 22,23
```

### 5.3 自定义端口分析

```bash
# 分析使用非标准端口的 TLS 流量
python -m pktmask.tools.tls_flow_analyzer --pcap custom_tls.pcapng --decode-as 8443,tls --decode-as 9443,tls
```

### 5.4 快速摘要分析

```bash
# 仅输出统计摘要，不生成详细文件
python -m pktmask.tools.tls_flow_analyzer --pcap large_file.pcapng --summary-only
```

### 5.5 详细结构分析

```bash
# 进行详细的消息结构分析
python -m pktmask.tools.tls_flow_analyzer --pcap tls_traffic.pcapng --detailed --verbose --output-dir ./analysis_results
```

### 5.6 生成可视化HTML报告

```bash
# 生成交互式HTML报告
python -m pktmask.tools.tls_flow_analyzer --pcap tls_traffic.pcapng --formats html --output-dir ./reports

# 生成包含所有格式的完整报告
python -m pktmask.tools.tls_flow_analyzer --pcap tls_traffic.pcapng --formats json,tsv,html --detailed --output-dir ./complete_analysis

# 仅生成HTML报告用于演示
python -m pktmask.tools.tls_flow_analyzer --pcap demo.pcapng --formats html --filter-types 22,23
```

---

## 6. 输出解读

### 6.1 统计摘要

工具会输出以下统计信息：

```
[tls-flow-analyzer] ✅ TLS 流量分析完成
  包含 TLS 消息的数据帧总数: 9
  TLS 记录总数: 12
  分析的 TCP 流总数: 1

  按 TLS 消息类型统计:
    TLS-20 (ChangeCipherSpec, keep_all): 2 帧, 2 记录
    TLS-21 (Alert, keep_all): 2 帧, 2 记录
    TLS-22 (Handshake, keep_all): 4 帧, 5 记录
    TLS-23 (ApplicationData, mask_payload): 2 帧, 3 记录
```

### 6.2 TCP 流分析

详细模式下会显示 TCP 流的双向信息：

```
  TCP 流分析详情:
    TCP 流 0: 9 个数据包
      forward: 10.171.250.80:33492 -> 10.50.50.161:443 (5 包, 200 字节载荷)
      reverse: 10.50.50.161:443 -> 10.171.250.80:33492 (4 包, 150 字节载荷)
```

### 6.3 重组消息详情（v1.1.0新增）

详细模式下会显示重组消息的精确序列号范围：

```
  重组 TLS 消息详情 (12 个消息):
    [ 1] 流0-forward Handshake (512字节) ✓ 单段
         头部序列号: 2422049781-2422049786
         载荷序列号: 2422049786-2422050298
    [ 2] 流0-forward Handshake (70字节) ✓ 单段
         头部序列号: 2422050298-2422050303
         载荷序列号: 2422050303-2422050373
    ...
```

这种详细的序列号信息有助于：
- 精确定位TLS协议各部分在TCP流中的位置
- 调试跨段消息的重组问题
- 验证掩码规则的准确性

---

## 7. 故障排除

### 7.1 常见问题

| 问题 | 解决方法 |
|------|----------|
| *tshark not found* | 确认 Wireshark CLI 已安装并位于 `$PATH`，或使用 `--tshark-path` 指定绝对路径 |
| tshark 版本过低 | 升级到 ≥ 4.2.0；Ubuntu 22.04 可使用 `ppa:wireshark-dev/stable` |
| 无法解析 PCAP 文件 | 检查文件格式是否正确，确保是有效的 pcap/pcapng 文件 |
| 内存不足 | 对于大文件，使用 `--no-tcp-reassembly` 禁用重组分析 |

### 7.2 调试选项

使用 `--verbose` 选项可以获得详细的执行日志：

```bash
python -m pktmask.tools.tls_flow_analyzer --pcap input.pcapng --verbose
```

---

## 8. 与其他工具的集成

### 8.1 与 PktMask 工作流集成

```bash
# 先分析 TLS 流量
python -m pktmask.tools.tls_flow_analyzer --pcap original.pcapng --output-dir ./analysis

# 然后执行掩码处理
python -m pktmask.cli mask original.pcapng -o masked.pcapng --mode enhanced

# 最后验证掩码效果
python -m pktmask.tools.tls_flow_analyzer --pcap masked.pcapng --output-dir ./verification
```

### 8.2 批量处理

```bash
# 批量分析多个文件
for file in *.pcapng; do
    python -m pktmask.tools.tls_flow_analyzer --pcap "$file" --summary-only
done
```

---

## 9. 最佳实践

1. **大文件处理**：对于大型 PCAP 文件，建议先使用 `--summary-only` 进行快速评估
2. **性能优化**：使用 `--filter-types` 只分析感兴趣的协议类型
3. **结果验证**：结合详细模式和摘要模式的输出进行交叉验证
4. **自动化集成**：在 CI/CD 流程中使用 `--summary-only` 进行自动化检查
5. **报告选择**：
   - 使用 **HTML 格式** 进行可视化分析和演示
   - 使用 **JSON 格式** 进行程序化处理和集成
   - 使用 **TSV 格式** 进行数据分析和统计
6. **HTML 报告优化**：
   - 对于大型数据集，考虑使用 `--filter-types` 减少报告大小
   - 使用浏览器的打印功能生成 PDF 版本
   - 利用折叠功能专注于感兴趣的部分

---

## 10. 版本历史

- **v1.1.0**：序列号范围拆分增强
  - 新增TLS消息头部和载荷序列号范围的精确拆分
  - 增强HTML报告表格，包含独立的头部和载荷序列号范围列
  - 改进TSV输出格式，添加`header_seq_start`、`header_seq_end`、`payload_seq_start`、`payload_seq_end`字段
  - 增强CLI详细输出，显示重组消息的精确序列号范围
  - 保持100%向后兼容性
- **v1.0.0**：初始版本，支持全面的 TLS 流量分析功能
