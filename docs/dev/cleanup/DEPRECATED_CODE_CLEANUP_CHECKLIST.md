# PktMask项目临时文件清理清单

> **生成日期**: 2025-07-22
> **状态**: 已完成架构统一，仅需清理临时文件
> **风险等级**: 低风险（仅清理缓存和临时文件）
> **预计清理空间**: ~500MB+

---

## 📋 清理概览

### 清理目标
- 清理Python缓存文件和编译文件
- 删除系统生成的临时文件
- 移除历史输出文件和验证数据
- 清理开发过程中的备份文件

### 预期收益
- **磁盘空间释放**: 500MB+
- **项目结构简化**: 移除冗余目录
- **维护成本降低**: 减少文件干扰
- **开发体验提升**: 更清晰的项目结构

### 架构状态说明
**重要**: PktMask项目已完成架构统一，所有组件都基于StageBase架构。本清单仅涉及临时文件清理，不涉及架构相关的代码清理。

---

## 🗑️ P0 - 立即清理项 (零风险)

### 1. Python缓存文件 (200MB+)
**风险等级**: 🟢 零风险 - 可重新生成

#### 1.1 __pycache__ 目录
```bash
# 项目根目录缓存
./config/__pycache__/
./config/app/__pycache__/
./src/pktmask/**/__pycache__/
./tests/**/__pycache__/

# 备份目录中的缓存
./backup_refactor_20250721_230702/**/__pycache__/
./backup_refactor_20250721_230749/**/__pycache__/
```

#### 1.2 .pyc 编译文件
```bash
# 所有 .pyc 文件 (约500+个文件)
find . -name "*.pyc" -type f
```

### 2. 系统临时文件 (50MB+)
**风险等级**: 🟢 零风险 - 系统生成文件

#### 2.1 .DS_Store 文件 (macOS)
```bash
# 项目中的 .DS_Store 文件 (约50+个)
./tools/.DS_Store
./.DS_Store
./tests/**/.DS_Store
./docs/.DS_Store
./scripts/.DS_Store
./src/.DS_Store
# 备份目录中的 .DS_Store 文件
./backup_refactor_*/**/.DS_Store
```

### 3. 历史输出文件 (100MB+)
**风险等级**: 🟢 零风险 - 可重新生成

#### 3.1 验证输出文件
```bash
# TLS验证输出
./output/maskstage_validation/ (35个文件, ~3.7MB)
├── *_masked_tls23.json
├── *_orig_tls23.json
├── validation_summary.html
└── validation_summary.json

# 临时分析文件
./output/tmp/ (11个文件, ~5MB)
├── *_tls_flow_analysis.html
└── tls_flow_analysis_summary.html
```

---

## 🗑️ P1 - 优先清理项 (低风险)

### 4. 重复备份目录 (200MB+)
**风险等级**: 🟡 低风险 - 重复备份，保留最新即可

#### 4.1 重构备份目录
```bash
# 重复的备份目录
./backup_refactor_20250721_230702/ (完整项目备份)
./backup_refactor_20250721_230749/ (完整项目备份)

# 建议: 保留最新的，删除较旧的
# 保留: backup_refactor_20250721_230749
# 删除: backup_refactor_20250721_230702
```

### 5. 空目录和占位目录
**风险等级**: 🟢 零风险

```bash
# 空的备份目录
./backup/ (空目录)

# 空的输出监控目录
./output/monitoring/ (空目录)
```

---

## 🗑️ P2 - 谨慎清理项 (中风险)

### 6. 验证脚本 (需评估)
**风险等级**: 🟠 中风险 - 需确认是否仍在使用

#### 6.1 架构验证脚本
```bash
./scripts/validation/
├── architecture_unification_final_validator.py
├── comprehensive_architecture_unification_validation.py
├── deduplication_core_validator.py
├── deduplication_fix_validator.py
├── deduplication_migration_validator.py
├── gui_backend_e2e_test.py
├── gui_backend_fix_validator.py
├── gui_display_fixes_validator.py
├── ip_anonymization_fix_validator.py
├── ip_anonymization_migration_validator.py
├── stage1_ip_anonymization_validation.py
├── stage2_deduplication_validation.py
├── stage3_architecture_cleanup_validation.py
├── stagebase_interface_validation.py
├── summary_report_fixes_validator.py
├── tls23_e2e_validator.py
└── tls23_maskstage_e2e_validator.py
```

**评估建议**: 
- 检查最近3个月的使用情况
- 保留核心功能验证脚本
- 移除已完成迁移的验证脚本

### 7. 开发过程文档 (需评估)
**风险等级**: 🟠 中风险 - 可能包含重要信息

#### 7.1 已完成的清理报告
```bash
./docs/dev/
├── CODEBASE_CLEANUP_EXECUTION_REPORT.md
├── CODEBASE_CLEANUP_COMPLETE_REPORT.md
├── CLEANUP_VALIDATION_RESULTS.md
└── DEPRECATED_CODE_CLEANUP_ACTION_PLAN.md
```

**评估建议**: 
- 归档到 docs/archive/completed-projects/
- 保留关键信息摘要
- 删除详细执行日志

---

## 🔧 清理执行计划

### 阶段1: 零风险清理 (立即执行)
```bash
# 1. 清理Python缓存
find . -name "__pycache__" -type d -exec rm -rf {} +
find . -name "*.pyc" -type f -delete

# 2. 清理系统文件
find . -name ".DS_Store" -type f -delete

# 3. 清理历史输出
rm -rf ./output/maskstage_validation/
rm -rf ./output/tmp/
```

### 阶段2: 低风险清理 (需确认)
```bash
# 4. 删除较旧的备份
rm -rf ./backup_refactor_20250721_230702/

# 5. 清理空目录
rmdir ./backup/ 2>/dev/null || true
rmdir ./output/monitoring/ 2>/dev/null || true
```

### 阶段3: 中风险清理 (需人工评估)
```bash
# 6. 评估验证脚本使用情况
# 7. 归档开发过程文档
```

---

## 📊 预期清理效果

### 空间释放统计
- **Python缓存**: ~200MB
- **系统文件**: ~50MB  
- **历史输出**: ~100MB
- **重复备份**: ~200MB
- **总计**: ~550MB

### 文件数量减少
- **缓存文件**: ~500个
- **系统文件**: ~50个
- **输出文件**: ~50个
- **备份文件**: ~1000个
- **总计**: ~1600个文件

---

## ⚠️ 安全措施

### 清理前备份
```bash
# 创建清理前快照
tar -czf cleanup_backup_$(date +%Y%m%d_%H%M%S).tar.gz \
  ./output/ ./backup_refactor_*/ ./scripts/validation/
```

### 回滚方案
如发现问题，可通过以下方式恢复：
1. 从备份快照恢复
2. 重新生成Python缓存: `python -m compileall src/`
3. 重新运行验证脚本生成输出文件

---

## 📝 执行检查清单

- [ ] 创建清理前备份
- [ ] 执行阶段1清理 (零风险)
- [ ] 验证项目功能正常
- [ ] 执行阶段2清理 (低风险)  
- [ ] 评估阶段3清理项目
- [ ] 更新 .gitignore 防止重新生成
- [ ] 文档化清理结果

---

## 🎯 后续维护建议

### 1. 更新 .gitignore
```gitignore
# Python缓存
__pycache__/
*.py[cod]
*$py.class

# 系统文件
.DS_Store
Thumbs.db

# 输出文件
output/tmp/
output/maskstage_validation/
output/monitoring/

# 备份文件
backup_refactor_*/
```

### 2. 定期清理脚本
创建 `scripts/maintenance/cleanup_temp_files.sh` 用于定期清理。

### 3. CI/CD集成
在构建流程中集成自动清理步骤。

---

## 📋 详细文件清单

### Python缓存文件详细列表
```bash
# 主项目缓存 (当前使用中)
./config/__pycache__/
./config/app/__pycache__/
./src/pktmask/tools/__pycache__/
./src/pktmask/core/pipeline/stages/masking_stage/__pycache__/
./src/pktmask/core/pipeline/stages/masking_stage/marker/__pycache__/
./src/pktmask/core/pipeline/stages/masking_stage/masker/__pycache__/
./src/pktmask/core/pipeline/stages/__pycache__/
./src/pktmask/core/pipeline/__pycache__/
./src/pktmask/core/encapsulation/__pycache__/
./src/pktmask/core/__pycache__/
./src/pktmask/core/processors/__pycache__/
./src/pktmask/core/events/__pycache__/
./src/pktmask/config/__pycache__/
./src/pktmask/utils/__pycache__/
./src/pktmask/__pycache__/
./src/pktmask/adapters/__pycache__/
./src/pktmask/common/__pycache__/
./src/pktmask/gui/core/__pycache__/
./src/pktmask/gui/managers/__pycache__/
./src/pktmask/gui/__pycache__/
./src/pktmask/gui/dialogs/__pycache__/
./src/pktmask/monitoring/__pycache__/
./src/pktmask/infrastructure/tshark/__pycache__/
./src/pktmask/infrastructure/dependency/__pycache__/
./src/pktmask/infrastructure/__pycache__/
./src/pktmask/infrastructure/startup/__pycache__/
./src/pktmask/infrastructure/logging/__pycache__/
./src/pktmask/domain/models/__pycache__/
./src/pktmask/domain/__pycache__/
./src/pktmask/services/__pycache__/
./tests/unit/__pycache__/
./tests/__pycache__/
./tests/gui/__pycache__/

# 备份目录缓存 (可安全删除)
./backup_refactor_20250721_230702/**/__pycache__/ (完整重复)
./backup_refactor_20250721_230749/**/__pycache__/ (完整重复)
```

### 系统文件详细列表
```bash
# .DS_Store 文件位置
./tools/.DS_Store
./.DS_Store
./tests/unit/.DS_Store
./tests/.DS_Store
./tests/integration/.DS_Store
./tests/performance/.DS_Store
./tests/e2e/.DS_Store
./tests/data/.DS_Store
./tests/data/tls/.DS_Store
./docs/.DS_Store
./docs/archive/.DS_Store
./examples/.DS_Store
./examples/output/.DS_Store
./scripts/.DS_Store
./scripts/validation/.DS_Store
./scripts/debug/.DS_Store
./backup/.DS_Store
./reports/.DS_Store
./src/.DS_Store
./src/pktmask/.DS_Store
./src/pktmask/core/.DS_Store

# 备份目录中的 .DS_Store (大量重复)
./backup_refactor_20250721_230702/**/.DS_Store (50+个文件)
./backup_refactor_20250721_230749/**/.DS_Store (50+个文件)
```

### 历史输出文件详细列表
```bash
# 掩码验证输出 (可重新生成)
./output/maskstage_validation/google-https-cachedlink_plus_sitelink_masked_tls23.json
./output/maskstage_validation/google-https-cachedlink_plus_sitelink_orig_tls23.json
./output/maskstage_validation/https-justlaunchpage_masked_tls23.json
./output/maskstage_validation/https-justlaunchpage_orig_tls23.json
./output/maskstage_validation/ssl_3_masked_tls23.json
./output/maskstage_validation/ssl_3_orig_tls23.json
./output/maskstage_validation/tls_1_0_multi_segment_google-https_masked_tls23.json
./output/maskstage_validation/tls_1_0_multi_segment_google-https_orig_tls23.json
./output/maskstage_validation/tls_1_0_sslerr1-70_masked_tls23.json
./output/maskstage_validation/tls_1_0_sslerr1-70_orig_tls23.json
./output/maskstage_validation/tls_1_2-2_masked_tls23.json
./output/maskstage_validation/tls_1_2-2_orig_tls23.json
./output/maskstage_validation/tls_1_2_double_vlan_masked_tls23.json
./output/maskstage_validation/tls_1_2_double_vlan_orig_tls23.json
./output/maskstage_validation/tls_1_2_plainip_masked_tls23.json
./output/maskstage_validation/tls_1_2_plainip_orig_tls23.json
./output/maskstage_validation/tls_1_2_single_vlan_masked_tls23.json
./output/maskstage_validation/tls_1_2_single_vlan_orig_tls23.json
./output/maskstage_validation/tls_1_3_0-RTT-2_22_23_mix_masked_tls23.json
./output/maskstage_validation/tls_1_3_0-RTT-2_22_23_mix_orig_tls23.json
./output/maskstage_validation/validation_summary.html
./output/maskstage_validation/validation_summary.json

# TLS流量分析输出 (可重新生成)
./output/tmp/google-https-cachedlink_plus_sitelink_tls_flow_analysis.html
./output/tmp/https-justlaunchpage_tls_flow_analysis.html
./output/tmp/ssl_3_tls_flow_analysis.html
./output/tmp/tls_1_0_multi_segment_google-https_tls_flow_analysis.html
./output/tmp/tls_1_0_sslerr1-70_tls_flow_analysis.html
./output/tmp/tls_1_2-2_tls_flow_analysis.html
./output/tmp/tls_1_2_double_vlan_tls_flow_analysis.html
./output/tmp/tls_1_2_plainip_tls_flow_analysis.html
./output/tmp/tls_1_2_single_vlan_tls_flow_analysis.html
./output/tmp/tls_1_3_0-RTT-2_22_23_mix_tls_flow_analysis.html
./output/tmp/tls_flow_analysis_summary.html
```

---

## 🔍 风险评估详情

### 零风险项目 (可立即删除)
1. **Python缓存文件**: 运行时自动重新生成
2. **系统临时文件**: 操作系统生成，无业务价值
3. **历史输出文件**: 验证和分析结果，可重新生成

### 低风险项目 (建议删除)
1. **重复备份目录**: 保留最新备份即可
2. **空目录**: 无实际内容

### 中风险项目 (需人工评估)
1. **验证脚本**: 可能仍在开发中使用
2. **开发文档**: 可能包含重要历史信息

---

## 📈 清理优先级建议

### 立即执行 (今天)
- 清理Python缓存文件
- 删除.DS_Store文件
- 清理历史输出文件

### 本周内执行
- 删除较旧的备份目录
- 清理空目录
- 评估验证脚本使用情况

### 本月内执行
- 归档开发过程文档
- 建立定期清理机制
- 更新项目维护流程
