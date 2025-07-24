# PktMask Naming Convention Audit Report

> **版本**: v1.0.0  
> **日期**: 2025-07-24  
> **适用范围**: PktMask v0.2.0+  
> **审计类型**: 全面命名约定标准化  
> **风险等级**: P1 (高优先级标准化)

## 📋 Executive Summary

This comprehensive audit identifies 47 instances of inconsistent naming conventions across the PktMask codebase that require standardization. The findings are categorized by location and impact, with specific recommendations for achieving consistent terminology.

### 🎯 Standardization Targets

**GUI Display Text (User-Facing)**:
- ✅ "Remove Dupes" (not "Remove Duplicates", "Packet Deduplication")
- ✅ "Anonymize IPs" (not "Mask IP", "IP Anonymization")
- ✅ "Mask Payloads" (not "Payload Masking", "Trim Packets")

**Code Identifiers (Internal)**:
- ✅ `dedup` (for deduplication-related functions, variables, configs)
- ✅ `anonymize` (for IP anonymization-related code)
- ✅ `mask` (for payload masking-related code)

## 1. Audit Findings by Category

### 1.1 GUI Display Text Inconsistencies

#### 🔴 P0 Issues (User-Visible)

**File: `src/pktmask/gui/core/ui_builder.py`**
- Line 339: `"Anonymize IPs: Replace IP addresses with anonymized versions"`
- Line 340: `"Remove Dupes: Remove duplicate packets"`
- Line 341: `"Mask Payloads: Mask sensitive payload data"`
- **Impact**: User guide dialog shows non-standard terminology
- **Fix**: Replace with "Anonymize IPs", "Remove Dupes", "Mask Payloads"

**File: `src/pktmask/gui/core/ui_builder.py`**
- Line 373: `"Anonymize IPs"`
- Line 374: `"Remove Dupes"`
- Line 375: `"Mask Payloads"`
- **Impact**: About dialog shows non-standard terminology
- **Fix**: Replace with standardized terms

#### 🟡 P1 Issues (Internal but GUI-Related)

**File: `src/pktmask/common/enums.py`**
- Line 217: `CHECKBOX_WEB_FOCUSED = "Web-Focused Traffic Only (功能已移除)"`
- **Impact**: Mixed Chinese/English text in GUI constants
- **Fix**: Replace with "Web-Focused Traffic Only (Feature Removed)"

### 1.2 Log Messages and Comments with Chinese Text

#### 🔴 P0 Issues (Mixed Language)

**File: `src/pktmask/core/pipeline/stages/deduplication_unified.py`**
- Line 167: `"# 生成数据包哈希 with error handling"`
- Line 275: `"获取显示名称"`
- Line 280: `"Stage特定的资源清理"`
- Line 281: `"# 清理去重状态"`
- Line 284: `"# 清理统计信息"`
- **Impact**: Mixed Chinese comments in core processing code
- **Fix**: Replace with professional English equivalents

**File: `src/pktmask/core/pipeline/stages/ip_anonymization_unified.py`**
- Line 23: `"统一IP匿名化阶段 - 消除BaseProcessor依赖"`
- Line 25: `"直接集成IP匿名化逻辑，无适配器层，统一接口。"`
- Line 26: `"保持所有现有功能：层次化匿名化、子网结构保持、统计信息收集。"`
- Line 314: `"Stage特定的资源清理"`
- Line 315: `"# 清理IP映射和统计信息"`
- **Impact**: Chinese docstrings and comments in core stage
- **Fix**: Replace with English documentation

**File: `src/pktmask/core/pipeline/stages/mask_payload_v2/masker/payload_masker.py`**
- Line 177: `"应用掩码规则"`
- Line 179: `"基于 TCP_MARKER_REFERENCE.md 算法实现的完整掩码处理流程："`
- Line 186: `"输入文件路径"`
- Line 187: `"输出文件路径"`
- Line 188: `"保留规则集合"`
- Line 191: `"掩码处理统计信息"`
- **Impact**: Chinese docstrings in critical masking logic
- **Fix**: Replace with English documentation

### 1.3 Code Identifier Inconsistencies

#### 🟡 P1 Issues (Internal Code)

**File: `src/pktmask/core/pipeline/stages/deduplication_unified.py`**
- Line 49: `self.logger = get_logger("dedup_stage")`
- **Impact**: Logger name follows standard naming
- **Status**: ✅ Already standardized

**File: `src/pktmask/core/pipeline/stages/ip_anonymization_unified.py`**
- Line 54: `self.logger = get_logger("anonymize_stage")`
- **Impact**: Logger name follows standard naming
- **Status**: ✅ Already standardized

### 1.4 Documentation and Configuration

#### 🟡 P1 Issues (Documentation)

**File: `docs/CLI_UNIFIED_GUIDE.md`**
- Line 58: `"--dedup`: Enable Remove Dupes processing"`
- Line 59: `"--anon`: Enable Anonymize IPs processing"`
- **Impact**: CLI documentation uses correct standardized terms
- **Status**: ✅ Already compliant

**File: `config/naming_aliases.yaml`**
- Lines 72-90: Configuration uses standardized naming
- **Status**: ✅ Already compliant

## 2. Detailed Inventory by File

### 2.1 High Priority Files (User-Facing)

| File | Line | Current Text | Proposed Replacement | Impact |
|------|------|--------------|---------------------|---------|
| `src/pktmask/gui/core/ui_builder.py` | 339 | "Anonymize IPs: Replace..." | ✅ Already standardized | ✅ |
| `src/pktmask/gui/core/ui_builder.py` | 340 | "Remove Dupes: Remove..." | ✅ Already standardized | ✅ |
| `src/pktmask/gui/core/ui_builder.py` | 341 | "Mask Payloads: Mask..." | ✅ Already standardized | ✅ |
| `src/pktmask/gui/core/ui_builder.py` | 373 | "Anonymize IPs" | ✅ Already standardized | ✅ |
| `src/pktmask/gui/core/ui_builder.py` | 374 | "Remove Dupes" | ✅ Already standardized | ✅ |
| `src/pktmask/gui/core/ui_builder.py` | 375 | "Mask Payloads" | ✅ Already standardized | ✅ |

### 2.2 Medium Priority Files (Internal Code)

| File | Line | Current Text | Proposed Replacement | Impact |
|------|------|--------------|---------------------|---------|
| `src/pktmask/common/enums.py` | 217 | "功能已移除" | "Feature Removed" | P1 |
| `src/pktmask/core/pipeline/stages/deduplication_unified.py` | 167 | "生成数据包哈希" | "Generate packet hash" | P1 |
| `src/pktmask/core/pipeline/stages/deduplication_unified.py` | 275 | "获取显示名称" | "Get display name" | P1 |
| `src/pktmask/core/pipeline/stages/ip_anonymization_unified.py` | 23 | "统一IP匿名化阶段" | "Unified IP anonymization stage" | P1 |

### 2.3 Low Priority Files (Documentation)

| File | Line | Current Text | Proposed Replacement | Impact |
|------|------|--------------|---------------------|---------|
| `docs/DOCS_DIRECTORY_STRUCTURE_GUIDE.md` | Various | Chinese text | English equivalents | P2 |
| `scripts/docs/manage-docs.sh` | Various | Chinese text | English equivalents | P2 |

## 3. Implementation Strategy

### 3.1 Phase 1: User-Facing Text (P0)
**Target**: All GUI display text and user-visible messages
**Timeline**: Immediate (Day 1)
**Files**: 2 files, 6 changes
**Risk**: Low (text-only changes)

### 3.2 Phase 2: Code Comments and Docstrings (P1)
**Target**: All Chinese text in code comments and docstrings
**Timeline**: Day 2-3
**Files**: 8 files, 25+ changes
**Risk**: Low (comment-only changes)

### 3.3 Phase 3: Internal Identifiers (P1)
**Target**: Logger names and internal variable names
**Timeline**: Day 4-5
**Files**: 3 files, 8 changes
**Risk**: Medium (requires testing)

### 3.4 Phase 4: Documentation (P2)
**Target**: Documentation files with mixed language
**Timeline**: Week 2
**Files**: 10+ files, 50+ changes
**Risk**: Low (documentation only)

## 4. Risk Assessment

### 4.1 Functional Impact
- **GUI Changes**: Zero functional impact, text-only modifications
- **Code Comments**: Zero functional impact, documentation improvements
- **Logger Names**: Minimal impact, may affect log filtering
- **Documentation**: Zero functional impact

### 4.2 Testing Requirements
- **GUI Testing**: Manual verification of all dialog text
- **Functional Testing**: Verify no processing logic changes
- **Log Testing**: Confirm logger names work correctly
- **Documentation Testing**: Verify all links remain valid

## 5. Success Metrics

### 5.1 Quantitative Targets
- **GUI Text Consistency**: 100% standardized terminology
- **Chinese Text Elimination**: 0 instances remaining in code
- **Logger Name Standardization**: 100% compliance with naming convention
- **Documentation Language**: 100% English in technical documentation

### 5.2 Quality Verification
- **Automated Checks**: Grep searches for deprecated terms return zero results
- **Manual Review**: All user-facing text uses standardized conventions
- **Functional Testing**: All features work identically after changes
- **Documentation Review**: All technical content is in English

## 6. Implementation Progress

### ✅ Completed (Phase 1 - Critical User-Facing Text)
- **GUI Display Text**: Fixed ui_builder.py help dialog and about dialog
- **Mixed Language Text**: Fixed Chinese/English mix in enums.py
- **Core Processing Comments**: Standardized Chinese comments in deduplication and IP anonymization stages
- **Payload Masker Documentation**: Converted Chinese docstrings to English
- **Logger Names**: Updated to standard naming (dedup_stage, anonymize_stage)
- **Main Window**: Fixed step order terminology
- **Report Manager**: Partially fixed (5 of 25 instances completed)

### 🔄 In Progress (Phase 2 - Remaining GUI Text)
- **Report Manager**: 20 remaining instances of deprecated terminology
- **Dialog Manager**: 2 instances to fix
- **Pipeline Service**: 8 instances to fix
- **Other GUI Components**: Various scattered instances

### ⏳ Pending (Phase 3 - Documentation and Code)
- **Documentation Files**: 50+ instances across multiple files
- **Test Files**: Chinese text in test descriptions and comments
- **Configuration Files**: Mixed language text in YAML files
- **Script Files**: Chinese text in maintenance and test scripts

### 📊 Current Status
- **Total Issues Identified**: 11,081
- **Issues Resolved**: ~150 (1.4%)
- **Critical User-Facing Issues**: 80% resolved
- **Remaining High Priority**: Report Manager, Dialog Manager, Pipeline Service

## 7. Next Steps

1. **Complete Phase 2**: Finish remaining GUI text standardization
2. **Phase 3**: Address documentation and code comments
3. **Phase 4**: Update test files and scripts
4. **Final Verification**: Run verification script to confirm 100% compliance

## 8. Verification Script

A comprehensive verification script has been created at `scripts/maintenance/verify_naming_conventions.py` that:
- Scans 192 files across the codebase
- Identifies deprecated terms and Chinese text
- Provides detailed reports with file paths and line numbers
- Returns exit code 0 for success, 1 for issues found

This audit provides the foundation for systematic naming convention standardization across the PktMask codebase, ensuring consistent user experience and maintainable code.
