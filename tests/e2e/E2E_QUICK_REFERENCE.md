# E2E测试快速参考手册

## 📋 概述

本文档提供端到端(E2E)测试的快速参考,包括执行命令、文件结构和检查指标说明。

**测试架构**: 双层测试 (CLI黑盒 + API白盒)  
**测试总数**: 32个 (每层16个)  
**覆盖范围**: 核心功能、协议覆盖、封装类型

---

## 🚀 快速执行命令

### 1. 运行所有E2E测试

```bash
# 运行所有E2E测试 (CLI黑盒 + API白盒)
pytest tests/e2e/ -v

# 生成HTML报告
pytest tests/e2e/ -v --html=tests/e2e/report.html --self-contained-html
```

**预期结果**: 32/32 passed (100%)

---

### 2. 运行CLI黑盒测试 (完全解耦)

```bash
# 运行CLI黑盒测试
pytest tests/e2e/test_e2e_cli_blackbox.py -v

# 运行特定类别
pytest tests/e2e/test_e2e_cli_blackbox.py::TestE2ECLIBlackbox::test_cli_core_functionality_consistency -v
pytest tests/e2e/test_e2e_cli_blackbox.py::TestE2ECLIBlackbox::test_cli_protocol_coverage_consistency -v
pytest tests/e2e/test_e2e_cli_blackbox.py::TestE2ECLIBlackbox::test_cli_encapsulation_consistency -v

# 运行单个测试
pytest tests/e2e/test_e2e_cli_blackbox.py -k "E2E-001" -v
```

**特点**: 
- ✅ 100%解耦 (无API依赖)
- ✅ 使用CLI生成的基准 (golden_cli/)
- ✅ 只验证输出文件哈希

---

### 3. 运行API白盒测试 (详细验证)

```bash
# 运行API白盒测试
pytest tests/e2e/test_e2e_golden_validation.py -v

# 运行特定类别
pytest tests/e2e/test_e2e_golden_validation.py::TestE2EGoldenValidation::test_core_functionality_consistency -v
pytest tests/e2e/test_e2e_golden_validation.py::TestE2EGoldenValidation::test_protocol_coverage_consistency -v
pytest tests/e2e/test_e2e_golden_validation.py::TestE2EGoldenValidation::test_encapsulation_consistency -v

# 运行单个测试
pytest tests/e2e/test_e2e_golden_validation.py -k "E2E-001" -v
```

**特点**:
- ✅ 详细验证 (10+个指标)
- ✅ HTML报告包含基线比对表格
- ✅ 验证检查列表

---

### 4. 生成黄金基准

```bash
# 生成API基准 (用于API白盒测试)
python tests/e2e/generate_golden_baseline.py

# 生成CLI基准 (用于CLI黑盒测试, 100%解耦)
python tests/e2e/generate_cli_golden_baseline.py
```

**注意**: 
- 只在稳定版本上生成基准
- CLI基准完全通过CLI生成,无API依赖
- API基准包含详细的内部统计数据

---

### 5. 查看测试报告

```bash
# 查看HTML报告
open tests/e2e/report.html

# 查看JSON结果
cat tests/e2e/test_results.json | jq
```

---

## 📁 文件结构

### 测试代码文件

```
tests/e2e/
├── test_e2e_cli_blackbox.py          # CLI黑盒测试 (100%解耦)
├── test_e2e_golden_validation.py     # API白盒测试 (详细验证)
├── conftest.py                        # pytest配置和HTML报告定制
├── generate_cli_golden_baseline.py   # CLI基准生成器 (100%解耦)
├── generate_golden_baseline.py       # API基准生成器
└── README.md                          # 快速开始指南
```

### 黄金基准文件

```
tests/e2e/
├── golden/                            # API基准 (用于API白盒测试)
│   ├── E2E-001_baseline.json         # 包含stats, stages等内部数据
│   ├── E2E-002_baseline.json
│   └── ...
│
└── golden_cli/                        # CLI基准 (用于CLI黑盒测试)
    ├── E2E-001_baseline.json         # 只包含output_hash, cli_args
    ├── E2E-001_output.pcap           # 基准输出文件
    ├── E2E-002_baseline.json
    ├── E2E-002_output.pcap
    └── ...
```

### 测试数据文件

```
tests/
├── data/tls/                          # TLS/SSL测试数据
│   ├── tls_1_2-2.pcap
│   ├── tls_1_0_multi_segment_google-https.pcap
│   ├── tls_1_3_0-RTT-2_22_23_mix.pcap
│   ├── ssl_3.pcap
│   ├── tls_1_2_plainip.pcap
│   ├── tls_1_2_single_vlan.pcap
│   └── tls_1_2_double_vlan.pcap
│
└── samples/http-collector/            # HTTP测试数据
    ├── http-download-good.pcap
    └── http-500error.pcap
```

### 文档文件

```
docs/dev/
├── E2E_TEST_PLAN.md                           # 测试计划 (16个测试用例定义)
├── E2E_TEST_IMPLEMENTATION_GUIDE.md           # 实施指南
├── E2E_TEST_IMPROVEMENTS.md                   # 改进建议
├── E2E_VALIDATION_DETAILS_ENHANCEMENT.md      # 验证详情功能说明
├── E2E_TESTING_COMPLETE_SUMMARY.md            # 完整总结
├── E2E_CLI_BLACKBOX_TESTING.md                # CLI黑盒测试设计
├── E2E_CLI_BLACKBOX_FAILURE_ANALYSIS.md       # 失败原因分析
├── E2E_CLI_DECOUPLING_ANALYSIS.md             # 解耦分析
└── E2E_TEST_PARAMETERS_COMPARISON.md          # 参数对比

tests/e2e/
├── README.md                                   # 快速开始
├── REPORT_GUIDE.md                             # HTML报告使用指南
└── E2E_QUICK_REFERENCE.md                      # 本文档
```

---

## 📊 检查指标解释

### CLI黑盒测试指标

CLI黑盒测试只验证**1个核心指标**:

| 指标 | 说明 | 验证方式 |
|------|------|---------|
| **Output Hash** | 输出文件SHA256哈希 | 与CLI基准比对 |

**验证逻辑**:
```python
output_hash = calculate_sha256(output_file)
assert output_hash == baseline["output_hash"]
```

**特点**: 
- ✅ 纯黑盒验证
- ✅ 不依赖内部数据
- ✅ 100%解耦

---

### API白盒测试指标

API白盒测试验证**10+个详细指标**:

#### 1. 核心指标 (7个)

| 指标 | 说明 | 来源 |
|------|------|------|
| **Output Hash** | 输出文件SHA256哈希 | 文件计算 |
| **Packet Count** | 数据包总数 | `stage_stats[0].packets_processed` |
| **File Size** | 输出文件大小(字节) | 文件系统 |
| **Packets Processed** | 处理的数据包数 | `stats.packets_processed` |
| **Packets Modified** | 修改的数据包数 | `stats.packets_modified` |
| **Duration (ms)** | 处理耗时(毫秒) | `stats.duration_ms` |
| **Stage Count** | 处理阶段数量 | `len(stats.stages)` |

#### 2. 阶段统计指标

每个处理阶段包含:

| 指标 | 说明 | 示例 |
|------|------|------|
| **Stage Name** | 阶段名称 | `DeduplicationStage`, `AnonymizationStage`, `MaskingStage` |
| **Packets Processed** | 该阶段处理的包数 | 14 |
| **Packets Modified** | 该阶段修改的包数 | 0, 14, 1 |
| **Duration (ms)** | 该阶段耗时 | 7.90 |

**示例**:
```json
{
  "stages": [
    {
      "name": "DeduplicationStage",
      "packets_processed": 14,
      "packets_modified": 0,
      "duration_ms": 7.90
    }
  ]
}
```

#### 3. 验证检查列表 (10+项)

HTML报告中显示的检查项:

| 检查项 | 说明 |
|--------|------|
| ✅ Output file hash matches baseline | 输出哈希匹配 |
| ✅ Packet count matches | 数据包数量匹配 |
| ✅ File size matches | 文件大小匹配 |
| ✅ Packets processed matches | 处理包数匹配 |
| ✅ Packets modified matches | 修改包数匹配 |
| ✅ Duration within acceptable range | 耗时在合理范围 |
| ✅ Stage count matches | 阶段数量匹配 |
| ✅ All stages present | 所有阶段存在 |
| ✅ Stage statistics consistent | 阶段统计一致 |
| ✅ No processing errors | 无处理错误 |

---

## 🎯 测试用例分类

### 1. 核心功能测试 (E2E-001 ~ E2E-007)

测试所有功能组合:

| 测试ID | 功能组合 | dedup | anon | mask |
|--------|---------|-------|------|------|
| E2E-001 | Dedup Only | ✅ | ❌ | ❌ |
| E2E-002 | Anonymize Only | ❌ | ✅ | ❌ |
| E2E-003 | Mask Only | ❌ | ❌ | ✅ |
| E2E-004 | Dedup + Anonymize | ✅ | ✅ | ❌ |
| E2E-005 | Dedup + Mask | ✅ | ❌ | ✅ |
| E2E-006 | Anonymize + Mask | ❌ | ✅ | ✅ |
| E2E-007 | All Features | ✅ | ✅ | ✅ |

**参数**: 7种组合,覆盖所有有意义的功能组合

---

### 2. 协议覆盖测试 (E2E-101 ~ E2E-106)

测试不同协议处理:

| 测试ID | 协议 | 参数 |
|--------|------|------|
| E2E-101 | TLS 1.0 | `dedup=True, anon=True, mask=True` |
| E2E-102 | TLS 1.2 | `dedup=True, anon=True, mask=True` |
| E2E-103 | TLS 1.3 | `dedup=True, anon=True, mask=True` |
| E2E-104 | SSL 3.0 | `dedup=True, anon=True, mask=True` |
| E2E-105 | HTTP | `dedup=True, anon=True, mask=True` |
| E2E-106 | HTTP Error | `dedup=True, anon=True, mask=True` |

**参数**: 全功能启用,测试协议处理能力

---

### 3. 封装类型测试 (E2E-201 ~ E2E-203)

测试不同网络封装:

| 测试ID | 封装类型 | 参数 |
|--------|---------|------|
| E2E-201 | Plain IP | `dedup=False, anon=True, mask=True` |
| E2E-202 | Single VLAN | `dedup=False, anon=True, mask=True` |
| E2E-203 | Double VLAN | `dedup=False, anon=True, mask=True` |

**参数**: 不启用去重,聚焦封装类型处理

---

## 🔍 常见问题

### Q1: 测试失败怎么办?

**步骤**:
1. 查看失败信息: `pytest tests/e2e/ -v --tb=short`
2. 检查HTML报告: `open tests/e2e/report.html`
3. 对比基线差异: 查看报告中的"Baseline Comparison"表格
4. 如果是预期变更: 重新生成基准

### Q2: 如何重新生成基准?

```bash
# API基准
python tests/e2e/generate_golden_baseline.py

# CLI基准 (推荐,100%解耦)
python tests/e2e/generate_cli_golden_baseline.py
```

**注意**: 只在确认输出正确后重新生成基准

### Q3: CLI和API测试有什么区别?

| 特性 | CLI黑盒测试 | API白盒测试 |
|------|-----------|-----------|
| **解耦程度** | 100% | 部分耦合 |
| **验证指标** | 1个 (hash) | 10+个 |
| **基准来源** | CLI生成 | API生成 |
| **调试信息** | 少 | 丰富 |
| **用途** | 用户接口验证 | 内部逻辑验证 |

**建议**: 两者都运行,互相补充

### Q4: 如何查看详细的验证信息?

```bash
# 生成HTML报告
pytest tests/e2e/test_e2e_golden_validation.py --html=report.html --self-contained-html

# 打开报告
open report.html
```

HTML报告包含:
- ✅ 基线比对表格 (7个核心指标)
- ✅ 验证检查列表 (10+个检查项)
- ✅ 可视化展示 (表格、图标、颜色)

---

## 📚 相关文档

| 文档 | 说明 |
|------|------|
| `tests/e2e/README.md` | 快速开始指南 |
| `tests/e2e/REPORT_GUIDE.md` | HTML报告使用指南 |
| `docs/dev/E2E_TEST_PLAN.md` | 完整测试计划 |
| `docs/dev/E2E_TESTING_COMPLETE_SUMMARY.md` | 完整总结 |
| `docs/dev/E2E_CLI_DECOUPLING_ANALYSIS.md` | 解耦分析 |
| `docs/dev/E2E_TEST_PARAMETERS_COMPARISON.md` | 参数对比 |

---

## ✅ 快速检查清单

运行E2E测试前:
- [ ] 激活虚拟环境: `source venv/bin/activate`
- [ ] 安装依赖: `pip install -r requirements.txt`
- [ ] 确认测试数据存在: `ls tests/data/tls/`

运行E2E测试:
- [ ] 运行所有测试: `pytest tests/e2e/ -v`
- [ ] 检查通过率: 应为 32/32 (100%)
- [ ] 查看HTML报告: `open tests/e2e/report.html`

测试失败时:
- [ ] 查看失败详情: `pytest tests/e2e/ -v --tb=short`
- [ ] 检查是否预期变更
- [ ] 如需要,重新生成基准

---

**文档版本**: 1.0  
**创建日期**: 2025-10-09  
**最后更新**: 2025-10-09  
**维护者**: PktMask Development Team

