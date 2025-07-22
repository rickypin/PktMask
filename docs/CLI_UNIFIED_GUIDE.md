# PktMask CLI 统一功能指南

## 概述

PktMask CLI 现已实现与 GUI 的完全功能统一，支持所有核心处理能力，包括：

- ✅ **单文件处理**：处理单个 PCAP/PCAPNG 文件
- ✅ **目录批量处理**：批量处理目录中的多个文件
- ✅ **统一配置系统**：与 GUI 使用相同的配置逻辑
- ✅ **丰富输出选项**：详细进度显示、统计信息和报告生成
- ✅ **完整错误处理**：统一的错误处理和恢复机制

## 安装与基本使用

### 安装
```bash
# 从项目根目录安装
pip install -e .

# 或直接运行
python -m pktmask --help
```

### 基本命令结构
```bash
pktmask <command> <input> -o <output> [options]
```

## 核心命令

### 1. mask - 载荷掩码处理

**单文件处理**：
```bash
# 基本掩码处理
pktmask mask input.pcap -o output.pcap

# 启用所有处理选项
pktmask mask input.pcap -o output.pcap --dedup --anon --verbose

# 自定义掩码模式
pktmask mask input.pcap -o output.pcap --mode basic --protocol tls
```

**目录批量处理**：
```bash
# 处理目录中的所有文件
pktmask mask /path/to/pcaps -o /path/to/output --dedup --anon

# 自定义文件匹配模式
pktmask mask /path/to/pcaps -o /path/to/output --pattern "*.pcap,*.cap"

# 详细输出和报告生成
pktmask mask /path/to/pcaps -o /path/to/output --verbose --save-report --report-detailed
```

**参数说明**：
- `--dedup`: 启用去重处理
- `--anon`: 启用 IP 匿名化
- `--mode`: 掩码模式 (`enhanced`|`basic`)
- `--protocol`: 协议类型 (`tls`|`http`)
- `--verbose`: 详细输出
- `--format`: 输出格式 (`text`|`json`)
- `--no-progress`: 禁用进度显示
- `--pattern`: 文件匹配模式
- `--save-report`: 保存详细报告
- `--report-format`: 报告格式 (`text`|`json`)
- `--report-detailed`: 包含详细统计信息

### 2. dedup - 去重处理

```bash
# 单文件去重
pktmask dedup input.pcap -o output.pcap

# 目录批量去重
pktmask dedup /path/to/pcaps -o /path/to/output --verbose
```

### 3. anon - IP 匿名化

```bash
# 单文件匿名化
pktmask anon input.pcap -o output.pcap

# 目录批量匿名化
pktmask anon /path/to/pcaps -o /path/to/output --verbose
```

### 4. batch - 批量处理（推荐）

专为大规模批量处理优化的命令：

```bash
# 使用默认设置处理目录
pktmask batch /path/to/pcaps -o /path/to/output

# 自定义处理选项
pktmask batch /path/to/pcaps -o /path/to/output \
  --no-dedup --mode basic --verbose --format json

# 生成详细报告
pktmask batch /path/to/pcaps -o /path/to/output \
  --verbose --save-report --report-detailed
```

**batch 命令特点**：
- 默认启用所有处理选项（dedup、anon、mask）
- 优化的批量处理性能
- 自动创建输出目录
- 支持并行处理（实验性）

### 5. info - 文件信息分析

```bash
# 分析单个文件
pktmask info input.pcap

# 分析目录
pktmask info /path/to/pcaps --verbose

# JSON 格式输出
pktmask info /path/to/pcaps --format json
```

## 高级功能

### 报告生成

CLI 现在支持与 GUI 相同的详细报告生成：

```bash
# 生成文本报告
pktmask mask input.pcap -o output.pcap --save-report

# 生成 JSON 报告
pktmask mask input.pcap -o output.pcap --save-report --report-format json

# 包含详细统计信息
pktmask mask input.pcap -o output.pcap --save-report --report-detailed
```

报告包含：
- 处理摘要和统计信息
- 每个阶段的详细性能数据
- 错误和警告信息
- 文件处理状态

### 进度显示

多种进度显示模式：

```bash
# 简单进度显示（默认）
pktmask mask /path/to/pcaps -o /path/to/output

# 详细进度显示
pktmask mask /path/to/pcaps -o /path/to/output --verbose

# 禁用进度显示
pktmask mask /path/to/pcaps -o /path/to/output --no-progress
```

### 输出格式

支持多种输出格式：

```bash
# 文本格式（默认）
pktmask mask input.pcap -o output.pcap --format text

# JSON 格式
pktmask mask input.pcap -o output.pcap --format json
```

## 使用示例

### 示例 1：基本单文件处理
```bash
pktmask mask sample.pcap -o processed.pcap --dedup --anon
```

### 示例 2：目录批量处理
```bash
pktmask batch /data/pcaps -o /data/processed \
  --verbose --save-report --report-detailed
```

### 示例 3：自定义配置处理
```bash
pktmask mask /data/pcaps -o /data/output \
  --mode basic --protocol http \
  --pattern "*.pcapng" --format json
```

### 示例 4：仅分析不处理
```bash
pktmask info /data/pcaps --verbose --format json > analysis.json
```

## 与 GUI 的一致性

CLI 现在与 GUI 完全一致：

| 功能特性 | GUI | CLI | 状态 |
|---------|-----|-----|------|
| 单文件处理 | ✅ | ✅ | 完全一致 |
| 目录批量处理 | ✅ | ✅ | 完全一致 |
| 配置选项 | ✅ | ✅ | 完全一致 |
| 进度显示 | ✅ | ✅ | 完全一致 |
| 错误处理 | ✅ | ✅ | 完全一致 |
| 报告生成 | ✅ | ✅ | 完全一致 |
| 统计信息 | ✅ | ✅ | 完全一致 |

## 性能优化

### 批量处理优化
- 使用 `batch` 命令获得最佳批量处理性能
- 大文件处理时使用 `--no-progress` 减少输出开销
- JSON 格式输出适合自动化脚本处理

### 内存管理
- CLI 使用与 GUI 相同的内存优化策略
- 大规模批量处理时自动进行内存管理
- 支持处理大型 PCAP 文件

## 故障排除

### 常见问题

**1. 配置错误**
```bash
❌ Configuration error: No processing stages enabled
```
解决：至少启用一个处理选项（--dedup、--anon 或默认的 mask）

**2. 文件权限问题**
```bash
❌ Error: Permission denied
```
解决：检查输入文件读取权限和输出目录写入权限

**3. 内存不足**
```bash
❌ Error: Memory allocation failed
```
解决：处理较小的文件批次或增加系统内存

### 调试选项

```bash
# 启用详细输出
pktmask mask input.pcap -o output.pcap --verbose

# 生成详细报告用于问题分析
pktmask mask input.pcap -o output.pcap --save-report --report-detailed

# JSON 格式便于程序化分析
pktmask mask input.pcap -o output.pcap --format json
```

## 迁移指南

### 从旧版 CLI 迁移

旧版命令仍然兼容，但建议使用新的统一命令：

```bash
# 旧版（仍然支持）
pktmask mask input.pcap -o output.pcap --dedup --anon --mode enhanced

# 新版（推荐）
pktmask mask input.pcap -o output.pcap --dedup --anon --verbose --save-report
```

### 从 GUI 迁移

GUI 用户可以轻松切换到 CLI：

1. **相同的配置选项**：GUI 中的所有选项在 CLI 中都有对应参数
2. **相同的处理结果**：CLI 和 GUI 产生完全相同的处理结果
3. **相同的报告格式**：CLI 可以生成与 GUI 相同的详细报告

## 总结

PktMask CLI 现在提供了与 GUI 完全一致的功能体验，同时保持了命令行工具的简洁和高效。无论是单文件处理还是大规模批量操作，CLI 都能提供强大而灵活的解决方案。
