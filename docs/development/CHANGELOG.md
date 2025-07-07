# 变更日志

## 最新变更

### 代码清理
- 移除过时的 PySharkAnalyzer 实现与相关测试脚本
  - 已完全移除旧的 PySharkAnalyzer 类实现
  - 删除相关的测试文件和脚本
  - 用户应迁移到 EnhancedPySharkAnalyzer，详见 [迁移指南](../user/PYSHARK_ANALYZER_MIGRATION_GUIDE.md)

### 技术改进
- 简化代码架构，提升系统稳定性
- 统一使用 EnhancedPySharkAnalyzer 进行协议分析
- 保持 API 向后兼容性

