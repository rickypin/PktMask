# CLI黑盒测试解耦程度分析

## 📋 概述

本文档详细分析CLI黑盒测试与主程序的解耦程度,识别耦合点,并提供完全解耦方案。

**分析日期**: 2025-10-09  
**当前解耦程度**: 85% ⚠️  
**目标解耦程度**: 100% ✅

---

## 🔍 解耦程度审查

### 1. 代码层面解耦 ✅ 100%

#### 1.1 导入语句检查

**文件**: `tests/e2e/test_e2e_cli_blackbox.py`

```python
# ✅ 只使用标准库和pytest
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

# ❌ 没有导入任何内部模块
# NO: from src.pktmask.core.consistency import ConsistentProcessor
# NO: from src.pktmask.services import ...
```

**结论**: ✅ **完全解耦** - 没有导入任何`src.pktmask`模块

---

#### 1.2 CLI调用方式检查

```python
def _run_cli_command(
    self,
    cli_executable: str,
    input_path: Path,
    output_path: Path,
    dedup: bool = False,
    anon: bool = False,
    mask: bool = False,
) -> subprocess.CompletedProcess:
    """Run PktMask CLI command"""
    
    # ✅ 使用subprocess调用CLI
    cmd = [sys.executable, "-m", "pktmask", "process"]
    cmd.extend([str(input_path), "-o", str(output_path)])
    
    if dedup:
        cmd.append("--dedup")
    if anon:
        cmd.append("--anon")
    if mask:
        cmd.append("--mask")
    
    # ✅ 纯黑盒调用
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    return result
```

**结论**: ✅ **完全解耦** - 使用subprocess,不调用任何内部API

---

#### 1.3 验证逻辑检查

```python
# ✅ 只验证CLI退出码
assert result.returncode == 0

# ✅ 只验证输出文件存在
assert output_path.exists()

# ✅ 只验证输出文件哈希
output_hash = self._calculate_file_hash(output_path)
assert output_hash == baseline["output_hash"]

# ❌ 不访问任何内部数据结构
# NO: result.stats
# NO: result.stage_stats
# NO: result.packets_processed
```

**结论**: ✅ **完全解耦** - 只验证外部可观察行为

---

### 2. 数据层面解耦 ❌ 0%

#### 2.1 黄金基准生成方式

**当前方式**: 使用API生成

```python
# tests/e2e/generate_golden_baseline.py

# ❌ 导入内部API
from src.pktmask.core.consistency import ConsistentProcessor

# ❌ 使用API生成基准
processor = ConsistentProcessor()
result = processor.process_file(input_path, output_path, config)

# ❌ 保存API内部数据
baseline = {
    "output_hash": output_hash,
    "stats": {
        "packets_processed": result.stats.packets_processed,
        "packets_modified": result.stats.packets_modified,
        "stages": [...]  # 内部stage信息
    }
}
```

**问题**: 黄金基准依赖API生成,存在间接耦合

---

#### 2.2 黄金基准内容分析

**当前基准文件**: `tests/e2e/golden/E2E-001_baseline.json`

```json
{
  "test_id": "E2E-001",
  "name": "Dedup Only",
  "input_file": "tests/data/tls/tls_1_2-2.pcap",
  "input_hash": "baf39e40...",
  "config": {
    "dedup": true,
    "anon": false,
    "mask": false
  },
  "output_hash": "baf39e40...",
  "output_file_size": 2721,
  "packet_count": 14,
  "stats": {                          // ❌ API内部数据
    "packets_processed": 14,
    "packets_modified": 0,
    "duration_ms": 8.348941802978516,
    "stages": [                       // ❌ API内部数据
      {
        "name": "DeduplicationStage",
        "packets_processed": 14,
        "packets_modified": 0,
        "duration_ms": 7.904052734375
      }
    ]
  },
  "timestamp": "2025-10-09T19:39:44.736627",
  "version": "1.0"
}
```

**问题**: 
- ❌ 包含API内部数据(`stats`, `stages`)
- ❌ 使用API配置格式(`config`)
- ⚠️ CLI黑盒测试只使用`output_hash`,但基准文件包含多余数据

---

### 3. 耦合链分析

```
┌─────────────────────────────────────────────────────────────┐
│  CLI黑盒测试 (test_e2e_cli_blackbox.py)                     │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│  ✅ 不导入内部模块                                          │
│  ✅ 使用subprocess调用CLI                                   │
│  ✅ 只验证output_hash                                       │
│                                                             │
│  ⬇️ 读取黄金基准                                            │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  黄金基准文件 (golden/E2E-001_baseline.json)                │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│  ✅ output_hash (CLI黑盒使用)                               │
│  ❌ stats (API内部数据,CLI黑盒不使用)                       │
│  ❌ stages (API内部数据,CLI黑盒不使用)                      │
│                                                             │
│  ⬆️ 由基准生成器生成                                        │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  基准生成器 (generate_golden_baseline.py)                   │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│  ❌ from src.pktmask.core.consistency import ...            │
│  ❌ processor = ConsistentProcessor()                       │
│  ❌ result = processor.process_file(...)                    │
│  ❌ 保存API内部数据到基准文件                                │
└─────────────────────────────────────────────────────────────┘
```

**耦合链**: CLI黑盒测试 → 黄金基准 → API生成器 → ConsistentProcessor

---

## 📊 解耦程度评分

| 维度 | 权重 | 得分 | 加权得分 | 说明 |
|------|------|------|---------|------|
| **代码导入** | 25% | 100% | 25% | ✅ 不导入内部模块 |
| **API调用** | 25% | 100% | 25% | ✅ 使用subprocess |
| **验证逻辑** | 25% | 100% | 25% | ✅ 只验证外部行为 |
| **数据依赖** | 25% | 0% | 0% | ❌ 基准依赖API生成 |
| **总分** | 100% | - | **75%** | ⚠️ 存在间接耦合 |

**注**: 之前评估为85%是乐观估计,实际应为75%

---

## 🛠️ 完全解耦方案

### 方案1: 创建CLI专用基准生成器 (推荐) ⭐

#### 实现

创建`tests/e2e/generate_cli_golden_baseline.py`:

```python
#!/usr/bin/env python3
"""
CLI Golden Baseline Generator

完全解耦的基准生成器:
- 使用subprocess调用CLI (不导入API)
- 只保存output_hash (不保存内部数据)
- 完全独立于内部实现
"""

import hashlib
import json
import subprocess
from pathlib import Path

def generate_baseline_via_cli(test_case):
    """使用CLI生成基准"""
    # ✅ 使用subprocess调用CLI
    cmd = ["python", "-m", "pktmask", "process", ...]
    subprocess.run(cmd)
    
    # ✅ 只保存output_hash
    baseline = {
        "test_id": test_case["test_id"],
        "output_hash": calculate_hash(output_file),
        "version": "1.0-cli"
    }
    
    return baseline
```

#### 优点

- ✅ 完全解耦 (100%)
- ✅ 真正的黑盒基准
- ✅ 不受API重构影响
- ✅ 基准文件更简洁

#### 缺点

- ⚠️ 需要维护两套基准生成器
- ⚠️ CLI和API基准可能不同

---

### 方案2: 共享基准但标注来源

#### 实现

在基准文件中标注生成方式:

```json
{
  "test_id": "E2E-001",
  "output_hash": "baf39e40...",
  "generation_method": "api",  // 标注生成方式
  "stats": { ... },            // API专用数据
  "note": "CLI tests only use output_hash"
}
```

#### 优点

- ✅ 只需一套基准
- ✅ 明确标注数据来源

#### 缺点

- ❌ 仍然依赖API生成
- ❌ 基准文件包含冗余数据
- ❌ 未解决根本耦合问题

---

### 方案3: 验证CLI和API输出一致性

#### 实现

创建一个验证脚本,确保CLI和API产生相同输出:

```python
def test_cli_api_consistency():
    """验证CLI和API产生相同输出"""
    # 使用CLI生成输出
    cli_output = run_cli(...)
    
    # 使用API生成输出
    api_output = run_api(...)
    
    # 验证哈希一致
    assert hash(cli_output) == hash(api_output)
```

#### 优点

- ✅ 确保CLI和API行为一致
- ✅ 可以使用任一方式生成基准

#### 缺点

- ❌ 仍然依赖API
- ❌ 未实现完全解耦

---

## 💡 推荐实施方案

### 立即实施: 方案1 (CLI专用基准生成器)

**步骤**:

1. **创建CLI基准生成器** ✅ (已完成)
   - `tests/e2e/generate_cli_golden_baseline.py`
   - 使用subprocess调用CLI
   - 只保存output_hash

2. **生成CLI专用基准**
   ```bash
   python tests/e2e/generate_cli_golden_baseline.py
   ```
   - 输出到`tests/e2e/golden_cli/`目录

3. **修改CLI黑盒测试读取基准**
   ```python
   # 修改前
   golden_dir = Path(__file__).parent / "golden"
   
   # 修改后
   golden_dir = Path(__file__).parent / "golden_cli"
   ```

4. **验证完全解耦**
   ```bash
   pytest tests/e2e/test_e2e_cli_blackbox.py -v
   ```

**预期结果**: 解耦程度从75%提升到**100%** ✅

---

## 📈 解耦程度对比

### 修改前 (当前)

| 维度 | 得分 | 说明 |
|------|------|------|
| 代码导入 | 100% | ✅ 不导入内部模块 |
| API调用 | 100% | ✅ 使用subprocess |
| 验证逻辑 | 100% | ✅ 只验证外部行为 |
| 数据依赖 | 0% | ❌ 基准依赖API生成 |
| **总分** | **75%** | ⚠️ 存在间接耦合 |

### 修改后 (方案1)

| 维度 | 得分 | 说明 |
|------|------|------|
| 代码导入 | 100% | ✅ 不导入内部模块 |
| API调用 | 100% | ✅ 使用subprocess |
| 验证逻辑 | 100% | ✅ 只验证外部行为 |
| 数据依赖 | 100% | ✅ 基准通过CLI生成 |
| **总分** | **100%** | ✅ 完全解耦 |

---

## 🎯 总结

### 当前状态

- **解耦程度**: 75% ⚠️
- **主要问题**: 黄金基准依赖API生成
- **影响**: 存在间接耦合,不是真正的黑盒测试

### 完全解耦方案

- **推荐方案**: 创建CLI专用基准生成器
- **实施难度**: 低 (约30分钟)
- **预期效果**: 解耦程度100% ✅

### 下一步行动

1. ✅ 创建`generate_cli_golden_baseline.py` (已完成)
2. ⏳ 生成CLI专用基准
3. ⏳ 修改CLI黑盒测试读取CLI基准
4. ⏳ 验证100%解耦

---

**文档版本**: 1.0  
**创建日期**: 2025-10-09  
**分析人**: PktMask Development Team  
**状态**: 待实施方案1

