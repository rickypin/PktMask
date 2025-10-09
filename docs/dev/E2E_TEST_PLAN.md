# PktMask 端到端测试方案

> **目标**: 确保重构、更新后功能一致性  
> **原则**: 聚焦功能一致性，理性实用，不过度设计  
> **测试数据**: `tests/data/tls/` 和 `tests/samples/http-collector/`

---

## 📋 方案概述

### 核心思想

**黄金文件测试法 (Golden File Testing)**
- 在当前稳定版本生成"黄金输出"（基准）
- 重构后运行相同测试，对比输出是否一致
- 使用文件哈希值验证完全一致性

### 测试范围

```
输入 PCAP → [PktMask 处理] → 输出 PCAP
                ↓
        验证功能一致性：
        1. 输出文件哈希值
        2. 数据包数量
        3. 关键字段保留/掩码
        4. 处理统计信息
```

---

## 🎯 测试矩阵

### 1. 核心功能组合测试

| 测试ID | Remove Dupes | Anonymize IPs | Mask Payloads | 测试文件 |
|--------|--------------|---------------|---------------|----------|
| E2E-001 | ✅ | ❌ | ❌ | tls_1_2-2.pcap |
| E2E-002 | ❌ | ✅ | ❌ | tls_1_2-2.pcap |
| E2E-003 | ❌ | ❌ | ✅ | tls_1_2-2.pcap |
| E2E-004 | ✅ | ✅ | ❌ | tls_1_2-2.pcap |
| E2E-005 | ✅ | ❌ | ✅ | tls_1_2-2.pcap |
| E2E-006 | ❌ | ✅ | ✅ | tls_1_2-2.pcap |
| E2E-007 | ✅ | ✅ | ✅ | tls_1_2-2.pcap |

**目的**: 验证所有功能组合的一致性

---

### 2. 协议覆盖测试

| 测试ID | 协议类型 | 测试文件 | 验证重点 |
|--------|----------|----------|----------|
| E2E-101 | TLS 1.0 | tls_1_0_multi_segment_google-https.pcap | 多段重组 |
| E2E-102 | TLS 1.2 | tls_1_2-2.pcap | 标准TLS处理 |
| E2E-103 | TLS 1.3 | tls_1_3_0-RTT-2_22_23_mix.pcap | TLS 1.3 + 0-RTT |
| E2E-104 | SSL 3.0 | ssl_3.pcap | 旧版SSL |
| E2E-105 | HTTP | http-download-good.pcap | HTTP协议 |
| E2E-106 | HTTP Error | http-500error.pcap | HTTP错误处理 |

**目的**: 验证不同协议的处理一致性

---

### 3. 封装类型测试

| 测试ID | 封装类型 | 测试文件 | 验证重点 |
|--------|----------|----------|----------|
| E2E-201 | Plain IP | tls_1_2_plainip.pcap | 无封装 |
| E2E-202 | Single VLAN | tls_1_2_single_vlan.pcap | 单层VLAN |
| E2E-203 | Double VLAN | tls_1_2_double_vlan.pcap | 双层VLAN (QinQ) |

**目的**: 验证不同封装类型的处理一致性

---

### 4. 边界条件测试

| 测试ID | 场景 | 测试文件/方法 | 验证重点 |
|--------|------|---------------|----------|
| E2E-301 | 空文件 | 创建空PCAP | 错误处理 |
| E2E-302 | 单包文件 | 创建单包PCAP | 最小输入 |
| E2E-303 | 大文件 | 合并多个PCAP | 性能和内存 |
| E2E-304 | 损坏文件 | 截断PCAP | 错误恢复 |
| E2E-305 | 无TLS流量 | http-download-good.pcap | 协议检测 |

**目的**: 验证异常情况的处理一致性

---

## 🔧 测试实现方案

### 阶段1: 生成黄金基准 (Golden Baseline)

```python
# tests/e2e/generate_golden_baseline.py

import hashlib
import json
from pathlib import Path
from typing import Dict, Any

class GoldenBaselineGenerator:
    """生成黄金基准输出"""
    
    def __init__(self, test_data_dir: Path, golden_dir: Path):
        self.test_data_dir = test_data_dir
        self.golden_dir = golden_dir
        self.golden_dir.mkdir(exist_ok=True)
    
    def generate_baseline(self, test_id: str, config: Dict[str, bool], 
                         input_file: Path) -> Dict[str, Any]:
        """
        生成单个测试的黄金基准
        
        Returns:
            {
                "test_id": "E2E-001",
                "input_file": "tls_1_2-2.pcap",
                "input_hash": "abc123...",
                "config": {"dedup": True, "anon": False, "mask": False},
                "output_hash": "def456...",
                "packet_count": 150,
                "stats": {...},
                "timestamp": "2025-10-09T12:00:00"
            }
        """
        # 1. 运行处理
        output_file = self.golden_dir / f"{test_id}_output.pcap"
        result = self._run_processing(input_file, output_file, config)
        
        # 2. 计算哈希
        input_hash = self._calculate_file_hash(input_file)
        output_hash = self._calculate_file_hash(output_file)
        
        # 3. 提取统计信息
        stats = self._extract_stats(result)
        
        # 4. 保存基准
        baseline = {
            "test_id": test_id,
            "input_file": input_file.name,
            "input_hash": input_hash,
            "config": config,
            "output_hash": output_hash,
            "packet_count": stats["packets_processed"],
            "stats": stats,
            "timestamp": datetime.now().isoformat()
        }
        
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
    
    def _run_processing(self, input_file, output_file, config):
        """运行实际处理（使用当前稳定版本）"""
        from pktmask.core.consistency import ConsistentProcessor
        
        executor = ConsistentProcessor.create_executor(
            dedup=config.get("dedup", False),
            anon=config.get("anon", False),
            mask=config.get("mask", False)
        )
        
        return executor.run(input_file, output_file)
```

**使用方式**:
```bash
# 在当前稳定版本运行一次，生成所有黄金基准
python tests/e2e/generate_golden_baseline.py
```

---

### 阶段2: 端到端验证测试

```python
# tests/e2e/test_e2e_golden_validation.py

import pytest
from pathlib import Path
import json

class TestE2EGoldenValidation:
    """端到端黄金基准验证测试"""
    
    @pytest.fixture(scope="class")
    def golden_baselines(self):
        """加载所有黄金基准"""
        golden_dir = Path("tests/e2e/golden")
        baselines = {}
        for baseline_file in golden_dir.glob("*_baseline.json"):
            baseline = json.loads(baseline_file.read_text())
            baselines[baseline["test_id"]] = baseline
        return baselines
    
    # ========== 核心功能组合测试 ==========
    
    @pytest.mark.parametrize("test_id,config,input_file", [
        ("E2E-001", {"dedup": True, "anon": False, "mask": False}, 
         "tls_1_2-2.pcap"),
        ("E2E-002", {"dedup": False, "anon": True, "mask": False}, 
         "tls_1_2-2.pcap"),
        ("E2E-003", {"dedup": False, "anon": False, "mask": True}, 
         "tls_1_2-2.pcap"),
        ("E2E-004", {"dedup": True, "anon": True, "mask": False}, 
         "tls_1_2-2.pcap"),
        ("E2E-005", {"dedup": True, "anon": False, "mask": True}, 
         "tls_1_2-2.pcap"),
        ("E2E-006", {"dedup": False, "anon": True, "mask": True}, 
         "tls_1_2-2.pcap"),
        ("E2E-007", {"dedup": True, "anon": True, "mask": True}, 
         "tls_1_2-2.pcap"),
    ])
    def test_core_functionality_consistency(self, test_id, config, 
                                           input_file, golden_baselines, 
                                           tmp_path):
        """验证核心功能组合的一致性"""
        # 1. 获取黄金基准
        baseline = golden_baselines[test_id]
        
        # 2. 运行当前版本处理
        input_path = Path("tests/data/tls") / input_file
        output_path = tmp_path / f"{test_id}_output.pcap"
        
        result = self._run_processing(input_path, output_path, config)
        
        # 3. 验证输出哈希一致
        output_hash = self._calculate_file_hash(output_path)
        assert output_hash == baseline["output_hash"], \
            f"Output hash mismatch for {test_id}"
        
        # 4. 验证数据包数量一致
        assert result.total_packets == baseline["packet_count"], \
            f"Packet count mismatch for {test_id}"
        
        # 5. 验证统计信息一致
        self._verify_stats_consistency(result.stats, baseline["stats"])
    
    # ========== 协议覆盖测试 ==========
    
    @pytest.mark.parametrize("test_id,protocol,input_file", [
        ("E2E-101", "TLS 1.0", "tls_1_0_multi_segment_google-https.pcap"),
        ("E2E-102", "TLS 1.2", "tls_1_2-2.pcap"),
        ("E2E-103", "TLS 1.3", "tls_1_3_0-RTT-2_22_23_mix.pcap"),
        ("E2E-104", "SSL 3.0", "ssl_3.pcap"),
        ("E2E-105", "HTTP", "http-download-good.pcap"),
        ("E2E-106", "HTTP Error", "http-500error.pcap"),
    ])
    def test_protocol_coverage_consistency(self, test_id, protocol, 
                                          input_file, golden_baselines, 
                                          tmp_path):
        """验证不同协议的处理一致性"""
        baseline = golden_baselines[test_id]
        
        # 使用全功能配置测试
        config = {"dedup": True, "anon": True, "mask": True}
        
        # 根据协议选择测试数据目录
        if "http" in input_file.lower():
            input_path = Path("tests/samples/http-collector") / input_file
        else:
            input_path = Path("tests/data/tls") / input_file
        
        output_path = tmp_path / f"{test_id}_output.pcap"
        result = self._run_processing(input_path, output_path, config)
        
        # 验证一致性
        output_hash = self._calculate_file_hash(output_path)
        assert output_hash == baseline["output_hash"], \
            f"Protocol {protocol} processing inconsistent"
    
    # ========== 封装类型测试 ==========
    
    @pytest.mark.parametrize("test_id,encap_type,input_file", [
        ("E2E-201", "Plain IP", "tls_1_2_plainip.pcap"),
        ("E2E-202", "Single VLAN", "tls_1_2_single_vlan.pcap"),
        ("E2E-203", "Double VLAN", "tls_1_2_double_vlan.pcap"),
    ])
    def test_encapsulation_consistency(self, test_id, encap_type, 
                                      input_file, golden_baselines, 
                                      tmp_path):
        """验证不同封装类型的处理一致性"""
        baseline = golden_baselines[test_id]
        
        config = {"dedup": False, "anon": True, "mask": True}
        input_path = Path("tests/data/tls") / input_file
        output_path = tmp_path / f"{test_id}_output.pcap"
        
        result = self._run_processing(input_path, output_path, config)
        
        output_hash = self._calculate_file_hash(output_path)
        assert output_hash == baseline["output_hash"], \
            f"Encapsulation {encap_type} processing inconsistent"
    
    # ========== 辅助方法 ==========
    
    def _run_processing(self, input_file, output_file, config):
        """运行处理（使用重构后的代码）"""
        from pktmask.core.consistency import ConsistentProcessor
        
        executor = ConsistentProcessor.create_executor(
            dedup=config.get("dedup", False),
            anon=config.get("anon", False),
            mask=config.get("mask", False)
        )
        
        return executor.run(input_file, output_file)
    
    def _calculate_file_hash(self, file_path):
        """计算文件哈希"""
        import hashlib
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    def _verify_stats_consistency(self, current_stats, baseline_stats):
        """验证统计信息一致性"""
        # 验证关键统计字段
        key_fields = ["packets_processed", "packets_modified", 
                     "duration_ms"]
        for field in key_fields:
            if field in baseline_stats:
                assert field in current_stats, \
                    f"Missing stats field: {field}"
                # 允许duration_ms有10%的误差
                if field == "duration_ms":
                    tolerance = baseline_stats[field] * 0.1
                    assert abs(current_stats[field] - baseline_stats[field]) <= tolerance
                else:
                    assert current_stats[field] == baseline_stats[field], \
                        f"Stats mismatch for {field}"
```

---

## 📁 测试目录结构

```
tests/
├── e2e/                              # 端到端测试
│   ├── __init__.py
│   ├── generate_golden_baseline.py  # 黄金基准生成器
│   ├── test_e2e_golden_validation.py # 黄金基准验证测试
│   ├── golden/                       # 黄金基准数据
│   │   ├── E2E-001_baseline.json
│   │   ├── E2E-001_output.pcap
│   │   ├── E2E-002_baseline.json
│   │   ├── E2E-002_output.pcap
│   │   └── ...
│   └── README.md                     # 使用说明
├── data/
│   └── tls/                          # TLS测试数据
│       ├── tls_1_2-2.pcap
│       ├── tls_1_3_0-RTT-2_22_23_mix.pcap
│       └── ...
└── samples/
    └── http-collector/               # HTTP测试数据
        ├── http-download-good.pcap
        └── ...
```

---

## 🚀 使用流程

### 步骤1: 生成黄金基准（仅一次）

```bash
# 在当前稳定版本运行
cd /path/to/PktMask
python tests/e2e/generate_golden_baseline.py

# 输出示例:
# ✅ Generated baseline for E2E-001
# ✅ Generated baseline for E2E-002
# ...
# 📊 Total: 20 baselines generated
```

### 步骤2: 重构代码

```bash
# 进行代码重构、优化、更新
# ...
```

### 步骤3: 运行端到端验证

```bash
# 运行所有端到端测试
pytest tests/e2e/test_e2e_golden_validation.py -v

# 或运行特定测试组
pytest tests/e2e/test_e2e_golden_validation.py::TestE2EGoldenValidation::test_core_functionality_consistency -v
```

### 步骤4: 分析差异（如果测试失败）

```bash
# 如果测试失败，查看详细差异
pytest tests/e2e/test_e2e_golden_validation.py -v --tb=long

# 手动对比输出文件
diff tests/e2e/golden/E2E-001_output.pcap /tmp/pytest-xxx/E2E-001_output.pcap
```

---

## 📊 验证指标

### 1. 完全一致性验证

- **输出文件哈希**: SHA256 完全匹配
- **数据包数量**: 精确匹配
- **文件大小**: 字节级匹配

### 2. 统计信息验证

- **处理数据包数**: 精确匹配
- **修改数据包数**: 精确匹配
- **处理时间**: 允许 ±10% 误差

### 3. 功能验证（可选）

```python
def verify_tls_handshake_preserved(output_pcap):
    """验证TLS握手被保留"""
    packets = rdpcap(output_pcap)
    tls_handshake_count = sum(1 for pkt in packets 
                              if has_tls_handshake(pkt))
    assert tls_handshake_count > 0

def verify_application_data_masked(output_pcap):
    """验证应用数据被掩码"""
    packets = rdpcap(output_pcap)
    for pkt in packets:
        if has_tls_application_data(pkt):
            assert is_masked(pkt)
```

---

## ⚠️ 注意事项

### 1. 黄金基准的稳定性

- **生成时机**: 在确认功能正确的稳定版本生成
- **版本控制**: 黄金基准文件纳入 Git 版本控制
- **更新策略**: 只在有意修改功能时更新基准

### 2. 测试数据管理

- **数据完整性**: 测试数据文件不应修改
- **数据多样性**: 覆盖不同协议、封装、场景
- **数据大小**: 平衡测试覆盖和执行时间

### 3. 性能考虑

- **并行执行**: 使用 `pytest-xdist` 并行运行测试
- **选择性运行**: 使用 pytest markers 分组测试
- **CI/CD 集成**: 在 CI 中运行核心测试，本地运行完整测试

---

## 🎯 成功标准

### 重构验证通过条件

✅ **所有端到端测试通过** (100% 通过率)
- 核心功能组合测试: 7/7 通过
- 协议覆盖测试: 6/6 通过  
- 封装类型测试: 3/3 通过

✅ **输出完全一致**
- 所有输出文件哈希匹配黄金基准
- 数据包数量精确匹配
- 统计信息在允许误差范围内

✅ **无回归问题**
- 没有新增的错误或异常
- 性能没有显著下降（±10%）

---

## 📝 总结

### 方案优势

1. **简单实用**: 基于文件哈希对比，实现简单
2. **可靠性高**: 黄金基准确保功能一致性
3. **易于维护**: 测试代码清晰，易于扩展
4. **快速反馈**: 自动化测试，快速发现问题

### 实施建议

1. **立即生成基准**: 在当前稳定版本生成黄金基准
2. **纳入 CI/CD**: 集成到持续集成流程
3. **定期审查**: 定期审查和更新测试用例
4. **文档同步**: 保持测试文档与代码同步

---

**文档版本**: 1.0  
**创建日期**: 2025-10-09  
**维护人**: 开发团队

