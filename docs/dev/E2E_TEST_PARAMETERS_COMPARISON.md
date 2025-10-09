# E2E测试参数对比详细文档

## 📋 概述

本文档详细对比CLI黑盒测试和API白盒测试中每个测试用例使用的参数配置。

**对比日期**: 2025-10-09  
**测试总数**: 16个 (每层)  
**参数一致性**: 100% ✅

---

## 📊 完整参数对比表

### 1. 核心功能测试 (E2E-001 ~ E2E-007)

| 测试ID | 测试名称 | dedup | anon | mask | CLI参数 | API参数 | 一致? |
|--------|---------|-------|------|------|---------|---------|-------|
| E2E-001 | Dedup Only | ✅ | ❌ | ❌ | `True, False, False` | `True, False, False` | ✅ |
| E2E-002 | Anonymize Only | ❌ | ✅ | ❌ | `False, True, False` | `False, True, False` | ✅ |
| E2E-003 | Mask Only | ❌ | ❌ | ✅ | `False, False, True` | `False, False, True` | ✅ |
| E2E-004 | Dedup + Anonymize | ✅ | ✅ | ❌ | `True, True, False` | `True, True, False` | ✅ |
| E2E-005 | Dedup + Mask | ✅ | ❌ | ✅ | `True, False, True` | `True, False, True` | ✅ |
| E2E-006 | Anonymize + Mask | ❌ | ✅ | ✅ | `False, True, True` | `False, True, True` | ✅ |
| E2E-007 | All Features | ✅ | ✅ | ✅ | `True, True, True` | `True, True, True` | ✅ |

**代码位置**:

**CLI黑盒** (`test_e2e_cli_blackbox.py` line 119-142):
```python
@pytest.mark.parametrize(
    "test_id,dedup,anon,mask,input_file",
    [
        ("E2E-001", True, False, False, "tls_1_2-2.pcap"),
        ("E2E-002", False, True, False, "tls_1_2-2.pcap"),
        ("E2E-003", False, False, True, "tls_1_2-2.pcap"),
        ("E2E-004", True, True, False, "tls_1_2-2.pcap"),
        ("E2E-005", True, False, True, "tls_1_2-2.pcap"),
        ("E2E-006", False, True, True, "tls_1_2-2.pcap"),
        ("E2E-007", True, True, True, "tls_1_2-2.pcap"),
    ],
)
def test_cli_core_functionality_consistency(...):
    result = self._run_cli_command(cli_executable, input_path, output_path, dedup, anon, mask)
```

**API白盒** (`test_e2e_golden_validation.py` line 109-132):
```python
@pytest.mark.parametrize(
    "test_id,config,input_file",
    [
        ("E2E-001", {"dedup": True, "anon": False, "mask": False}, "tls_1_2-2.pcap"),
        ("E2E-002", {"dedup": False, "anon": True, "mask": False}, "tls_1_2-2.pcap"),
        ("E2E-003", {"dedup": False, "anon": False, "mask": True}, "tls_1_2-2.pcap"),
        ("E2E-004", {"dedup": True, "anon": True, "mask": False}, "tls_1_2-2.pcap"),
        ("E2E-005", {"dedup": True, "anon": False, "mask": True}, "tls_1_2-2.pcap"),
        ("E2E-006", {"dedup": False, "anon": True, "mask": True}, "tls_1_2-2.pcap"),
        ("E2E-007", {"dedup": True, "anon": True, "mask": True}, "tls_1_2-2.pcap"),
    ],
)
def test_core_functionality_consistency(...):
    result = self._run_processing(input_path, output_path, config)
```

---

### 2. 协议覆盖测试 (E2E-101 ~ E2E-106)

| 测试ID | 协议 | 输入文件 | dedup | anon | mask | 参数 |
|--------|------|---------|-------|------|------|------|
| E2E-101 | TLS 1.0 | tls_1_0_multi_segment_google-https.pcap | ✅ | ✅ | ✅ | `True, True, True` |
| E2E-102 | TLS 1.2 | tls_1_2-2.pcap | ✅ | ✅ | ✅ | `True, True, True` |
| E2E-103 | TLS 1.3 | tls_1_3_0-RTT-2_22_23_mix.pcap | ✅ | ✅ | ✅ | `True, True, True` |
| E2E-104 | SSL 3.0 | ssl_3.pcap | ✅ | ✅ | ✅ | `True, True, True` |
| E2E-105 | HTTP | http-download-good.pcap | ✅ | ✅ | ✅ | `True, True, True` |
| E2E-106 | HTTP Error | http-500error.pcap | ✅ | ✅ | ✅ | `True, True, True` |

**统一参数**: `dedup=True, anon=True, mask=True` (全功能启用)

**代码位置**:

**CLI黑盒** (`test_e2e_cli_blackbox.py` line 163-190):
```python
@pytest.mark.parametrize(
    "test_id,protocol,input_file",
    [
        ("E2E-101", "TLS 1.0", "tls_1_0_multi_segment_google-https.pcap"),
        ("E2E-102", "TLS 1.2", "tls_1_2-2.pcap"),
        ("E2E-103", "TLS 1.3", "tls_1_3_0-RTT-2_22_23_mix.pcap"),
        ("E2E-104", "SSL 3.0", "ssl_3.pcap"),
        ("E2E-105", "HTTP", "http-download-good.pcap"),
        ("E2E-106", "HTTP Error", "http-500error.pcap"),
    ],
)
def test_cli_protocol_coverage_consistency(...):
    # Line 190: 硬编码全功能参数
    result = self._run_cli_command(cli_executable, input_path, output_path, 
                                    dedup=True, anon=True, mask=True)
```

**API白盒** (`test_e2e_golden_validation.py` line 178-210):
```python
@pytest.mark.parametrize(
    "test_id,protocol,input_file",
    [
        ("E2E-101", "TLS 1.0", "tls_1_0_multi_segment_google-https.pcap"),
        ("E2E-102", "TLS 1.2", "tls_1_2-2.pcap"),
        ("E2E-103", "TLS 1.3", "tls_1_3_0-RTT-2_22_23_mix.pcap"),
        ("E2E-104", "SSL 3.0", "ssl_3.pcap"),
        ("E2E-105", "HTTP", "http-download-good.pcap"),
        ("E2E-106", "HTTP Error", "http-500error.pcap"),
    ],
)
def test_protocol_coverage_consistency(...):
    # Line 200: 硬编码全功能参数
    config = {"dedup": True, "anon": True, "mask": True}
    result = self._run_processing(input_path, output_path, config)
```

**设计原因**:
- 协议覆盖测试的目的是验证不同协议在**全功能启用**时的处理能力
- 确保TLS 1.0/1.2/1.3、SSL 3.0、HTTP等协议都能正确处理
- 全功能启用可以最大程度测试协议处理的完整性

---

### 3. 封装类型测试 (E2E-201 ~ E2E-203)

| 测试ID | 封装类型 | 输入文件 | dedup | anon | mask | 参数 |
|--------|---------|---------|-------|------|------|------|
| E2E-201 | Plain IP | tls_1_2_plainip.pcap | ❌ | ✅ | ✅ | `False, True, True` |
| E2E-202 | Single VLAN | tls_1_2_single_vlan.pcap | ❌ | ✅ | ✅ | `False, True, True` |
| E2E-203 | Double VLAN | tls_1_2_double_vlan.pcap | ❌ | ✅ | ✅ | `False, True, True` |

**统一参数**: `dedup=False, anon=True, mask=True` (不启用去重)

**代码位置**:

**CLI黑盒** (`test_e2e_cli_blackbox.py` line 210-229):
```python
@pytest.mark.parametrize(
    "test_id,encap_type,input_file",
    [
        ("E2E-201", "Plain IP", "tls_1_2_plainip.pcap"),
        ("E2E-202", "Single VLAN", "tls_1_2_single_vlan.pcap"),
        ("E2E-203", "Double VLAN", "tls_1_2_double_vlan.pcap"),
    ],
)
def test_cli_encapsulation_consistency(...):
    # Line 229: 硬编码参数,不启用去重
    result = self._run_cli_command(cli_executable, input_path, output_path, 
                                    dedup=False, anon=True, mask=True)
```

**API白盒** (`test_e2e_golden_validation.py` line 244-260):
```python
@pytest.mark.parametrize(
    "test_id,encap_type,input_file",
    [
        ("E2E-201", "Plain IP", "tls_1_2_plainip.pcap"),
        ("E2E-202", "Single VLAN", "tls_1_2_single_vlan.pcap"),
        ("E2E-203", "Double VLAN", "tls_1_2_double_vlan.pcap"),
    ],
)
def test_encapsulation_consistency(...):
    # Line 256: 硬编码参数,不启用去重
    config = {"dedup": False, "anon": True, "mask": True}
    result = self._run_processing(input_path, output_path, config)
```

**设计原因**:
- 封装类型测试关注网络层封装(Plain IP, Single VLAN, Double VLAN)
- 去重功能与封装类型无关,因此不启用
- 只测试匿名化和掩码对不同封装类型的处理能力
- 减少测试变量,聚焦封装类型本身

---

## 🎯 参数设计原则

### 1. 核心功能测试 (E2E-001 ~ E2E-007)

**目的**: 测试所有功能组合

**策略**: 穷举所有有意义的组合
- 单功能: dedup, anon, mask (3个)
- 双功能: dedup+anon, dedup+mask, anon+mask (3个)
- 全功能: dedup+anon+mask (1个)

**总计**: 7个组合

---

### 2. 协议覆盖测试 (E2E-101 ~ E2E-106)

**目的**: 验证不同协议的处理能力

**策略**: 全功能启用 (`dedup=True, anon=True, mask=True`)

**原因**:
- 协议测试关注协议解析和处理,不关注功能组合
- 全功能启用可以最大程度测试协议处理的完整性
- 简化测试,避免协议×功能组合爆炸

---

### 3. 封装类型测试 (E2E-201 ~ E2E-203)

**目的**: 验证不同封装类型的处理能力

**策略**: 部分功能启用 (`dedup=False, anon=True, mask=True`)

**原因**:
- 封装类型测试关注网络层封装,不关注去重
- 去重功能与封装类型无关
- 启用anon和mask可以测试封装类型对这些功能的影响
- 简化测试,聚焦封装类型本身

---

## 📊 参数一致性验证

### 统计结果

| 测试类别 | 测试数量 | CLI参数 | API参数 | 一致性 |
|---------|---------|---------|---------|--------|
| 核心功能 | 7 | 7种组合 | 7种组合 | ✅ 100% |
| 协议覆盖 | 6 | 全部`T,T,T` | 全部`T,T,T` | ✅ 100% |
| 封装类型 | 3 | 全部`F,T,T` | 全部`F,T,T` | ✅ 100% |
| **总计** | **16** | - | - | ✅ **100%** |

### 验证方法

```python
# 核心功能测试 - 参数直接传递
CLI: result = self._run_cli_command(..., dedup, anon, mask)
API: result = self._run_processing(..., config)

# 协议覆盖测试 - 硬编码全功能
CLI: result = self._run_cli_command(..., dedup=True, anon=True, mask=True)
API: config = {"dedup": True, "anon": True, "mask": True}

# 封装类型测试 - 硬编码部分功能
CLI: result = self._run_cli_command(..., dedup=False, anon=True, mask=True)
API: config = {"dedup": False, "anon": True, "mask": True}
```

---

## 🔧 历史修复记录

### 修复前的问题 (已解决)

**封装类型测试参数错误**:

```python
# CLI黑盒测试 (修复前 - 错误)
result = self._run_cli_command(..., dedup=True, anon=True)  # ❌ 缺少mask参数

# API白盒测试 (一直正确)
config = {"dedup": False, "anon": True, "mask": True}  # ✅ 正确
```

**问题**:
- CLI黑盒测试使用`dedup=True, anon=True, mask=False`
- API白盒测试使用`dedup=False, anon=True, mask=True`
- 参数不一致导致输出哈希不匹配

**修复** (commit 6439113):
```python
# CLI黑盒测试 (修复后 - 正确)
result = self._run_cli_command(..., dedup=False, anon=True, mask=True)  # ✅ 正确
```

**结果**: 所有16个测试通过,参数100%一致

---

## 📝 总结

### 关键发现

1. ✅ **参数完全一致**: CLI黑盒和API白盒测试使用完全相同的参数
2. ✅ **设计合理**: 不同测试类别使用不同参数策略,符合测试目的
3. ✅ **已修复问题**: 之前的参数不一致问题已解决

### 参数策略

| 测试类别 | 参数策略 | 原因 |
|---------|---------|------|
| 核心功能 | 7种组合 | 穷举所有有意义的功能组合 |
| 协议覆盖 | 全功能 (`T,T,T`) | 最大程度测试协议处理能力 |
| 封装类型 | 部分功能 (`F,T,T`) | 聚焦封装类型,排除无关变量 |

### 一致性保证

- ✅ 所有16个测试用例参数100%一致
- ✅ CLI和API使用相同的黄金基准
- ✅ 测试结果可靠,回归验证有效

---

**文档版本**: 1.0  
**创建日期**: 2025-10-09  
**最后更新**: 2025-10-09  
**状态**: 参数100%一致 ✅

