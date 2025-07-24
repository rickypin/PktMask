# Tools Documentation

PktMask provides a series of specialized tools for network packet analysis and processing. This directory contains detailed usage guides for all tools.

## 🔧 Tool List

### 🔍 TLS Analysis Tools
- **[TLS Flow Analyzer](tls-flow-analyzer.md)** - Analyze TLS protocol traffic and generate detailed reports
- **[TLS23 Marker](tls23-marker.md)** - Mark TLS 1.3 ApplicationData frames
- **[TLS23 Validator](tls23-validator.md)** - End-to-end validation of TLS 1.3 processing results

### 🛡️ Mask Validation Tools
- **[MaskStage Validator](maskstage-validator.md)** - Validate the correctness of Mask Payloads functionality

## 🎯 Tool Categories

### By Functionality

#### Analysis Tools
- **TLS Flow Analyzer** - In-depth analysis of TLS protocol details
- **Network Traffic Statistics** - Generate traffic statistics reports

#### Marking Tools
- **TLS23 Marker** - Precisely mark TLS 1.3 message boundaries
- **Protocol Identification Tool** - Automatically identify network protocol types

#### Validation Tools
- **TLS23 Validator** - Validate TLS processing accuracy
- **MaskStage Validator** - Ensure Mask Payloads functionality works correctly

### By Usage Scenario

#### Development Debugging
- TLS23 Marker
- MaskStage Validator

#### Data Analysis
- TLS Flow Analyzer
- TLS23 Validator

#### Quality Assurance
- All validation tools
- End-to-end testing tools

## 🚀 快速开始

### 新用户推荐
1. **TLS 流量分析** → [TLS 流量分析工具](tls-flow-analyzer.md)
2. **掩码验证** → [MaskStage 验证工具](maskstage-validator.md)

### 开发者推荐
1. **调试 TLS 处理** → [TLS23 标记工具](tls23-marker.md)
2. **验证功能正确性** → [TLS23 验证工具](tls23-validator.md)

## 📋 使用要求

### 系统要求
- Python 3.8+
- tshark (Wireshark 命令行工具)
- 足够的磁盘空间用于临时文件

### 依赖安装
```bash
# 安装 Python 依赖
pip install -r requirements.txt

# 安装 tshark (参考安装指南)
# Ubuntu/Debian: sudo apt-get install tshark
# macOS: brew install wireshark
# Windows: 下载 Wireshark 安装包
```

## 🔗 工具集成

### 与主程序集成
所有工具都可以作为独立脚本运行，也可以通过主程序的 GUI 界面调用。

### 批处理支持
大多数工具支持批量处理多个文件，适合大规模数据分析。

### 输出格式
- **JSON** - 结构化数据输出
- **HTML** - 可视化报告
- **CSV** - 表格数据导出
- **文本** - 简单文本报告

## 📊 性能考虑

### 内存使用
- 大文件处理时注意内存限制
- 使用流式处理减少内存占用

### 处理速度
- tshark 解析速度取决于文件大小
- 并行处理可提高效率

### 磁盘空间
- 临时文件可能占用大量空间
- 定期清理临时目录

## 🔗 相关资源

- **[用户文档](../user/)** - 基础使用指南
- **[API 文档](../api/)** - 编程接口参考
- **[架构文档](../architecture/)** - 工具设计原理

## 📝 故障排除

### 常见问题
1. **tshark 未找到** → 检查 PATH 环境变量
2. **权限错误** → 确保有文件读写权限
3. **内存不足** → 减少并发处理数量

### 获取帮助
- 查看具体工具的文档
- 提交 GitHub Issue
- 参考 [开发文档](../dev/README.md) 获取技术支持

---

> 💡 **提示**: 每个工具都有详细的使用示例和参数说明，建议先阅读相应的工具文档。
