# TLS 流量分析工具批量处理功能使用指南

## 概述

TLS 流量分析工具现已支持批量处理功能，可以一次性处理目录下的所有 pcap/pcapng 文件，并生成对应的分析报告和汇总报告。

## 新增功能

### 1. 批量处理目录
- 支持输入一个目录，自动处理目录下所有 `.pcap`、`.pcapng`、`.cap` 文件
- 为每个文件生成独立的 JSON、TSV、HTML 分析报告
- 支持生成汇总 HTML 报告，包含所有文件的统计信息

### 2. 新增命令行参数

#### `--input-dir`
- 指定包含 pcap/pcapng 文件的目录路径
- 与 `--pcap` 参数互斥，只能选择其中一个

#### `--generate-summary-html`
- 批量处理时生成汇总 HTML 报告
- 包含所有文件的全局统计和详细信息
- 仅在批量处理模式下有效

## 使用示例

### 1. 批量处理目录中的所有文件

```bash
# 基本批量处理
python -m pktmask.tools.tls_flow_analyzer --input-dir /path/to/pcap/files

# 批量处理并生成所有格式的输出
python -m pktmask.tools.tls_flow_analyzer \
    --input-dir /path/to/pcap/files \
    --formats json,tsv,html \
    --output-dir /path/to/output

# 批量处理并生成汇总HTML报告
python -m pktmask.tools.tls_flow_analyzer \
    --input-dir /path/to/pcap/files \
    --formats json,tsv,html \
    --generate-summary-html \
    --verbose
```

### 2. 仅输出统计摘要（不生成文件）

```bash
# 快速统计目录中所有文件的TLS流量信息
python -m pktmask.tools.tls_flow_analyzer \
    --input-dir /path/to/pcap/files \
    --summary-only \
    --detailed
```

### 3. 单文件处理（保持向后兼容）

```bash
# 单文件处理仍然正常工作
python -m pktmask.tools.tls_flow_analyzer \
    --pcap /path/to/single/file.pcap \
    --formats json,tsv,html \
    --detailed
```

## 输出文件说明

### 批量处理输出结构

```
output_directory/
├── file1_tls_flow_analysis.json      # 文件1的JSON分析结果
├── file1_tls_flow_analysis.tsv       # 文件1的TSV分析结果
├── file1_tls_flow_analysis.html      # 文件1的HTML分析报告
├── file2_tls_flow_analysis.json      # 文件2的JSON分析结果
├── file2_tls_flow_analysis.tsv       # 文件2的TSV分析结果
├── file2_tls_flow_analysis.html      # 文件2的HTML分析报告
└── tls_flow_analysis_summary.html    # 汇总HTML报告（需要 --generate-summary-html）
```

### 汇总HTML报告特性

- **全局统计**：显示所有文件的汇总统计信息
- **协议类型统计**：按TLS消息类型汇总的全局统计
- **文件分块显示**：每个文件的详细分析结果独立显示
- **交互式界面**：可折叠的详细信息区域
- **美观的样式**：使用CSS样式和颜色编码
- **文件链接功能**：每个文件标题旁边都有"查看详情"链接
- **一键跳转**：点击链接在新标签页中打开对应的详细HTML分析报告
- **响应式设计**：在不同屏幕尺寸下都能正常显示和操作

## 性能优化

### 批量处理优化
- 每个文件独立处理，单个文件失败不影响其他文件
- 详细的进度显示和错误处理
- 支持详细模式查看每个文件的处理状态

### 内存管理
- 逐个处理文件，避免同时加载所有文件到内存
- 及时释放单个文件的分析结果

## 错误处理

- 单个文件分析失败不会中断整个批量处理过程
- 详细的错误信息和堆栈跟踪（在verbose模式下）
- 最终报告显示成功处理的文件数量

## 兼容性

- 完全向后兼容原有的单文件处理功能
- 所有现有的命令行参数和功能保持不变
- 新增的批量处理功能不影响现有工作流程

## 实际使用场景

1. **批量分析网络流量样本**：一次性分析多个捕获的网络流量文件
2. **定期流量分析**：对定期收集的流量文件进行批量分析
3. **比较分析**：通过汇总报告比较不同文件的TLS流量特征
4. **快速统计**：使用 `--summary-only` 快速获取目录中所有文件的统计信息
5. **导航式分析**：通过汇总报告的链接功能，快速跳转到感兴趣文件的详细分析
6. **团队协作**：分享汇总HTML报告，团队成员可以通过链接查看具体文件的详细信息

## 注意事项

- 确保目录中包含有效的 pcap/pcapng 文件
- 大量文件处理时建议使用 `--verbose` 查看进度
- 汇总HTML报告需要 Jinja2 库支持
- 输出目录会自动创建（如果不存在）
- 汇总HTML中的链接指向同目录下的详细HTML文件
- 文件名包含空格或特殊字符时，链接仍能正常工作
- 建议将所有相关文件保持在同一目录下以确保链接正常工作
