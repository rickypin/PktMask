# PktMask Tools - 生产工具集

本目录包含 PktMask 项目的生产级命令行工具，这些工具经过充分测试，可供最终用户使用。

## 工具列表

### tls23_marker.py
TLS Application Data (content-type=23) 标记工具

**功能**：
- 扫描 PCAP/PCAPNG 文件中的 TLS 23 类型数据包
- 标记和分析 TLS 应用数据
- 支持多种输出格式（JSON、TSV）
- 可选的数据包注释功能

**使用示例**：
```bash
# 基本使用
python -m pktmask.tools.tls23_marker --pcap input.pcapng

# 指定输出格式和目录
python -m pktmask.tools.tls23_marker --pcap input.pcapng --formats json,tsv --output-dir ./results

# 使用自定义端口解码
python -m pktmask.tools.tls23_marker --pcap input.pcapng --decode-as 8443,tls --decode-as 9443,tls
```

### enhanced_tls_marker.py
增强版 TLS 标记工具

**功能**：
- 提供更详细的 TLS 分析功能
- 支持跨数据包的 TLS 记录重组
- 高级过滤和统计功能

**使用示例**：
```bash
# 增强分析
python -m pktmask.tools.enhanced_tls_marker --pcap input.pcapng --deep-analysis

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
