## [Unreleased]

### Changed
- 统一入口点：所有功能通过 `pktmask` 命令访问
- GUI 成为默认模式（无参数启动）
- CLI 命令简化（移除 `cli` 前缀）
- 依赖管理集中化：移除子包独立配置，统一使用顶层 `pyproject.toml`

### Added
- 新增 `performance` 可选依赖组：包含 `psutil` 和 `memory-profiler`
- 子包 `tcp_payload_masker` 的 `typing-extensions` 依赖已合并到主项目

### Removed
- 移除 `src/pktmask/core/tcp_payload_masker/requirements.txt`
- 移除 `src/pktmask/core/tcp_payload_masker/setup.py`

### Deprecated
- `run_gui.py` 已弃用，请使用 `./pktmask` 或 `python pktmask.py`
- 直接运行 `src/pktmask/cli.py` 已不再支持

### Migration Guide
- GUI 用户：使用 `./pktmask` 替代 `python run_gui.py`
- CLI 用户：命令更简洁，如 `./pktmask mask` 替代之前的调用方式
- 开发者：子包依赖现由顶层管理，使用 `pip install -e ".[dev,performance]"` 安装所有依赖

---

# PktMask 变更日志

## v0.2.1 (2025-07-08)

### 🏗️ 命名统一重构

#### 统一模块命名规范
- **重命名**: `src/pktmask/steps/` → `src/pktmask/stages/`
- **类名统一**: 所有处理单元类名从 `*Step` 更改为 `*Stage`
  - `DeduplicationStep` → `DeduplicationStage`
  - `IpAnonymizationStep` → `IpAnonymizationStage`
  - `IntelligentTrimmingStep` → `IntelligentTrimmingStage`

#### 完全向后兼容
- 保留 `pktmask.steps` 兼容层，现有代码无需修改
- 旧的导入路径会显示弃用警告，但功能完全正常
- 所有现有测试和功能保持100%兼容

#### 开发者迁移建议
```python
# 旧方式（仍可用，显示弃用警告）
from pktmask.steps import DeduplicationStep

# 新方式（推荐）
from pktmask.stages import DeduplicationStage
```

#### 影响范围
- ✅ 解决了 Step vs Stage 概念混淆问题
- ✅ 统一了导入路径命名规范
- ✅ 提升了代码可读性和一致性
- ✅ 为后续架构统一打下基础

---

## v0.2.0 (2025-01-27)

### 🏗️ 架构重构与简化

#### MaskStage 架构简化
- 移除 BlindPacketMasker 中间层，直接使用 MaskingRecipe 进行数据包处理
- 简化 Basic 模式执行流程，减少 30-40% 相关代码量
- 提升执行效率 5-10%，降低内存消耗
- 统一错误处理逻辑，简化降级到透传模式的流程

#### 处理器架构优化
- 引入 ProcessorStageAdapter 统一处理器接口
- 重构 Pipeline 执行器，提升模块化程度
- 优化 CLI 和 GUI 管理器集成

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

# 组合处理
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
