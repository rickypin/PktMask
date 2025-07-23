# PktMask Tools - Production Tool Suite

This directory contains production-grade command-line tools for the PktMask project, which have been thoroughly tested and are ready for end-user use.

## Tool List

### tls23_marker.py
TLS Application Data (content-type=23) Marking Tool

**Features**:
- Scan TLS type 23 packets in PCAP/PCAPNG files
- Mark and analyze TLS application data
- Support multiple output formats (JSON, TSV)
- Optional packet annotation functionality

**Usage Examples**:
```bash
# Basic usage
python -m pktmask.tools.tls23_marker --pcap input.pcapng

# Specify output format and directory
python -m pktmask.tools.tls23_marker --pcap input.pcapng --formats json,tsv --output-dir ./results

# Use custom port decoding
python -m pktmask.tools.tls23_marker --pcap input.pcapng --decode-as 8443,tls --decode-as 9443,tls
```

### enhanced_tls_marker.py
Enhanced TLS Marking Tool

**Features**:
- Provide more detailed TLS analysis functionality
- Support cross-packet TLS record reassembly
- Advanced filtering and statistics functionality

**Usage Examples**:
```bash
# Enhanced analysis
python -m pktmask.tools.enhanced_tls_marker --pcap input.pcapng --deep-analysis
```

### tls_flow_analyzer.py
全面的 TLS 流量分析工具

**功能**：
- TCP 流向识别：准确区分 TCP 五元组的两个传输方向
- TLS 消息类型识别：识别并分类所有 TLS 消息类型（20-24）
- 跨 TCP 段处理：正确处理单个 TLS 消息被分割到多个 TCP 段的情况
- 协议层级分析：显示每个数据包的协议封装层级
- 详细的消息结构分析和统计信息

**使用示例**：
```bash
# 基本分析
python -m pktmask.tools.tls_flow_analyzer --pcap input.pcapng

# 详细分析模式
python -m pktmask.tools.tls_flow_analyzer --pcap input.pcapng --detailed --verbose

# 指定输出格式和目录
python -m pktmask.tools.tls_flow_analyzer --pcap input.pcapng --formats json,tsv --output-dir ./results

# 使用自定义端口解码
python -m pktmask.tools.tls_flow_analyzer --pcap input.pcapng --decode-as 8443,tls --decode-as 9443,tls

# 带统计报告
python -m pktmask.tools.enhanced_tls_marker --pcap input.pcapng --stats
```

## 工具开发指南

### 命名规范
- 工具文件名应简洁明了，使用下划线分隔：`功能_tool.py`
- 避免使用 `debug_`、`test_`、`backup_` 等前缀

### 代码要求
1. 必须包含完整的命令行参数解析
2. 提供 `--help` 帮助信息
3. 支持通过 `python -m` 方式调用
4. 包含适当的错误处理和用户友好的错误信息

### 文档要求
- 每个工具必须有详细的文档字符串
- 包含使用示例
- 说明所有命令行参数

## 与开发脚本的区别

| 特性 | 生产工具 (tools/) | 开发脚本 (scripts/) |
|------|------------------|---------------------|
| 目标用户 | 最终用户 | 开发者 |
| 稳定性 | 稳定版本 | 可能包含实验性功能 |
| 文档 | 完整文档 | 基本注释 |
| 测试 | 充分测试 | 基本验证 |
| 维护 | 长期维护 | 按需更新 |

## 注意事项

1. 本目录下的工具应保持向后兼容
2. 重大更改需要版本号更新
3. 废弃的功能应提供迁移指南
4. 临时或实验性工具请放在 `scripts/adhoc/` 目录

## 相关资源

- 开发脚本: `scripts/`
- API 文档: `docs/api/`
- 使用指南: `docs/user/`
