# 变更日志

## v0.2.1 (2025-07-15)

### 🐛 关键Bug修复

#### 架构重构后功能修复
- **修复 NewMaskPayloadStage 构造函数缺陷** - 添加缺失的 `self.config` 属性初始化
- **修复 PipelineExecutor 输出路径错误** - 纠正返回 `current_input` 而非 `output_path` 的问题
- **修复缺失的 validate_inputs 方法** - 用内联验证替换不存在的方法调用
- **修复 IP匿名化变量作用域错误** - 解决 `encap_adapter` 变量访问超出作用域的问题
- **修复 TrimmingResult 类未定义问题** - 统一类名映射，添加向后兼容别名

#### 功能恢复验证
- ✅ **MaskStage 功能完全恢复** - Basic和Enhanced模式均正常工作
- ✅ **IP匿名化功能完全恢复** - 层次化匿名化策略正常运行
- ✅ **完整Pipeline正常工作** - 去重+匿名化+掩码全流程验证通过
- ✅ **输出文件正确生成** - 所有处理结果文件正常输出

#### 性能表现
- **处理能力**: 101个数据包处理正常
- **掩码效率**: 59个数据包载荷成功掩码
- **匿名化效率**: 2个IP地址成功匿名化
- **总体耗时**: 完整Pipeline约1.5秒

### 📚 文档更新
- 新增 [架构重构后Bug修复报告](../architecture/POST_MIGRATION_BUG_FIXES_REPORT.md)
- 更新 [遗留架构移除报告](../architecture/LEGACY_ARCHITECTURE_REMOVAL_REPORT.md)
- 完善错误诊断和修复流程文档

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
- 新增完整的向后兼容性文档
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
- 新增架构设计决策文档
- 完善 API 参考文档
- 更新用户迁移指南
- 增加故障排除指南

#### 代码质量
- 统一代码风格和命名规范
- 简化调试流程，提升可维护性
- 优化日志记录和错误信息

### ⚠️ 废弃警告

以下配置项已废弃并移除：
- `recipe_path` → 已移除，现在使用 `processor_adapter` 模式进行智能协议分析
- `recipe_dict` → 仍支持，但推荐使用智能协议分析

### 📋 兼容性矩阵

| 组件 | v0.1.0 | v0.2.0 | 建议迁移 |
|------|---------|---------|----------|
| MaskStage API | ✅ | ✅ | 无需变更 |
| CLI 接口 | ✅ | ✅ | 推荐使用 `--mode processor_adapter` |
| GUI 界面 | ✅ | ✅ 自动更新 | 无需变更 |
| 配置文件 | ✅ | ⚠️ 废弃警告 | 参考迁移指南 |

---

## v0.1.0 (历史版本)

### 代码清理
- 移除过时的 PySharkAnalyzer 实现与相关测试脚本
  - 已完全移除旧的 PySharkAnalyzer 类实现
  - 删除相关的测试文件和脚本
  - 用户应迁移到 EnhancedPySharkAnalyzer，详见 [迁移指南](../user/PYSHARK_ANALYZER_MIGRATION_GUIDE.md)

### 技术改进
- 简化代码架构，提升系统稳定性
- 统一使用 EnhancedPySharkAnalyzer 进行协议分析
- 保持 API 向后兼容性

