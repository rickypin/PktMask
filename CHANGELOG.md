## [Unreleased]

### Removed
- **Deprecated Files Cleanup** (2025-07-15)
  - **Cleanup Description**: Comprehensive cleanup of deprecated proxy files, temporary scripts, and obsolete configuration files to reduce technical debt and improve codebase maintainability.
  - **Files Removed**:
    - **Backward Compatibility Proxy Files** (3 files, 67 lines):
      - `src/pktmask/core/encapsulation/adapter.py` - Migrated to `pktmask.adapters.encapsulation_adapter`
      - `src/pktmask/domain/adapters/statistics_adapter.py` - Migrated to `pktmask.adapters.statistics_adapter`
      - `run_gui.py` - Replaced by unified entry point `python -m pktmask`
    - **Temporary Debug Scripts** (5 files, 1,006 lines):
      - `test_log_fix.py`, `code_stats.py`, `detailed_stats.py` - One-time analysis scripts
      - `deprecated_files_analyzer.py`, `project_cleanup_analyzer.py` - Cleanup analysis tools
    - **Obsolete Configuration** (1 file, 39 lines):
      - `config/default/mask_config.yaml` - Legacy dual-module architecture config
    - **Historical Output Files** (46 files, 8.7MB):
      - `output/` directory - TLS analysis reports and validation data
  - **Code Cleanup**:
    - Removed legacy architecture comment in `src/pktmask/core/processors/registry.py`
  - **Impact**:
    - **Files Cleaned**: 55 files total
    - **Code Reduced**: 1,112 lines
    - **Disk Space Saved**: ~8.8MB
    - **Technical Debt**: Significantly reduced
  - **Safety Measures**: All important files were backed up during cleanup process
  - **Compatibility**: No functional impact, all core features preserved

### Changed
- **PayloadMasker Default Full Masking Strategy** (2025-07-15)
  - **Change Description**: Modified PayloadMasker module's default processing logic to implement "mask by default" strategy, ensuring all TCP payloads undergo masking processing, significantly enhancing data security.
  - **Core Changes**:
    - Removed "return as-is when no matching rules" logic, changed to default full masking processing
    - For any TCP payload, first create zero buffer, then selectively preserve only according to rules in KeepRuleSet
    - Non-TLS protocol TCP payloads (such as HTTP, SSH, FTP, etc.) are now completely masked instead of preserved as-is
  - **Modified File**: `src/pktmask/core/pipeline/stages/mask_payload_v2/masker/payload_masker.py`
  - **Key Modifications**:
    ```python
    # Before: Return as-is when no rules
    if stream_id not in rule_lookup or direction not in rule_lookup[stream_id]:
        return packet, False  # ❌ Return as-is, sensitive data exposed

    # After: Execute full masking when no rules
    if stream_id in rule_lookup and direction in rule_lookup[stream_id]:
        rule_data = rule_lookup[stream_id][direction]
    else:
        rule_data = {'header_only_ranges': [], 'full_preserve_ranges': []}
        # Will result in full masking processing
    ```
  - **Security Enhancements**:
    - **HTTP Protocol**: Usernames, passwords, API keys and other sensitive information are now completely masked
    - **SSH Protocol**: Version information, configuration information no longer leaked
    - **Database Protocols**: SQL queries, data content and other sensitive information protected
    - **Custom Protocols**: Business logic, configuration information protected
  - **Processing Strategy Changes**:
    - **Before**: "Default allow" - Only TLS traffic processed, other protocols completely preserved
    - **After**: "Default deny" - All TCP payloads masked by default, only data explicitly in KeepRuleSet preserved
  - **Verification Results**:
    - Non-TLS protocol payloads: From original plaintext → Complete masking (all zeros)
    - TLS protocol payloads: Selective preservation according to preservation rules (behavior unchanged)
    - Statistics: Correctly reflect masked bytes and preserved bytes
    - Modified packet count: Now includes all processed TCP payloads
  - **Compatibility**: Maintains existing TLS processing logic, rule priority strategy and interface signatures completely unchanged

### Fixed
- **TLS-23 Message Masking Inconsistency Issue** (2025-07-14)
  - **Problem Description**: GUI interface and command line scripts produce inconsistent masking results when processing multiple TLS files. In multi-file scenarios, GUI can only correctly mask a few files, most files' TLS-23 message bodies are not masked, while command line scripts can correctly mask all files.
  - **Root Cause**: `PayloadMasker` has state pollution issues during multi-file processing. GUI uses `PipelineExecutor` to reuse the same `NewMaskPayloadStage` instance to process multiple files, causing the following state variables to be reused between files:
    - `self.flow_directions = {}` - Flow direction identification state
    - `self.stream_id_cache = {}` - Stream ID cache
    - `self.tuple_to_stream_id = {}` - Tuple to stream ID mapping
    - `self.flow_id_counter` - Stream ID counter
  - **Fix Solution**: Add `_reset_processing_state()` method at the beginning of `PayloadMasker.apply_masking()` method to ensure all variables that could cause state pollution are reset when processing each file.
  - **修复代码**: 在`src/pktmask/core/pipeline/stages/mask_payload_v2/masker/payload_masker.py`中添加：
    ```python
    def _reset_processing_state(self) -> None:
        """重置处理状态以避免多文件处理时的状态污染"""
        self.logger.debug("重置PayloadMasker处理状态")

        # 重置流方向识别状态
        self.flow_directions.clear()
        self.stream_id_cache.clear()
        self.tuple_to_stream_id.clear()

        # 重置流ID计数器
        self.flow_id_counter = 0

        # 清除当前统计信息引用
        self._current_stats = None
    ```
  - **验证结果**: 修复后GUI多文件处理与命令行脚本结果完全一致。关键测试文件`ssl_3.pcap`从修改0个包恢复到正确修改59个包，所有12个测试文件均能正确处理。

- **GUI配置结构不匹配问题** (2025-07-14)
  - **问题描述**: GUI界面的TLS协议配置无法被TLSProtocolMarker正确读取，导致用户在GUI中设置的TLS消息处理策略（如application_data保留选项）被完全忽略，系统总是使用硬编码的默认值。
  - **根本原因**: `src/pktmask/services/pipeline_service.py`中的`build_pipeline_config()`函数生成的配置结构缺少`preserve`嵌套层级。TLSProtocolMarker期望配置格式为`marker_config.preserve.{配置项}`，但GUI生成的是`marker_config.{配置项}`的扁平结构。
  - **配置结构对比**:
    ```python
    # 修复前（❌ 错误 - 配置被忽略）
    "marker_config": {
        "application_data": False,  # 直接在顶层，无法被读取
        "handshake": True,
        # ...
    }

    # 修复后（✅ 正确 - 配置正确生效）
    "marker_config": {
        "preserve": {                    # TLSProtocolMarker期望的嵌套结构
            "application_data": False,   # 用户配置能被正确读取
            "handshake": True,
            "alert": True,
            "change_cipher_spec": True,
            "heartbeat": True
        }
    }
    ```
  - **修复方案**: 在`build_pipeline_config()`函数中为`marker_config`添加正确的`preserve`嵌套层级，确保配置结构与TLSProtocolMarker的解析逻辑匹配。
  - **功能影响**: 修复前用户的所有TLS配置选择都被忽略，修复后用户可以真正控制各种TLS消息类型的处理策略。这是从"配置无效"到"配置有效"的根本性功能修复。
  - **验证结果**: 通过测试确认TLSProtocolMarker能正确读取GUI配置，用户设置的`application_data`等参数能够正确生效。同时更新了相关测试文件以匹配修复后的配置结构。

### Changed
- Unified entry point: All features accessible through `pktmask` command
- GUI becomes default mode (launch without parameters)
- CLI commands simplified (removed `cli` prefix)
- Centralized dependency management: Removed sub-package independent configs, unified with top-level `pyproject.toml`

### Added
- Added `performance` optional dependency group: Contains `psutil` and `memory-profiler`
- Sub-package `tcp_payload_masker`'s `typing-extensions` dependency merged to main project

### Removed
- Removed `src/pktmask/core/tcp_payload_masker/requirements.txt`
- Removed `src/pktmask/core/tcp_payload_masker/setup.py`

### Deprecated
- `run_gui.py` deprecated, please use `./pktmask` or `python pktmask.py`
- Direct execution of `src/pktmask/cli.py` no longer supported

### Migration Guide
- GUI users: Use `./pktmask` instead of `python run_gui.py`
- CLI users: Commands are more concise, e.g., `./pktmask mask` instead of previous calling methods
- Developers: Sub-package dependencies now managed by top-level, use `pip install -e ".[dev,performance]"` to install all dependencies

---

# PktMask Changelog

## v0.2.1 (2025-07-08)

### 🏗️ 命名统一重构

#### 统一模块命名规范
- **重命名**: `src/pktmask/steps/` → `src/pktmask/stages/`
- **类名统一**: 所有处理单元类名从 `*Step` 更改为 `*Stage`
  - `DeduplicationStep` → `DeduplicationStage`
  - `IpAnonymizationStep` → `IpAnonymizationStage`
  - `IntelligentTrimmingStep` → `IntelligentTrimmingStage`

#### 架构迁移状态（更新说明）
**重要澄清**: 当前项目处于部分迁移状态，并非完全统一到StageBase架构

- ✅ **已迁移**: 载荷掩码功能（NewMaskPayloadStage → StageBase）
- 🔄 **待迁移**: IP匿名化和去重功能（仍使用BaseProcessor架构）
- 🔧 **桥接机制**: ProcessorRegistry提供统一访问接口

#### 当前推荐使用方式
```python
# 推荐：通过PipelineExecutor统一访问
from pktmask.core.pipeline.executor import PipelineExecutor

config = {
    'anonymize_ips': {'enabled': True},    # BaseProcessor系统
    'remove_dupes': {'enabled': True},     # BaseProcessor系统
    'mask_payloads': {'enabled': True}     # StageBase系统
}

executor = PipelineExecutor(config)  # 自动处理新旧架构差异
```

#### 影响范围
- ✅ 载荷掩码功能完全迁移到双模块架构
- 🔄 IP匿名化和去重功能保持BaseProcessor架构
- 🔧 ProcessorRegistry提供新旧系统的统一桥接
- 📋 为完整架构统一奠定基础

---

## v0.2.0 (2025-01-27)

### 🏗️ 架构重构与简化

#### MaskStage 架构简化
- 移除 BlindPacketMasker 中间层，直接使用 MaskingRecipe 进行数据包处理
- 简化 Basic 模式执行流程，减少 30-40% 相关代码量
- 提升执行效率 5-10%，降低内存消耗
- 统一错误处理逻辑，简化降级到透传模式的流程

#### 处理器架构优化（状态更新）
**澄清**: ProcessorStageAdapter已被移除，当前使用混合架构
- ✅ 移除 ProcessorStageAdapter 适配层
- ✅ 载荷掩码迁移到StageBase架构（NewMaskPayloadStage）
- 🔄 IP匿名化和去重保持BaseProcessor架构
- 🔧 ProcessorRegistry作为新旧系统桥接层

### 🔄 向后兼容性改进

#### 配置系统现代化
- 废弃 `recipe_dict` 和 `recipe_path` 配置项（保持兼容，发出警告）
- 引入 `processor_adapter` 智能模式作为推荐配置方式
- 支持直接传入 `MaskingRecipe` 对象的编程接口
- 保持所有公共 API 签名不变

#### 迁移支持
- 新增完整的向后兼容性文档 ([docs/development/BACKWARD_COMPATIBILITY.md](docs/development/BACKWARD_COMPATIBILITY.md))
- 提供详细的迁移指南和示例
- 保留废弃功能的透明降级机制

### 🧪 测试与验证增强

#### TLS 协议处理改进
- 完善跨数据包 TLS 记录处理
- 增强多段 TLS 握手和加密数据掩码
- 优化 TLS 1.0-1.3 和 SSL 3.0 协议支持
- 新增边界条件和异常情况处理

#### 测试覆盖率提升
- 新增 E2E 端到端测试套件
- 完善单元测试和集成测试
- 增加性能基准测试
- 实施回归测试机制

### 🛠️ 开发体验改进

#### 文档完善
- 新增架构设计决策文档 ([docs/development/MASK_STAGE_SIMPLIFICATION.md](docs/development/MASK_STAGE_SIMPLIFICATION.md))
- 完善 API 参考文档
- 更新用户迁移指南
- 增加故障排除指南

#### 代码质量
- 统一代码风格和命名规范
- 简化调试流程，提升可维护性
- 优化日志记录和错误信息

### ⚠️ 破坏性变更和废弃警告

以下配置项已废弃，将在 v1.0.0 版本中移除：

#### 配置简化
- 移除了所有废弃的配置参数和兼容性层
- 统一使用TSharkEnhancedMaskProcessor进行智能协议分析
- 简化了CLI参数，专注于核心功能

#### 使用方式

**CLI 用户**:
```bash
# 标准掩码处理
pktmask mask input.pcap -o output.pcap --mode enhanced

# 组合处理（Remove Dupes + Anonymize IPs + Mask Payloads）
pktmask mask input.pcap -o output.pcap --dedup --anon --mode enhanced
```

**编程接口用户**:
```python
# 推荐配置
config = {
    "mask": {
        "enabled": True,
        "mode": "enhanced"
    }
}
```

### 📋 兼容性矩阵

| 组件 | v0.1.0 | v0.2.0 | 建议迁移 |
|------|---------|---------|----------|
| MaskStage API | ✅ | ✅ | 无需变更 |
| CLI 接口 | ✅ | ✅ | 推荐使用 `--mode processor_adapter` |
| GUI 界面 | ✅ | ✅ 自动更新 | 无需变更 |
| 配置文件 | ✅ | ⚠️ 废弃警告 | 参考 [向后兼容性文档](docs/development/BACKWARD_COMPATIBILITY.md) |

### 🔗 相关文档

- [向后兼容性说明](docs/development/BACKWARD_COMPATIBILITY.md)
- [MaskStage 简化设计决策](docs/development/MASK_STAGE_SIMPLIFICATION.md)
- [PySharkAnalyzer 迁移指南](docs/user/PYSHARK_ANALYZER_MIGRATION_GUIDE.md)

---

## v0.1.0 (历史版本)

### 代码清理
- 移除过时的 PySharkAnalyzer 实现与相关测试脚本
  - 已完全移除旧的 PySharkAnalyzer 类实现
  - 删除相关的测试文件和脚本
  - 用户应迁移到 EnhancedPySharkAnalyzer，详见 [迁移指南](docs/user/PYSHARK_ANALYZER_MIGRATION_GUIDE.md)

### 技术改进
- 简化代码架构，提升系统稳定性
- 统一使用 EnhancedPySharkAnalyzer 进行协议分析
- 保持 API 向后兼容性
