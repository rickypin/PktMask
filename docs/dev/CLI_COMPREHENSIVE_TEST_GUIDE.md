# PktMask CLI 全面测试指南

## 概述

本文档提供 PktMask CLI 的全面测试指南，包括自动化测试和手动测试。

## 测试准备

### 1. 环境准备

```bash
# 激活虚拟环境
source venv/bin/activate

# 确保依赖已安装
pip install -e .

# 验证安装
python -m pktmask --help
```

### 2. 测试数据准备

确保以下测试数据目录存在：
- `tests/samples/tls-single/` - TLS 单文件测试
- `tests/samples/http-single/` - HTTP 单文件测试
- `tests/samples/mixed/` - 混合协议测试

## 自动化测试

### 运行 pytest 测试套件

```bash
# 运行所有 CLI 测试
pytest tests/test_cli_comprehensive.py -v

# 运行特定测试类
pytest tests/test_cli_comprehensive.py::TestCLICommands -v

# 运行特定测试方法
pytest tests/test_cli_comprehensive.py::TestCLICommands::test_process_help -v

# 显示详细输出
pytest tests/test_cli_comprehensive.py -v -s

# 生成覆盖率报告
pytest tests/test_cli_comprehensive.py --cov=pktmask.cli --cov-report=html
```

### 运行 Shell 测试脚本

```bash
# 赋予执行权限
chmod +x scripts/test/test_cli_comprehensive.sh

# 运行测试
./scripts/test/test_cli_comprehensive.sh

# 查看详细输出
./scripts/test/test_cli_comprehensive.sh 2>&1 | tee test_output.log
```

## 测试覆盖范围

### 1. 命令测试

#### 主命令
- [x] `pktmask --help` - 显示帮助
- [x] `pktmask` - 启动 GUI（需手动测试）
- [x] 无效命令错误处理

#### process 命令
- [x] 帮助信息
- [x] 单文件处理（所有操作）
- [x] 目录批量处理
- [x] 自动输出路径生成
- [x] 详细输出模式
- [x] 协议参数（tls/http/auto）
- [x] 错误处理

#### validate 命令
- [x] 帮助信息
- [x] 验证单个文件
- [x] 验证目录
- [x] 详细模式
- [x] 错误处理

#### config 命令
- [x] 帮助信息
- [x] 显示配置摘要
- [x] 所有操作组合
- [x] 错误处理

### 2. 参数测试

#### 操作标志
- [x] `--dedup` 单独使用
- [x] `--anon` 单独使用
- [x] `--mask` 单独使用
- [x] `--dedup --anon` 组合
- [x] `--dedup --mask` 组合
- [x] `--anon --mask` 组合
- [x] `--dedup --anon --mask` 全部组合
- [x] 无操作标志错误

#### 协议参数
- [x] `--mask-protocol tls`
- [x] `--mask-protocol http`
- [x] `--mask-protocol auto`
- [x] 无效协议值错误

#### 输出参数
- [x] `-o` 指定输出文件
- [x] `-o` 指定输出目录
- [x] 自动生成输出路径
- [x] 嵌套目录自动创建

#### 其他参数
- [x] `-v, --verbose` 详细输出

### 3. 输入验证测试

#### 文件输入
- [x] 有效 .pcap 文件
- [x] 有效 .pcapng 文件
- [x] 不存在的文件
- [x] 无效文件类型
- [x] 相对路径
- [x] 绝对路径

#### 目录输入
- [x] 包含 PCAP 文件的目录
- [x] 空目录
- [x] 混合文件类型的目录
- [x] 不存在的目录

### 4. 错误处理测试

- [x] 文件不存在错误
- [x] 无效文件类型错误
- [x] 无操作标志错误
- [x] 无效协议参数错误
- [x] 空目录警告

## 手动测试清单

### 1. GUI 启动测试

```bash
# 测试 1: 无参数启动 GUI
python -m pktmask
# 预期: GUI 窗口打开

# 测试 2: 使用启动脚本
./pktmask
# 预期: GUI 窗口打开
```

### 2. 交互式测试

```bash
# 测试 1: 处理大文件
python -m pktmask process large_file.pcap --dedup --verbose
# 观察: 进度显示、内存使用、处理时间

# 测试 2: 批量处理多个文件
python -m pktmask process /path/to/pcaps/ -o /path/to/output --dedup --anon --mask --verbose
# 观察: 批量处理进度、错误处理、总结信息

# 测试 3: 中断处理（Ctrl+C）
python -m pktmask process large_file.pcap --dedup
# 按 Ctrl+C 中断
# 预期: 优雅退出，显示中断消息
```

### 3. 边界条件测试

```bash
# 测试 1: 极小文件
python -m pktmask process tiny.pcap --dedup -v

# 测试 2: 空 PCAP 文件
python -m pktmask process empty.pcap --dedup -v

# 测试 3: 损坏的 PCAP 文件
python -m pktmask process corrupted.pcap --dedup -v
# 预期: 错误消息清晰
```

### 4. 路径测试

```bash
# 测试 1: 包含空格的路径
python -m pktmask process "path with spaces/test.pcap" --dedup

# 测试 2: 包含特殊字符的路径
python -m pktmask process "path-with_special.chars/test.pcap" --dedup

# 测试 3: 非常长的路径
python -m pktmask process "very/long/nested/path/structure/test.pcap" --dedup
```

### 5. 环境变量测试

```bash
# 测试 1: 设置日志级别为 DEBUG
PKTMASK_LOG_LEVEL=DEBUG python -m pktmask process test.pcap --dedup -v
# 预期: 显示详细调试信息

# 测试 2: 设置日志级别为 ERROR
PKTMASK_LOG_LEVEL=ERROR python -m pktmask process test.pcap --dedup -v
# 预期: 只显示错误信息
```

## 测试报告模板

### 测试执行记录

| 测试 ID | 测试描述 | 命令 | 预期结果 | 实际结果 | 状态 | 备注 |
|---------|----------|------|----------|----------|------|------|
| CLI-001 | 主帮助命令 | `pktmask --help` | 显示帮助信息 | | ✅/❌ | |
| CLI-002 | process 帮助 | `pktmask process --help` | 显示 process 帮助 | | ✅/❌ | |
| CLI-003 | 单文件去重 | `pktmask process test.pcap --dedup` | 成功处理 | | ✅/❌ | |
| ... | ... | ... | ... | ... | ... | ... |

### 问题记录

| 问题 ID | 严重性 | 描述 | 重现步骤 | 预期行为 | 实际行为 | 状态 |
|---------|--------|------|----------|----------|----------|------|
| BUG-001 | 高 | ... | ... | ... | ... | 待修复 |
| BUG-002 | 中 | ... | ... | ... | ... | 已修复 |

## 性能基准测试

### 测试场景

```bash
# 场景 1: 小文件处理（< 1MB）
time python -m pktmask process small.pcap --dedup --anon --mask

# 场景 2: 中等文件处理（1-10MB）
time python -m pktmask process medium.pcap --dedup --anon --mask

# 场景 3: 大文件处理（> 10MB）
time python -m pktmask process large.pcap --dedup --anon --mask

# 场景 4: 批量处理（10 个文件）
time python -m pktmask process /path/to/10files/ --dedup --anon --mask
```

### 性能指标

| 场景 | 文件大小 | 处理时间 | 内存使用 | CPU 使用 |
|------|----------|----------|----------|----------|
| 小文件 | < 1MB | | | |
| 中等文件 | 1-10MB | | | |
| 大文件 | > 10MB | | | |
| 批量处理 | 10 文件 | | | |

## 回归测试

### 每次发布前检查

```bash
# 1. 运行完整测试套件
pytest tests/test_cli_comprehensive.py -v

# 2. 运行 Shell 测试脚本
./scripts/test/test_cli_comprehensive.sh

# 3. 运行集成测试
pytest tests/integration/test_cli_simplified_scenarios.py -v

# 4. 运行 E2E 测试
pytest tests/e2e/test_e2e_cli_blackbox.py -v

# 5. 检查测试覆盖率
pytest tests/ --cov=pktmask.cli --cov-report=term-missing
```

## 故障排查

### 常见问题

#### 1. 测试文件不存在

```bash
# 检查测试数据
ls -la tests/samples/tls-single/

# 如果缺失，从其他位置复制或生成
```

#### 2. 权限问题

```bash
# 赋予脚本执行权限
chmod +x scripts/test/test_cli_comprehensive.sh

# 检查输出目录权限
ls -la /tmp/
```

#### 3. 虚拟环境问题

```bash
# 重新创建虚拟环境
deactivate
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

## 持续集成

### GitHub Actions 配置示例

```yaml
name: CLI Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -e .
          pip install pytest pytest-cov
      - name: Run CLI tests
        run: |
          pytest tests/test_cli_comprehensive.py -v --cov=pktmask.cli
      - name: Run Shell tests
        run: |
          chmod +x scripts/test/test_cli_comprehensive.sh
          ./scripts/test/test_cli_comprehensive.sh
```

## 总结

本测试指南涵盖了 PktMask CLI 的所有命令、参数和使用场景。通过自动化测试和手动测试的结合，确保 CLI 的稳定性和可靠性。

### 测试优先级

1. **高优先级**: 核心命令和参数功能
2. **中优先级**: 错误处理和边界条件
3. **低优先级**: 性能测试和跨平台测试

### 建议测试频率

- **每次提交**: 运行快速测试（pytest 核心测试）
- **每次 PR**: 运行完整测试套件
- **每次发布**: 运行所有测试 + 手动测试 + 性能测试

