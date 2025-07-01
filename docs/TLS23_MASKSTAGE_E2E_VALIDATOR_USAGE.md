# TLS23 MaskStage E2E Validator 使用指南

> 版本：v1.0 · 适用工具：scripts/validation/tls23_maskstage_e2e_validator.py · 作者：PktMask Core Team

---

## 📖 概述

**TLS23 MaskStage E2E Validator** 是专门用于验证 **Enhanced MaskStage** TLS23掩码功能的端到端测试工具。它与现有的 `tls23_e2e_validator.py`（使用EnhancedTrimmer）并行存在，专门验证新架构的集成效果。

### 🎯 主要特性

- **新架构验证**：专门测试Enhanced MaskStage的TLS23掩码功能
- **双模式支持**：支持通过PipelineExecutor或直接调用MaskStage
- **兼容性验证**：确保Enhanced MaskStage与EnhancedTrimmer功能对等
- **完整报告**：生成JSON和HTML格式的详细验证报告

### 🔄 与原版对比

| 方面 | 原版 (tls23_e2e_validator) | 新版 (tls23_maskstage_e2e_validator) |
|------|---------------------------|-------------------------------------|
| **核心组件** | EnhancedTrimmer | Enhanced MaskStage |
| **调用方式** | 直接调用处理器 | PipelineExecutor + 直接调用 |
| **架构验证** | 旧架构 | 新架构集成 |
| **配置方式** | ProcessorConfig | Pipeline配置 + Stage配置 |
| **输出目录** | `output/tls23_e2e` | `output/tls23_maskstage_e2e` |

---

## 🚀 快速开始

### 1. 前置条件

- PktMask ≥ 3.0 已正确安装
- Enhanced MaskStage 已完成集成（阶段1-3）
- `tshark` 与 `PyShark` 已配置完成
- 项目根目录可访问

### 2. 基本用法

```bash
# 通过PipelineExecutor调用（推荐）
python3 scripts/validation/tls23_maskstage_e2e_validator.py \
  --input-dir tests/data/tls \
  --output-dir output/maskstage_validation \
  --maskstage-mode pipeline \
  --verbose

# 直接调用MaskStage
python3 scripts/validation/tls23_maskstage_e2e_validator.py \
  --input-dir tests/data/tls \
  --output-dir output/maskstage_validation \
  --maskstage-mode direct \
  --verbose
```

### 3. 参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--input-dir` | 必填 | 递归扫描的 PCAP/PCAPNG 输入目录 |
| `--output-dir` | `output/tls23_maskstage_e2e` | 结果与报告输出目录 |
| `--maskstage-mode` | `pipeline` | 调用模式：`pipeline`或`direct` |
| `--glob` | `**/*.pcap,**/*.pcapng` | 文件匹配表达式 |
| `--verbose` | 关闭 | 输出详细调试信息 |

---

## 🔧 调用模式详解

### Pipeline模式（推荐）

```python
# 通过PipelineExecutor调用，验证完整集成
config = {
    "dedup": {"enabled": False},
    "anon": {"enabled": False}, 
    "mask": {
        "enabled": True,
        "mode": "enhanced",
        "preserve_ratio": 0.3,
        "tls_strategy_enabled": True,
        "enable_tshark_preprocessing": True
    }
}
executor = PipelineExecutor(config)
stats = executor.run(input_path, output_path)
```

**优势**：
- 验证PipelineExecutor集成
- 测试完整的配置传播
- 符合新架构设计理念

### Direct模式

```python
# 直接调用MaskStage，测试Stage独立功能
config = {
    "mode": "enhanced",
    "preserve_ratio": 0.3,
    "tls_strategy_enabled": True,
    "enable_tshark_preprocessing": True
}
mask_stage = MaskStage(config)
mask_stage.initialize()
stats = mask_stage.process_file(input_path, output_path)
```

**优势**：
- 测试MaskStage独立功能
- 隔离组件问题
- 性能基准测试

---

## 📊 输出报告

### JSON报告格式

```json
{
  "overall_pass_rate": 100.0,
  "maskstage_mode": "pipeline",
  "test_metadata": {
    "validator_version": "v1.0",
    "component": "Enhanced MaskStage",
    "vs_original": "EnhancedTrimmer E2E Validator"
  },
  "files": [
    {
      "file": "sample_tls.pcap",
      "status": "pass",
      "maskstage_mode": "pipeline",
      "records_before": 12,
      "records_after": 12,
      "total_records": 12,
      "masked_records": 12,
      "unmasked_records": 0,
      "masked_ok_frames": [1,2,3,4,5,6,7,8,9,10,11,12],
      "failed_frames": [],
      "failed_frame_details": []
    }
  ]
}
```

### HTML报告特性

- 📊 可视化测试结果表格
- 🎯 调用模式和组件信息展示
- 🔍 失败帧详细信息
- 📈 总体通过率醒目显示

---

## 🧪 典型使用场景

### 1. 功能对等验证

```bash
# 先运行原版EnhancedTrimmer验证
python3 scripts/validation/tls23_e2e_validator.py \
  --input-dir tests/data/tls \
  --output-dir output/enhanced_trimmer_baseline

# 再运行MaskStage验证进行对比
python3 scripts/validation/tls23_maskstage_e2e_validator.py \
  --input-dir tests/data/tls \
  --output-dir output/maskstage_comparison \
  --maskstage-mode pipeline
```

### 2. 架构集成测试

```bash
# 测试PipelineExecutor集成
python3 scripts/validation/tls23_maskstage_e2e_validator.py \
  --input-dir tests/data/tls \
  --maskstage-mode pipeline \
  --verbose

# 测试直接调用功能
python3 scripts/validation/tls23_maskstage_e2e_validator.py \
  --input-dir tests/data/tls \
  --maskstage-mode direct \
  --verbose
```

### 3. 性能基准测试

```bash
# 运行详细性能分析
python3 scripts/validation/tls23_maskstage_e2e_validator.py \
  --input-dir tests/data/tls \
  --maskstage-mode pipeline \
  --verbose \
  --output-dir output/performance_baseline
```

---

## ⚡ 性能和调优

### 建议的验证流程

1. **快速验证**：使用小样本集先验证基本功能
2. **全量测试**：使用完整样本集进行全面验证
3. **性能对比**：与EnhancedTrimmer结果进行对比
4. **回归测试**：在CI/CD中集成自动验证

### 常见问题解决

- **导入错误**：确保Enhanced MaskStage已正确集成
- **配置问题**：检查TShark/PyShark依赖是否完整
- **性能差异**：对比两种调用模式的性能特征

---

## 🤝 CI/CD集成

### GitHub Actions示例

```yaml
- name: TLS23 MaskStage E2E Validation
  run: |
    python3 scripts/validation/tls23_maskstage_e2e_validator.py \
      --input-dir tests/data/tls \
      --output-dir output/ci_validation \
      --maskstage-mode pipeline \
      --verbose
```

### 退出码

- `0`：全部文件验证通过
- `1`：至少1个文件验证失败
- `2`：输入目录无匹配文件
- `3`：运行时异常

---

## 📈 路线图

### v1.1 计划特性

- [ ] 并行处理支持（`--parallel N`）
- [ ] 更详细的性能指标收集
- [ ] 与原版验证器的结果自动对比
- [ ] 支持阈值配置（允许少量失败）

### v1.2 计划特性

- [ ] 集成到pytest测试框架
- [ ] 支持自定义验证规则
- [ ] 更丰富的HTML报告

---

## 📞 支持

- **文档**：本文档和相关API文档
- **问题报告**：通过项目Issue跟踪
- **性能对比**：参考Enhanced MaskStage性能报告

---

**版权声明**：© 2025 PktMask Core Team. 保留所有权利。 