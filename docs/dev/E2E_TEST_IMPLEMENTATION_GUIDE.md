# PktMask 端到端测试实施指南

> **配套文档**: [E2E_TEST_PLAN.md](./E2E_TEST_PLAN.md)  
> **目标**: 提供端到端测试的具体实施步骤和代码示例

---

## 🚀 快速开始

### 前置条件

```bash
# 1. 确保测试数据存在
ls tests/data/tls/
ls tests/samples/http-collector/

# 2. 安装测试依赖
pip install pytest pytest-xdist pytest-timeout

# 3. 确保项目可运行
python -m pktmask --help
```

---

## 📝 实施步骤

### 步骤1: 创建测试目录结构

```bash
# 创建端到端测试目录
mkdir -p tests/e2e/golden
touch tests/e2e/__init__.py
touch tests/e2e/README.md
```

---

### 步骤2: 实现黄金基准生成器

创建 `tests/e2e/generate_golden_baseline.py`:

```python
#!/usr/bin/env python3
"""
黄金基准生成器

在当前稳定版本运行一次，生成所有测试用例的黄金输出。
"""

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pktmask.core.consistency import ConsistentProcessor


class GoldenBaselineGenerator:
    """黄金基准生成器"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent
        self.golden_dir = self.project_root / "tests" / "e2e" / "golden"
        self.golden_dir.mkdir(parents=True, exist_ok=True)
        
        # 测试用例定义
        self.test_cases = self._define_test_cases()
    
    def _define_test_cases(self) -> List[Dict[str, Any]]:
        """定义所有测试用例"""
        return [
            # 核心功能组合测试
            {
                "test_id": "E2E-001",
                "name": "Dedup Only",
                "config": {"dedup": True, "anon": False, "mask": False},
                "input_file": "tests/data/tls/tls_1_2-2.pcap",
            },
            {
                "test_id": "E2E-002",
                "name": "Anonymize Only",
                "config": {"dedup": False, "anon": True, "mask": False},
                "input_file": "tests/data/tls/tls_1_2-2.pcap",
            },
            {
                "test_id": "E2E-003",
                "name": "Mask Only",
                "config": {"dedup": False, "anon": False, "mask": True},
                "input_file": "tests/data/tls/tls_1_2-2.pcap",
            },
            {
                "test_id": "E2E-004",
                "name": "Dedup + Anonymize",
                "config": {"dedup": True, "anon": True, "mask": False},
                "input_file": "tests/data/tls/tls_1_2-2.pcap",
            },
            {
                "test_id": "E2E-005",
                "name": "Dedup + Mask",
                "config": {"dedup": True, "anon": False, "mask": True},
                "input_file": "tests/data/tls/tls_1_2-2.pcap",
            },
            {
                "test_id": "E2E-006",
                "name": "Anonymize + Mask",
                "config": {"dedup": False, "anon": True, "mask": True},
                "input_file": "tests/data/tls/tls_1_2-2.pcap",
            },
            {
                "test_id": "E2E-007",
                "name": "All Features",
                "config": {"dedup": True, "anon": True, "mask": True},
                "input_file": "tests/data/tls/tls_1_2-2.pcap",
            },
            
            # 协议覆盖测试
            {
                "test_id": "E2E-101",
                "name": "TLS 1.0 Multi-Segment",
                "config": {"dedup": True, "anon": True, "mask": True},
                "input_file": "tests/data/tls/tls_1_0_multi_segment_google-https.pcap",
            },
            {
                "test_id": "E2E-102",
                "name": "TLS 1.2 Standard",
                "config": {"dedup": True, "anon": True, "mask": True},
                "input_file": "tests/data/tls/tls_1_2-2.pcap",
            },
            {
                "test_id": "E2E-103",
                "name": "TLS 1.3 with 0-RTT",
                "config": {"dedup": True, "anon": True, "mask": True},
                "input_file": "tests/data/tls/tls_1_3_0-RTT-2_22_23_mix.pcap",
            },
            {
                "test_id": "E2E-104",
                "name": "SSL 3.0",
                "config": {"dedup": True, "anon": True, "mask": True},
                "input_file": "tests/data/tls/ssl_3.pcap",
            },
            {
                "test_id": "E2E-105",
                "name": "HTTP Download",
                "config": {"dedup": True, "anon": True, "mask": True},
                "input_file": "tests/samples/http-collector/http-download-good.pcap",
            },
            {
                "test_id": "E2E-106",
                "name": "HTTP 500 Error",
                "config": {"dedup": True, "anon": True, "mask": True},
                "input_file": "tests/samples/http-collector/http-500error.pcap",
            },
            
            # 封装类型测试
            {
                "test_id": "E2E-201",
                "name": "Plain IP",
                "config": {"dedup": False, "anon": True, "mask": True},
                "input_file": "tests/data/tls/tls_1_2_plainip.pcap",
            },
            {
                "test_id": "E2E-202",
                "name": "Single VLAN",
                "config": {"dedup": False, "anon": True, "mask": True},
                "input_file": "tests/data/tls/tls_1_2_single_vlan.pcap",
            },
            {
                "test_id": "E2E-203",
                "name": "Double VLAN",
                "config": {"dedup": False, "anon": True, "mask": True},
                "input_file": "tests/data/tls/tls_1_2_double_vlan.pcap",
            },
        ]
    
    def generate_all_baselines(self):
        """生成所有黄金基准"""
        print("🚀 Starting Golden Baseline Generation")
        print(f"📁 Golden directory: {self.golden_dir}")
        print(f"📊 Total test cases: {len(self.test_cases)}\n")
        
        success_count = 0
        failed_cases = []
        
        for test_case in self.test_cases:
            try:
                print(f"Processing {test_case['test_id']}: {test_case['name']}...")
                baseline = self.generate_baseline(test_case)
                success_count += 1
                print(f"  ✅ Generated baseline")
                print(f"     Output hash: {baseline['output_hash'][:16]}...")
                print(f"     Packets: {baseline['packet_count']}\n")
            except Exception as e:
                failed_cases.append((test_case['test_id'], str(e)))
                print(f"  ❌ Failed: {e}\n")
        
        # 打印总结
        print("=" * 60)
        print(f"✅ Success: {success_count}/{len(self.test_cases)}")
        if failed_cases:
            print(f"❌ Failed: {len(failed_cases)}")
            for test_id, error in failed_cases:
                print(f"   - {test_id}: {error}")
        print("=" * 60)
    
    def generate_baseline(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
        """生成单个测试用例的黄金基准"""
        test_id = test_case["test_id"]
        config = test_case["config"]
        input_file = self.project_root / test_case["input_file"]
        
        # 验证输入文件存在
        if not input_file.exists():
            raise FileNotFoundError(f"Input file not found: {input_file}")
        
        # 准备输出文件
        output_file = self.golden_dir / f"{test_id}_output.pcap"
        
        # 运行处理
        executor = ConsistentProcessor.create_executor(
            dedup=config.get("dedup", False),
            anon=config.get("anon", False),
            mask=config.get("mask", False)
        )
        
        result = executor.run(input_file, output_file)
        
        # 计算哈希
        input_hash = self._calculate_file_hash(input_file)
        output_hash = self._calculate_file_hash(output_file)
        
        # 提取统计信息
        stats = {
            "packets_processed": result.total_packets,
            "packets_modified": sum(s.packets_modified for s in result.stage_stats),
            "duration_ms": result.duration_ms,
            "stages": [
                {
                    "name": s.stage_name,
                    "packets_processed": s.packets_processed,
                    "packets_modified": s.packets_modified,
                    "duration_ms": s.duration_ms,
                }
                for s in result.stage_stats
            ]
        }
        
        # 构建基准数据
        baseline = {
            "test_id": test_id,
            "name": test_case["name"],
            "input_file": test_case["input_file"],
            "input_hash": input_hash,
            "config": config,
            "output_hash": output_hash,
            "output_file_size": output_file.stat().st_size,
            "packet_count": result.total_packets,
            "stats": stats,
            "timestamp": datetime.now().isoformat(),
            "version": "1.0",
        }
        
        # 保存基准文件
        baseline_file = self.golden_dir / f"{test_id}_baseline.json"
        baseline_file.write_text(json.dumps(baseline, indent=2))
        
        return baseline
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """计算文件SHA256哈希"""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()


def main():
    """主函数"""
    generator = GoldenBaselineGenerator()
    generator.generate_all_baselines()


if __name__ == "__main__":
    main()
```

---

### 步骤3: 生成黄金基准

```bash
# 在当前稳定版本运行
cd /path/to/PktMask
python tests/e2e/generate_golden_baseline.py

# 预期输出:
# 🚀 Starting Golden Baseline Generation
# 📁 Golden directory: /path/to/PktMask/tests/e2e/golden
# 📊 Total test cases: 16
#
# Processing E2E-001: Dedup Only...
#   ✅ Generated baseline
#      Output hash: a1b2c3d4e5f6g7h8...
#      Packets: 150
# ...
# ============================================================
# ✅ Success: 16/16
# ============================================================
```

---

### 步骤4: 验证黄金基准

```bash
# 检查生成的文件
ls -lh tests/e2e/golden/

# 预期输出:
# E2E-001_baseline.json
# E2E-001_output.pcap
# E2E-002_baseline.json
# E2E-002_output.pcap
# ...

# 查看基准内容
cat tests/e2e/golden/E2E-001_baseline.json
```

---

### 步骤5: 提交黄金基准到版本控制

```bash
# 添加到 Git
git add tests/e2e/golden/
git commit -m "Add E2E golden baselines for regression testing"

# 注意: 黄金基准文件应该纳入版本控制
# 这样团队成员都使用相同的基准
```

---

### 步骤6: 创建验证测试

创建 `tests/e2e/test_e2e_golden_validation.py`（参考 E2E_TEST_PLAN.md 中的完整代码）

---

### 步骤7: 运行端到端测试

```bash
# 运行所有端到端测试
pytest tests/e2e/test_e2e_golden_validation.py -v

# 运行特定测试组
pytest tests/e2e/test_e2e_golden_validation.py::TestE2EGoldenValidation::test_core_functionality_consistency -v

# 并行运行（需要 pytest-xdist）
pytest tests/e2e/test_e2e_golden_validation.py -n auto

# 生成HTML报告
pytest tests/e2e/test_e2e_golden_validation.py --html=e2e_report.html --self-contained-html
```

---

## 🔧 CI/CD 集成

### GitHub Actions 示例

创建 `.github/workflows/e2e-tests.yml`:

```yaml
name: E2E Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]

jobs:
  e2e-tests:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.10'
    
    - name: Install dependencies
      run: |
        pip install -e .
        pip install pytest pytest-xdist pytest-timeout pytest-html
    
    - name: Run E2E tests
      run: |
        pytest tests/e2e/test_e2e_golden_validation.py -v --html=e2e_report.html --self-contained-html
    
    - name: Upload test report
      if: always()
      uses: actions/upload-artifact@v3
      with:
        name: e2e-test-report
        path: e2e_report.html
```

---

## 📊 测试报告示例

### 成功输出

```
tests/e2e/test_e2e_golden_validation.py::TestE2EGoldenValidation::test_core_functionality_consistency[E2E-001] PASSED
tests/e2e/test_e2e_golden_validation.py::TestE2EGoldenValidation::test_core_functionality_consistency[E2E-002] PASSED
tests/e2e/test_e2e_golden_validation.py::TestE2EGoldenValidation::test_core_functionality_consistency[E2E-003] PASSED
...
======================== 16 passed in 45.23s ========================
```

### 失败输出

```
tests/e2e/test_e2e_golden_validation.py::TestE2EGoldenValidation::test_core_functionality_consistency[E2E-003] FAILED

FAILED tests/e2e/test_e2e_golden_validation.py::TestE2EGoldenValidation::test_core_functionality_consistency[E2E-003]
AssertionError: Output hash mismatch for E2E-003
Expected: a1b2c3d4e5f6g7h8...
Got:      x9y8z7w6v5u4t3s2...

This indicates that the Mask Only functionality has changed.
Please verify if this is an intentional change.
```

---

## 🛠️ 故障排查

### 问题1: 测试数据文件不存在

```bash
# 错误信息
FileNotFoundError: Input file not found: tests/data/tls/tls_1_2-2.pcap

# 解决方案
# 确保测试数据文件存在
ls tests/data/tls/
ls tests/samples/http-collector/
```

### 问题2: 哈希不匹配但功能正确

```python
# 可能原因:
# 1. 时间戳字段变化
# 2. 随机数生成
# 3. 非确定性处理

# 解决方案:
# 检查是否是预期的变化，如果是，重新生成黄金基准
python tests/e2e/generate_golden_baseline.py
```

### 问题3: 性能测试超时

```bash
# 增加超时时间
pytest tests/e2e/test_e2e_golden_validation.py --timeout=300
```

---

## 📝 最佳实践

### 1. 黄金基准管理

- ✅ 在稳定版本生成基准
- ✅ 纳入版本控制
- ✅ 定期审查和更新
- ❌ 不要频繁修改基准

### 2. 测试数据选择

- ✅ 覆盖典型场景
- ✅ 包含边界条件
- ✅ 文件大小适中（<10MB）
- ❌ 避免过大文件影响测试速度

### 3. 测试执行

- ✅ 本地运行完整测试
- ✅ CI 运行核心测试
- ✅ 使用并行执行加速
- ❌ 不要跳过失败的测试

---

## 🎯 下一步

1. **立即执行**: 生成黄金基准
2. **集成 CI**: 添加到持续集成流程
3. **定期审查**: 每月审查测试覆盖
4. **持续改进**: 根据反馈优化测试

---

**文档版本**: 1.0  
**创建日期**: 2025-10-09  
**维护人**: 开发团队

