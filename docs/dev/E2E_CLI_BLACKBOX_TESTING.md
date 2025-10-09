# E2E CLI Blackbox Testing Design

## 概述

本文档描述PktMask的**完全解耦的CLI黑盒测试**设计,作为现有API白盒测试的补充层。

## 测试架构

### 分层测试策略

```
┌─────────────────────────────────────────────────────────────┐
│  Level 1: CLI Blackbox Tests (完全解耦)                      │
│  - 文件: test_e2e_cli_blackbox.py                           │
│  - 方法: 通过CLI subprocess调用                              │
│  - 验证: 仅输出文件SHA256哈希                                │
│  - 耦合: 零耦合,完全黑盒                                     │
│  - 目的: 确保用户接口稳定性                                  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Level 2: API Integration Tests (中度耦合)                   │
│  - 文件: test_e2e_golden_validation.py                      │
│  - 方法: 直接调用ConsistentProcessor API                    │
│  - 验证: 详细指标(hash, 包数, 阶段统计等)                    │
│  - 耦合: 依赖API接口和数据结构                               │
│  - 目的: 详细的回归验证和调试                                │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Level 3: Unit Tests (高度耦合)                              │
│  - 文件: tests/unit/*                                       │
│  - 方法: 测试单个类和函数                                    │
│  - 验证: 单元级别的功能正确性                                │
│  - 耦合: 直接依赖内部实现                                    │
│  - 目的: 快速定位问题,开发时验证                             │
└─────────────────────────────────────────────────────────────┘
```

## CLI黑盒测试设计

### 核心原则

1. **零代码依赖** - 不导入任何`src/pktmask`模块
2. **纯CLI接口** - 仅通过subprocess调用CLI
3. **最小验证** - 只验证输出文件哈希
4. **完全隔离** - 不依赖内部数据结构

### 实现特点

#### 1. 无内部导入

```python
# ❌ API白盒测试 - 有内部导入
from src.pktmask.core.consistency import ConsistentProcessor

# ✅ CLI黑盒测试 - 无内部导入
import subprocess  # 只使用标准库
```

#### 2. 通过CLI调用

```python
def _run_cli_command(self, cli_executable, input_path, output_path, 
                     dedup=False, anon=False, mask=False):
    """Run PktMask CLI command"""
    
    # Build command
    cmd = [sys.executable, "-m", "pktmask", "process"]
    cmd.extend([str(input_path), "-o", str(output_path)])
    
    if dedup:
        cmd.append("--dedup")
    if anon:
        cmd.append("--anon")
    if mask:
        cmd.append("--mask")
    
    # Run command (pure blackbox)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    
    return result
```

#### 3. 最小化验证

```python
def test_cli_core_functionality_consistency(self, test_id, ...):
    """Validate through CLI - only hash verification"""
    
    # 1. Run CLI
    result = self._run_cli_command(...)
    
    # 2. Verify exit code
    assert result.returncode == 0
    
    # 3. Verify output exists
    assert output_path.exists()
    
    # 4. Verify hash ONLY (no internal metrics)
    output_hash = self._calculate_file_hash(output_path)
    assert output_hash == baseline["output_hash"]
    
    # ❌ 不验证内部指标:
    # - result.stage_stats (不存在,因为没有调用API)
    # - result.packets_processed (不存在)
    # - result.duration_ms (不存在)
```

## 测试覆盖

### 相同的测试用例

CLI黑盒测试使用**相同的16个测试用例**和**相同的黄金基准**:

| 类别 | 测试ID | 说明 |
|------|--------|------|
| **核心功能** | E2E-001 to E2E-007 | 去重、匿名化、掩码的各种组合 |
| **协议覆盖** | E2E-101 to E2E-106 | TLS 1.0/1.2/1.3, SSL 3.0, HTTP |
| **封装类型** | E2E-201 to E2E-203 | Plain IP, Single/Double VLAN |

### 验证差异

| 方面 | CLI黑盒测试 | API白盒测试 |
|------|------------|------------|
| **验证指标** | 1个(文件哈希) | 10+个(哈希+详细统计) |
| **测试速度** | 较慢(进程启动) | 较快(直接调用) |
| **调试信息** | 少(仅CLI输出) | 多(详细内部指标) |
| **隔离程度** | 完全隔离 | 中度耦合 |
| **用户真实性** | 高(测试实际CLI) | 中(测试API) |

## 解耦优势

### 1. 不受内部重构影响

| 变更类型 | CLI黑盒测试 | API白盒测试 |
|---------|------------|------------|
| API接口改变 | ✅ 不影响 | ❌ 需要修改 |
| 数据结构改变 | ✅ 不影响 | ❌ 需要修改 |
| 内部算法优化 | ✅ 不影响 | ✅ 不影响 |
| CLI参数改变 | ❌ 需要修改 | ✅ 不影响 |
| 输出格式改变 | ❌ 需要重新生成基准 | ❌ 需要重新生成基准 |

### 2. 测试真实用户场景

```bash
# CLI黑盒测试执行的命令 = 用户实际使用的命令
python -m pktmask process input.pcap -o output.pcap --dedup --anon --mask

# API白盒测试调用的代码 ≠ 用户使用的方式
processor = ConsistentProcessor(config)
result = processor.process_file(input_path, output_path)
```

### 3. 可以测试不同版本

```python
# 可以测试不同版本的CLI(通过不同的可执行文件)
def test_with_different_versions():
    # 测试当前版本
    result_v1 = run_cli("/path/to/pktmask-v1.0", ...)
    
    # 测试新版本
    result_v2 = run_cli("/path/to/pktmask-v2.0", ...)
    
    # 比较输出
    assert calculate_hash(result_v1.output) == calculate_hash(result_v2.output)
```

## 使用方法

### 运行CLI黑盒测试

```bash
# 只运行CLI黑盒测试
pytest tests/e2e/test_e2e_cli_blackbox.py -v

# 运行特定测试
pytest tests/e2e/test_e2e_cli_blackbox.py::TestE2ECLIBlackbox::test_cli_core_functionality_consistency -v

# 生成HTML报告
pytest tests/e2e/test_e2e_cli_blackbox.py -v \
  --html=tests/e2e/report_cli_blackbox.html \
  --self-contained-html
```

### 运行所有E2E测试

```bash
# 运行API白盒 + CLI黑盒测试
pytest tests/e2e/ -v

# 使用便捷脚本
./tests/e2e/run_e2e_tests.sh --all
```

### 只运行快速验证

```bash
# CLI黑盒测试 - 快速验证用户接口
pytest tests/e2e/test_e2e_cli_blackbox.py -v --tb=short

# 如果失败,再运行API白盒测试获取详细信息
pytest tests/e2e/test_e2e_golden_validation.py -v
```

## 最佳实践

### 1. 分层测试策略

```
开发阶段:
  └─> 运行单元测试(快速反馈)
  └─> 运行API白盒测试(详细验证)

提交前:
  └─> 运行CLI黑盒测试(用户接口验证)
  └─> 运行API白盒测试(回归验证)

发布前:
  └─> 运行所有测试(完整验证)
  └─> 生成HTML报告(文档记录)
```

### 2. 失败调试流程

```
CLI黑盒测试失败
  ↓
检查CLI输出(stdout/stderr)
  ↓
运行API白盒测试
  ↓
查看详细指标差异
  ↓
定位问题原因
```

### 3. 基准更新策略

```
代码变更导致输出改变
  ↓
确认变更是预期的
  ↓
重新生成黄金基准
  ↓
CLI黑盒测试和API白盒测试共用相同基准
  ↓
两层测试都会通过
```

## 技术细节

### CLI执行方式

```python
# 方式1: 使用shell脚本
cmd = [sys.executable, "pktmask", "process", ...]

# 方式2: 使用Python启动器
cmd = [sys.executable, "pktmask_launcher.py", "process", ...]

# 方式3: 使用模块方式(推荐)
cmd = [sys.executable, "-m", "pktmask", "process", ...]
```

### 超时处理

```python
# 设置60秒超时,防止CLI挂起
result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
```

### 错误处理

```python
# 验证退出码
assert result.returncode == 0, (
    f"CLI command failed\n"
    f"STDOUT: {result.stdout}\n"
    f"STDERR: {result.stderr}"
)
```

## 总结

### CLI黑盒测试的价值

1. **完全解耦** - 不受内部代码重构影响
2. **真实场景** - 测试用户实际使用的CLI
3. **稳定性保证** - 确保用户接口不会意外改变
4. **版本兼容** - 可以测试不同版本的兼容性

### 与API白盒测试的互补

| 测试层 | 优势 | 劣势 | 适用场景 |
|--------|------|------|---------|
| **CLI黑盒** | 完全解耦,测试真实场景 | 调试信息少,速度慢 | 用户接口验证,版本兼容测试 |
| **API白盒** | 详细指标,快速执行 | 依赖内部API | 回归测试,问题调试 |

### 推荐使用方式

```bash
# 日常开发: API白盒测试(快速,详细)
pytest tests/e2e/test_e2e_golden_validation.py -v

# 提交前: CLI黑盒测试(用户接口验证)
pytest tests/e2e/test_e2e_cli_blackbox.py -v

# CI/CD: 两者都运行(完整覆盖)
pytest tests/e2e/ -v --html=report.html
```

---

**文档版本**: 1.0  
**创建日期**: 2025-10-09  
**作者**: PktMask Development Team

