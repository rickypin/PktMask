# PktMask CLI 快速参考

## 命令概览

```
pktmask                    # 启动 GUI
pktmask --help            # 显示帮助
pktmask process           # 处理 PCAP 文件
pktmask validate          # 验证 PCAP 文件
pktmask config            # 显示配置
```

## process 命令

### 基本语法
```bash
pktmask process <input> [options]
```

### 必需参数
- `<input>` - 输入文件或目录路径

### 可选参数
- `-o, --output PATH` - 输出路径（默认自动生成）
- `--dedup` - 启用去重
- `--anon` - 启用 IP 匿名化
- `--mask` - 启用载荷掩码
- `--mask-protocol {tls|http|auto}` - 掩码协议（默认 auto）
- `-v, --verbose` - 详细输出

### 快速示例

#### 单操作
```bash
# 去重
pktmask process input.pcap --dedup

# IP 匿名化
pktmask process input.pcap --anon

# 载荷掩码
pktmask process input.pcap --mask
```

#### 操作组合
```bash
# 去重 + 匿名化
pktmask process input.pcap --dedup --anon

# 所有操作
pktmask process input.pcap --dedup --anon --mask
```

#### 指定输出
```bash
pktmask process input.pcap -o output.pcap --dedup
```

#### 目录处理
```bash
pktmask process /path/to/pcaps -o /path/to/output --dedup --anon
```

#### 详细模式
```bash
pktmask process input.pcap --dedup --verbose
```

## validate 命令

### 基本语法
```bash
pktmask validate <input> [options]
```

### 示例
```bash
# 验证单个文件
pktmask validate input.pcap

# 验证目录
pktmask validate /path/to/pcaps

# 详细模式
pktmask validate input.pcap --verbose
```

## config 命令

### 基本语法
```bash
pktmask config [options]
```

### 示例
```bash
# 显示去重配置
pktmask config --dedup

# 显示所有操作配置
pktmask config --dedup --anon --mask
```

## 常用场景

### 场景 1: 快速去重
```bash
pktmask process sample.pcap --dedup
# 输出: sample_processed.pcap
```

### 场景 2: 完整处理
```bash
pktmask process sample.pcap -o clean.pcap --dedup --anon --mask
```

### 场景 3: 批量处理
```bash
pktmask process /data/pcaps -o /data/output --dedup --anon --mask --verbose
```

### 场景 4: TLS 掩码
```bash
pktmask process tls.pcap -o masked.pcap --mask --mask-protocol tls
```

### 场景 5: 验证后处理
```bash
# 先验证
pktmask validate input.pcap --verbose

# 再处理
pktmask process input.pcap --dedup --anon
```

## 错误处理

### 常见错误

#### 1. 无操作标志
```bash
❌ pktmask process input.pcap
✅ pktmask process input.pcap --dedup
```

#### 2. 文件不存在
```bash
❌ pktmask process nonexistent.pcap --dedup
✅ pktmask validate input.pcap  # 先验证
```

#### 3. 无效文件类型
```bash
❌ pktmask process file.txt --dedup
✅ pktmask process file.pcap --dedup
```

#### 4. 无效协议
```bash
❌ pktmask process input.pcap --mask --mask-protocol invalid
✅ pktmask process input.pcap --mask --mask-protocol tls
```

## 环境变量

### 日志级别
```bash
# 设置调试级别
PKTMASK_LOG_LEVEL=DEBUG pktmask process input.pcap --dedup

# 只显示错误
PKTMASK_LOG_LEVEL=ERROR pktmask process input.pcap --dedup
```

## 输出路径规则

### 自动生成规则
- 文件: `input.pcap` → `input_processed.pcap`
- 目录: `/data/pcaps` → `/data/pcaps_processed`

### 自定义输出
```bash
# 指定文件
pktmask process input.pcap -o custom.pcap --dedup

# 指定目录
pktmask process /data/pcaps -o /custom/output --dedup
```

## 性能提示

### 大文件处理
```bash
# 使用详细模式查看进度
pktmask process large.pcap --dedup --verbose
```

### 批量处理
```bash
# 目录处理会自动优化
pktmask process /data/pcaps -o /data/output --dedup --anon --mask
```

## 帮助信息

### 获取帮助
```bash
# 主帮助
pktmask --help

# 命令帮助
pktmask process --help
pktmask validate --help
pktmask config --help
```

## 测试命令

### 验证安装
```bash
# 检查版本
python -m pktmask --help

# 测试基本功能
pktmask validate tests/samples/tls-single/tls_sample.pcap
```

## 完整示例工作流

```bash
# 1. 验证输入文件
pktmask validate input.pcap --verbose

# 2. 查看配置
pktmask config --dedup --anon --mask

# 3. 处理文件
pktmask process input.pcap -o output.pcap --dedup --anon --mask --verbose

# 4. 验证输出文件
pktmask validate output.pcap --verbose
```

## 参数速查表

| 参数 | 简写 | 类型 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--dedup` | - | 布尔 | False | 启用去重 |
| `--anon` | - | 布尔 | False | 启用 IP 匿名化 |
| `--mask` | - | 布尔 | False | 启用载荷掩码 |
| `--mask-protocol` | - | 字符串 | auto | 掩码协议 |
| `--output` | `-o` | 路径 | 自动 | 输出路径 |
| `--verbose` | `-v` | 布尔 | False | 详细输出 |

## 退出码

- `0` - 成功
- `1` - 错误（配置错误、文件错误等）
- `2` - 无效命令

## 更多信息

- 详细指南: `docs/CLI_UNIFIED_GUIDE.md`
- 简化指南: `docs/CLI_SIMPLIFIED_GUIDE.md`
- 测试指南: `docs/dev/CLI_COMPREHENSIVE_TEST_GUIDE.md`

